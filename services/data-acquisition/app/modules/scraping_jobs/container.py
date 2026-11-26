"""
DEPENDENCY INJECTION: decides which class implements each port and builds the use cases.

The use cases only know the ports (`ScrapingJobRepository`, `EventPublisher`); this file plugs in the real
classes. To use another implementation, change it here only. `db` and `uow` come from the root
container (app/container.py).
"""

from dependency_injector import containers, providers
from platform_kit.database import Database, UnitOfWork

from app.modules.scraping_jobs.application.use_cases import (
    ParentExecutionUseCases,
    ScrapingJobUseCases,
    ScrapingScheduleUseCases,
)
from app.modules.scraping_jobs.infrastructure.logging_event_publisher import LoggingEventPublisher
from app.modules.scraping_jobs.infrastructure.persistence.sqlalchemy_scraping_job_repository import (
    SqlAlchemyJobAttemptRepository,
    SqlAlchemyParentExecutionRepository,
    SqlAlchemyScheduleOccurrenceRepository,
    SqlAlchemyScrapingJobRepository,
    SqlAlchemyScrapingScheduleRepository,
)


class ScrapingJobsContainer(containers.DeclarativeContainer):
    db = providers.Dependency(instance_of=Database)
    uow = providers.Dependency(instance_of=UnitOfWork)

    # Port -> implementation
    scraping_job_repository = providers.Factory(SqlAlchemyScrapingJobRepository, session=db.provided.scoped_session)
    scraping_schedule_repository = providers.Factory(
        SqlAlchemyScrapingScheduleRepository,
        session=db.provided.scoped_session,
    )
    parent_execution_repository = providers.Factory(
        SqlAlchemyParentExecutionRepository,
        session=db.provided.scoped_session,
    )
    job_attempt_repository = providers.Factory(SqlAlchemyJobAttemptRepository, session=db.provided.scoped_session)
    schedule_occurrence_repository = providers.Factory(
        SqlAlchemyScheduleOccurrenceRepository,
        session=db.provided.scoped_session,
    )
    events = providers.Factory(LoggingEventPublisher, uow=uow)

    # Used by router.py as Provide["scraping_jobs.use_cases"].
    use_cases = providers.Factory(
        ScrapingJobUseCases,
        repository=scraping_job_repository,
        attempt_repository=job_attempt_repository,
        events=events,
    )
    scraping_schedule_use_cases = providers.Factory(
        ScrapingScheduleUseCases,
        repository=scraping_schedule_repository,
    )
    parent_execution_use_cases = providers.Factory(
        ParentExecutionUseCases,
        repository=parent_execution_repository,
        scraping_job_repository=scraping_job_repository,
        occurrence_repository=schedule_occurrence_repository,
        events=events,
    )
