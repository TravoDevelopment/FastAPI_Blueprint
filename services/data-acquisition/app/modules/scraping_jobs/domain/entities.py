"""
Domain entities for the scraping jobs module.

Entity methods are the only place aggregate state changes. Policies validate transitions and
value objects validate immutable values.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.modules.scraping_jobs.domain.events import (
    DomainEvent,
    ParentExecutionCompleted,
    ParentExecutionStarted,
    ScheduleOccurrenceCreated,
    ScrapingJobAttemptStarted,
    ScrapingJobCancelled,
    ScrapingJobFailed,
    ScrapingJobQueued,
    ScrapingJobSucceeded,
    ScrapingScheduleCreated,
)
from app.modules.scraping_jobs.domain.policies import (
    calculate_child_execution_summary,
    ensure_attempt_can_fail,
    ensure_attempt_can_succeed,
    ensure_job_can_accept_result,
    ensure_job_can_begin_handoff,
    ensure_job_can_begin_scraping,
    ensure_job_can_cancel,
    ensure_job_can_fail,
    ensure_job_can_succeed,
    ensure_occurrence_can_be_claimed,
    ensure_occurrence_can_complete,
    ensure_occurrence_can_fail,
    ensure_occurrence_can_start,
    ensure_parent_can_create_jobs,
    ensure_parent_can_recompute_summary,
    ensure_parent_can_start,
    ensure_schedule_can_delete,
    ensure_schedule_can_disable,
    ensure_schedule_can_enable,
    ensure_valid_attempt_number,
    is_parent_execution_terminal,
)
from app.modules.scraping_jobs.domain.value_objects import (
    JobAttemptPhase,
    JobAttemptStatus,
    OccurrenceKey,
    ParentExecutionStatus,
    RetryPolicy,
    ScheduleFrequency,
    ScheduleName,
    ScheduleOccurrenceStatus,
    ScrapingJobStatus,
    SourceUrl,
    TriggerType,
)


@dataclass(slots=True)
class ScrapingJob:

    # --- Properties -----

    id: UUID
    parent_execution_id: UUID
    source_id: UUID
    source_url: SourceUrl
    category_id: UUID
    status: ScrapingJobStatus = ScrapingJobStatus.QUEUED
    result_reference: str | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # --- Behavioral Methods -----

    @classmethod
    def create_queued(
        cls,
        *,
        parent_execution_id: UUID,
        source_id: UUID,
        source_url: SourceUrl,
        category_id: UUID,
        retry_policy: RetryPolicy | None = None,
        at: datetime,
    ) -> "ScrapingJob":
        job = cls(
            id=uuid4(),
            parent_execution_id=parent_execution_id,
            source_id=source_id,
            source_url=source_url,
            category_id=category_id,
            status=ScrapingJobStatus.QUEUED,
            retry_policy=retry_policy or RetryPolicy(),
            created_at=at,
            updated_at=at,
        )
        job._events.append(ScrapingJobQueued(job.id, at, parent_execution_id, source_id, category_id))
        return job

    def begin_scraping(self, *, at: datetime) -> None:
        ensure_job_can_begin_scraping(self)
        self.status = ScrapingJobStatus.SCRAPING
        self.updated_at = at

    def accept_result_reference(self, *, result_reference: str, at: datetime) -> None:
        ensure_job_can_accept_result(self)
        cleaned = result_reference.strip()
        if not cleaned:
            raise ValueError("Result reference is required")
        self.result_reference = cleaned
        self.status = ScrapingJobStatus.AWAITING_REVIEW
        self.updated_at = at

    def begin_review_handoff(self, *, at: datetime) -> None:
        ensure_job_can_begin_handoff(self)
        self.status = ScrapingJobStatus.HANDING_OFF
        self.updated_at = at

    def accept_review_handoff(self, *, at: datetime) -> None:
        ensure_job_can_succeed(self)
        self.status = ScrapingJobStatus.SUCCEEDED
        self.updated_at = at
        self._events.append(ScrapingJobSucceeded(self.id, at, self.result_reference or ""))

    def fail(
        self,
        *,
        error_code: str,
        retryable: bool,
        at: datetime,
    ) -> None:
        ensure_job_can_fail(self)
        cleaned_error = error_code.strip()
        if not cleaned_error:
            raise ValueError("Error code is required")
        self.status = ScrapingJobStatus.RETRYABLE_FAILURE if retryable else ScrapingJobStatus.PERMANENT_FAILURE
        self.updated_at = at
        self._events.append(ScrapingJobFailed(self.id, at, cleaned_error, retryable))

    def cancel(self, *, at: datetime) -> None:
        ensure_job_can_cancel(self)
        self.status = ScrapingJobStatus.CANCELLED
        self.updated_at = at
        self._events.append(ScrapingJobCancelled(self.id, at))

    def is_retry_due(self, *, next_retry_at: datetime, at: datetime) -> bool:
        return self.status is ScrapingJobStatus.RETRYABLE_FAILURE and at >= next_retry_at

    # --- Events -----

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events


@dataclass(slots=True)
class ScrapingSchedule:

    # --- Properties -----
    id: UUID
    name: ScheduleName
    frequency: ScheduleFrequency
    interval_days: int
    next_run_at: datetime
    is_enabled: bool = False
    is_deleted: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # --- Behavioral Methods -----
    @classmethod
    def create(
        cls,
        *,
        name: ScheduleName,
        next_run_at: datetime,
        at: datetime,
        frequency: ScheduleFrequency = ScheduleFrequency.WEEKLY,
        interval_days: int = 7,
    ) -> "ScrapingSchedule":
        if frequency is not ScheduleFrequency.WEEKLY:
            raise ValueError("Only weekly schedules are supported")
        if interval_days != 7:
            raise ValueError("Weekly schedules must use an interval of 7 days")
        schedule = cls(
            id=uuid4(),
            name=name,
            frequency=frequency,
            interval_days=interval_days,
            next_run_at=next_run_at,
            created_at=at,
            updated_at=at,
        )
        schedule._events.append(
            ScrapingScheduleCreated(
                scraping_schedule_id=schedule.id,
                occurred_at=at,
                schedule_name=name.value,
                frequency=frequency.value,
                interval_days=interval_days,
            )
        )
        return schedule

    def enable(self, *, at: datetime) -> None:
        ensure_schedule_can_enable(self)
        self.is_enabled = True
        self.updated_at = at

    def disable(self, *, at: datetime) -> None:
        ensure_schedule_can_disable(self)
        self.is_enabled = False
        self.updated_at = at

    def delete(self, *, at: datetime) -> None:
        ensure_schedule_can_delete(self)
        self.is_enabled = False
        self.is_deleted = True
        self.updated_at = at

    # --- Events -----
    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events


@dataclass(slots=True)
class ScheduleOccurrence:
    # --- Properties -----
    id: UUID
    schedule_id: UUID
    occurrence_key: OccurrenceKey
    due_at: datetime
    status: ScheduleOccurrenceStatus = ScheduleOccurrenceStatus.PENDING
    parent_execution_id: UUID | None = None
    created_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # --- Behavioral Methods -----
    @classmethod
    def create(
        cls,
        *,
        schedule_id: UUID,
        occurrence_key: OccurrenceKey,
        due_at: datetime,
        at: datetime,
    ) -> "ScheduleOccurrence":
        occurrence = cls(
            id=uuid4(),
            schedule_id=schedule_id,
            occurrence_key=occurrence_key,
            due_at=due_at,
            status=ScheduleOccurrenceStatus.PENDING,
            created_at=at,
        )
        occurrence._events.append(ScheduleOccurrenceCreated(occurrence.id, at, schedule_id, occurrence_key, due_at))
        return occurrence

    def claim(self, *, parent_execution_id: UUID, at: datetime) -> None:
        ensure_occurrence_can_be_claimed(self)
        self.status = ScheduleOccurrenceStatus.CLAIMED
        self.parent_execution_id = parent_execution_id
        if self.created_at is None:
            self.created_at = at

    def start_processing(self, *, at: datetime) -> None:
        ensure_occurrence_can_start(self)
        self.status = ScheduleOccurrenceStatus.PROCESSING
        if self.created_at is None:
            self.created_at = at

    def complete_with_parent(self, *, parent_execution_id: UUID, at: datetime) -> None:
        ensure_occurrence_can_complete(self)
        self.status = ScheduleOccurrenceStatus.COMPLETED
        self.parent_execution_id = parent_execution_id
        if self.created_at is None:
            self.created_at = at

    def mark_failed(self, *, at: datetime) -> None:
        ensure_occurrence_can_fail(self)
        self.status = ScheduleOccurrenceStatus.FAILED
        if self.created_at is None:
            self.created_at = at

    # --- Events -----

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events


@dataclass(slots=True)
class ParentExecution:
    # --- Properties -----
    id: UUID
    trigger_type: TriggerType
    status: ParentExecutionStatus
    schedule_id: UUID | None = None
    occurrence_id: UUID | None = None
    discovery_completed: bool = False
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # --- Behavioral Methods -----
    @classmethod
    def start(
        cls,
        *,
        trigger_type: TriggerType,
        at: datetime,
        schedule_id: UUID | None = None,
        occurrence_id: UUID | None = None,
    ) -> "ParentExecution":
        ensure_parent_can_start(trigger_type=trigger_type, schedule_id=schedule_id)
        parent = cls(
            id=uuid4(),
            trigger_type=trigger_type,
            status=ParentExecutionStatus.DISCOVERING,
            schedule_id=schedule_id,
            occurrence_id=occurrence_id,
            created_at=at,
            started_at=at,
        )
        parent._events.append(ParentExecutionStarted(parent.id, at, trigger_type.value))
        return parent

    def create_child_jobs(
        self,
        *,
        discovery_snapshot: Sequence[tuple[UUID, SourceUrl, UUID]],
        at: datetime,
    ) -> list[ScrapingJob]:
        ensure_parent_can_create_jobs(self)
        jobs = [
            ScrapingJob.create_queued(
                parent_execution_id=self.id,
                source_id=source_id,
                source_url=source_url,
                category_id=category_id,
                at=at,
            )
            for source_id, source_url, category_id in discovery_snapshot
        ]
        self.discovery_completed = True
        self.status = ParentExecutionStatus.RUNNING
        self.total_count = len(jobs)
        return jobs

    def recompute_child_summary(
        self,
        *,
        child_jobs: Iterable[ScrapingJob],
        at: datetime,
    ) -> None:
        ensure_parent_can_recompute_summary(self)

        summary = calculate_child_execution_summary(child_jobs)

        self.total_count = summary.total_count
        self.succeeded_count = summary.succeeded_count
        self.failed_count = summary.failed_count
        self.cancelled_count = summary.cancelled_count
        self.status = summary.status

        if is_parent_execution_terminal(self.status):
            self.completed_at = at
            self._events.append(ParentExecutionCompleted(self.id, at))

    # --- Events -----

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events


@dataclass(slots=True)
class JobAttempt:

    # --- Properties -----
    id: UUID
    scraping_job_id: UUID
    phase: JobAttemptPhase
    attempt_number: int
    status: JobAttemptStatus = JobAttemptStatus.RUNNING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    next_retry_at: datetime | None = None
    error_code: str | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # --- Behavioral Methods -----
    @classmethod
    def start(
        cls,
        *,
        scraping_job_id: UUID,
        phase: JobAttemptPhase,
        attempt_number: int,
        at: datetime,
    ) -> "JobAttempt":
        ensure_valid_attempt_number(attempt_number)
        attempt = cls(
            id=uuid4(),
            scraping_job_id=scraping_job_id,
            phase=phase,
            attempt_number=attempt_number,
            status=JobAttemptStatus.RUNNING,
            started_at=at,
        )
        attempt._events.append(ScrapingJobAttemptStarted(scraping_job_id, attempt.id, at, phase.value, attempt_number))
        return attempt

    def mark_successful(self, *, at: datetime) -> None:
        ensure_attempt_can_succeed(self)
        self.status = JobAttemptStatus.SUCCEEDED
        self.finished_at = at
        self.next_retry_at = None

    def mark_failed(
        self,
        *,
        retryable: bool,
        error_code: str,
        at: datetime,
    ) -> None:
        ensure_attempt_can_fail(self)
        cleaned_error = error_code.strip()
        if not cleaned_error:
            raise ValueError("Error code is required")
        self.status = JobAttemptStatus.RETRYABLE_FAILURE if retryable else JobAttemptStatus.PERMANENT_FAILURE
        self.error_code = cleaned_error
        self.finished_at = at
        self.next_retry_at = None

    def schedule_bounded_retry(
        self,
        *,
        retry_policy: RetryPolicy,
        at: datetime,
    ) -> None:
        if self.status is not JobAttemptStatus.RETRYABLE_FAILURE:
            raise ValueError("Only retryable attempts can schedule a retry")
        if self.attempt_number >= retry_policy.max_attempts:
            self.status = JobAttemptStatus.PERMANENT_FAILURE
            self.next_retry_at = None
            return
        self.next_retry_at = retry_policy.next_retry_at(after=at)

    # --- Events -----
    def pull_events(self) -> list[DomainEvent]:
        self._events, events = [], self._events
        return events
