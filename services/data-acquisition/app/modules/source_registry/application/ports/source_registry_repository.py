"""
PORT (interface): what the use cases need from storage, without saying HOW it is stored.

The use cases only know this abstract class. Two classes implement it:
- `SqlAlchemySourceRegistryRepository` (infrastructure/persistence/): the real database, used by the app;
- `FakeSourceRegistryRepository` (tests/unit/source_registry/fakes.py): a dict in memory, used by unit tests.

To add a query: add an abstract method here, then implement it in both classes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app.modules.source_registry.domain.entities import SourceRegistry
from app.modules.source_registry.domain.value_objects import SourceRegistryCode, SourceRegistryStatus


@dataclass(frozen=True, slots=True)
class SourceRegistryPage:
    """One page of a list: the source registry on the page and how many there are in total."""

    items: list[SourceRegistry]
    total: int


class SourceRegistryRepository(ABC):
    @abstractmethod
    async def add(self, source_registry: SourceRegistry) -> None:
        """Stores a new source registry."""

    @abstractmethod
    async def get(self, source_registry_id: UUID) -> SourceRegistry:
        """Loads one source registry; raises `SourceRegistryNotFound` if the id does not exist."""

    @abstractmethod
    async def list(self, *, status: SourceRegistryStatus | None, offset: int, limit: int) -> SourceRegistryPage:
        """One page of source registry sorted by name, optionally only those with `status`."""

    @abstractmethod
    async def update(self, source_registry: SourceRegistry) -> None:
        """Saves the changes of an existing source registry."""

    @abstractmethod
    async def delete(self, source_registry_id: UUID) -> None:
        """Deletes one source registry; raises `SourceRegistryNotFound` if the id does not exist."""

    @abstractmethod
    async def code_exists(self, code: SourceRegistryCode, *, except_id: UUID | None = None) -> bool:
        """True if another source registry (not `except_id`) already uses this code (the fact the policy needs)."""
