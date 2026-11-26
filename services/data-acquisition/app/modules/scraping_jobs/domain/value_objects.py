from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from urllib.parse import urlparse

from app.modules.scraping_jobs.domain.exceptions import InvalidOccurrenceKey, InvalidScrapingUrl


class ScrapingJobStatus(StrEnum):
    QUEUED = "queued"
    SCRAPING = "scraping"
    AWAITING_REVIEW = "awaiting_review"
    HANDING_OFF = "handing_off"
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ScheduleFrequency(StrEnum):
    WEEKLY = "weekly"


class ScheduleOccurrenceStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"


class ParentExecutionStatus(StrEnum):
    DISCOVERING = "discovering"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobAttemptPhase(StrEnum):
    SCRAPER = "scraper"
    REVIEW = "review"


class JobAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class SourceUrl:
    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip()
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidScrapingUrl("Source URL must be an absolute HTTP or HTTPS URL")
        object.__setattr__(self, "value", cleaned)


@dataclass(frozen=True, slots=True)
class ScheduleName:
    value: str

    def __post_init__(self) -> None:
        cleaned = " ".join(self.value.split())
        if not 3 <= len(cleaned) <= 120:
            raise ValueError("Schedule name must contain 3-120 characters")
        object.__setattr__(self, "value", cleaned)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    delay_seconds: int = 60

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("Retry max_attempts must be at least 1")
        if self.delay_seconds < 0:
            raise ValueError("Retry delay_seconds cannot be negative")

    def next_retry_at(self, *, after: datetime) -> datetime:
        return after + timedelta(seconds=self.delay_seconds)


@dataclass(frozen=True, slots=True)
class OccurrenceKey:
    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip()

        if not cleaned:
            raise InvalidOccurrenceKey("Occurrence key cannot be empty")

        object.__setattr__(self, "value", cleaned)


@dataclass(frozen=True, slots=True)
class ChildExecutionSummary:
    total_count: int
    succeeded_count: int
    failed_count: int
    cancelled_count: int
    status: ParentExecutionStatus
