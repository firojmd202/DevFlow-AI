"""Append-only workflow audit records."""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.models.base import Base, UTCDateTime


class WorkflowAuditLog(Base):
    __tablename__ = "workflow_audit_log"
    __table_args__ = (
        Index("idx_audit_run_id", "workflow_run_id"),
        Index("idx_audit_created", "created_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))
