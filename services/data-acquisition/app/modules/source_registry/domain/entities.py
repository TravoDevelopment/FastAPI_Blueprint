"""
ENTITY: AcquisitionSource — the source registry's data, and the ONLY place where that data changes.

Every method follows the same 3 lines:
    1. check the rule        -> a function from policies.py (raises if not allowed)
    2. change the data       -> set the fields
    3. record the event      -> if something worth announcing happened

No rules are written here: they all live in policies.py. Use cases never set fields directly
(`source.is_enabled = True`); they call a method (`source.enable(...)`), so the rule always runs.

Plain Python: no FastAPI, Pydantic or SQLAlchemy. The table is a separate class (models.py).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.modules.source_registry.domain.events import (
    DomainEvent,
    SourceCreated,
    SourceDeleted,
    SourceDisabled,
    SourceEnabled,
    SourceUpdated,
)
from app.modules.source_registry.domain.policies import (
    ensure_details_changed,
    ensure_source_disabled,
    ensure_source_enabled,
    ensure_source_name_is_free,
    ensure_source_not_enabled,
)
from app.modules.source_registry.domain.value_objects import (
    SourceDescription,
    SourceName,
    SourceUrlList,
)


@dataclass(slots=True)
class AcquisitionSource:
    # --- Properties -------------------------------------------------------------------------------
    id: UUID
    name: SourceName
    description: SourceDescription
    is_enabled: bool
    source_urls: SourceUrlList
    created_by: UUID
    updated_by: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    # --- Changes: 1. rule  2. change  3. event ----------------------------------------------------

    @classmethod
    def register(
        cls,
        *,
        name: SourceName,
        description: SourceDescription,
        source_urls: SourceUrlList,
        created_by: UUID,
        name_taken: bool,
        at: datetime,
    ) -> "AcquisitionSource":
        ensure_source_name_is_free(name, taken=name_taken)  # 1. rule
        source = cls(  # 2. change
            id=uuid4(),
            name=name,
            description=description,
            is_enabled=False,
            source_urls=source_urls,
            created_by=created_by,
            updated_by=created_by,
            created_at=at,
            updated_at=at,
        )
        source._events.append(SourceCreated(source.id, at, source_name=name.value))  # 3. event
        return source

    def update(
        self,
        *,
        name: SourceName | None,
        description: SourceDescription | None,
        source_urls: SourceUrlList | None,
        updated_by: UUID,
        name_taken: bool,
        at: datetime,
    ) -> None:
        ensure_source_name_is_free(name, taken=name_taken)  # 1. rule
        ensure_details_changed(
            self,
            name=name,
            description_value=description.value if description is not None else ...,
            urls=source_urls,
        )  # 1. rule
        self.name, self.description, self.source_urls, self.updated_by, self.updated_at = (
            name or self.name,
            description or self.description,
            source_urls or self.source_urls,
            updated_by,
            at,
        )  # 2. change
        self._events.append(SourceUpdated(self.id, at))  # 3. event

    def enable(self, *, updated_by: UUID, at: datetime) -> None:
        ensure_source_enabled(self)  # 1. rule
        self.is_enabled, self.updated_by, self.updated_at = True, updated_by, at  # 2. change
        self._events.append(SourceEnabled(self.id, at))  # 3. event

    def disable(self, *, updated_by: UUID, at: datetime) -> None:
        ensure_source_not_enabled(self)  # 1. rule
        self.is_enabled, self.updated_by, self.updated_at = False, updated_by, at  # 2. change
        self._events.append(SourceDisabled(self.id, at))  # 3. event

    def delete(self, *, at: datetime) -> None:
        ensure_source_disabled(self)  # 1. rule
        self._events.append(SourceDeleted(self.id, at))  # 3. event

    # --- Events -----------------------------------------------------------------------------------

    def pull_events(self) -> list[DomainEvent]:
        """Returns and clears the events recorded since the last call (the use case publishes them)."""
        events, self._events = self._events, []
        return events
