# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Tasks

**Version:** 2.1.1
**Status:** Final corrections (awaiting ChatGPT approval)
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9)
**Last Updated:** 2026-11-17
**Companions:** `requirements.md` (v2.1.1), `design.md` (v2.1.1).

**Version history:**
- v2.0.0 — 2026-11-17 — Initial task breakdown (T1–T11).
- v2.1.0 — 2026-11-17 — Reconciliation pass (12 findings + Phase 1 compatibility).
- v2.1.1 — 2026-11-17 — Final corrections (two findings). **(F14)** T3/T5/T6 updated: approval consumed atomically with lease acquisition **before** the protected executor runs (`dispatch_protected_txn`), executor outside the DB txn, failed consume rolls back (unexecuted, re-gate), consumed approvals never restored, protected-op retries re-gate for fresh authorization. **(F15)** T5/T7 updated: deterministic failure-stop settle policy (`settle_to_failed`) — no new dispatch after failure-stop, in-flight steps finish (retry suppressed), all remaining non-terminal non-running steps settled to `FAILED` (`skipped`) via existing transitions (no ninth status), pending approvals on settled `WAITING_APPROVAL` steps expired, run → `failed` only after all settled. T10 adds the consume-before-execute, failure-stop, no-restore, and retry-suppression tests. Critical path unchanged.

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

### T2 — `WorkflowStepRun` model + migration 008 (incl. snapshot + approval validity columns)
**Area:** W1.1 (REQ-E1.2, E1.6, E1.8, E3.1, E3.4, E3.6). **Size:** M. **Depends on:** T1.
- Add `src/devflow_api/models/workflow_step_run.py` (`WorkflowStepRun`, eight-state CHECK, `UNIQUE(run,step_key)`, indexes, `UTCDateTime`, `attempt` default 0, nullable `idempotency_key`).
- Author `alembic/versions/008_add_workflow_execution_engine.py` (chains from verified head `007`):
  - CREATE `workflow_step_runs`.
  - ALTER `approval_requests` ADD: `operation`, `parameters_hash`, `actor_id`, `workflow_step_run_id` (ON DELETE SET NULL), `consumed_at`, `expires_at`, `authorization_expires_at` + indexes. **Do NOT change the `approval_requests.status` CHECK.**
  - ALTER `workflow_runs` ADD: `template_snapshot_json`, `template_version`, `template_hash` + index. **Do NOT change the `workflow_runs.status` CHECK.**
  - Reversible `downgrade()`.
- Re-confirm Alembic head before authoring; renumber if Phase 1 advanced.
- **Done when:** `alembic upgrade head` reaches `008`; `alembic downgrade -1` returns to `007`; round-trip 001→008 green; `mypy --strict` passes.

### T3 — Repositories (step run CAS/lease/fence + pre-execution consume + settle)
**Area:** W1.2/W1.3/W1.4 (REQ-E1.7, E3.3, E3.4, E3.6, E4.6, E4.10, E4.11, E4.12). **Size:** M. **Depends on:** T2.
- Add `WorkflowStepRunRepository`: `create_for_run`, `list_for_run`, `transition_cas` (`BEGIN IMMEDIATE`, CAS with `rowcount`), `dispatch_cas` (READY→RUNNING, increments `attempt`, sets lease + `idempotency_key`), `dispatch_protected_txn` (one transaction: lease CAS **AND** `consume_atomic`; on consume failure rollback both — step stays READY), `persist_result_cas` (RUNNING→terminal, fences on `lease_owner`+`attempt`), `renew_lease` (fenced), `release_lease`, `find_stale_running`, `list_interrupted`, `settle_to_failed` (failure-stop settle: PENDING/READY/WAITING_APPROVAL/INTERRUPTED → FAILED `skipped` via guarded CAS per state).
- Extend `ApprovalRequestRepository`: `create_bound` (operation/digest/actor/step/`expires_at`), `consume_atomic` (REQ-E3.3 CAS incl. `now < authorization_expires_at`; all seven bindings), `expire_pending` (TTL on `expires_at`; also expire `pending` approvals bound to settled `WAITING_APPROVAL` steps), `set_authorization_expires_at` (on resolve).
- No single-step-delete method (REQ-E3.5.2 guard). No code path sets `consumed_at` back to `NULL` (no-restore invariant; guard test).
- **Done when:** CAS/lease/fence/consume-settle unit tests green (concurrency, replay, all seven consume-validation rejections, authorization-expiry, stale-completion fence, atomic rollback on consume failure, no-restore) with `BEGIN IMMEDIATE`.

### T4 — Executor contract + MockExecutor + registry (canonical schema placement)
**Area:** W1.5 (REQ-E2.8, E5.1–E5.4). **Size:** M. **Depends on:** T1.
- Add `src/devflow_api/schemas/executor.py`: `ExecutorIdentifier`, `Capability`, `TimeoutPolicy`, `CancellationHandle`, `ExecutionContext`, `ArtifactRef`, `StructuredError` (category incl. `skipped`), `ExecutionMetadata`, `StepExecutionResult`.
- Add `src/devflow_api/executors/base.py`: `Executor` Protocol (+ `supports(tool_selection)`); imports contract types from `schemas/executor.py`.
- Add `src/devflow_api/executors/registry.py` (`ExecutorRegistry`); register `MockExecutor`.
- Add `src/devflow_api/executors/mock.py` (deterministic, no fs/network/subprocess, test modes: failed/indeterminate/cancelled/sleep/fail_after_attempt).
- Mandatory AST/import guard test: executors do not import repositories/services/models; do not use `subprocess`/`os.system`/`shell=True`/`os.environ`; `schemas/*` do not import `executors`.
- **Done when:** `registry.list_executors() == ["mock"]`; mock is deterministic; guard tests green; `mypy --strict` passes.

### T5 — WorkflowOrchestrator (create, start/resume, dispatch+consume, failure-stop, retry, cancel)
**Area:** W1.2 (REQ-E2.1–E2.3, E2.6–E2.9, E1.3–E1.5, E4.4, E4.6, E4.7, E4.11, E4.12). **Size:** L. **Depends on:** T3, T4.
- Add `src/devflow_api/orchestration.py` `WorkflowOrchestrator`: `create_run` (legacy `NULL`-template vs. templated + immutable snapshot; atomic), `start_or_resume` (pending→running via `WorkflowService.transition_run`; resolve inputs `PENDING→READY`/`PENDING→FAILED`; gate `READY→WAITING_APPROVAL`; pre-dispatch `READY→FAILED` checks; **dispatch** non-approvable `READY→RUNNING` CAS + lease + `attempt`; **dispatch_protected** atomic lease+consume BEFORE execute, executor outside DB txn, fenced `persist_result_cas`; **failure-stop** `engage_failure_stop`/`settle_to_failed`: no new dispatch, in-flight finish, settle remaining non-terminal non-running steps to `FAILED` `skipped`, expire pending approvals on settled `WAITING_APPROVAL` steps, run→`failed` only after all settled; **retry** `maybe_retry`: `RUNNING→READY` (non-approvable) / `RUNNING→WAITING_APPROVAL` (approvable, fresh authz) / `RUNNING→FAILED` (terminal or failure-stop retry-suppression)), `cancel`, `on_approval_resolved`.
- Run transitions via Phase 1 services per §5.8. Run terminal derivation only when all steps terminal (§3.4).
- Concurrency limit `Settings.RUN_CONCURRENCY` (default 1).
- **Done when:** linear/diamond dependency tests green; dispatch CAS conflict green; pre-dispatch `READY→FAILED` green; **consume-before-execute** (`test_protected_executor_not_invoked_until_approval_consumed`, atomic rollback on consume failure) green; retry-as-transient (non-approvable `RUNNING→READY`, approvable `RUNNING→WAITING_APPROVAL`, never `FAILED`) green; retry-suppression under failure-stop green; **failure-stop settle** (linear/diamond/independent-in-flight, no-new-dispatch, `WAITING_APPROVAL` settle + approval expiry, run→failed only after all settled, `skipped` category, no ninth status) green; no-restore-on-cancel/timeout/indeterminate green; timeout→`FAILED`/`READY` (not `INTERRUPTED`) green; fenced stale-completion discarded green; legacy-run vacuous-completion green.

### T6 — Approval checkpoints (binding, validity, pre-execution consumption, re-gating, no-restore)
**Area:** W1.3 (REQ-E2.4–E2.5, E3.1–E3.7, E4.11). **Size:** M. **Depends on:** T5, T3.
- Add `ApprovalService.request_bound_approval` (new; run running→waiting_approval + bound `ApprovalRequest` with `expires_at` + step `READY→WAITING_APPROVAL` + audit).
- Extend `ApprovalService.resolve` additively: `pending` (409 `APPROVAL_ALREADY_RESOLVED` if resolved; 409 `APPROVAL_EXPIRED` if past `expires_at`); on `approved` set `authorization_expires_at` + step `WAITING_APPROVAL→READY` (Phase 2 gate only); on `rejected` step `→ CANCELLED`; run transitions as Phase 1. Phase 1 approvals resolve exactly as Phase 1.
- **Consume before execute:** `consume_atomic` is invoked inside `dispatch_protected_txn` (T3) — atomically with lease acquisition, BEFORE the executor runs; on `rowcount == 0` the dispatch rolls back (step unexecuted) and the orchestrator re-gates.
- **Re-gating:** a `READY` approvable step with no consumable approval (none / expired / consumed / failed-consume) transitions `READY→WAITING_APPROVAL` with a fresh approval.
- **No restore:** `consumed_at` never set back to `NULL`; cancellation/failure/timeout/indeterminate never restore; protected-op retry re-gates (fresh authorization), not reuses the consumed approval.
- Pending-TTL sweep (`expires_at`) sets `expired`; approved not expired by the pending sweep (governed by `authorization_expires_at`).
- **Done when:** the seven `test_consume_validation_rejects_*` green; `test_concurrent_consume_only_one_dispatch_proceeds` green; the four `test_consumed_approval_not_restored_on_*` green; replay/mismatch/operation/actor/step-binding tests green; authorization-expiry + re-gating (incl. consume-failure re-gate) green; Phase 1 resolve-without-operation test still green.

### T7 — Recovery service + leases (auto-reconcile, no auto-dispatch, failure-stop aware)
**Area:** W1.4 (REQ-E4.3, E4.8, E4.10, E4.11, E4.12). **Size:** M. **Depends on:** T5, T3.
- Add `RecoveryService.recover()`: interrupt stale `RUNNING` (expired lease) via fenced CAS → `INTERRUPTED` + `step_interrupted` audit; decide `INTERRUPTED→READY` (safe + `attempt < max_attempts` AND run not in failure-stop) or `INTERRUPTED→FAILED` (otherwise, incl. failure-stop → `skipped`) + `step_recovery_decided` audit; idempotent; re-derive runs; **do NOT dispatch** (explicit `start_or_resume` resumes).
- Lease heartbeat (`renew_lease`, fenced on `lease_owner`+`attempt`); cancelled-run rejects renewal.
- Wire recovery into application startup (`main.py` lifespan) after migrations.
- **Done when:** recovery idempotent; safe-retry vs fail decision tests green; no-auto-dispatch green; lease/heartbeat green; fenced interrupt green; `test_recovery_settles_interrupted_when_run_in_failure_stop` green.

### T8 — Routers (run + steps + audit + start/cancel) and OpenAPI
**Area:** W1.7 (REQ-E7.1–E7.6, E7.8). **Size:** M. **Depends on:** T5, T6.
- Extend the run routes in `src/devflow_api/routers/workflows.py` (`POST /workflows/{id}/runs` → orchestrator.create_run, incl. legacy-run path); add `POST /workflow-runs/{run_id}/start`, `POST /workflow-runs/{run_id}/cancel`, `GET /workflow-runs/{run_id}/steps`, `GET /workflow-runs/{run_id}/steps/{step_id}`, `GET /workflow-runs/{run_id}/audit`.
- Extend `WorkflowRunResponse` with `steps` (default `[]`); preserve `approvals`/`pending_approvals` (W1.5.4).
- Extend `routers/approvals.py` resolve (binding/validity verified at pre-execution consume; 409 `APPROVAL_EXPIRED` for `pending` past `expires_at`).
- Regenerate `docs/openapi.json`; no `/merge` path.
- **Done when:** API validation tests green (422/409/200, incl. legacy-run 201); OpenAPI includes new paths; Phase 1 endpoints unchanged.

### T9 — Streamlit minimal UI
**Area:** W1.7 (REQ-E7.7). **Size:** M. **Depends on:** T8.
- Extend `src/devflow_ui/pages/6_Workflows.py`: run + step list, Start/Resume, Cancel, approval affordance, "Backend unavailable" notice.
- `AppTest` with mocked `APIClient`; no fabricated data; `mypy --strict` passes.
- **Done when:** `AppTest` renders run+steps; buttons call correct endpoints; backend-unavailable notice shown.

### T10 — Test suite (Wave 1, corrected to v2.1.1)
**Area:** W1.8 (REQ-E8.1–E8.3). **Size:** L. **Depends on:** T1–T9.
- Implement all named tests in REQ-E8.1, including the v2.1.1 additions:
  - **Pre-execution consumption (F14):** `test_protected_executor_not_invoked_until_approval_consumed`, `test_consume_and_lease_acquired_in_one_transaction`, `test_failed_consume_leaves_step_unexecuted_and_re_gates`, the seven `test_consume_validation_rejects_*`, `test_concurrent_consume_only_one_dispatch_proceeds`, `test_dispatch_and_consume_atomic_rollback_on_consume_failure`, the four `test_consumed_approval_not_restored_on_*`.
  - **Failure-stop settle (F15):** `test_failed_linear_workflow_settles_blocked_steps`, `test_failed_diamond_dependency_settles_blocked_step`, `test_independent_in_flight_step_finishes_before_run_failed`, `test_no_new_dispatch_after_failure_stop`, `test_waiting_approval_step_settled_and_approval_expired_on_run_failure`, `test_run_reaches_failed_only_after_all_steps_settled`, `test_settle_uses_skipped_category_no_ninth_status`.
  - **Retry:** `test_retryable_failure_approvable_re_gates_to_waiting_approval`, `test_retry_suppressed_under_failure_stop`, `test_cancel_does_not_restore_consumed_approval`, `test_timeout_does_not_restore_consumed_approval_for_approvable`, `test_recovery_settles_interrupted_when_run_in_failure_stop`.
  - Plus all v2.1.0 tests (pre-dispatch `READY→FAILED`/`PENDING→FAILED`; retry-as-transient; timeout vs process-death; recovery no-auto-dispatch; lease/attempt fencing + stale-completion cannot-consume; approved-authorization validity + re-gating; run terminal derivation; template snapshot; schema layering; Phase 1 backward-compat; migration 008 round-trip).
- Add the executor AST/import guard test; the no-single-step-delete guard test; the append-only audit test; the no-restore (`consumed_at` never reset) guard test.
- **Done when:** `ruff check .`, `mypy --strict src/`, `pytest --cov=src --cov-branch --cov-fail-under=80` all exit 0; all named tests green; Phase 0/1 tests green.

### T11 — Wave 1 readiness report + final verification
**Area:** W1.8 / reporting. **Size:** S. **Depends on:** T10.
- Run full quality gates on `feature/phase2-wave1-workflow-execution-engine`.
- Update `docs/reports/phase2-wave1-spec-readiness.md` with implementation verification evidence.
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
- T2 (model+migration) depends on T1.
- T3 (repositories, incl. `dispatch_protected_txn` + `settle_to_failed`) depends on T2.
- T4 (executor + contract schemas) depends on T1.
- T5 (orchestrator: dispatch+consume, failure-stop, retry) depends on T3 + T4.
- T6 (approval checkpoints, pre-execution consume, re-gating, no-restore) depends on T5 + T3.
- T7 (recovery, failure-stop aware) depends on T5 + T3.
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
- Phase 0 and Phase 1 tests pass unmodified ✓ (legacy `NULL`-template runs preserved; `WorkflowService.create_run` unchanged)
- `workflow_runs.status` and `approval_requests.status` CHECK constraints unchanged from Phase 1 ✓
- No `subprocess`/`os.system`/`shell=True`/`os.environ` in `src/devflow_api/executors/` ✓ (mandatory guard)
- No `schemas/*` module imports `devflow_api.executors` ✓ (layering guard)
- No single-step-delete repository method; audit append-only ✓
- `Settings.LOCAL_OPERATOR_ID` is the sole actor source; `actor_id` never read from request body ✓
- Post-dispatch transitions fence on `lease_owner` + `attempt` ✓
- **Protected executors are not invoked before their approval is atomically consumed** (lease+consume in one transaction; executor outside the txn) ✓
- **`consumed_at` is never set back to `NULL`** (no-restore guard) ✓
- **Failure-stop settles all remaining non-terminal non-running steps to `FAILED` (`skipped`); no ninth step status** ✓
- `docs/reports/phase2-wave1-spec-readiness.md` updated with verification evidence ✓

---

## Notes for the Implementer

- **Do not push, create a PR, or merge** during this specification task. The implementation (T1–T11) is a separate, later, separately-approved effort.
- Resolve the remaining open items in `design.md` §18 with ChatGPT approval before coding.
- Re-confirm the Alembic head immediately before authoring migration 008.
- Keep transactions short; the executor call is NEVER inside a DB transaction (§10); post-dispatch CAS fences on `lease_owner` + `attempt`.
- For an approvable step, the lease CAS and the approval consume are ONE `BEGIN IMMEDIATE` transaction; the executor runs only after it commits. A failed consume rolls back (step unexecuted) and re-gates.
- Retries are transient `RUNNING → READY` (non-approvable) or `RUNNING → WAITING_APPROVAL` (approvable, fresh authorization), never via `FAILED`; `attempt` increments on dispatch only.
- Failure-stop: no new dispatch, in-flight finish (retry suppressed → `FAILED`), settle remaining non-terminal non-running steps to `FAILED` (`skipped`), run → `failed` only after all settled.
- Consumed approvals are never restored (no code path sets `consumed_at` back to `NULL`).
- Reuse Phase 1 `WorkflowService.transition_run` (pending→running, running→completed/failed), `ApprovalService` (waiting_approval), `run_repo.transition_status` (cancel), `AuditLogRepository`, `RedactSecretsProcessor`, `UTCDateTime`, `BEGIN IMMEDIATE` patterns.
- Legacy `NULL`/empty-template runs MUST be preserved (201 pending, zero steps) so Phase 1 tests pass unmodified.
