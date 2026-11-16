# Phase 1 Wave 4 — Final FK Contract Resolution Report

**Date:** 2026-11-16
**Repository:** `J:\Android\GenAI\DevFlow-AI`
**Branch:** `feature/phase1-wave4-integration-execution`
**Specification version:** Phase 1 **v1.5.6** (corrected from v1.5.5 by this pass)
**Scope:** Specification correction only — no application code, migrations, alembic, CI, or `pyproject.toml` modified
**Author role:** Principal Database Architect, Application Security Engineer
**Mode:** SPECIFICATION CORRECTION ONLY

---

## 0. Executive summary

The v1.5.5 Wave 4 specification set `mcp_approvals.workflow_run_id` to
`ON DELETE RESTRICT` and simultaneously required that CONSUMED/PENDING/REJECTED/EXPIRED
approvals *permit* run deletion while only APPROVED approvals *block* it. SQLite's
`RESTRICT` is unconditional — it blocks deletion whenever ANY referencing row exists,
regardless of approval status — so the v1.5.5 acceptance criteria were
unimplementable as written: a run referenced by even one CONSUMED approval could not be
deleted, contradicting the stated rule.

This pass restores `ON DELETE SET NULL` and adds a **database-enforced BEFORE DELETE
trigger** on `workflow_runs` (`trg_workflow_runs_before_delete_expire_approved_mcp_approvals`)
that sets `status='EXPIRED'` on every APPROVED `MCPApproval` referencing the run **before**
the FK clears the reference. An APPROVED approval can therefore never become a valid
unbound (NULL) authorization: it is expired (rejected by `consume_atomic`'s
`status='APPROVED'` check) before `workflow_run_id` becomes NULL.

The contract was verified against real SQLite foreign-key enforcement (SQLite library
3.49.1, Python 3.12.10) — 17/17 assertions pass — including the critical ordering question
(trigger fires before the FK SET NULL action) and the cascade case (the trigger fires on
cascaded deletes under SQLite's default settings, no `recursive_triggers` PRAGMA needed).

**Final verdict: READY FOR CODEX — FK CONTRACT VERIFIED.**

One-paragraph summary: the v1.5.5 `ON DELETE RESTRICT` was an unconditional guard that
could not permit deletion for CONSUMED/PENDING/REJECTED/EXPIRED approvals, contradicting
its own acceptance criteria; the fix is `ON DELETE SET NULL` plus a BEFORE DELETE trigger
on `workflow_runs` that expires APPROVED approvals before the FK nulls the reference, so
no APPROVED approval can ever survive a run deletion as a valid NULL-bound authorization —
verified with 17 passing SQLite assertions (direct deletion, cascade, originally-unbound,
replay, rollback) using real FK enforcement.

---

## 1. Root cause

SQLite's `ON DELETE RESTRICT` is **unconditional**. Per the SQLite foreign-key
documentation, a `RESTRICT` action forbids deleting a parent row as long as *any* child
row references it; it does not inspect the child row's other columns. It cannot express
"block only if a referencing approval is APPROVED."

The v1.5.5 contract (W4-CR Conflict B) asserted all of:

- APPROVED approvals **block** workflow-run deletion (raise `IntegrityError`).
- CONSUMED approvals **permit** deletion.
- PENDING, REJECTED, EXPIRED approvals **permit** deletion.

These cannot all hold under `RESTRICT`: a single referencing row of any status — including
CONSUMED — makes the `DELETE FROM workflow_runs` raise `IntegrityError`. The schema was
therefore unable to satisfy its own stated acceptance criteria. The contradiction is in
the mechanism, not the policy: the *policy* (an APPROVED approval must not become a valid
unbound authorization after run deletion) is sound; `RESTRICT` is simply the wrong
mechanism to enforce it because it cannot be status-aware.

---

## 2. Evaluated options

| Option | Mechanism | DB-enforced? | Preserves history? | Status-aware? | Verdict |
|---|---|---|---|---|---|
| **A (chosen)** | `ON DELETE SET NULL` + BEFORE DELETE trigger on `workflow_runs` that expires APPROVED approvals before the FK clears the reference | Yes — trigger + FK run in the same transaction as the DELETE | Yes — SET NULL keeps the row (only clears the FK); trigger only changes `status` | Yes — `WHERE status='APPROVED'` filters; other statuses untouched | **Adopted** |
| B | `ON DELETE CASCADE` | Yes | No — deletes all referencing approvals, losing audit history | N/A | Rejected — violates the history-preservation requirement |
| C | Application-level pre-check (expire APPROVED, then delete) | No — a direct SQL DELETE bypasses it | Yes | Yes | Rejected — not database-enforced; the prompt requires DB enforcement |
| D | Add `originally_bound BOOLEAN` + `ON DELETE SET NULL`; `consume_atomic` rejects `originally_bound=TRUE AND workflow_run_id IS NULL` | Partially — the column is DB, the rejection is application-level | Yes | Indirect | Rejected — the rejection is application-level, not DB-enforced; the trigger (A) achieves the same guarantee purely in the DB |

**Why A over D:** both A and D preserve history and prevent escalation, but A owns the
invariant in the database (the trigger fires on every DELETE, including a direct SQL
DELETE and cascaded deletes, and is transactional with the DELETE). D's enforcement point
(`consume_atomic` rejecting `originally_bound=TRUE AND workflow_run_id IS NULL`) is
application code, which a direct SQL path can bypass; it also requires an extra schema
column and a changed consumption rule. A is strictly stronger and needs no new column.

**Why A over the v1.5.5 RESTRICT:** RESTRICT cannot be status-aware, so it cannot permit
deletion for CONSUMED/PENDING/REJECTED/EXPIRED approvals. A's trigger is status-aware
(`WHERE status='APPROVED'`), and the SET NULL FK preserves every approval row. The net
effect matches the *intended* v1.5.5 policy exactly, with a mechanism that actually
implements it.

---

## 3. Final schema

**Foreign key:**
```sql
workflow_run_id INTEGER REFERENCES workflow_runs(id) ON DELETE SET NULL
```

**Trigger (created by migration 006 `upgrade()`, dropped by its `downgrade()`):**
a BEFORE DELETE trigger on `workflow_runs` that expires APPROVED approvals before the
FK action clears the reference.

**Model (`MCPApproval.workflow_run_id`):**
```python
workflow_run_id: Mapped[int | None] = mapped_column(
    Integer, ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True
)
```

**Prerequisites:** `PRAGMA foreign_keys=ON` (REQ-DB1.3 / ADR-0012) is required for the
`ON DELETE SET NULL` action to fire. The trigger is a plain SQL DDL trigger that fires on
any DELETE of a `workflow_runs` row (direct or cascaded); it does not depend on the
foreign-keys PRAGMA. Verified: under SQLite 3.49.1 the trigger fires on cascaded deletes
with the default settings — no `PRAGMA recursive_triggers` is required.

---

## 4. Full trigger SQL DDL

```sql
CREATE TRIGGER trg_workflow_runs_before_delete_expire_approved_mcp_approvals
BEFORE DELETE ON workflow_runs
FOR EACH ROW
BEGIN
    UPDATE mcp_approvals
       SET status = 'EXPIRED'
     WHERE workflow_run_id = OLD.id
       AND status = 'APPROVED';
END;
```

Migration 006 downgrade:
```sql
DROP TRIGGER IF EXISTS trg_workflow_runs_before_delete_expire_approved_mcp_approvals;
```

The trigger fires **before** the row is removed and **before** the `ON DELETE SET NULL`
FK action runs (verified — Scenario A). At trigger time `OLD.id` is still the live run id,
so `WHERE workflow_run_id = OLD.id AND status = 'APPROVED'` correctly targets only the
APPROVED approvals bound to that run. Only `status` is changed; `workflow_run_id` is left
intact for the subsequent SET NULL action to clear.

---

## 5. Deletion rules (approval status → behavior after run deletion)

| Approval status before run deletion | Trigger action | FK SET NULL action | Final status | Final `workflow_run_id` | Consumable after? | History |
|---|---|---|---|---|---|---|
| APPROVED (originally bound) | `status` → `EXPIRED` | `workflow_run_id` → `NULL` | `EXPIRED` | `NULL` | **No** — `consume_atomic` requires `status='APPROVED'` (0 rows) | Preserved |
| CONSUMED (originally bound) | none (`status != 'APPROVED'`) | `workflow_run_id` → `NULL` | `CONSUMED` | `NULL` | No (already consumed) | Preserved |
| PENDING (originally bound) | none | `workflow_run_id` → `NULL` | `PENDING` | `NULL` | No (`status != 'APPROVED'`) | Preserved |
| REJECTED (originally bound) | none | `workflow_run_id` → `NULL` | `REJECTED` | `NULL` | No (`status != 'APPROVED'`) | Preserved |
| EXPIRED (originally bound) | none | `workflow_run_id` → `NULL` | `EXPIRED` | `NULL` | No (`status != 'APPROVED'`) | Preserved |
| APPROVED (originally unbound, `workflow_run_id IS NULL` at creation) | none (`WHERE workflow_run_id = OLD.id` matches no rows) | none (no reference to clear) | `APPROVED` | `NULL` | Yes — unbound invocation only, via REQ-M2.5 NULL→NULL semantics | Preserved |

**Run deletion is permitted for every approval status.** APPROVED approvals are expired
(not blocked); all others are preserved with the FK cleared. The run is always deleted.

---

## 6. Security rationale — how the NULL→NULL bypass is prevented

**The bypass being defended against:** `consume_atomic`'s binding check (REQ-M2.2 step 3.e
/ REQ-M2.5) is NULL-safe — an approval with `workflow_run_id = NULL` authorizes an
invocation with `trusted_workflow_run_id = NULL` (NULL-to-NULL match). If an APPROVED
approval originally bound to run X had its `workflow_run_id` cleared to NULL by a run
deletion, a later unbound invocation would satisfy the NULL-to-NULL match and the approval
would authorize an action it was never granted for — a privilege-escalation bypass of the
run binding. (This is exactly what the v1.5.4 `ON DELETE SET NULL` allowed, which v1.5.5
tried to fix with RESTRICT.)

**Why v1.5.5 RESTRICT did not actually fix it correctly:** RESTRICT prevents the binding
from being cleared (good for the APPROVED case), but it is unconditional, so it also blocks
deletion for CONSUMED/PENDING/REJECTED/EXPIRED approvals — contradicting the policy that
those statuses permit deletion. RESTRICT could not satisfy the full contract.

**How Option A prevents it:** the BEFORE DELETE trigger sets `status='EXPIRED'` on every
APPROVED approval referencing the run **before** the FK SET NULL action clears
`workflow_run_id`. After deletion the approval is `(EXPIRED, NULL)`. The NULL-to-NULL
binding check at the service layer would pass (both NULL), but `consume_atomic`'s
in-transaction `UPDATE ... WHERE status='APPROVED' ...` matches 0 rows, so consumption
fails (`ConsumedError`). The approval is therefore not executable. The bypass is closed
at the consumption gate, not at the binding gate.

**Why the invariant is owned by the trigger, not application code:** a direct SQL
`DELETE FROM workflow_runs` bypasses any application-level pre-check (Option C/D), but it
cannot bypass a DDL trigger — the trigger fires on every DELETE, including cascaded
deletes (Scenario B), and is transactional with the DELETE (Scenario D: ROLLBACK restores
the approval). The FK SET NULL provides the history-preserving cleanup; the trigger
provides the security invariant.

**Cascade safety:** deleting a `workflow` cascades to delete each `workflow_run`
(`WorkflowRun.workflow_id ... ON DELETE CASCADE`). For each run, the BEFORE DELETE trigger
fires (verified — fires under SQLite default settings, no `recursive_triggers` needed) and
expires APPROVED approvals bound to that run, then SET NULL clears the FK. Deleting a
project only sets `Workflow.project_id` to NULL (Scenario E); it does not reach the runs,
so it never fires the trigger and never spuriously expires an approval.

---

## 7. Executable SQLite verification evidence

A disposable Python script using the standard-library `sqlite3` module created an
in-memory database with `PRAGMA foreign_keys=ON`, built `projects`, `workflows`,
`workflow_runs`, and `mcp_approvals` with the proposed FK (`ON DELETE SET NULL`) and the
BEFORE DELETE trigger, then ran five scenarios (17 assertions). Environment: Python
3.12.10, SQLite library 3.49.1, sqlite3 module 2.6.0. The script was deleted after the run
(disposable artefact). Full output:

```
=== SCENARIO A: direct run deletion, all statuses + originally-unbound ===
[PASS] A1 APPROVED->EXPIRED (trigger fires BEFORE SET NULL): status='EXPIRED' workflow_run_id=None (expected status='EXPIRED', fk=None)
[PASS] A1b APPROVED approval NOT deleted: row still present
[PASS] A2 CONSUMED preserved, FK nulled: status='CONSUMED' workflow_run_id=None
[PASS] A3 PENDING preserved, FK nulled: status='PENDING' workflow_run_id=None
[PASS] A4 REJECTED preserved, FK nulled: status='REJECTED' workflow_run_id=None
[PASS] A5 EXPIRED preserved, FK nulled: status='EXPIRED' workflow_run_id=None
[PASS] A6 originally-unbound APPROVED unaffected: status='APPROVED' workflow_run_id=None (expected status='APPROVED', fk=None)
[PASS] A7 run deleted: rows remaining=0
=== SCENARIO C: replay after deletion (EXPIRED cannot be consumed) ===
[PASS] C1 consume_atomic rejects EXPIRED (rowcount==0): rowcount=0
[PASS] C2 EXPIRED approval stays EXPIRED, not CONSUMED: status='EXPIRED' workflow_run_id=None
=== SCENARIO D: rollback restores approval (trigger is transactional) ===
[PASS] D1 rollback restores APPROVED status: status='APPROVED'
[PASS] D2 rollback restores workflow_run_id binding: workflow_run_id=1
[PASS] D3 rollback restores the run: rows remaining=1
=== SCENARIO E: project delete does NOT reach runs (no spurious expiry) ===
[PASS] E1 project delete leaves approval APPROVED + bound: status='APPROVED' workflow_run_id=1
[PASS] E2 project delete sets workflow.project_id NULL, workflow+run survive: workflow.project_id=None run_present=1
=== SCENARIO B: cascaded deletion (workflow delete -> run cascade -> trigger)
[PASS] B [recursive_triggers=OFF(default)] cascade expires APPROVED + nulls FK: status='EXPIRED' workflow_run_id=None run_gone=0 wf_gone=0
[PASS] B [recursive_triggers=ON] cascade expires APPROVED + nulls FK: status='EXPIRED' workflow_run_id=None run_gone=0 wf_gone=0
=== SUMMARY ===
17 passed, 0 failed out of 17
```

**Scenarios:**
- **A — direct deletion (8 assertions):** one run with an approval in each status
  (APPROVED, CONSUMED, PENDING, REJECTED, EXPIRED) plus an originally-unbound APPROVED
  approval; delete the run. A1 confirms the critical ordering — the APPROVED approval
  becomes `EXPIRED` (not left `APPROVED`-with-`NULL`-FK), proving the trigger fires before
  the SET NULL action. A2–A5 confirm the other statuses are preserved (status unchanged,
  FK nulled). A6 confirms the originally-unbound APPROVED approval is untouched. A7
  confirms the run is deleted (deletion is permitted for every status).
- **C — replay (2 assertions):** the approval that was APPROVED before deletion is now
  `EXPIRED` with `NULL` FK; a `consume_atomic`-shaped UPDATE (`WHERE status='APPROVED'`)
  matches 0 rows — it cannot be consumed even via an unbound invocation.
- **D — rollback (3 assertions):** `DELETE` (trigger fires → `EXPIRED`) then `ROLLBACK`
  restores the approval to `APPROVED` with its original `workflow_run_id=1` and the run
  survives — the trigger is transactional.
- **E — project delete (2 assertions):** deleting a project only nulls
  `Workflow.project_id`; the run and its APPROVED approval survive unchanged (no spurious
  expiry; project-delete does not reach runs).
- **B — cascade (2 assertions):** deleting a `workflow` cascades to delete the run; the
  trigger fires per run and expires the APPROVED approval (then SET NULL clears the FK).
  Verified both with `recursive_triggers=OFF` (the SQLite default) and `ON` — the trigger
  fires on the cascaded delete under default settings, so **no `PRAGMA recursive_triggers`
  is required** for the implementer.

---

## 8. Test changes (renamed, kept, added)

**Renamed (1) — behavior changed from block to expire:**
- `test_workflow_run_deletion_blocked_with_approved_mcp_approval` →
  `test_workflow_run_deletion_expires_approved_mcp_approval`. v1.5.5 asserted an
  `IntegrityError` (RESTRICT blocked deletion); the new contract does not raise — the
  trigger expires the APPROVED approval and SET NULL clears the FK, then verifies the
  approval is `EXPIRED`/`NULL` and still present. Rationale: RESTRICT was unconditional and
  could not satisfy the per-status deletion criteria; the trigger is status-aware.

**Kept (4) — rationale updated from "RESTRICT prevents clearing" to "trigger expires before NULL":**
- `test_workflow_run_deletion_allowed_after_approval_consumed` (CONSUMED preserved, FK nulled)
- `test_workflow_run_deletion_allowed_with_pending_approval` (PENDING preserved, FK nulled)
- `test_null_to_null_match_rejected_for_originally_bound_approval` (originally-bound approval expired by the trigger before the FK is nulled, so a later unbound invocation fails `consume_atomic`'s `status='APPROVED'` check rather than matching NULL-to-NULL)
- `test_cascaded_deletion_handles_mcp_approvals` (workflow cascade → run delete → trigger expires APPROVED; CONSUMED/PENDING proceed untouched)

**Added (4):**
- `test_workflow_run_deletion_preserves_consumed_approval` — after deleting a run with a CONSUMED approval, the row still exists with `status='CONSUMED'` and `workflow_run_id=NULL` (history preserved, not deleted).
- `test_workflow_run_deletion_preserves_rejected_approval` — same for a REJECTED approval.
- `test_expired_approval_after_deletion_cannot_be_consumed` — an approval that was APPROVED before run deletion (now `EXPIRED`, `workflow_run_id=NULL`) cannot be consumed; `consume_atomic` updates 0 rows even for an unbound invocation.
- `test_trigger_rollback_restores_approval` — `DELETE` (trigger fires, approval→`EXPIRED`) then `ROLLBACK` restores the approval to `APPROVED` with its original `workflow_run_id` binding intact (the trigger is transactional).

The W4 deletion/binding named-test set is now **9** tests (was 5), present consistently in
`requirements.md` (REQ-M2.1 block), `tasks.md` (Task I4 named-tests block + Task I7
all-test-cases list), and the `phase1-roadmap.md` Wave 4 completion gate.

---

## 9. Exact files modified

### `.kiro/specs/phase1-functional-orchestration/requirements.md`
- **Metadata** — version 1.5.5 → 1.5.6; status → "Wave 4 Final FK Contract Correction".
- **Version history** — added v1.5.6 (W4-FK) entry documenting the RESTRICT→SET NULL+trigger reversal.
- **REQ-M2.1 description** — `workflow_run_id` FK `ON DELETE RESTRICT` → `ON DELETE SET NULL` + BEFORE DELETE trigger.
- **M2.1.3** — rewritten: SET NULL + trigger; explains RESTRICT is unconditional; `PRAGMA foreign_keys=ON` required for SET NULL.
- **M2.1.7** — rewritten (W4-FK): SET NULL + trigger; deletion permitted for every status; APPROVED expired by trigger; EXPIRED rejected by `consume_atomic`.
- **M2.1.8–M2.1.12** — added: the five new acceptance criteria (APPROVED→EXPIRED; CONSUMED/PENDING/REJECTED/EXPIRED preserved; originally-unbound unaffected; EXPIRED-not-consumable; trigger transactional/rollback).
- **Deletion binding invariant paragraph** — rewritten (W4-FK): invariant owned by the trigger; DB-enforced; originally-unbound unaffected.
- **Named deletion/binding tests block** — 5 → 9 tests (1 renamed, 4 kept with updated rationale, 4 added).

### `.kiro/specs/phase1-functional-orchestration/design.md`
- **Metadata** — version 1.5.5 → 1.5.6; status → "Wave 4 Final FK Contract Correction".
- **Version history** — added v1.5.6 (W4-FK) entry.
- **§3.7a SQL DDL** — `workflow_run_id ... ON DELETE RESTRICT` → `ON DELETE SET NULL`; added the trigger DDL after the index statements.
- **§3.7a MCPApproval model** — `ondelete="RESTRICT"` → `"SET NULL"`; comment updated to "SET NULL + BEFORE DELETE trigger (W4-FK)".
- **§3.7 FK behaviors table** — `MCPApproval.workflow_run_id` row: `RESTRICT` → `SET NULL (W4-FK)`; effect rewritten (trigger expires APPROVED, then SET NULL clears FK).
- **§3.7 deletion-invariant note** — rewritten (W4-FK): SET NULL + trigger; RESTRICT is unconditional; trigger invalidates before FK clears; security rationale paragraph added.
- **§7.5 MCPApproval model notes comment** — `ON DELETE RESTRICT` → `ON DELETE SET NULL` + trigger.
- **§7.5 consume_atomic** — added "EXPIRED rejection at consume_atomic (W4-FK)" note: an approval expired by the trigger is rejected at the consumption gate even for an unbound invocation.

### `.kiro/specs/phase1-functional-orchestration/tasks.md`
- **Metadata** — version 1.5.5 → 1.5.6; status → "Wave 4 Final FK Contract Correction".
- **Version history** — added v1.5.6 (W4-FK) entry.
- **Task I4 migration 006 `upgrade()`** — `sa.ForeignKey("workflow_runs.id", ondelete="RESTRICT")` → `"SET NULL"`; added `op.execute("""CREATE TRIGGER ... """)` to create the trigger.
- **Task I4 migration 006 `downgrade()`** — added `op.execute("DROP TRIGGER IF EXISTS ...")` before dropping indexes/table.
- **Task I4 named deletion/binding tests block** — 5 → 9 tests (1 renamed, 4 kept with updated rationale, 4 added).
- **Task I7 all-test-cases list** — the 5 W4-CR Conflict B entries replaced with the 9 W4-FK entries.

### `docs/planning/phase1-roadmap.md`
- **Metadata** — version 1.5.5 → 1.5.6; status → "Wave 4 Final FK Contract Correction Applied".
- **Version history** — added v1.5.6 (W4-FK) entry.
- **Wave 4 completion gate** — `mcp_approvals.workflow_run_id ON DELETE RESTRICT` → `ON DELETE SET NULL` + the BEFORE DELETE trigger; the "5 W4-CR Conflict B deletion/binding tests" → the "9 W4-FK deletion/binding tests" (full list with the renamed + added names).

### Created
- `docs/reports/phase1-wave4-fk-final-resolution.md` — this report.

### NOT modified (per strict boundaries)
- `src/**`, `tests/**`, `alembic/**`, `.github/workflows/**`, `pyproject.toml`,
  `.kiro/specs/foundation-and-architecture/**`, migrations 001–005, and the Wave 5
  `github_confirmations` migration 007 (`workflow_run_id ON DELETE SET NULL` — out of
  scope, intentionally retained). No Git commit, push, PR, or merge. All pre-existing
  Codex working-tree changes (`.env.example`, `src/devflow_api/adapters/exceptions.py`,
  `src/devflow_core/config.py`, `src/devflow_api/adapters/live/`,
  `tests/unit/test_live_adapters.py`, and the untracked reports) were preserved
  untouched. The disposable verification script was created, run, and deleted.

---

## 10. Cross-document consistency verification

1. **No `ON DELETE RESTRICT` for `mcp_approvals.workflow_run_id` in the active contract** — PASS. Every active clause (§3.7a SQL DDL, §3.7a model, §3.7 FK table, §3.7 deletion-invariant note, §7.5 model comment, REQ-M2.1 description, M2.1.3, M2.1.7, migration 006 SQL, roadmap completion gate) specifies `SET NULL` + trigger. Remaining `RESTRICT` strings are confined to (a) historical v1.5.5 version-history entries (accurate audit trail), (b) v1.5.6 version-history entries that describe the reversal, and (c) the W4-FK deletion-invariant note that explicitly says "NOT `ON DELETE RESTRICT`" and explains RESTRICT is unconditional.
2. **Trigger DDL consistent between `design.md` and `tasks.md` migration 006** — PASS. Identical trigger name (`trg_workflow_runs_before_delete_expire_approved_mcp_approvals`), event (`BEFORE DELETE ON workflow_runs`), and body (`UPDATE mcp_approvals SET status='EXPIRED' WHERE workflow_run_id=OLD.id AND status='APPROVED'`). `tasks.md` `downgrade()` drops it with `DROP TRIGGER IF EXISTS`.
3. **All test names updated consistently between `requirements.md` and `tasks.md`** — PASS. The 9-test set (1 renamed, 4 kept, 4 added) is identical in `requirements.md` (REQ-M2.1 block), `tasks.md` (Task I4 block + Task I7 list), and the roadmap completion gate. No active block retains the old name as a *current* test name (it survives only in "[RENAMED from …]" annotations and version-history rename documentation).
4. **No claim that `RESTRICT` can filter by status** — PASS. The W4-FK note and the v1.5.6 history entries explicitly state RESTRICT is unconditional and cannot filter by status. No active clause asserts otherwise.
5. **`consume_atomic` still rejects EXPIRED approvals (now covers trigger-expired)** — PASS. §7.5 "EXPIRED rejection at consume_atomic (W4-FK)" note + M2.1.11 + M2.2 step 3.e (`status = APPROVED AND expires_at > now AND consumed_at IS NULL`). Verified by Scenario C (0 rows).
6. **Originally unbound approvals still work (NULL→NULL match for approvals always NULL)** — PASS. REQ-M2.5 unchanged; M2.1.10; §7.5 note; the trigger's `WHERE workflow_run_id = OLD.id` never matches a NULL-bound row. Verified by Scenario A6 and E.
7. **Migration 006 FK definition updated** — PASS. `tasks.md` migration 006 `ondelete="SET NULL"` + trigger in `upgrade()`/`downgrade()`; `design.md` §3.7a SQL + model + FK table + note all consistent. Migrations 001–005 unchanged (alembic versions dir still lists only 001–005).
8. **Version 1.5.6 consistent** — PASS. All four modified files show `**Version:** 1.5.6`, `**Last Updated:** 2026-11-16`, and a v1.5.6 (W4-FK) version-history entry.
9. **No Wave 5 functionality introduced** — PASS. Only W4-FK FK/trigger/test changes; the Wave 5 `github_confirmations` migration 007 and GitHubConfirmation contract are untouched.
10. **No changes to migrations 001–005** — PASS. Only the migration 006 *spec* (in `tasks.md`) and the §3.7a DDL/model (in `design.md`) were edited. The `alembic/versions/` directory still contains only 001–005; no migration file was created or modified (migration 006 is a Wave 4 deliverable to be authored by Codex).

---

## 11. Remaining blockers

None at the specification layer. The contract is internally consistent and verified.

Implementation-time notes for Codex (not blockers):
- `PRAGMA foreign_keys=ON` (REQ-DB1.3 / ADR-0012) MUST be active at runtime for the
  `ON DELETE SET NULL` action to fire. This is already mandated; the implementer adds it
  to the `'connect'` handler in `src/devflow_api/database.py` (and `alembic/env.py`).
- Migration 006 `upgrade()` MUST create the trigger (DDL provided verbatim in §3.7a and
  Task I4); `downgrade()` MUST drop it before dropping `mcp_approvals`.
- The trigger fires on cascaded deletes under SQLite's default settings — no
  `PRAGMA recursive_triggers` is required (verified, Scenario B with both settings).
- The `alembic/env.py` `'connect'` handler is out of spec-correction scope and will be
  updated by the implementer alongside `src/devflow_api/database.py`.

---

## 12. Final verdict

**READY FOR CODEX — FK CONTRACT VERIFIED.**

The v1.5.5 RESTRICT contradiction is resolved: `ON DELETE SET NULL` + a database-enforced
BEFORE DELETE trigger on `workflow_runs` satisfies the full deletion policy (APPROVED
expired; CONSUMED/PENDING/REJECTED/EXPIRED preserved and permitted to delete; originally
unbound unaffected) while closing the NULL→NULL authorization bypass at the consumption
gate. Verified with real SQLite foreign-key enforcement — 17/17 assertions pass.
