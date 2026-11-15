from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.database import get_db
from devflow_api.repositories.project import ProjectRepository
from devflow_api.schemas.common import ErrorResponse
from devflow_api.schemas.project import ProjectCreate, ProjectResponse, ProjectStatus, ProjectUpdate
from devflow_api.services.project import ProjectService

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
_NOT_FOUND: dict[int | str, dict[str, object]] = {404: {"model": ErrorResponse}}
_VALIDATION: dict[int | str, dict[str, object]] = {422: {"model": ErrorResponse}}


async def get_project_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ProjectService:
    return ProjectService(ProjectRepository(session))


type Service = Annotated[ProjectService, Depends(get_project_service)]


@router.get("", responses=_VALIDATION)
async def list_items(
    service: Service,
    status: ProjectStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ProjectResponse]:
    return await service.list(status, limit, offset)


@router.post("", status_code=201, responses=_VALIDATION)
async def create_item(body: ProjectCreate, service: Service) -> ProjectResponse:
    return await service.create(body)


@router.get("/{id}", responses={**_NOT_FOUND, **_VALIDATION})
async def get_item(id: int, service: Service) -> ProjectResponse:
    return await service.get(id)


@router.put("/{id}", responses={**_NOT_FOUND, **_VALIDATION})
async def update_item(id: int, body: ProjectUpdate, service: Service) -> ProjectResponse:
    return await service.update(id, body)


@router.delete(
    "/{id}", status_code=204, response_class=Response, responses={**_NOT_FOUND, **_VALIDATION}
)
async def delete_item(id: int, service: Service) -> Response:
    await service.delete(id)
    return Response(status_code=204)
