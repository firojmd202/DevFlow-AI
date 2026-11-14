# DevFlow AI — Phase 1: Functional Orchestration Design

**Version:** 1.0.0
**Status:** Draft — Awaiting Independent Review
**Scope:** Phase 1 — Functional Orchestration
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Last Updated:** 2026-11-14
**Supersedes:** _(none — first Phase 1 design)_

---

## 1. Design Principles

Phase 1 extends the Phase 0 modular monolith without structural change. Every design decision below preserves the Phase 0 layering:

```
Streamlit UI → APIClient (httpx) → FastAPI routers → Domain services → Repositories → SQLite
                                                   → Adapter registry → Live/stub adapters → External APIs
```

Five rules govern every Phase 1 design decision:

1. **Phase 0 contracts are immutable.** No Phase 0 router, model, schema, or adapter interface changes signature.
2. **Stubs survive Phase 1.** Live adapters augment the registry; stub adapters remain available as fallbacks.
3. **Approval gates are non-bypassable.** Consequential actions cannot proceed without an explicit `confirmed=True` body field or a resolved `ApprovalRequest`.
4. **Secrets never leave `Settings`.** Live adapters read credentials only from `SecretStr` fields; `RedactSecretsProcessor` runs on every log record.
5. **Tests are offline-first.** Live adapter tests mock `httpx.AsyncClient` and MCP subprocess interactions.

---

## 2. Architecture Diagram (Phase 1)

```
  Developer Machine — 127.0.0.1 only
  ┌────────────────────────────────────────────────────────────────────────────┐
  │                                                                              │
  │  Browser :8501                              CLI / Postman :8000             │
  │      │                                              │                        │
  │  ════╪══════════════════════════════════════════════╪════════════════════   │
  │      │  Docker bridge                               │                        │
  │  ┌───▼─────────────────────┐       ┌───────────────▼────────────────────┐  │
  │  │  devflow-ui (Streamlit) │       │  devflow-api (FastAPI/Uvicorn)     │  │
  │  │                          │       │                                      │  │
  │  │  Phase 1 pages:          │       │  Routers (/api/v1/):               │  │
  │  │  1_Dashboard (live data) │       │   projects (live CRUD)             │  │
  │  │  2_Projects (live CRUD)  │       │   learning (live CRUD)             │  │
  │  │  6_Workflows (new)       │──────▶│   workflows (new)                  │  │
  │  │  7_History (new)         │       │   approvals (new)                  │  │
  │  │  9_Integrations (live)   │       │   repositories (new)               │  │
  │  │  10_Settings (extended)  │       │   integrations (extended)          │  │
  │  │                          │       │   health                           │  │
  │  │  APIClient (extended)    │       │                                      │  │
  │  └──────────────────────────┘       │  Services (new):                   │  │
  │                                      │   ProjectService                   │  │
  │                                      │   WorkflowService                  │  │
  │                                      │   ApprovalService                  │  │
  │                                      │   RepositoryService                │  │
  │                                      │                                      │  │
  │                                      │  Repositories (new):               │  │
  │                                      │   ProjectRepository                │  │
  │                                      │   WorkflowRepository               │  │
  │                                      │   ApprovalRepository               │  │
  │                                      │   RepositoryConfigRepository       │  │
  │                                      │                                      │  │
  │                                      │  Adapter Registry (extended):      │  │
  │                                      │   get_live() → live | stub         │  │
  │                                      │   GitHubAdapter (live)             │  │
  │                                      │   OllamaAdapter (live)             │  │
  │                                      │   FigmaAdapter (live)              │  │
  │                                      │   MCPLiveAdapter (new)             │  │
  │                                      │   + 7 stubs (unchanged)            │  │
  │                                      │                                      │  │
  │                                      │  MCPClient                         │  │
  │                                      │   subprocess → MCP servers         │  │
  │                                      │                                      │  │
  │                                      │  SQLAlchemy async + aiosqlite      │  │
  │                                      └──────────────────┬─────────────────┘  │
  │                                                          │                     │
  │                                              ┌───────────▼──────────┐         │
  │                                              │  devflow-data volume  │         │
  │                                              │  /data/devflow.db     │         │
  │                                              └───────────────────────┘         │
  └────────────────────────────────────────────────────────────────────────────────┘

  External (requires network + credentials):
  GitHub REST API  ←──  GitHubAdapter
  Figma REST API   ←──  FigmaAdapter
  Ollama :11434    ←──  OllamaAdapter (local, no key)
  MCP servers      ←──  MCPClient (local subprocesses)
```

---

## 3. New Database Schema

### 3.1 Addition to projects table

```sql
-- Migration 005
ALTER TABLE projects ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]';
```

The `Project` model gains `tags_json: Mapped[str] = mapped_column(Text, server_default="[]")`. The `ProjectResponse` schema deserialises `tags_json` via a `@model_validator` into `tags: list[str]`.

### 3.2 workflows

```sql
CREATE TABLE workflows (
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,
    name             TEXT     NOT NULL,
    description      TEXT,
    project_id       INTEGER  REFERENCES projects(id) ON DELETE SET NULL,
    status           TEXT     NOT NULL DEFAULT 'draft'
                              CHECK (status IN ('draft','active','paused','completed','failed')),
    definition_json  TEXT,
    created_at       DATETIME NOT NULL,
    updated_at       DATETIME NOT NULL
);
```

### 3.3 workflow_runs

```sql
CREATE TABLE workflow_runs (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    workflow_id     INTEGER  NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status          TEXT     NOT NULL DEFAULT 'pending'
                             CHECK (status IN (
                                 'pending','running','waiting_approval',
                                 'completed','failed','cancelled')),
    started_at      DATETIME,
    completed_at    DATETIME,
    result_json     TEXT,
    error_message   TEXT,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL
);
```

### 3.4 approval_requests

```sql
CREATE TABLE approval_requests (
    id                  INTEGER  PRIMARY KEY AUTOINCREMENT,
    workflow_run_id     INTEGER  NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_name           TEXT     NOT NULL,
    action_description  TEXT     NOT NULL,
    payload_json        TEXT,
    status              TEXT     NOT NULL DEFAULT 'pending'
                                 CHECK (status IN ('pending','approved','rejected','expired')),
    requested_at        DATETIME NOT NULL,
    resolved_at         DATETIME,
    resolved_by         TEXT,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);
```

### 3.5 workflow_audit_log

```sql
CREATE TABLE workflow_audit_log (
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,
    workflow_run_id  INTEGER  REFERENCES workflow_runs(id) ON DELETE SET NULL,
    event_type       TEXT     NOT NULL,
    actor            TEXT     NOT NULL,
    payload_json     TEXT,
    created_at       DATETIME NOT NULL
);
CREATE INDEX idx_audit_run_id ON workflow_audit_log(workflow_run_id);
CREATE INDEX idx_audit_created ON workflow_audit_log(created_at);
```

### 3.6 repository_configs

```sql
CREATE TABLE repository_configs (
    id              INTEGER  PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER  NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    owner           TEXT     NOT NULL,
    repo            TEXT     NOT NULL,
    default_branch  TEXT     NOT NULL DEFAULT 'main',
    is_active       BOOLEAN  NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    UNIQUE (project_id, owner, repo)
);
```

---

## 4. Repository Layer

Each domain entity has a typed repository in `src/devflow_api/repositories/`. All repositories extend `BaseRepository[ModelT]` from Phase 0.

### 4.1 ProjectRepository (`repositories/project.py`)

```python
class ProjectRepository(BaseRepository[Project]):
    async def list_filtered(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Project]: ...

    async def update_tags(self, id: int, tags: list[str]) -> Project | None: ...
```

### 4.2 WorkflowRepository (`repositories/workflow.py`)

```python
class WorkflowRepository(BaseRepository[Workflow]):
    async def list_by_project(self, project_id: int) -> list[Workflow]: ...
    async def list_by_status(self, status: str) -> list[Workflow]: ...

class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    async def list_by_workflow(self, workflow_id: int) -> list[WorkflowRun]: ...
    async def transition_status(
        self,
        run_id: int,
        new_status: str,
        valid_from: list[str],
    ) -> WorkflowRun: ...
    # Raises InvalidStatusTransitionError if current status not in valid_from
```

### 4.3 ApprovalRepository (`repositories/approval.py`)

```python
class ApprovalRepository(BaseRepository[ApprovalRequest]):
    async def list_pending(self) -> list[ApprovalRequest]: ...
    async def resolve(
        self,
        approval_id: int,
        decision: Literal["approved", "rejected"],
        resolved_by: str | None,
    ) -> ApprovalRequest: ...
    # Raises ApprovalAlreadyResolvedError if status != "pending"

class AuditLogRepository(BaseRepository[WorkflowAuditLog]):
    async def log_event(
        self,
        event_type: str,
        actor: str,
        workflow_run_id: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> WorkflowAuditLog: ...

    async def list_for_run(self, run_id: int) -> list[WorkflowAuditLog]: ...
```

### 4.4 RepositoryConfigRepository (`repositories/repository_config.py`)

```python
class RepositoryConfigRepository(BaseRepository[RepositoryConfig]):
    async def list_by_project(self, project_id: int) -> list[RepositoryConfig]: ...
    async def get_by_coords(
        self, project_id: int, owner: str, repo: str
    ) -> RepositoryConfig | None: ...
```

---

## 5. Service Layer

Services own business logic, coordinate repositories, and generate audit log entries. They do NOT call adapters directly — routers inject adapters from `app.state.adapter_registry`.

### 5.1 WorkflowService (`services/workflow.py`)

```python
class WorkflowService:
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        run_repo: WorkflowRunRepository,
        audit_repo: AuditLogRepository,
    ) -> None: ...

    async def create_run(self, workflow_id: int) -> WorkflowRun:
        """Creates a WorkflowRun with status=pending and logs run_created."""

    async def transition_run(
        self,
        run_id: int,
        new_status: str,
        actor: str,
        payload: dict[str, object] | None = None,
    ) -> WorkflowRun:
        """Transitions run status and logs run_status_changed."""
```

### 5.2 ApprovalService (`services/approval.py`)

```python
class ApprovalService:
    def __init__(
        self,
        approval_repo: ApprovalRepository,
        run_repo: WorkflowRunRepository,
        audit_repo: AuditLogRepository,
    ) -> None: ...

    async def request_approval(
        self,
        run_id: int,
        step_name: str,
        action_description: str,
        payload: dict[str, object] | None = None,
    ) -> ApprovalRequest:
        """Creates ApprovalRequest and transitions run to waiting_approval."""

    async def resolve(
        self,
        approval_id: int,
        decision: Literal["approved", "rejected"],
        resolved_by: str | None,
    ) -> tuple[ApprovalRequest, WorkflowRun]:
        """
        Resolves approval and transitions run:
        - approved → run transitions to running
        - rejected → run transitions to cancelled
        Raises ApprovalAlreadyResolvedError if already resolved.
        Logs approval_resolved audit event.
        """
```

---

## 6. Adapter Registry Extension

The Phase 0 `AdapterRegistry` is extended with a `get_live` method. The existing `get` method is unchanged.

```python
# src/devflow_api/adapters/registry.py

class AdapterRegistry:
    # Existing Phase 0 method (unchanged):
    def get(self, name: str) -> BaseAdapterProtocol:
        """Always returns the stub adapter."""

    # New Phase 1 method:
    def get_live(self, name: str) -> BaseAdapterProtocol:
        """
        Returns the live adapter for `name` if one is registered and
        can be initialised from current Settings.
        Falls back to the stub adapter when:
        - no live adapter is registered for this name
        - the live adapter raises MissingCredentialError during init
        Never raises; always returns a valid adapter instance.
        """

    def register_live(self, name: str, adapter: BaseAdapterProtocol) -> None:
        """Register a live adapter. Called at app startup for each configured integration."""
```

**Live adapter registration in `create_app()`:**
```python
# src/devflow_api/main.py — inside create_app()
from devflow_api.adapters.live.github import GitHubAdapter
from devflow_api.adapters.live.ollama import OllamaAdapter
from devflow_api.adapters.live.figma import FigmaAdapter
from devflow_api.adapters.live.mcp_live import MCPLiveAdapter

if settings.GITHUB_TOKEN:
    registry.register_live("github", GitHubAdapter(settings))
if settings.FIGMA_TOKEN:
    registry.register_live("figma", FigmaAdapter(settings))
registry.register_live("ollama", OllamaAdapter(settings))  # no key required
if mcp_configs := MCPServerConfig.from_settings(settings):
    registry.register_live("mcp", MCPLiveAdapter(mcp_client=MCPClient(mcp_configs)))
```

### 6.1 Live adapter directory structure

```
src/devflow_api/adapters/
    live/
        __init__.py
        github.py       — GitHubAdapter
        ollama.py       — OllamaAdapter
        figma.py        — FigmaAdapter
        mcp_live.py     — MCPLiveAdapter
```

### 6.2 Live adapter interface contract

Each live adapter:
- Accepts a `Settings` instance in `__init__`
- Implements the same `Protocol` as its stub counterpart
- Sets `stub=False` in all response objects
- Has no `ClassVar` capability — capability is a `@property` returning `IntegrationCapability(available_in_phase_0=True)`

---

## 7. MCP Client Design

### 7.1 MCPServerConfig

```python
# src/devflow_api/adapters/mcp_client.py

class MCPServerConfig(BaseModel):
    name: str
    command: list[str]
    args: list[str] = []
    env: dict[str, str] = {}           # supports ${SECRET_NAME} interpolation
    timeout_seconds: int = 30
    enabled: bool = True
    allowed_tools: list[str] = ["*"]   # "*" means all tools permitted

    @classmethod
    def from_settings(cls, settings: Settings) -> list[MCPServerConfig]:
        """Parse settings.MCP_SERVERS_CONFIG JSON. Returns [] on empty string."""
```

### 7.2 MCPClient

```python
class MCPClient:
    def __init__(self, configs: list[MCPServerConfig]) -> None: ...

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
    ) -> MCPToolResult:
        """
        1. Resolve server config by name (raises MCPServerNotFoundError if absent).
        2. Check tool against allowed_tools (raises MCPPermissionError if denied).
        3. Interpolate env secrets (raises MCPSecretResolutionError if unresolvable).
        4. Launch subprocess via MCP SDK stdio_client.
        5. Call tool with timeout_seconds.
        6. Terminate subprocess in finally block.
        7. Log invocation (keys only, not values).
        """
```

### 7.3 MCP result type

```python
class MCPToolResult(BaseModel):
    content: list[dict[str, object]]
    is_error: bool = False
    stub: bool = False
```

### 7.4 MCP exceptions

```python
# Added to src/devflow_api/adapters/exceptions.py

class MCPServerNotFoundError(DevFlowError):
    server_name: str

class MCPConnectionError(DevFlowError):
    server_name: str
    cause: str

class MCPTimeoutError(DevFlowError):
    server_name: str
    tool_name: str
    timeout_seconds: int

class MCPPermissionError(DevFlowError):
    server_name: str
    tool_name: str

class MCPSecretResolutionError(DevFlowError):
    key_name: str
```

---

## 8. GitHub Service Design

The GitHub integration is split into two concerns:
- `GitHubAdapter` — low-level REST API calls (lives in `adapters/live/github.py`)
- `RepositoryService` — business logic, confirmation gates, audit logging (lives in `services/repository.py`)

### 8.1 GitHubAdapter (live)

```python
class GitHubAdapter:
    def __init__(self, settings: Settings) -> None:
        self._token = settings.GITHUB_TOKEN   # SecretStr | None
        self._client_timeout = httpx.Timeout(10.0)

    async def _headers(self) -> dict[str, str]:
        if self._token is None:
            raise MissingCredentialError("github", "GITHUB_TOKEN")
        return {"Authorization": f"token {self._token.get_secret_value()}"}

    async def create_issue(self, repo: str, title: str, body: str) -> GitHubIssueResponse: ...
    async def list_branches(self, owner: str, repo: str) -> list[BranchSummary]: ...
    async def get_branch_status(self, owner: str, repo: str, branch: str) -> BranchStatus: ...
    async def list_pull_requests(self, owner: str, repo: str) -> list[PullRequestSummary]: ...
    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequestSummary: ...
    async def create_branch(self, owner: str, repo: str, name: str, base_sha: str) -> BranchSummary: ...
    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str, body: str = ""
    ) -> PullRequestSummary: ...
    async def get_check_runs(self, owner: str, repo: str, ref: str) -> list[CheckRunSummary]: ...
```

### 8.2 RepositoryService

```python
class RepositoryService:
    def __init__(
        self,
        repo_config_repo: RepositoryConfigRepository,
        audit_repo: AuditLogRepository,
        github_adapter: GitHubAdapter | GitHubStubAdapter,
    ) -> None: ...

    async def create_branch(
        self,
        repo_config_id: int,
        name: str,
        base_ref: str,
        confirmed: bool,
    ) -> BranchSummary:
        """Raises ConfirmationRequiredError if confirmed=False."""

    async def create_pull_request(
        self,
        repo_config_id: int,
        title: str,
        head: str,
        base: str,
        body: str,
        confirmed: bool,
    ) -> PullRequestSummary:
        """Raises ConfirmationRequiredError if confirmed=False. No merge support."""
```

---

## 9. Workflow State Machine

```
                     ┌─────────┐
                     │  draft  │
                     └────┬────┘
                          │ activate
                     ┌────▼────┐
                  ┌──│  active │──┐
                  │  └────┬────┘  │
            pause │       │ run   │ fail
                  │  ┌────▼─────┐ │
                  │  │ running  │ │
                  │  └──┬───┬───┘ │
                  │     │   │     │
          waiting │     │   │ complete/fail
              appr│     │   └──────────────────┐
                  │  ┌──▼──────────────────┐    │
                  │  │  waiting_approval   │    │
                  │  └──┬──────────────────┘    │
                  │     │ approved/rejected      │
                  │  ┌──▼────────────────────┐  │
                  └─▶│  paused               │  │
                     └───────────────────────┘  │
                                                 │
                     ┌──────────┐  ┌────────────▼┐
                     │cancelled │  │  completed   │
                     └──────────┘  └─────────────┘
```

**WorkflowRun valid transitions:**
| From | To | Trigger |
|---|---|---|
| `pending` | `running` | `WorkflowService.transition_run` |
| `running` | `waiting_approval` | approval gate reached |
| `running` | `completed` | all steps complete |
| `running` | `failed` | step raises exception |
| `waiting_approval` | `running` | approval approved |
| `waiting_approval` | `cancelled` | approval rejected |
| `running` | `cancelled` | user cancels |

Invalid transitions return `HTTP 422` with `code = "INVALID_STATUS_TRANSITION"`.

---

## 10. API Contracts (Phase 1 New Routes)

All routes follow the Phase 0 convention: prefixed `/api/v1/`, JSON bodies, `ErrorResponse` on errors.

### 10.1 Projects (extended)

```
GET    /api/v1/projects              ?status&limit&offset  → list[ProjectResponse]
POST   /api/v1/projects                                    → ProjectResponse        201
GET    /api/v1/projects/{id}                               → ProjectResponse        200 | 404
PUT    /api/v1/projects/{id}                               → ProjectResponse        200 | 404 | 422
DELETE /api/v1/projects/{id}                               → 204 | 404
```

### 10.2 Workflows (new)

```
GET    /api/v1/workflows             ?project_id&status    → list[WorkflowResponse]
POST   /api/v1/workflows                                   → WorkflowResponse       201
GET    /api/v1/workflows/{id}                              → WorkflowResponse       200 | 404
PUT    /api/v1/workflows/{id}                              → WorkflowResponse       200 | 404 | 422
DELETE /api/v1/workflows/{id}                              → 204 | 404
POST   /api/v1/workflows/{id}/runs                         → WorkflowRunResponse    201
GET    /api/v1/workflows/{id}/runs                         → list[WorkflowRunResponse]
GET    /api/v1/workflow-runs/{run_id}                      → WorkflowRunResponse    200 | 404
GET    /api/v1/workflow-runs/{run_id}/audit                → list[AuditLogEntry]    200 | 404
```

### 10.3 Approvals (new)

```
GET    /api/v1/approvals             ?status               → list[ApprovalResponse]
GET    /api/v1/approvals/{id}                              → ApprovalResponse       200 | 404
POST   /api/v1/approvals/{id}/resolve                      → ApprovalResponse       200 | 404 | 409
```

`resolve` body: `{"decision": "approved" | "rejected", "resolved_by": str | null}`

### 10.4 Repositories (new)

```
GET    /api/v1/repositories          ?project_id           → list[RepositoryConfigResponse]
POST   /api/v1/repositories                                → RepositoryConfigResponse  201 | 409
GET    /api/v1/repositories/{id}                           → RepositoryConfigResponse  200 | 404
DELETE /api/v1/repositories/{id}                           → 204 | 404
GET    /api/v1/repositories/{id}/branches                  → list[BranchSummary]       200 | 403 | 502
GET    /api/v1/repositories/{id}/branches/{branch}/status  → BranchStatus              200 | 403 | 404 | 502
GET    /api/v1/repositories/{id}/branches/{branch}/ci      → list[CheckRunSummary]     200 | 403 | 404 | 502
POST   /api/v1/repositories/{id}/branches                  → BranchSummary            201 | 403 | 409 | 422 | 502
GET    /api/v1/repositories/{id}/pull-requests             → list[PullRequestSummary]  200 | 403 | 502
POST   /api/v1/repositories/{id}/pull-requests             → PullRequestSummary        201 | 403 | 422 | 502
GET    /api/v1/repositories/{id}/pull-requests/{pr_number} → PullRequestSummary        200 | 403 | 404 | 502
```

**No `/merge` endpoint exists.**

### 10.5 Integrations (extended)

```
GET /api/v1/integrations                 → list[IntegrationSummary]       (unchanged schema)
GET /api/v1/integrations/{name}/health   → IntegrationHealthResponse      (now returns live status)
```

`IntegrationSummary` gains `mode: Literal["live", "stub"]` field in Phase 1.

---

## 11. Pydantic v2 Schema Additions

### 11.1 ProjectResponse (extended)

```python
class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    status: Literal["active", "archived", "completed"]
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

Serializer note: `created_at` and `updated_at` MUST be serialised as ISO 8601 with UTC offset. Use `model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})`.

### 11.2 WorkflowResponse

```python
class WorkflowResponse(BaseModel):
    id: int
    name: str
    description: str | None
    project_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 11.3 WorkflowRunResponse

```python
class WorkflowRunResponse(BaseModel):
    id: int
    workflow_id: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    pending_approvals: list[ApprovalResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 11.4 ApprovalResponse

```python
class ApprovalResponse(BaseModel):
    id: int
    workflow_run_id: int
    step_name: str
    action_description: str
    status: str
    requested_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None

    model_config = ConfigDict(from_attributes=True)
```

---

## 12. Streamlit Page Design

### 12.1 Page inventory (Phase 1)

| File | Phase 0 state | Phase 1 state |
|---|---|---|
| `1_Dashboard.py` | Placeholder | Live metrics (projects, workflows, approvals) |
| `2_Projects.py` | Placeholder | Live CRUD |
| `3_Learning.py` | Placeholder | Remains placeholder (Phase 2 scope) |
| `4_Specifications.py` | Placeholder | Remains placeholder (Phase 2 scope) |
| `5_Design.py` | Placeholder | Remains placeholder (Phase 2 scope) |
| `6_Coding.py` | Placeholder | Renamed `6_Workflows.py` — live workflows |
| `7_Testing.py` | Placeholder | Renamed `7_History.py` — execution history |
| `8_Documentation.py` | Placeholder | Remains placeholder (Phase 2 scope) |
| `9_Integrations.py` | Placeholder | Live integration status |
| `10_Settings.py` | Health check | Extended with integration/MCP/GitHub status |

**Page numbering note:** Pages 6 and 7 are renamed to reflect their Phase 1 function. The numeric prefix determines navigation order. `app.py` navigation registration is updated to match.

### 12.2 APIClient extension strategy

`APIClient` grows from one method (`get_health`) to a full typed client. Each method follows the Phase 0 contract: returns `None` on any error, logs a warning, never raises.

```python
class APIClient:
    # Phase 0 (unchanged)
    async def get_health(self) -> dict[str, str] | None: ...

    # Phase 1 — projects
    async def list_projects(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict[str, object]] | None: ...
    async def create_project(
        self, name: str, description: str | None = None, tags: list[str] | None = None
    ) -> dict[str, object] | None: ...
    async def update_project(
        self, project_id: int, **fields: object
    ) -> dict[str, object] | None: ...
    async def delete_project(self, project_id: int) -> bool: ...

    # Phase 1 — workflows
    async def list_workflows(
        self, project_id: int | None = None, status: str | None = None
    ) -> list[dict[str, object]] | None: ...
    async def create_workflow(self, name: str, project_id: int | None = None) -> dict[str, object] | None: ...
    async def create_run(self, workflow_id: int) -> dict[str, object] | None: ...

    # Phase 1 — approvals
    async def list_approvals(self, status: str = "pending") -> list[dict[str, object]] | None: ...
    async def resolve_approval(
        self, approval_id: int, decision: str, resolved_by: str | None = None
    ) -> dict[str, object] | None: ...

    # Phase 1 — integrations
    async def list_integrations(self) -> list[dict[str, object]] | None: ...
    async def get_integration_health(self, name: str) -> dict[str, object] | None: ...
```

---

## 13. New File Layout

Phase 1 adds these files. No Phase 0 file is deleted or renamed (except the two Streamlit page renames, which are file renames only — no content from other pages is affected).

```
src/devflow_api/
    models/
        workflow.py          (new — Workflow, WorkflowRun)
        approval.py          (new — ApprovalRequest)
        audit.py             (new — WorkflowAuditLog)
        repository.py        (new — RepositoryConfig)

    repositories/
        project.py           (extended — list_filtered, update_tags)
        workflow.py          (new — WorkflowRepository, WorkflowRunRepository)
        approval.py          (new — ApprovalRepository, AuditLogRepository)
        repository_config.py (new — RepositoryConfigRepository)

    services/
        project.py           (new — ProjectService)
        workflow.py          (new — WorkflowService)
        approval.py          (new — ApprovalService)
        repository.py        (new — RepositoryService)

    routers/
        projects.py          (replace stub with live DB calls)
        workflows.py         (new)
        approvals.py         (new)
        repositories.py      (new)
        integrations.py      (extended — live health, mode field)

    schemas/
        project.py           (extended — tags, created_at, updated_at)
        workflow.py          (new — WorkflowResponse, WorkflowRunResponse)
        approval.py          (new — ApprovalResponse)
        repository.py        (new — RepositoryConfigResponse, BranchSummary, etc.)

    adapters/
        live/
            __init__.py      (new)
            github.py        (new — GitHubAdapter)
            ollama.py        (new — OllamaAdapter)
            figma.py         (new — FigmaAdapter)
            mcp_live.py      (new — MCPLiveAdapter)
        mcp_client.py        (new — MCPServerConfig, MCPClient, MCPToolResult)
        exceptions.py        (extended — IntegrationExecutionError, MCP errors)
        registry.py          (extended — get_live, register_live)

alembic/versions/
    002_add_workflow_tables.py     (new)
    003_add_approval_audit_tables.py (new)
    004_add_repository_tables.py   (new)
    005_add_project_tags_column.py (new)

src/devflow_ui/
    api_client.py            (extended — all Phase 1 methods)
    pages/
        1_Dashboard.py       (replaced — live metrics)
        2_Projects.py        (replaced — live CRUD)
        6_Workflows.py       (renamed from 6_Coding.py + implemented)
        7_History.py         (renamed from 7_Testing.py + implemented)
        9_Integrations.py    (replaced — live integration status)
        10_Settings.py       (extended — integration/MCP/GitHub status)

tests/
    unit/
        test_project_service.py      (new)
        test_workflow_service.py     (new)
        test_approval_service.py     (new)
        test_repository_service.py   (new)
        test_live_adapters.py        (new — mocked httpx)
        test_mcp_client.py           (new — mocked subprocess)
        test_github_router.py        (new)
        test_workflows_router.py     (new)
        test_approvals_router.py     (new)
        test_repositories_router.py  (new)
    smoke/
        test_ui_pages.py             (extended — new page smoke tests)
    integration/
        test_database.py             (extended — Phase 1 migration round-trips)
```

---

## 14. Security Design

### 14.1 Confirmation gate pattern

All destructive or external actions use this pattern in the router:

```python
@router.post("/{id}/branches")
async def create_branch(
    id: int,
    body: CreateBranchRequest,
    # ...
) -> BranchSummary:
    if not body.confirmed:
        raise HTTPException(
            status_code=422,
            detail={"error": "Branch creation requires explicit confirmation", "code": "CONFIRMATION_REQUIRED"},
        )
    return await repo_service.create_branch(id, body.name, body.base_ref, confirmed=True)
```

### 14.2 Approval gate pattern

Workflow steps that touch external resources create an `ApprovalRequest` before proceeding:

```python
# WorkflowService
approval = await approval_service.request_approval(
    run_id=run.id,
    step_name="create_branch",
    action_description=f"Create branch '{branch_name}' from '{base_ref}' in {owner}/{repo}",
    payload={"owner": owner, "repo": repo, "branch_name": branch_name, "base_ref": base_ref},
)
# execution pauses here; resumes only when approval.status == "approved"
```

### 14.3 Credential flow

```
Environment / .env
    ↓
Settings (pydantic-settings, SecretStr)
    ↓
GitHubAdapter.__init__(settings) — stores SecretStr reference
    ↓
GitHubAdapter._headers() — calls .get_secret_value() only at request time
    ↓
httpx.AsyncClient — uses header value in-memory only
    ↓
structlog — RedactSecretsProcessor strips all secret values before emission
```

### 14.4 MCP subprocess isolation

```python
resolved_env = {
    k: _resolve_secret(v, settings)   # interpolates ${SECRET_NAME}
    for k, v in config.env.items()
}
# Launch with explicit env, not inheriting parent process environment
proc = await asyncio.create_subprocess_exec(
    *config.command, *config.args,
    env=resolved_env,                  # explicit, isolated env
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

---

## 15. Error Handling Extensions

Phase 0 `add_error_handlers` is extended with three new handlers:

| Exception | HTTP Status | Code |
|---|---|---|
| `IntegrationExecutionError` | 502 | `INTEGRATION_ERROR` |
| `MissingCredentialError` | 403 | `MISSING_CREDENTIAL` |
| `ConfirmationRequiredError` | 422 | `CONFIRMATION_REQUIRED` |
| `ApprovalAlreadyResolvedError` | 409 | `APPROVAL_ALREADY_RESOLVED` |
| `InvalidStatusTransitionError` | 422 | `INVALID_STATUS_TRANSITION` |
| `MCPServerNotFoundError` | 404 | `MCP_SERVER_NOT_FOUND` |
| `MCPPermissionError` | 403 | `MCP_PERMISSION_DENIED` |
| `MCPTimeoutError` | 504 | `MCP_TIMEOUT` |

---

## 16. Observability

Every service operation emits a structured log entry. Structlog context variables carry `request_id` (from Phase 0 middleware) through all nested calls.

Key log events:
| Event | Level | Fields |
|---|---|---|
| Project created | INFO | `project_id`, `name` |
| Workflow run created | INFO | `run_id`, `workflow_id` |
| Status transition | INFO | `run_id`, `from_status`, `to_status` |
| Approval requested | INFO | `approval_id`, `run_id`, `step_name` |
| Approval resolved | INFO | `approval_id`, `decision`, `resolved_by` |
| Integration call | INFO | `integration`, `action`, `duration_ms`, `stub` |
| MCP tool call | INFO | `server`, `tool`, `arg_keys`, `duration_ms`, `success` |
| Credential missing | WARNING | `integration`, `credential_key` (NOT value) |
| External HTTP error | WARNING | `integration`, `status_code`, `url` (NOT body) |

---

## 17. Dependency on Phase 0

Phase 1 depends on the following Phase 0 components without modification:
- `devflow_core.config.Settings` — extended with new fields only
- `devflow_core.logging.configure_logging` — unchanged
- `devflow_api.models.base.UTCDateTime` — reused for all new timestamp columns
- `devflow_api.models.base.TimestampMixin` — applied to all new models
- `devflow_api.database.get_db` — unchanged dependency injection
- `devflow_api.adapters.capability.IntegrationCapability` — unchanged schema
- `devflow_api.adapters.protocols.*` — all 11 unchanged
- `devflow_api.adapters.stubs.*` — all 11 remain; stubs are fallbacks
- `devflow_api.adapters.registry.AdapterRegistry` — `get()` method unchanged

New `Settings` fields added in Phase 1:
```python
OLLAMA_TIMEOUT_SECONDS: int = 30
GITHUB_API_BASE_URL: str = "https://api.github.com"
FIGMA_API_BASE_URL: str = "https://api.figma.com"
MCP_SERVERS_CONFIG: str = ""   # Already present in Phase 0; validator added in Phase 1
```

---

## 18. Architectural Decision Records (Phase 1)

### ADR-0005: Approval gate over direct API calls for consequential actions
**Decision:** Any action that creates or modifies a Git branch, PR, or external resource requires either `confirmed=True` in the request body (direct API call) or a resolved `ApprovalRequest` (workflow path).
**Rationale:** Prevents accidental execution of destructive operations. Aligns with the Phase 0 Codex two-phase approval model extended to all external mutations.
**Alternatives considered:** Role-based access control — deferred (single-user local tool), OAuth tokens — deferred.

### ADR-0006: Live adapters as registry augmentation (not replacement)
**Decision:** Live adapters are registered alongside stubs via `register_live`. `get_live()` falls back to stubs when live init fails.
**Rationale:** Tests that run without credentials continue to use stub adapters. The registry never raises; it always returns a usable adapter.
**Alternatives considered:** Conditional adapter class selection at startup — rejected (harder to test, creates tight coupling to Settings at import time).

### ADR-0007: MCP servers as subprocesses (stdio transport)
**Decision:** Use MCP Python SDK's `stdio_client` transport. Each tool call spawns and terminates a fresh process.
**Rationale:** stdio is the universal MCP transport. Persistent process management (SSE) is deferred to Phase 2 when connection pooling requirements are clearer.
**Alternatives considered:** SSE transport — deferred. HTTP transport — not universally supported by MCP servers.

### ADR-0008: Workflow state machine in service layer, not database
**Decision:** Status transition validation lives in `WorkflowRunRepository.transition_status`, not in a DB trigger or constraint.
**Rationale:** SQLite has limited trigger support. Python-side validation is testable with standard pytest. Invalid transitions return 422 HTTP errors, not DB exceptions.
