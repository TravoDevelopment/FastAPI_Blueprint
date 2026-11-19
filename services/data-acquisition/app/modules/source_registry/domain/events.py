"""
DOMAIN EVENTS: facts that happened, which other modules or services may react to.

The ENTITY records them when something happens (`SourceRegistry.create` records `SourceRegistryCreated`,
`archive` records `SourceRegistryArchived`). The USE CASE hands them to the `EventPublisher` port, which
publishes them only AFTER the database transaction commits, so nothing is announced for a change that
was rolled back. Today the publisher just logs them (infrastructure/logging_event_publisher.py).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DomainEvent:
    source_registry_id: UUID
    occurred_at: datetime

    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True, slots=True)
class SourceRegistryCreated(DomainEvent):
    code: str


@dataclass(frozen=True, slots=True)
class SourceRegistryArchived(DomainEvent):
    pass


@dataclass(frozen=True, slots=True)
class SourceEvent:
    """A change to an acquisition source, recorded before any publication."""

    source_id: UUID
    occurred_at: datetime

    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True, slots=True)
class SourceRegistered(SourceEvent):
    version: int


@dataclass(frozen=True, slots=True)
class SourceMetadataUpdated(SourceEvent):
    changed_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceEnabled(SourceEvent):
    version: int


@dataclass(frozen=True, slots=True)
class SourceDisabled(SourceEvent):
    version: int


@dataclass(frozen=True, slots=True)
class SourceConfigurationCreated(SourceEvent):
    version: int


type PublishableEvent = DomainEvent | SourceEvent
