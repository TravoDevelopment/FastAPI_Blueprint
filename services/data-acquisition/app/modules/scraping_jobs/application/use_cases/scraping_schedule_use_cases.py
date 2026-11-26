"""Application orchestration for scraping schedules."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.scraping_jobs.application.ports import (
    ScrapingScheduleRepository,
)
from app.modules.scraping_jobs.domain.entities import ScrapingSchedule
from app.modules.scraping_jobs.domain.exceptions import (
    InvalidScheduleFrequency,
    InvalidScheduleInterval,
)
from app.modules.scraping_jobs.domain.value_objects import (
    ScheduleFrequency,
    ScheduleName,
)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC time."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateScrapingScheduleCommand:
    """Input for creating a weekly scraping schedule."""

    name: str
    next_run_at: datetime
    frequency: ScheduleFrequency = ScheduleFrequency.WEEKLY
    interval_days: int = 7


class ScrapingScheduleUseCases:
    """Coordinates schedule lifecycle operations."""

    def __init__(
        self,
        repository: ScrapingScheduleRepository,
        clock: Clock = utc_now,
    ) -> None:
        self.repository = repository
        self.clock = clock

    async def create(self, command: CreateScrapingScheduleCommand) -> ScrapingSchedule:
        """Creates a disabled schedule; enabling is a separate state transition."""
        if command.frequency is not ScheduleFrequency.WEEKLY:
            raise InvalidScheduleFrequency("Only weekly schedules are supported")
        if command.interval_days != 7:
            raise InvalidScheduleInterval("Weekly schedules must use an interval of 7")

        schedule = ScrapingSchedule.create(
            name=ScheduleName(command.name),
            next_run_at=command.next_run_at,
            at=self.clock(),
            frequency=command.frequency,
            interval_days=command.interval_days,
        )
        await self.repository.add(schedule)
        return schedule

    async def enable(self, schedule_id: UUID) -> ScrapingSchedule:
        """Enables an existing schedule."""
        schedule = await self.repository.get(schedule_id)
        schedule.enable(at=self.clock())
        await self.repository.update(schedule)
        return schedule

    async def disable(self, schedule_id: UUID) -> ScrapingSchedule:
        """Disables an existing schedule."""
        schedule = await self.repository.get(schedule_id)
        schedule.disable(at=self.clock())
        await self.repository.update(schedule)
        return schedule

    async def delete(self, schedule_id: UUID) -> ScrapingSchedule:
        """Soft-deletes an existing schedule."""
        schedule = await self.repository.get(schedule_id)
        schedule.delete(at=self.clock())
        await self.repository.update(schedule)
        return schedule
