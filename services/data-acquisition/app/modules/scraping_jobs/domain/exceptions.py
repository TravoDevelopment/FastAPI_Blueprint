"""
DOMAIN ERRORS: one class per business rule that can be broken.

Each error has a stable `code` (clients rely on it: never rename it) and an HTTP status taken from the
class it extends:
    UnprocessableError -> 422  invalid input            (raised by value objects)
    ConflictError      -> 409  the action breaks a rule (raised by a policy)
    NotFoundError      -> 404  no such record           (raised by the repository)

The API turns them into problem responses automatically, e.g.
    {"status": 409, "code": "invalid_scraping_job_state", "detail": "Archive the scraping job before deleting it", ...}

The domain imports only `platform_kit.errors` (no FastAPI, no `app.core`).
"""

from platform_kit.errors import ConflictError, NotFoundError, UnprocessableError


class ScrapingJobNotFound(NotFoundError):
    """No scraping job with this id (raised by the repository)."""

    code = "scraping_job_not_found"

    def __init__(self) -> None:
        super().__init__("Scraping job not found")


class InvalidScheduleFrequency(UnprocessableError):
    code = "invalid_schedule_frequency"


class InvalidScheduleInterval(UnprocessableError):
    code = "invalid_schedule_interval"


class InvalidScrapingUrl(UnprocessableError):
    code = "invalid_scraping_url"


class InvalidJobTransition(ConflictError):
    code = "invalid_job_transition"


class InvalidParentExecutionState(ConflictError):
    code = "invalid_parent_execution_state"


class InvalidAttemptState(ConflictError):
    code = "invalid_attempt_state"


class InvalidScheduleOccurrenceState(ConflictError):
    code = "invalid_schedule_occurrence_state"


class ActivePairAlreadyExists(ConflictError):
    code = "active_pair_already_exists"


class DuplicatePairInOccurrence(ConflictError):
    code = "duplicate_pair_in_occurrence"


class ScheduleOccurrenceAlreadyClaimed(ConflictError):
    code = "schedule_occurrence_already_claimed"


class ScrapingScheduleNotFound(NotFoundError):
    code = "scraping_schedule_not_found"


class ParentExecutionNotFound(NotFoundError):
    code = "parent_execution_not_found"


class InvalidScrapingScheduleState(ConflictError):
    code = "invalid_scraping_schedule_state"


class InvalidOccurrenceKey(UnprocessableError):
    code = "invalid_occurrence_key"

class InvalidAttemptNumber(UnprocessableError):
    code = "invalid_attempt_number"
