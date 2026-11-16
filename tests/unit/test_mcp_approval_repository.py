"""Migration 006 retention, foreign-key, and transaction regressions."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from devflow_api.adapters.exceptions import ConsumedError
from devflow_api.repositories.mcp_approval import MCPApprovalRepository
from devflow_core.config import get_settings
from tests.conftest import ROOT

pytestmark = pytest.mark.integration
APPROVAL_ID = str(UUID(int=1))
TRIGGER = "trg_workflow_runs_before_delete_expire_mcp_approvals"


@pytest.fixture
def migrated_mcp(sqlite_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "005_add_repository_tables")
    command.upgrade(config, "006_add_mcp_approvals")
    return config


@pytest.fixture
def database(sqlite_path: Path, migrated_mcp: Config) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(sqlite_path)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        assert db.execute("PRAGMA foreign_keys").fetchone() == (1,)
        db.execute(
            "INSERT INTO workflows (id, name, created_at, updated_at) "
            "VALUES (1, 'Example', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        db.execute(
            "INSERT INTO workflow_runs (id, workflow_id, created_at, updated_at) "
            "VALUES (1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        db.commit()
        yield db


def insert(db: sqlite3.Connection, status: str, run_id: int | None = 1) -> None:
    db.execute(
        "INSERT INTO mcp_approvals (id, mcp_server_id, tool_name, arguments_hash, actor_id, "
        "workflow_run_id, status, requested_at, expires_at) "
        "VALUES (?, 'server', 'write', 'hash', 'actor', ?, ?, CURRENT_TIMESTAMP, '2099-01-01')",
        (APPROVAL_ID, run_id, status),
    )
    db.commit()


def check(db: sqlite3.Connection, status: str, run_id: int | None = None) -> None:
    assert db.execute(
        "SELECT status, workflow_run_id FROM mcp_approvals WHERE id=?", (APPROVAL_ID,)
    ).fetchone() == (status, run_id)


def delete_run(db: sqlite3.Connection) -> None:
    db.execute("DELETE FROM workflow_runs WHERE id=1")


def test_workflow_run_deletion_expires_approved_mcp_approval(database: sqlite3.Connection) -> None:
    insert(database, "APPROVED")
    delete_run(database)
    check(database, "EXPIRED")


def test_workflow_run_deletion_allowed_after_approval_consumed(
    database: sqlite3.Connection,
) -> None:
    insert(database, "CONSUMED")
    delete_run(database)
    assert database.execute("SELECT count(*) FROM workflow_runs").fetchone() == (0,)


def test_workflow_run_deletion_expires_pending_mcp_approval(database: sqlite3.Connection) -> None:
    insert(database, "PENDING")
    delete_run(database)
    check(database, "EXPIRED")


def test_workflow_run_deletion_preserves_consumed_approval(database: sqlite3.Connection) -> None:
    insert(database, "CONSUMED")
    delete_run(database)
    check(database, "CONSUMED")


def test_workflow_run_deletion_preserves_rejected_approval(database: sqlite3.Connection) -> None:
    insert(database, "REJECTED")
    delete_run(database)
    check(database, "REJECTED")


@pytest.mark.parametrize(
    "before,after",
    [
        ("PENDING", "EXPIRED"),
        ("APPROVED", "EXPIRED"),
        ("CONSUMED", "CONSUMED"),
        ("REJECTED", "REJECTED"),
        ("EXPIRED", "EXPIRED"),
    ],
)
def test_cascaded_deletion_handles_mcp_approvals(
    database: sqlite3.Connection, before: str, after: str
) -> None:
    insert(database, before)
    database.execute("DELETE FROM workflows WHERE id=1")
    assert database.execute("SELECT count(*) FROM workflow_runs").fetchone() == (0,)
    check(database, after)


@pytest.mark.parametrize("status", ["PENDING", "APPROVED"])
def test_trigger_rollback_restores_approval(database: sqlite3.Connection, status: str) -> None:
    insert(database, status)
    delete_run(database)
    check(database, "EXPIRED")
    database.rollback()
    check(database, status, 1)


@pytest.mark.parametrize("status", ["PENDING", "APPROVED"])
def test_originally_unbound_approval_is_unaffected(
    database: sqlite3.Connection, status: str
) -> None:
    insert(database, status, None)
    delete_run(database)
    check(database, status)


def test_migration_006_round_trip(migrated_mcp: Config, sqlite_path: Path) -> None:
    for expected in (True, False, True):
        if expected:
            command.upgrade(migrated_mcp, "006_add_mcp_approvals")
        else:
            command.downgrade(migrated_mcp, "-1")
        with closing(sqlite3.connect(sqlite_path)) as db:
            objects = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
            assert ("mcp_approvals" in objects) is expected
            assert (TRIGGER in objects) is expected
    command.upgrade(migrated_mcp, "head")
    command.check(migrated_mcp)


async def test_orphaned_pending_approval_cannot_be_promoted(
    database: sqlite3.Connection, sqlite_path: Path
) -> None:
    insert(database, "PENDING")
    delete_run(database)
    check(database, "EXPIRED")
    # Exercise the conditional resolution contract without adding a promotion API.
    cursor = database.execute(
        "UPDATE mcp_approvals SET status='APPROVED' WHERE id=? AND status='PENDING'",
        (APPROVAL_ID,),
    )
    assert cursor.rowcount == 0
    await _assert_expired_cannot_be_consumed(database, sqlite_path)


async def _assert_expired_cannot_be_consumed(
    database: sqlite3.Connection, sqlite_path: Path
) -> None:
    database.commit()
    engine = create_async_engine(f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    try:
        async with AsyncSession(engine) as session:
            repo = MCPApprovalRepository(session)
            with pytest.raises(ConsumedError):
                await repo.consume_atomic(
                    UUID(APPROVAL_ID), "actor", "server", "write", "hash", None, datetime.now(UTC)
                )
    finally:
        await engine.dispose()
    check(database, "EXPIRED")


async def test_null_to_null_match_rejected_for_originally_bound_approval(
    database: sqlite3.Connection, sqlite_path: Path
) -> None:
    insert(database, "APPROVED")
    delete_run(database)
    await _assert_expired_cannot_be_consumed(database, sqlite_path)


async def test_expired_approval_after_deletion_cannot_be_consumed(
    database: sqlite3.Connection, sqlite_path: Path
) -> None:
    insert(database, "APPROVED")
    delete_run(database)
    await _assert_expired_cannot_be_consumed(database, sqlite_path)
