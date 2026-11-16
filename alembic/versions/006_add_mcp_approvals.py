"""Create MCP approvals and invalidate authorized bindings before run deletion."""

import sqlalchemy as sa
from alembic import op

revision = "006_add_mcp_approvals"
down_revision = "005_add_repository_tables"
branch_labels = None
depends_on = None

_TRIGGER = "trg_workflow_runs_before_delete_expire_mcp_approvals"


def upgrade() -> None:
    op.create_table(
        "mcp_approvals",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("mcp_server_id", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("arguments_hash", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column(
            "workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL")
        ),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED')",
            name="ck_mcp_approvals_status",
        ),
    )
    op.create_index("idx_mcp_approvals_server", "mcp_approvals", ["mcp_server_id"])
    op.create_index("idx_mcp_approvals_status", "mcp_approvals", ["status"])
    op.create_index("idx_mcp_approvals_expires", "mcp_approvals", ["expires_at"])
    op.execute("""
        CREATE TRIGGER trg_workflow_runs_before_delete_expire_mcp_approvals
        BEFORE DELETE ON workflow_runs
        FOR EACH ROW
        BEGIN
            UPDATE mcp_approvals
               SET status = 'EXPIRED'
             WHERE workflow_run_id = OLD.id
               AND status IN ('PENDING', 'APPROVED');
        END;
    """)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER}")
    op.drop_index("idx_mcp_approvals_expires", table_name="mcp_approvals")
    op.drop_index("idx_mcp_approvals_status", table_name="mcp_approvals")
    op.drop_index("idx_mcp_approvals_server", table_name="mcp_approvals")
    op.drop_table("mcp_approvals")
