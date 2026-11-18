"""
Source Registry domain entities, independent of HTTP and persistence.

The generated SourceRegistry changes through methods that check policies and record events.
SourceConfiguration is an immutable snapshot that validates its own fields at construction.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from app.modules.source_registry.domain.events import (
    DomainEvent,
    SourceConfigurationCreated,
    SourceDisabled,
    SourceEnabled,
    SourceEvent,
    SourceMetadataUpdated,
    SourceRegistered,
    SourceRegistryArchived,
    SourceRegistryCreated,
)
from app.modules.source_registry.domain.exceptions import InvalidSourceConfiguration, InvalidSourceMetadata
from app.modules.source_registry.domain.policies import (
    ensure_can_archive,
    ensure_can_delete,
    ensure_can_restore,
    ensure_code_is_free,
    ensure_enable_eligible,
    ensure_is_active,
    ensure_replacement_eligible,
)
from app.modules.source_registry.domain.value_objects import (
    ApprovedDomain,
    ApprovedEndpoint,
    ConnectorIdentity,
    SourceClassification,
    SourceDescription,
    SourceName,
    SourceRegistryCode,
    SourceRegistryName,
    SourceRegistryStatus,
)


@dataclass(slots=True)
class SourceRegistry:
    # --- Properties -----------------------------------------------------------------------------
    id: UUID
    name: SourceRegistryName
    code: SourceRegistryCode
    status: SourceRegistryStatus = SourceRegistryStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # --- Changes: 1. rule  2. change  3. event ---------------------------------------------------

    @classmethod
    def create(
        cls, *, name: SourceRegistryName, code: SourceRegistryCode, code_taken: bool, at: datetime
    ) -> "SourceRegistry":
        ensure_code_is_free(code, taken=code_taken)  # 1. rule
        source_registry = cls(id=uuid4(), name=name, code=code, created_at=at, updated_at=at)  # 2. change
        source_registry._events.append(SourceRegistryCreated(source_registry.id, at, code=code.value))  # 3. event
        return source_registry

    def rename(self, name: SourceRegistryName, *, at: datetime) -> None:
        ensure_is_active(self, action="rename")  # 1. rule
        self.name, self.updated_at = name, at  # 2. change

    def change_code(self, code: SourceRegistryCode, *, code_taken: bool, at: datetime) -> None:
        ensure_is_active(self, action="change the code of")  # 1. rules
        ensure_code_is_free(code, taken=code_taken)
        self.code, self.updated_at = code, at  # 2. change

    def archive(self, *, at: datetime) -> None:
        ensure_can_archive(self)  # 1. rule
        self.status, self.updated_at = SourceRegistryStatus.ARCHIVED, at  # 2. change
        self._events.append(SourceRegistryArchived(self.id, at))  # 3. event

    def restore(self, *, at: datetime) -> None:
        ensure_can_restore(self)  # 1. rule
        self.status, self.updated_at = SourceRegistryStatus.ACTIVE, at  # 2. change

    def delete(self) -> None:
        """Only the rule: the repository removes the row."""
        ensure_can_delete(self)

    # --- Events ---------------------------------------------------------------------------------

    def pull_events(self) -> list[DomainEvent]:
        """Returns and clears the events recorded since the last call (the use case publishes them)."""
        events, self._events = self._events, []
        return events


@dataclass(frozen=True, slots=True, init=False)
class SourceConfiguration:
    """Complete snapshot identified by (source_id, version).

    Endpoint hosts must be listed exactly: approving a parent domain does not
    approve its subdomains. Rules are unique by canonical URL and match mode,
    so exact and subtree rules may share a URL.
    """

    # --- Properties -----------------------------------------------------------------------------
    source_id: UUID
    version: int
    classification: SourceClassification
    approved_domains: tuple[ApprovedDomain, ...]
    approved_endpoints: tuple[ApprovedEndpoint, ...]
    connector: ConnectorIdentity
    created_at: datetime
    created_by: UUID

    # --- Local rules ----------------------------------------------------------------------------

    def __init__(
        self,
        *,
        source_id: UUID,
        version: int,
        classification: SourceClassification,
        approved_domains: list[ApprovedDomain] | tuple[ApprovedDomain, ...],
        approved_endpoints: list[ApprovedEndpoint] | tuple[ApprovedEndpoint, ...],
        connector: ConnectorIdentity,
        created_at: datetime,
        created_by: UUID,
    ) -> None:
        if not isinstance(source_id, UUID) or not isinstance(created_by, UUID):
            raise InvalidSourceConfiguration("Source ID and creator ID must be UUIDs")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise InvalidSourceConfiguration("Configuration version must be a positive integer")
        if not isinstance(classification, SourceClassification):
            raise InvalidSourceConfiguration("Configuration classification must be a SourceClassification")
        if not isinstance(connector, ConnectorIdentity):
            raise InvalidSourceConfiguration("Configuration connector must be a ConnectorIdentity")
        if not isinstance(created_at, datetime) or created_at.utcoffset() is None:
            raise InvalidSourceConfiguration("Configuration creation time must be timezone-aware")

        if not isinstance(approved_domains, (list, tuple)) or not 1 <= len(approved_domains) <= 100:
            raise InvalidSourceConfiguration("Configuration must contain 1–100 approved domains")
        if not isinstance(approved_endpoints, (list, tuple)) or not 1 <= len(approved_endpoints) <= 100:
            raise InvalidSourceConfiguration("Configuration must contain 1–100 approved endpoints")
        domains = tuple(approved_domains)
        endpoints = tuple(approved_endpoints)
        if not all(isinstance(domain, ApprovedDomain) for domain in domains):
            raise InvalidSourceConfiguration("Approved domains must be ApprovedDomain values")
        if not all(isinstance(endpoint, ApprovedEndpoint) for endpoint in endpoints):
            raise InvalidSourceConfiguration("Approved endpoints must be ApprovedEndpoint values")
        approved_hosts = {domain.value for domain in domains}
        if len(approved_hosts) != len(domains):
            raise InvalidSourceConfiguration("Approved domains must be unique")
        if len({(endpoint.url, endpoint.match) for endpoint in endpoints}) != len(endpoints):
            raise InvalidSourceConfiguration("Approved endpoint rules must be unique")
        if any(urlsplit(endpoint.url).hostname not in approved_hosts for endpoint in endpoints):
            raise InvalidSourceConfiguration("Each endpoint hostname must exactly match an approved domain")

        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "classification", classification)
        object.__setattr__(self, "approved_domains", domains)
        object.__setattr__(self, "approved_endpoints", endpoints)
        object.__setattr__(self, "connector", connector)
        object.__setattr__(self, "created_at", created_at.astimezone(UTC))
        object.__setattr__(self, "created_by", created_by)

    # --- Events ---------------------------------------------------------------------------------
    # No events


class _Omitted(Enum):
    VALUE = auto()


@dataclass(slots=True, eq=False, kw_only=True)
class AcquisitionSource:
    """Owns source changes and the active version, not the configuration history."""

    # --- Properties -----------------------------------------------------------------------------
    _id: UUID
    _name: SourceName
    _description: SourceDescription
    _is_enabled: bool
    _active_version: int
    _created_at: datetime
    _updated_at: datetime
    _created_by: UUID
    _updated_by: UUID
    _events: list[SourceEvent] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not all(isinstance(value, UUID) for value in (self._id, self._created_by, self._updated_by)):
            raise InvalidSourceMetadata("Source ID, creator ID, and updater ID must be UUIDs")
        if not isinstance(self._name, SourceName) or not isinstance(self._description, SourceDescription):
            raise InvalidSourceMetadata("Source metadata must use SourceName and SourceDescription values")
        if not isinstance(self._is_enabled, bool):
            raise InvalidSourceMetadata("Source enabled state must be a boolean")
        version = self._active_version
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise InvalidSourceConfiguration("Active configuration version must be a positive integer")
        self._created_at = self._audit_time(self._created_at)
        self._updated_at = self._audit_time(self._updated_at, not_before=self._created_at)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def name(self) -> SourceName:
        return self._name

    @property
    def description(self) -> SourceDescription:
        return self._description

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    @property
    def active_version(self) -> int:
        return self._active_version

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def created_by(self) -> UUID:
        return self._created_by

    @property
    def updated_by(self) -> UUID:
        return self._updated_by

    # --- Local rules and changes ----------------------------------------------------------------

    @classmethod
    def register(
        cls,
        *,
        name: str,
        description: str | None = None,
        classification: SourceClassification,
        approved_domains: list[ApprovedDomain] | tuple[ApprovedDomain, ...],
        approved_endpoints: list[ApprovedEndpoint] | tuple[ApprovedEndpoint, ...],
        connector: ConnectorIdentity,
        actor_id: UUID,
        at: datetime,
    ) -> tuple[Self, SourceConfiguration]:
        """Create the disabled source and its first snapshot as a pair."""
        source_id = uuid4()
        source_name = SourceName(name)
        source_description = SourceDescription(description)
        initial = SourceConfiguration(
            source_id=source_id,
            version=1,
            classification=classification,
            approved_domains=approved_domains,
            approved_endpoints=approved_endpoints,
            connector=connector,
            created_at=at,
            created_by=actor_id,
        )
        source = cls(
            _id=source_id,
            _name=source_name,
            _description=source_description,
            _is_enabled=False,
            _active_version=initial.version,
            _created_at=initial.created_at,
            _updated_at=initial.created_at,
            _created_by=actor_id,
            _updated_by=actor_id,
        )
        source._events.append(SourceRegistered(source_id, initial.created_at, initial.version))
        return source, initial

    @classmethod
    def rehydrate(
        cls,
        *,
        source_id: UUID,
        name: SourceName,
        description: SourceDescription,
        is_enabled: bool,
        active_version: int,
        created_at: datetime,
        updated_at: datetime,
        created_by: UUID,
        updated_by: UUID,
    ) -> Self:
        """Rebuild an existing source without recording a registration event."""
        return cls(
            _id=source_id,
            _name=name,
            _description=description,
            _is_enabled=is_enabled,
            _active_version=active_version,
            _created_at=created_at,
            _updated_at=updated_at,
            _created_by=created_by,
            _updated_by=updated_by,
        )

    def update_metadata(
        self,
        *,
        name: str | _Omitted = _Omitted.VALUE,
        description: str | None | _Omitted = _Omitted.VALUE,
        actor_id: UUID,
        at: datetime,
    ) -> bool:
        """Apply supplied metadata fields; return whether normalized values changed."""
        next_name = self._name if isinstance(name, _Omitted) else SourceName(name)
        next_description = self._description if isinstance(description, _Omitted) else SourceDescription(description)
        changed_fields = tuple(
            field_name
            for field_name, previous, proposed in (
                ("name", self._name, next_name),
                ("description", self._description, next_description),
            )
            if previous != proposed
        )
        if not changed_fields:
            return False

        event = SourceMetadataUpdated(self.id, self._audit_time(at, not_before=self.created_at), changed_fields)
        self._name = next_name
        self._description = next_description
        self._record_change(event, actor_id=actor_id)
        return True

    def enable(
        self,
        *,
        active_configuration: SourceConfiguration | None,
        connector_available: bool,
        actor_id: UUID,
        at: datetime,
    ) -> bool:
        """Enable collection only with this source's active snapshot and its available connector."""
        if self.is_enabled:
            return False
        ensure_enable_eligible(
            active_configuration_exists=(
                active_configuration is not None
                and active_configuration.source_id == self.id
                and active_configuration.version == self.active_version
            ),
            connector_available=connector_available,
        )
        event = SourceEnabled(self.id, self._audit_time(at, not_before=self.created_at), self.active_version)
        self._is_enabled = True
        self._record_change(event, actor_id=actor_id)
        return True

    def disable(self, *, actor_id: UUID, at: datetime) -> bool:
        """Stop collection without changing the active snapshot."""
        if not self.is_enabled:
            return False
        event = SourceDisabled(self.id, self._audit_time(at, not_before=self.created_at), self.active_version)
        self._is_enabled = False
        self._record_change(event, actor_id=actor_id)
        return True

    def add_configuration(self, configuration: SourceConfiguration, *, connector_available: bool) -> None:
        """Activate the next version, using the snapshot's timestamp and creator for attribution."""
        if configuration.source_id != self.id:
            raise InvalidSourceConfiguration("Replacement configuration must belong to this source")
        if configuration.version != self.active_version + 1:
            raise InvalidSourceConfiguration("Replacement configuration must be the next version")
        ensure_replacement_eligible(connector_available=connector_available)

        at = self._audit_time(configuration.created_at, not_before=self.created_at)
        event = SourceConfigurationCreated(self.id, at, configuration.version)
        self._active_version = configuration.version
        self._record_change(event, actor_id=configuration.created_by)

    @staticmethod
    def _audit_time(at: datetime, *, not_before: datetime | None = None) -> datetime:
        if not isinstance(at, datetime) or at.utcoffset() is None:
            raise InvalidSourceMetadata("Source audit timestamps must be timezone-aware datetimes")
        normalized = at.astimezone(UTC)
        if not_before is not None and normalized < not_before:
            raise InvalidSourceMetadata("Source update time must not precede creation time")
        return normalized

    # --- Events ---------------------------------------------------------------------------------

    def _record_change(self, event: SourceEvent, *, actor_id: UUID) -> None:
        self._updated_at = event.occurred_at
        self._updated_by = actor_id
        self._events.append(event)

    def pull_events(self) -> list[SourceEvent]:
        """Return and clear pending events without publishing them."""
        events, self._events = self._events, []
        return events
