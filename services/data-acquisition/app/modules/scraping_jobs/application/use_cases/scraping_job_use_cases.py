"""Application orchestration for child scraping jobs."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.scraping_jobs.application.ports import (
    EventPublisher,
    JobAttemptRepository,
    ScrapingJobPage,
    ScrapingJobRepository,
)
from app.modules.scraping_jobs.domain.entities import JobAttempt, ScrapingJob
from app.modules.scraping_jobs.domain.value_objects import (
    JobAttemptPhase,
    JobAttemptStatus,
)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC time."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RecordScrapingResultCommand:
    """Input for recording a scraper result."""

    result_reference: str


@dataclass(frozen=True, slots=True)
class FailScrapingJobCommand:
    """Input for recording a scraping or review failure."""

    error_code: str
    retryable: bool


class ScrapingJobUseCases:
    """Coordinates scraping-job state transitions and attempt records."""

    def __init__(
        self,
        repository: ScrapingJobRepository,
        attempt_repository: JobAttemptRepository,
        events: EventPublisher,
        clock: Clock = utc_now,
    ) -> None:
        self.repository = repository
        self.attempt_repository = attempt_repository
        self.events = events
        self.clock = clock

    async def get(self, scraping_job_id: UUID) -> ScrapingJob:
        """Loads one child scraping job."""
        return await self.repository.get(scraping_job_id)

    async def list_by_parent(self, parent_execution_id: UUID) -> list[ScrapingJob]:
        """Lists child jobs belonging to one parent execution."""
        return await self.repository.list_by_parent(parent_execution_id)

    async def list_by_parent_page(
        self,
        parent_execution_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> ScrapingJobPage:
        """Returns a bounded page of jobs belonging to one parent execution."""
        return await self.repository.list_by_parent_page(
            parent_execution_id,
            offset=offset,
            limit=limit,
        )

    async def begin_scraping(self, scraping_job_id: UUID) -> ScrapingJob:
        """Moves a queued job into the scraping phase."""
        job = await self.repository.get(scraping_job_id)
        now = self.clock()
        job.begin_scraping(at=now)

        attempt = JobAttempt.start(
            scraping_job_id=job.id,
            phase=JobAttemptPhase.SCRAPER,
            attempt_number=await self._next_attempt_number(job.id),
            at=now,
        )
        await self.attempt_repository.add(attempt)
        return await self._save(job)

    async def record_result(
        self,
        scraping_job_id: UUID,
        command: RecordScrapingResultCommand,
    ) -> ScrapingJob:
        """Records a result reference after scraping succeeds."""
        job = await self.repository.get(scraping_job_id)
        job.accept_result_reference(
            result_reference=command.result_reference,
            at=self.clock(),
        )
        return await self._save(job)

    async def begin_review_handoff(self, scraping_job_id: UUID) -> ScrapingJob:
        """Moves a result from awaiting review into review handoff."""
        job = await self.repository.get(scraping_job_id)
        job.begin_review_handoff(at=self.clock())
        return await self._save(job)

    async def accept_review_handoff(self, scraping_job_id: UUID) -> ScrapingJob:
        """Marks a reviewed child job as succeeded."""
        job = await self.repository.get(scraping_job_id)
        job.accept_review_handoff(at=self.clock())
        return await self._save(job)

    async def fail(
        self,
        scraping_job_id: UUID,
        command: FailScrapingJobCommand,
    ) -> ScrapingJob:
        """Records a retryable or permanent job failure."""
        job = await self.repository.get(scraping_job_id)
        now = self.clock()
        job.fail(
            error_code=command.error_code,
            retryable=command.retryable,
            at=now,
        )
        await self._mark_latest_attempt_failed(
            scraping_job_id=job.id,
            retryable=command.retryable,
            error_code=command.error_code,
            at=now,
        )
        return await self._save(job)

    async def cancel(self, scraping_job_id: UUID) -> ScrapingJob:
        """Cancels a non-terminal scraping job."""
        job = await self.repository.get(scraping_job_id)
        job.cancel(at=self.clock())
        return await self._save(job)

    async def _next_attempt_number(self, scraping_job_id: UUID) -> int:
        attempts = await self.attempt_repository.list_by_job(scraping_job_id)
        return max((attempt.attempt_number for attempt in attempts), default=0) + 1

    async def _mark_latest_attempt_failed(
        self,
        *,
        scraping_job_id: UUID,
        retryable: bool,
        error_code: str,
        at: datetime,
    ) -> None:
        attempts = await self.attempt_repository.list_by_job(scraping_job_id)
        running = [attempt for attempt in attempts if attempt.status is JobAttemptStatus.RUNNING]
        if not running:
            return
        latest = max(running, key=lambda attempt: attempt.attempt_number)
        latest.mark_failed(
            retryable=retryable,
            error_code=error_code,
            at=at,
        )
        if retryable:
            # The retry policy is read through the job aggregate, where it remains owned.
            job = await self.repository.get(scraping_job_id)
            latest.schedule_bounded_retry(retry_policy=job.retry_policy, at=at)
        await self.attempt_repository.update(latest)

    async def _save(self, job: ScrapingJob) -> ScrapingJob:
        await self.repository.update(job)
        self.events.publish_after_commit(job.pull_events())
        return job
