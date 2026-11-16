"""004 add approval audit tables."""

import sqlalchemy as sa
from alembic import op

revision = "004_add_approval_audit_tables"
down_revision = "003_add_workflow_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_run_id",
            sa.Integer(),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.Text(), nullable=False),
        sa.Column("action_description", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text()),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.CheckConstraint("status IN ('pending','approved','rejected','expired')"),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("resolved_by", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "workflow_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL")
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("idx_audit_run_id", "workflow_audit_log", ["workflow_run_id"])
    op.create_index("idx_audit_created", "workflow_audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_created", table_name="workflow_audit_log")
    op.drop_index("idx_audit_run_id", table_name="workflow_audit_log")
    op.drop_table("workflow_audit_log")
    op.drop_table("approval_requests")
