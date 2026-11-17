# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Requirements

**Version:** 2.0.0
**Status:** Initial specification — awaiting ChatGPT review
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9, PR #13 merged)
**Last Updated:** 2026-11-17
**Supersedes:** None (new Phase 2 specification). Extends `.kiro/specs/phase1-functional-orchestration/` (v1.5.9); does not modify it.

**Version history:**
- v2.0.0 — 2026-11-17 — Initial Phase 2 Wave 1 specification. Defines the Workflow Execution Engine: workflow/step definition and execution model (E1), orchestration service (E2), approval checkpoints (E3), eight-state step lifecycle and recovery (E4), executor contracts with a mock/no-op executor (E5), security architecture (E6), minimal API and Streamlit contracts (E7), and testing/acceptance (E8). Migration 008 (`008_add_workflow_execution_engine`) planned, chaining from the verified Alembic head `007_add_github_confirmations`. No production code, migrations, or Phase 1 spec files are modified by this task. See `docs/reports/phase2-wave1-spec-readiness.md`.

---

## Overview

Phase 2 builds the end-to-end DevFlow AI workflow: a user describes a feature, DevFlow creates a workflow run, an AI provider generates specifications, Kiro verifies them through guided handoff, the AI reviews the Kiro report, the user approves, Codex CLI implements, the AI reviews the implementation, the user approves PR creation, the GitHub adapter creates and monitors the PR, and the user separately approves merging. Every operation is auditable. PR merging is never automatic.

**Wave 1 scope — Workflow Execution Engine only.** Wave 1 delivers the core engine that turns a workflow definition into durable, recoverable, approval-gated step executions. Wave 1 deliberately ships **no real coding-agent execution** and **no Kiro, Codex, OpenAI, Ollama, or GitHub integration**; a single safe mock/no-op executor validates the engine end-to-end. The six-wave Phase 2 roadmap is in `docs/planning/phase2-roadmap.md`.

Wave 1 reuses the Phase 1 persistence and authorization foundation without duplicating it:

| Phase 1 model (reused) | File | Wave 1 use |
|---|---|---|
| `Workflow` | `src/devflow_api/models/workflow.py` | Definition container; `definition_json` becomes the validated `WorkflowTemplate` (ordered steps, dependencies, I/O, tool selection, versioning). No column added to `workflows`. |
| `WorkflowRun` | `src/devflow_api/models/workflow.py` | Run instance; Phase 1 six-state run status **unchanged** and derived from step states for backward compatibility. |
| `ApprovalRequest` | `src/devflow_api/models/approval.py` | Human approval gate, **extended additively** with operation + parameter-digest + actor + step-run binding + single-use consumption marker. The Phase 1 `status` CHECK constraint is **not changed**. |
| `WorkflowAuditLog` | `src/devflow_api/models/audit.py` | Append-only audit; reused unchanged for every execution transition. |

Wave 1 adds **one new table** (`workflow_step_runs`) and **extends** `approval_requests` additively, via migration 008 (planned; not authored in this specification task).

**Phase 1 boundary carried into Wave 1:** the application remains local-first, single-user, loopback-only, free-core. The trust boundary is the local operator (`Settings.LOCAL_OPERATOR_ID`, default `'local_operator'`); Wave 1 does not introduce multi-user authentication.

### Global Constraints (apply to all requirements below)

- The application MUST remain local-first with free core functionality.
- All development services MUST bind exclusively to `127.0.0.1` on the host interface.
- The codebase MUST NOT contain Android, React, TypeScript, or Vite artefacts.
- No hardcoded credentials or secrets MUST appear in source control at any time.
- Architecture boundaries from Phase 0/1 (UI → API → domain services → repositories → SQLite; services → adapters) MUST be preserved.
- Phase 0 and Phase 1 specification files MUST NOT be modified by Wave 1 implementation. Phase 1 tests MUST continue to pass; where a Phase 1 assertion intentionally grows (see REQ-E3.1 backward-compatibility note), the change is documented and additive.
- `datetime.utcnow()` MUST NOT appear in any Phase 2 code; use `datetime.now(UTC)` exclusively.
- All new timestamp columns MUST use the `UTCDateTime` TypeDecorator from `src/devflow_api/models/base.py`.
- Every consequential or external action MUST require an explicit, digest-bound, single-use approval before execution. Approval presence is authorization; credential presence is not.
- No unrestricted shell/command execution MUST be introduced in Wave 1. Only the mock/no-op executor (REQ-E5.x) ships.
- Environment-variable scoping is a Python-level control; it is NOT OS-level sandboxing and MUST NOT be described as such (REQ-E6.x).

### Out of Scope for Wave 1

| Capability | Deferral reason |
|---|---|
| Real coding-agent execution (Codex CLI, Kiro, Ollama, OpenAI) | Wave 1 ships the engine + a mock executor only; integrations are Waves 2–3 |
| Unrestricted shell / arbitrary command execution | A separate safety concern; deferred past Phase 2 until OS-level isolation exists (REQ-E6.x) |
| Autonomous PR creation / merge | PR creation is Wave 4; merge is never automatic |
| Full Streamlit workflow dashboard | Wave 5; Wave 1 adds only minimal run/step observation (REQ-E7.x) |
| Multi-user access control | Local single-user tool; explicit trust boundary (REQ-E6.x) |
| OS-level process sandboxing (seccomp, namespaces, job objects) | Required before real coding-agent execution; documented as a prerequisite in REQ-E6.x, not delivered in Wave 1 |
| Changing the Phase 1 `workflow_runs.status` enum | Backward compatibility; the eight-state lifecycle lives on step runs (REQ-E4.x) |
| Renaming or restructuring Phase 1 models | Wave 1 extends additively only |

---

## Area E1 — Workflow Definition and Execution Model

**Scope note (maps to task W1.1):** the durable structure that turns a `Workflow` into ordered, executable steps with dependencies, inputs/outputs, tool selection, versioning, and durable execution state.

### REQ-E1.1
WHEN a workflow is defined for Phase 2 execution,
THEN the `Workflow.definition_json` column MUST hold a validated `WorkflowTemplate` (Pydantic v2 model) containing `template_version: int`, `steps: list[StepDefinition]` (ordered, non-empty, unique `key`), and `defaults: TemplateDefaults` (default executor id, default timeout seconds, default retry policy). The template MUST be validated on `Workflow` create/update and on run creation; invalid templates MUST be rejected with HTTP 422 and `code = "INVALID_WORKFLOW_TEMPLATE"`.

**Acceptance Criteria:**
E1.1.1 — `WorkflowTemplate` is a Pydantic v2 model in `src/devflow_api/schemas/workflow.py` and is importable.
E1.1.2 — `StepDefinition` carries: `key: str`, `version: int`, `title: str`, `description: str`, `depends_on: list[str]` (step keys), `executor_id: str`, `tool_selection: ToolSelection`, `inputs: dict[str, Any] | None`, `expected_outputs: list[str] | None`, `timeout_s: int`, `retry_policy: RetryPolicy`, `approvable: bool`, `protected_operation: str | None`.
E1.1.3 — A template with a duplicate step `key`, an empty `steps` list, a `depends_on` referencing a non-existent key, or a cycle in `depends_on` MUST be rejected with HTTP 422 `INVALID_WORKFLOW_TEMPLATE`.
E1.1.4 — `mypy --strict src/devflow_api/schemas/workflow.py` exits with code 0.
E1.1.5 — The existing `Workflow` SQLAlchemy model is NOT modified; no column is added to `workflows`. `definition_json` remains `deferred=True, deferred_raiseload=True`.

### REQ-E1.2
WHEN a workflow run is created for execution,
THEN a `WorkflowRun` MUST be persisted with Phase 1 status `pending`, and one `WorkflowStepRun` row MUST be created per `StepDefinition` in `WorkflowTemplate.steps`, each in step status `PENDING`, with `step_key`, `step_version`, `executor_id`, `tool_selection_json`, `input_json`, `depends_on_json`, `workflow_run_id` (FK CASCADE), `attempt = 0`, and `created_at`/`updated_at` set to `datetime.now(UTC)`.

**Acceptance Criteria:**
E1.2.1 — `POST /api/v1/workflows/{id}/runs` (Phase 1 endpoint, extended) creates the run AND all step rows in one transaction; partial creation MUST roll back entirely.
E1.2.2 — Step row count equals `len(WorkflowTemplate.steps)`; order matches template order; `step_key` values are unique within the run.
E1.2.3 — `WorkflowStepRun` model is importable from `devflow_api.models.workflow_step_run` (new file) and `mypy --strict` passes for it.
E1.2.4 — Re-running run creation against an unchanged template produces a deterministic set of step keys/versions (enables reproducibility tests).

### REQ-E1.3
WHEN steps declare dependencies,
THEN the orchestrator MUST compute step readiness from `depends_on`: a step is eligible to become `READY` only when every dependency's `WorkflowStepRun.status == "SUCCEEDED"`. A step whose dependency `FAILED` or `CANCELLED` MUST NOT become `READY`; its disposition is determined by the run stop/cancel policy (REQ-E4.4).

**Acceptance Criteria:**
E1.3.1 — A two-step template (`a → b`) where `a` fails leaves `b` non-`READY` and the run stops safely (REQ-E4.4).
E1.3.2 — Diamond dependency (`a → {b,c} → d`) gates `d` until both `b` and `c` are `SUCCEEDED`.
E1.3.3 — A dependency declared in `depends_on` that has no matching step row fails template validation (REQ-E1.1.3), not at run time.

### REQ-E1.4
WHEN step inputs and outputs are managed,
THEN each `WorkflowStepRun` MUST persist `input_json` at creation and `output_json` + `artifact_refs_json` at success; step outputs MUST be referenceable as inputs to downstream steps by `step_key.output_name` in the template `inputs` mapping, resolved by the orchestrator at dispatch time (no implicit global namespace).

**Acceptance Criteria:**
E1.4.1 — A downstream step whose `inputs` references `"$steps.a.spec_doc"` resolves to the `output_json["spec_doc"]` of step `a` only when `a` is `SUCCEEDED`; otherwise the downstream step cannot become `READY`.
E1.4.2 — A missing or malformed output reference MUST fail the step at dispatch with `code = "INPUT_RESOLUTION_FAILED"` (step → `FAILED`).
E1.4.3 — `output_json` and `artifact_refs_json` are `None` until the step `SUCCEEDED`; they are never written for non-terminal or `FAILED` steps except `error_json` (REQ-E4.5).

### REQ-E1.5
WHEN tool selection and versioning are recorded,
THEN every `WorkflowStepRun` MUST persist `tool_selection_json` (the `ToolSelection` snapshot from the template) and `step_version` (the `StepDefinition.version`) at creation, so an audit reader can reconstruct which tool/version executed even if the template later changes. `WorkflowTemplate.template_version` and `WorkflowStepRun.step_version` form the durable versioning record.

**Acceptance Criteria:**
E1.5.1 — Editing the `Workflow.definition_json` after a run is created does NOT alter any existing `WorkflowStepRun.tool_selection_json` or `step_version`.
E1.5.2 — `GET .../steps/{step_id}` returns `step_version` and `tool_selection` (read-only projection).
E1.5.3 — A run created from `template_version=2` records `template_version=2` on the run (REQ-E2.1); bumping the template does not retroactively change existing runs.

### REQ-E1.6
WHEN durable execution state and timestamps are required,
THEN `WorkflowStepRun` MUST carry UTC timestamps `ready_at`, `dispatched_at`, `started_at`, `completed_at` (all nullable, `UTCDateTime`), plus `lease_owner: str | None`, `lease_expires_at: UTCDateTime | None`, `attempt: int` (default 0), `status` (eight-state, REQ-E4.1), `result_status: str | None` (executor outcome), and `error_json: str | None`. All state MUST persist to SQLite and survive process restart.

**Acceptance Criteria:**
E1.6.1 — All timestamp columns use `UTCDateTime`; no `datetime.utcnow()` anywhere in the new code (`grep -R "datetime.utcnow"` returns no matches in `src/devflow_api/models/workflow_step_run.py` and the new service).
E1.6.2 — After a simulated restart (new process, same DB), step rows and their timestamps are unchanged.
E1.6.3 — `mypy --strict` passes for the new model.

### REQ-E1.7
WHEN state transitions occur,
THEN the orchestrator MUST validate each transition against the allowed-transition map (REQ-E4.2) using a compare-and-set `UPDATE ... WHERE id = ? AND status = ?` inside a `BEGIN IMMEDIATE` transaction, and MUST reject invalid transitions with `code = "INVALID_STEP_TRANSITION"` and no row mutation.

**Acceptance Criteria:**
E1.7.1 — A `PENDING → RUNNING` transition (skipping `READY`) is rejected; the row stays `PENDING` and an audit entry `step_transition_rejected` is written.
E1.7.2 — A valid `READY → RUNNING` CAS update sets `lease_owner`, `lease_expires_at`, `dispatched_at`, `started_at` atomically.
E1.7.3 — A concurrent `READY → RUNNING` attempt by two workers: exactly one CAS update affects one row (`rowcount == 1`); the other gets `rowcount == 0` and raises `StepDispatchConflict` (duplicate-dispatch prevention, REQ-E4.6).

---

## Area E2 — Workflow Orchestration Service

**Scope note (maps to task W1.2):** a Python orchestration service that drives runs from creation through terminal state, pausing for human approval and stopping safely on failure.

### REQ-E2.1
WHEN a workflow run is created,
THEN `WorkflowOrchestrator.create_run(workflow_id, actor)` MUST validate the `WorkflowTemplate`, persist the `WorkflowRun` (status `pending`, `template_version` recorded) and all `WorkflowStepRun` rows in one transaction, and write an audit event `run_created` with `actor` from `Settings.LOCAL_OPERATOR_ID`.

**Acceptance Criteria:**
E2.1.1 — `create_run` is atomic (all-or-nothing); a failure mid-creation leaves no partial run/step rows.
E2.1.2 — `run_created` audit entry carries `template_version`, `step_count`, `actor_id`.
E2.1.3 — `actor_id` equals `Settings.LOCAL_OPERATOR_ID` and is never read from the request body.

### REQ-E2.2
WHEN eligible execution is started or resumed,
THEN `WorkflowOrchestrator.start_or_resume(run_id, actor)` MUST select every step whose dependencies are `SUCCEEDED` and whose own status is `PENDING`, transition each to `READY` (PENDING → READY), and dispatch each `READY` step whose `executor_id` is registered to its `Executor` (READY → RUNNING) within a bounded per-run concurrency limit. Steps requiring approval (`approvable == true` with a pending gate) MUST NOT be dispatched; they transition `READY → WAITING_APPROVAL` and an `ApprovalRequest` is created (REQ-E3.2).

**Acceptance Criteria:**
E2.2.1 — A run with two independent root steps dispatches both (subject to the concurrency limit); a run with a linear chain dispatches only the first.
E2.2.2 — A step with `approvable == true` reaches `WAITING_APPROVAL` and is NOT dispatched; an `ApprovalRequest` bound to the step exists with `status = "pending"`.
E2.2.3 — A step whose `executor_id` is not registered transitions `READY → FAILED` with `code = "EXECUTOR_NOT_FOUND"` and the run stops safely (REQ-E4.4); no dispatch is attempted.
E2.2.4 — The run's Phase 1 `status` is derived to `running` while any step is `READY`/`RUNNING`, `waiting_approval` while any step is `WAITING_APPROVAL`, and remains derivable after recovery (REQ-E4.3).

### REQ-E2.3
WHEN a step succeeds,
THEN the orchestrator MUST persist the executor's `StepExecutionResult` (`output_json`, `artifact_refs_json`, `result_status`) to the step row, transition the step `RUNNING → SUCCEEDED`, set `completed_at`, write `step_succeeded`, and re-evaluate dependents for `READY` eligibility, advancing the run. No executor writes to the database directly.

**Acceptance Criteria:**
E2.3.1 — After the terminal step `SUCCEEDED`, the run transitions to Phase 1 `completed` and `completed_at` is set on the run.
E2.3.2 — `output_json`/`artifact_refs_json` are persisted only on `SUCCEEDED`; the executor return value is the sole source.
E2.3.3 — An audit `step_succeeded` entry is written with `step_key`, `step_version`, `result_status`, `attempt`.

### REQ-E2.4
WHEN an approval is required,
THEN the orchestrator MUST transition the gated step `READY → WAITING_APPROVAL`, create an `ApprovalRequest` bound to `workflow_run_id`, `workflow_step_run_id`, `operation` (`protected_operation`), `parameters_hash` (SHA-256 of the canonical artifact/parameters), `actor_id`, and write `approval_requested`. The run is derived to `waiting_approval`.

**Acceptance Criteria:**
E2.4.1 — The `ApprovalRequest` carries `operation`, `parameters_hash`, `actor_id`, `workflow_step_run_id` (all non-null for Phase 2 gates).
E2.4.2 — `approval_requested` audit entry includes `operation`, `parameters_hash`, `step_key`.
E2.4.3 — While a step is `WAITING_APPROVAL`, the orchestrator dispatches no further protected action for that step.

### REQ-E2.5
WHEN an approval is resolved,
THEN `ApprovalService.resolve` (Phase 1, extended) MUST verify the approval is `pending`, set `status` to `approved`/`rejected` and `resolved_at`/`resolved_by`, and notify the orchestrator: on `approved` the gated step transitions `WAITING_APPROVAL → READY` (re-eligible for dispatch) and the approval is marked for single-use consumption (REQ-E3.3); on `rejected` the step transitions to `CANCELLED` and the run to Phase 1 `cancelled`.

**Acceptance Criteria:**
E2.5.1 — `approved` resumes the step to `READY`; `rejected` cancels the step and the run.
E2.5.2 — Resolving an already-resolved approval returns HTTP 409 `APPROVAL_ALREADY_RESOLVED` (Phase 1 behavior preserved).
E2.5.3 — Resolving an `expired` approval returns HTTP 409 `APPROVAL_EXPIRED`.

### REQ-E2.6
WHEN a step fails,
THEN the orchestrator MUST transition the step `RUNNING → FAILED`, persist `error_json` (structured error from the executor), set `completed_at`, write `step_failed`, and stop the run safely: no further steps are dispatched; dependents are left non-`READY`; the run transitions to Phase 1 `failed` with `error_message`. Bounded retries apply only to safe, idempotent operations (REQ-E4.7); ambiguous external writes are never retried automatically (Wave 1 has no external writes; the rule is specified for when they arrive).

**Acceptance Criteria:**
E2.6.1 — A failing terminal step sets run `failed` and `error_message`.
E2.6.2 — Dependents of a `FAILED` step never become `READY`.
E2.6.3 — `step_failed` audit entry carries `step_key`, `error_code`, `error_category`, `attempt`.

### REQ-E2.7
WHEN a run is cancelled,
THEN `WorkflowOrchestrator.cancel(run_id, actor)` MUST transition every non-terminal step (`READY`/`RUNNING`/`WAITING_APPROVAL`/`INTERRUPTED`/`PENDING`) to `CANCELLED`, request cooperative cancellation of any in-flight executor call, transition the run to Phase 1 `cancelled`, and write `run_cancelled` with `actor`. Terminal steps (`SUCCEEDED`/`FAILED`/`CANCELLED`) are not mutated.

**Acceptance Criteria:**
E2.7.1 — Cancelling a run with one `RUNNING` and one `PENDING` step sets both to `CANCELLED` and the run to `cancelled`.
E2.7.2 — Already-`SUCCEEDED` steps remain `SUCCEEDED`.
E2.7.3 — `run_cancelled` audit entry includes `actor_id`, `cancelled_step_count`.

### REQ-E2.8
WHEN the orchestrator interacts with executors,
THEN the interface MUST be a one-way call `Executor.execute(context: ExecutionContext) -> StepExecutionResult` where the executor receives an immutable `ExecutionContext` (no DB handle, no run-state mutation capability) and returns a pure result; the orchestrator owns all persistence, state transitions, leases, and audit. Executors MUST NOT import or call repositories, services, or the orchestrator.

**Acceptance Criteria:**
E2.8.1 — The `Executor` Protocol and `ExecutionContext`/`StepExecutionResult` Pydantic models are defined in `src/devflow_api/executors/base.py` (new).
E2.8.2 — `mypy --strict` passes for the executor contract package.
E2.8.3 — No executor module imports `devflow_api.repositories`, `devflow_api.services`, or `devflow_api.models` (enforced by a test using `importlib`/AST checks).

---

## Area E3 — Approval Checkpoints

**Scope note (maps to task W1.3):** durable, digest-bound, single-use approval gates that do not auto-authorize later or unrelated actions.

### REQ-E3.1
WHEN a Phase 2 approval checkpoint is defined,
THEN the four protected operations MUST be enumerated as `ApprovalOperation` literals: `specification_approval`, `implementation_authorization`, `pr_creation_approval`, `merge_approval`. An `ApprovalRequest` created for a Phase 2 gate MUST set `operation` to one of these, `parameters_hash` to the SHA-256 of the canonical artifact/parameters, `actor_id` to `Settings.LOCAL_OPERATOR_ID`, and `workflow_step_run_id` to the gated step. Phase 1 approval requests (no `operation`) remain valid and unchanged (backward compatibility).

**Acceptance Criteria:**
E3.1.1 — `operation`, `parameters_hash`, `actor_id`, `workflow_step_run_id`, `consumed_at` columns are added to `approval_requests` by migration 008; all are nullable for backward compatibility with Phase 1 rows.
E3.1.2 — The `approval_requests.status` CHECK constraint remains exactly `('pending','approved','rejected','expired')` — **no `consumed` status is added**; single-use semantics are enforced via `consumed_at` (REQ-E3.3). This preserves the Phase 1 constraint and Phase 1 constraint tests.
E3.1.3 — A Phase 2 gate created without `operation` or `parameters_hash` is rejected with HTTP 422 `INVALID_APPROVAL_BINDING`.
E3.1.4 — Existing Phase 1 approval rows (created by Phase 1 code paths) continue to resolve without `operation`/`parameters_hash`/`consumed_at`; Phase 1 approval tests pass unmodified.

### REQ-E3.2
WHEN an approval is requested at a checkpoint,
THEN the artifact or parameter set being approved MUST be canonicalised identically at issuance and at consumption: `json.dumps(payload, sort_keys=True, separators=(',', ':'))` then SHA-256 hex, with documented normalization rules (strip surrounding whitespace, preserve internal content, no key reordering beyond `sort_keys`). `repo_full_name`-style server-side identity (where applicable in later waves) comes from server config, never the client.

**Acceptance Criteria:**
E3.2.1 — Issuing and consuming the same artifact yields identical `parameters_hash`.
E3.2.2 — A parameter added/removed/changed between issuance and consumption changes `parameters_hash` and consumption is rejected (REQ-E3.3).
E3.2.3 — The canonical function is a single shared implementation used at both issuance and consumption (no duplicate logic).

### REQ-E3.3
WHEN a protected action consumes an approval,
THEN `ApprovalRequest.consume_atomic(approval_id, operation, parameters_hash, workflow_step_run_id, actor_id)` MUST, inside a single `BEGIN IMMEDIATE` transaction, `UPDATE approval_requests SET consumed_at = now WHERE id = ? AND status = 'approved' AND consumed_at IS NULL AND operation = ? AND parameters_hash = ? AND workflow_step_run_id = ? AND actor_id = ?` and require `rowcount == 1`. Any mismatch (status not approved, already consumed, operation/digest/step/actor mismatch) yields `rowcount == 0` and the protected action is refused with `code = "APPROVAL_NOT_CONSUMABLE"`. An approval MUST NOT authorize a later step, a different operation, a different artifact, or a different actor.

**Acceptance Criteria:**
E3.3.1 — A second consume of the same approval returns `rowcount == 0` (replay rejected).
E3.3.2 — An approval whose `parameters_hash` differs from the action's canonical hash is rejected.
E3.3.3 — An approval bound to step `a` cannot be consumed to authorize step `b` (step-run binding enforced).
E3.3.4 — An approval bound to `operation = "pr_creation_approval"` cannot authorize `implementation_authorization`.
E3.3.5 — `actor_id` mismatch is rejected.
E3.3.6 — A `pending` (not yet resolved) approval cannot be consumed.
E3.3.7 — An `expired` approval cannot be consumed; `expired` approvals remain visible in the run's `approvals` projection (Phase 1 W1.5.4 preserved).

### REQ-E3.4
WHEN approval lifetime and staleness are managed,
THEN a `pending` approval MUST expire after `Settings.APPROVAL_TTL_SECONDS` (default e.g. 3600); expiry sets `status = "expired"` and writes `approval_expired`. A resolved (`approved`/`rejected`) approval is no longer expirable. Consumption (`consumed_at`) is terminal for authorization purposes. The local single-user trust boundary is explicit: `actor_id` is the local operator only; Wave 1 does not authenticate multiple users and MUST NOT claim to.

**Acceptance Criteria:**
E3.4.1 — A `pending` approval older than the TTL is expired by the expiry sweep and cannot be resolved to `approved`.
E3.4.2 — An `approved` approval past TTL is NOT auto-expired (it may still be consumed once); TTL governs `pending` only. (Rationale: an approved decision is the user's explicit consent; expiring it silently would force re-approval unpredictably. Documented as a deliberate decision.)
E3.4.3 — The spec and API responses MUST NOT claim multi-user authentication; `actor_id` is documented as the local operator identity.

### REQ-E3.5
WHEN run/step deletion interacts with approvals,
THEN the existing Phase 1 `approval_requests.workflow_run_id` `ON DELETE CASCADE` is preserved; deleting a run deletes its approvals (Phase 1 behavior). The new `approval_requests.workflow_step_run_id` FK uses `ON DELETE SET NULL`; because step rows are only deleted via run CASCADE (which deletes approvals first via `workflow_run_id`), the `SET NULL` path never creates an orphaned, still-consumable approval. This invariant MUST be covered by a deletion test.

**Acceptance Criteria:**
E3.5.1 — Deleting a run deletes its `ApprovalRequest` rows (cascade via `workflow_run_id`) and its `WorkflowStepRun` rows.
E3.5.2 — No code path deletes a single `WorkflowStepRun` without deleting the run; the repository exposes no such method (enforced by absence + a guard test).
E3.5.3 — An approval bound to a deleted run is gone; there is no NULL-to-NULL bypass (Phase 1 MCP/GitHub pattern) because approvals CASCADE rather than SET NULL on the run FK.

---

## Area E4 — Execution Lifecycle and Recovery

**Scope note (maps to task W1.4):** the eight-state step lifecycle, valid transitions, terminal states, restart recovery, duplicate-dispatch prevention, leases, timeouts, cancellation, bounded retries, idempotency, stale detection, and audit — all SQLite-safe.

### REQ-E4.1
WHEN step execution state is modelled,
THEN `WorkflowStepRun.status` MUST be constrained to exactly eight values: `PENDING`, `READY`, `RUNNING`, `WAITING_APPROVAL`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `INTERRUPTED`. Terminal states are `SUCCEEDED`, `FAILED`, `CANCELLED`. `INTERRUPTED` is non-terminal and recoverable. The run-level `WorkflowRun.status` keeps the Phase 1 six values (`pending`,`running`,`waiting_approval`,`completed`,`failed`,`cancelled`) unchanged and is derived from step states.

**Acceptance Criteria:**
E4.1.1 — The `workflow_step_runs.status` CHECK constraint lists exactly the eight values.
E4.1.2 — The `workflow_runs.status` CHECK constraint is unchanged from migration 003 (six values); migration 008 does not alter it.
E4.1.3 — `INTERRUPTED` is documented as non-terminal and recoverable (REQ-E4.8).

### REQ-E4.2
WHEN transitions are validated,
THEN the allowed transition map MUST be:

| From → To | Allowed | Trigger |
|---|---|---|
| PENDING → READY | yes | dependencies SUCCEEDED (orchestrator) |
| PENDING → CANCELLED | yes | run cancel |
| READY → RUNNING | yes | dispatch (CAS, lease acquired) |
| READY → WAITING_APPROVAL | yes | approvable gate reached |
| READY → CANCELLED | yes | run cancel |
| RUNNING → SUCCEEDED | yes | executor success |
| RUNNING → FAILED | yes | executor failure / timeout |
| RUNNING → INTERRUPTED | yes | restart recovery: lease expired |
| RUNNING → CANCELLED | yes | run cancel (cooperative) |
| WAITING_APPROVAL → READY | yes | approval approved |
| WAITING_APPROVAL → CANCELLED | yes | approval rejected / run cancel |
| INTERRUPTED → READY | yes | recovery: safe retry eligible |
| INTERRUPTED → FAILED | yes | recovery: ambiguous, no auto-retry |
| INTERRUPTED → CANCELLED | yes | run cancel |
| SUCCEEDED/FAILED/CANCELLED → * | no | terminal |

All other transitions MUST be rejected with `INVALID_STEP_TRANSITION`.

**Acceptance Criteria:**
E4.2.1 — Each allowed transition is exercised by a named test; each disallowed transition is exercised by a negative test that asserts no row mutation and an audit `step_transition_rejected`.
E4.2.2 — `PENDING → RUNNING` (skipping READY) is rejected.
E4.2.3 — `SUCCEEDED → RUNNING` (reviving a terminal step) is rejected.

### REQ-E4.3
WHEN the application restarts,
THEN a recovery routine MUST run at startup: it MUST scan `workflow_step_runs` for rows with `status = "RUNNING"` whose `lease_expires_at <= now` (or `lease_owner` is stale), transition each to `INTERRUPTED`, write `step_interrupted` with the prior `lease_owner`/`lease_expires_at`, and re-evaluate the run. Runs with no `RUNNING`/`WAITING_APPROVAL` steps are left to their terminal/derived state. The recovery MUST be idempotent (running it twice produces the same state).

**Acceptance Criteria:**
E4.3.1 — A step stuck `RUNNING` with an expired lease becomes `INTERRUPTED` on recovery; a second recovery run leaves it `INTERRUPTED` (idempotent).
E4.3.2 — A step `RUNNING` with a still-valid lease is NOT interrupted (a live worker owns it).
E4.3.3 — `step_interrupted` audit entry carries `prior_lease_owner`, `prior_lease_expires_at`.
E4.3.4 — A run whose only in-flight step became `INTERRUPTED` is re-derived to `running` (recoverable), not `failed`, until the re-evaluation decides retry-or-fail (REQ-E4.8).

### REQ-E4.4
WHEN execution fails and the run must stop safely,
THEN the orchestrator MUST NOT dispatch any new step after a `FAILED` step; dependent steps MUST remain non-`READY`; already-`RUNNING` independent steps are allowed to complete (no hard kill of safe in-process work) unless the run is cancelled; the run transitions to Phase 1 `failed`. The stop is "safe": no partial external commit is forced and no state is lost.

**Acceptance Criteria:**
E4.4.1 — After a `FAILED` step, `start_or_resume` dispatches no further steps for that run.
E4.4.2 — Independent `RUNNING` steps complete and record their own terminal state.
E4.4.3 — The run `error_message` is set and `failed` is terminal.

### REQ-E4.5
WHEN a step errors,
THEN `error_json` MUST be a structured object with `code: str`, `category: str` (`executor` | `timeout` | `cancelled` | `input_resolution` | `internal`), `message: str`, `retryable: bool`, `attempt: int`. `result_status` records the executor's declared outcome (`succeeded` | `failed` | `cancelled` | `indeterminate`). `INDETERMINATE` outcomes (REQ-E6.6) are treated as `FAILED` for state purposes but flagged so they are never auto-retried.

**Acceptance Criteria:**
E4.5.1 — A timeout produces `category = "timeout"`, `retryable = true` only for safe/idempotent steps.
E4.5.2 — An `indeterminate` outcome is persisted with `result_status = "indeterminate"` and `retryable = false`.
E4.5.3 — `error_json` is never set on `SUCCEEDED` steps.

### REQ-E4.6
WHEN duplicate dispatch is attempted,
THEN the `READY → RUNNING` transition MUST be a single CAS `UPDATE workflow_step_runs SET status='RUNNING', lease_owner=?, lease_expires_at=?, dispatched_at=?, started_at=? WHERE id=? AND status='READY'` inside `BEGIN IMMEDIATE`; exactly one concurrent caller observes `rowcount == 1` and proceeds; all others observe `rowcount == 0` and raise `StepDispatchConflict` without mutating state.

**Acceptance Criteria:**
E4.6.1 — Two concurrent `dispatch` calls on the same `READY` step: one succeeds, one raises `StepDispatchConflict`; the step has exactly one `lease_owner`.
E4.6.2 — The CAS uses `BEGIN IMMEDIATE`; the test asserts the transaction mode (via a spy or documented invariant).
E4.6.3 — A `lease_owner` that has expired allows a fresh `INTERRUPTED → READY → RUNNING` re-dispatch.

### REQ-E4.7
WHEN bounded retries are configured,
THEN a safe, idempotent step (`retry_policy.max_attempts > 1` and `retry_policy.safe == true`) that fails with a retryable error MAY be re-dispatched up to `max_attempts` times, incrementing `attempt` and writing `step_retry_scheduled` each time. Ambiguous external writes (`retry_policy.safe == false` or `result_status == "indeterminate"`) MUST NOT be retried automatically; they require human intervention (step stays `FAILED`/`INTERRUPTED` with `retryable = false`).

**Acceptance Criteria:**
E4.7.1 — A safe step with `max_attempts = 3` that fails twice then succeeds reaches `SUCCEEDED` with `attempt = 2`.
E4.7.2 — A safe step that exhausts `max_attempts` reaches `FAILED`.
E4.7.3 — An unsafe/indeterminate step is never auto-retried even if `max_attempts > 1`.
E4.7.4 — Wave 1's mock executor is the only executor and is declared `safe = true`, so retries are exercisable in Wave 1 without external writes.

### REQ-E4.8
WHEN recovery decides retry-or-fail for an `INTERRUPTED` step,
THEN the recovery routine MUST transition `INTERRUPTED → READY` only when the step is safe and idempotent (`retry_policy.safe == true`) and `attempt < max_attempts`; otherwise `INTERRUPTED → FAILED` with `category = "internal"`, `retryable = false`, requiring human action. The decision and its reason MUST be audited as `step_recovery_decided`.

**Acceptance Criteria:**
E4.8.1 — A safe `INTERRUPTED` step under its attempt budget goes `INTERRUPTED → READY` and is re-dispatched.
E4.8.2 — A safe `INTERRUPTED` step at `attempt == max_attempts` goes `INTERRUPTED → FAILED`.
E4.8.3 — An unsafe `INTERRUPTED` step goes `INTERRUPTED → FAILED` regardless of attempt budget.
E4.8.4 — `step_recovery_decided` audit entry carries `decision` (`retry` | `fail`), `reason`.

### REQ-E4.9
WHEN idempotency is required,
THEN each dispatch MUST carry an idempotency key `f"{run_id}:{step_key}:{attempt}"` and an input digest (`SHA-256` of canonical `input_json`); a re-dispatch with the same key and input digest for a safe step MUST produce the same persisted result where the executor supports it (the mock executor is deterministic; real executors declare idempotency in their contract, REQ-E5.x). Non-idempotent steps MUST NOT be retried (REQ-E4.7).

**Acceptance Criteria:**
E4.9.1 — Re-running the same safe step with identical input produces an identical `output_json` (mock executor deterministic).
E4.9.2 — The idempotency key and input digest are persisted on the step row and appear in audit entries.
E4.9.3 — A changed input digest between attempts is audited and, for non-idempotent steps, blocks retry.

### REQ-E4.10
WHEN stale execution is detected,
THEN a heartbeat/lease model MUST mark a `RUNNING` step stale when `lease_expires_at <= now`; the lease is renewed by the executing worker via a bounded CAS heartbeat (`UPDATE ... SET lease_expires_at = ? WHERE id = ? AND status = 'RUNNING' AND lease_owner = ?`). A lease owned by a cancelled run MUST NOT be renewed.

**Acceptance Criteria:**
E4.10.1 — A heartbeat from the owning worker extends `lease_expires_at`; a heartbeat from a non-owner is rejected (`rowcount == 0`).
E4.10.2 — A cancelled run's `RUNNING` step rejects heartbeat renewal.
E4.10.3 — Stale detection (lease expiry) feeds REQ-E4.3 recovery.

---

## Area E5 — Executor Contracts

**Scope note (maps to task W1.5):** a versioned executor interface and the one safe executor Wave 1 ships.

### REQ-E5.1
WHEN an executor is registered,
THEN it MUST implement the `Executor` Protocol with: `identifier: ExecutorIdentifier` (id + version), `capabilities: list[Capability]` (declared operations/tools), `input_schema: type[BaseModel]`, `output_schema: type[BaseModel]`, `timeout_policy: TimeoutPolicy`, and `async def execute(context: ExecutionContext) -> StepExecutionResult`. The orchestrator MUST select an executor by `executor_id` and refuse dispatch for unregistered ids.

**Acceptance Criteria:**
E5.1.1 — `ExecutorIdentifier`, `Capability`, `ExecutionContext`, `StepExecutionResult`, `TimeoutPolicy` are Pydantic v2 models / dataclasses in `src/devflow_api/executors/base.py`; `mypy --strict` passes.
E5.1.2 — Dispatching an unregistered `executor_id` fails the step `READY → FAILED` with `EXECUTOR_NOT_FOUND` (REQ-E2.2.3).
E5.1.3 — An executor whose declared `Capability` does not match the step's `tool_selection` is not selected (capability negotiation test).

### REQ-E5.2
WHEN an executor executes,
THEN it MUST receive an `ExecutionContext` containing `run_id`, `step_run_id`, `step_key`, `step_version`, `inputs` (resolved), `tool_selection`, `working_directory` (approved dir or `None`), `env_allowlist` (explicit dict, never the parent environment), `timeout_s`, `cancellation: CancellationHandle`, `actor_id`, `idempotency_key`, `input_digest`, and `attempt`. It MUST return a `StepExecutionResult` with `outcome` (`succeeded`|`failed`|`cancelled`|`indeterminate`), `output` (validated against `output_schema`), `artifact_refs: list[ArtifactRef]`, `error: StructuredError | None`, `metadata: ExecutionMetadata` (logs, durations, executor version).

**Acceptance Criteria:**
E5.2.1 — `ExecutionContext.working_directory` is either `None` or a member of `Settings.APPROVED_WORKING_DIRECTORIES`; executors MUST NOT write outside it.
E5.2.2 — `ExecutionContext.env_allowlist` is an explicit dict; executors MUST NOT read `os.environ` directly (enforced by test + lint where feasible).
E5.2.3 — A result whose `output` fails `output_schema` validation is treated as `outcome = "failed"` with `category = "executor"`.
E5.2.4 — `artifact_refs` are references (paths/digests), never inlined large payloads.

### REQ-E5.3
WHEN a timeout or cancellation occurs,
THEN the orchestrator MUST enforce `timeout_s` and pass a `CancellationHandle`; an executor MUST observe cancellation cooperatively and return `outcome = "cancelled"` (or be marked `failed`/`interrupted` by the orchestrator if it does not return within a grace period). Cancellation MUST NOT leave external state partially committed (Wave 1 has no external writes; the contract is specified for later waves).

**Acceptance Criteria:**
E5.3.1 — A step exceeding `timeout_s` is transitioned `RUNNING → FAILED` with `category = "timeout"` (or `INTERRUPTED` if the process died, per recovery).
E5.3.2 — A cancelled executor call returns `outcome = "cancelled"` and the step reaches `CANCELLED`.
E5.3.3 — An executor that ignores cancellation beyond the grace period is force-marked `INTERRUPTED` and recovery applies (REQ-E4.8).

### REQ-E5.4
WHEN Wave 1 validates the engine,
THEN exactly one executor MUST ship: `MockExecutor` (`identifier.id = "mock"`, `version = 1`), a pure in-process no-op that echoes its inputs into `output`, sleeps a configurable short duration, observes the `CancellationHandle`, produces a deterministic `ArtifactRef` (digest of a constant), declares `safe = true` and `idempotent = true`, uses no working directory, no environment, and no subprocess. No other executor and no shell/command execution MUST exist in Wave 1.

**Acceptance Criteria:**
E5.4.1 — `MockExecutor` is the only executor registered by default; `registry.list_executors()` returns exactly `["mock"]` in Wave 1.
E5.4.2 — `MockExecutor` performs no filesystem, network, or subprocess access (asserted by a sandbox-leak test).
E5.4.3 — No module under `src/devflow_api/executors/` invokes `subprocess`, `os.system`, `os.exec*`, or `shell=True` (asserted by a grep/AST guard test).
E5.4.4 — `MockExecutor` is deterministic: identical inputs → identical `output_json` and `artifact_refs`.

---

## Area E6 — Security Architecture

**Scope note (maps to task W1.6):** the local-first execution boundary and the honest statement of what is and is not isolated.

### REQ-E6.1
WHEN the API is exposed,
THEN all FastAPI/Uvicorn and Streamlit services MUST bind exclusively to `127.0.0.1` (Phase 0/1 constraint preserved); Wave 1 adds no network listener beyond the existing loopback services.

**Acceptance Criteria:**
E6.1.1 — No Wave 1 configuration binds to `0.0.0.0` or a non-loopback interface (config test).
E6.1.2 — Executor dispatch happens in-process over the loopback API only; no remote executor protocol in Wave 1.

### REQ-E6.2
WHEN an executor operates,
THEN it MUST be restricted to `Settings.APPROVED_WORKING_DIRECTORIES` (an explicit allowlist; empty by default). Paths outside the allowlist MUST be refused. `MockExecutor` uses no working directory. The spec MUST document that this is application-level path checking, not OS-enforced filesystem isolation.

**Acceptance Criteria:**
E6.2.1 — An `ExecutionContext.working_directory` not in the allowlist is rejected before dispatch (`code = "WORKING_DIRECTORY_NOT_APPROVED"`).
E6.2.2 — The default allowlist is empty; `MockExecutor` dispatches with `working_directory = None`.
E6.2.3 — A documentation note states this is not OS-level filesystem sandboxing.

### REQ-E6.3
WHEN environment variables are passed to any (future) subprocess,
THEN only `Settings.EXECUTOR_ENV_ALLOWLIST` variables are forwarded via an explicit `env` dict; there MUST be no implicit parent-environment inheritance (`get_default_environment()` / `os.environ` MUST NOT be merged). Required system variables (e.g., `PATH`, `SYSTEMROOT`, `WINDIR` on Windows) are added explicitly and minimally only when a subprocess exists — Wave 1 has no subprocess, so this is contractual only.

**Acceptance Criteria:**
E6.3.1 — The executor contract forbids `os.environ` reads in executor implementations (test + lint).
E6.3.2 — The spec explicitly states env-var scoping is Python-level, not OS sandboxing (no claim of OS-level isolation).
E6.3.3 — When subprocesses arrive in later waves, the explicit-env contract from Phase 1's MCP transport (W4-CR) is reused, not reinvented.

### REQ-E6.4
WHEN credentials appear,
THEN `RedactSecretsProcessor` (Phase 1) MUST run on every log record; no credential, token, or secret MUST appear in logs or audit payloads. `parameters_hash` stores a digest, never the secret material.

**Acceptance Criteria:**
E6.4.1 — A test asserts no token/secret substring appears in log records or `workflow_audit_log.payload_json` for a gated action (named `test_no_secret_in_audit_or_logs`).
E6.4.2 — `parameters_hash` is a SHA-256 hex digest; the raw parameters are stored in `payload_json` only for non-secret artifacts and redaction applies.

### REQ-E6.5
WHEN approval enforcement is evaluated,
THEN every protected action MUST require a consumed, digest-bound, single-use `ApprovalRequest` (REQ-E3.3); credential presence MUST NOT be treated as authorization; an approval MUST NOT authorize a later, different, or unrelated action.

**Acceptance Criteria:**
E6.5.1 — A protected action without a consumable approval is refused (`APPROVAL_NOT_CONSUMABLE`).
E6.5.2 — A consumed approval cannot authorize a second action (replay rejected).
E6.5.3 — An approval for operation `merge_approval` cannot authorize `pr_creation_approval`.

### REQ-E6.6
WHEN an external action outcome is indeterminate,
THEN the spec MUST define `INDETERMINATE` (5xx/transport errors for future external calls) as NOT auto-retried and NOT auto-restoring any consumed approval; reconciliation requires a fresh approval. Wave 1 has no external calls, so this is specified contractually for Waves 2–4 and exercised by the mock executor's `indeterminate` test mode.

**Acceptance Criteria:**
E6.6.1 — `MockExecutor` has a test mode returning `outcome = "indeterminate"`; the step is `FAILED` with `retryable = false` and the approval (if any) is not restored.
E6.6.2 — A fresh approval is required before any retry of an indeterminate action.
E6.6.3 — The mock executor's `indeterminate` mode does not perform any external write (no side effect to reconcile).

### REQ-E6.7
WHEN audit integrity is considered,
THEN `WorkflowAuditLog` MUST remain append-only (Phase 1); Wave 1 MUST NOT add update/delete paths to audit rows. The spec MUST document that Phase 1/2 audit is append-only but not cryptographically signed/tamper-evident; a future wave may add chained hashes. No false claim of cryptographic integrity MUST be made.

**Acceptance Criteria:**
E6.7.1 — No `UPDATE`/`DELETE` is issued against `workflow_audit_log` in any Wave 1 code path (asserted by a repository-shape test).
E6.7.2 — The spec documents the integrity posture honestly (append-only, not signed).

### REQ-E6.8
WHEN the boundary before real coding-agent execution is documented,
THEN the spec MUST list the additional isolation required before any real coding-agent (Codex/Kiro) or shell execution is enabled: OS-level process isolation, filesystem allowlists enforced by the OS, network egress control, resource limits (CPU/memory/time), and a credential vault. Wave 1 MUST NOT enable such execution and MUST gate it behind an explicit, separate future wave.

**Acceptance Criteria:**
E6.8.1 — The design document lists the isolation prerequisites (REQ-E6.8) in a dedicated section.
E6.8.1 — No Wave 1 code path enables real coding-agent or shell execution (guard test, REQ-E5.4.3).

---

## Area E7 — API and Streamlit Contracts

**Scope note (maps to task W1.7):** minimal APIs for observing and driving execution; full UX is Wave 5.

### REQ-E7.1
WHEN a client creates a run,
THEN `POST /api/v1/workflows/{id}/runs` MUST create the run and all step rows (REQ-E2.1) and return HTTP 201 with the run and its initial steps. An invalid template returns HTTP 422 `INVALID_WORKFLOW_TEMPLATE`.

### REQ-E7.2
WHEN a client starts or resumes execution,
THEN `POST /api/v1/workflow-runs/{run_id}/start` MUST invoke `WorkflowOrchestrator.start_or_resume` and return HTTP 200 with the updated run and step states. Starting an already-terminal run returns HTTP 409 `RUN_NOT_STARTABLE`.

### REQ-E7.3
WHEN a client cancels a run,
THEN `POST /api/v1/workflow-runs/{run_id}/cancel` MUST invoke `WorkflowOrchestrator.cancel` and return HTTP 200 with the cancelled run. Cancelling an already-terminal run is idempotent (HTTP 200, no mutation).

### REQ-E7.4
WHEN a client inspects a run,
THEN `GET /api/v1/workflow-runs/{run_id}` MUST return the run plus `steps: list[StepRunResponse]` (ordered, with status, timestamps, `step_version`, `tool_selection`, `result_status`, `error`), and the existing Phase 1 `approvals`/`pending_approvals` projections (W1.5.4) preserved. `GET /api/v1/workflow-runs/{run_id}/steps/{step_id}` returns a single step including `output_json` and `artifact_refs` for `SUCCEEDED` steps and `error_json` for `FAILED` steps.

**Acceptance Criteria:**
E7.4.1 — `WorkflowRunResponse.steps` is ordered by template order; empty list `[]` never `null`.
E7.4.2 — `approvals` and `pending_approvals` behave exactly as Phase 1 (W1.5.4a–c) — backward compatible.
E7.4.3 — `output_json`/`error_json` are `null` until the step reaches the relevant terminal state.

### REQ-E7.5
WHEN a client reads audit events,
THEN `GET /api/v1/workflow-runs/{run_id}/audit` MUST return ordered audit entries for the run (Phase 1 `WorkflowAuditLog`, extended event types). Pagination via `limit`/`offset` is supported.

### REQ-E7.6
WHEN a client approves or rejects a gate,
THEN `POST /api/v1/approvals/{id}/resolve` (Phase 1, extended) with `{"decision": "approved"|"rejected", "resolved_by": ...}` MUST validate the approval is `pending`, bind/verify `operation`/`parameters_hash`/`workflow_step_run_id`/`actor_id` consistency on consumption (the consume happens when the protected action executes, REQ-E3.3), and resume or cancel the gated step (REQ-E2.5). HTTP 409 `APPROVAL_ALREADY_RESOLVED` / `APPROVAL_EXPIRED` preserved.

### REQ-E7.7
WHEN the Streamlit UI observes execution,
THEN the existing `6_Workflows.py` page MUST be extended minimally to show a run's step list with live status, a "Start/Resume" button, a "Cancel" button, and an approval affordance for `WAITING_APPROVAL` steps (calls the existing approvals API). The full dashboard, filtering, and rich UX are deferred to Wave 5.

**Acceptance Criteria:**
E7.7.1 — `6_Workflows.py` renders run + steps without exception when the backend is available (`AppTest` with mocked `APIClient`).
E7.7.1b — A "Backend unavailable" notice (not an exception) is shown when the backend is unreachable (Phase 1 pattern preserved).
E7.7.2 — Start/Resume and Cancel buttons call the correct endpoints.
E7.7.3 — No fabricated/hard-coded run or step data.
E7.7.4 — `mypy --strict src/devflow_ui/pages/6_Workflows.py` exits with code 0.

### REQ-E7.8
WHEN OpenAPI is regenerated,
THEN `docs/openapi.json` MUST be regenerated to include the new endpoints (`/workflow-runs/{run_id}/start`, `/cancel`, `/audit`, `/steps/{step_id}`) and the extended `WorkflowRunResponse.steps`; no `/merge` endpoint is introduced (Phase 1 exclusion preserved).

---

## Area E8 — Testing and Acceptance Criteria

**Scope note (maps to task W1.8):** the automated test matrix and quality gates. Named tests below are the minimum required set; the implementation MAY add more.

### REQ-E8.1
WHEN the test suite runs,
THEN it MUST cover valid and invalid state transitions (REQ-E4.2), dependency ordering (REQ-E1.3), approval enforcement and replay prevention (REQ-E3.3), concurrent execution and duplicate-dispatch prevention (REQ-E4.6), process interruption and recovery (REQ-E4.3, E4.8), cancellation (REQ-E2.7), timeouts (REQ-E5.3), idempotency (REQ-E4.9), SQLite transaction rollback (REQ-E2.1, E4.6), audit logging (all), API validation (REQ-E7.x), mock executor behavior (REQ-E5.4), and backward compatibility with Phase 1.

**Required named tests (minimum set):**

State & transitions:
- `test_step_pending_to_ready_requires_dependencies_succeeded`
- `test_step_skip_ready_to_running_rejected`
- `test_step_terminal_state_revival_rejected`
- `test_invalid_transition_writes_rejection_audit_and_no_mutation`

Dependencies:
- `test_linear_chain_dispatches_in_order`
- `test_diamond_dependency_gates_until_all_succeeded`
- `test_failed_dependency_blocks_dependents`

Approvals:
- `test_approval_consumed_once_replay_rejected`
- `test_approval_parameter_digest_mismatch_rejected`
- `test_approval_bound_to_step_a_cannot_authorize_step_b`
- `test_approval_operation_mismatch_rejected`
- `test_approval_actor_mismatch_rejected`
- `test_pending_approval_not_consumable`
- `test_expired_approval_not_consumable`
- `test_expired_pending_approval_cannot_be_promoted_to_approved`

Concurrency & duplicate dispatch:
- `test_concurrent_dispatch_only_one_succeeds`
- `test_cas_uses_begin_immediate`
- `test_heartbeat_only_owner_renews_lease`
- `test_cancelled_run_rejects_heartbeat`

Recovery:
- `test_running_step_with_expired lease_becomes_interrupted`
- `test_recovery_idempotent`
- `test_recovery_safe_step_retries_under_budget`
- `test_recovery_unsafe_step_fails`
- `test_recovery_step_at_max_attempts_fails`

Cancellation:
- `test_cancel_run_marks_non_terminal_steps_cancelled`
- `test_cancel_run_keeps_succeeded_steps`
- `test_cancel_idempotent_on_terminal_run`

Timeouts:
- `test_step_timeout_marks_failed`
- `test_executor_ignoring_cancel_marked_interrupted`

Idempotency:
- `test_mock_executor_deterministic_output`
- `test_input_digest_change_blocks_retry_for_non_idempotent`

SQLite transactions:
- `test_run_creation_atomic_rollback`
- `test_cas_update_rolls_back_on_zero_rowcount`

Audit:
- `test_every_transition_writes_audit`
- `test_audit_append_only_no_update_delete`
- `test_no_secret_in_audit_or_logs`

API:
- `test_create_run_invalid_template_422`
- `test_start_terminal_run_409`
- `test_cancel_terminal_run_idempotent_200`
- `test_run_response_includes_steps_and_approvals_projection`
- `test_audit_endpoint_pagination`

Mock executor:
- `test_mock_executor_only_registered_executor`
- `test_mock_executor_no_fs_network_subprocess`
- `test_no_shell_execution_in_executors_package`

Backward compatibility (Phase 1):
- `test_phase1_workflow_crud_still_works`
- `test_phase1_approval_resolve_still_works_without_operation`
- `test_phase1_run_status_constraint_unchanged`
- `test_approval_status_constraint_unchanged_no_consumed_value`

Security negatives:
- `test_working_directory_outside_allowlist_rejected`
- `test_env_allowlist_no_parent_inheritance_contract`
- `test_indeterminate_outcome_not_retried_and_approval_not_restored`
- `test_no_automatic_pr_merge_endpoint_absent`

Migrations:
- `test_migration_008_upgrade_creates_step_runs_and_extends_approvals`
- `test_migration_008_downgrade_restores_prior_schema`
- `test_full_round_trip_001_to_008`

### REQ-E8.2
WHEN quality gates run,
THEN `ruff check .`, `mypy --strict src/`, `pytest --cov=src --cov-branch --cov-fail-under=80` MUST all exit 0; `alembic upgrade head` reaches `008_add_workflow_execution_engine`; `alembic downgrade -1` returns to `007_add_github_confirmations`; and `docs/openapi.json` is regenerated. Phase 0 and Phase 1 tests continue to pass.

### REQ-E8.3
WHEN migration upgrade/downgrade is tested,
THEN migration 008 MUST be reversible: `upgrade` creates `workflow_step_runs` and adds the `approval_requests` columns/indexes; `downgrade` drops them and restores the prior schema exactly, including the unchanged `approval_requests.status` CHECK constraint.

---

## Traceability Matrix (requirements → task area → design section)

| Requirement | Task area (W1.x) | Design section |
|---|---|---|
| REQ-E1.x | W1.1 definition/execution model | §3 (data model), §4 (template model) |
| REQ-E2.x | W1.2 orchestration service | §5 (orchestration), §6 (orchestrator–executor interface) |
| REQ-E3.x | W1.3 approval checkpoints | §7 (approval binding & consumption) |
| REQ-E4.x | W1.4 lifecycle & recovery | §8 (state machine), §9 (recovery), §10 (SQLite patterns) |
| REQ-E5.x | W1.5 executor contracts | §6 (executor contract), §11 (mock executor) |
| REQ-E6.x | W1.6 security | §12 (security & threat model) |
| REQ-E7.x | W1.7 API & Streamlit | §13 (API contracts), §14 (Streamlit) |
| REQ-E8.x | W1.8 testing | §15 (test matrix), tasks.md |

---

## Assumptions, Open Decisions, Dependencies, Out-of-Scope

**Assumptions:**
- Phase 1 v1.5.9 (commit `2d077ec`) is the merged, green baseline (verified by preflight; PR #13 merged).
- The Alembic head is `007_add_github_confirmations` (verified); migration 008 chains from it. The implementer MUST re-confirm the head at implementation time and renumber if Phase 1 advanced.
- The local operator identity is `Settings.LOCAL_OPERATOR_ID` (default `'local_operator'`), reused from Phase 1 (W5-SR).
- `Workflow.definition_json` (Phase 1, deferred/raiseload) is the home for the validated `WorkflowTemplate`; no new template table is introduced (avoid duplication).

**Open decisions (left to the implementer / ChatGPT review):**
- `Settings.APPROVAL_TTL_SECONDS` default value (proposed 3600) — confirm.
- Per-run concurrency limit default (proposed 1 in Wave 1 for simplicity and determinism; mock executor is in-process) — confirm.
- Whether `approved` (not just `pending`) approvals should also be TTL-expirable (REQ-E3.4.2 deliberately says no; flagged for review).
- Lease duration and heartbeat interval defaults (proposed lease 60s, heartbeat 15s) — confirm.
- Whether to store the full `WorkflowTemplate` snapshot on the `WorkflowRun` (for replay) vs. referencing the `Workflow.definition_json` (mutability risk). Proposed: snapshot `template_version` + `definition_hash` on the run, and reject run start if the live template's hash changed since creation? Open.

**Dependencies:**
- Phase 1 models, services, routers, and migrations 001–007 (present, green).
- `Settings.LOCAL_OPERATOR_ID`, `RedactSecretsProcessor`, `UTCDateTime`, `_transaction`/`BEGIN IMMEDIATE` patterns (Phase 1).

**Out of scope (Wave 1):** all items in the Out-of-Scope table above; notably real coding-agent execution, external integrations, PR creation/merge, and the full Streamlit dashboard.

**Backward-compatibility commitments:**
- `workflow_runs.status` CHECK constraint unchanged.
- `approval_requests.status` CHECK constraint unchanged (no `consumed` value); consumption via `consumed_at`.
- Phase 1 endpoints, schemas, and audit event types preserved; Wave 1 adds new event types and endpoints only.
- Phase 1 tests pass unmodified except where an additive assertion is explicitly required (none required in Wave 1; the `consumed`-free design avoids constraint-test changes).
