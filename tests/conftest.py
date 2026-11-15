"""Offline, function-scoped test isolation."""

import logging
import os
import socket
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from devflow_api.models import Base
from devflow_core import logging as app_logging
from devflow_core.config import Settings, get_settings

ROOT = Path(__file__).resolve().parents[1]
MEMORY_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.chdir(tmp_path)
    fields = {name.lower() for name in Settings.model_fields}
    for key in list(os.environ):
        if key.lower() in fields:
            monkeypatch.delenv(key)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", MEMORY_URL)
    get_settings.cache_clear()
    snapshot = structlog.get_config()
    configured = structlog.is_configured()
    context = structlog.contextvars.get_contextvars()
    root_logger = logging.getLogger()
    handlers, level = root_logger.handlers[:], root_logger.level
    monkeypatch.setattr(app_logging, "_configured", False)

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("External network access is disabled in tests")

    native_connect = socket.socket.connect

    def connect(sock: socket.socket, address: tuple[str, int]) -> None:
        # Windows asyncio uses a loopback socket pair for its internal wakeup pipe.
        if address[0] not in {"127.0.0.1", "::1"}:
            no_network()
        native_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    structlog.contextvars.clear_contextvars()
    try:
        yield
    finally:
        get_settings.cache_clear()
        structlog.reset_defaults()
        if configured:
            structlog.configure(**snapshot)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(**context)
        root_logger.handlers[:] = handlers
        root_logger.setLevel(level)


@pytest.fixture
def test_settings() -> Settings:
    return get_settings()


@pytest.fixture
def synthetic_secret() -> str:
    return uuid4().hex


@pytest.fixture
def sqlite_path(tmp_path: Path) -> Path:
    return tmp_path / "test_devflow.db"


@pytest.fixture
async def async_engine() -> AsyncIterator[AsyncEngine]:
    from devflow_api.database import _configure_sqlite

    engine = create_async_engine(
        MEMORY_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine.sync_engine, "connect", _configure_sqlite)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_factory(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest.fixture
async def async_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture
def api_app(test_settings: Settings) -> FastAPI:
    from devflow_api.main import create_app

    return create_app(test_settings)


@pytest.fixture
async def test_client(
    api_app: FastAPI, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[httpx.AsyncClient]:
    from devflow_api.database import get_db

    async def get_test_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    api_app.dependency_overrides[get_db] = get_test_db
    transport = httpx.ASGITransport(app=api_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
