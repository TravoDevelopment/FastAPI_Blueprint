"""
DOMAIN ERRORS: one class per business rule that can be broken.

Each error has a stable `code` (clients rely on it: never rename it) and an HTTP status taken from the
class it extends:
    UnprocessableError -> 422  invalid input            (raised by value objects)
    ConflictError      -> 409  the action breaks a rule (raised by a policy)
    NotFoundError      -> 404  no such record           (raised by the repository)

The API turns them into problem responses automatically, e.g.
    {"status": 409, "code": "invalid_source_registry_state", "detail": "Archive the source registry before deleting it", ...}

The domain imports only `platform_kit.errors` (no FastAPI, no `app.core`).
"""

from platform_kit.errors import ConflictError, NotFoundError, UnprocessableError


class InvalidSourceMetadata(UnprocessableError):
    """The source name or description is not valid."""

    code = "invalid_source_metadata"


class InvalidSourceName(InvalidSourceMetadata):
    """The source name is not 3-120 characters after normalization."""

    code = "invalid_source_name"


class InvalidSourceDescription(InvalidSourceMetadata):
    """The source description is longer than 2,000 characters."""

    code = "invalid_source_description"


class InvalidSourceConfiguration(UnprocessableError):
    """The source configuration contains an invalid value."""

    code = "invalid_source_configuration"


class InvalidSourceClassification(InvalidSourceConfiguration):
    """The classification is not one of the five allowed values."""

    code = "invalid_source_classification"


class InvalidApprovedDomain(InvalidSourceConfiguration):
    """The approved domain is not a canonical public DNS hostname."""

    code = "invalid_approved_domain"


class InvalidApprovedEndpoint(InvalidSourceConfiguration):
    """The approved endpoint is not an HTTPS GET rule with an approved shape."""

    code = "invalid_approved_endpoint"


class InvalidConnectorIdentity(InvalidSourceConfiguration):
    """The connector key or version has an invalid format."""

    code = "invalid_connector_identity"


class InvalidSourceRegistryName(UnprocessableError):
    """The name is not 3-120 characters long."""

    code = "invalid_source_registry_name"


class InvalidSourceRegistryCode(UnprocessableError):
    """The code is not 2-20 letters, digits or dashes."""

    code = "invalid_source_registry_code"


class SourceRegistryCodeTaken(ConflictError):
    """Another source registry already uses this code (raised by the policy)."""

    code = "source_registry_code_taken"


class InvalidSourceRegistryState(ConflictError):
    """The action is not allowed in the current status, e.g. renaming an archived source registry (raised by the entity)."""

    code = "invalid_source_registry_state"


class SourceRegistryNotFound(NotFoundError):
    """No source registry with this id (raised by the repository)."""

    code = "source_registry_not_found"

    def __init__(self) -> None:
        super().__init__("Source registry not found")
