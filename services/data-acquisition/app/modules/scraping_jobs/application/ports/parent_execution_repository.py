"""Persistence port for parent scraping executions."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.scraping_jobs.domain.entities import ParentExecution


class ParentExecutionRepository(ABC):
    """Stores parent executions and their reconciled summaries."""

    @abstractmethod
    async def add(self, parent: ParentExecution) -> None:
        """Stores a new parent execution."""

    @abstractmethod
    async def get(self, parent_execution_id: UUID) -> ParentExecution:
        """Loads a parent or raises ParentExecutionNotFound."""

    @abstractmethod
    async def update(self, parent: ParentExecution) -> None:
        """Saves parent state and summary changes."""
