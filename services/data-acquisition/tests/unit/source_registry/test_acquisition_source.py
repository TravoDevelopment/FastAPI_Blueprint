"""Test the AcquisitionSource aggregate without persistence or publishing."""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import RFC_4122, UUID

import pytest

from app.modules.source_registry.domain.entities import AcquisitionSource, SourceConfiguration
from app.modules.source_registry.domain.events import (
    SourceConfigurationCreated,
    SourceDisabled,
    SourceEnabled,
    SourceEvent,
    SourceMetadataUpdated,
    SourceRegistered,
)
from app.modules.source_registry.domain.exceptions import (
    InvalidSourceConfiguration,
    InvalidSourceMetadata,
    SourceConfigurationNotFound,
    SourceConnectorUnavailable,
)
from app.modules.source_registry.domain.value_objects import (
    ApprovedDomain,
    ApprovedEndpoint,
    ConnectorIdentity,
    SourceClassification,
    SourceDescription,
    SourceName,
)

CREATOR = UUID(int=1)
EDITOR = UUID(int=2)
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
T2 = T0 + timedelta(hours=2)
DOMAINS = (ApprovedDomain("example.org"),)
ENDPOINTS = (ApprovedEndpoint("https://example.org/feed"),)
CONNECTOR = ConnectorIdentity("sample_feed", "2.1.0")


def register_source(
    *,
    name: str = "  Example   Feed ",
    domains: tuple[ApprovedDomain, ...] = DOMAINS,
    at: datetime = T0,
) -> tuple[AcquisitionSource, SourceConfiguration]:
    """Register a source with otherwise valid metadata and configuration."""
    return AcquisitionSource.register(
        name=name,
        description="  Example description  ",
        classification=SourceClassification.OFFICIAL_API,
        approved_domains=domains,
        approved_endpoints=ENDPOINTS,
        connector=CONNECTOR,
        actor_id=CREATOR,
        at=at,
    )


@pytest.mark.parametrize(
    ("event", "expected_name", "extra_field", "extra_type"),
    [
        (SourceRegistered(CREATOR, T0, 1), "SourceRegistered", "version", int),
        (SourceMetadataUpdated(CREATOR, T0, ("name",)), "SourceMetadataUpdated", "changed_fields", tuple),
        (SourceEnabled(CREATOR, T0, 2), "SourceEnabled", "version", int),
        (SourceDisabled(CREATOR, T0, 2), "SourceDisabled", "version", int),
        (SourceConfigurationCreated(CREATOR, T0, 2), "SourceConfigurationCreated", "version", int),
    ],
)
def test_source_event_payload_is_frozen_and_has_expected_types(
    event: SourceEvent, expected_name: str, extra_field: str, extra_type: type[object]
) -> None:
    """Protect published names and payload shape, types, and immutability for all five events."""
    assert event.name == expected_name
    payload = asdict(event)
    assert set(payload) == {"source_id", "occurred_at", extra_field}
    assert isinstance(payload["source_id"], UUID)
    assert isinstance(payload["occurred_at"], datetime)
    assert payload["occurred_at"].tzinfo is UTC
    extra = payload[extra_field]
    assert type(extra) is extra_type
    if isinstance(extra, tuple):
        assert all(isinstance(field_name, str) for field_name in extra)

    for field_name, value in payload.items():
        with pytest.raises(FrozenInstanceError):
            setattr(event, field_name, value)


def test_registration_creates_disabled_source_with_version_one() -> None:
    """Generate a new UUID and pair the disabled source with a complete initial snapshot."""
    source, initial = register_source(at=T0.astimezone(timezone(timedelta(hours=2))))
    another_source, _ = register_source()

    assert source.id.variant == RFC_4122
    assert source.id.version == 4
    assert source.id != another_source.id
    assert not source.is_enabled
    assert source.name == SourceName("Example Feed")
    assert source.description == SourceDescription("Example description")
    assert (initial.source_id, initial.version, source.active_version) == (source.id, 1, 1)
    assert initial.connector == CONNECTOR
    assert initial.approved_domains == DOMAINS
    assert initial.approved_endpoints == ENDPOINTS
    assert initial.classification is SourceClassification.OFFICIAL_API
    assert source.created_at == source.updated_at == initial.created_at == T0
    assert source.created_at.tzinfo is source.updated_at.tzinfo is initial.created_at.tzinfo is UTC
    assert source.created_by == source.updated_by == initial.created_by == CREATOR
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1)]
    assert source.pull_events() == []


def test_registration_rejects_invalid_metadata_or_configuration() -> None:
    """Refuse to create a pair if either the metadata or snapshot is invalid."""
    with pytest.raises(InvalidSourceMetadata):
        register_source(name="x")
    with pytest.raises(InvalidSourceConfiguration):
        register_source(domains=())


def test_rehydration_restores_existing_state_without_recording_events() -> None:
    """Load an existing source, including its active version, without replaying registration."""
    source = AcquisitionSource.rehydrate(
        source_id=UUID(int=3),
        name=SourceName("Saved Feed"),
        description=SourceDescription(None),
        is_enabled=True,
        active_version=4,
        created_at=T0,
        updated_at=T1,
        created_by=CREATOR,
        updated_by=EDITOR,
    )

    assert source.id == UUID(int=3)
    assert source.name == SourceName("Saved Feed")
    assert source.description.value is None
    assert source.is_enabled
    assert source.active_version == 4
    assert (source.created_at, source.updated_at, source.created_by, source.updated_by) == (T0, T1, CREATOR, EDITOR)
    assert source.pull_events() == []


def test_direct_constructor_rejects_invalid_active_version() -> None:
    """Dataclass construction cannot skip the positive-version invariant."""
    source, _ = register_source()

    with pytest.raises(InvalidSourceConfiguration):
        replace(source, _active_version=0)


@pytest.mark.parametrize(
    ("field_name", "value", "error"),
    [
        ("source_id", str(CREATOR), InvalidSourceMetadata),
        ("created_by", str(CREATOR), InvalidSourceMetadata),
        ("updated_by", str(EDITOR), InvalidSourceMetadata),
        ("name", "Saved Feed", InvalidSourceMetadata),
        ("description", None, InvalidSourceMetadata),
        ("is_enabled", 1, InvalidSourceMetadata),
        ("active_version", True, InvalidSourceConfiguration),
        ("active_version", "4", InvalidSourceConfiguration),
        ("active_version", -1, InvalidSourceConfiguration),
        ("created_at", T0.isoformat(), InvalidSourceMetadata),
        ("updated_at", T1.replace(tzinfo=None), InvalidSourceMetadata),
        ("updated_at", T0 - timedelta(seconds=1), InvalidSourceMetadata),
    ],
)
def test_rehydration_rejects_invalid_state(field_name: str, value: object, error: type[Exception]) -> None:
    """Reject malformed stored values with domain errors rather than coercing them."""
    fields: dict[str, Any] = {
        "source_id": UUID(int=3),
        "name": SourceName("Saved Feed"),
        "description": SourceDescription(None),
        "is_enabled": True,
        "active_version": 4,
        "created_at": T0,
        "updated_at": T1,
        "created_by": CREATOR,
        "updated_by": EDITOR,
    }
    fields[field_name] = value

    with pytest.raises(error):
        AcquisitionSource.rehydrate(**fields)


def test_rehydration_allows_equal_audit_instants_in_different_timezones() -> None:
    """Compare audit instants in UTC, with equality allowed for a newly created source."""
    source = AcquisitionSource.rehydrate(
        source_id=UUID(int=3),
        name=SourceName("Saved Feed"),
        description=SourceDescription(None),
        is_enabled=False,
        active_version=1,
        created_at=T0.astimezone(timezone(timedelta(hours=2))),
        updated_at=T0.astimezone(timezone(timedelta(hours=-3))),
        created_by=CREATOR,
        updated_by=CREATOR,
    )

    assert source.created_at == source.updated_at == T0
    assert source.created_at.tzinfo is source.updated_at.tzinfo is UTC
    assert source.pull_events() == []


def test_backdated_changes_leave_aggregate_and_pending_events_unchanged() -> None:
    """Reject writes before creation without applying metadata, lifecycle, or version changes."""
    source, initial = register_source()
    assert source.enable(active_configuration=initial, connector_available=True, actor_id=CREATOR, at=T0)
    earlier = T0 - timedelta(seconds=1)

    with pytest.raises(InvalidSourceMetadata):
        source.update_metadata(name="Renamed Feed", actor_id=EDITOR, at=earlier)
    with pytest.raises(InvalidSourceMetadata):
        source.disable(actor_id=EDITOR, at=earlier)
    with pytest.raises(InvalidSourceMetadata):
        source.add_configuration(replace(initial, version=2, created_at=earlier), connector_available=True)

    assert (source.name.value, source.is_enabled, source.active_version) == ("Example Feed", True, 1)
    assert (source.updated_at, source.updated_by) == (T0, CREATOR)
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1), SourceEnabled(source.id, T0, 1)]


def test_update_metadata_distinguishes_omission_from_clearing() -> None:
    """Keep omitted fields and allow a caller to clear the description explicitly."""
    source, _ = register_source()

    assert source.update_metadata(name=" example  feed ", actor_id=EDITOR, at=T1)
    assert source.name == SourceName("example feed")
    assert source.description == SourceDescription("Example description")
    assert source.update_metadata(description=None, actor_id=EDITOR, at=T2)
    assert source.name == SourceName("example feed")
    assert source.description.value is None
    assert (source.updated_at, source.updated_by, source.active_version, source.is_enabled) == (T2, EDITOR, 1, False)
    assert source.pull_events() == [
        SourceRegistered(source.id, T0, 1),
        SourceMetadataUpdated(source.id, T1, ("name",)),
        SourceMetadataUpdated(source.id, T2, ("description",)),
    ]


def test_update_both_fields_records_one_event() -> None:
    """Change both metadata fields together and record one event naming both changes."""
    source, _ = register_source()
    source.pull_events()

    assert source.update_metadata(name=" Renamed Feed ", description=" New description ", actor_id=EDITOR, at=T1)
    assert (source.name.value, source.description.value) == ("Renamed Feed", "New description")
    assert source.pull_events() == [SourceMetadataUpdated(source.id, T1, ("name", "description"))]


def test_normalized_or_omitted_metadata_is_a_no_op() -> None:
    """Do not touch audit fields or pending events when no normalized value changes."""
    source, _ = register_source()

    assert not source.update_metadata(name="Example  Feed", description=" Example description ", actor_id=EDITOR, at=T1)
    assert not source.update_metadata(actor_id=EDITOR, at=T2)
    assert (source.updated_at, source.updated_by) == (T0, CREATOR)
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1)]


def test_invalid_metadata_does_not_partially_apply() -> None:
    """Reject an invalid description without applying the valid name or disturbing the event queue."""
    source, _ = register_source()

    with pytest.raises(InvalidSourceMetadata):
        source.update_metadata(name="Renamed Feed", description="x" * 2001, actor_id=EDITOR, at=T1)

    assert (source.name.value, source.description.value) == ("Example Feed", "Example description")
    assert (source.updated_at, source.updated_by) == (T0, CREATOR)
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1)]


def test_enable_and_disable_are_idempotent_and_keep_active_version() -> None:
    """Record only effective state transitions and preserve the active pointer when disabling."""
    source, initial = register_source()
    assert not source.disable(actor_id=EDITOR, at=T1)
    assert (source.updated_at, source.updated_by) == (T0, CREATOR)
    assert source.enable(active_configuration=initial, connector_available=True, actor_id=EDITOR, at=T1)
    assert source.is_enabled
    assert not source.enable(active_configuration=None, connector_available=False, actor_id=CREATOR, at=T2)
    assert (source.updated_at, source.updated_by) == (T1, EDITOR)
    assert source.disable(actor_id=CREATOR, at=T2)
    assert not source.disable(actor_id=EDITOR, at=T2 + timedelta(hours=1))
    assert not source.is_enabled
    assert source.active_version == 1
    assert (source.updated_at, source.updated_by) == (T2, CREATOR)
    assert source.pull_events() == [
        SourceRegistered(source.id, T0, 1),
        SourceEnabled(source.id, T1, 1),
        SourceDisabled(source.id, T2, 1),
    ]


@pytest.mark.parametrize("invalid_snapshot", ["missing", "wrong-source", "wrong-version"])
def test_enable_rejects_missing_or_mismatched_active_snapshot(invalid_snapshot: str) -> None:
    """A usable snapshot must match both source ID and active version; missing wins over unavailable."""
    source, initial = register_source()
    candidates = {
        "missing": None,
        "wrong-source": replace(initial, source_id=EDITOR),
        "wrong-version": replace(initial, version=2),
    }

    with pytest.raises(SourceConfigurationNotFound):
        source.enable(
            active_configuration=candidates[invalid_snapshot], connector_available=False, actor_id=EDITOR, at=T1
        )

    assert not source.is_enabled
    assert (source.updated_at, source.updated_by) == (T0, CREATOR)
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1)]


def test_enable_rejects_unavailable_connector() -> None:
    """Reject enablement without changing enabled state, audit fields, or pending events."""
    source, initial = register_source()

    with pytest.raises(SourceConnectorUnavailable):
        source.enable(active_configuration=initial, connector_available=False, actor_id=EDITOR, at=T1)

    assert not source.is_enabled
    assert (source.updated_at, source.updated_by) == (T0, CREATOR)
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1)]


def test_rejected_audit_timestamp_does_not_mutate_source() -> None:
    """Reject a naive timestamp before changing metadata or enabled state."""
    source, initial = register_source()
    naive_time = T1.replace(tzinfo=None)

    with pytest.raises(InvalidSourceMetadata):
        source.enable(active_configuration=initial, connector_available=True, actor_id=EDITOR, at=naive_time)
    with pytest.raises(InvalidSourceMetadata):
        source.update_metadata(name="Renamed Feed", actor_id=EDITOR, at=naive_time)

    assert not source.is_enabled
    assert source.name == SourceName("Example Feed")
    assert (source.updated_at, source.updated_by) == (T0, CREATOR)
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1)]


def test_replacements_advance_versions_without_changing_old_snapshots() -> None:
    """Activate consecutive snapshots without changing an earlier snapshot or the enabled flag."""
    source, initial = register_source()
    second = replace(
        initial, version=2, connector=ConnectorIdentity("other_feed", "3.0.0"), created_at=T1, created_by=EDITOR
    )
    third = replace(second, version=3, created_at=T2, created_by=CREATOR)

    source.add_configuration(second, connector_available=True)
    assert (source.active_version, source.updated_at, source.updated_by) == (2, T1, EDITOR)
    assert not source.is_enabled
    assert source.enable(active_configuration=second, connector_available=True, actor_id=EDITOR, at=T1)
    source.add_configuration(third, connector_available=True)
    assert (source.active_version, source.updated_at, source.updated_by) == (3, T2, CREATOR)
    assert source.is_enabled
    assert (initial.version, initial.connector, initial.created_at) == (1, CONNECTOR, T0)
    assert (second.version, second.created_at, second.created_by) == (2, T1, EDITOR)
    assert source.disable(actor_id=EDITOR, at=T2)
    assert source.pull_events() == [
        SourceRegistered(source.id, T0, 1),
        SourceConfigurationCreated(source.id, T1, 2),
        SourceEnabled(source.id, T1, 2),
        SourceConfigurationCreated(source.id, T2, 3),
        SourceDisabled(source.id, T2, 3),
    ]
    assert source.pull_events() == []


def test_pull_events_drains_independent_batches_in_change_order() -> None:
    """Keep a new batch ordered and intact across no-ops, rejections, and mutation of a drained batch."""
    source, initial = register_source()
    drained = source.pull_events()
    assert drained == [SourceRegistered(source.id, T0, 1)]
    assert source.pull_events() == []

    assert source.update_metadata(name="Renamed Feed", actor_id=EDITOR, at=T1)
    assert not source.update_metadata(name=" Renamed  Feed ", actor_id=CREATOR, at=T2)
    with pytest.raises(SourceConnectorUnavailable):
        source.enable(active_configuration=initial, connector_available=False, actor_id=EDITOR, at=T2)
    assert source.enable(active_configuration=initial, connector_available=True, actor_id=EDITOR, at=T2)

    assert drained == [SourceRegistered(source.id, T0, 1)]
    drained.clear()
    assert source.pull_events() == [
        SourceMetadataUpdated(source.id, T1, ("name",)),
        SourceEnabled(source.id, T2, 1),
    ]
    assert source.pull_events() == []


@pytest.mark.parametrize("invalid_snapshot", ["foreign", "repeated", "skipped", "unavailable"])
def test_rejected_replacement_leaves_pointer_audit_and_events_unchanged(invalid_snapshot: str) -> None:
    """Do not activate an invalid or unavailable replacement, even on a disabled source."""
    source, initial = register_source()
    next_snapshot = replace(initial, version=2, created_at=T1, created_by=EDITOR)
    candidates = {
        "foreign": replace(next_snapshot, source_id=EDITOR),
        "repeated": replace(next_snapshot, version=1),
        "skipped": replace(next_snapshot, version=3),
        "unavailable": next_snapshot,
    }
    expected_error = SourceConnectorUnavailable if invalid_snapshot == "unavailable" else InvalidSourceConfiguration

    with pytest.raises(expected_error):
        source.add_configuration(candidates[invalid_snapshot], connector_available=False)

    assert not source.is_enabled
    assert (source.active_version, source.updated_at, source.updated_by) == (1, T0, CREATOR)
    assert source.pull_events() == [SourceRegistered(source.id, T0, 1)]
