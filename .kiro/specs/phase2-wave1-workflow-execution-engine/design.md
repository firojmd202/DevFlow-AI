# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Design

**Version:** 2.0.0
**Status:** Initial specification — awaiting ChatGPT review
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9)
**Last Updated:** 2026-11-17
**Companion:** `requirements.md` (EARS requirements + acceptance criteria), `tasks.md` (implementation breakdown).

**Version history:**
- v2.0.0 — 2026-11-17 — Initial design. Adds `workflow_step_runs` (eight-state step lifecycle), additive `approval_requests` extension (operation + digest + actor + step binding + `consumed_at` single-use), `WorkflowOrchestrator`, the `Executor` contract, `MockExecutor`, recovery, SQLite-safe CAS/lease patterns, minimal API/Streamlit, and migration 008 plan. Reuses Phase 1 `Workflow`, `WorkflowRun`, `ApprovalRequest`, `WorkflowAuditLog`, `Settings.LOCAL_OPERATOR_ID`, `RedactSecretsProcessor`, `UTCDateTime`, `BEGIN IMMEDIATE` patterns. No Phase 1 model is renamed or restructured; the Phase 1 `workflow_runs.status` and `approval_requests.status` CHECK constraints are unchanged.

---

## 1. Design Principles

Wave 1 extends Phase 1 without structural change. The Phase 0/1 layering is preserved:

```
Streamlit UI → APIClient (httpx) → FastAPI routers → Domain services → Repositories → SQLite
                                                   → WorkflowOrchestrator → Executors (in-process)
                                                   → Adapter registry (unchanged)
```

Eight rules govern Wave 1:

1. **Phase 0/1 contracts are immutable where possible.** `workflow_runs.status` and `approval_requests.status` CHECK constraints are not changed. Extensions are additive columns and one new table.
2. **The eight-state lifecycle is step-level.** `WorkflowRun` keeps Phase 1's six run states, derived from step states. This preserves Phase 1 behavior and tests.
3. **The orchestrator owns state; executors do not.** Executors receive an immutable context and return a pure result; the orchestrator persists, transitions, leases, and audits. No executor imports repositories/services/models.
4. **Approvals are digest-bound and single-use.** An approval authorizes exactly one operation, one artifact digest, one step, one actor, once. Consumption is a CAS `UPDATE` with `consumed_at`; no `consumed` status value is added.
5. **SQLite writes are serialised via the database, not the application.** `BEGIN IMMEDIATE` + `busy_timeout` + CAS `rowcount` checks; no application-level locks claiming to serialise writes.
6. **Recovery is idempotent and conservative.** Restart recovery interrupts stale `RUNNING` steps and retries only safe, idempotent steps under their attempt budget; ambiguous/indeterminate outcomes are never auto-retried.
7. **Honest isolation boundary.** Env-var scoping and path allowlists are application-level; the design explicitly states they are not OS sandboxing and lists what OS-level isolation is required before real coding-agent execution.
8. **Wave 1 ships one executor: the in-process mock.** No subprocess, shell, filesystem, or network from executors. No real coding-agent execution.

**Wave 1 execution boundary:** `WorkflowOrchestrator` reads the validated `WorkflowTemplate` from `Workflow.definition_json`, materialises `WorkflowStepRun` rows, and drives them through the eight-state lifecycle via `WorkflowOrchestrator.start_or_resume`, dispatching to registered `Executor`s, pausing for `ApprovalRequest` gates, and stopping safely on failure. Autonomous reading of `definition_json` (Phase 1's deferred capability) is now implemented — but only the structure defined here, dispatched only to the mock executor.

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
  │  │  - run + step list       │       │   workflows (Phase 1, extended)     │  │
  │  │  - start/resume, cancel   │       │   workflow-runs (Phase 1 + start/   │  │
  │  │  - approval affordance   │       │     cancel/audit/steps — new)      │  │
  │  └──────────────────────────┘       │   approvals (Phase 1, extended)     │  │
  │                                      │                                     │  │
  │                                      │ Services:                           │  │
  │                                      │   WorkflowService (Phase 1)         │  │
  │                                      │   ApprovalService (Phase 1, ext.)  │  │
  │                                      │   WorkflowOrchestrator (NEW)        │  │
  │                                      │   RecoveryService (NEW)             │  │
  │                                      │   ExecutorRegistry (NEW)            │  │
  │                                      │                                     │  │
  │                                      │ Repositories:                       │  │
  │                                      │   WorkflowRunRepository (ext.)      │  │
  │                                      │   WorkflowStepRunRepository (NEW)   │  │
  │                                      │   ApprovalRequestRepository (ext.)  │  │
  │                                      │   AuditLogRepository (Phase 1)     │  │
  │                                      │                                     │  │
  │                                      │ Executors (NEW package):            │  │
  │                                      │   Executor Protocol + contract types │  │
  │                                      │   MockExecutor (only one)          │  │
  │                                      │                                     │  │
  │                                      │ SQLAlchemy async + aiosqlite        │  │
  │                                      └──────────────────┬──────────────────┘  │
  │                                              ┌─────────▼──────────┐          │
  │                                              │ devflow.db (SQLite) │          │
  │                                              │ + workflow_step_runs │          │
  │                                              │ + approval_requests  │          │
  │                                              │   (extended cols)    │          │
  │                                              └────────────────────┘          │
  └────────────────────────────────────────────────────────────────────────────┘
  External: NONE in Wave 1 (mock executor only; integrations deferred to Waves 2–4)
```

New packages/modules (proposed paths; final names are the implementer's choice):
- `src/devflow_api/orchestration.py` — `WorkflowOrchestrator`, `RecoveryService`.
- `src/devflow_api/executors/__init__.py`, `base.py`, `registry.py`, `mock.py`.
- `src/devflow_api/models/workflow_step_run.py` — `WorkflowStepRun`.
- `src/devflow_api/schemas/workflow_template.py` — `WorkflowTemplate`, `StepDefinition`, `ToolSelection`, `RetryPolicy`, `TemplateDefaults`.
- `src/devflow_api/schemas/workflow.py` — extended `WorkflowRunResponse` (`steps`), `StepRunResponse`.
- `src/devflow_api/repositories/workflow_step_run.py` — `WorkflowStepRunRepository` (CAS, lease, consume).
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
| `"008_add_workflow_execution_engine"` | `"007_add_github_confirmations"` | `008_add_workflow_execution_engine.py` | Phase 2 Wave 1 | NEW `workflow_step_runs`; ALTER `approval_requests` (additive columns + indexes) |

**Implementer note:** re-confirm the Alembic head immediately before authoring migration 008; if Phase 1 advanced past 007, re-chain accordingly. The revision string `008_add_workflow_execution_engine` is the next logical revision from the verified head; it is not invented arbitrarily.

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
    inputs_json         TEXT,                              -- resolved inputs at dispatch (NULL until READY)
    input_digest        TEXT,                              -- SHA-256 hex of canonical inputs (for idempotency)
    idempotency_key     TEXT     NOT NULL,                  -- f"{run_id}:{step_key}:{attempt}"
    status              TEXT     NOT NULL DEFAULT 'PENDING'
                                 CHECK (status IN (
                                     'PENDING','READY','RUNNING','WAITING_APPROVAL',
                                     'SUCCEEDED','FAILED','CANCELLED','INTERRUPTED')),
    attempt             INTEGER  NOT NULL DEFAULT 0,
    result_status       TEXT,                              -- executor outcome: succeeded|failed|cancelled|indeterminate
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
- `inputs_json` is written when the step becomes `READY` (resolved from dependencies' outputs); `input_digest` and `idempotency_key` support idempotency (REQ-E4.9).
- `lease_owner` + `lease_expires_at` implement execution leases / duplicate-dispatch prevention / stale detection (REQ-E4.6, E4.10).
- `UNIQUE (workflow_run_id, step_key)` enforces step-key uniqueness within a run (REQ-E1.2.2).
- No `paused` value (mirrors Phase 1's `WorkflowRun` decision).

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
    workflow_run_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE")
    )
    step_key: Mapped[str] = mapped_column(Text)
    step_version: Mapped[int] = mapped_column(Integer)
    executor_id: Mapped[str] = mapped_column(Text)
    tool_selection_json: Mapped[str | None] = mapped_column(Text)
    depends_on_json: Mapped[str] = mapped_column(Text, server_default="[]")
    inputs_json: Mapped[str | None] = mapped_column(Text)
    input_digest: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text)
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

### 3.2 `approval_requests` additive extension (migration 008 — ALTER)

Migration 008 adds columns and indexes to `approval_requests`. **It does NOT change the `status` CHECK constraint** (backward compatibility with Phase 1, REQ-E3.1.2):

```sql
-- migration 008 (ALTER portion)
ALTER TABLE approval_requests ADD COLUMN operation            TEXT;             -- Phase 2 protected operation (nullable for Phase 1 rows)
ALTER TABLE approval_requests ADD COLUMN parameters_hash     TEXT;             -- SHA-256 hex of canonical artifact/parameters
ALTER TABLE approval_requests ADD COLUMN actor_id            TEXT;             -- Settings.LOCAL_OPERATOR_ID
ALTER TABLE approval_requests ADD COLUMN workflow_step_run_id INTEGER REFERENCES workflow_step_runs(id) ON DELETE SET NULL;
ALTER TABLE approval_requests ADD COLUMN consumed_at         DATETIME;          -- single-use consumption marker (NULL until consumed)
CREATE INDEX idx_approval_operation        ON approval_requests(operation);
CREATE INDEX idx_approval_consumed_at       ON approval_requests(consumed_at);
CREATE INDEX idx_approval_step_run_id       ON approval_requests(workflow_step_run_id);
```

**Why no `consumed` status value:** Phase 1's `status` CHECK is `('pending','approved','rejected','expired')`. Single-use semantics are enforced by the nullable `consumed_at` column combined with the atomic consume in §7. This avoids altering the Phase 1 constraint and avoids changing Phase 1 constraint tests. An approval is consumable iff `status = 'approved' AND consumed_at IS NULL`.

**Deletion semantics (no NULL-to-NULL bypass):**
- `approval_requests.workflow_run_id` remains `ON DELETE CASCADE` (Phase 1). Deleting a run deletes its approvals directly. Because step rows also CASCADE-delete from the run, and approvals are deleted via the run FK before the step FK matters, the new `workflow_step_run_id` `ON DELETE SET NULL` never produces an orphaned, still-consumable approval in practice. The invariant is: **no code path deletes a single `WorkflowStepRun` without deleting the run** (the repository exposes no such method; enforced by a guard test). This differs from the Phase 1 MCP/GitHub `SET NULL` + BEFORE DELETE trigger pattern, which was needed because those tables used `SET NULL` on the run FK. Approvals use `CASCADE` on the run FK, so no trigger is required.

### 3.3 Run ↔ step state derivation (no schema change to `workflow_runs`)

`workflow_runs.status` keeps Phase 1's six values. The orchestrator derives the run status from step states:

| Run status (Phase 1) | Derivation from `workflow_step_runs` |
|---|---|
| `pending` | All steps `PENDING` (none `READY`/`RUNNING` yet) |
| `running` | Any step `READY` or `RUNNING` (or `INTERRUPTED` pending recovery) |
| `waiting_approval` | Any step `WAITING_APPROVAL` |
| `completed` | All steps `SUCCEEDED` |
| `failed` | Any step `FAILED` (and run stop policy engaged) |
| `cancelled` | Run cancelled (any non-terminal step `CANCELLED` by cancel) |

This derivation is computed by the orchestrator and persisted via the existing Phase 1 `WorkflowService.transition_run` (reuse), so Phase 1 transition semantics, audit events (`run_status_changed`), and tests remain valid. The orchestrator never sets a run status outside Phase 1's six values.

---

## 4. Workflow Template Model (Pydantic v2)

The `Workflow.definition_json` column (Phase 1, `deferred=True, deferred_raiseload=True`) now holds a validated `WorkflowTemplate`. The `Workflow` model is not modified.

```python
# src/devflow_api/schemas/workflow_template.py
class ToolSelection(BaseModel):
    executor_id: str                       # e.g. "mock"
    tool: str | None = None                # executor-specific tool name
    options: dict[str, Any] | None = None   # executor-specific options (validated by executor.input_schema)

class RetryPolicy(BaseModel):
    safe: bool = False                      # idempotent + no external write → retryable
    idempotent: bool = False
    max_attempts: int = 1                  # >= 1

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
    protected_operation: str | None = None  # one of ApprovalOperation if approvable

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
        ...
```

**Validation rules (REQ-E1.1.3):**
- `steps` non-empty; `key` unique.
- Every `depends_on` entry references an existing step `key`.
- `depends_on` graph is acyclic (Kahn's algorithm / DFS cycle detection).
- `executor_id` presence is checked at dispatch (registry), not at template validation (a template may name a future executor); but an unknown `executor_id` fails the step at `READY → FAILED` with `EXECUTOR_NOT_FOUND` (REQ-E2.2.3).
- If `approvable` is true, `protected_operation` must be one of `ApprovalOperation` literals.

**Input reference resolution (REQ-E1.4):** `inputs` may contain `"$steps.<key>.<output_name>"` strings. The orchestrator resolves these at the `PENDING → READY` transition by reading the dependency step's `output_json`. Unresolved references fail the step with `INPUT_RESOLUTION_FAILED`.

---

## 5. Workflow Orchestration Service

`WorkflowOrchestrator` (new, `src/devflow_api/orchestration.py`) drives runs. It depends on `WorkflowRunRepository`, `WorkflowStepRunRepository`, `ApprovalRequestRepository`, `AuditLogRepository`, `ExecutorRegistry`, and `Settings`.

### 5.1 Public surface

```python
class WorkflowOrchestrator:
    async def create_run(self, workflow_id: int, actor: str) -> WorkflowRunResponse: ...
    async def start_or_resume(self, run_id: int, actor: str) -> WorkflowRunResponse: ...
    async def cancel(self, run_id: int, actor: str) -> WorkflowRunResponse: ...
    async def on_approval_resolved(self, approval_id: int, decision: str, actor: str) -> WorkflowRunResponse: ...
    async def recover(self) -> int: ...   # returns count of steps interrupted (startup recovery)
```

### 5.2 `create_run` (REQ-E2.1)

1. Load `Workflow`; parse `definition_json` into `WorkflowTemplate` (validate; 422 `INVALID_WORKFLOW_TEMPLATE` on failure).
2. `BEGIN IMMEDIATE`; insert `WorkflowRun` (status `pending`, record `template_version` in `result_json` metadata or a dedicated column? — see Open Decision; proposed: store `template_version` in `result_json` until a column is justified). Insert one `WorkflowStepRun` per `StepDefinition` (status `PENDING`, `attempt=0`, `idempotency_key=f"{run_id}:{step_key}:0"` initially recomputed at dispatch, `depends_on_json`, `tool_selection_json`, `executor_id`, `step_version`). Set `created_at`/`updated_at` via `datetime.now(UTC)`.
3. Write audit `run_created` (`actor`, `template_version`, `step_count`).
4. Commit. All-or-nothing (REQ-E2.1.1).

### 5.3 `start_or_resume` (REQ-E2.2)

Repeat until no progress:
1. Resolve inputs and compute readiness: for each `PENDING` step whose every dependency is `SUCCEEDED`, resolve `inputs` references; transition `PENDING → READY` (CAS), set `ready_at`, persist `inputs_json` + `input_digest`. Failed resolution → `PENDING → FAILED` with `INPUT_RESOLUTION_FAILED`.
2. For each `READY` step:
   - If `approvable` and no `pending` approval exists for it: `READY → WAITING_APPROVAL`, create `ApprovalRequest` (§7), audit `approval_requested`. (Re-derive run `waiting_approval`.)
   - Else if `executor_id` registered: dispatch (§6): `READY → RUNNING` (CAS, lease acquired), call `Executor.execute(context)` with a timeout and cancellation handle, then `RUNNING → SUCCEEDED|FAILED` based on result (§5.4). Concurrency limited to `Settings.RUN_CONCURRENCY` (proposed 1 in Wave 1).
   - Else (`executor_id` not registered): `READY → FAILED` `EXECUTOR_NOT_FOUND`, stop run (§5.5).
3. After a step `SUCCEEDED`, re-evaluate dependents (loop).
4. If any step `WAITING_APPROVAL`, re-derive run `waiting_approval` and stop (await human).
5. If all steps `SUCCEEDED`, transition run `completed`.
6. If any step `FAILED`, stop run safely (§5.5).

### 5.4 Dispatch & result handling (REQ-E2.3, E5.x)

```
dispatch(step_run):
    lease_owner = f"worker:{uuid4()}"   # or a stable worker id
    lease_expires_at = now + LEASE_TTL
    rows = UPDATE workflow_step_runs
            SET status='RUNNING', lease_owner=?, lease_expires_at=?,
                dispatched_at=now, started_at=now, attempt=attempt
            WHERE id=? AND status='READY'      # CAS (BEGIN IMMEDIATE)
    if rows != 1: raise StepDispatchConflict
    context = ExecutionContext(...)            # immutable; resolved inputs, allowlists, handle
    try:
        result = await asyncio.wait_for(executor.execute(context), timeout=timeout_s)
    except TimeoutError:
        result = StepExecutionResult(outcome="failed", error=StructuredError(category="timeout", ...))
    except CancelledError:
        result = StepExecutionResult(outcome="cancelled", ...)
    # persist result
    if result.outcome == "succeeded":
        validate result.output against output_schema; on failure -> outcome="failed", category="executor"
        UPDATE step SET status='SUCCEEDED', result_status='succeeded', output_json=?, artifact_refs_json=?, completed_at=now
        audit step_succeeded
    elif result.outcome == "failed":
        maybe_retry(step_run, result)          # §5.6
    elif result.outcome == "cancelled":
        UPDATE step SET status='CANCELLED', result_status='cancelled', error_json=?, completed_at=now
    elif result.outcome == "indeterminate":
        UPDATE step SET status='FAILED', result_status='indeterminate', error_json=(retryable=false), completed_at=now
        audit step_failed (indeterminate; not retried)
    release lease (set lease_owner=NULL, lease_expires_at=NULL on terminal)
```

### 5.5 Stop safely on failure (REQ-E4.4)

- Transition failing step `RUNNING → FAILED`; persist `error_json`, `completed_at`; audit `step_failed`.
- Set run `failed` (via Phase 1 `transition_run`) with `error_message`; audit `run_status_changed`.
- Do not dispatch new steps; dependents stay non-`READY`. Independent `RUNNING` steps are allowed to finish (no hard kill) unless the run is cancelled.

### 5.6 Bounded retries (REQ-E4.7)

```
maybe_retry(step_run, result):
    policy = step.retry_policy
    if result.error.retryable and policy.safe and policy.idempotent and step.attempt < policy.max_attempts:
        step.attempt += 1
        step.idempotency_key = f"{run_id}:{step_key}:{attempt}"
        UPDATE step SET status='READY', attempt=?, idempotency_key=?, lease_owner=NULL
        audit step_retry_scheduled
        # loop will re-dispatch
    else:
        UPDATE step SET status='FAILED', result_status='failed', error_json=?, completed_at=now
        audit step_failed
        stop run safely
```

`indeterminate` outcomes bypass `maybe_retry` (never retried).

### 5.7 Cancel (REQ-E2.7)

- `BEGIN IMMEDIATE`; for each non-terminal step (`PENDING`,`READY`,`RUNNING`,`WAITING_APPROVAL`,`INTERRUPTED`): `UPDATE ... SET status='CANCELLED', completed_at=now WHERE id=? AND status NOT IN ('SUCCEEDED','FAILED','CANCELLED')`.
- Signal cancellation to in-flight executor calls via their `CancellationHandle`.
- Transition run `cancelled` (Phase 1); audit `run_cancelled`.
- Idempotent on terminal runs (no mutation).

---

## 6. Orchestrator–Executor Interface

Executors are isolated from state and persistence. The contract lives in `src/devflow_api/executors/base.py`.

```python
class ExecutorIdentifier(BaseModel):
    id: str          # e.g. "mock"
    version: int

class Capability(BaseModel):
    operation: str        # e.g. "noop", "generate_spec" (future)
    tool: str | None = None

class TimeoutPolicy(BaseModel):
    default_s: int
    max_s: int

class CancellationHandle(BaseModel):
    # async-safe flag + event
    cancelled: bool
    async def cancel(self) -> None: ...
    async def wait(self) -> None: ...

class ExecutionContext(BaseModel):
    run_id: int
    step_run_id: int
    step_key: str
    step_version: int
    inputs: dict[str, Any]
    tool_selection: ToolSelection
    working_directory: str | None      # None or approved dir
    env_allowlist: dict[str, str]      # explicit; never os.environ
    timeout_s: int
    cancellation: CancellationHandle
    actor_id: str
    idempotency_key: str
    input_digest: str
    attempt: int
    model_config = {"frozen": True}   # immutable

class ArtifactRef(BaseModel):
    name: str
    digest: str            # SHA-256 of the artifact content
    uri: str | None = None # path or reference (within approved dir); None for mock

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

class StepExecutionResult(BaseModel):
    outcome: str             # succeeded | failed | cancelled | indeterminate
    output: dict[str, Any] | None = None
    artifact_refs: list[ArtifactRef] = []
    error: StructuredError | None = None
    metadata: ExecutionMetadata

class Executor(Protocol):
    identifier: ExecutorIdentifier
    capabilities: list[Capability]
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    timeout_policy: TimeoutPolicy
    async def execute(self, context: ExecutionContext) -> StepExecutionResult: ...
```

**Invariants (enforced by tests + AST guards):**
- Executors MUST NOT import `devflow_api.repositories`, `devflow_api.services`, or `devflow_api.models`.
- Executors MUST NOT read `os.environ` (use `context.env_allowlist`).
- Executors MUST NOT spawn subprocesses/shell (Wave 1).
- Executors MUST NOT write outside `context.working_directory` (which is `None` or an approved dir).
- The orchestrator validates `result.output` against `executor.output_schema` before persisting success.

---

## 7. Approval Binding & Consumption

### 7.1 Canonical digest (REQ-E3.2)

```python
def canonical_hash(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```
Normalization: strip surrounding whitespace from string leaves; preserve internal content; keys ordered by `sort_keys`; no key reordering beyond that. The same function is used at issuance (create `ApprovalRequest`) and consumption. Server-side identity (e.g. `repo_full_name` in later waves) comes from server config, not the client (reusing Phase 1 W5-SR).

### 7.2 `consume_atomic` (REQ-E3.3)

```python
async def consume_atomic(self, approval_id, operation, parameters_hash,
                         workflow_step_run_id, actor_id) -> bool:
    async with begin_immediate() as conn:           # BEGIN IMMEDIATE; busy_timeout set
        now = datetime.now(UTC)
        result = await conn.execute(
            text("""
                UPDATE approval_requests
                   SET consumed_at = :now
                 WHERE id = :id
                   AND status = 'approved'
                   AND consumed_at IS NULL
                   AND operation = :op
                   AND parameters_hash = :ph
                   AND workflow_step_run_id = :srid
                   AND actor_id = :actor
            """),
            {...},
        )
        await conn.commit()
        return result.rowcount == 1
```
- `rowcount == 1` → consumed; the protected action may proceed.
- `rowcount == 0` → refused with `APPROVAL_NOT_CONSUMABLE`. The caller MUST NOT proceed and MUST audit `approval_not_consumable` with the mismatch reason (status/consumed/op/digest/step/actor). The approval row is not mutated.

### 7.3 Approval lifecycle (REQ-E3.4)

```
pending  ──approve──▶ approved  ──consume──▶ (consumed_at set; status stays "approved")
   │                     │
   │reject               │expire(TTL)  [approved NOT auto-expired — REQ-E3.4.2]
   ▼                     ▼
rejected              expired
```
- `pending` → `approved`/`rejected` (human resolve).
- `pending` → `expired` (TTL sweep).
- `approved` → consumed (`consumed_at` set; status unchanged). An `approved` approval is consumable exactly once.
- Consumption is the authorization boundary for protected actions.

### 7.4 Replay defense (REQ-E6.5, E3.3)

Each protected action consumes exactly one approval. Because consumption is a CAS `UPDATE ... WHERE status='approved' AND consumed_at IS NULL AND <all bindings>`, a second use gets `rowcount == 0`. Bindings (operation, digest, step, actor) prevent cross-step, cross-operation, cross-actor authorization. An approval bound to step `a` cannot be consumed for step `b` (different `workflow_step_run_id`).

---

## 8. Step State-Transition Specification

### 8.1 States and meaning

| State | Meaning | Terminal? |
|---|---|---|
| `PENDING` | Step row created; dependencies not yet all `SUCCEEDED`; inputs not resolved. | no |
| `READY` | Dependencies `SUCCEEDED`; inputs resolved; eligible for dispatch or approval gate. | no |
| `RUNNING` | Dispatched to an executor; lease held. | no |
| `WAITING_APPROVAL` | Approval gate reached; paused for human decision. | no |
| `SUCCEEDED` | Executor returned success; outputs persisted. | yes |
| `FAILED` | Executor failure, timeout, input-resolution failure, or recovery-decided failure; run stopped. | yes |
| `CANCELLED` | Run cancelled (or approval rejected). | yes |
| `INTERRUPTED` | Process died / lease expired; pending recovery decision (retry or fail). | no (recoverable) |

### 8.2 Transition map (authoritative)

```
PENDING  ──deps SUCCEEDED──▶ READY
PENDING  ──run cancel──▶ CANCELLED
READY    ──dispatch (CAS)──▶ RUNNING
READY    ──approvable gate──▶ WAITING_APPROVAL
READY    ──run cancel──▶ CANCELLED
RUNNING  ──executor success──▶ SUCCEEDED
RUNNING  ──executor failure──▶ FAILED        (or retry → READY if safe & under budget)
RUNNING  ──lease expired (recovery)──▶ INTERRUPTED
RUNNING  ──run cancel──▶ CANCELLED
WAITING_APPROVAL ──approved──▶ READY
WAITING_APPROVAL ──rejected──▶ CANCELLED
WAITING_APPROVAL ──run cancel──▶ CANCELLED
INTERRUPTED ──recovery: safe & under budget──▶ READY
INTERRUPTED ──recovery: unsafe / over budget──▶ FAILED
INTERRUPTED ──run cancel──▶ CANCELLED
SUCCEEDED / FAILED / CANCELLED ──► (terminal; no outgoing transitions)
```

Every transition is a CAS `UPDATE ... WHERE id=? AND status=<expected_from>` inside `BEGIN IMMEDIATE`; invalid transitions are rejected (`INVALID_STEP_TRANSITION`), audited as `step_transition_rejected`, and leave no mutation.

### 8.3 Run derivation

`workflow_runs.status` (Phase 1 six values) is derived per §3.3 and set via Phase 1 `WorkflowService.transition_run` (reused), preserving `run_status_changed` audit. The orchestrator never introduces run states outside the Phase 1 enum.

---

## 9. Recovery

### 9.1 Startup recovery (`RecoveryService.recover`, REQ-E4.3)

```
recover():
    count = 0
    BEGIN IMMEDIATE
    rows = SELECT id, lease_owner, lease_expires_at, attempt, step_key
           FROM workflow_step_runs WHERE status='RUNNING'
    for r in rows:
        if r.lease_expires_at is None or r.lease_expires_at <= now:
            UPDATE workflow_step_runs SET status='INTERRUPTED',
                   lease_owner=NULL, lease_expires_at=NULL
             WHERE id=r.id AND status='RUNNING'   # CAS
            if rowcount == 1:
                audit step_interrupted(prior_lease_owner, prior_lease_expires_at)
                count += 1
    commit
    # idempotent: running again finds no RUNNING with expired lease (they're INTERRUPTED now)
    # then decide retry-or-fail for each INTERRUPTED
    for r in INTERRUPTED rows:
        if step.retry_policy.safe and step.retry_policy.idempotent and attempt < max_attempts:
            UPDATE ... SET status='READY' WHERE id=? AND status='INTERRUPTED'
            audit step_recovery_decided(decision="retry")
        else:
            UPDATE ... SET status='FAILED', error_json={category:"internal",retryable:false}, completed_at=now
                 WHERE id=? AND status='INTERRUPTED'
            audit step_recovery_decided(decision="fail")
    re-derive affected runs
    return count
```

- A `RUNNING` step with a still-valid lease is NOT interrupted (a live worker owns it).
- Idempotent: a second `recover()` finds `INTERRUPTED` (not `RUNNING`) rows and decides once; re-running `step_recovery_decided` is guarded by CAS (`WHERE status='INTERRUPTED'`).
- After recovery, `start_or_resume` may be invoked to continue, or the orchestrator auto-resumes eligible `READY` steps.

### 9.2 Stale detection (lease model, REQ-E4.10)

- `LEASE_TTL` (proposed 60s); heartbeat interval (proposed 15s).
- A worker holding a lease renews via `UPDATE ... SET lease_expires_at=? WHERE id=? AND status='RUNNING' AND lease_owner=?` (CAS; only owner renews).
- A cancelled run's `RUNNING` step rejects renewal (the cancel transitioned it to `CANCELLED`, so the CAS `status='RUNNING'` fails).
- Stale detection is the input to §9.1.

### 9.3 Timeout (REQ-E5.3)

- `asyncio.wait_for(executor.execute(context), timeout=timeout_s)`.
- Timeout → `StepExecutionResult(outcome="failed", error(category="timeout", retryable=policy.safe))`; routed through §5.6 `maybe_retry`.
- If the process dies mid-execution (no return), the lease expires and §9.1 interrupts the step.

---

## 10. SQLite-Safe Transactional Patterns

Reused from Phase 1 (W4/T2) and applied consistently:

1. **`BEGIN IMMEDIATE`** for every write transaction (state transitions, run creation, dispatch CAS, consume, cancel, recovery). Acquires the write lock up-front, avoiding "database is locked" mid-transaction.
2. **`busy_timeout`** (e.g. 5000 ms) set on the connection so writers wait briefly for the lock instead of failing immediately.
3. **Compare-and-set (CAS)** `UPDATE ... WHERE id=? AND status=?` with `rowcount` checks; `rowcount != expected` → conflict, no mutation, raise (`StepDispatchConflict`, `INVALID_STEP_TRANSITION`, `APPROVAL_NOT_CONSUMABLE`).
4. **Short transactions**: no long-held locks; dispatch holds the write transaction only for the CAS, then commits and runs the executor call outside the transaction (the executor call is not inside a DB transaction).
5. **Retry on `SQLITE_BUSY`**: bounded retries with small backoff for `BEGIN IMMEDIATE` contention (the mock executor + concurrency=1 in Wave 1 makes contention rare; the pattern is specified for correctness under later concurrency).
6. **Write serialisation is a database guarantee**: the design does NOT claim SQLAlchemy connection pooling serialises writes (correcting the Phase 1 v1.5.2 misconception). SQLite serialises writers via its file lock; `BEGIN IMMEDIATE` acquires it deterministically.
7. **Timestamps**: `datetime.now(UTC)` exclusively; `UTCDateTime` TypeDecorator for all columns.
8. **Audit is append-only**: every transition writes one `WorkflowAuditLog` row inside the same transaction as the state change (so audit and state commit atomically).

**Transaction scope for dispatch (important):** the executor call is NOT inside a DB transaction. The flow is: `BEGIN IMMEDIATE` → CAS `READY→RUNNING` + lease → commit → run executor (no DB lock held) → `BEGIN IMMEDIATE` → persist result + CAS `RUNNING→terminal` + audit → commit. This avoids holding the write lock across a long executor call.

---

## 11. Mock Executor

`MockExecutor` (`src/devflow_api/executors/mock.py`) is the only registered executor in Wave 1.

```python
class MockExecutor:
    identifier = ExecutorIdentifier(id="mock", version=1)
    capabilities = [Capability(operation="noop")]
    input_schema = BaseModel   # accepts any dict
    output_schema = MockOutput  # {echo: dict, marker: str}
    timeout_policy = TimeoutPolicy(default_s=30, max_s=300)

    async def execute(self, context: ExecutionContext) -> StepExecutionResult:
        # honor cancellation
        if context.cancellation.cancelled:
            return StepExecutionResult(outcome="cancelled", error=StructuredError(category="cancelled", ...))
        # optional short sleep (configurable via tool_selection.options.sleep_s, default 0)
        await asyncio.sleep(sleep_s)
        # deterministic output: echo inputs + constant marker
        output = {"echo": context.inputs, "marker": "mock-v1"}
        artifact = ArtifactRef(name="mock-artifact", digest=canonical_hash({"mock": True}))
        return StepExecutionResult(
            outcome="succeeded",
            output=output,
            artifact_refs=[artifact],
            metadata=ExecutionMetadata(executor_id="mock", executor_version=1, ...),
        )
```

- **No filesystem, network, or subprocess** (REQ-E5.4.2). `working_directory` is `None`; `env_allowlist` is `{}`.
- **Deterministic** (REQ-E5.4.4, E4.9.1): identical inputs → identical `output_json` and `artifact_refs`.
- **Test modes** (via `tool_selection.options`): `outcome="failed"`, `outcome="indeterminate"`, `outcome="cancelled"`, `sleep_s`, `fail_after_attempt` — to exercise retry, indeterminate, timeout, and cancellation paths without external resources.
- **safe=true, idempotent=true** by declaration (so retries are exercisable, REQ-E4.7.4).

---

## 12. Security & Threat Model

### 12.1 Trust boundary

- **Local single-user.** The trust principal is the local operator (`Settings.LOCAL_OPERATOR_ID`, default `'local_operator'`), resolved server-side, never from the request body (reusing Phase 1 W5-SR). Wave 1 does NOT authenticate multiple users and does NOT claim to.
- **Loopback only.** All services bind `127.0.0.1` (REQ-E6.1). No remote executor protocol.

### 12.2 Threat model (Stride-style, scoped to Wave 1)

| Threat | Mitigation |
|---|---|
| **Spoofing** (caller claims another actor) | `actor_id` from `Settings.LOCAL_OPERATOR_ID`, never request body; loopback-only transport. |
| **Tampering** (modify step state/approval out of band) | All transitions are CAS with `rowcount` checks; audit append-only; SQLite file is local. |
| **Repudiation** | Every transition and approval event audited with actor + timestamp + digest. |
| **Information disclosure** (secrets in logs/audit) | `RedactSecretsProcessor` on all log records; digests not raw secrets; `payload_json` redaction. |
| **Denial of service** (runaway executor) | Per-step `timeout_s`; `RUN_CONCURRENCY` limit (proposed 1); lease TTL; mock executor is in-process and bounded. |
| **Elevation of privilege** (executor escapes boundary) | Executors cannot access repositories/services/models; no subprocess/shell; working dir allowlist; explicit env. **Explicitly NOT OS-sandboxed** — see §12.4. |
| **Replay** (reuse an approval) | Single-use `consume_atomic` CAS; digest + operation + step + actor binding; TTL expiry on `pending`. |
| **Stale authorization** (approval outlives its action) | Digest binding (parameters must match at consume); step binding; TTL on `pending`; `approved` consumption is terminal. |

### 12.3 What is and is not isolated (honest statement)

**Isolated (application-level):**
- API surface (loopback only).
- Working directories (application allowlist check; `MockExecutor` uses none).
- Environment variables (explicit allowlist; no parent inheritance — contractual in Wave 1 since no subprocess).
- Credentials (never in logs; digests not raw secrets).
- Approvals (digest-bound, single-use, replay-protected).

**NOT isolated (must not be claimed as such):**
- Filesystem (no OS-enforced per-executor filesystem jail; the working-dir allowlist is an application check a sufficiently privileged local process can bypass).
- Process (no OS-level process isolation; executors run in-process in Wave 1).
- Network (no egress filtering).
- Resources (no OS CPU/memory limits beyond asyncio timeouts).

### 12.4 Prerequisites before real coding-agent / shell execution (REQ-E6.8)

Before any real coding-agent (Codex/Kiro) or shell execution is enabled in a later wave, the following MUST exist and are out of scope for Wave 1:
1. **OS-level process isolation** (Windows Job Objects / Linux namespaces+seccomp).
2. **OS-enforced filesystem allowlist** (chroot/bind-mount/ACL, not an application check).
3. **Network egress control** (allowlist of destinations; default deny).
4. **Resource limits** (CPU, memory, wall time, disk quotas).
5. **Credential vault** (secrets injected per-execution, not ambient).
6. **Executor capability review gate** (human approves each new executor's capability declaration).
Wave 1 gates these behind an explicit future wave; no Wave 1 code path enables them.

### 12.5 Audit integrity posture (REQ-E6.7)

`WorkflowAuditLog` is append-only (Phase 1). Wave 1 adds no update/delete paths. It is **not** cryptographically signed or tamper-evident; a future wave may add chained hashes (e.g., each row's `payload_json` includes the previous row's hash). The spec makes no false claim of cryptographic integrity.

---

## 13. API Contracts

Base path `/api/v1`. All request/response bodies are JSON; timestamps ISO 8601 UTC. Error shape is Phase 1's `{"error": "...", "code": "..."}`.

### 13.1 Endpoints (new + extended)

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/workflows/{id}/runs` | 201 / 422 | Extended (REQ-E7.1): creates run + step rows. 422 `INVALID_WORKFLOW_TEMPLATE`. |
| GET | `/workflow-runs/{run_id}` | 200 / 404 | Extended (REQ-E7.4): adds `steps: list[StepRunResponse]`; preserves `approvals`/`pending_approvals` (W1.5.4). |
| POST | `/workflow-runs/{run_id}/start` | 200 / 409 | NEW (REQ-E7.2): `start_or_resume`. 409 `RUN_NOT_STARTABLE` for terminal runs. |
| POST | `/workflow-runs/{run_id}/cancel` | 200 | NEW (REQ-E7.3): idempotent cancel. |
| GET | `/workflow-runs/{run_id}/steps` | 200 / 404 | NEW: ordered step list. |
| GET | `/workflow-runs/{run_id}/steps/{step_id}` | 200 / 404 | NEW (REQ-E7.4): step detail incl. output/error. |
| GET | `/workflow-runs/{run_id}/audit` | 200 | NEW (REQ-E7.5): ordered audit; `limit`/`offset`. |
| GET | `/approvals?status=pending` | 200 | Phase 1 (preserved). |
| GET | `/approvals/{id}` | 200 / 404 | Phase 1 (preserved). |
| POST | `/approvals/{id}/resolve` | 200 / 409 | Phase 1 (extended, REQ-E7.6): binding verified on consume; 409 `APPROVAL_ALREADY_RESOLVED` / `APPROVAL_EXPIRED`. |

No `/merge` endpoint (Phase 1 exclusion preserved). No endpoint performs external writes in Wave 1.

### 13.2 Schemas (new)

```python
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

`run_created`, `run_status_changed` (Phase 1, reused), `step_created`, `step_transition_rejected`, `step_ready`, `step_dispatched`, `step_succeeded`, `step_failed`, `step_retry_scheduled`, `step_interrupted`, `step_recovery_decided`, `approval_requested` (Phase 1, extended with `operation`/`parameters_hash`), `approval_resolved` (Phase 1), `approval_expired`, `approval_not_consumable`, `run_cancelled`.

---

## 14. Streamlit Minimal Contracts (REQ-E7.7)

`6_Workflows.py` is extended (not replaced):
- Run list → run detail with ordered step list (status badges, timestamps).
- "Start/Resume" button → `POST .../start`; "Cancel" button → `POST .../cancel`.
- For `WAITING_APPROVAL` steps, an approval affordance (Approve/Reject) → `POST /approvals/{id}/resolve`.
- "Backend unavailable" notice (not exception) when unreachable (Phase 1 pattern).
- No fabricated data; `AppTest` with mocked `APIClient` for UI tests.
- `mypy --strict` passes.
- Full dashboard, filters, and rich UX are deferred to Wave 5.

---

## 15. Test Matrix (reference)

See `requirements.md` REQ-E8.1 for the authoritative named-test set and REQ-E8.2/E8.3 for quality gates and migration round-trip. The design above is the implementation reference for each named test (state machine §8, recovery §9, SQLite §10, approval §7, executor §6/§11, security §12).

---

## 16. Architecture Decision Records (proposed)

New ADRs to be authored with the spec (not required in this task, but listed for completeness):
- **ADR-0005 — Step-level eight-state lifecycle** (why the rich lifecycle lives on `workflow_step_runs`, run keeps Phase 1 six states).
- **ADR-0006 — Approval consumption via `consumed_at` not a `consumed` status** (backward compatibility with the Phase 1 CHECK constraint; single-use via CAS).
- **ADR-0007 — Orchestrator-owns-state executor interface** (why executors are stateless/pure and cannot touch persistence).
- **ADR-0008 — Honest isolation boundary** (what Wave 1 isolates at the application level and what OS-level isolation is required before real coding-agent execution).

(Existing ADRs 0001–0004 are unchanged.)

---

## 17. Backward Compatibility

- `workflow_runs.status` CHECK: unchanged (six values). Run transitions reuse Phase 1 `WorkflowService.transition_run`.
- `approval_requests.status` CHECK: unchanged (four values; no `consumed`). New columns nullable; Phase 1 rows have `NULL` for `operation`/`parameters_hash`/`actor_id`/`workflow_step_run_id`/`consumed_at` and remain resolvable.
- `WorkflowAuditLog`: unchanged structure; new event types added additively.
- Phase 1 endpoints: preserved; new endpoints added; `WorkflowRunResponse` gains `steps` (default `[]`), `approvals`/`pending_approvals` behavior identical (W1.5.4a–c).
- Phase 1 tests: pass unmodified. The `consumed_at` design means no Phase 1 constraint test needs editing. The only intentional additions are new Wave 1 tests (REQ-E8.1).
- Migrations 001–007: unchanged; migration 008 chains from 007 and is reversible.

---

## 18. Open Issues & Decisions for ChatGPT Review

1. **`Settings.APPROVAL_TTL_SECONDS` default** (proposed 3600) — confirm.
2. **`Settings.RUN_CONCURRENCY`** (proposed 1 in Wave 1 for determinism) — confirm; note mock executor is in-process.
3. **Lease TTL / heartbeat** (proposed 60s / 15s) — confirm.
4. **`approved` TTL** (REQ-E3.4.2 deliberately does NOT auto-expire `approved`; flagged for review) — confirm or change.
5. **Template snapshot on run** (store `template_version` + `definition_hash` on run to detect template drift between run creation and dispatch; proposed: snapshot `template_version` and compute a `definition_hash` at run creation, store in `result_json` metadata, and reject `start` if the live `Workflow.definition_json` hash changed) — confirm approach vs. simply trusting the live template.
6. **`template_version` storage location** (proposed: `WorkflowRun.result_json` metadata to avoid adding a column; alternatively a small `template_version` column via migration 008) — confirm. Current spec avoids a new run column.
7. **Recovery auto-resume** (proposed: `recover()` transitions `INTERRUPTED→READY` for safe steps but does NOT auto-dispatch; a subsequent `start` or a scheduled tick dispatches) — confirm whether Wave 1 should auto-resume after recovery.
8. **Executor AST/import guard test scope** (forbid `subprocess`/`os.system`/`shell=True`/`os.environ` in `executors/`) — confirm as a hard gate vs. advisory.
9. **Migration revision number** `008` is derived from the verified head `007`; confirm no Phase 1 migration was added between preflight and implementation.

These are documented, not silently resolved; the implementer resolves them with ChatGPT review before coding.
