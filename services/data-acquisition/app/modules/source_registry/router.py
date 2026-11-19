"""
ROUTER (HTTP endpoints): the thin layer between HTTP and the use cases. No business rules here.

For every request:
    1. `require_access()` (on the router) checks the route's `operation_id` against
       config/access-control.json: 401 if not signed in, 403 if not granted. Never check roles here.
    2. `rate_limit(...)` limits calls per client; the schema validates the JSON.
    3. ONE use-case method is called with plain values.
    4. The result is turned into a response schema.

To add an endpoint: copy a function below, give it a NEW camelCase `operation_id` (never rename one
later), then grant that operation_id to roles in config/access-control.json.
"""

from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request, Response, status
from platform_kit.access import require_access
from platform_kit.http.pagination import PageInfo, Pagination

from app.core.security import rate_limit
from app.modules.source_registry.application.use_cases import (
    CreateSourceRegistryCommand,
    SourceRegistryUseCases,
    UpdateSourceRegistryCommand,
)
from app.modules.source_registry.domain.value_objects import SourceRegistryStatus
from app.modules.source_registry.schemas import (
    SourceRegistryCreate,
    SourceRegistryList,
    SourceRegistryResponse,
    SourceRegistryUpdate,
)

# Mounted under /v1 in app/api.py, so these routes are /v1/source-registry/...
router = APIRouter(prefix="/source-registry", tags=["source-registry"], dependencies=[require_access()])

READ_LIMIT = [rate_limit("200/minute")]
WRITE_LIMIT = [rate_limit("60/minute")]
USE_CASES = "source_registry.use_cases"  # built by container.py


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=SourceRegistryResponse,
    operation_id="createSourceRegistry",
    summary="Create Source registry",
    dependencies=WRITE_LIMIT,
)
@inject
async def create_source_registry(
    body: SourceRegistryCreate,
    request: Request,
    response: Response,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceRegistryResponse:
    source_registry = await use_cases.create(CreateSourceRegistryCommand(name=body.name, code=body.code))
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{source_registry.id}"
    return SourceRegistryResponse.from_entity(source_registry)


@router.get(
    "/",
    response_model=SourceRegistryList,
    operation_id="listSourceRegistry",
    summary="List Source registry",
    dependencies=READ_LIMIT,
)
@inject
async def list_source_registry(
    page: Pagination,  # ?page=1&pageSize=20
    status_filter: Annotated[SourceRegistryStatus | None, Query(alias="status")] = None,  # ?status=active
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceRegistryList:
    result = await use_cases.list(status=status_filter, offset=page.offset, limit=page.page_size)
    return SourceRegistryList(
        items=[SourceRegistryResponse.from_entity(x) for x in result.items],
        page_info=PageInfo(page=page.page, page_size=page.page_size, total_count=result.total),
    )


@router.get(
    "/{source_registry_id}",
    response_model=SourceRegistryResponse,
    operation_id="getSourceRegistry",
    summary="Get Source registry",
    dependencies=READ_LIMIT,
)
@inject
async def get_source_registry(
    source_registry_id: UUID,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceRegistryResponse:
    return SourceRegistryResponse.from_entity(await use_cases.get(source_registry_id))


@router.patch(
    "/{source_registry_id}",
    response_model=SourceRegistryResponse,
    operation_id="updateSourceRegistry",
    summary="Update Source registry",
    dependencies=WRITE_LIMIT,
)
@inject
async def update_source_registry(
    source_registry_id: UUID,
    body: SourceRegistryUpdate,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceRegistryResponse:
    source_registry = await use_cases.update(
        source_registry_id, UpdateSourceRegistryCommand(name=body.name, code=body.code)
    )
    return SourceRegistryResponse.from_entity(source_registry)


@router.post(
    "/{source_registry_id}:archive",
    response_model=SourceRegistryResponse,
    operation_id="archiveSourceRegistry",
    summary="Archive Source registry",
    dependencies=WRITE_LIMIT,
)
@inject
async def archive_source_registry(
    source_registry_id: UUID,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceRegistryResponse:
    return SourceRegistryResponse.from_entity(await use_cases.archive(source_registry_id))


@router.post(
    "/{source_registry_id}:restore",
    response_model=SourceRegistryResponse,
    operation_id="restoreSourceRegistry",
    summary="Restore Source registry",
    dependencies=WRITE_LIMIT,
)
@inject
async def restore_source_registry(
    source_registry_id: UUID,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceRegistryResponse:
    return SourceRegistryResponse.from_entity(await use_cases.restore(source_registry_id))


@router.delete(
    "/{source_registry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteSourceRegistry",
    summary="Delete Source registry",
    dependencies=WRITE_LIMIT,
)
@inject
async def delete_source_registry(
    source_registry_id: UUID,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> Response:
    await use_cases.delete(source_registry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
