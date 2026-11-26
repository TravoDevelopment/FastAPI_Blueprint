"""SQLAlchemy adapters for the scraping-jobs repository ports."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scraping_jobs.application.ports import (
    JobAttemptRepository,
    ParentExecutionRepository,
    ScheduleOccurrenceRepository,
    ScrapingJobPage,
    ScrapingJobRepository,
    ScrapingScheduleRepository,
)
from app.modules.scraping_jobs.domain.entities import (
    JobAttempt,
    ParentExecution,
    ScheduleOccurrence,
    ScrapingJob,
    ScrapingSchedule,
)
from app.modules.scraping_jobs.domain.exceptions import (
    ParentExecutionNotFound,
    ScheduleOccurrenceAlreadyClaimed,
    ScrapingJobNotFound,
    ScrapingScheduleNotFound,
)
from app.modules.scraping_jobs.domain.value_objects import (
    JobAttemptPhase,
    JobAttemptStatus,
    OccurrenceKey,
    ParentExecutionStatus,
    RetryPolicy,
    ScheduleFrequency,
    ScheduleName,
    ScheduleOccurrenceStatus,
    ScrapingJobStatus,
    SourceUrl,
    TriggerType,
)
from app.modules.scraping_jobs.infrastructure.persistence.models import (
    JobAttemptModel,
    ParentExecutionModel,
    ScheduleOccurrenceModel,
    ScrapingJobModel,
    ScrapingScheduleModel,
)

_OCCURRENCE_KEY_CONSTRAINT = "uq_schedule_occurrence_schedule_key"


class _SqlAlchemyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session


class SqlAlchemyScrapingJobRepository(_SqlAlchemyRepository, ScrapingJobRepository):
    async def add(self, scraping_job: ScrapingJob) -> None:
        row = self._to_model(scraping_job)
        self.session.add(row)
        await self.session.flush()
        scraping_job.created_at, scraping_job.updated_at = row.created_at, row.updated_at

    async def add_many(self, scraping_jobs: Sequence[ScrapingJob]) -> None:
        rows = [self._to_model(job) for job in scraping_jobs]
        self.session.add_all(rows)
        await self.session.flush()
        for job, row in zip(scraping_jobs, rows, strict=True):
            job.created_at, job.updated_at = row.created_at, row.updated_at

    async def get(self, scraping_job_id: UUID) -> ScrapingJob:
        row = await self.session.get(ScrapingJobModel, scraping_job_id, populate_existing=True)
        if row is None:
            raise ScrapingJobNotFound()
        return self._to_entity(row)

    async def list_by_parent(self, parent_execution_id: UUID) -> list[ScrapingJob]:
        rows = await self.session.scalars(
            select(ScrapingJobModel)
            .where(ScrapingJobModel.parent_execution_id == parent_execution_id)
            .order_by(ScrapingJobModel.created_at, ScrapingJobModel.id)
        )
        return [self._to_entity(row) for row in rows]

    async def list_by_parent_page(
        self,
        parent_execution_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> ScrapingJobPage:
        total = await self.session.scalar(
            select(func.count())
            .select_from(ScrapingJobModel)
            .where(ScrapingJobModel.parent_execution_id == parent_execution_id)
        )
        rows = await self.session.scalars(
            select(ScrapingJobModel)
            .where(ScrapingJobModel.parent_execution_id == parent_execution_id)
            .order_by(ScrapingJobModel.created_at, ScrapingJobModel.id)
            .offset(offset)
            .limit(limit)
        )
        return ScrapingJobPage(items=[self._to_entity(row) for row in rows], total=total or 0)

    async def list_retryable(self) -> list[ScrapingJob]:
        rows = await self.session.scalars(
            select(ScrapingJobModel)
            .where(ScrapingJobModel.status == ScrapingJobStatus.RETRYABLE_FAILURE.value)
            .order_by(ScrapingJobModel.updated_at, ScrapingJobModel.id)
        )
        return [self._to_entity(row) for row in rows]

    async def update(self, scraping_job: ScrapingJob) -> None:
        row = await self.session.get(ScrapingJobModel, scraping_job.id)
        if row is None:
            raise ScrapingJobNotFound()
        row.parent_execution_id = scraping_job.parent_execution_id
        row.source_id = scraping_job.source_id
        row.source_url = scraping_job.source_url.value
        row.category_id = scraping_job.category_id
        row.status = scraping_job.status.value
        row.result_reference = scraping_job.result_reference
        row.retry_max_attempts = scraping_job.retry_policy.max_attempts
        row.retry_delay_seconds = scraping_job.retry_policy.delay_seconds
        if scraping_job.updated_at is not None:
            row.updated_at = scraping_job.updated_at
        row.version += 1
        await self.session.flush()
        scraping_job.updated_at = row.updated_at

    @staticmethod
    def _to_model(scraping_job: ScrapingJob) -> ScrapingJobModel:
        return ScrapingJobModel(
            id=scraping_job.id,
            parent_execution_id=scraping_job.parent_execution_id,
            source_id=scraping_job.source_id,
            source_url=scraping_job.source_url.value,
            category_id=scraping_job.category_id,
            status=scraping_job.status.value,
            result_reference=scraping_job.result_reference,
            retry_max_attempts=scraping_job.retry_policy.max_attempts,
            retry_delay_seconds=scraping_job.retry_policy.delay_seconds,
            created_at=scraping_job.created_at,
            updated_at=scraping_job.updated_at,
            version=1,
        )

    @staticmethod
    def _to_entity(row: ScrapingJobModel) -> ScrapingJob:
        return ScrapingJob(
            id=row.id,
            parent_execution_id=row.parent_execution_id,
            source_id=row.source_id,
            source_url=SourceUrl(row.source_url),
            category_id=row.category_id,
            status=ScrapingJobStatus(row.status),
            result_reference=row.result_reference,
            retry_policy=RetryPolicy(
                max_attempts=row.retry_max_attempts,
                delay_seconds=row.retry_delay_seconds,
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SqlAlchemyScrapingScheduleRepository(_SqlAlchemyRepository, ScrapingScheduleRepository):
    async def add(self, schedule: ScrapingSchedule) -> None:
        row = self._to_model(schedule)
        self.session.add(row)
        await self.session.flush()
        schedule.created_at, schedule.updated_at = row.created_at, row.updated_at

    async def get(self, schedule_id: UUID) -> ScrapingSchedule:
        row = await self.session.get(ScrapingScheduleModel, schedule_id, populate_existing=True)
        if row is None:
            raise ScrapingScheduleNotFound()
        return self._to_entity(row)

    async def update(self, schedule: ScrapingSchedule) -> None:
        row = await self.session.get(ScrapingScheduleModel, schedule.id)
        if row is None:
            raise ScrapingScheduleNotFound()
        row.name = schedule.name.value
        row.frequency = schedule.frequency.value
        row.interval_days = schedule.interval_days
        row.next_run_at = schedule.next_run_at
        row.is_enabled = schedule.is_enabled
        row.is_deleted = schedule.is_deleted
        if schedule.updated_at is not None:
            row.updated_at = schedule.updated_at
        row.version += 1
        await self.session.flush()
        schedule.updated_at = row.updated_at

    async def list_enabled_due(self, *, at: datetime) -> list[ScrapingSchedule]:
        rows = await self.session.scalars(
            select(ScrapingScheduleModel)
            .where(
                ScrapingScheduleModel.is_enabled.is_(True),
                ScrapingScheduleModel.is_deleted.is_(False),
                ScrapingScheduleModel.next_run_at <= at,
            )
            .order_by(ScrapingScheduleModel.next_run_at, ScrapingScheduleModel.id)
        )
        return [self._to_entity(row) for row in rows]

    @staticmethod
    def _to_model(schedule: ScrapingSchedule) -> ScrapingScheduleModel:
        return ScrapingScheduleModel(
            id=schedule.id,
            name=schedule.name.value,
            frequency=schedule.frequency.value,
            interval_days=schedule.interval_days,
            next_run_at=schedule.next_run_at,
            is_enabled=schedule.is_enabled,
            is_deleted=schedule.is_deleted,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            version=1,
        )

    @staticmethod
    def _to_entity(row: ScrapingScheduleModel) -> ScrapingSchedule:
        return ScrapingSchedule(
            id=row.id,
            name=ScheduleName(row.name),
            frequency=ScheduleFrequency(row.frequency),
            interval_days=row.interval_days,
            next_run_at=row.next_run_at,
            is_enabled=row.is_enabled,
            is_deleted=row.is_deleted,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SqlAlchemyParentExecutionRepository(_SqlAlchemyRepository, ParentExecutionRepository):
    async def add(self, parent: ParentExecution) -> None:
        row = self._to_model(parent)
        self.session.add(row)
        await self.session.flush()
        parent.created_at = row.created_at

    async def get(self, parent_execution_id: UUID) -> ParentExecution:
        row = await self.session.get(ParentExecutionModel, parent_execution_id, populate_existing=True)
        if row is None:
            raise ParentExecutionNotFound()
        return self._to_entity(row)

    async def update(self, parent: ParentExecution) -> None:
        row = await self.session.get(ParentExecutionModel, parent.id)
        if row is None:
            raise ParentExecutionNotFound()
        row.trigger_type = parent.trigger_type.value
        row.status = parent.status.value
        row.schedule_id = parent.schedule_id
        row.occurrence_id = parent.occurrence_id
        row.discovery_completed = parent.discovery_completed
        row.started_at = parent.started_at
        row.completed_at = parent.completed_at
        row.total_count = parent.total_count
        row.succeeded_count = parent.succeeded_count
        row.failed_count = parent.failed_count
        row.cancelled_count = parent.cancelled_count
        row.version += 1
        await self.session.flush()
        parent.created_at = row.created_at

    @staticmethod
    def _to_model(parent: ParentExecution) -> ParentExecutionModel:
        return ParentExecutionModel(
            id=parent.id,
            trigger_type=parent.trigger_type.value,
            status=parent.status.value,
            schedule_id=parent.schedule_id,
            occurrence_id=parent.occurrence_id,
            discovery_completed=parent.discovery_completed,
            created_at=parent.created_at,
            started_at=parent.started_at,
            completed_at=parent.completed_at,
            total_count=parent.total_count,
            succeeded_count=parent.succeeded_count,
            failed_count=parent.failed_count,
            cancelled_count=parent.cancelled_count,
            version=1,
        )

    @staticmethod
    def _to_entity(row: ParentExecutionModel) -> ParentExecution:
        return ParentExecution(
            id=row.id,
            trigger_type=TriggerType(row.trigger_type),
            status=ParentExecutionStatus(row.status),
            schedule_id=row.schedule_id,
            occurrence_id=row.occurrence_id,
            discovery_completed=row.discovery_completed,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            total_count=row.total_count,
            succeeded_count=row.succeeded_count,
            failed_count=row.failed_count,
            cancelled_count=row.cancelled_count,
        )


class SqlAlchemyJobAttemptRepository(_SqlAlchemyRepository, JobAttemptRepository):
    async def add(self, attempt: JobAttempt) -> None:
        self.session.add(self._to_model(attempt))
        await self.session.flush()

    async def list_by_job(self, scraping_job_id: UUID) -> list[JobAttempt]:
        rows = await self.session.scalars(
            select(JobAttemptModel)
            .where(JobAttemptModel.scraping_job_id == scraping_job_id)
            .order_by(JobAttemptModel.attempt_number, JobAttemptModel.id)
        )
        return [self._to_entity(row) for row in rows]

    async def update(self, attempt: JobAttempt) -> None:
        row = await self.session.get(JobAttemptModel, attempt.id)
        if row is None:
            raise KeyError(f"Job attempt {attempt.id} not found")
        row.phase = attempt.phase.value
        row.attempt_number = attempt.attempt_number
        row.status = attempt.status.value
        row.started_at = attempt.started_at
        row.finished_at = attempt.finished_at
        row.next_retry_at = attempt.next_retry_at
        row.error_code = attempt.error_code
        row.version += 1
        await self.session.flush()

    @staticmethod
    def _to_model(attempt: JobAttempt) -> JobAttemptModel:
        return JobAttemptModel(
            id=attempt.id,
            scraping_job_id=attempt.scraping_job_id,
            phase=attempt.phase.value,
            attempt_number=attempt.attempt_number,
            status=attempt.status.value,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            next_retry_at=attempt.next_retry_at,
            error_code=attempt.error_code,
            version=1,
        )

    @staticmethod
    def _to_entity(row: JobAttemptModel) -> JobAttempt:
        return JobAttempt(
            id=row.id,
            scraping_job_id=row.scraping_job_id,
            phase=JobAttemptPhase(row.phase),
            attempt_number=row.attempt_number,
            status=JobAttemptStatus(row.status),
            started_at=row.started_at,
            finished_at=row.finished_at,
            next_retry_at=row.next_retry_at,
            error_code=row.error_code,
        )


class SqlAlchemyScheduleOccurrenceRepository(_SqlAlchemyRepository, ScheduleOccurrenceRepository):
    async def add(self, occurrence: ScheduleOccurrence) -> None:
        row = self._to_model(occurrence)
        self.session.add(row)
        await self._flush_occurrence_key()
        occurrence.created_at = row.created_at

    async def get(self, occurrence_id: UUID) -> ScheduleOccurrence:
        row = await self.session.get(ScheduleOccurrenceModel, occurrence_id, populate_existing=True)
        if row is None:
            raise KeyError(f"Schedule occurrence {occurrence_id} not found")
        return self._to_entity(row)

    async def get_by_key(
        self,
        *,
        schedule_id: UUID,
        occurrence_key: OccurrenceKey,
    ) -> ScheduleOccurrence | None:
        row = await self.session.scalar(
            select(ScheduleOccurrenceModel).where(
                ScheduleOccurrenceModel.schedule_id == schedule_id,
                ScheduleOccurrenceModel.occurrence_key == occurrence_key.value,
            )
        )
        return None if row is None else self._to_entity(row)

    async def update(self, occurrence: ScheduleOccurrence) -> None:
        row = await self.session.get(ScheduleOccurrenceModel, occurrence.id)
        if row is None:
            raise KeyError(f"Schedule occurrence {occurrence.id} not found")
        row.schedule_id = occurrence.schedule_id
        row.occurrence_key = occurrence.occurrence_key.value
        row.due_at = occurrence.due_at
        row.status = occurrence.status.value
        row.parent_execution_id = occurrence.parent_execution_id
        row.version += 1
        await self._flush_occurrence_key()

    async def _flush_occurrence_key(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as error:
            original = error.orig
            constraint_name = getattr(original, "constraint_name", None)
            if constraint_name is None:
                constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
            if constraint_name == _OCCURRENCE_KEY_CONSTRAINT:
                raise ScheduleOccurrenceAlreadyClaimed("This schedule occurrence already exists") from error
            raise

    @staticmethod
    def _to_model(occurrence: ScheduleOccurrence) -> ScheduleOccurrenceModel:
        return ScheduleOccurrenceModel(
            id=occurrence.id,
            schedule_id=occurrence.schedule_id,
            occurrence_key=occurrence.occurrence_key.value,
            due_at=occurrence.due_at,
            status=occurrence.status.value,
            parent_execution_id=occurrence.parent_execution_id,
            created_at=occurrence.created_at,
            version=1,
        )

    @staticmethod
    def _to_entity(row: ScheduleOccurrenceModel) -> ScheduleOccurrence:
        return ScheduleOccurrence(
            id=row.id,
            schedule_id=row.schedule_id,
            occurrence_key=OccurrenceKey(row.occurrence_key),
            due_at=row.due_at,
            status=ScheduleOccurrenceStatus(row.status),
            parent_execution_id=row.parent_execution_id,
            created_at=row.created_at,
        )
