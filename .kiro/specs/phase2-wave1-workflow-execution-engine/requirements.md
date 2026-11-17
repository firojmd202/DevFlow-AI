# DevFlow AI — Phase 2 Wave 1: Workflow Execution Engine Requirements

**Version:** 2.1.0
**Status:** Corrected — reconciliation pass (awaiting ChatGPT review)
**Scope:** Phase 2 Wave 1 — Workflow Execution Engine
**Branch:** `feature/phase2-wave1-workflow-execution-engine`
**Base commit:** `2d077ecb9f96ff767160e6c1564b2c6f8d4e0a9e` (Phase 1 v1.5.9, PR #13 merged)
**Last Updated:** 2026-11-17
**Supersedes:** v2.0.0 (initial). Extends `.kiro/specs/phase1-functional-orchestration/` (v1.5.9); does not modify it.

**Version history:**
- v2.0.0 — 2026-11-17 — Initial Phase 2 Wave 1 specification. See `docs/reports/phase2-wave1-spec-resolution.md` for the v2.0.0 → v2.1.0 reconciliation.
- v2.1.0 — 2026-11-17 — Reconciliation pass. Resolves 12 findings: (1) `READY → FAILED` and `PENDING → FAILED` pre-dispatch/input-resolution transitions added to the map; (2) retry split into a transient `RUNNING → READY` (never via terminal `FAILED`); (3) interruption triggers disambiguated (timeout → `FAILED`/`READY`; process death → `INTERRUPTED` via recovery only) and recovery made automatic state-reconciliation with explicit user start; (4) approval re-gating and single-use consumption races specified (fenced on lease/attempt; refused after cancel); (5) run terminal-state derived only when all steps are terminal; (6) immutable full template snapshot per run (`template_snapshot_json` + `template_version` + `template_hash` on `workflow_runs`); (7) `attempt` increments on dispatch and budget enforced consistently; (8) pending TTL (3600s) and approved authorization validity (3600s) enforced separately via columns, no `status` CHECK change; (9) lease-owner/attempt fencing for stale executor completions; (10) canonical schema-module naming (contract types in `schemas/executor.py`); (11) task-name typo and duplicate AC ID fixed; (12) negative/concurrency tests added for the corrected behavior. Resolved defaults applied (concurrency 1, lease 60s, heartbeat 15s, mandatory executor guards, immutable snapshot). Phase 1 compatibility reconciled against the actual `WorkflowService`/`ApprovalService` (run `waiting_approval` transitions go through the approval service, not `transition_run`; legacy `NULL`-template runs preserved).

---

## Overview

Phase 2 builds the end-to-end DevFlow AI workflow: a user describes a feature, DevFlow creates a workflow run, an AI provider generates specifications, Kiro verifies them through guided handoff, the AI reviews the Kiro report, the user approves, Codex CLI implements, the AI reviews the implementation, the user approves PR creation, the GitHub adapter creates and monitors the PR, and the user separately approves merging. Every operation is auditable. PR merging is never automatic.

**Wave 1 scope — Workflow Execution Engine only.** Wave 1 delivers the core engine that turns a workflow definition into durable, recoverable, approval-gated step executions. Wave 1 deliberately ships **no real coding-agent execution** and **no Kiro, Codex, OpenAI, Ollama, or GitHub integration**; a single safe mock/no-op executor validates the engine end-to-end. The six-wave Phase 2 roadmap is in `docs/planning/phase2-roadmap.md`.

Wave 1 reuses the Phase 1 persistence and authorization foundation without duplicating it:

| Phase 1 model (reused) | File | Wave 1 use |
|---|---|---|
| `Workflow` | `src/devflow_api/models/workflow.py` | Definition container; `definition_json` holds the validated `WorkflowTemplate` (ordered steps, dependencies, I/O, tool selection, versioning). No column added to `workflows`. |
| `WorkflowRun` | `src/devflow_api/models/workflow.py` | Run instance; Phase 1 six-state run status **unchanged** and derived from step states for backward compatibility. Extended additively with the immutable template snapshot columns (REQ-E1.8). |
| `ApprovalRequest` | `src/devflow_api/models/approval.py` | Human approval gate, **extended additively** with operation + parameter-digest + actor + step-run binding + single-use `consumed_at` + pending `expires_at` + approved `authorization_expires_at`. The Phase 1 `status` CHECK constraint is **not changed**. |
| `WorkflowAuditLog` | `src/devflow_api/models/audit.py` | Append-only audit; reused unchanged for every execution transition. |

Wave 1 adds **one new table** (`workflow_step_runs`), **extends** `approval_requests` additively, and **extends** `workflow_runs` additively (template snapshot), via migration 008 (planned; not authored in this specification task).

**Phase 1 service compatibility (reconciled against actual code):**
- `WorkflowService.WORKFLOW_TRANSITIONS = {"pending": {"running"}, "running": {"completed", "failed", "cancelled"}}`. `waiting_approval` is **not** in this map; Phase 1 reaches `waiting_approval` only through `ApprovalService.request_approval`/`resolve` via the lower-level `WorkflowRunRepository.transition_status`. The orchestrator follows the same split (REQ-E2.9).
- `ApprovalService.request_approval(run_id, step_name, action_description, payload)` and `resolve(approval_id, decision, resolved_by)` are preserved; Wave 1 adds `request_bound_approval(...)` and extends `resolve` additively to also transition the gated step when the approval has a `workflow_step_run_id` (REQ-E2.5, E3.1).
- `WorkflowService.create_run(workflow_id)` (Phase 1) is preserved unchanged; Wave 1's atomic run+step creation is a new orchestrator path that does **not** call it (to keep step creation atomic), and reuses the repositories and `AuditLogRepository` (REQ-E2.1).

**Phase 1 boundary carried into Wave 1:** the application remains local-first, single-user, loopback-only, free-core. The trust boundary is the local operator (`Settings.LOCAL_OPERATOR_ID`, default `'local_operator'`); Wave 1 does not introduce multi-user authentication.

### Global Constraints (apply to all requirements below)

- The application MUST remain local-first with free core functionality.
- All development services MUST bind exclusively to `127.0.0.1` on the host interface.
- The codebase MUST NOT contain Android, React, TypeScript, or Vite artefacts.
- No hardcoded credentials or secrets MUST appear in source control at any time.
- Architecture boundaries from Phase 0/1 (UI → API → domain services → repositories → SQLite; services → adapters) MUST be preserved. Schema types live under `src/devflow_api/schemas/`; executors import schemas, never the reverse (REQ-E2.8).
- Phase 0 and Phase 1 specification files MUST NOT be modified by Wave 1 implementation. Phase 1 production code is extended additively; Phase 1 tests continue to pass. The one documented exception is a single Phase 1 router-test fixture that may gain a valid template if/when the project chooses to make templated runs mandatory; the v2.1.0 design avoids that by preserving legacy `NULL`-template runs (REQ-E2.1), so no Phase 1 test requires modification.
- `datetime.utcnow()` MUST NOT appear in any Phase 2 code; use `datetime.now(UTC)` exclusively.
- All new timestamp columns MUST use the `UTCDateTime` TypeDecorator from `src/devflow_api/models/base.py`.
- Every consequential or external action MUST require an explicit, digest-bound, single-use, validity-bounded approval before execution. Approval presence is authorization; credential presence is not.
- No unrestricted shell/command execution MUST be introduced in Wave 1. Only the mock/no-op executor (REQ-E5.x) ships. Executor security guards are **mandatory** (REQ-E5.4, E6.x).
- Environment-variable scoping and working-directory allowlists are Python-level controls; they are NOT OS-level sandboxing and MUST NOT be described as such (REQ-E6.x).

### Resolved Defaults (applied throughout; from task §3)

| Setting | Default | Where |
|---|---|---|
| `Settings.APPROVAL_TTL_SECONDS` (pending approval TTL) | 3600 | REQ-E3.4 |
| `Settings.APPROVAL_AUTHORIZATION_VALIDITY_SECONDS` (approved authorization validity) | 3600 | REQ-E3.6 |
| `Settings.RUN_CONCURRENCY` (per-run step dispatch concurrency) | 1 | REQ-E2.2 |
| `Settings.STEP_LEASE_TTL_SECONDS` | 60 | REQ-E4.6 |
| `Settings.STEP_HEARTBEAT_INTERVAL_SECONDS` | 15 | REQ-E4.10 |
| Recovery | automatic state reconciliation; explicit user start for resumed execution | REQ-E4.3 |
| Executor security guards | mandatory (hard gate, not advisory) | REQ-E5.4 |
| Template per run | immutable full execution snapshot | REQ-E1.8 |

### Out of Scope for Wave 1

| Capability | Deferral reason |
|---|---|
| Real coding-agent execution (Codex CLI, Kiro, Ollama, OpenAI) | Wave 1 ships the engine + a mock executor only; integrations are Waves 2–3 |
| Unrestricted shell / arbitrary command execution | A separate safety concern; deferred past Phase 2 until OS-level isolation exists (REQ-E6.8) |
| Autonomous PR creation / merge | PR creation is Wave 4; merge is never automatic |
| Full Streamlit workflow dashboard | Wave 5; Wave 1 adds only minimal run/step observation (REQ-E7.x) |
| Multi-user access control | Local single-user tool; explicit trust boundary (REQ-E6.x) |
| OS-level process sandboxing (seccomp, namespaces, job objects) | Required before real coding-agent execution; documented as a prerequisite in REQ-E6.8, not delivered in Wave 1 |
| Changing the Phase 1 `workflow_runs.status` enum | Backward compatibility; the eight-state lifecycle lives on step runs (REQ-E4.1) |
| Renaming or restructuring Phase 1 models | Wave 1 extends additively only |

---

## Area E1 — Workflow Definition and Execution Model

**Scope note (maps to task W1.1):** the durable structure that turns a `Workflow` into ordered, executable steps with dependencies, inputs/outputs, tool selection, versioning, and durable execution state.

### REQ-E1.1
WHEN a workflow is defined for Phase 2 execution,
THEN the `Workflow.definition_json` column MUST hold a validated `WorkflowTemplate` (Pydantic v2 model) containing `template_version: int`, `steps: list[StepDefinition]` (ordered, non-empty, unique `key`), and `defaults: TemplateDefaults` (default executor id, default timeout seconds, default retry policy). The template MUST be validated when a run is created from it (REQ-E2.1); invalid templates MUST be rejected with HTTP 422 and `code = "INVALID_WORKFLOW_TEMPLATE"`. `Workflow` create/update MUST NOT validate `definition_json` (Phase 1 behavior: stored as-is).

**Acceptance Criteria:**
E1.1.1 — `WorkflowTemplate` is a Pydantic v2 model in `src/devflow_api/schemas/workflow_template.py` and is importable.
E1.1.2 — `StepDefinition` carries: `key: str`, `version: int`, `title: str`, `description: str`, `depends_on: list[str]` (step keys), `executor_id: str`, `tool_selection: ToolSelection`, `inputs: dict[str, Any] | None`, `expected_outputs: list[str] | None`, `timeout_s: int`, `retry_policy: RetryPolicy`, `approvable: bool`, `protected_operation: str | None`.
E1.1.3 — A template with a duplicate step `key`, an empty `steps` list, a `depends_on` referencing a non-existent key, or a cycle in `depends_on` MUST be rejected with HTTP 422 `INVALID_WORKFLOW_TEMPLATE` at run creation.
E1.1.4 — `mypy --strict src/devflow_api/schemas/workflow_template.py` exits with code 0.
E1.1.5 — The existing `Workflow` SQLAlchemy model is NOT modified; no column is added to `workflows`. `definition_json` remains `deferred=True, deferred_raiseload=True`.

### REQ-E1.2
WHEN a workflow run is created for execution,
THEN a `WorkflowRun` MUST be persisted with Phase 1 status `pending`, and one `WorkflowStepRun` row MUST be created per `StepDefinition` in `WorkflowTemplate.steps`, each in step status `PENDING`, with `step_key`, `step_version`, `executor_id`, `tool_selection_json`, `depends_on_json`, `workflow_run_id` (FK CASCADE), `attempt = 0` (executions attempted so far; incremented on dispatch, REQ-E4.7), and `created_at`/`updated_at` set to `datetime.now(UTC)`.

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
THEN each `WorkflowStepRun` MUST persist `input_json` when it becomes `READY` (resolved inputs) and `output_json` + `artifact_refs_json` at success; step outputs MUST be referenceable as inputs to downstream steps by `"$steps.<key>.<output_name>"` in the template `inputs` mapping, resolved by the orchestrator at the `PENDING → READY` transition (no implicit global namespace).

**Acceptance Criteria:**
E1.4.1 — A downstream step whose `inputs` references `"$steps.a.spec_doc"` resolves to the `output_json["spec_doc"]` of step `a` only when `a` is `SUCCEEDED`; otherwise the downstream step cannot become `READY`.
E1.4.2 — A missing or malformed output reference MUST fail the step at the `PENDING → READY` transition with `code = "INPUT_RESOLUTION_FAILED"`, transitioning `PENDING → FAILED` (REQ-E4.2). It never reaches `READY`.
E1.4.3 — `output_json` and `artifact_refs_json` are `None` until the step `SUCCEEDED`; they are never written for non-terminal or `FAILED` steps except `error_json` (REQ-E4.5).

### REQ-E1.5
WHEN tool selection and versioning are recorded,
THEN every `WorkflowStepRun` MUST persist `tool_selection_json` (the `ToolSelection` snapshot from the run's immutable template snapshot, REQ-E1.8) and `step_version` (the `StepDefinition.version`) at creation, so an audit reader can reconstruct which tool/version executed even if the live `Workflow.definition_json` later changes. `WorkflowTemplate.template_version` and `WorkflowStepRun.step_version` form the durable versioning record.

**Acceptance Criteria:**
E1.5.1 — Editing the `Workflow.definition_json` after a run is created does NOT alter any existing `WorkflowStepRun.tool_selection_json` or `step_version`, and does NOT alter the run's template snapshot (REQ-E1.8).
E1.5.2 — `GET .../steps/{step_id}` returns `step_version` and `tool_selection` (read-only projection).
E1.5.3 — A run created from `template_version=2` records `template_version=2` on the run; bumping the live template does not retroactively change existing runs.

### REQ-E1.6
WHEN durable execution state and timestamps are required,
THEN `WorkflowStepRun` MUST carry UTC timestamps `ready_at`, `dispatched_at`, `started_at`, `completed_at` (all nullable, `UTCDateTime`), plus `lease_owner: str | None`, `lease_expires_at: UTCDateTime | None`, `attempt: int` (default 0; executions attempted so far), `status` (eight-state, REQ-E4.1), `result_status: str | None` (executor outcome), and `error_json: str | None`. All state MUST persist to SQLite and survive process restart.

**Acceptance Criteria:**
E1.6.1 — All timestamp columns use `UTCDateTime`; no `datetime.utcnow()` anywhere in the new code (`grep -R "datetime.utcnow"` returns no matches in `src/devflow_api/models/workflow_step_run.py` and the new service).
E1.6.2 — After a simulated restart (new process, same DB), step rows and their timestamps are unchanged.
E1.6.3 — `mypy --strict` passes for the new model.

### REQ-E1.7
WHEN state transitions occur,
THEN the orchestrator MUST validate each transition against the allowed-transition map (REQ-E4.2) using a compare-and-set `UPDATE ... WHERE id = ? AND status = <expected_from>` (plus `lease_owner`/`attempt` fencing for post-dispatch transitions, REQ-E4.11) inside a `BEGIN IMMEDIATE` transaction, and MUST reject invalid transitions with `code = "INVALID_STEP_TRANSITION"` and no row mutation.

**Acceptance Criteria:**
E1.7.1 — A `PENDING → RUNNING` transition (skipping `READY`) is rejected; the row stays `PENDING` and an audit entry `step_transition_rejected` is written.
E1.7.2 — A valid `READY → RUNNING` CAS update sets `lease_owner`, `lease_expires_at`, `dispatched_at`, `started_at`, and increments `attempt` atomically.
E1.7.3 — A concurrent `READY → RUNNING` attempt by two workers: exactly one CAS update affects one row (`rowcount == 1`); the other gets `rowcount == 0` and raises `StepDispatchConflict` (duplicate-dispatch prevention, REQ-E4.6).

### REQ-E1.8
WHEN a run is created from a valid `WorkflowTemplate`,
THEN the orchestrator MUST persist an **immutable full execution snapshot** of the template on the `WorkflowRun`: `template_snapshot_json` (the full validated `WorkflowTemplate` JSON), `template_version` (INTEGER), and `template_hash` (TEXT, SHA-256 of the canonical template). All three are nullable for Phase 1 / legacy runs. The orchestrator MUST execute from the snapshot, NEVER from the live `Workflow.definition_json`. Editing the live workflow after run creation MUST NOT affect any existing run or its steps. A run created from a `NULL`/empty `definition_json` is a **legacy run** (pending, zero step rows, no snapshot) and is preserved for backward compatibility with Phase 1 (REQ-E2.1).

**Acceptance Criteria:**
E1.8.1 — Migration 008 adds `template_snapshot_json`, `template_version`, `template_hash` (all nullable) to `workflow_runs`; Phase 1 rows have `NULL` and remain valid.
E1.8.2 — After `create_run` from a valid template, mutating `Workflow.definition_json` does not change `workflow_runs.template_snapshot_json`/`template_hash`/`template_version` or any step row.
E1.8.3 — `template_hash` equals `canonical_hash(template_snapshot_json)` and is recorded on the run; `run_created` audit carries `template_version` and `template_hash`.
E1.8.4 — A run created from `NULL`/empty `definition_json` has zero step rows and `template_snapshot_json IS NULL`; it remains `pending` until started, then vacuously completes (REQ-E4.4 derivation: zero steps ⇒ all-terminal ⇒ `completed`).

---

## Area E2 — Workflow Orchestration Service

**Scope note (maps to task W1.2):** a Python orchestration service that drives runs from creation through terminal state, pausing for human approval and stopping safely on failure.

### REQ-E2.1
WHEN a workflow run is created,
THEN `WorkflowOrchestrator.create_run(workflow_id, actor)` MUST: load the `Workflow`; if `definition_json` is `NULL`/empty, create a **legacy run** (status `pending`, no step rows, no snapshot, audit `run_created`) and return 201; otherwise parse and validate `definition_json` as `WorkflowTemplate` (422 `INVALID_WORKFLOW_TEMPLATE` on failure), then in one atomic transaction persist the `WorkflowRun` (status `pending`) with the immutable template snapshot (`template_snapshot_json`, `template_version`, `template_hash`) and all `WorkflowStepRun` rows, and write `run_created` with `actor` from `Settings.LOCAL_OPERATOR_ID`. `WorkflowService.create_run` (Phase 1) is preserved unchanged for Phase 1 callers; the orchestrator does NOT call it (step creation must be atomic).

**Acceptance Criteria:**
E2.1.1 — `create_run` is atomic (all-or-nothing); a failure mid-creation leaves no partial run/step rows.
E2.1.2 — `run_created` audit entry carries `template_version`, `template_hash`, `step_count`, `actor_id`.
E2.1.3 — `actor_id` equals `Settings.LOCAL_OPERATOR_ID` and is never read from the request body.
E2.1.4 — A workflow with `NULL`/empty `definition_json` produces a legacy run (201, `status="pending"`, zero steps, `template_snapshot_json` `null`) — preserving Phase 1 router behavior and tests.
E2.1.5 — A workflow whose `definition_json` is non-empty but not a valid `WorkflowTemplate` returns 422 `INVALID_WORKFLOW_TEMPLATE`.

### REQ-E2.2
WHEN eligible execution is started or resumed,
THEN `WorkflowOrchestrator.start_or_resume(run_id, actor)` MUST first transition the run `pending → running` if it is `pending` (via Phase 1 `WorkflowService.transition_run`), then repeatedly: (a) for each `PENDING` step whose dependencies are all `SUCCEEDED`, resolve inputs and transition `PENDING → READY`; failed input resolution transitions `PENDING → FAILED` (`INPUT_RESOLUTION_FAILED`); (b) for each `READY` step, gate (REQ-E2.4) if `approvable` and no consumable approval exists, else dispatch `READY → RUNNING` if the `executor_id` is registered and the working directory is approved, else transition `READY → FAILED` for the specific pre-dispatch error (`EXECUTOR_NOT_FOUND` / `WORKING_DIRECTORY_NOT_APPROVED` / `CAPABILITY_MISMATCH`); (c) after each `SUCCEEDED` step, re-evaluate dependents. Dispatch concurrency is bounded by `Settings.RUN_CONCURRENCY` (default 1). Resuming a terminal run returns 409 `RUN_NOT_STARTABLE`.

**Acceptance Criteria:**
E2.2.1 — A run with two independent root steps dispatches both (subject to the concurrency limit); a run with a linear chain dispatches only the first.
E2.2.2 — A step with `approvable == true` reaches `WAITING_APPROVAL` and is NOT dispatched; an `ApprovalRequest` bound to the step exists with `status = "pending"`.
E2.2.3 — A step whose `executor_id` is not registered transitions `READY → FAILED` with `code = "EXECUTOR_NOT_FOUND"` and the run stops safely (REQ-E4.4); no dispatch is attempted.
E2.2.4 — The run's Phase 1 `status` is derived to `running` while any step is `READY`/`RUNNING`/`INTERRUPTED`, `waiting_approval` while any step is `WAITING_APPROVAL`, and to a terminal Phase 1 state only when ALL steps are terminal (REQ-E4.4).

### REQ-E2.3
WHEN a step succeeds,
THEN the orchestrator MUST persist the executor's `StepExecutionResult` (`output_json`, `artifact_refs_json`, `result_status`) to the step row via a fenced CAS `RUNNING → SUCCEEDED` (fenced on `lease_owner`/`attempt`, REQ-E4.11), set `completed_at`, release the lease, write `step_succeeded`, and re-evaluate dependents for `READY` eligibility. No executor writes to the database directly.

**Acceptance Criteria:**
E2.3.1 — After the terminal step `SUCCEEDED` (and all steps terminal), the run transitions to Phase 1 `completed` and `completed_at` is set on the run.
E2.3.2 — `output_json`/`artifact_refs_json` are persisted only on `SUCCEEDED`; the executor return value is the sole source.
E2.3.3 — An audit `step_succeeded` entry is written with `step_key`, `step_version`, `result_status`, `attempt`.

### REQ-E2.4
WHEN an approval is required (initial gate or re-gate),
THEN the orchestrator MUST transition the gated step `READY → WAITING_APPROVAL`, create an `ApprovalRequest` bound to `workflow_run_id`, `workflow_step_run_id`, `operation` (`protected_operation`), `parameters_hash` (SHA-256 of the canonical artifact/parameters), `actor_id` (`Settings.LOCAL_OPERATOR_ID`), `expires_at` (`requested_at + APPROVAL_TTL_SECONDS`), and write `approval_requested`. The run is derived to `waiting_approval` via the approval service (REQ-E2.9). **Re-gating:** if a previously-approved authorization has expired (`now >= authorization_expires_at`) while the step waits to dispatch, the step MUST re-gate (`READY → WAITING_APPROVAL`) and a fresh `ApprovalRequest` MUST be created; an expired authorization MUST NOT be consumed (REQ-E3.6).

**Acceptance Criteria:**
E2.4.1 — The `ApprovalRequest` carries `operation`, `parameters_hash`, `actor_id`, `workflow_step_run_id`, `expires_at` (all non-null for Phase 2 gates).
E2.4.2 — `approval_requested` audit entry includes `operation`, `parameters_hash`, `step_key`.
E2.4.3 — While a step is `WAITING_APPROVAL`, the orchestrator dispatches no further protected action for that step.
E2.4.4 — A step whose prior approved authorization expired before dispatch re-gates to `WAITING_APPROVAL` with a fresh approval rather than dispatching or failing.

### REQ-E2.5
WHEN an approval is resolved,
THEN `ApprovalService.resolve` (Phase 1, extended) MUST verify the approval is `pending` (409 `APPROVAL_ALREADY_RESOLVED` if not; 409 `APPROVAL_EXPIRED` if `pending` but past `expires_at`), set `status` to `approved`/`rejected`, set `resolved_at`/`resolved_by`, and, for a Phase 2 gate (approval has `workflow_step_run_id`), set `authorization_expires_at = resolved_at + APPROVAL_AUTHORIZATION_VALIDITY_SECONDS` and transition the gated step `WAITING_APPROVAL → READY` (`approved`) or `→ CANCELLED` (`rejected`); the run transitions `waiting_approval → running` (`approved`) or `→ cancelled` (`rejected`) as in Phase 1. Phase 1 approvals (no `workflow_step_run_id`) resolve exactly as Phase 1 (run only).

**Acceptance Criteria:**
E2.5.1 — `approved` resumes the step to `READY` and the run to `running`; `rejected` cancels the step and the run.
E2.5.2 — Resolving an already-resolved approval returns HTTP 409 `APPROVAL_ALREADY_RESOLVED` (Phase 1 behavior preserved).
E2.5.3 — Resolving a `pending` approval past `expires_at` returns HTTP 409 `APPROVAL_EXPIRED`.
E2.5.4 — On `approved`, `authorization_expires_at` is set; the approval is consumable only before that time (REQ-E3.3, E3.6).

### REQ-E2.6
WHEN a step fails terminally,
THEN the orchestrator MUST transition the step `RUNNING → FAILED` (fenced CAS; REQ-E4.11), persist `error_json`, set `completed_at`, release the lease, write `step_failed`, and stop the run safely: no new steps are dispatched; dependents remain non-`READY`; independent `RUNNING` steps are allowed to complete; the run transitions to Phase 1 `failed` only once all steps are terminal (REQ-E4.4). **Retry is NOT a `FAILED` transition:** a retryable failure transitions `RUNNING → READY` (REQ-E4.7) and never passes through `FAILED`. Ambiguous external writes / `indeterminate` outcomes are never retried automatically and transition `RUNNING → FAILED` (REQ-E6.6).

**Acceptance Criteria:**
E2.6.1 — A terminally-failing step (with no other in-flight steps) sets run `failed` and `error_message`.
E2.6.2 — Dependents of a `FAILED` step never become `READY`.
E2.6.3 — `step_failed` audit entry carries `step_key`, `error_code`, `error_category`, `attempt`.

### REQ-E2.7
WHEN a run is cancelled,
THEN `WorkflowOrchestrator.cancel(run_id, actor)` MUST transition every non-terminal step (`PENDING`/`READY`/`RUNNING`/`WAITING_APPROVAL`/`INTERRUPTED`) to `CANCELLED` (fenced CAS where a lease is held), request cooperative cancellation of in-flight executor calls, transition the run to Phase 1 `cancelled` (from any non-terminal run state via `run_repo.transition_status` with the appropriate from-set, REQ-E2.9), and write `run_cancelled` with `actor`. Terminal steps are not mutated. Cancelling an already-terminal run is idempotent (HTTP 200, no mutation).

**Acceptance Criteria:**
E2.7.1 — Cancelling a run with one `RUNNING` and one `PENDING` step sets both to `CANCELLED` and the run to `cancelled`.
E2.7.2 — Already-`SUCCEEDED` steps remain `SUCCEEDED`.
E2.7.3 — `run_cancelled` audit entry includes `actor_id`, `cancelled_step_count`.
E2.7.4 — A protected action in flight when its run is cancelled does NOT consume its approval (the step transitions to `CANCELLED`; the fenced persist CAS for a stale completion fails, REQ-E4.11).

### REQ-E2.8
WHEN the orchestrator interacts with executors,
THEN the interface MUST be a one-way call `Executor.execute(context: ExecutionContext) -> StepExecutionResult` where the executor receives an immutable `ExecutionContext` (no DB handle, no run-state mutation capability) and returns a pure result; the orchestrator owns all persistence, state transitions, leases, and audit. Executors MUST NOT import or call repositories, services, or models. All Pydantic contract types (`ExecutionContext`, `StepExecutionResult`, `StructuredError`, `ArtifactRef`, `CancellationHandle`, `TimeoutPolicy`, `Capability`, `ExecutorIdentifier`) MUST live in `src/devflow_api/schemas/executor.py`; the `Executor` Protocol lives in `src/devflow_api/executors/base.py` and imports those types. No `schemas/*` module MAY import from `devflow_api.executors` (no layering inversion).

**Acceptance Criteria:**
E2.8.1 — The `Executor` Protocol is in `src/devflow_api/executors/base.py`; contract Pydantic models are in `src/devflow_api/schemas/executor.py`; `mypy --strict` passes for both packages.
E2.8.2 — No module under `src/devflow_api/schemas/` imports `devflow_api.executors` (enforced by an import-graph test).
E2.8.3 — No executor module imports `devflow_api.repositories`, `devflow_api.services`, or `devflow_api.models` (enforced by an import-graph/AST test).

### REQ-E2.9
WHEN the orchestrator transitions the run,
THEN it MUST reuse Phase 1 services compatibly: `pending → running`, `running → completed`, and `running → failed` via `WorkflowService.transition_run` (whose map is exactly `{"pending": {"running"}, "running": {"completed", "failed", "cancelled"}}`); the `running → waiting_approval` and `waiting_approval → running`/`→ cancelled` transitions via `ApprovalService` (`request_bound_approval` / `resolve`), which use `run_repo.transition_status` exactly as Phase 1's `request_approval`/`resolve` do; and `cancel` from any non-terminal run state via `run_repo.transition_status(run_id, "cancelled", <from-set>)`. The orchestrator MUST NOT introduce run states outside the Phase 1 six-value enum or attempt a transition not in the Phase 1 maps without going through the matching Phase 1 mechanism.

**Acceptance Criteria:**
E2.9.1 — Run transitions used by the orchestrator are exactly those Phase 1 already supports (transition_run map + approval-service transitions + transition_status for cancel); no new run state value is introduced.
E2.9.2 — `pending → running` is issued once at the start of the first `start_or_resume` (so a step that gates immediately does `pending → running → waiting_approval`, both valid in Phase 1).
E2.9.3 — A run cancelled while `waiting_approval` transitions `waiting_approval → cancelled` via `run_repo.transition_status` (mirroring Phase 1's reject path); no `transition_run` call is made for that state.

---

## Area E3 — Approval Checkpoints

**Scope note (maps to task W1.3):** durable, digest-bound, single-use, validity-bounded approval gates that do not auto-authorize later or unrelated actions.

### REQ-E3.1
WHEN a Phase 2 approval checkpoint is defined,
THEN the four protected operations MUST be enumerated as `ApprovalOperation` literals: `specification_approval`, `implementation_authorization`, `pr_creation_approval`, `merge_approval`. An `ApprovalRequest` created for a Phase 2 gate MUST set `operation` to one of these, `parameters_hash` to the SHA-256 of the canonical artifact/parameters, `actor_id` to `Settings.LOCAL_OPERATOR_ID`, `workflow_step_run_id` to the gated step, and `expires_at` to `requested_at + APPROVAL_TTL_SECONDS`. Phase 1 approval requests (no `operation`) remain valid and unchanged (backward compatibility).

**Acceptance Criteria:**
E3.1.1 — `operation`, `parameters_hash`, `actor_id`, `workflow_step_run_id`, `consumed_at`, `expires_at`, `authorization_expires_at` columns are added to `approval_requests` by migration 008; all are nullable for backward compatibility with Phase 1 rows.
E3.1.2 — The `approval_requests.status` CHECK constraint remains exactly `('pending','approved','rejected','expired')` — **no `consumed` status is added**; single-use semantics are enforced via `consumed_at` (REQ-E3.3) and approved validity via `authorization_expires_at` (REQ-E3.6). This preserves the Phase 1 constraint and Phase 1 constraint tests.
E3.1.3 — A Phase 2 gate created without `operation` or `parameters_hash` is rejected with HTTP 422 `INVALID_APPROVAL_BINDING`.
E3.1.4 — Existing Phase 1 approval rows (created by Phase 1 code paths) continue to resolve without the new columns; Phase 1 approval tests pass unmodified.

### REQ-E3.2
WHEN an approval is requested at a checkpoint,
THEN the artifact or parameter set being approved MUST be canonicalised identically at issuance and at consumption: `json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)` then SHA-256 hex, with documented normalization rules (strip surrounding whitespace, preserve internal content, no key reordering beyond `sort_keys`). `repo_full_name`-style server-side identity (where applicable in later waves) comes from server config, never the client.

**Acceptance Criteria:**
E3.2.1 — Issuing and consuming the same artifact yields identical `parameters_hash`.
E3.2.2 — A parameter added/removed/changed between issuance and consumption changes `parameters_hash` and consumption is rejected (REQ-E3.3).
E3.2.3 — The canonical function is a single shared implementation used at both issuance and consumption (no duplicate logic).

### REQ-E3.3
WHEN a protected action consumes an approval,
THEN `ApprovalRequest.consume_atomic(approval_id, operation, parameters_hash, workflow_step_run_id, actor_id)` MUST, inside a single `BEGIN IMMEDIATE` transaction, `UPDATE approval_requests SET consumed_at = now WHERE id = ? AND status = 'approved' AND consumed_at IS NULL AND now < authorization_expires_at AND operation = ? AND parameters_hash = ? AND workflow_step_run_id = ? AND actor_id = ?` and require `rowcount == 1`. Any mismatch (status not approved, already consumed, authorization expired, operation/digest/step/actor mismatch) yields `rowcount == 0` and the protected action is refused with `code = "APPROVAL_NOT_CONSUMABLE"` and an `approval_not_consumable` audit entry naming the mismatch reason. An approval MUST NOT authorize a later step, a different operation, a different artifact, or a different actor. Consumption is invoked only by the dispatch that currently owns the step's lease (REQ-E4.11); a stale completion cannot consume.

**Acceptance Criteria:**
E3.3.1 — A second consume of the same approval returns `rowcount == 0` (replay rejected).
E3.3.2 — An approval whose `parameters_hash` differs from the action's canonical hash is rejected.
E3.3.3 — An approval bound to step `a` cannot be consumed to authorize step `b` (step-run binding enforced).
E3.3.4 — An approval bound to `operation = "pr_creation_approval"` cannot authorize `implementation_authorization`.
E3.3.5 — `actor_id` mismatch is rejected.
E3.3.6 — A `pending` (not yet resolved) approval cannot be consumed.
E3.3.7 — An `expired` approval cannot be consumed; `expired` approvals remain visible in the run's `approvals` projection (Phase 1 W1.5.4 preserved).
E3.3.8 — An `approved` approval whose `authorization_expires_at <= now` cannot be consumed (REQ-E3.6).
E3.3.9 — Two concurrent `consume_atomic` calls on the same approval: exactly one returns `rowcount == 1`.

### REQ-E3.4
WHEN pending approval lifetime is managed,
THEN a `pending` approval MUST expire after `Settings.APPROVAL_TTL_SECONDS` (default 3600): the expiry sweep sets `status = "expired"` for `pending` approvals whose `expires_at <= now` and writes `approval_expired`. A resolved (`approved`/`rejected`) approval is no longer pending-expirable. The local single-user trust boundary is explicit: `actor_id` is the local operator only; Wave 1 does not authenticate multiple users and MUST NOT claim to.

**Acceptance Criteria:**
E3.4.1 — A `pending` approval older than the TTL (`expires_at <= now`) is expired by the sweep and cannot be resolved to `approved` (resolve returns 409 `APPROVAL_EXPIRED`).
E3.4.2 — An `approved` approval is not expired by the pending-TTL sweep (it is governed by authorization validity, REQ-E3.6, not the pending TTL).
E3.4.3 — The spec and API responses MUST NOT claim multi-user authentication; `actor_id` is documented as the local operator identity.

### REQ-E3.5
WHEN run/step deletion interacts with approvals,
THEN the existing Phase 1 `approval_requests.workflow_run_id` `ON DELETE CASCADE` is preserved; deleting a run deletes its approvals (Phase 1 behavior). The new `approval_requests.workflow_step_run_id` FK uses `ON DELETE SET NULL`; because step rows are only deleted via run CASCADE (which deletes approvals first via `workflow_run_id`), the `SET NULL` path never creates an orphaned, still-consumable approval. This invariant MUST be covered by a deletion test.

**Acceptance Criteria:**
E3.5.1 — Deleting a run deletes its `ApprovalRequest` rows (cascade via `workflow_run_id`) and its `WorkflowStepRun` rows.
E3.5.2 — No code path deletes a single `WorkflowStepRun` without deleting the run; the repository exposes no such method (enforced by absence + a guard test).
E3.5.3 — An approval bound to a deleted run is gone; there is no NULL-to-NULL bypass because approvals CASCADE (not SET NULL) on the run FK.

### REQ-E3.6
WHEN approved authorization validity is managed,
THEN an `approved` approval MUST carry `authorization_expires_at = resolved_at + Settings.APPROVAL_AUTHORIZATION_VALIDITY_SECONDS` (default 3600), enforced **separately** from the `status` CHECK constraint (the status stays `approved`; no new status value). An `approved` approval is consumable only while `now < authorization_expires_at` and `consumed_at IS NULL` (REQ-E3.3). If the authorization expires before the protected action is dispatched, the gated step MUST re-gate (`READY → WAITING_APPROVAL`) with a fresh approval (REQ-E2.4); an expired authorization is never consumed and never auto-restored. `authorization_expires_at` is `NULL` for Phase 1 rows (treated as no expiry / always-valid for backward compatibility).

**Acceptance Criteria:**
E3.6.1 — An `approved` approval past `authorization_expires_at` cannot be consumed (`rowcount == 0`).
E3.6.2 — A gated step whose approved authorization expired before dispatch re-gates to `WAITING_APPROVAL` with a fresh approval (no dispatch, no `FAILED`).
E3.6.3 — Phase 1 `approved` rows (`authorization_expires_at IS NULL`) remain consumable per Phase 1 semantics (no regression).
E3.6.4 — The `status` CHECK constraint is unchanged; validity is enforced via the column and the consume predicate only.

---

## Area E4 — Execution Lifecycle and Recovery

**Scope note (maps to task W1.4):** the eight-state step lifecycle, valid transitions, terminal states, restart recovery, duplicate-dispatch prevention, leases, timeouts, cancellation, bounded retries, idempotency, stale detection, fencing, and audit — all SQLite-safe.

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
| PENDING → READY | yes | dependencies SUCCEEDED + inputs resolved (orchestrator) |
| PENDING → FAILED | yes | input resolution failure (`INPUT_RESOLUTION_FAILED`) |
| PENDING → CANCELLED | yes | run cancel |
| READY → RUNNING | yes | dispatch (CAS, lease acquired, `attempt` incremented) |
| READY → WAITING_APPROVAL | yes | approvable gate reached, or re-gate after expired authorization |
| READY → FAILED | yes | pre-dispatch error: `EXECUTOR_NOT_FOUND` / `WORKING_DIRECTORY_NOT_APPROVED` / `CAPABILITY_MISMATCH` |
| READY → CANCELLED | yes | run cancel |
| RUNNING → SUCCEEDED | yes | executor success (fenced CAS) |
| RUNNING → READY | yes | retryable failure, safe + idempotent + `attempt < max_attempts` (transient; NOT terminal) |
| RUNNING → FAILED | yes | terminal: non-retryable, OR `attempt >= max_attempts`, OR `indeterminate` |
| RUNNING → INTERRUPTED | yes | recovery: lease expired while still `RUNNING` (process death) |
| RUNNING → CANCELLED | yes | run cancel (cooperative) |
| WAITING_APPROVAL → READY | yes | approval approved |
| WAITING_APPROVAL → CANCELLED | yes | approval rejected / run cancel |
| INTERRUPTED → READY | yes | recovery: safe + `attempt < max_attempts` (no auto-dispatch; awaits explicit start) |
| INTERRUPTED → FAILED | yes | recovery: unsafe or `attempt >= max_attempts` |
| INTERRUPTED → CANCELLED | yes | run cancel |
| SUCCEEDED / FAILED / CANCELLED → * | no | terminal |

All other transitions MUST be rejected with `INVALID_STEP_TRANSITION`. A retry (`RUNNING → READY`) is a distinct, non-terminal transition and MUST NOT pass through `FAILED` (REQ-E4.7).

**Acceptance Criteria:**
E4.2.1 — Each allowed transition is exercised by a named test; each disallowed transition is exercised by a negative test that asserts no row mutation and an audit `step_transition_rejected`.
E4.2.2 — `PENDING → RUNNING` (skipping READY) is rejected.
E4.2.3 — `SUCCEEDED → RUNNING` (reviving a terminal step) is rejected.
E4.2.4 — A retryable failure transitions `RUNNING → READY` (status becomes `READY`, not `FAILED`); `FAILED` is reached only on exhaustion/non-retryable/indeterminate.

### REQ-E4.3
WHEN the application restarts,
THEN `RecoveryService.recover()` MUST run at startup and perform **automatic state reconciliation**: it MUST scan `workflow_step_runs` for rows with `status = "RUNNING"` whose `lease_expires_at <= now` (or `lease_expires_at IS NULL`), transition each to `INTERRUPTED` (fenced CAS) and write `step_interrupted` with the prior `lease_owner`/`lease_expires_at`; then for each `INTERRUPTED` step decide `INTERRUPTED → READY` (safe + idempotent + `attempt < max_attempts`) or `INTERRUPTED → FAILED` (otherwise), writing `step_recovery_decided`. The recovery MUST be idempotent. **Resumed execution is NOT automatic:** `READY` steps (including those recovered from `INTERRUPTED`) are dispatched only by an explicit `start_or_resume` call (resolved default). A `RUNNING` step with a still-valid lease is NOT interrupted (a live worker owns it).

**Acceptance Criteria:**
E4.3.1 — A step stuck `RUNNING` with an expired lease becomes `INTERRUPTED` on recovery; a second recovery run leaves it `INTERRUPTED` or applies the decision once (idempotent).
E4.3.2 — A step `RUNNING` with a still-valid lease is NOT interrupted (a live worker owns it).
E4.3.3 — `step_interrupted` audit entry carries `prior_lease_owner`, `prior_lease_expires_at`.
E4.3.4 — After recovery, a safe recovered step is `READY` but is NOT dispatched until `start_or_resume` is called (no auto-resume).

### REQ-E4.4
WHEN the run reaches a terminal derivation,
THEN the run's terminal Phase 1 status MUST be derived **only when all steps are terminal**: `completed` if all `SUCCEEDED`; `failed` if any `FAILED` and none `CANCELLED` by cancel; `cancelled` if cancelled. While any step is non-terminal (`PENDING`/`READY`/`RUNNING`/`WAITING_APPROVAL`/`INTERRUPTED`), the run is `running` (or `waiting_approval` if a step is `WAITING_APPROVAL`). After a `FAILED` step, the orchestrator MUST NOT dispatch any new step; dependents stay non-`READY`; independent `RUNNING` steps are allowed to complete; the run transitions to `failed` once all steps are terminal. The stop is "safe": no partial external commit is forced and no state is lost. (With the default concurrency of 1, a `FAILED` step implies no other in-flight step, so the run can go `failed` immediately.)

**Acceptance Criteria:**
E4.4.1 — After a `FAILED` step (concurrency 1), `start_or_resume` dispatches no further steps and the run reaches `failed`.
E4.4.2 — With concurrency > 1, an independent `RUNNING` step completes and records its own terminal state before the run reaches `failed` (run stays `running` until all terminal).
E4.4.3 — A legacy run (zero steps) vacuously derives `completed` on `start_or_resume` (`pending → running → completed`).

### REQ-E4.5
WHEN a step errors,
THEN `error_json` MUST be a structured object with `code: str`, `category: str` (`executor` | `timeout` | `cancelled` | `input_resolution` | `internal`), `message: str`, `retryable: bool`, `attempt: int`. `result_status` records the executor's declared outcome (`succeeded` | `failed` | `cancelled` | `indeterminate`). `indeterminate` outcomes (REQ-E6.6) are treated as terminal `FAILED` with `retryable = false` (never auto-retried).

**Acceptance Criteria:**
E4.5.1 — A timeout produces `category = "timeout"`, `retryable = true` only for safe/idempotent steps.
E4.5.2 — An `indeterminate` outcome is persisted with `result_status = "indeterminate"` and `retryable = false`.
E4.5.3 — `error_json` is never set on `SUCCEEDED` steps.

### REQ-E4.6
WHEN duplicate dispatch is attempted,
THEN the `READY → RUNNING` transition MUST be a single CAS `UPDATE workflow_step_runs SET status='RUNNING', lease_owner=?, lease_expires_at=?, dispatched_at=now, started_at=now, attempt = attempt + 1, idempotency_key=f"{run_id}:{step_key}:{attempt+1}" WHERE id=? AND status='READY'` inside `BEGIN IMMEDIATE`; exactly one concurrent caller observes `rowcount == 1` and proceeds; all others observe `rowcount == 0` and raise `StepDispatchConflict` without mutating state. `lease_expires_at = now + STEP_LEASE_TTL_SECONDS` (default 60).

**Acceptance Criteria:**
E4.6.1 — Two concurrent `dispatch` calls on the same `READY` step: one succeeds (new `lease_owner`, `attempt` incremented), one raises `StepDispatchConflict`; the step has exactly one `lease_owner`.
E4.6.2 — The CAS uses `BEGIN IMMEDIATE`; the test asserts the transaction mode (via a spy or documented invariant).
E4.6.3 — A `lease_owner` whose lease expired allows a fresh `INTERRUPTED → READY → RUNNING` re-dispatch (new `lease_owner`, incremented `attempt`).

### REQ-E4.7
WHEN bounded retries are configured,
THEN a safe, idempotent step (`retry_policy.safe == true` and `retry_policy.idempotent == true`) that fails with a retryable error and whose current `attempt < max_attempts` MUST transition `RUNNING → READY` (transient; `attempt` is NOT incremented at this transition — it is incremented on the next `READY → RUNNING` dispatch), writing `step_retry_scheduled` with the next `attempt`. When `attempt >= max_attempts` (or the step is unsafe, non-idempotent, or the outcome is `indeterminate`), the step MUST transition `RUNNING → FAILED` (terminal). `max_attempts` is the total executions allowed (including the first); default 1 (no retry). Ambiguous external writes / `indeterminate` outcomes MUST NOT be retried automatically.

**Acceptance Criteria:**
E4.7.1 — A safe step with `max_attempts = 3` that fails at attempts 1 and 2 then succeeds at attempt 3 reaches `SUCCEEDED` with `attempt = 3`.
E4.7.2 — A safe step that exhausts `max_attempts = 3` (fails at attempts 1, 2, 3) reaches `FAILED` with `attempt = 3`.
E4.7.3 — An unsafe/`indeterminate` step is never auto-retried even if `max_attempts > 1`.
E4.7.4 — A retry transitions `RUNNING → READY` and never passes through `FAILED`; `FAILED` is terminal.
E4.7.5 — Wave 1's mock executor is the only executor and is declared `safe = true`, so retries are exercisable in Wave 1 without external writes.

### REQ-E4.8
WHEN recovery decides retry-or-fail for an `INTERRUPTED` step,
THEN the recovery routine MUST transition `INTERRUPTED → READY` only when the step is safe and idempotent (`retry_policy.safe == true`) and `attempt < max_attempts`; otherwise `INTERRUPTED → FAILED` with `category = "internal"`, `retryable = false`, requiring human action. The decision and its reason MUST be audited as `step_recovery_decided`. The recovered `READY` step awaits an explicit `start_or_resume` (REQ-E4.3).

**Acceptance Criteria:**
E4.8.1 — A safe `INTERRUPTED` step under its attempt budget goes `INTERRUPTED → READY` (not dispatched until explicit start).
E4.8.2 — A safe `INTERRUPTED` step at `attempt >= max_attempts` goes `INTERRUPTED → FAILED`.
E4.8.3 — An unsafe `INTERRUPTED` step goes `INTERRUPTED → FAILED` regardless of attempt budget.
E4.8.4 — `step_recovery_decided` audit entry carries `decision` (`retry` | `fail`), `reason`, `attempt`.

### REQ-E4.9
WHEN idempotency is required,
THEN each dispatch MUST carry an idempotency key `f"{run_id}:{step_key}:{attempt}"` (post-increment `attempt`) and an input digest (`SHA-256` of canonical `input_json`); a re-dispatch with the same key and input digest for a safe step MUST produce the same persisted result where the executor supports it (the mock executor is deterministic; real executors declare idempotency in their contract, REQ-E5.x). Non-idempotent steps MUST NOT be retried (REQ-E4.7).

**Acceptance Criteria:**
E4.9.1 — Re-running the same safe step with identical input produces an identical `output_json` (mock executor deterministic).
E4.9.2 — The idempotency key and input digest are persisted on the step row and appear in audit entries.
E4.9.3 — A changed input digest between attempts is audited and, for non-idempotent steps, blocks retry.

### REQ-E4.10
WHEN stale execution is detected,
THEN a heartbeat/lease model MUST mark a `RUNNING` step stale when `lease_expires_at <= now`; the lease is renewed by the executing worker every `STEP_HEARTBEAT_INTERVAL_SECONDS` (default 15) via a fenced CAS heartbeat (`UPDATE ... SET lease_expires_at = ? WHERE id = ? AND status = 'RUNNING' AND lease_owner = ? AND attempt = ?`). A lease owned by a cancelled run MUST NOT be renewed. Stale detection feeds REQ-E4.3 recovery.

**Acceptance Criteria:**
E4.10.1 — A heartbeat from the owning worker extends `lease_expires_at`; a heartbeat from a non-owner (or wrong `attempt`) is rejected (`rowcount == 0`).
E4.10.2 — A cancelled run's `RUNNING` step rejects heartbeat renewal.
E4.10.3 — Stale detection (lease expiry) feeds REQ-E4.3 recovery.

### REQ-E4.11
WHEN a stale executor completion arrives,
THEN every post-dispatch state-mutating CAS (`RUNNING → SUCCEEDED`, `RUNNING → FAILED`, `RUNNING → READY` retry, `RUNNING → CANCELLED`) MUST fence on the current `lease_owner` AND `attempt`: `UPDATE ... WHERE id = ? AND status = 'RUNNING' AND lease_owner = ? AND attempt = ?`. A completion from a stale (superseded) lease/attempt MUST yield `rowcount == 0`, be discarded, and write a `step_stale_completion_discarded` audit entry; it MUST NOT mutate the step or consume any approval. This prevents a late return from a superseded dispatch (after the step was `INTERRUPTED` and re-dispatched, or after cancel) from corrupting state or consuming an approval.

**Acceptance Criteria:**
E4.11.1 — A stale completion (old `lease_owner`/`attempt`) after the step was re-dispatched (new lease/attempt) is discarded (`rowcount == 0`); the step keeps the new state.
E4.11.2 — A stale completion does NOT consume any `ApprovalRequest`.
E4.11.3 — `step_stale_completion_discarded` audit entry carries `prior_lease_owner`, `prior_attempt`.
E4.11.4 — A cancel that supersedes an in-flight dispatch causes that dispatch's completion CAS to fail (`status` no longer `RUNNING`), so no stale persistence occurs.

---

## Area E5 — Executor Contracts

**Scope note (maps to task W1.5):** a versioned executor interface and the one safe executor Wave 1 ships.

### REQ-E5.1
WHEN an executor is registered,
THEN it MUST implement the `Executor` Protocol (in `src/devflow_api/executors/base.py`) with: `identifier: ExecutorIdentifier` (id + version), `capabilities: list[Capability]` (declared operations/tools), `input_schema: type[BaseModel]`, `output_schema: type[BaseModel]`, `timeout_policy: TimeoutPolicy`, and `async def execute(context: ExecutionContext) -> StepExecutionResult`. The contract Pydantic types live in `src/devflow_api/schemas/executor.py` (REQ-E2.8). The orchestrator MUST select an executor by `executor_id` and refuse dispatch for unregistered ids or capability mismatches (REQ-E2.2).

**Acceptance Criteria:**
E5.1.1 — `ExecutorIdentifier`, `Capability`, `ExecutionContext`, `StepExecutionResult`, `TimeoutPolicy` are Pydantic v2 models in `src/devflow_api/schemas/executor.py`; `mypy --strict` passes.
E5.1.2 — Dispatching an unregistered `executor_id` fails the step `READY → FAILED` with `EXECUTOR_NOT_FOUND` (REQ-E2.2.3).
E5.1.3 — An executor whose declared `Capability` does not match the step's `tool_selection` fails the step `READY → FAILED` with `CAPABILITY_MISMATCH`.

### REQ-E5.2
WHEN an executor executes,
THEN it MUST receive an `ExecutionContext` containing `run_id`, `step_run_id`, `step_key`, `step_version`, `inputs` (resolved), `tool_selection`, `working_directory` (approved dir or `None`), `env_allowlist` (explicit dict, never the parent environment), `timeout_s`, `cancellation: CancellationHandle`, `actor_id`, `idempotency_key`, `input_digest`, and `attempt`. It MUST return a `StepExecutionResult` with `outcome` (`succeeded`|`failed`|`cancelled`|`indeterminate`), `output` (validated against `output_schema`), `artifact_refs: list[ArtifactRef]`, `error: StructuredError | None`, `metadata: ExecutionMetadata`.

**Acceptance Criteria:**
E5.2.1 — `ExecutionContext.working_directory` is either `None` or a member of `Settings.APPROVED_WORKING_DIRECTORIES`; executors MUST NOT write outside it.
E5.2.2 — `ExecutionContext.env_allowlist` is an explicit dict; executors MUST NOT read `os.environ` directly (enforced by test + lint where feasible).
E5.2.3 — A result whose `output` fails `output_schema` validation is treated as `outcome = "failed"` with `category = "executor"`.
E5.2.4 — `artifact_refs` are references (paths/digests), never inlined large payloads.

### REQ-E5.3
WHEN a timeout or cancellation occurs,
THEN the orchestrator MUST enforce `timeout_s` via `asyncio.wait_for` and pass a `CancellationHandle`; a timeout (executor raised/`wait_for` expired while the process is alive) produces `outcome = "failed"`, `category = "timeout"`, routed through retry logic (REQ-E4.7) or terminal `FAILED` — **never `INTERRUPTED`**. `INTERRUPTED` is reached only by recovery when the process died and the lease expired (REQ-E4.3). An executor that observes cancellation MUST return `outcome = "cancelled"` and the step reaches `CANCELLED`. Cancellation MUST NOT leave external state partially committed (Wave 1 has no external writes; the contract is specified for later waves).

**Acceptance Criteria:**
E5.3.1 — A step exceeding `timeout_s` is transitioned `RUNNING → READY` (retry, if safe & under budget) or `RUNNING → FAILED` (terminal) with `category = "timeout"` — never `INTERRUPTED`.
E5.3.2 — A cancelled executor call returns `outcome = "cancelled"` and the step reaches `CANCELLED`.
E5.3.3 — A process death (no completion recorded) with an expired lease is recovered to `INTERRUPTED` by recovery (REQ-E4.3), not by the dispatch path.

### REQ-E5.4
WHEN Wave 1 validates the engine,
THEN exactly one executor MUST ship: `MockExecutor` (`identifier.id = "mock"`, `version = 1`), a pure in-process no-op that echoes its inputs into `output`, sleeps a configurable short duration, observes the `CancellationHandle`, produces a deterministic `ArtifactRef` (digest of a constant), declares `safe = true` and `idempotent = true`, uses no working directory, no environment, and no subprocess. No other executor and no shell/command execution MUST exist in Wave 1. **Executor security guards are mandatory** (hard gate): no module under `src/devflow_api/executors/` MAY invoke `subprocess`, `os.system`, `os.exec*`, `shell=True`, or read `os.environ`; executors MUST NOT import repositories/services/models (REQ-E2.8.3).

**Acceptance Criteria:**
E5.4.1 — `MockExecutor` is the only executor registered by default; `registry.list_executors()` returns exactly `["mock"]` in Wave 1.
E5.4.2 — `MockExecutor` performs no filesystem, network, or subprocess access (asserted by a sandbox-leak test).
E5.4.3 — No module under `src/devflow_api/executors/` invokes `subprocess`, `os.system`, `os.exec*`, or `shell=True`, or reads `os.environ` (asserted by an AST guard test — mandatory gate).
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
THEN it MUST be restricted to `Settings.APPROVED_WORKING_DIRECTORIES` (an explicit allowlist; empty by default). Paths outside the allowlist MUST be refused as a pre-dispatch error (`READY → FAILED`, `WORKING_DIRECTORY_NOT_APPROVED`). `MockExecutor` uses no working directory. The spec MUST document that this is application-level path checking, not OS-enforced filesystem isolation.

**Acceptance Criteria:**
E6.2.1 — An `ExecutionContext.working_directory` not in the allowlist transitions the step `READY → FAILED` with `code = "WORKING_DIRECTORY_NOT_APPROVED"` before dispatch.
E6.2.2 — The default allowlist is empty; `MockExecutor` dispatches with `working_directory = None`.
E6.2.3 — A documentation note states this is not OS-level filesystem sandboxing.

### REQ-E6.3
WHEN environment variables are passed to any (future) subprocess,
THEN only `Settings.EXECUTOR_ENV_ALLOWLIST` variables are forwarded via an explicit `env` dict; there MUST be no implicit parent-environment inheritance (`get_default_environment()` / `os.environ` MUST NOT be merged). Required system variables are added explicitly and minimally only when a subprocess exists — Wave 1 has no subprocess, so this is contractual only.

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
THEN every protected action MUST require a consumed, digest-bound, single-use, validity-bounded `ApprovalRequest` (REQ-E3.3, E3.6); credential presence MUST NOT be treated as authorization; an approval MUST NOT authorize a later, different, or unrelated action; a stale completion MUST NOT consume an approval (REQ-E4.11).

**Acceptance Criteria:**
E6.5.1 — A protected action without a consumable approval is refused (`APPROVAL_NOT_CONSUMABLE`).
E6.5.2 — A consumed approval cannot authorize a second action (replay rejected).
E6.5.3 — An approval for operation `merge_approval` cannot authorize `pr_creation_approval`.
E6.5.4 — A stale completion does not consume an approval (fencing, REQ-E4.11.2).

### REQ-E6.6
WHEN an external action outcome is indeterminate,
THEN the spec MUST define `INDETERMINATE` (5xx/transport errors for future external calls) as NOT auto-retried, as terminal `FAILED` with `retryable = false`, and as NOT auto-restoring any consumed approval; reconciliation requires a fresh approval (and a fresh run/step, since `FAILED` is terminal). Wave 1 has no external calls, so this is specified contractually for Waves 2–4 and exercised by the mock executor's `indeterminate` test mode.

**Acceptance Criteria:**
E6.6.1 — `MockExecutor` has a test mode returning `outcome = "indeterminate"`; the step is `FAILED` with `retryable = false` and the approval (if any) is not restored/consumed for retry.
E6.6.2 — A fresh approval is required before any retry of an indeterminate action (via a new run/step).
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
E6.8.2 — No Wave 1 code path enables real coding-agent or shell execution (guard test, REQ-E5.4.3).

---

## Area E7 — API and Streamlit Contracts

**Scope note (maps to task W1.7):** minimal APIs for observing and driving execution; full UX is Wave 5.

### REQ-E7.1
WHEN a client creates a run,
THEN `POST /api/v1/workflows/{id}/runs` MUST create the run and (for a valid template) all step rows (REQ-E2.1) and return HTTP 201 with the run and its initial steps. A non-empty invalid template returns HTTP 422 `INVALID_WORKFLOW_TEMPLATE`; a `NULL`/empty `definition_json` creates a legacy run (201, zero steps).

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
E7.4.1 — `WorkflowRunResponse.steps` is ordered by template order; empty list `[]` never `null` (legacy runs return `[]`).
E7.4.2 — `approvals` and `pending_approvals` behave exactly as Phase 1 (W1.5.4a–c) — backward compatible.
E7.4.3 — `output_json`/`error_json` are `null` until the step reaches the relevant terminal state.

### REQ-E7.5
WHEN a client reads audit events,
THEN `GET /api/v1/workflow-runs/{run_id}/audit` MUST return ordered audit entries for the run (Phase 1 `WorkflowAuditLog`, extended event types). Pagination via `limit`/`offset` is supported.

### REQ-E7.6
WHEN a client approves or rejects a gate,
THEN `POST /api/v1/approvals/{id}/resolve` (Phase 1, extended) with `{"decision": "approved"|"rejected", "resolved_by": ...}` MUST validate the approval is `pending` (409 `APPROVAL_ALREADY_RESOLVED` if resolved; 409 `APPROVAL_EXPIRED` if `pending` but past `expires_at`), and resume or cancel the gated step (REQ-E2.5). Binding/validity is verified at consumption, not at resolve (REQ-E3.3, E3.6).

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
THEN it MUST cover valid and invalid state transitions (REQ-E4.2), dependency ordering (REQ-E1.3), approval enforcement, replay prevention, authorization validity and re-gating (REQ-E3.3, E3.6), concurrent execution and duplicate-dispatch prevention (REQ-E4.6), lease/attempt fencing and stale completions (REQ-E4.11), process interruption and recovery (REQ-E4.3, E4.8), cancellation (REQ-E2.7), timeouts (REQ-E5.3), idempotency (REQ-E4.9), attempt counting and retry budget (REQ-E4.7), run terminal derivation with independent steps (REQ-E4.4), template snapshot immutability (REQ-E1.8), SQLite transaction rollback (REQ-E2.1, E4.6), audit logging (all), API validation (REQ-E7.x), mock executor behavior (REQ-E5.4), schema layering (REQ-E2.8), and backward compatibility with Phase 1.

**Required named tests (minimum set):**

State & transitions:
- `test_step_pending_to_ready_requires_dependencies_succeeded`
- `test_step_skip_ready_to_running_rejected`
- `test_step_terminal_state_revival_rejected`
- `test_invalid_transition_writes_rejection_audit_and_no_mutation`
- `test_pending_to_failed_on_input_resolution_failure`
- `test_ready_to_failed_on_executor_not_found`
- `test_ready_to_failed_on_working_directory_not_approved`
- `test_ready_to_failed_on_capability_mismatch`

Dependencies:
- `test_linear_chain_dispatches_in_order`
- `test_diamond_dependency_gates_until_all_succeeded`
- `test_failed_dependency_blocks_dependents`

Retry & attempt budget:
- `test_retryable_failure_transitions_running_to_ready_not_failed`
- `test_retry_exhaustion_transitions_to_failed_terminal`
- `test_retry_never_passes_through_failed`
- `test_attempt_increments_on_dispatch`
- `test_attempt_budget_enforced_max_attempts`
- `test_unsafe_indeterminate_step_not_retried`

Approvals:
- `test_approval_consumed_once_replay_rejected`
- `test_concurrent_consume_only_one_succeeds`
- `test_approval_parameter_digest_mismatch_rejected`
- `test_approval_bound_to_step_a_cannot_authorize_step_b`
- `test_approval_operation_mismatch_rejected`
- `test_approval_actor_mismatch_rejected`
- `test_pending_approval_not_consumable`
- `test_expired_approval_not_consumable`
- `test_expired_pending_approval_cannot_be_promoted_to_approved`
- `test_approved_authorization_expires_after_validity`
- `test_consume_refused_after_authorization_expiry`
- `test_consume_refused_after_run_cancelled`
- `test_approval_re_gated_after_authorization_expiry`

Concurrency, leases & fencing:
- `test_concurrent_dispatch_only_one_succeeds`
- `test_cas_uses_begin_immediate`
- `test_heartbeat_only_owner_renews_lease`
- `test_cancelled_run_rejects_heartbeat`
- `test_stale_completion_discarded_by_lease_fence`
- `test_stale_completion_cannot_consume_approval`

Recovery:
- `test_running_step_with_expired_lease_becomes_interrupted`
- `test_running_step_with_valid_lease_not_interrupted`
- `test_recovery_idempotent`
- `test_recovery_does_not_auto_dispatch_requires_explicit_start`
- `test_recovery_safe_step_retries_under_budget`
- `test_recovery_unsafe_step_fails`
- `test_recovery_step_at_max_attempts_fails`

Cancellation:
- `test_cancel_run_marks_non_terminal_steps_cancelled`
- `test_cancel_run_keeps_succeeded_steps`
- `test_cancel_idempotent_on_terminal_run`
- `test_cancel_run_while_waiting_approval`

Timeouts:
- `test_step_timeout_marks_failed_or_ready_not_interrupted`
- `test_executor_ignoring_cancel_marked_cancelled`

Run derivation:
- `test_run_failed_derived_only_after_all_steps_terminal`
- `test_run_completed_only_when_all_steps_succeeded`
- `test_legacy_run_with_zero_steps_vacuously_completes`
- `test_run_cancelled_while_waiting_approval_transitions_correctly`

Template snapshot:
- `test_template_snapshot_immutable_after_live_workflow_edit`
- `test_template_hash_recorded_on_run`
- `test_legacy_run_has_no_snapshot_and_zero_steps`

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
- `test_step_stale_completion_discarded_audited`

API:
- `test_create_run_invalid_template_422`
- `test_create_run_legacy_run_on_null_template_201`
- `test_start_terminal_run_409`
- `test_cancel_terminal_run_idempotent_200`
- `test_run_response_includes_steps_and_approvals_projection`
- `test_audit_endpoint_pagination`

Mock executor & schema layering:
- `test_mock_executor_only_registered_executor`
- `test_mock_executor_no_fs_network_subprocess`
- `test_no_shell_execution_in_executors_package`
- `test_executors_do_not_import_repositories_services_models`
- `test_schemas_do_not_import_executors_package`

Backward compatibility (Phase 1):
- `test_phase1_workflow_crud_still_works`
- `test_phase1_create_run_on_null_template_returns_pending` (legacy run; preserves `test_create_run_returns_pending_status`)
- `test_phase1_approval_resolve_still_works_without_operation`
- `test_phase1_run_status_constraint_unchanged`
- `test_approval_status_constraint_unchanged_no_consumed_value`
- `test_phase1_workflow_service_create_run_unchanged`

Security negatives:
- `test_working_directory_outside_allowlist_rejected`
- `test_env_allowlist_no_parent_inheritance_contract`
- `test_indeterminate_outcome_not_retried_and_approval_not_restored`
- `test_no_automatic_pr_merge_endpoint_absent`

Migrations:
- `test_migration_008_upgrade_creates_step_runs_extends_approvals_and_workflow_runs`
- `test_migration_008_downgrade_restores_prior_schema`
- `test_full_round_trip_001_to_008`

### REQ-E8.2
WHEN quality gates run,
THEN `ruff check .`, `mypy --strict src/`, `pytest --cov=src --cov-branch --cov-fail-under=80` MUST all exit 0; `alembic upgrade head` reaches `008_add_workflow_execution_engine`; `alembic downgrade -1` returns to `007_add_github_confirmations`; and `docs/openapi.json` is regenerated. Phase 0 and Phase 1 tests continue to pass.

### REQ-E8.3
WHEN migration upgrade/downgrade is tested,
THEN migration 008 MUST be reversible: `upgrade` creates `workflow_step_runs`, adds the `approval_requests` columns/indexes (operation, parameters_hash, actor_id, workflow_step_run_id, consumed_at, expires_at, authorization_expires_at), and adds the `workflow_runs` snapshot columns (template_snapshot_json, template_version, template_hash); `downgrade` drops them and restores the prior schema exactly, including the unchanged `approval_requests.status` and `workflow_runs.status` CHECK constraints.

---

## Traceability Matrix (requirements → task area → design section)

| Requirement | Task area (W1.x) | Design section |
|---|---|---|
| REQ-E1.x | W1.1 definition/execution model | §3 (data model), §4 (template model + snapshot) |
| REQ-E2.x | W1.2 orchestration service | §5 (orchestration), §6 (orchestrator–executor interface), §5.8 (run transitions/compat) |
| REQ-E3.x | W1.3 approval checkpoints | §7 (approval binding, validity, consumption, re-gating) |
| REQ-E4.x | W1.4 lifecycle & recovery | §8 (state machine), §9 (recovery), §10 (SQLite patterns + fencing) |
| REQ-E5.x | W1.5 executor contracts | §6 (executor contract), §11 (mock executor) |
| REQ-E6.x | W1.6 security | §12 (security & threat model) |
| REQ-E7.x | W1.7 API & Streamlit | §13 (API contracts), §14 (Streamlit) |
| REQ-E8.x | W1.8 testing | §15 (test matrix), tasks.md |

---

## Assumptions, Dependencies, Out-of-Scope

**Assumptions:**
- Phase 1 v1.5.9 (commit `2d077ec`) is the merged, green baseline (verified by preflight; PR #13 merged; 313 tests pass).
- The Alembic head is `007_add_github_confirmations` (verified); migration 008 chains from it. The implementer MUST re-confirm the head at implementation time.
- The local operator identity is `Settings.LOCAL_OPERATOR_ID` (default `'local_operator'`), reused from Phase 1 (W5-SR).
- `Workflow.definition_json` (Phase 1, deferred/raiseload) holds the `WorkflowTemplate`; no new template table is introduced. The immutable snapshot is stored on `workflow_runs` (additive columns), not a new table.

**Dependencies:**
- Phase 1 models, services (`WorkflowService.transition_run`, `ApprovalService.request_approval`/`resolve`, `run_repo.transition_status`), routers, and migrations 001–007 (present, green).
- `Settings.LOCAL_OPERATOR_ID`, `RedactSecretsProcessor`, `UTCDateTime`, `_transaction`/`BEGIN IMMEDIATE` patterns (Phase 1).

**Out of scope (Wave 1):** all items in the Out-of-Scope table above; notably real coding-agent execution, external integrations, PR creation/merge, and the full Streamlit dashboard.

**Backward-compatibility commitments:**
- `workflow_runs.status` CHECK constraint unchanged (six values); snapshot columns added additively (nullable).
- `approval_requests.status` CHECK constraint unchanged (four values; no `consumed`); consumption via `consumed_at`; approved validity via `authorization_expires_at`; pending TTL via `expires_at`.
- Phase 1 endpoints, schemas, audit event types preserved; Wave 1 adds new event types, endpoints, and the additive `steps` field (default `[]`).
- Phase 1 `WorkflowService.create_run`, `ApprovalService.request_approval`/`resolve` signatures preserved; Wave 1 adds `request_bound_approval` and extends `resolve` additively (step transition only when `workflow_step_run_id` is set).
- Legacy `NULL`/empty-template runs are preserved (201 pending, zero steps) so Phase 1 tests pass unmodified.
- Phase 1 tests pass unmodified (the v2.1.0 design avoids any required Phase 1 test change).
