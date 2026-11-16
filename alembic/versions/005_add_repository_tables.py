"""005 add repository tables."""

import sqlalchemy as sa
from alembic import op

revision = "005_add_repository_tables"
down_revision = "004_add_approval_audit_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repository_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("repo", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.Text(), server_default="main", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "owner", "repo"),
        sqlite_autoincrement=True,
    )


def downgrade() -> None:
    op.drop_table("repository_configs")
