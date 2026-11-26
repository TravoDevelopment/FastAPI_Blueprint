"""Persistence port for schedule occurrences."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.scraping_jobs.domain.entities import ScheduleOccurrence
from app.modules.scraping_jobs.domain.value_objects import OccurrenceKey


class ScheduleOccurrenceRepository(ABC):
    """Stores schedule occurrences and prevents duplicate occurrence keys."""

    @abstractmethod
    async def add(self, occurrence: ScheduleOccurrence) -> None:
        """Stores a new schedule occurrence."""

    @abstractmethod
    async def get(self, occurrence_id: UUID) -> ScheduleOccurrence:
        """Loads one occurrence or raises the domain not-found error."""

    @abstractmethod
    async def get_by_key(
        self,
        *,
        schedule_id: UUID,
        occurrence_key: OccurrenceKey,
    ) -> ScheduleOccurrence | None:
        """Finds an occurrence by its schedule and occurrence key."""

    @abstractmethod
    async def update(self, occurrence: ScheduleOccurrence) -> None:
        """Saves occurrence state changes."""
