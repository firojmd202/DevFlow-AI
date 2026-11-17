# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Design

**Version:** 2.1.0
**Status:** Corrected — reconciliation pass (awaiting ChatGPT review)
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9)
**Last Updated:** 2026-11-17
**Companion:** `requirements.md` (EARS requirements + acceptance criteria), `tasks.md` (implementation breakdown).

**Version history:**
- v2.0.0 — 2026-11-17 — Initial design.
- v2.1.0 — 2026-11-17 — Reconciliation pass. See `docs/reports/phase2-wave1-spec-resolution.md`. Changes: pre-dispatch `READY → FAILED` and `PENDING → FAILED` transitions; retry as transient `RUNNING → READY` (never via `FAILED`); disambiguated interruption triggers (timeout vs process-death); automatic recovery reconciliation with explicit user start; run terminal derivation only when all steps terminal; immutable template snapshot on `workflow_runs` (`template_snapshot_json`/`template_version`/`template_hash`); `attempt` increments on dispatch with consistent budget; pending TTL (`expires_at`) and approved authorization validity (`authorization_expires_at`) enforced via columns without changing the `status` CHECK; approval re-gating on expired authorization; lease-owner/attempt fencing for stale completions; contract schema types moved to `src/devflow_api/schemas/executor.py` (no schema→executor imports); run-transition compatibility with the actual Phase 1 `WorkflowService`/`ApprovalService` (`waiting_approval` via the approval service; legacy `NULL`-template runs preserved). Migration 008 extended to also alter `workflow_runs` (snapshot columns).

---

## 1. Design Principles

Wave 1 extends Phase 1 without structural change. The Phase 0/1 layering is preserved:

```
Streamlit UI → APIClient (httpx) → FastAPI routers → Domain services → Repositories → SQLite
                                                   → WorkflowOrchestrator → Executors (in-process)
                                                   → Adapter registry (unchanged)
```

Ten rules govern Wave 1:

1. **Phase 0/1 contracts are immutable where possible.** `workflow_runs.status` and `approval_requests.status` CHECK constraints are not changed. Extensions are additive columns and one new table.
2. **The eight-state lifecycle is step-level.** `WorkflowRun` keeps Phase 1's six run states, derived from step states. This preserves Phase 1 behavior and tests.
3. **The orchestrator owns state; executors do not.** Executors receive an immutable context and return a pure result; the orchestrator persists, transitions, leases, and audits. No executor imports repositories/services/models. Schema types live in `schemas/`; executors import them, never the reverse.
4. **Approvals are digest-bound, single-use, and validity-bounded.** An approval authorizes exactly one operation, one artifact digest, one step, one actor, once, before its authorization expires. Consumption is a CAS `UPDATE` with `consumed_at`; approved validity is a separate column (`authorization_expires_at`); no `consumed` status value is added.
5. **Retries are transient, not terminal.** A retryable failure transitions `RUNNING → READY` and never passes through `FAILED`. `FAILED` is terminal and reached only on exhaustion, non-retryable, or indeterminate outcomes.
6. **SQLite writes are serialised via the database, not the application.** `BEGIN IMMEDIATE` + `busy_timeout` + CAS `rowcount` checks; no application-level locks claiming to serialise writes.
7. **Recovery is idempotent, conservative, and non-dispatching.** Restart recovery reconciles stale state and decides retry-or-fail; it does NOT auto-dispatch. Resumed execution requires an explicit user `start`.
8. **Stale completions are fenced.** Every post-dispatch transition fences on `lease_owner` + `attempt`; a late return from a superseded dispatch is discarded and cannot consume an approval.
9. **Honest isolation boundary.** Env-var scoping and path allowlists are application-level; the design explicitly states they are not OS sandboxing and lists what OS-level isolation is required before real coding-agent execution.
10. **Wave 1 ships one executor: the in-process mock.** No subprocess, shell, filesystem, or network from executors. No real coding-agent execution. Executor security guards are mandatory.

**Wave 1 execution boundary:** `WorkflowOrchestrator` reads the validated `WorkflowTemplate` (from the run's immutable snapshot, not the live `Workflow.definition_json`), materialises `WorkflowStepRun` rows, and drives them through the eight-state lifecycle via `WorkflowOrchestrator.start_or_resume`, dispatching to registered `Executor`s, pausing for `ApprovalRequest` gates, and stopping safely on failure.

---

## 2. Architecture Diagram (Wave 1 additions)

```
  Developer Machine — 127.0.0.1 only
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  Browser :8501                              CLI / Postman :8000             │
  │  ════╪═══════════════════════════════════════════════════════════════════   │
  │  ┌───▼─────────────────────┐       ┌────────────────▼────────────────────┐  │
  │  │ devflow-ui (Streamlit)   │       │ devflow-api (FastAPI/Uvicorn)       │  │
  │  │ 6_Workflows (extended)  │──────▶│ Routers (/api/v1/)                  │  │
  │  └──────────────────────────┘       │   workflows (Phase 1, extended)     │  │
  │                                      │   workflow-runs (+start/cancel/    │  │
  │                                      │     audit/steps — new)             │  │
  │                                      │   approvals (Phase 1, extended)    │  │
  │                                      │ Services:                          │  │
  │                                      │   WorkflowService (Phase 1, reused) │  │
  │                                      │   ApprovalService (Phase 1, ext.)  │  │
  │                                      │   WorkflowOrchestrator (NEW)        │  │
  │                                      │   RecoveryService (NEW)            │  │
  │                                      │   ExecutorRegistry (NEW)           │  │
  │                                      │ Repositories:                      │  │
  │                                      │   WorkflowRunRepository (ext.)      │  │
  │                                      │   WorkflowStepRunRepository (NEW)   │  │
  │                                      │   ApprovalRequestRepository (ext.) │  │
  │                                      │   AuditLogRepository (Phase 1)     │  │
  │                                      │ Executors (NEW package):           │  │
  │                                      │   Executor Protocol (base.py)       │  │
  │                                      │   MockExecutor (only one)          │  │
  │                                      │ Schemas (canonical):               │  │
  │                                      │   workflow_template.py             │  │
  │                                      │   executor.py (contract types)     │  │
  │                                      │   workflow.py (run/step responses) │  │
  │                                      │ SQLAlchemy async + aiosqlite       │  │
  │                                      └──────────────────┬──────────────────┘  │
  │                                              ┌─────────▼──────────┐          │
  │                                              │ devflow.db (SQLite) │          │
  │                                              │ + workflow_step_runs│          │
  │                                              │ + approval_requests  │          │
  │                                              │   (extended cols)    │          │
  │                                              │ + workflow_runs       │          │
  │                                              │   (snapshot cols)     │          │
  │                                              └────────────────────┘          │
  └────────────────────────────────────────────────────────────────────────────┘
  External: NONE in Wave 1 (mock executor only; integrations deferred to Waves 2–4)
```

New packages/modules (proposed paths; final names are the implementer's choice):
- `src/devflow_api/orchestration.py` — `WorkflowOrchestrator`, `RecoveryService`.
- `src/devflow_api/executors/__init__.py`, `base.py` (`Executor` Protocol only), `registry.py`, `mock.py`.
- `src/devflow_api/models/workflow_step_run.py` — `WorkflowStepRun`.
- `src/devflow_api/schemas/workflow_template.py` — `WorkflowTemplate`, `StepDefinition`, `ToolSelection`, `RetryPolicy`, `TemplateDefaults`, `ApprovalOperation`.
- `src/devflow_api/schemas/executor.py` — `ExecutorIdentifier`, `Capability`, `TimeoutPolicy`, `CancellationHandle`, `ExecutionContext`, `ArtifactRef`, `StructuredError`, `ExecutionMetadata`, `StepExecutionResult`.
- `src/devflow_api/schemas/workflow.py` — extended `WorkflowRunResponse` (`steps`), `StepRunResponse`, `ResolveApprovalRequest` (imports from `schemas/executor.py` and `schemas/workflow_template.py`).
- `src/devflow_api/repositories/workflow_step_run.py` — `WorkflowStepRunRepository` (CAS, lease, consume, fence).
- `alembic/versions/008_add_workflow_execution_engine.py` — migration 008.

---

## 3. New Database Schema (migration 008)

### 3.0 Migration chain

The verified Alembic head is `007_add_github_confirmations` (preflight-confirmed via `alembic heads` and direct file read). Migration 008 chains from it:

```
001_create_initial_tables (Phase 0)
  └── ... (002–007, Phase 1)
        └── 007_add_github_confirmations  ← verified HEAD
              └── 008_add_workflow_execution_engine  ← Wave 1 (planned)
```

| Revision ID | `down_revision` | File | Wave | Tables / changes |
|---|---|---|---|---|
| `"007_add_github_confirmations"` | `"006_add_mcp_approvals"` | `007_add_github_confirmations.py` | Phase 1 | github_confirmations (existing) |
| `"008_add_workflow_execution_engine"` | `"007_add_github_confirmations"` | `008_add_workflow_execution_engine.py` | Phase 2 Wave 1 | NEW `workflow_step_runs`; ALTER `approval_requests` (additive columns + indexes); ALTER `workflow_runs` (snapshot columns) |

**Implementer note:** re-confirm the Alembic head immediately before authoring migration 008; if Phase 1 advanced past 007, re-chain accordingly.

### 3.1 `workflow_step_runs` (migration 008 — NEW table)

```sql
CREATE TABLE workflow_step_runs (
    id                  INTEGER  PRIMARY KEY AUTOINCREMENT,
    workflow_run_id     INTEGER  NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    step_key            TEXT     NOT NULL,
    step_version        INTEGER  NOT NULL,
    executor_id         TEXT     NOT NULL,
    tool_selection_json TEXT,
    depends_on_json     TEXT     NOT NULL DEFAULT '[]',   -- JSON array of step keys
    inputs_json         TEXT,                              -- resolved inputs, written at PENDING->READY (NULL until then)
    input_digest        TEXT,                              -- SHA-256 hex of canonical inputs (for idempotency)
    idempotency_key     TEXT,                              -- f"{run_id}:{step_key}:{attempt}"; set on dispatch (NULL until RUNNING)
    status              TEXT     NOT NULL DEFAULT 'PENDING'
                                 CHECK (status IN (
                                     'PENDING','READY','RUNNING','WAITING_APPROVAL',
                                     'SUCCEEDED','FAILED','CANCELLED','INTERRUPTED')),
    attempt             INTEGER  NOT NULL DEFAULT 0,       -- executions attempted so far; incremented on READY->RUNNING dispatch
    result_status       TEXT,                              -- succeeded|failed|cancelled|indeterminate
    output_json         TEXT,
    artifact_refs_json  TEXT,
    error_json          TEXT,
    lease_owner         TEXT,
    lease_expires_at    DATETIME,
    ready_at            DATETIME,
    dispatched_at       DATETIME,
    started_at          DATETIME,
    completed_at        DATETIME,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL,
    UNIQUE (workflow_run_id, step_key)
);
CREATE INDEX idx_step_runs_run_id       ON workflow_step_runs(workflow_run_id);
CREATE INDEX idx_step_runs_status       ON workflow_step_runs(status);
CREATE INDEX idx_step_runs_lease_expiry ON workflow_step_runs(lease_expires_at);
```

**Design notes:**
- `status` CHECK is exactly the eight values (REQ-E4.1.1). Terminal: `SUCCEEDED`, `FAILED`, `CANCELLED`. Non-terminal recoverable: `INTERRUPTED`.
- `attempt` = executions attempted so far (0 before first dispatch). Incremented atomically on `READY → RUNNING` (REQ-E4.6); NOT incremented on retry (`RUNNING → READY`) or recovery (`INTERRUPTED → READY`) — only on the subsequent dispatch.
- `idempotency_key` = `f"{run_id}:{step_key}:{attempt}"` computed with the post-increment `attempt`; set on dispatch; NULL until first dispatch.
- `inputs_json` is written at `PENDING → READY` (resolved from dependencies' outputs); `input_digest` supports idempotency (REQ-E4.9).
- `lease_owner` + `lease_expires_at` implement execution leases / duplicate-dispatch prevention / stale detection / fencing (REQ-E4.6, E4.10, E4.11).
- `UNIQUE (workflow_run_id, step_key)` enforces step-key uniqueness within a run.

**SQLAlchemy model (proposed):**
```python
# src/devflow_api/models/workflow_step_run.py
class WorkflowStepRun(TimestampMixin, Base):
    __tablename__ = "workflow_step_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','READY','RUNNING','WAITING_APPROVAL',"
            "'SUCCEEDED','FAILED','CANCELLED','INTERRUPTED')"
        ),
        UniqueConstraint("workflow_run_id", "step_key", name="uq_step_run_key"),
        Index("idx_step_runs_status", "status"),
        Index("idx_step_runs_lease_expiry", "lease_expires_at"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    step_key: Mapped[str] = mapped_column(Text)
    step_version: Mapped[int] = mapped_column(Integer)
    executor_id: Mapped[str] = mapped_column(Text)
    tool_selection_json: Mapped[str | None] = mapped_column(Text)
    depends_on_json: Mapped[str] = mapped_column(Text, server_default="[]")
    inputs_json: Mapped[str | None] = mapped_column(Text)
    input_digest: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="PENDING")
    attempt: Mapped[int] = mapped_column(Integer, server_default="0")
    result_status: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[str | None] = mapped_column(Text)
    artifact_refs_json: Mapped[str | None] = mapped_column(Text)
    error_json: Mapped[str | None] = mapped_column(Text)
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    dispatched_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
```

### 3.2 `workflow_runs` additive extension (migration 008 — ALTER, immutable template snapshot)

Migration 008 adds the immutable template snapshot columns to `workflow_runs`. **It does NOT change the `status` CHECK constraint** (backward compatibility with Phase 1):

```sql
-- migration 008 (workflow_runs ALTER portion)
ALTER TABLE workflow_runs ADD COLUMN template_snapshot_json TEXT;  -- full validated WorkflowTemplate JSON at run creation; NULL for legacy runs
ALTER TABLE workflow_runs ADD COLUMN template_version      INTEGER; -- WorkflowTemplate.template_version; NULL for legacy runs
ALTER TABLE workflow_runs ADD COLUMN template_hash         TEXT;    -- SHA-256 hex of canonical template_snapshot_json; NULL for legacy runs
CREATE INDEX idx_workflow_runs_template_hash ON workflow_runs(template_hash);
```

- Phase 1 runs have `NULL` for all three (additive, backward compatible).
- Legacy runs (created from `NULL`/empty `definition_json` in Phase 2) also have `NULL` (no snapshot, zero steps).
- The orchestrator executes from `template_snapshot_json`, NEVER from the live `Workflow.definition_json` (REQ-E1.8).

### 3.3 `approval_requests` additive extension (migration 008 — ALTER)

Migration 008 adds columns and indexes to `approval_requests`. **It does NOT change the `status` CHECK constraint** (backward compatibility with Phase 1, REQ-E3.1.2):

```sql
-- migration 008 (approval_requests ALTER portion)
ALTER TABLE approval_requests ADD COLUMN operation              TEXT;      -- Phase 2 protected operation (nullable for Phase 1 rows)
ALTER TABLE approval_requests ADD COLUMN parameters_hash       TEXT;      -- SHA-256 hex of canonical artifact/parameters
ALTER TABLE approval_requests ADD COLUMN actor_id              TEXT;      -- Settings.LOCAL_OPERATOR_ID
ALTER TABLE approval_requests ADD COLUMN workflow_step_run_id  INTEGER REFERENCES workflow_step_runs(id) ON DELETE SET NULL;
ALTER TABLE approval_requests ADD COLUMN consumed_at           DATETIME;  -- single-use consumption marker (NULL until consumed)
ALTER TABLE approval_requests ADD COLUMN expires_at            DATETIME;  -- pending TTL: requested_at + APPROVAL_TTL_SECONDS (NULL for Phase 1 rows = no pending expiry)
ALTER TABLE approval_requests ADD COLUMN authorization_expires_at DATETIME; -- approved validity: resolved_at + APPROVAL_AUTHORIZATION_VALIDITY_SECONDS (NULL for Phase 1 rows = no validity bound)
CREATE INDEX idx_approval_operation            ON approval_requests(operation);
CREATE INDEX idx_approval_consumed_at          ON approval_requests(consumed_at);
CREATE INDEX idx_approval_step_run_id          ON approval_requests(workflow_step_run_id);
CREATE INDEX idx_approval_expires_at            ON approval_requests(expires_at);
CREATE INDEX idx_approval_authz_expires_at     ON approval_requests(authorization_expires_at);
```

**Why no `consumed` status value:** Phase 1's `status` CHECK is `('pending','approved','rejected','expired')`. Single-use semantics are enforced by `consumed_at`; approved validity by `authorization_expires_at`; pending TTL by `expires_at`. None alter the status CHECK. An approval is consumable iff `status = 'approved' AND consumed_at IS NULL AND now < authorization_expires_at`.

**Deletion semantics (no NULL-to-NULL bypass):** `approval_requests.workflow_run_id` remains `ON DELETE CASCADE` (Phase 1). Deleting a run deletes its approvals directly (before the step FK matters), so the new `workflow_step_run_id` `ON DELETE SET NULL` never produces an orphaned, still-consumable approval. Invariant: **no code path deletes a single `WorkflowStepRun` without deleting the run** (the repository exposes no such method; enforced by a guard test). No trigger is required (approvals CASCADE on the run FK, unlike Phase 1 MCP/GitHub `SET NULL` + trigger).

### 3.4 Run ↔ step state derivation (no `workflow_runs.status` change)

`workflow_runs.status` keeps Phase 1's six values. The orchestrator derives the run status from step states and persists it via Phase 1 mechanisms (§5.8):

| Run status (Phase 1) | Derivation from `workflow_step_runs` |
|---|---|
| `pending` | Run created; no `start_or_resume` yet (all steps `PENDING`; legacy run with zero steps also starts `pending`) |
| `running` | After start, while any step is `PENDING`/`READY`/`RUNNING`/`INTERRUPTED` |
| `waiting_approval` | Any step is `WAITING_APPROVAL` |
| `completed` | All steps `SUCCEEDED` (a legacy zero-step run vacuously satisfies this on start) |
| `failed` | Any step `FAILED` AND none `CANCELLED` by cancel AND all steps are terminal |
| `cancelled` | Run cancelled |

**Terminal derivation rule (corrected):** the run reaches `completed`/`failed`/`cancelled` only when **all steps are terminal**. While any step is non-terminal, the run is `running` (or `waiting_approval`). This avoids the "run `failed` while an independent step is still `RUNNING`" inconsistency. With the default concurrency of 1, at most one step is `RUNNING`, so a `FAILED` step implies no other in-flight step and the run can go `failed` immediately.

---

## 4. Workflow Template Model (Pydantic v2)

The `Workflow.definition_json` column (Phase 1, `deferred=True, deferred_raiseload=True`) holds a validated `WorkflowTemplate` when present. The `Workflow` model is not modified.

```python
# src/devflow_api/schemas/workflow_template.py
ApprovalOperation = Literal["specification_approval", "implementation_authorization",
                            "pr_creation_approval", "merge_approval"]

class ToolSelection(BaseModel):
    executor_id: str                       # e.g. "mock"
    tool: str | None = None                # executor-specific tool name
    options: dict[str, Any] | None = None   # executor-specific options (validated by executor.input_schema)

class RetryPolicy(BaseModel):
    safe: bool = False                      # idempotent + no external write -> retryable
    idempotent: bool = False
    max_attempts: int = 1                  # >= 1; total executions allowed incl. the first

class StepDefinition(BaseModel):
    key: str                               # unique within template
    version: int                            # step version (durable)
    title: str
    description: str = ""
    depends_on: list[str] = []             # step keys
    executor_id: str                        # resolves to a registered Executor
    tool_selection: ToolSelection
    inputs: dict[str, Any] | None = None    # may reference "$steps.<key>.<output>"
    expected_outputs: list[str] | None = None
    timeout_s: int = 60
    retry_policy: RetryPolicy = RetryPolicy()
    approvable: bool = False
    protected_operation: ApprovalOperation | None = None  # required iff approvable

class TemplateDefaults(BaseModel):
    executor_id: str = "mock"
    timeout_s: int = 60
    retry_policy: RetryPolicy = RetryPolicy()

class WorkflowTemplate(BaseModel):
    template_version: int
    defaults: TemplateDefaults
    steps: list[StepDefinition]             # non-empty, unique keys, acyclic depends_on

    @model_validator(mode="after")
    def _validate(self) -> "WorkflowTemplate":
        # unique keys, non-empty, depends_on references exist, acyclic (topological sort)
        # approvable -> protected_operation set
        ...
```

**Validation rules (REQ-E1.1.3):** non-empty `steps`; unique `key`; `depends_on` references exist; acyclic graph; `approvable` ⇒ `protected_operation` set. `executor_id` presence/capability is checked at dispatch (READY → FAILED on miss), not at template validation.

**Input reference resolution (REQ-E1.4):** `inputs` may contain `"$steps.<key>.<output_name>"` strings. The orchestrator resolves these at the `PENDING → READY` transition by reading the dependency step's `output_json`. Unresolved references transition `PENDING → FAILED` with `INPUT_RESOLUTION_FAILED` (the step never reaches `READY`).

**Immutable snapshot (REQ-E1.8):** at run creation, the validated `WorkflowTemplate` is serialised to `workflow_runs.template_snapshot_json`; `template_version` and `template_hash = canonical_hash(template_snapshot_json)` are recorded. The orchestrator parses the snapshot (not the live `Workflow.definition_json`) for all execution decisions.

---

## 5. Workflow Orchestration Service

`WorkflowOrchestrator` (new, `src/devflow_api/orchestration.py`) drives runs. It depends on `WorkflowRepository`, `WorkflowRunRepository`, `WorkflowStepRunRepository`, `ApprovalRequestRepository`, `AuditLogRepository`, `ExecutorRegistry`, `WorkflowService`/`ApprovalService` (Phase 1, reused per §5.8), and `Settings`.

### 5.1 Public surface

```python
class WorkflowOrchestrator:
    async def create_run(self, workflow_id: int, actor: str) -> WorkflowRunResponse: ...
    async def start_or_resume(self, run_id: int, actor: str) -> WorkflowRunResponse: ...
    async def cancel(self, run_id: int, actor: str) -> WorkflowRunResponse: ...
    async def on_approval_resolved(self, approval_id: int, decision: str, actor: str) -> WorkflowRunResponse: ...
    # recover() lives on RecoveryService (§9)
```

### 5.2 `create_run` (REQ-E2.1)

```
create_run(workflow_id, actor):
    wf = load Workflow(workflow_id)            # 404 if missing
    raw = wf.definition_json
    if raw is None or raw == "":
        # legacy run (backward compatible with Phase 1): run only, no steps, no snapshot
        BEGIN IMMEDIATE
        insert WorkflowRun(status="pending", template_snapshot_json=NULL, ...)
        audit run_created(actor, template_version=NULL, template_hash=NULL, step_count=0)
        commit
        return run                              # steps == []
    template = WorkflowTemplate.model_validate_json(raw)   # 422 INVALID_WORKFLOW_TEMPLATE on failure
    snapshot = template.model_dump_json(...)                 # canonical, immutable
    thash = canonical_hash(snapshot)
    BEGIN IMMEDIATE
    insert WorkflowRun(status="pending",
                       template_snapshot_json=snapshot,
                       template_version=template.template_version,
                       template_hash=thash)
    for step in template.steps:
        insert WorkflowStepRun(workflow_run_id=run.id, step_key=step.key,
            step_version=step.version, executor_id=step.executor_id,
            tool_selection_json=..., depends_on_json=json.dumps(step.depends_on),
            status="PENDING", attempt=0, idempotency_key=NULL,
            created_at=now, updated_at=now)
    audit run_created(actor, template_version, template_hash, step_count=len(steps))
    commit                                      # all-or-nothing
    return run
```

### 5.3 `start_or_resume` (REQ-E2.2)

```
start_or_resume(run_id, actor):
    run = load run; steps = list steps for run
    if run.status in {"completed","failed","cancelled"}: raise 409 RUN_NOT_STARTABLE
    if run.status == "pending": WorkflowService.transition_run(run_id, "running", actor)   # pending->running (Phase 1 map)
    loop until no progress:
        # (a) resolve + ready
        for s in steps where s.status=="PENDING" and all deps SUCCEEDED:
            try: inputs = resolve_inputs(s, deps)   # "$steps.<key>.<out>" -> dep.output_json[...]
            except ResolutionError:
                CAS PENDING->FAILED (WHERE id=? AND status='PENDING')  # no lease fence (no lease yet)
                error_json={code:"INPUT_RESOLUTION_FAILED", category:"input_resolution", retryable:false}
                audit step_failed; mark run dirty; continue
            CAS PENDING->READY (WHERE id=? AND status='PENDING'); set ready_at, inputs_json, input_digest
            audit step_ready
        # (b) gate or dispatch each READY step (bounded by RUN_CONCURRENCY)
        for s in steps where s.status=="READY" (up to concurrency):
            if s.approvable:
                approval = find consumable approval for s (status='approved', consumed_at IS NULL, now < authorization_expires_at, op=s.protected_operation)
                if approval is None:
                    READY->WAITING_APPROVAL (CAS); create bound ApprovalRequest (§7.5); audit approval_requested
                    re-derive run running->waiting_approval via ApprovalService.request_bound_approval (§5.8)
                    continue
                # else fall through to dispatch; consume at the protected action (§5.6)
            # pre-dispatch checks -> READY->FAILED on error
            executor = registry.get(s.executor_id)
            if executor is None: CAS READY->FAILED EXECUTOR_NOT_FOUND; stop run dirty; continue
            if s.tool_selection.working_directory not None and not in APPROVED_WORKING_DIRECTORIES:
                CAS READY->FAILED WORKING_DIRECTORY_NOT_APPROVED; stop run dirty; continue
            if not executor.supports(s.tool_selection): CAS READY->FAILED CAPABILITY_MISMATCH; stop run dirty; continue
            dispatch(s, executor)   # §5.4
        # (c) after SUCCEEDED steps, re-evaluate dependents (loop)
        re-derive run status per §3.4 (only terminal when all steps terminal)
    # post-loop: if any step WAITING_APPROVAL -> run waiting_approval; elif all SUCCEEDED -> run completed; elif any FAILED and all terminal -> run failed
```

### 5.4 Dispatch & result handling (REQ-E2.3, E5.x, E4.6, E4.11)

```
dispatch(step, executor):
    lease_owner = f"worker:{uuid4()}"
    next_attempt = step.attempt + 1
    lease_expires_at = now + STEP_LEASE_TTL_SECONDS
    idem = f"{run_id}:{step_key}:{next_attempt}"
    rows = UPDATE workflow_step_runs
            SET status='RUNNING', lease_owner=?, lease_expires_at=?,
                dispatched_at=now, started_at=now, attempt=?, idempotency_key=?
            WHERE id=? AND status='READY'           # CAS (BEGIN IMMEDIATE)
    if rows != 1: raise StepDispatchConflict
    context = ExecutionContext(step_run_id, step_key, step_version, inputs, tool_selection,
                               working_directory, env_allowlist, timeout_s,
                               cancellation, actor_id, idem, input_digest, next_attempt)
    try:
        result = await asyncio.wait_for(executor.execute(context), timeout=timeout_s)
    except TimeoutError:
        result = StepExecutionResult(outcome="failed", error=StructuredError(category="timeout", retryable=policy.safe, ...))
    except CancelledError:
        result = StepExecutionResult(outcome="cancelled", ...)
    persist_result(step, next_attempt, lease_owner, result)   # fenced CAS below
```

```
persist_result(step, attempt, lease_owner, result):
    # fenced on lease_owner + attempt so a stale completion cannot mutate
    if result.outcome == "succeeded":
        validate result.output against executor.output_schema; on failure -> outcome="failed", category="executor"
        rows = UPDATE step SET status='SUCCEEDED', result_status='succeeded',
                        output_json=?, artifact_refs_json=?, completed_at=now,
                        lease_owner=NULL, lease_expires_at=NULL
                 WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?
        if rows != 1: audit step_stale_completion_discarded(prior_lease_owner, prior_attempt=attempt); return
        audit step_succeeded(step_key, step_version, result_status, attempt)
    elif result.outcome == "failed":
        maybe_retry(step, attempt, lease_owner, result)        # §5.6 (RUNNING->READY or ->FAILED)
    elif result.outcome == "cancelled":
        rows = UPDATE step SET status='CANCELLED', result_status='cancelled', error_json=?, completed_at=now,
                        lease_owner=NULL, lease_expires_at=NULL
                 WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?
        if rows == 1: audit step_cancelled
        else: audit step_stale_completion_discarded
    elif result.outcome == "indeterminate":
        rows = UPDATE step SET status='FAILED', result_status='indeterminate',
                        error_json={category:"internal"? no: "executor", retryable:false, ...}, completed_at=now,
                        lease_owner=NULL, lease_expires_at=NULL
                 WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?
        if rows == 1: audit step_failed(indeterminate; not retried); stop run dirty
        else: audit step_stale_completion_discarded
```

### 5.5 Stop safely on failure (REQ-E4.4)

- Transition failing step `RUNNING → FAILED` (fenced CAS); persist `error_json`, `completed_at`; release lease; audit `step_failed`.
- Do NOT dispatch new steps; dependents stay non-`READY`. Independent `RUNNING` steps are allowed to finish (no hard kill) unless the run is cancelled.
- Run → `failed` only once all steps are terminal (§3.4), via `WorkflowService.transition_run(run_id, "failed", actor, payload={"error_message": ...})` (Phase 1, `running → failed`).

### 5.6 Bounded retries (REQ-E4.7)

```
maybe_retry(step, attempt, lease_owner, result):
    policy = step.retry_policy
    retryable = (result.error.retryable and policy.safe and policy.idempotent
                 and attempt < policy.max_attempts)
    if retryable:
        # transient: RUNNING -> READY (NOT FAILED); attempt NOT incremented here (increment on next dispatch)
        rows = UPDATE step SET status='READY', lease_owner=NULL, lease_expires_at=NULL
                 WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?
        if rows == 1:
            audit step_retry_scheduled(step_key, next_attempt=attempt+1, reason=result.error)
        else:
            audit step_stale_completion_discarded; return
        # loop will re-dispatch (READY -> RUNNING increments attempt)
    else:
        rows = UPDATE step SET status='FAILED', result_status='failed', error_json=?, completed_at=now,
                        lease_owner=NULL, lease_expires_at=NULL
                 WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?
        if rows == 1: audit step_failed(step_key, error_code, error_category, attempt); stop run dirty
        else: audit step_stale_completion_discarded
```

`indeterminate` outcomes bypass `maybe_retry` and go straight to terminal `FAILED` in `persist_result` (never retried).

### 5.7 Cancel (REQ-E2.7)

```
cancel(run_id, actor):
    BEGIN IMMEDIATE
    for s in steps where s.status in (PENDING, READY, RUNNING, WAITING_APPROVAL, INTERRUPTED):
        # fenced CAS where a lease is held; non-leased states (PENDING/READY/WAITING_APPROVAL) match on status only
        if s.status == "RUNNING":
            UPDATE step SET status='CANCELLED', completed_at=now, lease_owner=NULL, lease_expires_at=NULL
             WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?   # fenced
        else:
            UPDATE step SET status='CANCELLED', completed_at=now
             WHERE id=? AND status=?   # status in (PENDING, READY, WAITING_APPROVAL, INTERRUPTED)
    signal cancellation to in-flight executor calls via CancellationHandle
    # run transition: from any non-terminal run state to cancelled via run_repo.transition_status
    run_repo.transition_status(run_id, "cancelled",
        from_states=["pending","running","waiting_approval"])
    audit run_cancelled(actor, cancelled_step_count)
    commit
    # idempotent on terminal runs (no mutation; HTTP 200)
```

### 5.8 Run transitions — Phase 1 service compatibility (REQ-E2.9)

The orchestrator reuses Phase 1 services exactly as Phase 1 already uses them:

| Run transition | Mechanism | Phase 1 basis |
|---|---|---|
| `pending → running` | `WorkflowService.transition_run(run_id, "running", actor)` | `WORKFLOW_TRANSITIONS["pending"]={"running"}` |
| `running → completed` | `WorkflowService.transition_run(run_id, "completed", actor)` | `WORKFLOW_TRANSITIONS["running"]` |
| `running → failed` | `WorkflowService.transition_run(run_id, "failed", actor, payload={"error_message":...})` | `WORKFLOW_TRANSITIONS["running"]` |
| `running → waiting_approval` | `ApprovalService.request_bound_approval(...)` (new), which calls `run_repo.transition_status(run_id, "waiting_approval", ["running"])` | Phase 1 `request_approval` does exactly this |
| `waiting_approval → running` | `ApprovalService.resolve` (extended) → `run_repo.transition_status(run_id, "running", ["waiting_approval"])` | Phase 1 `resolve` does exactly this |
| `waiting_approval → cancelled` | `ApprovalService.resolve` (reject) → `run_repo.transition_status(run_id, "cancelled", ["waiting_approval"])` | Phase 1 `resolve` does exactly this |
| `* → cancelled` (user cancel) | `run_repo.transition_status(run_id, "cancelled", ["pending","running","waiting_approval"])` | `transition_status` accepts a from-set (Phase 1 pattern) |

- `running → cancelled` is in `WORKFLOW_TRANSITIONS["running"]`, so a user cancel while `running` can also go through `WorkflowService.transition_run`. The orchestrator uses `run_repo.transition_status` for the cancel path to uniformly cover `pending`/`running`/`waiting_approval`.
- The orchestrator never introduces a run state outside Phase 1's six values and never calls a transition not supported by the Phase 1 maps without the matching Phase 1 mechanism.

---

## 6. Orchestrator–Executor Interface

Executors are isolated from state and persistence. The `Executor` Protocol lives in `src/devflow_api/executors/base.py`; all contract Pydantic types live in `src/devflow_api/schemas/executor.py` (canonical schema module — REQ-E2.8).

```python
# src/devflow_api/schemas/executor.py
class ExecutorIdentifier(BaseModel):
    id: str
    version: int

class Capability(BaseModel):
    operation: str
    tool: str | None = None

class TimeoutPolicy(BaseModel):
    default_s: int
    max_s: int

class CancellationHandle(BaseModel):
    cancelled: bool
    async def cancel(self) -> None: ...
    async def wait(self) -> None: ...

class ArtifactRef(BaseModel):
    name: str
    digest: str
    uri: str | None = None

class StructuredError(BaseModel):
    code: str
    category: str            # executor | timeout | cancelled | input_resolution | internal
    message: str
    retryable: bool

class ExecutionMetadata(BaseModel):
    executor_id: str
    executor_version: int
    started_at: datetime
    finished_at: datetime
    logs: list[str] = []

class ExecutionContext(BaseModel):
    run_id: int
    step_run_id: int
    step_key: str
    step_version: int
    inputs: dict[str, Any]
    tool_selection: ToolSelection        # imported from schemas/workflow_template.py
    working_directory: str | None
    env_allowlist: dict[str, str]
    timeout_s: int
    cancellation: CancellationHandle
    actor_id: str
    idempotency_key: str
    input_digest: str
    attempt: int
    model_config = {"frozen": True}

class StepExecutionResult(BaseModel):
    outcome: str             # succeeded | failed | cancelled | indeterminate
    output: dict[str, Any] | None = None
    artifact_refs: list[ArtifactRef] = []
    error: StructuredError | None = None
    metadata: ExecutionMetadata
```

```python
# src/devflow_api/executors/base.py
from devflow_api.schemas.executor import (ExecutionContext, StepExecutionResult, ...)

class Executor(Protocol):
    identifier: ExecutorIdentifier
    capabilities: list[Capability]
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    timeout_policy: TimeoutPolicy
    async def execute(self, context: ExecutionContext) -> StepExecutionResult: ...
    def supports(self, tool_selection: ToolSelection) -> bool: ...
```

**Invariants (mandatory guards, enforced by tests + AST):**
- No module under `src/devflow_api/schemas/` imports `devflow_api.executors` (no layering inversion).
- Executors MUST NOT import `devflow_api.repositories`, `devflow_api.services`, or `devflow_api.models`.
- Executors MUST NOT read `os.environ` (use `context.env_allowlist`).
- Executors MUST NOT spawn subprocesses/shell (Wave 1).
- Executors MUST NOT write outside `context.working_directory` (`None` or approved).
- The orchestrator validates `result.output` against `executor.output_schema` before persisting success.

---

## 7. Approval Binding, Validity, Consumption, and Re-gating

### 7.1 Canonical digest (REQ-E3.2)

```python
def canonical_hash(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```
Normalization: strip surrounding whitespace from string leaves; preserve internal content; keys ordered by `sort_keys`. The same function is used at issuance and consumption. Server-side identity (later waves) comes from server config, not the client (reusing Phase 1 W5-SR).

### 7.2 `consume_atomic` (REQ-E3.3, E3.6)

```python
async def consume_atomic(self, approval_id, operation, parameters_hash,
                         workflow_step_run_id, actor_id) -> bool:
    async with begin_immediate():
        now = datetime.now(UTC)
        result = await conn.execute(text("""
            UPDATE approval_requests
               SET consumed_at = :now
             WHERE id = :id
               AND status = 'approved'
               AND consumed_at IS NULL
               AND (authorization_expires_at IS NULL OR :now < authorization_expires_at)
               AND operation = :op
               AND parameters_hash = :ph
               AND workflow_step_run_id = :srid
               AND actor_id = :actor
        """), {...})
        await conn.commit()
        return result.rowcount == 1
```
- `rowcount == 1` → consumed; the protected action may proceed (only the dispatch owning the current lease calls this — §5.4/§5.6 fence first).
- `rowcount == 0` → refused `APPROVAL_NOT_CONSUMABLE`; audit `approval_not_consumable` with the mismatch reason; the approval row is not mutated; the protected action does NOT execute.
- `authorization_expires_at IS NULL` keeps Phase 1 approvals consumable (backward compatible).

### 7.3 Approval lifecycle (REQ-E3.4, E3.6)

```
pending   ──approve (< expires_at)──▶ approved  (set authorization_expires_at = resolved_at + VALIDITY)
   │                                     │
   │reject                               │ consume (< authorization_expires_at, consumed_at IS NULL)
   ▼                                     ▼
rejected                              consumed (consumed_at set; status stays "approved")
   │
   │expire (expires_at <= now, pending only)
   ▼
expired  (cannot be resolved; cannot be consumed)
```
- `pending` → `approved`/`rejected` (human resolve; reject on `now > expires_at` → 409 `APPROVAL_EXPIRED`).
- `pending` → `expired` (TTL sweep on `expires_at <= now`).
- `approved` → consumed (`consumed_at` set; status unchanged; consumable while `now < authorization_expires_at` and `consumed_at IS NULL`).
- An `approved` authorization past `authorization_expires_at` is NOT consumable; the gated step re-gates (§7.4).

### 7.4 Re-gating (REQ-E2.4, E3.6)

When an approvable step is `READY` and has no consumable approval (none approved, or the approved one expired (`now >= authorization_expires_at`) or was consumed), the orchestrator transitions `READY → WAITING_APPROVAL` and creates a fresh bound `ApprovalRequest`. This covers the initial gate and re-gating after authorization expiry. The step is NOT dispatched and NOT failed for an expired authorization — it waits for a fresh human decision.

### 7.5 `request_bound_approval` (REQ-E2.4, new; preserves Phase 1 `request_approval`)

```python
async def request_bound_approval(self, run_id, step_run_id, step_key, operation,
                                 parameters_hash, actor_id, action_description, payload):
    async with transaction(self._session):
        run_repo.transition_status(run_id, "waiting_approval", ["running"], commit=False)  # Phase 1 pattern
        approval = approval_repo.create({
            "workflow_run_id": run_id, "workflow_step_run_id": step_run_id,
            "step_name": step_key, "action_description": action_description,
            "payload_json": json.dumps(payload, allow_nan=False) if payload else None,
            "operation": operation, "parameters_hash": parameters_hash, "actor_id": actor_id,
            "expires_at": now + APPROVAL_TTL_SECONDS,
        }, commit=False)
        step_repo.transition_cas(step_run_id, "WAITING_APPROVAL", from_status="READY", commit=False)
        audit_repo.log_event("approval_requested", "system", run_id,
            {"approval_id": approval.id, "step_name": step_key, "operation": operation,
             "parameters_hash": parameters_hash}, commit=False)
    return approval
```
Phase 1 `request_approval(run_id, step_name, action_description, payload)` is preserved unchanged for Phase 1 callers; `request_bound_approval` is the additive Phase 2 path.

### 7.6 Extended `resolve` (REQ-E2.5)

Phase 1 `resolve(approval_id, decision, resolved_by)` is extended additively: after the Phase 1 behavior (set status, resolved_at, resolved_by; run `waiting_approval → running`/`→ cancelled`; audit `approval_resolved`), if `approval.workflow_step_run_id is not None` (Phase 2 gate): on `approved` set `authorization_expires_at = resolved_at + APPROVAL_AUTHORIZATION_VALIDITY_SECONDS` and `step_repo.transition_cas(step_run_id, "READY", from_status="WAITING_APPROVAL")`; on `rejected` `step_repo.transition_cas(step_run_id, "CANCELLED", from_status="WAITING_APPROVAL")` and notify the orchestrator. Phase 1 approvals (`workflow_step_run_id IS NULL`) resolve exactly as Phase 1 (run only).

### 7.7 Replay & stale-completion defense (REQ-E6.5, E4.11)

- Replay: consumption is a CAS `UPDATE ... WHERE status='approved' AND consumed_at IS NULL AND now < authorization_expires_at AND <bindings>`; a second use gets `rowcount == 0`.
- Stale completion: consumption is invoked only after the fenced `persist_result` CAS succeeds (the dispatch owns the current lease/attempt); a stale completion's persist CAS fails first, so it never reaches consume (REQ-E4.11.2).
- Cross-binding: operation/digest/step/actor bindings prevent authorizing a different action/step/actor.

---

## 8. Step State-Transition Specification

### 8.1 States and meaning

| State | Meaning | Terminal? |
|---|---|---|
| `PENDING` | Step row created; dependencies not yet all `SUCCEEDED`; inputs not resolved. | no |
| `READY` | Dependencies `SUCCEEDED`; inputs resolved; eligible for dispatch or approval gate. | no |
| `RUNNING` | Dispatched to an executor; lease held. | no |
| `WAITING_APPROVAL` | Approval gate reached; paused for human decision (initial or re-gate). | no |
| `SUCCEEDED` | Executor returned success; outputs persisted. | yes |
| `FAILED` | Terminal failure: non-retryable, attempt budget exhausted, pre-dispatch error, input-resolution failure, or indeterminate outcome. | yes |
| `CANCELLED` | Run cancelled (or approval rejected). | yes |
| `INTERRUPTED` | Process died / lease expired; pending recovery decision (retry or fail). | no (recoverable) |

### 8.2 Transition map (authoritative)

```
PENDING  ──deps SUCCEEDED + inputs resolved──▶ READY
PENDING  ──input resolution failure──▶ FAILED
PENDING  ──run cancel──▶ CANCELLED
READY    ──dispatch (CAS, lease, attempt++)──▶ RUNNING
READY    ──approvable gate / re-gate──▶ WAITING_APPROVAL
READY    ──pre-dispatch error (executor/dir/capability)──▶ FAILED
READY    ──run cancel──▶ CANCELLED
RUNNING  ──executor success (fenced)──▶ SUCCEEDED
RUNNING  ──retryable failure (safe+idempotent+attempt<max)──▶ READY        (transient; NOT FAILED)
RUNNING  ──terminal failure (non-retryable / attempt>=max / indeterminate)──▶ FAILED
RUNNING  ──recovery: lease expired (process death)──▶ INTERRUPTED
RUNNING  ──run cancel (fenced)──▶ CANCELLED
WAITING_APPROVAL ──approved──▶ READY
WAITING_APPROVAL ──rejected / run cancel──▶ CANCELLED
INTERRUPTED ──recovery: safe + attempt<max──▶ READY   (no auto-dispatch; awaits explicit start)
INTERRUPTED ──recovery: unsafe / attempt>=max──▶ FAILED
INTERRUPTED ──run cancel──▶ CANCELLED
SUCCEEDED / FAILED / CANCELLED ──► (terminal; no outgoing transitions)
```

Every transition is a CAS inside `BEGIN IMMEDIATE`. Post-dispatch transitions (`RUNNING → *`) fence on `lease_owner` + `attempt` (REQ-E4.11). Invalid transitions are rejected (`INVALID_STEP_TRANSITION`), audited as `step_transition_rejected`, and leave no mutation. **A retry (`RUNNING → READY`) never passes through `FAILED`**; `FAILED` is terminal.

### 8.3 Run derivation

`workflow_runs.status` (Phase 1 six values) is derived per §3.4 and persisted via Phase 1 mechanisms (§5.8), preserving `run_status_changed` audit. The orchestrator never introduces run states outside the Phase 1 enum. Terminal run states are reached only when all steps are terminal.

---

## 9. Recovery

### 9.1 Startup recovery (`RecoveryService.recover`, REQ-E4.3)

```
recover():
    # Phase 1 — interrupt stale RUNNING (automatic state reconciliation)
    BEGIN IMMEDIATE
    rows = SELECT id, lease_owner, lease_expires_at, attempt, step_key, retry_policy_json
           FROM workflow_step_runs WHERE status='RUNNING'
    for r in rows:
        if r.lease_expires_at is None or r.lease_expires_at <= now:
            rows2 = UPDATE workflow_step_runs SET status='INTERRUPTED', lease_owner=NULL, lease_expires_at=NULL
                    WHERE id=r.id AND status='RUNNING' AND lease_owner=r.lease_owner AND attempt=r.attempt  # fenced
            if rows2 == 1: audit step_interrupted(prior_lease_owner, prior_lease_expires_at)
    commit
    # Phase 2 — decide retry-or-fail for each INTERRUPTED (idempotent; CAS on status='INTERRUPTED')
    rows = SELECT ... FROM workflow_step_runs WHERE status='INTERRUPTED'
    for r in rows:
        policy = json.loads(r.retry_policy_json)   # from snapshot/step
        if policy.safe and policy.idempotent and r.attempt < policy.max_attempts:
            UPDATE ... SET status='READY' WHERE id=r.id AND status='INTERRUPTED'
            audit step_recovery_decided(decision="retry", attempt=r.attempt)
        else:
            UPDATE ... SET status='FAILED', error_json={category:"internal", retryable:false}, completed_at=now
                 WHERE id=r.id AND status='INTERRUPTED'
            audit step_recovery_decided(decision="fail", reason="unsafe_or_budget_exhausted", attempt=r.attempt)
    re-derive affected runs per §3.4 (do NOT dispatch)
    return count_interrupted
```

- A `RUNNING` step with a still-valid lease is NOT interrupted (live worker).
- Idempotent: a second `recover()` finds `INTERRUPTED` rows already decided (CAS `WHERE status='INTERRUPTED'` is a no-op once decided to `READY`/`FAILED`).
- **No auto-dispatch:** recovered `READY` steps wait for an explicit `start_or_resume` (resolved default).
- A run whose only in-flight step became `INTERRUPTED` is re-derived to `running` (recoverable) until the decision; after `INTERRUPTED → FAILED` and all steps terminal, the run → `failed`.

### 9.2 Stale detection (lease model, REQ-E4.10)

- `STEP_LEASE_TTL_SECONDS` (default 60); heartbeat every `STEP_HEARTBEAT_INTERVAL_SECONDS` (default 15).
- Renewal: `UPDATE ... SET lease_expires_at=? WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?` (fenced; only owner + current attempt).
- A cancelled run's `RUNNING` step rejects renewal (the cancel set it to `CANCELLED`, so the CAS `status='RUNNING'` fails).
- Stale detection feeds §9.1.

### 9.3 Timeout vs interruption (REQ-E5.3)

- **Timeout** (executor raised / `wait_for` expired while the process is alive): `outcome="failed"`, `category="timeout"` → routed through `maybe_retry` (`RUNNING → READY`) or terminal `RUNNING → FAILED`. **Never `INTERRUPTED`.**
- **Process death** (no completion recorded, process restarted): the lease expires; recovery transitions `RUNNING → INTERRUPTED` (§9.1). Only this path reaches `INTERRUPTED`.

---

## 10. SQLite-Safe Transactional Patterns

Reused from Phase 1 (W4/T2) and applied consistently:

1. **`BEGIN IMMEDIATE`** for every write transaction (run creation, dispatch CAS, persist CAS, consume, cancel, recovery). Acquires the write lock up-front.
2. **`busy_timeout`** (e.g. 5000 ms) so writers wait briefly for the lock instead of failing immediately.
3. **Compare-and-set (CAS)** `UPDATE ... WHERE id=? AND status=?` (and `lease_owner`/`attempt` for post-dispatch transitions) with `rowcount` checks; `rowcount != expected` → conflict, no mutation, raise (`StepDispatchConflict`, `INVALID_STEP_TRANSITION`, `APPROVAL_NOT_CONSUMABLE`) or discard stale (`step_stale_completion_discarded`).
4. **Fencing (REQ-E4.11):** post-dispatch transitions fence on `lease_owner` + `attempt` so a superseded dispatch cannot mutate state or consume an approval.
5. **Short transactions:** the executor call is NEVER inside a DB transaction. Dispatch: `BEGIN IMMEDIATE` → CAS `READY→RUNNING` + lease → commit → run executor (no DB lock) → `BEGIN IMMEDIATE` → fenced persist CAS + audit → commit.
6. **Retry on `SQLITE_BUSY`:** bounded retries with small backoff for `BEGIN IMMEDIATE` contention (rare with concurrency=1; specified for later concurrency).
7. **Write serialisation is a database guarantee:** the design does NOT claim SQLAlchemy connection pooling serialises writes. SQLite serialises writers via its file lock; `BEGIN IMMEDIATE` acquires it deterministically.
8. **Timestamps:** `datetime.now(UTC)` exclusively; `UTCDateTime` for all columns.
9. **Audit is append-only:** every transition writes one `WorkflowAuditLog` row inside the same transaction as the state change (atomic state + audit).

---

## 11. Mock Executor

`MockExecutor` (`src/devflow_api/executors/mock.py`) is the only registered executor in Wave 1.

```python
class MockExecutor:
    identifier = ExecutorIdentifier(id="mock", version=1)
    capabilities = [Capability(operation="noop")]
    input_schema = BaseModel
    output_schema = MockOutput  # {echo: dict, marker: str}
    timeout_policy = TimeoutPolicy(default_s=30, max_s=300)

    async def execute(self, context: ExecutionContext) -> StepExecutionResult:
        if context.cancellation.cancelled:
            return StepExecutionResult(outcome="cancelled", error=StructuredError(code="cancelled", category="cancelled", message="", retryable=False), metadata=...)
        opts = context.tool_selection.options or {}
        sleep_s = opts.get("sleep_s", 0)
        await asyncio.sleep(sleep_s)
        mode = opts.get("outcome", "succeeded")
        if mode == "failed":
            return StepExecutionResult(outcome="failed", error=StructuredError(code=opts.get("code","mock_fail"), category="executor", message="", retryable=True), metadata=...)
        if mode == "indeterminate":
            return StepExecutionResult(outcome="indeterminate", error=StructuredError(code="mock_indeterminate", category="executor", message="", retryable=False), metadata=...)
        output = {"echo": context.inputs, "marker": "mock-v1"}
        artifact = ArtifactRef(name="mock-artifact", digest=canonical_hash({"mock": True}))
        return StepExecutionResult(outcome="succeeded", output=output, artifact_refs=[artifact], metadata=ExecutionMetadata(executor_id="mock", executor_version=1, started_at=..., finished_at=...))
```

- **No filesystem, network, or subprocess** (REQ-E5.4.2). `working_directory=None`; `env_allowlist={}`.
- **Deterministic** (REQ-E5.4.4, E4.9.1): identical inputs → identical `output_json`/`artifact_refs` (except `mode`-driven failure/indeterminate).
- **Test modes** (via `tool_selection.options`): `outcome` ∈ {`succeeded`,`failed`,`indeterminate`,`cancelled`}, `sleep_s`, `fail_after_attempt` — to exercise retry, indeterminate, timeout, cancellation without external resources.
- **safe=true, idempotent=true** by declaration (so retries are exercisable, REQ-E4.7.5).

---

## 12. Security & Threat Model

### 12.1 Trust boundary

- **Local single-user.** Trust principal = local operator (`Settings.LOCAL_OPERATOR_ID`, default `'local_operator'`), server-side, never from the request body (reusing Phase 1 W5-SR). No multi-user authentication; none claimed.
- **Loopback only.** All services bind `127.0.0.1` (REQ-E6.1). No remote executor protocol.

### 12.2 Threat model (Stride-style, scoped to Wave 1)

| Threat | Mitigation |
|---|---|
| **Spoofing** | `actor_id` from `Settings.LOCAL_OPERATOR_ID`, never request body; loopback-only. |
| **Tampering** | All transitions are fenced CAS with `rowcount` checks; audit append-only; SQLite local. |
| **Repudiation** | Every transition/approval event audited with actor + timestamp + digest + attempt + lease_owner. |
| **Information disclosure** | `RedactSecretsProcessor` on all log records; digests not raw secrets; `payload_json` redaction. |
| **Denial of service** | Per-step `timeout_s`; `RUN_CONCURRENCY=1`; lease TTL; mock executor in-process and bounded. |
| **Elevation of privilege** | Executors cannot access repositories/services/models; no subprocess/shell; working-dir allowlist; explicit env. **Explicitly NOT OS-sandboxed** — §12.4. |
| **Replay** (reuse an approval) | Single-use `consume_atomic` CAS; digest + operation + step + actor binding; pending TTL (`expires_at`); approved validity (`authorization_expires_at`). |
| **Stale authorization** (approval outlives its action) | Digest binding; step binding; pending TTL; approved validity; consumption is terminal. |
| **Stale completion** (late return from superseded dispatch) | Lease/attempt fencing (REQ-E4.11); stale results discarded; cannot consume an approval. |
| **Cancellation race** (cancel during in-flight action) | Cancel transitions the step to `CANCELLED`; the in-flight persist CAS fences on `status='RUNNING'` and fails; the approval is not consumed (REQ-E2.7.4, E4.11.4). |

### 12.3 What is and is not isolated (honest statement)

**Isolated (application-level):** API surface (loopback); working directories (application allowlist; mock uses none); environment variables (explicit allowlist; no parent inheritance — contractual); credentials (never in logs; digests not raw); approvals (digest-bound, single-use, validity-bounded, replay-protected, stale-completion-protected).

**NOT isolated (must not be claimed as such):** filesystem (no OS-enforced per-executor jail); process (no OS-level isolation; executors in-process in Wave 1); network (no egress filtering); resources (no OS CPU/memory limits beyond asyncio timeouts).

### 12.4 Prerequisites before real coding-agent / shell execution (REQ-E6.8)

Before any real coding-agent (Codex/Kiro) or shell execution is enabled in a later wave, the following MUST exist and are out of scope for Wave 1: (1) OS-level process isolation (Windows Job Objects / Linux namespaces+seccomp); (2) OS-enforced filesystem allowlist; (3) network egress control (default deny); (4) resource limits (CPU, memory, wall time, disk); (5) credential vault; (6) executor capability review gate. Wave 1 gates these behind an explicit future wave; no Wave 1 code path enables them.

### 12.5 Audit integrity posture (REQ-E6.7)

`WorkflowAuditLog` is append-only (Phase 1). Wave 1 adds no update/delete paths. It is **not** cryptographically signed or tamper-evident; a future wave may add chained hashes. No false claim of cryptographic integrity.

---

## 13. API Contracts

Base path `/api/v1`. JSON bodies; ISO 8601 UTC timestamps; Phase 1 error shape `{"error": "...", "code": "..."}`.

### 13.1 Endpoints (new + extended)

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/workflows/{id}/runs` | 201 / 422 | Extended (REQ-E7.1): valid template → run + steps (201); non-empty invalid → 422 `INVALID_WORKFLOW_TEMPLATE`; `NULL`/empty template → legacy run (201, zero steps). |
| GET | `/workflow-runs/{run_id}` | 200 / 404 | Extended (REQ-E7.4): adds `steps: list[StepRunResponse]`; preserves `approvals`/`pending_approvals` (W1.5.4). |
| POST | `/workflow-runs/{run_id}/start` | 200 / 409 | NEW (REQ-E7.2): `start_or_resume`. 409 `RUN_NOT_STARTABLE` for terminal runs. |
| POST | `/workflow-runs/{run_id}/cancel` | 200 | NEW (REQ-E7.3): idempotent cancel. |
| GET | `/workflow-runs/{run_id}/steps` | 200 / 404 | NEW: ordered step list. |
| GET | `/workflow-runs/{run_id}/steps/{step_id}` | 200 / 404 | NEW (REQ-E7.4): step detail incl. output/error. |
| GET | `/workflow-runs/{run_id}/audit` | 200 | NEW (REQ-E7.5): ordered audit; `limit`/`offset`. |
| GET | `/approvals?status=pending` | 200 | Phase 1 (preserved). |
| GET | `/approvals/{id}` | 200 / 404 | Phase 1 (preserved). |
| POST | `/approvals/{id}/resolve` | 200 / 409 | Phase 1 (extended, REQ-E7.6): binding/validity verified at consume; 409 `APPROVAL_ALREADY_RESOLVED` / `APPROVAL_EXPIRED`. |

No `/merge` endpoint (Phase 1 exclusion preserved). No endpoint performs external writes in Wave 1.

### 13.2 Schemas (new)

```python
# src/devflow_api/schemas/workflow.py
class StepRunResponse(BaseModel):
    id: int
    step_key: str
    step_version: int
    executor_id: str
    status: str
    attempt: int
    result_status: str | None
    tool_selection: ToolSelection | None
    ready_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    output: dict[str, Any] | None
    artifact_refs: list[ArtifactRef] = []
    error: StructuredError | None

class WorkflowRunResponse(BaseModel):   # extends Phase 1
    # ... Phase 1 fields (id, workflow_id, status, started_at, completed_at, result_json, error_message, created_at, updated_at)
    steps: list[StepRunResponse] = []
    approvals: list[ApprovalResponse] = []          # Phase 1 W1.5.4 preserved
    pending_approvals: list[ApprovalResponse] = []  # Phase 1 W1.5.4 preserved

class ResolveApprovalRequest(BaseModel):  # extends Phase 1
    decision: str          # approved | rejected
    resolved_by: str | None = None
```

### 13.3 New audit event types (additive)

`run_created`, `run_status_changed` (Phase 1, reused), `step_created`, `step_ready`, `step_dispatched`, `step_succeeded`, `step_failed`, `step_retry_scheduled`, `step_interrupted`, `step_recovery_decided`, `step_stale_completion_discarded`, `step_transition_rejected`, `approval_requested` (Phase 1, extended with `operation`/`parameters_hash`), `approval_resolved` (Phase 1), `approval_expired`, `approval_not_consumable`, `run_cancelled`.

---

## 14. Streamlit Minimal Contracts (REQ-E7.7)

`6_Workflows.py` is extended (not replaced): run detail with ordered step list (status badges, timestamps); "Start/Resume" → `POST .../start`; "Cancel" → `POST .../cancel`; approval affordance for `WAITING_APPROVAL` steps → `POST /approvals/{id}/resolve`; "Backend unavailable" notice (not exception) when unreachable (Phase 1 pattern); no fabricated data; `AppTest` with mocked `APIClient`; `mypy --strict` passes. Full dashboard/filters/UX deferred to Wave 5.

---

## 15. Test Matrix (reference)

See `requirements.md` REQ-E8.1 for the authoritative named-test set (including all v2.1.0 additions: pre-dispatch failures, retry-as-transient, fencing/stale-completion, authorization validity/re-gating, attempt budget, run terminal derivation, template snapshot, schema layering) and REQ-E8.2/E8.3 for quality gates and migration round-trip. The design above is the implementation reference for each named test (state machine §8, recovery §9, SQLite/fencing §10, approval §7, executor §6/§11, security §12).

---

## 16. Architecture Decision Records (proposed)

- **ADR-0005 — Step-level eight-state lifecycle** (rich lifecycle on `workflow_step_runs`; run keeps Phase 1 six states).
- **ADR-0006 — Approval consumption via `consumed_at` and validity via `authorization_expires_at`** (no `consumed`/validity status value; Phase 1 CHECK unchanged).
- **ADR-0007 — Orchestrator-owns-state executor interface; contract types in `schemas/`** (executors stateless/pure; no schema→executor imports).
- **ADR-0008 — Honest isolation boundary** (application-level only; OS-level prerequisites listed).
- **ADR-0009 — Immutable template snapshot per run** (execute from `workflow_runs.template_snapshot_json`, not the live `definition_json`; legacy `NULL`-template runs preserved).
- **ADR-0010 — Lease/attempt fencing for stale completions** (post-dispatch CAS fences on `lease_owner`+`attempt`; retries are transient `RUNNING→READY`, never via `FAILED`).

(Existing ADRs 0001–0004 unchanged.)

---

## 17. Backward Compatibility

- `workflow_runs.status` CHECK: unchanged (six values). Snapshot columns added additively (nullable); Phase 1 and legacy runs have `NULL`.
- `approval_requests.status` CHECK: unchanged (four values; no `consumed`/validity status). New columns nullable; Phase 1 rows have `NULL` (`expires_at`/`authorization_expires_at` NULL ⇒ no expiry, Phase 1 semantics preserved).
- `WorkflowAuditLog`: unchanged structure; new event types added additively.
- Phase 1 endpoints: preserved; new endpoints added; `WorkflowRunResponse` gains `steps` (default `[]`), `approvals`/`pending_approvals` behavior identical (W1.5.4a–c).
- Phase 1 services: `WorkflowService.create_run`/`transition_run` and `ApprovalService.request_approval`/`resolve` signatures preserved; `request_bound_approval` (new) and `resolve` (additive step transition when `workflow_step_run_id` is set) extend without breaking Phase 1 callers.
- Phase 1 tests pass unmodified: legacy `NULL`/empty-template runs (201 pending, zero steps) preserve `test_create_run_returns_pending_status`; `WorkflowService.create_run` (service) is unchanged, preserving service tests; constraint tests unchanged.
- Migrations 001–007: unchanged; migration 008 chains from 007 and is reversible (drops step table, approval columns/indexes, and run snapshot columns; restores prior schema exactly).

---

## 18. Open Issues & Decisions for ChatGPT Review

Resolved defaults (applied; from task §3): pending TTL 3600s; approved authorization validity 3600s (separate column); run concurrency 1; lease 60s; heartbeat 15s; recovery = automatic reconciliation + explicit start; executor guards mandatory; immutable full template snapshot per run.

Remaining (implementation-time):
1. **Migration revision `008`** is derived from the verified head `007`; the implementer MUST re-confirm the head immediately before authoring and renumber if Phase 1 advanced.
2. **`attempt` representation**: spec uses `attempt` = executions attempted (0 before first); `max_attempts` = total executions incl. first. Confirm this is the intended semantics (alternatively 1-based from creation). The spec's tests encode the chosen semantics.
3. **Approved-authorization re-gating UX**: when an approved authorization expires while a step waits, the step re-gates to `WAITING_APPROVAL` (requires a fresh human decision). Confirm this is preferred over auto-failing the step.

These are documented, not silently resolved.
