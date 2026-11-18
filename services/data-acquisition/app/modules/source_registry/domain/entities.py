"""
ENTITY: the source registry's data, and the ONLY place where that data changes.

Every method follows the same 3 lines:
    1. check the rule        -> a function from policies.py (raises if not allowed)
    2. change the data       -> set the fields
    3. record the event      -> if something worth announcing happened

No rules are written here: they all live in policies.py. Use cases never set fields directly
(`source_registry.status = ...`); they call a method (`source_registry.archive(...)`), so the rule always runs.

Plain Python: no FastAPI, Pydantic or SQLAlchemy. The table is a separate class (models.py).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.modules.source_registry.domain.events import DomainEvent, SourceRegistryArchived, SourceRegistryCreated
from app.modules.source_registry.domain.policies import (
    ensure_can_archive,
    ensure_can_delete,
    ensure_can_restore,
    ensure_code_is_free,
    ensure_is_active,
)
from app.modules.source_registry.domain.value_objects import (
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
