"""
HTTP SCHEMAS (Pydantic): the JSON the API accepts and returns.

They check only the SHAPE of the JSON (types, required fields, maximum length) and use camelCase on the
wire (`createdAt`). The business rules (name length, code format, unique code, archived rules) stay in the
domain, so they hold for every caller.

    Request  (POST):  {"name": "Blue pen", "code": "itm-001"}
    Request  (PATCH): {"name": "Red pen"}                        <- send only what changes
    Response:         {"id": "...", "name": "Blue pen", "code": "ITM-001", "status": "active", ...}
"""

from datetime import datetime
from uuid import UUID

from platform_kit.http.pagination import CamelModel, PageInfo
from pydantic import Field

from app.modules.source_registry.domain.entities import SourceRegistry
from app.modules.source_registry.domain.value_objects import CODE_MAX_LENGTH, NAME_MAX_LENGTH, SourceRegistryStatus


class SourceRegistryCreate(CamelModel):
    """Body of POST /v1/source-registry/."""

    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH, examples=["Blue pen"])
    code: str = Field(..., min_length=1, max_length=CODE_MAX_LENGTH, examples=["ITM-001"])


class SourceRegistryUpdate(CamelModel):
    """Body of PATCH /v1/source-registry/{id}: every field is optional."""

    name: str | None = Field(None, min_length=1, max_length=NAME_MAX_LENGTH, examples=["Red pen"])
    code: str | None = Field(None, min_length=1, max_length=CODE_MAX_LENGTH, examples=["ITM-002"])


class SourceRegistryResponse(CamelModel):
    """One source registry as the API returns it."""

    id: UUID
    name: str
    code: str
    status: SourceRegistryStatus
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, source_registry: SourceRegistry) -> "SourceRegistryResponse":
        """Entity -> JSON: the only place that decides which fields are exposed."""
        return cls(
            id=source_registry.id,
            name=source_registry.name.value,
            code=source_registry.code.value,
            status=source_registry.status,
            created_at=source_registry.created_at,
            updated_at=source_registry.updated_at,
        )


class SourceRegistryList(CamelModel):
    """GET /v1/source-registry/: one page plus paging info (page, pageSize, totalCount)."""

    items: list[SourceRegistryResponse]
    page_info: PageInfo
