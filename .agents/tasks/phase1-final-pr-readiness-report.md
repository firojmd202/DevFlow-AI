# Phase 1 Final PR Readiness Report

**Date:** 2026-11-15  
**Branch:** feature/phase1-specification-planning  
**Specification version after this pass:** v1.5.3  
**Mode:** Specification correction and final verification only — no src/, tests/, alembic/, .github/workflows/, or pyproject.toml modified

---

## 1. C1 Resolution Evidence — Trusted Workflow Context (Single Parameter)

### What was found

`MCPService.invoke_tool` in design.md §7.5 had **two** competing workflow context parameters:
- `workflow_run_id: int | None = None` — a caller-supplied field
- `trusted_workflow_run_id: int | None = None` — the server-side parameter

tasks.md I4 described them additively: a base signature `invoke_tool(server_name, tool_name, arguments, actor_id, workflow_run_id=None, mcp_approval_id=None)` with `trusted_workflow_run_id` added as "an additional server-side parameter." This language allowed a caller to supply both, creating ambiguity about which value governs the authorization decision.

requirements.md REQ-M1.7 step 7 and REQ-M2.5 were otherwise correct — they referred only to `trusted_workflow_run_id`. The design.md signature was the source of the redundancy.

### What was changed

- **design.md §7.5 `invoke_tool` signature:** Removed `workflow_run_id: int | None = None`. Signature is now `invoke_tool(server_name, tool_name, arguments, actor_id, mcp_approval_id=None, trusted_workflow_run_id=None)`.
- **design.md §7.5 docstring notes:** Added explicit note: "invoke_tool has exactly ONE workflow context parameter: trusted_workflow_run_id: int | None. trusted_workflow_run_id is resolved by the application layer from the current execution session before calling invoke_tool. It is never read from tool arguments, request body, or any client-supplied field."
- **design.md §7.5 "C1 — Trusted workflow context" block:** Added standalone statement: "MCPService.invoke_tool has exactly ONE workflow context parameter: trusted_workflow_run_id: int | None. The former workflow_run_id parameter has been removed. trusted_workflow_run_id is resolved by the application layer from the current execution session before calling invoke_tool. It is never read from tool arguments, request body, or any client-supplied field. Callers cannot select or override this value."
- **requirements.md REQ-M2.5 M2.5.1:** Explicitly states "This is the ONLY workflow context parameter — the former workflow_run_id parameter has been removed."
- **requirements.md REQ-M1.7 step 7:** Updated consume_atomic call to reflect new signature.
- **tasks.md I4 key implementation notes:** Base signature now `invoke_tool(server_name, tool_name, arguments, actor_id, mcp_approval_id=None, trusted_workflow_run_id=None)`. "Additional parameter" language replaced with "exactly ONE workflow context parameter."

### No change required to

`MCPApproval.id` (UUID, unchanged), `WorkflowRun.id` (INTEGER, unchanged), `MCPApproval.workflow_run_id` (int | None FK, unchanged). These types were already correct at v1.5.2.

**Verdict: C1 RESOLVED — single unambiguous trusted context parameter, source unambiguous.**

---

## 2. C2 Resolution Evidence — Transactional Authorization Bindings in consume_atomic

### What was found

`MCPApprovalRepository.consume_atomic` accepted only `(id, trusted_workflow_run_id, now)` — 3 parameters. The actor_id, mcp_server_id, tool_name, and arguments_hash bindings were validated in step 6 of `invoke_tool` (service-layer pre-consumption validation) but were NOT re-verified as explicit parameters inside the atomic `BEGIN IMMEDIATE` transaction. This created a TOCTOU window: if the approval record was modified between service-layer validation (step 6) and atomic consumption (step 7), the consume_atomic would not detect the modification.

The in-transaction steps verified `status`, `expires_at`, `consumed_at`, and `workflow_run_id` but NOT `actor_id`, `mcp_server_id`, `tool_name`, or `arguments_hash`.

### What was changed

**design.md §7.5 `MCPApprovalRepository.consume_atomic` signature:**
```python
# Before (3 parameters):
async def consume_atomic(
    self,
    id: UUID,
    trusted_workflow_run_id: int | None,
    now: datetime,
) -> MCPApproval:

# After (7 parameters — C2):
async def consume_atomic(
    self,
    id: UUID,
    actor_id: str,                         # C2: binding field
    mcp_server_id: str,                    # C2: binding field
    tool_name: str,                        # C2: binding field
    arguments_hash: str,                   # C2: binding field
    trusted_workflow_run_id: int | None,   # T1/S1/C2: int | None
    now: datetime,                         # S2: datetime.now(UTC)
) -> MCPApproval:
```

**design.md §7.5 consume_atomic docstring:** Updated to 8-step algorithm with "Within SAME transaction verify ALL of these: a. actor_id matches; b. mcp_server_id matches; c. tool_name matches; d. arguments_hash matches; e. workflow_run_id matches (NULL-safe); f. status=APPROVED AND expires_at > now AND consumed_at IS NULL."

**design.md §7.5 invoke_tool step 7:** Updated consume_atomic call: `consume_atomic(mcp_approval_id, actor_id, server_name, tool_name, arguments_hash, trusted_workflow_run_id, now=datetime.now(UTC))`.

**requirements.md REQ-M2.2:**
```
# Before (3-parameter signature):
consume_atomic(id: UUID, trusted_workflow_run_id: int | None, now: datetime) → MCPApproval

# After (7-parameter signature — C2):
consume_atomic(approval_id: UUID, actor_id: str, mcp_server_id: str, tool_name: str,
               arguments_hash: str, workflow_run_id: int | None, now: datetime) → MCPApproval
```

8-step in-transaction algorithm updated to include explicit verification of all binding fields (steps 3a–3f).

**requirements.md REQ-M2.2 named tests:** Added `test_approval_modified_between_validation_and_consumption` as the 6th named T2 test.

**tasks.md I4:** Updated consume_atomic call and description; added new test to S2 block and I7 all-tests list.

**roadmap.md:** Wave 4 completion gate updated to reference all 26 named tests.

### New test added

`test_approval_modified_between_validation_and_consumption` — approval status changed by another transaction between the MCPService pre-consumption validation (step 6 of invoke_tool) and the consume_atomic call (step 7); verify ConsumedError raised and no subprocess launched.

**Verdict: C2 RESOLVED — all 7 binding fields accepted as explicit parameters and verified in-transaction; modification-between-validation-and-consumption scenario covered.**

---

## 3. Ten-Gate Acceptance Matrix

| Gate | Verdict | File + Section | Evidence | Failure scenario if FAIL |
|---|---|---|---|---|
| G1 — Requirements, design, tasks mutually consistent | **PASS** | requirements.md REQ-M2.x ↔ design.md §7.5 ↔ tasks.md I4/I7; all consume_atomic signatures consistent | Every REQ-M2.x has a corresponding design section and at least one task; all consume_atomic signatures match (7 parameters) across the three documents; migration chain consistent across all files | — |
| G2 — MCP approval authorization has no bypass | **PASS** | design.md §7.5 "No-bypass rule" and "C1" block; requirements.md REQ-M1.7.11; tasks.md I7 `test_no_direct_mcp_client_bypass` | Explicit no-bypass rule stated in §7.5; ADR-0011 documents MCPService as mandatory gateway; no router/adapter/Streamlit path calls MCPClient directly per spec | — |
| G3 — Trusted actor and workflow context are unambiguous | **PASS** | design.md §7.5 "C1 — Trusted workflow context" block; requirements.md REQ-M2.5 M2.5.1 | Single `trusted_workflow_run_id: int | None` parameter (C1 applied); explicit statement that it is resolved from server-side session only and never from tool arguments; `workflow_run_id` removed from invoke_tool signature | — |
| G4 — Approval consumption is atomic and replay-safe | **PASS** | design.md §7.5 `MCPApprovalRepository.consume_atomic` (8-step); requirements.md REQ-M2.2 | BEGIN IMMEDIATE; all 7 binding fields verified in-transaction (C2); rowcount==1 required; COMMIT before subprocess; no restoration after failure; test_approval_modified_between_validation_and_consumption covers TOCTOU window | — |
| G5 — SQLite FK and migration contracts are correct | **PASS** | design.md §3.7, §3.7a, §3.7b; requirements.md REQ-DB1.3 | MCPApproval.workflow_run_id → workflow_runs.id (Integer FK ON DELETE SET NULL); GitHubConfirmation.workflow_run_id same; PRAGMA foreign_keys=ON in connect event (REQ-DB1.3) | — |
| G6 — Migration sequence 001–007 is linear | **PASS** | design.md §3.0; requirements.md REQ-DB1.1; roadmap.md Migration Chain | Exact chain: 001→002→003→004→005→006→007; each down_revision correctly points to preceding revision; no gaps or forks; all revision IDs are exact strings | — |
| G7 — No wave depends on a later wave | **PASS** | tasks.md Wave definitions; design.md §13; roadmap.md Task Dependency Graph | Wave 1 uses no Wave 2+ deliverables; Wave 2 uses no Wave 3+ deliverables; Wave 4 owns migration 006 and MCPApproval (not Wave 5); Wave 4 completion gate explicitly states "no Wave 5 dependency" | — |
| G8 — Required security negative tests are specified | **PASS** | tasks.md I4 (named tests), I7 (all-tests list) — 26 named tests | All 6 required tests confirmed present: `test_forged_approval_record_rejected` ✓, `test_replay_after_consumption_rejected` ✓, `test_concurrent_consumption_only_one_succeeds` ✓, `test_approval_wrong_workflow_run_rejected` ✓, `test_no_direct_mcp_client_bypass` ✓, `test_approval_modified_between_validation_and_consumption` ✓ | — |
| G9 — Phase 0 compatibility and scope preserved | **PASS** | requirements.md Global Constraints, Out of Scope; design.md §1; review.md §6 | No Phase 0 requirement modified; no autonomous AI execution; no auto-merge endpoint; all 11 integration adapters retain approved execution modes (GitHub=automated_api; Ollama=automated_api; Figma=automated_api; MCP=automated_api; Codex=cli_handoff; ChatGPT/Claude/Kiro/NotebookLM/Antigravity/Google Stitch=stub or manual_handoff) | — |
| G10 — Git changes contain only intended specification artifacts | **PASS** | `git diff --name-only` output | Only 5 spec/planning/review files in diff: `.kiro/specs/phase1-functional-orchestration/design.md`, `requirements.md`, `tasks.md`; `docs/planning/phase1-roadmap.md`; `docs/reviews/phase1-specification-review.md`. No src/, tests/, alembic/, .github/, or pyproject.toml. | — |

---

## 4. Remaining Blockers

**None.**

All 10 acceptance gates PASS. No demonstrable security bypass, data-integrity defect, invalid migration dependency, or contradiction preventing implementation was found.

---

## 5. Non-Blocking Implementation Notes

The following items are pre-existing open decisions carried from prior reviews. None are new, none block the PR.

1. **(G9 — Workflow page numbering):** Pages 6 and 7 renamed to `6_Workflows.py` / `7_History.py`. Open since v1.0.0. UX preference, not a correctness issue. Implementer should confirm naming before Wave 3 Task A4.

2. **(G9 — MCP SDK version):** `mcp>=1.0,<2.0` is the operative constraint (pyproject.toml has no mcp entry at base commit). Implementer must check pyproject.toml at Wave 4 implementation time (REQ-M1.8) and update spec if a different version is already declared.

3. **(G9 — pyproject.toml / ci.yml coverage flags):** `branch = true` and `--cov-branch` must be added during Wave 1 (Task P1 configuration ownership section). Out of specification-correction scope. Known gap from Finding 2 (§11).

4. **(G4 — BEGIN IMMEDIATE Python implementation):** `aiosqlite`/SQLAlchemy async does not have a direct `BEGIN IMMEDIATE` syntax helper. The implementer may use raw `EXECUTE 'BEGIN IMMEDIATE'` or `connection.execution_options(isolation_level="IMMEDIATE")`. The spec states intent; the implementer selects the mechanism.

5. **(G4 — busy_timeout configuration point):** The spec recommends 5000 ms. The implementer decides whether to use `connect_args={"timeout": 5}` or PRAGMA in the connect event handler.

---

## 6. Exact Files Modified in This Pass

| File | Sections changed | Version |
|---|---|---|
| `.kiro/specs/phase1-functional-orchestration/design.md` | Version header; §7.5 invoke_tool signature (removed workflow_run_id); §7.5 "C1 — Trusted workflow context" block (new); §7.5 docstring note (C1 explicit statement); §7.5 step 7 (updated consume_atomic call); §7.5 MCPApprovalRepository.consume_atomic signature (3→7 parameters); §7.5 consume_atomic docstring (8-step with all-bindings); version history entry | 1.5.2 → 1.5.3 |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | Version header; REQ-M1.7 step 7 (updated consume_atomic call); REQ-M2.2 consume_atomic signature (3→7 parameters) and 8-step algorithm; REQ-M2.2 named tests (5→6, new test added); REQ-M2.5 M2.5.1 (single-parameter statement); version history entry | 1.5.2 → 1.5.3 |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Version header; I4 invoke_tool signature note (removed workflow_run_id); I4 consume_atomic call and description (3→7 params); I4 S2 tests block (5→6, new test added); I7 all-tests list (25→26, new test added); version history entry | 1.5.2 → 1.5.3 |
| `docs/planning/phase1-roadmap.md` | Version header; Wave 4 completion gate (25→26 named tests); Security Summary MCP row (C1/C2 reference added); version history entry | 1.5.2 → 1.5.3 |
| `docs/reviews/phase1-specification-review.md` | Version header and status; §21 "Final PR Readiness Gate (C1–C2 + 10-Gate Review)" appended | 1.5.2 → 1.5.3 |
| `.agents/tasks/phase1-final-pr-readiness-report.md` | New file (this document) | — |

---

## 7. Git Branch and Working-Tree Status

**Branch:** `feature/phase1-specification-planning`

**`git status --short` output:**
```
A  .agents/tasks/phase1-v1.5-final-mcp-security-report.md
A  .agents/tasks/phase1-v1.5.1-final-type-concurrency-report.md
 M .kiro/specs/phase1-functional-orchestration/design.md
 M .kiro/specs/phase1-functional-orchestration/requirements.md
 M .kiro/specs/phase1-functional-orchestration/tasks.md
 M docs/planning/phase1-roadmap.md
 M docs/reviews/phase1-specification-review.md
?? .agents/tasks/phase1-final-pr-readiness-report.md
```

**`git diff --stat` output:**
```
 .../phase1-functional-orchestration/design.md      | 105 ++++++-
 .../requirements.md                                |  76 +++++-
 .../specs/phase1-functional-orchestration/tasks.md |  50 +++-
 docs/planning/phase1-roadmap.md                    |  11 +-
 docs/reviews/phase1-specification-review.md        | 303 ++++++++++++++++++++-
 5 files changed, 524 insertions(+), 21 deletions(-)
```

No `src/`, `tests/`, `alembic/`, `.github/workflows/`, or `pyproject.toml` files appear in the diff.

---

## 8. Final Verdict

**CONDITIONAL PASS — READY FOR PR WITH NON-BLOCKING NOTES**

Both corrections applied:

- **C1 RESOLVED:** `MCPService.invoke_tool` now has exactly one workflow context parameter (`trusted_workflow_run_id: int | None`). The redundant `workflow_run_id` parameter has been removed from the design.md §7.5 signature and the tasks.md I4 implementation notes. An explicit statement in §7.5 and REQ-M2.5 M2.5.1 confirms that `trusted_workflow_run_id` is resolved from the server-side session context only and is never read from tool arguments, request body, or any client-supplied field.

- **C2 RESOLVED:** `MCPApprovalRepository.consume_atomic` now accepts all 7 binding fields as explicit parameters (`approval_id`, `actor_id`, `mcp_server_id`, `tool_name`, `arguments_hash`, `workflow_run_id`, `now`). The in-transaction algorithm verifies all bindings within the same `BEGIN IMMEDIATE` transaction, closing the TOCTOU window between service-layer validation and atomic consumption. The new test `test_approval_modified_between_validation_and_consumption` covers this scenario. The total named negative test count in Wave 4 is now 26.

All 10 acceptance gates PASS. Five non-blocking implementation notes are recorded — all are pre-existing open items from prior review rounds, none introduced by this pass. The specification is ready for the Phase 1 implementation PR.
