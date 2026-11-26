"""HTTP endpoints for scraping-job scheduling and execution workflows."""

from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path, Response, status
from platform_kit.access import require_access
from platform_kit.http.pagination import PageInfo, Pagination

from app.core.security import rate_limit
from app.modules.scraping_jobs.application.use_cases import (
    CreateScrapingScheduleCommand,
    FailScrapingJobCommand,
    ParentExecutionUseCases,
    RecordScrapingResultCommand,
    ScrapingJobUseCases,
    ScrapingScheduleUseCases,
    StartParentExecutionCommand,
)
from app.modules.scraping_jobs.domain.value_objects import SourceUrl
from app.modules.scraping_jobs.schemas import (
    ClaimScheduleOccurrenceRequest,
    CreatedScrapingJobsResponse,
    CreateScrapingScheduleRequest,
    DiscoverScrapingJobsRequest,
    FailScrapingJobRequest,
    ParentExecutionResponse,
    RecordScrapingResultRequest,
    ScrapingJobList,
    ScrapingJobResponse,
    ScrapingScheduleResponse,
    StartParentExecutionRequest,
)

router = APIRouter(tags=["scraping-jobs"], dependencies=[require_access()])

READ_LIMIT = [rate_limit("200/minute")]
WRITE_LIMIT = [rate_limit("60/minute")]
JOB_USE_CASES = "scraping_jobs.use_cases"
SCHEDULE_USE_CASES = "scraping_jobs.scraping_schedule_use_cases"
PARENT_EXECUTION_USE_CASES = "scraping_jobs.parent_execution_use_cases"


@router.get(
    "/scraping-jobs/{scraping_job_id}",
    response_model=ScrapingJobResponse,
    operation_id="getScrapingJob",
    summary="Get a scraping job",
    dependencies=READ_LIMIT,
)
@inject
async def get_scraping_job(
    scraping_job_id: Annotated[UUID, Path(description="Scraping job identifier")],
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobResponse:
    return ScrapingJobResponse.from_entity(await use_cases.get(scraping_job_id))


@router.get(
    "/parent-executions/{parent_execution_id}/scraping-jobs",
    response_model=ScrapingJobList,
    operation_id="listScrapingJobsByParentExecution",
    summary="List child jobs for a parent execution",
    dependencies=READ_LIMIT,
)
@inject
async def list_scraping_jobs_by_parent_execution(
    parent_execution_id: Annotated[UUID, Path(description="Parent execution identifier")],
    page: Pagination,
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobList:
    result = await use_cases.list_by_parent_page(
        parent_execution_id,
        offset=page.offset,
        limit=page.page_size,
    )
    return ScrapingJobList(
        items=[ScrapingJobResponse.from_entity(job) for job in result.items],
        page_info=PageInfo(page=page.page, page_size=page.page_size, total_count=result.total),
    )


@router.post(
    "/scraping-jobs/{scraping_job_id}:begin-scraping",
    response_model=ScrapingJobResponse,
    operation_id="beginScrapingJob",
    summary="Begin scraping a queued job",
    dependencies=WRITE_LIMIT,
)
@inject
async def begin_scraping_job(
    scraping_job_id: Annotated[UUID, Path(description="Scraping job identifier")],
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobResponse:
    return ScrapingJobResponse.from_entity(await use_cases.begin_scraping(scraping_job_id))


@router.post(
    "/scraping-jobs/{scraping_job_id}:record-result",
    response_model=ScrapingJobResponse,
    operation_id="recordScrapingResult",
    summary="Record a scraping result reference",
    dependencies=WRITE_LIMIT,
)
@inject
async def record_scraping_result(
    scraping_job_id: Annotated[UUID, Path(description="Scraping job identifier")],
    body: RecordScrapingResultRequest,
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobResponse:
    result = await use_cases.record_result(
        scraping_job_id,
        RecordScrapingResultCommand(result_reference=body.result_reference),
    )
    return ScrapingJobResponse.from_entity(result)


@router.post(
    "/scraping-jobs/{scraping_job_id}:begin-review-handoff",
    response_model=ScrapingJobResponse,
    operation_id="beginScrapingReviewHandoff",
    summary="Begin review handoff for a scraping result",
    dependencies=WRITE_LIMIT,
)
@inject
async def begin_scraping_review_handoff(
    scraping_job_id: Annotated[UUID, Path(description="Scraping job identifier")],
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobResponse:
    return ScrapingJobResponse.from_entity(await use_cases.begin_review_handoff(scraping_job_id))


@router.post(
    "/scraping-jobs/{scraping_job_id}:accept-review-handoff",
    response_model=ScrapingJobResponse,
    operation_id="acceptScrapingReviewHandoff",
    summary="Accept the review handoff and complete a scraping job",
    dependencies=WRITE_LIMIT,
)
@inject
async def accept_scraping_review_handoff(
    scraping_job_id: Annotated[UUID, Path(description="Scraping job identifier")],
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobResponse:
    return ScrapingJobResponse.from_entity(await use_cases.accept_review_handoff(scraping_job_id))


@router.post(
    "/scraping-jobs/{scraping_job_id}:fail",
    response_model=ScrapingJobResponse,
    operation_id="failScrapingJob",
    summary="Record a scraping job failure",
    dependencies=WRITE_LIMIT,
)
@inject
async def fail_scraping_job(
    scraping_job_id: Annotated[UUID, Path(description="Scraping job identifier")],
    body: FailScrapingJobRequest,
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobResponse:
    result = await use_cases.fail(
        scraping_job_id,
        FailScrapingJobCommand(error_code=body.error_code, retryable=body.retryable),
    )
    return ScrapingJobResponse.from_entity(result)


@router.post(
    "/scraping-jobs/{scraping_job_id}:cancel",
    response_model=ScrapingJobResponse,
    operation_id="cancelScrapingJob",
    summary="Cancel a non-terminal scraping job",
    dependencies=WRITE_LIMIT,
)
@inject
async def cancel_scraping_job(
    scraping_job_id: Annotated[UUID, Path(description="Scraping job identifier")],
    use_cases: ScrapingJobUseCases = Depends(Provide[JOB_USE_CASES]),
) -> ScrapingJobResponse:
    return ScrapingJobResponse.from_entity(await use_cases.cancel(scraping_job_id))


@router.post(
    "/scraping-schedules/",
    status_code=status.HTTP_201_CREATED,
    response_model=ScrapingScheduleResponse,
    operation_id="createScrapingSchedule",
    summary="Create a scraping schedule",
    dependencies=WRITE_LIMIT,
)
@inject
async def create_scraping_schedule(
    body: CreateScrapingScheduleRequest,
    use_cases: ScrapingScheduleUseCases = Depends(Provide[SCHEDULE_USE_CASES]),
) -> ScrapingScheduleResponse:
    schedule = await use_cases.create(
        CreateScrapingScheduleCommand(
            name=body.name,
            next_run_at=body.next_run_at,
            frequency=body.frequency,
            interval_days=body.interval_days,
        )
    )
    return ScrapingScheduleResponse.from_entity(schedule)


@router.post(
    "/scraping-schedules/{schedule_id}:enable",
    response_model=ScrapingScheduleResponse,
    operation_id="enableScrapingSchedule",
    summary="Enable a scraping schedule",
    dependencies=WRITE_LIMIT,
)
@inject
async def enable_scraping_schedule(
    schedule_id: Annotated[UUID, Path(description="Scraping schedule identifier")],
    use_cases: ScrapingScheduleUseCases = Depends(Provide[SCHEDULE_USE_CASES]),
) -> ScrapingScheduleResponse:
    return ScrapingScheduleResponse.from_entity(await use_cases.enable(schedule_id))


@router.post(
    "/scraping-schedules/{schedule_id}:disable",
    response_model=ScrapingScheduleResponse,
    operation_id="disableScrapingSchedule",
    summary="Disable a scraping schedule",
    dependencies=WRITE_LIMIT,
)
@inject
async def disable_scraping_schedule(
    schedule_id: Annotated[UUID, Path(description="Scraping schedule identifier")],
    use_cases: ScrapingScheduleUseCases = Depends(Provide[SCHEDULE_USE_CASES]),
) -> ScrapingScheduleResponse:
    return ScrapingScheduleResponse.from_entity(await use_cases.disable(schedule_id))


@router.delete(
    "/scraping-schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteScrapingSchedule",
    summary="Soft-delete a scraping schedule",
    dependencies=WRITE_LIMIT,
)
@inject
async def delete_scraping_schedule(
    schedule_id: Annotated[UUID, Path(description="Scraping schedule identifier")],
    use_cases: ScrapingScheduleUseCases = Depends(Provide[SCHEDULE_USE_CASES]),
) -> Response:
    await use_cases.delete(schedule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/parent-executions/",
    status_code=status.HTTP_201_CREATED,
    response_model=ParentExecutionResponse,
    operation_id="startParentExecution",
    summary="Start a manual or scheduled parent execution",
    dependencies=WRITE_LIMIT,
)
@inject
async def start_parent_execution(
    body: StartParentExecutionRequest,
    use_cases: ParentExecutionUseCases = Depends(Provide[PARENT_EXECUTION_USE_CASES]),
) -> ParentExecutionResponse:
    parent = await use_cases.start(
        StartParentExecutionCommand(
            trigger_type=body.trigger_type,
            schedule_id=body.schedule_id,
            occurrence_id=body.occurrence_id,
        )
    )
    return ParentExecutionResponse.from_entity(parent)


@router.post(
    "/parent-executions/{parent_execution_id}/scraping-jobs",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedScrapingJobsResponse,
    operation_id="discoverAndCreateScrapingJobs",
    summary="Create child jobs from a discovery snapshot",
    dependencies=WRITE_LIMIT,
)
@inject
async def discover_and_create_scraping_jobs(
    parent_execution_id: Annotated[UUID, Path(description="Parent execution identifier")],
    body: DiscoverScrapingJobsRequest,
    use_cases: ParentExecutionUseCases = Depends(Provide[PARENT_EXECUTION_USE_CASES]),
) -> CreatedScrapingJobsResponse:
    jobs = await use_cases.discover_and_create_jobs(
        parent_execution_id=parent_execution_id,
        discovery_snapshot=[
            (item.source_id, SourceUrl(item.source_url), item.category_id) for item in body.discovery_snapshot
        ],
    )
    items = [ScrapingJobResponse.from_entity(job) for job in jobs]
    return CreatedScrapingJobsResponse(items=items, total_count=len(items))


@router.post(
    "/schedule-occurrences/{occurrence_id}:claim",
    status_code=status.HTTP_201_CREATED,
    response_model=ParentExecutionResponse,
    operation_id="claimScheduleOccurrence",
    summary="Claim a schedule occurrence and start its parent execution",
    dependencies=WRITE_LIMIT,
)
@inject
async def claim_schedule_occurrence(
    occurrence_id: Annotated[UUID, Path(description="Schedule occurrence identifier")],
    body: ClaimScheduleOccurrenceRequest,
    use_cases: ParentExecutionUseCases = Depends(Provide[PARENT_EXECUTION_USE_CASES]),
) -> ParentExecutionResponse:
    parent = await use_cases.claim_scheduled_occurrence(
        occurrence_id=occurrence_id,
        schedule_id=body.schedule_id,
    )
    return ParentExecutionResponse.from_entity(parent)


@router.post(
    "/parent-executions/{parent_execution_id}:reconcile",
    response_model=ParentExecutionResponse,
    operation_id="reconcileParentExecution",
    summary="Recompute a parent execution summary from its child jobs",
    dependencies=WRITE_LIMIT,
)
@inject
async def reconcile_parent_execution(
    parent_execution_id: Annotated[UUID, Path(description="Parent execution identifier")],
    use_cases: ParentExecutionUseCases = Depends(Provide[PARENT_EXECUTION_USE_CASES]),
) -> ParentExecutionResponse:
    parent = await use_cases.reconcile_summary(parent_execution_id=parent_execution_id)
    return ParentExecutionResponse.from_entity(parent)
