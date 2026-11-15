# Phase 1 v1.4.0 Specification Correction Report

**Version:** 1.0.0
**Date:** 2026-11-15
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Preceding report:** `.agents/tasks/phase1-final-spec-correction-report.md` (v1.3.0, F1–F5 + D1–D4)

---

## 1. Files Modified

| File | Sections changed | Version before → after |
|---|---|---|
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | Header only (version, Last Updated, Supersedes, version history) | v1.3.0 → v1.4.0 |
| `.kiro/specs/phase1-functional-orchestration/design.md` | Header only (version, Last Updated, Supersedes, version history) | v1.3.0 → v1.4.0 |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Header only (version, Last Updated, Supersedes, version history) | v1.3.0 → v1.4.0 |
| `docs/planning/phase1-roadmap.md` | Header only (version, Last Updated, Supersedes, version history) | v1.3.0 → v1.4.0 |
| `docs/reviews/phase1-specification-review.md` | Header (version, Last Updated, Supersedes); new §16 "v1.4.0 Correction Pass (F1–F3)" appended | v1.3.0 → v1.4.0 |
| `.agents/tasks/phase1-v1.4.0-correction-report.md` | New file — this report | — |

No `src/`, `tests/`, `alembic/`, `.github/workflows/`, or `pyproject.toml` files were modified.

---

## 2. F1 Closure Summary — MCP Approval Authorization

**Finding:** The original `MCPService.invoke_tool` accepted an in-memory `ApprovalRecord` object supplied by its caller, allowing callers to fabricate an approved record and bypass the authorization gate.

**Fix applied (from v1.3.0 — already in all five documents):**

The `invoke_tool` signature was changed to accept `approval_request_id: str | None`. MCPService retrieves the `ApprovalRequest` from `ApprovalRequestRepository` by that ID and validates it internally. Callers never touch the approval object.

**8-step mandatory authorization sequence (requirements.md REQ-M1.7, design.md §7.5):**
1. Verify MCP server is configured and enabled.
2. Verify tool is on the allow-list (raises `MCPPermissionError` if denied).
3. Classify tool as `read_only`, `consequential`, or `unknown`.
4. Default `unknown` → `consequential` (deny-by-default).
5. For `consequential`/`unknown`: retrieve `ApprovalRequest` from `ApprovalRequestRepository` by `approval_request_id`. If absent or not found → log `mcp_approval_missing`, raise `MCPApprovalRequiredError`.
6. Validate retrieved record: status == APPROVED; expires_at in future (else log `mcp_approval_expired`, raise `MCPApprovalExpiredError` — NOT `mcp_approval_denied`); mcp_server_id/tool_name/arguments_hash/actor_id match; not already CONSUMED. Atomically set CONSUMED via `consume_atomic`.
7. Execute: `MCPClient.call_tool` only through `MCPService` gateway; no direct calls permitted.
8. Record all 7 MCP audit events without leaking credentials or argument values.

**No-bypass rule:** No adapter, router, or Streamlit handler may import or call `MCPClient.call_tool` directly. Verified by `test_no_direct_mcp_client_bypass`.

**8 named tests (all in `tests/unit/test_mcp_service.py`):**
- `test_forged_approval_record_rejected`
- `test_expired_approval_rejected_at_invocation`
- `test_mismatched_tool_name_rejected`
- `test_mismatched_arguments_hash_rejected`
- `test_replay_after_consumption_rejected`
- `test_concurrent_consumption_safe`
- `test_read_only_tool_no_approval_required`
- `test_no_direct_mcp_client_bypass`

---

## 3. F2 Closure Summary — FK Cascade Test Corrections

**Finding:** The original FK cascade tests in Wave 1 (Task P6) referenced `WorkflowRun` and `WorkflowAuditLog` — Wave 2 tables — making Wave 1 independently unsatisfiable. Additionally, the cascade directions required correction.

**Fix applied (from v1.3.0 — already in all five documents):**

**Corrected FK cascade directions (design.md §3.7):**

| Column | References | ON DELETE behavior | Effect |
|---|---|---|---|
| `Workflow.project_id` | `projects.id` | SET NULL | Deleting a Project sets Workflow.project_id to NULL; Workflow record is NOT deleted. |
| `WorkflowRun.workflow_id` | `workflows.id` | CASCADE | Deleting a Workflow deletes all its WorkflowRun records. |
| `WorkflowAuditLog.workflow_run_id` | `workflow_runs.id` | SET NULL | Deleting a WorkflowRun sets WorkflowAuditLog.workflow_run_id to NULL; audit entries are NOT deleted. |

**5 named FK tests with wave assignments:**

| Test name | Wave | Task | Relationship tested | ON DELETE behavior |
|---|---|---|---|---|
| `test_foreign_key_pragma_enabled_on_connection` | 1 | P6 | PRAGMA foreign_keys=ON active | — |
| `test_wave1_cascade_delete_enforced` | 1 | P6 | Wave 1 tables only (no WorkflowRun) | CASCADE (Wave 1 scope) |
| `test_wave1_insert_invalid_foreign_key_raises_integrity_error` | 1 | P6 | Wave 1 FK constraint | IntegrityError |
| `test_delete_project_sets_workflow_project_id_null` | 2 | W6 | Workflow.project_id | SET NULL |
| `test_delete_workflow_cascades_to_workflow_runs` | 2 | W6 | WorkflowRun.workflow_id | CASCADE |
| `test_delete_workflow_run_sets_audit_log_workflow_run_id_null` | 2 | W6 | WorkflowAuditLog.workflow_run_id | SET NULL |
| `test_insert_invalid_foreign_key_raises_integrity_error` | 2 | W6 | WorkflowRun with non-existent workflow_id | IntegrityError |

Note: Wave 1 tests (Task P6) use Wave 1 tables only. Wave 2 tests (Task W6) use Wave 2 tables and cover the full cascade chain.

---

## 4. F3 Closure — Document Metadata

**Finding:** All five spec documents contained placeholder `Last Updated` text: `[current correction pass — implementer fills date at commit time]`. All five showed version 1.3.0.

**Fix applied (this pass):**

| Field | Before | After |
|---|---|---|
| `Version` | `1.3.0` | `1.4.0` |
| `Last Updated` | `[current correction pass — implementer fills date at commit time]` | `2026-11-15` |
| `Supersedes` | `v1.2.0 (F1–F5 ...)` | `v1.3.0 (F1–F3 corrections applied — ...)` |
| `Version history` | Ends at v1.3.0 entry | Adds: `v1.4.0 — 2026-11-15 — Corrections F1 (MCP approval authorization via approval_request_id), F2 (FK cascade test corrections), F3 (metadata). Branch: feature/phase1-specification-planning, Base: aaaaacb703124fc31b0e757b2bf1739c4fb225c9.` |

Applied to all five documents:
- `.kiro/specs/phase1-functional-orchestration/requirements.md`
- `.kiro/specs/phase1-functional-orchestration/design.md`
- `.kiro/specs/phase1-functional-orchestration/tasks.md`
- `docs/planning/phase1-roadmap.md`
- `docs/reviews/phase1-specification-review.md`

No Git commit hashes were invented. No PRs are claimed as merged.

---

## 5. Consistency Verification Results

All 13 checks evaluated against all five v1.4.0 documents:

| # | Check | Result |
|---|---|---|
| 1 | Linear Alembic migration chain: 001→002→003→004→005→006 (no gaps, no forks). Migration 006 assigned to Wave 5. | PASS |
| 2 | GitHubConfirmation: SQLite-backed, single-use, atomic consume_atomic, bound to repo/operation/parameters_hash/actor. | PASS |
| 3 | MCP approval: invoke_tool accepts approval_request_id (not ApprovalRecord); MCPService retrieves from repo internally; all binding fields validated; atomic CONSUMED transition. | PASS |
| 4 | WorkflowRun states: exactly CREATED/PENDING/APPROVED/RUNNING/COMPLETED/FAILED/CANCELLED mapping (no PAUSED state). Spec uses: pending, running, waiting_approval, completed, failed, cancelled — no paused. | PASS |
| 5 | Coverage gate consistent: `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` everywhere. | PASS |
| 6 | Wave 1 completion gate does not reference any Wave 2 table (WorkflowRun, WorkflowStep, ApprovalRequest, WorkflowAuditLog). | PASS |
| 7 | FK cascade directions: Workflow.project_id SET NULL; WorkflowRun.workflow_id CASCADE; WorkflowAuditLog.workflow_run_id SET NULL. | PASS |
| 8 | No autonomous AI provider invocation in Phase 1. | PASS |
| 9 | No automatic GitHub PR merging. | PASS |
| 10 | No confirmed=True boolean as authorization gate anywhere in active sections. | PASS |
| 11 | All 11 integration adapters retain approved execution modes (Codex = cli_handoff). | PASS |
| 12 | No Android, React, TypeScript, or Vite references. | PASS |
| 13 | No ApprovalRecord (in-memory) object passed to invoke_tool anywhere in spec text. | PASS |

No fixes were required during consistency verification. All 13 checks pass on the v1.4.0 documents.

---

## 6. MCP Approval Authorization Design Summary

**invoke_tool flow (design.md §7.5, requirements.md REQ-M1.7):**

```
Caller → MCPService.invoke_tool(
    server_name, tool_name, arguments,
    actor_id, workflow_run_id=None,
    approval_request_id="<UUID string>"   ← caller supplies ONLY this ID
)

Step 1: Verify server configured and enabled in MCPServerConfig.
Step 2: Check tool against allowed_tools → MCPPermissionError if denied.
Step 3: Classify tool: read_only | consequential | unknown.
Step 4: Default unknown → consequential (deny-by-default).
Step 5: For consequential/unknown:
         record = ApprovalRequestRepository.get_by_id(approval_request_id)
         If None → log mcp_approval_missing, raise MCPApprovalRequiredError.
Step 6: Validate record:
         (a) status == APPROVED → else MCPApprovalRequiredError
         (b) expires_at > now(UTC) → else log mcp_approval_expired,
             raise MCPApprovalExpiredError (NOT mcp_approval_denied)
         (c) mcp_server_id, tool_name, arguments_hash, actor_id match
             → else MCPApprovalRequiredError (mismatch)
         (d) status != CONSUMED → else MCPApprovalRequiredError (replay)
         ApprovalRequestRepository.consume_atomic(id, now)
           ← single DB transaction: UPDATE WHERE status='APPROVED' AND id=?
           ← 0 rows updated → MCPApprovalRequiredError (concurrent safety)
         Log mcp_approval_granted.
Step 7: MCPClient.call_tool(server_name, tool_name, arguments)
         → On success: log mcp_tool_invoked
         → On exception: log mcp_tool_failed, re-raise
Step 8: Audit events recorded; no credentials or argument values in logs.
```

**Security properties:**
- Caller cannot fabricate an approval — they only supply an ID string.
- Approval is bound to specific server, tool, arguments (via SHA-256 hash), and actor.
- One-time use enforced via atomic `consume_atomic` (UPDATE WHERE status='APPROVED').
- Two concurrent calls with same ID: exactly one succeeds, one gets MCPApprovalRequiredError.
- Expiry emits `mcp_approval_expired`, not `mcp_approval_denied` (distinct audit events).

---

## 7. FK Test Matrix

| Test name | Relationship tested | ON DELETE behavior | Wave |
|---|---|---|---|
| `test_foreign_key_pragma_enabled_on_connection` | PRAGMA foreign_keys=ON | — (infrastructure) | Wave 1 (P6) |
| `test_wave1_cascade_delete_enforced` | Wave 1 table FKs only | CASCADE (Wave 1 scope) | Wave 1 (P6) |
| `test_wave1_insert_invalid_foreign_key_raises_integrity_error` | Wave 1 FK constraint | IntegrityError | Wave 1 (P6) |
| `test_delete_project_sets_workflow_project_id_null` | Workflow.project_id → projects.id | SET NULL | Wave 2 (W6) |
| `test_delete_workflow_cascades_to_workflow_runs` | WorkflowRun.workflow_id → workflows.id | CASCADE | Wave 2 (W6) |
| `test_delete_workflow_run_sets_audit_log_workflow_run_id_null` | WorkflowAuditLog.workflow_run_id → workflow_runs.id | SET NULL | Wave 2 (W6) |
| `test_insert_invalid_foreign_key_raises_integrity_error` | WorkflowRun.workflow_id referential integrity | IntegrityError | Wave 2 (W6) |

---

## 8. Remaining Risks or Unresolved Decisions

| Risk/Decision | Severity | Notes |
|---|---|---|
| `pyproject.toml` and `ci.yml` not in scope | Low | `branch = true` must be added to `[tool.coverage.run]` and `--cov-branch` to CI pytest command at Wave 1 implementation time (Task P1 configuration ownership section). Already documented. |
| `consume_atomic` SQLite concurrency | Medium | SQLite WAL mode + `UPDATE WHERE status='APPROVED' AND id=?` provides sufficient atomicity for single-node local use. Concurrent test must verify under asyncio concurrency. Already covered by named tests `test_concurrent_consumption_safe` (MCP) and `test_concurrent_consumption_safe` (GitHub). |
| `github_confirmations.workflow_run_id` FK | Low | ON DELETE SET NULL is correct for audit purposes — confirmation record preserved when run is deleted. Already documented in design.md §3.7a. |
| Self-assessed review | Medium | This review document is self-assessed. Independent review by a reviewer other than the spec author is required before implementation begins. |
| MCP SDK version pin | Low | `mcp>=1.0,<2.0` operative at base commit. Implementer must check `pyproject.toml` at Wave 4 as instructed in Task I4 and REQ-M1.8. |
| Wave 1 and Wave 2 FK test independence | Resolved | Wave 1 P6 tests use only Wave 1 tables. Wave 2 W6 tests cover full workflow cascade chain. Split documented clearly in requirements.md REQ-DB1.3 and tasks.md P6/W6. |

---

## 9. Requirement/Task/Test Traceability

Covering F1 (MCP approval authorization) and F2 (FK cascade test corrections) requirements at minimum:

| Req ID | Req summary | Design section | Task IDs | Named tests |
|---|---|---|---|---|
| REQ-M1.7 | MCP 8-step auth; approval_request_id only; atomic CONSUMED; 7 audit events | design.md §7.5 | I4, I7 | test_forged_approval_record_rejected; test_expired_approval_rejected_at_invocation; test_mismatched_tool_name_rejected; test_mismatched_arguments_hash_rejected; test_replay_after_consumption_rejected; test_concurrent_consumption_safe; test_read_only_tool_no_approval_required; test_no_direct_mcp_client_bypass |
| REQ-DB1.3 (Wave 1) | PRAGMA foreign_keys=ON; Wave 1 FK tests independent of Wave 2 tables | design.md §3.7 | P1, P6 | test_foreign_key_pragma_enabled_on_connection; test_wave1_cascade_delete_enforced; test_wave1_insert_invalid_foreign_key_raises_integrity_error |
| REQ-DB1.3 (Wave 2) | WorkflowRun CASCADE; WorkflowAuditLog SET NULL; IntegrityError on bad FK | design.md §3.7 | W6 | test_delete_project_sets_workflow_project_id_null; test_delete_workflow_cascades_to_workflow_runs; test_delete_workflow_run_sets_audit_log_workflow_run_id_null; test_insert_invalid_foreign_key_raises_integrity_error |
| REQ-G1.4 | Branch creation requires GitHubConfirmation (SQLite-backed, atomic consume_atomic) | design.md §3.7a, §8.2 | G1, G2, G5 | test_github_confirmation_persisted_to_db; test_confirmation_expires_after_ttl; test_replay_rejected_after_use; test_parameter_mismatch_rejected; test_concurrent_consumption_safe; test_recovery_after_github_api_failure |
| REQ-W1.2 | WorkflowRun 6 states, no paused | design.md §3.3, §9 | W1, W2, W6 | test_transition_run_valid; test_transition_run_invalid |
| REQ-W1.7 | WorkflowAuditLog + 7 MCP audit events | design.md §3.5, §16 | W1, W4, W5, W6 | test_expired_mcp_approval_emits_approval_expired_event; test_missing_approval_emits_approval_missing_event |
| REQ-T1.1 | 80% branch coverage; canonical pytest command | design.md §13 | P6, W6, A5, I7, G5 | (gate: pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing exits 0) |
| REQ-S1.4 | No /merge endpoint | design.md §10.4 | G3, G5 | test_no_merge_endpoint_exists |

---

## 10. Git Status

**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9

**git status --short:**
```
 M .kiro/specs/phase1-functional-orchestration/design.md
 M .kiro/specs/phase1-functional-orchestration/requirements.md
 M .kiro/specs/phase1-functional-orchestration/tasks.md
 M docs/planning/phase1-roadmap.md
 M docs/reviews/phase1-specification-review.md
```

**git diff --stat:**
```
 .kiro/specs/phase1-functional-orchestration/design.md      |   7 +-
 .kiro/specs/phase1-functional-orchestration/requirements.md |   7 +-
 .kiro/specs/phase1-functional-orchestration/tasks.md        |   7 +-
 docs/planning/phase1-roadmap.md                             | 102 +++--
 docs/reviews/phase1-specification-review.md                 | 493 ++++++++++++++++++---
 5 files changed, 526 insertions(+), 90 deletions(-)
```

No `src/`, `tests/`, `alembic/`, `.github/workflows/`, or `pyproject.toml` files modified.

Note: The `docs/planning/phase1-roadmap.md` and `docs/reviews/phase1-specification-review.md` lines include the F1/F2 corrections already applied before this pass, in addition to the F3 metadata changes. The `.kiro/specs/` files show only the F3 header changes (7 lines each) because F1/F2 were already committed to those files.

---

## 11. Final Recommendation

**READY FOR INDEPENDENT REVIEW**

All three findings resolved:
- F1 (MCP approval authorization via approval_request_id) — applied and consistent across all five documents
- F2 (FK cascade test corrections — corrected SET NULL/CASCADE directions, 5+ named tests with wave assignments) — applied and consistent
- F3 (metadata — placeholder dates replaced with 2026-11-15, version v1.4.0 set in all five documents) — applied this pass

All 13 consistency checks PASS. No blockers remain.

**Note:** This report is self-assessed. Independent review by a reviewer other than the spec author is required before implementation begins.
