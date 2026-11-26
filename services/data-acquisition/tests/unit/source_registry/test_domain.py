"""Behavior of acquisition source value objects and the aggregate."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.modules.source_registry.domain.entities import AcquisitionSource
from app.modules.source_registry.domain.events import SourceCreated, SourceDisabled, SourceEnabled
from app.modules.source_registry.domain.exceptions import (
    EmptySourceUrls,
    InvalidSourceDescription,
    InvalidSourceName,
    InvalidSourceUrl,
    SourceAlreadyDisabled,
    SourceAlreadyEnabled,
    SourceMustBeDisabled,
    SourceNameTaken,
    UrlCountExceeded,
)
from app.modules.source_registry.domain.value_objects import (
    DESCRIPTION_MAX_LENGTH,
    NAME_MAX_LENGTH,
    URL_MAX_COUNT,
    SourceDescription,
    SourceName,
    SourceUrl,
    SourceUrlList,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CREATOR = UUID(int=1)
EDITOR = UUID(int=2)
FIRST_URL = "https://example.com/feed"
SECOND_URL = "https://example.com/news"


def _register(*, name_taken: bool = False) -> AcquisitionSource:
    return AcquisitionSource.register(
        name=SourceName("Tourism Feed"),
        description=SourceDescription("A tourism feed"),
        source_urls=SourceUrlList([FIRST_URL]),
        created_by=CREATOR,
        name_taken=name_taken,
        at=NOW,
    )


def test_name_normalizes_unicode_and_whitespace_before_casefolding() -> None:
    """Normalize display names without losing case and casefold the lookup key."""
    name = SourceName("  Cafe\u0301   Feed  ")
    assert name.value == "Café Feed"
    assert name.key == "café feed"


@pytest.mark.parametrize("raw", ["ab", "   ", "x" * (NAME_MAX_LENGTH + 1)])
def test_name_rejects_invalid_length_after_normalization(raw: str) -> None:
    """Reject blank, too-short, or too-long normalized names."""
    with pytest.raises(InvalidSourceName):
        SourceName(raw)


@pytest.mark.parametrize(("raw", "expected"), [(None, None), (" \t ", None), (" feed ", "feed")])
def test_description_trims_text_and_normalizes_blank_to_none(raw: str | None, expected: str | None) -> None:
    """Represent absent and blank descriptions as None while trimming text."""
    assert SourceDescription(raw).value == expected


def test_description_rejects_text_over_the_limit() -> None:
    """Reject descriptions exceeding the maximum length after trimming."""
    with pytest.raises(InvalidSourceDescription):
        SourceDescription("x" * (DESCRIPTION_MAX_LENGTH + 1))


@pytest.mark.parametrize("raw", ["http://example.com/feed", "https:///feed", "https://example.com/*"])
def test_url_requires_https_and_a_hostname_without_wildcards(raw: str) -> None:
    """Reject source URLs that are not complete HTTPS addresses or use wildcards."""
    with pytest.raises(InvalidSourceUrl):
        SourceUrl(raw)


def test_url_list_deduplicates_trimmed_urls_in_input_order() -> None:
    """Keep each URL once, preserving the first occurrence after trimming."""
    urls = SourceUrlList([SECOND_URL, f" {FIRST_URL} ", SECOND_URL, FIRST_URL])
    assert [url.value for url in urls] == [SECOND_URL, FIRST_URL]
    assert len(urls) == 2


def test_url_list_rejects_empty_input() -> None:
    """Require at least one source URL."""
    with pytest.raises(EmptySourceUrls):
        SourceUrlList([])


def test_url_list_enforces_limit_before_deduplication() -> None:
    """Reject requests with too many URL entries even when they all repeat."""
    with pytest.raises(UrlCountExceeded):
        SourceUrlList([FIRST_URL] * (URL_MAX_COUNT + 1))


def test_register_creates_a_disabled_source_and_records_creation() -> None:
    """Initialize audit fields and drain the creation event exactly once."""
    source = _register()
    assert source.is_enabled is False
    assert source.created_by == source.updated_by == CREATOR
    assert source.created_at == source.updated_at == NOW
    assert source.pull_events() == [SourceCreated(source.id, NOW, source_name="Tourism Feed")]
    assert source.pull_events() == []


def test_register_rejects_a_taken_name() -> None:
    """Reject registration when the repository reports the name is taken."""
    with pytest.raises(SourceNameTaken):
        _register(name_taken=True)


def test_enable_and_disable_update_audit_fields_and_record_events() -> None:
    """Record state transitions and retain the original creation audit fields."""
    source = _register()
    source.pull_events()
    enabled_at = NOW + timedelta(minutes=1)
    disabled_at = NOW + timedelta(minutes=2)

    source.enable(updated_by=EDITOR, at=enabled_at)
    assert (source.is_enabled, source.updated_by, source.updated_at) == (True, EDITOR, enabled_at)
    source.disable(updated_by=EDITOR, at=disabled_at)
    assert (source.is_enabled, source.updated_by, source.updated_at) == (False, EDITOR, disabled_at)
    assert (source.created_by, source.created_at) == (CREATOR, NOW)
    assert source.pull_events() == [SourceEnabled(source.id, enabled_at), SourceDisabled(source.id, disabled_at)]


def test_invalid_lifecycle_calls_record_no_events() -> None:
    """Reject disabling twice, enabling twice, and deleting an enabled source without recording events."""
    source = _register()
    source.pull_events()
    with pytest.raises(SourceAlreadyDisabled):
        source.disable(updated_by=EDITOR, at=NOW)
    assert source.pull_events() == []

    source.enable(updated_by=EDITOR, at=NOW)
    source.pull_events()
    with pytest.raises(SourceAlreadyEnabled):
        source.enable(updated_by=EDITOR, at=NOW)
    with pytest.raises(SourceMustBeDisabled):
        source.delete(at=NOW)
    assert source.is_enabled is True
    assert source.pull_events() == []
