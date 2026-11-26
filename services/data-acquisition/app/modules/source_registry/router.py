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

from dataclasses import replace
from typing import Annotated, Any
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request, Response, status
from platform_kit.access import require_access
from platform_kit.http.pagination import PageInfo, Pagination
from platform_kit.http.problems import PROBLEM_JSON

from app.core.security import rate_limit
from app.modules.auth.dependencies import CurrentUserDep
from app.modules.source_registry.application.use_cases import (
    RegisterSourceCommand,
    SourceRegistryUseCases,
    UpdateSourceCommand,
)
from app.modules.source_registry.schemas import SourceCreate, SourceList, SourceResponse, SourceUpdate

# Mounted under /v1 in app/api.py, so these routes are /v1/sources/...
router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[require_access()])

READ_LIMIT = [rate_limit("200/minute")]
WRITE_LIMIT = [rate_limit("60/minute")]
USE_CASES = "source_registry.use_cases"  # built by container.py


def _problem(description: str, *, validation: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {
        field: {"type": "string"} for field in ("type", "title", "detail", "instance", "code")
    }
    properties["status"] = {"type": "integer"}
    properties["request_id"] = {"type": ["string", "null"]}
    required = list(properties)
    if validation:
        properties["errors"] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {field: {"type": "string"} for field in ("field", "message", "type")},
                "required": ["field", "message", "type"],
            },
        }
    return {
        "description": description,
        "content": {PROBLEM_JSON: {"schema": {"type": "object", "properties": properties, "required": required}}},
    }


COMMON_ERRORS = {
    401: _problem("Missing or invalid bearer token"),
    403: _problem("The caller lacks the operation grant"),
    422: _problem("Invalid request or source details", validation=True),
    429: _problem("Too many requests"),
}
SOURCE_ERRORS = {**COMMON_ERRORS, 404: _problem("Source not found")}


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=SourceResponse,
    operation_id="registerSource",
    summary="Register Source",
    responses={
        **COMMON_ERRORS,
        201: {"headers": {"Location": {"description": "URI of the new source", "schema": {"type": "string"}}}},
        409: _problem("Source name already exists"),
    },
    dependencies=WRITE_LIMIT,
)
@inject
async def register_source(
    body: SourceCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceResponse:
    source = await use_cases.register(
        RegisterSourceCommand(
            name=body.name,
            description=body.description,
            source_urls=body.source_urls,
            created_by=current_user.user_id,
        )
    )
    response.headers["Location"] = f"{request.url.path.rstrip('/')}/{source.id}"
    return SourceResponse.from_entity(source)


@router.get(
    "/",
    response_model=SourceList,
    operation_id="listSources",
    summary="List Sources",
    responses=COMMON_ERRORS,
    dependencies=READ_LIMIT,
)
@inject
async def list_sources(
    page: Pagination,
    is_enabled: Annotated[bool | None, Query(alias="isEnabled")] = None,
    name: Annotated[str | None, Query(alias="name")] = None,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceList:
    result = await use_cases.list(
        is_enabled=is_enabled,
        name_contains=name,
        offset=page.offset,
        limit=page.page_size,
    )
    return SourceList(
        sources=[SourceResponse.from_entity(s) for s in result.sources],
        page_info=PageInfo(page=page.page, page_size=page.page_size, total_count=result.total),
    )


@router.get(
    "/{source_id}",
    response_model=SourceResponse,
    operation_id="getSource",
    summary="Get Source",
    responses=SOURCE_ERRORS,
    dependencies=READ_LIMIT,
)
@inject
async def get_source(
    source_id: UUID,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceResponse:
    return SourceResponse.from_entity(await use_cases.get(source_id))


@router.patch(
    "/{source_id}",
    response_model=SourceResponse,
    operation_id="updateSource",
    summary="Update Source",
    responses={**SOURCE_ERRORS, 409: _problem("Source name already exists or no details changed")},
    dependencies=WRITE_LIMIT,
)
@inject
async def update_source(
    source_id: UUID,
    body: SourceUpdate,
    current_user: CurrentUserDep,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceResponse:
    command = UpdateSourceCommand(
        name=body.name,
        source_urls=body.source_urls,
        updated_by=current_user.user_id,
    )
    if "description" in body.model_fields_set:
        command = replace(command, description=body.description)
    source = await use_cases.update(source_id, command)
    return SourceResponse.from_entity(source)


@router.post(
    "/{source_id}:enable",
    response_model=SourceResponse,
    operation_id="enableSource",
    summary="Enable Source",
    responses={**SOURCE_ERRORS, 409: _problem("Source is already enabled or is not ready")},
    dependencies=WRITE_LIMIT,
)
@inject
async def enable_source(
    source_id: UUID,
    current_user: CurrentUserDep,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceResponse:
    return SourceResponse.from_entity(await use_cases.enable(source_id, actor_id=current_user.user_id))


@router.post(
    "/{source_id}:disable",
    response_model=SourceResponse,
    operation_id="disableSource",
    summary="Disable Source",
    responses={**SOURCE_ERRORS, 409: _problem("Source is already disabled")},
    dependencies=WRITE_LIMIT,
)
@inject
async def disable_source(
    source_id: UUID,
    current_user: CurrentUserDep,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> SourceResponse:
    return SourceResponse.from_entity(await use_cases.disable(source_id, actor_id=current_user.user_id))


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteSource",
    summary="Delete Source",
    responses={**SOURCE_ERRORS, 409: _problem("Source is enabled or still in use")},
    dependencies=WRITE_LIMIT,
)
@inject
async def delete_source(
    source_id: UUID,
    use_cases: SourceRegistryUseCases = Depends(Provide[USE_CASES]),
) -> Response:
    await use_cases.delete(source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
