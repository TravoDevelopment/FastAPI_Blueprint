"""Persistence port for scraping schedules."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.modules.scraping_jobs.domain.entities import ScrapingSchedule


class ScrapingScheduleRepository(ABC):
    """Stores scraping schedules and finds schedules that are due."""

    @abstractmethod
    async def add(self, schedule: ScrapingSchedule) -> None:
        """Stores a new schedule."""

    @abstractmethod
    async def get(self, schedule_id: UUID) -> ScrapingSchedule:
        """Loads a schedule or raises ScrapingScheduleNotFound."""

    @abstractmethod
    async def update(self, schedule: ScrapingSchedule) -> None:
        """Saves state changes on an existing schedule."""

    @abstractmethod
    async def list_enabled_due(self, *, at: datetime) -> list[ScrapingSchedule]:
        """Lists enabled schedules whose next-run time has arrived."""
