import json
from datetime import UTC

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models import ApprovalRequest, Project, WorkflowAuditLog
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.workflow import WorkflowRepository, WorkflowRunRepository
from devflow_api.services.workflow import WorkflowService
from devflow_core.exceptions import InvalidStatusTransitionError


@pytest.fixture
async def workflow_id(async_db_session: AsyncSession) -> int:
    repo = WorkflowRepository(async_db_session)
    return (await repo.create({"name": "Workflow", "definition_json": "opaque"})).id


@pytest.fixture
def workflow_service(async_db_session: AsyncSession) -> WorkflowService:
    return WorkflowService(
        WorkflowRepository(async_db_session),
        WorkflowRunRepository(async_db_session),
        AuditLogRepository(async_db_session),
    )


async def test_create_run_generates_audit_entry(
    workflow_service: WorkflowService, workflow_id: int, async_db_session: AsyncSession
) -> None:
    run = await workflow_service.create_run(workflow_id)
    assert run.status == "pending" and run.started_at is None
    events = await AuditLogRepository(async_db_session).list_for_run(run.id)
    assert [(event.event_type, event.actor) for event in events] == [("run_created", "system")]


@pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled"])
async def test_transition_run_valid(
    workflow_service: WorkflowService,
    workflow_id: int,
    async_db_session: AsyncSession,
    terminal: str,
) -> None:
    run_id = (await workflow_service.create_run(workflow_id)).id
    started = await workflow_service.transition_run(run_id, "running", "user")
    assert started.status == "running" and started.started_at is not None
    assert started.started_at.tzinfo is UTC
    finished = await workflow_service.transition_run(
        run_id, terminal, "system", {"error_message": "Example failure"}
    )
    assert finished.status == terminal and finished.completed_at is not None
    assert finished.completed_at.tzinfo is UTC
    assert finished.error_message == ("Example failure" if terminal == "failed" else None)
    events = await AuditLogRepository(async_db_session).list_for_run(run_id)
    assert events[-1].event_type == "run_status_changed" and events[-1].actor == "system"
    assert events[-1].payload_json is not None
    assert json.loads(events[-1].payload_json) == {
        "from": "running",
        "to": terminal,
        "error_message": "Example failure",
    }


async def test_transition_run_invalid(
    workflow_service: WorkflowService, workflow_id: int, async_db_session: AsyncSession
) -> None:
    run_id = (await workflow_service.create_run(workflow_id)).id
    for target in ("completed", "waiting_approval", "paused"):
        with pytest.raises(InvalidStatusTransitionError) as exc:
            await workflow_service.transition_run(run_id, target, "user")
        assert (exc.value.run_id, exc.value.from_status, exc.value.to_status) == (
            run_id,
            "pending",
            target,
        )
    assert len(await AuditLogRepository(async_db_session).list_for_run(run_id)) == 1


async def test_repository_filters_and_transition(async_db_session: AsyncSession) -> None:
    session = async_db_session
    project = Project(name="Project")
    session.add(project)
    await session.commit()
    workflows = WorkflowRepository(session)
    runs = WorkflowRunRepository(session)
    first = (
        await workflows.create({"name": "A", "project_id": project.id, "definition_json": "opaque"})
    ).id
    second = (await workflows.create({"name": "B", "status": "active"})).id
    project_id = project.id
    session.expunge_all()
    project_workflows = await workflows.list_by_project(project_id)
    assert [row.id for row in project_workflows] == [first]
    assert "definition_json" in inspect(project_workflows[0]).unloaded
    assert [row.id for row in await workflows.list_by_status("active")] == [second]
    pending_id = (await runs.create({"workflow_id": first})).id
    running_id = (await runs.create({"workflow_id": first, "status": "running"})).id
    await runs.create({"workflow_id": second})
    assert [row.id for row in await runs.list_by_workflow(first)] == [pending_id, running_id]
    with pytest.raises(InvalidStatusTransitionError):
        await runs.transition_status(pending_id, "completed", ["pending", "running"])
    assert (
        await runs.transition_status(running_id, "completed", ["running"])
    ).status == "completed"
    with pytest.raises(LookupError):
        await runs.transition_status(999, "running", ["pending"])


async def test_workflow_service_rejects_missing_and_paused(
    workflow_service: WorkflowService, async_db_session: AsyncSession
) -> None:
    with pytest.raises(LookupError):
        await workflow_service.create_run(999)
    paused = await WorkflowRepository(async_db_session).create(
        {"name": "Paused", "status": "paused"}
    )
    with pytest.raises(ValueError, match="paused"):
        await workflow_service.create_run(paused.id)


async def test_audit_failure_rolls_back_run_change(
    workflow_service: WorkflowService, workflow_id: int, async_db_session: AsyncSession
) -> None:
    run_id = (await workflow_service.create_run(workflow_id)).id
    with pytest.raises(TypeError):
        await workflow_service.transition_run(run_id, "running", "system", {"bad": object()})
    assert await WorkflowRunRepository(async_db_session).get_status(run_id) == "pending"
    assert len(await AuditLogRepository(async_db_session).list_for_run(run_id)) == 1


async def test_delete_project_sets_workflow_project_id_null(async_db_session: AsyncSession) -> None:
    project = Project(name="Project")
    async_db_session.add(project)
    await async_db_session.commit()
    repo = WorkflowRepository(async_db_session)
    workflow_id = (await repo.create({"name": "Example", "project_id": project.id})).id
    await async_db_session.delete(project)
    await async_db_session.commit()
    async_db_session.expunge_all()
    workflow = await repo.get(workflow_id)
    assert workflow is not None and workflow.project_id is None


async def test_delete_workflow_cascades_to_workflow_runs(
    workflow_service: WorkflowService, workflow_id: int, async_db_session: AsyncSession
) -> None:
    await workflow_service.create_run(workflow_id)
    assert await WorkflowRepository(async_db_session).delete(workflow_id)
    assert await WorkflowRunRepository(async_db_session).list_by_workflow(workflow_id) == []


async def test_delete_workflow_run_sets_audit_log_workflow_run_id_null(
    workflow_service: WorkflowService, workflow_id: int, async_db_session: AsyncSession
) -> None:
    run = await workflow_service.create_run(workflow_id)
    async_db_session.add(
        ApprovalRequest(workflow_run_id=run.id, step_name="Review", action_description="Review")
    )
    await async_db_session.commit()
    assert await WorkflowRunRepository(async_db_session).delete(run.id)
    async_db_session.expunge_all()
    audit = (await async_db_session.scalars(select(WorkflowAuditLog))).one()
    assert audit.workflow_run_id is None and audit.event_type == "run_created"
    assert (await async_db_session.scalars(select(ApprovalRequest))).all() == []


async def test_insert_invalid_foreign_key_raises_integrity_error(
    async_db_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        await WorkflowRunRepository(async_db_session).create({"workflow_id": 999})


async def test_paused_is_not_a_run_status(workflow_id: int, async_db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="CHECK"):
        await WorkflowRunRepository(async_db_session).create(
            {"workflow_id": workflow_id, "status": "paused"}
        )


async def test_invalid_audit_actor_is_rejected(async_db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="actor"):
        await AuditLogRepository(async_db_session).log_event("run_created", "external")
    assert (await async_db_session.scalars(select(WorkflowAuditLog))).all() == []
