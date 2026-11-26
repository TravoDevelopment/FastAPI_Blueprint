"""
POLICIES: EVERY business rule of the source_registry module, in one file.

A policy is a CHECK: it answers "is this allowed?" and raises a domain error if not.
    - It never changes anything (changes are entity methods).
    - It never touches the database: a fact it needs (e.g. "is this name taken?") is passed in.

Who calls them: the entity methods (entities.py), as their first line. So every change of an
AcquisitionSource is checked, and a rule cannot be skipped.

    ensure_source_name_is_free(name, taken=True)   -> raises SourceNameTaken
    ensure_source_disabled(source)                 -> raises SourceMustBeDisabled if enabled
    ensure_source_enabled(source)                  -> raises SourceAlreadyEnabled if already enabled
    ensure_source_not_enabled(source)              -> raises SourceAlreadyDisabled if already disabled
    ensure_details_changed(source, ...)            -> raises SourceNotModified if nothing changed
"""

from types import EllipsisType
from typing import TYPE_CHECKING

from app.modules.source_registry.domain.exceptions import (
    SourceAlreadyDisabled,
    SourceAlreadyEnabled,
    SourceMustBeDisabled,
    SourceNameTaken,
    SourceNotModified,
)
from app.modules.source_registry.domain.value_objects import SourceName, SourceUrlList

if TYPE_CHECKING:  # type hints only: entities.py imports this file, so no runtime import back
    from app.modules.source_registry.domain.entities import AcquisitionSource


def ensure_source_name_is_free(name: SourceName | None, *, taken: bool) -> None:
    """The name must be unique (case-insensitive). The use case asks the repository and passes `taken`."""
    if taken and name is not None:
        raise SourceNameTaken(f"A source named {name.value!r} already exists")


def ensure_source_disabled(source: "AcquisitionSource") -> None:
    """The source must be disabled before it can be deleted."""
    if source.is_enabled:
        raise SourceMustBeDisabled("Disable the source before deleting it")


def ensure_source_enabled(source: "AcquisitionSource") -> None:
    """Idempotency guard: raise if the source is already enabled."""
    if source.is_enabled:
        raise SourceAlreadyEnabled("The source is already enabled")


def ensure_source_not_enabled(source: "AcquisitionSource") -> None:
    """Idempotency guard: raise if the source is already disabled."""
    if not source.is_enabled:
        raise SourceAlreadyDisabled("The source is already disabled")


def ensure_details_changed(
    source: "AcquisitionSource",
    *,
    name: SourceName | None,
    description_value: str | None | EllipsisType,  # `...` means "not supplied by the caller"
    urls: SourceUrlList | None,
) -> None:
    """Raises SourceNotModified when every supplied field is identical to the current state."""
    name_same = name is None or name.value == source.name.value
    desc_same = (
        description_value is ...  # caller did not supply
        or description_value == source.description.value
    )
    urls_same = urls is None or {u.value for u in urls.urls} == {u.value for u in source.source_urls.urls}
    if name_same and desc_same and urls_same:
        raise SourceNotModified("No fields were changed")
