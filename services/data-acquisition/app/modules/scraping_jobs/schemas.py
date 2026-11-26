"""HTTP request and response schemas for scraping jobs and their execution workflow."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from platform_kit.http.pagination import CamelModel, PageInfo
from pydantic import AwareDatetime, Field, StringConstraints

from app.modules.scraping_jobs.domain.entities import ParentExecution, ScrapingJob, ScrapingSchedule
from app.modules.scraping_jobs.domain.value_objects import (
    ParentExecutionStatus,
    RetryPolicy,
    ScheduleFrequency,
    ScrapingJobStatus,
    TriggerType,
)

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ScheduleNameText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]


class CreateScrapingScheduleRequest(CamelModel):
    """Request body for creating a disabled weekly schedule."""

    name: ScheduleNameText
    next_run_at: AwareDatetime
    frequency: ScheduleFrequency = ScheduleFrequency.WEEKLY
    interval_days: int = Field(default=7, ge=1)


class StartParentExecutionRequest(CamelModel):
    """Request body for starting a manual or scheduled parent execution."""

    trigger_type: TriggerType
    schedule_id: UUID | None = None
    occurrence_id: UUID | None = None


class DiscoverySource(CamelModel):
    """One source and category discovered for a parent execution."""

    source_id: UUID
    source_url: NonBlankString
    category_id: UUID


class DiscoverScrapingJobsRequest(CamelModel):
    """Snapshot of sources to turn into child scraping jobs."""

    discovery_snapshot: list[DiscoverySource]


class ClaimScheduleOccurrenceRequest(CamelModel):
    """Schedule identifier required to claim an existing occurrence."""

    schedule_id: UUID


class RecordScrapingResultRequest(CamelModel):
    """Reference to the result produced by a scraper."""

    result_reference: NonBlankString


class FailScrapingJobRequest(CamelModel):
    """Failure details recorded for a scraping or review attempt."""

    error_code: NonBlankString
    retryable: bool


class RetryPolicyResponse(CamelModel):
    """Retry settings exposed with a scraping job."""

    max_attempts: int
    delay_seconds: int

    @classmethod
    def from_value(cls, retry_policy: RetryPolicy) -> "RetryPolicyResponse":
        return cls(
            max_attempts=retry_policy.max_attempts,
            delay_seconds=retry_policy.delay_seconds,
        )


class ScrapingJobResponse(CamelModel):
    """One child scraping job as returned by the API."""

    id: UUID
    parent_execution_id: UUID
    source_id: UUID
    source_url: str
    category_id: UUID
    status: ScrapingJobStatus
    result_reference: str | None
    retry_policy: RetryPolicyResponse
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, scraping_job: ScrapingJob) -> "ScrapingJobResponse":
        return cls(
            id=scraping_job.id,
            parent_execution_id=scraping_job.parent_execution_id,
            source_id=scraping_job.source_id,
            source_url=scraping_job.source_url.value,
            category_id=scraping_job.category_id,
            status=scraping_job.status,
            result_reference=scraping_job.result_reference,
            retry_policy=RetryPolicyResponse.from_value(scraping_job.retry_policy),
            created_at=scraping_job.created_at,
            updated_at=scraping_job.updated_at,
        )


class CreatedScrapingJobsResponse(CamelModel):
    """Child jobs created from a discovery snapshot."""

    items: list[ScrapingJobResponse]
    total_count: int


class ScrapingJobList(CamelModel):
    """One page of child jobs and its pagination metadata."""

    items: list[ScrapingJobResponse]
    page_info: PageInfo


class ScrapingScheduleResponse(CamelModel):
    """One schedule, including its enabled and soft-deleted state."""

    id: UUID
    name: str
    frequency: ScheduleFrequency
    interval_days: int
    next_run_at: datetime
    is_enabled: bool
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, schedule: ScrapingSchedule) -> "ScrapingScheduleResponse":
        return cls(
            id=schedule.id,
            name=schedule.name.value,
            frequency=schedule.frequency,
            interval_days=schedule.interval_days,
            next_run_at=schedule.next_run_at,
            is_enabled=schedule.is_enabled,
            is_deleted=schedule.is_deleted,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )


class ParentExecutionResponse(CamelModel):
    """Parent execution status and aggregate child-job summary."""

    id: UUID
    trigger_type: TriggerType
    status: ParentExecutionStatus
    schedule_id: UUID | None
    occurrence_id: UUID | None
    discovery_completed: bool
    created_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    total_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int

    @classmethod
    def from_entity(cls, parent: ParentExecution) -> "ParentExecutionResponse":
        return cls(
            id=parent.id,
            trigger_type=parent.trigger_type,
            status=parent.status,
            schedule_id=parent.schedule_id,
            occurrence_id=parent.occurrence_id,
            discovery_completed=parent.discovery_completed,
            created_at=parent.created_at,
            started_at=parent.started_at,
            completed_at=parent.completed_at,
            total_count=parent.total_count,
            succeeded_count=parent.succeeded_count,
            failed_count=parent.failed_count,
            cancelled_count=parent.cancelled_count,
        )
