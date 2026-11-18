"""
USE CASES: the STEPS of each user action. No rules here (they are in policies.py, run by the entity).

Every method follows the same steps:
    1. turn the input into value objects   (they check the format: 422)
    2. load the source registry               (repository: 404)
    3. fetch the facts a rule needs         (e.g. "is this code taken?")
    4. call ONE entity method               (it checks its rule: 409, then changes the data)
    5. save                                  (repository)
    6. publish the events                    (sent only after the commit)

A use case receives plain values (commands, ids) and returns entities, never HTTP objects. It never
commits (the request does) and never checks roles (the router's access check does). Its dependencies
are injected by container.py, so unit tests pass in-memory fakes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.source_registry.application.ports import EventPublisher, SourceRegistryPage, SourceRegistryRepository
from app.modules.source_registry.domain.entities import SourceRegistry
from app.modules.source_registry.domain.value_objects import (
    SourceRegistryCode,
    SourceRegistryName,
    SourceRegistryStatus,
)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateSourceRegistryCommand:
    """Input of `create`."""

    name: str
    code: str


@dataclass(frozen=True, slots=True)
class UpdateSourceRegistryCommand:
    """Input of `update`: only the fields that are not None change."""

    name: str | None = None
    code: str | None = None


class SourceRegistryUseCases:
    def __init__(self, repository: SourceRegistryRepository, events: EventPublisher, clock: Clock = utc_now) -> None:
        self.repository = repository
        self.events = events
        self.clock = clock  # injected so tests can fix the time

    async def create(self, command: CreateSourceRegistryCommand) -> SourceRegistry:
        name, code = SourceRegistryName(command.name), SourceRegistryCode(command.code)  # 1. value objects
        taken = await self.repository.code_exists(code)  # 3. fact
        source_registry = SourceRegistry.create(name=name, code=code, code_taken=taken, at=self.clock())  # 4. entity
        await self.repository.add(source_registry)  # 5. save
        self.events.publish_after_commit(source_registry.pull_events())  # 6. events
        return source_registry

    async def get(self, source_registry_id: UUID) -> SourceRegistry:
        return await self.repository.get(source_registry_id)

    async def list(self, *, status: SourceRegistryStatus | None, offset: int, limit: int) -> SourceRegistryPage:
        return await self.repository.list(status=status, offset=offset, limit=limit)

    async def update(self, source_registry_id: UUID, command: UpdateSourceRegistryCommand) -> SourceRegistry:
        source_registry = await self.repository.get(source_registry_id)  # 2. load
        now = self.clock()
        if command.name is not None:
            source_registry.rename(SourceRegistryName(command.name), at=now)  # 4. entity
        if command.code is not None:
            code = SourceRegistryCode(command.code)
            taken = await self.repository.code_exists(code, except_id=source_registry.id)  # 3. fact
            source_registry.change_code(code, code_taken=taken, at=now)  # 4. entity
        return await self._save(source_registry)

    async def archive(self, source_registry_id: UUID) -> SourceRegistry:
        source_registry = await self.repository.get(source_registry_id)
        source_registry.archive(at=self.clock())
        return await self._save(source_registry)

    async def restore(self, source_registry_id: UUID) -> SourceRegistry:
        source_registry = await self.repository.get(source_registry_id)
        source_registry.restore(at=self.clock())
        return await self._save(source_registry)

    async def delete(self, source_registry_id: UUID) -> None:
        source_registry = await self.repository.get(source_registry_id)
        source_registry.delete()  # the rule: archived first
        await self.repository.delete(source_registry_id)

    async def _save(self, source_registry: SourceRegistry) -> SourceRegistry:
        await self.repository.update(source_registry)  # 5. save
        self.events.publish_after_commit(source_registry.pull_events())  # 6. events
        return source_registry
