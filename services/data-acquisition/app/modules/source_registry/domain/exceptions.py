"""
DOMAIN ERRORS: one class per business rule that can be broken.

Each error has a stable `code` (clients rely on it: never rename it) and an HTTP status taken from the
class it extends:
    UnprocessableError -> 422  invalid input            (raised by value objects)
    ConflictError      -> 409  the action breaks a rule (raised by a policy)
    NotFoundError      -> 404  no such record           (raised by the repository)

The API turns them into problem responses automatically, e.g.
    {"status": 409, "code": "source_must_be_disabled", "detail": "Disable the source before deleting it", ...}

The domain imports only `platform_kit.errors` (no FastAPI, no `app.core`).
"""

from platform_kit.errors import ConflictError, NotFoundError, UnprocessableError


class InvalidSourceName(UnprocessableError):
    """The name fails length or normalisation rules (3–120 chars after NFC + whitespace collapse)."""

    code = "invalid_source_name"


class InvalidSourceDescription(UnprocessableError):
    """The description exceeds 2,000 characters."""

    code = "invalid_source_description"


class InvalidSourceUrl(UnprocessableError):
    """A URL is not a complete, canonical HTTPS URL, or its hostname is private/reserved."""

    code = "invalid_source_url"


class EmptySourceUrls(UnprocessableError):
    """The source_urls list must contain at least one URL."""

    code = "empty_source_urls"


class UrlCountExceeded(UnprocessableError):
    """The source_urls list exceeds the 100-URL limit."""

    code = "url_count_exceeded"


class SourceNameTaken(ConflictError):
    """Another source already uses this name (case-insensitive; raised by the policy)."""

    code = "source_name_taken"


class SourceNotModified(ConflictError):
    """The update contains no changes; every supplied field is identical to the current state."""

    code = "source_not_modified"


class SourceMustBeDisabled(ConflictError):
    """The source must be disabled before it can be deleted (raised by the entity)."""

    code = "source_must_be_disabled"


class SourceAlreadyEnabled(ConflictError):
    """The source is already enabled; enable is idempotent but the caller may not expect this."""

    code = "source_already_enabled"


class SourceAlreadyDisabled(ConflictError):
    """The source is already disabled; disable is idempotent."""

    code = "source_already_disabled"


class SourceNotReady(ConflictError):
    """The source cannot be enabled because it has no valid URL list."""

    code = "source_not_ready"


class SourceInUse(ConflictError):
    """The source cannot be deleted because one or more scraping jobs reference it (FK RESTRICT)."""

    code = "source_in_use"


class SourceNotFound(NotFoundError):
    """No AcquisitionSource with this id (raised by the repository)."""

    code = "source_not_found"

    def __init__(self) -> None:
        super().__init__("Item not found")