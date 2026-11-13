# DevFlow AI — Phase 0: Foundation & Architecture Requirements

**Version:** 1.1.1  
**Status:** Draft — Awaiting Approval  
**Scope:** Phase 0 — Foundation & Architecture  
**Last Updated:** 2026-11-14  
**Supersedes:** v1.1.0

---

## Overview

DevFlow AI is a personal AI development and learning orchestrator. It is a production-quality, local-first Python application that coordinates AI-assisted project planning, learning, specifications, design, coding, testing, documentation, and integrations. Phase 0 establishes the entire technical foundation upon which all subsequent phases are built. No actual AI execution occurs in Phase 0; this phase is exclusively concerned with structure, contracts, infrastructure, and tooling.

### Global Constraints (apply to all requirements below)

- The application MUST remain local-first with free core functionality.
- The codebase MUST NOT contain Android, React, TypeScript, or Vite artefacts.
- No actual AI model execution or live AI API calls SHALL occur during Phase 0.
- No paid API dependency SHALL be introduced in Phase 0.
- Secrets (API keys, tokens, passwords) MUST NOT appear in source control at any time.
- All development services MUST bind exclusively to `127.0.0.1` on the host interface (containers may bind internally to `0.0.0.0` for intra-container networking, but host port mappings MUST specify `127.0.0.1`).
- Architecture boundaries between UI, API, domain services, adapters, and storage MUST be maintained.
- The existing README.md MUST be preserved and may only be extended.
- Every task MUST be small enough to be independently testable.

---

## Area 1 — Repository and Project Standards

### REQ-1.1
WHEN a developer clones the repository,  
THEN the root directory MUST contain a `.gitignore` that excludes `.env`, `*.pyc`, `__pycache__/`, `.venv/`, `dist/`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, and SQLite database files (`*.db`, `*.sqlite3`).

**Acceptance Criteria:**  
1.1.1 — `git status` after a fresh clone shows no untracked secrets or build artefacts.  
1.1.2 — A `.env` file created locally does not appear in `git status`.  
1.1.3 — `*.pyc` and `__pycache__/` entries are absent from `git status` after a test run.

### REQ-1.2
WHEN a developer opens the repository root,  
THEN a `pyproject.toml` MUST be present that defines: project name (`devflow-ai`), version (`0.1.0`), minimum Python version (`>=3.12`), and tool configurations for Ruff, MyPy, Pytest, and Coverage.

**Acceptance Criteria:**  
1.2.1 — `python -m build --no-isolation` succeeds from the repository root.  
1.2.2 — `ruff check .` exits with code 0 on a clean codebase.  
1.2.3 — `mypy --strict src/` exits with code 0 on stub source files.  
1.2.4 — `pytest --co -q` (collect-only) exits with code 0 when at least one test file exists; this criterion is satisfied by the testing wave (Tasks 15–19), not by Task 1 alone.

> **v1.1.1 note (FIX 3):** REQ-1.2.4 previously read "`pytest --collect-only` discovers at least one test without error." Exit code 5 (no tests collected) is not success. This criterion now requires at least one discoverable test, which is first satisfied when Task 15 creates the initial test files. Task 1 validates pytest configuration using configuration inspection only — see Task 1 acceptance criteria.

### REQ-1.3
WHERE the repository root exists,  
THEN an `.editorconfig` file MUST be present specifying: UTF-8 charset, LF line endings, 4-space indentation for Python, 2-space indentation for YAML/TOML/JSON, and final newline insertion.

**Acceptance Criteria:**  
1.3.1 — `.editorconfig` is parseable by the `editorconfig` Python package without errors.  
1.3.2 — Configured indentation rules match the Ruff `indent-width` setting.

### REQ-1.4
WHEN a contributor opens the repository,  
THEN a `CONTRIBUTING.md` MUST exist describing: branch naming convention (`feature/`, `fix/`, `chore/`), commit message format (Conventional Commits), PR checklist (lint, type-check, tests), how to run the full local dev setup on both Linux/macOS and Windows, and how to add a new integration adapter.

**Acceptance Criteria:**  
1.4.1 — `CONTRIBUTING.md` contains all five described sections.  
1.4.2 — The PR checklist references the exact CLI commands used in CI for Linux/macOS (`make`) and Windows (PowerShell).

---

## Area 2 — Python Environment Configuration

### REQ-2.1
WHEN a developer sets up the project,  
THEN a `requirements/` directory MUST contain at minimum: `base.txt` (runtime dependencies), `dev.txt` (development tools, includes `-r base.txt`), and `test.txt` (testing tools, includes `-r dev.txt`).

**Acceptance Criteria:**  
2.1.1 — `pip install -r requirements/test.txt` completes without dependency conflicts in a fresh Python 3.12 virtual environment.  
2.1.2 — Every package in `requirements/` files specifies an exact version pin (`==`).

### REQ-2.2
WHEN a developer runs the project setup on Linux or macOS,  
THEN a `Makefile` MUST provide at minimum the following targets: `install`, `dev`, `test`, `lint`, `typecheck`, `format`, `migrate`, `audit`, `docs`, `clean`, `help`.

**Acceptance Criteria:**  
2.2.1 — `make install` creates a `.venv` and installs all base dependencies.  
2.2.2 — `make test` runs the full test suite and returns a non-zero exit code on failure.  
2.2.3 — `make lint` runs Ruff and returns a non-zero exit code on violations.  
2.2.4 — `make typecheck` runs MyPy and returns a non-zero exit code on type errors.  
2.2.5 — `make help` lists all targets with brief descriptions.

### REQ-2.3
WHEN a developer runs the project setup on Windows (PowerShell),  
THEN a `scripts/dev.ps1` PowerShell script MUST exist providing equivalent commands for: environment creation, dependency installation, running tests, linting, type-checking, running migrations, and starting Docker Compose.

**Acceptance Criteria:**  
2.3.1 — `scripts/dev.ps1 -Task install` creates `.venv` and installs base dependencies in a fresh PowerShell session.  
2.3.2 — `scripts/dev.ps1 -Task test` runs the full pytest suite on Windows.  
2.3.3 — `scripts/dev.ps1 -Task lint` runs Ruff on Windows.  
2.3.4 — `scripts/dev.ps1 -Task help` prints all available tasks.  
2.3.5 — The script does not use Linux-specific shell syntax (backticks, `&&`, `||` without PowerShell equivalents).

### REQ-2.4
IF a developer uses VS Code or a compatible IDE,  
THEN a `.vscode/settings.json` MUST be present enabling: Python interpreter from `.venv`, format-on-save using Ruff, and MyPy as the type-checker.

**Acceptance Criteria:**  
2.4.1 — `.vscode/settings.json` contains `python.defaultInterpreterPath`, `editor.formatOnSave`, and `python.analysis.typeCheckingMode` keys.

---

## Area 3 — Streamlit Multipage Application Foundation

### REQ-3.1
WHEN the Streamlit application is started,  
THEN it MUST launch from `src/devflow_ui/app.py` as the entry point and display a named application title.

**Acceptance Criteria:**  
3.1.1 — `streamlit run src/devflow_ui/app.py` starts without error.  
3.1.2 — The browser title contains "DevFlow AI".  
3.1.3 — `AppTest.from_file("src/devflow_ui/app.py").run()` completes without exception.

### REQ-3.2
WHEN the Streamlit application loads,  
THEN it MUST use `st.Page` / `st.navigation` (Streamlit ≥ 1.36 programmatic navigation) as the single primary navigation strategy, declaring all ten pages in `app.py` and placing page modules under `src/devflow_ui/pages/`. The pages MUST be: Dashboard, Projects, Learning, Specifications, Design, Coding, Testing, Documentation, Integrations, Settings.

**Acceptance Criteria:**  
3.2.1 — `app.py` contains a single `st.navigation(...)` call listing all ten `st.Page` entries.  
3.2.2 — Each of the ten page files exists under `src/devflow_ui/pages/` with a `_` prefix-number naming convention.  
3.2.3 — `AppTest.from_file` can test each page file independently without importing `app.py`.  
3.2.4 — Navigating to each page does not raise an unhandled exception.  
3.2.5 — Each page renders a heading that matches its page name.

### REQ-3.3
WHILE the Streamlit application is running in Phase 0,  
THEN all pages that will show AI-driven or dynamic content in future phases MUST display a clearly labelled "Phase 0 — not yet implemented" placeholder widget. No fabricated metrics, integration status badges, or simulated project data MUST appear.

**Acceptance Criteria:**  
3.3.1 — No HTTP call to any external AI endpoint is made during `AppTest` execution.  
3.3.2 — Every placeholder widget contains the string "Phase 0" or "not yet implemented".  
3.3.3 — The Dashboard page MUST NOT display hard-coded project counts, AI status indicators, or simulated charts.

### REQ-3.4
WHERE the Streamlit application communicates with the backend,  
THEN all backend calls MUST go through a typed `APIClient` class that wraps `httpx` and targets the FastAPI service at a configurable base URL.

**Acceptance Criteria:**  
3.4.1 — `APIClient` is importable from `src/devflow_ui/api_client.py`.  
3.4.2 — `APIClient.__init__` accepts a `base_url: str` parameter.  
3.4.3 — All public methods on `APIClient` carry complete type annotations validated by MyPy.  
3.4.4 — When the backend is unavailable, `APIClient` methods return `None` and log a warning; they MUST NOT raise to the calling page.

---

## Area 4 — FastAPI Backend Foundation

### REQ-4.1
WHEN the FastAPI application is started,  
THEN it MUST launch from `src/devflow_api/main.py` via a `create_app()` factory function and expose OpenAPI documentation at `/docs` and `/redoc`.

**Acceptance Criteria:**  
4.1.1 — `uvicorn devflow_api.main:app --reload` starts without error from an editable install.  
4.1.2 — `GET /docs` returns HTTP 200.  
4.1.3 — `GET /redoc` returns HTTP 200.  
4.1.4 — `GET /openapi.json` returns a valid OpenAPI 3.x document.

### REQ-4.2
WHEN the FastAPI application receives a request,  
THEN a `GET /health` endpoint MUST return HTTP 200 with a JSON body `{"status": "ok", "version": "<current version>"}`.

**Acceptance Criteria:**  
4.2.1 — `GET /health` returns HTTP 200 in a `TestClient` unit test.  
4.2.2 — The response body is a valid JSON object containing `status` and `version` keys.  
4.2.3 — The `version` value matches the version declared in `pyproject.toml`.

### REQ-4.3
WHEN the FastAPI application is initialized,  
THEN all API routers MUST be registered under a versioned prefix (`/api/v1/`) and organized by domain into separate router modules.

**Acceptance Criteria:**  
4.3.1 — All routes visible in `/openapi.json` (except `/health`) are prefixed with `/api/v1/`.  
4.3.2 — At least one router module exists per Phase 0 domain (projects, learning, integrations).  
4.3.3 — Each router module is in its own file under `src/devflow_api/routers/`.

### REQ-4.4
IF the FastAPI application encounters an unhandled exception during request processing,  
THEN it MUST return a structured JSON error response with `{"error": "<message>", "code": "<error_code>"}` and an appropriate HTTP status code, and MUST log the exception with a stack trace.

**Acceptance Criteria:**  
4.4.1 — A deliberate `500` trigger endpoint returns `{"error": ..., "code": ...}` rather than a raw traceback.  
4.4.2 — The exception is recorded in the structured log output.  
4.4.3 — The response `Content-Type` is `application/json`.

### REQ-4.5
WHEN the FastAPI application starts,  
THEN CORS MUST be configured to allow only origins listed in the `ALLOWED_ORIGINS` configuration variable, defaulting to `["http://localhost:8501"]`.

**Acceptance Criteria:**  
4.5.1 — A CORS preflight request from `http://localhost:8501` succeeds.  
4.5.2 — A CORS preflight request from an unlisted origin is rejected.

---

## Area 5 — SQLite and Alembic

### REQ-5.1
WHEN the application initialises its database,  
THEN SQLAlchemy 2 declarative base models MUST be defined in `src/devflow_api/models/` with one module per domain entity group, and all timestamp columns MUST use a custom `UTCDateTime` TypeDecorator that guarantees timezone-aware UTC round-trips through SQLite.

**Acceptance Criteria:**  
5.1.1 — All model modules are importable without error.  
5.1.2 — MyPy reports no type errors on model files.  
5.1.3 — Every model class has a `__tablename__` attribute and at least a primary key column.  
5.1.4 — `created_at` and `updated_at` columns use the `UTCDateTime` TypeDecorator and default to `datetime.now(UTC)`.  
5.1.5 — Reading a persisted `created_at` value from SQLite returns a `datetime` object with `tzinfo` set to UTC (not `None`).

> **v1.1.1 note (FIX 2):** `DateTime(timezone=True)` alone does not guarantee timezone-aware Python values when SQLite is the backend. The `UTCDateTime` TypeDecorator defined in REQ-5.6 MUST be used for all timestamp columns.

### REQ-5.2
WHEN the database layer is used,  
THEN a SQLAlchemy async session factory MUST be provided via a FastAPI dependency (`get_db`) that yields an `AsyncSession` per request and explicitly closes it in a `finally` block after the response completes.

**Acceptance Criteria:**  
5.2.1 — `get_db` is importable from `src/devflow_api/database.py`.  
5.2.2 — A test using `get_db` with an in-memory SQLite database completes without connection leak.  
5.2.3 — The session is closed even if the request handler raises an exception (verified by asserting `session.is_active == False` or by asserting no "connection was not closed" warning appears in test output).

### REQ-5.3
WHEN in-memory SQLite is used in tests,  
THEN the async engine MUST be created with `StaticPool` and `connect_args={"check_same_thread": False}` to allow the same connection to be reused across the async context, preventing "Cannot operate on a closed database" errors.

**Acceptance Criteria:**  
5.3.1 — All database-dependent unit tests pass reliably (no intermittent "closed database" failures).  
5.3.2 — `pytest -x tests/unit/test_models.py` runs to completion without SQLite threading errors.

### REQ-5.4
WHEN database schema changes are made,  
THEN Alembic MUST be configured with an `alembic/` directory at the repository root, `alembic.ini` at the root, and an `env.py` that reads the database URL from the application configuration rather than hardcoding it.

**Acceptance Criteria:**  
5.4.1 — `alembic current` executes without error against the configured database.  
5.4.2 — `alembic upgrade head` applies all migrations in a fresh environment.  
5.4.3 — `alembic downgrade -1` reverses the most recent migration without data loss on empty tables.  
5.4.4 — The database URL in `alembic.ini` MUST NOT be a hardcoded connection string containing credentials.  
5.4.5 — Alembic migrations MUST NOT run against the developer's real `devflow.db` during automated tests (tests use in-memory or a `tmp_path`-scoped file).

### REQ-5.5
IF a migration generates a new revision,  
THEN the generated migration file MUST include both `upgrade()` and `downgrade()` functions, and both MUST be non-empty (not just `pass`).

**Acceptance Criteria:**  
5.5.1 — The initial `create_tables` migration contains table creation in `upgrade()`.  
5.5.2 — The initial migration contains `drop_table` calls in `downgrade()`.

### REQ-5.6
WHEN timezone-aware datetime values are stored in or retrieved from SQLite,  
THEN a reusable `UTCDateTime` SQLAlchemy TypeDecorator MUST be used in place of `DateTime(timezone=True)` to guarantee correct UTC round-trips.

**Acceptance Criteria:**  
5.6.1 — `UTCDateTime` is defined in `src/devflow_api/models/base.py` as a `TypeDecorator` subclass with `impl = DateTime`.  
5.6.2 — `process_bind_param` converts timezone-aware inputs to UTC before storage and raises `ValueError` for naive datetime inputs (naive datetimes MUST NOT be silently accepted).  
5.6.3 — `process_result_value` returns a `datetime` with `tzinfo=UTC` when reading from SQLite; it returns `None` unchanged if the stored value is `NULL`.  
5.6.4 — A unit test inserts a datetime with a non-UTC timezone (e.g., `America/New_York`) and verifies the round-tripped value equals the original instant expressed in UTC.  
5.6.5 — A unit test inserts a naive datetime and verifies that `ValueError` is raised at bind time.  
5.6.6 — `datetime.now(UTC)` MUST be used for all default timestamp values; `datetime.utcnow()` MUST NOT appear anywhere in the codebase.  
5.6.7 — Alembic migration DDL for timestamp columns uses `DATETIME` (the underlying SQLite type); the TypeDecorator handles Python-side conversion independently of the DDL type.

> **v1.1.1 note (FIX 2):** This requirement is new in v1.1.1. It documents the naive-datetime rejection policy: naive datetimes raise `ValueError` rather than being silently coerced. Any callers that previously passed naive datetimes must be updated to pass timezone-aware UTC values.

---

## Area 6 — Typed Integration Adapter Contracts

### REQ-6.1
WHEN integration adapters are defined,  
THEN each integration MUST be classified by its **execution mode** — one of: `automated_api` (a real programmatic API exists), `cli_handoff` (invoked via CLI subprocess), `manual_handoff` (user-driven workflow with no programmatic control), or `unknown` (classification deferred to later phases). This classification MUST be recorded in typed `IntegrationCapability` metadata.

**Acceptance Criteria:**  
6.1.1 — An `IntegrationCapability` Pydantic v2 model is defined in `src/devflow_api/adapters/capability.py`.  
6.1.2 — `IntegrationCapability` contains at minimum: `name: str`, `execution_mode: ExecutionMode` (enum), `supported_actions: list[str]`, `auth_required: bool`, `auth_type: str | None`, `available_in_phase_0: bool`.  
6.1.3 — Every integration has a `capability` class attribute on its Protocol returning an `IntegrationCapability` instance.

### REQ-6.2
WHEN integration adapters are classified,  
THEN the following mode assignments MUST apply, with Phase 0 protocols reflecting only the capabilities that are actually available through a free, programmatic channel:

| Integration | Execution Mode | Rationale |
|---|---|---|
| ChatGPT | `automated_api` | Official REST API (OpenAI) — requires paid key |
| Codex | `cli_handoff` | Codex CLI is the preferred local integration; no OpenAI API key required for CLI usage. An optional API-based adapter may be added in future phases. Authentication and plan requirements vary by CLI version and must be documented. |
| Kiro | `manual_handoff` | No public programmatic API; user drives Kiro IDE |
| Claude | `automated_api` | Anthropic REST API — requires paid key |
| Antigravity | `unknown` | No public API documented; deferred |
| Google Stitch | `unknown` | Pre-release / no public API; deferred |
| Figma | `automated_api` | Official REST API (free tier available) |
| NotebookLM | `manual_handoff` | No public API; personal notebook workflows are user-driven |
| GitHub | `automated_api` | REST / GraphQL API (free tier) |
| Ollama | `automated_api` | Local REST API (free, no key required) |
| MCP Servers | `automated_api` | Model Context Protocol — programmatic |

**Acceptance Criteria:**  
6.2.1 — Each integration's `IntegrationCapability.execution_mode` matches the table above.  
6.2.2 — Integrations with `execution_mode == manual_handoff` MUST NOT define async action methods that imply direct programmatic control (they may define `get_instructions() -> str` only).  
6.2.3 — Integrations with `execution_mode == unknown` MUST NOT define any action methods beyond `health_check`.  
6.2.4 — The Codex integration's `execution_mode` is `cli_handoff`, not `automated_api`.  
6.2.5 — No OpenAI API key is required for the Codex CLI stub in Phase 0.

> **v1.1.1 note (FIX 1):** Codex was previously classified as `automated_api`. It is now `cli_handoff` to reflect the preferred local-first Codex CLI integration. CLI usage is not guaranteed to be free or unlimited; authentication and plan requirements are documented in the Codex adapter notes. An API-based adapter remains an option for future phases but is not the default.

### REQ-6.3
WHEN integration adapters are defined,  
THEN a typed Python `Protocol` MUST exist for each of the eleven integrations in REQ-6.2. Protocols for `manual_handoff` and `unknown` integrations MUST be explicitly scoped to reflect their limitations.

**Acceptance Criteria:**  
6.3.1 — Each protocol is defined in `src/devflow_api/adapters/protocols/` with one file per integration.  
6.3.2 — All protocols pass `mypy --strict` without errors.  
6.3.3 — `manual_handoff` protocols expose only `health_check` and `get_instructions(self) -> str`.  
6.3.4 — `unknown` protocols expose only `health_check`.

### REQ-6.4
WHEN an integration adapter is implemented,  
THEN it MUST implement the corresponding `Protocol` and be registered in an adapter registry accessible via `src/devflow_api/adapters/registry.py`.

**Acceptance Criteria:**  
6.4.1 — The adapter registry exposes a `get(name: str) -> BaseAdapterProtocol` method.  
6.4.2 — Requesting an unregistered adapter name raises a typed `AdapterNotFoundError`.  
6.4.3 — Phase 0 stub adapters exist for all 11 integrations.

### REQ-6.5
WHILE Phase 0 is active,  
THEN all integration adapters MUST be stub implementations that return typed placeholder responses and MUST NOT make any network calls or subprocess calls to external services. Stub responses MUST carry a `stub: bool = True` marker field so callers can detect Phase 0 mode.

**Acceptance Criteria:**  
6.5.1 — Running the full test suite with network access blocked produces zero failures attributable to adapter network calls.  
6.5.2 — Each stub adapter `health_check()` returns `{"status": "stub", "integration": "<name>", "execution_mode": "<mode>"}`.  
6.5.3 — No stub module imports `httpx`, `requests`, `subprocess`, or any network/process library.

### REQ-6.6
IF an integration requires an API key or token for live calls,  
THEN the adapter MUST read that credential exclusively from the application configuration layer, and MUST raise a `MissingCredentialError` if the credential is absent when a live call is attempted. Stub adapters in Phase 0 MUST NOT raise `MissingCredentialError`.

**Acceptance Criteria:**  
6.6.1 — No adapter module contains a hardcoded credential string.  
6.6.2 — `MissingCredentialError` is defined in `src/devflow_api/adapters/exceptions.py`.  
6.6.3 — A unit test demonstrates that stub adapters do NOT raise `MissingCredentialError`.

### REQ-6.7
WHEN the Codex CLI adapter is defined,  
THEN the protocol and stub MUST reflect `cli_handoff` semantics and enforce the following safety constraints, even though no real Codex execution occurs in Phase 0:

**Acceptance Criteria:**  
6.7.1 — The Codex protocol defines `request_code_generation(description: str, language: str, workspace_path: str) -> CodexCLIRequest` returning a request object for user review, not a live execution result.  
6.7.2 — The Codex protocol defines `execute_approved_request(request: CodexCLIRequest) -> CodexCLIResult` with a docstring stating that execution requires explicit user approval and is restricted to authorized workspace paths.  
6.7.3 — `CodexCLIRequest` includes fields: `description: str`, `language: str`, `workspace_path: str`, `approved: bool` (default `False`), `timeout_seconds: int` (default `30`).  
6.7.4 — `CodexCLIResult` includes fields: `stdout: str`, `stderr: str`, `exit_code: int`, `timed_out: bool`, `stub: bool`.  
6.7.5 — The Codex stub `IntegrationCapability.notes` documents that CLI authentication and plan requirements vary; free tier availability is not guaranteed.  
6.7.6 — The Codex stub does NOT import `subprocess` and does NOT execute any process.

---

## Area 7 — Configuration and Logging

### REQ-7.1
WHEN the application loads its configuration,  
THEN all configuration MUST be managed by a `pydantic-settings` `Settings` class defined in `src/devflow_core/config.py` that reads values from environment variables and a `.env` file.

**Acceptance Criteria:**  
7.1.1 — `Settings()` instantiates without error when a valid `.env.example` is copied to `.env`.  
7.1.2 — `Settings()` raises a `ValidationError` if a required field is set to an invalid value.  
7.1.3 — The `Settings` class is importable by both the FastAPI app and integration adapters.

### REQ-7.2
WHERE the application configuration is stored,  
THEN a `.env.example` file MUST exist at the repository root containing every configuration key with a placeholder (non-secret) value and an inline comment describing each key. The actual `.env` file MUST be excluded by `.gitignore`.

**Acceptance Criteria:**  
7.2.1 — `.env.example` is committed to source control and contains all required keys.  
7.2.2 — `.env` does not appear in `git status` after creation.  
7.2.3 — Every key in `.env.example` corresponds to a field in the `Settings` class.

### REQ-7.3
WHEN the application logs an event,  
THEN logging MUST use `structlog` and MUST emit structured JSON in production mode and human-readable output in development/test mode, controlled by the `LOG_FORMAT` configuration key.

**Acceptance Criteria:**  
7.3.1 — In production mode (`LOG_FORMAT=json`), log output is valid JSON on each line.  
7.3.2 — In development mode (`LOG_FORMAT=text`), log output is human-readable.  
7.3.3 — Log records MUST include at minimum: `timestamp`, `level`, `logger`, `message`.  
7.3.4 — Log records for HTTP requests MUST include: `method`, `path`, `status_code`, `duration_ms`.

### REQ-7.4
IF a secret value is present in the configuration,  
THEN it MUST NOT appear in log output at any log level.

**Acceptance Criteria:**  
7.4.1 — A unit test confirms that a Settings instance with a mock API key does not emit that key's value in any log record produced during application startup or request handling.

---

## Area 8 — Unit and Smoke Testing

### REQ-8.1
WHEN the test suite is executed,  
THEN `pytest` MUST be the test runner, configured in `pyproject.toml` with `testpaths = ["tests"]`, `asyncio_mode = "auto"`, and a minimum coverage threshold of 80% for `src/`.

**Acceptance Criteria:**  
8.1.1 — `pytest` discovers all tests under `tests/` without additional flags.  
8.1.2 — `pytest --cov=src --cov-fail-under=80` exits with code 0 on a complete Phase 0 codebase.  
8.1.3 — Coverage reports are generated in both terminal and HTML formats.

### REQ-8.2
WHEN unit tests are written for the FastAPI backend,  
THEN they MUST use FastAPI's `TestClient` (synchronous) or `httpx.AsyncClient` with the ASGI transport (asynchronous), and MUST NOT start a live server process.

**Acceptance Criteria:**  
8.2.1 — All FastAPI unit tests complete without binding to a network port.  
8.2.2 — The `GET /health` endpoint has at least one unit test verifying both status code and body structure.  
8.2.3 — Each router module has at least one test per HTTP method defined in Phase 0, covering both success and error paths.

### REQ-8.3
WHEN smoke tests are executed,  
THEN `Streamlit AppTest` MUST be used to verify that every Streamlit page renders without an unhandled exception and contains its expected heading text.

**Acceptance Criteria:**  
8.3.1 — An `AppTest` smoke test exists for every page defined in Area 3.  
8.3.2 — All `AppTest` smoke tests pass without a live Streamlit server.  
8.3.3 — Each smoke test asserts the absence of `at.exception` AND the presence of the page heading string.

### REQ-8.4
WHEN database-dependent tests are run,  
THEN they MUST use an in-memory SQLite database with `StaticPool` and MUST NOT modify the developer's local database file or create `.db` files in the repository.

**Acceptance Criteria:**  
8.4.1 — Database fixture creates tables in-memory and tears them down after each test function (not session), isolating test state.  
8.4.2 — No `.db` or `.sqlite3` file is created in the repository directory during the test run.  
8.4.3 — Alembic commands in tests target a `tmp_path`-scoped SQLite file, not the development database.

### REQ-8.5
IF a test requires an external integration,  
THEN the integration dependency MUST be replaced with a stub or mock (using `pytest-mock` or `unittest.mock`) so the test passes without network access.

**Acceptance Criteria:**  
8.5.1 — `pytest -m "not integration"` completes with zero failures in a fully offline environment.  
8.5.2 — Integration tests are marked with `@pytest.mark.integration` and skipped by default in CI.

### REQ-8.6
WHEN acceptance criteria reference running tests,  
THEN the referenced test files MUST exist before those criteria can be evaluated. Task acceptance criteria that verify test behavior (e.g., "tests pass") apply only after the test files are created in a subsequent testing task.

**Acceptance Criteria:**  
8.6.1 — Every source-code task (Tasks 5–13) has a corresponding testing task (Tasks 14–17) that creates and runs the verifying tests.  
8.6.2 — Source tasks are considered "Done" when the source files pass linting and type-checking; the full behavioral verification is owned by the corresponding test task.

### REQ-8.7
WHEN UTCDateTime TypeDecorator behavior is verified,  
THEN dedicated tests MUST cover the full round-trip behavior including timezone conversion, naive datetime rejection, and NULL handling.

**Acceptance Criteria:**  
8.7.1 — A test verifies that a UTC datetime inserted into an in-memory SQLite database is returned with `tzinfo=UTC` (not `None`).  
8.7.2 — A test verifies that a non-UTC timezone-aware datetime (e.g., `America/New_York`) is converted to UTC on insert and returned as the equivalent UTC instant on read.  
8.7.3 — A test verifies that attempting to insert a naive datetime raises `ValueError` (not silently succeeds).  
8.7.4 — A test verifies that a `NULL` column value is returned as Python `None` (not a default datetime).  
8.7.5 — All four tests run against an in-memory `StaticPool` SQLite database; no `.db` file is created.

---

## Area 9 — Docker Compose

### REQ-9.1
WHEN a developer starts the application stack using Docker Compose (Task 20),  
THEN `docker compose up` MUST start exactly two services: `devflow-ui` (Streamlit) and `devflow-api` (FastAPI/uvicorn). Host port mappings MUST bind to `127.0.0.1` only. Container processes MAY bind internally to `0.0.0.0` for Docker bridge networking.

**Acceptance Criteria:**  
9.1.1 — `docker compose up --build` completes without error.  
9.1.2 — The `devflow-ui` service is reachable at `http://localhost:8501` from the host.  
9.1.3 — The `devflow-api` service is reachable at `http://localhost:8000` from the host.  
9.1.4 — `docker compose port devflow-api 8000` shows `127.0.0.1:8000`, not `0.0.0.0:8000`.

### REQ-9.2
WHEN the Docker Compose stack is configured,  
THEN the named data volume MUST be mounted exclusively on the `devflow-api` service. The `devflow-ui` service MUST NOT have access to the SQLite volume.

**Acceptance Criteria:**  
9.2.1 — The SQLite volume is listed under `devflow-api` volumes only in `docker-compose.yml`.  
9.2.2 — The `devflow-ui` service definition contains no volume mounts.  
9.2.3 — Stopping and restarting the stack preserves previously created records.

### REQ-9.3
WHERE environment variables are required by containerised services,  
THEN Docker Compose MUST read them from an `.env` file at the repository root using the `env_file` directive, and no secret value MUST be hardcoded in `docker-compose.yml`.

**Acceptance Criteria:**  
9.3.1 — `docker-compose.yml` contains no hardcoded passwords, tokens, or keys.  
9.3.2 — Removing the `.env` file causes `docker compose config` to emit warnings for undefined variables.

### REQ-9.4
IF the application is running in a container,  
THEN health checks MUST be defined for both services, and the health check command MUST use a tool (`curl` or `wget`) that is present in the container image.

**Acceptance Criteria:**  
9.4.1 — Both services define a `healthcheck` stanza in `docker-compose.yml`.  
9.4.2 — The Dockerfile for each stage explicitly installs `curl` (or confirms its presence in `python:3.12-slim`) before the health check is defined.  
9.4.3 — `docker compose ps` shows `healthy` status for both services within 60 seconds of startup.

### REQ-9.5
WHEN containers run application processes,  
THEN they MUST run as a non-root user and MUST drop all Linux capabilities not required for normal operation.

**Acceptance Criteria:**  
9.5.1 — `docker compose exec devflow-api whoami` returns a non-root username.  
9.5.2 — `docker-compose.yml` includes `cap_drop: [ALL]` for both services.

---

## Area 10 — GitHub Actions

### REQ-10.1
WHEN code is pushed to any branch,  
THEN a GitHub Actions CI workflow MUST run: dependency installation, linting (Ruff), type-checking (MyPy), and the test suite (Pytest with coverage).

**Acceptance Criteria:**  
10.1.1 — The workflow file exists at `.github/workflows/ci.yml`.  
10.1.2 — Jobs for lint, typecheck, and test are present in the workflow.  
10.1.3 — The workflow runs on `push` and `pull_request` triggers for all branches.  
10.1.4 — A failing lint check causes the workflow to exit with a non-zero status.

### REQ-10.2
WHEN the CI workflow runs the test job,  
THEN it MUST upload a coverage report as a workflow artefact and report the coverage percentage in the job summary.

**Acceptance Criteria:**  
10.2.1 — A coverage XML or HTML report is uploaded as a GitHub Actions artefact named `coverage-report`.  
10.2.2 — The job summary displays the coverage percentage.

### REQ-10.3
WHEN a pull request targets the `main` branch,  
THEN a security scanning workflow MUST run: dependency vulnerability scanning (`pip-audit`), secret detection (`trufflehog` or `detect-secrets`), and SAST (`bandit`).

**Acceptance Criteria:**  
10.3.1 — The security workflow file exists at `.github/workflows/security.yml`.  
10.3.2 — A known-vulnerable dependency causes the workflow to fail.  
10.3.3 — A committed secret pattern causes the secret detection step to fail.

### REQ-10.4
IF GitHub Actions secrets are needed by the workflow,  
THEN they MUST be referenced via `${{ secrets.SECRET_NAME }}` syntax and MUST NOT be echoed in workflow logs.

**Acceptance Criteria:**  
10.4.1 — No workflow file contains a literal secret value.  
10.4.2 — Workflow logs do not contain the string value of any `${{ secrets.* }}` reference.

---

## Area 11 — Security Baseline

### REQ-11.1
WHEN the codebase is committed,  
THEN a pre-commit configuration (`.pre-commit-config.yaml`) MUST enforce: Ruff linting, secret detection (`detect-secrets`), and trailing-whitespace removal on every commit.

**Acceptance Criteria:**  
11.1.1 — `pre-commit run --all-files` completes without violations on a clean codebase.  
11.1.2 — Attempting to commit a string matching a secret pattern is blocked by the pre-commit hook.

### REQ-11.2
WHERE Python dependencies are declared,  
THEN all packages MUST be pinned to exact versions, and `pip-audit` MUST be runnable against `requirements/base.txt` without known high-severity CVEs.

**Acceptance Criteria:**  
11.2.1 — Every entry in `requirements/*.txt` uses `==` version pinning.  
11.2.2 — `pip-audit -r requirements/base.txt` exits with code 0.

### REQ-11.3
WHEN input data is received by the FastAPI application,  
THEN all request bodies and query parameters MUST be validated by Pydantic v2 models before reaching any business logic, and invalid input MUST return HTTP 422 with a structured error body.

**Acceptance Criteria:**  
11.3.1 — A unit test confirms that sending an invalid request body to any endpoint returns HTTP 422.  
11.3.2 — The 422 response body contains a `detail` array matching FastAPI's standard validation error schema.

### REQ-11.4
IF the application uses SQLAlchemy,  
THEN all database queries MUST use parameterised statements (ORM queries or `text()` with bound parameters) and MUST NOT use Python string interpolation to construct SQL.

**Acceptance Criteria:**  
11.4.1 — A Bandit SAST scan reports zero B608 (SQL injection) findings.  
11.4.2 — A code review checklist item in `CONTRIBUTING.md` explicitly prohibits raw SQL string interpolation.

### REQ-11.5
WHEN the application configuration is loaded,  
THEN sensitive fields in `Settings` MUST use `pydantic.SecretStr` type so their values are masked in string representations.

**Acceptance Criteria:**  
11.5.1 — `str(settings)` and `repr(settings)` do not reveal the value of any `SecretStr` field.  
11.5.2 — MyPy confirms that `SecretStr` fields cannot be passed directly to functions expecting `str`.

---

## Area 12 — Developer Documentation

### REQ-12.1
WHEN a developer reads the repository root,  
THEN `README.md` MUST be extended (not replaced) to include: project description, architecture overview, prerequisites (Python 3.12+, Docker v2+, Make or PowerShell), quick-start instructions for both Linux/macOS and Windows, and links to the specification documents in `.kiro/specs/`.

**Acceptance Criteria:**  
12.1.1 — `README.md` contains all five described sections.  
12.1.2 — The existing stub content (`# DevFlow-AI`) is preserved.  
12.1.3 — The quick-start section contains both `make`-based and PowerShell-based instructions.

### REQ-12.2
WHERE architecture decisions are made,  
THEN a `docs/adr/` directory MUST exist containing Architecture Decision Records (ADRs) in MADR template format, covering at minimum: modular monolith choice, SQLite for local-first, Alembic for migrations, and Streamlit for UI.

**Acceptance Criteria:**  
12.2.1 — `docs/adr/ADR-0001-modular-monolith.md` exists and follows the MADR template (title, status, context, decision, consequences).  
12.2.2 — At least four ADRs exist, one per major technology choice listed above.

### REQ-12.3
WHEN a developer needs to understand the API,  
THEN the FastAPI OpenAPI schema MUST be exportable as a static `docs/openapi.json` file, generated by a `make docs` target (Linux/macOS) or `scripts/dev.ps1 -Task docs` (Windows).

**Acceptance Criteria:**  
12.3.1 — `make docs` generates `docs/openapi.json` without starting a live server.  
12.3.2 — The generated `docs/openapi.json` is valid JSON and contains at least the `/health` endpoint.

### REQ-12.4
IF a developer adds a new integration adapter,  
THEN `CONTRIBUTING.md` MUST contain a step-by-step guide covering: determine the execution mode, define the Protocol and `IntegrationCapability`, implement the stub, register in the adapter registry, write unit tests, and update the integration mode table in the documentation.

**Acceptance Criteria:**  
12.4.1 — The integration adapter guide is a numbered list of at least six steps.  
12.4.2 — The guide references the specific files and modules to be modified and explicitly addresses the `execution_mode` classification step.

---

## Assumptions

1. The project targets Python 3.12 as the minimum version; Python 3.13+ compatibility is a stretch goal.
2. `structlog` is the primary logging library. Fallback to stdlib `logging` with `python-json-logger` is permitted if a compatibility issue is discovered; the `get_logger()` interface MUST remain unchanged.
3. Kiro, Antigravity, Google Stitch, and personal NotebookLM workflows have no public programmatic API available at the time of Phase 0 design. Their protocols are limited accordingly. If public APIs become available before Phase 1 begins, the execution mode classification MUST be revisited.
4. Codex CLI is the preferred local integration for Codex. CLI usage is not guaranteed to be free or unlimited; authentication and plan requirements depend on the CLI version and the user's OpenAI plan. An API-based Codex adapter is a future option, not a Phase 0 requirement.
5. The MCP server integration is a category covering multiple MCP-compatible servers; the Protocol covers the common JSON-RPC-over-stdio interface.
6. GitHub Actions is assumed to target `ubuntu-latest` runners; self-hosted runners are out of scope for Phase 0.
7. Docker Compose v2 (`docker compose`) is assumed, not the legacy `docker-compose` v1 binary.
8. All Streamlit pages are static scaffolds in Phase 0; dynamic data loading from the API is a Phase 1+ concern, with the exception of the health check on the Settings page.
9. `pip-audit` is preferred over `safety` due to no authentication requirement; both tools satisfy the security requirement.
10. `python:3.12-slim` does not include `curl` by default; the Dockerfile MUST install it explicitly (`RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*`).
11. Windows developers are primary consumers of this project. PowerShell scripts are a first-class deliverable, not an afterthought.

---

## Out of Scope for Phase 0

- Any live AI model execution or inference
- Actual ChatGPT, Claude, Codex, or Ollama API calls
- Implementing Kiro, Antigravity, Google Stitch, or NotebookLM beyond Phase 0 stubs
- User authentication and authorisation
- Multi-user support
- Cloud deployment or hosting
- Android, React, TypeScript, or Vite
- Real-time collaboration features
- Payment processing or subscription management
- Data export/import features
- Production database (PostgreSQL, MySQL, etc.)
- Kubernetes or any orchestration beyond Docker Compose
- Performance benchmarking or load testing
- Fully functional CRUD services connected to the database (database models exist; services are wired in Phase 1+)
- Real Codex CLI execution or subprocess calls in Phase 0

---

## Review Findings Response (v1.1.0 → v1.1.1)

| Finding | Action Taken |
|---|---|
| **FIX 1 — Codex classification** — Codex was `automated_api` implying a paid OpenAI API key requirement | REQ-6.2 updated: Codex is now `cli_handoff`. REQ-6.7 added: Codex CLI protocol contract with approval gate, workspace restriction, timeouts, and execution log fields. `CODEX_API_KEY` retained in Settings as optional for future API adapter. |
| **FIX 2 — SQLite UTC round-trip** — `DateTime(timezone=True)` alone is insufficient | REQ-5.1 updated to require `UTCDateTime` TypeDecorator. REQ-5.6 added: full TypeDecorator specification including naive-datetime rejection policy (`ValueError`). REQ-8.7 added: four dedicated UTC round-trip tests. |
| **FIX 3 — Pytest exit code 5** — REQ-1.2.4 accepted zero-test collection as success | REQ-1.2.4 updated: at least one test must be discoverable; this criterion is satisfied by the testing wave (Tasks 15–19). Task 1 uses configuration inspection only. |
| **FIX 4 — Docker task references** — REQ-9.1 did not explicitly name Task 20 | REQ-9.1 updated to reference Task 20 explicitly. No stale task number references found in requirements.md. |
