"""Explicit workflow run lifecycle operations."""

from devflow_api.models.workflow import WorkflowRun
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.repositories.workflow import WorkflowRepository, WorkflowRunRepository
from devflow_api.services._transaction import shared_session, transaction
from devflow_core.exceptions import InvalidStatusTransitionError

WORKFLOW_TRANSITIONS = {
    "pending": {"running"},
    "running": {"completed", "failed", "cancelled"},
}


class WorkflowService:
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        run_repo: WorkflowRunRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._workflow_repo = workflow_repo
        self._run_repo = run_repo
        self._audit_repo = audit_repo
        self._session = shared_session(workflow_repo.session, run_repo.session, audit_repo.session)

    async def create_run(self, workflow_id: int) -> WorkflowRun:
        async with transaction(self._session):
            status = await self._workflow_repo.get_status(workflow_id)
            if status is None:
                raise LookupError(f"Workflow {workflow_id} does not exist")
            if status == "paused":
                raise ValueError("A paused workflow cannot start a new run")
            run = await self._run_repo.create({"workflow_id": workflow_id}, commit=False)
            await self._audit_repo.log_event("run_created", "system", run.id, commit=False)
        return run

    async def transition_run(
        self,
        run_id: int,
        new_status: str,
        actor: str,
        payload: dict[str, object] | None = None,
    ) -> WorkflowRun:
        async with transaction(self._session):
            old_status = await self._run_repo.get_status(run_id)
            if new_status not in WORKFLOW_TRANSITIONS.get(old_status, set()):
                raise InvalidStatusTransitionError(run_id, old_status, new_status)
            audit_payload = dict(payload or {})
            error_message = audit_payload.get("error_message")
            run = await self._run_repo.transition_status(
                run_id,
                new_status,
                [old_status],
                error_message=error_message if isinstance(error_message, str) else None,
                commit=False,
            )
            audit_payload.update({"from": old_status, "to": new_status})
            await self._audit_repo.log_event(
                "run_status_changed", actor, run.id, audit_payload, commit=False
            )
        return run
