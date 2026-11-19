"""
DOMAIN TESTS: the rules on their own. Fast: no database, no HTTP.

    Value objects -> format checks on one value
    Policies      -> every business rule, tested directly
    Entity        -> each method runs its rule, changes the data and records its event
"""

from datetime import UTC, datetime

import pytest

from app.modules.source_registry.domain.entities import SourceRegistry
from app.modules.source_registry.domain.exceptions import (
    InvalidSourceRegistryCode,
    InvalidSourceRegistryName,
    InvalidSourceRegistryState,
    SourceRegistryCodeTaken,
)
from app.modules.source_registry.domain.policies import (
    ensure_can_archive,
    ensure_can_delete,
    ensure_can_restore,
    ensure_code_is_free,
    ensure_is_active,
)
from app.modules.source_registry.domain.value_objects import (
    NAME_MAX_LENGTH,
    SourceRegistryCode,
    SourceRegistryName,
    SourceRegistryStatus,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _new() -> SourceRegistry:
    return SourceRegistry.create(
        name=SourceRegistryName("Blue pen"), code=SourceRegistryCode("ITM-001"), code_taken=False, at=NOW
    )


def _archived() -> SourceRegistry:
    source_registry = _new()
    source_registry.archive(at=NOW)
    return source_registry


# --- Value objects: format checks ------------------------------------------------------------------


def test_name_removes_extra_spaces() -> None:
    assert SourceRegistryName("  Blue   pen ").value == "Blue pen"


@pytest.mark.parametrize("raw", ["ab", "   ", "x" * (NAME_MAX_LENGTH + 1)])
def test_name_must_be_3_to_120_characters(raw: str) -> None:
    with pytest.raises(InvalidSourceRegistryName):
        SourceRegistryName(raw)


def test_code_is_trimmed_and_upper_case() -> None:
    assert SourceRegistryCode(" itm-001 ").value == "ITM-001"


@pytest.mark.parametrize("raw", ["A", "ITM 001", "-ITM", "ITM_001", "X" * 21])
def test_code_must_be_2_to_20_letters_digits_or_dashes(raw: str) -> None:
    with pytest.raises(InvalidSourceRegistryCode):
        SourceRegistryCode(raw)


# --- Policies: every business rule, on its own -----------------------------------------------------


def test_policy_code_must_be_free() -> None:
    ensure_code_is_free(SourceRegistryCode("ITM-001"), taken=False)
    with pytest.raises(SourceRegistryCodeTaken):
        ensure_code_is_free(SourceRegistryCode("ITM-001"), taken=True)


def test_policy_only_an_active_source_registry_can_change() -> None:
    ensure_is_active(_new(), action="rename")
    with pytest.raises(InvalidSourceRegistryState):
        ensure_is_active(_archived(), action="rename")


def test_policy_cannot_archive_twice() -> None:
    ensure_can_archive(_new())
    with pytest.raises(InvalidSourceRegistryState):
        ensure_can_archive(_archived())


def test_policy_only_an_archived_source_registry_can_be_restored() -> None:
    ensure_can_restore(_archived())
    with pytest.raises(InvalidSourceRegistryState):
        ensure_can_restore(_new())


def test_policy_only_an_archived_source_registry_can_be_deleted() -> None:
    ensure_can_delete(_archived())
    with pytest.raises(InvalidSourceRegistryState):
        ensure_can_delete(_new())


# --- Entity: each method = rule -> change -> event -------------------------------------------------


def test_create_makes_an_active_source_registry_and_records_created() -> None:
    source_registry = _new()
    assert source_registry.status is SourceRegistryStatus.ACTIVE
    assert [e.name for e in source_registry.pull_events()] == ["SourceRegistryCreated"]
    assert source_registry.pull_events() == []  # pulled events are cleared


def test_create_runs_the_unique_code_rule() -> None:
    with pytest.raises(SourceRegistryCodeTaken):
        SourceRegistry.create(
            name=SourceRegistryName("Blue pen"), code=SourceRegistryCode("ITM-001"), code_taken=True, at=NOW
        )


def test_archive_changes_the_status_and_records_archived() -> None:
    source_registry = _archived()
    assert source_registry.status is SourceRegistryStatus.ARCHIVED
    assert [e.name for e in source_registry.pull_events()] == ["SourceRegistryCreated", "SourceRegistryArchived"]


def test_restore_makes_it_active_again() -> None:
    source_registry = _archived()
    source_registry.restore(at=NOW)
    assert source_registry.status is SourceRegistryStatus.ACTIVE


def test_methods_refuse_what_the_rules_refuse() -> None:
    archived = _archived()
    with pytest.raises(InvalidSourceRegistryState):
        archived.rename(SourceRegistryName("Red pen"), at=NOW)
    with pytest.raises(InvalidSourceRegistryState):
        archived.change_code(SourceRegistryCode("ITM-002"), code_taken=False, at=NOW)
    with pytest.raises(InvalidSourceRegistryState):
        _new().delete()
    with pytest.raises(SourceRegistryCodeTaken):
        _new().change_code(SourceRegistryCode("ITM-002"), code_taken=True, at=NOW)
