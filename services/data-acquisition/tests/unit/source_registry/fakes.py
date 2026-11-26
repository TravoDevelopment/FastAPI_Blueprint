"""In-memory source registry ports for use-case tests."""

from collections.abc import Sequence
from copy import deepcopy
from uuid import UUID

from app.modules.source_registry.application.ports import EventPublisher, SourcePage, SourceRegistryRepository
from app.modules.source_registry.domain.entities import AcquisitionSource
from app.modules.source_registry.domain.events import DomainEvent
from app.modules.source_registry.domain.exceptions import SourceNotFound
from app.modules.source_registry.domain.value_objects import SourceName


class FakeSourceRegistryRepository(SourceRegistryRepository):
    def __init__(self) -> None:
        self.rows: dict[UUID, AcquisitionSource] = {}

    @staticmethod
    def _row(source: AcquisitionSource) -> AcquisitionSource:
        """Copy the entity without persisting its pending domain events."""
        stored = deepcopy(source)
        stored.pull_events()
        return stored

    async def add(self, source: AcquisitionSource) -> None:
        self.rows[source.id] = self._row(source)

    async def get(self, source_id: UUID) -> AcquisitionSource:
        if source_id not in self.rows:
            raise SourceNotFound()
        return deepcopy(self.rows[source_id])

    async def list(self, *, is_enabled: bool | None, name_contains: str | None, offset: int, limit: int) -> SourcePage:
        name_filter = name_contains.casefold() if name_contains is not None else None
        matches = sorted(
            (
                source
                for source in self.rows.values()
                if (is_enabled is None or source.is_enabled is is_enabled)
                and (name_filter is None or name_filter in source.name.key)
            ),
            key=lambda source: (source.name.key, source.id),
        )
        return SourcePage(sources=deepcopy(matches[offset : offset + limit]), total=len(matches))

    async def update(self, source: AcquisitionSource) -> None:
        if source.id not in self.rows:
            raise SourceNotFound()
        self.rows[source.id] = self._row(source)

    async def delete(self, source_id: UUID) -> None:
        if self.rows.pop(source_id, None) is None:
            raise SourceNotFound()

    async def name_exists(self, name: SourceName, *, except_id: UUID | None = None) -> bool:
        return any(source.name.key == name.key and source.id != except_id for source in self.rows.values())


class FakeEventPublisher(EventPublisher):
    def __init__(self) -> None:
        self.scheduled: list[DomainEvent] = []

    def publish_after_commit(self, events: Sequence[DomainEvent]) -> None:
        self.scheduled.extend(events)
