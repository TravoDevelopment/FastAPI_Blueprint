"""
USE-CASE TESTS: the steps of each use case, with in-memory fakes instead of the database and the broker.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.source_registry.application.use_cases import (
    CreateSourceRegistryCommand,
    SourceRegistryUseCases,
    UpdateSourceRegistryCommand,
)
from app.modules.source_registry.domain.exceptions import (
    InvalidSourceRegistryState,
    SourceRegistryCodeTaken,
    SourceRegistryNotFound,
)
from app.modules.source_registry.domain.value_objects import SourceRegistryStatus
from tests.unit.source_registry.fakes import FakeEventPublisher, FakeSourceRegistryRepository

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def repo() -> FakeSourceRegistryRepository:
    return FakeSourceRegistryRepository()


@pytest.fixture
def events() -> FakeEventPublisher:
    return FakeEventPublisher()


@pytest.fixture
def use_cases(repo: FakeSourceRegistryRepository, events: FakeEventPublisher) -> SourceRegistryUseCases:
    return SourceRegistryUseCases(repo, events, clock=lambda: NOW)  # fixed clock: predictable timestamps


async def test_create_saves_and_publishes_created(
    use_cases: SourceRegistryUseCases, repo: FakeSourceRegistryRepository, events: FakeEventPublisher
) -> None:
    source_registry = await use_cases.create(CreateSourceRegistryCommand(name=" Blue  pen ", code="itm-001"))
    assert (source_registry.name.value, source_registry.code.value) == ("Blue pen", "ITM-001")
    assert source_registry.id in repo.rows
    assert events.names == ["SourceRegistryCreated"]


async def test_create_refuses_a_taken_code(
    use_cases: SourceRegistryUseCases, repo: FakeSourceRegistryRepository
) -> None:
    await use_cases.create(CreateSourceRegistryCommand(name="Blue pen", code="ITM-001"))
    with pytest.raises(SourceRegistryCodeTaken):
        await use_cases.create(CreateSourceRegistryCommand(name="Red pen", code="itm-001"))
    assert len(repo.rows) == 1  # nothing saved


async def test_get_an_unknown_id_is_not_found(use_cases: SourceRegistryUseCases) -> None:
    with pytest.raises(SourceRegistryNotFound):
        await use_cases.get(uuid4())


async def test_list_filters_by_status_and_paginates(use_cases: SourceRegistryUseCases) -> None:
    for name, code in [("Pencil", "ITM-003"), ("Blue pen", "ITM-001"), ("Marker", "ITM-002")]:
        await use_cases.create(CreateSourceRegistryCommand(name=name, code=code))
    page = await use_cases.list(status=None, offset=0, limit=2)
    assert [x.name.value for x in page.items] == ["Blue pen", "Marker"]
    assert page.total == 3
    archived = await use_cases.list(status=SourceRegistryStatus.ARCHIVED, offset=0, limit=10)
    assert archived.total == 0


async def test_update_changes_only_the_fields_sent(use_cases: SourceRegistryUseCases) -> None:
    source_registry = await use_cases.create(CreateSourceRegistryCommand(name="Blue pen", code="ITM-001"))
    updated = await use_cases.update(source_registry.id, UpdateSourceRegistryCommand(name="Red pen"))
    assert (updated.name.value, updated.code.value) == ("Red pen", "ITM-001")


async def test_update_may_keep_its_own_code_but_not_take_another(use_cases: SourceRegistryUseCases) -> None:
    first = await use_cases.create(CreateSourceRegistryCommand(name="Blue pen", code="ITM-001"))
    await use_cases.create(CreateSourceRegistryCommand(name="Red pen", code="ITM-002"))
    await use_cases.update(first.id, UpdateSourceRegistryCommand(code="ITM-001"))  # its own code: fine
    with pytest.raises(SourceRegistryCodeTaken):
        await use_cases.update(first.id, UpdateSourceRegistryCommand(code="ITM-002"))


async def test_archived_source_registry_cannot_be_updated(use_cases: SourceRegistryUseCases) -> None:
    source_registry = await use_cases.create(CreateSourceRegistryCommand(name="Blue pen", code="ITM-001"))
    await use_cases.archive(source_registry.id)
    with pytest.raises(
        InvalidSourceRegistryState
    ):  # the policy, run by the entity method, reached through the use case
        await use_cases.update(source_registry.id, UpdateSourceRegistryCommand(name="Red pen"))


async def test_archive_publishes_archived(use_cases: SourceRegistryUseCases, events: FakeEventPublisher) -> None:
    source_registry = await use_cases.create(CreateSourceRegistryCommand(name="Blue pen", code="ITM-001"))
    archived = await use_cases.archive(source_registry.id)
    assert archived.status is SourceRegistryStatus.ARCHIVED
    assert events.names == ["SourceRegistryCreated", "SourceRegistryArchived"]


async def test_delete_needs_archive_first(
    use_cases: SourceRegistryUseCases, repo: FakeSourceRegistryRepository
) -> None:
    source_registry = await use_cases.create(CreateSourceRegistryCommand(name="Blue pen", code="ITM-001"))
    with pytest.raises(InvalidSourceRegistryState):
        await use_cases.delete(source_registry.id)
    await use_cases.archive(source_registry.id)
    await use_cases.delete(source_registry.id)
    assert repo.rows == {}
