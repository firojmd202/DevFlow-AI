import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from devflow_core.config import get_settings
from tests.conftest import ROOT

TABLES = {"projects", "learning_items", "integration_configs"}


def tables(db: Path) -> set[str]:
    with closing(sqlite3.connect(db)) as connection:
        return {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}


@pytest.mark.integration
def test_alembic_upgrade_downgrade_roundtrip(
    sqlite_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not sqlite_path.exists()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    configuration = Config(str(ROOT / "alembic.ini"))
    assert not tables(sqlite_path)
    command.upgrade(configuration, "head")
    assert TABLES <= tables(sqlite_path)
    command.downgrade(configuration, "base")
    assert not TABLES & tables(sqlite_path)
    command.upgrade(configuration, "head")
    assert TABLES <= tables(sqlite_path)
    command.check(configuration)
    with closing(sqlite3.connect(sqlite_path)) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "002_add_project_tags_column",
        )
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    sqlite_path.unlink()
    assert not sqlite_path.exists()


@pytest.mark.integration
def test_migration_002_round_trip(sqlite_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "001_create_initial_tables")
    with closing(sqlite3.connect(sqlite_path)) as connection, connection:
        connection.execute(
            "INSERT INTO projects (name, created_at, updated_at) "
            "VALUES ('Legacy', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
    command.upgrade(config, "002_add_project_tags_column")
    with closing(sqlite3.connect(sqlite_path)) as connection:
        assert connection.execute("SELECT tags_json FROM projects").fetchone() == ("[]",)
    command.downgrade(config, "-1")
    with closing(sqlite3.connect(sqlite_path)) as connection:
        columns = {column[1] for column in connection.execute("PRAGMA table_info(projects)")}
        assert "tags_json" not in columns
        assert columns


@pytest.mark.integration
def test_migration_002_upgrade_downgrade(
    sqlite_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "002_add_project_tags_column")
    assert TABLES <= tables(sqlite_path)
    command.downgrade(config, "base")
    assert not TABLES & tables(sqlite_path)
