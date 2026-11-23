"""Single-use standalone specification approvals."""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from devflow_api.models.specification import SpecificationApprovalRequest
from devflow_api.repositories._workflow_transaction import immediate_transaction
from devflow_api.specification_errors import ApprovalBindingMismatch, SpecificationNotFoundError
from devflow_core.exceptions import ApprovalAlreadyResolvedError, ApprovalExpiredError

OPERATION = "approve_specification"


class SpecificationApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, approval_id: int) -> SpecificationApprovalRequest:
        row = await self.session.get(
            SpecificationApprovalRequest, approval_id, populate_existing=True
        )
        if row is None:
            raise SpecificationNotFoundError("Specification approval not found")
        return row

    async def create(
        self,
        version_id: int,
        parameters_hash: str,
        actor_id: str,
        expires_at: datetime,
        *,
        commit: bool = True,
    ) -> SpecificationApprovalRequest:
        async with immediate_transaction(self.session, commit=commit):
            row = await self.session.scalar(
                select(SpecificationApprovalRequest)
                .where(
                    SpecificationApprovalRequest.specification_version_id == version_id,
                    SpecificationApprovalRequest.consumed_at.is_(None),
                    SpecificationApprovalRequest.rejected_at.is_(None),
                    SpecificationApprovalRequest.expires_at > datetime.now(UTC),
                )
                .limit(1)
            )
            if row is not None:
                self.check_binding(row, version_id, parameters_hash, actor_id)
                return row
            row = SpecificationApprovalRequest(
                specification_version_id=version_id,
                parameters_hash=parameters_hash,
                actor_id=actor_id,
                expires_at=expires_at,
                operation=OPERATION,
            )
            self.session.add(row)
            await self.session.flush()
            return row

    @staticmethod
    def check_binding(
        row: SpecificationApprovalRequest,
        version_id: int,
        parameters_hash: str,
        actor_id: str,
    ) -> None:
        if (row.specification_version_id, row.parameters_hash, row.actor_id, row.operation) != (
            version_id,
            parameters_hash,
            actor_id,
            OPERATION,
        ):
            raise ApprovalBindingMismatch("Specification approval binding does not match")

    @staticmethod
    def check_pending(row: SpecificationApprovalRequest, now: datetime) -> None:
        if row.consumed_at is not None or row.rejected_at is not None:
            raise ApprovalAlreadyResolvedError(
                row.id, "approved" if row.consumed_at is not None else "rejected"
            )
        if row.expires_at <= now:
            raise ApprovalExpiredError("Specification approval expired")

    async def consume_atomic(
        self,
        approval_id: int,
        expected_version_id: int,
        expected_parameters_hash: str,
        expected_actor_id: str,
        *,
        commit: bool = True,
    ) -> bool:
        async with immediate_transaction(self.session, commit=commit):
            row = await self.get(approval_id)
            self.check_binding(
                row, expected_version_id, expected_parameters_hash, expected_actor_id
            )
            self.check_pending(row, datetime.now(UTC))
            await self._resolve(approval_id, consumed=True)
            return True

    async def reject(self, approval_id: int, *, commit: bool = True) -> None:
        async with immediate_transaction(self.session, commit=commit):
            row = await self.get(approval_id)
            self.check_pending(row, datetime.now(UTC))
            await self._resolve(approval_id, consumed=False)

    async def _resolve(self, approval_id: int, *, consumed: bool) -> None:
        field = "consumed_at" if consumed else "rejected_at"
        result = cast(
            CursorResult[object],
            await self.session.execute(
                update(SpecificationApprovalRequest)
                .where(
                    SpecificationApprovalRequest.id == approval_id,
                    SpecificationApprovalRequest.consumed_at.is_(None),
                    SpecificationApprovalRequest.rejected_at.is_(None),
                )
                .values(**{field: datetime.now(UTC)})
            ),
        )
        if result.rowcount != 1:
            raise ApprovalAlreadyResolvedError(approval_id, "resolved")
