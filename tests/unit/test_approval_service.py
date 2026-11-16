import json
from asyncio import gather
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from devflow_api.database import _configure_sqlite
from devflow_api.models import ApprovalRequest, Base, WorkflowAuditLog
from devflow_api.repositories.approval import ApprovalRepository, AuditLogRepository
from devflow_api.repositories.workflow import WorkflowRepository, WorkflowRunRepository
from devflow_api.services.approval import ApprovalService
from devflow_core.exceptions import ApprovalAlreadyResolvedError, InvalidStatusTransitionError


@pytest.fixture
async def running_id(async_db_session: AsyncSession) -> int:
    workflow = await WorkflowRepository(async_db_session).create({"name": "Example"})
    run = await WorkflowRunRepository(async_db_session).create(
        {"workflow_id": workflow.id, "status": "running", "started_at": datetime.now(UTC)}
    )
    return run.id


@pytest.fixture
def approval_service(async_db_session: AsyncSession) -> ApprovalService:
    return ApprovalService(
        ApprovalRepository(async_db_session),
        WorkflowRunRepository(async_db_session),
        AuditLogRepository(async_db_session),
    )


async def test_request_approval_logs_approval_requested(
    approval_service: ApprovalService, running_id: int, async_db_session: AsyncSession
) -> None:
    body: dict[str, object] = {"resource": "Example"}
    approval = await approval_service.request_approval(running_id, "Review", "Review it", body)
    assert approval.requested_at == approval.created_at
    assert approval.requested_at.tzinfo is UTC
    assert approval.payload_json is not None and json.loads(approval.payload_json) == body
    events = await AuditLogRepository(async_db_session).list_for_run(running_id)
    assert [(event.event_type, event.actor) for event in events] == [
        ("approval_requested", "system")
    ]
    assert events[0].payload_json is not None
    assert json.loads(events[0].payload_json) == {"approval_id": approval.id, "step_name": "Review"}


async def test_request_approval_transitions_run_to_waiting(
    approval_service: ApprovalService, running_id: int, async_db_session: AsyncSession
) -> None:
    approval = await approval_service.request_approval(running_id, "Review", "Review it")
    approval_id = approval.id
    assert (
        await WorkflowRunRepository(async_db_session).get_status(running_id) == "waiting_approval"
    )
    with pytest.raises(InvalidStatusTransitionError):
        await approval_service.request_approval(running_id, "Again", "Duplicate gate")
    assert [row.id for row in await ApprovalRepository(async_db_session).list_pending()] == [
        approval_id
    ]


async def test_resolve_approval_approved_resumes_run(
    approval_service: ApprovalService, running_id: int, async_db_session: AsyncSession
) -> None:
    run_before = await WorkflowRunRepository(async_db_session).get(running_id)
    assert run_before is not None
    started_at = run_before.started_at
    approval = await approval_service.request_approval(running_id, "Review", "Review it")
    resolved, run = await approval_service.resolve(approval.id, "approved", "reviewer")
    assert run.status == "running" and run.started_at == started_at
    assert resolved.status == "approved" and resolved.resolved_by == "reviewer"
    assert resolved.resolved_at is not None and resolved.resolved_at.tzinfo is UTC
    assert await ApprovalRepository(async_db_session).list_pending() == []
    events = await AuditLogRepository(async_db_session).list_for_run(running_id)
    assert (events[-1].event_type, events[-1].actor) == ("approval_resolved", "user")


async def test_resolve_approval_rejected_cancels_run(
    approval_service: ApprovalService, running_id: int
) -> None:
    approval = await approval_service.request_approval(running_id, "Review", "Review it")
    resolved, run = await approval_service.resolve(approval.id, "rejected", None)
    assert run.status == "cancelled" and run.completed_at is not None
    assert resolved.status == "rejected" and resolved.resolved_by is None


async def test_resolve_already_resolved_raises(
    approval_service: ApprovalService, running_id: int, async_db_session: AsyncSession
) -> None:
    approval = await approval_service.request_approval(running_id, "Review", "Review it")
    approval_id = approval.id
    await approval_service.resolve(approval_id, "approved", None)
    for layer in (approval_service, ApprovalRepository(async_db_session)):
        with pytest.raises(ApprovalAlreadyResolvedError) as exc:
            await layer.resolve(approval_id, "rejected", None)
        assert (exc.value.approval_id, exc.value.current_status) == (approval_id, "approved")
    assert await WorkflowRunRepository(async_db_session).get_status(running_id) == "running"
    assert len(await AuditLogRepository(async_db_session).list_for_run(running_id)) == 2


async def test_audit_list_ordered_by_created_at(
    running_id: int, async_db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    async_db_session.add_all(
        [
            WorkflowAuditLog(
                workflow_run_id=running_id, event_type="late", actor="user", created_at=now
            ),
            WorkflowAuditLog(
                workflow_run_id=running_id,
                event_type="early",
                actor="user",
                created_at=now - timedelta(days=1),
            ),
            WorkflowAuditLog(
                workflow_run_id=running_id, event_type="tie", actor="user", created_at=now
            ),
            WorkflowAuditLog(event_type="unbound", actor="system", created_at=now),
        ]
    )
    await async_db_session.commit()
    assert [
        event.event_type
        for event in await AuditLogRepository(async_db_session).list_for_run(running_id)
    ] == ["early", "late", "tie"]


async def test_request_rolls_back_after_payload_failure(
    approval_service: ApprovalService, running_id: int, async_db_session: AsyncSession
) -> None:
    with pytest.raises(TypeError):
        await approval_service.request_approval(
            running_id, "Review", "Review it", {"bad": object()}
        )
    assert await WorkflowRunRepository(async_db_session).get_status(running_id) == "running"
    assert (await async_db_session.scalars(select(ApprovalRequest))).all() == []
    assert await AuditLogRepository(async_db_session).list_for_run(running_id) == []


async def test_resolution_rolls_back_after_audit_failure(
    approval_service: ApprovalService, running_id: int, async_db_session: AsyncSession
) -> None:
    class FailingAudit(AuditLogRepository):
        async def log_event(
            self,
            event_type: str,
            actor: str,
            workflow_run_id: int | None = None,
            payload: dict[str, object] | None = None,
            *,
            commit: bool = True,
        ) -> WorkflowAuditLog:
            raise RuntimeError("Audit unavailable")

    approval_id = (await approval_service.request_approval(running_id, "Review", "Review it")).id
    repo = ApprovalRepository(async_db_session)
    failing = ApprovalService(
        repo, WorkflowRunRepository(async_db_session), FailingAudit(async_db_session)
    )
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await failing.resolve(approval_id, "approved", None)
    approval = await repo.get(approval_id)
    assert approval is not None and approval.status == "pending" and approval.resolved_at is None
    assert (
        await WorkflowRunRepository(async_db_session).get_status(running_id) == "waiting_approval"
    )
    assert len(await AuditLogRepository(async_db_session).list_for_run(running_id)) == 1


async def test_missing_approval_and_invalid_decision(approval_service: ApprovalService) -> None:
    with pytest.raises(LookupError):
        await approval_service.resolve(999, "approved", None)
    decision: Literal["approved", "rejected"] = json.loads('"expired"')
    with pytest.raises(ValueError, match="decision"):
        await approval_service.resolve(999, decision, None)


async def test_audit_records_are_append_only(async_db_session: AsyncSession) -> None:
    repo = AuditLogRepository(async_db_session)
    entry = await repo.log_event("run_created", "system")
    with pytest.raises(TypeError, match="append-only"):
        await repo.update(entry.id, {"event_type": "edited"})
    with pytest.raises(TypeError, match="append-only"):
        await repo.delete(entry.id)
    assert (
        await async_db_session.scalars(select(WorkflowAuditLog))
    ).one().event_type == "run_created"


async def test_concurrent_resolution_has_one_winner(sqlite_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    event.listen(engine.sync_engine, "connect", _configure_sqlite)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def resolve(approval_id: int, decision: Literal["approved", "rejected"]) -> str:
        async with sessions() as session:
            service = ApprovalService(
                ApprovalRepository(session),
                WorkflowRunRepository(session),
                AuditLogRepository(session),
            )
            try:
                approval, _ = await service.resolve(approval_id, decision, None)
            except ApprovalAlreadyResolvedError:
                return "already resolved"
            return approval.status

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            workflow = await WorkflowRepository(session).create({"name": "Review"})
            runs = WorkflowRunRepository(session)
            run = await runs.create({"workflow_id": workflow.id, "status": "running"})
            service = ApprovalService(
                ApprovalRepository(session), runs, AuditLogRepository(session)
            )
            approval = await service.request_approval(run.id, "Review", "Check it")
            approval_id, run_id = approval.id, run.id

        outcomes = await gather(resolve(approval_id, "approved"), resolve(approval_id, "rejected"))
        assert outcomes.count("already resolved") == 1
        async with sessions() as session:
            persisted = await ApprovalRepository(session).get(approval_id)
            assert persisted is not None and persisted.status in outcomes
            persisted_run = await WorkflowRunRepository(session).get(run_id)
            assert persisted_run is not None
            assert persisted_run.status == (
                "running" if persisted.status == "approved" else "cancelled"
            )
            entries = await AuditLogRepository(session).list_for_run(run_id)
            assert [entry.event_type for entry in entries] == [
                "approval_requested",
                "approval_resolved",
            ]
    finally:
        await engine.dispose()
