"""create acquisition_sources

Revision ID: 8fc148aebf87
Revises:
Create Date: 2026-11-25 16:00:00.000000

Handwritten to match AcquisitionSourceModel exactly.
For later changes, autogenerate a NEW revision (`uv run alembic revision --autogenerate -m "..."`);
never edit this one after it has been applied.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import config

# revision identifiers, used by Alembic.
revision: str = "8fc148aebf87"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = config.DB_SCHEMA


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "acquisition_sources",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("source_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acquisition_sources")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_acquisition_sources_is_enabled"),
        "acquisition_sources",
        ["is_enabled"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_acquisition_sources_name_key"),
        "acquisition_sources",
        ["name_key"],
        unique=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_acquisition_sources_name_key"), table_name="acquisition_sources", schema=SCHEMA)
    op.drop_index(op.f("ix_acquisition_sources_is_enabled"), table_name="acquisition_sources", schema=SCHEMA)
    op.drop_table("acquisition_sources", schema=SCHEMA)
