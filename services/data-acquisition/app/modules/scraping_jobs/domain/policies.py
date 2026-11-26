from collections.abc import Iterable
from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.scraping_jobs.domain.exceptions import (
    InvalidAttemptNumber,
    InvalidAttemptState,
    InvalidJobTransition,
    InvalidParentExecutionState,
    InvalidScheduleOccurrenceState,
    InvalidScrapingScheduleState,
)
from app.modules.scraping_jobs.domain.value_objects import (
    ChildExecutionSummary,
    JobAttemptStatus,
    ParentExecutionStatus,
    ScheduleOccurrenceStatus,
    ScrapingJobStatus,
    TriggerType,
)

if TYPE_CHECKING:
    from app.modules.scraping_jobs.domain.entities import (
        JobAttempt,
        ParentExecution,
        ScheduleOccurrence,
        ScrapingJob,
        ScrapingSchedule,
    )


def ensure_job_can_begin_scraping(job: "ScrapingJob") -> None:
    if job.status is not ScrapingJobStatus.QUEUED:
        raise InvalidJobTransition("Only queued jobs can begin scraping")


def ensure_job_can_accept_result(job: "ScrapingJob") -> None:
    if job.status is not ScrapingJobStatus.SCRAPING:
        raise InvalidJobTransition("Only scraping jobs can accept a result reference")


def ensure_job_can_begin_handoff(job: "ScrapingJob") -> None:
    if job.status is not ScrapingJobStatus.AWAITING_REVIEW:
        raise InvalidJobTransition("Only jobs awaiting review can begin handoff")


def ensure_job_can_succeed(job: "ScrapingJob") -> None:
    if job.status is not ScrapingJobStatus.HANDING_OFF:
        raise InvalidJobTransition("Only jobs in review handoff can succeed")


def ensure_job_can_fail(job: "ScrapingJob") -> None:
    if job.status in {
        ScrapingJobStatus.SUCCEEDED,
        ScrapingJobStatus.PERMANENT_FAILURE,
        ScrapingJobStatus.CANCELLED,
        ScrapingJobStatus.FAILED,
    }:
        raise InvalidJobTransition("Terminal jobs cannot fail again")


def ensure_job_can_cancel(job: "ScrapingJob") -> None:
    if job.status in {
        ScrapingJobStatus.SUCCEEDED,
        ScrapingJobStatus.PERMANENT_FAILURE,
        ScrapingJobStatus.CANCELLED,
        ScrapingJobStatus.FAILED,
    }:
        raise InvalidJobTransition("Terminal jobs cannot be cancelled")


def ensure_occurrence_can_be_claimed(occurrence: "ScheduleOccurrence") -> None:
    if occurrence.status is not ScheduleOccurrenceStatus.PENDING:
        raise InvalidScheduleOccurrenceState("Only pending occurrences can be claimed")


def ensure_occurrence_can_start(occurrence: "ScheduleOccurrence") -> None:
    if occurrence.status is not ScheduleOccurrenceStatus.CLAIMED:
        raise InvalidScheduleOccurrenceState("Only claimed occurrences can start processing")


def ensure_occurrence_can_complete(occurrence: "ScheduleOccurrence") -> None:
    if occurrence.status is not ScheduleOccurrenceStatus.PROCESSING:
        raise InvalidScheduleOccurrenceState("Only processing occurrences can be completed")


def ensure_occurrence_can_fail(occurrence: "ScheduleOccurrence") -> None:
    if occurrence.status in {
        ScheduleOccurrenceStatus.COMPLETED,
        ScheduleOccurrenceStatus.FAILED,
    }:
        raise InvalidScheduleOccurrenceState("Terminal occurrences cannot be marked failed")


def ensure_parent_can_start(
    *,
    trigger_type: TriggerType,
    schedule_id: UUID | None,
) -> None:
    if trigger_type is TriggerType.SCHEDULED and schedule_id is None:
        raise InvalidParentExecutionState("A scheduled execution requires a schedule")


def ensure_parent_can_create_jobs(parent: "ParentExecution") -> None:
    if parent.status is not ParentExecutionStatus.DISCOVERING:
        raise InvalidParentExecutionState("Child jobs require a discovery snapshot")


def ensure_schedule_can_enable(schedule: "ScrapingSchedule") -> None:
    if schedule.is_deleted:
        raise InvalidScrapingScheduleState("Deleted schedules cannot be enabled")

    if schedule.is_enabled:
        raise InvalidScrapingScheduleState("Schedule is already enabled")


def ensure_schedule_can_disable(schedule: "ScrapingSchedule") -> None:
    if schedule.is_deleted:
        raise InvalidScrapingScheduleState("Deleted schedules cannot be disabled")

    if not schedule.is_enabled:
        raise InvalidScrapingScheduleState("Schedule is already disabled")


def ensure_schedule_can_delete(schedule: "ScrapingSchedule") -> None:
    if schedule.is_deleted:
        raise InvalidScrapingScheduleState("Schedule is already deleted")


def ensure_attempt_can_succeed(attempt: "JobAttempt") -> None:
    if attempt.status is not JobAttemptStatus.RUNNING:
        raise InvalidAttemptState("Only running attempts can succeed")


def ensure_attempt_can_fail(attempt: "JobAttempt") -> None:
    if attempt.status is not JobAttemptStatus.RUNNING:
        raise InvalidAttemptState("Only running attempts can fail")


def ensure_parent_can_recompute_summary(
    parent: "ParentExecution",
) -> None:
    if not parent.discovery_completed:
        raise InvalidParentExecutionState("Discovery must be complete before recomputing child summary")


def calculate_child_execution_summary(
    child_jobs: Iterable["ScrapingJob"],
) -> ChildExecutionSummary:
    jobs = list(child_jobs)

    succeeded_count = sum(job.status is ScrapingJobStatus.SUCCEEDED for job in jobs)

    failed_count = sum(
        job.status
        in {
            ScrapingJobStatus.PERMANENT_FAILURE,
            ScrapingJobStatus.FAILED,
        }
        for job in jobs
    )

    cancelled_count = sum(job.status is ScrapingJobStatus.CANCELLED for job in jobs)

    total_count = len(jobs)

    active_count = sum(
        job.status
        not in {
            ScrapingJobStatus.SUCCEEDED,
            ScrapingJobStatus.PERMANENT_FAILURE,
            ScrapingJobStatus.CANCELLED,
            ScrapingJobStatus.FAILED,
        }
        for job in jobs
    )

    if active_count > 0:
        status = ParentExecutionStatus.RUNNING

    elif cancelled_count == total_count:
        status = ParentExecutionStatus.CANCELLED

    elif failed_count == 0:
        status = ParentExecutionStatus.SUCCEEDED

    elif succeeded_count == 0:
        status = ParentExecutionStatus.FAILED

    else:
        status = ParentExecutionStatus.PARTIAL_FAILED

    return ChildExecutionSummary(
        total_count=total_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        cancelled_count=cancelled_count,
        status=status,
    )


def is_parent_execution_terminal(
    status: ParentExecutionStatus,
) -> bool:
    return status in {
        ParentExecutionStatus.SUCCEEDED,
        ParentExecutionStatus.FAILED,
        ParentExecutionStatus.PARTIAL_FAILED,
        ParentExecutionStatus.CANCELLED,
    }

def ensure_valid_attempt_number(attempt_number: int) -> None:
    if attempt_number < 1:
        raise InvalidAttemptNumber(
            "Attempt number must be at least 1"
        )
