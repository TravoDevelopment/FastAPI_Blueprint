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

from app.modules.source_registry.domain.entities import AcquisitionSource
from app.modules.source_registry.domain.value_objects import SourceName, SourceDescription, SourceUrl, SourceUrlList


@dataclass(frozen=True, slots=True)
class SourcePage:
    """One page of a list: the sources on the page and how many there are in total."""

    sources: list[AcquisitionSource]
    total: int


class SourceRegistryRepository(ABC):
    @abstractmethod
    async def add(self, source: AcquisitionSource) -> None:
        """Stores a new source."""

    @abstractmethod
    async def get(self, source_id: UUID) -> AcquisitionSource:
        """Loads one source; raises `SourceNotFound` if the id does not exist."""

    @abstractmethod
    async def list(
        self, *, is_enabled: bool | None, name_contains: str | None, offset: int, limit: int) -> SourcePage:
        """One page of sources sorted by name, with optional filters."""

    @abstractmethod
    async def update(self, source: AcquisitionSource) -> None:
        """Saves the changes of an existing source."""

    @abstractmethod
    async def delete(self, source_id: UUID) -> None:
        """
        Permanently deletes the source row. The DB FK RESTRICT on scraping jobs ensures
        deletion is blocked when references exist; the adapter maps IntegrityError -> SourceInUse.
        """

    @abstractmethod
    async def name_exists(self, name: SourceName, *, except_id: UUID | None = None) -> bool:
        """True if another source (not `except_id`) already uses this name (the fact the policy needs)."""
