"""Single-use persisted authorization for a GitHub write."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.models.base import Base, UTCDateTime


class GitHubConfirmation(Base):
    __tablename__ = "github_confirmations"
    __table_args__ = (
        CheckConstraint(
            "operation IN ('branch_create', 'pr_create')", name="ck_github_confirmations_operation"
        ),
        CheckConstraint(
            "status IN ('ISSUED','EXPIRED','USED')", name="ck_github_confirmations_status"
        ),
        Index("idx_github_confirmations_expires", "expires_at"),
        Index("idx_github_confirmations_actor", "actor_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    repo_full_name: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(Text)
    parameters_hash: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(Text)
    workflow_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL")
    )
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(Text, server_default="ISSUED")
