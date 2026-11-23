"""Local-operator API for Wave 2 specification requests."""

import asyncio
import json
from collections.abc import Sequence
from typing import Annotated, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.adapters.mcp_adapter import MCPClientAdapter
from devflow_api.adapters.mcp_client import MCPClient
from devflow_api.models.audit import WorkflowAuditLog
from devflow_api.models.specification import (
    GenerationAttempt,
    ReviewAttempt,
    SpecificationRequest,
    SpecificationVersion,
)
from devflow_api.providers.base import AIProvider
from devflow_api.providers.factory import ProviderFactory
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.specification_version import SpecificationVersionRepository
from devflow_api.routers.workflows import ExecutionSettings, ResourceId, Session
from devflow_api.schemas.specification import (
    AI_REVIEW_DISCLAIMER,
    ArtifactType,
    SpecificationRequestCreate,
)
from devflow_api.schemas.specification_http import (
    ApprovalBinding,
    ApprovalBody,
    ApprovalResponse,
    ArtifactResponse,
    AttemptTrigger,
    CancelTaskResponse,
    FindingResponse,
    ProviderAvailability,
    ReviewFindingsResponse,
    SpecificationCreateBody,
    SpecificationRequestResponse,
    SpecificationUpdateBody,
    StatusResponse,
    TaskResponse,
    VersionResponse,
)
from devflow_api.schemas.workflow import AuditLogEntry
from devflow_api.services.specification_approval import SpecificationApprovalService
from devflow_api.services.specification_attempts import ACTIVE, select_model
from devflow_api.services.specification_generation import SpecificationGenerationService
from devflow_api.services.specification_review import SpecificationReviewService
from devflow_api.services.workflow_projection import audit_payload
from devflow_api.specification_errors import (
    ApprovalBindingMismatch,
    InvalidSpecTransitionError,
    SpecificationNotFoundError,
    TaskNotCancellableError,
)
from devflow_core.config import Settings
from devflow_core.exceptions import ApprovalExpiredError
from devflow_core.mcp_config import MCPServerConfig

PREFIX = "/api/v1/specification-requests"
router = APIRouter(prefix=PREFIX, tags=["specification requests"])
type Offset = Annotated[int, Query(ge=0)]
type Limit = Annotated[int, Query(gt=0, le=100)]


def _runtime(request: Request) -> tuple[async_sessionmaker[AsyncSession], AIProvider]:
    return (
        cast(async_sessionmaker[AsyncSession], request.app.state.workflow_sessions),
        cast(AIProvider, request.app.state.ai_provider),
    )


def _selection(
    provider: AIProvider,
    config: Settings,
    requested: str | None,
) -> tuple[AIProvider, Settings]:
    if requested == "ollama" and config.AI_PROVIDER == "openai":
        local = config.model_copy(update={"AI_PROVIDER": "ollama"})
        return ProviderFactory.create(local), local
    return provider, config


def _view(row: SpecificationRequest) -> SpecificationRequestResponse:
    return SpecificationRequestResponse(
        **SpecificationVersionRepository.draft_input(row).model_dump(),
        id=row.id,
        status=row.status,
        version=row.current_version,
        content_hash=row.content_hash,
        provider_id=row.provider_id,
        model_id=row.model_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _owned_version(
    repo: SpecificationVersionRepository,
    request_id: int,
    version_id: int | None = None,
) -> SpecificationVersion:
    request = await repo.get_request(request_id)
    if version_id is None:
        return await repo.current_version(request)
    version = await repo.get_version(version_id)
    if version.specification_request_id != request.id:
        raise SpecificationNotFoundError("Specification version not found")
    return version


async def _generation(session: AsyncSession, request_id: int) -> GenerationAttempt | None:
    return await session.scalar(
        select(GenerationAttempt)
        .where(GenerationAttempt.specification_request_id == request_id)
        .order_by(GenerationAttempt.id.desc())
        .limit(1)
    )


async def _review(session: AsyncSession, version_id: int) -> ReviewAttempt | None:
    return await session.scalar(
        select(ReviewAttempt)
        .where(ReviewAttempt.specification_version_id == version_id)
        .order_by(ReviewAttempt.id.desc())
        .limit(1)
    )


async def _run_generation(
    sessions: async_sessionmaker[AsyncSession],
    provider: AIProvider,
    config: Settings,
    attempt_id: int,
) -> None:
    async with sessions() as audit_session:
        mcp = MCPClientAdapter(
            MCPClient(MCPServerConfig.from_settings(config), config),
            AuditLogRepository(audit_session),
            config,
        )
        await SpecificationGenerationService(sessions, provider, settings=config, mcp=mcp).run(
            attempt_id, actor_id=config.LOCAL_OPERATOR_ID
        )


@router.get("/providers")
async def providers(request: Request, config: ExecutionSettings) -> list[ProviderAvailability]:
    _, provider = _runtime(request)
    local, _ = _selection(provider, config, "ollama")
    try:
        async with asyncio.timeout(2):
            available = (await local.check_availability()).available
    except TimeoutError:
        available = False
    result = [
        ProviderAvailability(
            provider_id=local.provider_id,
            model_id=local.model_id,
            available=available,
            reason=None if available else "Provider unavailable",
        )
    ]
    if provider.provider_id == "openai":
        result.append(
            ProviderAvailability(
                provider_id=provider.provider_id,
                model_id=provider.model_id,
                available=None,
                reason="Availability checked when explicitly selected",
            )
        )
    return result


@router.get("")
async def list_requests(
    session: Session,
    offset: Offset = 0,
    limit: Limit = 50,
) -> list[SpecificationRequestResponse]:
    rows = await session.scalars(
        select(SpecificationRequest)
        .order_by(SpecificationRequest.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [_view(row) for row in rows]


@router.post("", status_code=201)
async def create_request(
    body: SpecificationCreateBody,
    request: Request,
    session: Session,
    config: ExecutionSettings,
) -> SpecificationRequestResponse:
    _, provider = _runtime(request)
    provider, config = _selection(provider, config, body.provider_id)
    model = select_model(provider, config, body.provider_id, body.model_id)
    draft = SpecificationRequestCreate.model_validate(
        body.model_dump(exclude={"provider_id", "model_id", "supersedes_version_id"})
    )
    async with immediate_transaction(session):
        row = await SpecificationVersionRepository(session, config).create_request(
            draft,
            actor_id=config.LOCAL_OPERATOR_ID,
            supersedes_version_id=body.supersedes_version_id,
            commit=False,
        )
        row.provider_id, row.model_id = provider.provider_id, model
        return _view(row)


@router.get("/{id}")
async def get_request(id: ResourceId, session: Session) -> SpecificationRequestResponse:
    return _view(await SpecificationVersionRepository(session).get_request(id))


@router.patch("/{id}")
async def update_request(
    id: ResourceId,
    body: SpecificationUpdateBody,
    session: Session,
    config: ExecutionSettings,
) -> SpecificationRequestResponse:
    repo = SpecificationVersionRepository(session, config)
    draft = SpecificationRequestCreate.model_validate(body.model_dump(exclude={"expected_version"}))
    changed = await repo.update_request(
        id,
        draft,
        expected_version=body.expected_version,
        actor_id=config.LOCAL_OPERATOR_ID,
    )
    return _view(changed)


@router.delete("/{id}", status_code=204)
async def cancel_request(id: ResourceId, session: Session, config: ExecutionSettings) -> Response:
    repo = SpecificationVersionRepository(session, config)
    async with immediate_transaction(session):
        row = await repo.get_request(id)
        version = await repo.current_version(row)
        generation = await _generation(session, id)
        review = await _review(session, version.id)
        if any(item is not None and item.status in ACTIVE for item in (generation, review)):
            raise InvalidSpecTransitionError("Cancel the active attempt first")
        await repo.transition_status(version.id, version.status, "cancelled", commit=False)
        await repo.audit("spec_request_cancelled", row, version, actor="user")
    return Response(status_code=204)


@router.post("/{id}/generate", status_code=202)
async def generate(
    id: ResourceId,
    request: Request,
    tasks: BackgroundTasks,
    session: Session,
    config: ExecutionSettings,
    body: AttemptTrigger | None = None,
) -> TaskResponse:
    options = body or AttemptTrigger()
    row = await SpecificationVersionRepository(session).get_request(id)
    sessions, provider = _runtime(request)
    provider, config = _selection(provider, config, options.provider_id or row.provider_id)
    attempt = await SpecificationGenerationService(sessions, provider, settings=config).start(
        id,
        expected_version=options.expected_version or row.current_version,
        provider_id=options.provider_id or row.provider_id,
        model=options.model_id or row.model_id,
    )
    tasks.add_task(_run_generation, sessions, provider, config, attempt.id)
    return TaskResponse(task_id=str(attempt.id), poll_url=f"{PREFIX}/{id}/status")


@router.post("/{id}/review", status_code=202)
async def review(
    id: ResourceId,
    request: Request,
    tasks: BackgroundTasks,
    session: Session,
    config: ExecutionSettings,
    body: AttemptTrigger | None = None,
) -> TaskResponse:
    options = body or AttemptTrigger()
    version = await _owned_version(SpecificationVersionRepository(session), id)
    if options.expected_version is not None and options.expected_version != version.version_number:
        raise InvalidSpecTransitionError("Specification version is stale")
    sessions, provider = _runtime(request)
    row = await SpecificationVersionRepository(session).get_request(id)
    provider, config = _selection(provider, config, options.provider_id or row.provider_id)
    service = SpecificationReviewService(sessions, provider, settings=config)
    attempt = await service.start(
        version.id,
        provider_id=options.provider_id or row.provider_id,
        model=options.model_id or row.model_id,
    )
    tasks.add_task(service.run, attempt.id)
    return TaskResponse(task_id=str(attempt.id), poll_url=f"{PREFIX}/{id}/status?kind=review")


@router.get("/{id}/status")
async def status(
    id: ResourceId,
    session: Session,
    kind: Literal["generation", "review"] = "generation",
) -> StatusResponse:
    repo = SpecificationVersionRepository(session)
    version = await _owned_version(repo, id)
    if kind == "review":
        attempt = await _review(session, version.id)
        if attempt is None:
            return StatusResponse(status=version.status)
        return StatusResponse(
            status="failed"
            if attempt.error_code and attempt.status == "succeeded"
            else attempt.status,
            error_code=attempt.error_code,
            completed_at=attempt.completed_at,
        )
    generation = await _generation(session, id)
    if generation is None or generation.specification_version_id != version.id:
        return StatusResponse(status=version.status)
    return StatusResponse(
        status=generation.status,
        error_code=generation.error_code,
        error_message=generation.error_message,
        completed_at=generation.completed_at,
    )


@router.delete("/{id}/generate")
async def cancel_generation(
    id: ResourceId,
    request: Request,
    session: Session,
    config: ExecutionSettings,
) -> CancelTaskResponse:
    version = await _owned_version(SpecificationVersionRepository(session), id)
    attempt = await _generation(session, id)
    if attempt is None or attempt.specification_version_id != version.id:
        raise TaskNotCancellableError("No cancellable generation attempt")
    sessions, provider = _runtime(request)
    await SpecificationGenerationService(sessions, provider, settings=config).cancel(attempt.id)
    return CancelTaskResponse()


@router.delete("/{id}/review")
async def cancel_review(
    id: ResourceId,
    request: Request,
    session: Session,
    config: ExecutionSettings,
) -> CancelTaskResponse:
    version = await _owned_version(SpecificationVersionRepository(session), id)
    attempt = await _review(session, version.id)
    if attempt is None:
        raise TaskNotCancellableError("No cancellable review attempt")
    sessions, provider = _runtime(request)
    await SpecificationReviewService(sessions, provider, settings=config).cancel(attempt.id)
    return CancelTaskResponse()


@router.post("/{id}/revision")
async def request_revision(
    id: ResourceId,
    request: Request,
    session: Session,
    config: ExecutionSettings,
) -> VersionResponse:
    repo = SpecificationVersionRepository(session, config)
    version = await _owned_version(repo, id)
    if version.status == "under_review":
        sessions, provider = _runtime(request)
        await SpecificationReviewService(sessions, provider, settings=config).request_revision(
            version.id,
            actor_id=config.LOCAL_OPERATOR_ID,
        )
        version = await repo.get_version(version.id)
    else:
        async with immediate_transaction(session):
            version = await repo.transition_status(
                version.id,
                "ready_for_approval",
                "revision_required",
                commit=False,
            )
            await repo.audit(
                "spec_revision_requested",
                await repo.get_request(id),
                version,
                actor="user",
                actor_id=config.LOCAL_OPERATOR_ID,
            )
    return VersionResponse.model_validate(version)


@router.get("/{id}/versions")
async def versions(id: ResourceId, session: Session) -> list[VersionResponse]:
    repo = SpecificationVersionRepository(session)
    await repo.get_request(id)
    return [VersionResponse.model_validate(row) for row in await repo.list_versions(id)]


@router.get("/{id}/versions/{version_id}/artifacts/{artifact_type}")
async def artifact(
    id: ResourceId,
    version_id: ResourceId,
    artifact_type: ArtifactType,
    session: Session,
) -> ArtifactResponse:
    repo = SpecificationVersionRepository(session)
    await _owned_version(repo, id, version_id)
    row = await repo.get_artifact(version_id, artifact_type)
    if row is None:
        raise SpecificationNotFoundError("Specification artifact not found")
    return ArtifactResponse.model_validate(row)


@router.get("/{id}/review/findings")
async def findings(
    id: ResourceId,
    session: Session,
    version_id: Annotated[int | None, Query(gt=0)] = None,
) -> ReviewFindingsResponse:
    repo = SpecificationVersionRepository(session)
    version = await _owned_version(repo, id, version_id)
    attempt = await _review(session, version.id)
    rows = await repo.list_findings(attempt.id) if attempt is not None else []
    summary: dict[str, int] = {}
    for row in rows:
        summary[row.severity] = summary.get(row.severity, 0) + 1
    return ReviewFindingsResponse(
        findings=[FindingResponse.model_validate(row) for row in rows],
        disclaimer=AI_REVIEW_DISCLAIMER,
        summary=summary,
    )


@router.post("/{id}/findings/{finding_id}/acknowledge")
async def acknowledge(
    id: ResourceId,
    finding_id: ResourceId,
    session: Session,
    config: ExecutionSettings,
) -> FindingResponse:
    finding = await SpecificationApprovalService(session, config).acknowledge(
        id,
        finding_id,
        config.LOCAL_OPERATOR_ID,
    )
    return FindingResponse.model_validate(finding)


@router.post("/{id}/approval")
async def request_approval(
    id: ResourceId,
    body: ApprovalBinding,
    session: Session,
    config: ExecutionSettings,
) -> ApprovalResponse:
    service = SpecificationApprovalService(session, config)
    version = await _owned_version(service.versions, id, body.version_id)
    if body.content_digest != version.content_digest:
        raise ApprovalBindingMismatch("Approval digest is stale")
    row = await service.request_approval(
        id,
        config.LOCAL_OPERATOR_ID,
        expected_version_id=version.id,
        expected_digest=body.content_digest,
    )
    return ApprovalResponse(
        id=row.id, status="pending", expires_at=row.expires_at, version_id=version.id
    )


@router.post("/{id}/approve")
async def approve(
    id: ResourceId,
    body: ApprovalBody,
    session: Session,
    config: ExecutionSettings,
) -> ApprovalResponse:
    service = SpecificationApprovalService(session, config)
    row = await service.versions.get_request(id)
    resolve = service.resolve_standalone if row.workflow_run_id is None else service.resolve_bound
    try:
        version = await resolve(
            body.approval_id,
            body.decision,
            config.LOCAL_OPERATOR_ID,
            request_id=id,
            expected_version_id=body.version_id,
            expected_digest=body.content_digest,
            reason=body.reason,
        )
    except ApprovalExpiredError:
        async with immediate_transaction(session):
            current = await service.versions.get_request(id)
            version = await _owned_version(service.versions, id, body.version_id)
            await service.versions.audit(
                "spec_approval_expired",
                current,
                version,
                approval_id=body.approval_id,
            )
        raise
    return ApprovalResponse(id=body.approval_id, status=body.decision, version_id=version.id)


@router.get("/{id}/audit")
async def audit(
    id: ResourceId,
    session: Session,
    config: ExecutionSettings,
    offset: Offset = 0,
    limit: Limit = 50,
) -> Sequence[AuditLogEntry]:
    await SpecificationVersionRepository(session).get_request(id)
    rows = await session.scalars(
        select(WorkflowAuditLog)
        .where(func.json_extract(WorkflowAuditLog.payload_json, "$.specification_request_id") == id)
        .order_by(WorkflowAuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        AuditLogEntry(
            id=row.id,
            event_type=row.event_type,
            actor=row.actor,
            created_at=row.created_at,
            workflow_run_id=row.workflow_run_id,
            payload_json=json.dumps(audit_payload(json.loads(row.payload_json), config))
            if row.payload_json
            else None,
        )
        for row in rows
    ]
