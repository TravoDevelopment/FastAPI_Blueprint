"""
TEST DOUBLES: in-memory versions of the ports, so use-case tests run without a database or a broker.
They implement the same interfaces as the real adapters.
"""

from collections.abc import Sequence
from copy import deepcopy
from uuid import UUID

from app.modules.source_registry.application.ports import EventPublisher, SourceRegistryPage, SourceRegistryRepository
from app.modules.source_registry.domain.entities import SourceRegistry
from app.modules.source_registry.domain.events import PublishableEvent
from app.modules.source_registry.domain.exceptions import SourceRegistryNotFound
from app.modules.source_registry.domain.value_objects import SourceRegistryCode, SourceRegistryStatus


class FakeSourceRegistryRepository(SourceRegistryRepository):
    def __init__(self) -> None:
        self.rows: dict[UUID, SourceRegistry] = {}  # stands in for the table

    @staticmethod
    def _row(source_registry: SourceRegistry) -> SourceRegistry:
        """A stored copy, like a database row: pending events are not stored."""
        stored = deepcopy(source_registry)
        stored.pull_events()
        return stored

    async def add(self, source_registry: SourceRegistry) -> None:
        self.rows[source_registry.id] = self._row(source_registry)

    async def get(self, source_registry_id: UUID) -> SourceRegistry:
        if source_registry_id not in self.rows:
            raise SourceRegistryNotFound()
        return deepcopy(self.rows[source_registry_id])

    async def list(self, *, status: SourceRegistryStatus | None, offset: int, limit: int) -> SourceRegistryPage:
        matches = sorted(
            (x for x in self.rows.values() if status is None or x.status is status), key=lambda x: x.name.value
        )
        return SourceRegistryPage(items=matches[offset : offset + limit], total=len(matches))

    async def update(self, source_registry: SourceRegistry) -> None:
        if source_registry.id not in self.rows:
            raise SourceRegistryNotFound()
        self.rows[source_registry.id] = self._row(source_registry)

    async def delete(self, source_registry_id: UUID) -> None:
        if self.rows.pop(source_registry_id, None) is None:
            raise SourceRegistryNotFound()

    async def code_exists(self, code: SourceRegistryCode, *, except_id: UUID | None = None) -> bool:
        return any(x.code == code and x.id != except_id for x in self.rows.values())


class FakeEventPublisher(EventPublisher):
    def __init__(self) -> None:
        self.published: list[PublishableEvent] = []  # tests assert on this list

    def publish_after_commit(self, events: Sequence[PublishableEvent]) -> None:
        self.published.extend(events)

    @property
    def names(self) -> list[str]:
        return [event.name for event in self.published]
