# DevFlow AI — Phase 1: Implementation Tasks

**Version:** 1.3.0
**Status:** Corrected — Awaiting Final Independent Review
**Scope:** Phase 1 — Functional Orchestration
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Last Updated:** [current correction pass — implementer fills date at commit time]
**Supersedes:** v1.2.0 (F1–F5 and D1–D4 final specification corrections applied — see .agents/tasks/phase1-final-spec-correction-report.md)

**Version history:**
- v1.0.0 — Initial specification
- v1.1.0 — Eight independent-review findings applied
- v1.2.0 — Five amendment-round findings applied
- v1.3.0 — Final specification correction: F1–F5 and D1–D4 applied (FK test split to Wave 1 / Wave 2, GitHubConfirmation persistence + migration 006 + 6 named tests in Wave 5, MCP 8-step sequence + 3 new audit events + named test, superseded guidance labelled, metadata corrected)

---

## Execution Model

Tasks are grouped into five independently reviewable waves. Each wave produces a dedicated GitHub PR targeting `develop`. No wave begins until the previous wave's PR is merged into `develop`.

```
Wave 1 — Persistent Project Management (Tasks P1–P6)
  P1  → Alembic migration 002: tags_json column
  P2  → Project model + schema extensions
  P3  → ProjectRepository + ProjectService
  P4  → Projects router (live DB)
  P5  → Streamlit Projects page (live CRUD) + APIClient extension
  P6  → Tests: Wave 1

Wave 2 — Workflow Data Layer (Tasks W1–W6)
  W1  → Models: Workflow, WorkflowRun, ApprovalRequest, WorkflowAuditLog
  W2  → Alembic migrations 003–005
  W3  → Repositories: WorkflowRepository, WorkflowRunRepository
  W4  → Repositories: ApprovalRepository, AuditLogRepository
  W5  → Services: WorkflowService, ApprovalService
  W6  → Tests: Wave 2

Wave 3 — Workflow API and Streamlit (Tasks A1–A5)
  A1  → Routers: workflows, workflow-runs
  A2  → Routers: approvals
  A3  → Exception handler extensions
  A4  → Streamlit: Dashboard, Workflows page, History page
  A5  → Tests: Wave 3

Wave 4 — Integration Execution (Tasks I1–I7)
  I1  → Adapter exceptions: IntegrationExecutionError, MCP errors
  I2  → Live adapter: GitHubAdapter
  I3  → Live adapter: OllamaAdapter + FigmaAdapter
  I4  → MCP client: MCPServerConfig, MCPClient, MCPLiveAdapter
  I5  → Registry extension: get_live, register_live
  I6  → Integrations router extension + Settings extension
  I7  → Streamlit: Integrations page, Settings page + Tests: Wave 4

Wave 5 — GitHub Workflow Orchestration (Tasks G1–G5)
  G1  → Repository model + RepositoryConfigRepository
  G2  → RepositoryService + GitHubAdapter extension
  G3  → Repositories router
  G4  → Streamlit: (no new pages — settings shows GitHub status)
  G5  → Tests: Wave 5 + final CI verification
```

**Total tasks: 29** (P1–P6 = 6, W1–W6 = 6, A1–A5 = 5, I1–I7 = 7, G1–G5 = 5)

---

## Wave 1 — Persistent Project Management

---

### Task P1 — Alembic migration: add tags_json column

**Wave:** 1
**Requirements:** REQ-DB1.1, REQ-DB1.2, REQ-P1.5
**Depends on:** _(Phase 0 complete)_
**Estimated size:** Small (< 1 hour)

**Description:**
Author migration `002_add_project_tags_column.py` to add `tags_json TEXT NOT NULL DEFAULT '[]'` to the `projects` table. Existing rows receive the default value. This migration chains directly from the Phase 0 head revision.

**Deliverables:**
- `alembic/versions/002_add_project_tags_column.py`

**Migration content:**
```python
revision = "002_add_project_tags_column"
down_revision = "001_create_initial_tables"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("projects", sa.Column("tags_json", sa.Text(), server_default="[]", nullable=False))

def downgrade() -> None:
    op.drop_column("projects", "tags_json")
```

**Acceptance Criteria:**
1. `alembic upgrade head` from a Phase 0 schema (head = `001_create_initial_tables`) applies migration `002_add_project_tags_column` without error. No other Phase 1 migration needs to exist for this to succeed.
2. `alembic downgrade -1` removes the `tags_json` column without error.
3. `downgrade()` is non-trivial (not `pass`).
4. The migration file does not contain credentials or hardcoded database paths.
5. `revision = "002_add_project_tags_column"` and `down_revision = "001_create_initial_tables"` appear exactly as shown in the file.

**Wave 1 configuration ownership (REQ-DB1.3, Amendment 4):**
During Wave 1 implementation, the implementer MUST:
- Add `PRAGMA foreign_keys=ON` to the existing `'connect'` event handler in `src/devflow_api/database.py` alongside `PRAGMA journal_mode=WAL` (REQ-DB1.3).
- Update `pyproject.toml` `[tool.pytest.ini_options]` `addopts` to: `-v --tb=short --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` (replace the current `-v --tb=short` entry).
- Update `pyproject.toml` `[tool.coverage.run]` to add `branch = true`.
- Update the CI workflow pytest command to match the canonical form `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing`.
- Update `CONTRIBUTING.md` to replace the existing coverage command with `python -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing`.

**Wave 1 CI/configuration acceptance criterion:** `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` runs and exits 0 in CI.

**Definition of Done:** Migration file committed; criteria 1–5 verified; Wave 1 configuration items applied.

---

### Task P2 — Project model and schema extensions

**Wave:** 1
**Requirements:** REQ-P1.5
**Depends on:** P1
**Estimated size:** Small (1–2 hours)

**Description:**
Extend `src/devflow_api/models/project.py` with `tags_json` column. Extend `src/devflow_api/schemas/project.py` with `tags`, `created_at`, `updated_at` fields in `ProjectResponse`. Add `ProjectUpdate` schema for partial updates.

**Deliverables:**
- `src/devflow_api/models/project.py` — add `tags_json: Mapped[str]` with `server_default="[]"`
- `src/devflow_api/schemas/project.py` — extend `ProjectResponse`; add `ProjectUpdate(BaseModel)`

**`ProjectResponse` target:**
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

    @model_validator(mode="before")
    @classmethod
    def parse_tags(cls, data: object) -> object:
        # Deserialise tags_json TEXT → tags list[str] when loading from ORM
        ...
```

**`ProjectUpdate` target:**
```python
class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: Literal["active", "archived", "completed"] | None = None
    tags: list[str] | None = None
    # Null semantics: a field set to null is treated the same as omitting it
    # (the existing value is NOT cleared). There is no way to clear a field via PUT.
```

**Acceptance Criteria:**
1. `ProjectResponse.model_validate(project_orm_instance)` works with `from_attributes=True`.
2. `ProjectResponse(id=1, name="x", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))` instantiates without error; `tags` defaults to `[]`.
3. `created_at` and `updated_at` serialise as ISO 8601 UTC strings in the JSON response.
4. `mypy --strict src/devflow_api/models/project.py src/devflow_api/schemas/project.py` exits with code 0.
5. No Phase 0 test fails due to the schema extension.

**Definition of Done:** Files committed; all criteria verified.

---

### Task P3 — ProjectRepository and ProjectService

**Wave:** 1
**Requirements:** REQ-P1.1, REQ-P1.2, REQ-P1.3, REQ-P1.4
**Depends on:** P2
**Estimated size:** Medium (2–4 hours)

**Description:**
Implement `ProjectRepository` extending `BaseRepository[Project]` with `list_filtered` and `update_tags`. Implement `ProjectService` with full CRUD methods that call the repository and return `ProjectResponse` objects.

**Deliverables:**
- `src/devflow_api/repositories/project.py` — `ProjectRepository`
- `src/devflow_api/services/project.py` — `ProjectService`

**`ProjectRepository` interface:**
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

**`ProjectService` interface:**
```python
class ProjectService:
    def __init__(self, repo: ProjectRepository) -> None: ...
    async def list(self, status=None, limit=50, offset=0) -> list[ProjectResponse]: ...
    async def create(self, body: ProjectCreate) -> ProjectResponse: ...
    async def get(self, id: int) -> ProjectResponse: ...   # raises HTTPException 404
    async def update(self, id: int, body: ProjectUpdate) -> ProjectResponse: ...  # raises 404
    async def delete(self, id: int) -> None: ...           # raises 404
```

**Acceptance Criteria:**
1. `ProjectService.create(body)` calls `ProjectRepository.create(...)` and returns a `ProjectResponse` with a non-zero `id`.
2. `ProjectService.get(9999)` raises `HTTPException(status_code=404)`.
3. `ProjectService.update(id, body)` updates only fields provided in `body` where the value is not `None` (None fields are skipped — not cleared).
4. `mypy --strict src/devflow_api/repositories/project.py src/devflow_api/services/project.py` exits with code 0.
5. No network or filesystem side effects occur in service or repository code.

**Definition of Done:** Files committed; all criteria verified (behavior verified in Task P6 tests).

---

### Task P4 — Projects router: live DB calls

**Wave:** 1
**Requirements:** REQ-P1.1, REQ-P1.2, REQ-P1.3, REQ-P1.4
**Depends on:** P3
**Estimated size:** Medium (2–3 hours)

**Description:**
Replace the Phase 0 stub router at `src/devflow_api/routers/projects.py` with live database-backed endpoints. Inject `ProjectService` via `Depends`. Use `get_db` from `database.py`. Change `POST` response to HTTP 201.

**Key implementation notes:**
- `ProjectService` is constructed per-request via `Depends` injecting a `ProjectRepository` and `AsyncSession`.
- `GET /api/v1/projects` accepts `status: str | None = Query(None)`, `limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`.
- `PUT /api/v1/projects/{id}` uses `ProjectUpdate` (partial update schema). Fields set to `null` in the JSON body are treated as absent (skipped).
- `DELETE /api/v1/projects/{id}` returns `Response(status_code=204)`.

**Acceptance Criteria:**
1. `POST /api/v1/projects` returns HTTP 201 (not 200).
2. `GET /api/v1/projects/{id}` returns the project created by the previous `POST`.
3. `GET /api/v1/projects?status=invalid` returns HTTP 422.
4. `PUT /api/v1/projects/9999` returns HTTP 404.
5. `DELETE /api/v1/projects/{id}` returns HTTP 204; subsequent `GET` returns 404.
6. `mypy --strict src/devflow_api/routers/projects.py` exits with code 0.

**Definition of Done:** Router committed; all criteria verified (integration verified in Task P6 tests).

---

### Task P5 — Streamlit Projects page and APIClient extension

**Wave:** 1
**Requirements:** REQ-P1.6, REQ-U1.4
**Depends on:** P4
**Estimated size:** Medium (2–4 hours)

**Description:**
Replace Phase 0 `2_Projects.py` placeholder with a functional CRUD page. Extend `APIClient` with the project-related methods defined in design.md §12.2.

**Deliverables:**
- `src/devflow_ui/pages/2_Projects.py` — project list + create form + edit/delete actions
- `src/devflow_ui/api_client.py` — extended with `list_projects`, `create_project`, `update_project`, `delete_project`

**Page behaviour:**
- Shows a table of projects from `APIClient.list_projects()`.
- A form with `name` (required), `description` (optional) for creating projects.
- Inline edit/delete actions per project row.
- Shows "Backend unavailable — start the FastAPI service to view projects." when backend is unreachable (not an exception).

**Acceptance Criteria:**
1. `AppTest` with mocked `APIClient` completes without exception.
2. The page does not display fabricated project data.
3. Form validates non-empty `name` before calling `APIClient.create_project`.
4. All new `APIClient` methods return `None` on error without raising.
5. `mypy --strict src/devflow_ui/pages/2_Projects.py src/devflow_ui/api_client.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in Task P6 tests.

---

### Task P6 — Tests: Wave 1

**Wave:** 1
**Requirements:** REQ-T1.1, REQ-T1.2, REQ-T1.3, REQ-T1.4
**Depends on:** P1–P5
**Estimated size:** Medium (3–5 hours)

**Description:**
Write unit and smoke tests covering all Wave 1 deliverables.

**Deliverables:**
- `tests/unit/test_project_service.py` — service + repository unit tests (in-memory DB)
- `tests/unit/test_projects_router.py` — extended to cover HTTP 201, live DB, pagination
- `tests/smoke/test_ui_pages.py` — extended with Projects page smoke test
- `tests/integration/test_database.py` — extended with migration 002 round-trip

**Required test cases:**
- `test_create_project_persists` — POST then GET confirms persistence
- `test_list_projects_filter_by_status` — GET with status=active returns only active
- `test_update_project_partial` — PUT with only name updates only name
- `test_update_project_null_field_does_not_clear` — PUT with `{"description": null}` leaves description unchanged
- `test_delete_project_removes_record` — DELETE then GET returns 404
- `test_project_tags_serialisation` — tags round-trips through JSON
- `test_migration_002_round_trip` — alembic upgrade/downgrade for tags column (migration 002, chains from 001)
- `test_projects_page_renders` — AppTest smoke test
- `test_foreign_key_pragma_enabled_on_connection` — queries `PRAGMA foreign_keys` and asserts result is `1` (REQ-DB1.3.2). Uses in-memory SQLite only — no Wave 2 tables required.
- `test_wave1_cascade_delete_enforced` — deleting a `Project` cascades to any child records reachable via Wave 1 tables only. If no Wave 1 child FK exists yet, creates a minimal test using the tags_json column FK relationships or skips with a comment that Wave 2 provides the full cascade test. Does NOT reference `WorkflowRun`, `WorkflowAuditLog`, or any Wave 2+ table. (REQ-DB1.3.3)
- `test_wave1_insert_invalid_foreign_key_raises_integrity_error` — inserts a row referencing a non-existent `project_id` in a Wave 1 table. If no Wave 1 child FK table exists, creates a minimal in-memory table with a FK to verify PRAGMA is enforcing constraints. Does NOT reference `WorkflowRun` or any Wave 2+ table. (REQ-DB1.3.4)

**Note on FK tests moved to Wave 2 (F2 correction):** The following tests reference Wave 2 tables and are deferred to Task W6:
- `test_delete_project_sets_workflow_project_id_null` (Workflow.project_id SET NULL when Project deleted)
- `test_delete_workflow_cascades_to_workflow_runs` (WorkflowRun CASCADE when Workflow deleted)
- `test_delete_workflow_run_sets_audit_log_workflow_run_id_null` (WorkflowAuditLog.workflow_run_id SET NULL when WorkflowRun deleted)
- `test_insert_invalid_foreign_key_raises_integrity_error` (WorkflowRun with non-existent workflow_id)

**Acceptance Criteria:**
1. All new tests pass.
2. No Phase 0 test is broken.
3. `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0.
4. All tests complete without network access.
5. No `.db` file is created in the repository directory.
6. `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` runs and exits 0 in CI (Wave 1 completion gate).

**Definition of Done:** All test files committed; all criteria verified; `pytest -v` output recorded in commit message.

---

## Wave 2 — Workflow Data Layer

---

### Task W1 — Models: Workflow, WorkflowRun, ApprovalRequest, WorkflowAuditLog

**Wave:** 2
**Requirements:** REQ-W1.1, REQ-W1.2, REQ-W1.3, REQ-W1.7
**Depends on:** Wave 1 merged
**Estimated size:** Medium (2–4 hours)

**Description:**
Create three new model files: `workflow.py` (Workflow + WorkflowRun), `approval.py` (ApprovalRequest), `audit.py` (WorkflowAuditLog). All timestamp columns use `UTCDateTime`. All models extend `TimestampMixin`.

**Deliverables:**
- `src/devflow_api/models/workflow.py`
- `src/devflow_api/models/approval.py`
- `src/devflow_api/models/audit.py`

**Key implementation notes:**
- `WorkflowRun.workflow_id` FK: `ForeignKey("workflows.id", ondelete="CASCADE")`
- `ApprovalRequest.workflow_run_id` FK: `ForeignKey("workflow_runs.id", ondelete="CASCADE")`
- `WorkflowAuditLog.workflow_run_id` FK: `ForeignKey("workflow_runs.id", ondelete="SET NULL")`
- `WorkflowAuditLog` does NOT use `TimestampMixin` — it has only `created_at` (immutable log entries have no `updated_at`)
- `WorkflowRun.status` CHECK constraint must include exactly: `'pending','running','waiting_approval','completed','failed','cancelled'` — `'paused'` is NOT included
- `definition_json` on `Workflow` stores step definitions for future Phase 2 execution; Phase 1 never reads or executes this column
- All `CheckConstraint` values MUST exactly match the allowed status lists in requirements

**Acceptance Criteria:**
1. All three model files importable without error.
2. `mypy --strict src/devflow_api/models/workflow.py src/devflow_api/models/approval.py src/devflow_api/models/audit.py` exits with code 0.
3. All timestamp columns use `UTCDateTime` TypeDecorator.
4. `WorkflowRun.status` CHECK constraint includes exactly `pending`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled` — no `paused`.
5. `WorkflowAuditLog` has no `updated_at` column.

**Definition of Done:** Files committed; all criteria verified (behavioral tests in W6).

---

### Task W2 — Alembic migrations 003–005

**Wave:** 2
**Requirements:** REQ-DB1.1
**Depends on:** W1 (and implicitly on Wave 1 merged — migration 002 must exist as the predecessor to 003)
**Estimated size:** Medium (2–3 hours)

**Description:**
Hand-author three migration files. Each file must import nothing from `devflow_api.models` to avoid circular imports — use inline `sa.Table` definitions. These migrations continue the chain started by migration 002 in Wave 1.

**Deliverables:**
- `alembic/versions/003_add_workflow_tables.py` — creates `workflows`, `workflow_runs`
- `alembic/versions/004_add_approval_audit_tables.py` — creates `approval_requests`, `workflow_audit_log`
- `alembic/versions/005_add_repository_tables.py` — creates `repository_configs`

**Required revision headers:**
```python
# 003_add_workflow_tables.py
revision = "003_add_workflow_tables"
down_revision = "002_add_project_tags_column"

# 004_add_approval_audit_tables.py
revision = "004_add_approval_audit_tables"
down_revision = "003_add_workflow_tables"

# 005_add_repository_tables.py
revision = "005_add_repository_tables"
down_revision = "004_add_approval_audit_tables"
```

**WorkflowRun status CHECK constraint in migration 003:**
The `workflow_runs` table CHECK constraint must list exactly: `'pending','running','waiting_approval','completed','failed','cancelled'` — `'paused'` is NOT included.

**Acceptance Criteria:**
1. `alembic upgrade head` from Phase 0 schema (after Wave 1 is merged — head = `002_add_project_tags_column`) applies migrations 003, 004, 005 in order.
2. `alembic downgrade base` from head undoes all five Phase 1 migrations without error.
3. Each `downgrade()` is non-trivial.
4. No migration file contains credentials.
5. The chain `upgrade head → downgrade -1 → upgrade head` completes without error for each migration.
6. Each migration file imports nothing from `devflow_api.models` (no model imports — inline `sa.Table` only).

**Definition of Done:** Migration files committed; all criteria verified in W6 integration tests.

---

### Task W3 — Repositories: WorkflowRepository, WorkflowRunRepository

**Wave:** 2
**Requirements:** REQ-W1.4, REQ-W1.5
**Depends on:** W1, W2
**Estimated size:** Medium (2–4 hours)

**Description:**
Implement typed repositories for `Workflow` and `WorkflowRun`. `WorkflowRunRepository.transition_status` enforces the valid transition table from design.md §9.

**Deliverables:**
- `src/devflow_api/repositories/workflow.py`

**`InvalidStatusTransitionError` exception:**
```python
class InvalidStatusTransitionError(DevFlowError):
    run_id: int
    from_status: str
    to_status: str
```
Defined in `src/devflow_core/exceptions.py`.

**Acceptance Criteria:**
1. `WorkflowRunRepository.transition_status(run_id, "completed", valid_from=["running"])` succeeds when current status is `running`.
2. `WorkflowRunRepository.transition_status(run_id, "completed", valid_from=["running"])` raises `InvalidStatusTransitionError` when current status is `pending`.
3. `WorkflowRepository.list_by_project(project_id)` returns only workflows for that project.
4. `mypy --strict src/devflow_api/repositories/workflow.py` exits with code 0.
5. All methods tested with in-memory SQLite.

**Definition of Done:** File committed; all criteria verified in W6 tests.

---

### Task W4 — Repositories: ApprovalRepository, AuditLogRepository

**Wave:** 2
**Requirements:** REQ-W1.6, REQ-W1.7
**Depends on:** W1, W2
**Estimated size:** Medium (2–3 hours)

**Description:**
Implement `ApprovalRepository` and `AuditLogRepository`.

**Deliverables:**
- `src/devflow_api/repositories/approval.py`

**`ApprovalAlreadyResolvedError` exception:**
```python
class ApprovalAlreadyResolvedError(DevFlowError):
    approval_id: int
    current_status: str
```
Defined in `src/devflow_core/exceptions.py`.

**Acceptance Criteria:**
1. `ApprovalRepository.resolve(id, "approved", ...)` raises `ApprovalAlreadyResolvedError` when `status != "pending"`.
2. `AuditLogRepository.log_event(...)` persists an audit entry with correct `event_type` and `actor`.
3. `AuditLogRepository.list_for_run(run_id)` returns entries ordered by `created_at` ascending.
4. `mypy --strict src/devflow_api/repositories/approval.py` exits with code 0.

**Definition of Done:** File committed; all criteria verified in W6 tests.

---

### Task W5 — Services: WorkflowService, ApprovalService

**Wave:** 2
**Requirements:** REQ-W1.5, REQ-W1.6, REQ-W1.7
**Depends on:** W3, W4
**Estimated size:** Medium (3–4 hours)

**Description:**
Implement `WorkflowService` and `ApprovalService` as described in design.md §5.1 and §5.2. Services own all state transition logic and audit logging. No service method reads `definition_json` or autonomously executes workflow steps.

**Deliverables:**
- `src/devflow_api/services/workflow.py`
- `src/devflow_api/services/approval.py`

**Key implementation notes:**
- `WorkflowService.create_run` logs `run_created` audit event with `actor="system"`. Does NOT read `definition_json`.
- `WorkflowService.transition_run` logs `run_status_changed` with `{"from": old, "to": new}` in payload. All transitions triggered by explicit calls only.
- `ApprovalService.request_approval` transitions run to `waiting_approval` THEN creates `ApprovalRequest`. Logs `approval_requested` audit event with `actor="system"`.
- `ApprovalService.resolve` resolves approval, transitions run (`approved` → `running`, `rejected` → `cancelled`), logs `approval_resolved` with `actor="user"`.
- Both services receive their repositories via `__init__` (dependency injection, not `get_settings()` calls).

**Acceptance Criteria:**
1. `WorkflowService.create_run(workflow_id)` creates a `WorkflowRun` with status `pending` and logs `run_created` audit event.
2. `ApprovalService.request_approval(run_id, ...)` logs `approval_requested` audit event and transitions run to `waiting_approval`.
3. `ApprovalService.resolve(id, "approved", ...)` transitions run to `running` and sets `resolved_at`.
4. `ApprovalService.resolve(id, "rejected", ...)` transitions run to `cancelled`.
5. `ApprovalService.resolve` on an already-resolved approval raises `ApprovalAlreadyResolvedError`.
6. No service method reads or acts on `definition_json`.
7. `mypy --strict src/devflow_api/services/workflow.py src/devflow_api/services/approval.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in W6 tests.

---

### Task W6 — Tests: Wave 2

**Wave:** 2
**Requirements:** REQ-T1.1, REQ-T1.3, REQ-T1.4
**Depends on:** W1–W5
**Estimated size:** Large (4–6 hours)

**Description:**
Write unit and integration tests covering all Wave 2 deliverables.

**Deliverables:**
- `tests/unit/test_workflow_service.py`
- `tests/unit/test_approval_service.py`
- `tests/integration/test_database.py` — extended with migrations 003–005 round-trips

**Required test cases:**
- `test_create_run_generates_audit_entry` — event_type = "run_created"
- `test_transition_run_valid` (pending → running)
- `test_transition_run_invalid` (pending → completed raises InvalidStatusTransitionError)
- `test_request_approval_logs_approval_requested` — event_type = "approval_requested"
- `test_request_approval_transitions_run_to_waiting`
- `test_resolve_approval_approved_resumes_run`
- `test_resolve_approval_rejected_cancels_run`
- `test_resolve_already_resolved_raises`
- `test_audit_list_ordered_by_created_at`
- `test_migration_003_004_005_round_trip` — upgrade/downgrade for migrations 003, 004, 005
- `test_delete_project_sets_workflow_project_id_null` — deleting a `Project` sets `Workflow.project_id` to `NULL` (`ON DELETE SET NULL`; REQ-DB1.3.5 — requires Wave 2 tables; deferred from Task P6 by F2 correction)
- `test_delete_workflow_cascades_to_workflow_runs` — deleting a `Workflow` deletes its `WorkflowRun` records (`ON DELETE CASCADE` on `WorkflowRun.workflow_id`; REQ-DB1.3.6 — requires Wave 2 tables; deferred from Task P6 by F2 correction)
- `test_delete_workflow_run_sets_audit_log_workflow_run_id_null` — deleting a `WorkflowRun` sets `WorkflowAuditLog.workflow_run_id` to `NULL` (`ON DELETE SET NULL`; REQ-DB1.3.7 — requires Wave 2 tables; deferred from Task P6 by F2 correction)
- `test_insert_invalid_foreign_key_raises_integrity_error` — inserting `WorkflowRun` with non-existent `workflow_id` raises `IntegrityError` (REQ-DB1.3.8 — requires Wave 2 tables; deferred from Task P6 by F2 correction)

**Acceptance Criteria:**
1. All new tests pass.
2. No Phase 0 or Wave 1 test is broken.
3. `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0.
4. All tests use in-memory or `tmp_path` SQLite (no `devflow.db` created).

**Definition of Done:** Files committed; all criteria verified.

---

## Wave 3 — Workflow API and Streamlit

---

### Task A1 — Routers: workflows and workflow-runs

**Wave:** 3
**Requirements:** REQ-W1.4, REQ-W1.5
**Depends on:** Wave 2 merged
**Estimated size:** Medium (3–4 hours)

**Description:**
Implement `src/devflow_api/routers/workflows.py` with all workflow and run endpoints defined in design.md §10.2.

**Deliverables:**
- `src/devflow_api/routers/workflows.py`
- `src/devflow_api/schemas/workflow.py` — `WorkflowCreate`, `WorkflowUpdate`, `WorkflowResponse`, `WorkflowRunResponse`, `AuditLogEntry`

**Acceptance Criteria:**
1. `POST /api/v1/workflows` returns HTTP 201.
2. `GET /api/v1/workflows?project_id={id}` filters correctly.
3. `POST /api/v1/workflows/{id}/runs` returns HTTP 201 with `status=pending`.
4. `GET /api/v1/workflow-runs/{run_id}/audit` returns audit entries ordered by `created_at`.
5. `DELETE /api/v1/workflows/{id}` returns 204 and cascades run deletion.
6. `mypy --strict src/devflow_api/routers/workflows.py src/devflow_api/schemas/workflow.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in A5 tests.

---

### Task A2 — Router: approvals

**Wave:** 3
**Requirements:** REQ-W1.6
**Depends on:** A1
**Estimated size:** Small (1–2 hours)

**Description:**
Implement `src/devflow_api/routers/approvals.py` with the three approval endpoints from design.md §10.3.

**Deliverables:**
- `src/devflow_api/routers/approvals.py`
- `src/devflow_api/schemas/approval.py` — `ApprovalResponse`, `ResolveApprovalRequest`

**Acceptance Criteria:**
1. `POST /api/v1/approvals/{id}/resolve` with `{"decision": "approved"}` returns HTTP 200.
2. `POST /api/v1/approvals/{id}/resolve` on already-resolved approval returns HTTP 409.
3. `GET /api/v1/approvals?status=pending` returns only pending approvals.
4. `mypy --strict src/devflow_api/routers/approvals.py src/devflow_api/schemas/approval.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in A5 tests.

---

### Task A3 — Exception handler extensions

**Wave:** 3
**Requirements:** REQ-I1.5, REQ-S1.1
**Depends on:** A1, A2
**Estimated size:** Small (1 hour)

**Description:**
Extend `src/devflow_api/middleware/error_handler.py` with handlers for all Phase 1 exceptions listed in design.md §15.

**Deliverables:**
- `src/devflow_api/middleware/error_handler.py` — extended
- `src/devflow_core/exceptions.py` — extended with `InvalidStatusTransitionError`, `ApprovalAlreadyResolvedError`, `ConfirmationRequiredError`
- `src/devflow_api/adapters/exceptions.py` — extended with `IntegrationExecutionError`, MCP errors

**Note:** `ConfirmationRequiredError` is used by `RepositoryService` (Wave 5, Task G2) but it is defined here in Wave 3 so the exception handler can be registered. Defining an exception before it is used in service code is correct — no forward reference problem.

**Acceptance Criteria:**
1. A route that raises `ApprovalAlreadyResolvedError` returns HTTP 409 with `code = "APPROVAL_ALREADY_RESOLVED"`.
2. A route that raises `InvalidStatusTransitionError` returns HTTP 422 with `code = "INVALID_STATUS_TRANSITION"`.
3. A route that raises `IntegrationExecutionError` returns HTTP 502 with `code = "INTEGRATION_ERROR"`.
4. A route that raises `MissingCredentialError` returns HTTP 403 with `code = "MISSING_CREDENTIAL"`.
5. `mypy --strict src/devflow_api/middleware/error_handler.py` exits with code 0.

**Definition of Done:** File committed; all criteria verified in A5 tests.

---

### Task A4 — Streamlit: Dashboard, Workflows page, History page

**Wave:** 3
**Requirements:** REQ-U1.1, REQ-U1.2, REQ-U1.3, REQ-U1.4
**Depends on:** A1, A2
**Estimated size:** Medium (3–5 hours)

**Description:**
Replace `1_Dashboard.py` placeholder with live metrics. Rename `6_Coding.py` to `6_Workflows.py` with live workflow list and approval actions. Rename `7_Testing.py` to `7_History.py` with execution history. Extend `APIClient` with workflow and approval methods.

**Deliverables:**
- `src/devflow_ui/pages/1_Dashboard.py` — replaced
- `src/devflow_ui/pages/6_Workflows.py` — renamed + implemented (remove `6_Coding.py`)
- `src/devflow_ui/pages/7_History.py` — renamed + implemented (remove `7_Testing.py`)
- `src/devflow_ui/app.py` — updated navigation entries for pages 6 and 7
- `src/devflow_ui/api_client.py` — extended with workflow and approval methods

**Acceptance Criteria:**
1. Dashboard page no longer contains "Phase 0" text.
2. `AppTest` for Dashboard, Workflows, History pages completes without exception (mocked `APIClient`).
3. Workflows page shows an "Approve" button for runs in `waiting_approval` status.
4. History page shows entries in reverse-chronological order.
5. `mypy --strict src/devflow_ui/pages/1_Dashboard.py src/devflow_ui/pages/6_Workflows.py src/devflow_ui/pages/7_History.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in A5 tests.

---

### Task A5 — Tests: Wave 3

**Wave:** 3
**Requirements:** REQ-T1.1, REQ-T1.2, REQ-T1.4
**Depends on:** A1–A4
**Estimated size:** Large (4–6 hours)

**Description:**
Write unit and smoke tests for all Wave 3 deliverables.

**Deliverables:**
- `tests/unit/test_workflows_router.py`
- `tests/unit/test_approvals_router.py`
- `tests/smoke/test_ui_pages.py` — extended with new page tests

**Required test cases:**
- `test_create_workflow_returns_201`
- `test_list_workflows_filter_by_project_id`
- `test_create_run_returns_pending_status`
- `test_resolve_approval_approved_200`
- `test_resolve_approval_already_resolved_409`
- `test_invalid_status_transition_returns_422`
- `test_missing_credential_returns_403`
- `test_dashboard_page_renders` (mocked APIClient)
- `test_workflows_page_renders` (mocked APIClient)
- `test_history_page_renders` (mocked APIClient)

**Acceptance Criteria:**
1. All new tests pass.
2. No prior test is broken.
3. `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0.
4. All tests complete without network access.

**Definition of Done:** Files committed; all criteria verified.

---

## Wave 4 — Integration Execution

---

### Task I1 — Adapter exceptions

**Wave:** 4
**Requirements:** REQ-I1.5, REQ-M1.4, REQ-M1.5
**Depends on:** Wave 3 merged
**Estimated size:** Small (< 1 hour)

**Description:**
Add `IntegrationExecutionError` and all MCP exception classes to `src/devflow_api/adapters/exceptions.py`.

**Deliverables:**
- `src/devflow_api/adapters/exceptions.py` — extended

**New exceptions:**
```python
class IntegrationExecutionError(DevFlowError):
    integration_name: str
    action: str
    status_code: int | None
    message: str

class MCPServerNotFoundError(DevFlowError): ...
class MCPConnectionError(DevFlowError): ...
class MCPTimeoutError(DevFlowError): ...
class MCPPermissionError(DevFlowError): ...
class MCPSecretResolutionError(DevFlowError): ...
```

**Note on `exceptions.py` split:** `ConfirmationRequiredError`, `InvalidStatusTransitionError`, `ApprovalAlreadyResolvedError` are defined in `src/devflow_core/exceptions.py` (Task A3). `IntegrationExecutionError` and all MCP errors are defined here in `src/devflow_api/adapters/exceptions.py` (this task). No overlap.

**Acceptance Criteria:**
1. All new exception classes importable from `devflow_api.adapters.exceptions`.
2. `mypy --strict src/devflow_api/adapters/exceptions.py` exits with code 0.
3. No Phase 0 adapter import is broken.

**Definition of Done:** File committed; all criteria verified.

---

### Task I2 — Live adapter: GitHubAdapter

**Wave:** 4
**Requirements:** REQ-I1.1
**Depends on:** I1
**Estimated size:** Medium (3–4 hours)

**Description:**
Implement `src/devflow_api/adapters/live/github.py` with the full `GitHubAdapter` as defined in design.md §8.1.

**Deliverables:**
- `src/devflow_api/adapters/live/__init__.py`
- `src/devflow_api/adapters/live/github.py`

**Acceptance Criteria:**
1. `GitHubAdapter.create_issue` calls GitHub API with correct Authorization header.
2. `GitHubAdapter` raises `MissingCredentialError` when `GITHUB_TOKEN is None` before any network call.
3. `GitHubAdapter` raises `IntegrationExecutionError` on 4xx/5xx responses.
4. All requests use 10-second timeout via `httpx.AsyncClient(timeout=10.0)`.
5. `mypy --strict src/devflow_api/adapters/live/github.py` exits with code 0.
6. Unit tests mock `httpx.AsyncClient` and require no network access.

**Definition of Done:** Files committed; all criteria verified in I7 tests.

---

### Task I3 — Live adapters: OllamaAdapter and FigmaAdapter

**Wave:** 4
**Requirements:** REQ-I1.2, REQ-I1.3
**Depends on:** I1
**Estimated size:** Medium (2–3 hours)

**Description:**
Implement `src/devflow_api/adapters/live/ollama.py` and `src/devflow_api/adapters/live/figma.py`.

**Deliverables:**
- `src/devflow_api/adapters/live/ollama.py`
- `src/devflow_api/adapters/live/figma.py`

**Acceptance Criteria:**
1. `OllamaAdapter.generate` calls `{OLLAMA_BASE_URL}/api/generate` with configurable timeout (from `Settings.OLLAMA_TIMEOUT_SECONDS`).
2. `OllamaAdapter.health_check()` returns `{"status": "unavailable", ...}` when Ollama is not running (connection refused, no raise).
3. `FigmaAdapter.get_file` raises `MissingCredentialError` when `FIGMA_TOKEN is None`.
4. `mypy --strict src/devflow_api/adapters/live/ollama.py src/devflow_api/adapters/live/figma.py` exits with code 0.
5. Unit tests mock `httpx.AsyncClient`.

**Definition of Done:** Files committed; all criteria verified in I7 tests.

---

### Task I4 — MCP client: MCPServerConfig, MCPClient, MCPLiveAdapter, MCPService

**Wave:** 4
**Requirements:** REQ-M1.1, REQ-M1.2, REQ-M1.3, REQ-M1.4, REQ-M1.5, REQ-M1.6, REQ-M1.7, REQ-M1.8
**Depends on:** I1
**Estimated size:** Large (4–6 hours)

**Description:**
Implement `src/devflow_api/adapters/mcp_client.py` with `MCPServerConfig`, `MCPClient`, `MCPToolResult`, and secret interpolation. Implement `src/devflow_api/adapters/live/mcp_live.py` with `MCPLiveAdapter`. Implement `src/devflow_api/services/mcp_service.py` with `MCPService` (the approval gate layer). Implement `src/devflow_api/repositories/approval_request.py` with `ApprovalRequestRepository`. Add `mcp>=1.0,<2.0` to `requirements/base.txt`. Generate and commit a lockfile.

**Deliverables:**
- `src/devflow_api/adapters/mcp_client.py`
- `src/devflow_api/adapters/live/mcp_live.py`
- `src/devflow_api/services/mcp_service.py` — MCPService (approval gate + audit events)
- `src/devflow_api/repositories/approval_request.py` — ApprovalRequestRepository (get_by_id, create, consume_atomic)
- `src/devflow_api/adapters/exceptions.py` — extended with `MCPApprovalRequiredError`, `MCPApprovalExpiredError`
- `requirements/base.txt` — add `mcp>=1.0,<2.0` (after checking `pyproject.toml` for an existing `mcp` declaration; use the existing version if present)
- `requirements/requirements.lock` (or equivalent) — generated lockfile committed

**Key implementation notes:**
- Use `mcp` Python SDK's `stdio_client` and `ClientSession`.
- Secret interpolation pattern: `${VAR_NAME}` in `env` values is resolved ONLY if `VAR_NAME.upper()` resolves to a `SecretStr` attribute on `Settings`. If the attribute exists but is not `SecretStr`, or does not exist, raise `MCPSecretResolutionError`.
- Log `arg_keys = list(arguments.keys())` — NEVER log argument values.
- Terminate subprocess unconditionally in `finally` using SIGTERM → 5s grace → SIGKILL sequence.
- Subprocess MUST be launched with `env=resolved_env` (not `env=None`).
- `MCPService.invoke_tool` signature: `invoke_tool(server_name, tool_name, arguments, actor_id, workflow_run_id=None, approval_request_id=None)`. The parameter is `approval_request_id: str | None`, NOT `approval_record`. Callers MUST NOT pass a pre-built approval object.
- `MCPService` retrieves the `ApprovalRequest` from `ApprovalRequestRepository` by `approval_request_id` and validates it internally (status == APPROVED, not expired, field match, not already CONSUMED).
- Atomic consumption: `ApprovalRequestRepository.consume_atomic` sets `status = CONSUMED` and `consumed_at = now(UTC)` via `UPDATE ... WHERE status = 'APPROVED' AND id = ?`. If 0 rows updated, raises `MCPApprovalRequiredError` (replay prevention and concurrent-call safety).
- `MCPService` owns the approval gate: allow-list check → classification → retrieve `ApprovalRequest` by `approval_request_id` → validate → `consume_atomic` → `MCPClient.call_tool`. All seven MCP audit events are emitted by `MCPService`.
- No code path may call `MCPClient.call_tool` directly from a router, adapter, or any other layer; all MCP calls must go through `MCPService.invoke_tool`.
- All MCP tests MUST run offline using mocked subprocess responses; no live MCP server is required (REQ-M1.8.3).

**Acceptance Criteria:**
1. `MCPClient.call_tool("test_server", "read_file", {"path": "/x"})` with mocked subprocess returns `MCPToolResult(stub=False)`.
2. Calling an unconfigured server raises `MCPServerNotFoundError`.
3. `${GITHUB_TOKEN}` in env resolves to token value at process launch (not logged).
4. `${MISSING}` raises `MCPSecretResolutionError` before process launch.
5. Tool not in `allowed_tools` raises `MCPPermissionError` before subprocess starts.
6. Subprocess is launched with `env=resolved_env` (verified by inspecting mock call arguments).
7. `MCPService.invoke_tool` signature accepts `approval_request_id: str | None`, not an `ApprovalRecord` object.
8. `MCPService.invoke_tool` raises `MCPApprovalRequiredError` for `consequential`/`unknown` tools when `approval_request_id` is None or the retrieved `ApprovalRequest` is not found/not APPROVED.
9. `MCPService.invoke_tool` raises `MCPApprovalExpiredError` for an `ApprovalRequest` with `expires_at` in the past.
10. `MCPService.invoke_tool` raises `MCPApprovalRequiredError` for an `ApprovalRequest` whose `tool_name` or `arguments_hash` or `actor_id` does not match the current invocation.
11. `MCPService.invoke_tool` raises `MCPApprovalRequiredError` for an `ApprovalRequest` with `status = CONSUMED` (replay prevention).
12. `ApprovalRequestRepository.consume_atomic` atomically sets `status = CONSUMED` and `consumed_at`; two concurrent calls with the same `approval_request_id` result in exactly one success and one `MCPApprovalRequiredError`.
13. `MCPService.invoke_tool` emits all seven MCP audit events to `AuditLogRepository`.
14. `mypy --strict src/devflow_api/adapters/mcp_client.py src/devflow_api/adapters/live/mcp_live.py src/devflow_api/services/mcp_service.py src/devflow_api/repositories/approval_request.py` exits with code 0.
15. All MCP unit tests mock MCP subprocess; no real process is spawned.
16. `requirements/base.txt` contains `mcp>=1.0,<2.0` (or the actual constraint if `pyproject.toml` already declares a different `mcp` version).

**Named tests (all 8 MUST be present in `tests/unit/test_mcp_service.py`):**
- `test_forged_approval_record_rejected` — verifies a caller cannot bypass the gate by constructing an in-memory approval object; `MCPService.invoke_tool` only accepts `approval_request_id` and retrieves the record from the repository
- `test_expired_approval_rejected_at_invocation` — `ApprovalRequest.expires_at` in the past raises `MCPApprovalExpiredError`
- `test_mismatched_tool_name_rejected` — `ApprovalRequest.tool_name` differs from invoked tool → `MCPApprovalRequiredError`
- `test_mismatched_arguments_hash_rejected` — `ApprovalRequest.arguments_hash` does not match SHA-256 of supplied arguments → `MCPApprovalRequiredError`
- `test_replay_after_consumption_rejected` — second call with an already-`CONSUMED` `ApprovalRequest` → `MCPApprovalRequiredError`
- `test_concurrent_consumption_safe` — two concurrent `invoke_tool` calls with the same `approval_request_id` result in exactly one success and one `MCPApprovalRequiredError` (atomic consumption via `consume_atomic`)
- `test_read_only_tool_no_approval_required` — `read_only` classified tool proceeds without `approval_request_id`
- `test_no_direct_mcp_client_bypass` — integration test verifying no router or adapter calls `MCPClient.call_tool` directly without going through `MCPService.invoke_tool`

**Additional named tests (MUST also be present — from prior specification):**
- `test_unknown_tool_denied_without_approval` — MCPService raises MCPApprovalRequiredError for unknown tool without approval_request_id
- `test_consequential_tool_denied_without_approval` — MCPService raises MCPApprovalRequiredError for consequential tool without approval_request_id
- `test_read_only_tool_permitted_without_approval` — MCPService allows read_only tool without approval_request_id (subject to allow-list)
- `test_direct_mcp_client_call_blocked_without_service_layer` — integration test verifying no router/adapter bypasses MCPService
- `test_expired_mcp_approval_rejected` — MCPService raises MCPApprovalExpiredError for ApprovalRequest with expires_at in past
- `test_expired_mcp_approval_emits_approval_expired_event` — verifies an expired ApprovalRequest emits `mcp_approval_expired` audit event, NOT `mcp_approval_denied`
- `test_missing_approval_emits_approval_missing_event` — verifies absence of ApprovalRequest (or absent approval_request_id) emits `mcp_approval_missing` audit event
- `test_allowlist_alone_insufficient_for_consequential_tool` — verifies a tool that passes allow-list check but lacks ApprovalRequest is still denied for consequential classification
- `test_mcp_client_uses_locked_sdk_version` — asserts installed `mcp` package version satisfies `>=1.0,<2.0`
- `test_mcp_integration_runs_offline_with_mock_subprocess` — full MCPService → MCPClient flow with mocked subprocess, no network

**Definition of Done:** Files committed; all criteria verified in I7 tests.

---

### Task I5 — Registry extension: get_live, register_live

**Wave:** 4
**Requirements:** REQ-I1.4
**Depends on:** I2, I3, I4
**Estimated size:** Small (1–2 hours)

**Description:**
Extend `src/devflow_api/adapters/registry.py` with `get_live` and `register_live`. Update `src/devflow_api/main.py` `create_app()` to register live adapters at startup.

**Deliverables:**
- `src/devflow_api/adapters/registry.py` — extended
- `src/devflow_api/main.py` — extended with live adapter registration

**Acceptance Criteria:**
1. `registry.get_live("github")` returns `GitHubAdapter` when `GITHUB_TOKEN` is set.
2. `registry.get_live("github")` returns `GitHubStubAdapter` when `GITHUB_TOKEN` is `None`.
3. `registry.get("github")` still returns `GitHubStubAdapter` (Phase 0 behaviour preserved).
4. `registry.get_live` never raises; it always returns a valid adapter.
5. `mypy --strict src/devflow_api/adapters/registry.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in I7 tests.

---

### Task I6 — Integrations router and Settings extension

**Wave:** 4
**Requirements:** REQ-I1.6, REQ-M1.1, REQ-S1.2
**Depends on:** I5
**Estimated size:** Small (1–2 hours)

**Description:**
Extend `src/devflow_api/routers/integrations.py` to use `get_live()` for health checks and add `mode: Literal["live", "stub"]` to `IntegrationSummary`. Add `OLLAMA_TIMEOUT_SECONDS` and `GITHUB_API_BASE_URL` / `FIGMA_API_BASE_URL` to `Settings`. Add `MCP_SERVERS_CONFIG` JSON validator to `Settings`.

**Deliverables:**
- `src/devflow_api/routers/integrations.py` — extended
- `src/devflow_api/schemas/integration.py` — `IntegrationSummary` gains `mode` field
- `src/devflow_core/config.py` — new fields
- `.env.example` — new keys documented

**Acceptance Criteria:**
1. `GET /api/v1/integrations` returns entries with `mode: "live"` or `mode: "stub"`.
2. `GET /api/v1/integrations/github/health` returns live status when `GITHUB_TOKEN` is set.
3. `Settings.MCP_SERVERS_CONFIG = ""` parses to `[]` without error.
4. `Settings.MCP_SERVERS_CONFIG = "[invalid json"` raises `ValidationError`.
5. `mypy --strict src/devflow_core/config.py src/devflow_api/schemas/integration.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in I7 tests.

---

### Task I7 — Streamlit: Integrations page, Settings page + Tests: Wave 4

**Wave:** 4
**Requirements:** REQ-I1.6, REQ-U1.5, REQ-T1.1, REQ-T1.2
**Depends on:** I1–I6
**Estimated size:** Large (4–6 hours)

**Description:**
Replace `9_Integrations.py` placeholder with live integration status. Extend `10_Settings.py` with Phase 1 configuration summary. Write all Wave 4 tests.

**Deliverables:**
- `src/devflow_ui/pages/9_Integrations.py` — replaced
- `src/devflow_ui/pages/10_Settings.py` — extended
- `src/devflow_ui/api_client.py` — extended with integration methods
- `tests/unit/test_live_adapters.py` — GitHub, Ollama, Figma adapter unit tests (mocked)
- `tests/unit/test_mcp_client.py` — MCPClient unit tests (mocked subprocess)
- `tests/unit/test_mcp_service.py` — MCPService approval gate unit tests (all 18 named tests from I4)
- `tests/smoke/test_ui_pages.py` — extended with Integrations and Settings smoke tests

**Required test cases (security-critical — must be named):**
- `test_github_adapter_timeout_raises_integration_error` — when httpx raises TimeoutException, GitHubAdapter raises IntegrationExecutionError (REQ-S1.2)
- `test_github_token_not_in_log_records` — asserts GITHUB_TOKEN value does not appear in any structlog record during adapter init or invocation (REQ-S1.3.2)
- `test_mcp_subprocess_launched_with_explicit_env` — verifies `asyncio.create_subprocess_exec` is called with `env=resolved_env` and not `env=None` (REQ-S1.5.1, REQ-S1.5.4)
- `test_mcp_secret_values_not_in_log_records` — asserts secret values in `MCPServerConfig.env` do not appear in log output (REQ-M1.5.3)

**All test cases:**
- `test_github_adapter_creates_issue` (mocked httpx)
- `test_github_adapter_raises_missing_credential`
- `test_github_adapter_timeout_raises_integration_error` ← security required
- `test_github_token_not_in_log_records` ← security required
- `test_ollama_adapter_generate` (mocked httpx)
- `test_ollama_health_check_unavailable_when_not_running`
- `test_figma_adapter_raises_missing_credential`
- `test_mcp_call_tool_returns_result` (mocked subprocess)
- `test_mcp_permission_denied_before_subprocess`
- `test_mcp_subprocess_launched_with_explicit_env` ← security required
- `test_mcp_secret_values_not_in_log_records` ← security required
- `test_unknown_tool_denied_without_approval` ← MCP approval gate required
- `test_consequential_tool_denied_without_approval` ← MCP approval gate required
- `test_read_only_tool_permitted_without_approval` ← MCP approval gate required
- `test_direct_mcp_client_call_blocked_without_service_layer` ← MCP bypass prevention required
- `test_expired_mcp_approval_rejected` ← MCP approval gate required
- `test_expired_mcp_approval_emits_approval_expired_event` ← D4 required (distinct audit event for expiry)
- `test_missing_approval_emits_approval_missing_event` ← D4 required (distinct audit event for missing)
- `test_allowlist_alone_insufficient_for_consequential_tool` ← F3 required (allow-list ≠ sufficient for consequential)
- `test_mcp_client_uses_locked_sdk_version` ← SDK version required
- `test_mcp_integration_runs_offline_with_mock_subprocess` ← offline testing required
- `test_forged_approval_record_rejected` ← F1 required (caller cannot fabricate approval object)
- `test_expired_approval_rejected_at_invocation` ← F1 required (expires_at validation at invocation)
- `test_mismatched_tool_name_rejected` ← F1 required (tool_name binding)
- `test_mismatched_arguments_hash_rejected` ← F1 required (arguments_hash binding)
- `test_replay_after_consumption_rejected` ← F1 required (one-time use)
- `test_concurrent_consumption_safe` ← F1 required (atomic consumption)
- `test_read_only_tool_no_approval_required` ← F1 required (read_only bypass)
- `test_no_direct_mcp_client_bypass` ← F1 required (no-bypass rule)
- `test_integrations_page_renders` (mocked APIClient)
- `test_settings_page_renders` (mocked APIClient)

**Acceptance Criteria:**
1. Integrations page renders without exception (mocked `APIClient`).
2. Settings page shows MCP server count and GitHub connection status.
3. All live adapter tests pass without network access.
4. All MCP client tests pass without spawning real processes.
5. `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0.
6. All four security-critical test cases listed above pass.

**Definition of Done:** Files committed; all criteria verified.

---

## Wave 5 — GitHub Workflow Orchestration

---

### Task G1 — Repository model, RepositoryConfigRepository, GitHubConfirmation model, and migration 006

**Wave:** 5
**Requirements:** REQ-G1.1, REQ-G1.4, REQ-DB1.1
**Depends on:** Wave 4 merged (and implicitly W2 — migration 005 creates the repository_configs table)
**Estimated size:** Medium (3–4 hours)

**Description:**
Implement `src/devflow_api/models/repository.py` with `RepositoryConfig`. The `repository_configs` table was created by migration `005_add_repository_tables.py` in Wave 2 (Task W2). Implement `src/devflow_api/models/github_confirmation.py` with the SQLAlchemy `GitHubConfirmation` model (F2 correction — SQLite-backed, not in-memory). Author migration `006_add_github_confirmations.py` chaining from migration `005`. The table does not exist until this migration is applied; `GitHubConfirmationRepository` reads from the `github_confirmations` table created by migration 006.

**Deliverables:**
- `src/devflow_api/models/repository.py`
- `src/devflow_api/repositories/repository_config.py`
- `src/devflow_api/models/github_confirmation.py` — `GitHubConfirmation` SQLAlchemy model (see design.md §3.7a and §8.2)
- `src/devflow_api/repositories/github_confirmation.py` — `GitHubConfirmationRepository` with `get_by_id`, `create`, `consume_atomic`
- `alembic/versions/006_add_github_confirmations.py` — migration chaining from 005

**Migration 006 required content:**
```python
revision = "006_add_github_confirmations"
down_revision = "005_add_repository_tables"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "github_confirmations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("repo_full_name", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("parameters_hash", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("operation IN ('branch_create', 'pr_create')", name="ck_github_confirmations_operation"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_github_confirmations_expires", "github_confirmations", ["expires_at"])
    op.create_index("idx_github_confirmations_actor", "github_confirmations", ["actor_id"])

def downgrade() -> None:
    op.drop_index("idx_github_confirmations_actor", table_name="github_confirmations")
    op.drop_index("idx_github_confirmations_expires", table_name="github_confirmations")
    op.drop_table("github_confirmations")
```

**Dependency note:** This task depends on Wave 2 having been merged (which includes migration 005 creating the repository_configs table). The dependency `"Wave 4 merged"` implies Wave 2 was already merged; migration 005 must exist. Migration 006 chains from 005 and must be applied for `GitHubConfirmationRepository` to function.

**Acceptance Criteria:**
1. `RepositoryConfig` model importable with correct FK and unique constraint.
2. `RepositoryConfig` column definitions exactly match the `repository_configs` DDL in migration `005_add_repository_tables.py`.
3. `RepositoryConfigRepository.get_by_coords(project_id, owner, repo)` returns the matching config.
4. Creating a duplicate `(project_id, owner, repo)` raises a SQLAlchemy `IntegrityError`.
5. `GitHubConfirmation` model importable from `devflow_api.models.github_confirmation`.
6. `GitHubConfirmationRepository.consume_atomic` atomically sets `used_at` and returns the updated record; raises `ConfirmationAlreadyUsedError` if already used.
7. `alembic upgrade head` from `005_add_repository_tables` applies migration 006 without error.
8. `alembic downgrade -1` from `006` removes `github_confirmations` table without error.
9. Migration 006 file has `revision = "006_add_github_confirmations"` and `down_revision = "005_add_repository_tables"` exactly.
10. `mypy --strict src/devflow_api/models/repository.py src/devflow_api/models/github_confirmation.py src/devflow_api/repositories/repository_config.py src/devflow_api/repositories/github_confirmation.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in G5 tests.

---

### Task G2 — RepositoryService and GitHubAdapter extension

**Wave:** 5
**Requirements:** REQ-G1.2, REQ-G1.3, REQ-G1.4, REQ-G1.5, REQ-G1.6
**Depends on:** G1
**Estimated size:** Large (4–6 hours)

**Description:**
Extend `GitHubAdapter` with branch, PR, and CI endpoints. Implement `RepositoryService` with `GitHubConfirmation` gates (REQ-G1.4, REQ-G1.5). All mutating GitHub operations route through `RepositoryService`; no router handler calls mutating `GitHubAdapter` methods directly. Implement `GitHubConfirmationRepository` for persistence.

**Deliverables:**
- `src/devflow_api/adapters/live/github.py` — extended with branch/PR/CI methods
- `src/devflow_api/services/repository.py` — `RepositoryService` with `issue_confirmation` + `create_branch` + `create_pull_request`
- `src/devflow_api/repositories/github_confirmation.py` — `GitHubConfirmationRepository`
- `src/devflow_api/models/github_confirmation.py` — `GitHubConfirmation` model (or Pydantic model for in-memory use)
- `src/devflow_core/exceptions.py` — extended with `ConfirmationExpiredError`, `ConfirmationMismatchError`, `ConfirmationAlreadyUsedError`, `ConfirmationNotFoundError`

**Key implementation notes:**
- `RepositoryService.issue_confirmation` persists a `GitHubConfirmation` to SQLite (via `GitHubConfirmationRepository.create`) with `expires_at = now(UTC) + TTL` (configurable via `Settings.GITHUB_CONFIRMATION_TTL_SECONDS: int = 600`, default 10 minutes). In-memory storage is NOT acceptable (F2 correction).
- `RepositoryService.create_branch` accepts `confirmation_id: str`, not `confirmed: bool`.
- Validation sequence: load confirmation from DB → check operation match → check parameters_hash match → check not expired → check not used → atomically set `used_at` via `GitHubConfirmationRepository.consume_atomic` → call adapter.
- `consume_atomic` uses `UPDATE github_confirmations SET used_at = ? WHERE id = ? AND used_at IS NULL`. If rowcount is 0, `ConfirmationAlreadyUsedError` is raised (concurrent duplicate-consumption prevention).
- Recovery/idempotency: If the GitHub API call fails after `used_at` is set, the caller receives the error and may re-check GitHub state manually. The confirmation cannot be reused; a new one must be issued.
- Duplicate `confirmation_id` after use returns HTTP 409.
- All confirmation gate audit events (`github_confirmation_issued`, `github_action_authorized`, `github_action_executed`, `github_action_rejected`) are logged.

**Acceptance Criteria:**
1. `RepositoryService.create_branch(..., confirmation_id=None)` raises `ConfirmationRequiredError`.
2. `RepositoryService.create_branch(..., confirmation_id="<expired>")` raises `ConfirmationExpiredError`.
3. `RepositoryService.create_branch(..., confirmation_id="<used>")` raises `ConfirmationAlreadyUsedError`.
4. `RepositoryService.create_branch(..., confirmation_id="<mismatched_params>")` raises `ConfirmationMismatchError`.
5. `RepositoryService.create_branch(..., confirmation_id="<valid>")` calls `GitHubAdapter.create_branch` and logs `branch_created` audit event with `actor="user"`.
6. `RepositoryService.create_pull_request(..., confirmation_id=None)` raises `ConfirmationRequiredError`.
7. `RepositoryService.create_pull_request(..., confirmation_id="<valid>")` calls `GitHubAdapter.create_pull_request` and logs `pr_created` audit event.
8. `mypy --strict src/devflow_api/services/repository.py` exits with code 0.

**Named tests (must be present in `tests/unit/test_repository_service.py`):**
- `test_branch_create_requires_confirmation`
- `test_pr_create_requires_confirmation`
- `test_expired_confirmation_rejected`
- `test_used_confirmation_rejected_on_replay`
- `test_mismatched_parameters_rejected`
- `test_boolean_flag_alone_insufficient` — POST body with `{"confirmed": true}` (without `confirmation_id`) returns HTTP 422
- `test_github_confirmation_persisted_to_db` — verifies a `GitHubConfirmation` record is written to the SQLite `github_confirmations` table (not held in memory) after `POST /api/v1/github-confirmations` (REQ-G1.4.9 — F2 correction)
- `test_confirmation_expires_after_ttl` — verifies an expired confirmation (expires_at in the past) returns HTTP 422 with code `CONFIRMATION_EXPIRED` (REQ-G1.4.10 — F2 correction)
- `test_replay_rejected_after_use` — verifies re-submitting a used `confirmation_id` returns HTTP 409 (REQ-G1.4.11 — F2 correction)
- `test_parameter_mismatch_rejected` — verifies a confirmation with a different `parameters_hash` returns HTTP 422 with code `CONFIRMATION_MISMATCH` (REQ-G1.4.12 — F2 correction)
- `test_concurrent_consumption_safe` — verifies two concurrent requests with the same `confirmation_id` result in exactly one success and one HTTP 409 via atomic `consume_atomic` (REQ-G1.4.13 — F2 correction)
- `test_recovery_after_github_api_failure` — verifies the system reports failure correctly when the GitHub API call fails after `used_at` is set (REQ-G1.4.14 — F2 correction)

**Definition of Done:** Files committed; all criteria verified in G5 tests.

---

### Task G3 — Repositories router

**Wave:** 5
**Requirements:** REQ-G1.1, REQ-G1.2, REQ-G1.3, REQ-G1.4, REQ-G1.5, REQ-G1.6
**Depends on:** G2
**Estimated size:** Medium (3–4 hours)

**Description:**
Implement `src/devflow_api/routers/repositories.py` with all repository and GitHub endpoints from design.md §10.4. Verify no `/merge` route is registered. All mutating endpoints call `RepositoryService` methods — no router handler calls `GitHubAdapter` directly.

**Deliverables:**
- `src/devflow_api/routers/repositories.py`
- `src/devflow_api/schemas/repository.py`

**Acceptance Criteria:**
1. `POST /api/v1/repositories/{id}/branches` with `confirmed=false` returns HTTP 422.
2. `POST /api/v1/repositories/{id}/pull-requests` with `confirmed=false` returns HTTP 422.
3. No route containing the path segment `merge` is registered.
4. `GET /api/v1/repositories/{id}/branches/{branch}/ci` returns `list[CheckRunSummary]`.
5. `mypy --strict src/devflow_api/routers/repositories.py src/devflow_api/schemas/repository.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in G5 tests.

---

### Task G4 — Settings page: GitHub status

**Wave:** 5
**Requirements:** REQ-U1.5
**Depends on:** G3
**Estimated size:** Small (< 1 hour)

**Description:**
Update `10_Settings.py` to show GitHub connection status (connected / no token). Add `get_repositories` method to `APIClient`.

**Deliverables:**
- `src/devflow_ui/pages/10_Settings.py` — extended with GitHub status section
- `src/devflow_ui/api_client.py` — add `list_repositories(project_id=None)`

**Acceptance Criteria:**
1. Settings page shows "GitHub: connected" when `GITHUB_TOKEN` is set, "GitHub: no token configured" otherwise.
2. `AppTest` with mocked `APIClient` completes without exception.
3. `mypy --strict src/devflow_ui/pages/10_Settings.py` exits with code 0.

**Definition of Done:** Files committed; all criteria verified in G5 tests.

---

### Task G5 — Tests: Wave 5 and final CI verification

**Wave:** 5
**Requirements:** REQ-T1.1, REQ-T1.2, REQ-T1.3, REQ-T1.4
**Depends on:** G1–G4
**Estimated size:** Large (5–7 hours)

**Description:**
Write all Wave 5 tests and run full CI verification to confirm Phase 1 completion.

**Deliverables:**
- `tests/unit/test_repository_service.py`
- `tests/unit/test_repositories_router.py`
- `tests/smoke/test_ui_pages.py` — final Settings page test
- `tests/integration/test_database.py` — complete migration round-trip (all 5 migrations: 001→002→003→004→005)
- Updated `docs/openapi.json` — regenerated with `make docs` or `python scripts/export_openapi.py`

**Required test cases:**
- `test_create_branch_requires_confirmation`
- `test_create_pr_requires_confirmation`
- `test_no_merge_endpoint_exists` — asserts `/merge` not in openapi.json routes
- `test_branch_creation_logs_audit_event` — event_type = "branch_created"
- `test_pr_creation_logs_audit_event` — event_type = "pr_created"
- `test_migration_full_round_trip` — all 6 migrations (001→002→003→004→005→006) up and down in a tmp_path SQLite
- `test_settings_page_github_status` (mocked APIClient)
- `test_github_confirmation_persisted_to_db` (from G2 — integrated full-stack verification)
- `test_confirmation_expires_after_ttl` (from G2 — integrated full-stack verification)
- `test_replay_rejected_after_use` (from G2 — integrated full-stack verification)
- `test_parameter_mismatch_rejected` (from G2 — integrated full-stack verification)
- `test_concurrent_consumption_safe` (from G2 — concurrent test using async)
- `test_recovery_after_github_api_failure` (from G2 — error path test)

**Final verification commands (record output in commit message):**
```
pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing
mypy --strict src/
ruff check .
```

**Acceptance Criteria:**
1. All tests pass.
2. `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0.
3. `mypy --strict src/` exits with code 0.
4. `ruff check .` exits with code 0.
5. `docs/openapi.json` contains no path with the word `merge`.
6. All Phase 0 tests continue to pass.
7. `alembic upgrade head` from Phase 0 schema reaches `"006_add_github_confirmations"` without error (migration chain: 001→002→003→004→005→006). (F2 correction)
8. All six GitHubConfirmation named tests pass: `test_github_confirmation_persisted_to_db`, `test_confirmation_expires_after_ttl`, `test_replay_rejected_after_use`, `test_parameter_mismatch_rejected`, `test_concurrent_consumption_safe`, `test_recovery_after_github_api_failure`. (F2 correction)

**Definition of Done:** All files committed; all criteria verified; full verification output recorded in commit message.
