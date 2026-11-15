"""Add persistent project tags."""

import sqlalchemy as sa
from alembic import op

revision = "002_add_project_tags_column"
down_revision = "001_create_initial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects", sa.Column("tags_json", sa.Text(), server_default="[]", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("projects", "tags_json")
