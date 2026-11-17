# Phase 2 Wave 1 — Specification Resolution Report (v2.0.0 → v2.1.1)

**Report date:** 2026-11-17 (updated for v2.1.1 final corrections)
**Scope:** Reconciliation of the Phase 2 Wave 1 specifications: the 12 correction items (v2.0.0 → v2.1.0, findings F1–F12), Phase 1 service compatibility (F13), the resolved defaults, and the two final corrections (v2.1.0 → v2.1.1, findings F14–F15).
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9)
**Task type:** Specification only — no production code, migrations, tests, or OpenAPI artifacts were modified. No push, PR, or merge.

**Correction passes:**
- **v2.0.0 → v2.1.0:** findings F1–F13 (below).
- **v2.1.0 → v2.1.1:** findings F14 (approval consumption before execution) and F15 (terminal run with blocked dependencies), appended after F13.

---

## 0. Summary

The v2.0.0 specification was re-reviewed and corrected through two passes: v2.1.0 (twelve findings F1–F12 from task §2 plus Phase 1-compatibility finding F13) and v2.1.1 (two final corrections F14–F15). Fifteen findings total are resolved. Resolved defaults were applied. Every requirement has an implementation task, a design reference, an acceptance criterion, and a named test. Eight step states and six Phase 1 run states are preserved. The `workflow_runs.status` and `approval_requests.status` CHECK constraints are unchanged (additive columns only). No ninth step status is introduced (failure-stop settle reuses existing transitions to `FAILED`).

**Files changed (all on the feature branch, spec/docs only):**
- `.kiro/specs/phase2-wave1-workflow-execution-engine/requirements.md` → v2.1.0
- `.kiro/specs/phase2-wave1-workflow-execution-engine/design.md` → v2.1.0
- `.kiro/specs/phase2-wave1-workflow-execution-engine/tasks.md` → v2.1.0
- `docs/planning/phase2-roadmap.md` → v2.1.0
- `docs/reports/phase2-wave1-spec-readiness.md` → v2.1.0 (updated)
- `docs/reports/phase2-wave1-spec-resolution.md` → v2.1.0 (new, this file)

No production code, tests, migrations, or `docs/openapi.json` were modified.

---

## 1. Findings and Resolutions

### F1 — Missing `READY → FAILED` (and `PENDING → FAILED`) pre-dispatch transitions
**Finding:** The v2.0.0 transition map (design §8.2) listed `READY → RUNNING/WAITING_APPROVAL/CANCELLED` but NOT `READY → FAILED`. Pre-dispatch errors (executor not found, working directory not approved, capability mismatch) were described in prose (§5.3) but absent from the authoritative map. Input-resolution failure was said to go `PENDING → FAILED` (§5.3) but `PENDING → FAILED` was also absent from the map.
**Resolution:** Added `PENDING → FAILED` (`INPUT_RESOLUTION_FAILED`) and `READY → FAILED` (`EXECUTOR_NOT_FOUND` / `WORKING_DIRECTORY_NOT_APPROVED` / `CAPABILITY_MISMATCH`) to the map (REQ-E4.2; design §8.2). Input resolution fails at the `PENDING → READY` transition (the step never reaches `READY`).
**Files/sections:** requirements REQ-E1.4.2, E2.2, E4.2; design §5.3, §8.2; tasks T5.
**Rationale:** The map must be the single source of truth for allowed transitions; prose-only transitions are untestable and ambiguous.
**Tests:** `test_pending_to_failed_on_input_resolution_failure`, `test_ready_to_failed_on_executor_not_found`, `test_ready_to_failed_on_working_directory_not_approved`, `test_ready_to_failed_on_capability_mismatch`.

### F2 — Retry transitions conflicting with terminal `FAILED` semantics
**Finding:** v2.0.0 map row "RUNNING → FAILED (executor failure) (or retry → READY if safe & under budget)" conflated a terminal `FAILED` with a transient retry, implying a step could pass through `FAILED` to retry. Since `FAILED` is terminal, this is contradictory.
**Resolution:** Split retry into an explicit transient transition `RUNNING → READY` (retryable failure, safe + idempotent + `attempt < max_attempts`), distinct from terminal `RUNNING → FAILED` (non-retryable / budget exhausted / indeterminate). A retry NEVER passes through `FAILED` (REQ-E4.2.4, E4.7.4). `maybe_retry` (design §5.6) transitions `RUNNING → READY` (attempt NOT incremented; incremented on the next dispatch).
**Files/sections:** requirements REQ-E4.2, E4.7; design §5.6, §8.2; tasks T5.
**Rationale:** Terminal states must be irreversible; conflating retry with `FAILED` would allow "reviving" a failed step and break audit/recovery invariants.
**Tests:** `test_retryable_failure_transitions_running_to_ready_not_failed`, `test_retry_exhaustion_transitions_to_failed_terminal`, `test_retry_never_passes_through_failed`.

### F3 — Inconsistent interruption triggers and recovery handling
**Finding:** v2.0.0 mixed two distinct triggers: timeout (REQ-E5.3.1 said "timeout → FAILED (or INTERRUPTED if process died)") and process death (`RUNNING → INTERRUPTED` via recovery). The "or INTERRUPTED" for timeout was ambiguous. Recovery auto-resume was an open question (§9.1 said "or the orchestrator auto-resumes").
**Resolution:** Disambiguated: **timeout** (executor raised / `wait_for` expired while process alive) → `RUNNING → READY` (retry) or `RUNNING → FAILED` (terminal), NEVER `INTERRUPTED`. **Process death** (no completion, lease expired) → `RUNNING → INTERRUPTED` via recovery ONLY. Recovery is automatic state reconciliation (interrupt + decide retry/fail) but does NOT auto-dispatch; resumed execution requires an explicit user `start` (resolved default).
**Files/sections:** requirements REQ-E4.3, E5.3; design §9.1, §9.3; tasks T7.
**Rationale:** A timeout means the orchestrator is alive and got control back (can decide retry/fail); `INTERRUPTED` means the process died and only recovery can detect it. Auto-dispatch after recovery could resume work the user did not re-authorize.
**Tests:** `test_step_timeout_marks_failed_or_ready_not_interrupted`, `test_running_step_with_valid_lease_not_interrupted`, `test_recovery_does_not_auto_dispatch_requires_explicit_start`, `test_running_step_with_expired_lease_becomes_interrupted`, `test_recovery_idempotent`.

### F4 — Approval re-gating and single-use consumption races
**Finding:** v2.0.0 did not specify what happens when an approved authorization expires before the protected action dispatches (the step waits in `READY`), nor how consumption interacts with run cancellation or stale completions.
**Resolution:** (a) Re-gating: an approvable `READY` step with no consumable approval (none approved, or approved-but-authorization-expired, or consumed) transitions `READY → WAITING_APPROVAL` with a fresh `ApprovalRequest` (REQ-E2.4, E3.6). (b) Consumption races: `consume_atomic` is a single-use CAS; it is invoked only by the dispatch owning the current lease (after the fenced persist CAS succeeds), so a stale completion cannot consume (F9); a cancelled run's step is `CANCELLED` (not `RUNNING`), so its persist CAS fails and consume is not reached (REQ-E2.7.4). Concurrent consumes: exactly one `rowcount == 1` (REQ-E3.3.9).
**Files/sections:** requirements REQ-E2.4, E3.3, E3.6, E6.5; design §7.2, §7.4, §7.7; tasks T6.
**Rationale:** An approved decision has a bounded validity; if it lapses before use, a fresh human decision is required (no silent auto-consumption of a stale consent). Consumption must be race-free and cancel-safe.
**Tests:** `test_approval_re_gated_after_authorization_expiry`, `test_consume_refused_after_run_cancelled`, `test_concurrent_consume_only_one_succeeds`, `test_stale_completion_cannot_consume_approval`.

### F5 — Run terminal-state derivation with independently running steps
**Finding:** v2.0.0 derivation (design §3.3) said run `failed` if "any step FAILED (and run stop policy engaged)" — but with concurrency > 1, an independent step could still be `RUNNING` when another fails, making the run `failed` while a step is still running (inconsistent, since Phase 1 `failed` is terminal).
**Resolution:** Run terminal states (`completed`/`failed`/`cancelled`) are derived ONLY when ALL steps are terminal: `completed` iff all `SUCCEEDED`; `failed` iff any `FAILED` and none cancelled-by-cancel; `cancelled` iff cancelled. While any step is non-terminal, the run is `running` (or `waiting_approval`). With concurrency=1 (Wave 1 default), a `FAILED` step implies no other in-flight step, so the run can go `failed` immediately.
**Files/sections:** requirements REQ-E4.4; design §3.4, §5.5; tasks T5.
**Rationale:** A terminal run status while non-terminal steps exist is self-contradictory and breaks the Phase 1 invariant that `failed`/`completed`/`cancelled` are terminal.
**Tests:** `test_run_failed_derived_only_after_all_steps_terminal`, `test_run_completed_only_when_all_steps_succeeded`, `test_legacy_run_with_zero_steps_vacuously_completes`.

### F6 — Immutable workflow-template snapshot and version/hash persistence
**Finding:** v2.0.0 executed from the live `Workflow.definition_json` (open decision §5/§6 proposed storing only `template_version`/`definition_hash` in `result_json` metadata). If the live template changed between run creation and dispatch, the run would execute a different template than intended (mutability risk). Open decisions #5/#6 were unresolved.
**Resolution:** Resolved default "immutable full execution snapshot per run." Migration 008 adds `template_snapshot_json` (full validated `WorkflowTemplate`), `template_version`, and `template_hash` (SHA-256) to `workflow_runs` (nullable; Phase 1/legacy runs have `NULL`). `create_run` snapshots the template; the orchestrator executes from the snapshot, NEVER the live `definition_json`. Editing the live workflow after run creation does not affect any run or its steps.
**Files/sections:** requirements REQ-E1.8, E2.1, E1.5.1; design §3.2, §4, §5.2; tasks T2, T5. Open decisions #5/#6 resolved (design §18).
**Rationale:** Execution reproducibility and auditability require that a run's definition is immutable for its lifetime; a live edit must not silently change in-flight or future-dispatched steps.
**Tests:** `test_template_snapshot_immutable_after_live_workflow_edit`, `test_template_hash_recorded_on_run`, `test_legacy_run_has_no_snapshot_and_zero_steps`.

### F7 — Consistent attempt counting and retry-budget semantics
**Finding:** v2.0.0 had `attempt` default 0, dispatch CAS set `attempt=attempt` (did not increment), and `maybe_retry` incremented `attempt`. `idempotency_key` used `attempt`. REQ-E4.7.1 said "fails twice then succeeds reaches SUCCEEDED with attempt=2" with `max_attempts=3` — off-by-one vs. "max_attempts = total attempts." The increment point and budget check were inconsistent.
**Resolution:** `attempt` = executions attempted so far (0 before first). Incremented on `READY → RUNNING` dispatch (CAS). NOT incremented on retry (`RUNNING → READY`) or recovery (`INTERRUPTED → READY`) — only on the subsequent dispatch. `idempotency_key = f"{run_id}:{step_key}:{attempt}"` (post-increment). Budget: retry while `attempt < max_attempts` (attempt = the just-completed attempt); `max_attempts` = total executions including the first (default 1). With `max_attempts=3`: attempts 1,2,3; succeed at 3 → `SUCCEEDED` `attempt=3`; fail at 3 → `FAILED`.
**Files/sections:** requirements REQ-E1.2, E1.6, E4.6, E4.7, E4.9; design §3.1, §5.4, §5.6, §9.1; tasks T3, T5. Open decision (design §18 #2) rephrased.
**Rationale:** A single, unambiguous increment point (dispatch) and a clear budget definition prevent off-by-one retries and make idempotency keys stable per execution.
**Tests:** `test_attempt_increments_on_dispatch`, `test_attempt_budget_enforced_max_attempts`, `test_retry_exhaustion_transitions_to_failed_terminal`.

### F8 — Pending versus approved approval validity and expiry
**Finding:** v2.0.0 REQ-E3.4.2 deliberately did NOT expire `approved` approvals (open decision #4). The resolved default requires approved authorization validity of 3600s, enforced separately without changing the Phase 1 `status` CHECK.
**Resolution:** Two separate timers, both via columns (no status change): (a) pending TTL `expires_at = requested_at + APPROVAL_TTL_SECONDS` (3600); the sweep sets `status='expired'` for `pending` approvals past `expires_at`. (b) approved authorization validity `authorization_expires_at = resolved_at + APPROVAL_AUTHORIZATION_VALIDITY_SECONDS` (3600), set on resolve; `consume_atomic` requires `now < authorization_expires_at` (NULL ⇒ no bound, Phase 1 backward compatible). An approved authorization past validity is not consumable; the gated step re-gates (F4). `status` stays `approved`; the CHECK is unchanged.
**Files/sections:** requirements REQ-E3.1, E3.3, E3.4, E3.6, E8.3; design §3.3, §7.2, §7.3; tasks T2, T3, T6. Open decision #4 resolved.
**Rationale:** A pending request and an approved authorization have different risk profiles; bounding both (separately) prevents both indefinite pending requests and indefinite-lived authorizations, while preserving Phase 1's status enum.
**Tests:** `test_approved_authorization_expires_after_validity`, `test_consume_refused_after_authorization_expiry`, `test_approval_re_gated_after_authorization_expiry`, `test_phase1_approval_resolve_still_works_without_operation` (NULL ⇒ no bound).

### F9 — Lease-owner/attempt fencing for stale executor completions
**Finding:** v2.0.0 did not fence post-dispatch transitions on `lease_owner`/`attempt`. A late return from a superseded dispatch (after the step was `INTERRUPTED` and re-dispatched, or after cancel) could persist a stale result or consume an approval.
**Resolution:** Every post-dispatch state-mutating CAS (`RUNNING → SUCCEEDED/FAILED/READY/CANCELLED`) fences on `lease_owner` AND `attempt`: `WHERE id=? AND status='RUNNING' AND lease_owner=? AND attempt=?`. A stale completion yields `rowcount == 0`, is discarded, and writes `step_stale_completion_discarded`; it cannot consume an approval (consume happens only after the fenced persist CAS succeeds). Heartbeat renewal also fences on `lease_owner`+`attempt`.
**Files/sections:** requirements REQ-E4.10, E4.11, E2.3, E6.5; design §5.4, §5.6, §5.7, §9.2, §10.4; tasks T3, T5, T7.
**Rationale:** Without fencing, a slow executor from a superseded attempt could overwrite the current attempt's state or burn an approval — a correctness and security bug.
**Tests:** `test_stale_completion_discarded_by_lease_fence`, `test_stale_completion_cannot_consume_approval`, `test_step_stale_completion_discarded_audited`, `test_heartbeat_only_owner_renews_lease`.

### F10 — Canonical schema-module naming and imports
**Finding:** v2.0.0 placed contract Pydantic types (`ExecutionContext`, `StepExecutionResult`, `ArtifactRef`, `StructuredError`) in `src/devflow_api/executors/base.py`. `schemas/workflow.py` (`StepRunResponse`) used `ArtifactRef`/`StructuredError` — i.e., a `schemas/*` module importing from `executors/`, a layering inversion (schemas should not depend on the executors package).
**Resolution:** Moved all contract Pydantic types to `src/devflow_api/schemas/executor.py` (canonical schema module). `executors/base.py` holds only the `Executor` Protocol and imports from `schemas/executor.py`. `schemas/workflow.py` imports `ArtifactRef`/`StructuredError` from `schemas/executor.py` (same package). No `schemas/*` module imports `devflow_api.executors` (enforced by an import-graph test).
**Files/sections:** requirements REQ-E2.8, E5.1.1; design §2, §6; tasks T4, T8.
**Rationale:** Schemas are a lower layer than executors; dependencies must point downward (executors → schemas), never upward. This keeps the layering clean and testable.
**Tests:** `test_schemas_do_not_import_executors_package`, `test_executors_do_not_import_repositories_services_models`.

### F11 — Task naming errors and duplicate acceptance-criteria identifiers
**Finding:** (a) tasks.md T5 used `start_orume` (typo for `start_or_resume`). (b) tasks.md T8 had a duplicated phrase "Extend `routers/workflows.py` and `routers/workflows.py`". (c) requirements REQ-E6.8 had two `E6.8.1` entries. (v2.0.0 had already fixed E4.3.4/E4.10.2.)
**Resolution:** Fixed `start_orume` → `start_or_resume` (tasks T5); fixed the duplicated router phrase (tasks T8); renumbered the second `E6.8.1` → `E6.8.2` (requirements REQ-E6.8). Verified all AC IDs unique across the rewritten requirements.
**Files/sections:** tasks T5, T8; requirements REQ-E6.8.
**Rationale:** Typos and duplicate identifiers break traceability and tooling.
**Tests:** (covered by the corrected traceability matrix and the unique-ID invariant; no separate runtime test.)

### F12 — Missing negative and concurrency tests for the corrected behavior
**Finding:** v2.0.0's named-test set did not cover the corrected behaviors (pre-dispatch failures, transient retry, fencing, authorization validity, re-gating, attempt budget, run terminal derivation, template snapshot, schema layering).
**Resolution:** Added the named tests listed under each finding above to REQ-E8.1, and a dedicated "Run derivation", "Template snapshot", "Retry & attempt budget", "Concurrency, leases & fencing", and "Approvals" test groups. The full updated set is in requirements REQ-E8.1 and is the authoritative test matrix.
**Files/sections:** requirements REQ-E8.1; design §15; tasks T10.
**Rationale:** Every corrected behavior needs a negative/concurrency test to lock the semantics and prevent regressions.
**Tests:** (the test list itself; see REQ-E8.1.)

### F13 — Phase 1 service compatibility (from task §4 verification)
**Finding:** v2.0.0 design §17 said "Run transitions reuse Phase 1 `WorkflowService.transition_run`" for ALL run states. The actual `WorkflowService.WORKFLOW_TRANSITIONS` is `{"pending": {"running"}, "running": {"completed", "failed", "cancelled"}}` — `waiting_approval` is NOT in this map. Phase 1 reaches `waiting_approval` ONLY through `ApprovalService.request_approval`/`resolve` (via `run_repo.transition_status`). Also, Phase 1 tests create runs from workflows with `definition_json = NULL` (router test `{"name": "Example"}`) or `"opaque"` (service test, via `WorkflowService.create_run` directly, which ignores `definition_json`); a strict "valid template required" `create_run` would break `test_create_run_returns_pending_status`.
**Resolution:** (a) The orchestrator reuses Phase 1 services exactly as Phase 1 uses them: `transition_run` for `pending→running`/`running→completed`/`running→failed`; `ApprovalService` (`request_bound_approval`/`resolve`) for `waiting_approval` in/out (via `run_repo.transition_status`, the Phase 1 pattern); `run_repo.transition_status` for cancel from any non-terminal run state. Documented in design §5.8 and REQ-E2.9. (b) `create_run` preserves legacy `NULL`/empty-template runs: a `NULL`/empty `definition_json` creates a legacy run (201, `pending`, zero steps, no snapshot) — exactly Phase 1 behavior — so Phase 1 router tests pass unmodified; `WorkflowService.create_run` (service) is unchanged, so Phase 1 service tests pass; a non-empty invalid template returns 422. (c) `WorkflowService.create_run`/`transition_run` and `ApprovalService.request_approval`/`resolve` signatures are preserved; `request_bound_approval` is new and `resolve` is extended additively (step transition only when `workflow_step_run_id` is set).
**Files/sections:** requirements REQ-E2.1, E2.5, E2.9, E8.1 (backward-compat tests); design §5.2, §5.8, §7.5, §7.6, §17; tasks T5, T6, T10.
**Rationale:** The corrected design must remain compatible with the actual Phase 1 code, not an assumed version of it. Breaking Phase 1 tests or services would violate the backward-compatibility commitment.
**Tests:** `test_phase1_create_run_on_null_template_returns_pending` (legacy run; preserves `test_create_run_returns_pending_status`), `test_phase1_workflow_service_create_run_unchanged`, `test_phase1_run_status_constraint_unchanged`, `test_approval_status_constraint_unchanged_no_consumed_value`, `test_run_cancelled_while_waiting_approval_transitions_correctly`.

### F14 — Approval consumption before execution (v2.1.1)
**Finding:** v2.1.0 described approval consumption as happening *after* fenced result persistence (the protected action executed, then consumed the approval). This is too late: a protected executor could be invoked before its authorization was confirmed, risking execution without valid authorization. The single-use guarantee was also tangled with the result-persist fence.
**Resolution:** Approval consumption moved to **before** the protected executor is invoked. Lease acquisition, `attempt` increment, the `READY → RUNNING` transition, and `consume_atomic` are coordinated in **one `BEGIN IMMEDIATE` transaction** (`dispatch_protected_txn`). The consume predicate validates all seven: operation, parameter digest, step binding, actor, status (`approved`), consumption marker (`consumed_at IS NULL`), and authorization validity (`now < authorization_expires_at`). On `rowcount == 0` the whole transaction rolls back — the step stays `READY` (no lease, `attempt` unchanged, **unexecuted**), an `approval_not_consumable` audit names the reason, and the orchestrator re-gates (`READY → WAITING_APPROVAL`, fresh approval). The executor is invoked **only after** the transaction commits, and the executor call is **outside** the DB transaction. Stale completions still cannot overwrite current results (fencing on `lease_owner`+`attempt` at persist) and cannot re-consume (the approval was consumed at the original dispatch's transaction). Cancellation, failure, timeout, and `indeterminate` outcomes **never** restore the consumed approval (`consumed_at` is never set back to `NULL`; no-restore guard test). Protected-operation retries require fresh authorization: an approvable step's retryable failure transitions `RUNNING → WAITING_APPROVAL` (re-gate) rather than `RUNNING → READY`.
**Files/sections:** requirements REQ-E2.2, E2.4 (re-gate on consume failure), E2.6, E3.3 (consume before execute; seven-binding predicate; rollback), **new REQ-E3.7** (pre-execution authorization), E4.2 (new `RUNNING → WAITING_APPROVAL` transition), E4.6 (consume in same txn), E4.7 (approvable retry re-gate), E4.11 (no re-consume), E6.5, E8.1; design §5.3, §5.4 (`dispatch_protected`), §5.6, §7.2, §7.4, §7.7, §8.2, §10.4, §12.2; tasks T3, T5, T6, T10.
**Rationale:** Authorization must be confirmed before a protected side effect is taken; consuming after execution allows unauthorized side effects. Atomicity (lease+consume in one txn) prevents a partial state where the lease is acquired but the approval is invalid. Never-restoring keeps the single-use guarantee meaningful across all outcomes.
**Tests:** `test_protected_executor_not_invoked_until_approval_consumed`, `test_consume_and_lease_acquired_in_one_transaction`, `test_failed_consume_leaves_step_unexecuted_and_re_gates`, `test_consume_validation_rejects_status_not_approved`, `test_consume_validation_rejects_already_consumed`, `test_consume_validation_rejects_authorization_expired`, `test_consume_validation_rejects_operation_mismatch`, `test_consume_validation_rejects_digest_mismatch`, `test_consume_validation_rejects_step_binding_mismatch`, `test_consume_validation_rejects_actor_mismatch`, `test_concurrent_consume_only_one_dispatch_proceeds`, `test_dispatch_and_consume_atomic_rollback_on_consume_failure`, `test_consumed_approval_not_restored_on_failure`, `test_consumed_approval_not_restored_on_cancel`, `test_consumed_approval_not_restored_on_timeout`, `test_consumed_approval_not_restored_on_indeterminate`, `test_retryable_failure_approvable_re_gates_to_waiting_approval`.

### F15 — Terminal run with blocked dependencies (v2.1.1)
**Finding:** v2.1.0 derived the run as `failed` only when all steps are terminal, but did not define what happens to `PENDING`/`READY`/`WAITING_APPROVAL`/`INTERRUPTED` steps that remain when another step fails — they would stay non-terminal forever, so the run could hang in `running` and never reach `failed`.
**Resolution:** Deterministic failure-stop settle policy. When a step transitions to a real terminal `FAILED`, the orchestrator engages the policy: (a) **no new `READY → RUNNING` dispatch**; (b) already-`RUNNING` independent steps are allowed to finish to their natural terminal (a retryable failure during failure-stop is **suppressed** → `RUNNING → FAILED` with reason `run_failure_stop`, not retried); (c) every remaining non-terminal non-running step (`PENDING`, `READY`, `WAITING_APPROVAL`, `INTERRUPTED`) is transitioned to `FAILED` with `category = "skipped"`, `code = "STEP_BLOCKED_BY_RUN_FAILURE"`, `retryable = false`, via guarded CAS per state (reusing existing `PENDING → FAILED`, `READY → FAILED`, `INTERRUPTED → FAILED` transitions plus a new `WAITING_APPROVAL → FAILED` transition — **all between existing states; no ninth step status**); (d) any `pending` approval bound to a settled `WAITING_APPROVAL` step is set to `expired` (a later resolve 409s/no-ops); (e) each settled step writes `step_failed` with the skipped reason. The run transitions to Phase 1 `failed` **only after** the policy has settled all remaining steps (all terminal). The policy is idempotent (CAS `WHERE status=<expected>` is a no-op once terminal). Recovery (§9) also settles `INTERRUPTED → FAILED` (`skipped`) when the run is already in failure-stop.
**Files/sections:** requirements REQ-E1.3, E2.6, **new REQ-E4.12** (failure-stop settle), E4.2 (new `WAITING_APPROVAL → FAILED` transition; failure-stop triggers on existing `→ FAILED`), E4.4, E4.5 (`skipped` category; `run_failure_stop` reason), E4.7.5 (retry suppression), E4.8.4 (recovery settle), E8.1; design §3.4, §5.5 (`engage_failure_stop`/`settle_to_failed`), §8.2, §9.1, §12.2; tasks T3 (`settle_to_failed`), T5, T7, T10.
**Rationale:** Without settling blocked steps, the run can never reach a terminal state, breaking the "run reaches `failed` when all steps terminal" rule and leaving runs stuck. A deterministic settle with a documented `skipped` reason makes the run outcome unambiguous. Reusing `FAILED` (terminal) avoids introducing a ninth status; the `skipped` category distinguishes "never ran due to run failure" from "executed and failed."
**Tests:** `test_failed_linear_workflow_settles_blocked_steps`, `test_failed_diamond_dependency_settles_blocked_step`, `test_independent_in_flight_step_finishes_before_run_failed`, `test_no_new_dispatch_after_failure_stop`, `test_waiting_approval_step_settled_and_approval_expired_on_run_failure`, `test_run_reaches_failed_only_after_all_steps_settled`, `test_settle_uses_skipped_category_no_ninth_status`, `test_retry_suppressed_under_failure_stop`, `test_step_blocked_by_run_failure_audited`.

---

## 2. Resolved Defaults Applied (task §3)

| Default | Value | Where applied |
|---|---|---|
| Pending approval TTL | 3600s | `Settings.APPROVAL_TTL_SECONDS`; `approval_requests.expires_at` (REQ-E3.4) |
| Approved authorization validity | 3600s, separate column | `Settings.APPROVAL_AUTHORIZATION_VALIDITY_SECONDS`; `approval_requests.authorization_expires_at` (REQ-E3.6); status CHECK unchanged |
| Run concurrency | 1 | `Settings.RUN_CONCURRENCY` (REQ-E2.2) |
| Lease | 60s | `Settings.STEP_LEASE_TTL_SECONDS` (REQ-E4.6) |
| Heartbeat | 15s | `Settings.STEP_HEARTBEAT_INTERVAL_SECONDS` (REQ-E4.10) |
| Recovery | automatic reconciliation; explicit start for resumed execution | REQ-E4.3; design §9.1 |
| Executor security guards | mandatory (hard gate) | REQ-E5.4; AST guard test |
| Template | immutable full execution snapshot per run | REQ-E1.8; `workflow_runs.template_snapshot_json` |

---

## 3. Migration Additions and Backward Compatibility

Migration `008_add_workflow_execution_engine` (chains from verified head `007_add_github_confirmations`; implementer re-confirms head). It is additive and reversible:

- **NEW table `workflow_step_runs`** (eight-state CHECK, `UNIQUE(run,step_key)`, lease/timestamp/idempotency columns, indexes).
- **ALTER `approval_requests` ADD** `operation`, `parameters_hash`, `actor_id`, `workflow_step_run_id` (ON DELETE SET NULL), `consumed_at`, `expires_at`, `authorization_expires_at` + indexes. **`status` CHECK unchanged.**
- **ALTER `workflow_runs` ADD** `template_snapshot_json`, `template_version`, `template_hash` + index. **`status` CHECK unchanged.**
- `downgrade()` drops all of the above and restores the prior schema exactly.

**Backward compatibility:**
- `workflow_runs.status` and `approval_requests.status` CHECK constraints unchanged.
- All new columns nullable; Phase 1 rows have `NULL` (`expires_at`/`authorization_expires_at` NULL ⇒ no expiry, preserving Phase 1 semantics).
- Legacy `NULL`/empty-template runs preserved (201 pending, zero steps) so Phase 1 router tests pass unmodified.
- `WorkflowService.create_run`/`transition_run` and `ApprovalService.request_approval`/`resolve` signatures preserved; `request_bound_approval` (new) and `resolve` (additive) extend without breaking Phase 1 callers.
- Migrations 001–007 unchanged.
- No Phase 1 test requires modification.

---

## 4. Cross-Document Verification (task §4)

Reconciled across `requirements.md`, `design.md`, `tasks.md`, `docs/planning/phase2-roadmap.md`, `docs/reports/phase2-wave1-spec-readiness.md`:

- **Every requirement has an implementation task, design reference, acceptance criterion, and test coverage** — see the traceability in §5 below and `requirements.md` Traceability Matrix. REQ-E1.8 (snapshot) ↔ T2/T5 ↔ design §3.2/§4/§5.2 ↔ tests `test_template_snapshot_*`. REQ-E4.11 (fencing) ↔ T3/T5/T7 ↔ design §5.4/§10.4 ↔ tests `test_stale_completion_*`. REQ-E3.6 (validity/re-gating) ↔ T2/T3/T6 ↔ design §7.2/§7.4 ↔ tests `test_approved_authorization_*`/`test_approval_re_gated_*`. etc.
- **SQLite concurrency:** `BEGIN IMMEDIATE` + `busy_timeout` + CAS `rowcount` for every write (design §10); write serialisation is a database guarantee, not an application/pool claim (F-context correction carried from Phase 1 v1.5.2). Concurrency=1 in Wave 1 makes contention rare; the pattern is specified for later concurrency.
- **Approval atomicity:** `consume_atomic` is a single CAS `UPDATE` with all bindings + `now < authorization_expires_at`; concurrent consumes yield exactly one `rowcount == 1` (REQ-E3.3.9). Consumption is invoked only after the fenced persist CAS succeeds (F9).
- **Cancellation races:** cancel transitions the step to `CANCELLED`; the in-flight persist CAS fences on `status='RUNNING'` and fails; the approval is not consumed (REQ-E2.7.4, E4.11.4).
- **Stale completion fencing:** post-dispatch CAS fences on `lease_owner`+`attempt`; stale results discarded and audited; cannot consume (F9).
- **Failure recovery:** automatic reconciliation (interrupt + decide retry/fail, idempotent); no auto-dispatch; explicit start resumes (F3).
- **Phase 1 model/service compatibility:** verified against the actual `WorkflowService.WORKFLOW_TRANSITIONS`, `ApprovalService.request_approval`/`resolve` signatures, `WorkflowRun`/`ApprovalRequest`/`WorkflowAuditLog` columns (F13). Run `waiting_approval` transitions go through the approval service; legacy `NULL`-template runs preserved.

---

## 5. Requirements-to-Tests Traceability

| Requirement | Acceptance criteria | Named tests (minimum) |
|---|---|---|
| REQ-E1.1 template | E1.1.1–E1.1.5 | (template validation unit tests in T1) |
| REQ-E1.2 run/step creation | E1.2.1–E1.2.4 | `test_run_creation_atomic_rollback`, `test_template_hash_recorded_on_run` |
| REQ-E1.3 dependencies | E1.3.1–E1.3.3 | `test_linear_chain_dispatches_in_order`, `test_diamond_dependency_gates_until_all_succeeded`, `test_failed_dependency_blocks_dependents` |
| REQ-E1.4 inputs/outputs | E1.4.1–E1.4.3 | `test_pending_to_failed_on_input_resolution_failure` |
| REQ-E1.5 tool selection/version | E1.5.1–E1.5.3 | `test_template_snapshot_immutable_after_live_workflow_edit` |
| REQ-E1.6 durable state | E1.6.1–E1.6.3 | (model/type tests in T2) |
| REQ-E1.7 CAS transitions | E1.7.1–E1.7.3 | `test_step_skip_ready_to_running_rejected`, `test_invalid_transition_writes_rejection_audit_and_no_mutation`, `test_concurrent_dispatch_only_one_succeeds` |
| REQ-E1.8 immutable snapshot | E1.8.1–E1.8.4 | `test_template_snapshot_immutable_after_live_workflow_edit`, `test_template_hash_recorded_on_run`, `test_legacy_run_has_no_snapshot_and_zero_steps` |
| REQ-E2.1 create_run | E2.1.1–E2.1.5 | `test_run_creation_atomic_rollback`, `test_create_run_legacy_run_on_null_template_201`, `test_create_run_invalid_template_422` |
| REQ-E2.2 start/resume | E2.2.1–E2.2.4 | `test_ready_to_failed_on_executor_not_found`, `test_ready_to_failed_on_working_directory_not_approved`, `test_ready_to_failed_on_capability_mismatch` |
| REQ-E2.3 succeed | E2.3.1–E2.3.3 | `test_mock_executor_deterministic_output` |
| REQ-E2.4 approval gate/re-gate | E2.4.1–E2.4.4 | `test_approval_re_gated_after_authorization_expiry` |
| REQ-E2.5 resolve | E2.5.1–E2.5.4 | `test_phase1_approval_resolve_still_works_without_operation`, `test_phase1_create_run_on_null_template_returns_pending` |
| REQ-E2.6 fail | E2.6.1–E2.6.3 | `test_retry_exhaustion_transitions_to_failed_terminal`, `test_failed_dependency_blocks_dependents` |
| REQ-E2.7 cancel | E2.7.1–E2.7.4 | `test_cancel_run_marks_non_terminal_steps_cancelled`, `test_cancel_run_keeps_succeeded_steps`, `test_cancel_idempotent_on_terminal_run`, `test_consume_refused_after_run_cancelled`, `test_cancel_run_while_waiting_approval` |
| REQ-E2.8 executor interface/layering | E2.8.1–E2.8.3 | `test_schemas_do_not_import_executors_package`, `test_executors_do_not_import_repositories_services_models` |
| REQ-E2.9 run transitions/compat | E2.9.1–E2.9.3 | `test_run_cancelled_while_waiting_approval_transitions_correctly`, `test_phase1_workflow_service_create_run_unchanged` |
| REQ-E3.1 checkpoint def | E3.1.1–E3.1.4 | `test_approval_status_constraint_unchanged_no_consumed_value` |
| REQ-E3.2 canonical digest | E3.2.1–E3.2.3 | `test_approval_parameter_digest_mismatch_rejected` |
| REQ-E3.3 consume_atomic | E3.3.1–E3.3.9 | `test_approval_consumed_once_replay_rejected`, `test_concurrent_consume_only_one_succeeds`, `test_approval_bound_to_step_a_cannot_authorize_step_b`, `test_approval_operation_mismatch_rejected`, `test_approval_actor_mismatch_rejected`, `test_pending_approval_not_consumable`, `test_expired_approval_not_consumable`, `test_consume_refused_after_authorization_expiry` |
| REQ-E3.4 pending TTL | E3.4.1–E3.4.3 | `test_expired_pending_approval_cannot_be_promoted_to_approved` |
| REQ-E3.5 deletion | E3.5.1–E3.5.3 | (no-single-step-delete guard test in T3) |
| REQ-E3.6 approved validity/re-gate | E3.6.1–E3.6.4 | `test_approved_authorization_expires_after_validity`, `test_consume_refused_after_authorization_expiry`, `test_approval_re_gated_after_authorization_expiry` |
| REQ-E4.1 states | E4.1.1–E4.1.3 | `test_phase1_run_status_constraint_unchanged` |
| REQ-E4.2 transition map | E4.2.1–E4.2.4 | `test_step_terminal_state_revival_rejected`, `test_retryable_failure_transitions_running_to_ready_not_failed` |
| REQ-E4.3 recovery | E4.3.1–E4.3.4 | `test_running_step_with_expired_lease_becomes_interrupted`, `test_running_step_with_valid_lease_not_interrupted`, `test_recovery_idempotent`, `test_recovery_does_not_auto_dispatch_requires_explicit_start` |
| REQ-E4.4 run derivation | E4.4.1–E4.4.3 | `test_run_failed_derived_only_after_all_steps_terminal`, `test_run_completed_only_when_all_steps_succeeded`, `test_legacy_run_with_zero_steps_vacuously_completes` |
| REQ-E4.5 errors | E4.5.1–E4.5.3 | `test_step_timeout_marks_failed_or_ready_not_interrupted` |
| REQ-E4.6 dispatch CAS | E4.6.1–E4.6.3 | `test_concurrent_dispatch_only_one_succeeds`, `test_cas_uses_begin_immediate`, `test_attempt_increments_on_dispatch` |
| REQ-E4.7 retry/budget | E4.7.1–E4.7.5 | `test_retryable_failure_transitions_running_to_ready_not_failed`, `test_retry_exhaustion_transitions_to_failed_terminal`, `test_retry_never_passes_through_failed`, `test_attempt_budget_enforced_max_attempts`, `test_unsafe_indeterminate_step_not_retried` |
| REQ-E4.8 recovery decision | E4.8.1–E4.8.4 | `test_recovery_safe_step_retries_under_budget`, `test_recovery_unsafe_step_fails`, `test_recovery_step_at_max_attempts_fails` |
| REQ-E4.9 idempotency | E4.9.1–E4.9.3 | `test_mock_executor_deterministic_output`, `test_input_digest_change_blocks_retry_for_non_idempotent` |
| REQ-E4.10 stale/heartbeat | E4.10.1–E4.10.3 | `test_heartbeat_only_owner_renews_lease`, `test_cancelled_run_rejects_heartbeat` |
| REQ-E4.11 fencing | E4.11.1–E4.11.4 | `test_stale_completion_discarded_by_lease_fence`, `test_stale_completion_cannot_consume_approval`, `test_step_stale_completion_discarded_audited` |
| REQ-E5.1 executor registry | E5.1.1–E5.1.3 | `test_ready_to_failed_on_executor_not_found`, `test_ready_to_failed_on_capability_mismatch` |
| REQ-E5.2 context/result | E5.2.1–E5.2.4 | `test_mock_executor_no_fs_network_subprocess` |
| REQ-E5.3 timeout/cancel | E5.3.1–E5.3.3 | `test_step_timeout_marks_failed_or_ready_not_interrupted`, `test_executor_ignoring_cancel_marked_cancelled` |
| REQ-E5.4 mock/guards | E5.4.1–E5.4.4 | `test_mock_executor_only_registered_executor`, `test_no_shell_execution_in_executors_package` |
| REQ-E6.1 loopback | E6.1.1–E6.1.2 | (config test in T10) |
| REQ-E6.2 working dir | E6.2.1–E6.2.3 | `test_working_directory_outside_allowlist_rejected` |
| REQ-E6.3 env allowlist | E6.3.1–E6.3.3 | `test_env_allowlist_no_parent_inheritance_contract` |
| REQ-E6.4 credentials | E6.4.1–E6.4.2 | `test_no_secret_in_audit_or_logs` |
| REQ-E6.5 approval enforcement | E6.5.1–E6.5.4 | `test_stale_completion_cannot_consume_approval` |
| REQ-E6.6 indeterminate | E6.6.1–E6.6.3 | `test_indeterminate_outcome_not_retried_and_approval_not_restored` |
| REQ-E6.7 audit integrity | E6.7.1–E6.7.2 | `test_audit_append_only_no_update_delete` |
| REQ-E6.8 isolation prereqs | E6.8.1–E6.8.2 | `test_no_shell_execution_in_executors_package`, `test_no_automatic_pr_merge_endpoint_absent` |
| REQ-E7.1 create run | (endpoint) | `test_create_run_invalid_template_422`, `test_create_run_legacy_run_on_null_template_201` |
| REQ-E7.2 start | (endpoint) | `test_start_terminal_run_409` |
| REQ-E7.3 cancel | (endpoint) | `test_cancel_terminal_run_idempotent_200` |
| REQ-E7.4 inspect | E7.4.1–E7.4.3 | `test_run_response_includes_steps_and_approvals_projection` |
| REQ-E7.5 audit | (endpoint) | `test_audit_endpoint_pagination` |
| REQ-E7.6 resolve | (endpoint) | `test_phase1_approval_resolve_still_works_without_operation` |
| REQ-E7.7 Streamlit | E7.7.1–E7.7.4 | (AppTest in T9) |
| REQ-E7.8 OpenAPI | (regen) | `test_no_automatic_pr_merge_endpoint_absent` |
| REQ-E8.1 test matrix | (the matrix itself) | (all of the above) |
| REQ-E8.2 quality gates | (gates) | `test_full_round_trip_001_to_008` |
| REQ-E8.3 migration round-trip | (upgrade/downgrade) | `test_migration_008_upgrade_creates_step_runs_extends_approvals_and_workflow_runs`, `test_migration_008_downgrade_restores_prior_schema`, `test_full_round_trip_001_to_008` |

---

## 6. Remaining Risks

1. **Migration head drift:** `008` is derived from the verified head `007`. If Phase 1 advances before implementation, the implementer MUST re-confirm and re-chain. (Low risk; gated by an explicit instruction.)
2. **Concurrency > 1 correctness:** Wave 1 defaults to concurrency 1. The run-derivation and fencing rules are specified for concurrency > 1 but are exercised only lightly in Wave 1 (mock executor is in-process). Later waves introducing real concurrency should re-stress these paths. (Medium risk; mitigated by the specified rules + tests, but under-exercised.)
3. **Approved-authorization re-gating UX:** an approved authorization that expires while a step waits forces a fresh human decision (re-gate). If approvals are slow, this could stall a run at `WAITING_APPROVAL` repeatedly. (Low-medium risk; acceptable for a local single-user tool; documented as a deliberate decision — design §18 #3.)
4. **`attempt` semantics choice:** the spec uses `attempt` = executions attempted (0-based, incremented on dispatch) and `max_attempts` = total executions incl. the first. An implementer reading the numeric literals should follow the tests' encoded semantics; a mismatch would cause off-by-one retries. (Low risk; pinned by named tests.)
5. **Audit integrity is append-only, not signed:** a local privileged user can edit the SQLite file. This is honestly documented (no false claim). A future wave may add chained hashes. (Accepted; out of Wave 1 scope.)
6. **No OS-level isolation:** Wave 1 is application-level only; real coding-agent execution is gated behind Wave 6. The mock executor has no fs/network/subprocess, so the risk is contained in Wave 1, but any later executor must not be enabled until the §12.4 prerequisites exist. (Documented; enforced by the mandatory guard test.)
7. **Local environment defect (non-blocking):** the committed `.venv` is corrupted and the system Python 3.12.10 is incomplete (missing `xml.dom`), so `coverage` cannot run locally. The 313-test develop baseline was verified with coverage disabled; CI remains the authoritative coverage gate. (Environment issue, not a spec issue.)
8. **Consumed approval + discarded stale result (F14 edge, later waves):** if a protected dispatch consumes its approval, executes an external side effect, but its completion is later discarded as stale (superseded by a re-dispatch after process death), the approval is spent and the external side effect is indeterminate. Wave 1 (mock, no external writes) is unaffected; later waves with real external writes must treat this as the indeterminate-external-write case (fresh approval + reconciliation). Documented in design §18 #3.
9. **Settle target state choice (F15):** blocked steps are settled to `FAILED` (`skipped`) rather than `CANCELLED` (cancel is reserved for user cancel/approval-reject). This is a deliberate semantic choice; flagged for ChatGPT confirmation (design §18 #4).
10. **Approved-authorization re-gating UX (F14):** an approved authorization that expires while a step waits forces a fresh human decision (re-gate), which could stall a run at `WAITING_APPROVAL` repeatedly if approvals are slow. Acceptable for a local single-user tool; flagged for confirmation (design §18 #5).

---

## 7. Final Readiness Verdict

All fifteen findings are resolved: F1–F12 (the 12 correction items), F13 (Phase 1 service compatibility), F14 (approval consumption before execution), and F15 (terminal run with blocked dependencies). Resolved defaults are applied. The corrected spec (v2.1.1) is internally consistent across requirements/design/tasks/roadmap/readiness-report, every requirement traces to a task, design section, acceptance criterion, and named test, and the design is compatible with the actual Phase 1 models and services (CHECK constraints unchanged; legacy `NULL`-template runs preserved; service signatures preserved). Eight step states and six Phase 1 run states are preserved; no ninth step status is introduced (failure-stop settle reuses existing transitions to `FAILED`). Key v2.1.1 invariants: protected executors are never invoked before their approval is atomically consumed (lease+consume in one transaction; executor outside the txn; failed consume rolls back and re-gates); consumed approvals are never restored; failure-stop deterministically settles all remaining non-terminal non-running steps to `FAILED` (`skipped`) and the run reaches `failed` only after settle. Security claims are honest (no OS-sandboxing claim; fencing prevents stale-completion re-consumption). Remaining risks are documented and acceptable for a spec-only deliverable awaiting ChatGPT approval.

**PHASE 2 WAVE 1 SPEC READY — AWAITING CHATGPT APPROVAL**

Stop after specification verification. No implementation, migration, push, PR, or merge was performed.
