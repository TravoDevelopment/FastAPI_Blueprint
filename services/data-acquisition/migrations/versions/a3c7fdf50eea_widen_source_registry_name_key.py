"""widen source registry name key

Revision ID: a3c7fdf50eea
Revises: 8fc148aebf87
Create Date: 2026-11-25 23:03:58.105652

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.config import config

# revision identifiers, used by Alembic.
revision: str = "a3c7fdf50eea"
down_revision: str | Sequence[str] | None = "8fc148aebf87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow Unicode casefolded keys to exceed the display name length limit."""
    op.alter_column(
        "acquisition_sources",
        "name_key",
        existing_type=sa.VARCHAR(length=120),
        type_=sa.Text(),
        existing_nullable=False,
        schema=config.DB_SCHEMA,
    )


def downgrade() -> None:
    """Restore the old limit, failing if any stored key exceeds it."""
    op.alter_column(
        "acquisition_sources",
        "name_key",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=120),
        existing_nullable=False,
        schema=config.DB_SCHEMA,
    )
