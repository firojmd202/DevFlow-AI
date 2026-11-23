"""Add the seven Wave 2 specification tables."""

import sqlalchemy as sa
from alembic import op

revision = "009_add_ai_specification_generation"
down_revision = "008_add_workflow_execution_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite accepts the forward reference from standalone approvals to versions.
    op.create_table(
        "specification_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("business_goal", sa.Text()),
        sa.Column("functional_requirements", sa.Text()),
        sa.Column("nonfunctional_constraints", sa.Text()),
        sa.Column("acceptance_criteria", sa.Text()),
        sa.Column("repo_context", sa.Text()),
        sa.Column("clarifying_questions", sa.Text()),
        sa.Column(
            "workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL")
        ),
        sa.Column(
            "workflow_step_id",
            sa.Integer(),
            sa.ForeignKey("workflow_step_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','generating','generated','under_review',"
            " 'revision_required','ready_for_approval','approved','cancelled')"
        ),
        sa.Column("current_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text()),
        sa.Column("model_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "specification_approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specification_version_id",
            sa.Integer(),
            sa.ForeignKey("specification_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "operation",
            sa.Text(),
            server_default=sa.text("'approve_specification'"),
            nullable=False,
        ),
        sa.Column("parameters_hash", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("rejected_at", sa.DateTime()),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "specification_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specification_request_id",
            sa.Integer(),
            sa.ForeignKey("specification_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','generated','under_review','revision_required',"
            " 'ready_for_approval','approved','cancelled')"
        ),
        sa.Column("content_digest", sa.Text()),
        sa.Column("approved_at", sa.Text()),
        sa.Column("approved_by", sa.Text()),
        sa.Column(
            "spec_standalone_approval_id",
            sa.Integer(),
            sa.ForeignKey("specification_approval_requests.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "spec_bound_approval_id",
            sa.Integer(),
            sa.ForeignKey("approval_requests.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "supersedes_version_id",
            sa.Integer(),
            sa.ForeignKey("specification_versions.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("specification_request_id", "version_number"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "specification_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specification_version_id",
            sa.Integer(),
            sa.ForeignKey("specification_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.CheckConstraint("artifact_type IN ('requirements','design','tasks')"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("specification_version_id", "artifact_type"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "generation_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specification_request_id",
            sa.Integer(),
            sa.ForeignKey("specification_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "specification_version_id",
            sa.Integer(),
            sa.ForeignKey("specification_versions.id", ondelete="SET NULL"),
        ),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("prompt_hash", sa.Text(), nullable=False),
        sa.Column("context_truncated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "cancellation_requested", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed','cancelled')"),
        sa.Column("started_at", sa.Text()),
        sa.Column("completed_at", sa.Text()),
        sa.Column("token_usage_json", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "review_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specification_version_id",
            sa.Integer(),
            sa.ForeignKey("specification_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("artifact_hash", sa.Text(), nullable=False),
        sa.Column(
            "cancellation_requested", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed','cancelled')"),
        sa.Column("started_at", sa.Text()),
        sa.Column("completed_at", sa.Text()),
        sa.Column("finding_count_by_severity", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "review_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "review_attempt_id",
            sa.Integer(),
            sa.ForeignKey("review_attempts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "specification_version_id",
            sa.Integer(),
            sa.ForeignKey("specification_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.CheckConstraint("severity IN ('Critical','High','Medium','Low','Informational')"),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("finding_text", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.CheckConstraint("source IN ('deterministic','ai')"),
        sa.Column("acknowledged", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("acknowledged_by", sa.Text()),
        sa.Column("acknowledged_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("idx_spec_req_status", "specification_requests", ["status"])
    op.create_index("idx_spec_req_workflow_run_id", "specification_requests", ["workflow_run_id"])
    op.create_index(
        "idx_spec_ver_request_id", "specification_versions", ["specification_request_id"]
    )
    op.create_index("idx_spec_ver_status", "specification_versions", ["status"])
    op.create_index(
        "idx_spec_ver_standalone_approval_id",
        "specification_versions",
        ["spec_standalone_approval_id"],
    )
    op.create_index(
        "idx_spec_ver_bound_approval_id", "specification_versions", ["spec_bound_approval_id"]
    )
    op.create_index(
        "idx_spec_art_version_id", "specification_artifacts", ["specification_version_id"]
    )
    op.create_index(
        "idx_gen_attempt_request_id", "generation_attempts", ["specification_request_id"]
    )
    op.create_index("idx_gen_attempt_status", "generation_attempts", ["status"])
    op.create_index(
        "idx_review_attempt_version_id", "review_attempts", ["specification_version_id"]
    )
    op.create_index("idx_review_attempt_status", "review_attempts", ["status"])
    op.create_index(
        "idx_review_finding_version_id", "review_findings", ["specification_version_id"]
    )
    op.create_index("idx_review_finding_severity", "review_findings", ["severity"])
    op.create_index(
        "idx_spec_approval_version_id",
        "specification_approval_requests",
        ["specification_version_id"],
    )
    op.create_index(
        "idx_spec_approval_expires_at", "specification_approval_requests", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_spec_approval_expires_at", table_name="specification_approval_requests")
    op.drop_index("idx_spec_approval_version_id", table_name="specification_approval_requests")
    op.drop_index("idx_review_finding_severity", table_name="review_findings")
    op.drop_index("idx_review_finding_version_id", table_name="review_findings")
    op.drop_index("idx_review_attempt_status", table_name="review_attempts")
    op.drop_index("idx_review_attempt_version_id", table_name="review_attempts")
    op.drop_index("idx_gen_attempt_status", table_name="generation_attempts")
    op.drop_index("idx_gen_attempt_request_id", table_name="generation_attempts")
    op.drop_index("idx_spec_art_version_id", table_name="specification_artifacts")
    op.drop_index("idx_spec_ver_bound_approval_id", table_name="specification_versions")
    op.drop_index("idx_spec_ver_standalone_approval_id", table_name="specification_versions")
    op.drop_index("idx_spec_ver_status", table_name="specification_versions")
    op.drop_index("idx_spec_ver_request_id", table_name="specification_versions")
    op.drop_index("idx_spec_req_workflow_run_id", table_name="specification_requests")
    op.drop_index("idx_spec_req_status", table_name="specification_requests")
    op.drop_table("review_findings")
    op.drop_table("review_attempts")
    op.drop_table("generation_attempts")
    op.drop_table("specification_artifacts")
    # Break the circular reference while both parent tables still exist.
    op.execute("UPDATE specification_versions SET spec_standalone_approval_id = NULL")
    op.execute("DELETE FROM specification_approval_requests")
    op.drop_table("specification_versions")
    op.drop_table("specification_approval_requests")
    op.drop_table("specification_requests")
