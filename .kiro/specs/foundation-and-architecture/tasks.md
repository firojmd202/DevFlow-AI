# DevFlow AI — Phase 0: Implementation Tasks

**Version:** 1.1.1  
**Status:** Draft — Awaiting Approval  
**Scope:** Phase 0 — Foundation & Architecture  
**Last Updated:** 2026-11-14  
**Supersedes:** v1.1.0

---

## Suggested Execution Order

Tasks are grouped into five sequential waves. Within a wave, tasks without inter-dependencies may be worked in parallel. Never begin a wave until all tasks in the preceding wave are Done.

```
Wave 1 — Repository Scaffolding (Tasks 1–4)
  Task 1  → pyproject.toml & project metadata
  Task 2  → .gitignore, .editorconfig, .vscode/settings.json, .dockerignore
  Task 3  → requirements/ directory (base, dev, test)
  Task 4  → Makefile + scripts/dev.ps1

Wave 2 — Core Infrastructure (Tasks 5–8)
  Task 5  → devflow_core: config.py + .env.example      [depends: 1, 3]
  Task 6  → devflow_core: logging.py                    [depends: 5]
  Task 7  → devflow_api: database.py + models           [depends: 5]
  Task 8  → Alembic setup + initial migration           [depends: 7]

Wave 3 — Application Foundations (Tasks 9–14)
  Task 9  → Integration capability metadata             [depends: 5]
  Task 10 → FastAPI app factory + middleware             [depends: 5, 6]
  Task 11 → FastAPI routers (health + 3 domain)         [depends: 10, 7]
  Task 12 → Integration adapter protocols + stubs       [depends: 5, 6, 9]
  Task 13 → Adapter registry                            [depends: 12]
  Task 14 → Streamlit app + pages + APIClient           [depends: 5, 6]

Wave 4 — Testing (Tasks 15–19)
  Task 15 → conftest.py + unit tests: config, logging, models   [depends: 5, 6, 7]
  Task 16 → Unit tests: FastAPI routers                         [depends: 10, 11, 15]
  Task 17 → Unit tests: adapters, capability, registry          [depends: 12, 13]
  Task 18 → Smoke tests: Streamlit AppTest                      [depends: 14]
  Task 19 → Integration test: Alembic round-trip                [depends: 8, 15]

Wave 5 — Infrastructure & Delivery (Tasks 20–24)
  Task 20 → Docker Compose + Dockerfile                 [depends: 10, 14]
  Task 21 → GitHub Actions: ci.yml                      [depends: 1–19]
  Task 22 → GitHub Actions: security.yml + dependabot   [depends: 1–4]
  Task 23 → Pre-commit hooks (.pre-commit-config.yaml)  [depends: 1–4]
  Task 24 → Developer documentation (README, ADRs, CONTRIBUTING) [depends: all]
```

---

## Tasks

---

### Task 1 — pyproject.toml and Project Metadata

**Scope Areas:** 1 (Repository Standards), 2 (Python Environment)  
**Depends on:** _(none)_  
**Estimated Size:** Small (< 2 hours)

**Description:**  
Create `pyproject.toml` at the repository root. This is the single source of truth for project identity, build system, and tool configuration. All tooling sections must be present before any other source file is written.

**Deliverables:**
- `pyproject.toml` with sections: `[project]`, `[build-system]`, `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.coverage.report]`, `[tool.bandit]`

**Tool configuration:**

Ruff:
- `target-version = "py312"`, `line-length = 100`, `indent-width = 4`
- `select = ["E", "F", "I", "UP", "B", "S", "ANN"]`
- `ignore = ["ANN101", "ANN102"]`

MyPy:
- `strict = true`, `python_version = "3.12"`, `plugins = ["pydantic.mypy"]`

Pytest:
- `testpaths = ["tests"]`, `asyncio_mode = "auto"`, `addopts = "-v --tb=short"`
- `markers = ["integration: marks tests requiring external resources (skipped in CI by default)"]`

Coverage:
- `source = ["src"]`, `omit = ["*/tests/*", "*/__init__.py"]`, `fail_under = 80`

Bandit:
- `skips = ["B101"]` (assert is acceptable in tests)

**Acceptance Criteria:**
1. `python -m build --no-isolation` completes in a fresh environment.
2. `ruff check . --select ALL` exits with code 0 on a directory containing only `pyproject.toml`.
3. `pytest --co -q` exits with code 0 when at least one test file exists; this criterion is NOT evaluated at Task 1 time — it is evaluated after Task 15 creates the first test files. Task 1 validates pytest configuration by inspecting `pyproject.toml` with `python -c "import tomllib; ..."` or equivalent to confirm required keys are present.
4. The `[tool.pytest.ini_options]` section defines the `integration` marker.

> **v1.1.1 note (FIX 3):** Criterion 3 was previously "`pytest --collect-only` exits with code 0 (zero tests collected is acceptable)." Exit code 5 (no tests collected) is not success. Task 1 does not run pytest at all — it validates the pytest configuration section in `pyproject.toml` by parsing the TOML file directly. The first time pytest is invoked with real tests is in Task 15.

**Definition of Done:** `pyproject.toml` committed; criteria 1, 2, and 4 verified now; criterion 3 verified in Task 15.

---

### Task 2 — Repository Configuration Files

**Scope Areas:** 1 (Repository Standards), 2 (Python Environment)  
**Depends on:** Task 1  
**Estimated Size:** Small (< 1 hour)

**Description:**  
Create the repository-level editor and VCS configuration files.

**Deliverables:**
- `.gitignore` — Python, venv, caches, coverage, SQLite files, secrets, OS artefacts
- `.editorconfig` — UTF-8, LF endings, 4-space Python, 2-space YAML/TOML/JSON, final newline
- `.vscode/settings.json` — Python interpreter path, Ruff format-on-save, MyPy type checking
- `.dockerignore` — excludes `.env`, `.git/`, `tests/`, `docs/`, `*.md`, `.venv/`, `htmlcov/`

**Acceptance Criteria:**
1. A `.env` file created locally does not appear in `git status`.
2. A `__pycache__/` directory created locally does not appear in `git status`.
3. `.vscode/settings.json` is valid JSON parseable by `python -m json.tool`.
4. `.dockerignore` lists `.env` as an excluded pattern.

**Definition of Done:** All four files committed; all criteria verified.

---

### Task 3 — Requirements Files

**Scope Areas:** 2 (Python Environment)  
**Depends on:** Task 1  
**Estimated Size:** Small (< 1 hour)

**Description:**  
Create the `requirements/` directory with three pinned requirement files. All entries use exact `==` pins.

**Deliverables:**
- `requirements/base.txt`:  
  `fastapi`, `uvicorn[standard]`, `streamlit`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `aiosqlite`, `alembic`, `httpx`, `structlog`, `python-dotenv`
- `requirements/dev.txt` (includes `-r base.txt`):  
  `ruff`, `mypy`, `pydantic[mypy]`, `pre-commit`, `pip-audit`, `bandit`, `detect-secrets`
- `requirements/test.txt` (includes `-r dev.txt`):  
  `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`, `httpx`

**Acceptance Criteria:**
1. `pip install -r requirements/test.txt` completes in a fresh Python 3.12 venv.
2. All entries use `==` pinning — `grep -vE "^(#|-r)" requirements/*.txt | grep -v "==" | wc -l` returns 0.
3. `pip-audit -r requirements/base.txt` exits with code 0.

**Definition of Done:** All three files committed; all criteria verified in CI.

---

### Task 4 — Makefile and PowerShell Dev Script

**Scope Areas:** 2 (Python Environment), 12 (Developer Documentation)  
**Depends on:** Task 1, Task 3  
**Estimated Size:** Small (1–2 hours)

**Description:**  
Create a POSIX `Makefile` for Linux/macOS developers and a `scripts/dev.ps1` PowerShell script for Windows developers. Both must expose identical capabilities.

**Makefile targets:**

| Target | Action |
|---|---|
| `install` | Create `.venv`, `pip install -r requirements/base.txt`, `pip install -e .` |
| `dev` | `pip install -r requirements/dev.txt`, `pre-commit install` |
| `test` | `pytest -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80` |
| `lint` | `ruff check .` |
| `format` | `ruff format .` |
| `typecheck` | `mypy --strict src/` |
| `audit` | `pip-audit -r requirements/base.txt` |
| `migrate` | `alembic upgrade head` |
| `docs` | `python scripts/export_openapi.py` |
| `clean` | Remove `.venv`, `__pycache__`, `.mypy_cache`, `.ruff_cache`, `htmlcov`, `.coverage`, `dist` |
| `help` | Print all targets with descriptions |

**PowerShell `scripts/dev.ps1` tasks (via `-Task` parameter):**  
`install`, `dev`, `test`, `lint`, `format`, `typecheck`, `audit`, `migrate`, `docs`, `up`, `down`, `help`

Additional PowerShell requirements:
- `$ErrorActionPreference = "Stop"` at the top of the script
- Activates `.venv\Scripts\Activate.ps1` before running Python commands
- Uses PowerShell-native syntax only (no backticks, no `&&`)
- `-Task up` runs `docker compose up --build -d`; `-Task down` runs `docker compose down`

**Acceptance Criteria:**
1. `make help` lists all targets with descriptions.
2. `make lint` exits with code 0 on a clean codebase.
3. `scripts/dev.ps1 -Task help` prints all available tasks.
4. `scripts/dev.ps1 -Task lint` calls `ruff check .` using the venv Python.
5. `scripts/dev.ps1` does not contain backtick command substitution or `&&` chaining.

**Definition of Done:** Both files committed; all five criteria verified.

---

### Task 5 — devflow_core: Configuration Module

**Scope Areas:** 7 (Configuration and Logging), 11 (Security Baseline)  
**Depends on:** Task 1, Task 3  
**Estimated Size:** Medium (2–4 hours)

**Description:**  
Create the `src/devflow_core/` package. The `Settings` class is the foundation every other module depends on.

**Deliverables:**
- `src/devflow_core/__init__.py`
- `src/devflow_core/config.py` — `Settings` class per design.md §8.1 and `get_settings()` singleton
- `src/devflow_core/exceptions.py` — `DevFlowError(Exception)`, `ConfigurationError(DevFlowError)`
- `.env.example` — all 15+ keys with inline comments, placeholder values only

**Key implementation notes:**
- `Settings` must be importable as `from devflow_core.config import Settings` (not `src.devflow_core`). The editable install from Task 4 enables this.
- All credential fields (`*_API_KEY`, `*_TOKEN`) must be `SecretStr | None`.
- `get_settings()` uses `functools.lru_cache(maxsize=1)`. Tests must call `get_settings.cache_clear()` in teardown.
- `NOTEBOOKLM_API_KEY` MUST NOT be present — NotebookLM has no public API.
- `CODEX_API_KEY` MUST be present as `SecretStr | None = None` — reserved for the optional future API-based Codex adapter; the CLI stub does not use it.
- `DEVFLOW_API_BASE_URL: str = "http://localhost:8000"` MUST be present (used by Streamlit UI).

**Acceptance Criteria:**
1. `from devflow_core.config import Settings` works in a Python session with `.env` present.
2. `Settings()` raises `ValidationError` when `ENVIRONMENT` is set to an invalid value.
3. `str(settings)` does not contain the value of any `SecretStr` field.
4. `get_settings() is get_settings()` returns `True`.
5. `.env.example` contains entries for every field in `Settings`.
6. `mypy --strict src/devflow_core/` exits with code 0.

**Definition of Done:** Package committed; criteria 1–6 pass (1–5 verified in Task 15 unit tests; 6 verified now).

---

### Task 6 — devflow_core: Logging Module

**Scope Areas:** 7 (Configuration and Logging)  
**Depends on:** Task 5  
**Estimated Size:** Small (1–2 hours)

**Description:**  
Create `src/devflow_core/logging.py` with `configure_logging()` and `get_logger()`. The function is idempotent and reads parameters from the `Settings` instance.

**Deliverables:**
- `src/devflow_core/logging.py` — `configure_logging(log_level, log_format)`, `get_logger(name)`, `RedactSecretsProcessor`

**Key implementation notes:**
- Module-level `_configured: bool = False` prevents double-configuration.
- In `test` environment, force `LOG_FORMAT=text` and `LOG_LEVEL=DEBUG` regardless of env vars.
- `RedactSecretsProcessor` replaces values whose key contains `key`, `token`, `secret`, `password`, or `credential` with `"[REDACTED]"`.
- `TimeStamper` MUST use `utc=True`.

**Acceptance Criteria:**
1. `configure_logging("INFO", "json")` produces valid JSON on each log line.
2. `configure_logging("INFO", "text")` produces human-readable output.
3. `mypy --strict src/devflow_core/logging.py` exits with code 0.
4. Calling `configure_logging` twice does not raise or change the configuration.

**Definition of Done:** Module committed; criteria 1–4 verified (1–2 also verified in Task 15 unit tests).

---

### Task 7 — devflow_api: Database Module and Models

**Scope Areas:** 5 (SQLite and Alembic)  
**Depends on:** Task 5  
**Estimated Size:** Medium (2–4 hours)

**Description:**  
Create the database layer and all three Phase 0 domain models. All timestamp columns MUST use the `UTCDateTime` TypeDecorator defined in design.md §5.1 to guarantee timezone-aware UTC round-trips through SQLite.

**Deliverables:**
- `src/devflow_api/__init__.py`
- `src/devflow_api/database.py` — `create_async_engine`, `AsyncSessionLocal`, `get_db`
- `src/devflow_api/models/__init__.py`
- `src/devflow_api/models/base.py` — `UTCDateTime` TypeDecorator, `Base`, `TimestampMixin`
- `src/devflow_api/models/project.py` — `Project` model
- `src/devflow_api/models/learning.py` — `LearningItem` model
- `src/devflow_api/models/integration.py` — `IntegrationConfig` model (includes `execution_mode` TEXT column)

**Key implementation notes:**
- `UTCDateTime` MUST be a `TypeDecorator` subclass with `impl = DateTime` and `cache_ok = True`.
- `UTCDateTime.process_bind_param` MUST raise `ValueError` for naive datetime inputs; it MUST convert timezone-aware non-UTC inputs to UTC before storage.
- `UTCDateTime.process_result_value` MUST return a `datetime` with `tzinfo=UTC`; it MUST return `None` unchanged for `NULL` values.
- `TimestampMixin` uses `UTCDateTime` (not `DateTime(timezone=True)`) with lambda defaults: `default=lambda: datetime.now(UTC)`.
- `datetime.utcnow()` MUST NOT appear anywhere in the codebase — use `datetime.now(UTC)` exclusively.
- `get_db` MUST use a `try/finally` block to close the session.
- WAL mode: `@event.listens_for(engine, "connect")` runs `PRAGMA journal_mode=WAL`.
- `CheckConstraint` enforces allowed status values on `Project` and `LearningItem`.
- **Do NOT use `StaticPool` in the production engine** — only in test fixtures (Task 15).

**Acceptance Criteria:**
1. All model files importable without error.
2. `mypy --strict src/devflow_api/models/ src/devflow_api/database.py` exits with code 0.
3. `created_at` column uses `UTCDateTime` TypeDecorator (not `DateTime(timezone=True)` alone) — verified by inspecting the mapped column type.
4. `IntegrationConfig` has an `execution_mode` TEXT column.
5. `UTCDateTime.process_bind_param` raises `ValueError` when called with a naive datetime (verified by unit test in Task 15).

> **v1.1.1 note (FIX 2):** Criterion 3 was previously "`created_at` column type is `DateTime(timezone=True)`." This is replaced by the requirement to use `UTCDateTime` TypeDecorator. `DateTime(timezone=True)` alone is insufficient for SQLite. See design.md §5.1.

**Definition of Done:** All files committed; all five criteria verified (behavioral tests in Task 15).

---

### Task 8 — Alembic Setup and Initial Migration

**Scope Areas:** 5 (SQLite and Alembic)  
**Depends on:** Task 7  
**Estimated Size:** Medium (2–3 hours)

**Description:**  
Initialise Alembic with an `env.py` that reads the database URL from `Settings` and derives a synchronous dialect URL for Alembic's synchronous engine. Author the initial migration manually.

**Deliverables:**
- `alembic.ini` — `sqlalchemy.url` left empty
- `alembic/env.py` — imports `get_settings`, strips `+aiosqlite`, imports all models
- `alembic/script.py.mako` — standard template unchanged
- `alembic/versions/001_create_initial_tables.py` — hand-authored `upgrade()` and `downgrade()`

**Migration content:**

`upgrade()` creates: `projects`, `learning_items`, `integration_configs` with all columns, constraints, and `DATETIME` columns (the `UTCDateTime` TypeDecorator handles Python-side conversion; Alembic emits standard `DATETIME` DDL).

`downgrade()` drops all three tables in reverse order.

**Key implementation notes:**
- `env.py` synchronous URL derivation:  
  `sync_url = settings.DATABASE_URL.replace("+aiosqlite", "")`
- `alembic.ini` MUST NOT contain a database URL with credentials.
- Timestamp columns in the migration DDL use `DATETIME` (the SQLite type that `UTCDateTime.impl = DateTime` maps to). No `server_default=func.now()` — Python-side defaults are authoritative.

**Acceptance Criteria:**
1. `alembic current` exits with code 0 against a fresh database (uses `devflow.db` from `.env`).
2. `alembic upgrade head` creates all three tables.
3. `alembic downgrade -1` drops all three tables.
4. `grep -E "sqlite:" alembic.ini | grep -v "^#"` returns empty.
5. `mypy --strict alembic/env.py` exits with code 0 (or acceptable MyPy ignores documented).

**Definition of Done:** Alembic files committed; criteria 1–4 verified manually and in Task 19 integration test.

---

### Task 9 — Integration Capability Metadata

**Scope Areas:** 6 (Typed Integration Adapter Contracts)  
**Depends on:** Task 5  
**Estimated Size:** Small (1 hour)

**Description:**  
Create `src/devflow_api/adapters/capability.py` with the `ExecutionMode` enum and `IntegrationCapability` Pydantic v2 model. This module has no dependencies on the rest of the adapter layer, making it safe to implement early.

**Deliverables:**
- `src/devflow_api/adapters/__init__.py`
- `src/devflow_api/adapters/capability.py` — `ExecutionMode(StrEnum)`, `IntegrationCapability(BaseModel)`
- `src/devflow_api/adapters/exceptions.py` — `AdapterNotFoundError`, `MissingCredentialError`

**`IntegrationCapability` fields:**
```python
name: str
execution_mode: ExecutionMode
supported_actions: list[str]
auth_required: bool
auth_type: str | None          # "api_key" | "oauth" | "token" | "cli_auth" | None
available_in_phase_0: bool     # always False for Phase 0
notes: str = ""
```

**`ExecutionMode` values:** `automated_api`, `cli_handoff`, `manual_handoff`, `unknown`

**Acceptance Criteria:**
1. `from devflow_api.adapters.capability import ExecutionMode, IntegrationCapability` works.
2. `IntegrationCapability(name="test", execution_mode=ExecutionMode.UNKNOWN, ...)` instantiates without error.
3. `mypy --strict src/devflow_api/adapters/capability.py src/devflow_api/adapters/exceptions.py` exits with code 0.
4. `ExecutionMode` is a `StrEnum` (values compare equal to their string representations).
5. `ExecutionMode.CLI_HANDOFF == "cli_handoff"` returns `True`.

**Definition of Done:** Files committed; all five criteria verified (behavioral tests in Task 17).

---

### Task 10 — FastAPI App Factory and Middleware

**Scope Areas:** 4 (FastAPI Backend Foundation), 7 (Configuration), 11 (Security)  
**Depends on:** Task 5, Task 6  
**Estimated Size:** Medium (3–4 hours)

**Description:**  
Create `src/devflow_api/main.py` as a `create_app()` factory. Wire middleware: CORS, request logging, error handling. The factory is used by both the production entry point and all tests.

**Deliverables:**
- `src/devflow_api/main.py` — `create_app(settings: Settings | None = None) -> FastAPI` + module-level `app = create_app()`
- `src/devflow_api/middleware/__init__.py`
- `src/devflow_api/middleware/logging.py` — `RequestLoggingMiddleware`
- `src/devflow_api/middleware/error_handler.py` — `add_error_handlers(app)`
- `src/devflow_api/schemas/__init__.py`
- `src/devflow_api/schemas/common.py` — `ErrorResponse(BaseModel)`, `HealthResponse(BaseModel)`

**`create_app()` MUST:**
1. Accept an optional `settings` parameter (uses `get_settings()` if not provided — enables test injection).
2. Instantiate `FastAPI` with `title`, `version`, `description`.
3. Add `CORSMiddleware` with `allow_origins=settings.ALLOWED_ORIGINS`.
4. Add `RequestLoggingMiddleware`.
5. Call `add_error_handlers(app)`.
6. Register routers (health router added here; domain routers added in Task 11).
7. Store `AdapterRegistry` in `app.state.adapter_registry` (populated in Task 13).
8. Call `configure_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)`.

**`RequestLoggingMiddleware` MUST:**
- Generate a UUID4 `request_id`, bind to structlog contextvars, clear after response.
- Log `method`, `path`, `status_code`, `duration_ms`, `request_id`.

**`add_error_handlers` MUST:**
- Handle `Exception` → HTTP 500 `ErrorResponse` + log ERROR with traceback.
- Handle `HTTPException` → appropriate status + `ErrorResponse`.
- Handle `RequestValidationError` → HTTP 422 `ErrorResponse`.

**Acceptance Criteria:**
1. `create_app()` returns a `FastAPI` instance without error.
2. `create_app(settings=mock_settings)` uses the provided settings (not env vars).
3. `mypy --strict src/devflow_api/main.py src/devflow_api/middleware/ src/devflow_api/schemas/common.py` exits with code 0.
4. A CORS preflight from `http://localhost:8501` is accepted (verified in Task 16).

**Definition of Done:** All files committed; criteria 1–3 verified now; criterion 4 verified in Task 16.

---

### Task 11 — FastAPI Routers

**Scope Areas:** 4 (FastAPI Backend Foundation)  
**Depends on:** Task 10, Task 7  
**Estimated Size:** Medium (3–4 hours)

**Description:**  
Implement the four Phase 0 routers. Domain routers return stub data — no service or database calls yet.

**Deliverables:**
- `src/devflow_api/routers/__init__.py`
- `src/devflow_api/routers/health.py` — `GET /health`
- `src/devflow_api/routers/projects.py` — CRUD stubs under `/api/v1/projects`
- `src/devflow_api/routers/learning.py` — CRUD stubs under `/api/v1/learning`
- `src/devflow_api/routers/integrations.py` — list + per-integration health under `/api/v1/integrations`
- `src/devflow_api/schemas/project.py`, `learning.py`, `integration.py` — Pydantic v2 request/response schemas

**Health router:**
```
GET /health → HealthResponse(status="ok", version=settings.APP_VERSION)
```

**Projects router (stub — no DB calls):**
```
GET    /api/v1/projects          → list[ProjectResponse]  (empty list)
POST   /api/v1/projects          → ProjectResponse        (echo input, id=1)
GET    /api/v1/projects/{id}     → ProjectResponse | 404
PUT    /api/v1/projects/{id}     → ProjectResponse | 404
DELETE /api/v1/projects/{id}     → 204 | 404
```

**Learning router:** same pattern as projects.

**Integrations router (uses adapter registry from `request.app.state`):**
```
GET /api/v1/integrations                    → list[IntegrationSummary]
GET /api/v1/integrations/{name}/health      → IntegrationHealthResponse
```

`IntegrationSummary` MUST include `execution_mode` from the adapter's `IntegrationCapability`. `IntegrationHealthResponse` MUST include the full health check dict from `adapter.health_check()`.

**Acceptance Criteria:**
1. `GET /health` returns `{"status": "ok", "version": "0.1.0"}` and HTTP 200.
2. All routes appear in `/openapi.json` under correct prefixes.
3. `POST /api/v1/projects` with missing `name` returns HTTP 422.
4. `GET /api/v1/projects/9999` returns HTTP 404 with `{"error": "Not found", "code": "NOT_FOUND"}`.
5. `GET /api/v1/integrations` returns a list including an entry with `execution_mode` field.
6. `mypy --strict src/devflow_api/routers/ src/devflow_api/schemas/` exits with code 0.

**Definition of Done:** All files committed; criteria 1–6 verified (1–5 also tested in Task 16).

---

### Task 12 — Integration Adapter Protocols and Stubs

**Scope Areas:** 6 (Typed Integration Adapter Contracts)  
**Depends on:** Task 5, Task 6, Task 9  
**Estimated Size:** Large (4–6 hours)

**Description:**  
Implement all 11 Protocol definitions and their corresponding Phase 0 stubs. Protocol scope is determined by `execution_mode` (see design.md §7.3). Codex is `cli_handoff` and requires `CodexCLIRequest`/`CodexCLIResult` types with an approval gate.

**Deliverables:**
- `src/devflow_api/adapters/protocols/__init__.py`
- `src/devflow_api/adapters/protocols/base.py` — `BaseAdapterProtocol` (runtime_checkable)
- 11 protocol files (one per integration)
- `src/devflow_api/adapters/stubs/__init__.py`
- 11 stub files (one per integration)

**Protocol scoping rules (MUST be enforced):**

| Integration | Mode | Protocol action methods |
|---|---|---|
| ChatGPT | `automated_api` | `complete(prompt, model) → ChatGPTResponse` |
| **Codex** | **`cli_handoff`** | **`request_code_generation(description, language, workspace_path) → CodexCLIRequest`; `execute_approved_request(request: CodexCLIRequest) → CodexCLIResult`** |
| Kiro | `manual_handoff` | `get_instructions(task: str) → str` only |
| Claude | `automated_api` | `complete(prompt, model) → ClaudeResponse` |
| Antigravity | `unknown` | _(none beyond health_check)_ |
| Google Stitch | `unknown` | _(none beyond health_check)_ |
| Figma | `automated_api` | `get_file(file_key: str) → FigmaResponse` |
| NotebookLM | `manual_handoff` | `get_instructions(notebook_context: str) → str` only |
| GitHub | `automated_api` | `create_issue(repo, title, body) → GitHubIssueResponse` |
| Ollama | `automated_api` | `generate(model, prompt) → OllamaResponse` |
| MCP Servers | `automated_api` | `call_tool(server, tool, args) → MCPResponse` |

**Codex-specific requirements:**
- `CodexCLIRequest` dataclass: `description: str`, `language: str`, `workspace_path: str`, `approved: bool = False`, `timeout_seconds: int = 30`.
- `CodexCLIResult` dataclass: `stdout: str`, `stderr: str`, `exit_code: int`, `timed_out: bool`, `stub: bool = True`.
- `execute_approved_request` MUST raise `ValueError` if `request.approved is False`.
- Codex stub `IntegrationCapability.notes` MUST document that CLI authentication and plan limits may apply.
- Codex stub MUST NOT import `subprocess`.

**General stub requirements:**
- Each stub has a `_capability` class attribute of type `IntegrationCapability`.
- `health_check()` returns `{"status": "stub", "integration": name, "execution_mode": mode}`.
- `automated_api` stubs with async action methods return a typed response with `stub=True`.
- `manual_handoff` stubs return a formatted instruction string from `get_instructions()`.
- `unknown` stubs expose ONLY `health_check`.
- **No stub MUST import `httpx`, `requests`, `subprocess`, or any network/process library.**

**Acceptance Criteria:**
1. `mypy --strict src/devflow_api/adapters/protocols/ src/devflow_api/adapters/stubs/` exits with code 0.
2. `isinstance(stub_instance, BaseAdapterProtocol)` is `True` for all 11 stubs.
3. Kiro and NotebookLM stubs do NOT define `run_spec`, `query`, or any async action method.
4. Antigravity and Google Stitch stubs expose ONLY `name`, `capability`, and `health_check`.
5. `health_check()` on any stub returns a dict containing `execution_mode` key.
6. Codex stub `execution_mode` is `"cli_handoff"` (not `"automated_api"`).
7. Codex stub `execute_approved_request` raises `ValueError` when `request.approved is False`.
8. No Codex stub file imports `subprocess`.

**Definition of Done:** All files committed; criteria 1–8 verified (behavioral tests in Task 17).

---

### Task 13 — Adapter Registry

**Scope Areas:** 6 (Typed Integration Adapter Contracts)  
**Depends on:** Task 12  
**Estimated Size:** Small (1 hour)

**Description:**  
Implement `AdapterRegistry` and the module-level `registry` singleton populated with all 11 stubs. Wire the registry into the FastAPI app state.

**Deliverables:**
- `src/devflow_api/adapters/registry.py` — `AdapterRegistry` class + `registry` singleton

**Key implementation notes:**
- `registry` is populated at import time by registering all 11 stub instances.
- `main.py` `create_app()` calls `app.state.adapter_registry = registry` during startup.
- `list_names()` returns a sorted list.

**Acceptance Criteria:**
1. `from devflow_api.adapters.registry import registry` gives a populated registry with 11 entries.
2. `registry.get("kiro")` returns the `KiroStubAdapter` instance.
3. `registry.get("codex")` returns the `CodexStubAdapter` instance with `execution_mode == "cli_handoff"`.
4. `registry.get("nonexistent")` raises `AdapterNotFoundError`.
5. `registry.list_names()` returns a sorted list of exactly 11 strings.
6. `mypy --strict src/devflow_api/adapters/registry.py` exits with code 0.

**Definition of Done:** Module committed; criteria verified (behavioral tests in Task 17).

---

### Task 14 — Streamlit Application Foundation

**Scope Areas:** 3 (Streamlit Multipage Application Foundation)  
**Depends on:** Task 5, Task 6  
**Estimated Size:** Medium (3–5 hours)

**Description:**  
Create the full Streamlit multipage application using `st.Page`/`st.navigation` as the single navigation strategy. All 10 page stubs display Phase 0 placeholders with no fabricated data.

**Deliverables:**
- `src/devflow_ui/__init__.py`
- `src/devflow_ui/app.py` — `st.set_page_config` + `st.navigation` with 10 `st.Page` entries
- `src/devflow_ui/api_client.py` — `APIClient(base_url: str)` wrapping `httpx`
- `src/devflow_ui/components/__init__.py`
- `src/devflow_ui/components/sidebar.py` — `render_sidebar() -> None`
- `src/devflow_ui/components/placeholders.py` — `phase0_placeholder(feature_name: str) -> None`
- `src/devflow_ui/pages/1_Dashboard.py` through `10_Settings.py` (10 files)

**`app.py` navigation pattern:**
```python
import streamlit as st
st.set_page_config(page_title="DevFlow AI", page_icon="🤖", layout="wide")
pages = [
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon="🏠"),
    # ... all 10 pages
]
pg = st.navigation(pages)
pg.run()
```

**`phase0_placeholder` MUST display:**
- A warning/info box containing the string "Phase 0"
- The feature name passed as parameter
- No hard-coded metrics, charts, status badges, or simulated data

**`APIClient` interface:**
```python
class APIClient:
    def __init__(self, base_url: str) -> None: ...
    async def get_health(self) -> dict[str, str] | None: ...
```
On connection error or non-2xx, all methods return `None` and log a warning. Never raise to the caller.

**Settings page** (10_Settings.py) MAY call `APIClient.get_health()` and show the result. If the backend is unavailable, it shows "API unavailable — start the backend to connect."

**Dashboard page** (1_Dashboard.py) MUST NOT display any hard-coded project counts, AI status indicators, or simulated metrics.

**Acceptance Criteria:**
1. `AppTest.from_file("src/devflow_ui/app.py").run()` completes without exception.
2. `AppTest.from_file("src/devflow_ui/pages/1_Dashboard.py").run()` does not emit `at.exception`.
3. Each of the 10 page files contains a `phase0_placeholder` call.
4. `mypy --strict src/devflow_ui/` exits with code 0.
5. No page file imports `httpx` directly; all network access goes through `APIClient`.

**Definition of Done:** All files committed; criteria 1–5 verified (smoke tests in Task 18).

---

### Task 15 — conftest.py and Unit Tests: Core, Config, Logging, Models

**Scope Areas:** 8 (Unit and Smoke Testing)  
**Depends on:** Task 5, Task 6, Task 7  
**Estimated Size:** Medium (3–5 hours)

**Description:**  
Establish the shared test fixtures in `tests/conftest.py` and write the first wave of unit tests. This task creates the testing infrastructure that later tasks build on. It is also the first task where `pytest` is invoked with real test files — this is when REQ-1.2.4 and Task 1 criterion 3 are first evaluated.

**Deliverables:**
- `tests/__init__.py`
- `tests/conftest.py` — shared fixtures (see below)
- `tests/unit/__init__.py`
- `tests/unit/test_config.py` — Settings validation, singleton, SecretStr masking
- `tests/unit/test_logging.py` — JSON output, text output, secret redaction, idempotence
- `tests/unit/test_models.py` — model creation, timestamp timezone, CheckConstraint enforcement, UTCDateTime round-trip

**Required fixtures in `conftest.py`:**

```python
@pytest.fixture(autouse=False)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    yield Settings()
    get_settings.cache_clear()

@pytest.fixture
async def async_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    # StaticPool required for in-memory SQLite across async contexts
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def async_db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session:
        yield session
        await session.rollback()   # isolation between tests

@pytest.fixture
def test_client(test_settings: Settings) -> TestClient:
    app = create_app(settings=test_settings)
    return TestClient(app)
```

**test_config.py tests MUST verify:**
- `Settings()` with valid values instantiates without error
- `Settings()` raises `ValidationError` with invalid `ENVIRONMENT`
- `str(settings)` does not contain `SecretStr` values
- `get_settings() is get_settings()` (singleton)
- `get_settings.cache_clear()` allows fresh instantiation

**test_logging.py tests MUST verify:**
- JSON format output is valid JSON (use `json.loads`)
- Text format output is not valid JSON
- A log event with key `api_key` does not emit the value in output
- Calling `configure_logging` twice does not raise or duplicate output

**test_models.py tests MUST verify:**
- `Project`, `LearningItem`, `IntegrationConfig` can be inserted into in-memory DB
- `created_at` is timezone-aware (`tzinfo is not None`) after round-trip through SQLite
- `created_at` `tzinfo` equals `UTC` after read-back (not just non-None)
- A `Project` inserted with a non-UTC datetime (e.g., `America/New_York`) returns the equivalent UTC instant on read-back
- Attempting to insert a `Project` with a naive `datetime` raises `ValueError` (from `UTCDateTime.process_bind_param`)
- `CheckConstraint` on `Project.status` raises `IntegrityError` for invalid values
- In-memory database does not create any files in the working directory
- `datetime.utcnow()` does NOT appear in any source file (verified by grepping `src/`)

**Acceptance Criteria:**
1. `pytest tests/unit/test_config.py` passes with zero failures.
2. `pytest tests/unit/test_logging.py` passes with zero failures.
3. `pytest tests/unit/test_models.py` passes with zero failures — including UTCDateTime round-trip, non-UTC timezone, naive datetime rejection, and NULL tests (REQ-8.7).
4. No `.db` or `.sqlite3` file appears in the repository directory after the test run.
5. `pytest --cov=src/devflow_core --cov=src/devflow_api/models --cov-fail-under=80` exits with code 0.
6. `pytest --co -q` exits with code 0 (at least one test is now discoverable — REQ-1.2.4 is now satisfied).

> **v1.1.1 note (FIX 3):** Criterion 6 is new. This is the first task that creates test files, making it the first point at which `pytest --co -q` can exit successfully (exit code 0, not exit code 5). Task 1 does not run pytest; this task is where the Task 1 criterion 3 is evaluated for the first time.

**Definition of Done:** All test files committed; all six criteria pass in CI.

---

### Task 16 — Unit Tests: FastAPI Routers

**Scope Areas:** 8 (Unit and Smoke Testing)  
**Depends on:** Task 10, Task 11, Task 15  
**Estimated Size:** Medium (2–4 hours)

**Description:**  
Write unit tests for all FastAPI router modules using the `test_client` fixture from Task 15. Each endpoint must have both a happy-path test and at least one error test.

**Deliverables:**
- `tests/unit/test_health.py`
- `tests/unit/test_projects_router.py`
- `tests/unit/test_learning_router.py`
- `tests/unit/test_integrations_router.py`

**test_health.py MUST verify:**
- `GET /health` returns HTTP 200
- Response body contains `{"status": "ok"}` and a `version` key
- `version` value matches the string in `pyproject.toml`

**test_projects_router.py MUST verify:**
- `GET /api/v1/projects` returns HTTP 200 and an empty list
- `POST /api/v1/projects` with valid body returns HTTP 200 or 201
- `POST /api/v1/projects` with missing `name` returns HTTP 422
- `GET /api/v1/projects/9999` returns HTTP 404 with structured `ErrorResponse`
- CORS preflight from `http://localhost:8501` returns HTTP 200 with correct `Access-Control-Allow-Origin`

**test_integrations_router.py MUST verify:**
- `GET /api/v1/integrations` returns a list of 11 integration summaries
- Each summary contains an `execution_mode` field
- `GET /api/v1/integrations/kiro/health` returns `{"status": "stub", "execution_mode": "manual_handoff", ...}`
- `GET /api/v1/integrations/codex/health` returns `{"status": "stub", "execution_mode": "cli_handoff", ...}`
- `GET /api/v1/integrations/antigravity/health` returns `{"status": "stub", "execution_mode": "unknown", ...}`
- `GET /api/v1/integrations/nonexistent/health` returns HTTP 404

**Acceptance Criteria:**
1. `pytest tests/unit/test_health.py` passes.
2. `pytest tests/unit/test_projects_router.py` passes (all endpoints, success and error paths).
3. `pytest tests/unit/test_integrations_router.py` passes including execution_mode assertions for Codex (`cli_handoff`), Kiro (`manual_handoff`), and Antigravity (`unknown`).
4. All tests complete offline (no live network calls).
5. `pytest --cov=src/devflow_api/routers --cov-fail-under=80` exits with code 0.

**Definition of Done:** All test files committed; all five criteria pass in CI.

---

### Task 17 — Unit Tests: Adapters, Capability, and Registry

**Scope Areas:** 8 (Unit and Smoke Testing)  
**Depends on:** Task 12, Task 13  
**Estimated Size:** Small (1–2 hours)

**Description:**  
Write unit tests for all adapter stubs, the capability model, and the registry.

**Deliverables:**
- `tests/unit/test_adapters.py`

**Tests MUST cover:**
- `IntegrationCapability` instantiates with valid `ExecutionMode` values
- `ExecutionMode.CLI_HANDOFF == "cli_handoff"` returns `True`
- All 11 stubs pass `isinstance(stub, BaseAdapterProtocol)` check
- All 11 `health_check()` calls return `{"status": "stub", "integration": name, "execution_mode": mode}`
- Codex stub has `execution_mode == "cli_handoff"` and exposes `request_code_generation()` and `execute_approved_request()`
- Codex stub `request_code_generation("add tests", "python", "/workspace")` returns a `CodexCLIRequest` with `approved=False`
- Codex stub `execute_approved_request` raises `ValueError` when `request.approved is False`
- Codex stub `execute_approved_request` with `request.approved = True` returns `CodexCLIResult(stub=True)` without launching a subprocess
- Kiro stub has `execution_mode == "manual_handoff"` and exposes `get_instructions()`
- Kiro stub `get_instructions("write tests")` returns a non-empty string containing "Phase 0"
- Antigravity and Google Stitch stubs do NOT have `invoke`, `stitch`, or any action method beyond `health_check`
- NotebookLM stub exposes `get_instructions()` and NOT `query()`
- Registry `get("chatgpt")` returns a `ChatGPTStubAdapter` instance
- Registry `get("codex")` returns a `CodexStubAdapter` instance
- Registry `get("nonexistent")` raises `AdapterNotFoundError`
- Registry `list_names()` returns a sorted list of 11 items
- No stub imports `httpx`, `requests`, or `subprocess` (checked via `inspect.getfile`)

**Acceptance Criteria:**
1. All adapter stub assertions pass for all 11 integrations.
2. Codex execution mode is `cli_handoff`; approval gate raises `ValueError` as designed.
3. Execution mode assertions pass for Kiro (`manual_handoff`), NotebookLM (`manual_handoff`), Antigravity (`unknown`), Stitch (`unknown`).
4. Registry tests pass including error case.
5. `pytest --cov=src/devflow_api/adapters --cov-fail-under=80` exits with code 0.
6. All tests pass offline.

**Definition of Done:** Test file committed; all six criteria pass in CI.

---

### Task 18 — Smoke Tests: Streamlit AppTest

**Scope Areas:** 8 (Unit and Smoke Testing)  
**Depends on:** Task 14  
**Estimated Size:** Small (1–2 hours)

**Description:**  
Write Streamlit `AppTest` smoke tests for all 10 pages. Each test verifies the page renders without an unhandled exception and contains the expected heading.

**Deliverables:**
- `tests/smoke/__init__.py`
- `tests/smoke/test_ui_pages.py`

**Test pattern:**
```python
import pytest
from streamlit.testing.v1 import AppTest

PAGE_SPECS = [
    ("src/devflow_ui/pages/1_Dashboard.py", "Dashboard"),
    ("src/devflow_ui/pages/2_Projects.py", "Projects"),
    ("src/devflow_ui/pages/3_Learning.py", "Learning"),
    ("src/devflow_ui/pages/4_Specifications.py", "Specifications"),
    ("src/devflow_ui/pages/5_Design.py", "Design"),
    ("src/devflow_ui/pages/6_Coding.py", "Coding"),
    ("src/devflow_ui/pages/7_Testing.py", "Testing"),
    ("src/devflow_ui/pages/8_Documentation.py", "Documentation"),
    ("src/devflow_ui/pages/9_Integrations.py", "Integrations"),
    ("src/devflow_ui/pages/10_Settings.py", "Settings"),
]

@pytest.mark.parametrize("page_file,expected_heading", PAGE_SPECS)
def test_page_renders_without_exception(page_file: str, expected_heading: str) -> None:
    at = AppTest.from_file(page_file)
    at.run()
    assert not at.exception, f"Page {page_file} raised: {at.exception}"
    all_text = [str(e.value) for e in at.markdown + at.header + at.subheader]
    assert any(expected_heading in t for t in all_text), (
        f"Heading '{expected_heading}' not found in page {page_file}"
    )

def test_dashboard_has_no_fabricated_metrics() -> None:
    at = AppTest.from_file("src/devflow_ui/pages/1_Dashboard.py")
    at.run()
    all_text = " ".join(str(e.value) for e in at.markdown + at.metric + at.text)
    # Hard-coded project counts or status badges should not appear
    assert "projects: " not in all_text.lower() or "phase 0" in all_text.lower()
```

**Acceptance Criteria:**
1. All 10 parameterised page tests pass.
2. `test_dashboard_has_no_fabricated_metrics` passes.
3. No test makes a network call.
4. No test requires a live Streamlit server.
5. `pytest tests/smoke/` completes in under 90 seconds.

**Definition of Done:** Test file committed; all five criteria pass in CI.

---

### Task 19 — Integration Test: Alembic Round-Trip

**Scope Areas:** 5 (SQLite and Alembic), 8 (Testing)  
**Depends on:** Task 8, Task 15  
**Estimated Size:** Small (1 hour)

**Description:**  
Write an integration test that verifies the full Alembic migration round-trip using a `tmp_path`-scoped SQLite file, ensuring migrations never touch the developer's real database.

**Deliverables:**
- `tests/integration/__init__.py`
- `tests/integration/test_database.py`

**Test logic:**
```python
import pytest
from pathlib import Path
from alembic.config import Config
from alembic import command

@pytest.mark.integration
def test_alembic_upgrade_downgrade_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "test_devflow.db"
    db_url = f"sqlite:///{db_path}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(alembic_cfg, "head")
    assert db_path.exists()

    command.downgrade(alembic_cfg, "-1")

    command.upgrade(alembic_cfg, "head")  # round-trip must succeed
```

**Acceptance Criteria:**
1. Test uses `tmp_path` — no `.db` file appears in the repository directory.
2. `upgrade head` creates all three tables.
3. `downgrade -1` completes without error.
4. Second `upgrade head` completes without error.
5. The test is marked `@pytest.mark.integration` and skipped in default CI (`pytest -m "not integration"`).

**Definition of Done:** Test file committed; all five criteria verified.

---

### Task 20 — Docker Compose and Dockerfile

**Scope Areas:** 9 (Docker Compose)  
**Depends on:** Task 10, Task 14  
**Estimated Size:** Medium (3–5 hours)

**Description:**  
Create the multi-stage `Dockerfile` and `docker-compose.yml` per design.md §10. Host ports bind to `127.0.0.1`. The SQLite volume is mounted on the API service only. `curl` is explicitly installed in the base stage.

**Deliverables:**
- `Dockerfile` — three stages: `base`, `api`, `ui`
- `docker-compose.yml` — per design.md §10.1 topology
- Verify/update `.dockerignore` from Task 2

**Dockerfile base stage MUST:**
```
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1001 appuser
WORKDIR /app
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/base.txt
```

**docker-compose.yml MUST:**
- Use `"127.0.0.1:8000:8000"` and `"127.0.0.1:8501:8501"` port syntax
- Mount `devflow-data:/data` on `devflow-api` ONLY
- Include `cap_drop: [ALL]` on both services
- Set `DEVFLOW_API_BASE_URL=http://devflow-api:8000` as an environment variable on `devflow-ui`
- Define `healthcheck` on both services using `curl`

**Acceptance Criteria:**
1. `docker compose build` completes without error.
2. `docker compose up -d` starts both services.
3. `curl http://localhost:8000/health` returns `{"status": "ok"}`.
4. `curl http://localhost:8501/_stcore/health` returns HTTP 200.
5. `docker compose ps` shows both services as `healthy` within 60 seconds.
6. `docker compose port devflow-api 8000` shows `127.0.0.1:8000` (not `0.0.0.0`).
7. `docker compose down && docker compose up -d` preserves the named volume data.

**Definition of Done:** All files committed; all seven criteria verified manually.

---

### Task 21 — GitHub Actions: CI Workflow

**Scope Areas:** 10 (GitHub Actions)  
**Depends on:** Tasks 1–19 (all source and test tasks complete)  
**Estimated Size:** Small (1–2 hours)

**Description:**  
Create `.github/workflows/ci.yml` per design.md §12.1.

**Deliverables:**
- `.github/workflows/ci.yml`

**Job structure:**
```yaml
name: CI
on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["**"]
permissions:
  contents: read
jobs:
  lint:     ruff check + ruff format --check
  typecheck: mypy --strict src/   [needs: lint]
  test:     pytest --cov=src --cov-fail-under=80   [needs: typecheck]
            upload coverage as artefact "coverage-report"
            write coverage % to $GITHUB_STEP_SUMMARY
```

Each job uses `actions/checkout@v4`, `actions/setup-python@v5` (python-version: "3.12"), `actions/cache@v4` keyed on `${{ hashFiles('requirements/test.txt') }}`.

The test job runs `pytest -m "not integration"` to skip integration tests that need external resources.

**Acceptance Criteria:**
1. Workflow runs on every push and every PR.
2. A Ruff violation causes `lint` to fail.
3. A MyPy error causes `typecheck` to fail.
4. A failing test causes `test` to fail.
5. Coverage artefact named `coverage-report` is uploaded.
6. `actions/cache@v4` is used for pip.

**Definition of Done:** Workflow committed; observed to pass on a clean push.

---

### Task 22 — GitHub Actions: Security Workflow

**Scope Areas:** 10 (GitHub Actions), 11 (Security Baseline)  
**Depends on:** Tasks 1–4  
**Estimated Size:** Small (1 hour)

**Description:**  
Create `.github/workflows/security.yml` and `.github/dependabot.yml` per design.md §12.2.

**Deliverables:**
- `.github/workflows/security.yml`
- `.github/dependabot.yml`

**Job structure:**
```yaml
name: Security
on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * 1'
permissions:
  contents: read
jobs:
  dependency-scan: pip-audit -r requirements/base.txt
  secret-detection: trufflehog filesystem . --only-verified --fail
  sast: bandit -r src/ -ll -f json -o bandit.json + upload
```

**Acceptance Criteria:**
1. Workflow runs on PRs to `main` and weekly.
2. `pip-audit` step fails on a known-vulnerable package.
3. `bandit` step fails on a B608 SQL injection pattern.
4. No step echoes secret values.
5. `dependabot.yml` is valid YAML targeting `pip` ecosystem for `requirements/base.txt`.

**Definition of Done:** Both files committed; manually verified.

---

### Task 23 — Pre-Commit Hooks

**Scope Areas:** 11 (Security Baseline)  
**Depends on:** Tasks 1–4  
**Estimated Size:** Small (1 hour)

**Description:**  
Create `.pre-commit-config.yaml` and initialise the `detect-secrets` baseline.

**Deliverables:**
- `.pre-commit-config.yaml` — all hooks pinned to exact SHAs or version tags
- `.secrets.baseline` — generated by `detect-secrets scan`

**Hook list:**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <exact-version>
    hooks: [ruff, ruff-format]
  - repo: https://github.com/Yelp/detect-secrets
    rev: <exact-version>
    hooks: [detect-secrets]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: <exact-version>
    hooks:
      - trailing-whitespace
      - end-of-file-fixer
      - check-yaml
      - check-toml
      - check-merge-conflict
```

**Acceptance Criteria:**
1. `pre-commit run --all-files` exits with code 0 on a clean codebase.
2. Adding `password = "hunter2"` to a Python file causes `detect-secrets` hook to fail.
3. All `rev` values are exact (not `latest` or a branch name).
4. `.secrets.baseline` is committed and contains no real secrets.

**Definition of Done:** Both files committed; all four criteria verified.

---

### Task 24 — Developer Documentation

**Scope Areas:** 12 (Developer Documentation)  
**Depends on:** Tasks 1–23 (all)  
**Estimated Size:** Medium (2–4 hours)

**Description:**  
Extend `README.md`, create ADRs, create `CONTRIBUTING.md`, and add the `make docs` / `dev.ps1 docs` target that exports `docs/openapi.json`.

**Deliverables:**
- `README.md` — extended with five sections (original `# DevFlow-AI` heading preserved)
- `CONTRIBUTING.md` — includes dual OS setup, adapter guide (6+ steps including execution mode classification)
- `docs/adr/ADR-0001-modular-monolith.md`
- `docs/adr/ADR-0002-sqlite-for-local-first.md`
- `docs/adr/ADR-0003-alembic-migrations.md`
- `docs/adr/ADR-0004-streamlit-ui.md`
- `scripts/export_openapi.py` — script invoked by `make docs` / `dev.ps1`
- `docs/openapi.json` — committed artefact (generated output)

**README.md sections to add:**
1. Project description and goals
2. Architecture overview (ASCII diagram, links to design.md)
3. Prerequisites (Python 3.12+, Docker v2+, Make or PowerShell 7+)
4. Quick-start (Linux/macOS: `make dev && make test && docker compose up`; Windows: `.\scripts\dev.ps1 -Task dev && .\scripts\dev.ps1 -Task test && .\scripts\dev.ps1 -Task up`)
5. Links to spec documents in `.kiro/specs/`

**CONTRIBUTING.md integration adapter guide (minimum 6 steps):**
1. Determine the `ExecutionMode` for the new integration
2. Add `IntegrationCapability` metadata and add to classification table
3. Define the Protocol (scope methods to match the execution mode; for `cli_handoff`, include request/result types and approval gate)
4. Implement the stub in `adapters/stubs/`
5. Register the stub in `adapters/registry.py`
6. Write unit tests (capability assertions, health_check, action methods, execution mode)
7. Update `CONTRIBUTING.md` integration table

**ADR format (MADR):**
```markdown
# ADR-000X: <Title>
## Status: Accepted
## Context
## Decision
## Consequences
```

**Acceptance Criteria:**
1. `README.md` contains the original `# DevFlow-AI` heading plus all five sections, with both OS quick-start instructions.
2. All four ADR files exist and follow the MADR template.
3. `make docs` (or `.\scripts\dev.ps1 -Task docs`) generates a valid `docs/openapi.json` containing the `/health` endpoint.
4. `CONTRIBUTING.md` integration adapter guide has ≥ 6 numbered steps including the `execution_mode` classification step and a note about `cli_handoff` approval gate requirements.
5. `CONTRIBUTING.md` PR checklist references exact CLI commands for both Make and PowerShell.

**Definition of Done:** All files committed; all five criteria pass.

---

## Definition of Done — Phase 0 Complete

Phase 0 is complete when **all** of the following conditions are met:

### Code Quality
- [ ] `ruff check .` exits with code 0
- [ ] `ruff format --check .` exits with code 0
- [ ] `mypy --strict src/` exits with code 0
- [ ] No TODO, FIXME, or HACK comments in committed code
- [ ] `datetime.utcnow()` does NOT appear in any source file

### Testing
- [ ] `pytest -m "not integration"` exits with code 0
- [ ] `pytest --cov=src --cov-fail-under=80` exits with code 0
- [ ] All 10 Streamlit page smoke tests pass
- [ ] All FastAPI router tests pass offline
- [ ] All adapter stub tests pass, including execution_mode assertions
- [ ] No test creates a `.db` file outside `tmp_path`
- [ ] UTCDateTime round-trip tests pass (UTC, non-UTC, naive rejection, NULL)

### Database
- [ ] `alembic upgrade head` completes on a fresh database
- [ ] `alembic downgrade -1` completes without error
- [ ] Round-trip migration (up → down → up) succeeds against `tmp_path` SQLite (Task 19)
- [ ] `created_at` / `updated_at` values are timezone-aware UTC after SQLite round-trip
- [ ] Naive datetime inputs raise `ValueError` at bind time

### Infrastructure
- [ ] `docker compose build` completes without error (Task 20)
- [ ] `docker compose up -d` starts both services as `healthy` (Task 20)
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok"}` (Task 20)
- [ ] `docker compose port devflow-api 8000` shows `127.0.0.1:8000` (Task 20)
- [ ] The UI container has no volume mounts (Task 20)
- [ ] `docker compose down && docker compose up -d` preserves volume data (Task 20)

### Security
- [ ] `pre-commit run --all-files` exits with code 0
- [ ] `pip-audit -r requirements/base.txt` exits with code 0
- [ ] `bandit -r src/ -ll` exits with code 0
- [ ] `.env` does not appear in `git status`
- [ ] No secret values appear in any committed file
- [ ] `str(settings)` does not reveal any `SecretStr` value

### Developer Experience (Windows)
- [ ] `scripts/dev.ps1 -Task test` runs pytest successfully in PowerShell
- [ ] `scripts/dev.ps1 -Task lint` runs Ruff successfully in PowerShell
- [ ] `scripts/dev.ps1 -Task help` prints all available tasks

### Integration Adapter Contracts
- [ ] All 11 stubs pass `isinstance(stub, BaseAdapterProtocol)`
- [ ] All 11 `health_check()` responses include `execution_mode`
- [ ] Codex stub `execution_mode` is `"cli_handoff"` (not `"automated_api"`)
- [ ] Codex stub exposes `request_code_generation` and `execute_approved_request`
- [ ] Codex stub `execute_approved_request` raises `ValueError` when `approved is False`
- [ ] Codex stub does NOT import `subprocess`
- [ ] Kiro and NotebookLM stubs have no async action methods
- [ ] Antigravity and Stitch stubs have no action methods at all
- [ ] No stub imports `httpx`, `requests`, or `subprocess`
- [ ] `NOTEBOOKLM_API_KEY` does NOT appear in `Settings` or `.env.example`
- [ ] `CODEX_API_KEY` IS present in `Settings` as `SecretStr | None = None` (for future API adapter)

### CI
- [ ] `ci.yml` passes on the `main` branch
- [ ] `security.yml` passes on the `main` branch
- [ ] Coverage artefact uploaded on every CI run

### Documentation
- [ ] `README.md` contains all five sections with dual OS quick-start
- [ ] All four ADR files exist
- [ ] `docs/openapi.json` is present and valid
- [ ] `CONTRIBUTING.md` adapter guide has ≥ 6 steps including `execution_mode` classification and `cli_handoff` approval gate
- [ ] `.env.example` matches the `Settings` class and does NOT contain `NOTEBOOKLM_API_KEY`

---

## Task Summary Table

| Task | Scope Areas | Depends On | Size | Wave |
|---|---|---|---|---|
| 1 | 1, 2 | — | Small | 1 |
| 2 | 1, 2 | 1 | Small | 1 |
| 3 | 2 | 1 | Small | 1 |
| 4 | 2, 12 | 1, 3 | Small | 1 |
| 5 | 7, 11 | 1, 3 | Medium | 2 |
| 6 | 7 | 5 | Small | 2 |
| 7 | 5 | 5 | Medium | 2 |
| 8 | 5 | 7 | Medium | 2 |
| 9 | 6 | 5 | Small | 3 |
| 10 | 4, 7, 11 | 5, 6 | Medium | 3 |
| 11 | 4 | 10, 7 | Medium | 3 |
| 12 | 6 | 5, 6, 9 | Large | 3 |
| 13 | 6 | 12 | Small | 3 |
| 14 | 3 | 5, 6 | Medium | 3 |
| 15 | 8 | 5, 6, 7 | Medium | 4 |
| 16 | 8 | 10, 11, 15 | Medium | 4 |
| 17 | 8 | 12, 13 | Small | 4 |
| 18 | 8 | 14 | Small | 4 |
| 19 | 5, 8 | 8, 15 | Small | 4 |
| 20 | 9 | 10, 14 | Medium | 5 |
| 21 | 10 | 1–19 | Small | 5 |
| 22 | 10, 11 | 1–4 | Small | 5 |
| 23 | 11 | 1–4 | Small | 5 |
| 24 | 12 | 1–23 | Medium | 5 |

---

## Review Findings Response (v1.1.0 → v1.1.1)

| Finding | Action Taken |
|---|---|
| **FIX 1 — Codex `automated_api` → `cli_handoff`** | Task 9 criterion 5 added (`ExecutionMode.CLI_HANDOFF == "cli_handoff"`). Task 12 protocol table updated: Codex is now `cli_handoff` with `CodexCLIRequest`/`CodexCLIResult` types and approval gate; criteria 6, 7, 8 added. Task 13 criterion 3 added for Codex registry entry. Task 16 test updated: `GET /api/v1/integrations/codex/health` asserts `cli_handoff`. Task 17 tests expanded for Codex CLI approval gate and subprocess absence. Definition of Done updated: `cli_handoff` checks added, `automated_api` removed for Codex. |
| **FIX 2 — SQLite UTC round-trip** | Task 7 description and criterion 3 updated to require `UTCDateTime` TypeDecorator; criterion 5 added for naive datetime rejection. Task 15 description updated: test_models.py now covers UTC round-trip, non-UTC timezone, naive rejection, and NULL. Task 15 criterion 3 updated to reference REQ-8.7. Task 15 criterion 6 added (REQ-1.2.4 satisfaction point). Definition of Done: `datetime.utcnow()` prohibition and UTC round-trip checks added. |
| **FIX 3 — Pytest exit code 5** | Task 1 criterion 3 completely rewritten: pytest is NOT run in Task 1; `pyproject.toml` is validated by TOML inspection. Task 1 Definition of Done updated. Task 15 criterion 6 added: this is the first task where `pytest --co -q` succeeds. |
| **FIX 4 — Docker task references** | Task 20 heading and all Definition of Done Docker items explicitly reference Task 20. Cross-checked all 24 tasks — no stale Docker references to any other task number found. Task 18 (Streamlit AppTest) is unchanged. |
