"""Source registry use cases exercised through in-memory ports."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.modules.source_registry.application.use_cases import (
    RegisterSourceCommand,
    SourceRegistryUseCases,
    UpdateSourceCommand,
)
from app.modules.source_registry.domain.events import (
    SourceCreated,
    SourceDeleted,
    SourceDisabled,
    SourceEnabled,
    SourceUpdated,
)
from app.modules.source_registry.domain.exceptions import (
    SourceInUse,
    SourceMustBeDisabled,
    SourceNameTaken,
    SourceNotFound,
    SourceNotModified,
)
from tests.unit.source_registry.fakes import FakeEventPublisher, FakeSourceRegistryRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CREATOR = UUID(int=1)
EDITOR = UUID(int=2)
FEED_URL = "https://example.com/feed"


@pytest.fixture(scope="function")  # noqa: PT003
def repo() -> FakeSourceRegistryRepository:
    return FakeSourceRegistryRepository()


@pytest.fixture(scope="function")  # noqa: PT003
def events() -> FakeEventPublisher:
    return FakeEventPublisher()


@pytest.fixture(scope="function")  # noqa: PT003
def use_cases(repo: FakeSourceRegistryRepository, events: FakeEventPublisher) -> SourceRegistryUseCases:
    return SourceRegistryUseCases(repo, events, clock=lambda: NOW)


def _registration(name: str = "Tourism Feed", *, description: str | None = "Tourism updates") -> RegisterSourceCommand:
    return RegisterSourceCommand(name=name, description=description, source_urls=[FEED_URL], created_by=CREATOR)


async def test_register_saves_normalized_source_and_schedules_creation(
    use_cases: SourceRegistryUseCases, events: FakeEventPublisher
) -> None:
    """Persist normalized details and schedule one creation event with the source identity."""
    source = await use_cases.register(_registration("  Tourism   Feed ", description=" Tourism updates "))

    stored = await use_cases.get(source.id)
    assert stored is not source
    assert stored.name.value == "Tourism Feed"
    assert stored.description.value == "Tourism updates"
    assert [url.value for url in stored.source_urls] == [FEED_URL]
    assert stored.is_enabled is False
    assert stored.pull_events() == []
    assert events.scheduled == [SourceCreated(source.id, NOW, source_name="Tourism Feed")]


async def test_register_refuses_duplicate_normalized_name(
    use_cases: SourceRegistryUseCases, repo: FakeSourceRegistryRepository, events: FakeEventPublisher
) -> None:
    """Reject case and whitespace variants of a registered name without saving or scheduling an event."""
    first = await use_cases.register(_registration())

    with pytest.raises(SourceNameTaken):
        await use_cases.register(_registration(" tourism   FEED "))

    assert set(repo.rows) == {first.id}
    assert events.scheduled == [SourceCreated(first.id, NOW, source_name="Tourism Feed")]


async def test_get_an_unknown_id_is_not_found(use_cases: SourceRegistryUseCases) -> None:
    """Propagate the repository's not-found error for a missing source."""
    with pytest.raises(SourceNotFound):
        await use_cases.get(uuid4())


async def test_list_filters_before_paginating_in_casefolded_name_order(use_cases: SourceRegistryUseCases) -> None:
    """Combine enabled and case-insensitive name filters, and count all matches before slicing."""
    zoo = await use_cases.register(_registration("Zoo Feed"))
    alpha = await use_cases.register(_registration("alpha feed"))
    await use_cases.register(_registration("Disabled Feed"))
    notices = await use_cases.register(_registration("Other Notices"))
    for source in (zoo, alpha, notices):
        await use_cases.enable(source.id, actor_id=EDITOR)

    first_page = await use_cases.list(is_enabled=True, name_contains="FEED", offset=0, limit=1)
    second_page = await use_cases.list(is_enabled=True, name_contains="FEED", offset=1, limit=1)

    assert first_page.total == second_page.total == 2
    assert [source.id for source in first_page.sources] == [alpha.id]
    assert [source.id for source in second_page.sources] == [zoo.id]


async def test_update_preserves_omitted_description_and_clears_explicit_none(
    use_cases: SourceRegistryUseCases, events: FakeEventPublisher
) -> None:
    """Keep the omitted description on rename, then persist explicit None and schedule both updates."""
    source = await use_cases.register(_registration())
    events.scheduled.clear()

    renamed = await use_cases.update(source.id, UpdateSourceCommand(name="Travel Feed", updated_by=EDITOR))
    assert renamed.name.value == "Travel Feed"
    assert renamed.description.value == "Tourism updates"
    assert (await use_cases.get(source.id)).description.value == "Tourism updates"

    cleared = await use_cases.update(source.id, UpdateSourceCommand(description=None, updated_by=EDITOR))
    assert cleared.description.value is None
    assert cleared.name == renamed.name
    assert cleared.source_urls == source.source_urls
    assert cleared.updated_by == EDITOR
    assert (await use_cases.get(source.id)).description.value is None
    assert events.scheduled == [SourceUpdated(source.id, NOW), SourceUpdated(source.id, NOW)]


async def test_update_can_keep_its_own_name_but_not_take_another(
    use_cases: SourceRegistryUseCases, events: FakeEventPublisher
) -> None:
    """Exclude the current source from uniqueness checks and reject a rename to another source's key."""
    first = await use_cases.register(_registration())
    await use_cases.register(_registration("Weather Feed"))
    events.scheduled.clear()

    updated = await use_cases.update(first.id, UpdateSourceCommand(name="Tourism Feed", description="New details"))
    assert updated.description.value == "New details"
    with pytest.raises(SourceNameTaken):
        await use_cases.update(first.id, UpdateSourceCommand(name=" weather   FEED ", description="Not saved"))

    assert await use_cases.get(first.id) == updated
    assert events.scheduled == [SourceUpdated(first.id, NOW)]


async def test_update_rejects_unchanged_details_without_scheduling_an_event(
    use_cases: SourceRegistryUseCases, events: FakeEventPublisher
) -> None:
    """Reject an empty patch or identical normalized values without changing the stored source."""
    source = await use_cases.register(_registration(description=None))
    events.scheduled.clear()

    with pytest.raises(SourceNotModified):
        await use_cases.update(source.id, UpdateSourceCommand(updated_by=EDITOR))
    with pytest.raises(SourceNotModified):
        await use_cases.update(
            source.id,
            UpdateSourceCommand(name=" Tourism  Feed ", description=None, source_urls=[FEED_URL, FEED_URL]),
        )

    assert await use_cases.get(source.id) == source
    assert events.scheduled == []


async def test_enable_disable_and_delete_persist_lifecycle_and_schedule_events(
    use_cases: SourceRegistryUseCases, events: FakeEventPublisher
) -> None:
    """Persist enable and disable, reject deletion while enabled, then remove the disabled source."""
    source = await use_cases.register(_registration())
    events.scheduled.clear()

    await use_cases.enable(source.id, actor_id=EDITOR)
    enabled = await use_cases.get(source.id)
    assert enabled.is_enabled is True
    assert enabled.updated_by == EDITOR
    with pytest.raises(SourceMustBeDisabled):
        await use_cases.delete(source.id)
    assert events.scheduled == [SourceEnabled(source.id, NOW)]

    await use_cases.disable(source.id, actor_id=CREATOR)
    disabled = await use_cases.get(source.id)
    assert disabled.is_enabled is False
    assert disabled.updated_by == CREATOR
    await use_cases.delete(source.id)

    with pytest.raises(SourceNotFound):
        await use_cases.get(source.id)
    assert events.scheduled == [
        SourceEnabled(source.id, NOW),
        SourceDisabled(source.id, NOW),
        SourceDeleted(source.id, NOW),
    ]


async def test_delete_does_not_schedule_event_when_repository_rejects_it(
    use_cases: SourceRegistryUseCases,
    repo: FakeSourceRegistryRepository,
    events: FakeEventPublisher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Propagate a storage-level SourceInUse error without scheduling a deletion event."""
    source = await use_cases.register(_registration())
    events.scheduled.clear()
    monkeypatch.setattr(repo, "delete", AsyncMock(side_effect=SourceInUse("Source is referenced")))

    with pytest.raises(SourceInUse):
        await use_cases.delete(source.id)

    assert await use_cases.get(source.id) == source
    assert events.scheduled == []
