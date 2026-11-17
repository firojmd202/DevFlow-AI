# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Tasks

**Version:** 2.0.0
**Status:** Initial specification — awaiting ChatGPT review
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9)
**Last Updated:** 2026-11-17
**Companions:** `requirements.md`, `design.md`.

**Version history:**
- v2.0.0 — 2026-11-17 — Initial task breakdown. Maps W1.1–W1.8 to ordered, independently-testable tasks T1–T11 with explicit dependencies and a Wave 1 completion gate.

---

## Task Sizing Legend

- **S** — Small: a single model/schema/migration/test cluster; < 1 day.
- **M** — Medium: a service or router with tests; 1–2 days.
- **L** — Large: a cross-cutting component (orchestrator/recovery) with extensive tests; 2–3 days.

---

## Tasks

### T1 — Workflow template schema and validation
**Area:** W1.1 (REQ-E1.1). **Size:** M. **Depends on:** nothing (Phase 1 baseline).
- Add `src/devflow_api/schemas/workflow_template.py`: `WorkflowTemplate`, `StepDefinition`, `ToolSelection`, `RetryPolicy`, `TemplateDefaults`, `ApprovalOperation` literals.
- Validate: unique `key`, non-empty `steps`, `depends_on` references exist, acyclic graph, `approvable` ⇒ `protected_operation` set.
- `mypy --strict` passes; unit tests for valid/invalid templates.
- **Done when:** invalid templates raise `INVALID_WORKFLOW_TEMPLATE`; cycle/duplicate/missing-dependency tests green.

### T2 — `WorkflowStepRun` model + migration 008
**Area:** W1.1 (REQ-E1.2, E1.6). **Size:** M. **Depends on:** T1.
- Add `src/devflow_api/models/workflow_step_run.py` (`WorkflowStepRun`, eight-state CHECK, `UNIQUE(run,step_key)`, indexes, `UTCDateTime`).
- Author `alembic/versions/008_add_workflow_execution_engine.py` (chains from verified head `007`): create `workflow_step_runs`; additively alter `approval_requests` (operation, parameters_hash, actor_id, workflow_step_run_id, consumed_at + indexes); **do not change the `approval_requests.status` CHECK**. Reversible `downgrade()`.
- Re-confirm Alembic head before authoring; renumber if Phase 1 advanced.
- **Done when:** `alembic upgrade head` reaches `008`; `alembic downgrade -1` returns to `007`; round-trip test (001→008) green; `mypy --strict` passes.

### T3 — Repositories (step run + approval extension)
**Area:** W1.2/W1.3 (REQ-E1.7, E3.3, E4.6, E4.10). **Size:** M. **Depends on:** T2.
- Add `WorkflowStepRunRepository`: `create_for_run`, `list_for_run`, `transition_cas` (BEGIN IMMEDIATE, CAS with rowcount), `acquire_lease`, `renew_lease`, `release_lease`, `find_stale_running`, `list_interrupted`.
- Extend `ApprovalRequestRepository`: `create_bound` (operation/digest/actor/step), `consume_atomic` (REQ-E3.3 CAS), `expire_pending` (TTL).
- No single-step-delete method (REQ-E3.5.2 guard).
- **Done when:** CAS/lease/consume unit tests green (concurrency, replay, mismatch) with `BEGIN IMMEDIATE`.

### T4 — Executor contract + MockExecutor + registry
**Area:** W1.5 (REQ-E2.8, E5.1–E5.4). **Size:** M. **Depends on:** T1.
- Add `src/devflow_api/executors/base.py` (`Executor` Protocol, `ExecutionContext`, `StepExecutionResult`, `StructuredError`, `ArtifactRef`, `CancellationHandle`, `TimeoutPolicy`, `Capability`, `ExecutorIdentifier`).
- Add `src/devflow_api/executors/registry.py` (`ExecutorRegistry`); register `MockExecutor`.
- Add `src/devflow_api/executors/mock.py` (deterministic, no fs/network/subprocess, test modes: failed/indeterminate/cancelled/sleep/fail_after_attempt).
- AST/import guard test: executors do not import repositories/services/models, do not use `subprocess`/`os.system`/`shell=True`/`os.environ`.
- **Done when:** `registry.list_executors() == ["mock"]`; mock is deterministic; guard test green; `mypy --strict` passes.

### T5 — WorkflowOrchestrator (create, start/resume, dispatch, succeed/fail)
**Area:** W1.2 (REQ-E2.1–E2.3, E1.3–E1.5). **Size:** L. **Depends on:** T3, T4.
- Add `src/devflow_api/orchestration.py` `WorkflowOrchestrator`: `create_run`, `start_orume`, dispatch loop (resolve inputs, `PENDING→READY`, `READY→RUNNING` CAS+lease, call executor outside DB txn, persist result, `RUNNING→SUCCEEDED|FAILED`), dependency re-evaluation, bounded retries (`maybe_retry`), run-status derivation via Phase 1 `WorkflowService.transition_run`.
- Concurrency limit `Settings.RUN_CONCURRENCY` (proposed 1).
- **Done when:** linear/diamond dependency tests green; dispatch CAS conflict test green; timeout/indeterminate/cancelled paths green; run derivation correct.

### T6 — Approval checkpoints in the orchestrator
**Area:** W1.3 (REQ-E2.4–E2.5, E3.1–E3.5). **Size:** M. **Depends on:** T5, T3.
- `approvable` step → `READY→WAITING_APPROVAL` + create bound `ApprovalRequest` (canonical digest, actor from `Settings.LOCAL_OPERATOR_ID`).
- `ApprovalService.resolve` extended: `approved` → step `WAITING_APPROVAL→READY`; `rejected` → step `CANCELLED`, run `cancelled`; `expired` → 409.
- `consume_atomic` invoked when the protected action executes (mock: at the gated step's dispatch).
- TTL expiry sweep for `pending` approvals; `approved` not auto-expired (REQ-E3.4.2).
- **Done when:** replay/mismatch/operation/actor/step-binding tests green; `pending`-only TTL test green; Phase 1 resolve-without-operation test still green.

### T7 — Recovery service + leases
**Area:** W1.4 (REQ-E4.3, E4.8, E4.10). **Size:** M. **Depends on:** T5, T3.
- Add `RecoveryService.recover()`: interrupt stale `RUNNING` (expired lease), `step_interrupted` audit, decide `INTERRUPTED→READY` (safe & under budget) or `INTERRUPTED→FAILED` (unsafe/over-budget), `step_recovery_decided` audit, idempotent.
- Lease heartbeat (`renew_lease`, owner-only); cancelled-run rejects renewal.
- Wire recovery into application startup (`main.py` lifespan) after migrations.
- **Done when:** recovery idempotent; safe retry vs fail decision tests green; lease/heartbeat tests green.

### T8 — Routers (run + steps + audit + start/cancel) and OpenAPI
**Area:** W1.7 (REQ-E7.1–E7.6, E7.8). **Size:** M. **Depends on:** T5, T6.
- Extend `routers/workflows.py` and `routers/workflows.py` run routes; add `POST .../start`, `POST .../cancel`, `GET .../steps`, `GET .../steps/{step_id}`, `GET .../audit`.
- Extend `WorkflowRunResponse` with `steps` (default `[]`); preserve `approvals`/`pending_approvals` (W1.5.4).
- Extend `routers/approvals.py` resolve (binding verified on consume).
- Regenerate `docs/openapi.json`; no `/merge` path.
- **Done when:** API validation tests green (422/409/200); OpenAPI includes new paths; Phase 1 endpoints unchanged.

### T9 — Streamlit minimal UI
**Area:** W1.7 (REQ-E7.7). **Size:** M. **Depends on:** T8.
- Extend `src/devflow_ui/pages/6_Workflows.py`: run + step list, Start/Resume, Cancel, approval affordance, "Backend unavailable" notice.
- `AppTest` with mocked `APIClient`; no fabricated data; `mypy --strict` passes.
- **Done when:** `AppTest` renders run+steps; buttons call correct endpoints; backend-unavailable notice shown.

### T10 — Test suite (Wave 1)
**Area:** W1.8 (REQ-E8.1–E8.3). **Size:** L. **Depends on:** T1–T9.
- Implement all named tests in REQ-E8.1 (state transitions, dependencies, approvals, concurrency, recovery, cancellation, timeouts, idempotency, SQLite rollback, audit, API, mock executor, backward compatibility, security negatives, migration round-trip).
- Add the executor AST/import guard test; the no-single-step-delete guard test; the append-only audit test.
- **Done when:** `ruff check .`, `mypy --strict src/`, `pytest --cov=src --cov-branch --cov-fail-under=80` all exit 0; all named tests green; Phase 0/1 tests green.

### T11 — Wave 1 readiness report + final verification
**Area:** W1.8 / reporting. **Size:** S. **Depends on:** T10.
- Run full quality gates on `feature/phase2-wave1-workflow-execution-engine`.
- Update `docs/reports/phase2-wave1-spec-readiness.md` with implementation results (this is the spec readiness report authored in the spec task; the implementation updates it with verification evidence).
- **Done when:** all gates green; readiness report updated; branch ready for PR (do NOT push/merge per task constraints — that is a later, separately-approved step).

---

## Task Dependency Graph

```
Phase 1 baseline (2d077ec)
    │
    ├── T1 ──┬── T2 ── T3 ──┬── T5 ──┬── T6 ──┐
    │        │              │        │        │
    │        └── T4 ────────┘        T7      T8 ── T9 ──┐
    │                                   │             │
    └─────────────────────────────────────────────── T10 ── T11
```

**Key dependencies:**
- T2 (model+migration) depends on T1 (template schema).
- T3 (repositories) depends on T2.
- T4 (executor) depends on T1 (tool selection types).
- T5 (orchestrator) depends on T3 + T4.
- T6 (approval checkpoints) depends on T5 + T3.
- T7 (recovery) depends on T5 + T3.
- T8 (routers) depends on T5 + T6.
- T9 (Streamlit) depends on T8.
- T10 (tests) depends on T1–T9.
- T11 (readiness) depends on T10.

**Critical path:** T1 → T2 → T3 → T5 → T6 → T8 → T10 → T11.

---

## Wave 1 Completion Gate

- `ruff check .` ✓
- `mypy --strict src/` ✓
- `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` ✓ (exit 0; all REQ-E8.1 named tests green)
- `alembic upgrade head` reaches `008_add_workflow_execution_engine`; `alembic downgrade -1` returns to `007_add_github_confirmations`; round-trip 001→008 ✓
- `docs/openapi.json` regenerated; no `/merge` path; new endpoints present ✓
- Phase 0 and Phase 1 tests pass unmodified ✓
- `workflow_runs.status` and `approval_requests.status` CHECK constraints unchanged from Phase 1 ✓
- No `subprocess`/`os.system`/`shell=True`/`os.environ` in `src/devflow_api/executors/` ✓
- No single-step-delete repository method; audit append-only ✓
- `Settings.LOCAL_OPERATOR_ID` is the sole actor source; `actor_id` never read from request body ✓
- `docs/reports/phase2-wave1-spec-readiness.md` updated with verification evidence ✓

---

## Notes for the Implementer

- **Do not push, create a PR, or merge** during this specification task. The implementation (T1–T11) is a separate, later, separately-approved effort. This task creates specifications only.
- Resolve the open decisions in `design.md` §18 with ChatGPT review before coding.
- Re-confirm the Alembic head immediately before authoring migration 008.
- Keep transactions short; the executor call is NEVER inside a DB transaction (§10).
- Reuse Phase 1 `WorkflowService.transition_run`, `ApprovalService`, `AuditLogRepository`, `RedactSecretsProcessor`, `UTCDateTime`, `BEGIN IMMEDIATE` patterns; do not reimplement them.
