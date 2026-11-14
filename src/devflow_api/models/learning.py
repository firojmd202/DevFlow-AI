"""Learning item records."""

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.models.base import Base, TimestampMixin


class LearningItem(TimestampMixin, Base):
    __tablename__ = "learning_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'done')", name="ck_learning_items_status"
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending", server_default="pending")
