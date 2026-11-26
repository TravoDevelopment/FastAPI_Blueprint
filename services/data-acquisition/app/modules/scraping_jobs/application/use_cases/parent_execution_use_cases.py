"""Application orchestration for parent scraping executions."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.scraping_jobs.application.ports import (
    EventPublisher,
    ParentExecutionRepository,
    ScheduleOccurrenceRepository,
    ScrapingJobRepository,
)
from app.modules.scraping_jobs.domain.entities import ParentExecution, ScrapingJob
from app.modules.scraping_jobs.domain.value_objects import (
    SourceUrl,
    TriggerType,
)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC time."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class StartParentExecutionCommand:
    """Input for starting a manual or scheduled parent execution."""

    trigger_type: TriggerType
    schedule_id: UUID | None = None
    occurrence_id: UUID | None = None


class ParentExecutionUseCases:
    """Coordinates discovery, child creation, and parent reconciliation."""

    def __init__(
        self,
        repository: ParentExecutionRepository,
        scraping_job_repository: ScrapingJobRepository,
        occurrence_repository: ScheduleOccurrenceRepository,
        events: EventPublisher,
        clock: Clock = utc_now,
    ) -> None:
        self.repository = repository
        self.scraping_job_repository = scraping_job_repository
        self.occurrence_repository = occurrence_repository
        self.events = events
        self.clock = clock

    async def start(
        self,
        command: StartParentExecutionCommand,
    ) -> ParentExecution:
        """Starts a parent execution and publishes its started event."""
        parent = ParentExecution.start(
            trigger_type=command.trigger_type,
            schedule_id=command.schedule_id,
            occurrence_id=command.occurrence_id,
            at=self.clock(),
        )
        await self.repository.add(parent)
        self.events.publish_after_commit(parent.pull_events())
        return parent

    async def claim_scheduled_occurrence(
        self,
        *,
        occurrence_id: UUID,
        schedule_id: UUID,
    ) -> ParentExecution:
        """Claims an occurrence and starts its scheduled parent execution."""
        occurrence = await self.occurrence_repository.get(occurrence_id)
        now = self.clock()

        parent = ParentExecution.start(
            trigger_type=TriggerType.SCHEDULED,
            schedule_id=schedule_id,
            occurrence_id=occurrence_id,
            at=now,
        )
        await self.repository.add(parent)

        occurrence.claim(parent_execution_id=parent.id, at=now)
        await self.occurrence_repository.update(occurrence)
        self.events.publish_after_commit(parent.pull_events())
        return parent

    async def discover_and_create_jobs(
        self,
        *,
        parent_execution_id: UUID,
        discovery_snapshot: Sequence[tuple[UUID, SourceUrl, UUID]],
    ) -> list[ScrapingJob]:
        """Creates child jobs from an already-discovered external snapshot."""
        parent = await self.repository.get(parent_execution_id)
        jobs = parent.create_child_jobs(
            discovery_snapshot=discovery_snapshot,
            at=self.clock(),
        )
        await self.scraping_job_repository.add_many(jobs)
        await self.repository.update(parent)
        self.events.publish_after_commit(parent.pull_events())
        return jobs

    async def reconcile_summary(
        self,
        *,
        parent_execution_id: UUID,
    ) -> ParentExecution:
        """Recomputes the parent summary from its persisted child jobs."""
        parent = await self.repository.get(parent_execution_id)
        child_jobs = await self.scraping_job_repository.list_by_parent(parent.id)
        parent.recompute_child_summary(
            child_jobs=child_jobs,
            at=self.clock(),
        )
        await self.repository.update(parent)
        self.events.publish_after_commit(parent.pull_events())
        return parent
