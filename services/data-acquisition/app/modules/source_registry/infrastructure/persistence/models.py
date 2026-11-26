"""
DATABASE TABLE (SQLAlchemy model): how an AcquisitionSource is stored. Only the repository uses this class.

`source_urls` is stored as a JSONB column (bounded list of ≤ 100 URLs, ≤ 2,048 bytes each).
`AuditColumnsMixin` adds `id`, `created_at`, and `updated_at`. Audit actor UUIDs (created_by,
updated_by) are stored as plain columns — no FK to identity service.

After changing this class: `uv run alembic revision --autogenerate -m "..."`, review it, `uv run task upgrade`.
"""

from uuid import UUID

from platform_kit.persistence import AuditColumnsMixin
from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AcquisitionSourceModel(AuditColumnsMixin, Base):
    __tablename__ = "acquisition_sources"

    # Display name (3–120 chars); unique via name_key below
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Unicode casefolding can expand the display name beyond 120 characters.
    name_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    # Optional free text, up to 2,000 chars; NULL when blank
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whether this source may be used for scraping jobs
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    # JSONB list of canonical HTTPS URL strings (≤ 100 items, ≤ 2,048 bytes each)
    source_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    # Audit actors (identity-service UUIDs; no FK across services)
    created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    updated_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
