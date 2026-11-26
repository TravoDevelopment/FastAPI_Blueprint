from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DomainEvent:
    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True, slots=True)
class ScrapingJobQueued(DomainEvent):
    scraping_job_id: UUID
    occurred_at: datetime
    parent_execution_id: UUID
    source_id: UUID
    category_id: UUID


@dataclass(frozen=True, slots=True)
class ScrapingJobSucceeded(DomainEvent):
    scraping_job_id: UUID
    occurred_at: datetime
    result_reference: str


@dataclass(frozen=True, slots=True)
class ScrapingJobFailed(DomainEvent):
    scraping_job_id: UUID
    occurred_at: datetime
    error_code: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class ScrapingJobCancelled(DomainEvent):
    scraping_job_id: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ParentExecutionStarted(DomainEvent):
    parent_execution_id: UUID
    occurred_at: datetime
    trigger_type: str


@dataclass(frozen=True, slots=True)
class ParentExecutionCompleted(DomainEvent):
    parent_execution_id: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ScrapingScheduleCreated(DomainEvent):
    scraping_schedule_id: UUID
    occurred_at: datetime
    schedule_name: str
    frequency: str
    interval_days: int


@dataclass(frozen=True, slots=True)
class ScheduleOccurrenceCreated(DomainEvent):
    schedule_occurrence_id: UUID
    occurred_at: datetime
    schedule_id: UUID
    occurrence_key: str
    due_at: datetime

@dataclass(frozen=True, slots=True)
class ScrapingJobAttemptStarted(DomainEvent):
    attempt_id: UUID
    occurred_at: datetime
    scraping_job_id: UUID
    attempt_number: int
