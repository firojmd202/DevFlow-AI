"""Asynchronous SQLite engine and session lifecycle."""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

from devflow_core.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.DATABASE_URL, echo=settings.ENVIRONMENT == "development", hide_parameters=True
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(connection: DBAPIConnection, record: ConnectionPoolEntry) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.fetchone()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session and release it when the caller finishes or raises."""
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()
