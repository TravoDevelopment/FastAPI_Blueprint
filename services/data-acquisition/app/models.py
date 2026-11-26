"""Model registry for Alembic and tests: import every module's ORM models here."""

from app.db import Base
from app.modules.scraping_jobs.infrastructure.persistence.models import (
    JobAttemptModel,  # noqa: F401
    ParentExecutionModel,  # noqa: F401
    ScheduleOccurrenceModel,  # noqa: F401
    ScrapingJobModel,  # noqa: F401
    ScrapingScheduleModel,  # noqa: F401
)

__all__ = ["Base"]
