# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Tasks

**Version:** 2.1.2
**Status:** Codex blocker resolution — awaiting ChatGPT review
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9)
**Last Updated:** 2026-11-18
**Companions:** `requirements.md` (v2.1.2), `design.md` (v2.1.2).

**Version history:**
- v2.0.0 — 2026-11-17 — Initial task breakdown (T1–T11).
- v2.1.0 — 2026-11-17 — Reconciliation pass (12 findings + Phase 1 compatibility).
- v2.1.1 — 2026-11-17 — Final corrections (F14, F15). T3/T5/T6 updated for consume-before-execute; T5/T7 updated for failure-stop settle.
- v2.1.2 — 2026-11-18 — Codex blocker resolution (F16, F17). **T3** adds `expire_and_re_gate` and `derive_and_persist_run_status` to `WorkflowStepRunRepository` / `ApprovalRequestRepository`. **T5** updated: `start_or_resume` calls `derive_and_persist_run_status` after every step state change; multi-gate handling (second gate skips run transition; run stays `waiting_approval`); expiry re-gate from `WAITING_APPROVAL` via `expire_and_re_gate`. **T6** updated: `resolve` uses F16 corrected expiry response order (`APPROVAL_EXPIRED` beats `APPROVAL_ALREADY_RESOLVED` for Phase 2 expired approvals); `request_bound_approval` skips run transition for second+ gates; `expire_and_re_gate` wired into the reconciliation sweep. **T10** adds F16/F17 named tests (approval expiry pre/post-sweep, concurrent gates, run status precedence, derive-idempotency). Critical path unchanged.

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
**Area:** W1.2/W1.3/W1.4 (REQ-E1.7, E2.10, E3.3, E3.4, E3.6, E3.8, E4.6, E4.10, E4.11, E4.12). **Size:** M. **Depends on:** T2.
- Add `WorkflowStepRunRepository`: `create_for_run`, `list_for_run`, `transition_cas` (`BEGIN IMMEDIATE`, CAS with `rowcount`), `dispatch_cas` (READY→RUNNING, increments `attempt`, sets lease + `idempotency_key`), `dispatch_protected_txn` (one transaction: lease CAS **AND** `consume_atomic`; on consume failure rollback both — step stays READY), `persist_result_cas` (RUNNING→terminal, fences on `lease_owner`+`attempt`), `renew_lease` (fenced), `release_lease`, `find_stale_running`, `list_interrupted`, `settle_to_failed` (failure-stop settle: PENDING/READY/WAITING_APPROVAL/INTERRUPTED → FAILED `skipped` via guarded CAS per state).
- Add **`derive_and_persist_run_status(run_id, is_failure_stop, session)`** (REQ-E2.10, F17): reads all step statuses, applies precedence table (§5.9), calls `transition_status` only for the winning target and only if the transition is in `VALID_FROM`; inside `BEGIN IMMEDIATE`; idempotent and concurrent-safe.
- Extend `ApprovalRequestRepository`: `create_bound` (operation/digest/actor/step/`expires_at`), `consume_atomic` (REQ-E3.3 CAS incl. `now < authorization_expires_at`; all seven bindings), `expire_pending` (TTL on `expires_at`; also expire `pending` approvals bound to settled `WAITING_APPROVAL` steps), `set_authorization_expires_at` (on resolve), **`expire_and_re_gate(step_run_id, new_approval_data, run_id, session)`** (REQ-E3.8, F16: atomic expire-old + create-new approval; guarded against cancelled/failure-stop; idempotent post-sweep).
- No single-step-delete method; no code path sets `consumed_at` back to `NULL`.
- **Done when:** CAS/lease/fence/consume-settle/derive/re-gate unit tests green; F16 pre-sweep/post-sweep expiry tests (E3.8.1, E3.8.2) green; F17 derive-precedence tests (E2.10.1–E2.10.5) green; concurrent derive produces consistent state; `BEGIN IMMEDIATE` verified.

### T4 — Executor contract + MockExecutor + registry (canonical schema placement)
**Area:** W1.5 (REQ-E2.8, E5.1–E5.4). **Size:** M. **Depends on:** T1.
- Add `src/devflow_api/schemas/executor.py`: `ExecutorIdentifier`, `Capability`, `TimeoutPolicy`, `CancellationHandle`, `ExecutionContext`, `ArtifactRef`, `StructuredError` (category incl. `skipped`), `ExecutionMetadata`, `StepExecutionResult`.
- Add `src/devflow_api/executors/base.py`: `Executor` Protocol (+ `supports(tool_selection)`); imports contract types from `schemas/executor.py`.
- Add `src/devflow_api/executors/registry.py` (`ExecutorRegistry`); register `MockExecutor`.
- Add `src/devflow_api/executors/mock.py` (deterministic, no fs/network/subprocess, test modes: failed/indeterminate/cancelled/sleep/fail_after_attempt).
- Mandatory AST/import guard test: executors do not import repositories/services/models; do not use `subprocess`/`os.system`/`shell=True`/`os.environ`; `schemas/*` do not import `executors`.
- **Done when:** `registry.list_executors() == ["mock"]`; mock is deterministic; guard tests green; `mypy --strict` passes.

### T5 — WorkflowOrchestrator (create, start/resume, dispatch+consume, failure-stop, retry, cancel, derive-status, expiry-re-gate)
**Area:** W1.2 (REQ-E2.1–E2.3, E2.6–E2.10, E1.3–E1.5, E4.4, E4.6, E4.7, E4.11, E4.12). **Size:** L. **Depends on:** T3, T4.
- Add `src/devflow_api/orchestration.py` `WorkflowOrchestrator`: `create_run` (legacy vs. templated + immutable snapshot; atomic), `start_or_resume`:
  - **Multi-gate handling (F17):** when gating a step and the run is already `waiting_approval`, skip the `running → waiting_approval` run transition; only transition the step `READY→WAITING_APPROVAL`; call `derive_and_persist_run_status` to confirm idempotent `waiting_approval`.
  - **Expiry re-gate (F16):** when `start_or_resume` encounters a `WAITING_APPROVAL` step whose pending approval has `expires_at <= now`, call `expire_and_re_gate` (not a step transition through `READY`); refuse if run cancelled or failure-stop.
  - **All run status changes** go through `derive_and_persist_run_status` (not direct `transition_run` calls, except the initial `pending → running`).
  - Dispatch, failure-stop settle, retry paths unchanged from v2.1.1.
- Run initial start still uses `WorkflowService.transition_run(run_id, "running", actor)` for `pending → running`.
- **Done when:** F17 multi-gate tests green (`test_two_independent_gates_run_stays_waiting_approval`, `test_approve_one_of_two_gates_run_stays_waiting_approval`, `test_approve_both_gates_run_becomes_running`); F16 expiry re-gate from `WAITING_APPROVAL` tests green; derive-idempotency and precedence tests green; all v2.1.1 tests still green.

### T6 — Approval checkpoints (binding, validity, pre-execution consumption, re-gating, no-restore, expiry response)
**Area:** W1.3 (REQ-E2.4–E2.5, E3.1–E3.8, E4.11). **Size:** M. **Depends on:** T5, T3.
- Add `ApprovalService.request_bound_approval` (new): **first gate** issues `run_repo.transition_status(run_id, "waiting_approval", ["running"])`; **subsequent gates** (run already `waiting_approval`) skip the run transition and call `derive_and_persist_run_status` to confirm.
- Extend `ApprovalService.resolve` with **F16 expiry response order**: check Phase 2 `pending` approval past `expires_at` first → 409 `APPROVAL_EXPIRED`; check Phase 2 `expired` approval (`status='expired' AND operation IS NOT NULL`) → 409 `APPROVAL_EXPIRED`; then `APPROVAL_ALREADY_RESOLVED` for all other non-pending cases. Phase 1 approvals (`expires_at IS NULL`) retain original `APPROVAL_ALREADY_RESOLVED` for non-pending. On `approved`: step `WAITING_APPROVAL→READY`; call `derive_and_persist_run_status`; run returns to `running` only if no other `WAITING_APPROVAL` steps remain.
- Wire `expire_and_re_gate` into the approval reconciliation sweep (called by the sweep and by `start_or_resume`).
- Consume-before-execute, no-restore, re-gate from `READY`, TTL sweep — unchanged from v2.1.1.
- **Done when:** F16 expiry tests (`test_approval_expired_pre_sweep_returns_expired_code`, `test_approval_expired_post_sweep_returns_expired_code`, `test_phase1_approval_already_resolved_still_returned_for_expired`); F17 approval resolve triggers correct run status derivation; all v2.1.1 approval tests still green.

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

### T10 — Test suite (Wave 1, corrected to v2.1.2)
**Area:** W1.8 (REQ-E8.1–E8.3). **Size:** L. **Depends on:** T1–T9.
- Implement all named tests in REQ-E8.1, including the v2.1.2 additions:
  - **F16 approval expiry (E3.8.x):** `test_approval_expired_pre_sweep_returns_expired_code`, `test_approval_expired_post_sweep_returns_expired_code`, `test_phase1_approval_already_resolved_still_returned_for_expired`, `test_expire_and_re_gate_pre_sweep_waiting_approval_step`, `test_expire_and_re_gate_post_sweep_waiting_approval_step`, `test_expire_and_re_gate_idempotent`, `test_expire_and_re_gate_refused_when_run_cancelled`, `test_expire_and_re_gate_refused_when_failure_stop_engaged`, `test_concurrent_expire_and_re_gate_produces_valid_state`, `test_old_approval_id_returns_expired_after_re_gate`.
  - **F17 concurrent gates and run status precedence (E2.10.x):** `test_two_independent_gates_run_stays_waiting_approval`, `test_approve_one_of_two_gates_run_stays_waiting_approval`, `test_approve_both_gates_run_becomes_running`, `test_reject_one_gate_cancels_run_regardless_of_other_gate`, `test_executor_fails_while_gate_pending_run_stays_running_until_settled`, `test_derive_run_status_all_succeeded_returns_completed`, `test_derive_run_status_any_waiting_returns_waiting_approval`, `test_derive_run_status_failure_stop_all_terminal_returns_failed`, `test_derive_run_status_failure_stop_inflight_step_stays_running`, `test_derive_run_status_idempotent_on_terminal_run`, `test_derive_run_status_concurrent_calls_produce_consistent_state`, `test_run_status_precedence_failed_beats_waiting_approval`.
  - Plus all v2.1.1 tests (F14/F15 consume-before-execute, failure-stop settle, no-restore, retry-suppression).
- Add all guard tests from previous versions; audit append-only; no-ninth-status.
- **Done when:** `ruff check .`, `mypy --strict src/`, `pytest --cov=src --cov-branch --cov-fail-under=80` all exit 0; all named tests (F14/F15/F16/F17) green; Phase 0/1 tests green.

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
- **`derive_and_persist_run_status` called after all step state changes** (not direct `transition_run` except initial pending→running) ✓
- **F16: `APPROVAL_EXPIRED` returned for both pre-sweep and post-sweep Phase 2 expired approvals** ✓
- **F17: multi-gate runs stay `waiting_approval` until all gates cleared** ✓
- **F16/F17 named tests green** ✓
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
