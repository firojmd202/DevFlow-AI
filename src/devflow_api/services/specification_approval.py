"""Digest-bound human decisions for standalone and workflow specifications."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.approval import ApprovalRequest
from devflow_api.models.audit import WorkflowAuditLog
from devflow_api.models.specification import (
    ReviewAttempt,
    ReviewFinding,
    SpecificationApprovalRequest,
    SpecificationRequest,
    SpecificationVersion,
)
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.repositories.approval import ApprovalRepository, AuditLogRepository
from devflow_api.repositories.specification_approval import (
    OPERATION,
    SpecificationApprovalRepository,
)
from devflow_api.repositories.specification_version import SpecificationVersionRepository, text_hash
from devflow_api.repositories.workflow import WorkflowRunRepository
from devflow_api.schemas.approval import ApprovalDecision
from devflow_api.services.approval import ApprovalService
from devflow_api.specification_errors import (
    ApprovalBindingMismatch,
    ApprovedSpecificationError,
    InvalidSpecTransitionError,
    SpecDigestMismatchError,
    SpecificationNotFoundError,
)
from devflow_api.specification_security import redact_text
from devflow_core.config import Settings, get_settings


def parameters_hash(version_id: int, digest: str) -> str:
    return text_hash(f"{version_id}:{digest}")


class SpecificationApprovalService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.versions = SpecificationVersionRepository(session, self.settings)
        self.standalone = SpecificationApprovalRepository(session)
        self.workflow = ApprovalService(
            ApprovalRepository(session, self.settings),
            WorkflowRunRepository(session),
            AuditLogRepository(session),
        )

    def _actor(self, actor: str) -> None:
        if actor != self.settings.LOCAL_OPERATOR_ID:
            raise ApprovalBindingMismatch("Approval actor does not match the local operator")

    @staticmethod
    def _check_decision(decision: ApprovalDecision) -> None:
        if decision not in ("approved", "rejected"):
            raise ApprovalBindingMismatch("Invalid approval decision")

    async def request_approval(
        self,
        request_id: int,
        actor_id: str,
        *,
        expected_version_id: int,
        expected_digest: str | None = None,
    ) -> SpecificationApprovalRequest | ApprovalRequest:
        self._actor(actor_id)
        async with immediate_transaction(self.session):
            request = await self.versions.get_request(request_id)
            version = await self.versions.current_version(request)
            if version.id != expected_version_id:
                raise ApprovalBindingMismatch("Specification version is stale")
            digest = await self._eligible(version)
            if expected_digest is not None and expected_digest != digest:
                raise SpecDigestMismatchError("Approval digest is stale")
            binding = parameters_hash(version.id, digest)
            row: SpecificationApprovalRequest | ApprovalRequest
            path: Literal["standalone", "bound"] = "standalone"
            if request.workflow_run_id is None:
                row = await self.standalone.create(
                    version.id,
                    binding,
                    actor_id,
                    datetime.now(UTC) + timedelta(seconds=self.settings.APPROVAL_TTL_SECONDS),
                    commit=False,
                )
            else:
                path = "bound"
                if request.workflow_step_id is None:
                    raise ApprovalBindingMismatch("Specification has no workflow step")
                row = await self.workflow.request_bound_approval(
                    request.workflow_run_id,
                    request.workflow_step_id,
                    commit=False,
                )
                self._check_bound(request, row)
            existing = await self._record(request.id, version.id, row.id, path)
            if existing is not None and existing != binding:
                raise ApprovalBindingMismatch("Approval was requested for different artifacts")
            if existing is None:
                await self.versions.audit(
                    "spec_approval_requested",
                    request,
                    version,
                    approval_id=row.id,
                    parameters_hash=binding,
                    actor_id=actor_id,
                    approval_path=path,
                )
            return row

    async def resolve_standalone(
        self,
        approval_id: int,
        decision: ApprovalDecision,
        resolved_by: str,
        *,
        request_id: int,
        expected_version_id: int,
        expected_digest: str,
        reason: str | None = None,
    ) -> SpecificationVersion:
        self._actor(resolved_by)
        self._check_decision(decision)
        async with immediate_transaction(self.session):
            request = await self.versions.get_request(request_id)
            version = await self.versions.current_version(request)
            if request.workflow_run_id is not None or version.id != expected_version_id:
                raise ApprovalBindingMismatch("Approval does not match the current specification")
            row = await self.standalone.get(approval_id)
            binding = parameters_hash(version.id, expected_digest)
            self.standalone.check_binding(row, version.id, binding, resolved_by)
            self.standalone.check_pending(row, datetime.now(UTC))
            if decision == "approved":
                await self.standalone.consume_atomic(
                    approval_id, version.id, binding, resolved_by, commit=False
                )
            else:
                await self.standalone.reject(approval_id, commit=False)
            if await self._eligible(version) != expected_digest:
                raise SpecDigestMismatchError("Specification digest changed")
            await self._finalize(request, version, approval_id, decision, resolved_by, reason)
            return version

    async def resolve_bound(
        self,
        approval_id: int,
        decision: ApprovalDecision,
        resolved_by: str,
        *,
        request_id: int,
        expected_version_id: int,
        expected_digest: str,
        reason: str | None = None,
    ) -> SpecificationVersion:
        self._actor(resolved_by)
        self._check_decision(decision)
        request = await self.versions.get_request(request_id)
        version = await self.versions.current_version(request)
        row = await self.session.get(ApprovalRequest, approval_id)
        if row is None:
            raise SpecificationNotFoundError("Workflow approval not found")
        self._check_bound(request, row)
        if version.id != expected_version_id or await self._record(
            request_id, version.id, approval_id, "bound"
        ) != parameters_hash(version.id, expected_digest):
            raise ApprovalBindingMismatch("Workflow approval binding does not match")
        if row.status != "pending":
            await self.workflow.resolve(approval_id, decision, resolved_by)
        if version.status != "ready_for_approval":
            raise InvalidSpecTransitionError("Current specification is not ready for approval")
        # This commits the Wave 1 human decision. The dispatch lease is separate.
        await self.workflow.resolve(approval_id, decision, resolved_by)
        failure = False
        async with immediate_transaction(self.session):
            request = await self.versions.get_request(request_id)
            current = await self.versions.current_version(request)
            row = await self.session.get(ApprovalRequest, approval_id, populate_existing=True)
            failure = (
                current.id != expected_version_id
                or current.content_digest != expected_digest
                or current.status != "ready_for_approval"
                or row is None
                or row.workflow_run_id != request.workflow_run_id
                or row.workflow_step_run_id != request.workflow_step_id
                or not await self.versions.verify_digest(current.id)
            )
            if not failure:
                try:
                    await self._eligible(current)
                except (InvalidSpecTransitionError, SpecDigestMismatchError):
                    failure = True
            if failure:
                await self.versions.audit(
                    "spec_approval_digest_mismatch",
                    request,
                    current,
                    approval_id=approval_id,
                    reason="specification_binding_changed_since_approval",
                )
            else:
                await self._finalize(request, current, approval_id, decision, resolved_by, reason)
        if failure:
            raise SpecDigestMismatchError("Specification changed after workflow approval")
        return current

    async def is_implementation_authorized(self, request_id: int) -> bool:
        """Check the specification prerequisite. Wave 1 still owns dispatch authorization."""
        request = await self.versions.get_request(request_id)
        version = await self.versions.current_version(request)
        if version.status != "approved" or not await self.versions.verify_digest(version.id):
            return False
        if request.workflow_run_id is not None:
            return version.spec_bound_approval_id is not None
        if version.spec_standalone_approval_id is None:
            return False
        row = await self.standalone.get(version.spec_standalone_approval_id)
        return (
            row.specification_version_id == version.id
            and row.operation == OPERATION
            and row.parameters_hash == parameters_hash(version.id, version.content_digest or "")
            and row.consumed_at is not None
            and row.rejected_at is None
        )

    async def acknowledge(self, request_id: int, finding_id: int, actor_id: str) -> ReviewFinding:
        self._actor(actor_id)
        async with immediate_transaction(self.session):
            request = await self.versions.get_request(request_id)
            version = await self.versions.current_version(request)
            finding = await self.session.get(ReviewFinding, finding_id)
            if finding is None or finding.specification_version_id != version.id:
                raise SpecificationNotFoundError("Current specification finding not found")
            if version.status not in {"ready_for_approval", "revision_required"}:
                raise InvalidSpecTransitionError("Finding cannot be acknowledged in this state")
            if not finding.acknowledged:
                now = datetime.now(UTC)
                finding.acknowledged = 1
                finding.acknowledged_at = now
                finding.acknowledged_by = redact_text(actor_id, self.settings)
                await self.versions.audit(
                    "critical_finding_acknowledged"
                    if finding.severity == "Critical"
                    else "spec_finding_acknowledged",
                    request,
                    version,
                    actor="user",
                    actor_id=actor_id,
                    finding_id=finding.id,
                    acknowledged_at=now.isoformat(),
                )
            return finding

    async def _eligible(self, version: SpecificationVersion) -> str:
        if version.status == "approved":
            raise ApprovedSpecificationError("Approved specification is immutable")
        if version.status != "ready_for_approval":
            raise InvalidSpecTransitionError("Specification is not ready for approval")
        attempt = await self.session.scalar(
            select(ReviewAttempt)
            .where(ReviewAttempt.specification_version_id == version.id)
            .order_by(ReviewAttempt.id.desc())
            .limit(1)
        )
        if attempt is None or attempt.status != "succeeded" or attempt.error_code is not None:
            raise InvalidSpecTransitionError("Specification requires a completed review")
        findings = await self.versions.list_findings(attempt.id)
        if any(
            f.severity == "Critical" or (f.severity == "High" and not f.acknowledged)
            for f in findings
        ):
            raise InvalidSpecTransitionError("Review findings block approval")
        if (
            version.content_digest is None
            or attempt.artifact_hash != version.content_digest
            or not await self.versions.verify_digest(version.id)
        ):
            raise SpecDigestMismatchError("Specification requires a verified digest")
        return version.content_digest

    async def _record(
        self,
        request_id: int,
        version_id: int,
        approval_id: int,
        path: Literal["standalone", "bound"],
    ) -> str | None:
        return await self.session.scalar(
            select(func.json_extract(WorkflowAuditLog.payload_json, "$.parameters_hash"))
            .where(
                WorkflowAuditLog.event_type == "spec_approval_requested",
                func.json_extract(WorkflowAuditLog.payload_json, "$.specification_request_id")
                == request_id,
                func.json_extract(WorkflowAuditLog.payload_json, "$.specification_version_id")
                == version_id,
                func.json_extract(WorkflowAuditLog.payload_json, "$.approval_id") == approval_id,
                func.json_extract(WorkflowAuditLog.payload_json, "$.approval_path") == path,
            )
            .order_by(WorkflowAuditLog.id.desc())
            .limit(1)
        )

    def _check_bound(self, request: SpecificationRequest, approval: ApprovalRequest) -> None:
        if (
            request.workflow_run_id is None
            or request.workflow_step_id is None
            or approval.workflow_run_id != request.workflow_run_id
            or approval.workflow_step_run_id != request.workflow_step_id
            or approval.operation != "specification_approval"
            or approval.actor_id != self.settings.LOCAL_OPERATOR_ID
        ):
            raise ApprovalBindingMismatch("Workflow approval does not belong to the specification")

    async def _finalize(
        self,
        request: SpecificationRequest,
        version: SpecificationVersion,
        approval_id: int,
        decision: ApprovalDecision,
        actor_id: str,
        reason: str | None,
    ) -> None:
        if decision == "approved":
            await self.versions.approve_verified(
                version.id,
                approval_id,
                actor_id,
                bound=request.workflow_run_id is not None,
            )
        else:
            await self.versions.transition_status(
                version.id,
                "ready_for_approval",
                "revision_required",
                commit=False,
            )
        await self.versions.audit(
            "spec_approved" if decision == "approved" else "spec_approval_rejected",
            request,
            version,
            actor="user",
            actor_id=actor_id,
            approval_id=approval_id,
            parameters_hash=parameters_hash(version.id, version.content_digest or ""),
            reason=reason,
        )
