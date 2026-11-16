# DevFlow AI — Phase 1 Wave 5 Specification Readiness Report

**Version:** 1.0
**Date:** 2026-11-16
**Branch:** feature/phase1-wave5-github-orchestration
**Base commit:** bceb9bab4328fe4ca5ed068a25fa9f541841f0ff
**Specification version after corrections:** v1.5.8
**Verdict:** WAVE 5 SPECIFICATIONS READY — PROCEED TO CODEX

---

## 1. Wave 4 Merge Verification

| Check | Result |
|---|---|
| PR #12 | MERGED |
| PR target branch | `develop` |
| Merge commit SHA | `bceb9bab4328fe4ca5ed068a25fa9f541841f0ff` |
| `origin/develop` contains Wave 4 changes | ✓ |
| Migration `006_add_mcp_approvals.py` present | ✓ |
| Specification v1.5.7 confirmed at merge | ✓ |
| Wave 4 I1–I7 deliverables present in `origin/develop` | ✓ (per prior merge report) |

Wave 4 merged cleanly as PR #12. The base commit `bceb9ba` is confirmed in `origin/develop` and is the starting point for the Wave 5 feature branch.

---

## 2. Wave 5 Branch and Base SHA

| Item | Value |
|---|---|
| Branch | `feature/phase1-wave5-github-orchestration` |
| Base SHA | `bceb9bab4328fe4ca5ed068a25fa9f541841f0ff` |
| Branch created from | `origin/develop` at Wave 4 merge commit |
| Branch exists locally | ✓ (created in prior step) |
| Push / PR status | None — not pushed, no PR opened |

---

## 3. G1–G5 Scope Summary

Wave 5 delivers GitHub Workflow Orchestration in five tasks. No autonomous coding, deployment, or automatic PR merging is in scope.

| Task | Description | Key deliverables |
|---|---|---|
| G1 | `RepositoryConfig` model + `RepositoryConfigRepository`; `GitHubConfirmation` model + `GitHubConfirmationRepository`; migration 007 | `models/repository.py`, `models/github_confirmation.py`, `repositories/repository_config.py`, `repositories/github_confirmation.py`, `007_add_github_confirmations.py` |
| G2 | `RepositoryService` + `GitHubAdapter` extension (branch/PR/CI endpoints) | `services/repository.py`, `adapters/live/github.py` (extended), confirmation exception classes |
| G3 | Repositories router (`/api/v1/repositories` + `/api/v1/github-confirmations`) | `routers/repositories.py`, `schemas/repository.py` |
| G4 | Settings page: GitHub status | `pages/10_Settings.py` (extended), `api_client.py` (extended) |
| G5 | Tests: Wave 5 + final CI verification | All test files, regenerated `docs/openapi.json` |

**Preserved scope (explicitly not in Wave 5):**
- No automatic PR merging (no `/merge` endpoint anywhere)
- No boolean-only authorization (confirmed: bool rejected; `GitHubConfirmation` record required)
- No Wave 5 application code in this spec-correction step
- No Phase 2 capabilities (no autonomous AI step execution)

---

## 4. GitHubConfirmation Security Design

### 4.1 Status Field (W5-GC)

The `github_confirmations` table now has a `status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED','EXPIRED','USED'))` column.

| Status | Meaning | Set by |
|---|---|---|
| `ISSUED` | Confirmation created; not yet consumed or expired | `issue_confirmation` |
| `EXPIRED` | ISSUED confirmation's bound run was deleted; cannot be consumed | BEFORE DELETE trigger on `workflow_runs` |
| `USED` | Atomically consumed on first use | `consume_atomic` |

**Deletion lifecycle:**

| Status before run deletion | Status after run deletion |
|---|---|
| `ISSUED` | `EXPIRED` (trigger fires before FK SET NULL) |
| `USED` | `USED` (trigger does not touch USED); FK cleared to NULL |
| `EXPIRED` | `EXPIRED` (trigger only updates `status='ISSUED'`); FK cleared to NULL |
| Unbound (`workflow_run_id IS NULL`) | Unaffected |

### 4.2 BEFORE DELETE Trigger

```sql
CREATE TRIGGER trg_workflow_runs_before_delete_expire_github_confirmations
BEFORE DELETE ON workflow_runs
FOR EACH ROW
BEGIN
    UPDATE github_confirmations SET status = 'EXPIRED'
    WHERE workflow_run_id = OLD.id AND status = 'ISSUED';
END;
```

**Security rationale:** Without this trigger, an ISSUED confirmation bound to run X would survive run deletion as `(ISSUED, workflow_run_id=NULL)`. Since `workflow_run_id=NULL` is also the value for an originally-unbound confirmation, a future invocation with `trusted_workflow_run_id=None` could match it via NULL-to-NULL. The trigger prevents this by expiring the confirmation before the FK is cleared. This is the same pattern used for `mcp_approvals` in W4-PA.

### 4.3 consume_atomic Contract

`GitHubConfirmationRepository.consume_atomic` uses:
```sql
UPDATE github_confirmations
SET used_at = ?, status = 'USED'
WHERE id = ? AND status = 'ISSUED' AND expires_at > ?
```
- rowcount == 1 required; 0 rows → `ConfirmationAlreadyUsedError`
- This rejects both already-USED (`status='USED'`) and EXPIRED-by-trigger (`status='EXPIRED'`) confirmations
- `BEGIN IMMEDIATE` transaction prevents TOCTOU between SELECT and UPDATE

---

## 5. Migration 007 Contract (Full DDL Spec)

### 5.1 Revision Chain

```
001_create_initial_tables (Phase 0)
  └── 002_add_project_tags_column  (Wave 1)
        └── 003_add_workflow_tables  (Wave 2)
              └── 004_add_approval_audit_tables  (Wave 2)
                    └── 005_add_repository_tables  (Wave 2)
                          └── 006_add_mcp_approvals  (Wave 4)
                                └── 007_add_github_confirmations  (Wave 5) ← HEAD
```

### 5.2 Required revision header

```python
revision = "007_add_github_confirmations"
down_revision = "006_add_mcp_approvals"
```

### 5.3 Full upgrade() DDL

```python
def upgrade() -> None:
    op.create_table(
        "github_confirmations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("repo_full_name", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("parameters_hash", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("workflow_run_id", sa.Integer(),
                  sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.Text(), server_default="ISSUED", nullable=False),
        sa.CheckConstraint("operation IN ('branch_create', 'pr_create')",
                           name="ck_github_confirmations_operation"),
        sa.CheckConstraint("status IN ('ISSUED','EXPIRED','USED')",
                           name="ck_github_confirmations_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_github_confirmations_expires", "github_confirmations", ["expires_at"])
    op.create_index("idx_github_confirmations_actor", "github_confirmations", ["actor_id"])
    op.execute("""
CREATE TRIGGER trg_workflow_runs_before_delete_expire_github_confirmations
BEFORE DELETE ON workflow_runs
FOR EACH ROW
BEGIN
    UPDATE github_confirmations SET status = 'EXPIRED'
    WHERE workflow_run_id = OLD.id AND status = 'ISSUED';
END;
""")

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_workflow_runs_before_delete_expire_github_confirmations")
    op.drop_index("idx_github_confirmations_actor", table_name="github_confirmations")
    op.drop_index("idx_github_confirmations_expires", table_name="github_confirmations")
    op.drop_table("github_confirmations")
```

### 5.4 Foreign key behavior

- `workflow_run_id REFERENCES workflow_runs(id) ON DELETE SET NULL`
- BEFORE DELETE trigger fires first (expires ISSUED confirmations), then SET NULL clears the FK
- Requires `PRAGMA foreign_keys=ON` for SET NULL to fire (already registered in `database.py` connect event)

### 5.5 Chain verification

| Revision | down_revision | Status |
|---|---|---|
| `007_add_github_confirmations` | `006_add_mcp_approvals` | ✓ correct |
| `006_add_mcp_approvals` | `005_add_repository_tables` | ✓ verified in migration 006 file |

---

## 6. Execution Failure and Reconciliation Semantics

### 6.1 Three GitHub execution outcomes (W5-GC)

| Outcome | Definition | Action |
|---|---|---|
| `SUCCEEDED` | GitHub API returned 2xx; operation confirmed complete | Log `github_action_executed`; confirmation stays USED |
| `FAILED` | GitHub API returned 4xx/5xx; operation definitively did not execute | Log `github_action_failed`; confirmation stays USED; new confirmation required for retry |
| `INDETERMINATE` | Timeout or network error; operation may or may not have executed | Log `github_action_failed` with `reason=INDETERMINATE`; do NOT auto-retry; do NOT restore confirmation |

### 6.2 Rules

1. Confirmation MUST be consumed (`status→USED`, `used_at` set) **before** the GitHub API call.
2. After INDETERMINATE: record `github_action_failed` audit event with `reason=INDETERMINATE`; do NOT auto-retry; do NOT restore the confirmation.
3. After FAILED: same — confirmation stays USED; new confirmation required for retry.
4. Exact-once caveat: *"DevFlow AI cannot guarantee exactly-once execution of external GitHub operations. If the API call result is unknown, the user must verify GitHub state before issuing a new confirmation."*

### 6.3 Reconciliation flow

```
User: POST /api/v1/github-confirmations → receives confirmation_id
User: POST /api/v1/repositories/{id}/branches (confirmation_id=...)
  → RepositoryService: load → validate → consume_atomic (status→USED) → GitHubAdapter.create_branch
  → SUCCEEDED: log github_action_executed → return 201
  → FAILED: log github_action_failed → return 502
  → INDETERMINATE: log github_action_failed(reason=INDETERMINATE) → return 502
  → User checks GitHub manually → issues new confirmation → retries
```

---

## 7. Required Negative Tests

All tests listed below are mandated by the spec (REQ-G1.4, design §8.2, tasks G5).

### 7.1 Original six GitHubConfirmation tests (F2 / REQ-G1.4.9–G1.4.14)

1. `test_github_confirmation_persisted_to_db`
2. `test_confirmation_expires_after_ttl`
3. `test_replay_rejected_after_use`
4. `test_parameter_mismatch_rejected`
5. `test_concurrent_consumption_safe`
6. `test_recovery_after_github_api_failure`

### 7.2 F9 failure semantics test

7. `test_github_confirmation_not_restored_after_api_failure`

### 7.3 W5-GC security negative tests (10 tests — REQ-G1.4.15–G1.4.24)

8. `test_boolean_flag_alone_insufficient_for_github_action` — boolean `confirmed: true` without `confirmation_id` → HTTP 422
9. `test_expired_github_confirmation_rejected` — `expires_at` in past → HTTP 422, `CONFIRMATION_EXPIRED`
10. `test_used_github_confirmation_rejected_on_replay` — re-submit used `confirmation_id` → HTTP 409
11. `test_mismatched_operation_rejected` — wrong operation type → HTTP 422
12. `test_mismatched_parameters_hash_rejected` — wrong `parameters_hash` → HTTP 422
13. `test_mismatched_repo_rejected` — wrong `repo_full_name` → HTTP 422
14. `test_concurrent_consumption_only_one_succeeds` — two concurrent consumes; exactly one success, one `ConfirmationAlreadyUsedError`
15. `test_no_automatic_pr_merge` — no `/merge` route in OpenAPI spec
16. `test_github_token_not_in_audit_log` — `GITHUB_TOKEN` value absent from all audit log entries
17. `test_workflow_run_deletion_expires_github_confirmation` — BEFORE DELETE trigger expires ISSUED confirmation; cannot then be consumed

**Total named negative tests for Wave 5: 17**

(In addition, Task G5 also carries forward `test_mcp_approval_model_importable` and `test_mcp_approval_consume_atomic_safe` as full-round-trip verification of Wave 4.)

---

## 8. Specification Changes

### 8.1 Files modified and sections changed

| File | Sections changed | Version |
|---|---|---|
| `requirements.md` | v1.5.8 header; version history; REQ-G1.4 (status field, trigger, security contract, execution outcomes, G1.4.15–G1.4.24); W1.7.7 audit events | v1.5.8 (**already at v1.5.8 before this run**) |
| `design.md` | v1.5.8 header; §3.7b SQL DDL (status column, trigger DDL, SQLAlchemy model); §3.7 FK behaviors table (github_confirmations row); `consume_atomic` signature (status='ISSUED'); §8.2 security contract | v1.5.8 (**already at v1.5.8; DDL and model updated in this run**) |
| `tasks.md` | v1.5.8 header; version history; Task G1 migration 007 DDL (status column, CHECK, trigger in upgrade/downgrade); G1 acceptance criteria (criteria 6–12); Task G5 required test cases (10 W5-GC tests); G5 acceptance criteria (11–12) | v1.5.7 → **v1.5.8 (corrected in this run)** |
| `docs/planning/phase1-roadmap.md` | v1.5.8 header; version history; Wave 5 completion gate (trigger, status column, 10 W5-GC tests); Security Summary (Wave 5 rows) | v1.5.7 → **v1.5.8 (corrected in this run)** |

### 8.2 Summary of changes applied in this run

1. **tasks.md**: Version bumped 1.5.7→1.5.8; migration 007 DDL spec updated with `status` column, `ck_github_confirmations_status` CHECK constraint, BEFORE DELETE trigger in `upgrade()`, `DROP TRIGGER IF EXISTS` in `downgrade()`; G1 acceptance criteria extended (11→12 criteria) to cover status column and trigger; G5 required test cases extended with 10 W5-GC security negative tests; G5 acceptance criteria extended (10→12) with criteria 11–12.

2. **design.md**: §3.7b SQL DDL updated with `status` column and inline trigger DDL block; SQLAlchemy model updated with `status` field and inline comment; `consume_atomic` docstring updated to use `WHERE status='ISSUED'`; §3.7 FK behaviors table extended with `GitHubConfirmation.workflow_run_id` row (W5-GC).

3. **phase1-roadmap.md**: Version bumped 1.5.7→1.5.8; version history entry added; Wave 5 completion gate updated with trigger, status column, and 10 W5-GC tests; Security Summary Wave 5 rows updated.

4. **requirements.md** and **design.md** (version history/header): Both were already at v1.5.8 when this run started, confirmed correct. The design.md §3.7b DDL and model corrections above bring the implementation-level spec into full alignment with the security intent already documented in §8.2.

### 8.3 Files NOT modified (strict boundaries respected)

- `src/` — no application code
- `tests/` — no test files
- `alembic/` — no migration files created or modified
- `.github/workflows/` — no CI changes
- `pyproject.toml` — unchanged
- `.kiro/specs/foundation-and-architecture/` — Phase 0 spec, untouched
- `alembic/versions/006_add_mcp_approvals.py` — migration 006, untouched

---

## 9. SQLite Verification Evidence

**Script:** `.agents/tasks/_gc_fk_verify_temp.py` (deleted after run)

**Command:** `py .agents/tasks/_gc_fk_verify_temp.py`

**Full output:**
```
CHECK 1 PASS: ISSUED confirmation expired and FK nulled on run deletion
CHECK 2 PASS: USED confirmation preserved as USED with FK nulled
CHECK 3 PASS: Originally unbound confirmation unaffected by run deletion
CHECK 4 PASS: DELETE+ROLLBACK restores ISSUED status and original FK binding
CHECK 5 PASS: EXPIRED confirmation cannot be consumed (WHERE status='ISSUED' → 0 rows)

All 5 checks PASSED. GitHubConfirmation deletion binding verified.
```

**Exit code:** 0

**Checks performed:**
1. ISSUED confirmation bound to run → trigger expires on run deletion → `status=EXPIRED`, `workflow_run_id=NULL`
2. USED confirmation → preserved as USED with `workflow_run_id=NULL`
3. Originally unbound (`workflow_run_id=NULL`) → unaffected by any run deletion
4. DELETE + ROLLBACK → confirmation still ISSUED with original FK (trigger is transactional)
5. EXPIRED confirmation cannot be consumed (`UPDATE WHERE status='ISSUED'` → 0 rows)

**SQLite version:** System default (Python 3.x `sqlite3` module, Windows)

---

## 10. Remaining Blockers

None. All specification corrections have been applied. The following cross-document consistency checks are verified:

| # | Check | Status |
|---|---|---|
| 1 | `status` field (ISSUED/EXPIRED/USED) in requirements, design, tasks, migration 007 DDL | ✓ |
| 2 | BEFORE DELETE trigger on `workflow_runs` for `github_confirmations` in design and migration 007 | ✓ |
| 3 | `consume_atomic` rejects `status != 'ISSUED'` | ✓ |
| 4 | All negative tests listed in requirements.md (G1.4.15–G1.4.24) and tasks.md G5 | ✓ |
| 5 | Execution outcomes (SUCCEEDED/FAILED/INDETERMINATE) defined in requirements and design | ✓ |
| 6 | No automatic PR merging | ✓ (REQ-S1.4, REQ-G1.5.5, no `/merge` route) |
| 7 | No boolean-only authorization | ✓ (REQ-G1.4, REQ-G1.5.2, design §14.1) |
| 8 | Migration 007 chains from `006_add_mcp_approvals` | ✓ |
| 9 | Chain 001→007 consistent in requirements §REQ-DB1.1, design §3.0, roadmap | ✓ |
| 10 | Version v1.5.8, date 2026-11-16, all modified files | ✓ |
| 11 | No Wave 5 application code introduced | ✓ |
| 12 | No changes to migrations 001–006 | ✓ |

---

## 11. Final Verdict

**WAVE 5 SPECIFICATIONS READY — PROCEED TO CODEX**

All four spec files (`requirements.md`, `design.md`, `tasks.md`, `docs/planning/phase1-roadmap.md`) are at version **v1.5.8** and are mutually consistent. The `GitHubConfirmation` deletion binding vulnerability (NULL-to-NULL bypass) is closed by the `status` field (`ISSUED`/`EXPIRED`/`USED`) and the BEFORE DELETE trigger on `workflow_runs`, verified against real SQLite (5/5 checks pass). The migration 007 DDL spec is complete with status column, CHECK constraint, trigger in `upgrade()`, and `DROP TRIGGER IF EXISTS` in `downgrade()`. The confirmation security contract (13 rules), execution outcomes (SUCCEEDED/FAILED/INDETERMINATE), and all 17 named negative tests (including 10 W5-GC security boundary tests) are specified and cross-referenced. No application code, migration files, or migration 006 were modified. The Wave 5 feature branch exists at `bceb9ba` and is ready for Codex implementation.
