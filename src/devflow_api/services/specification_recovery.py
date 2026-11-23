"""Startup settlement of specification work interrupted by a process restart."""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.models.audit import WorkflowAuditLog
from devflow_api.models.specification import (
    GenerationAttempt,
    ReviewAttempt,
    SpecificationApprovalRequest,
    SpecificationRequest,
    SpecificationVersion,
)
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.approval import AuditLogRepository
from devflow_api.services.specification_attempts import ACTIVE

INTERRUPTED = "INTERRUPTED"
type Attempt = GenerationAttempt | ReviewAttempt


async def record_standalone_expiry(
    session: AsyncSession,
    approval: SpecificationApprovalRequest,
) -> bool:
    """Record expiry once. The caller holds the immediate write transaction."""
    exists = await session.scalar(
        select(WorkflowAuditLog.id)
        .where(
            WorkflowAuditLog.event_type == "spec_approval_expired",
            WorkflowAuditLog.workflow_run_id.is_(None),
            func.json_extract(WorkflowAuditLog.payload_json, "$.approval_id") == approval.id,
        )
        .limit(1)
    )
    if exists is not None:
        return False
    version = await session.get(SpecificationVersion, approval.specification_version_id)
    await AuditLogRepository(session).log_event(
        "spec_approval_expired",
        "system",
        None,
        {
            "approval_id": approval.id,
            "approval_path": "standalone",
            "specification_request_id": version.specification_request_id if version else None,
            "specification_version_id": approval.specification_version_id,
        },
        commit=False,
    )
    return True


class SpecificationRecoveryService:
    """Recover durable attempts without invoking providers or workflow dispatch."""

    def __init__(self, session: AsyncSession) -> None:
        self._sessions = async_sessionmaker(session.bind, expire_on_commit=False)

    async def recover(self) -> dict[str, int]:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            generation_ids = list(
                await session.scalars(
                    select(GenerationAttempt.id)
                    .where(GenerationAttempt.status.in_(ACTIVE))
                    .order_by(GenerationAttempt.id)
                )
            )
            review_ids = list(
                await session.scalars(
                    select(ReviewAttempt.id)
                    .where(ReviewAttempt.status.in_(ACTIVE))
                    .order_by(ReviewAttempt.id)
                )
            )
            expired_ids = list(
                await session.scalars(
                    select(SpecificationApprovalRequest.id)
                    .where(
                        SpecificationApprovalRequest.expires_at <= now,
                        SpecificationApprovalRequest.consumed_at.is_(None),
                        SpecificationApprovalRequest.rejected_at.is_(None),
                    )
                    .order_by(SpecificationApprovalRequest.id)
                )
            )

        counts = {"generations": 0, "reviews": 0, "expired_approvals": 0}
        for attempt_id in generation_ids:
            counts["generations"] += await self._recover_attempt(GenerationAttempt, attempt_id, now)
        for attempt_id in review_ids:
            counts["reviews"] += await self._recover_attempt(ReviewAttempt, attempt_id, now)
        for approval_id in expired_ids:
            counts["expired_approvals"] += await self._recover_approval(approval_id, now)
        return counts

    async def _recover_attempt(
        self,
        model: type[Attempt],
        attempt_id: int,
        now: datetime,
    ) -> bool:
        async with self._sessions() as session, immediate_transaction(session):
            attempt = cast(Attempt | None, await session.get(model, attempt_id))
            if attempt is None or attempt.status not in ACTIVE:
                return False
            prior_status = attempt.status
            values: dict[str, object] = {
                "status": "failed",
                "error_code": INTERRUPTED,
                "completed_at": now,
                "updated_at": now,
            }
            if model is GenerationAttempt:
                values["error_message"] = "Specification generation interrupted by service restart"
            result = cast(
                CursorResult[object],
                await session.execute(
                    update(model)
                    .where(model.id == attempt_id, model.status == prior_status)
                    .values(**values)
                ),
            )
            if result.rowcount != 1:
                return False

            version = (
                await session.get(SpecificationVersion, attempt.specification_version_id)
                if attempt.specification_version_id is not None
                else None
            )
            generation = isinstance(attempt, GenerationAttempt)
            request_id = (
                attempt.specification_request_id
                if isinstance(attempt, GenerationAttempt)
                else version.specification_request_id
                if version is not None
                else None
            )
            if version is not None and request_id is not None:
                await self._restore_current(session, attempt, version, request_id, now)

            await AuditLogRepository(session).log_event(
                "spec_generation_failed" if generation else "spec_review_failed",
                "system",
                None,
                {
                    "attempt_id": attempt_id,
                    "specification_request_id": request_id,
                    "specification_version_id": attempt.specification_version_id,
                    "error_code": INTERRUPTED,
                    "prior_status": prior_status,
                    "cancellation_requested": bool(attempt.cancellation_requested),
                },
                commit=False,
            )
            return True

    @staticmethod
    async def _restore_current(
        session: AsyncSession,
        attempt: Attempt,
        version: SpecificationVersion,
        request_id: int,
        now: datetime,
    ) -> None:
        request = await session.get(SpecificationRequest, request_id)
        if (
            request is None
            or version.specification_request_id != request.id
            or request.current_version != version.version_number
        ):
            return

        if isinstance(attempt, GenerationAttempt):
            newer = select(GenerationAttempt.id).where(
                GenerationAttempt.specification_request_id == request_id,
                GenerationAttempt.id > attempt.id,
            )
            expected_request, expected_version, restored = "generating", "draft", "draft"
        else:
            newer = select(ReviewAttempt.id).where(
                ReviewAttempt.specification_version_id == version.id,
                ReviewAttempt.id > attempt.id,
            )
            expected_request, expected_version, restored = (
                "under_review",
                "under_review",
                "generated",
            )

        if (
            request.status != expected_request
            or version.status != expected_version
            or await session.scalar(newer.limit(1)) is not None
        ):
            return
        request.status, request.updated_at = restored, now
        version.status, version.updated_at = restored, now

    async def _recover_approval(self, approval_id: int, now: datetime) -> bool:
        async with self._sessions() as session, immediate_transaction(session):
            approval = await session.get(SpecificationApprovalRequest, approval_id)
            if (
                approval is None
                or approval.expires_at > now
                or approval.consumed_at is not None
                or approval.rejected_at is not None
            ):
                return False
            return await record_standalone_expiry(session, approval)
