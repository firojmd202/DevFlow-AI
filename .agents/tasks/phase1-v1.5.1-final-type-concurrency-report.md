# Phase 1 v1.5.1 Final Type and Concurrency Alignment Report

**Date:** 2026-11-15
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Specification version after this pass:** v1.5.2
**Mode:** Documentation-only — no src/, tests/, alembic/, .github/workflows/, or pyproject.toml modified

---

## 1. Exact Files and Sections Modified

| File | Section | What changed |
|---|---|---|
| `.kiro/specs/phase1-functional-orchestration/design.md` | Version header | Bumped to v1.5.2; added v1.5.2 version history entry |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `MCPService.invoke_tool` signature | `trusted_workflow_run_id: UUID | None` → `trusted_workflow_run_id: int | None` (T1); added annotation "WorkflowRun.id is an INTEGER primary key (T1). It is NOT a UUID." |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `invoke_tool` docstring step 7 | Replaced "SQLite serialized write" with `BEGIN IMMEDIATE` semantics (T2); added busy_timeout policy, lock-contention retry rule; noted `trusted_workflow_run_id` as `int | None` |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `invoke_tool` docstring note block | Added "trusted_workflow_run_id is int | None — WorkflowRun.id is an INTEGER primary key (T1). It is NOT a UUID." |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `MCPApprovalRepository.consume_atomic` signature | `trusted_workflow_run_id: UUID | None` → `trusted_workflow_run_id: int | None` (T1) |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `MCPApprovalRepository.consume_atomic` docstring | Replaced "SELECT row with row-level lock (or SQLite serialized write)" with `BEGIN IMMEDIATE` semantics; added full write-lock explanation; added busy_timeout policy; added lock-contention retry rule; replaced "raise ConsumedError" with "ROLLBACK; raise ConsumedError" on 0-rows-updated path |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | Version header | Bumped to v1.5.2; added v1.5.2 version history entry |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M2.2 `consume_atomic` signature | `trusted_workflow_run_id: UUID | None` → `int | None` (T1); step 1 updated to `BEGIN IMMEDIATE;`; step 4 annotated with `int | None` and T1 reference |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M2.2 SQLite concurrency assumptions | Removed: "concurrent writes from the same process are serialized by SQLAlchemy's connection pool"; added correct SQLite engine write-lock semantics (T2); added `BEGIN IMMEDIATE` requirement; added `busy_timeout` recommendation (5000 ms); added lock-contention retry policy |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M2.2 acceptance criteria | Added M2.2.9: `consume_atomic` uses `BEGIN IMMEDIATE` (T2) |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M2.2 named T2 tests | Added 5 T2 named negative tests block |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M2.5 M2.5.1 | `trusted_workflow_run_id: UUID | None` → `int | None` with T1 annotation |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M1.7 step 7 | Updated consume_atomic call description to reference `BEGIN IMMEDIATE` and correct write-lock semantics |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Version header | Bumped to v1.5.2; added v1.5.2 version history entry |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task I4 key implementation notes | `trusted_workflow_run_id: UUID | None` → `int | None` with T1 annotation; replaced incorrect "SQLAlchemy connection-pool write serialization" with correct SQLite engine write-lock semantics (T2); added `BEGIN IMMEDIATE`; added busy_timeout; added lock-contention retry rule |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task I4 S1 binding test descriptions | Updated integer terminology (X, Y ∈ ℤ; None instead of NULL); confirmed `trusted_workflow_run_id` integer comparisons |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task I4 S2 atomic consumption tests | Replaced `test_stale_in_memory_approval_rejected_at_consumption` with `test_begin_immediate_prevents_toctou`; added `test_busy_timeout_treated_as_authorization_failure` as fifth T2 test |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task I7 all-tests list | Updated S2/T2 test entries: added `test_busy_timeout_treated_as_authorization_failure` and `test_begin_immediate_prevents_toctou`; replaced `test_stale_in_memory_approval_rejected_at_consumption`; total 25 named tests |
| `docs/planning/phase1-roadmap.md` | Version header | Bumped to v1.5.2; added v1.5.2 version history entry |
| `docs/planning/phase1-roadmap.md` | Wave 4 completion gate | Updated "all 20 named tests" → "all 25 named tests" including T2 tests |
| `docs/planning/phase1-roadmap.md` | Security Summary MCP row | Updated `trusted_workflow_run_id` to note `int | None` and `WorkflowRun.id is INTEGER PK`; noted `BEGIN IMMEDIATE` transaction semantics (S2/T2) |
| `docs/reviews/phase1-specification-review.md` | Version header | Bumped to v1.5.2 |
| `docs/reviews/phase1-specification-review.md` | §20 (new section) | Added "Type and Concurrency Alignment Pass (T1–T2)" with T1 type contract table, T2 atomic SQL pattern, 12-check consistency results, and final verdict |
| `.agents/tasks/phase1-v1.5.1-final-type-concurrency-report.md` | New file | This document |

---

## 2. Corrected Type Contract Table

| Field / parameter | Type | Notes |
|---|---|---|
| `MCPApproval.id` | `UUID` (stored as `TEXT` in SQLite) | Primary key of the MCPApproval record; UUID |
| `mcp_approval_id` parameter (invoke_tool, consume_atomic caller) | `UUID | None` | Caller passes UUID to identify the approval; unchanged |
| `WorkflowRun.id` | `int` | INTEGER primary key — NOT a UUID (T1) |
| `MCPApproval.workflow_run_id` | `int | None` | Nullable INTEGER FK → `workflow_runs.id` ON DELETE SET NULL |
| `trusted_workflow_run_id` parameter (`MCPService.invoke_tool`) | `int | None` | Server-side session context; must match `MCPApproval.workflow_run_id` exactly; never from tool arguments |
| `MCPApprovalRepository.consume_atomic` `trusted_workflow_run_id` | `int | None` | Same type as the FK it is compared against; `int | None` (T1) |
| `MCPApprovalRepository.consume_atomic` `now` | `datetime` | `datetime.now(UTC)` — `datetime.utcnow()` prohibited |

**Unchanged (UUID types):** `MCPApproval.id` remains UUID (TEXT). `mcp_approval_id` parameter remains `UUID | None`. `GitHubConfirmation.id` remains UUID (TEXT). These were not changed.

---

## 3. Atomic SQL / Transaction Specification

The `consume_atomic` operation executes as a single SQLite write transaction using `BEGIN IMMEDIATE`:

```sql
BEGIN IMMEDIATE;  -- acquires write lock immediately, prevents TOCTOU
SELECT id, status, expires_at, consumed_at, actor_id, mcp_server_id,
       tool_name, arguments_hash, workflow_run_id
FROM mcp_approvals
WHERE id = :approval_id;
-- validate all fields within the transaction (status=APPROVED, expires_at > :now,
-- consumed_at IS NULL, actor_id=:actor_id, mcp_server_id=:server_id,
-- tool_name=:tool_name, arguments_hash=:args_hash, workflow_run_id IS :wf_run_id)
-- wf_run_id comparison: :wf_run_id is int | None; NULL-to-NULL and int-to-int must match
UPDATE mcp_approvals
SET status = 'CONSUMED', consumed_at = :now
WHERE id = :approval_id
  AND status = 'APPROVED'
  AND expires_at > :now
  AND consumed_at IS NULL;
-- if rowcount != 1: ROLLBACK and raise ConsumedError
COMMIT;
-- only after COMMIT: proceed to subprocess launch
```

**Key properties:**
- `:now` is `datetime.now(UTC)` captured once at the start of the transaction (not re-evaluated). `datetime.utcnow()` is prohibited.
- `BEGIN IMMEDIATE` acquires the write lock before the SELECT, preventing another transaction from modifying the row between SELECT and UPDATE (TOCTOU prevention).
- After `COMMIT`, if the subprocess fails or times out: approval remains `CONSUMED`. No rollback. No automatic retry of the external MCP invocation.
- **SQLite write serialization:** SQLite serializes writes at the database-file level. Only one write transaction holds the write lock at a time. This is a SQLite engine guarantee, NOT a SQLAlchemy connection-pool guarantee.
- **busy_timeout:** Configure `busy_timeout` (recommended: 5000 ms). If `BEGIN IMMEDIATE` cannot acquire the write lock immediately, SQLite waits up to `busy_timeout` ms before raising `OperationalError`/busy.
- **Lock contention:** An `OperationalError`/busy from `BEGIN IMMEDIATE` is treated as an authorization failure for the current request. The caller (MCPService) MAY retry the database operation only (not the external MCP invocation) after a brief delay, up to a configurable maximum (e.g. 3 retries with exponential backoff).
- **Exactly-once caveat:** "DevFlow AI cannot guarantee exactly-once execution of external MCP tools. If the subprocess was launched but the result is unknown, the user must verify external state before requesting a new approval."

---

## 4. Updated Security Test Matrix

| Test name | Finding | Scenario | Wave | Task | Status |
|---|---|---|---|---|---|
| `test_forged_approval_record_rejected` | F1/F6 | Caller passes in-memory approval object; MCPService only accepts mcp_approval_id | Wave 4 | I4, I7 | Existing |
| `test_expired_approval_rejected_at_invocation` | F1/F6 | MCPApproval.expires_at in the past at invocation time | Wave 4 | I4, I7 | Existing |
| `test_mismatched_tool_name_rejected` | F1/F6 | MCPApproval.tool_name ≠ invoked tool | Wave 4 | I4, I7 | Existing |
| `test_mismatched_arguments_hash_rejected` | F1/F6 | MCPApproval.arguments_hash ≠ SHA-256 of supplied arguments | Wave 4 | I4, I7 | Existing |
| `test_replay_after_consumption_rejected` | F1/F6 | Second call with already-CONSUMED MCPApproval | Wave 4 | I4, I7 | Existing |
| `test_concurrent_consumption_safe` | F1/F6 | Two concurrent invoke_tool calls: exactly one success, one MCPApprovalRequiredError | Wave 4 | I4, I7 | Existing |
| `test_read_only_tool_no_approval_required` | F1/F6 | read_only tool proceeds without mcp_approval_id | Wave 4 | I4, I7 | Existing |
| `test_no_direct_mcp_client_bypass` | F1/F6 | No router/adapter calls MCPClient.call_tool without MCPService | Wave 4 | I4, I7 | Existing |
| `test_allowlist_alone_insufficient_for_consequential_tool` | F3 | Consequential tool passes allow-list but has no MCPApproval → denied | Wave 4 | I4, I7 | Existing |
| `test_unknown_tool_denied_without_approval` | F1 | Unknown-classification tool without mcp_approval_id → MCPApprovalRequiredError | Wave 4 | I4, I7 | Existing |
| `test_consequential_tool_denied_without_approval` | F1 | Consequential tool without mcp_approval_id → MCPApprovalRequiredError | Wave 4 | I4, I7 | Existing |
| `test_approval_wrong_workflow_run_rejected` | S1/T1 | approval.workflow_run_id = X (int), trusted = Y (int, X≠Y) → rejected; reason=workflow_run_mismatch; approval NOT consumed | Wave 4 | I4, I7 | Existing |
| `test_approval_bound_to_workflow_rejected_without_workflow_context` | S1/T1 | approval.workflow_run_id non-NULL (int), trusted = None → rejected; reason=missing_workflow_context | Wave 4 | I4, I7 | Existing |
| `test_approval_unbound_rejected_with_workflow_context` | S1/T1 | approval.workflow_run_id = NULL, trusted = N (int, non-None) → rejected; reason=unexpected_workflow_context | Wave 4 | I4, I7 | Existing |
| `test_workflow_run_id_from_arguments_not_trusted` | S1/T1 | workflow_run_id in tool args ignored; session int context (None) used; approval with non-NULL int workflow_run_id → rejected | Wave 4 | I4, I7 | Existing |
| `test_concurrent_consumption_only_one_succeeds` | S2/T2 | Two threads/tasks attempt consume_atomic simultaneously; BEGIN IMMEDIATE; exactly one succeeds | Wave 4 | I4, I7 | Existing (T2 strengthened) |
| `test_expired_at_consumption_time_rejected` | S2/T2 | Approval valid at service-layer check; expires_at passes before consume_atomic; in-transaction check rejects; ConsumedError raised | Wave 4 | I4, I7 | Existing (T2 name confirmed) |
| `test_consumed_approval_cannot_be_reused` | S2 | consume_atomic on already-CONSUMED record: 0 rows updated → ConsumedError | Wave 4 | I4, I7 | Existing |
| `test_execution_failure_does_not_restore_consumed_approval` | S2/F9 | Subprocess raises after consume_atomic; MCPApproval remains CONSUMED; mcp_tool_failed logged | Wave 4 | I4, I7 | Existing |
| `test_busy_timeout_treated_as_authorization_failure` | **T2** | Simulate lock contention (OperationalError); verify caught and treated as authorization failure; DB-only retry permitted; MCP invocation NOT retried | Wave 4 | I4, I7 | **New (T2)** |
| `test_begin_immediate_prevents_toctou` | **T2** | Verify consume_atomic uses BEGIN IMMEDIATE; write lock acquired before SELECT; prevents TOCTOU | Wave 4 | I4, I7 | **New (T2)** |
| `test_execution_failure_does_not_restore_approval` | F9 | After mcp_tool_failed, MCPApproval remains CONSUMED (prior F9 test) | Wave 4 | I4, I7 | Existing |
| `test_timeout_recorded_as_indeterminate_in_audit` | F9 | Subprocess timeout logs mcp_tool_failed; approval not restored | Wave 4 | I4, I7 | Existing |
| `test_new_approval_required_for_retry_after_failure` | F9 | Retry after failure requires new MCPApproval; consumed one raises MCPApprovalRequiredError | Wave 4 | I4, I7 | Existing |
| `test_stale_in_memory_approval_rejected_at_consumption` | S2 | In-memory validation passes; in-transaction expiry check rejects stale approval | Wave 4 | I4, I7 | Replaced by `test_expired_at_consumption_time_rejected` (T2 clarification) |

**Total named tests in Wave 4 (I4+I7): 25** (20 existing from prior passes + 2 new T2 tests; `test_stale_in_memory_approval_rejected_at_consumption` retired in favor of the more precise `test_expired_at_consumption_time_rejected`).

---

## 5. Cross-Document Consistency Results (12 Checks)

| # | Check | Result |
|---|---|---|
| 1 | `MCPApproval.workflow_run_id` typed as `int | None` everywhere (no UUID for this field) | **PASS** — ORM model uses `Mapped[int | None]` with INTEGER FK; all parameter descriptions now say `int | None` |
| 2 | `trusted_workflow_run_id` parameter typed as `int | None` in MCPService.invoke_tool and consume_atomic | **PASS** — Fixed in design.md §7.5 (both signatures), requirements.md REQ-M2.2 and REQ-M2.5, tasks.md I4 |
| 3 | `MCPApproval.id` and `mcp_approval_id` parameter remain UUID (unchanged) | **PASS** — UUID (TEXT) for `MCPApproval.id`; `UUID | None` for `mcp_approval_id` caller parameter; not changed |
| 4 | `consume_atomic` uses `BEGIN IMMEDIATE` transaction semantics (documented in design.md §7.5) | **FIXED** — Added `BEGIN IMMEDIATE` to design.md §7.5 consume_atomic docstring and invoke_tool step 7, requirements.md REQ-M2.2 step 1, tasks.md I4 consume_atomic description |
| 5 | `busy_timeout` policy documented | **FIXED** — Added to design.md §7.5 (both consume_atomic docstring and invoke_tool step 7), requirements.md REQ-M2.2 SQLite concurrency section, tasks.md I4 key implementation notes |
| 6 | No claim that SQLAlchemy connection pooling serializes writes | **FIXED** — Removed from requirements.md REQ-M2.2 SQLite concurrency assumptions; removed from tasks.md I4 key implementation notes; replaced with correct SQLite engine write-lock semantics |
| 7 | No automatic retry of external MCP invocation | **PASS** — Only DB-operation retry permitted; MCP invocation retry explicitly prohibited throughout |
| 8 | `datetime.now(UTC)` used as the UTC source (not `datetime.utcnow()`) | **PASS** — Consistent throughout; utcnow() prohibition stated in global constraints and all consume_atomic descriptions |
| 9 | All 25 named negative tests present in Wave 4 tasks I4 and I7 (20 prior + 5 new T2 tests; 1 renamed) | **FIXED** — Added `test_busy_timeout_treated_as_authorization_failure` and `test_begin_immediate_prevents_toctou` to I4 and I7; `test_stale_in_memory_approval_rejected_at_consumption` replaced by `test_expired_at_consumption_time_rejected` |
| 10 | Migration chain 001→007 unchanged | **PASS** — 001→002→003→004→005→006→007 unchanged |
| 11 | Wave 4 has no Wave 5 dependencies | **PASS** — Wave 4 owns migration 006; Wave 5 owns migration 007; no cross-wave dependency |
| 12 | Version metadata updated to v1.5.2 and date 2026-11-15 in all five documents | **FIXED** — All five documents updated to v1.5.2 / 2026-11-15 |

**Summary:** 4 checks FIXED (checks 4, 5, 6, 9/12); 8 checks already PASS. No REMAINING BLOCKERS.

---

## 6. Remaining Risks and Unresolved Decisions

| Item | Status | Action required |
|---|---|---|
| Workflow page numbering (pages 6 and 7 renamed) | Open (from v1.0.0) | Reviewer to confirm `6_Workflows.py` / `7_History.py` is preferred |
| MCP SDK version pin | Open (from v1.0.0) | Reviewer to confirm `mcp>=1.0,<2.0` is acceptable |
| `pyproject.toml` and `ci.yml` coverage flags | Open (from v1.1.0 Finding 2) | `branch = true` must be added at implementation time (Wave 1, Task P1) |
| MCP server binary trust model | Open (from v1.3.0 §12) | Reviewer to confirm operator-trust model in §14.4 is acceptable |
| `busy_timeout` exact configuration point | Minor open | The spec recommends 5000 ms and says "configure"; the implementer must decide whether to set via SQLAlchemy engine `connect_args={"timeout": 5}` or via PRAGMA in the connect event handler. Both achieve the same effect. No spec change needed. |
| `BEGIN IMMEDIATE` Python implementation | Minor open | Python's `aiosqlite`/SQLAlchemy async does not have a direct `BEGIN IMMEDIATE` syntax helper. The implementer may use a raw `EXECUTE 'BEGIN IMMEDIATE'` before the ORM operations, or use `connection.execution_options(isolation_level="IMMEDIATE")` if supported. The spec describes intent; the implementer selects the mechanism. |
| `test_stale_in_memory_approval_rejected_at_consumption` rename | Resolved | Retired in favour of the more precise `test_expired_at_consumption_time_rejected`. Both tests cover the same in-transaction expiry scenario. The rename aligns with T2 test naming conventions. |

**No new blockers introduced by T1 or T2 corrections.**

---

## 7. Git Status

```
Branch: feature/phase1-specification-planning
```

**`git status --short` output:**
```
 M .kiro/specs/phase1-functional-orchestration/design.md
 M .kiro/specs/phase1-functional-orchestration/requirements.md
 M .kiro/specs/phase1-functional-orchestration/tasks.md
 M docs/planning/phase1-roadmap.md
 M docs/reviews/phase1-specification-review.md
?? .agents/tasks/phase1-v1.5-final-mcp-security-report.md
```

**`git diff --stat` output:**
```
 .../phase1-functional-orchestration/design.md      |  77 +++++++-
 .../requirements.md                                |  66 ++++++-
 .../specs/phase1-functional-orchestration/tasks.md |  44 ++++-
 docs/planning/phase1-roadmap.md                    |   8 +-
 docs/reviews/phase1-specification-review.md        | 210 ++++++++++++++++++++-
 5 files changed, 391 insertions(+), 14 deletions(-)
```

No changes to: `src/`, `tests/`, `alembic/`, `.github/workflows/`, `pyproject.toml`

---

## 8. Final Verdict

**READY FOR FINAL PR READINESS REVIEW**

Both findings are resolved at the specification level:

**T1 — Workflow Run Identifier Type:** `trusted_workflow_run_id` corrected from `UUID | None` to `int | None` throughout all five spec documents (design.md §7.5 invoke_tool and consume_atomic signatures, requirements.md REQ-M2.2 and REQ-M2.5, tasks.md I4 key implementation notes and S1 test descriptions). `MCPApproval.workflow_run_id` is a nullable INTEGER FK → `workflow_runs.id`; the trusted context parameter that is compared against it must be `int | None`. UUID approval IDs (`MCPApproval.id`, `mcp_approval_id`) are unchanged.

**T2 — SQLite Atomic Consumption and Concurrency:** The incorrect claim that "SQLAlchemy connection pooling serializes writes" has been removed from all active spec sections and replaced with the correct description: "SQLite serializes writes at the database-file level — only one write transaction holds the write lock at a time — a SQLite engine guarantee, not a SQLAlchemy pooling guarantee." The `consume_atomic` algorithm now explicitly requires `BEGIN IMMEDIATE` to acquire the write lock before the SELECT (TOCTOU prevention), documents a `busy_timeout` policy (5000 ms recommended), and specifies that lock contention is an authorization failure allowing DB-only retry (not MCP invocation retry). Five new named tests cover the T2 scenarios. The total named negative test count in Wave 4 (I4+I7) is now 25.

The five specification documents are internally consistent at v1.5.2. The approved migration chain 001→002→003→004→005→006→007 is unchanged. Wave 4 has no Wave 5 dependencies.
