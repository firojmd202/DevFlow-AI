"""Local repository registration and confirmed GitHub operations."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.adapters.live.github import GitHubAdapter
from devflow_api.adapters.stubs.github import GitHubStubAdapter
from devflow_api.database import get_db
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.github_confirmation import GitHubConfirmationRepository
from devflow_api.repositories.repository_config import RepositoryConfigRepository
from devflow_api.schemas.common import ErrorResponse
from devflow_api.schemas.github import (
    BranchStatus,
    BranchSummary,
    CheckRunSummary,
    PullRequestSummary,
)
from devflow_api.schemas.repository import (
    BranchWrite,
    GitHubConfirmationRequest,
    GitHubConfirmationResponse,
    PullRequestWrite,
    RepositoryConfigResponse,
    RepositoryCreate,
)
from devflow_api.services.repository import GitHubOutcomeError, RepositoryService
from devflow_core.config import Settings

router = APIRouter(prefix="/api/v1", tags=["repositories"])


async def get_repository_service(
    request: Request, session: Annotated[AsyncSession, Depends(get_db)]
) -> RepositoryService:
    settings: Settings = request.app.state.settings
    adapter = request.app.state.adapter_registry.get_live("github")
    if not isinstance(adapter, GitHubAdapter | GitHubStubAdapter):
        raise RuntimeError("GitHub registry entry has an invalid type")
    return RepositoryService(
        RepositoryConfigRepository(session),
        AuditLogRepository(session),
        adapter,
        GitHubConfirmationRepository(session),
        settings,
    )


type Service = Annotated[RepositoryService, Depends(get_repository_service)]

_ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (403, 404, 409, 422, 502)
}


async def github_outcome_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, GitHubOutcomeError):
        raise exc
    if exc.outcome == "INDETERMINATE":
        message = "GitHub execution outcome is unknown. Verify GitHub state before retrying."
    else:
        message = "GitHub rejected the request."
    status = 409 if exc.status_code == 409 else 502
    code = "CONFLICT" if status == 409 else "INTEGRATION_ERROR"
    return JSONResponse(
        status_code=status, content=ErrorResponse(error=message, code=code).model_dump()
    )


@router.get("/repositories", responses=_ERRORS)
async def list_repositories(
    service: Service, project_id: int | None = None
) -> list[RepositoryConfigResponse]:
    return [
        RepositoryConfigResponse.model_validate(row)
        for row in await service.list_repositories(project_id)
    ]


@router.post("/repositories", status_code=201, responses=_ERRORS)
async def register_repository(body: RepositoryCreate, service: Service) -> RepositoryConfigResponse:
    return RepositoryConfigResponse.model_validate(await service.register_repository(body))


@router.get("/repositories/{id}", responses=_ERRORS)
async def get_repository(id: int, service: Service) -> RepositoryConfigResponse:
    return RepositoryConfigResponse.model_validate(await service.get_repository(id))


@router.delete("/repositories/{id}", status_code=204, responses=_ERRORS)
async def delete_repository(id: int, service: Service) -> Response:
    await service.delete_repository(id)
    return Response(status_code=204)


@router.get("/repositories/{id}/branches", responses=_ERRORS)
async def list_branches(id: int, service: Service) -> list[BranchSummary]:
    repo = await service.get_repository(id)
    return await service.github().list_branches(repo.owner, repo.repo)


@router.get("/repositories/{id}/branches/{branch:path}/status", responses=_ERRORS)
async def get_branch_status(id: int, branch: str, service: Service) -> BranchStatus:
    repo = await service.get_repository(id)
    return await service.github().get_branch_status(repo.owner, repo.repo, branch)


@router.get("/repositories/{id}/branches/{branch:path}/ci", responses=_ERRORS)
async def get_branch_ci(id: int, branch: str, service: Service) -> list[CheckRunSummary]:
    repo = await service.get_repository(id)
    return await service.github().get_check_runs(repo.owner, repo.repo, branch)


@router.post("/repositories/{id}/branches", status_code=201, responses=_ERRORS)
async def create_branch(id: int, body: BranchWrite, service: Service) -> BranchSummary:
    return await service.create_branch(id, body.name, body.base_ref, body.confirmation_id)


@router.get("/repositories/{id}/pull-requests", responses=_ERRORS)
async def list_pull_requests(id: int, service: Service) -> list[PullRequestSummary]:
    repo = await service.get_repository(id)
    return await service.github().list_pull_requests(repo.owner, repo.repo)


@router.get("/repositories/{id}/pull-requests/{pr_number}", responses=_ERRORS)
async def get_pull_request(id: int, pr_number: int, service: Service) -> PullRequestSummary:
    repo = await service.get_repository(id)
    return await service.github().get_pull_request(repo.owner, repo.repo, pr_number)


@router.post("/repositories/{id}/pull-requests", status_code=201, responses=_ERRORS)
async def create_pull_request(
    id: int, body: PullRequestWrite, service: Service
) -> PullRequestSummary:
    return await service.create_pull_request(
        id, body.title, body.head, body.base, body.body, body.confirmation_id
    )


@router.post("/github-confirmations", status_code=201, responses=_ERRORS)
async def issue_confirmation(
    body: GitHubConfirmationRequest, service: Service
) -> GitHubConfirmationResponse:
    row = await service.issue_for_coordinates(body.repo_full_name, body.operation, body.parameters)
    return GitHubConfirmationResponse.model_validate(row)
