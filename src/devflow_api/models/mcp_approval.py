"""Persisted authorization for a single MCP invocation."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.models.base import Base, UTCDateTime


class MCPApproval(Base):
    __tablename__ = "mcp_approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED')",
            name="ck_mcp_approvals_status",
        ),
        Index("idx_mcp_approvals_server", "mcp_server_id"),
        Index("idx_mcp_approvals_status", "status"),
        Index("idx_mcp_approvals_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    mcp_server_id: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str] = mapped_column(Text)
    arguments_hash: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(Text)
    workflow_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, server_default="PENDING")
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
