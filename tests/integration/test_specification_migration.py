"""Migration 009 compatibility against isolated SQLite databases."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from devflow_core.config import get_settings
from tests.conftest import ROOT

WAVE1 = "008_add_workflow_execution_engine"
WAVE2 = "009_add_ai_specification_generation"
TABLES = {
    "specification_requests",
    "specification_approval_requests",
    "specification_versions",
    "specification_artifacts",
    "generation_attempts",
    "review_attempts",
    "review_findings",
}
INDEXES = {
    "idx_spec_req_status",
    "idx_spec_req_workflow_run_id",
    "idx_spec_ver_request_id",
    "idx_spec_ver_status",
    "idx_spec_ver_standalone_approval_id",
    "idx_spec_ver_bound_approval_id",
    "idx_spec_art_version_id",
    "idx_gen_attempt_request_id",
    "idx_gen_attempt_status",
    "idx_review_attempt_version_id",
    "idx_review_attempt_status",
    "idx_review_finding_version_id",
    "idx_review_finding_severity",
    "idx_spec_approval_version_id",
    "idx_spec_approval_expires_at",
}


@pytest.fixture
def migration(sqlite_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    return Config(str(ROOT / "alembic.ini"))


def objects(connection: sqlite3.Connection, kind: str) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,))
    }


@pytest.mark.integration
def test_wave2_009_preserves_legacy_data_and_downgrades_populated_schema(
    migration: Config,
    sqlite_path: Path,
) -> None:
    command.upgrade(migration, WAVE1)
    with closing(sqlite3.connect(sqlite_path)) as db, db:
        legacy_tables = objects(db, "table")
        legacy_indexes = objects(db, "index")
        db.execute(
            "INSERT INTO workflows(name,created_at,updated_at) "
            "VALUES ('Legacy',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        db.execute(
            "INSERT INTO workflow_runs(workflow_id,created_at,updated_at) "
            "VALUES (1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
    command.upgrade(migration, "head")
    command.check(migration)
    with closing(sqlite3.connect(sqlite_path)) as db, db:
        db.execute("PRAGMA foreign_keys=ON")
        assert objects(db, "table") == legacy_tables | TABLES
        added_indexes = objects(db, "index") - legacy_indexes
        assert {
            name for name in added_indexes if not name.startswith("sqlite_autoindex")
        } == INDEXES
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (WAVE2,)
        assert db.execute("SELECT id, name FROM workflows").fetchone() == (1, "Legacy")
        db.execute(
            "INSERT INTO specification_requests"
            "(title,description,workflow_run_id,content_hash,created_at,updated_at) "
            "VALUES ('Feature','Details',1,'hash',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        db.execute(
            "INSERT INTO specification_versions"
            "(specification_request_id,version_number,created_at,updated_at) "
            "VALUES (1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
        db.execute(
            "INSERT INTO specification_approval_requests"
            "(specification_version_id,parameters_hash,actor_id,expires_at) "
            "VALUES (1,'hash','actor',CURRENT_TIMESTAMP)"
        )
        db.execute("UPDATE specification_versions SET spec_standalone_approval_id=1")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE specification_versions SET status='invalid'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE specification_requests SET workflow_run_id=999")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO specification_versions"
                "(specification_request_id,version_number,created_at,updated_at) "
                "VALUES (1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    command.downgrade(migration, "-1")
    with closing(sqlite3.connect(sqlite_path)) as db:
        assert objects(db, "table") == legacy_tables
        assert objects(db, "index") == legacy_indexes
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (WAVE1,)
        assert db.execute("SELECT id, name FROM workflows").fetchone() == (1, "Legacy")
        assert db.execute("SELECT id, workflow_id FROM workflow_runs").fetchone() == (1, 1)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.integration
def test_wave2_009_roundtrip_from_001(migration: Config, sqlite_path: Path) -> None:
    initial = "001_create_initial_tables"
    command.upgrade(migration, initial)
    command.upgrade(migration, WAVE2)
    command.downgrade(migration, initial)
    with closing(sqlite3.connect(sqlite_path)) as db:
        assert not TABLES & objects(db, "table")
        assert not INDEXES & objects(db, "index")
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (initial,)
