"""
POLICIES: EVERY business rule of the source_registry module, in one file.

A policy is a CHECK: it answers "is this allowed?" and raises a domain error if not.
    - It never changes anything (changes are entity methods).
    - It never touches the database: a fact it needs (e.g. "is this code taken?") is passed in.

Who calls them: the entity methods (entities.py), as their first line. So every change of a
source registry is checked, and a rule cannot be skipped.

    ensure_can_archive(source_registry)             -> raises if it is already archived
    ensure_code_is_free(code, taken=True)      -> raises SourceRegistryCodeTaken
"""

from typing import TYPE_CHECKING

from app.modules.source_registry.domain.exceptions import (
    InvalidSourceRegistryState,
    SourceConfigurationNotFound,
    SourceConnectorUnavailable,
    SourceDisabled,
    SourceRegistryCodeTaken,
)
from app.modules.source_registry.domain.value_objects import SourceRegistryCode, SourceRegistryStatus

if TYPE_CHECKING:  # type hints only: entities.py imports this file, so no runtime import back
    from app.modules.source_registry.domain.entities import SourceRegistry


def ensure_code_is_free(code: SourceRegistryCode, *, taken: bool) -> None:
    """The code must be unique. The use case asks the repository and passes `taken`."""
    if taken:
        raise SourceRegistryCodeTaken(f"Code {code.value} is already used")


def ensure_is_active(source_registry: "SourceRegistry", *, action: str) -> None:
    """An archived source registry cannot be changed (restore it first)."""
    if source_registry.status is not SourceRegistryStatus.ACTIVE:
        raise InvalidSourceRegistryState(f"Cannot {action} an archived source registry; restore it first")


def ensure_can_archive(source_registry: "SourceRegistry") -> None:
    """A source registry cannot be archived twice."""
    if source_registry.status is SourceRegistryStatus.ARCHIVED:
        raise InvalidSourceRegistryState("The source registry is already archived")


def ensure_can_restore(source_registry: "SourceRegistry") -> None:
    """Only an archived source registry can be restored."""
    if source_registry.status is not SourceRegistryStatus.ARCHIVED:
        raise InvalidSourceRegistryState("Only an archived source registry can be restored")


def ensure_can_delete(source_registry: "SourceRegistry") -> None:
    """Only an archived source registry can be deleted (archive it first)."""
    if source_registry.status is not SourceRegistryStatus.ARCHIVED:
        raise InvalidSourceRegistryState("Archive the source registry before deleting it")


def ensure_enable_eligible(*, active_configuration_exists: bool, connector_available: bool) -> None:
    """Check configuration existence before availability of its exact connector."""
    if not active_configuration_exists:
        raise SourceConfigurationNotFound("Active source configuration not found")
    if not connector_available:
        raise SourceConnectorUnavailable("Active source configuration connector is unavailable")


def ensure_replacement_eligible(*, connector_available: bool) -> None:
    """Require an available connector for a validated replacement, even on a disabled source."""
    if not connector_available:
        raise SourceConnectorUnavailable("Replacement source configuration connector is unavailable")


def ensure_collection_eligible(
    *, is_enabled: bool, selected_configuration_exists: bool, connector_available: bool
) -> None:
    """Check enabled state, selected configuration existence, then its connector availability."""
    if not is_enabled:
        raise SourceDisabled("Source is disabled for collection")
    if not selected_configuration_exists:
        raise SourceConfigurationNotFound("Selected source configuration not found")
    if not connector_available:
        raise SourceConnectorUnavailable("Selected source configuration connector is unavailable")
