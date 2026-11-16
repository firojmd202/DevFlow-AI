"""Registered project repositories."""

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.models.base import Base, TimestampMixin


class RepositoryConfig(TimestampMixin, Base):
    __tablename__ = "repository_configs"
    __table_args__ = (
        UniqueConstraint("project_id", "owner", "repo"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    owner: Mapped[str] = mapped_column(Text)
    repo: Mapped[str] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(Text, server_default="main")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}".lower()
