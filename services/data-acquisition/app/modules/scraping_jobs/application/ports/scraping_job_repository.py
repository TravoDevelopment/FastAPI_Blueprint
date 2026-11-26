"""Persistence port for child scraping jobs."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.modules.scraping_jobs.domain.entities import ScrapingJob


@dataclass(frozen=True, slots=True)
class ScrapingJobPage:
    """One bounded page of child jobs and the total matching count."""

    items: list[ScrapingJob]
    total: int


class ScrapingJobRepository(ABC):
    """Stores child scraping jobs and supports parent/retry queries."""

    @abstractmethod
    async def add(self, scraping_job: ScrapingJob) -> None:
        """Stores a new scraping job."""

    @abstractmethod
    async def add_many(self, scraping_jobs: Sequence[ScrapingJob]) -> None:
        """Stores a discovery result as one batch."""

    @abstractmethod
    async def get(self, scraping_job_id: UUID) -> ScrapingJob:
        """Loads a scraping job or raises ScrapingJobNotFound."""

    @abstractmethod
    async def list_by_parent(self, parent_execution_id: UUID) -> list[ScrapingJob]:
        """Lists all child jobs belonging to a parent execution."""

    @abstractmethod
    async def list_by_parent_page(
        self,
        parent_execution_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> ScrapingJobPage:
        """Lists one bounded page of child jobs and returns the total matching count."""

    @abstractmethod
    async def list_retryable(self) -> list[ScrapingJob]:
        """Lists jobs currently in retryable-failure state."""

    @abstractmethod
    async def update(self, scraping_job: ScrapingJob) -> None:
        """Saves scraping-job state changes."""
