"""Workflow approvals and append-only audit persistence."""

import json
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.approval import ApprovalRequest
from devflow_api.models.audit import WorkflowAuditLog
from devflow_api.repositories.base import BaseRepository
from devflow_core.exceptions import ApprovalAlreadyResolvedError


class ApprovalRepository(BaseRepository[ApprovalRequest]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ApprovalRequest, session)

    async def list_pending(self) -> list[ApprovalRequest]:
        query = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "pending")
            .order_by(ApprovalRequest.created_at, ApprovalRequest.id)
        )
        return list((await self.session.scalars(query)).all())

    async def resolve(
        self,
        approval_id: int,
        decision: Literal["approved", "rejected"],
        resolved_by: str | None,
        *,
        commit: bool = True,
    ) -> ApprovalRequest:
        if decision not in ("approved", "rejected"):
            raise ValueError("Approval decision must be approved or rejected")
        now = datetime.now(UTC)
        statement = (
            update(ApprovalRequest)
            .where(ApprovalRequest.id == approval_id, ApprovalRequest.status == "pending")
            .values(status=decision, resolved_at=now, resolved_by=resolved_by, updated_at=now)
            .returning(ApprovalRequest)
            .execution_options(populate_existing=True)
        )
        try:
            approval = (await self.session.scalars(statement)).one_or_none()
            if approval is None:
                status = await self.session.scalar(
                    select(ApprovalRequest.status).where(ApprovalRequest.id == approval_id)
                )
                if status is None:
                    raise LookupError(f"Approval {approval_id} does not exist")
                raise ApprovalAlreadyResolvedError(approval_id, status)
            if commit:
                await self.session.commit()
        except Exception:
            if commit:
                await self.session.rollback()
            raise
        return approval


class AuditLogRepository(BaseRepository[WorkflowAuditLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(WorkflowAuditLog, session)

    async def update(self, id: int, obj_in: dict[str, object]) -> WorkflowAuditLog | None:
        raise TypeError("Audit records are append-only")

    async def delete(self, id: int) -> bool:
        raise TypeError("Audit records are append-only")

    async def log_event(
        self,
        event_type: str,
        actor: str,
        workflow_run_id: int | None = None,
        payload: dict[str, object] | None = None,
        *,
        commit: bool = True,
    ) -> WorkflowAuditLog:
        if actor not in ("system", "user"):
            raise ValueError("Audit actor must be system or user")
        return await self.create(
            {
                "event_type": event_type,
                "actor": actor,
                "workflow_run_id": workflow_run_id,
                "payload_json": json.dumps(payload, allow_nan=False)
                if payload is not None
                else None,
            },
            commit=commit,
        )

    async def list_for_run(self, run_id: int) -> list[WorkflowAuditLog]:
        query = (
            select(WorkflowAuditLog)
            .where(WorkflowAuditLog.workflow_run_id == run_id)
            .order_by(WorkflowAuditLog.created_at, WorkflowAuditLog.id)
        )
        return list((await self.session.scalars(query)).all())
