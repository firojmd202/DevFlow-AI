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
    command.downgrade(configuration, "-1")
    assert not TABLES & tables(sqlite_path)
    command.upgrade(configuration, "head")
    assert TABLES <= tables(sqlite_path)
    command.check(configuration)
    with closing(sqlite3.connect(sqlite_path)) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "001_create_initial_tables",
        )
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    sqlite_path.unlink()
    assert not sqlite_path.exists()
