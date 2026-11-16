"""SQLite transaction boundaries for MCP approvals."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.adapters.exceptions import ConsumedError
from devflow_api.models.mcp_approval import MCPApproval


class MCPApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._writers = async_sessionmaker(session.bind, expire_on_commit=False)

    async def create(self, approval: MCPApproval) -> MCPApproval:
        self.session.add(approval)
        try:
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()
            raise
        await self.session.refresh(approval)
        return approval

    async def get_by_id(self, id: UUID) -> MCPApproval | None:
        return await self.session.get(MCPApproval, str(id), populate_existing=True)

    async def list_pending(self, server_id: str) -> list[MCPApproval]:
        query = (
            select(MCPApproval)
            .where(MCPApproval.mcp_server_id == server_id, MCPApproval.status == "PENDING")
            .order_by(MCPApproval.requested_at, MCPApproval.id)
        )
        return list((await self.session.scalars(query)).all())

    async def consume_atomic(
        self,
        id: UUID,
        actor_id: str,
        mcp_server_id: str,
        tool_name: str,
        arguments_hash: str,
        trusted_workflow_run_id: int | None,
        now: datetime,
    ) -> MCPApproval:
        if now.utcoffset() is None:
            raise ConsumedError("MCP approval consumption requires a UTC timestamp")
        async with self._writers() as writer:
            try:
                await writer.execute(text("BEGIN IMMEDIATE"))
                now = max(now, datetime.now(UTC))
                authorized = (
                    MCPApproval.id == str(id),
                    MCPApproval.actor_id == actor_id,
                    MCPApproval.mcp_server_id == mcp_server_id,
                    MCPApproval.tool_name == tool_name,
                    MCPApproval.arguments_hash == arguments_hash,
                    MCPApproval.workflow_run_id == trusted_workflow_run_id,
                    MCPApproval.status == "APPROVED",
                    MCPApproval.expires_at > now,
                    MCPApproval.consumed_at.is_(None),
                )
                result = await writer.scalar(select(MCPApproval.id).where(*authorized))
                if result is None:
                    existing = await writer.get(MCPApproval, str(id))
                    if existing is not None:
                        if existing.status == "CONSUMED" or existing.consumed_at is not None:
                            raise ConsumedError(
                                "MCP approval cannot be consumed", "already_consumed"
                            )
                        if existing.status == "EXPIRED" or existing.expires_at <= now:
                            raise ConsumedError("MCP approval cannot be consumed", "expired")
                    raise ConsumedError("MCP approval cannot be consumed")
                # RETURNING proves that exactly one row was changed. The primary key bounds the set.
                statement = (
                    update(MCPApproval)
                    .where(*authorized)
                    .values(status="CONSUMED", consumed_at=now)
                    .returning(MCPApproval)
                )
                approval = (await writer.scalars(statement)).one_or_none()
                if approval is None:
                    raise ConsumedError("MCP approval cannot be consumed", "already_consumed")
                await writer.commit()
            except SQLAlchemyError:
                await writer.rollback()
                raise ConsumedError("MCP authorization database operation failed") from None
            except BaseException:
                await writer.rollback()
                raise
            return approval
