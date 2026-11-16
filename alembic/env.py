"""Run Alembic with the application metadata and configured SQLite path."""

from alembic import context
from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry

from devflow_api.models import Base
from devflow_core.config import get_settings

sync_url = get_settings().DATABASE_URL.replace("+aiosqlite", "")
target_metadata = Base.metadata


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    # Migration 005 owns this table until Wave 5 registers its ORM model.
    return not (
        type_ == "table" and name == "repository_configs" and name not in target_metadata.tables
    )


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(sync_url, poolclass=pool.NullPool, hide_parameters=True)

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection: DBAPIConnection, record: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.fetchone()
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_server_default=True,
                include_name=include_name,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
