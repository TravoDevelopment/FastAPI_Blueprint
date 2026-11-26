"""
HTTP SCHEMAS (Pydantic): the JSON the API accepts and returns.

They check only the SHAPE of the JSON (types, required fields, maximum lengths) and use camelCase on the
wire (`isEnabled`, `sourceUrls`, `createdAt`). The business rules (name uniqueness, URL validation,
hostname boundary, disable-before-delete) stay in the domain, so they hold for every caller.

    POST /v1/sources/   body:  {"name": "Tourism Website A", "sourceUrls": ["https://example.com/p1"]}
    PATCH /v1/sources/{id}:    {"name": "New Name"}           <- send only what changes
    Response:          {"id": "...", "name": "Tourism Website A", "isEnabled": false, ...}
"""

from datetime import datetime
from uuid import UUID

from platform_kit.http.pagination import CamelModel, PageInfo
from pydantic import Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.modules.source_registry.domain.entities import AcquisitionSource
from app.modules.source_registry.domain.value_objects import (
    DESCRIPTION_MAX_LENGTH,
    NAME_MAX_LENGTH,
    URL_MAX_COUNT,
)


class SourceCreate(CamelModel):
    """Body of POST /v1/sources/."""

    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH, examples=["Tourism Website A"])
    description: str | None = Field(None, max_length=DESCRIPTION_MAX_LENGTH, examples=["Sri Lankan attractions"])
    source_urls: list[str] = Field(
        ..., min_length=1, max_length=URL_MAX_COUNT, examples=[["https://example.com/places/sigiriya"]]
    )


class SourceUpdate(CamelModel):
    """Body of PATCH /v1/sources/{id}: every field is optional; omit to leave unchanged."""

    name: str | SkipJsonSchema[None] = Field(default_factory=lambda: None, min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(None, max_length=DESCRIPTION_MAX_LENGTH)
    source_urls: list[str] | SkipJsonSchema[None] = Field(
        default_factory=lambda: None, min_length=1, max_length=URL_MAX_COUNT
    )

    @field_validator("name", "source_urls", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit this field to leave it unchanged; null is not allowed")
        return value


class SourceResponse(CamelModel):
    """One AcquisitionSource as the API returns it."""

    id: UUID
    name: str
    description: str | None
    is_enabled: bool
    source_urls: list[str]
    created_by: UUID
    updated_by: UUID
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, source: AcquisitionSource) -> "SourceResponse":
        """Entity -> JSON: the only place that decides which fields are exposed."""
        return cls(
            id=source.id,
            name=source.name.value,
            description=source.description.value,
            is_enabled=source.is_enabled,
            source_urls=[u.value for u in source.source_urls],
            created_by=source.created_by,
            updated_by=source.updated_by,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )


class SourceList(CamelModel):
    """GET /v1/sources/: one page plus paging info (page, pageSize, totalCount)."""

    sources: list[SourceResponse]
    page_info: PageInfo
