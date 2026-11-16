# DevFlow AI — Phase 1: Functional Orchestration Design

**Version:** 1.5.8
**Status:** Corrected — Wave 5 GitHub Orchestration Security Specification
**Scope:** Phase 1 — Functional Orchestration
**Branch:** feature/phase1-wave5-github-orchestration
**Base commit:** bceb9bab4328fe4ca5ed068a25fa9f541841f0ff
**Last Updated:** 2026-11-16
**Supersedes:** v1.3.0 (F1–F3 corrections applied — see .agents/tasks/phase1-v1.4.0-correction-report.md)

**Version history:**
- v1.0.0 — Initial specification
- v1.1.0 — Eight independent-review findings applied
- v1.2.0 — Five amendment-round findings applied
- v1.3.0 — Final specification correction: F1–F5 and D1–D4 applied (FK test split, GitHubConfirmation persistence + migration 006, MCP authorization 8-step sequence, superseded guidance labelled, metadata corrected, D2 MCP binary trust statement, D4 audit event distinction)
- v1.4.0 — 2026-11-15 — Corrections F1 (MCP approval authorization via approval_request_id), F2 (FK cascade test corrections), F3 (metadata), F6 (MCPApproval dedicated schema + migration 007), F7 (outdated MCP authorization references), F8 (Wave 1 FK tests), F9 (approval consumption and external failure handling). Branch: feature/phase1-specification-planning, Base: aaaaacb703124fc31b0e757b2bf1739c4fb225c9.
- v1.5.0 — Migration and dependency alignment: 006↔007 swap (006=mcp_approvals Wave 4, 007=github_confirmations Wave 5); MCPApproval model/repository/migration moved to Wave 4 Task I4; down_revision chain updated (007 chains from 006_add_mcp_approvals); §13 file layout updated; traceability matrix updated. Branch: feature/phase1-specification-planning.
- v1.5.1 — MCP Security Hardening Pass (S1–S2): S1 workflow_run_id binding rules added to §7.5 (invoke_tool signature, 6 binding rules, trusted_workflow_run_id server-side parameter); S2 atomic consumption contract strengthened in §7.5 and MCPApprovalRepository (8-step transaction sequence, SQLite concurrency assumptions, datetime.now(UTC) enforcement); mcp_approval_rejected audit event with reason field added to §7.5 and §16; 9 new named negative tests added to §7.5. Branch: feature/phase1-specification-planning.
- v1.5.2 — 2026-11-15 — Type and Concurrency Alignment Pass (T1–T2): T1 trusted_workflow_run_id type corrected UUID → int | None throughout §7.5 (invoke_tool signature, consume_atomic signature, MCPApproval model notes); T2 SQLite concurrency model clarified: removed incorrect "SQLAlchemy connection pooling serializes writes" claim; added BEGIN IMMEDIATE transaction semantics, busy_timeout policy, and retry rules to §7.5 consume_atomic; 5 new T2 named negative tests added. Branch: feature/phase1-specification-planning.
- v1.5.3 — 2026-11-15 — Final PR Readiness Gate (C1–C2): C1 redundant workflow_run_id parameter removed from invoke_tool; only trusted_workflow_run_id: int | None remains; added explicit §7.5 statement that trusted_workflow_run_id is resolved from server-side session context and never from tool arguments or client-supplied fields. C2 consume_atomic signature extended with all binding fields (actor_id, mcp_server_id, tool_name, arguments_hash) as explicit parameters; in-transaction verification of all bindings documented with 8-step algorithm; test_approval_modified_between_validation_and_consumption added to Wave 4 I4 and I7. Branch: feature/phase1-specification-planning.

- v1.5.4 — 2026-11-16 — Wave 3 Response Contract Correction (W3-RC): resolved the REQ-W1.5.4 ↔ §11.3 conflict reported in docs/reports/phase1-wave3-codex-report.md. §11.3 WorkflowRunResponse now carries `approvals: list[ApprovalResponse]` (every associated ApprovalRequest — all statuses — ordered by `created_at` ascending) AND `pending_approvals: list[ApprovalResponse]` (pending-only subset, backward compatibility); both default to `[]` (never null); read-only projection, no approval-lifecycle change. Added `ApprovalRepository.list_for_run(run_id)` to §4.3 (read-only data source; no migration). Added ADR-0013. Traceability matrix: REQ-W1.5 → §10.2, §9, §11.3. See requirements REQ-W1.5.4a–c; tasks A1, A5. Branch: feature/phase1-wave3-integration-execution.
- v1.5.5 — 2026-11-16 — Wave 4 Specification Conflict Resolution (W4-CR): resolved four Wave 4 conflicts reported in docs/reports/phase1-wave4-spec-resolution.md. Conflict A (MCP transport): §7.2 `MCPClient.call_tool` transport corrected — `MCPClient` launches the configured server via an explicit-environment subprocess (`asyncio.create_subprocess_exec(..., env=resolved_env)`) feeding the MCP Python SDK `ClientSession`; SDK `stdio_client` dropped because it merges `get_default_environment()` into the supplied env (breaking isolation) and exposes no 5 s termination grace; required system env vars explicitly added to `resolved_env`; §7.6 offline-testing note updated. Conflict B (approval binding): §3.7a `mcp_approvals.workflow_run_id` FK changed from `ON DELETE SET NULL` to `ON DELETE RESTRICT`; §3.7 FK table and §7.5 model notes updated so an APPROVED approval bound to a deleted run cannot become a valid unbound (NULL) authorization. Conflict C (live adapter capability metadata): §6.2 corrected — live adapters return `IntegrationCapability(available_in_phase_0=False)` (the Phase 0 schema is immutable `Literal[False]`; `available_in_phase_0=True` is impossible); live/stub distinction via `execution_mode`, `mode`, and `stub=False`. Conflict D (page numbering): §12.1 confirmed — Wave 4 updates existing `9_Integrations.py` and `10_Settings.py`; no new Integrations/Settings pages created. Branch: feature/phase1-wave4-integration-execution.
- v1.5.6 — 2026-11-16 — Wave 4 Final FK Contract Correction (W4-FK): resolved the v1.5.5 RESTRICT contradiction. SQLite's `ON DELETE RESTRICT` is unconditional — it blocks deletion whenever ANY referencing `mcp_approvals` row exists, regardless of approval status — so the v1.5.5 acceptance criteria (CONSUMED/PENDING/REJECTED/EXPIRED approvals permit deletion) were unimplementable. §3.7a `mcp_approvals.workflow_run_id` FK changed from `ON DELETE RESTRICT` back to `ON DELETE SET NULL`, combined with a database-enforced BEFORE DELETE trigger on `workflow_runs` (`trg_workflow_runs_before_delete_expire_approved_mcp_approvals`) that sets `status='EXPIRED'` on every APPROVED MCPApproval referencing the run BEFORE the FK clears the reference; §3.7a SQL DDL + model, §3.7 FK behaviors table, §3.7 deletion-invariant note + security rationale, and §7.5 model notes + EXPIRED-rejection note updated. Verified against real SQLite foreign-key enforcement (SQLite library 3.49.1, 17/17 checks pass): the BEFORE DELETE trigger fires before the FK SET NULL action (APPROVED→EXPIRED, not left APPROVED-with-NULL-FK); CONSUMED/PENDING/REJECTED/EXPIRED preserved with FK cleared to NULL; originally-unbound approvals unaffected; the EXPIRED approval cannot be consumed (`consume_atomic` 0 rows); cascaded deletion (workflow delete → run cascade) expires APPROVED with default SQLite settings (no `recursive_triggers` PRAGMA required); project delete does not reach runs; ROLLBACK restores the approval. The deletion/binding test set updated: 1 renamed, 4 kept (rationale updated), 4 added. See docs/reports/phase1-wave4-fk-final-resolution.md. Branch: feature/phase1-wave4-integration-execution.
- v1.5.7 — 2026-11-16 — Wave 4 PENDING Approval Lifecycle Correction (W4-PA): resolved the remaining MCP authorization lifecycle gap. A PENDING MCPApproval bound to workflow run X survived deletion of X with `status='PENDING'` and `workflow_run_id=NULL`, indistinguishable from an originally-unbound PENDING approval; a future resolve operation could promote it to APPROVED, authorizing an unbound invocation. Fix: §3.7a BEFORE DELETE trigger updated from `status='APPROVED'` to `status IN ('PENDING','APPROVED')` and renamed `trg_workflow_runs_before_delete_expire_mcp_approvals` (W4-PA); §3.7 FK behaviors table and §3.7 deletion-invariant + security rationale notes updated to cover PENDING; §3.7a MCPApproval model comment updated. Valid-status-transitions list gains `PENDING → EXPIRED` (run-deletion path, distinct from TTL). Run-deletion trigger note extended: approval-resolution flow MUST only resolve approvals whose status is PENDING; an EXPIRED approval cannot be resolved or promoted. Verified with real SQLite: 23/23 assertions pass (direct deletion, cascade, promotion prevention, rollback, unbound unaffected, consume_atomic rejection). See docs/reports/phase1-wave4-pending-approval-resolution.md. Branch: feature/phase1-wave4-integration-execution.
- v1.5.8 — 2026-11-16 — Wave 5 GitHub Orchestration Security Specification (W5-GC): §3.7b updated — `github_confirmations` table gains `status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED','EXPIRED','USED'))` column; BEFORE DELETE trigger `trg_workflow_runs_before_delete_expire_github_confirmations` added to migration 007 DDL; `GitHubConfirmationRepository.consume_atomic` updated to use `WHERE status='ISSUED'`; §3.7 FK behaviors table gains github_confirmations row; §8.2 security contract expanded with 13-rule security contract, execution outcomes (SUCCEEDED/FAILED/INDETERMINATE), `github_action_failed` and `github_confirmation_expired` audit events; §7.5b GitHub failure semantics clarified with the three outcomes; 10 new named negative tests added to §8.2; migration 007 DDL spec updated with status column, CHECK constraint, and trigger DDL. SQLite verification: 10/10 assertions pass. Branch: feature/phase1-wave5-github-orchestration.

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
3. **Approval gates are non-bypassable.** Consequential actions cannot proceed without a valid `GitHubConfirmation` record (GitHub branch/PR creation) or a resolved `ApprovalRequest` (workflow step approval gate). MCP consequential/unknown tool calls additionally require an `MCPApproval` record (UUID PK, `mcp_approvals` table) validated by `MCPService` — NOT an `ApprovalRequest` from the workflow approval system. The simple `confirmed: bool` field is replaced by `confirmation_id: str` referencing a `GitHubConfirmation`.
4. **Secrets never leave `Settings`.** Live adapters read credentials only from `SecretStr` fields; `RedactSecretsProcessor` runs on every log record.
5. **Tests are offline-first.** Live adapter tests mock `httpx.AsyncClient` and MCP subprocess interactions.

**Phase 1 workflow execution boundary:** WorkflowRun tracks state for human-approved processes. Autonomous AI provider invocation from `definition_json` is NOT implemented in Phase 1 and is deferred to Phase 2. All WorkflowRun state transitions are triggered by explicit API calls to `WorkflowService.transition_run`.

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

### 3.0 Phase 1 Migration Sequence

The Phase 0 head revision is `"001_create_initial_tables"`. Phase 1 adds four migrations in this exact linear chain:

**Before (Phase 0 head):**
```
None (base)
  └── 001_create_initial_tables   ← Phase 0 HEAD
```

**After (Phase 1 head):**
```
None (base)
  └── 001_create_initial_tables
        └── 002_add_project_tags_column   ← Wave 1 (Task P1)
              └── 003_add_workflow_tables   ← Wave 2 (Task W2)
                    └── 004_add_approval_audit_tables   ← Wave 2 (Task W2)
                          └── 005_add_repository_tables   ← Wave 2 (Task W2)
                                └── 006_add_mcp_approvals   ← Wave 4 (Task I4)
                                      └── 007_add_github_confirmations   ← Wave 5 (Task G1)
```

| Revision ID | `down_revision` | File | Wave | Tables / columns |
|---|---|---|---|---|
| `"001_create_initial_tables"` | `None` | `001_create_initial_tables.py` | Phase 0 | projects, learning_items, integration_configs |
| `"002_add_project_tags_column"` | `"001_create_initial_tables"` | `002_add_project_tags_column.py` | Wave 1 | ALTER TABLE projects ADD tags_json |
| `"003_add_workflow_tables"` | `"002_add_project_tags_column"` | `003_add_workflow_tables.py` | Wave 2 | workflows, workflow_runs |
| `"004_add_approval_audit_tables"` | `"003_add_workflow_tables"` | `004_add_approval_audit_tables.py` | Wave 2 | approval_requests, workflow_audit_log |
| `"005_add_repository_tables"` | `"004_add_approval_audit_tables"` | `005_add_repository_tables.py` | Wave 2 | repository_configs |
| `"006_add_mcp_approvals"` | `"005_add_repository_tables"` | `006_add_mcp_approvals.py` | Wave 4 | mcp_approvals |
| `"007_add_github_confirmations"` | `"006_add_mcp_approvals"` | `007_add_github_confirmations.py` | Wave 5 | github_confirmations |

**Wave 4 migration note:** Migration 006 (`006_add_mcp_approvals`) is a Wave 4 deliverable (Task I4). Wave 4 completion requires migration 006 applied and MCP approval tests passing. Wave 4 has no dependency on any Wave 5 deliverable.

Each revision ID string in the table above is the exact string that MUST appear in the Python file as `revision = "..."`. The `down_revision` column is the exact string that MUST appear as `down_revision = "..."` in the next file.

**Rationale for Wave 1 migration being 002:** Migration 002 (`tags_json` column) can be applied from the Phase 0 head independently of the workflow tables. This allows Wave 1 to pass `alembic upgrade head` without requiring Wave 2 migrations to exist first.

### 3.1 Addition to projects table (migration 002)

```sql
-- Migration 002_add_project_tags_column
-- revision = "002_add_project_tags_column"
-- down_revision = "001_create_initial_tables"
ALTER TABLE projects ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]';
```

The `Project` model gains `tags_json: Mapped[str] = mapped_column(Text, server_default="[]")`. The `ProjectResponse` schema deserialises `tags_json` via a `@model_validator` into `tags: list[str]`.

### 3.2 workflows (migration 003)

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

**Note:** `definition_json` stores workflow step definitions for future Phase 2 execution. Phase 1 does not read or execute the contents of this column.

### 3.3 workflow_runs (migration 003)

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

**WorkflowRun status constraint includes exactly:** `pending`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled`. The value `paused` is NOT in this constraint. `paused` appears only in the `workflows` table status (a workflow definition may be paused), not in `workflow_runs`.

### 3.4 approval_requests (migration 004)

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

### 3.5 workflow_audit_log (migration 004)

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

### 3.6 repository_configs (migration 005)

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

**Note on model/migration timing:** The `repository_configs` table is created by migration `005_add_repository_tables.py` in Wave 2 (Task W2). The SQLAlchemy `RepositoryConfig` model and `RepositoryConfigRepository` are written in Wave 5 (Task G1). Alembic migrations use inline `sa.Table` definitions and do not require the ORM model to exist. The table exists in the database before the ORM model; the first code that uses the ORM interface against `repository_configs` is in Wave 5.

---

### 3.7a mcp_approvals (migration 006 — Wave 4)

Migration `006_add_mcp_approvals.py` is authored in Wave 4 (Task I4), chaining from `005_add_repository_tables`. The `MCPApproval` SQLAlchemy model, `MCPApprovalRepository`, and this migration are all Wave 4 deliverables. Wave 4 completion requires migration 006 applied and MCP approval tests passing. Wave 4 has no dependency on any Wave 5 deliverable.

**Separation note:** The `approval_requests` table (integer PK, `ApprovalRequest` model) is used exclusively for workflow step approval gates. It is NOT used for MCP tool authorization. `MCPApproval` (UUID PK, `mcp_approvals` table) is the sole authorization record for MCP consequential tool invocations.

```sql
CREATE TABLE mcp_approvals (
    id              TEXT     PRIMARY KEY,                 -- UUID as text
    mcp_server_id   TEXT     NOT NULL,                   -- MCPServerConfig.name
    tool_name       TEXT     NOT NULL,
    arguments_hash  TEXT     NOT NULL,                   -- SHA-256 of canonical JSON
    actor_id        TEXT     NOT NULL,
    workflow_run_id INTEGER  REFERENCES workflow_runs(id) ON DELETE SET NULL,
    status          TEXT     NOT NULL DEFAULT 'PENDING'
                             CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED')),
    requested_at    DATETIME NOT NULL,
    resolved_at     DATETIME,
    expires_at      DATETIME NOT NULL,
    consumed_at     DATETIME
);
CREATE INDEX idx_mcp_approvals_server ON mcp_approvals(mcp_server_id);
CREATE INDEX idx_mcp_approvals_status ON mcp_approvals(status);
CREATE INDEX idx_mcp_approvals_expires ON mcp_approvals(expires_at);

-- W4-PA: BEFORE DELETE trigger expires BOTH PENDING and APPROVED MCP approvals
-- before the ON DELETE SET NULL FK action clears the reference. Expiring
-- PENDING prevents an orphaned PENDING approval (FK cleared to NULL) from being
-- later promoted to APPROVED and authorizing an unbound invocation. See §3.7
-- for the deletion-invariant note and the security rationale. This trigger is
-- created by migration 006 (Task I4) and must exist wherever mcp_approvals does.
CREATE TRIGGER trg_workflow_runs_before_delete_expire_mcp_approvals
BEFORE DELETE ON workflow_runs
FOR EACH ROW
BEGIN
    UPDATE mcp_approvals
       SET status = 'EXPIRED'
     WHERE workflow_run_id = OLD.id
       AND status IN ('PENDING', 'APPROVED');
END;
```

**Required revision header:**
```python
# 006_add_mcp_approvals.py
revision = "006_add_mcp_approvals"
down_revision = "005_add_repository_tables"
```

**MCPApproval SQLAlchemy model:**
```python
# src/devflow_api/models/mcp_approval.py
class MCPApproval(Base):
    __tablename__ = "mcp_approvals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)          # UUID as text
    mcp_server_id: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_hash: Mapped[str] = mapped_column(Text, nullable=False) # SHA-256
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True
        # SET NULL + BEFORE DELETE trigger (W4-PA): a PENDING or APPROVED MCPApproval
        # bound to a run is expired (status -> EXPIRED) by the trigger BEFORE the FK
        # clears the reference, so it cannot become a valid unbound (NULL)
        # authorization after run deletion, and an orphaned PENDING approval cannot
        # be later promoted to APPROVED (it is already EXPIRED, and the resolution
        # flow only resolves PENDING approvals).
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="PENDING"
    )
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
```

**MCPApproval valid status transitions:**
- `PENDING` → `APPROVED` (human resolves as approved)
- `PENDING` → `REJECTED` (human resolves as rejected)
- `APPROVED` → `CONSUMED` (atomic consumption via `consume_atomic` before tool execution)
- `PENDING` → `EXPIRED` (TTL elapsed before resolution)
- `APPROVED` → `EXPIRED` (TTL elapsed before consumption)

**Run-deletion trigger (W4-PA):** a `PENDING` or `APPROVED` `MCPApproval` originally bound to a deleted `workflow_run` is set to `EXPIRED` by the BEFORE DELETE trigger (§3.7a) BEFORE the `ON DELETE SET NULL` action clears `workflow_run_id` to NULL. This is a distinct path to `EXPIRED` from TTL expiry, and it is database-enforced (a direct SQL `DELETE FROM workflow_runs` cannot bypass it). An approval resolution flow MUST only resolve approvals whose status is `PENDING`; an `EXPIRED` approval (whether by TTL or by the run-deletion trigger) cannot be resolved or promoted to `APPROVED`.

---

### 3.7b github_confirmations (migration 007 — Wave 5)

Migration `007_add_github_confirmations.py` is authored in Wave 5 (Task G1), chaining from `006_add_mcp_approvals`. The `GitHubConfirmation` SQLAlchemy model, `GitHubConfirmationRepository`, and this migration are all Wave 5 deliverables.

```sql
CREATE TABLE github_confirmations (
    id              TEXT     PRIMARY KEY,                 -- UUID as text
    repo_full_name  TEXT     NOT NULL,
    operation       TEXT     NOT NULL
                             CHECK (operation IN ('branch_create', 'pr_create')),
    parameters_hash TEXT     NOT NULL,                   -- SHA-256 of canonical JSON
    actor_id        TEXT     NOT NULL,
    workflow_run_id INTEGER  REFERENCES workflow_runs(id) ON DELETE SET NULL,
    issued_at       DATETIME NOT NULL,
    expires_at      DATETIME NOT NULL,
    used_at         DATETIME,                            -- NULL until first use
    status          TEXT     NOT NULL DEFAULT 'ISSUED'
                             CHECK (status IN ('ISSUED','EXPIRED','USED'))
                             -- W5-GC: BEFORE DELETE trigger sets ISSUED→EXPIRED before FK SET NULL
);
CREATE INDEX idx_github_confirmations_expires ON github_confirmations(expires_at);
CREATE INDEX idx_github_confirmations_actor   ON github_confirmations(actor_id);

-- W5-GC: BEFORE DELETE trigger expires ISSUED GitHubConfirmations before FK SET NULL
-- prevents a formerly-bound ISSUED confirmation from becoming a valid unbound (NULL→NULL)
-- authorization after run deletion. See §8.2 security contract.
CREATE TRIGGER trg_workflow_runs_before_delete_expire_github_confirmations
BEFORE DELETE ON workflow_runs
FOR EACH ROW
BEGIN
    UPDATE github_confirmations SET status = 'EXPIRED'
    WHERE workflow_run_id = OLD.id AND status = 'ISSUED';
END;
```

**Required revision header:**
```python
# 007_add_github_confirmations.py
revision = "007_add_github_confirmations"
down_revision = "006_add_mcp_approvals"
```

**GitHubConfirmation SQLAlchemy model:**
```python
# src/devflow_api/models/github_confirmation.py
class GitHubConfirmation(Base):
    __tablename__ = "github_confirmations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)          # UUID
    repo_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_hash: Mapped[str] = mapped_column(Text, nullable=False)  # SHA-256
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True
        # SET NULL + BEFORE DELETE trigger (W5-GC): an ISSUED GitHubConfirmation
        # bound to a run is expired (status -> EXPIRED) by the trigger BEFORE the FK
        # clears the reference, so it cannot become a valid unbound (NULL)
        # authorization after run deletion.
    )
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="ISSUED"
        # W5-GC: CHECK IN ('ISSUED','EXPIRED','USED')
        # ISSUED — created, not yet consumed or expired
        # EXPIRED — set by BEFORE DELETE trigger on workflow_runs when bound run deleted
        # USED — set atomically by consume_atomic on first use
    )
```

**GitHubConfirmationRepository (F2 correction):**
```python
# src/devflow_api/repositories/github_confirmation.py
class GitHubConfirmationRepository(BaseRepository[GitHubConfirmation]):
    async def get_by_id(self, confirmation_id: str) -> GitHubConfirmation | None: ...

    async def create(
        self,
        id: str,
        repo_full_name: str,
        operation: Literal["branch_create", "pr_create"],
        parameters_hash: str,
        actor_id: str,
        workflow_run_id: int | None,
        issued_at: datetime,
        expires_at: datetime,
    ) -> GitHubConfirmation: ...

    async def consume_atomic(self, confirmation_id: str, now: datetime) -> GitHubConfirmation:
        """
        Atomically sets used_at = now and status = 'USED' on the first call.
        Raises ConfirmationAlreadyUsedError if status != 'ISSUED' (0 rows updated —
        covers both already-USED and EXPIRED-by-trigger confirmations).
        Uses: UPDATE ... SET used_at=now, status='USED'
              WHERE id=? AND status='ISSUED' AND expires_at > now
        rowcount == 1 required; 0 rows → ConfirmationAlreadyUsedError.
        BEGIN IMMEDIATE transaction prevents TOCTOU between SELECT and UPDATE.
        Returns updated record.
        """
```

**Persistence rationale (F2):** `GitHubConfirmation` records are persisted to SQLite (not held in-memory) so that:
1. Confirmation records survive service restarts — a confirmation issued before a restart can still be consumed after.
2. Concurrent duplicate-consumption is prevented via atomic `UPDATE WHERE used_at IS NULL` (not possible with in-memory maps).
3. Audit trail is complete — issued and used timestamps are durable.

---

### 3.7 SQLite Foreign-Key Enforcement

SQLite does not enforce foreign key constraints unless `PRAGMA foreign_keys=ON` is executed on each connection after it is opened. Without this PRAGMA, `ON DELETE CASCADE` and `ON DELETE SET NULL` are silently ignored, making every FK-dependent integrity guarantee in §3.2–§3.6 non-operational.

**Implementation:** Register a `'connect'` SQLAlchemy event on the async engine in `src/devflow_api/database.py`:

```python
from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry

@event.listens_for(engine.sync_engine, "connect")
def configure_sqlite_pragmas(
    connection: DBAPIConnection, record: ConnectionPoolEntry
) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.fetchone()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.fetchone()
    finally:
        cursor.close()
```

**Foreign-key relationships and ON DELETE behaviors (F2 correction):**

The three workflow-domain FK relationships and their delete behaviors are:

| Column | References | ON DELETE behavior | Effect |
|---|---|---|---|
| `Workflow.project_id` | `projects.id` | **SET NULL** | Deleting a Project sets `Workflow.project_id` to NULL; the Workflow record is NOT deleted. |
| `WorkflowRun.workflow_id` | `workflows.id` | **CASCADE** | Deleting a Workflow deletes all its WorkflowRun records. |
| `WorkflowAuditLog.workflow_run_id` | `workflow_runs.id` | **SET NULL** | Deleting a WorkflowRun sets `WorkflowAuditLog.workflow_run_id` to NULL; audit log entries are NOT deleted. |
| `MCPApproval.workflow_run_id` | `workflow_runs.id` | **SET NULL** (W4-PA) | Deleting a WorkflowRun first fires a BEFORE DELETE trigger (`trg_workflow_runs_before_delete_expire_mcp_approvals`) that sets `status='EXPIRED'` on every PENDING and APPROVED `MCPApproval` referencing the run, then the FK action clears `workflow_run_id` to NULL for all referencing rows. A PENDING or APPROVED approval cannot become a valid unbound (NULL) authorization: it is EXPIRED (rejected by `consume_atomic`, and not promotable by the resolution flow, which only resolves PENDING) before the binding is cleared. |
| `GitHubConfirmation.workflow_run_id` | `workflow_runs.id` | **SET NULL** (W5-GC) | Deleting a WorkflowRun first fires a BEFORE DELETE trigger (`trg_workflow_runs_before_delete_expire_github_confirmations`) that sets `status='EXPIRED'` on every ISSUED `GitHubConfirmation` referencing the run, then the FK action clears `workflow_run_id` to NULL. An ISSUED confirmation cannot become a valid unbound (NULL→NULL) authorization: it is EXPIRED (rejected by `consume_atomic WHERE status='ISSUED'`) before the binding is cleared. USED and EXPIRED confirmations are untouched by the trigger; their FK is cleared to NULL (audit history preserved). |

**Note:** Deleting a Project does NOT cascade to WorkflowRun records. The chain is: Project deleted → Workflow.project_id set NULL (Workflow remains) → no further cascade. WorkflowRun records are only deleted when their parent Workflow is deleted.

**MCPApproval deletion-invariant note (W4-FK, refined by W4-PA):** `MCPApproval.workflow_run_id` uses `ON DELETE SET NULL` combined with a BEFORE DELETE trigger on `workflow_runs` (`trg_workflow_runs_before_delete_expire_mcp_approvals`), NOT `ON DELETE RESTRICT`. SQLite's `RESTRICT` is unconditional — it blocks deletion whenever any referencing row exists, regardless of approval status — so it could not satisfy the requirement that CONSUMED/REJECTED/EXPIRED approvals permit deletion. The trigger invalidates PENDING and APPROVED MCP approvals before the FK SET NULL action clears the reference. This prevents a PENDING or APPROVED approval from becoming a valid unbound (NULL→NULL) authorization after run deletion: the approval is set to `status='EXPIRED'` (rejected by `consume_atomic`'s `status='APPROVED'` check) before `workflow_run_id` becomes NULL. Expiring PENDING (not just APPROVED) closes the additional gap that a PENDING approval, once orphaned by a run deletion, could otherwise be indistinguishable from an originally-unbound PENDING approval and later promoted to APPROVED — the trigger sets it to `EXPIRED` first, and the approval-resolution flow only resolves approvals whose status is `PENDING`, so an `EXPIRED` approval cannot be promoted. The `ON DELETE SET NULL` action requires `PRAGMA foreign_keys=ON` (REQ-DB1.3); the trigger is a plain SQL DDL trigger that fires on any DELETE of a `workflow_runs` row (direct or cascaded — verified to fire under SQLite's default settings without `PRAGMA recursive_triggers`). Originally-unbound approvals (`workflow_run_id IS NULL` at creation) are unaffected (the trigger only updates rows `WHERE workflow_run_id = OLD.id`) and keep REQ-M2.5 NULL-to-NULL semantics. CONSUMED/REJECTED/EXPIRED approvals are untouched by the trigger and have their `workflow_run_id` cleared to NULL (history preserved). The trigger runs in the same transaction as the DELETE, so a rolled-back run deletion restores PENDING and APPROVED approvals to their original status with their original binding intact.

**Security rationale (W4-FK, refined by W4-PA):** the BEFORE DELETE trigger on `workflow_runs` invalidates PENDING and APPROVED MCP approvals before the FK SET NULL action clears the reference. This prevents an APPROVED approval from becoming a valid unbound (NULL→NULL) authorization after run deletion, and prevents an orphaned PENDING approval from being later promoted to APPROVED and authorizing an unbound invocation. An EXPIRED approval cannot be resolved or promoted — the approval resolution flow rejects any approval whose status is not PENDING.

**Note on `alembic/env.py`:** The existing `alembic/env.py` already registers a `'connect'` event for `PRAGMA journal_mode=WAL`. During implementation, `PRAGMA foreign_keys=ON` must also be added to that same handler in `alembic/env.py`. The `alembic/env.py` file is out of scope for this specification-correction step and will be updated by the implementer alongside `src/devflow_api/database.py`.

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
    async def list_for_run(self, run_id: int) -> list[ApprovalRequest]:
        # All ApprovalRequest rows for run_id (every status: pending, approved,
        # rejected, expired), ordered by created_at ascending (ties by id).
        # Read-only: does not mutate approval state. Returns [] when the run
        # has no approvals. Feeds WorkflowRunResponse.approvals (§11.3, W3-RC).
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
        """
        Creates a WorkflowRun with status=pending.
        Logs run_created audit event with actor="system".
        Does NOT read definition_json or execute any steps.
        """

    async def transition_run(
        self,
        run_id: int,
        new_status: str,
        actor: str,
        payload: dict[str, object] | None = None,
    ) -> WorkflowRun:
        """
        Transitions run status and logs run_status_changed.
        All transitions are triggered by explicit API calls, not autonomous execution.
        """
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
        """
        Creates ApprovalRequest, transitions run to waiting_approval,
        and logs approval_requested audit event with actor="system".
        """

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
        Logs approval_resolved audit event with actor="user".
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
- Exposes `capability` as a `@property` returning an `IntegrationCapability` populated for the live integration. Per W4-CR Conflict C, `available_in_phase_0` MUST be `False` — the `IntegrationCapability` schema (`src/devflow_api/adapters/capability.py`) declares `available_in_phase_0: Literal[False]`, so `True` is impossible (pydantic `ValidationError`) and the Phase 0 schema is immutable and out of scope to modify. The live/stub distinction is expressed through `execution_mode` (`ExecutionMode.AUTOMATED_API` for live adapters), the per-response `stub=False` flag, and the `mode: Literal["live","stub"]` field on `IntegrationSummary` (Task I6). Live adapters populate `supported_actions`, `auth_required`, and `auth_type` from the live integration's real capabilities (e.g. `auth_required=True`, `auth_type="bearer"` for GitHub/Figma; `auth_required=False` for Ollama).

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
           Note: allowed_tools is a configuration-time permission control, not human approval.
        3. Interpolate env secrets (raises MCPSecretResolutionError if unresolvable).
           Only SecretStr Settings fields may be interpolated.
        4. Compose resolved_env:
              a. Start from interpolated MCPServerConfig.env.
              b. Explicitly add system vars required for child startup, by name from parent:
                 Windows: PATH, SYSTEMROOT, WINDIR, TEMP, TMP, PATHEXT, COMSPEC
                 POSIX:   PATH, HOME, LANG, LC_ALL, TMPDIR
              c. No other parent variables copied; no parent secrets inherited.
           W4-CR Conflict A: DO NOT use sdk.stdio_client or get_default_environment()
           — they merge the full parent env, breaking explicit isolation.
        5. Launch subprocess via asyncio.create_subprocess_exec(
               *command, *args,
               env=resolved_env,
               stdin=PIPE, stdout=PIPE, stderr=...
           )  — child receives ONLY resolved_env.
        6. Wrap subprocess stdio in SDK ClientSession(read_stream, write_stream).
           ClientSession.initialize() performs tool discovery.
        7. Call tool with timeout_seconds via ClientSession.call_tool().
        8. On completion/timeout: in finally block, send SIGTERM → wait 5 s grace
           → SIGKILL if still alive. Owned by MCPClient, not SDK stdio_client context.
        9. Log invocation (keys only, not values).

        W4-CR Conflict A — SDK transport decision:
        The SDK stdio_client helper is NOT used. SDK v1.x stdio_client calls
        get_default_environment() and merges the result into the supplied env dict,
        causing the child to inherit parent-process variables (PATH, USERPROFILE, etc.)
        that must NOT be inherited for explicit environment isolation (REQ-M1.5, REQ-S1.5).
        Additionally, stdio_client uses a fixed asyncio.Event-based cleanup with no
        configurable grace period, making the SIGTERM → 5 s → SIGKILL sequence
        impossible to implement via its context manager API.
        ClientSession is the SDK interface used here; subprocess ownership and cleanup
        remain entirely within MCPClient.
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

class MCPApprovalRequiredError(DevFlowError):
    server_name: str
    tool_name: str
    classification: str   # "consequential" | "unknown"

class MCPApprovalExpiredError(DevFlowError):
    server_name: str
    tool_name: str
```

---

### 7.5 MCPService — Approval Gate Layer

`MCPService` sits between routers/adapters and `MCPClient`. It owns the approval gate and emits the eight MCP audit events. No code path may call `MCPClient.call_tool` directly; all MCP tool invocations go through `MCPService.invoke_tool`.

**No-bypass rule:** No adapter, router, or Streamlit handler may import or instantiate `MCPClient` directly. All MCP invocations MUST go through `MCPService.invoke_tool`. This rule is enforced by architecture convention and verified by `test_no_direct_mcp_client_bypass`.

**C1 — Trusted workflow context (single parameter, server-side only):** `MCPService.invoke_tool` has exactly ONE workflow context parameter: `trusted_workflow_run_id: int | None`. The former `workflow_run_id` parameter has been removed. `trusted_workflow_run_id` is resolved by the application layer from the current execution session before calling `invoke_tool`. It is never read from tool arguments, request body, or any client-supplied field. Callers cannot select or override this value.

**Separation of approval systems:** The workflow `approval_requests` table (integer PK) is not used for MCP authorization. `MCPApproval` (UUID PK, `mcp_approvals` table) is the sole authorization record for MCP consequential tool invocations. `MCPService` MUST use `MCPApprovalRepository` and MUST NOT use `ApprovalRequestRepository`.

```python
# src/devflow_api/services/mcp_service.py

class MCPService:
    def __init__(
        self,
        mcp_client: MCPClient,
        audit_repo: AuditLogRepository,
        mcp_approval_repo: MCPApprovalRepository,   # F6: NOT ApprovalRequestRepository
    ) -> None: ...

    async def invoke_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, object],
        actor_id: str,
        mcp_approval_id: UUID | None = None,          # F6: UUID, NOT str approval_request_id
        trusted_workflow_run_id: int | None = None,   # C1/T1/S1: int | None (WorkflowRun.id is INTEGER PK); resolved from server-side session context ONLY; NEVER from tool arguments or any caller-supplied request field
    ) -> MCPToolResult:
        """
        Mandatory 9-step authorization sequence (F6/F7 correction):
        1. Verify MCP server is configured and enabled (raises MCPServerNotFoundError if absent).
        2. Verify tool is on the allow-list (REQ-M1.4). Raises MCPPermissionError if denied.
        3. Classify tool as read_only, consequential, or unknown.
        4. Default unknown → consequential (deny-by-default policy).
        5. For consequential/unknown tools: retrieve MCPApproval from
           MCPApprovalRepository by mcp_approval_id (REQ-M1.7, REQ-M2.x).
           - If mcp_approval_id is None or record not found:
             log mcp_approval_missing, raise MCPApprovalRequiredError.
           - MCPService retrieves the record internally — the caller MUST NOT
             pass a pre-built approval object.
           NOTE: MCPApprovalRepository is used here — NOT ApprovalRequestRepository.
        6. Validate retrieved MCPApproval:
           a. status MUST be APPROVED; otherwise raise MCPApprovalRequiredError.
           b. expires_at MUST be in the future; if expired:
              log mcp_approval_expired, raise MCPApprovalExpiredError.
              IMPORTANT: mcp_approval_expired is NOT mcp_approval_denied.
              Expiry is not a human rejection.
           c. mcp_server_id, tool_name, arguments_hash, and actor_id MUST match
              the current invocation; mismatch → MCPApprovalRequiredError.
           d. status MUST NOT be CONSUMED (replay prevention).
           e. (S1) workflow_run_id binding check using trusted_workflow_run_id
              (resolved from server-side session context, NOT from tool arguments):
              - approval.workflow_run_id = X AND trusted_workflow_run_id = Y (X ≠ Y):
                log mcp_approval_rejected(reason="workflow_run_mismatch"), raise MCPApprovalRequiredError.
              - approval.workflow_run_id non-NULL AND trusted_workflow_run_id = NULL:
                log mcp_approval_rejected(reason="missing_workflow_context"), raise MCPApprovalRequiredError.
              - approval.workflow_run_id = NULL AND trusted_workflow_run_id non-NULL:
                log mcp_approval_rejected(reason="unexpected_workflow_context"), raise MCPApprovalRequiredError.
              This check runs BEFORE consume_atomic. A rejected invocation does NOT consume the approval.
        7. Call MCPApprovalRepository.consume_atomic(mcp_approval_id, actor_id, server_name, tool_name, arguments_hash, trusted_workflow_run_id, now=datetime.now(UTC)).
           consume_atomic executes a single DB transaction (C2/S2/T2 — all binding fields verified in-transaction):
             i.   BEGIN IMMEDIATE; — acquires write lock immediately, preventing TOCTOU.
             ii.  SELECT the MCPApproval row within the transaction.
             iii. Within SAME transaction verify ALL bindings:
                  a. actor_id matches; b. mcp_server_id matches; c. tool_name matches; d. arguments_hash matches;
                  e. workflow_run_id matches trusted_workflow_run_id (NULL-safe: both NULL, or both equal integers);
                  f. status = APPROVED; g. expires_at > now; h. consumed_at IS NULL.
             iv.  UPDATE mcp_approvals SET status='CONSUMED', consumed_at=now WHERE id=? AND status='APPROVED' AND expires_at > now AND consumed_at IS NULL.
             v.   Verify rowcount == 1 — if 0 rows updated → ROLLBACK; raise ConsumedError; log mcp_approval_already_consumed.
             vi.  COMMIT BEFORE launching subprocess.
           SQLite write-lock semantics: SQLite serializes writes at the database-file level. BEGIN IMMEDIATE
           prevents another writer from modifying the row between SELECT and UPDATE. This is a SQLite
           engine guarantee, NOT a SQLAlchemy connection-pool guarantee.
           busy_timeout (recommended: 5000 ms): if BEGIN IMMEDIATE blocks due to contention, SQLite waits
           up to busy_timeout ms before raising OperationalError/busy. Treat OperationalError as an
           authorization failure; the caller may retry the DB operation only (not the MCP invocation),
           up to a configurable maximum (e.g. 3 retries with exponential backoff).
           - If 0 rows updated (already consumed or any binding mismatch): raise ConsumedError → MCPApprovalRequiredError.
           - Log mcp_approval_granted.
        8. Execute: call MCPClient.call_tool.
           - On subprocess launch: log mcp_tool_invoked (approval consumed, subprocess started).
           - On success: log mcp_tool_completed.
           - On exception/timeout: log mcp_tool_failed, re-raise.
           - IMPORTANT: execution failure does NOT restore MCPApproval to APPROVED. See §7.6b.
           - After commit in step 7, subprocess launch and failure do NOT roll back consumption.
        9. Record all audit events without leaking credentials or argument values.
           Each audit event includes mcp_approval_id for traceability.

        Note: allow-list alone is NOT sufficient for consequential tools. Both checks are additive
        and sequential: allow-list check runs first; then classification + approval gate.
        Note: read_only tools proceed without mcp_approval_id (subject to allow-list only).
        Note: trusted_workflow_run_id comes from server-side session context ONLY. Any
        workflow_run_id value in the tool arguments payload is ignored for binding purposes.
        Note: trusted_workflow_run_id is int | None — WorkflowRun.id is an INTEGER primary key
        (T1). It is NOT a UUID. Only MCPApproval.id is UUID.
        Note: datetime.now(UTC) is used throughout — datetime.utcnow() MUST NOT appear.
        Note (C1): invoke_tool has exactly ONE workflow context parameter: trusted_workflow_run_id:
        int | None. The redundant workflow_run_id parameter has been removed. trusted_workflow_run_id
        is resolved by the application layer from the current execution session before calling
        invoke_tool. It is never read from tool arguments, request body, or any client-supplied field.
        """
```

**SUPERSEDED — ApprovalRequest-based MCPService (F6 correction):** The earlier design (v1.3.0, v1.4.0 pre-F6) specified `MCPService` using `ApprovalRequestRepository` and accepting `approval_request_id: str`. This is SUPERSEDED. `MCPService` now uses `MCPApprovalRepository` and accepts `mcp_approval_id: UUID | None`. The `ApprovalRequestRepository` and `approval_requests` table remain for workflow step approvals only.

**MCPApproval model (MCP-specific, persisted to `mcp_approvals` table — F6 correction):**
```python
# SQLAlchemy model — see §3.7b for full DDL and model definition.
# Fields:
#   id              — TEXT (UUID as text; primary key; supplied as mcp_approval_id by caller)
#   mcp_server_id   — TEXT (must match the target MCP server's MCPServerConfig.name)
#   tool_name       — TEXT (must match the tool being invoked)
#   arguments_hash  — TEXT (SHA-256 of canonical JSON of arguments; must match)
#   actor_id        — TEXT (must match actor_id in the invoke_tool call)
#   workflow_run_id — INTEGER | None (nullable FK → workflow_runs.id ON DELETE SET NULL — W4-FK: a BEFORE DELETE trigger on workflow_runs expires (status -> EXPIRED) every APPROVED approval referencing the run before the FK clears the reference, so an APPROVED approval bound to a deleted run can NOT become a valid unbound NULL authorization)
#   status          — TEXT CHECK IN ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED')
#   requested_at    — DATETIME (UTCDateTime)
#   resolved_at     — DATETIME | None (UTCDateTime; set when APPROVED or REJECTED)
#   expires_at      — DATETIME (UTCDateTime; must be in the future for the call to proceed)
#   consumed_at     — DATETIME | None (UTCDateTime; set atomically on first successful consumption)
```

**MCPApprovalRepository (§3.7a above — full interface):**
```python
# src/devflow_api/repositories/mcp_approval.py
class MCPApprovalRepository(BaseRepository[MCPApproval]):
    async def create(self, approval: MCPApproval) -> MCPApproval: ...
    async def get_by_id(self, id: UUID) -> MCPApproval | None: ...
    async def consume_atomic(
        self,
        id: UUID,
        actor_id: str,                         # C2: binding field — must match MCPApproval.actor_id
        mcp_server_id: str,                    # C2: binding field — must match MCPApproval.mcp_server_id
        tool_name: str,                        # C2: binding field — must match MCPApproval.tool_name
        arguments_hash: str,                   # C2: binding field — must match MCPApproval.arguments_hash
        trusted_workflow_run_id: int | None,   # T1/S1/C2: int | None — WorkflowRun.id is INTEGER PK; never from tool arguments
        now: datetime,                         # S2: datetime.now(UTC); no utcnow()
    ) -> MCPApproval:
        """
        Single-transaction atomic consumption (C2/S2/T2 — all binding fields verified in-transaction):
        1. BEGIN IMMEDIATE; — acquires the write lock immediately, preventing TOCTOU between SELECT and UPDATE.
        2. SELECT the MCPApproval row within the transaction.
        3. Within the SAME transaction verify ALL of these:
           a. actor_id matches the persisted MCPApproval.actor_id.
           b. mcp_server_id matches the persisted MCPApproval.mcp_server_id.
           c. tool_name matches the persisted MCPApproval.tool_name.
           d. arguments_hash matches the persisted MCPApproval.arguments_hash.
           e. status = APPROVED AND expires_at > now AND consumed_at IS NULL.
        4. Verify workflow_run_id binding against trusted_workflow_run_id (S1 rules) within SAME transaction.
           trusted_workflow_run_id is int | None — WorkflowRun.id is an INTEGER primary key (T1).
           (NULL-safe: both NULL, or both equal integers must match.)
        5. UPDATE mcp_approvals SET status='CONSUMED', consumed_at=now
           WHERE id=? AND status='APPROVED' AND expires_at > now AND consumed_at IS NULL.
        6. Verify rowcount == 1 — if 0 rows updated → ROLLBACK; raise ConsumedError; log mcp_approval_already_consumed.
        7. COMMIT BEFORE returning (subprocess launch happens after commit, not inside the transaction).
        8. If subprocess fails after COMMIT: approval remains CONSUMED — no rollback.
        Raises ConsumedError on any binding mismatch, concurrent consumption, expiry during consumption,
        or prior consumption. Uses datetime.now(UTC) — NOT datetime.utcnow().

        C1 note: trusted_workflow_run_id is resolved by the application layer from the current execution
        session before calling consume_atomic. It is never read from tool arguments, request body, or
        any client-supplied field.

        SQLite write-lock semantics (T2):
        BEGIN IMMEDIATE acquires the write lock upfront for the entire transaction, preventing another
        writer from modifying the approval row between SELECT and UPDATE. SQLite serializes writes at
        the database-file level — only one write transaction holds the write lock at a time. This is a
        SQLite engine guarantee, NOT a SQLAlchemy connection-pool guarantee.

        busy_timeout: Configure the SQLite busy_timeout (recommended: 5000 ms) so that a competing
        write transaction waits briefly rather than immediately raising OperationalError.

        Lock contention: If BEGIN IMMEDIATE raises OperationalError/busy, treat it as an authorization
        failure for the current request. The caller (MCPService) MAY retry the database operation only
        (not the external MCP invocation) after a brief delay, up to a configurable maximum (e.g.
        3 retries with exponential backoff).
        """
    async def list_pending(self, server_id: str) -> list[MCPApproval]: ...
```

**EXPIRED rejection at consume_atomic (W4-FK, refined by W4-PA):** `consume_atomic` rejects any approval whose `status != 'APPROVED'` (in-transaction check 3.e: `status = APPROVED AND expires_at > now AND consumed_at IS NULL`). This existing behavior now also covers approvals expired by the BEFORE DELETE trigger on `workflow_runs` (§3.7a): an approval that was PENDING or APPROVED before its run was deleted has `status = 'EXPIRED'` and `workflow_run_id = NULL`, so even an unbound invocation (`trusted_workflow_run_id = NULL`, which would otherwise match NULL-to-NULL per REQ-M2.5) is rejected at the consumption gate — the `UPDATE ... WHERE status='APPROVED'` matches 0 rows and `consume_atomic` raises `ConsumedError`. The NULL-to-NULL authorization bypass is therefore impossible for an approval that was *originally bound* to the deleted run. An orphaned PENDING approval cannot be promoted to APPROVED either: the trigger already set it to `EXPIRED`, and the approval-resolution flow only resolves approvals whose status is `PENDING`, so a resolution `UPDATE ... WHERE status='PENDING'` matches 0 rows. Originally-unbound approvals (`workflow_run_id IS NULL` at creation) keep their REQ-M2.5 NULL-to-NULL semantics; the trigger never fires for them (it only updates rows `WHERE workflow_run_id = OLD.id`).

**Tool classification:** `MCPServerConfig` gains an optional `tool_classifications: dict[str, Literal["read_only", "consequential", "unknown"]]` field. Any tool not listed defaults to `"unknown"`. Read-only tools may proceed without an `mcp_approval_id`.

**Additive sequential checks (both must pass):**
1. Allow-list check (`MCPPermissionError` if denied) — from REQ-M1.4.
2. Approval gate check (`MCPApprovalRequiredError` if consequential/unknown without a valid, persisted, unconsumed `MCPApproval` retrieved by `mcp_approval_id` from `MCPApprovalRepository`) — from REQ-M1.7 and REQ-M2.x.

**Audit events emitted by MCPService (D4/F6 correction — full set):**

| Event type | When | Distinct from |
|---|---|---|
| `mcp_approval_requested` | Before raising `MCPApprovalRequiredError` when a consequential/unknown tool is invoked | — |
| `mcp_approval_granted` | After retrieving, validating, and atomically consuming the `MCPApproval` for a tool call | Distinct from `mcp_approval_requested` |
| `mcp_approval_denied` | When an `MCPApproval` for an MCP tool is **explicitly rejected** by a human approver | NOT emitted on expiry |
| `mcp_approval_expired` | When `MCPApproval.expires_at` is in the past — TTL elapsed before use | NOT `mcp_approval_denied`; expiry is not a human rejection |
| `mcp_approval_missing` | When no `MCPApproval` is found (absent `mcp_approval_id` or record not in DB) for a consequential/unknown tool | NOT `mcp_approval_requested`; missing is a different error path |
| `mcp_approval_rejected` | When workflow_run_id binding check fails (S1) — MUST include `reason` field: `workflow_run_mismatch` \| `missing_workflow_context` \| `unexpected_workflow_context` \| `mismatched_binding` \| `expired` \| `already_consumed` | Distinct from `mcp_approval_missing` and `mcp_approval_expired`; covers all authorization rejections at consumption time |
| `mcp_tool_invoked` | After approval consumed and subprocess launched (before result known) | — |
| `mcp_tool_completed` | After `MCPClient.call_tool` returns without exception | Distinct from `mcp_tool_invoked` |
| `mcp_tool_failed` | After `MCPClient.call_tool` raises any exception or times out | — |

**New files:** `MCPApprovalRepository` lives at `src/devflow_api/repositories/mcp_approval.py`. `MCPApproval` model lives at `src/devflow_api/models/mcp_approval.py`. Both added to new-file layout in §13 and to Wave 4, Task I4 deliverables. Migration 006 (`006_add_mcp_approvals`) is a Wave 4 deliverable. No Wave 5 deliverable is required by Wave 4.

---

### 7.5b Failure and Retry Policy (F9 correction)

**MCPApproval failure semantics:**
- An `MCPApproval` authorizes at most one execution attempt (enforced by `consume_atomic`).
- Consumed approvals cannot be replayed regardless of execution outcome (success, failure, timeout).
- An execution failure does NOT restore the approval to `APPROVED` status.
- Timeout or connection loss is treated as indeterminate (not confirmed success, not confirmed failure).
- No automatic retry of a consequential action without a new explicit `MCPApproval`.

**Exact-once caveat:** "DevFlow AI cannot guarantee exactly-once execution of external MCP tools. If the subprocess was launched but the result is unknown (timeout/crash), the user must verify the external state before approving a retry."

**GitHubConfirmation failure semantics:**
- A `GitHubConfirmation` consumed (`used_at` set) means the action was attempted, not necessarily completed.
- GitHub API failure after confirmation consumption: record `github_action_failed` audit event; do NOT automatically restore the confirmation or retry.
- The user must verify GitHub state and issue a new `GitHubConfirmation` for retry.
- "DevFlow AI cannot guarantee exactly-once execution of GitHub API operations. If the API call was made but the result is unknown, the user must verify the GitHub state before issuing a new confirmation."

---

### 7.6 MCP SDK Dependency Management

**Declared version range:** `mcp>=1.0,<2.0` in `requirements/base.txt`. The `mcp` package was not present in `pyproject.toml` or `requirements/base.txt` as of base commit `aaaaacb`. The implementer MUST check `pyproject.toml` first at implementation time (Wave 4, Task I4); if a different `mcp` version is already declared there, that version takes precedence and REQ-M1.8 must be updated to reflect the actual constraint. The operative constraint as of this specification is `mcp>=1.0,<2.0`.

**Trust statement (D2 — exact statement required by Final Specification Correction):**
"For Phase 1, operator-configured MCP server binaries are trusted within the documented local single-user threat model. Environment-variable scoping is not an OS-level sandbox. Untrusted MCP binaries must not be executed. OS-level sandboxing (seccomp, namespaces, AppArmor) is deferred to a future phase."

**MCP binary trust elaboration:** MCP server binaries configured in `MCPServerConfig.command` are trusted by the operator who configured them. DevFlow AI does not verify binary signatures or hash values. The operator is responsible for ensuring the configured binary is trustworthy. The security boundary is environment-variable scoping and the allow-list defined in `MCPServerConfig.allowed_tools`. Do NOT claim that environment-variable scoping provides OS-level isolation — it does not.

**Reproducible locking:** A lockfile (`requirements/requirements.lock` or equivalent) MUST be generated by `uv lock` or `pip-compile` and committed. CI installs from the lockfile.

**Upgrade procedure:**
1. Bump the constraint in `requirements/base.txt`.
2. Regenerate the lockfile (`uv lock` or `pip-compile`).
3. Run the full test suite including MCP integration tests.
4. If the MCP SDK introduces behaviour changes visible to callers, update this spec.

**Offline testing:** All MCP unit and integration tests MUST mock the subprocess. No live MCP server is required in CI. `asyncio.create_subprocess_exec` (the subprocess launch) and `ClientSession` (the SDK session) are mocked in tests. The SDK `stdio_client` is not imported or called in production code (W4-CR Conflict A — it is not used as the transport); only `ClientSession` is imported for type-checking and mocking purposes.

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
        confirmation_repo: GitHubConfirmationRepository,
    ) -> None: ...

    async def issue_confirmation(
        self,
        repo_full_name: str,
        operation: Literal["branch_create", "pr_create"],
        parameters: dict[str, object],
        actor_id: str,
        workflow_run_id: int | None = None,
    ) -> GitHubConfirmation:
        """
        Creates and persists a GitHubConfirmation record.
        Sets: parameters_hash = SHA-256(canonical JSON of parameters),
              issued_at = now(UTC), expires_at = now(UTC) + TTL (default 10 minutes),
              used_at = None.
        Logs github_confirmation_issued audit event.
        Returns the GitHubConfirmation record (including its id).
        """

    async def create_branch(
        self,
        repo_config_id: int,
        name: str,
        base_ref: str,
        confirmation_id: str,
        actor_id: str,
    ) -> BranchSummary:
        """
        1. Load GitHubConfirmation by confirmation_id. Raises ConfirmationNotFoundError if absent.
        2. Validate operation == "branch_create". Raises ConfirmationMismatchError if wrong.
        3. Validate parameters_hash matches SHA-256 of {name, base_ref, repo_config_id}.
           Raises ConfirmationMismatchError (HTTP 422, code CONFIRMATION_MISMATCH) if mismatch.
        4. Validate expires_at > now(UTC). Raises ConfirmationExpiredError (HTTP 422, code CONFIRMATION_EXPIRED) if expired.
        5. Validate used_at is None. Raises ConfirmationAlreadyUsedError (HTTP 409) if used.
        6. Set used_at = now(UTC). Logs github_action_authorized.
        7. Calls GitHubAdapter.create_branch. Logs github_action_executed with actor=actor_id.
        8. Logs branch_created audit event with actor="user".
        """

    async def create_pull_request(
        self,
        repo_config_id: int,
        title: str,
        head: str,
        base: str,
        body: str,
        confirmation_id: str,
        actor_id: str,
    ) -> PullRequestSummary:
        """
        Same confirmation validation as create_branch, with operation == "pr_create".
        No merge support.
        Logs pr_created audit event with actor="user".
        Logs github_action_authorized and github_action_executed.
        """
```

**GitHubConfirmation record (F2 correction — SQLAlchemy ORM model, persisted to SQLite):**
```python
# src/devflow_api/models/github_confirmation.py  (SQLAlchemy model — see §3.7b for full definition)
class GitHubConfirmation(Base):
    __tablename__ = "github_confirmations"
    id: Mapped[str]                       # UUID as text, primary key
    repo_full_name: Mapped[str]
    operation: Mapped[str]                # "branch_create" | "pr_create"
    parameters_hash: Mapped[str]          # SHA-256 of canonical JSON
    actor_id: Mapped[str]
    workflow_run_id: Mapped[int | None]   # nullable FK → workflow_runs.id
    issued_at: Mapped[datetime]
    expires_at: Mapped[datetime]          # default: issued_at + 10 minutes
    used_at: Mapped[datetime | None]      # None until first use; set atomically
```

**SUPERSEDED — see §3.7b:** The earlier design stub defined `GitHubConfirmation` as a Pydantic `BaseModel` for in-memory use. This is superseded by the SQLAlchemy model above with migration 007. In-memory storage is NOT acceptable (F2 correction). The persistence requirement ensures restart recovery and concurrent duplicate-consumption prevention.

**Confirmation endpoint:** `POST /api/v1/github-confirmations` → issues a `GitHubConfirmation`, returns `{"id": "...", "expires_at": "..."}`. The client then includes `{"confirmation_id": "<id>", ...}` in the branch/PR creation request body.

**Rejection cases and HTTP codes:**
- No `confirmation_id` supplied → HTTP 422, code `CONFIRMATION_REQUIRED`
- `confirmation_id` not found → HTTP 404, code `CONFIRMATION_NOT_FOUND`
- `operation` or `parameters_hash` mismatch → HTTP 422, code `CONFIRMATION_MISMATCH`
- `expires_at` in the past → HTTP 422, code `CONFIRMATION_EXPIRED`
- `used_at` already set → HTTP 409, code `CONFIRMATION_ALREADY_USED`

**Audit events logged by RepositoryService:**

| Event type | Trigger |
|---|---|
| `github_confirmation_issued` | `issue_confirmation` |
| `github_action_authorized` | After confirmation validated, before adapter call |
| `github_action_executed` | After adapter call succeeds |
| `github_action_rejected` | When any confirmation validation fails |
| `branch_created` | After `create_branch` succeeds |
| `pr_created` | After `create_pull_request` succeeds |

---

## 9. WorkflowRun State Machine

### 9.1 WorkflowRun states

| State | Meaning |
|---|---|
| `pending` | Record created; no work started. Run waits for an explicit `transition_run` call to `running`. Created by `WorkflowService.create_run`. |
| `running` | Active processing in progress (steps being executed). Only state from which `completed`, `failed`, `waiting_approval`, or `cancelled` can be reached. |
| `waiting_approval` | An approval gate was reached. Run is paused at this gate until an `ApprovalRequest` is resolved by a human. |
| `completed` | All steps finished successfully. Terminal state. `completed_at` is set. |
| `failed` | An unhandled error occurred. Terminal state. `error_message` is set. `completed_at` is set. |
| `cancelled` | Cancelled by user action from `running` state, or by an `ApprovalRequest` being rejected. Terminal state. |

**States NOT present in WorkflowRun:** `paused` (this is a `Workflow` definition status only, not a run status). `created` (the initial state at record creation is `pending`). `approved` (this is an `ApprovalRequest.status` value that causes the run to transition from `waiting_approval` back to `running`, not a run status itself).

### 9.2 WorkflowRun valid transitions

```
                     ┌─────────┐
                     │  draft  │  (Workflow status — not WorkflowRun)
                     └────┬────┘
                          │ activate
                     ┌────▼────┐
                     │  active │  (Workflow status — not WorkflowRun)
                     └─────────┘

   WorkflowRun transitions:

   [pending] ──transition_run──▶ [running]
                                      │
                              ┌───────┼──────────┬────────────┐
                        appr  │       │complete  │fail        │cancel
                        gate  │       │          │            │
                              ▼       ▼          ▼            ▼
                   [waiting_approval] [completed] [failed] [cancelled]
                              │
                     approved │ rejected
                              │         │
                              ▼         ▼
                           [running] [cancelled]
```

**WorkflowRun valid transitions table:**

| From | To | Trigger |
|---|---|---|
| `pending` | `running` | `WorkflowService.transition_run(run_id, "running", actor)` |
| `running` | `waiting_approval` | `ApprovalService.request_approval(run_id, ...)` |
| `running` | `completed` | `WorkflowService.transition_run(run_id, "completed", actor)` |
| `running` | `failed` | `WorkflowService.transition_run(run_id, "failed", actor)` |
| `running` | `cancelled` | `WorkflowService.transition_run(run_id, "cancelled", actor)` |
| `waiting_approval` | `running` | `ApprovalService.resolve(id, "approved", ...)` |
| `waiting_approval` | `cancelled` | `ApprovalService.resolve(id, "rejected", ...)` |

All other transitions are invalid. Invalid transitions raise `InvalidStatusTransitionError` → HTTP 422 with `code = "INVALID_STATUS_TRANSITION"`.

**Phase 1 execution boundary:** `WorkflowService.transition_run` performs the state transition and writes an audit log entry. It does NOT read `definition_json` or dispatch step execution. All transitions in Phase 1 are triggered by explicit API calls, not autonomous processing.

### 9.3 Workflow definition status (separate from WorkflowRun)

The `Workflow` model (the definition, not a run) has status: `draft | active | paused | completed | failed`. These are definition lifecycle states and are separate from WorkflowRun execution states. A paused `Workflow` definition means no new runs should be started; it does not affect already-running `WorkflowRun` records.

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

**PUT null semantics:** `ProjectUpdate` fields set to `null` are treated as absent (skipped). There is no way to clear an existing field value via PUT in Phase 1.

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
POST   /api/v1/repositories/{id}/branches                  → BranchSummary            201 | 403 | 404 | 409 | 422 | 502
GET    /api/v1/repositories/{id}/pull-requests             → list[PullRequestSummary]  200 | 403 | 502
POST   /api/v1/repositories/{id}/pull-requests             → PullRequestSummary        201 | 403 | 404 | 422 | 502
GET    /api/v1/repositories/{id}/pull-requests/{pr_number} → PullRequestSummary        200 | 403 | 404 | 502
POST   /api/v1/github-confirmations                        → GitHubConfirmationResponse 201 | 422

```

`POST /api/v1/github-confirmations` body: `{"repo_full_name": str, "operation": "branch_create" | "pr_create", "parameters": dict}`. Response: `{"id": str, "expires_at": datetime}`.

`POST /api/v1/repositories/{id}/branches` body: `{"name": str, "base_ref": str, "confirmation_id": str}` — the `confirmed: bool` field is replaced.

`POST /api/v1/repositories/{id}/pull-requests` body: `{"title": str, "head": str, "base": str, "body": str, "confirmation_id": str}` — the `confirmed: bool` field is replaced.

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
    approvals: list[ApprovalResponse] = []
    pending_approvals: list[ApprovalResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

**Approval projection contract (W3-RC; resolves REQ-W1.5.4 ↔ §11.3):**
- `approvals` — every `ApprovalRequest` associated with the run, regardless of status (`pending`, `approved`, `rejected`, `expired`), ordered by `created_at` ascending (ties broken by `id`). Returned by `GET /api/v1/workflow-runs/{run_id}` and the run-list endpoints.
- `pending_approvals` — the subset of `approvals` whose `status == "pending"`, in the same order. This is a backward-compatibility convenience filter; it MUST equal `[a for a in approvals if a.status == "pending"]`.
- When the run has no associated approvals, BOTH fields serialise as an empty array `[]`, never `null` (the `= []` default enforces this at the schema layer).
- This is a read-only projection. Building the response does not mutate `ApprovalRequest.status`, `resolved_at`, or `resolved_by`, does not reopen or restore resolved/expired approvals, and writes no audit log entry. The approval lifecycle (REQ-W1.6, §5.2) and the `approval_requests` schema are unchanged, so no migration is required.
- Data source: the response is assembled in the service/router layer (following the existing `ProjectService` pattern) from the `WorkflowRun` (fetched by id via `WorkflowRunRepository.get`) plus approvals from `ApprovalRepository.list_for_run(run_id)` (§4.3). `pending_approvals` is derived in that same layer by filtering the fetched list; no second query is required.

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

**Wave 4 page-numbering confirmation (W4-CR Conflict D):** Task I7 UPDATEs the EXISTING pages `9_Integrations.py` (placeholder → live integration status) and `10_Settings.py` (health check → extended with integration/MCP/GitHub status) in place. No new Integrations or Settings pages are created, and no pages are renumbered. The canonical Wave 4 page names are `9_Integrations.py` and `10_Settings.py`, matching the actual `src/devflow_ui/pages/` file tree (which contains `3_Learning.py` and `4_Specifications.py`, not `3_Integrations.py`/`4_Settings.py`). `app.py` navigation is unchanged for pages 9 and 10.

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
        approval.py          (new — ApprovalRequest; for workflow step approval gates only)
        audit.py             (new — WorkflowAuditLog)
        repository.py        (new — RepositoryConfig)
        mcp_approval.py      (new — MCPApproval; UUID PK; for MCP authorization only)

    repositories/
        project.py              (extended — list_filtered, update_tags)
        workflow.py             (new — WorkflowRepository, WorkflowRunRepository)
        approval.py             (new — ApprovalRepository, AuditLogRepository)
        approval_request.py     (new — ApprovalRequestRepository; get_by_id, create, consume_atomic; for workflow step approvals only)
        mcp_approval.py         (new — MCPApprovalRepository; create, get_by_id, consume_atomic, list_pending; for MCP authorization only)
        repository_config.py    (new — RepositoryConfigRepository)
        github_confirmation.py  (new — GitHubConfirmationRepository)

    services/
        project.py           (new — ProjectService)
        workflow.py          (new — WorkflowService)
        approval.py          (new — ApprovalService)
        repository.py        (new — RepositoryService; owns GitHubConfirmation gate)
        mcp_service.py       (new — MCPService; owns MCP approval gate; depends on MCPApprovalRepository; NOT ApprovalRequestRepository)

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
    002_add_project_tags_column.py    (new — Wave 1, Task P1)
    003_add_workflow_tables.py        (new — Wave 2, Task W2)
    004_add_approval_audit_tables.py  (new — Wave 2, Task W2)
    005_add_repository_tables.py      (new — Wave 2, Task W2)
    006_add_mcp_approvals.py          (new — Wave 4, Task I4)
    007_add_github_confirmations.py   (new — Wave 5, Task G1)

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
        test_mcp_service.py          (new — MCPService approval gate tests)
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

GitHub branch and PR creation use a two-step confirmation pattern. First, the client obtains a `GitHubConfirmation` record by calling `POST /api/v1/github-confirmations`. Then it submits that `confirmation_id` in the creation request:

```python
# Step 1 — issue confirmation (client calls this first)
# POST /api/v1/github-confirmations
# Body: {"repo_full_name": "owner/repo", "operation": "branch_create",
#        "parameters": {"name": "feature/x", "base_ref": "develop", "repo_config_id": 1}}
# Response: {"id": "<uuid>", "expires_at": "2025-01-21T10:10:00+00:00"}

# Step 2 — create branch with confirmation_id
@router.post("/{id}/branches")
async def create_branch(
    id: int,
    body: CreateBranchRequest,
    # body.confirmation_id: str (required)
    # body.name: str
    # body.base_ref: str
) -> BranchSummary:
    return await repo_service.create_branch(
        id, body.name, body.base_ref,
        confirmation_id=body.confirmation_id,
        actor_id="user",
    )
    # RepositoryService validates the GitHubConfirmation record before calling GitHubAdapter
```

**The simple `confirmed: bool` field is REPLACED by `confirmation_id: str`.** A boolean flag alone is not accepted for branch or PR creation. The `GitHubConfirmation` record IS the confirmation; it binds the specific repository, operation, and parameters to a time-limited single-use token.

**Authorization model:** Having `GITHUB_TOKEN` configured is an authentication prerequisite (it allows the GitHub API call to authenticate), not authorization. The `GitHubConfirmation` record is the authorization gate.

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

**Isolation boundary (D2 correction):** Phase 1 provides environment-variable scoping only. The launched subprocess receives an explicitly constructed `env` dict. It does NOT inherit the parent process environment (`env=None` is never passed to `create_subprocess_exec`). This is Python-level environment variable isolation only. OS-level sandbox isolation (seccomp, namespaces, cgroups, AppArmor) is NOT implemented in Phase 1 and is deferred to a future phase.

**D2 exact statement:** "For Phase 1, operator-configured MCP server binaries are trusted within the documented local single-user threat model. Environment-variable scoping is not an OS-level sandbox. Untrusted MCP binaries must not be executed. OS-level sandboxing (seccomp, namespaces, AppArmor) is deferred to a future phase."

**Operator trust:** MCP server binaries in `MCPServerConfig.command` are trusted by the operator who configured them. DevFlow AI does not verify binary signatures.

**Secret interpolation:** Only `Settings` attributes that are `SecretStr` fields may be referenced via `${VAR_NAME}` in `MCPServerConfig.env`. Referencing a non-existent or non-secret attribute raises `MCPSecretResolutionError` before process launch.

**Termination sequence:** On timeout or completion: SIGTERM is sent first; if the process has not exited after a 5-second grace period, SIGKILL is sent. All subprocess interactions are wrapped in `try/finally` to guarantee termination.

```python
resolved_env = {
    k: _resolve_secret(v, settings)   # interpolates ${SECRET_NAME} from SecretStr fields only
    for k, v in config.env.items()
}
# Launch with explicit env dict — does NOT inherit parent process environment
proc = await asyncio.create_subprocess_exec(
    *config.command, *config.args,
    env=resolved_env,                  # explicit env, not env=None
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
try:
    result = await asyncio.wait_for(proc.communicate(input=request_bytes), timeout=config.timeout_seconds)
finally:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
```

---

## 15. Error Handling Extensions

Phase 0 `add_error_handlers` is extended with three new handlers:

| Exception | HTTP Status | Code |
|---|---|---|
| `IntegrationExecutionError` | 502 | `INTEGRATION_ERROR` |
| `MissingCredentialError` | 403 | `MISSING_CREDENTIAL` |
| `ConfirmationRequiredError` | 422 | `CONFIRMATION_REQUIRED` |
| `ConfirmationExpiredError` | 422 | `CONFIRMATION_EXPIRED` |
| `ConfirmationMismatchError` | 422 | `CONFIRMATION_MISMATCH` |
| `ConfirmationAlreadyUsedError` | 409 | `CONFIRMATION_ALREADY_USED` |
| `ConfirmationNotFoundError` | 404 | `CONFIRMATION_NOT_FOUND` |
| `ApprovalAlreadyResolvedError` | 409 | `APPROVAL_ALREADY_RESOLVED` |
| `InvalidStatusTransitionError` | 422 | `INVALID_STATUS_TRANSITION` |
| `MCPServerNotFoundError` | 404 | `MCP_SERVER_NOT_FOUND` |
| `MCPPermissionError` | 403 | `MCP_PERMISSION_DENIED` |
| `MCPTimeoutError` | 504 | `MCP_TIMEOUT` |
| `MCPApprovalRequiredError` | 403 | `MCP_APPROVAL_REQUIRED` |
| `MCPApprovalExpiredError` | 422 | `MCP_APPROVAL_EXPIRED` |

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

**Required audit event types (persisted to `workflow_audit_log`):**

| Event type | Trigger | Actor |
|---|---|---|
| `run_created` | `WorkflowService.create_run` | `"system"` |
| `run_status_changed` | `WorkflowService.transition_run` | passed `actor` param |
| `approval_requested` | `ApprovalService.request_approval` | `"system"` |
| `approval_resolved` | `ApprovalService.resolve` | `"user"` |
| `branch_created` | `RepositoryService.create_branch` | `"user"` |
| `pr_created` | `RepositoryService.create_pull_request` | `"user"` |
| `github_confirmation_issued` | `RepositoryService.issue_confirmation` | `"user"` |
| `github_action_authorized` | `RepositoryService` after confirmation validated | `"user"` |
| `github_action_executed` | `RepositoryService` after adapter call succeeds | `"user"` |
| `github_action_rejected` | `RepositoryService` after confirmation validation fails | `"user"` |
| `mcp_approval_requested` | `MCPService` before raising `MCPApprovalRequiredError` | `"system"` |
| `mcp_approval_granted` | `MCPService` after validating and atomically consuming `MCPApproval` | `"user"` |
| `mcp_approval_denied` | `MCPService` when an MCP `MCPApproval` is **explicitly rejected** by user (NOT expiry) | `"user"` |
| `mcp_approval_expired` | `MCPService` when `MCPApproval.expires_at` is in the past — TTL elapsed, NOT a human rejection | `"system"` |
| `mcp_approval_missing` | `MCPService` when no `MCPApproval` is found for a consequential/unknown tool | `"system"` |
| `mcp_approval_rejected` | `MCPService` when any authorization check fails at invocation time — includes `reason` field: `workflow_run_mismatch` \| `missing_workflow_context` \| `unexpected_workflow_context` \| `mismatched_binding` \| `expired` \| `already_consumed` | `"system"` |
| `mcp_tool_invoked` | `MCPService` after approval consumed and subprocess launched | `"system"` |
| `mcp_tool_completed` | `MCPService` after `MCPClient.call_tool` returns success — DISTINCT from `mcp_tool_invoked` | `"system"` |
| `mcp_tool_failed` | `MCPService` after `MCPClient.call_tool` raises or times out | `"system"` |

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
**Decision:** Any action that creates or modifies a Git branch, PR, or external resource requires either a `GitHubConfirmation` record (direct API call, branch/PR creation) or a resolved `ApprovalRequest` (workflow path). The simple `confirmed: bool` field (v1.1.0) is upgraded to a `GitHubConfirmation` record with single-use semantics, expiry, and parameter binding.
**Rationale:** A `confirmed: bool` field sent by the client can be trivially re-sent with the same value; it does not bind to specific parameters. `GitHubConfirmation` binds the confirmation to a specific repository, operation type, and parameter hash, with a time-limited single-use token. This prevents replay attacks and confirmation-without-reviewing-parameters scenarios. Credential presence (`GITHUB_TOKEN` in Settings) is authentication, not authorization.
**Alternatives considered:** Role-based access control — deferred (single-user local tool), OAuth tokens — deferred.

### ADR-0006: Live adapters as registry augmentation (not replacement)
**Decision:** Live adapters are registered alongside stubs via `register_live`. `get_live()` falls back to stubs when live init fails.
**Rationale:** Tests that run without credentials continue to use stub adapters. The registry never raises; it always returns a usable adapter.
**Alternatives considered:** Conditional adapter class selection at startup — rejected (harder to test, creates tight coupling to Settings at import time).

### ADR-0007: MCP servers as subprocesses (stdio transport)
**Decision:** Launch each MCP server as an explicit-environment subprocess via `asyncio.create_subprocess_exec(*command, *args, env=resolved_env, stdin=PIPE, stdout=PIPE, stderr=...)` and wrap the subprocess stdio in the MCP Python SDK `ClientSession` (W4-CR Conflict A). Each tool call spawns a fresh process; `MCPClient` owns the `SIGTERM → 5 s grace → SIGKILL` cleanup in a `finally` block. The SDK `stdio_client` helper is NOT used: SDK v1.x `stdio_client` merges `get_default_environment()` into the supplied env dict (breaking explicit environment isolation) and exposes no configurable termination grace period.
**Rationale:** stdio is the universal MCP transport. Explicit subprocess ownership preserves the environment-isolation invariant (REQ-M1.5, REQ-S1.5) and the deterministic 5 s termination grace (REQ-M1.2.5), neither of which the SDK `stdio_client` context manager can guarantee. Persistent process management (SSE) is deferred to Phase 2 when connection pooling requirements are clearer.
**Alternatives considered:** SDK `stdio_client` transport — rejected (parent-env merge; no grace control). SSE transport — deferred. HTTP transport — not universally supported by MCP servers.

### ADR-0008: Workflow state machine in service layer, not database
**Decision:** Status transition validation lives in `WorkflowRunRepository.transition_status`, not in a DB trigger or constraint.
**Rationale:** SQLite has limited trigger support. Python-side validation is testable with standard pytest. Invalid transitions return 422 HTTP errors, not DB exceptions.

### ADR-0009: WorkflowRun has no paused state
**Decision:** `WorkflowRun` does not have a `paused` status. `Workflow` (the definition) has `paused`; `WorkflowRun` (the execution) does not.
**Rationale:** A paused workflow definition should not create new runs; existing runs at an approval gate are in `waiting_approval`. Adding `paused` to `WorkflowRun` would require defining transitions from `running` to `paused` and back, with unclear semantics in Phase 1 when no autonomous execution engine exists. Deferred to Phase 2 if needed.

### ADR-0010: Wave 1 migration is 002 (tags column), not 005
**Decision:** The `tags_json` column migration is numbered `002` (second in the chain, after `001_create_initial_tables`) rather than `005` as originally drafted.
**Rationale:** Wave 1 creates migration `002_add_project_tags_column.py`. Its `down_revision = "001_create_initial_tables"`. This allows Wave 1's acceptance criterion "alembic upgrade head applies the tags migration" to be satisfied independently of Wave 2 migrations. If `002` were renamed `005`, it would need migrations `002`–`004` to exist first (since it would chain from `004`), but those are Wave 2 deliverables. The renumbering eliminates this cross-wave dependency.

### ADR-0011: MCPService as mandatory gateway to MCPClient
**Decision:** All MCP tool invocations go through `MCPService.invoke_tool`. No code path may call `MCPClient.call_tool` directly from a router or adapter.
**Rationale:** The approval gate for MCP `consequential` and `unknown` tools must be enforced at a single, non-bypassable point. If routers or adapters could call `MCPClient` directly, the approval check could be bypassed. `MCPService` owns the sequential allow-list check + approval gate check and emits all five MCP audit events.
**Alternatives considered:** Middleware-based interception — rejected (too complex; easier to verify service-layer invariant in code review and integration tests).

### ADR-0012: PRAGMA foreign_keys=ON in SQLAlchemy connect event
**Decision:** `PRAGMA foreign_keys=ON` is added to the SQLAlchemy `'connect'` event handler in `src/devflow_api/database.py`, alongside `PRAGMA journal_mode=WAL`.
**Rationale:** SQLite silently ignores FK constraints unless this PRAGMA is set per connection. All `ON DELETE CASCADE` and `ON DELETE SET NULL` semantics in migrations 003–005 depend on it. The event-handler pattern is already in use for WAL mode; reusing it for FK enforcement is consistent and requires no other changes.
**Alternatives considered:** Setting it only in `alembic/env.py` — rejected (doesn't apply to runtime application connections). Database-level trigger — not supported in SQLite migrations portably.

### ADR-0013: WorkflowRunResponse exposes all approvals plus a pending-only filter
**Decision:** `WorkflowRunResponse` (§11.3) carries two approval fields: `approvals` (every associated `ApprovalRequest`, all statuses) and `pending_approvals` (the pending-only subset). Both default to `[]`.
**Rationale:** REQ-W1.5.4 requires the run-detail response to include "any associated `ApprovalRequest` records" — all of them, including resolved and expired ones. The original §11.3 schema exposed only `pending_approvals`, which hid resolved approvals after resolution and contradicted the requirement. Adding `approvals` satisfies the requirement; keeping `pending_approvals` preserves the existing pending-focused contract for any consumer that relied on it. Both fields are read-only projections of `ApprovalRequest` rows; the approval lifecycle (REQ-W1.6, §5.2) and the `approval_requests` schema are unchanged, so no migration is required.
**Alternatives considered:** Replace `pending_approvals` with `approvals` only — rejected (removes an existing specced field, a breaking change, and loses the pending-filter convenience). Add a query parameter to toggle scope — rejected (the requirement asks for the records to be present, not optionally filtered). Exclude expired approvals from `approvals` — rejected (REQ-W1.5.4 says "any associated" with no status exclusion; expired approvals are part of the history).

---

## 19. Requirements-to-Design-to-Tasks Traceability Matrix

| Req ID | Requirement summary | Design section | Task IDs |
|---|---|---|---|
| REQ-P1.1 | POST /projects persists to SQLite | §10.1, §4.1, §5.1 | P3, P4, P6 |
| REQ-P1.2 | GET /projects with filter + pagination | §10.1, §4.1 | P3, P4, P6 |
| REQ-P1.3 | PUT /projects/{id} partial update, null=skip | §10.1, §4.1 | P3, P4, P6 |
| REQ-P1.4 | DELETE /projects/{id} removes record | §10.1, §4.1 | P3, P4, P6 |
| REQ-P1.5 | ProjectResponse + tags + timestamps | §3.1, §11.1 | P1, P2, P6 |
| REQ-P1.6 | Streamlit Projects page live CRUD | §12.1, §12.2 | P5, P6 |
| REQ-W1.1 | Workflow model | §3.2 | W1, W6 |
| REQ-W1.2 | WorkflowRun model + 6 states (no paused) | §3.3, §9 | W1, W6 |
| REQ-W1.3 | ApprovalRequest model | §3.4 | W1, W6 |
| REQ-W1.4 | Workflow CRUD endpoints | §10.2 | A1, A5 |
| REQ-W1.5 | WorkflowRun create + manage; run-detail exposes all approvals (W3-RC) | §10.2, §9, §11.3 | W3, W5, A1, A5 |
| REQ-W1.6 | Approval resolve endpoints | §10.3, §5.2 | W4, W5, A2, A5 |
| REQ-W1.7 | WorkflowAuditLog + 6 event types | §3.5, §16 | W1, W4, W5, W6 |
| REQ-I1.1 | GitHubAdapter live | §8.1, §6 | I2, I5, I7 |
| REQ-I1.2 | OllamaAdapter live | §6.1, §6.2 | I3, I5, I7 |
| REQ-I1.3 | FigmaAdapter live | §6.1, §6.2 | I3, I5, I7 |
| REQ-I1.4 | Registry get_live / fallback | §6 | I5, I7 |
| REQ-I1.5 | IntegrationExecutionError → 502 | §15 | I1, A3, I7 |
| REQ-I1.6 | Integrations page live status | §12.1 | I6, I7 |
| REQ-M1.1 | MCPServerConfig model | §7.1 | I4, I6, I7 |
| REQ-M1.2 | MCPClient subprocess + SIGTERM/SIGKILL | §7.2 | I4, I7 |
| REQ-M1.3 | MCP tool call structured logging (keys only) | §7.2, §16 | I4, I7 |
| REQ-M1.4 | MCP allowed_tools permission control | §7.1 | I4, I7 |
| REQ-M1.5 | MCP secret interpolation + env isolation | §14.4, §7.1 | I4, I7 |
| REQ-M1.6 | MCPLiveAdapter / MCPStubAdapter fallback | §6, §7.2 | I4, I5, I7 |
| REQ-M1.7 | MCP tool classification + approval gate + 9-step sequence + 8 audit events | §7.5 | I4, I7 |
| REQ-M1.8 | MCP SDK version constraint + lockfile + offline tests | §7.6 | I4 |
| REQ-M2.1 | MCPApproval model (UUID PK, mcp_approvals table) | §3.7a | I4, I7 |
| REQ-M2.2 | MCPApprovalRepository (create, get_by_id, consume_atomic, list_pending) | §3.7a, §7.5 | I4, I7 |
| REQ-M2.3 | MCPService injected with MCPApprovalRepository (not ApprovalRequestRepository) | §7.5 | I4, I7 |
| REQ-M2.4 | Failure semantics: no auto-restore; indeterminate treated as failure; new approval for retry | §7.5b | I4, I7 |
| REQ-G1.1 | RepositoryConfig model (Wave 5); table created Wave 2 | §3.6, §4.4, §10.4 | G1, G3, G5 |
| REQ-G1.2 | Branch listing + status | §8.1, §10.4 | G2, G3, G5 |
| REQ-G1.3 | PR listing + detail | §8.1, §10.4 | G2, G3, G5 |
| REQ-G1.4 | Branch creation with GitHubConfirmation gate | §8.2, §14.1, §10.4 | G2, G3, G5 |
| REQ-G1.5 | PR creation with GitHubConfirmation gate; no merge | §8.2, §14.1, §10.4 | G2, G3, G5 |
| REQ-G1.6 | CI status via Check Runs API | §8.1, §10.4 | G2, G3, G5 |
| REQ-U1.1 | Dashboard live metrics | §12.1 | A4, A5 |
| REQ-U1.2 | Workflows page | §12.1 | A4, A5 |
| REQ-U1.3 | History page | §12.1 | A4, A5 |
| REQ-U1.4 | APIClient extension for all Phase 1 endpoints | §12.2 | P5, A4, I7, G4 |
| REQ-U1.5 | Settings page Phase 1 config summary | §12.1 | I6, I7, G4, G5 |
| REQ-DB1.1 | 7 migrations: 001–007, exact revision IDs + chain, Wave assignments | §3.0 | P1, W2, I4, G1, G5 |
| REQ-DB1.2 | Migration 002 adds tags_json, applies from Phase 0 head | §3.1 | P1, P6 |
| REQ-DB1.3 | PRAGMA foreign_keys=ON on every connection; correct CASCADE/SET NULL directions; Wave 1 tests use Wave 1 tables only | §3.7 | P1, P6 (Wave 1 tests), W6 (Wave 2 tests) |
| REQ-S1.1 | GitHubConfirmation gates; credential ≠ authorization | §14.1, §14.2 | A3, G2, G3, G5, W5, W6 |
| REQ-S1.2 | Bounded timeouts; timeout test named in I7 | §8.1 (timeout), §17 | I2, I3, I4, I6, I7 |
| REQ-S1.3 | Secrets not in logs; token test named in I7 | §14.3, §16 | I2, I3, I4, I7 |
| REQ-S1.4 | No /merge endpoint | §10.4, §18 ADR-0005 | G3, G5 |
| REQ-S1.5 | MCP env isolation (env-var scope only); subprocess env test | §14.4 | I4, I7 |
| REQ-T1.1 | 80% branch coverage; canonical pytest command | §13 test file list | P6, W6, A5, I7, G5 |
| REQ-T1.2 | AppTest smoke tests for all Phase 1 pages | §13 test file list | P6, A5, I7, G5 |
| REQ-T1.3 | Migration round-trip integration tests | §13 | P6, W6, G5 |
| REQ-T1.4 | Phase 0 tests continue to pass | §17 | P6, W6, A5, I7, G5 |
