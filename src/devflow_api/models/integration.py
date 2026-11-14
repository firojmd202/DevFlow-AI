"""Integration settings records."""

from sqlalchemy import Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from devflow_api.models.base import Base, TimestampMixin


class IntegrationConfig(TimestampMixin, Base):
    __tablename__ = "integration_configs"
    __table_args__ = (
        UniqueConstraint("integration_key", name="uq_integration_configs_integration_key"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_key: Mapped[str] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(default=False, server_default=false())
    execution_mode: Mapped[str] = mapped_column(Text)
    config_json: Mapped[str | None] = mapped_column(Text)
