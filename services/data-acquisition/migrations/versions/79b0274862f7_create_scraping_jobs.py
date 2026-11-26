"""create scraping-jobs persistence tables

Revision ID: 79b0274862f7
Revises:
Create Date: 2026-11-22 09:55:13.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.config import config

revision: str = "79b0274862f7"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = config.DB_SCHEMA


def upgrade() -> None:
    """Create the scraping-jobs persistence schema."""
    op.create_table(
        "scraping_schedules",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("frequency", sa.String(length=24), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("next_run_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("interval_days > 0", name=op.f("ck_scraping_schedules_positive_interval_days")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scraping_schedules")),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_scraping_schedules_enabled_next_run",
        "scraping_schedules",
        ["is_enabled", "next_run_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "parent_executions",
        sa.Column("trigger_type", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurrence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("discovery_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("total_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("succeeded_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cancelled_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "total_count >= 0 AND succeeded_count >= 0 AND failed_count >= 0 AND cancelled_count >= 0",
            name=op.f("ck_parent_executions_nonnegative_summary_counts"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            [f"{SCHEMA}.scraping_schedules.id"],
            name=op.f("fk_parent_executions_schedule_id_scraping_schedules"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parent_executions")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_parent_executions_status"),
        "parent_executions",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_parent_executions_schedule_id"),
        "parent_executions",
        ["schedule_id"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "scraping_jobs",
        sa.Column("parent_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_reference", sa.Text(), nullable=True),
        sa.Column("retry_max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("retry_delay_seconds", sa.Integer(), server_default=sa.text("60"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("retry_max_attempts >= 1", name=op.f("ck_scraping_jobs_positive_retry_max_attempts")),
        sa.CheckConstraint("retry_delay_seconds >= 0", name=op.f("ck_scraping_jobs_nonnegative_retry_delay_seconds")),
        sa.ForeignKeyConstraint(
            ["parent_execution_id"],
            [f"{SCHEMA}.parent_executions.id"],
            name=op.f("fk_scraping_jobs_parent_execution_id_parent_executions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scraping_jobs")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_scraping_jobs_parent_execution_id"),
        "scraping_jobs",
        ["parent_execution_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_scraping_jobs_source_id"),
        "scraping_jobs",
        ["source_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_scraping_jobs_category_id"),
        "scraping_jobs",
        ["category_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_scraping_jobs_status"),
        "scraping_jobs",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_scraping_jobs_parent_status",
        "scraping_jobs",
        ["parent_execution_id", "status"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "job_attempts",
        sa.Column("scraping_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase", sa.String(length=24), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_retry_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempt_number >= 1", name=op.f("ck_job_attempts_positive_attempt_number")),
        sa.ForeignKeyConstraint(
            ["scraping_job_id"],
            [f"{SCHEMA}.scraping_jobs.id"],
            name=op.f("fk_job_attempts_scraping_job_id_scraping_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_attempts")),
        sa.UniqueConstraint("scraping_job_id", "attempt_number", name="uq_job_attempt_job_number"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_job_attempts_scraping_job_id"),
        "job_attempts",
        ["scraping_job_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_job_attempts_status"),
        "job_attempts",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_job_attempts_next_retry_at"),
        "job_attempts",
        ["next_retry_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "schedule_occurrences",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurrence_key", sa.Text(), nullable=False),
        sa.Column("due_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("parent_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            [f"{SCHEMA}.scraping_schedules.id"],
            name=op.f("fk_schedule_occurrences_schedule_id_scraping_schedules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_execution_id"],
            [f"{SCHEMA}.parent_executions.id"],
            name=op.f("fk_schedule_occurrences_parent_execution_id_parent_executions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_occurrences")),
        sa.UniqueConstraint("schedule_id", "occurrence_key", name="uq_schedule_occurrence_schedule_key"),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_schedule_occurrences_schedule_id"),
        "schedule_occurrences",
        ["schedule_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_schedule_occurrences_parent_execution_id"),
        "schedule_occurrences",
        ["parent_execution_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_schedule_occurrences_status"),
        "schedule_occurrences",
        ["status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_schedule_occurrences_status_due_at",
        "schedule_occurrences",
        ["status", "due_at"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_foreign_key(
        "fk_parent_executions_occurrence_id_schedule_occurrences",
        "parent_executions",
        "schedule_occurrences",
        ["occurrence_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Drop the scraping-jobs persistence schema."""
    op.drop_constraint(
        "fk_parent_executions_occurrence_id_schedule_occurrences",
        "parent_executions",
        schema=SCHEMA,
        type_="foreignkey",
    )

    op.drop_index("ix_schedule_occurrences_status_due_at", table_name="schedule_occurrences", schema=SCHEMA)
    op.drop_index(op.f("ix_schedule_occurrences_status"), table_name="schedule_occurrences", schema=SCHEMA)
    op.drop_index(op.f("ix_schedule_occurrences_parent_execution_id"), table_name="schedule_occurrences", schema=SCHEMA)
    op.drop_index(op.f("ix_schedule_occurrences_schedule_id"), table_name="schedule_occurrences", schema=SCHEMA)
    op.drop_table("schedule_occurrences", schema=SCHEMA)

    op.drop_index(op.f("ix_job_attempts_next_retry_at"), table_name="job_attempts", schema=SCHEMA)
    op.drop_index(op.f("ix_job_attempts_status"), table_name="job_attempts", schema=SCHEMA)
    op.drop_index(op.f("ix_job_attempts_scraping_job_id"), table_name="job_attempts", schema=SCHEMA)
    op.drop_table("job_attempts", schema=SCHEMA)

    op.drop_index("ix_scraping_jobs_parent_status", table_name="scraping_jobs", schema=SCHEMA)
    op.drop_index(op.f("ix_scraping_jobs_status"), table_name="scraping_jobs", schema=SCHEMA)
    op.drop_index(op.f("ix_scraping_jobs_category_id"), table_name="scraping_jobs", schema=SCHEMA)
    op.drop_index(op.f("ix_scraping_jobs_source_id"), table_name="scraping_jobs", schema=SCHEMA)
    op.drop_index(op.f("ix_scraping_jobs_parent_execution_id"), table_name="scraping_jobs", schema=SCHEMA)
    op.drop_table("scraping_jobs", schema=SCHEMA)

    op.drop_index(op.f("ix_parent_executions_schedule_id"), table_name="parent_executions", schema=SCHEMA)
    op.drop_index(op.f("ix_parent_executions_status"), table_name="parent_executions", schema=SCHEMA)
    op.drop_table("parent_executions", schema=SCHEMA)

    op.drop_index("ix_scraping_schedules_enabled_next_run", table_name="scraping_schedules", schema=SCHEMA)
    op.drop_table("scraping_schedules", schema=SCHEMA)
