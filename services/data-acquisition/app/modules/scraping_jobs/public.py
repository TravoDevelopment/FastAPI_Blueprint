"""
PUBLIC API of the scraping_jobs module: the ONLY file other modules may import.

Re-exports application contracts and domain types only; no business logic or infrastructure leaks.
"""

from app.modules.scraping_jobs.application.use_cases import (
    CreateScrapingScheduleCommand,
    FailScrapingJobCommand,
    ParentExecutionUseCases,
    RecordScrapingResultCommand,
    ScrapingJobUseCases,
    ScrapingScheduleUseCases,
    StartParentExecutionCommand,
)
from app.modules.scraping_jobs.domain.entities import (
    ParentExecution,
    ScrapingJob,
    ScrapingSchedule,
)
from app.modules.scraping_jobs.domain.value_objects import (
    ParentExecutionStatus,
    ScrapingJobStatus,
)

__all__ = [
    "CreateScrapingScheduleCommand",
    "FailScrapingJobCommand",
    "ParentExecution",
    "ParentExecutionStatus",
    "ParentExecutionUseCases",
    "RecordScrapingResultCommand",
    "ScrapingJob",
    "ScrapingJobStatus",
    "ScrapingJobUseCases",
    "ScrapingSchedule",
    "ScrapingScheduleUseCases",
    "StartParentExecutionCommand",
]
