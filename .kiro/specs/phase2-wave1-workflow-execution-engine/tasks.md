# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Tasks

**Version:** 2.1.0
**Status:** Corrected — reconciliation pass (awaiting ChatGPT review)
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9)
**Last Updated:** 2026-11-17
**Companions:** `requirements.md` (v2.1.0), `design.md` (v2.1.0).

**Version history:**
- v2.0.0 — 2026-11-17 — Initial task breakdown (T1–T11).
- v2.1.0 — 2026-11-17 — Reconciliation pass. Fixes the `start_or_resume` task-name typo and the duplicated router phrase; adds template-snapshot (T2), fencing/lease-attempt (T3/T5/T7), approved-authorization validity + re-gating (T2/T3/T6), canonical schema-module placement (T4/T8), legacy-run handling (T5), and the corrected test set (T10). Critical path unchanged; T4 contract types relocated to `schemas/executor.py`.

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
  - Reversible `downgrade()` (drops all of the above; restores prior schema exactly).
- Re-confirm Alembic head before authoring; renumber if Phase 1 advanced.
- **Done when:** `alembic upgrade head` reaches `008`; `alembic downgrade -1` returns to `007`; round-trip 001→008 green; `mypy --strict` passes.

### T3 — Repositories (step run CAS/lease/fence + approval validity/consume)
**Area:** W1.2/W1.3/W1.4 (REQ-E1.7, E3.3, E3.4, E3.6, E4.6, E4.10, E4.11). **Size:** M. **Depends on:** T2.
- Add `WorkflowStepRunRepository`: `create_for_run`, `list_for_run`, `transition_cas` (`BEGIN IMMEDIATE`, CAS with `rowcount`), `dispatch_cas` (READY→RUNNING, increments `attempt`, sets lease + `idempotency_key`), `persist_result_cas` (RUNNING→terminal, fences on `lease_owner`+`attempt`), `renew_lease` (fenced on `lease_owner`+`attempt`), `release_lease`, `find_stale_running`, `list_interrupted`.
- Extend `ApprovalRequestRepository`: `create_bound` (operation/digest/actor/step/`expires_at`), `consume_atomic` (REQ-E3.3 CAS incl. `now < authorization_expires_at`), `expire_pending` (TTL on `expires_at`), `set_authorization_expires_at` (on resolve).
- No single-step-delete method (REQ-E3.5.2 guard).
- **Done when:** CAS/lease/fence/consume unit tests green (concurrency, replay, mismatch, authorization-expiry, stale-completion fence) with `BEGIN IMMEDIATE`.

### T4 — Executor contract + MockExecutor + registry (canonical schema placement)
**Area:** W1.5 (REQ-E2.8, E5.1–E5.4). **Size:** M. **Depends on:** T1.
- Add `src/devflow_api/schemas/executor.py`: `ExecutorIdentifier`, `Capability`, `TimeoutPolicy`, `CancellationHandle`, `ExecutionContext`, `ArtifactRef`, `StructuredError`, `ExecutionMetadata`, `StepExecutionResult` (imports `ToolSelection` from `schemas/workflow_template.py`).
- Add `src/devflow_api/executors/base.py`: `Executor` Protocol (+ `supports(tool_selection)`); imports contract types from `schemas/executor.py`.
- Add `src/devflow_api/executors/registry.py` (`ExecutorRegistry`); register `MockExecutor`.
- Add `src/devflow_api/executors/mock.py` (deterministic, no fs/network/subprocess, test modes: failed/indeterminate/cancelled/sleep/fail_after_attempt).
- Mandatory AST/import guard test: executors do not import repositories/services/models; do not use `subprocess`/`os.system`/`shell=True`/`os.environ`; `schemas/*` do not import `executors`.
- **Done when:** `registry.list_executors() == ["mock"]`; mock is deterministic; guard tests green; `mypy --strict` passes.

### T5 — WorkflowOrchestrator (create, start/resume, dispatch, succeed/fail/retry, cancel)
**Area:** W1.2 (REQ-E2.1–E2.3, E2.6–E2.9, E1.3–E1.5, E4.4, E4.6, E4.7, E4.11). **Size:** L. **Depends on:** T3, T4.
- Add `src/devflow_api/orchestration.py` `WorkflowOrchestrator`: `create_run` (legacy `NULL`-template run vs. templated run + immutable snapshot; atomic), `start_or_resume` (pending→running via `WorkflowService.transition_run`; resolve inputs `PENDING→READY`/`PENDING→FAILED`; gate `READY→WAITING_APPROVAL`; pre-dispatch `READY→FAILED` checks; dispatch `READY→RUNNING` CAS + lease + `attempt` increment; executor call outside DB txn; fenced `persist_result_cas`; retry `RUNNING→READY` (transient); terminal `RUNNING→FAILED`), `cancel`, `on_approval_resolved`.
- Run transitions via Phase 1 services per §5.8 (`transition_run` for pending→running/running→completed/failed; approval service for waiting_approval; `run_repo.transition_status` for cancel). Run terminal derivation only when all steps terminal (§3.4).
- Concurrency limit `Settings.RUN_CONCURRENCY` (default 1).
- **Done when:** linear/diamond dependency tests green; dispatch CAS conflict green; pre-dispatch `READY→FAILED` tests green; retry-as-transient (`RUNNING→READY`, never `FAILED`) green; timeout→`FAILED`/`READY` (not `INTERRUPTED`) green; fenced stale-completion discarded green; run terminal-derivation tests green; legacy-run vacuous-completion green.

### T6 — Approval checkpoints (binding, validity, re-gating, consumption)
**Area:** W1.3 (REQ-E2.4–E2.5, E3.1–E3.6, E4.11). **Size:** M. **Depends on:** T5, T3.
- Add `ApprovalService.request_bound_approval` (new; run running→waiting_approval + bound `ApprovalRequest` with `expires_at` + step `READY→WAITING_APPROVAL` + audit).
- Extend `ApprovalService.resolve` additively: `pending` (409 `APPROVAL_ALREADY_RESOLVED` if resolved; 409 `APPROVAL_EXPIRED` if past `expires_at`); on `approved` set `authorization_expires_at = resolved_at + APPROVAL_AUTHORIZATION_VALIDITY_SECONDS` + step `WAITING_APPROVAL→READY` (Phase 2 gate only); on `rejected` step `→ CANCELLED`; run transitions as Phase 1. Phase 1 approvals (`workflow_step_run_id IS NULL`) resolve exactly as Phase 1.
- `consume_atomic` invoked only by the dispatch owning the current lease (after the fenced persist CAS); refused after authorization expiry or run cancel.
- Re-gating: a `READY` approvable step with no consumable approval (none approved, or approved-but-expired, or consumed) transitions `READY→WAITING_APPROVAL` with a fresh approval.
- Pending-TTL sweep (`expires_at`) sets `expired`; approved not expired by the pending sweep.
- **Done when:** replay/mismatch/operation/actor/step-binding tests green; authorization-expiry + re-gating tests green; consume-after-cancel refused green; Phase 1 resolve-without-operation test still green.

### T7 — Recovery service + leases (auto-reconcile, no auto-dispatch)
**Area:** W1.4 (REQ-E4.3, E4.8, E4.10, E4.11). **Size:** M. **Depends on:** T5, T3.
- Add `RecoveryService.recover()`: interrupt stale `RUNNING` (expired lease) via fenced CAS → `INTERRUPTED` + `step_interrupted` audit; decide `INTERRUPTED→READY` (safe + `attempt < max_attempts`) or `INTERRUPTED→FAILED` (otherwise) + `step_recovery_decided` audit; idempotent; re-derive runs; **do NOT dispatch** (explicit `start_or_resume` resumes).
- Lease heartbeat (`renew_lease`, fenced on `lease_owner`+`attempt`); cancelled-run rejects renewal.
- Wire recovery into application startup (`main.py` lifespan) after migrations.
- **Done when:** recovery idempotent; safe-retry vs fail decision tests green; no-auto-dispatch test green; lease/heartbeat tests green; fenced interrupt test green.

### T8 — Routers (run + steps + audit + start/cancel) and OpenAPI
**Area:** W1.7 (REQ-E7.1–E7.6, E7.8). **Size:** M. **Depends on:** T5, T6.
- Extend the run routes in `src/devflow_api/routers/workflows.py` (`POST /workflows/{id}/runs` → orchestrator.create_run, incl. legacy-run path); add `POST /workflow-runs/{run_id}/start`, `POST /workflow-runs/{run_id}/cancel`, `GET /workflow-runs/{run_id}/steps`, `GET /workflow-runs/{run_id}/steps/{step_id}`, `GET /workflow-runs/{run_id}/audit`.
- Extend `WorkflowRunResponse` with `steps` (default `[]`); preserve `approvals`/`pending_approvals` (W1.5.4).
- Extend `routers/approvals.py` resolve (binding/validity verified at consume; 409 `APPROVAL_EXPIRED` for `pending` past `expires_at`).
- Regenerate `docs/openapi.json`; no `/merge` path.
- **Done when:** API validation tests green (422/409/200, incl. legacy-run 201); OpenAPI includes new paths; Phase 1 endpoints unchanged.

### T9 — Streamlit minimal UI
**Area:** W1.7 (REQ-E7.7). **Size:** M. **Depends on:** T8.
- Extend `src/devflow_ui/pages/6_Workflows.py`: run + step list, Start/Resume, Cancel, approval affordance, "Backend unavailable" notice.
- `AppTest` with mocked `APIClient`; no fabricated data; `mypy --strict` passes.
- **Done when:** `AppTest` renders run+steps; buttons call correct endpoints; backend-unavailable notice shown.

### T10 — Test suite (Wave 1, corrected)
**Area:** W1.8 (REQ-E8.1–E8.3). **Size:** L. **Depends on:** T1–T9.
- Implement all named tests in REQ-E8.1, including the v2.1.0 additions: pre-dispatch `READY→FAILED` and `PENDING→FAILED`; retry-as-transient (`RUNNING→READY`, never `FAILED`) and attempt-budget; timeout vs process-death; recovery no-auto-dispatch; lease/attempt fencing and stale-completion discard (incl. cannot-consume); approved-authorization validity + re-gating + consume-after-cancel; run terminal derivation with independent steps; template snapshot immutability + legacy run; schema layering (`schemas` not importing `executors`); Phase 1 backward-compat (legacy run pending, service unchanged, constraints unchanged); migration 008 round-trip incl. run snapshot columns.
- Add the executor AST/import guard test; the no-single-step-delete guard test; the append-only audit test.
- **Done when:** `ruff check .`, `mypy --strict src/`, `pytest --cov=src --cov-branch --cov-fail-under=80` all exit 0; all named tests green; Phase 0/1 tests green.

### T11 — Wave 1 readiness report + final verification
**Area:** W1.8 / reporting. **Size:** S. **Depends on:** T10.
- Run full quality gates on `feature/phase2-wave1-workflow-execution-engine`.
- Update `docs/reports/phase2-wave1-spec-readiness.md` with implementation verification evidence (the spec readiness report is authored in the spec task; the implementation updates it).
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
- T4 (executor + contract schemas) depends on T1 (tool selection types).
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
- Phase 0 and Phase 1 tests pass unmodified ✓ (legacy `NULL`-template runs preserved; `WorkflowService.create_run` unchanged)
- `workflow_runs.status` and `approval_requests.status` CHECK constraints unchanged from Phase 1 ✓
- No `subprocess`/`os.system`/`shell=True`/`os.environ` in `src/devflow_api/executors/` ✓ (mandatory guard)
- No `schemas/*` module imports `devflow_api.executors` ✓ (layering guard)
- No single-step-delete repository method; audit append-only ✓
- `Settings.LOCAL_OPERATOR_ID` is the sole actor source; `actor_id` never read from request body ✓
- Post-dispatch transitions fence on `lease_owner` + `attempt` ✓
- `docs/reports/phase2-wave1-spec-readiness.md` updated with verification evidence ✓

---

## Notes for the Implementer

- **Do not push, create a PR, or merge** during this specification task. The implementation (T1–T11) is a separate, later, separately-approved effort. This task creates specifications only.
- Resolve the remaining open items in `design.md` §18 with ChatGPT review before coding.
- Re-confirm the Alembic head immediately before authoring migration 008.
- Keep transactions short; the executor call is NEVER inside a DB transaction (§10); post-dispatch CAS fences on `lease_owner` + `attempt`.
- Retries are transient `RUNNING → READY` (never `FAILED`); `attempt` increments on dispatch only.
- Reuse Phase 1 `WorkflowService.transition_run` (pending→running, running→completed/failed), `ApprovalService` (waiting_approval), `run_repo.transition_status` (cancel), `AuditLogRepository`, `RedactSecretsProcessor`, `UTCDateTime`, `BEGIN IMMEDIATE` patterns; do not reimplement them.
- Legacy `NULL`/empty-template runs MUST be preserved (201 pending, zero steps) so Phase 1 tests pass unmodified.
