# Phase 1 v1.5 Final MCP Security Hardening Report

**Date:** 2026-11-15
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Specification version after this pass:** v1.5.1
**Mode:** Documentation-only — no src/, tests/, alembic/, .github/workflows/, or pyproject.toml modified

---

## 1. Exact Files and Sections Changed

| File | Section | What changed |
|---|---|---|
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | Version header | Bumped to v1.5.1; added v1.5.1 version history entry |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-W1.7 audit event table | Added `mcp_approval_rejected` row with `reason` field variants |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M2.2 | Replaced single-line `consume_atomic` description with full 8-step atomic transaction specification; added M2.2.6–M2.2.8 acceptance criteria; added SQLite concurrency assumptions section; added `now: datetime` and `trusted_workflow_run_id` to signature |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-M2.5 (new) | New requirement: 6 workflow_run_id binding rules, 7 acceptance criteria, 4 named negative tests |
| `.kiro/specs/phase1-functional-orchestration/design.md` | Version header | Bumped to v1.5.1; added v1.5.1 version history entry |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `MCPService.invoke_tool` signature | Added `trusted_workflow_run_id: UUID | None` parameter (server-side only) |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `invoke_tool` docstring | Added step 6e (workflow_run_id binding check with 3 rejection cases); expanded step 7 to show full 6-step transaction sequence; added datetime.now(UTC) note |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 `MCPApprovalRepository` interface | Replaced 1-line `consume_atomic` with full docstring including 6-step algorithm, `trusted_workflow_run_id` and `now` parameters |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §7.5 audit event table | Added `mcp_approval_rejected` row with reason field and "Distinct from" note |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §16 master audit event table | Added `mcp_approval_rejected` row with reason field variants |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Version header | Bumped to v1.5.1; added v1.5.1 version history entry |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task I4 key implementation notes | Added `trusted_workflow_run_id` parameter note; added S1 binding rules (3 cases + no-consume guarantee); replaced single-line `consume_atomic` note with full 7-step transaction description including datetime.now(UTC) and SQLite concurrency |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task I4 named tests | Added S1 workflow run binding section (4 tests); added S2 atomic consumption section (5 tests) |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task I7 all test cases | Added 9 new tests (4 S1 + 5 S2) to the complete test list |
| `docs/planning/phase1-roadmap.md` | Version header | Bumped to v1.5.1; added v1.5.1 version history entry |
| `docs/planning/phase1-roadmap.md` | Wave 4 completion gate | Updated to require all 20 named tests (not 8) |
| `docs/planning/phase1-roadmap.md` | Security Summary table — MCP row | Added S1 workflow_run_id binding and S2 atomic consumption to authorization mechanism description |
| `docs/reviews/phase1-specification-review.md` | §19 (new) | Appended MCP Security Hardening Pass (S1–S2): S1 findings and 4 tests; S2 findings and 5 tests; 9-point consistency check; updated final verdict |
| `.agents/tasks/phase1-v1.5-final-mcp-security-report.md` | New file | This document |

---

## 2. Final Approval Authorization Contract

Every MCP `consequential` or `unknown` tool invocation through `MCPService.invoke_tool` MUST pass ALL of the following checks before execution. The checks are sequential and each failure is a hard stop (fail closed).

### Pre-consumption checks (steps 1–6 of the 9-step sequence)

| Step | Check | Failure action |
|---|---|---|
| 1 | MCP server is configured and enabled in `MCPServerConfig` | Raise `MCPServerNotFoundError` |
| 2 | Tool is on the allow-list (`MCPServerConfig.allowed_tools`) | Raise `MCPPermissionError`; no approval consumed |
| 3–4 | Tool classification: `read_only` / `consequential` / `unknown`; `unknown` → `consequential` | — |
| 5 | `mcp_approval_id` is not None AND `MCPApproval` record found in DB | Log `mcp_approval_missing`; raise `MCPApprovalRequiredError` |
| 6a | `MCPApproval.status = APPROVED` | Raise `MCPApprovalRequiredError` |
| 6b | `MCPApproval.expires_at > now(UTC)` | Log `mcp_approval_expired`; raise `MCPApprovalExpiredError` |
| 6c | `MCPApproval.mcp_server_id`, `tool_name`, `arguments_hash`, `actor_id` match invocation | Raise `MCPApprovalRequiredError` |
| 6d | `MCPApproval.status ≠ CONSUMED` | Raise `MCPApprovalRequiredError` (replay prevention) |
| **6e** | **workflow_run_id binding (S1)** — `trusted_workflow_run_id` from server-side session ONLY | Log `mcp_approval_rejected(reason=...)`; raise `MCPApprovalRequiredError`; approval NOT consumed |

### Workflow run ID binding rules (S1 — step 6e)

| Approval `workflow_run_id` | Invocation `trusted_workflow_run_id` | Verdict | Reason |
|---|---|---|---|
| X (non-NULL) | Y (non-NULL, X≠Y) | REJECT | `workflow_run_mismatch` |
| X (non-NULL) | NULL | REJECT | `missing_workflow_context` |
| NULL | Y (non-NULL) | REJECT | `unexpected_workflow_context` |
| X | X | ALLOW | — |
| NULL | NULL | ALLOW | — |

**Rule 4 (implicit):** Any `workflow_run_id` value supplied in the tool arguments payload is ignored for binding. Only the server-side session context value is used.

**Rule 5:** Failure closes — no execution, no consumption.

**Rule 6:** Every rejection from step 6e emits `mcp_approval_rejected` audit event with structured `reason` field.

### Atomic consumption (step 7)

After all pre-consumption checks pass, `MCPApprovalRepository.consume_atomic(id, trusted_workflow_run_id, now)` is called. See §3 below for the full algorithm.

### Post-execution behavior

- `mcp_approval_granted` logged after successful consumption.
- `mcp_tool_invoked` logged after subprocess launch.
- `mcp_tool_completed` logged on success.
- `mcp_tool_failed` logged on exception/timeout — approval remains CONSUMED; no rollback.

---

## 3. Atomic Consumption Algorithm (S2 — 8 Steps)

`MCPApprovalRepository.consume_atomic(id: UUID, trusted_workflow_run_id: UUID | None, now: datetime) → MCPApproval`

```
Step 1: BEGIN TRANSACTION
         SELECT mcp_approvals WHERE id = ? FOR UPDATE (or SQLite serialized write)

Step 2: Within SAME transaction, verify:
         status = 'APPROVED'
         AND expires_at > now                   ← in-transaction expiry check (prevents stale validation)
         AND consumed_at IS NULL

Step 3: Within SAME transaction, verify workflow_run_id binding:
         Apply S1 binding rules (Table §2 above) comparing
         record.workflow_run_id against trusted_workflow_run_id

Step 4: If steps 2–3 pass:
         UPDATE mcp_approvals
            SET status = 'CONSUMED',
                consumed_at = now
          WHERE id = ?
            AND status = 'APPROVED'
            AND expires_at > now
            AND consumed_at IS NULL

Step 5: Check rowcount:
         If rowcount = 0 → raise ConsumedError
                           log mcp_approval_already_consumed
                           ROLLBACK

Step 6: COMMIT transaction
         (Subprocess launch happens AFTER commit — not inside the transaction)

Step 7: Return updated MCPApproval record

Step 8: (Caller) Launch subprocess
         If subprocess fails/times out → log mcp_tool_failed
         Approval remains CONSUMED (no rollback, no restore)
```

**Timestamp rule:** `now` MUST be `datetime.now(UTC)`. `datetime.utcnow()` MUST NOT be used anywhere in Phase 1 code (global constraint).

**SQLite concurrency assumptions:**
- SQLite uses database-level write serialization (WAL mode or exclusive locking).
- In Phase 1 single-process deployment, concurrent writes from the same process are serialized by SQLAlchemy's connection pool.
- In a multi-process deployment, SQLite WAL mode MUST be enabled (`PRAGMA journal_mode=WAL`); this PRAGMA is already registered in the `'connect'` event handler (REQ-DB1.3).
- The in-transaction `expires_at > now` check (step 2) prevents a stale in-memory validation result from bypassing expiry between the service-layer check and consumption.
- Phase 1 targets single-process deployment.

---

## 4. Complete Negative Test Matrix

| Test name | Finding | Scenario | Wave | Task |
|---|---|---|---|---|
| `test_forged_approval_record_rejected` | F1/F6 | Caller passes in-memory approval object; MCPService only accepts mcp_approval_id | Wave 4 | I4, I7 |
| `test_expired_approval_rejected_at_invocation` | F1/F6 | MCPApproval.expires_at in the past at invocation time | Wave 4 | I4, I7 |
| `test_mismatched_tool_name_rejected` | F1/F6 | MCPApproval.tool_name ≠ invoked tool | Wave 4 | I4, I7 |
| `test_mismatched_arguments_hash_rejected` | F1/F6 | MCPApproval.arguments_hash ≠ SHA-256 of supplied arguments | Wave 4 | I4, I7 |
| `test_replay_after_consumption_rejected` | F1/F6 | Second call with already-CONSUMED MCPApproval | Wave 4 | I4, I7 |
| `test_concurrent_consumption_safe` | F1/F6 | Two concurrent invoke_tool calls: exactly one success, one MCPApprovalRequiredError | Wave 4 | I4, I7 |
| `test_read_only_tool_no_approval_required` | F1/F6 | read_only tool proceeds without mcp_approval_id | Wave 4 | I4, I7 |
| `test_no_direct_mcp_client_bypass` | F1/F6 | No router/adapter calls MCPClient.call_tool without MCPService | Wave 4 | I4, I7 |
| `test_allowlist_alone_insufficient_for_consequential_tool` | F3 | Consequential tool passes allow-list but has no MCPApproval → denied | Wave 4 | I4, I7 |
| `test_expired_approval_rejected_at_invocation` | F1/D4 | MCPApproval.expires_at in the past; MCPApprovalExpiredError raised | Wave 4 | I4, I7 |
| `test_unknown_tool_denied_without_approval` | F1 | Unknown-classification tool without mcp_approval_id → MCPApprovalRequiredError | Wave 4 | I4, I7 |
| `test_consequential_tool_denied_without_approval` | F1 | Consequential tool without mcp_approval_id → MCPApprovalRequiredError | Wave 4 | I4, I7 |
| `test_approval_wrong_workflow_run_rejected` | **S1** | approval.workflow_run_id = X, trusted = Y (X≠Y) → rejected; reason=workflow_run_mismatch; approval NOT consumed | Wave 4 | I4, I7 |
| `test_approval_bound_to_workflow_rejected_without_workflow_context` | **S1** | approval.workflow_run_id non-NULL, trusted = NULL → rejected; reason=missing_workflow_context | Wave 4 | I4, I7 |
| `test_approval_unbound_rejected_with_workflow_context` | **S1** | approval.workflow_run_id = NULL, trusted non-NULL → rejected; reason=unexpected_workflow_context | Wave 4 | I4, I7 |
| `test_workflow_run_id_from_arguments_not_trusted` | **S1** | workflow_run_id in tool args ignored; session context (NULL) used; approval with non-NULL workflow_run_id → rejected | Wave 4 | I4, I7 |
| `test_concurrent_consumption_only_one_succeeds` | **S2** | Two concurrent consume_atomic calls: in-transaction UPDATE rowcount check; exactly one success, one ConsumedError | Wave 4 | I4, I7 |
| `test_expired_at_consumption_time_rejected` | **S2** | Approval valid at service-layer check; expired by consume_atomic time; in-transaction check rejects; ConsumedError raised | Wave 4 | I4, I7 |
| `test_consumed_approval_cannot_be_reused` | **S2** | consume_atomic on already-CONSUMED record: 0 rows updated → ConsumedError | Wave 4 | I4, I7 |
| `test_execution_failure_does_not_restore_consumed_approval` | **S2**/F9 | Subprocess raises after consume_atomic; MCPApproval remains CONSUMED; mcp_tool_failed logged | Wave 4 | I4, I7 |
| `test_stale_in_memory_approval_rejected_at_consumption` | **S2** | In-memory check passes (expires_at future); in-transaction check at consume_atomic time finds expiry → ConsumedError | Wave 4 | I4, I7 |

**Total negative tests: 20** (some test names overlap with strengthened scope; e.g., `test_concurrent_consumption_only_one_succeeds` is a stricter restatement of `test_concurrent_consumption_safe`; both are listed in I7 for clarity).

---

## 5. Requirement-to-Task-to-Test Traceability

| Req ID | Requirement summary | Design section | Task | Named tests |
|---|---|---|---|---|
| REQ-M2.2 | MCPApprovalRepository.consume_atomic: single-transaction; in-transaction expiry check; rowcount=1 guard; commit before subprocess; no rollback on failure | §7.5 (consume_atomic docstring) | I4, I7 | test_concurrent_consumption_only_one_succeeds; test_expired_at_consumption_time_rejected; test_consumed_approval_cannot_be_reused; test_execution_failure_does_not_restore_consumed_approval; test_stale_in_memory_approval_rejected_at_consumption |
| REQ-M2.4 | No auto-restore after execution failure; consumed = attempted not completed | §7.5b | I4, I7 | test_execution_failure_does_not_restore_consumed_approval; test_execution_failure_does_not_restore_approval (prior F9) |
| REQ-M2.5 (new) | Workflow run ID binding: 6 rules; trusted_workflow_run_id server-side only; mcp_approval_rejected with reason | §7.5 step 6e | I4, I7 | test_approval_wrong_workflow_run_rejected; test_approval_bound_to_workflow_rejected_without_workflow_context; test_approval_unbound_rejected_with_workflow_context; test_workflow_run_id_from_arguments_not_trusted |
| REQ-W1.7 | mcp_approval_rejected audit event (new) with reason field | §16 | I4, I7 | All S1 tests (reason field assertion) |
| REQ-M1.7 | 9-step mandatory authorization sequence | §7.5 | I4, I7 | All 20 negative tests collectively |

---

## 6. Remaining Risks and Unresolved Decisions

| Item | Status | Action required |
|---|---|---|
| Workflow page numbering (pages 6 and 7 renamed) | Open (from v1.0.0) | Reviewer to confirm `6_Workflows.py` / `7_History.py` is preferred |
| MCP SDK version pin | Open (from v1.0.0) | Reviewer to confirm `mcp>=1.0,<2.0` is acceptable |
| `pyproject.toml` and `ci.yml` coverage flags | Open (from v1.1.0 Finding 2) | `branch = true` must be added at implementation time |
| MCP server binary trust model | Open (from v1.3.0 §12) | Reviewer to confirm operator-trust model in §14.4 is acceptable |
| Multi-process SQLite WAL enforcement | Open (new, minor) | Phase 1 is single-process; WAL is already enabled via PRAGMA; no action needed for Phase 1, but multi-process future phases must verify |
| `mcp_approval_rejected` reason field: `mismatched_binding` and `already_consumed` variants | Minor ambiguity | These reason values are defined in design.md §7.5 and §16 audit event table; `mismatched_binding` covers cases where mcp_server_id/tool_name/arguments_hash/actor_id mismatch; `already_consumed` is emitted by `mcp_approval_already_consumed` event inside consume_atomic. Implementer should use the most specific reason. No spec change needed. |
| `test_concurrent_consumption_safe` vs `test_concurrent_consumption_only_one_succeeds` | Intentional overlap | Both are listed. The original test (`test_concurrent_consumption_safe`) tests the service-layer behavior; the new S2 test (`test_concurrent_consumption_only_one_succeeds`) explicitly tests the in-transaction rowcount check at the repository layer. Both must pass. |

**No new blockers introduced by S1 or S2 corrections.**

---

## 7. Git Status

```
Branch: feature/phase1-specification-planning
```

Changes produced by this hardening pass (specification and documentation files only):
- `M  .kiro/specs/phase1-functional-orchestration/requirements.md`
- `M  .kiro/specs/phase1-functional-orchestration/design.md`
- `M  .kiro/specs/phase1-functional-orchestration/tasks.md`
- `M  docs/planning/phase1-roadmap.md`
- `M  docs/reviews/phase1-specification-review.md`
- `?? .agents/tasks/phase1-v1.5-final-mcp-security-report.md`

No changes to: src/, tests/, alembic/, .github/workflows/, pyproject.toml

---

## 8. Final Verdict

**READY FOR INDEPENDENT SECURITY REVIEW**

Both findings (S1 — workflow run binding and S2 — atomic approval consumption TOCTOU) have been resolved at the specification level. The five specification documents are internally consistent at v1.5.1. The MCP authorization contract now:

1. Explicitly binds approvals to their originating workflow run context (or lack thereof), with six enforced rules and three named rejection reasons.
2. Requires a single-transaction atomic consumption sequence that re-validates expiry and binding inside the transaction, preventing TOCTOU vulnerabilities.
3. Names 20 negative tests covering every significant attack and race scenario.
4. Specifies `datetime.now(UTC)` throughout (consistent with the global `datetime.utcnow()` prohibition).
5. Documents SQLite single-process concurrency assumptions and WAL-mode requirements for future multi-process deployments.
6. Preserves the approved migration chain 001→002→003→004→005→006→007 unchanged.
7. Preserves Wave 4 independence from Wave 5.
8. Does not modify any application source code, test file, migration file, or CI configuration.
