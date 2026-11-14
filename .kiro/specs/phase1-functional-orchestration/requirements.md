# DevFlow AI — Phase 1: Functional Orchestration Requirements

**Version:** 1.0.0
**Status:** Draft — Awaiting Independent Review
**Scope:** Phase 1 — Functional Orchestration
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Last Updated:** 2026-11-14
**Supersedes:** _(none — first Phase 1 specification)_

---

## Overview

Phase 1 is the first functional release of DevFlow AI. It replaces Phase 0 stubs with real, database-backed behaviour across five areas: persistent project management, AI workflow orchestration, integration execution, MCP client infrastructure, and GitHub workflow support. The Streamlit UI is upgraded from placeholder pages to working project and workflow interfaces.

Phase 1 builds exclusively on the Phase 0 foundation. It does not replace, rename, or restructure any approved Phase 0 module.

### Global Constraints (apply to all requirements below)

- The application MUST remain local-first with free core functionality.
- The codebase MUST NOT contain Android, React, TypeScript, or Vite artefacts.
- No hardcoded credentials or secrets MUST appear in source control at any time.
- All development services MUST bind exclusively to `127.0.0.1` on the host interface.
- Architecture boundaries from Phase 0 (UI → API → domain services → adapters → storage) MUST be preserved.
- Phase 0 specification files MUST NOT be modified.
- Phase 0 tests MUST continue to pass without modification.
- Every task MUST be small enough to be independently testable.
- Consequential actions (modifying files, Git branches, PRs, external resources) MUST require explicit user approval before execution.
- `datetime.utcnow()` MUST NOT appear anywhere in Phase 1 code; use `datetime.now(UTC)` exclusively.
- All new timestamp columns MUST use `UTCDateTime` TypeDecorator from `src/devflow_api/models/base.py`.

---

## Area 1 — Persistent Project Management

### REQ-P1.1
WHEN a user submits a valid project creation request,
THEN the FastAPI `POST /api/v1/projects` endpoint MUST persist the project to SQLite via the `ProjectRepository` and return the created `ProjectResponse` with a database-assigned `id`, `created_at`, and `updated_at`.

**Acceptance Criteria:**
P1.1.1 — `POST /api/v1/projects` with `{"name": "My Project"}` returns HTTP 201 with a `ProjectResponse` containing a non-zero `id` and ISO 8601 UTC timestamps for `created_at` and `updated_at`.
P1.1.2 — A subsequent `GET /api/v1/projects/{id}` returns the same project.
P1.1.3 — `POST /api/v1/projects` with an empty `name` field returns HTTP 422.
P1.1.4 — Two `POST` requests with identical names produce two separate records with distinct `id` values (names are not unique-constrained at the data layer).
P1.1.5 — The `ProjectRepository.create` method is covered by a unit test using an in-memory SQLite database.

### REQ-P1.2
WHEN a user requests the project list,
THEN `GET /api/v1/projects` MUST return all persisted projects from the database, support optional `status` filter and `limit`/`offset` pagination query parameters, and return an empty list (not an error) when no projects exist.

**Acceptance Criteria:**
P1.2.1 — `GET /api/v1/projects` returns HTTP 200 with a JSON array.
P1.2.2 — `GET /api/v1/projects?status=active` returns only projects with `status == "active"`.
P1.2.3 — `GET /api/v1/projects?limit=5&offset=0` returns at most 5 items.
P1.2.4 — `GET /api/v1/projects?status=invalid_value` returns HTTP 422.
P1.2.5 — `GET /api/v1/projects` on an empty database returns `[]` with HTTP 200.

### REQ-P1.3
WHEN a user updates a project,
THEN `PUT /api/v1/projects/{id}` MUST update only the provided fields in the database, update the `updated_at` timestamp to the current UTC time, and return the full updated `ProjectResponse`.

**Acceptance Criteria:**
P1.3.1 — `PUT /api/v1/projects/{id}` with changed `name` returns HTTP 200 with the updated name.
P1.3.2 — `updated_at` in the response is strictly later than `created_at` after a successful update.
P1.3.3 — `PUT /api/v1/projects/9999` returns HTTP 404 with `{"error": "Not found", "code": "NOT_FOUND"}`.
P1.3.4 — `PUT /api/v1/projects/{id}` with `status = "invalid"` returns HTTP 422.

### REQ-P1.4
WHEN a user deletes a project,
THEN `DELETE /api/v1/projects/{id}` MUST remove the record from the database and return HTTP 204. Deleting a non-existent project MUST return HTTP 404.

**Acceptance Criteria:**
P1.4.1 — `DELETE /api/v1/projects/{id}` for an existing project returns HTTP 204.
P1.4.2 — A subsequent `GET /api/v1/projects/{id}` for the deleted project returns HTTP 404.
P1.4.3 — `DELETE /api/v1/projects/9999` returns HTTP 404.

### REQ-P1.5
WHEN project schemas are defined for Phase 1,
THEN `ProjectResponse` MUST include `created_at: datetime` and `updated_at: datetime` fields in addition to the Phase 0 fields, and `ProjectCreate` MUST be extended with an optional `tags: list[str]` field stored as a JSON-encoded TEXT column.

**Acceptance Criteria:**
P1.5.1 — `ProjectResponse` schema includes `id`, `name`, `description`, `status`, `tags`, `created_at`, `updated_at`.
P1.5.2 — `created_at` and `updated_at` in API responses are ISO 8601 strings with UTC timezone offset (`+00:00` or `Z`).
P1.5.3 — `tags` defaults to `[]` when not provided.
P1.5.4 — `mypy --strict src/devflow_api/schemas/project.py` exits with code 0.

### REQ-P1.6
WHEN the Streamlit Projects page is active,
THEN it MUST replace the Phase 0 placeholder with a functional UI showing the project list, a create-project form, and project detail/edit actions connected to the FastAPI backend via `APIClient`.

**Acceptance Criteria:**
P1.6.1 — The Projects page renders without exception when the backend is available (verified by `AppTest` with a mocked `APIClient`).
P1.6.2 — The Projects page shows a "Backend unavailable" notice (not an exception) when the backend is unreachable.
P1.6.3 — The create-project form validates that `name` is non-empty before submitting.
P1.6.4 — The page does not display hard-coded or fabricated project data.
P1.6.5 — `mypy --strict src/devflow_ui/pages/2_Projects.py` exits with code 0.

---

## Area 2 — AI Workflow Orchestration Foundation

### REQ-W1.1
WHEN a workflow is defined,
THEN a `Workflow` SQLAlchemy model MUST exist in `src/devflow_api/models/workflow.py` with the following columns: `id` (INTEGER PK), `name` (TEXT NOT NULL), `description` (TEXT), `project_id` (INTEGER FK → projects.id, nullable), `status` (TEXT, constrained to `draft | active | paused | completed | failed`), `definition_json` (TEXT — workflow step definitions), `created_at` (UTCDateTime), `updated_at` (UTCDateTime).

**Acceptance Criteria:**
W1.1.1 — `Workflow` model is importable from `devflow_api.models.workflow`.
W1.1.2 — `mypy --strict src/devflow_api/models/workflow.py` exits with code 0.
W1.1.3 — `status` column has a `CheckConstraint` enforcing the allowed values.
W1.1.4 — `project_id` is a nullable foreign key with `ON DELETE SET NULL`.
W1.1.5 — `created_at` and `updated_at` use `UTCDateTime` TypeDecorator.

### REQ-W1.2
WHEN a workflow execution is tracked,
THEN a `WorkflowRun` SQLAlchemy model MUST exist in `src/devflow_api/models/workflow.py` with columns: `id` (INTEGER PK), `workflow_id` (INTEGER FK → workflows.id NOT NULL), `status` (TEXT, constrained to `pending | running | waiting_approval | completed | failed | cancelled`), `started_at` (UTCDateTime nullable), `completed_at` (UTCDateTime nullable), `result_json` (TEXT), `error_message` (TEXT), `created_at` (UTCDateTime), `updated_at` (UTCDateTime).

**Acceptance Criteria:**
W1.2.1 — `WorkflowRun` model is importable from `devflow_api.models.workflow`.
W1.2.2 — `status` column enforces its allowed values via `CheckConstraint`.
W1.2.3 — `workflow_id` is a non-nullable foreign key; deleting a workflow MUST cascade to delete its runs.
W1.2.4 — `mypy --strict src/devflow_api/models/workflow.py` exits with code 0.

### REQ-W1.3
WHEN a workflow approval gate is reached,
THEN an `ApprovalRequest` SQLAlchemy model MUST exist in `src/devflow_api/models/approval.py` with columns: `id` (INTEGER PK), `workflow_run_id` (INTEGER FK → workflow_runs.id NOT NULL), `step_name` (TEXT NOT NULL), `action_description` (TEXT NOT NULL — human-readable description of the pending action), `payload_json` (TEXT — the data the action would operate on), `status` (TEXT, constrained to `pending | approved | rejected | expired`), `requested_at` (UTCDateTime), `resolved_at` (UTCDateTime nullable), `resolved_by` (TEXT nullable), `created_at` (UTCDateTime), `updated_at` (UTCDateTime).

**Acceptance Criteria:**
W1.3.1 — `ApprovalRequest` is importable from `devflow_api.models.approval`.
W1.3.2 — `status` enforces allowed values via `CheckConstraint`.
W1.3.3 — `workflow_run_id` is a non-nullable foreign key; deleting a workflow run MUST cascade to delete its approval requests.
W1.3.4 — `mypy --strict src/devflow_api/models/approval.py` exits with code 0.
W1.3.5 — A `WorkflowRun` with status `waiting_approval` MUST have at least one `ApprovalRequest` with status `pending` (enforced by application logic, not DB constraint — verified in service unit tests).

### REQ-W1.4
WHEN workflow CRUD operations are performed,
THEN `GET/POST /api/v1/workflows` and `GET/PUT/DELETE /api/v1/workflows/{id}` MUST be implemented with database persistence, following the same repository-service-router layering as projects.

**Acceptance Criteria:**
W1.4.1 — `POST /api/v1/workflows` with valid body returns HTTP 201 with a workflow containing `id` and timestamps.
W1.4.2 — `GET /api/v1/workflows?project_id={id}` returns only workflows for the specified project.
W1.4.3 — `GET /api/v1/workflows?status=active` filters by status.
W1.4.4 — `DELETE /api/v1/workflows/{id}` cascades to delete associated `WorkflowRun` records.
W1.4.5 — All five endpoints appear in `/openapi.json` under `/api/v1/workflows`.

### REQ-W1.5
WHEN a workflow run is created and managed,
THEN `POST /api/v1/workflows/{id}/runs`, `GET /api/v1/workflows/{id}/runs`, and `GET /api/v1/workflow-runs/{run_id}` MUST be implemented and persist `WorkflowRun` records with accurate status transitions.

**Acceptance Criteria:**
W1.5.1 — `POST /api/v1/workflows/{id}/runs` returns HTTP 201 with status `pending`.
W1.5.2 — A run's `status` transitions are enforced: `pending → running → waiting_approval | completed | failed | cancelled`.
W1.5.3 — Transitioning to an invalid status (e.g., `pending → completed` skipping `running`) returns HTTP 422.
W1.5.4 — `GET /api/v1/workflow-runs/{run_id}` returns the full run including any associated `ApprovalRequest` records.

### REQ-W1.6
WHEN an approval gate is pending,
THEN `GET /api/v1/approvals?status=pending`, `GET /api/v1/approvals/{id}`, and `POST /api/v1/approvals/{id}/resolve` MUST be implemented. Resolving an approval MUST update the `ApprovalRequest` status, set `resolved_at` to current UTC time, and resume or cancel the associated `WorkflowRun` based on the resolution.

**Acceptance Criteria:**
W1.6.1 — `GET /api/v1/approvals?status=pending` returns all unresolved approvals.
W1.6.2 — `POST /api/v1/approvals/{id}/resolve` with `{"decision": "approved"}` sets `ApprovalRequest.status = "approved"` and `WorkflowRun.status = "running"`.
W1.6.3 — `POST /api/v1/approvals/{id}/resolve` with `{"decision": "rejected"}` sets `ApprovalRequest.status = "rejected"` and `WorkflowRun.status = "cancelled"`.
W1.6.4 — Resolving an already-resolved approval returns HTTP 409 with `{"error": "...", "code": "APPROVAL_ALREADY_RESOLVED"}`.
W1.6.5 — `resolved_by` is set from the request body when provided.

### REQ-W1.7
WHEN an audit trail is required,
THEN a `WorkflowAuditLog` SQLAlchemy model MUST exist in `src/devflow_api/models/audit.py` with columns: `id` (INTEGER PK), `workflow_run_id` (INTEGER FK nullable), `event_type` (TEXT NOT NULL), `actor` (TEXT NOT NULL — `"system"` or `"user"`), `payload_json` (TEXT), `created_at` (UTCDateTime). Every status transition on `WorkflowRun` or `ApprovalRequest` MUST generate an audit log entry.

**Acceptance Criteria:**
W1.7.1 — `WorkflowAuditLog` is importable from `devflow_api.models.audit`.
W1.7.2 — Creating a `WorkflowRun` generates an audit log entry with `event_type = "run_created"`.
W1.7.3 — Every `WorkflowRun` status transition generates an audit log entry with `event_type = "run_status_changed"` and the old/new status in `payload_json`.
W1.7.4 — Resolving an `ApprovalRequest` generates an audit log entry with `event_type = "approval_resolved"`.
W1.7.5 — `GET /api/v1/workflow-runs/{run_id}/audit` returns the full audit log for a run, ordered by `created_at` ascending.

---

## Area 3 — Integration Execution

### REQ-I1.1
WHEN the GitHub adapter is invoked,
THEN the `GitHubAdapter` MUST replace the Phase 0 `GitHubStubAdapter` with a live implementation that uses `httpx` to call the GitHub REST API v3, authenticates with `GITHUB_TOKEN` from `Settings`, and raises `MissingCredentialError` when the token is absent.

**Acceptance Criteria:**
I1.1.1 — `GitHubAdapter.create_issue(repo, title, body)` calls `POST https://api.github.com/repos/{repo}/issues` and returns a `GitHubIssueResponse` with `stub=False`.
I1.1.2 — When `GITHUB_TOKEN` is `None`, calling any action method raises `MissingCredentialError` before any network call.
I1.1.3 — HTTP errors from GitHub (4xx, 5xx) raise `IntegrationExecutionError` with the status code and body preserved in the error.
I1.1.4 — All GitHub adapter methods have a default timeout of 10 seconds enforced via `httpx.AsyncClient(timeout=10.0)`.
I1.1.5 — Unit tests mock `httpx.AsyncClient` and do NOT require a real GitHub token or network access.
I1.1.6 — `GitHubStubAdapter` remains in `stubs/github.py` and in the registry when `GITHUB_TOKEN` is absent (live adapter is only used when explicitly configured).

### REQ-I1.2
WHEN the Ollama adapter is invoked,
THEN the `OllamaAdapter` MUST replace the Phase 0 stub with a live implementation that calls the Ollama local REST API at `OLLAMA_BASE_URL` from `Settings`, requires no API key, and handles the case where Ollama is not running.

**Acceptance Criteria:**
I1.2.1 — `OllamaAdapter.generate(model, prompt)` calls `POST {OLLAMA_BASE_URL}/api/generate` and returns an `OllamaResponse` with `stub=False`.
I1.2.2 — When Ollama is not running (connection refused), `health_check()` returns `{"status": "unavailable", ...}` without raising.
I1.2.3 — `OllamaAdapter.generate` has a configurable timeout defaulting to 30 seconds.
I1.2.4 — Unit tests mock `httpx.AsyncClient` and do NOT require Ollama to be running.
I1.2.5 — `OllamaStubAdapter` remains available for environments without Ollama.

### REQ-I1.3
WHEN the Figma adapter is invoked,
THEN the `FigmaAdapter` MUST replace the Phase 0 stub with a live implementation that calls the Figma REST API, authenticates with `FIGMA_TOKEN` from `Settings`, and raises `MissingCredentialError` when the token is absent.

**Acceptance Criteria:**
I1.3.1 — `FigmaAdapter.get_file(file_key)` calls `GET https://api.figma.com/v1/files/{file_key}` and returns a `FigmaResponse` with `stub=False`.
I1.3.2 — When `FIGMA_TOKEN` is `None`, calling `get_file` raises `MissingCredentialError`.
I1.3.3 — HTTP errors from Figma raise `IntegrationExecutionError`.
I1.3.4 — Default timeout is 10 seconds.
I1.3.5 — Unit tests mock `httpx.AsyncClient`.

### REQ-I1.4
WHEN integration adapters are selected at runtime,
THEN the adapter registry MUST support a `get_live(name: str) -> BaseAdapterProtocol` method that returns the live adapter when one is configured and available, falling back to the stub when the live adapter cannot be initialised (e.g., missing credential).

**Acceptance Criteria:**
I1.4.1 — `registry.get_live("github")` returns a `GitHubAdapter` instance when `GITHUB_TOKEN` is set.
I1.4.2 — `registry.get_live("github")` returns a `GitHubStubAdapter` instance when `GITHUB_TOKEN` is not set.
I1.4.3 — `registry.get_live("kiro")` always returns `KiroStubAdapter` (no live Kiro adapter exists in Phase 1).
I1.4.4 — `registry.get("name")` continues to return the stub adapter (unchanged Phase 0 behaviour).
I1.4.5 — `mypy --strict src/devflow_api/adapters/registry.py` exits with code 0.

### REQ-I1.5
WHEN an integration error occurs,
THEN `IntegrationExecutionError` MUST be defined in `src/devflow_api/adapters/exceptions.py` with fields: `integration_name: str`, `action: str`, `status_code: int | None`, `message: str`. The FastAPI error handler MUST convert `IntegrationExecutionError` to HTTP 502 with `{"error": "...", "code": "INTEGRATION_ERROR"}`.

**Acceptance Criteria:**
I1.5.1 — `IntegrationExecutionError` is importable from `devflow_api.adapters.exceptions`.
I1.5.2 — `GET /api/v1/integrations/{name}/health` for an adapter that raises `IntegrationExecutionError` returns HTTP 502.
I1.5.3 — `mypy --strict src/devflow_api/adapters/exceptions.py` exits with code 0.

### REQ-I1.6
WHEN the Integrations page is active in Phase 1,
THEN the Streamlit Integrations page (9_Integrations.py) MUST display the live integration status for all adapters, showing `execution_mode`, current health status, and whether live or stub mode is active.

**Acceptance Criteria:**
I1.6.1 — The Integrations page renders without exception when the backend is available (verified by `AppTest` with mocked `APIClient`).
I1.6.2 — Each integration card shows: `name`, `execution_mode`, `status` (from health check), and `mode: live | stub`.
I1.6.3 — The page shows "Backend unavailable" when the API is unreachable.
I1.6.4 — No integration card shows hardcoded status; all data comes from `APIClient`.

---

## Area 4 — MCP Client Infrastructure

### REQ-M1.1
WHEN MCP servers are configured,
THEN a `MCPServerConfig` Pydantic v2 model MUST be defined in `src/devflow_api/adapters/mcp_client.py` with fields: `name: str`, `command: list[str]`, `args: list[str]`, `env: dict[str, str]`, `timeout_seconds: int` (default 30), `enabled: bool` (default True). MCP server configurations MUST be loaded from `MCP_SERVERS_CONFIG` in `Settings` as a JSON array.

**Acceptance Criteria:**
M1.1.1 — `MCPServerConfig` is importable from `devflow_api.adapters.mcp_client`.
M1.1.2 — `Settings.MCP_SERVERS_CONFIG` is parsed as `list[MCPServerConfig]` by a Pydantic validator.
M1.1.3 — An empty `MCP_SERVERS_CONFIG` string parses to an empty list (no error).
M1.1.4 — An invalid JSON value for `MCP_SERVERS_CONFIG` raises `ValidationError` on `Settings` instantiation.
M1.1.5 — `mypy --strict src/devflow_api/adapters/mcp_client.py` exits with code 0.

### REQ-M1.2
WHEN an MCP tool is invoked,
THEN the `MCPClient` MUST launch the configured server as a subprocess using the MCP Python SDK's `stdio_client`, discover available tools, call the specified tool with the provided arguments, and return a typed `MCPToolResult`.

**Acceptance Criteria:**
M1.2.1 — `MCPClient.call_tool(server_name, tool_name, arguments)` returns an `MCPToolResult` with `content`, `is_error`, and `stub=False`.
M1.2.2 — Calling a tool on an unconfigured server raises `MCPServerNotFoundError`.
M1.2.3 — When the server process fails to start, `MCPClient.call_tool` raises `MCPConnectionError`.
M1.2.4 — Tool execution is bounded by `MCPServerConfig.timeout_seconds`; exceeding the limit raises `MCPTimeoutError`.
M1.2.5 — All subprocess interactions are wrapped in `try/finally` to ensure the subprocess is terminated.
M1.2.6 — Unit tests mock the MCP subprocess and do NOT spawn real processes.

### REQ-M1.3
WHEN MCP tool invocations are recorded,
THEN every `MCPClient.call_tool` invocation MUST generate a structured log entry containing: `server_name`, `tool_name`, `argument_keys` (not argument values — to avoid logging secrets), `duration_ms`, `success: bool`.

**Acceptance Criteria:**
M1.3.1 — A unit test captures structlog output and verifies the required fields are present.
M1.3.2 — Argument values are NOT logged (only keys).
M1.3.3 — Errors are logged at WARNING level with `success=False`.

### REQ-M1.4
WHEN MCP tool permissions are evaluated,
THEN each tool invocation MUST be checked against an allow-list defined in `MCPServerConfig.allowed_tools: list[str]` (defaults to `["*"]` meaning all tools allowed). Calling a tool not in the allow-list MUST raise `MCPPermissionError` without spawning a process.

**Acceptance Criteria:**
M1.4.1 — When `allowed_tools = ["read_file"]`, calling `write_file` raises `MCPPermissionError`.
M1.4.2 — When `allowed_tools = ["*"]`, any tool name is allowed.
M1.4.3 — `MCPPermissionError` is raised before any subprocess is started.
M1.4.4 — `mypy --strict` passes on the permission-check code path.

### REQ-M1.5
WHEN MCP secrets are required,
THEN `MCPServerConfig.env` MUST support `${SECRET_NAME}` interpolation resolved from `Settings` at runtime. Secret values MUST NOT appear in log output.

**Acceptance Criteria:**
M1.5.1 — `${GITHUB_TOKEN}` in `MCPServerConfig.env` is resolved to `Settings.GITHUB_TOKEN.get_secret_value()` at process launch time.
M1.5.2 — An unresolvable `${MISSING_KEY}` raises `MCPSecretResolutionError` before process launch.
M1.5.3 — Resolved secret values do not appear in any log record (verified by unit test capturing log output).

### REQ-M1.6
WHEN the `MCPAdapter` is used through the adapter registry,
THEN the Phase 0 `MCPStubAdapter` MUST be replaced by a `MCPLiveAdapter` that delegates to `MCPClient`, but falls back to `MCPStubAdapter` when no MCP servers are configured.

**Acceptance Criteria:**
M1.6.1 — `registry.get_live("mcp")` returns `MCPLiveAdapter` when at least one `MCPServerConfig` is configured and enabled.
M1.6.2 — `registry.get_live("mcp")` returns `MCPStubAdapter` when `MCP_SERVERS_CONFIG` is empty.
M1.6.3 — `MCPLiveAdapter.call_tool` delegates to `MCPClient`.
M1.6.4 — `MCPLiveAdapter.health_check()` returns `{"status": "ok", ...}` when the first configured server responds, `{"status": "unavailable", ...}` when no server responds, and `{"status": "stub", ...}` when in stub mode.

---

## Area 5 — GitHub Workflow Orchestration

### REQ-G1.1
WHEN a repository connection is configured,
THEN a `RepositoryConfig` SQLAlchemy model MUST exist in `src/devflow_api/models/repository.py` with columns: `id` (INTEGER PK), `project_id` (INTEGER FK → projects.id NOT NULL), `owner` (TEXT NOT NULL), `repo` (TEXT NOT NULL), `default_branch` (TEXT NOT NULL DEFAULT `"main"`), `is_active` (BOOLEAN NOT NULL DEFAULT 1), `created_at` (UTCDateTime), `updated_at` (UTCDateTime). The combination `(project_id, owner, repo)` MUST be unique.

**Acceptance Criteria:**
G1.1.1 — `RepositoryConfig` is importable from `devflow_api.models.repository`.
G1.1.2 — The unique constraint on `(project_id, owner, repo)` is enforced at the database level.
G1.1.3 — `mypy --strict src/devflow_api/models/repository.py` exits with code 0.
G1.1.4 — `POST /api/v1/repositories` creates a repository config and returns HTTP 201.
G1.1.5 — `GET /api/v1/repositories?project_id={id}` returns configs for the given project.

### REQ-G1.2
WHEN branch status is queried,
THEN `GET /api/v1/repositories/{repo_config_id}/branches` MUST call the GitHub REST API to list branches, and `GET /api/v1/repositories/{repo_config_id}/branches/{branch}/status` MUST return the branch protection status, latest commit SHA, and CI check results.

**Acceptance Criteria:**
G1.2.1 — Branch listing calls `GET https://api.github.com/repos/{owner}/{repo}/branches` and returns a list of branch summaries.
G1.2.2 — Branch status returns: `branch_name`, `sha`, `protected`, `ci_status` (`success | failure | pending | unknown`).
G1.2.3 — When `GITHUB_TOKEN` is absent, both endpoints return HTTP 403 with `{"error": "...", "code": "MISSING_CREDENTIAL"}`.
G1.2.4 — HTTP errors from GitHub are wrapped as `IntegrationExecutionError` and returned as HTTP 502.
G1.2.5 — Unit tests mock `httpx.AsyncClient`.

### REQ-G1.3
WHEN a PR is inspected,
THEN `GET /api/v1/repositories/{repo_config_id}/pull-requests` and `GET /api/v1/repositories/{repo_config_id}/pull-requests/{pr_number}` MUST retrieve PR data from GitHub and return structured `PullRequestSummary` responses.

**Acceptance Criteria:**
G1.3.1 — `PullRequestSummary` includes: `number`, `title`, `state`, `base_ref`, `head_ref`, `merged_at` (nullable), `checks_passed: bool`.
G1.3.2 — `checks_passed` is `True` only when all required status checks have concluded with `success`.
G1.3.3 — Unit tests mock the GitHub API calls.

### REQ-G1.4
WHEN a branch needs to be prepared,
THEN `POST /api/v1/repositories/{repo_config_id}/branches` MUST support creating a new branch from a specified base ref by calling the GitHub Refs API. This action MUST require an explicit `confirmed: bool = True` field in the request body; requests with `confirmed = false` MUST return HTTP 422.

**Acceptance Criteria:**
G1.4.1 — `POST /api/v1/repositories/{repo_config_id}/branches` with `{"name": "feature/x", "base_ref": "develop", "confirmed": true}` creates the branch via GitHub API and returns HTTP 201.
G1.4.2 — The same request with `"confirmed": false` returns HTTP 422 with `{"error": "Branch creation requires explicit confirmation", "code": "CONFIRMATION_REQUIRED"}`.
G1.4.3 — Duplicate branch name returns HTTP 409.
G1.4.4 — The action is logged in `WorkflowAuditLog` with `event_type = "branch_created"` and `actor = "user"`.
G1.4.5 — Unit tests mock the GitHub API and verify the confirmation gate.

### REQ-G1.5
WHEN a PR is created,
THEN `POST /api/v1/repositories/{repo_config_id}/pull-requests` MUST call the GitHub PRs API to create a PR. This is a consequential action requiring explicit `confirmed: bool = True` in the request body. Automatic merging MUST NOT be supported.

**Acceptance Criteria:**
G1.5.1 — `POST /api/v1/repositories/{repo_config_id}/pull-requests` with valid body and `"confirmed": true` creates the PR via GitHub API and returns HTTP 201 with `PullRequestSummary`.
G1.5.2 — The same request with `"confirmed": false` returns HTTP 422 with code `CONFIRMATION_REQUIRED`.
G1.5.3 — The API MUST NOT expose a merge endpoint. Any `POST /api/v1/.../merge` route MUST NOT exist.
G1.5.4 — PR creation is logged in `WorkflowAuditLog` with `event_type = "pr_created"`.
G1.5.5 — Unit tests mock the GitHub API and verify the confirmation gate.

### REQ-G1.6
WHEN CI status is reported,
THEN `GET /api/v1/repositories/{repo_config_id}/branches/{branch}/ci` MUST return the CI check results for the latest commit on that branch by querying the GitHub Check Runs API.

**Acceptance Criteria:**
G1.6.1 — Response includes a list of `CheckRunSummary` objects with: `name`, `status` (`queued | in_progress | completed`), `conclusion` (nullable: `success | failure | skipped | cancelled`).
G1.6.2 — `GET /api/v1/repositories/{repo_config_id}/branches/{branch}/ci` returns HTTP 200 when the branch exists.
G1.6.3 — Returns HTTP 404 when the branch does not exist.
G1.6.4 — Unit tests mock the GitHub API.

---

## Area 6 — Streamlit Phase 1 Experience

### REQ-U1.1
WHEN the Dashboard page loads in Phase 1,
THEN it MUST display real data from the FastAPI backend: project count, active workflow count, and pending approval count — all fetched via `APIClient`. No hard-coded or fabricated metrics MUST appear.

**Acceptance Criteria:**
U1.1.1 — Dashboard page fetches `GET /api/v1/projects`, `GET /api/v1/workflows?status=active`, and `GET /api/v1/approvals?status=pending` via `APIClient` to build its metric display.
U1.1.2 — Each metric shows "—" or "0" when the backend is unavailable or returns 0.
U1.1.3 — `AppTest` with mocked `APIClient` completes without exception.
U1.1.4 — No "Phase 0" placeholder text remains on the Dashboard page.

### REQ-U1.2
WHEN the Workflows page is active,
THEN a new `6_Workflows.py` page MUST be added to the navigation showing active workflows, their current run status, and pending approvals for each run.

**Acceptance Criteria:**
U1.2.1 — The Workflows page exists at `src/devflow_ui/pages/6_Workflows.py` and is registered in `app.py` navigation.
U1.2.2 — The page lists workflows from `GET /api/v1/workflows` via `APIClient`.
U1.2.3 — Each workflow entry shows its status and the count of pending approvals.
U1.2.4 — An "Approve" action button is visible for runs in `waiting_approval` status.
U1.2.5 — `AppTest` with mocked `APIClient` completes without exception.

### REQ-U1.3
WHEN the Execution History page is active,
THEN a new `7_History.py` page MUST display the audit log for recent workflow runs, ordered by recency.

**Acceptance Criteria:**
U1.3.1 — The History page exists at `src/devflow_ui/pages/7_History.py` and is registered in `app.py` navigation.
U1.3.2 — The page fetches recent workflow runs and their audit log entries via `APIClient`.
U1.3.3 — Each entry shows: `workflow name`, `run status`, `started_at`, `completed_at` (if available), `event count`.
U1.3.4 — `AppTest` with mocked `APIClient` completes without exception.

### REQ-U1.4
WHEN the APIClient is extended for Phase 1,
THEN `src/devflow_ui/api_client.py` MUST add typed methods for all new Phase 1 endpoints: projects CRUD, workflows CRUD, runs, approvals, and repository configs. Each method MUST follow the Phase 0 pattern: return `None` on error, log a warning, never raise to the caller.

**Acceptance Criteria:**
U1.4.1 — `APIClient.list_projects(status=None, limit=50, offset=0)` returns `list[dict] | None`.
U1.4.2 — `APIClient.create_project(name, description=None, tags=None)` returns `dict | None`.
U1.4.3 — `APIClient.list_workflows(project_id=None, status=None)` returns `list[dict] | None`.
U1.4.4 — `APIClient.resolve_approval(approval_id, decision)` returns `dict | None`.
U1.4.5 — All new methods carry complete type annotations validated by `mypy --strict`.

### REQ-U1.5
WHEN the Settings page is active in Phase 1,
THEN it MUST display all Phase 1 configuration values (integration availability, MCP server config count, GitHub connection status) in addition to the Phase 0 health check.

**Acceptance Criteria:**
U1.5.1 — Settings page shows `GET /api/v1/integrations` summary (number of live vs stub adapters).
U1.5.2 — Settings page shows how many MCP servers are configured.
U1.5.3 — Settings page shows GitHub connection status (connected / no token).
U1.5.4 — `AppTest` with mocked `APIClient` completes without exception.

---

## Area 7 — Database Migrations

### REQ-DB1.1
WHEN Phase 1 schema changes are applied,
THEN dedicated Alembic migrations MUST be authored for each new table group introduced in Phase 1: (a) `002_add_workflow_tables.py`, (b) `003_add_approval_audit_tables.py`, (c) `004_add_repository_tables.py`, (d) `005_add_project_tags_column.py`.

**Acceptance Criteria:**
DB1.1.1 — `alembic upgrade head` from a Phase 0 schema applies all four Phase 1 migrations.
DB1.1.2 — `alembic downgrade -1` from head undoes the most recent migration without error.
DB1.1.3 — Each migration has a non-trivial `downgrade()` (not `pass`).
DB1.1.4 — Migration files are hand-authored; `alembic revision --autogenerate` output MUST be reviewed and edited before commit.
DB1.1.5 — Tests MUST NOT run against the developer's `devflow.db`; they use `tmp_path`-scoped SQLite files.

### REQ-DB1.2
WHEN the tags column is added to projects,
THEN migration `005_add_project_tags_column.py` MUST add a nullable TEXT column `tags_json` with `server_default = "[]"`. Existing project rows receive `tags_json = "[]"`.

**Acceptance Criteria:**
DB1.2.1 — After `alembic upgrade head`, existing `projects` rows have `tags_json = "[]"`.
DB1.2.2 — `downgrade()` removes the `tags_json` column.
DB1.2.3 — The Alembic test (`test_database.py`) covers the round-trip for this migration.

---

## Area 8 — Security Requirements

### REQ-S1.1
ALL consequential actions (branch creation, PR creation, file writes, subprocess execution) MUST require explicit user confirmation via either an `ApprovalRequest` workflow gate or a `confirmed: bool = True` request body field before execution.

**Acceptance Criteria:**
S1.1.1 — Branch creation without `"confirmed": true` returns HTTP 422.
S1.1.2 — PR creation without `"confirmed": true` returns HTTP 422.
S1.1.3 — `WorkflowRun` actions that reach a `waiting_approval` status gate MUST NOT proceed until `ApprovalRequest.status = "approved"`.
S1.1.4 — A unit test verifies that a workflow action requiring approval does not execute when `ApprovalRequest.status = "pending"`.

### REQ-S1.2
ALL integration adapter live implementations MUST enforce bounded execution timeouts.

**Acceptance Criteria:**
S1.2.1 — GitHub adapter requests time out after 10 seconds.
S1.2.2 — Ollama adapter requests time out after 30 seconds (configurable via `Settings.OLLAMA_TIMEOUT_SECONDS: int = 30`).
S1.2.3 — Figma adapter requests time out after 10 seconds.
S1.2.4 — MCP tool calls time out after `MCPServerConfig.timeout_seconds`.
S1.2.5 — Timeout values MUST be configurable via `Settings`; hardcoded timeout constants MUST NOT be used.

### REQ-S1.3
ALL credentials MUST be accessed exclusively through `Settings` SecretStr fields and MUST NOT appear in log output.

**Acceptance Criteria:**
S1.3.1 — `RedactSecretsProcessor` from Phase 0 is applied to all log records in Phase 1.
S1.3.2 — A unit test asserts that GitHub token value does not appear in any log record produced during adapter initialization or invocation.
S1.3.3 — MCP env secret values do not appear in log records.

### REQ-S1.4
Automatic PR merging MUST NOT be supported.

**Acceptance Criteria:**
S1.4.1 — No merge endpoint exists in the API (`/merge` path MUST NOT be registered).
S1.4.2 — `docs/openapi.json` (regenerated after Phase 1) contains no path containing the word `merge`.

### REQ-S1.5
Subprocess execution (MCP server launch) MUST be bounded and isolated.

**Acceptance Criteria:**
S1.5.1 — MCP server subprocesses are launched with `env` explicitly set (not inheriting the full parent environment).
S1.5.2 — Server processes are terminated in a `finally` block after each tool call.
S1.5.3 — No MCP adapter spawns a process without an entry in `MCPServerConfig`.

---

## Area 9 — Testing Requirements

### REQ-T1.1
WHEN Phase 1 unit tests are executed,
THEN they MUST achieve at least 80% branch coverage across `src/` and cover all new repository methods, service methods, router endpoints (success and error paths), adapter live implementations (mocked), MCP client logic (mocked), and GitHub API interactions (mocked).

**Acceptance Criteria:**
T1.1.1 — `pytest --cov=src --cov-fail-under=80` exits with code 0 on the complete Phase 1 codebase.
T1.1.2 — Every new router has tests for at least: success path, 404, 422, and (where applicable) 502.
T1.1.3 — Every new service method has at least one unit test using an in-memory database.
T1.1.4 — All mocked adapter tests pass without network access.

### REQ-T1.2
WHEN Phase 1 Streamlit pages are tested,
THEN `AppTest` smoke tests MUST exist for every new and modified page.

**Acceptance Criteria:**
T1.2.1 — `AppTest` smoke tests exist for: `1_Dashboard.py`, `2_Projects.py`, `6_Workflows.py`, `7_History.py`, `9_Integrations.py`, `10_Settings.py`.
T1.2.2 — All smoke tests mock `APIClient` methods to avoid backend dependency.
T1.2.3 — All smoke tests assert absence of `at.exception`.

### REQ-T1.3
WHEN integration tests for database migrations are run,
THEN the Phase 1 migration test MUST run the full round-trip: `upgrade head → verify tables → downgrade to Phase 0 → verify Phase 0 tables remain`.

**Acceptance Criteria:**
T1.3.1 — `pytest -m integration tests/integration/test_database.py` runs all migration round-trips.
T1.3.2 — Tests use a `tmp_path`-scoped SQLite file, not the development database.
T1.3.3 — The test verifies that after downgrade the Phase 1-only tables are absent.

### REQ-T1.4
WHEN Phase 0 tests are re-run on the Phase 1 codebase,
THEN all Phase 0 tests MUST continue to pass without modification.

**Acceptance Criteria:**
T1.4.1 — `pytest tests/unit/ tests/smoke/ tests/integration/` exits with code 0 on the Phase 1 codebase.
T1.4.2 — No Phase 0 test file is modified in Phase 1 (exception: fixture additions in `conftest.py` that do not change existing fixtures).
