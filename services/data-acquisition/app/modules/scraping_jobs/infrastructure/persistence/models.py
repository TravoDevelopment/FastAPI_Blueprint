"""SQLAlchemy tables for the scraping-jobs module."""

from datetime import datetime
from uuid import UUID

from platform_kit.persistence import AuditColumnsMixin
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ScrapingScheduleModel(AuditColumnsMixin, Base):
    __tablename__ = "scraping_schedules"
    __table_args__ = (
        CheckConstraint("interval_days > 0", name="positive_interval_days"),
        Index("ix_scraping_schedules_enabled_next_run", "is_enabled", "next_run_at"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(String(24), nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    occurrences: Mapped[list["ScheduleOccurrenceModel"]] = relationship(
        back_populates="scraping_schedule",
        lazy="selectin",
    )
    parent_executions: Mapped[list["ParentExecutionModel"]] = relationship(
        back_populates="scraping_schedule",
        lazy="selectin",
    )


class ParentExecutionModel(AuditColumnsMixin, Base):
    __tablename__ = "parent_executions"
    __table_args__ = (
        CheckConstraint(
            "total_count >= 0 AND succeeded_count >= 0 AND failed_count >= 0 AND cancelled_count >= 0",
            name="nonnegative_summary_counts",
        ),
    )

    trigger_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    schedule_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("scraping_schedules.id", ondelete="SET NULL"),
        index=True,
    )
    occurrence_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "schedule_occurrences.id",
            name="fk_parent_executions_occurrence_id_schedule_occurrences",
            ondelete="SET NULL",
            use_alter=True,
        ),
    )
    discovery_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    succeeded_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    scraping_schedule: Mapped[ScrapingScheduleModel | None] = relationship(
        back_populates="parent_executions",
        lazy="selectin",
    )
    scraping_jobs: Mapped[list["ScrapingJobModel"]] = relationship(
        back_populates="parent_execution",
        lazy="selectin",
    )
    schedule_occurrence: Mapped["ScheduleOccurrenceModel | None"] = relationship(
        foreign_keys=[occurrence_id],
        lazy="selectin",
    )


class ScrapingJobModel(AuditColumnsMixin, Base):
    __tablename__ = "scraping_jobs"
    __table_args__ = (
        CheckConstraint("retry_max_attempts >= 1", name="positive_retry_max_attempts"),
        CheckConstraint("retry_delay_seconds >= 0", name="nonnegative_retry_delay_seconds"),
        Index("ix_scraping_jobs_parent_status", "parent_execution_id", "status"),
    )

    parent_execution_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("parent_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    result_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("60"))

    parent_execution: Mapped[ParentExecutionModel] = relationship(
        back_populates="scraping_jobs",
        lazy="selectin",
    )
    attempts: Mapped[list["JobAttemptModel"]] = relationship(
        back_populates="scraping_job",
        lazy="selectin",
    )


class JobAttemptModel(AuditColumnsMixin, Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="positive_attempt_number"),
        UniqueConstraint("scraping_job_id", "attempt_number", name="uq_job_attempt_job_number"),
    )

    scraping_job_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("scraping_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase: Mapped[str] = mapped_column(String(24), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    scraping_job: Mapped[ScrapingJobModel] = relationship(back_populates="attempts", lazy="selectin")


class ScheduleOccurrenceModel(AuditColumnsMixin, Base):
    __tablename__ = "schedule_occurrences"
    __table_args__ = (
        UniqueConstraint("schedule_id", "occurrence_key", name="uq_schedule_occurrence_schedule_key"),
        Index("ix_schedule_occurrences_status_due_at", "status", "due_at"),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("scraping_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    occurrence_key: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    parent_execution_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("parent_executions.id", ondelete="SET NULL"),
        index=True,
    )

    scraping_schedule: Mapped[ScrapingScheduleModel] = relationship(
        back_populates="occurrences",
        lazy="selectin",
    )
    parent_execution: Mapped[ParentExecutionModel | None] = relationship(
        foreign_keys=[parent_execution_id],
        lazy="selectin",
    )
