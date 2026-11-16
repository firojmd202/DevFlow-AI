# DevFlow AI — Phase 1: Functional Orchestration Requirements

**Version:** 1.5.9
**Status:** Corrected — Wave 5 Security Resolution (HTTP Outcome Classification, Canonical Binding, Trusted Local Principal)
**Scope:** Phase 1 — Functional Orchestration
**Branch:** feature/phase1-wave5-github-orchestration
**Base commit:** bceb9bab4328fe4ca5ed068a25fa9f541841f0ff
**Last Updated:** 2026-11-16
**Supersedes:** v1.3.0 (F1–F3 corrections applied — see .agents/tasks/phase1-v1.4.0-correction-report.md)

**Version history:**
- v1.0.0 — Initial specification
- v1.1.0 — Eight independent-review findings applied (see docs/reviews/phase1-specification-review.md §11)
- v1.2.0 — Five amendment-round findings applied (see docs/reviews/phase1-specification-review.md §13)
- v1.3.0 — Final specification correction: F1–F5 applied (FK test split, GitHubConfirmation persistence, MCP authorization consistency, superseded guidance labelled, metadata corrected)
- v1.4.0 — 2026-11-15 — Corrections F1 (MCP approval authorization via approval_request_id), F2 (FK cascade test corrections), F3 (metadata), F6 (MCPApproval dedicated schema), F7 (outdated MCP authorization references), F8 (Wave 1 FK tests), F9 (approval consumption and external failure handling). Branch: feature/phase1-specification-planning, Base: aaaaacb703124fc31b0e757b2bf1739c4fb225c9.
- v1.5.0 — Migration and dependency alignment: 006=mcp_approvals (Wave 4), 007=github_confirmations (Wave 5); REQ-G1.4 migration reference updated; REQ-M2.x wave ownership aligned to Wave 4. Branch: feature/phase1-specification-planning.
- v1.5.1 — MCP Security Hardening Pass (S1–S2): S1 workflow_run_id binding rules added to REQ-M2.x (REQ-M2.5); S2 atomic consumption contract strengthened in REQ-M2.2 and REQ-M2.4; SQLite concurrency assumptions documented; 9 new named negative tests added; mcp_approval_rejected audit event reason field added to REQ-W1.7. Branch: feature/phase1-specification-planning.
- v1.5.2 — 2026-11-15 — Type and Concurrency Alignment Pass (T1–T2): T1 trusted_workflow_run_id type corrected UUID → int | None in REQ-M2.5 (M2.5.1) and REQ-M2.2 consume_atomic signature; T2 SQLite concurrency model clarified in REQ-M2.2: removed incorrect pooling-serializes-writes claim, added BEGIN IMMEDIATE semantics, busy_timeout policy, and retry rules; 5 new T2 named negative tests added to REQ-M2.2. Branch: feature/phase1-specification-planning.
- v1.5.3 — 2026-11-15 — Final PR Readiness Gate (C1–C2): C1 redundant workflow_run_id parameter removed from invoke_tool (REQ-M1.7 step 7, REQ-M2.5 M2.5.1); only trusted_workflow_run_id: int | None remains; added explicit statement that trusted_workflow_run_id is resolved from server-side session context and never from tool arguments or client-supplied fields. C2 consume_atomic signature extended with all binding fields (REQ-M2.2): actor_id, mcp_server_id, tool_name, arguments_hash, workflow_run_id as explicit parameters; in-transaction 8-step verification algorithm updated; test_approval_modified_between_validation_and_consumption added to named T2 tests (now 6 total). Branch: feature/phase1-specification-planning.
- v1.5.4 — 2026-11-16 — Wave 3 Response Contract Correction (W3-RC): resolved the REQ-W1.5.4 ↔ design §11.3 conflict reported in docs/reports/phase1-wave3-codex-report.md. REQ-W1.5.4 refined to require the run-detail response to expose ALL associated ApprovalRequest records via an `approvals` field plus a `pending_approvals` pending-only subset (backward compatibility); added W1.5.4a (both fields typed `list[ApprovalResponse]`, ordered by `created_at` ascending; `pending_approvals` = pending subset of `approvals`), W1.5.4b (empty list `[]`, never `null`, when no approvals), W1.5.4c (read-only projection; no mutation, no restoration, no approval-lifecycle change). See design §11.3, §4.3, ADR-0013; tasks A1, A5. Branch: feature/phase1-wave3-integration-execution.
- v1.5.5 — 2026-11-16 — Wave 4 Specification Conflict Resolution (W4-CR): resolved four Wave 4 conflicts reported in docs/reports/phase1-wave4-spec-resolution.md. Conflict A (MCP transport): REQ-M1.2 transport corrected — `MCPClient` launches the configured server via an explicit-environment subprocess (`asyncio.create_subprocess_exec(..., env=resolved_env)`) feeding the MCP Python SDK `ClientSession`; the SDK `stdio_client` is no longer required because it merges the parent environment (`get_default_environment()`) into the supplied dict and exposes no 5 s termination grace; required system env vars (PATH, SYSTEMROOT, WINDIR, etc.) are explicitly added to `resolved_env` (REQ-M1.5, REQ-S1.5). Conflict B (approval binding): `mcp_approvals.workflow_run_id` FK changed from `ON DELETE SET NULL` to `ON DELETE RESTRICT` (REQ-M2.1 M2.1.3) so an APPROVED approval bound to a deleted run cannot become a valid unbound (NULL) authorization via NULL-to-NULL context match; 5 new named deletion/binding tests added; deletion-invariant note added to REQ-M1.7. Conflict C (live adapter capability metadata): design §6.2 corrected — live adapters return `IntegrationCapability(available_in_phase_0=False)`; the Phase 0 schema is immutable `Literal[False]`, so `available_in_phase_0=True` is impossible (pydantic ValidationError); live/stub distinction expressed via `execution_mode`, the `mode` field (Task I6), and `stub=False`. Conflict D (page numbering): confirmed Wave 4 updates existing `9_Integrations.py` and `10_Settings.py` (REQ-I1.6, REQ-U1.5); no new Integrations/Settings pages created. Branch: feature/phase1-wave4-integration-execution.
- v1.5.6 — 2026-11-16 — Wave 4 Final FK Contract Correction (W4-FK): resolved the v1.5.5 RESTRICT contradiction. SQLite's `ON DELETE RESTRICT` is unconditional — it blocks deletion whenever ANY referencing `mcp_approvals` row exists, regardless of approval status — so the v1.5.5 acceptance criteria (CONSUMED/PENDING/REJECTED/EXPIRED approvals permit deletion) were unimplementable. `mcp_approvals.workflow_run_id` FK changed from `ON DELETE RESTRICT` back to `ON DELETE SET NULL`, combined with a database-enforced BEFORE DELETE trigger on `workflow_runs` (`trg_workflow_runs_before_delete_expire_approved_mcp_approvals`) that sets `status='EXPIRED'` on every APPROVED MCPApproval referencing the run BEFORE the FK clears the reference. The trigger runs in the same transaction as the DELETE, so ROLLBACK restores the approval. Verified against real SQLite foreign-key enforcement (SQLite library 3.49.1): APPROVED→EXPIRED; CONSUMED/PENDING/REJECTED/EXPIRED preserved with FK cleared to NULL; originally-unbound approvals unaffected; the EXPIRED approval cannot be consumed (`consume_atomic` 0 rows); cascaded deletion (workflow delete → run cascade) expires APPROVED; project delete does not reach runs. The deletion/binding test set updated: 1 renamed (`test_workflow_run_deletion_blocked_with_approved_mcp_approval` → `test_workflow_run_deletion_expires_approved_mcp_approval`, behavior changed from block to expire), 4 kept (rationale updated), 4 added (`test_workflow_run_deletion_preserves_consumed_approval`, `test_workflow_run_deletion_preserves_rejected_approval`, `test_expired_approval_after_deletion_cannot_be_consumed`, `test_trigger_rollback_restores_approval`). See docs/reports/phase1-wave4-fk-final-resolution.md. Branch: feature/phase1-wave4-integration-execution.
- v1.5.7 — 2026-11-16 — Wave 4 PENDING Approval Lifecycle Correction (W4-PA): resolved the remaining MCP authorization lifecycle gap. A PENDING MCPApproval bound to workflow run X survived deletion of X with `status='PENDING'` and `workflow_run_id=NULL`, indistinguishable from an originally-unbound PENDING approval; a future resolve operation could promote it to APPROVED, authorizing an unbound invocation. Fix: REQ-M2.1 trigger description updated — BEFORE DELETE trigger now expires `status IN ('PENDING','APPROVED')` (renamed `trg_workflow_runs_before_delete_expire_mcp_approvals`; W4-PA); M2.1.3 updated with new trigger name and PENDING coverage; M2.1.7 updated: PENDING→EXPIRED on run deletion is now explicit; M2.1.9 updated: PENDING→EXPIRED (not preserved); deletion lifecycle table updated: PENDING→EXPIRED. Named deletion/binding tests updated: `test_workflow_run_deletion_allowed_with_pending_approval` renamed to `test_workflow_run_deletion_expires_pending_mcp_approval`; `test_cascaded_deletion_handles_mcp_approvals` updated (PENDING also expires on cascade); `test_trigger_rollback_restores_approval` updated (restores both PENDING and APPROVED). Added: `test_orphaned_pending_approval_cannot_be_promoted`. Approval resolution rejects non-PENDING status: an EXPIRED approval (whether by TTL or run-deletion trigger) cannot be resolved or promoted to APPROVED. Verified with real SQLite: 23/23 assertions pass. See docs/reports/phase1-wave4-pending-approval-resolution.md. Branch: feature/phase1-wave4-integration-execution.
- v1.5.8 — 2026-11-16 — Wave 5 GitHub Orchestration Security Specification (W5-GC): added GitHubConfirmation status field (ISSUED/EXPIRED/USED), BEFORE DELETE trigger on workflow_runs for github_confirmations, complete confirmation security contract (REQ-G1.4), execution outcome definitions (SUCCEEDED/FAILED/INDETERMINATE), and all required negative and named tests. Status field closes the NULL-to-NULL bypass risk for GitHubConfirmations (same pattern as MCPApproval in W4-PA). Migration 007 DDL updated to include status column, CHECK constraint, and trigger. All 10 security contract negative tests added to REQ-G1.4 and G5. Execution outcomes added to REQ-M2.4 scope (GitHub). Version bumped, branch updated. Branch: feature/phase1-wave5-github-orchestration.
- v1.5.9 — 2026-11-16 — Wave 5 Security Resolution (W5-SR): resolved three security-sensitive specification conflicts reported by Codex before Wave 5 implementation. (1) HTTP outcome classification refined: 4xx responses (400/401/403/404/409/422) are FAILED (definitively did NOT execute on GitHub); 5xx responses (500/502/503/504) and all transport errors (httpx.TimeoutException, asyncio.TimeoutError, httpx.ConnectError, httpx.ReadError) are INDETERMINATE (may or may not have executed on GitHub) — this is the key distinction the prior v1.5.8 text conflated. (2) Canonical parameter binding: exact Python canonical payload functions defined for branch_create and pr_create operations — `json.dumps(..., sort_keys=True, separators=(',',':'))` with SHA-256 hex; normalization rules added (strip whitespace, lowercase repo_full_name, preserve branch/ref case, body='' when None); issuance and consumption use the identical canonical function; repo_full_name from server-side RepositoryConfig, never from client string. (3) Trusted actor and workflow context: `actor_id` source defined as `Settings.LOCAL_OPERATOR_ID` (default `'local_operator'`), never from request body; Phase 1 is explicitly local-first single-user; all Phase 1 GitHub operations are standalone (`workflow_run_id=None`); workflow-bound GitHub operations deferred to future phase. New named tests added: 6 HTTP-outcome tests, 6 canonical-binding tests, 4 actor/workflow-context tests. See docs/reports/phase1-wave5-security-resolution.md. Branch: feature/phase1-wave5-github-orchestration.

---

## Overview

Phase 1 is the first functional release of DevFlow AI. It replaces Phase 0 stubs with real, database-backed behaviour across five areas: persistent project management, workflow orchestration foundation, integration execution, MCP client infrastructure, and GitHub workflow support. The Streamlit UI is upgraded from placeholder pages to working project and workflow interfaces.

**Workflow execution boundary (Phase 1):** Phase 1 provides workflow state tracking with a human-approval gate. WorkflowRun records progress through states via explicit API calls; no autonomous AI provider invocation occurs in Phase 1. Reading `definition_json` and executing workflow steps automatically is out of scope and deferred to Phase 2.

Phase 1 builds exclusively on the Phase 0 foundation. It does not replace, rename, or restructure any approved Phase 0 module.

### Global Constraints (apply to all requirements below)

- The application MUST remain local-first with free core functionality.
- The codebase MUST NOT contain Android, React, TypeScript, or Vite artefacts.
- No hardcoded credentials or secrets MUST appear in source control at any time.
- All development services MUST bind exclusively to `127.0.0.1` on the host interface.
- Architecture boundaries from Phase 0 (UI → API → domain services → adapters → storage) MUST be preserved.
- Phase 0 specification files MUST NOT be modified.
- Phase 0 tests MUST continue to pass without modification.
- Every task MUST be small enough to be independently testable.
- Consequential actions (modifying files, Git branches, PRs, external resources) MUST require explicit user approval before execution.
- `datetime.utcnow()` MUST NOT appear anywhere in Phase 1 code; use `datetime.now(UTC)` exclusively.
- All new timestamp columns MUST use `UTCDateTime` TypeDecorator from `src/devflow_api/models/base.py`.

---

## Out of Scope for Phase 1

The following capabilities are explicitly deferred. No Phase 1 component may implement or assume them:

| Capability | Deferral reason |
|---|---|
| Autonomous AI step execution from `definition_json` | Requires safe execution sandbox and step-type dispatch — Phase 2 |
| ChatGPT / Claude live adapters | Requires paid API key; free-first policy |
| Codex CLI live execution | Real subprocess execution is a separate safety concern; stub approved for Phase 1 |
| NotebookLM, Kiro live adapters | No public programmatic API |
| MCP SSE / HTTP transports | Phase 2 when connection pooling requirements are clearer |
| Multi-user access control | Local single-user tool in Phase 1 |
| PR auto-merge | Policy decision — will never be default; explicit scope exclusion |

---

## Area 1 — Persistent Project Management

### REQ-P1.1
WHEN a user submits a valid project creation request,
THEN the FastAPI `POST /api/v1/projects` endpoint MUST persist the project to SQLite via the `ProjectRepository` and return the created `ProjectResponse` with a database-assigned `id`, `created_at`, and `updated_at`.

**Acceptance Criteria:**
P1.1.1 — `POST /api/v1/projects` with `{"name": "My Project"}` returns HTTP 201 with a `ProjectResponse` containing a non-zero `id` and ISO 8601 UTC timestamps for `created_at` and `updated_at`.
P1.1.2 — A subsequent `GET /api/v1/projects/{id}` returns the same project.
P1.1.3 — `POST /api/v1/projects` with an empty `name` field returns HTTP 422.
P1.1.4 — Two `POST` requests with identical names produce two separate records with distinct `id` values (names are not unique-constrained at the data layer).
P1.1.5 — The `ProjectRepository.create` method is covered by a unit test using an in-memory SQLite database.

### REQ-P1.2
WHEN a user requests the project list,
THEN `GET /api/v1/projects` MUST return all persisted projects from the database, support optional `status` filter and `limit`/`offset` pagination query parameters, and return an empty list (not an error) when no projects exist.

**Acceptance Criteria:**
P1.2.1 — `GET /api/v1/projects` returns HTTP 200 with a JSON array.
P1.2.2 — `GET /api/v1/projects?status=active` returns only projects with `status == "active"`.
P1.2.3 — `GET /api/v1/projects?limit=5&offset=0` returns at most 5 items.
P1.2.4 — `GET /api/v1/projects?status=invalid_value` returns HTTP 422.
P1.2.5 — `GET /api/v1/projects` on an empty database returns `[]` with HTTP 200.

### REQ-P1.3
WHEN a user updates a project,
THEN `PUT /api/v1/projects/{id}` MUST update only the fields explicitly provided in the request body, update the `updated_at` timestamp to the current UTC time, and return the full updated `ProjectResponse`.

**Null semantics:** A `ProjectUpdate` field set to `null` in the JSON body is treated identically to omitting the field — both skip the field (leave it unchanged). There is no way to clear an existing non-null field value via `PUT` in Phase 1. This is intentional and matches the `ProjectUpdate` Pydantic schema where `null` and absent both map to `None` in Python.

**Acceptance Criteria:**
P1.3.1 — `PUT /api/v1/projects/{id}` with changed `name` returns HTTP 200 with the updated name.
P1.3.2 — `updated_at` in the response is strictly later than `created_at` after a successful update.
P1.3.3 — `PUT /api/v1/projects/9999` returns HTTP 404 with `{"error": "Not found", "code": "NOT_FOUND"}`.
P1.3.4 — `PUT /api/v1/projects/{id}` with `status = "invalid"` returns HTTP 422.
P1.3.5 — `PUT /api/v1/projects/{id}` with `{"description": null}` does NOT clear the existing description — the value is unchanged (null = skip).

### REQ-P1.4
WHEN a user deletes a project,
THEN `DELETE /api/v1/projects/{id}` MUST remove the record from the database and return HTTP 204. Deleting a non-existent project MUST return HTTP 404.

**Acceptance Criteria:**
P1.4.1 — `DELETE /api/v1/projects/{id}` for an existing project returns HTTP 204.
P1.4.2 — A subsequent `GET /api/v1/projects/{id}` for the deleted project returns HTTP 404.
P1.4.3 — `DELETE /api/v1/projects/9999` returns HTTP 404.

### REQ-P1.5
WHEN project schemas are defined for Phase 1,
THEN `ProjectResponse` MUST include `created_at: datetime` and `updated_at: datetime` fields in addition to the Phase 0 fields, and `ProjectCreate` MUST be extended with an optional `tags: list[str]` field stored as a JSON-encoded TEXT column.

**Acceptance Criteria:**
P1.5.1 — `ProjectResponse` schema includes `id`, `name`, `description`, `status`, `tags`, `created_at`, `updated_at`.
P1.5.2 — `created_at` and `updated_at` in API responses are ISO 8601 strings with UTC timezone offset (`+00:00` or `Z`).
P1.5.3 — `tags` defaults to `[]` when not provided.
P1.5.4 — `mypy --strict src/devflow_api/schemas/project.py` exits with code 0.

### REQ-P1.6
WHEN the Streamlit Projects page is active,
THEN it MUST replace the Phase 0 placeholder with a functional UI showing the project list, a create-project form, and project detail/edit actions connected to the FastAPI backend via `APIClient`.

**Acceptance Criteria:**
P1.6.1 — The Projects page renders without exception when the backend is available (verified by `AppTest` with a mocked `APIClient`).
P1.6.2 — The Projects page shows a "Backend unavailable" notice (not an exception) when the backend is unreachable.
P1.6.3 — The create-project form validates that `name` is non-empty before submitting.
P1.6.4 — The page does not display hard-coded or fabricated project data.
P1.6.5 — `mypy --strict src/devflow_ui/pages/2_Projects.py` exits with code 0.

---

## Area 2 — Workflow Orchestration Foundation

**Scope note:** Phase 1 provides the data layer, state machine, approval gates, and audit log for workflow orchestration. WorkflowRun status transitions are driven by explicit API calls only. Autonomous reading and execution of `definition_json` step definitions is NOT implemented in Phase 1 — that is deferred to Phase 2.

### REQ-W1.1
WHEN a workflow is defined,
THEN a `Workflow` SQLAlchemy model MUST exist in `src/devflow_api/models/workflow.py` with the following columns: `id` (INTEGER PK), `name` (TEXT NOT NULL), `description` (TEXT), `project_id` (INTEGER FK → projects.id, nullable), `status` (TEXT, constrained to `draft | active | paused | completed | failed`), `definition_json` (TEXT — workflow step definitions, stored for future Phase 2 execution; not read or executed in Phase 1), `created_at` (UTCDateTime), `updated_at` (UTCDateTime).

**Acceptance Criteria:**
W1.1.1 — `Workflow` model is importable from `devflow_api.models.workflow`.
W1.1.2 — `mypy --strict src/devflow_api/models/workflow.py` exits with code 0.
W1.1.3 — `status` column has a `CheckConstraint` enforcing the allowed values.
W1.1.4 — `project_id` is a nullable foreign key with `ON DELETE SET NULL`.
W1.1.5 — `created_at` and `updated_at` use `UTCDateTime` TypeDecorator.

### REQ-W1.2
WHEN a workflow execution is tracked,
THEN a `WorkflowRun` SQLAlchemy model MUST exist in `src/devflow_api/models/workflow.py` with columns: `id` (INTEGER PK), `workflow_id` (INTEGER FK → workflows.id NOT NULL), `status` (TEXT, constrained to `pending | running | waiting_approval | completed | failed | cancelled`), `started_at` (UTCDateTime nullable), `completed_at` (UTCDateTime nullable), `result_json` (TEXT), `error_message` (TEXT), `created_at` (UTCDateTime), `updated_at` (UTCDateTime).

**WorkflowRun status definitions:**

| Status | Meaning |
|---|---|
| `pending` | Record created; no work started. Run waits for a `transition_run` call to `running`. |
| `running` | Active processing in progress. Only state from which `completed`, `failed`, `waiting_approval`, or `cancelled` can be reached. |
| `waiting_approval` | An approval gate was reached. The run is paused until an `ApprovalRequest` is resolved. |
| `completed` | All steps finished successfully (terminal). `completed_at` is set. |
| `failed` | An unhandled error occurred (terminal). `error_message` is set. `completed_at` is set. |
| `cancelled` | Cancelled by user action on a `running` run, or by an `ApprovalRequest` being rejected (terminal). |

**Note:** `paused` is a `Workflow` (definition) status, not a `WorkflowRun` status. `WorkflowRun` does not have a `paused` state.

**Acceptance Criteria:**
W1.2.1 — `WorkflowRun` model is importable from `devflow_api.models.workflow`.
W1.2.2 — `status` column enforces its allowed values via `CheckConstraint` with exactly: `pending`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled`.
W1.2.3 — `workflow_id` is a non-nullable foreign key; deleting a workflow MUST cascade to delete its runs.
W1.2.4 — `mypy --strict src/devflow_api/models/workflow.py` exits with code 0.
W1.2.5 — `WorkflowRun` does NOT have a `paused` status value.

### REQ-W1.3
WHEN a workflow approval gate is reached,
THEN an `ApprovalRequest` SQLAlchemy model MUST exist in `src/devflow_api/models/approval.py` with columns: `id` (INTEGER PK), `workflow_run_id` (INTEGER FK → workflow_runs.id NOT NULL), `step_name` (TEXT NOT NULL), `action_description` (TEXT NOT NULL — human-readable description of the pending action), `payload_json` (TEXT — the data the action would operate on), `status` (TEXT, constrained to `pending | approved | rejected | expired`), `requested_at` (UTCDateTime NOT NULL — domain timestamp visible in API responses), `resolved_at` (UTCDateTime nullable), `resolved_by` (TEXT nullable), `created_at` (UTCDateTime NOT NULL — from TimestampMixin, used for audit ordering), `updated_at` (UTCDateTime NOT NULL — from TimestampMixin).

**Note on `requested_at` vs `created_at`:** Both are set at record creation and will have the same value. `created_at` is the TimestampMixin field used for consistent audit log ordering across all models. `requested_at` is the domain-semantic field exposed in `ApprovalResponse` and meaningful to users. Both are required.

**Acceptance Criteria:**
W1.3.1 — `ApprovalRequest` is importable from `devflow_api.models.approval`.
W1.3.2 — `status` enforces allowed values via `CheckConstraint`.
W1.3.3 — `workflow_run_id` is a non-nullable foreign key; deleting a workflow run MUST cascade to delete its approval requests.
W1.3.4 — `mypy --strict src/devflow_api/models/approval.py` exits with code 0.
W1.3.5 — A `WorkflowRun` with status `waiting_approval` MUST have at least one `ApprovalRequest` with status `pending` (enforced by application logic, not DB constraint — verified in service unit tests).

### REQ-W1.4
WHEN workflow CRUD operations are performed,
THEN `GET/POST /api/v1/workflows` and `GET/PUT/DELETE /api/v1/workflows/{id}` MUST be implemented with database persistence, following the same repository-service-router layering as projects.

**Acceptance Criteria:**
W1.4.1 — `POST /api/v1/workflows` with valid body returns HTTP 201 with a workflow containing `id` and timestamps.
W1.4.2 — `GET /api/v1/workflows?project_id={id}` returns only workflows for the specified project.
W1.4.3 — `GET /api/v1/workflows?status=active` filters by status.
W1.4.4 — `DELETE /api/v1/workflows/{id}` cascades to delete associated `WorkflowRun` records.
W1.4.5 — All five endpoints appear in `/openapi.json` under `/api/v1/workflows`.

### REQ-W1.5
WHEN a workflow run is created and managed,
THEN `POST /api/v1/workflows/{id}/runs`, `GET /api/v1/workflows/{id}/runs`, and `GET /api/v1/workflow-runs/{run_id}` MUST be implemented and persist `WorkflowRun` records with accurate status transitions.

**WorkflowRun lifecycle (Phase 1 scope):**

| Operation | What Phase 1 does | What is deferred |
|---|---|---|
| Create run (`POST .../runs`) | Inserts `WorkflowRun` with `status=pending`; logs `run_created` audit event | — |
| Start run (transition to `running`) | Calls `WorkflowService.transition_run(run_id, "running", actor)`; logs `run_status_changed` | Automatic step execution from `definition_json` |
| Approval gate | Calls `ApprovalService.request_approval`; transitions run to `waiting_approval`; creates `ApprovalRequest` | — |
| Approve | Resolves `ApprovalRequest`; transitions run back to `running`; logs `approval_resolved` | — |
| Reject | Resolves `ApprovalRequest` as rejected; transitions run to `cancelled` | — |
| Complete run (transition to `completed`) | Calls `transition_run(run_id, "completed", actor)`; sets `completed_at`; logs `run_status_changed` | — |
| Fail run (transition to `failed`) | Calls `transition_run(run_id, "failed", actor)`; sets `error_message`; logs `run_status_changed` | — |
| Cancel run | Calls `transition_run(run_id, "cancelled", actor)` from `running` state | — |

**Acceptance Criteria:**
W1.5.1 — `POST /api/v1/workflows/{id}/runs` returns HTTP 201 with `status = "pending"`.
W1.5.2 — A run's `status` transitions are enforced: `pending → running → waiting_approval | completed | failed | cancelled`.
W1.5.3 — Transitioning to an invalid status (e.g., `pending → completed` skipping `running`) returns HTTP 422 with `code = "INVALID_STATUS_TRANSITION"`.
W1.5.4 — `GET /api/v1/workflow-runs/{run_id}` returns the full run including ALL associated `ApprovalRequest` records. The response exposes every approval for the run via an `approvals` field, plus a `pending_approvals` field that is the pending-only subset (backward compatibility). Resolved and expired approvals remain visible in `approvals`; this is a read-only projection and does not mutate, reopen, or restore any `ApprovalRequest` or change the approval lifecycle (REQ-W1.6).
W1.5.4a — `WorkflowRunResponse.approvals: list[ApprovalResponse]` contains every associated `ApprovalRequest` regardless of status (`pending`, `approved`, `rejected`, `expired`), ordered by `created_at` ascending. `WorkflowRunResponse.pending_approvals: list[ApprovalResponse]` is the subset of `approvals` whose `status == "pending"`, in the same order.
W1.5.4b — When a run has no associated approvals, both `approvals` and `pending_approvals` return an empty list (`[]`), never `null`.
W1.5.4c — Resolved approvals (`approved`, `rejected`, `expired`) remain visible in `approvals`. Reading them does not change `ApprovalRequest.status`, `resolved_at`, `resolved_by`, or any audit log entry; the approval lifecycle defined in REQ-W1.6 is unchanged.
W1.5.5 — No Phase 1 code path reads `definition_json` and executes steps from it autonomously.

### REQ-W1.6
WHEN an approval gate is pending,
THEN `GET /api/v1/approvals?status=pending`, `GET /api/v1/approvals/{id}`, and `POST /api/v1/approvals/{id}/resolve` MUST be implemented. Resolving an approval MUST update the `ApprovalRequest` status, set `resolved_at` to current UTC time, and resume or cancel the associated `WorkflowRun` based on the resolution.

**Acceptance Criteria:**
W1.6.1 — `GET /api/v1/approvals?status=pending` returns all unresolved approvals.
W1.6.2 — `POST /api/v1/approvals/{id}/resolve` with `{"decision": "approved"}` sets `ApprovalRequest.status = "approved"` and `WorkflowRun.status = "running"`.
W1.6.3 — `POST /api/v1/approvals/{id}/resolve` with `{"decision": "rejected"}` sets `ApprovalRequest.status = "rejected"` and `WorkflowRun.status = "cancelled"`.
W1.6.4 — Resolving an already-resolved approval returns HTTP 409 with `{"error": "...", "code": "APPROVAL_ALREADY_RESOLVED"}`.
W1.6.5 — `resolved_by` is set from the request body when provided.

### REQ-W1.7
WHEN an audit trail is required,
THEN a `WorkflowAuditLog` SQLAlchemy model MUST exist in `src/devflow_api/models/audit.py` with columns: `id` (INTEGER PK), `workflow_run_id` (INTEGER FK nullable), `event_type` (TEXT NOT NULL), `actor` (TEXT NOT NULL — `"system"` or `"user"`), `payload_json` (TEXT), `created_at` (UTCDateTime). Every status transition on `WorkflowRun` or `ApprovalRequest` MUST generate an audit log entry.

**Required audit event types:**

| Event type | Trigger | Actor |
|---|---|---|
| `run_created` | `WorkflowService.create_run` | `"system"` |
| `run_status_changed` | `WorkflowService.transition_run` | `"system"` or `"user"` (passed via `actor` param) |
| `approval_requested` | `ApprovalService.request_approval` (transitions run to `waiting_approval`) | `"system"` |
| `approval_resolved` | `ApprovalService.resolve` | `"user"` |
| `branch_created` | `RepositoryService.create_branch` | `"user"` |
| `pr_created` | `RepositoryService.create_pull_request` | `"user"` |
| `github_confirmation_issued` | `POST /api/v1/github-confirmations` | `"user"` |
| `github_action_authorized` | `RepositoryService` validates a `GitHubConfirmation` before action | `"user"` |
| `github_action_executed` | `RepositoryService` completes branch/PR creation | `"user"` |
| `github_action_rejected` | `RepositoryService` rejects an invalid/expired/used confirmation | `"user"` |
| `github_action_failed` | GitHub API call result was FAILED or INDETERMINATE after confirmation consumption | `"user"` |
| `github_confirmation_expired` | BEFORE DELETE trigger expired an ISSUED `GitHubConfirmation` on `workflow_runs` deletion | `"system"` |
| `mcp_approval_requested` | `MCPService` before calling a consequential/unknown tool | `"system"` |
| `mcp_approval_granted` | Approval resolved as approved for an MCP tool call | `"user"` |
| `mcp_approval_denied` | Approval explicitly rejected by a human approver for an MCP tool call (NOT expiry — expiry emits `mcp_approval_expired`) | `"user"` |
| `mcp_approval_expired` | `MCPApproval.expires_at` elapsed before use — TTL timeout, NOT a human rejection | `"system"` |
| `mcp_approval_missing` | No `MCPApproval` found when a consequential/unknown tool call is attempted | `"system"` |
| `mcp_approval_rejected` | An `MCPApproval` lookup or validation fails at invocation time — MUST include a `reason` field with one of: `workflow_run_mismatch`, `missing_workflow_context`, `unexpected_workflow_context`, `mismatched_binding`, `expired`, `already_consumed` | `"system"` |
| `mcp_tool_invoked` | `MCPClient.call_tool` launched (approval consumed, subprocess launched) | `"system"` |
| `mcp_tool_completed` | `MCPClient.call_tool` returned success — DISTINCT from `mcp_tool_invoked` | `"system"` |
| `mcp_tool_failed` | `MCPClient.call_tool` raises any exception or times out | `"system"` |

**Acceptance Criteria:**
W1.7.1 — `WorkflowAuditLog` is importable from `devflow_api.models.audit`.
W1.7.2 — Creating a `WorkflowRun` generates an audit log entry with `event_type = "run_created"`.
W1.7.3 — Every `WorkflowRun` status transition generates an audit log entry with `event_type = "run_status_changed"` and the old/new status in `payload_json`.
W1.7.4 — Calling `ApprovalService.request_approval` generates an audit log entry with `event_type = "approval_requested"`.
W1.7.5 — Resolving an `ApprovalRequest` generates an audit log entry with `event_type = "approval_resolved"`.
W1.7.6 — `GET /api/v1/workflow-runs/{run_id}/audit` returns the full audit log for a run, ordered by `created_at` ascending.
W1.7.7 — Issuing a `GitHubConfirmation` logs `github_confirmation_issued`; executing the action logs `github_action_authorized` and `github_action_executed`; rejecting a confirmation logs `github_action_rejected`; a FAILED or INDETERMINATE GitHub API outcome logs `github_action_failed`; expiry of an ISSUED confirmation via the BEFORE DELETE trigger logs `github_confirmation_expired`.
W1.7.8 — MCP service operations log the eight MCP audit events defined in REQ-M1.7 (`mcp_approval_requested`, `mcp_approval_granted`, `mcp_approval_denied`, `mcp_approval_expired`, `mcp_approval_missing`, `mcp_tool_invoked`, `mcp_tool_completed`, `mcp_tool_failed`). `mcp_approval_denied` MUST NOT be emitted on expiry; `mcp_approval_expired` MUST be emitted instead. `mcp_tool_completed` is DISTINCT from `mcp_tool_invoked`.

---

## Area 3 — Integration Execution

### REQ-I1.1
WHEN the GitHub adapter is invoked,
THEN the `GitHubAdapter` MUST replace the Phase 0 `GitHubStubAdapter` with a live implementation that uses `httpx` to call the GitHub REST API v3, authenticates with `GITHUB_TOKEN` from `Settings`, and raises `MissingCredentialError` when the token is absent.

**Acceptance Criteria:**
I1.1.1 — `GitHubAdapter.create_issue(repo, title, body)` calls `POST https://api.github.com/repos/{repo}/issues` and returns a `GitHubIssueResponse` with `stub=False`.
I1.1.2 — When `GITHUB_TOKEN` is `None`, calling any action method raises `MissingCredentialError` before any network call.
I1.1.3 — HTTP errors from GitHub (4xx, 5xx) raise `IntegrationExecutionError` with the status code and body preserved in the error.
I1.1.4 — All GitHub adapter methods have a default timeout of 10 seconds enforced via `httpx.AsyncClient(timeout=10.0)`.
I1.1.5 — Unit tests mock `httpx.AsyncClient` and do NOT require a real GitHub token or network access.
I1.1.6 — `GitHubStubAdapter` remains in `stubs/github.py` and in the registry when `GITHUB_TOKEN` is absent (live adapter is only used when explicitly configured).

### REQ-I1.2
WHEN the Ollama adapter is invoked,
THEN the `OllamaAdapter` MUST replace the Phase 0 stub with a live implementation that calls the Ollama local REST API at `OLLAMA_BASE_URL` from `Settings`, requires no API key, and handles the case where Ollama is not running.

**Acceptance Criteria:**
I1.2.1 — `OllamaAdapter.generate(model, prompt)` calls `POST {OLLAMA_BASE_URL}/api/generate` and returns an `OllamaResponse` with `stub=False`.
I1.2.2 — When Ollama is not running (connection refused), `health_check()` returns `{"status": "unavailable", ...}` without raising.
I1.2.3 — `OllamaAdapter.generate` has a configurable timeout defaulting to 30 seconds (via `Settings.OLLAMA_TIMEOUT_SECONDS`).
I1.2.4 — Unit tests mock `httpx.AsyncClient` and do NOT require Ollama to be running.
I1.2.5 — `OllamaStubAdapter` remains available for environments without Ollama.

### REQ-I1.3
WHEN the Figma adapter is invoked,
THEN the `FigmaAdapter` MUST replace the Phase 0 stub with a live implementation that calls the Figma REST API, authenticates with `FIGMA_TOKEN` from `Settings`, and raises `MissingCredentialError` when the token is absent.

**Acceptance Criteria:**
I1.3.1 — `FigmaAdapter.get_file(file_key)` calls `GET https://api.figma.com/v1/files/{file_key}` and returns a `FigmaResponse` with `stub=False`.
I1.3.2 — When `FIGMA_TOKEN` is `None`, calling `get_file` raises `MissingCredentialError`.
I1.3.3 — HTTP errors from Figma raise `IntegrationExecutionError`.
I1.3.4 — Default timeout is 10 seconds.
I1.3.5 — Unit tests mock `httpx.AsyncClient`.

### REQ-I1.4
WHEN integration adapters are selected at runtime,
THEN the adapter registry MUST support a `get_live(name: str) -> BaseAdapterProtocol` method that returns the live adapter when one is configured and available, falling back to the stub when the live adapter cannot be initialised (e.g., missing credential).

**Acceptance Criteria:**
I1.4.1 — `registry.get_live("github")` returns a `GitHubAdapter` instance when `GITHUB_TOKEN` is set.
I1.4.2 — `registry.get_live("github")` returns a `GitHubStubAdapter` instance when `GITHUB_TOKEN` is not set.
I1.4.3 — `registry.get_live("kiro")` always returns `KiroStubAdapter` (no live Kiro adapter exists in Phase 1).
I1.4.4 — `registry.get("name")` continues to return the stub adapter (unchanged Phase 0 behaviour).
I1.4.5 — `mypy --strict src/devflow_api/adapters/registry.py` exits with code 0.

### REQ-I1.5
WHEN an integration error occurs,
THEN `IntegrationExecutionError` MUST be defined in `src/devflow_api/adapters/exceptions.py` with fields: `integration_name: str`, `action: str`, `status_code: int | None`, `message: str`. The FastAPI error handler MUST convert `IntegrationExecutionError` to HTTP 502 with `{"error": "...", "code": "INTEGRATION_ERROR"}`.

**Acceptance Criteria:**
I1.5.1 — `IntegrationExecutionError` is importable from `devflow_api.adapters.exceptions`.
I1.5.2 — `GET /api/v1/integrations/{name}/health` for an adapter that raises `IntegrationExecutionError` returns HTTP 502.
I1.5.3 — `mypy --strict src/devflow_api/adapters/exceptions.py` exits with code 0.

### REQ-I1.6
WHEN the Integrations page is active in Phase 1,
THEN the Streamlit Integrations page (9_Integrations.py) MUST display the live integration status for all adapters, showing `execution_mode`, current health status, and whether live or stub mode is active.

**Page-numbering note (W4-CR Conflict D):** `9_Integrations.py` is an EXISTING Phase 0 page (present in `src/devflow_ui/pages/`). Wave 4 UPDATEs it in place (replaces the placeholder content with live status); it does NOT create a new page and does NOT renumber the navigation. The canonical page name is `9_Integrations.py` (consistent with design §12.1 and Task I7); the repository does not contain `3_Integrations.py`.

**Acceptance Criteria:**
I1.6.1 — The Integrations page renders without exception when the backend is available (verified by `AppTest` with mocked `APIClient`).
I1.6.2 — Each integration card shows: `name`, `execution_mode`, `status` (from health check), and `mode: live | stub`.
I1.6.3 — The page shows "Backend unavailable" when the API is unreachable.
I1.6.4 — No integration card shows hardcoded status; all data comes from `APIClient`.

---

## Area 4 — MCP Client Infrastructure

### REQ-M1.1
WHEN MCP servers are configured,
THEN a `MCPServerConfig` Pydantic v2 model MUST be defined in `src/devflow_api/adapters/mcp_client.py` with fields: `name: str`, `command: list[str]`, `args: list[str]`, `env: dict[str, str]`, `timeout_seconds: int` (default 30), `enabled: bool` (default True), `allowed_tools: list[str]` (default `["*"]`). MCP server configurations MUST be loaded from `MCP_SERVERS_CONFIG` in `Settings` as a JSON array.

**Acceptance Criteria:**
M1.1.1 — `MCPServerConfig` is importable from `devflow_api.adapters.mcp_client`.
M1.1.2 — `Settings.MCP_SERVERS_CONFIG` is parsed as `list[MCPServerConfig]` by a Pydantic validator.
M1.1.3 — An empty `MCP_SERVERS_CONFIG` string parses to an empty list (no error).
M1.1.4 — An invalid JSON value for `MCP_SERVERS_CONFIG` raises `ValidationError` on `Settings` instantiation.
M1.1.5 — `mypy --strict src/devflow_api/adapters/mcp_client.py` exits with code 0.

### REQ-M1.2
WHEN an MCP tool is invoked,
THEN the `MCPClient` MUST launch the configured server as an explicit-environment subprocess and drive the MCP protocol over its stdio using the MCP Python SDK `ClientSession`. `MCPClient` owns the subprocess lifecycle and the `SIGTERM → 5 s grace → SIGKILL` cleanup; it does NOT use the SDK `stdio_client` helper (W4-CR Conflict A: SDK v1.x `stdio_client` merges `get_default_environment()` into the supplied env dict, which breaks explicit environment isolation, and exposes no configurable termination grace period). `ClientSession` is the supported SDK interface used here.

**Transport contract (W4-CR Conflict A):**
- `MCPClient` spawns the server with `asyncio.create_subprocess_exec(*command, *args, env=resolved_env, stdin=PIPE, stdout=PIPE, stderr=...)`. Passing `env=resolved_env` (not `env=None`) means the child receives ONLY `resolved_env` — no parent-environment inheritance.
- `resolved_env` = interpolated `MCPServerConfig.env` (secrets via `${SECRET_NAME}` from `SecretStr` Settings fields) PLUS a minimal, explicit set of system variables required for the child to start: Windows `PATH`, `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`, `COMSPEC`; POSIX `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`. These are copied by name from the parent env, not by wholesale inheritance. No other parent variables are copied; no parent secrets are inherited.
- `MCPClient` bridges the subprocess stdout/stdin to anyio memory streams and constructs `ClientSession(read_stream, write_stream)` from the SDK. `ClientSession.initialize()` performs tool discovery; `call_tool` invokes the tool.
- Cleanup is deterministic and owned by `MCPClient` (see REQ-S1.5.2): in a `finally` block, send `SIGTERM`; wait up to 5 s for the process to exit; if still alive, send `SIGKILL`. On Windows `SIGTERM` maps to process termination via `Process.terminate()`; the 5 s grace and kill fallback are unchanged.
- No OS-level sandbox (seccomp/namespaces/cgroups/AppArmor) is claimed or implemented (Phase 2).

**Acceptance Criteria:**
M1.2.1 — `MCPClient.call_tool(server_name, tool_name, arguments)` returns an `MCPToolResult` with `content`, `is_error`, and `stub=False`.
M1.2.2 — Calling a tool on an unconfigured server raises `MCPServerNotFoundError`.
M1.2.3 — When the server process fails to start, `MCPClient.call_tool` raises `MCPConnectionError`.
M1.2.4 — Tool execution is bounded by `MCPServerConfig.timeout_seconds`; exceeding the limit raises `MCPTimeoutError`.
M1.2.5 — On timeout: SIGTERM is sent to the subprocess first; after a 5-second grace period, SIGKILL is sent if the process is still running. All subprocess interactions are wrapped in `try/finally` to ensure termination. This cleanup is owned by `MCPClient` (the subprocess owner), not delegated to the SDK `stdio_client` context manager.
M1.2.6 — Unit tests mock the MCP subprocess (`asyncio.create_subprocess_exec`) and `ClientSession`; they do NOT spawn real processes and do NOT require `stdio_client`.

### REQ-M1.3
WHEN MCP tool invocations are recorded,
THEN every `MCPClient.call_tool` invocation MUST generate a structured log entry containing: `server_name`, `tool_name`, `argument_keys` (not argument values — to avoid logging secrets), `duration_ms`, `success: bool`.

**Acceptance Criteria:**
M1.3.1 — A unit test captures structlog output and verifies the required fields are present.
M1.3.2 — Argument values are NOT logged (only keys).
M1.3.3 — Errors are logged at WARNING level with `success=False`.

### REQ-M1.4
WHEN MCP tool permissions are evaluated,
THEN each tool invocation MUST be checked against an allow-list defined in `MCPServerConfig.allowed_tools: list[str]` (defaults to `["*"]` meaning all tools allowed). Calling a tool not in the allow-list MUST raise `MCPPermissionError` without spawning a process.

**Note:** `allowed_tools` is a configuration-time permission control, not a per-invocation human approval. It restricts which tool names may be invoked against a configured server; it does not replace the `ApprovalRecord` gate for consequential workflow actions. Both checks are additive and sequential: the allow-list check runs first; if it passes, the approval gate check runs next. A tool call must pass BOTH checks to proceed.

**Acceptance Criteria:**
M1.4.1 — When `allowed_tools = ["read_file"]`, calling `write_file` raises `MCPPermissionError`.
M1.4.2 — When `allowed_tools = ["*"]`, any tool name is allowed.
M1.4.3 — `MCPPermissionError` is raised before any subprocess is started.
M1.4.4 — `mypy --strict` passes on the permission-check code path.

### REQ-M1.5
WHEN MCP secrets are required,
THEN `MCPServerConfig.env` MUST support `${SECRET_NAME}` interpolation resolved from `Settings` at runtime. Only `SecretStr` fields declared in `Settings` may be interpolated; arbitrary attribute access is not permitted. Secret values MUST NOT appear in log output.

**MCP subprocess trust statement:** MCP server binaries configured in `MCPServerConfig.command` are trusted by the operator who configured them. DevFlow AI does not verify binary signatures or hash values. The operator is responsible for ensuring the configured binary is trustworthy. The security boundary is environment-variable scoping and the allow-list defined in `MCPServerConfig.allowed_tools`.

**MCP subprocess isolation boundary:** The subprocess isolation boundary in Phase 1 is environment-variable scoping only. The launched process receives an explicit `resolved_env` dict: interpolated `MCPServerConfig.env` (secrets via `${SECRET_NAME}` from `SecretStr` Settings fields) PLUS a minimal, explicitly-named set of system variables required for the child to start (Windows: `PATH`, `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`, `COMSPEC`; POSIX: `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`). It does NOT inherit the parent process environment as a whole; no other parent variables (and no parent secrets) are copied. This is Python-level environment isolation, not OS-level sandbox isolation (no seccomp, namespaces, cgroups, or AppArmor). OS-level sandboxing is deferred to a future phase.

**Transport note (W4-CR Conflict A):** `MCPClient` spawns the subprocess with `asyncio.create_subprocess_exec(..., env=resolved_env)` and wraps its stdio in the MCP Python SDK `ClientSession`. The SDK `stdio_client` helper is NOT used: SDK v1.x `stdio_client` merges `get_default_environment()` (parent PATH, Windows `USERPROFILE`, etc.) into the supplied env dict, which would break the explicit-isolation requirement, and it exposes no configurable termination grace period. `ClientSession` is the supported SDK interface used here; the subprocess lifecycle and the `SIGTERM → 5 s grace → SIGKILL` cleanup are owned by `MCPClient`.

**Acceptance Criteria:**
M1.5.1 — `${GITHUB_TOKEN}` in `MCPServerConfig.env` is resolved to `Settings.GITHUB_TOKEN.get_secret_value()` at process launch time.
M1.5.2 — An unresolvable `${MISSING_KEY}` raises `MCPSecretResolutionError` before process launch.
M1.5.3 — Resolved secret values do not appear in any log record (verified by unit test capturing log output).
M1.5.4 — Only `Settings` attributes that are `SecretStr` fields (or explicitly declared as allowable) may be interpolated; referencing a non-secret Settings field via `${VAR}` raises `MCPSecretResolutionError`.
M1.5.5 — The subprocess is launched with `env=resolved_env` (not `env=None` which would inherit parent env). `resolved_env` is the ONLY environment the child receives — no parent-environment merge occurs (the SDK `stdio_client` parent-merge path is not used; see W4-CR Conflict A).
M1.5.6 — [W4-CR Conflict A] `resolved_env` includes a minimal, explicitly-named set of system variables required for the child to start (Windows: `PATH`, `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`, `COMSPEC`; POSIX: `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`), copied by name from the parent env. No other parent variables are copied; no parent secrets are inherited.
M1.5.7 — [W4-CR Conflict A] The subprocess is launched via `asyncio.create_subprocess_exec` with `env=resolved_env` and its stdio is wrapped in the SDK `ClientSession`; the SDK `stdio_client` is NOT used. A unit test asserts `asyncio.create_subprocess_exec` (not `stdio_client`) is the launch mechanism and that `env` is the resolved dict.

### REQ-M1.6
WHEN the `MCPAdapter` is used through the adapter registry,
THEN the Phase 0 `MCPStubAdapter` MUST be replaced by a `MCPLiveAdapter` that delegates to `MCPClient`, but falls back to `MCPStubAdapter` when no MCP servers are configured.

**Acceptance Criteria:**
M1.6.1 — `registry.get_live("mcp")` returns `MCPLiveAdapter` when at least one `MCPServerConfig` is configured and enabled.
M1.6.2 — `registry.get_live("mcp")` returns `MCPStubAdapter` when `MCP_SERVERS_CONFIG` is empty.
M1.6.3 — `MCPLiveAdapter.call_tool` delegates to `MCPClient`.
M1.6.4 — `MCPLiveAdapter.health_check()` returns `{"status": "ok", ...}` when the first configured server responds, `{"status": "unavailable", ...}` when no server responds, and `{"status": "stub", ...}` when in stub mode.

### REQ-M1.7
WHEN an MCP tool call is evaluated for approval,
THEN every MCP tool MUST be classified as `read_only`, `consequential`, or `unknown` before invocation, and a default-deny policy MUST apply to `consequential` and `unknown` tools. Approval MUST originate from a persisted `MCPApproval` record (in the `mcp_approvals` table, UUID PK) retrieved by `MCPService` from `MCPApprovalRepository` — the caller supplies only an `mcp_approval_id` (UUID); the caller may NOT supply a pre-constructed approval object.

**Separation of approval systems:** The workflow `approval_requests` table (integer PK, `ApprovalRequest` model) is used exclusively for workflow step approval gates (REQ-W1.3, REQ-W1.6). It is NOT used for MCP tool authorization. `MCPApproval` (UUID PK, `mcp_approvals` table) is the sole authorization record for MCP consequential tool invocations. These two systems are independent and must not be conflated.

**Mandatory 9-step authorization sequence (F6/F7 correction — applies to every MCP tool call through MCPService):**
1. Verify MCP server is configured and enabled in `MCPServerConfig`.
2. Verify requested tool is on the allow-list (`MCPServerConfig.allowed_tools`). Deny → `MCPPermissionError`.
3. Classify tool as `read_only`, `consequential`, or `unknown`.
4. Default `unknown` → `consequential` (deny-by-default policy).
5. For `consequential`/`unknown` tools: retrieve `MCPApproval` from `MCPApprovalRepository` by `mcp_approval_id`. If `mcp_approval_id` is absent or no record is found → log `mcp_approval_missing`, raise `MCPApprovalRequiredError`. MCPService performs this retrieval internally — the caller MUST NOT pass a pre-built approval object.
6. Validate the retrieved `MCPApproval`: (a) `status` MUST be `APPROVED`; (b) `expires_at` MUST be in the future — if expired, log `mcp_approval_expired`, raise `MCPApprovalExpiredError` (never `mcp_approval_denied`); (c) `mcp_server_id`, `tool_name`, `arguments_hash`, and `actor_id` MUST match the current invocation — mismatch → `MCPApprovalRequiredError`; (d) record MUST NOT already be `CONSUMED` — if consumed, raise `MCPApprovalRequiredError` (replay prevention).
7. Call `MCPApprovalRepository.consume_atomic(mcp_approval_id, actor_id, server_name, tool_name, arguments_hash, trusted_workflow_run_id, now=datetime.now(UTC))` — executes a single `BEGIN IMMEDIATE` transaction verifying ALL binding fields in-transaction: actor_id, mcp_server_id, tool_name, arguments_hash, workflow_run_id (NULL-safe match against trusted_workflow_run_id), status=APPROVED, expires_at > now, consumed_at IS NULL. `UPDATE WHERE status='APPROVED' AND expires_at > now AND consumed_at IS NULL AND id=?`. Verify rowcount == 1 — if 0 rows updated (concurrent consumption, expiry, or any binding mismatch won the race), `ROLLBACK` and raise `ConsumedError`. `COMMIT` before subprocess launch. See REQ-M2.2 for the full algorithm. SQLite serializes writes at the database-file level (T2 — NOT SQLAlchemy connection-pool serialization). Log `mcp_approval_granted`.
8. Execute only through `MCPService` gateway — no direct `MCPClient` calls from routers, adapters, or any other layer. Invoke `MCPClient.call_tool`.
9. Record all required audit events without leaking credentials or argument values. Log `mcp_tool_invoked` on success; `mcp_tool_failed` on exception, with `mcp_approval_id` reference.

**Note on step 7:** Step 7 (consume_atomic) is explicitly separated from step 6 (validation) because atomic consumption is the last gate before execution. A consumed approval cannot be replayed regardless of execution outcome — see REQ-M2.4.

**Allow-list clarification:** `MCPServerConfig.allowed_tools` is a configuration-time permission control, not a per-invocation human approval. It restricts which tool names may be invoked. It is NOT sufficient authorization for consequential actions — both allow-list AND human approval checks are required (additive and sequential).

**Additive sequential checks (both must pass):**
1. Allow-list check (`MCPPermissionError` if denied) — from REQ-M1.4.
2. Classification + approval gate check (`MCPApprovalRequiredError` if consequential/unknown without a valid, persisted, unconsumed `MCPApproval`) — from this requirement and REQ-M2.x.

**Caller contract:** The caller passes `mcp_approval_id: UUID | None`. `MCPService` retrieves and validates the `MCPApproval` record from `MCPApprovalRepository` internally. No caller may fabricate or pass a pre-constructed approval object to bypass this gate.

**Required audit events (persisted to `workflow_audit_log`):**

| Event type | Trigger | Actor |
|---|---|---|
| `mcp_approval_requested` | `MCPService` before calling a consequential/unknown tool, requesting human approval | `"system"` |
| `mcp_approval_granted` | `MCPApproval` retrieved, validated, and atomically consumed for an MCP tool call | `"user"` |
| `mcp_approval_denied` | An `MCPApproval` for an MCP tool call is **explicitly rejected** by a human approver (NOT expiry) | `"user"` |
| `mcp_approval_expired` | `MCPApproval.expires_at` elapsed before use — TTL timeout, **NOT** a human rejection | `"system"` |
| `mcp_approval_missing` | No `MCPApproval` found (absent `mcp_approval_id` or record not in DB) when a consequential/unknown tool call is attempted | `"system"` |
| `mcp_tool_invoked` | `MCPClient.call_tool` launched (approval consumed, subprocess launched) | `"system"` |
| `mcp_tool_completed` | `MCPClient.call_tool` returned success | `"system"` |
| `mcp_tool_failed` | `MCPClient.call_tool` raises any exception or times out | `"system"` |

**Acceptance Criteria:**
M1.7.1 — `MCPService.invoke_tool` accepts `mcp_approval_id: UUID | None` (not an `ApprovalRecord` or `MCPApproval` object). For `consequential`/`unknown` tools, the caller MUST supply an `mcp_approval_id`; passing a pre-constructed approval object is not supported and MUST NOT be accepted.
M1.7.2 — `MCPService` retrieves the `MCPApproval` from `MCPApprovalRepository` by `mcp_approval_id`. If the record is not found, it logs `mcp_approval_missing` and raises `MCPApprovalRequiredError` (HTTP 403, code `MCP_APPROVAL_REQUIRED`).
M1.7.3 — `MCPService` rejects the `MCPApproval` if `status != APPROVED`, logs `mcp_approval_missing`, and raises `MCPApprovalRequiredError`.
M1.7.4 — `MCPService` rejects the `MCPApproval` if `expires_at` is in the past, logs `mcp_approval_expired`, and raises `MCPApprovalExpiredError` (HTTP 422, code `MCP_APPROVAL_EXPIRED`). It MUST NOT log `mcp_approval_denied`.
M1.7.5 — `MCPService` rejects the invocation if `mcp_server_id`, `tool_name`, `arguments_hash`, or `actor_id` on the `MCPApproval` do not match the current call, and raises `MCPApprovalRequiredError`.
M1.7.6 — `MCPService` rejects a replay: if the `MCPApproval` already has `status = CONSUMED`, it raises `MCPApprovalRequiredError` without executing the tool.
M1.7.7 — Atomic consumption: `MCPService` calls `MCPApprovalRepository.consume_atomic(mcp_approval_id)` in a single DB transaction (UPDATE WHERE status='APPROVED' AND id=?) before launching the subprocess. Two concurrent calls with the same `mcp_approval_id` MUST result in exactly one success and one `MCPApprovalRequiredError`.
M1.7.8 — A tool classified as `read_only` proceeds without an `mcp_approval_id` (subject to allow-list check only).
M1.7.9 — Allow-list alone is NOT sufficient for consequential tool execution; human approval is also required. A test verifies a tool that passes allow-list check but lacks an `MCPApproval` record is still denied.
M1.7.10 — All eight MCP audit events (`mcp_approval_requested`, `mcp_approval_granted`, `mcp_approval_denied`, `mcp_approval_expired`, `mcp_approval_missing`, `mcp_tool_invoked`, `mcp_tool_completed`, `mcp_tool_failed`) are logged to `workflow_audit_log`.
M1.7.11 — No code path in `MCPAdapter`, `MCPRouter`, or any other layer calls `MCPClient.call_tool` directly without going through `MCPService.invoke_tool`.
M1.7.12 — `test_expired_mcp_approval_emits_approval_expired_event` — verifies an expired `MCPApproval` emits `mcp_approval_expired`, NOT `mcp_approval_denied`.

**Named tests (all 8 MUST be present in the MCP test suite):**
- `test_forged_approval_record_rejected` — verifies a caller cannot bypass the gate by constructing an in-memory approval object; `MCPService` only accepts `mcp_approval_id` and retrieves `MCPApproval` from `MCPApprovalRepository`
- `test_expired_approval_rejected_at_invocation` — `MCPApproval.expires_at` in the past raises `MCPApprovalExpiredError`
- `test_mismatched_tool_name_rejected` — `MCPApproval.tool_name` differs from invoked tool → `MCPApprovalRequiredError`
- `test_mismatched_arguments_hash_rejected` — `MCPApproval.arguments_hash` does not match SHA-256 of supplied arguments → `MCPApprovalRequiredError`
- `test_replay_after_consumption_rejected` — second call with an already-`CONSUMED` `MCPApproval` → `MCPApprovalRequiredError`
- `test_concurrent_consumption_safe` — two concurrent `invoke_tool` calls with the same `mcp_approval_id` result in exactly one success and one `MCPApprovalRequiredError` (atomic consumption via `consume_atomic`)
- `test_read_only_tool_no_approval_required` — `read_only` classified tool proceeds without `mcp_approval_id`
- `test_no_direct_mcp_client_bypass` — integration test verifying no router or adapter calls `MCPClient.call_tool` directly without going through `MCPService.invoke_tool`

---

## Area 4b — MCPApproval Model and Repository (F6 Correction)

**Separation note:** The `approval_requests` table (integer PK, `ApprovalRequest` model) is used exclusively for workflow step approval gates. It is NOT used for MCP tool authorization. The `mcp_approvals` table (UUID PK, `MCPApproval` model) is the sole authorization record for MCP consequential tool invocations.

### REQ-M2.1
WHEN a consequential MCP tool invocation is authorized,
THEN an `MCPApproval` SQLAlchemy model MUST exist in `src/devflow_api/models/mcp_approval.py` with the following columns: `id` (TEXT PK — UUID stored as text), `mcp_server_id` (TEXT NOT NULL — matches `MCPServerConfig.name`), `tool_name` (TEXT NOT NULL), `arguments_hash` (TEXT NOT NULL — SHA-256 of canonical JSON of arguments), `actor_id` (TEXT NOT NULL — local user identifier), `workflow_run_id` (INTEGER nullable FK → workflow_runs.id ON DELETE SET NULL — a database-enforced BEFORE DELETE trigger on workflow_runs expires every PENDING and APPROVED MCPApproval referencing the run before the FK clears the reference; see M2.1.7), `status` (TEXT, constrained to `PENDING | APPROVED | REJECTED | EXPIRED | CONSUMED`), `requested_at` (UTCDateTime NOT NULL), `resolved_at` (UTCDateTime nullable — set when status moves to APPROVED or REJECTED), `expires_at` (UTCDateTime NOT NULL), `consumed_at` (UTCDateTime nullable — set atomically on consumption).

**Valid status transitions:**
- `PENDING` → `APPROVED` (human resolves as approved)
- `PENDING` → `REJECTED` (human resolves as rejected)
- `APPROVED` → `CONSUMED` (atomic consumption on use, via `consume_atomic`)
- `PENDING` → `EXPIRED` (TTL elapsed before resolution, OR run-deletion trigger — W4-PA)
- `APPROVED` → `EXPIRED` (TTL elapsed before consumption, OR run-deletion trigger — W4-FK)

**Acceptance Criteria:**
M2.1.1 — `MCPApproval` is importable from `devflow_api.models.mcp_approval`.
M2.1.2 — `status` column has a `CheckConstraint` enforcing exactly: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `CONSUMED`.
M2.1.3 — `workflow_run_id` is a nullable foreign key with `ON DELETE SET NULL` (W4-FK: restored from RESTRICT, which is unconditional in SQLite and cannot permit deletion for CONSUMED/PENDING/REJECTED/EXPIRED approvals). Deletion is combined with a database-enforced BEFORE DELETE trigger on `workflow_runs` (`trg_workflow_runs_before_delete_expire_mcp_approvals` — W4-PA) that sets `status='EXPIRED'` on every PENDING and APPROVED `MCPApproval` referencing the run BEFORE the FK action clears the reference. `PRAGMA foreign_keys=ON` (REQ-DB1.3) is required for the SET NULL action; the trigger is a plain SQL DDL trigger that fires on any DELETE of a `workflow_runs` row. This prevents a PENDING or APPROVED approval from losing its run binding and becoming a valid unbound (NULL) authorization: it is expired (not consumable, and not promotable to APPROVED) before `workflow_run_id` is set to NULL.
M2.1.4 — `id` column is TEXT (UUID stored as text), primary key.
M2.1.5 — All timestamp columns use `UTCDateTime` TypeDecorator.
M2.1.6 — `mypy --strict src/devflow_api/models/mcp_approval.py` exits with code 0.
M2.1.7 — [W4-FK / W4-PA — deletion binding invariant] `MCPApproval.workflow_run_id` uses `ON DELETE SET NULL` combined with a BEFORE DELETE trigger on `workflow_runs` (`trg_workflow_runs_before_delete_expire_mcp_approvals` — NOT `ON DELETE RESTRICT`, which is unconditional in SQLite and cannot permit deletion for CONSUMED/PENDING/REJECTED/EXPIRED approvals). A `PENDING` or `APPROVED` `MCPApproval` originally bound to a `workflow_run_id` MUST NOT become a valid unbound (NULL) authorization after that run is deleted. The trigger sets `status='EXPIRED'` on every PENDING and APPROVED approval referencing the run BEFORE the FK clears the reference. An EXPIRED approval is rejected by `consume_atomic` (`status='APPROVED'` check fails, 0 rows updated), so the NULL-to-NULL authorization bypass is impossible. An EXPIRED approval (whether by TTL or the run-deletion trigger) also cannot be promoted — the approval-resolution flow MUST only resolve approvals whose status is `PENDING`; it rejects any approval that is not `PENDING`. Deleting a run is permitted for every approval status: PENDING and APPROVED approvals are expired by the trigger (then SET NULL clears the FK); CONSUMED/REJECTED/EXPIRED approvals are left untouched by the trigger and have their FK cleared to NULL (history preserved). Originally-unbound approvals (`workflow_run_id IS NULL` at creation) are unaffected. This is the database-enforced guard against both the NULL-to-NULL authorization bypass (APPROVED) and the orphaned-PENDING promotion attack (PENDING).

M2.1.8 — Deleting a `workflow_runs` row that has a PENDING or APPROVED `MCPApproval` referencing it sets those approvals' `status` to `EXPIRED` (via the BEFORE DELETE trigger), then the FK SET NULL clears `workflow_run_id` to NULL. (tests: `test_workflow_run_deletion_expires_approved_mcp_approval`, `test_workflow_run_deletion_expires_pending_mcp_approval`)
M2.1.9 — Deleting a `workflow_runs` row referenced by CONSUMED/REJECTED/EXPIRED approvals preserves those approvals (their status is unchanged; only `workflow_run_id` is cleared to NULL). A PENDING approval is expired by the trigger (not preserved — W4-PA). (tests: `test_workflow_run_deletion_allowed_after_approval_consumed`, `test_workflow_run_deletion_preserves_consumed_approval`, `test_workflow_run_deletion_preserves_rejected_approval`)
M2.1.10 — Originally-unbound approvals (`workflow_run_id IS NULL` at creation) are unaffected by any run deletion; they retain their status and NULL binding and keep REQ-M2.5 NULL-to-NULL authorization semantics. (test: `test_null_to_null_match_rejected_for_originally_bound_approval` covers the originally-bound contrast.)
M2.1.11 — An `MCPApproval` that became EXPIRED by the trigger (was APPROVED or PENDING before run deletion) cannot be consumed: `consume_atomic` rejects it because `status != 'APPROVED'` (0 rows updated), even for an unbound invocation. (test: `test_expired_approval_after_deletion_cannot_be_consumed`)
M2.1.12 — The BEFORE DELETE trigger runs within the same transaction as the DELETE; a rolled-back run deletion restores both PENDING and APPROVED approvals to their original status with their original `workflow_run_id` binding intact. (test: `test_trigger_rollback_restores_approval`)
M2.1.13 — [W4-PA] An `MCPApproval` that was PENDING and was expired by the run-deletion trigger (`status='EXPIRED'`, `workflow_run_id=NULL`) cannot be promoted to APPROVED by any approval-resolution operation: the resolution flow MUST reject any approval whose status is not `PENDING`, so an EXPIRED approval cannot become a valid authorization. (test: `test_orphaned_pending_approval_cannot_be_promoted`)

**Deletion binding invariant (W4-FK / W4-PA — DB-enforced):** `PRAGMA foreign_keys=ON` (REQ-DB1.3) MUST be active so the `ON DELETE SET NULL` FK action fires (clearing `workflow_run_id` to NULL). The security invariant itself is owned by the BEFORE DELETE trigger on `workflow_runs` (`trg_workflow_runs_before_delete_expire_mcp_approvals`), not the FK action: the trigger sets `status='EXPIRED'` on every PENDING and APPROVED approval referencing the run before the FK clears the reference. A PENDING approval cannot survive as PENDING with a NULL FK (indistinguishable from originally-unbound), and an APPROVED approval cannot survive as APPROVED with a NULL FK (exploitable via NULL-to-NULL match). An EXPIRED approval is rejected by `consume_atomic` and cannot be promoted by the resolution flow (which only resolves PENDING approvals). The trigger is a plain SQL DDL trigger (fires on any DELETE, direct or cascaded) and the SET NULL action requires `PRAGMA foreign_keys=ON`; both run in the same transaction as the DELETE. This is database-enforced (not application code), because a direct SQL DELETE bypasses application checks but cannot bypass the trigger. Originally-unbound approvals (`workflow_run_id IS NULL` at creation) are unaffected by run deletion and keep REQ-M2.5 NULL-to-NULL semantics — the trigger only updates rows `WHERE workflow_run_id = OLD.id`; it only expires approvals that were *originally bound* to the deleted run.

**Named deletion/binding tests (all 10 MUST be present in `tests/unit/test_mcp_approval_repository.py` or `tests/unit/test_mcp_service.py`):**
- `test_workflow_run_deletion_expires_approved_mcp_approval` — [RENAMED from `test_workflow_run_deletion_blocked_with_approved_mcp_approval` in v1.5.5; behavior changed from block to expire] deleting a `workflow_run` referenced by an APPROVED `MCPApproval` does NOT raise `IntegrityError`; the BEFORE DELETE trigger sets that approval's `status` to `EXPIRED` and the FK SET NULL clears `workflow_run_id` to NULL (`PRAGMA foreign_keys=ON`). The approval row is preserved (history) but is no longer consumable.
- `test_workflow_run_deletion_expires_pending_mcp_approval` — [RENAMED from `test_workflow_run_deletion_allowed_with_pending_approval` in v1.5.7; behavior changed from preserve to expire — W4-PA] deleting a `workflow_run` referenced by a PENDING `MCPApproval` sets that approval's `status` to `EXPIRED` via the BEFORE DELETE trigger; the FK SET NULL clears `workflow_run_id` to NULL. The approval cannot be promoted to APPROVED after deletion.
- `test_workflow_run_deletion_allowed_after_approval_consumed` — [KEPT] a CONSUMED `MCPApproval` does not block `workflow_run` deletion; it is preserved with `workflow_run_id` cleared to NULL (the trigger does not touch CONSUMED).
- `test_null_to_null_match_rejected_for_originally_bound_approval` — [KEPT; rationale updated] an approval originally bound to run X cannot become a valid unbound authorization after run deletion: the trigger expires it (status→EXPIRED) before the FK is nulled, so a later unbound invocation (`trusted_workflow_run_id = NULL`) fails the `consume_atomic` `status='APPROVED'` check (0 rows updated) rather than matching NULL-to-NULL.
- `test_cascaded_deletion_handles_mcp_approvals` — [KEPT; behavior updated — W4-PA] deleting a workflow cascades to delete each run; the trigger fires per run and expires PENDING and APPROVED approvals (then SET NULL clears the FK); CONSUMED/REJECTED/EXPIRED approvals are left untouched and have their FK cleared.
- `test_workflow_run_deletion_preserves_consumed_approval` — [ADDED in v1.5.6] after deleting a run with a CONSUMED approval, the approval row still exists with `status='CONSUMED'` and `workflow_run_id=NULL` (history preserved, not deleted).
- `test_workflow_run_deletion_preserves_rejected_approval` — [ADDED in v1.5.6] after deleting a run with a REJECTED approval, the approval row still exists with `status='REJECTED'` and `workflow_run_id=NULL`.
- `test_expired_approval_after_deletion_cannot_be_consumed` — [ADDED in v1.5.6] an approval that was APPROVED before run deletion (now EXPIRED via trigger, `workflow_run_id=NULL`) cannot be consumed; `consume_atomic` updates 0 rows (`status='EXPIRED'` ≠ `'APPROVED'`) even for an unbound invocation.
- `test_trigger_rollback_restores_approval` — [ADDED in v1.5.6; updated W4-PA] DELETE run (trigger fires, PENDING→EXPIRED and APPROVED→EXPIRED) within a transaction, then ROLLBACK; both approvals are restored to their original status (PENDING and APPROVED respectively) with their original `workflow_run_id` binding intact (the trigger is transactional).
- `test_orphaned_pending_approval_cannot_be_promoted` — [ADDED in v1.5.7 — W4-PA] after a run deletion causes a PENDING approval to become EXPIRED (`workflow_run_id=NULL`), an attempt to resolve it as APPROVED (`UPDATE ... SET status='APPROVED' WHERE id=? AND status='PENDING'`) updates 0 rows; the approval remains EXPIRED and cannot authorize any MCP invocation.

### REQ-M2.2
WHEN MCPApproval records are persisted and retrieved,
THEN an `MCPApprovalRepository` MUST exist in `src/devflow_api/repositories/mcp_approval.py` with the following interface:
- `create(approval: MCPApproval) → MCPApproval` — persists a new MCPApproval with status=PENDING.
- `get_by_id(id: UUID) → MCPApproval | None` — retrieves by UUID.
- `consume_atomic(approval_id: UUID, actor_id: str, mcp_server_id: str, tool_name: str, arguments_hash: str, workflow_run_id: int | None, now: datetime) → MCPApproval` — executes a single database transaction (C2/S2/T2 hardening):
  1. `BEGIN IMMEDIATE;` — acquires the SQLite write lock immediately, preventing TOCTOU between SELECT and UPDATE.
  2. Within the SAME transaction: `SELECT` the MCPApproval row.
  3. Within the SAME transaction verify ALL of these:
     a. `actor_id` matches the persisted `MCPApproval.actor_id`.
     b. `mcp_server_id` matches the persisted `MCPApproval.mcp_server_id`.
     c. `tool_name` matches the persisted `MCPApproval.tool_name`.
     d. `arguments_hash` matches the persisted `MCPApproval.arguments_hash`.
     e. `workflow_run_id` matches against `MCPApproval.workflow_run_id` using the S1 rules (REQ-M2.5) — NULL-safe: both NULL, or both equal integers must match. `workflow_run_id` is `int | None` — `WorkflowRun.id` is an INTEGER primary key (T1). It is NOT a UUID.
     f. `status = APPROVED` AND `expires_at > now` AND `consumed_at IS NULL`.
  4. If all checks pass: `UPDATE mcp_approvals SET status='CONSUMED', consumed_at=now WHERE id=? AND status='APPROVED' AND expires_at > now AND consumed_at IS NULL`.
  5. Verify exactly 1 row was updated — if 0 rows updated, `ROLLBACK` and raise `ConsumedError`.
  6. `COMMIT` the transaction BEFORE launching any subprocess.
  7. If the subprocess fails after commit, the approval remains CONSUMED (no rollback).
  Raises `ConsumedError` if 0 rows updated (concurrent consumption, expiry, or binding mismatch). Uses `datetime.now(UTC)` — NOT `datetime.utcnow()`.
  Note (C1): `workflow_run_id` parameter here is the `trusted_workflow_run_id` resolved by the application layer from the server-side session context — it is never read from tool arguments or any client-supplied field.
- `list_pending(server_id: str) → list[MCPApproval]` — returns all PENDING approvals for a given server.

**SQLite write-lock and concurrency semantics (T2):**
- SQLite serializes writes at the database-file level. Concurrent write transactions from the same process or multiple processes will queue; only one write transaction holds the write lock at a time. This is a SQLite engine guarantee, NOT a SQLAlchemy connection-pool guarantee. SQLAlchemy connection pooling does NOT serialize database writes.
- `BEGIN IMMEDIATE` acquires the write lock upfront for the entire transaction. This prevents another writer from modifying the approval row between the SELECT and the UPDATE (TOCTOU prevention).
- Configure a SQLite `busy_timeout` (recommended: 5000 ms) so that competing write transactions wait briefly for the lock rather than immediately raising `OperationalError`.
- Lock contention (`OperationalError`/busy) on `consume_atomic` is treated as an authorization failure for the current request. The caller (MCPService) MAY retry the database operation only (not the external MCP invocation) after a brief delay, up to a configurable maximum (e.g. 3 retries with exponential backoff).
- In Phase 1 single-process deployment, write contention is unlikely but possible under concurrent API requests.
- In a multi-process deployment, SQLite WAL mode MUST be enabled (`PRAGMA journal_mode=WAL`) to allow concurrent readers; this PRAGMA is already registered in the `'connect'` event handler (REQ-DB1.3).
- The `expires_at > now` check inside the transaction (step 3 above) prevents stale in-memory validation results from bypassing expiry between the service-layer check and consumption.
- Phase 1 targets single-process deployment.

**Acceptance Criteria:**
M2.2.1 — `MCPApprovalRepository` is importable from `devflow_api.repositories.mcp_approval`.
M2.2.2 — `consume_atomic` with a valid APPROVED record returns the updated record with `status = CONSUMED` and `consumed_at` set.
M2.2.3 — `consume_atomic` with an already-CONSUMED record raises `ConsumedError` (0 rows updated).
M2.2.4 — Two concurrent `consume_atomic` calls with the same id result in exactly one success and one `ConsumedError`.
M2.2.5 — `mypy --strict src/devflow_api/repositories/mcp_approval.py` exits with code 0.
M2.2.6 — `consume_atomic` uses `datetime.now(UTC)` (NOT `datetime.utcnow()`) for the expiry check inside the transaction.
M2.2.7 — An approval valid at request time but expired by consumption time (stale validation) is rejected inside `consume_atomic` via the in-transaction `expires_at > now` check; `ConsumedError` is raised and no subprocess is launched. (test: `test_expired_at_consumption_time_rejected`)
M2.2.8 — `consume_atomic` commits the transaction before the subprocess is launched; subprocess failure does NOT roll back the consumption. (test: `test_execution_failure_does_not_restore_consumed_approval`)
M2.2.9 — `consume_atomic` uses `BEGIN IMMEDIATE` (or equivalent exclusive write-lock acquisition) to acquire the write lock before the SELECT, preventing TOCTOU. SQLite write serialization is a database-engine guarantee, not a SQLAlchemy connection-pool guarantee. (test: `test_begin_immediate_prevents_toctou`)

**Named T2 negative tests (all 6 MUST be present in `tests/unit/test_mcp_service.py` or `tests/unit/test_mcp_approval_repository.py`):**
- `test_concurrent_consumption_only_one_succeeds` — two concurrent consume_atomic calls: exactly one succeeds, one raises ConsumedError; in-transaction UPDATE rowcount check enforces single-winner semantics
- `test_busy_timeout_treated_as_authorization_failure` — simulate lock contention (OperationalError); verify it is caught and treated as authorization failure; caller may retry DB operation only
- `test_expired_at_consumption_time_rejected` — approval valid at service-layer check; expires_at elapses before consume_atomic executes; in-transaction check rejects; ConsumedError raised; no subprocess launched
- `test_execution_failure_does_not_restore_consumed_approval` — approval stays CONSUMED after subprocess error; no rollback
- `test_begin_immediate_prevents_toctou` — verify consume_atomic uses BEGIN IMMEDIATE or equivalent; write lock acquired before SELECT, not after
- `test_approval_modified_between_validation_and_consumption` — approval status changed by another transaction between the MCPService pre-consumption validation (step 6) and the consume_atomic call (step 7); verify ConsumedError raised and no subprocess launched (C2)

### REQ-M2.3
WHEN MCPService is constructed,
THEN it MUST be injected with `mcp_approval_repo: MCPApprovalRepository` (NOT `approval_request_repo: ApprovalRequestRepository`). The `ApprovalRequestRepository` is used only for workflow step approvals (REQ-W1.3, REQ-W1.6) and MUST NOT be used by `MCPService`.

**Acceptance Criteria:**
M2.3.1 — `MCPService.__init__` signature includes `mcp_approval_repo: MCPApprovalRepository`.
M2.3.2 — `MCPService.__init__` does NOT include `approval_request_repo: ApprovalRequestRepository`.
M2.3.3 — `MCPService.invoke_tool` calls `self.mcp_approval_repo.consume_atomic(...)` not `self.approval_request_repo.consume_atomic(...)`.
M2.3.4 — `mypy --strict src/devflow_api/services/mcp_service.py` exits with code 0.

### REQ-M2.4
WHEN a consequential MCP tool execution fails or times out,
THEN the system MUST NOT automatically restore the `MCPApproval` to `APPROVED` status. Consumed approvals cannot be replayed regardless of execution outcome.

**Failure semantics:**
- An `MCPApproval` authorizes at most one execution attempt (enforced by `consume_atomic`).
- Consumed approvals cannot be replayed regardless of execution outcome (success, failure, or timeout).
- An execution failure does NOT restore the approval to `APPROVED` status.
- Timeout or connection loss is treated as indeterminate (not confirmed success, not confirmed failure).
- No automatic retry of a consequential action without a new explicit `MCPApproval`.

**Audit requirements:**
- Record `mcp_tool_invoked` (approval consumed, subprocess launched) with `mcp_approval_id` reference.
- Record `mcp_tool_completed` (subprocess returned success) — this is DISTINCT from `mcp_tool_invoked`.
- Record `mcp_tool_failed` (subprocess returned error or timed out) with `mcp_approval_id` reference.

**User recovery flow:** After a failure or indeterminate outcome, the user may inspect the audit log and request a new `MCPApproval` for a retry. The new approval goes through the full approval flow (`PENDING` → `APPROVED`). Note: "DevFlow AI cannot guarantee exactly-once execution of external MCP tools. If the subprocess was launched but the result is unknown (timeout/crash), the user must verify the external state before approving a retry."

**Acceptance Criteria:**
M2.4.1 — `test_execution_failure_does_not_restore_approval` — after `mcp_tool_failed` audit event, the `MCPApproval` remains in `CONSUMED` status.
M2.4.2 — `test_timeout_recorded_as_indeterminate_in_audit` — a subprocess timeout logs `mcp_tool_failed` with an indeterminate note; the approval is NOT restored.
M2.4.3 — `test_new_approval_required_for_retry_after_failure` — a retry of a failed consequential tool call requires a new `MCPApproval` (a new `mcp_approval_id`); reusing the consumed one raises `MCPApprovalRequiredError`.
M2.4.4 — `test_github_confirmation_not_restored_after_api_failure` — after a GitHub API call failure following confirmation consumption, the `GitHubConfirmation` remains consumed; a new confirmation must be issued for retry.

### REQ-M1.8
WHEN the MCP Python SDK is used,
THEN the `mcp` package MUST be declared with a constrained version range of `mcp>=1.0,<2.0` in `requirements/base.txt`. The implementer MUST check `pyproject.toml` first at implementation time; if a different `mcp` version is already declared there, that version takes precedence over `mcp>=1.0,<2.0` and this specification MUST be updated to reflect the actual constraint. As of the Phase 0 base commit (`aaaaacb703124fc31b0e757b2bf1739c4fb225c9`), `mcp` is not present in `pyproject.toml`, so `mcp>=1.0,<2.0` is the operative constraint. All MCP integration tests MUST be runnable offline using mocked subprocess responses; no live MCP server is required in CI.

**Reproducible locking:** A lockfile (`requirements/requirements.lock` or equivalent generated by `uv lock` or `pip-compile`) MUST be committed to source control. CI installs from the lockfile, not from floating constraints.

**Upgrade procedure:** To upgrade the MCP SDK — bump the constraint in `requirements/base.txt`, regenerate the lockfile, run the full test suite including MCP integration tests, and update this spec if behaviour changes.

**Acceptance Criteria:**
M1.8.1 — `requirements/base.txt` contains `mcp>=1.0,<2.0` (or the actual version if `pyproject.toml` already declares a different constraint at implementation time).
M1.8.2 — A committed lockfile exists and CI installs from it.
M1.8.3 — All MCP unit and integration tests pass in CI without a live MCP server or external network access.
M1.8.4 — `test_mcp_client_uses_locked_sdk_version` asserts the installed `mcp` version satisfies the constraint at import time.

### REQ-M2.5 — Workflow Run ID Binding (S1)
WHEN `MCPService.invoke_tool` is called,
THEN it MUST validate `workflow_run_id` binding between the `MCPApproval` record and the server-side trusted invocation context BEFORE calling `consume_atomic`. The `trusted_workflow_run_id` is resolved exclusively from the server-side session context — it is NOT accepted from caller-supplied tool arguments.

**Workflow run ID binding rules (all six MUST be enforced):**
1. An approval with `workflow_run_id = X` MUST NOT authorize an invocation for a different `workflow_run_id = Y` (mismatch → reject; reason: `workflow_run_mismatch`).
2. An approval with `workflow_run_id = X` (non-NULL) MUST NOT authorize an invocation with no workflow context (`trusted_workflow_run_id = NULL` in invocation → reject; reason: `missing_workflow_context`).
3. An approval with `workflow_run_id = NULL` MUST authorize only an invocation with no workflow context (`trusted_workflow_run_id = NULL`). An approval with `workflow_run_id = NULL` MUST NOT authorize an invocation that carries a workflow context (reason: `unexpected_workflow_context`) — unless a more restrictive policy is explicitly documented for the deployment.
4. A caller MUST NOT override the trusted workflow context through tool arguments. `trusted_workflow_run_id` comes from the server-side session/context ONLY.
5. Missing or mismatched `workflow_run_id` context MUST fail closed — no execution proceeds.
6. Every `workflow_run_id` mismatch or missing-context rejection MUST be recorded as a `mcp_approval_rejected` audit event with a `reason` field set to one of: `workflow_run_mismatch` | `missing_workflow_context` | `unexpected_workflow_context`.

**Acceptance Criteria:**
M2.5.1 — `MCPService.invoke_tool` accepts `trusted_workflow_run_id: int | None` as a server-side parameter (C1). This is the ONLY workflow context parameter — the former `workflow_run_id` parameter has been removed. `WorkflowRun.id` is an INTEGER primary key; `trusted_workflow_run_id` is therefore `int | None`, NOT a UUID (T1). This parameter is resolved from the session context and MUST NOT be supplied via the tool arguments payload. It is resolved by the application layer from the current execution session before calling `invoke_tool` and is never read from tool arguments, request body, or any client-supplied field.
M2.5.2 — An `MCPApproval` with `workflow_run_id = X` rejected when `trusted_workflow_run_id = Y` (X ≠ Y); `mcp_approval_rejected` audit event emitted with `reason = "workflow_run_mismatch"`. (test: `test_approval_wrong_workflow_run_rejected`)
M2.5.3 — An `MCPApproval` with `workflow_run_id = X` (non-NULL) rejected when `trusted_workflow_run_id = NULL`; `mcp_approval_rejected` emitted with `reason = "missing_workflow_context"`. (test: `test_approval_bound_to_workflow_rejected_without_workflow_context`)
M2.5.4 — An `MCPApproval` with `workflow_run_id = NULL` rejected when `trusted_workflow_run_id = X` (non-NULL); `mcp_approval_rejected` emitted with `reason = "unexpected_workflow_context"`. (test: `test_approval_unbound_rejected_with_workflow_context`)
M2.5.5 — `trusted_workflow_run_id` supplied via tool arguments is ignored; only the server-side session value is used. (test: `test_workflow_run_id_from_arguments_not_trusted`)
M2.5.6 — Workflow run ID check occurs BEFORE `consume_atomic`; a rejected invocation does NOT consume the approval.
M2.5.7 — All workflow_run_id rejection reasons are present in the `mcp_approval_rejected` audit event as a structured `reason` field.

**Named negative tests (all 4 MUST be present in `tests/unit/test_mcp_service.py`):**
- `test_approval_wrong_workflow_run_rejected` — approval.workflow_run_id = X, invocation trusted_workflow_run_id = Y → reject with reason `workflow_run_mismatch`
- `test_approval_bound_to_workflow_rejected_without_workflow_context` — approval.workflow_run_id non-NULL, invocation trusted_workflow_run_id = NULL → reject with reason `missing_workflow_context`
- `test_approval_unbound_rejected_with_workflow_context` — approval.workflow_run_id = NULL, invocation trusted_workflow_run_id non-NULL → reject with reason `unexpected_workflow_context`
- `test_workflow_run_id_from_arguments_not_trusted` — caller passes workflow_run_id in tool arguments; server ignores it and uses session context; if session has no context and approval has non-NULL workflow_run_id → reject

---

## Area 5 — GitHub Workflow Orchestration

### REQ-G1.1
WHEN a repository connection is configured,
THEN a `RepositoryConfig` SQLAlchemy model MUST exist in `src/devflow_api/models/repository.py` with columns: `id` (INTEGER PK), `project_id` (INTEGER FK → projects.id NOT NULL), `owner` (TEXT NOT NULL), `repo` (TEXT NOT NULL), `default_branch` (TEXT NOT NULL DEFAULT `"main"`), `is_active` (BOOLEAN NOT NULL DEFAULT 1), `created_at` (UTCDateTime), `updated_at` (UTCDateTime). The combination `(project_id, owner, repo)` MUST be unique.

**Note on wave timing:** The `repository_configs` table is created by Alembic migration `003_add_repository_tables.py` in Wave 2 (Task W2). The `RepositoryConfig` SQLAlchemy model and `RepositoryConfigRepository` are written in Wave 5 (Task G1). This is intentional: Alembic migrations use inline `sa.Table` definitions and do not require the ORM model to exist. The migration creates the table; the model provides the ORM interface used by the service and router.

**Acceptance Criteria:**
G1.1.1 — `RepositoryConfig` is importable from `devflow_api.models.repository`.
G1.1.2 — The unique constraint on `(project_id, owner, repo)` is enforced at the database level.
G1.1.3 — `mypy --strict src/devflow_api/models/repository.py` exits with code 0.
G1.1.4 — `POST /api/v1/repositories` creates a repository config and returns HTTP 201.
G1.1.5 — `GET /api/v1/repositories?project_id={id}` returns configs for the given project.

### REQ-G1.2
WHEN branch status is queried,
THEN `GET /api/v1/repositories/{repo_config_id}/branches` MUST call the GitHub REST API to list branches, and `GET /api/v1/repositories/{repo_config_id}/branches/{branch}/status` MUST return the branch protection status, latest commit SHA, and CI check results.

**Acceptance Criteria:**
G1.2.1 — Branch listing calls `GET https://api.github.com/repos/{owner}/{repo}/branches` and returns a list of branch summaries.
G1.2.2 — Branch status returns: `branch_name`, `sha`, `protected`, `ci_status` (`success | failure | pending | unknown`).
G1.2.3 — When `GITHUB_TOKEN` is absent, both endpoints return HTTP 403 with `{"error": "...", "code": "MISSING_CREDENTIAL"}`.
G1.2.4 — HTTP errors from GitHub are wrapped as `IntegrationExecutionError` and returned as HTTP 502.
G1.2.5 — Unit tests mock `httpx.AsyncClient`.

### REQ-G1.3
WHEN a PR is inspected,
THEN `GET /api/v1/repositories/{repo_config_id}/pull-requests` and `GET /api/v1/repositories/{repo_config_id}/pull-requests/{pr_number}` MUST retrieve PR data from GitHub and return structured `PullRequestSummary` responses.

**Acceptance Criteria:**
G1.3.1 — `PullRequestSummary` includes: `number`, `title`, `state`, `base_ref`, `head_ref`, `merged_at` (nullable), `checks_passed: bool`.
G1.3.2 — `checks_passed` is `True` only when all required status checks have concluded with `success`.
G1.3.3 — Unit tests mock the GitHub API calls.

### REQ-G1.4
WHEN a branch needs to be prepared,
THEN `POST /api/v1/repositories/{repo_config_id}/branches` MUST support creating a new branch from a specified base ref by calling the GitHub Refs API. This action MUST require a valid `confirmation_id: str` in the request body that references a previously issued `GitHubConfirmation` record. Requests without a valid, unexpired, unused `confirmation_id` MUST NOT create a branch.

**GitHubConfirmation record structure:** `id` (UUID), `repo_full_name` (str), `operation` (Literal `"branch_create"` | `"pr_create"`), `parameters_hash` (SHA-256 of canonicalised operation parameters), `actor_id` (str), `workflow_run_id` (int | None), `issued_at` (datetime), `expires_at` (datetime — default TTL 10 minutes), `used_at` (datetime | None — set on first use).

**Persistence requirement (F2 correction):** `GitHubConfirmation` MUST be persisted to SQLite via a `GitHubConfirmation` SQLAlchemy model and `GitHubConfirmationRepository`. In-memory storage is NOT acceptable — confirmation records must survive service restarts. A new Alembic migration `007_add_github_confirmations.py` MUST be authored in Wave 5 (Task G1), chaining from migration `006_add_mcp_approvals`. The migration chain becomes: 001 → 002 → 003 → 004 → 005 → 006 → 007.

**Issuing a confirmation:** A `POST /api/v1/github-confirmations` endpoint issues a `GitHubConfirmation` record. The client then submits that `confirmation_id` in the branch or PR creation request. The simple `confirmed: bool` field is replaced by `confirmation_id: str`; a boolean flag alone is not accepted.

**Single-use semantics:** `used_at` is set atomically on first use using an optimistic lock or DB-level uniqueness to prevent double-consumption. Subsequent submissions with the same `confirmation_id` return HTTP 409 (already used).

**Expiration:** Confirmations expire after the configured TTL (default 10 minutes, configurable via `Settings.GITHUB_CONFIRMATION_TTL_SECONDS: int = 600`). An expired confirmation returns HTTP 422 with code `CONFIRMATION_EXPIRED`.

**Local operator identity (W5-SR):** `Settings` MUST include `LOCAL_OPERATOR_ID: str = "local_operator"`. This is the `actor_id` used for all Phase 1 GitHub operations. It is never accepted from the request body.

**Mismatch rejection:** If `repo_full_name`, `operation`, or `parameters_hash` in the request do not match the stored `GitHubConfirmation`, the request returns HTTP 422 with code `CONFIRMATION_MISMATCH`.

**Concurrent requests:** Two simultaneous requests attempting to consume the same `confirmation_id` MUST NOT both succeed. The `used_at` column is updated atomically; only the first request to set it proceeds to the GitHub API call.

**Recovery/idempotency:** If the GitHub API call succeeds but the `used_at` update fails (e.g., transient DB error), the system MUST re-check GitHub state before issuing a new confirmation for the same operation (to avoid duplicate branch/PR creation). The idempotency key is the combination of `(confirmation_id, operation)`.

**Failure semantics (F9 correction):** A `GitHubConfirmation` consumed (`used_at` set) means the action was attempted, not necessarily completed. GitHub API failure after confirmation consumption: record `github_action_failed` audit event; do NOT automatically restore the confirmation or retry. The user must verify GitHub state and issue a new `GitHubConfirmation` for retry. Note: "DevFlow AI cannot guarantee exactly-once execution of GitHub API operations. If the API call was made but the result is unknown, the user must verify the GitHub state before issuing a new confirmation."

**GitHubConfirmation status field (W5-GC):** The `github_confirmations` table MUST have a `status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED','EXPIRED','USED'))` column. The three status values are:
- `ISSUED` — confirmation created; not yet consumed or expired.
- `EXPIRED` — set by the BEFORE DELETE trigger on `workflow_runs` when the bound run is deleted and the confirmation has `status='ISSUED'`. An EXPIRED confirmation cannot be consumed.
- `USED` — set atomically by `consume_atomic` on first use.

This prevents the NULL-to-NULL bypass: if a workflow run is deleted, its ISSUED confirmations become EXPIRED before `workflow_run_id` is cleared to NULL, so they cannot match a future invocation with `trusted_workflow_run_id=None`.

**BEFORE DELETE trigger on workflow_runs for github_confirmations (W5-GC):** Migration 007 MUST create:
```sql
CREATE TRIGGER trg_workflow_runs_before_delete_expire_github_confirmations
BEFORE DELETE ON workflow_runs
FOR EACH ROW
BEGIN
    UPDATE github_confirmations SET status = 'EXPIRED'
    WHERE workflow_run_id = OLD.id AND status = 'ISSUED';
END;
```
USED confirmations are not changed by the trigger (audit history preserved). Originally-unbound confirmations (`workflow_run_id IS NULL` at creation) are unaffected.

**Authorization model:** The `GitHubConfirmation` record is explicit user acknowledgement of the specific action with the specific parameters. Having a `GITHUB_TOKEN` credential in Settings is an authentication prerequisite, not authorization. The credential allows the GitHub API call to authenticate; the confirmation record is the authorization gate. Never treat a client-supplied boolean as sufficient authorization.

**Canonical parameter binding (W5-SR — REQ-G1.4):** One authoritative canonical payload function is defined for each operation. Both issuance (`RepositoryService.issue_confirmation`) and consumption (`consume_atomic`) use the IDENTICAL canonical function. The `parameters_hash` is stored in `GitHubConfirmation` at issuance time; at consumption the hash is recomputed from the provided parameters and compared against the stored value — any mismatch is rejected.

```python
# Canonical payload definitions (authoritative — used identically at issuance and consumption)
import json, hashlib

def canonical_branch_create_payload(
    repo_full_name: str,
    branch_name: str,
    base_ref: str,
) -> str:
    """Canonical JSON for branch_create operations. sort_keys=True, no spaces."""
    return json.dumps(
        {
            "operation": "branch_create",
            "repo_full_name": repo_full_name,
            "branch_name": branch_name,
            "base_ref": base_ref,
        },
        sort_keys=True,
        separators=(',', ':'),
    )

def canonical_pr_create_payload(
    repo_full_name: str,
    title: str,
    body: str,
    head_ref: str,
    base_ref: str,
) -> str:
    """Canonical JSON for pr_create operations. sort_keys=True, no spaces."""
    return json.dumps(
        {
            "operation": "pr_create",
            "repo_full_name": repo_full_name,
            "title": title,
            "body": body,
            "head_ref": head_ref,
            "base_ref": base_ref,
        },
        sort_keys=True,
        separators=(',', ':'),
    )

def hash_payload(payload: str) -> str:
    """SHA-256 hex digest of UTF-8 encoded canonical JSON string."""
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
```

**Normalization rules (applied before hashing):**
- All string fields: stripped of leading/trailing whitespace before hashing.
- `repo_full_name`: lowercased before hashing (GitHub repos are case-insensitive).
- `branch_name` and ref names (`base_ref`, `head_ref`): NOT lowercased (Git refs are case-sensitive).
- `body`: empty string `''` if `None` or not provided.

**Repository identity rule (W5-SR):** `repo_full_name` is taken from the server-side `RepositoryConfig` record (looked up by `repo_config_id`), never from a client-supplied string directly. Once issued, parameters cannot be changed: the confirmation is bound to the exact `parameters_hash` computed at issuance.

**Trusted actor and workflow context (W5-SR):** Phase 1 is explicitly local-first with a single operator. There is no multi-user authentication system in Phase 1. The `actor_id` for all Phase 1 GitHub operations is `Settings.LOCAL_OPERATOR_ID` (a fixed string configured in `Settings`, default value `'local_operator'`). The `actor_id` is NEVER accepted from the HTTP request body or query parameters; it is resolved by the application layer from `Settings` before any service call. The `GitHubConfirmation` and `MCPApproval` `actor_id` fields are set to this configured value at issuance time.

**Standalone operation policy (W5-SR):** All Phase 1 GitHub operations are standalone — `trusted_workflow_run_id = None` / `workflow_run_id = None`. Workflow-bound GitHub operations (where the confirmation is issued with a specific `workflow_run_id`) are deferred to a future phase when server-side session context is available. Document: *'Phase 1 GitHub operations are standalone (workflow_run_id=None). Workflow-bound GitHub operations are deferred to a future phase when server-side session context is available.'*

**Deployment assumptions (W5-SR):**
- Single local operator; no network exposure (binds to localhost).
- No multi-user authentication.
- `GitHubConfirmation` provides operation-level approval, not user authentication.
- Policy: *'GitHubConfirmation is an operation-level authorization gate, not a user authentication mechanism. It assumes the operator has physical access to the local instance.'*

**Complete security contract (REQ-G1.4 — W5-GC, refined W5-SR):**
1. Actor identity: `actor_id` is `Settings.LOCAL_OPERATOR_ID` (default `'local_operator'`), resolved by the application layer from `Settings` — never accepted from the HTTP request body or query parameters.
2. Repository access: GitHub token must be present and the target repo accessible before issuing a confirmation.
3. Canonical parameters hash: SHA-256 hex digest of canonical JSON (sort_keys=True, no spaces) of operation parameters, using the exact canonical functions defined above. Normalization: strip whitespace, lowercase `repo_full_name`, preserve ref case, body=`''` when None.
4. Exact operation binding: `confirmation.operation` MUST exactly match the requested operation.
5. Trusted workflow-run binding: Phase 1 uses `workflow_run_id=None` for all operations (standalone). The status field (ISSUED/EXPIRED/USED) prevents a formerly-bound ISSUED confirmation from becoming a valid unbound authorization after run deletion.
6. Expiration: configurable TTL default 10 minutes; `expires_at` checked inside `consume_atomic`.
7. SQLite `BEGIN IMMEDIATE` consumption: single transaction with SELECT then conditional `UPDATE WHERE status='ISSUED' AND expires_at > now`.
8. `rowcount == 1` required: if 0 rows updated, raise `ConfirmationAlreadyUsedError` (concurrent or expired).
9. Single-use: `used_at` set, `status→USED`, never reset after FAILED/INDETERMINATE execution.
10. Credential safety: GitHub token never logged; audit events reference `repo_full_name`, not token.
11. Audit events: `github_confirmation_issued`, `github_action_authorized`, `github_action_executed`, `github_action_failed` (with `outcome` field: `FAILED` or `INDETERMINATE`), `github_action_rejected`, `github_confirmation_expired`.
12. No boolean-only authorization: a `GitHubConfirmation` DB record (`status=ISSUED`) is required.
13. No automatic merging: PR creation is the only allowed operation; merge operations are out of scope.

**GitHub execution outcomes (W5-GC, refined W5-SR):** Every `branch_create` and `pr_create` GitHub API call has one of three outcomes:

**SUCCEEDED**
- GitHub API returned HTTP 2xx with a response body confirming the operation (e.g. created branch SHA or PR number).
- The confirmation record is updated: `status=USED`, `used_at=now`, outcome recorded as SUCCEEDED.
- Audit event: `github_action_executed`.

**FAILED (definitive)**
- GitHub API returned HTTP 400, 401, 403, 404, 409, or 422 — operations that definitively fail without ambiguity (e.g. branch already exists, invalid ref, missing permissions, authentication failure).
- These are NOT retried with the same confirmation (confirmation is already USED).
- Audit event: `github_action_failed` with `outcome=FAILED`.
- New confirmation required for retry.
- **Key property: FAILED = definitively did NOT execute on GitHub.**

**INDETERMINATE (ambiguous)**
- HTTP 5xx responses (500, 502, 503, 504): the server received the request but remote execution CANNOT be ruled out.
- Timeout: `httpx.TimeoutException`, `asyncio.TimeoutError` — request was sent but we do not know if GitHub processed it.
- Connection loss: `httpx.ConnectError`, `httpx.ReadError` — the write may or may not have been received.
- **Key property: INDETERMINATE = may or may not have executed on GitHub.**
- Audit event: `github_action_failed` with `outcome=INDETERMINATE`.
- Rules:
  1. Confirmation is already USED (consumed before the API call) — never restored.
  2. No automatic retry.
  3. User must verify GitHub state manually (check if branch/PR exists) before issuing a new confirmation.
  4. Policy: *'DevFlow AI cannot guarantee exactly-once execution. Verify GitHub state before retrying.'*
  5. If the user reconciles and the operation succeeded, they should NOT issue a new confirmation for that resource.
  6. If the operation did not complete, a new `GitHubConfirmation` must be issued and approved for the retry.

**Key distinction (W5-SR):** FAILED = definitively did NOT execute on GitHub. INDETERMINATE = may or may not have executed on GitHub. Both leave the confirmation as USED. Both require a new confirmation for any retry attempt.

Rules:
1. Confirmation MUST be consumed (status→USED, `used_at` set) BEFORE the GitHub API call.
2. After INDETERMINATE: record `github_action_failed` audit event with `outcome=INDETERMINATE`; do NOT auto-retry; do NOT restore the confirmation.
3. After FAILED: same — confirmation stays USED, new confirmation required for retry.
4. 'DevFlow AI cannot guarantee exactly-once execution of external GitHub operations. If the API call result is unknown, the user must verify GitHub state before issuing a new confirmation.'

**Complete security contract (REQ-G1.4 — W5-GC):**
1. Actor identity: `actor_id` comes from server-side session context, never from request body.
2. Repository access: GitHub token must be present and the target repo accessible before issuing a confirmation.
3. Canonical parameters hash: SHA-256 of canonical JSON of operation parameters (`repo_full_name`, `branch_name` or PR `title/body/base`).
4. Exact operation binding: `confirmation.operation` MUST exactly match the requested operation.
5. Trusted workflow-run binding: `workflow_run_id: int | None` from server-side session; same NULL-to-NULL rules as MCPApproval. The status field (ISSUED/EXPIRED/USED) prevents a formerly-bound ISSUED confirmation from becoming a valid unbound authorization after run deletion.
6. Expiration: configurable TTL default 10 minutes; `expires_at` checked inside `consume_atomic`.
7. SQLite `BEGIN IMMEDIATE` consumption: single transaction with SELECT then conditional `UPDATE WHERE status='ISSUED' AND expires_at > now`.
8. `rowcount == 1` required: if 0 rows updated, raise `ConfirmationAlreadyUsedError` (concurrent or expired).
9. Single-use: `used_at` set, `status→USED`, never reset after FAILED/INDETERMINATE execution.
10. Credential safety: GitHub token never logged; audit events reference `repo_full_name`, not token.
11. Audit events: `github_confirmation_issued`, `github_action_authorized`, `github_action_executed`, `github_action_failed`, `github_action_rejected`, `github_confirmation_expired`.
12. No boolean-only authorization: a `GitHubConfirmation` DB record (`status=ISSUED`) is required.
13. No automatic merging: PR creation is the only allowed operation; merge operations are out of scope.

**Acceptance Criteria:**
G1.4.1 — `POST /api/v1/repositories/{repo_config_id}/branches` with a valid, unexpired, unused `confirmation_id` creates the branch via GitHub API and returns HTTP 201.
G1.4.2 — The same request without `confirmation_id` or with `confirmed: true` (boolean) alone returns HTTP 422 with code `CONFIRMATION_REQUIRED`.
G1.4.3 — An expired `confirmation_id` returns HTTP 422 with code `CONFIRMATION_EXPIRED`.
G1.4.4 — A `confirmation_id` whose `parameters_hash` does not match the current request parameters returns HTTP 422 with code `CONFIRMATION_MISMATCH`.
G1.4.5 — Re-submitting an already-used `confirmation_id` returns HTTP 409.
G1.4.6 — Duplicate branch name returns HTTP 409.
G1.4.7 — The action is logged in `WorkflowAuditLog` with `event_type = "branch_created"` and `actor = "user"`.
G1.4.8 — Unit tests mock the GitHub API and verify all confirmation gate paths.
G1.4.9 — `test_github_confirmation_persisted_to_db` — verifies a `GitHubConfirmation` record is written to the SQLite `github_confirmations` table (not held in memory) after `POST /api/v1/github-confirmations`.
G1.4.10 — `test_confirmation_expires_after_ttl` — verifies an expired confirmation (expires_at in the past) returns HTTP 422 with code `CONFIRMATION_EXPIRED`.
G1.4.11 — `test_replay_rejected_after_use` — verifies re-submitting a used `confirmation_id` returns HTTP 409.
G1.4.12 — `test_parameter_mismatch_rejected` — verifies a confirmation with a different `parameters_hash` returns HTTP 422 with code `CONFIRMATION_MISMATCH`.
G1.4.13 — `test_concurrent_consumption_safe` — verifies that two concurrent requests with the same valid `confirmation_id` result in exactly one success and one HTTP 409 (double-consumption prevention via `consume_atomic WHERE status='ISSUED'`).
G1.4.14 — `test_recovery_after_github_api_failure` — verifies that if the GitHub API call fails after `used_at` is set, the system does not silently lose the confirmation record and reports the failure correctly.

**Additional security-negative tests (all MUST be present — W5-GC):**
G1.4.15 — `test_boolean_flag_alone_insufficient_for_github_action` — POST body with `{"confirmed": true}` without `confirmation_id` returns HTTP 422.
G1.4.16 — `test_expired_github_confirmation_rejected` — `expires_at` in the past; HTTP 422, code `CONFIRMATION_EXPIRED`.
G1.4.17 — `test_used_github_confirmation_rejected_on_replay` — re-submitting a `used_at`-set confirmation returns HTTP 409.
G1.4.18 — `test_mismatched_operation_rejected` — confirmation with `operation='branch_create'` submitted for PR creation; HTTP 422.
G1.4.19 — `test_mismatched_parameters_hash_rejected` — confirmation's `parameters_hash` does not match; HTTP 422.
G1.4.20 — `test_mismatched_repo_rejected` — `repo_full_name` in request differs from stored confirmation; HTTP 422.
G1.4.21 — `test_concurrent_consumption_only_one_succeeds` — two concurrent consume calls, exactly one succeeds and one raises `ConfirmationAlreadyUsedError`.
G1.4.22 — `test_no_automatic_pr_merge` — no `/merge` route exists in the OpenAPI spec.
G1.4.23 — `test_github_token_not_in_audit_log` — GITHUB_TOKEN value does not appear in any audit log entry.
G1.4.24 — `test_workflow_run_deletion_expires_github_confirmation` — deleting a workflow run with a bound ISSUED confirmation sets the confirmation's `status` to `EXPIRED` via the BEFORE DELETE trigger; the confirmation cannot then be consumed.

**Additional W5-SR security tests (HTTP outcome classification — all MUST be present):**
G1.4.25 — `test_http_5xx_treated_as_indeterminate` — GitHub returns HTTP 500 → outcome=INDETERMINATE; `github_action_failed` audit event emitted with `outcome=INDETERMINATE`; confirmation stays USED.
G1.4.26 — `test_http_4xx_treated_as_failed` — GitHub returns HTTP 422 → outcome=FAILED; `github_action_failed` audit event emitted with `outcome=FAILED`; confirmation stays USED.
G1.4.27 — `test_timeout_treated_as_indeterminate` — `httpx.TimeoutException` raised during GitHub API call → outcome=INDETERMINATE; `github_action_failed` with `outcome=INDETERMINATE`; confirmation NOT restored.
G1.4.28 — `test_indeterminate_outcome_does_not_restore_confirmation` — confirmation stays USED after INDETERMINATE (no rollback, no status reset).
G1.4.29 — `test_new_confirmation_required_after_indeterminate` — after INDETERMINATE, re-submitting the same `confirmation_id` returns HTTP 409 (already USED).
G1.4.30 — `test_reconciliation_documented_before_retry` — spec/docstring requirement: a comment in `RepositoryService` asserts the user must verify GitHub state before issuing a new confirmation after INDETERMINATE.

**Additional W5-SR security tests (canonical parameter binding — all MUST be present):**
G1.4.31 — `test_canonical_hash_deterministic` — same inputs to `canonical_branch_create_payload` and `canonical_pr_create_payload` always produce the same hash.
G1.4.32 — `test_mismatched_base_ref_rejected` — branch_create confirmation issued with `base_ref='main'`; consumed with `base_ref='develop'` → rejected with `ConfirmationMismatchError`.
G1.4.33 — `test_mismatched_pr_head_rejected` — pr_create confirmation issued with `head_ref='feature/x'`; consumed with `head_ref='feature/y'` → rejected.
G1.4.34 — `test_mismatched_repo_rejected_canonical` — `repo_full_name` from RepositoryConfig differs from canonical payload stored at issuance → rejected.
G1.4.35 — `test_canonical_hash_mismatch_rejected` — any parameter change after issuance → `parameters_hash` does not match → `ConfirmationMismatchError`.
G1.4.36 — `test_repo_identity_from_server_config_not_client` — `repo_full_name` in canonical payload comes from server-side `RepositoryConfig` (looked up by `repo_config_id`), not from any client-supplied field.

**Additional W5-SR security tests (trusted actor and workflow context — all MUST be present):**
G1.4.37 — `test_actor_id_from_settings_not_request_body` — service uses `Settings.LOCAL_OPERATOR_ID` as `actor_id`; any `actor_id` in the request body is ignored.
G1.4.38 — `test_actor_id_mismatch_rejected` — confirmation issued with `actor_id='local_operator'`; consumed with a different `actor_id` → `ConfirmationMismatchError`.
G1.4.39 — `test_standalone_operation_allowed_without_workflow_context` — `workflow_run_id=None` is permitted for all Phase 1 GitHub operations.
G1.4.40 — `test_workflow_run_mismatch_rejected` — if workflow-bound confirmations are used, a confirmation issued with `workflow_run_id=X` cannot be consumed for `workflow_run_id=Y`. (Deferred to future phase; test documents the expected rejection if attempted.)

### REQ-G1.5
WHEN a PR is created,
THEN `POST /api/v1/repositories/{repo_config_id}/pull-requests` MUST call the GitHub PRs API to create a PR. This is a consequential action requiring a valid `confirmation_id: str` in the request body referencing a previously issued `GitHubConfirmation` with `operation = "pr_create"`. Automatic merging MUST NOT be supported.

**Acceptance Criteria:**
G1.5.1 — `POST /api/v1/repositories/{repo_config_id}/pull-requests` with valid body and a valid, unexpired, unused `confirmation_id` creates the PR via GitHub API and returns HTTP 201 with `PullRequestSummary`.
G1.5.2 — The same request without `confirmation_id` or with `confirmed: true` (boolean) alone returns HTTP 422 with code `CONFIRMATION_REQUIRED`.
G1.5.3 — An expired `confirmation_id` returns HTTP 422 with code `CONFIRMATION_EXPIRED`.
G1.5.4 — A used `confirmation_id` returns HTTP 409.
G1.5.5 — The API MUST NOT expose a merge endpoint. Any `POST /api/v1/.../merge` route MUST NOT exist.
G1.5.6 — PR creation is logged in `WorkflowAuditLog` with `event_type = "pr_created"`.
G1.5.7 — Unit tests mock the GitHub API and verify the confirmation gate.

### REQ-G1.6
WHEN CI status is reported,
THEN `GET /api/v1/repositories/{repo_config_id}/branches/{branch}/ci` MUST return the CI check results for the latest commit on that branch by querying the GitHub Check Runs API.

**Acceptance Criteria:**
G1.6.1 — Response includes a list of `CheckRunSummary` objects with: `name`, `status` (`queued | in_progress | completed`), `conclusion` (nullable: `success | failure | skipped | cancelled`).
G1.6.2 — `GET /api/v1/repositories/{repo_config_id}/branches/{branch}/ci` returns HTTP 200 when the branch exists.
G1.6.3 — Returns HTTP 404 when the branch does not exist.
G1.6.4 — Unit tests mock the GitHub API.

---

## Area 6 — Streamlit Phase 1 Experience

### REQ-U1.1
WHEN the Dashboard page loads in Phase 1,
THEN it MUST display real data from the FastAPI backend: project count, active workflow count, and pending approval count — all fetched via `APIClient`. No hard-coded or fabricated metrics MUST appear.

**Acceptance Criteria:**
U1.1.1 — Dashboard page fetches `GET /api/v1/projects`, `GET /api/v1/workflows?status=active`, and `GET /api/v1/approvals?status=pending` via `APIClient` to build its metric display.
U1.1.2 — Each metric shows "—" or "0" when the backend is unavailable or returns 0.
U1.1.3 — `AppTest` with mocked `APIClient` completes without exception.
U1.1.4 — No "Phase 0" placeholder text remains on the Dashboard page.

### REQ-U1.2
WHEN the Workflows page is active,
THEN a new `6_Workflows.py` page MUST be added to the navigation showing active workflows, their current run status, and pending approvals for each run.

**Acceptance Criteria:**
U1.2.1 — The Workflows page exists at `src/devflow_ui/pages/6_Workflows.py` and is registered in `app.py` navigation.
U1.2.2 — The page lists workflows from `GET /api/v1/workflows` via `APIClient`.
U1.2.3 — Each workflow entry shows its status and the count of pending approvals.
U1.2.4 — An "Approve" action button is visible for runs in `waiting_approval` status.
U1.2.5 — `AppTest` with mocked `APIClient` completes without exception.

### REQ-U1.3
WHEN the Execution History page is active,
THEN a new `7_History.py` page MUST display the audit log for recent workflow runs, ordered by recency.

**Acceptance Criteria:**
U1.3.1 — The History page exists at `src/devflow_ui/pages/7_History.py` and is registered in `app.py` navigation.
U1.3.2 — The page fetches recent workflow runs and their audit log entries via `APIClient`.
U1.3.3 — Each entry shows: `workflow name`, `run status`, `started_at`, `completed_at` (if available), `event count`.
U1.3.4 — `AppTest` with mocked `APIClient` completes without exception.

### REQ-U1.4
WHEN the APIClient is extended for Phase 1,
THEN `src/devflow_ui/api_client.py` MUST add typed methods for all new Phase 1 endpoints: projects CRUD, workflows CRUD, runs, approvals, and repository configs. Each method MUST follow the Phase 0 pattern: return `None` on error, log a warning, never raise to the caller.

**Acceptance Criteria:**
U1.4.1 — `APIClient.list_projects(status=None, limit=50, offset=0)` returns `list[dict] | None`.
U1.4.2 — `APIClient.create_project(name, description=None, tags=None)` returns `dict | None`.
U1.4.3 — `APIClient.list_workflows(project_id=None, status=None)` returns `list[dict] | None`.
U1.4.4 — `APIClient.resolve_approval(approval_id, decision)` returns `dict | None`.
U1.4.5 — All new methods carry complete type annotations validated by `mypy --strict`.

### REQ-U1.5
WHEN the Settings page is active in Phase 1,
THEN it MUST display all Phase 1 configuration values (integration availability, MCP server config count, GitHub connection status) in addition to the Phase 0 health check.

**Page-numbering note (W4-CR Conflict D):** `10_Settings.py` is an EXISTING Phase 0 page (present in `src/devflow_ui/pages/`). Wave 4 EXTENDs it in place; it does NOT create a new page and does NOT renumber the navigation. The canonical page name is `10_Settings.py` (consistent with design §12.1 and Task I7); the repository does not contain `4_Settings.py`.

**Acceptance Criteria:**
U1.5.1 — Settings page shows `GET /api/v1/integrations` summary (number of live vs stub adapters).
U1.5.2 — Settings page shows how many MCP servers are configured.
U1.5.3 — Settings page shows GitHub connection status (connected / no token).
U1.5.4 — `AppTest` with mocked `APIClient` completes without exception.

---

## Area 7 — Database Migrations

### REQ-DB1.1
WHEN Phase 1 schema changes are applied,
THEN dedicated Alembic migrations MUST be authored for each new table group introduced in Phase 1. The migrations form a linear chain from the Phase 0 head revision (`"001_create_initial_tables"`):

| File | Revision ID | `down_revision` | Tables / columns | Wave |
|---|---|---|---|---|
| `002_add_project_tags_column.py` | `"002_add_project_tags_column"` | `"001_create_initial_tables"` | ALTER TABLE projects ADD tags_json | Wave 1 |
| `003_add_workflow_tables.py` | `"003_add_workflow_tables"` | `"002_add_project_tags_column"` | workflows, workflow_runs | Wave 2 |
| `004_add_approval_audit_tables.py` | `"004_add_approval_audit_tables"` | `"003_add_workflow_tables"` | approval_requests, workflow_audit_log | Wave 2 |
| `005_add_repository_tables.py` | `"005_add_repository_tables"` | `"004_add_approval_audit_tables"` | repository_configs | Wave 2 |
| `006_add_mcp_approvals.py` | `"006_add_mcp_approvals"` | `"005_add_repository_tables"` | mcp_approvals | Wave 4 |
| `007_add_github_confirmations.py` | `"007_add_github_confirmations"` | `"006_add_mcp_approvals"` | github_confirmations | Wave 5 |

**Revision chain:** `001_create_initial_tables` → `002_add_project_tags_column` → `003_add_workflow_tables` → `004_add_approval_audit_tables` → `005_add_repository_tables` → `006_add_mcp_approvals` → `007_add_github_confirmations`

Each migration's `revision` string MUST exactly match the value in the table above. Each migration's `down_revision` string MUST exactly match the preceding revision's `revision` string.

**Acceptance Criteria:**
DB1.1.1 — `alembic upgrade head` from a Phase 0 schema (head = `001_create_initial_tables`) applies all six Phase 1 migrations in order: 002, 003, 004, 005, 006, 007.
DB1.1.2 — `alembic downgrade -1` from head undoes the most recent migration without error.
DB1.1.3 — Each migration has a non-trivial `downgrade()` (not `pass`).
DB1.1.4 — Migration files are hand-authored; `alembic revision --autogenerate` output MUST be reviewed and edited before commit.
DB1.1.5 — Tests MUST NOT run against the developer's `devflow.db`; they use `tmp_path`-scoped SQLite files.
DB1.1.6 — Each migration file imports nothing from `devflow_api.models` — inline `sa.Table` definitions are used to avoid circular imports.

### REQ-DB1.2
WHEN the tags column is added to projects,
THEN migration `002_add_project_tags_column.py` MUST add a nullable TEXT column `tags_json` with `server_default = "[]"`. Existing project rows receive `tags_json = "[]"`.

**Acceptance Criteria:**
DB1.2.1 — After `alembic upgrade head`, existing `projects` rows have `tags_json = "[]"`.
DB1.2.2 — `downgrade()` removes the `tags_json` column.
DB1.2.3 — The Alembic test (`test_database.py`) covers the round-trip for this migration.
DB1.2.4 — Migration 002 applies successfully from the Phase 0 head (`001_create_initial_tables`) without requiring any other Phase 1 migration to be present first.

### REQ-DB1.3
WHEN a SQLite connection is opened,
THEN `PRAGMA foreign_keys=ON` MUST be executed on every connection immediately after it is opened. Without this PRAGMA, SQLite silently ignores all foreign key constraints, rendering `ON DELETE CASCADE` and `ON DELETE SET NULL` semantics ineffective.

**Implementation location:** The PRAGMA must be added to the SQLAlchemy `'connect'` event handler in `src/devflow_api/database.py`. The existing `alembic/env.py` already registers a `'connect'` event for `PRAGMA journal_mode=WAL`; the `PRAGMA foreign_keys=ON` must be added to the same handler in that file during implementation (note: `alembic/env.py` is out of specification-correction scope and will be updated by the implementer alongside `database.py`).

**Acceptance Criteria (split by wave — F6/F8 correction):**

*Wave 1 (Task P6 — uses only Wave 1 tables: projects; no Wave 2 tables):*
DB1.3.1 — Every SQLite connection opened by the application executes `PRAGMA foreign_keys=ON` before any query runs.
DB1.3.2 — `test_foreign_key_pragma_enabled_on_connection` verifies the PRAGMA is active by querying `PRAGMA foreign_keys` and asserting the result is `1`. This test uses only a live test connection (in-memory SQLite) and is independently satisfiable before Wave 2 exists.
DB1.3.3 — `test_fk_enforcement_with_wave1_tables` verifies that inserting a row with an invalid parent FK raises `IntegrityError` with `PRAGMA foreign_keys=ON`. Use `repository_configs.project_id → projects.id` as the FK relationship if `repository_configs` is accessible (created by migration 005, Wave 2). If Wave 2 tables are not available in a Wave 1 test run, create a minimal in-memory `sa.Table` with a FK to `projects` to verify PRAGMA FK enforcement without depending on Wave 2 tables. This test does NOT reference `WorkflowRun`, `WorkflowAuditLog`, or any Wave 2 model class.
DB1.3.4 — `test_migration_002_upgrade_downgrade` — applies `alembic upgrade` to revision 002 and downgrades back to base; asserts no error occurs. Uses `tmp_path`-scoped SQLite file, not `devflow.db`.

*Wave 2 (Task W6 — uses Wave 2 tables: workflows, workflow_runs, workflow_audit_log):*
DB1.3.5 — `test_delete_project_sets_workflow_project_id_null` verifies that deleting a `Project` sets `Workflow.project_id` to `NULL` (`ON DELETE SET NULL` — Project deletion does NOT cascade to WorkflowRuns; requires Wave 2 tables — deferred to Wave 2 Task W6).
DB1.3.6 — `test_delete_workflow_cascades_to_workflow_runs` verifies that deleting a `Workflow` deletes its associated `WorkflowRun` records (`ON DELETE CASCADE` on `WorkflowRun.workflow_id`; requires Wave 2 tables — deferred to Wave 2 Task W6).
DB1.3.7 — `test_delete_workflow_run_sets_audit_log_workflow_run_id_null` verifies that deleting a `WorkflowRun` sets `WorkflowAuditLog.workflow_run_id` to `NULL` rather than leaving a dangling reference (`ON DELETE SET NULL`; requires Wave 2 tables — deferred to Wave 2 Task W6).
DB1.3.8 — `test_insert_invalid_foreign_key_raises_integrity_error` verifies that inserting a `WorkflowRun` with a non-existent `workflow_id` raises `IntegrityError` (requires Wave 2 tables — deferred to Wave 2 Task W6).

---

## Area 8 — Security Requirements

### REQ-S1.1
ALL consequential actions (branch creation, PR creation, file writes, subprocess execution) MUST require explicit user confirmation via either an `ApprovalRequest` workflow gate or a `GitHubConfirmation` record before execution.

**Bypass prevention:** All consequential adapter calls MUST route through the confirmation gate or approval gate. Direct calls to `GitHubAdapter` methods that mutate state (branch creation, PR creation) MUST NOT be callable from router handlers without passing through `RepositoryService`, which enforces the confirmation check. No adapter method call in a router handler may bypass the service layer for mutating operations.

**Distinction between credentials and authorization:**
- Having `GITHUB_TOKEN` in `Settings` is an authentication prerequisite — it allows GitHub API calls to authenticate. It is NOT an authorization decision.
- Authorization for consequential GitHub actions is granted by: a valid, unexpired, unused `GitHubConfirmation` record (direct API call path) or `ApprovalRequest.status == "approved"` (workflow path).
- `MCPServerConfig.allowed_tools` is a configuration-time permission control. It restricts which tool names may be invoked; it is not a per-invocation human approval.
- MCP `consequential` and `unknown` tool calls additionally require an `MCPApproval` as defined in REQ-M1.7 and REQ-M2.x. The `MCPApproval` is retrieved from `MCPApprovalRepository` by `mcp_approval_id` — the caller never supplies the approval object itself.

**Acceptance Criteria:**
S1.1.1 — Branch creation without a valid `confirmation_id` returns HTTP 422.
S1.1.2 — PR creation without a valid `confirmation_id` returns HTTP 422.
S1.1.3 — `WorkflowRun` actions that reach a `waiting_approval` status gate MUST NOT proceed until `ApprovalRequest.status = "approved"`.
S1.1.4 — A unit test verifies that a workflow action requiring approval does not execute when `ApprovalRequest.status = "pending"`.
S1.1.5 — No router handler directly calls a mutating `GitHubAdapter` method without going through `RepositoryService`.

### REQ-S1.2
ALL integration adapter live implementations MUST enforce bounded execution timeouts.

**Acceptance Criteria:**
S1.2.1 — GitHub adapter requests time out after 10 seconds.
S1.2.2 — Ollama adapter requests time out after 30 seconds (configurable via `Settings.OLLAMA_TIMEOUT_SECONDS: int = 30`).
S1.2.3 — Figma adapter requests time out after 10 seconds.
S1.2.4 — MCP tool calls time out after `MCPServerConfig.timeout_seconds`.
S1.2.5 — Timeout values MUST be configurable via `Settings`; hardcoded timeout constants MUST NOT be used.
S1.2.6 — A unit test verifies that when `httpx.AsyncClient` raises `httpx.TimeoutException`, the adapter raises `IntegrationExecutionError` (GitHub/Figma) or returns unavailable status (Ollama health check).

### REQ-S1.3
ALL credentials MUST be accessed exclusively through `Settings` SecretStr fields and MUST NOT appear in log output.

**Acceptance Criteria:**
S1.3.1 — `RedactSecretsProcessor` from Phase 0 is applied to all log records in Phase 1.
S1.3.2 — A unit test asserts that GitHub token value does not appear in any log record produced during adapter initialization or invocation.
S1.3.3 — MCP env secret values do not appear in log records.

### REQ-S1.4
Automatic PR merging MUST NOT be supported.

**Acceptance Criteria:**
S1.4.1 — No merge endpoint exists in the API (`/merge` path MUST NOT be registered).
S1.4.2 — `docs/openapi.json` (regenerated after Phase 1) contains no path containing the word `merge`.

### REQ-S1.5
Subprocess execution (MCP server launch) MUST be bounded with explicit environment-variable scoping.

**Isolation boundary:** Phase 1 provides environment-variable isolation only. The subprocess receives an explicitly constructed `resolved_env` dict and does NOT inherit the parent process environment as a whole. `resolved_env` = interpolated `MCPServerConfig.env` (secrets via `${SECRET_NAME}`) PLUS a minimal, explicitly-named set of system vars required for the child to start (Windows: `PATH`, `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`, `COMSPEC`; POSIX: `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`). No other parent variables — and no parent secrets — are copied. OS-level sandbox isolation (seccomp, namespaces, cgroups, AppArmor) is NOT implemented in Phase 1.

**Transport (W4-CR Conflict A):** `MCPClient` launches the subprocess via `asyncio.create_subprocess_exec(..., env=resolved_env)` and wraps its stdio in the SDK `ClientSession`. The SDK `stdio_client` helper is NOT used (it merges `get_default_environment()` into the supplied env, breaking isolation, and exposes no configurable termination grace).

**Acceptance Criteria:**
S1.5.1 — MCP server subprocesses are launched with `env` explicitly set to `resolved_env` (not `env=None`, which would inherit the full parent environment). The child receives ONLY `resolved_env`.
S1.5.2 — Server processes are terminated in a `finally` block after each tool call, using the SIGTERM → (5 s grace) → SIGKILL sequence. This cleanup is owned by `MCPClient` (the subprocess owner), not delegated to the SDK `stdio_client` context manager.
S1.5.3 — No MCP adapter spawns a process without an entry in `MCPServerConfig`.
S1.5.4 — A unit test verifies that the subprocess is launched with `env=resolved_env` (the resolved dict) and not with `env=None` (the test inspects the `asyncio.create_subprocess_exec` call arguments; the SDK `stdio_client` parent-merge path is not used).
S1.5.5 — [W4-CR Conflict A] `resolved_env` includes the minimal named system variables above; no undeclared parent variable (and no parent-only secret) appears in the child env.
S1.5.6 — [W4-CR Conflict A] The subprocess launch mechanism is `asyncio.create_subprocess_exec` driving SDK `ClientSession`; the SDK `stdio_client` is not imported by production code.

**Named subprocess tests (all 4 MUST be present in `tests/unit/test_mcp_client.py`):**
- `test_mcp_subprocess_receives_explicit_env` — `asyncio.create_subprocess_exec` is called with `env=resolved_env` exactly; `ClientSession` wraps the subprocess stdio.
- `test_mcp_subprocess_does_not_inherit_parent_secrets` — a secret present only in the parent/test environment is absent from the `env` passed to the spawned subprocess.
- `test_mcp_subprocess_terminated_on_timeout` — on `timeout_seconds` expiry, SIGTERM → 5 s grace → SIGKILL; `MCPTimeoutError` raised.
- `test_mcp_subprocess_cleanup_in_finally_block` — on every exit path (success, error, timeout) the subprocess is terminated in `finally`.

---

## Area 9 — Testing Requirements

### REQ-T1.1
WHEN Phase 1 unit tests are executed,
THEN they MUST achieve at least 80% branch coverage across `src/` and cover all new repository methods, service methods, router endpoints (success and error paths), adapter live implementations (mocked), MCP client logic (mocked), and GitHub API interactions (mocked).

**Acceptance Criteria:**
T1.1.1 — `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0 on the complete Phase 1 codebase.
T1.1.2 — Every new router has tests for at least: success path, 404, 422, and (where applicable) 502.
T1.1.3 — Every new service method has at least one unit test using an in-memory database.
T1.1.4 — All mocked adapter tests pass without network access.

### REQ-T1.2
WHEN Phase 1 Streamlit pages are tested,
THEN `AppTest` smoke tests MUST exist for every new and modified page.

**Acceptance Criteria:**
T1.2.1 — `AppTest` smoke tests exist for: `1_Dashboard.py`, `2_Projects.py`, `6_Workflows.py`, `7_History.py`, `9_Integrations.py`, `10_Settings.py`.
T1.2.2 — All smoke tests mock `APIClient` methods to avoid backend dependency.
T1.2.3 — All smoke tests assert absence of `at.exception`.

### REQ-T1.3
WHEN integration tests for database migrations are run,
THEN the Phase 1 migration test MUST run the full round-trip: `upgrade head → verify tables → downgrade to Phase 0 → verify Phase 0 tables remain`.

**Acceptance Criteria:**
T1.3.1 — `pytest -m integration tests/integration/test_database.py` runs all migration round-trips.
T1.3.2 — Tests use a `tmp_path`-scoped SQLite file, not the development database.
T1.3.3 — The test verifies that after downgrade the Phase 1-only tables are absent.

### REQ-T1.4
WHEN Phase 0 tests are re-run on the Phase 1 codebase,
THEN all Phase 0 tests MUST continue to pass without modification.

**Acceptance Criteria:**
T1.4.1 — `pytest tests/unit/ tests/smoke/ tests/integration/` exits with code 0 on the Phase 1 codebase.
T1.4.2 — No Phase 0 test file is modified in Phase 1 (exception: fixture additions in `conftest.py` that do not change existing fixtures).
