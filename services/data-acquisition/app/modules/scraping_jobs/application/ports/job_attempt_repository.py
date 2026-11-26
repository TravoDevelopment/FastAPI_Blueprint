"""Persistence port for scraping job attempts."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.scraping_jobs.domain.entities import JobAttempt


class JobAttemptRepository(ABC):
    """Stores attempt lifecycle records for individual scraping jobs."""

    @abstractmethod
    async def add(self, attempt: JobAttempt) -> None:
        """Stores a new attempt."""

    @abstractmethod
    async def list_by_job(self, scraping_job_id: UUID) -> list[JobAttempt]:
        """Lists attempts for a scraping job in chronological order."""

    @abstractmethod
    async def update(self, attempt: JobAttempt) -> None:
        """Saves attempt state changes."""
