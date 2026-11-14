from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Column, MetaData, Table, insert, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from devflow_api.models import Base, IntegrationConfig, LearningItem, Project
from devflow_api.models.base import UTCDateTime
from tests.conftest import ROOT


async def test_initial_models(async_db_session: AsyncSession, tmp_path: Path) -> None:
    assert set(Base.metadata.tables) == {"projects", "learning_items", "integration_configs"}
    assert all(
        list(table.primary_key.columns.keys()) == ["id"] for table in Base.metadata.tables.values()
    )
    assert all(not table.foreign_keys for table in Base.metadata.tables.values())
    session = async_db_session
    session.add_all(
        [
            Project(name="Example"),
            LearningItem(title="Example"),
            IntegrationConfig(integration_key="codex", execution_mode="cli_handoff"),
        ]
    )
    await session.commit()
    session.expunge_all()
    project = (await session.scalars(select(Project))).one()
    learning = (await session.scalars(select(LearningItem))).one()
    integration = (await session.scalars(select(IntegrationConfig))).one()
    assert project.status == "active" and learning.status == "pending"
    assert integration.is_enabled is False and integration.execution_mode == "cli_handoff"
    for row in (project, learning, integration):
        assert row.created_at.tzinfo is UTC and row.updated_at.tzinfo is UTC
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param([Project(name="Example", status="invalid")], id="project-status"),
        pytest.param([LearningItem(title="Example", status="invalid")], id="learning-status"),
        pytest.param([Project()], id="missing-name"),
        pytest.param(
            [
                IntegrationConfig(integration_key="duplicate", execution_mode="unknown"),
                IntegrationConfig(integration_key="duplicate", execution_mode="unknown"),
            ],
            id="unique-key",
        ),
    ],
)
async def test_constraints(async_db_session: AsyncSession, rows: list[Base]) -> None:
    async_db_session.add_all(rows)
    with pytest.raises(IntegrityError):
        await async_db_session.flush()


@pytest.mark.parametrize("offset", [0, 330])
async def test_roundtrip(offset: int, async_db_session: AsyncSession) -> None:
    stamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(minutes=offset)))
    session = async_db_session
    session.add(Project(name="Round trip", created_at=stamp))
    await session.commit()
    session.expunge_all()
    loaded = (await session.scalars(select(Project))).one().created_at
    assert loaded == stamp.astimezone(UTC) and loaded.tzinfo is UTC


async def test_naive_timestamp_rejected(async_db_session: AsyncSession) -> None:
    async_db_session.add(Project(name="Naive", created_at=datetime(2026, 1, 2)))
    with pytest.raises(StatementError) as error:
        await async_db_session.flush()
    assert isinstance(error.value.orig, ValueError)
    assert "timezone-aware" in str(error.value.orig)


async def test_null_and_invalid_timestamp(async_engine: AsyncEngine) -> None:
    metadata = MetaData()
    probe = Table("probe", metadata, Column("stamp", UTCDateTime, nullable=True))
    async with async_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
        await conn.execute(insert(probe).values(stamp=None))
        assert (await conn.scalars(select(probe.c.stamp))).one() is None
        await conn.execute(text("INSERT INTO probe VALUES ('invalid')"))
        with pytest.raises(ValueError):
            (await conn.scalars(select(probe.c.stamp))).all()
    dialect = async_engine.dialect
    timestamp_type = UTCDateTime()
    assert timestamp_type.process_result_value("2026-01-02T03:04:05+05:30", dialect) == datetime(
        2026, 1, 1, 21, 34, 5, tzinfo=UTC
    )
    with pytest.raises(ValueError, match="Invalid persisted"):
        timestamp_type.process_result_value("invalid", dialect)


async def test_session_cleanup_and_memory_wal(monkeypatch: pytest.MonkeyPatch) -> None:
    from devflow_api import database

    engine = create_memory_engine()
    monkeypatch.setattr(database, "AsyncSessionLocal", async_sessionmaker(engine))
    try:
        async for session in database.get_db():
            assert await session.scalar(text("PRAGMA journal_mode")) == "memory"
        assert not session.in_transaction()
        dependency = database.get_db()
        failing = await anext(dependency)
        await failing.execute(text("SELECT 1"))
        with pytest.raises(RuntimeError, match="handler"):
            await dependency.athrow(RuntimeError("handler"))
        assert not failing.in_transaction()
    finally:
        await engine.dispose()


def create_memory_engine() -> AsyncEngine:
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool

    from devflow_api import database

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine.sync_engine, "connect", database._configure_sqlite)
    return engine


def test_source_uses_aware_clock() -> None:
    assert all(
        "datetime.utcnow(" not in path.read_text(encoding="utf-8")
        for path in (ROOT / "src").rglob("*.py")
    )
