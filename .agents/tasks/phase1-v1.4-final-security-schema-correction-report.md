# Phase 1 v1.4.0 Final Security and Schema Correction Report (F6–F9)

**Version:** 1.0.0
**Date:** 2026-11-15
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Preceding report:** `.agents/tasks/phase1-v1.4.0-correction-report.md` (v1.4.0, F1–F3)

---

## 1. Findings F6–F9 Closure

### F6 — MCP Approval Schema Conflict (CRITICAL)

**Original problem:** The spec (v1.4.0 pre-F6) conflated MCP authorization with workflow step approvals by reusing the `approval_requests` table / `ApprovalRequest` model (integer PK) for MCP tool authorization. `MCPService` was specified to use `ApprovalRequestRepository` and accept `approval_request_id: str`. This is architecturally incorrect — the `approval_requests` table is exclusively for workflow step approval gates (REQ-W1.3, REQ-W1.6).

**Exact fix applied:**
- Added a dedicated `mcp_approvals` table (UUID PK as TEXT) with its own SQLAlchemy model `MCPApproval` and `MCPApprovalRepository`.
- Added migration `007_add_mcp_approvals` (Wave 5, Task G1 extended), `down_revision = "006_add_github_confirmations"`. Full chain: 001 → 002 → 003 → 004 → 005 → 006 → 007.
- Updated `MCPService.__init__` to inject `mcp_approval_repo: MCPApprovalRepository` (NOT `approval_request_repo: ApprovalRequestRepository`).
- Updated `MCPService.invoke_tool` to accept `mcp_approval_id: UUID | None` and retrieve `MCPApproval` from `MCPApprovalRepository` internally.
- Added REQ-M2.1–REQ-M2.4 requirements section in requirements.md.
- Added §3.7b (mcp_approvals DDL, MCPApproval model, MCPApprovalRepository interface) in design.md.
- Added `MCPApproval` model and `MCPApprovalRepository` as Wave 5 deliverables in tasks.md Task G1 (extended).
- Noted the Wave 5 migration reassignment explicitly: Wave 5 previously delivered migration 006 only; it now delivers both 006 (github_confirmations) and 007 (mcp_approvals).
- Added explicit separation note in design.md §7.5: "The workflow `approval_requests` table (integer PK) is not used for MCP authorization. `MCPApproval` (UUID PK, `mcp_approvals` table) is the sole authorization record for MCP consequential tool invocations."

**Sections updated:**
- requirements.md: REQ-M1.7 (complete rewrite), new REQ-M2.1–M2.4 section, REQ-W1.7 audit table, REQ-S1.1, REQ-DB1.1
- design.md: §1 (design principles), §3.0 (migration chain), new §3.7b (MCPApproval DDL + model + repo), §7.5 (MCPService — full rewrite), §7.5b (new failure/retry policy), §13 (file layout), §16 (audit events), §19 (traceability matrix)
- tasks.md: Task G1 (extended deliverables + acceptance criteria), Task I4 (deliverables, key notes, acceptance criteria, named tests)
- roadmap.md: Alembic Migration Chain, Wave 5 task description, Wave 5 completion gate, Security Summary table, Scope Boundaries

---

### F7 — Outdated MCP Authorization References (HIGH)

**Original problem:** Multiple places in the spec referred to `ApprovalRecord` (in-memory), `ApprovalRequest` in MCP context, and `ApprovalRequestRepository` for MCP authorization. The 8-step sequence became 9 steps with the F6 separation.

**Exact fix applied:**
- Replaced all `ApprovalRecord` references in MCP authorization contexts with `MCPApproval`.
- Replaced `ApprovalRequestRepository` in `MCPService` context with `MCPApprovalRepository`.
- Updated the mandatory sequence from 8 to 9 steps: step 7 (consume_atomic) is now explicitly separated from step 6 (validation) to make clear that atomic consumption is the last gate before execution.
- Added the full 9-step sequence to REQ-M1.7 and design.md §7.5.
- Labelled old `ApprovalRequestRepository`-based MCPService design as SUPERSEDED in design.md §7.5.
- Updated design.md §16 audit event table to reference `MCPApproval` and add `mcp_tool_completed`.
- Scan results for remaining `ApprovalRecord` or `caller-supplied approval` language in MCP context: clean after corrections.

**Sections updated:**
- requirements.md: REQ-M1.7 (9-step sequence, MCPApproval references throughout), REQ-W1.7 (audit table updated)
- design.md: §1, §7.5 (SUPERSEDED label on old ApprovalRequestRepository content), §16
- roadmap.md: Security Summary table (MCP row updated)

---

### F8 — Wave 1 Foreign-Key Tests (MEDIUM)

**Original problem:** Wave 1 Task P6 included `test_wave1_cascade_delete_enforced`, but no real CASCADE relationship exists between Wave 1 tables. The `projects` table (Phase 0) and the `tags_json` column (migration 002) have no child FK relationship that would cascade. The fallback "if no Wave 1 child FK exists yet, creates a minimal test using the tags_json column FK relationships or skips with a comment" was ambiguous and unimplementable.

**Exact fix applied:**

Wave 1 (Task P6) now contains ONLY these precise FK-related tests:
1. `test_foreign_key_pragma_enabled_on_connection` — PRAGMA foreign_keys=ON verified on a live test connection (unchanged from prior spec)
2. `test_fk_enforcement_with_wave1_tables` — Insert a row with an invalid parent FK → verify IntegrityError is raised. Use `repository_configs.project_id → projects.id` if available, OR create a minimal in-memory `sa.Table` with an FK to `projects` to verify PRAGMA enforcement. Does NOT reference `WorkflowRun`, `WorkflowAuditLog`, or any Wave 2 model class.
3. `test_migration_002_upgrade_downgrade` — alembic upgrade to 002 and downgrade back to base succeeds without error.

Removed: `test_wave1_cascade_delete_enforced` (no real Wave 1 CASCADE). Removed the ambiguous "or skips with a comment" fallback language.

Wave 2 (Task W6) FK tests remain authoritative (unchanged):
1. `test_delete_project_sets_workflow_project_id_null`
2. `test_delete_workflow_cascades_to_workflow_runs`
3. `test_delete_workflow_run_sets_audit_log_workflow_run_id_null`
4. `test_insert_invalid_foreign_key_raises_integrity_error`

Updated REQ-DB1.3 acceptance criteria numbering:
- DB1.3.1 — PRAGMA foreign_keys=ON on every connection
- DB1.3.2 — `test_foreign_key_pragma_enabled_on_connection`
- DB1.3.3 — `test_fk_enforcement_with_wave1_tables` (FK enforcement, Wave 1 tables / in-memory, NO Wave 2 tables)
- DB1.3.4 — `test_migration_002_upgrade_downgrade`
- DB1.3.5–DB1.3.8 — Wave 2 FK tests (unchanged)

**Sections updated:**
- requirements.md: REQ-DB1.3 acceptance criteria (Wave 1 criteria replaced)
- tasks.md: Task P6 required test cases, "Note on FK tests moved to Wave 2" section

---

### F9 — Approval Consumption and External Failure Handling (MEDIUM)

**Original problem:** No spec text defined what happens when a consequential MCP tool or GitHub action fails after the approval/confirmation is consumed. The spec implied approvals could be replayed on failure, which is incorrect and dangerous.

**Exact fix applied:**

Added to requirements.md (new REQ-M2.4 section and REQ-G1.4 failure semantics paragraph):
- An MCPApproval authorizes at most one execution attempt.
- Consumed approvals cannot be replayed regardless of execution outcome.
- Execution failure does NOT restore the approval to APPROVED status.
- Timeout/connection loss treated as indeterminate.
- No automatic retry without new explicit MCPApproval.
- Exactly-once caveat added for both MCP and GitHub operations.

Added to design.md (new §7.5b):
- MCPApproval failure semantics (full policy)
- GitHubConfirmation failure semantics (parallel policy)
- Exact-once caveats for both

Added to requirements.md REQ-G1.4:
- GitHubConfirmation failure semantics paragraph

Added named tests:
- `test_execution_failure_does_not_restore_approval` (REQ-M2.4.1)
- `test_timeout_recorded_as_indeterminate_in_audit` (REQ-M2.4.2)
- `test_new_approval_required_for_retry_after_failure` (REQ-M2.4.3)
- `test_github_confirmation_not_restored_after_api_failure` (REQ-M2.4.4)

**Sections updated:**
- requirements.md: REQ-M2.4 (new), REQ-G1.4 (failure semantics paragraph)
- design.md: new §7.5b (Failure and Retry Policy)
- tasks.md: Task I4 (key implementation notes, acceptance criteria 14, additional named tests), Task G2 (audit note), Task G5 (additional test cases + acceptance criteria 9–10)

---

## 2. Exact Files and Sections Modified

| File | Sections changed |
|---|---|
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | Header (version history), REQ-W1.7 (audit table), REQ-M1.7 (complete rewrite → 9-step sequence, MCPApproval), new REQ-M2.1–M2.4, REQ-S1.1, REQ-DB1.1 (migration 007 added), REQ-DB1.3 (Wave 1 criteria F8), REQ-G1.4 (failure semantics F9) |
| `.kiro/specs/phase1-functional-orchestration/design.md` | Header (version history), §1 (design principles), §3.0 (migration chain + 007), new §3.7b (MCPApproval DDL/model/repo), §7.5 (MCPService full rewrite, SUPERSEDED label), new §7.5b (failure/retry policy), §13 (file layout), §16 (audit events), §19 (traceability matrix) |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Header (version history), Task P6 (FK tests F8), Task I4 (deliverables, key notes, ACs, named tests for F6/F9), Task G1 (extended for migration 007 + MCPApproval), Task G5 (additional test cases + ACs), Task I7 (test list updated for F6) |
| `docs/planning/phase1-roadmap.md` | Header (version history), Scope Boundaries, Alembic Migration Chain (007 added), Wave 5 task description + completion gate, Security Summary table |
| `docs/reviews/phase1-specification-review.md` | New §17 "v1.4.0 Security and Schema Correction Pass (F6–F9)" appended |
| `.agents/tasks/phase1-v1.4-final-security-schema-correction-report.md` | New file — this report |

---

## 3. MCPApproval Schema

**Table:** `mcp_approvals`
**Migration:** `007_add_mcp_approvals` (Wave 5, `down_revision = "006_add_github_confirmations"`)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | UUID stored as text |
| `mcp_server_id` | TEXT | NOT NULL | MCPServerConfig.name |
| `tool_name` | TEXT | NOT NULL | Tool being authorized |
| `arguments_hash` | TEXT | NOT NULL | SHA-256 of canonical JSON of arguments |
| `actor_id` | TEXT | NOT NULL | Local user identifier (single-user threat model) |
| `workflow_run_id` | INTEGER | nullable FK → workflow_runs.id ON DELETE SET NULL | Optional audit linkage |
| `status` | TEXT | NOT NULL DEFAULT 'PENDING' CHECK IN ('PENDING','APPROVED','REJECTED','EXPIRED','CONSUMED') | Lifecycle state |
| `requested_at` | DATETIME | NOT NULL | UTCDateTime |
| `resolved_at` | DATETIME | nullable | Set when APPROVED or REJECTED |
| `expires_at` | DATETIME | NOT NULL | UTCDateTime |
| `consumed_at` | DATETIME | nullable | Set atomically on consumption |

**Indexes:** `idx_mcp_approvals_server`, `idx_mcp_approvals_status`, `idx_mcp_approvals_expires`

**Valid status transitions:**
- `PENDING` → `APPROVED` (human resolves as approved)
- `PENDING` → `REJECTED` (human resolves as rejected)
- `APPROVED` → `CONSUMED` (atomic consumption on use, via `consume_atomic`)
- `PENDING` → `EXPIRED` (TTL elapsed before resolution)
- `APPROVED` → `EXPIRED` (TTL elapsed before consumption)

---

## 4. Complete Alembic Migration Sequence

| Revision ID | `down_revision` | File | Wave | Tables |
|---|---|---|---|---|
| `"001_create_initial_tables"` | `None` | `001_create_initial_tables.py` | Phase 0 | projects, learning_items, integration_configs |
| `"002_add_project_tags_column"` | `"001_create_initial_tables"` | `002_add_project_tags_column.py` | Wave 1 | ALTER projects ADD tags_json |
| `"003_add_workflow_tables"` | `"002_add_project_tags_column"` | `003_add_workflow_tables.py` | Wave 2 | workflows, workflow_runs |
| `"004_add_approval_audit_tables"` | `"003_add_workflow_tables"` | `004_add_approval_audit_tables.py` | Wave 2 | approval_requests, workflow_audit_log |
| `"005_add_repository_tables"` | `"004_add_approval_audit_tables"` | `005_add_repository_tables.py` | Wave 2 | repository_configs |
| `"006_add_github_confirmations"` | `"005_add_repository_tables"` | `006_add_github_confirmations.py` | Wave 5 | github_confirmations |
| `"007_add_mcp_approvals"` | `"006_add_github_confirmations"` | `007_add_mcp_approvals.py` | Wave 5 | mcp_approvals |

**Wave ownership:** Wave 1 = {002}. Wave 2 = {003, 004, 005}. Wave 5 = {006, 007}. Each migration assigned to exactly one wave. No gaps. No forks.

---

## 5. MCP 9-Step Authorization Sequence

```
Caller → MCPService.invoke_tool(
    server_name, tool_name, arguments,
    actor_id, workflow_run_id=None,
    mcp_approval_id=<UUID>   ← caller supplies ONLY this UUID
)

Step 1: Verify MCP server is configured and enabled in MCPServerConfig.
        → MCPServerNotFoundError if absent.

Step 2: Verify tool is on the allow-list (MCPServerConfig.allowed_tools).
        → MCPPermissionError if denied.

Step 3: Classify tool as read_only | consequential | unknown.

Step 4: Default unknown → consequential (deny-by-default policy).

Step 5: For consequential/unknown:
         record = MCPApprovalRepository.get_by_id(mcp_approval_id)
         If None → log mcp_approval_missing, raise MCPApprovalRequiredError.

Step 6: Validate MCPApproval record:
         (a) status == APPROVED → else MCPApprovalRequiredError
         (b) expires_at > now(UTC) → else log mcp_approval_expired,
             raise MCPApprovalExpiredError (NOT mcp_approval_denied)
         (c) mcp_server_id, tool_name, arguments_hash, actor_id match
             → else MCPApprovalRequiredError (mismatch)
         (d) status != CONSUMED → else MCPApprovalRequiredError (replay)

Step 7: MCPApprovalRepository.consume_atomic(mcp_approval_id)
         ← UPDATE WHERE status='APPROVED' AND id=?
         ← 0 rows updated → ConsumedError → MCPApprovalRequiredError
         Log mcp_approval_granted.

Step 8: MCPClient.call_tool(server_name, tool_name, arguments)
         → Log mcp_tool_invoked (subprocess launched)
         → On success: log mcp_tool_completed
         → On exception/timeout: log mcp_tool_failed, re-raise
         IMPORTANT: execution failure does NOT restore MCPApproval to APPROVED.

Step 9: Audit events recorded; no credentials or argument values in logs.
        Each event includes mcp_approval_id for traceability.
```

**Step 7 is explicitly separated from step 6** because atomic consumption is the last gate before execution. A consumed approval cannot be replayed regardless of execution outcome.

**Security properties:**
- Caller cannot fabricate an approval — they only supply a UUID.
- Approval is bound to specific server, tool, arguments (SHA-256), and actor.
- One-time use enforced by atomic `consume_atomic` (UPDATE WHERE status='APPROVED').
- Two concurrent calls with same ID: exactly one succeeds, one gets MCPApprovalRequiredError.
- Expiry emits `mcp_approval_expired`, not `mcp_approval_denied` (distinct audit events).
- Failed execution does not restore approval — user must issue new MCPApproval for retry.

---

## 6. FK Test Matrix

| Test name | Tables involved | Relationship type | Wave | Task |
|---|---|---|---|---|
| `test_foreign_key_pragma_enabled_on_connection` | Live test connection only | Infrastructure (PRAGMA check) | Wave 1 | P6 |
| `test_fk_enforcement_with_wave1_tables` | projects + minimal in-memory sa.Table (or repository_configs if available) | FK constraint enforcement (IntegrityError) | Wave 1 | P6 |
| `test_migration_002_upgrade_downgrade` | projects (via alembic) | Migration round-trip | Wave 1 | P6 |
| `test_delete_project_sets_workflow_project_id_null` | projects, workflows | ON DELETE SET NULL (Workflow.project_id) | Wave 2 | W6 |
| `test_delete_workflow_cascades_to_workflow_runs` | workflows, workflow_runs | ON DELETE CASCADE (WorkflowRun.workflow_id) | Wave 2 | W6 |
| `test_delete_workflow_run_sets_audit_log_workflow_run_id_null` | workflow_runs, workflow_audit_log | ON DELETE SET NULL (WorkflowAuditLog.workflow_run_id) | Wave 2 | W6 |
| `test_insert_invalid_foreign_key_raises_integrity_error` | workflows, workflow_runs | Referential integrity (WorkflowRun.workflow_id) | Wave 2 | W6 |

**Removed test (F8):** `test_wave1_cascade_delete_enforced` — no real CASCADE in Wave 1 tables.

---

## 7. Failure and Retry Policy Summary

### MCP Tool Invocations

| Event | Approval status after | Audit event | Retry path |
|---|---|---|---|
| `MCPClient.call_tool` succeeds | CONSUMED (unchanged) | `mcp_tool_invoked`, `mcp_tool_completed` | N/A — success |
| `MCPClient.call_tool` raises exception | CONSUMED (not restored) | `mcp_tool_invoked`, `mcp_tool_failed` | User issues new MCPApproval |
| Subprocess timeout | CONSUMED (not restored) | `mcp_tool_invoked`, `mcp_tool_failed` | User verifies external state; issues new MCPApproval |
| Indeterminate outcome (crash) | CONSUMED (not restored) | `mcp_tool_invoked`, `mcp_tool_failed` | User verifies external state; issues new MCPApproval |

**Exactly-once caveat:** "DevFlow AI cannot guarantee exactly-once execution of external MCP tools. If the subprocess was launched but the result is unknown (timeout/crash), the user must verify the external state before approving a retry."

### GitHub API Operations

| Event | Confirmation status after | Audit event | Retry path |
|---|---|---|---|
| GitHub API succeeds | used_at set (unchanged) | `github_action_authorized`, `github_action_executed` | N/A — success |
| GitHub API fails after consumption | used_at set (not restored) | `github_action_authorized`, `github_action_failed` | User verifies GitHub state; issues new GitHubConfirmation |
| Indeterminate outcome | used_at set (not restored) | `github_action_authorized`, `github_action_failed` | User verifies GitHub state; issues new GitHubConfirmation |

**Exactly-once caveat:** "DevFlow AI cannot guarantee exactly-once execution of GitHub API operations. If the API call was made but the result is unknown, the user must verify the GitHub state before issuing a new confirmation."

---

## 8. Requirement → Design → Task → Test Traceability (F6–F9)

| Req ID | Requirement summary | Design section | Task IDs | Named tests |
|---|---|---|---|---|
| REQ-M1.7 | MCP 9-step auth; mcp_approval_id only; MCPApprovalRepository; 8 audit events | design.md §7.5 | I4, I7 | test_forged_approval_record_rejected; test_expired_approval_rejected_at_invocation; test_mismatched_tool_name_rejected; test_mismatched_arguments_hash_rejected; test_replay_after_consumption_rejected; test_concurrent_consumption_safe; test_read_only_tool_no_approval_required; test_no_direct_mcp_client_bypass |
| REQ-M2.1 | MCPApproval model (UUID PK, mcp_approvals table, 5-state lifecycle) | design.md §3.7b | G1, I4 | test_mcp_approval_model_importable |
| REQ-M2.2 | MCPApprovalRepository (create, get_by_id, consume_atomic, list_pending) | design.md §3.7b, §7.5 | G1, I4, I7 | test_mcp_approval_consume_atomic_safe; test_concurrent_consumption_safe |
| REQ-M2.3 | MCPService injected with MCPApprovalRepository (not ApprovalRequestRepository) | design.md §7.5 | I4, I7 | test_forged_approval_record_rejected (verifies no ApprovalRequest bypass) |
| REQ-M2.4 | Failure semantics: no auto-restore; indeterminate treated as failure; new approval for retry | design.md §7.5b | I4, I7 | test_execution_failure_does_not_restore_approval; test_timeout_recorded_as_indeterminate_in_audit; test_new_approval_required_for_retry_after_failure; test_github_confirmation_not_restored_after_api_failure |
| REQ-DB1.1 | 7 migrations: 001–007, exact revision IDs + chain, Wave assignments | design.md §3.0 | P1, W2, G1, G5 | test_migration_full_round_trip (001→007) |
| REQ-DB1.3 (Wave 1) | PRAGMA FK test; fk_enforcement_with_wave1_tables; migration 002 round-trip | design.md §3.7 | P1, P6 | test_foreign_key_pragma_enabled_on_connection; test_fk_enforcement_with_wave1_tables; test_migration_002_upgrade_downgrade |
| REQ-DB1.3 (Wave 2) | WorkflowRun CASCADE; WorkflowAuditLog SET NULL; IntegrityError on bad FK | design.md §3.7 | W6 | test_delete_project_sets_workflow_project_id_null; test_delete_workflow_cascades_to_workflow_runs; test_delete_workflow_run_sets_audit_log_workflow_run_id_null; test_insert_invalid_foreign_key_raises_integrity_error |
| REQ-G1.4 (F9) | GitHub failure semantics; no auto-restore of confirmation | design.md §7.5b | G2, G5 | test_github_confirmation_not_restored_after_api_failure |

---

## 9. Remaining Risks or Unresolved Decisions

| Risk/Decision | Severity | Notes |
|---|---|---|
| Self-assessed review | Medium | This correction report is self-assessed. Independent review by a reviewer other than the spec author is required before implementation begins. |
| `consume_atomic` SQLite concurrency for MCPApproval | Medium | SQLite WAL mode + `UPDATE WHERE status='APPROVED' AND id=?` provides sufficient atomicity for single-node local use. The named test `test_concurrent_consumption_safe` must verify this under asyncio concurrency. Equivalent to the same test already specified for GitHubConfirmation. |
| `approval_requests` table still exists for workflow step approvals | Low | The `approval_requests` table (integer PK) remains in the spec for workflow step approval gates (REQ-W1.3, REQ-W1.6). It has no UUID fields. The separation from `mcp_approvals` is now explicit and unambiguous. The `ApprovalRequestRepository` in `repositories/approval_request.py` is for workflow step approvals only — it has never been correct to use it for MCP authorization, and F6 corrects this. |
| MCPApproval issuance API endpoint not specified | Low | The spec defines the MCPApproval model, repository, and consumption flow. It does not define a `POST /api/v1/mcp-approvals` endpoint for creating MCPApproval records. This endpoint would be needed in practice but falls outside the correction scope. The human approval flow for MCP (how PENDING becomes APPROVED) should be defined in a follow-on spec pass. |
| Wave 5 complexity increase | Low | Task G1 now delivers 2 additional files (mcp_approval model + repository) and migration 007. The estimated size (Medium) may need revision to Large. |
| `mcp_tool_completed` vs `mcp_tool_invoked` semantics | Low | `mcp_tool_invoked` is logged when approval is consumed and subprocess launched. `mcp_tool_completed` is logged when subprocess returns success. These two events are now explicitly distinct per F6/F9. Implementer must ensure both are emitted in the success path. |

---

## 10. Git Status

**git status --short:**
```
 M .kiro/specs/phase1-functional-orchestration/design.md
 M .kiro/specs/phase1-functional-orchestration/requirements.md
 M .kiro/specs/phase1-functional-orchestration/tasks.md
 M docs/planning/phase1-roadmap.md
 M docs/reviews/phase1-specification-review.md
?? .agents/tasks/phase1-v1.4.0-correction-report.md
?? .agents/tasks/phase1-v1.4-final-security-schema-correction-report.md
?? zip/kiro-phase1-specs-v1.4.0-20261115-080931.zip
```

**git diff --stat:**
```
 .kiro/specs/phase1-functional-orchestration/design.md      | 247 +++++++---
 .kiro/specs/phase1-functional-orchestration/requirements.md | 187 +++++--
 .kiro/specs/phase1-functional-orchestration/tasks.md        | 136 +++--
 docs/planning/phase1-roadmap.md                             | 108 ++--
 docs/reviews/phase1-specification-review.md                 | 545 +++++++++++++++++++--
 5 files changed, 955 insertions(+), 268 deletions(-)
```

No `src/`, `tests/`, `alembic/`, `.github/workflows/`, or `pyproject.toml` files modified.

---

## 11. Final Verdict

**READY FOR FINAL INDEPENDENT REVIEW**

All four findings resolved:
- **F6** (CRITICAL) — Dedicated `mcp_approvals` table / `MCPApproval` model / `MCPApprovalRepository` defined. `MCPService` updated to use `MCPApprovalRepository`. `ApprovalRequest`/`ApprovalRequestRepository` retained exclusively for workflow step approvals. Migration 007 added to Wave 5.
- **F7** (HIGH) — All `ApprovalRecord` and `ApprovalRequestRepository` references in MCP authorization context replaced with `MCPApproval` and `MCPApprovalRepository`. 9-step mandatory sequence documented. SUPERSEDED label on old design.
- **F8** (MEDIUM) — `test_wave1_cascade_delete_enforced` removed (no real Wave 1 CASCADE). Replaced by precise `test_fk_enforcement_with_wave1_tables` and `test_migration_002_upgrade_downgrade`. REQ-DB1.3 acceptance criteria renumbered and clarified.
- **F9** (MEDIUM) — Explicit failure semantics defined for MCPApproval and GitHubConfirmation. No auto-restore after failure. Indeterminate outcomes treated as failures. Exactly-once caveats added. 4 named tests added.

All 15 consistency checks pass (see §16 of review document for verification).

**Note:** This report is self-assessed. Independent review by a reviewer other than the spec author is required before implementation begins.
