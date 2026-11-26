"""
USE CASES: the STEPS of each user action. No rules here (they are in policies.py, run by the entity).

Every method follows the same steps:
    1. turn the input into value objects   (they check the format: 422)
    2. load the source                     (repository: 404)
    3. fetch the facts a rule needs        (e.g. "is this name taken?")
    4. call ONE entity method              (it checks its rule: 409, then changes the data)
    5. save                                (repository)
    6. publish the events                  (sent only after the commit)

A use case receives plain values (commands, ids) and returns entities, never HTTP objects. It never
commits (the request does) and never checks roles (the router's access check does). Its dependencies
are injected by container.py, so unit tests pass in-memory fakes.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.modules.source_registry.application.ports import EventPublisher, SourcePage, SourceRegistryRepository
from app.modules.source_registry.domain.entities import AcquisitionSource
from app.modules.source_registry.domain.value_objects import (
    SourceDescription,
    SourceName,
    SourceUrl,
    SourceUrlList,
)

Clock = Callable[[], datetime]

_SENTINEL = object()  # marks "field not supplied" in UpdateSourceCommand


def utc_now() -> datetime:
    return datetime.now(UTC)


# ── Commands ───────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RegisterSourceCommand:
    """Input of `register`."""

    name: str
    description: str | None
    source_urls: list[str]
    created_by: UUID


@dataclass(frozen=True, slots=True)
class UpdateSourceCommand:
    """
    Input of `update`: only the fields that are not None change.
    Use the sentinel `_SENTINEL` for description to distinguish "not supplied" from "explicitly null".
    """

    name: str | None = None
    # description=None means "clear it"; description=_SENTINEL means "not supplied"
    description: object = field(default_factory=lambda: _SENTINEL)
    source_urls: list[str] | None = None
    updated_by: UUID | None = None


# ── Use cases ──────────────────────────────────────────────────────────────────────────────────────


class SourceRegistryUseCases:
    def __init__(
        self,
        repository: SourceRegistryRepository,
        events: EventPublisher,
        clock: Clock = utc_now,
    ) -> None:
        self.repository = repository
        self.events = events
        self.clock = clock  # injected so tests can fix the time

    async def register(self, command: RegisterSourceCommand) -> AcquisitionSource:
        name = SourceName(command.name)  # 1. value objects
        description = SourceDescription(command.description)
        urls = SourceUrlList(command.source_urls)
        taken = await self.repository.name_exists(name)  # 3. fact
        source = AcquisitionSource.register(  # 4. entity
            name=name,
            description=description,
            source_urls=urls,
            created_by=command.created_by,
            name_taken=taken,
            at=self.clock(),
        )
        await self.repository.add(source)  # 5. save
        self.events.publish_after_commit(source.pull_events())  # 6. events
        return source

    async def get(self, source_id: UUID) -> AcquisitionSource:
        return await self.repository.get(source_id)

    async def list(
        self,
        *,
        is_enabled: bool | None,
        name_contains: str | None,
        offset: int,
        limit: int,
    ) -> SourcePage:
        return await self.repository.list(
            is_enabled=is_enabled,
            name_contains=name_contains,
            offset=offset,
            limit=limit,
        )

    async def update(self, source_id: UUID, command: UpdateSourceCommand) -> AcquisitionSource:
        source = await self.repository.get(source_id)  # 2. load
        now = self.clock()

        name_vo = SourceName(command.name) if command.name is not None else None  # 1. value objects
        desc_vo = (
            None if command.description is _SENTINEL else SourceDescription(command.description)  # type: ignore[arg-type]
        )
        url_vos = SourceUrlList(command.source_urls) if command.source_urls is not None else None

        name_taken = False
        if name_vo is not None:
            name_taken = await self.repository.name_exists(name_vo, except_id=source.id)  # 3. fact

        updated_by = command.updated_by or source.created_by
        source.update(  # 4. entity (raises SourceNotModified if no-op)
            name=name_vo,
            description=desc_vo,
            source_urls=url_vos,
            updated_by=updated_by,
            name_taken=name_taken,
            at=now,
        )
        return await self._save(source)  # 5+6. save + events

    async def enable(self, source_id: UUID, *, actor_id: UUID) -> AcquisitionSource:
        source = await self.repository.get(source_id)  # 2. load
        source.enable(updated_by=actor_id, at=self.clock())  # 4. entity
        return await self._save(source)

    async def disable(self, source_id: UUID, *, actor_id: UUID) -> AcquisitionSource:
        source = await self.repository.get(source_id)  # 2. load
        source.disable(updated_by=actor_id, at=self.clock())  # 4. entity
        return await self._save(source)

    async def delete(self, source_id: UUID) -> None:
        source = await self.repository.get(source_id)  # 2. load
        source.delete(at=self.clock())  # 4. entity (checks disabled)
        events = source.pull_events()
        await self.repository.delete(source_id)  # 5. save (may raise SourceInUse)
        self.events.publish_after_commit(events)  # 6. events

    async def _save(self, source: AcquisitionSource) -> AcquisitionSource:
        await self.repository.update(source)  # 5. save
        self.events.publish_after_commit(source.pull_events())  # 6. events
        return source
