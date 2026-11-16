"""Workflow step approval gates."""

import json
from typing import Literal

from devflow_api.models.approval import ApprovalRequest
from devflow_api.models.workflow import WorkflowRun
from devflow_api.repositories.approval import ApprovalRepository, AuditLogRepository
from devflow_api.repositories.workflow import WorkflowRunRepository
from devflow_api.services._transaction import shared_session, transaction


class ApprovalService:
    def __init__(
        self,
        approval_repo: ApprovalRepository,
        run_repo: WorkflowRunRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._approval_repo = approval_repo
        self._run_repo = run_repo
        self._audit_repo = audit_repo
        self._session = shared_session(approval_repo.session, run_repo.session, audit_repo.session)

    async def request_approval(
        self,
        run_id: int,
        step_name: str,
        action_description: str,
        payload: dict[str, object] | None = None,
    ) -> ApprovalRequest:
        async with transaction(self._session):
            await self._run_repo.transition_status(
                run_id, "waiting_approval", ["running"], commit=False
            )
            approval = await self._approval_repo.create(
                {
                    "workflow_run_id": run_id,
                    "step_name": step_name,
                    "action_description": action_description,
                    "payload_json": json.dumps(payload, allow_nan=False)
                    if payload is not None
                    else None,
                },
                commit=False,
            )
            await self._audit_repo.log_event(
                "approval_requested",
                "system",
                run_id,
                {"approval_id": approval.id, "step_name": step_name},
                commit=False,
            )
        return approval

    async def resolve(
        self,
        approval_id: int,
        decision: Literal["approved", "rejected"],
        resolved_by: str | None,
    ) -> tuple[ApprovalRequest, WorkflowRun]:
        async with transaction(self._session):
            approval = await self._approval_repo.resolve(
                approval_id, decision, resolved_by, commit=False
            )
            new_status = "running" if decision == "approved" else "cancelled"
            run = await self._run_repo.transition_status(
                approval.workflow_run_id, new_status, ["waiting_approval"], commit=False
            )
            await self._audit_repo.log_event(
                "approval_resolved",
                "user",
                run.id,
                {"approval_id": approval.id, "decision": decision, "resolved_by": resolved_by},
                commit=False,
            )
        return approval, run
