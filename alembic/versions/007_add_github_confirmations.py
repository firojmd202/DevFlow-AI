"""Persist single-use GitHub confirmations and invalidate deleted run bindings."""

import sqlalchemy as sa
from alembic import op

revision = "007_add_github_confirmations"
down_revision = "006_add_mcp_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_confirmations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("repo_full_name", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("parameters_hash", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column(
            "workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL")
        ),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime()),
        sa.Column("status", sa.Text(), server_default="ISSUED", nullable=False),
        sa.CheckConstraint(
            "operation IN ('branch_create', 'pr_create')", name="ck_github_confirmations_operation"
        ),
        sa.CheckConstraint(
            "status IN ('ISSUED','EXPIRED','USED')", name="ck_github_confirmations_status"
        ),
    )
    op.create_index("idx_github_confirmations_expires", "github_confirmations", ["expires_at"])
    op.create_index("idx_github_confirmations_actor", "github_confirmations", ["actor_id"])
    op.execute("""
        CREATE TRIGGER trg_workflow_runs_before_delete_expire_github_confirmations
        BEFORE DELETE ON workflow_runs
        FOR EACH ROW
        BEGIN
            INSERT INTO workflow_audit_log
                (workflow_run_id, event_type, actor, payload_json, created_at)
            SELECT OLD.id, 'github_confirmation_expired', 'system',
                   json_object('confirmation_id', id, 'repo_full_name', repo_full_name,
                               'actor_id', actor_id, 'operation', operation),
                   strftime('%Y-%m-%d %H:%M:%f', 'now')
            FROM github_confirmations
            WHERE workflow_run_id = OLD.id AND status = 'ISSUED';
            UPDATE github_confirmations SET status = 'EXPIRED'
            WHERE workflow_run_id = OLD.id AND status = 'ISSUED';
        END;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_workflow_runs_before_delete_expire_github_confirmations")
    op.drop_index("idx_github_confirmations_actor", table_name="github_confirmations")
    op.drop_index("idx_github_confirmations_expires", table_name="github_confirmations")
    op.drop_table("github_confirmations")
