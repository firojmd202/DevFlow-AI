"""Persistent workflow and read-only run history endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.database import get_db
from devflow_api.models.project import Project
from devflow_api.models.workflow import Workflow, WorkflowRun
from devflow_api.repositories.approval import ApprovalRepository, AuditLogRepository
from devflow_api.repositories.workflow import WorkflowRepository, WorkflowRunRepository
from devflow_api.schemas.approval import ApprovalResponse
from devflow_api.schemas.common import ErrorResponse
from devflow_api.schemas.workflow import (
    AuditLogEntry,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowRunResponse,
    WorkflowStatus,
    WorkflowUpdate,
)
from devflow_api.services.workflow import WorkflowService
from devflow_core.exceptions import InvalidStatusTransitionError, PausedWorkflowError

router = APIRouter(prefix="/api/v1", tags=["workflows"])
type Session = Annotated[AsyncSession, Depends(get_db)]
_NOT_FOUND: dict[int | str, dict[str, object]] = {404: {"model": ErrorResponse}}
_VALIDATION: dict[int | str, dict[str, object]] = {422: {"model": ErrorResponse}}


async def _require_workflow(id: int, session: AsyncSession) -> Workflow:
    workflow = await WorkflowRepository(session).get(id)
    if workflow is None:
        raise HTTPException(404)
    return workflow


async def _require_run(id: int, session: AsyncSession) -> WorkflowRun:
    run = await WorkflowRunRepository(session).get(id)
    if run is None:
        raise HTTPException(404)
    return run


async def _validate_project(project_id: int | None, session: AsyncSession) -> None:
    if project_id is not None and await session.get(Project, project_id) is None:
        raise HTTPException(422)


async def _run_response(run: WorkflowRun, approvals: ApprovalRepository) -> WorkflowRunResponse:
    response = WorkflowRunResponse.model_validate(run)
    response.approvals = [
        ApprovalResponse.model_validate(row) for row in await approvals.list_for_run(run.id)
    ]
    response.pending_approvals = [row for row in response.approvals if row.status == "pending"]
    return response


@router.get("/workflows", responses=_VALIDATION)
async def list_workflows(
    session: Session, project_id: int | None = None, status: WorkflowStatus | None = None
) -> list[WorkflowResponse]:
    rows = await WorkflowRepository(session).list_filtered(project_id, status)
    return [WorkflowResponse.model_validate(row) for row in rows]


@router.post("/workflows", status_code=201, responses=_VALIDATION)
async def create_workflow(body: WorkflowCreate, session: Session) -> WorkflowResponse:
    await _validate_project(body.project_id, session)
    row = await WorkflowRepository(session).create(body.model_dump())
    return WorkflowResponse.model_validate(row)


@router.get("/workflows/{id}", responses={**_NOT_FOUND, **_VALIDATION})
async def get_workflow(id: int, session: Session) -> WorkflowResponse:
    return WorkflowResponse.model_validate(await _require_workflow(id, session))


@router.put("/workflows/{id}", responses={**_NOT_FOUND, **_VALIDATION})
async def update_workflow(id: int, body: WorkflowUpdate, session: Session) -> WorkflowResponse:
    await _require_workflow(id, session)
    await _validate_project(body.project_id, session)
    row = await WorkflowRepository(session).update(
        id, body.model_dump(exclude_unset=True, exclude_none=True)
    )
    if row is None:
        raise HTTPException(404)
    return WorkflowResponse.model_validate(row)


@router.delete("/workflows/{id}", status_code=204, responses={**_NOT_FOUND, **_VALIDATION})
async def delete_workflow(id: int, session: Session) -> Response:
    if not await WorkflowRepository(session).delete(id):
        raise HTTPException(404)
    return Response(status_code=204)


@router.post("/workflows/{id}/runs", status_code=201, responses={**_NOT_FOUND, **_VALIDATION})
async def create_run(id: int, session: Session) -> WorkflowRunResponse:
    service = WorkflowService(
        WorkflowRepository(session), WorkflowRunRepository(session), AuditLogRepository(session)
    )
    try:
        run = await service.create_run(id)
    except LookupError as exc:
        raise HTTPException(404) from exc
    except PausedWorkflowError as exc:
        raise InvalidStatusTransitionError(id, "paused", "pending") from exc
    return WorkflowRunResponse.model_validate(run)


@router.get("/workflows/{id}/runs", responses={**_NOT_FOUND, **_VALIDATION})
async def list_runs(id: int, session: Session) -> list[WorkflowRunResponse]:
    await _require_workflow(id, session)
    runs = await WorkflowRunRepository(session).list_by_workflow(id)
    approvals = ApprovalRepository(session)
    return [await _run_response(run, approvals) for run in runs]


@router.get("/workflow-runs/{run_id}", responses={**_NOT_FOUND, **_VALIDATION})
async def get_run(run_id: int, session: Session) -> WorkflowRunResponse:
    return await _run_response(await _require_run(run_id, session), ApprovalRepository(session))


@router.get("/workflow-runs/{run_id}/audit", responses={**_NOT_FOUND, **_VALIDATION})
async def list_run_audit(run_id: int, session: Session) -> list[AuditLogEntry]:
    await _require_run(run_id, session)
    rows = await AuditLogRepository(session).list_for_run(run_id)
    return [AuditLogEntry.model_validate(row) for row in rows]
