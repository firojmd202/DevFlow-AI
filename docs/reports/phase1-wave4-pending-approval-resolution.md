# Phase 1 Wave 4 — PENDING Approval Lifecycle Resolution Report

**Date:** 2026-11-16
**Repository:** `J:\Android\GenAI\DevFlow-AI`
**Branch:** `feature/phase1-wave4-integration-execution`
**Specification version:** Phase 1 **v1.5.7** (corrected from v1.5.6 by this pass)
**Scope:** Specification correction only — no application code, migrations, alembic, CI, or `pyproject.toml` modified
**Author role:** Principal Application Security Architect and SQLite Database Engineer
**Mode:** SPECIFICATION CORRECTION ONLY
**Precedes:** Codex implementation of Wave 4 (Task I4)

---

## 1. Root cause

The v1.5.6 BEFORE DELETE trigger on `workflow_runs` expired only `APPROVED` MCP approvals:

```sql
UPDATE mcp_approvals
   SET status = 'EXPIRED'
 WHERE workflow_run_id = OLD.id
   AND status = 'APPROVED';
```

A `PENDING` MCPApproval bound to a workflow run survived run deletion with:
- `status = 'PENDING'`
- `workflow_run_id = NULL` (FK SET NULL action)

After deletion, this record is **indistinguishable** from an originally-unbound PENDING approval (`workflow_run_id IS NULL` at creation). The existing gateway (`consume_atomic`) denies PENDING approvals because it requires `status='APPROVED'` — so the approval was not *immediately* exploitable. However, the stored authorization state was unsafe for future promotion:

If an approval-resolution operation later set the status to `APPROVED` (resolving what it incorrectly treated as an ordinary unbound PENDING approval), the resulting record would be `(APPROVED, NULL)`. The `consume_atomic` NULL-to-NULL binding check (`M2.5`) would match any invocation with `trusted_workflow_run_id=NULL`, authorizing an unbound MCP tool call that was never granted for that context — a privilege-escalation attack via orphaned-PENDING promotion.

The fix is to extend the BEFORE DELETE trigger to expire `status IN ('PENDING', 'APPROVED')`, closing the gap before it can be exploited.

---

## 2. Final trigger SQL

```sql
-- W4-PA: BEFORE DELETE trigger expires BOTH PENDING and APPROVED MCP approvals
-- before the ON DELETE SET NULL FK action clears the reference.
-- Trigger name: trg_workflow_runs_before_delete_expire_mcp_approvals
CREATE TRIGGER trg_workflow_runs_before_delete_expire_mcp_approvals
BEFORE DELETE ON workflow_runs
FOR EACH ROW
BEGIN
    UPDATE mcp_approvals
       SET status = 'EXPIRED'
     WHERE workflow_run_id = OLD.id
       AND status IN ('PENDING', 'APPROVED');
END;
```

**Migration 006 downgrade:**
```sql
DROP TRIGGER IF EXISTS trg_workflow_runs_before_delete_expire_mcp_approvals;
```

The trigger fires BEFORE the row is removed and BEFORE the `ON DELETE SET NULL` FK action clears `workflow_run_id`. At trigger time `OLD.id` is still the live run id. Only `status` is changed; `workflow_run_id` is left intact for the subsequent SET NULL action to clear.

---

## 3. Updated deletion lifecycle table

| Approval status before run deletion | Trigger action | FK SET NULL | Final status | Final `workflow_run_id` | Consumable after? | Promotable after? |
|---|---|---|---|---|---|---|
| PENDING (originally bound) | `status` → `EXPIRED` | `workflow_run_id` → `NULL` | `EXPIRED` | `NULL` | **No** (`status != 'APPROVED'`) | **No** (resolution only resolves PENDING; this is EXPIRED) |
| APPROVED (originally bound) | `status` → `EXPIRED` | `workflow_run_id` → `NULL` | `EXPIRED` | `NULL` | **No** (`consume_atomic` 0 rows) | **No** (already EXPIRED) |
| CONSUMED (originally bound) | none | `workflow_run_id` → `NULL` | `CONSUMED` | `NULL` | No (already consumed) | N/A |
| REJECTED (originally bound) | none | `workflow_run_id` → `NULL` | `REJECTED` | `NULL` | No (`status != 'APPROVED'`) | N/A |
| EXPIRED (originally bound) | none | `workflow_run_id` → `NULL` | `EXPIRED` | `NULL` | No (`status != 'APPROVED'`) | No |
| PENDING (originally unbound, `workflow_run_id IS NULL`) | none (no matching row) | none | `PENDING` | `NULL` | No (`status != 'APPROVED'`) | Yes — normal flow |
| APPROVED (originally unbound, `workflow_run_id IS NULL`) | none (no matching row) | none | `APPROVED` | `NULL` | Yes — via NULL→NULL match | N/A |

**Change from v1.5.6:** `PENDING` row changed from "preserved as PENDING" to "expired by trigger". All other rows unchanged.

---

## 4. Security rationale

### The gap being closed

After run deletion, a formerly-bound PENDING approval becomes `(PENDING, NULL)`. Because both a formerly-bound PENDING and an originally-unbound PENDING look identical in the database (both have `workflow_run_id=NULL`), no downstream check can distinguish them. If the approval-resolution system receives a request to approve this record — treating it as a valid unbound pending approval — it would succeed, producing `(APPROVED, NULL)`.

The `consume_atomic` NULL-to-NULL binding check (REQ-M2.5) would then match any invocation where `trusted_workflow_run_id=NULL`. The result: an MCP tool call authorized by a run that no longer exists and was never granted for unbound use.

### Why expiring PENDING is the correct fix

Expiring the PENDING approval at deletion time closes the attack before the promotion step. The approval becomes `(EXPIRED, NULL)`:
- `consume_atomic` rejects it (`status='APPROVED'` check, 0 rows).
- The resolution flow rejects it (resolution MUST only act on PENDING approvals; it rejects EXPIRED). No promotion is possible.

The trigger is database-enforced (not application code), so a direct SQL `DELETE FROM workflow_runs` cannot bypass it. The trigger fires on direct deletes and cascaded deletes. It runs in the same transaction as the DELETE, so a ROLLBACK restores the original PENDING status and binding.

### Why originally-unbound PENDING approvals are unaffected

The trigger's `WHERE workflow_run_id = OLD.id` clause never matches a row with `workflow_run_id IS NULL`. Originally-unbound approvals are therefore untouched, and REQ-M2.5 NULL-to-NULL semantics for them are preserved.

### Why the approval-resolution gate is the second line of defense

Even if a future implementation had a resolution flow that did not check status before resolving, the EXPIRED status set by the trigger would cause the resolution UPDATE (`WHERE status='PENDING'`) to match 0 rows — it would silently fail (or raise `ApprovalAlreadyResolvedError` if that error is wired). The trigger provides the primary guard; the resolution gate provides defense-in-depth.

---

## 5. Full SQLite verification output

Script: disposable in-memory Python script using standard-library `sqlite3` with `PRAGMA foreign_keys=ON`, the updated trigger (`status IN ('PENDING','APPROVED')`), and all five approval statuses. 23 assertions across 6 scenarios. Script created, run, and **deleted** (disposable artefact).

Environment: Python 3.x, SQLite standard library, Windows.

```
=== SCENARIO A: direct run deletion, all statuses + originally-unbound ===
[PASS] A1 PENDING->EXPIRED (trigger fires)
[PASS] A2 APPROVED->EXPIRED (trigger fires)
[PASS] A3 CONSUMED preserved, FK nulled
[PASS] A4 REJECTED preserved, FK nulled
[PASS] A5 EXPIRED preserved, FK nulled
[PASS] A6 originally-unbound APPROVED unaffected
[PASS] A7 run deleted
=== SCENARIO B: cascaded deletion ===
[PASS] B1 cascade: PENDING->EXPIRED
[PASS] B2 cascade: APPROVED->EXPIRED
[PASS] B3 cascade: CONSUMED unchanged
[PASS] B4 run deleted by cascade
=== SCENARIO C: promotion prevention (orphaned PENDING cannot be promoted) ===
[PASS] C1 PENDING->EXPIRED after run deletion
[PASS] C2 promotion attempt on EXPIRED: 0 rows updated
[PASS] C3 still EXPIRED after promotion attempt
=== SCENARIO D: rollback restores both PENDING and APPROVED ===
[PASS] D1 rollback restores PENDING status
[PASS] D2 rollback restores PENDING workflow_run_id
[PASS] D3 rollback restores APPROVED status
[PASS] D4 rollback restores APPROVED workflow_run_id
[PASS] D5 rollback restores the run
=== SCENARIO E: originally unbound approval unaffected ===
[PASS] E1 unbound PENDING unaffected by run deletion
[PASS] E2 unbound APPROVED unaffected by run deletion
=== SCENARIO F: consume_atomic rejects EXPIRED-after-deletion ===
[PASS] F1 consume_atomic on was-PENDING (now EXPIRED): 0 rows
[PASS] F2 consume_atomic on was-APPROVED (now EXPIRED): 0 rows
=== SUMMARY ===
23 passed, 0 failed out of 23
ALL ASSERTIONS PASS
```

**Scenario descriptions:**

- **A — direct deletion (7 assertions):** one run with approvals in all five statuses plus an originally-unbound APPROVED approval; delete the run. A1 confirms PENDING→EXPIRED (key new behavior). A2 confirms APPROVED→EXPIRED (unchanged). A3–A5 confirm CONSUMED/REJECTED/EXPIRED preserved with FK cleared. A6 confirms unbound APPROVED unaffected. A7 confirms run is deleted.
- **B — cascade (4 assertions):** deleting a workflow cascades to delete the run; trigger fires per run and expires PENDING and APPROVED. CONSUMED preserved. Run gone.
- **C — promotion prevention (3 assertions):** PENDING approval becomes EXPIRED after run deletion; a subsequent `UPDATE ... WHERE status='PENDING'` matches 0 rows — the promotion attack is blocked.
- **D — rollback (5 assertions):** DELETE (trigger fires, PENDING→EXPIRED and APPROVED→EXPIRED), then ROLLBACK; both approvals restored to original status with original `workflow_run_id` binding — trigger is fully transactional.
- **E — originally unbound (2 assertions):** unbound PENDING and APPROVED approvals untouched by any run deletion.
- **F — consume_atomic (2 assertions):** approvals expired by run deletion (both was-PENDING and was-APPROVED) produce 0 rows on a `WHERE status='APPROVED'` UPDATE — neither can be consumed.

---

## 6. Updated acceptance criteria

The following acceptance criteria are added or updated in `requirements.md` (REQ-M2.1):

| Criterion | Change |
|---|---|
| M2.1.3 | Trigger name updated to `trg_workflow_runs_before_delete_expire_mcp_approvals`; PENDING now also mentioned as expired |
| M2.1.7 | PENDING→EXPIRED on run deletion is now explicit; approval-resolution flow MUST only resolve PENDING; EXPIRED cannot be promoted |
| M2.1.8 | Updated: "PENDING or APPROVED" (was: "APPROVED") |
| M2.1.9 | Updated: PENDING is now expired, not preserved; test list updated |
| M2.1.11 | Updated: "was APPROVED or PENDING before run deletion" |
| M2.1.12 | Updated: "both PENDING and APPROVED approvals" restored by ROLLBACK |
| M2.1.13 | **NEW (W4-PA):** orphaned-PENDING cannot be promoted; promotion attempt updates 0 rows |
| Valid-status-transitions | `PENDING → EXPIRED` path now explicitly includes "OR run-deletion trigger — W4-PA" |
| Deletion binding invariant | Updated to cover PENDING and to name new trigger |
| Named tests block | Renamed, updated, added — total 10 tests |

---

## 7. Test changes

### Renamed (1)
- `test_workflow_run_deletion_allowed_with_pending_approval` → **`test_workflow_run_deletion_expires_pending_mcp_approval`**
  - Behavior changed from "PENDING preserved as PENDING, FK nulled" to "PENDING expired by trigger, FK nulled"
  - Rationale: a surviving PENDING with NULL FK is indistinguishable from an originally-unbound PENDING and exploitable via promotion; expiring it closes the attack

### Updated (2)
- `test_cascaded_deletion_handles_mcp_approvals` — description updated to include PENDING→EXPIRED on cascade alongside APPROVED→EXPIRED; CONSUMED/REJECTED/EXPIRED still preserved
- `test_trigger_rollback_restores_approval` — description updated to cover restoring both PENDING and APPROVED to their original status; was previously scoped to APPROVED only

### Added (1)
- **`test_orphaned_pending_approval_cannot_be_promoted`** (W4-PA)
  - After run deletion: PENDING approval is now EXPIRED with `workflow_run_id=NULL`
  - Attempt: `UPDATE mcp_approvals SET status='APPROVED' WHERE id=? AND status='PENDING'`
  - Assert: 0 rows updated; approval remains EXPIRED
  - Rationale: regression test for the orphaned-PENDING promotion attack; proves the trigger closes the gap at the DB level

### Test set counts
- v1.5.6 W4-FK: 9 deletion/binding tests
- v1.5.7 W4-FK+PA: **10** deletion/binding tests

---

## 8. Exact files modified

### `.kiro/specs/phase1-functional-orchestration/design.md`
- **Metadata** — version 1.5.6 → 1.5.7; status → "Wave 4 PENDING Approval Lifecycle Correction".
- **Version history** — added v1.5.7 (W4-PA) entry.
- _(Trigger DDL, FK table, deletion-invariant note, security rationale, MCPApproval model comment, Run-deletion trigger note — all already updated in a prior pass that partially applied W4-PA; no further changes needed to DDL/prose sections.)_

### `.kiro/specs/phase1-functional-orchestration/requirements.md`
- **Metadata** — version 1.5.6 → 1.5.7; status → "Wave 4 PENDING Approval Lifecycle Correction".
- **Version history** — added v1.5.7 (W4-PA) entry.
- **REQ-M2.1 description** — "every APPROVED" → "every PENDING and APPROVED" MCPApproval.
- **Valid-status-transitions** — `PENDING → EXPIRED` now explicitly includes run-deletion trigger path (W4-PA).
- **M2.1.3** — trigger name updated to `trg_workflow_runs_before_delete_expire_mcp_approvals`; PENDING included in trigger coverage.
- **M2.1.7** — extended: PENDING→EXPIRED on deletion explicit; approval-resolution MUST only resolve PENDING; EXPIRED cannot be promoted; covers both bypasses.
- **M2.1.8** — "PENDING or APPROVED" approvals expired; test list updated.
- **M2.1.9** — PENDING now expired, not preserved; test list updated (removed `test_workflow_run_deletion_allowed_with_pending_approval`).
- **M2.1.11** — "was APPROVED or PENDING before run deletion".
- **M2.1.12** — "both PENDING and APPROVED approvals" restored by ROLLBACK.
- **M2.1.13** — NEW: orphaned-PENDING-cannot-be-promoted acceptance criterion.
- **Deletion binding invariant** — updated to reference new trigger name and PENDING.
- **Named tests block** — 9 → 10 tests (1 renamed, 2 updated, 1 added).

### `.kiro/specs/phase1-functional-orchestration/tasks.md`
- **Metadata** — version 1.5.6 → 1.5.7; status → "Wave 4 PENDING Approval Lifecycle Correction".
- **Version history** — added v1.5.7 (W4-PA) entry.
- **Task I4 migration 006 `upgrade()` trigger DDL** — `AND status = 'APPROVED'` → `AND status IN ('PENDING', 'APPROVED')`; trigger renamed `trg_workflow_runs_before_delete_expire_mcp_approvals`; comment updated.
- **Task I4 migration 006 `downgrade()`** — DROP TRIGGER name updated to match.
- **Task I4 W4-FK named tests block** — 9 → 10 tests (renamed, 2 updated, 1 added).
- **Task I7 all-tests list** — `test_workflow_run_deletion_allowed_with_pending_approval` → `test_workflow_run_deletion_expires_pending_mcp_approval`; label updated to W4-PA; `test_cascaded_deletion_handles_mcp_approvals` label updated; `test_orphaned_pending_approval_cannot_be_promoted` added.

### `docs/planning/phase1-roadmap.md`
- **Metadata** — version 1.5.6 → 1.5.7; status → "Wave 4 PENDING Approval Lifecycle Correction Applied".
- **Version history** — added v1.5.7 (W4-PA) entry.
- **Wave 4 completion gate** — trigger name updated to `trg_workflow_runs_before_delete_expire_mcp_approvals` with `IN ('PENDING','APPROVED')`; test count 9 → 10; `test_workflow_run_deletion_allowed_with_pending_approval` → `test_workflow_run_deletion_expires_pending_mcp_approval`; `test_orphaned_pending_approval_cannot_be_promoted` added.

### Created
- `docs/reports/phase1-wave4-pending-approval-resolution.md` — this report.

### NOT modified
- `src/**`, `tests/**`, `alembic/**`, `.github/workflows/**`, `pyproject.toml`,
  `.kiro/specs/foundation-and-architecture/**`, migrations 001–005, `docs/reports/phase1-wave4-fk-final-resolution.md`. No Git commit, push, PR, or merge performed.

---

## 9. 11-check consistency results

| # | Check | Result |
|---|---|---|
| 1 | Trigger `WHERE` clause = `status IN ('PENDING', 'APPROVED')` in both `design.md` and `tasks.md` | **PASS** — DDL at §3.7a and migration 006 `upgrade()` both use `IN ('PENDING', 'APPROVED')` |
| 2 | Deletion rules table: PENDING→EXPIRED in all documents | **PASS** — requirements M2.1.7/M2.1.8/M2.1.9, design §3.7 FK table, design §3.7 deletion-invariant note, roadmap Wave 4 completion gate all state PENDING→EXPIRED |
| 3 | Test names updated consistently between `requirements.md` and `tasks.md` | **PASS** — `test_workflow_run_deletion_expires_pending_mcp_approval` and `test_orphaned_pending_approval_cannot_be_promoted` appear identically in requirements.md (REQ-M2.1 block), tasks.md (I4 block + I7 list), and roadmap completion gate |
| 4 | No claim that PENDING approvals survive deletion as PENDING | **PASS** — all active clauses state PENDING→EXPIRED; "trigger does not touch PENDING" language removed; surviving instances of the old test name are confined to "[RENAMED from ...]" annotations and version-history entries |
| 5 | `consume_atomic` still rejects EXPIRED | **PASS** — REQ-M2.2 step 3.f, M2.1.11, design §7.5; Scenario F verification (0 rows) |
| 6 | Originally unbound approvals still work (NULL→NULL match) | **PASS** — REQ-M2.5 unchanged; trigger `WHERE workflow_run_id = OLD.id` never matches NULL-FK rows; Scenario E verification; M2.1.10 unchanged |
| 7 | Migration 006 trigger DDL updated (`design.md` §3.7a and `tasks.md` migration 006) | **PASS** — both use `trg_workflow_runs_before_delete_expire_mcp_approvals` with `IN ('PENDING', 'APPROVED')`; `downgrade()` drop name matches |
| 8 | Version 1.5.7 consistent across all modified files | **PASS** — all four modified spec files (`requirements.md`, `design.md`, `tasks.md`, `phase1-roadmap.md`) show `**Version:** 1.5.7` |
| 9 | No Wave 5 functionality introduced | **PASS** — only W4-FK+PA trigger/test changes; Wave 5 `github_confirmations` migration 007 and GitHubConfirmation contract are untouched |
| 10 | No changes to migrations 001–005 | **PASS** — only the migration 006 *spec* (in `tasks.md`) updated; `alembic/versions/` directory and migrations 001–005 unmodified |
| 11 | Approval resolution rejects non-PENDING (EXPIRED cannot be promoted) | **PASS** — REQ-M2.1 M2.1.7: "the approval-resolution flow MUST only resolve approvals whose status is `PENDING`; it rejects any approval that is not `PENDING`"; M2.1.13: orphaned-PENDING-cannot-be-promoted acceptance criterion; design §3.7a Run-deletion trigger note: "An approval resolution flow MUST only resolve approvals whose status is `PENDING`; an `EXPIRED` approval ... cannot be resolved or promoted to `APPROVED`" |

**All 11 checks pass.**

---

## 10. Remaining blockers

None at the specification layer. The contract is internally consistent and verified.

**Implementation-time notes for Codex (not blockers):**
- Migration 006 `upgrade()` MUST use the new trigger name `trg_workflow_runs_before_delete_expire_mcp_approvals` and `status IN ('PENDING', 'APPROVED')` (DDL provided verbatim in design §3.7a and Task I4).
- Migration 006 `downgrade()` MUST drop `trg_workflow_runs_before_delete_expire_mcp_approvals` (not the old name).
- The approval-resolution service layer MUST reject any MCPApproval whose `status != 'PENDING'` before attempting to approve it; the EXPIRED check is defense-in-depth on top of the trigger.
- `PRAGMA foreign_keys=ON` (REQ-DB1.3) remains required at runtime for the `ON DELETE SET NULL` action to fire.
- The trigger fires on cascaded deletes under SQLite's default settings — no `PRAGMA recursive_triggers` required (verified in both v1.5.6 and this pass).

---

## 11. Final verdict

**READY FOR CODEX — PENDING APPROVAL CONTRACT RESOLVED.**

The v1.5.6 trigger expired only APPROVED approvals on run deletion, leaving a PENDING approval surviving as `(PENDING, NULL)` — indistinguishable from an originally-unbound PENDING and exploitable via promotion to APPROVED. The fix extends the BEFORE DELETE trigger to `status IN ('PENDING', 'APPROVED')`, expiring bound PENDING approvals before the FK is cleared. An EXPIRED approval cannot be consumed (`consume_atomic` rejects it) and cannot be promoted (the resolution flow only resolves PENDING). The contract is verified with real SQLite — 23/23 assertions pass across direct deletion, cascade, promotion prevention, rollback, unbound-unaffected, and consume_atomic rejection scenarios. All 11 cross-document consistency checks pass. Version 1.5.7 is consistent across all four modified spec files.
