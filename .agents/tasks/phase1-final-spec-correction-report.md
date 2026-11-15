# Phase 1 Final Specification Correction Report

**Version:** 1.0.0
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Preceding reports:**
- `.agents/tasks/phase1-spec-correction-report.md` (v1.1.0, 8 findings)
- `.agents/tasks/phase1-spec-amendments-report.md` (v1.2.0, 5 amendments)

---

## 1. Findings and Exact Corrections

### F1 — Wave 1 FK test dependencies (HIGH)

**Original problem:** Wave 1 Task P6 required three tests that reference `WorkflowRun` and `WorkflowAuditLog` tables — both Wave 2 deliverables. This made Wave 1 independently unsatisfiable: running the P6 test suite before Wave 2 is merged would fail because the tables do not exist. The specific tests: `test_cascade_delete_enforced` (WorkflowRun cascade), `test_set_null_enforced` (WorkflowAuditLog SET NULL), `test_insert_invalid_foreign_key_raises_integrity_error` (WorkflowRun with bad workflow_id). REQ-DB1.3 acceptance criteria DB1.3.3–DB1.3.5 all referenced Wave 2 tables.

**Exact fix applied:**
1. Removed the three Wave 2 table-dependent FK tests from Task P6 required test cases.
2. Added two Wave-1-only FK tests to Task P6:
   - `test_wave1_cascade_delete_enforced` — cascades using only Wave 1 tables (or in-memory FK verification)
   - `test_wave1_insert_invalid_foreign_key_raises_integrity_error` — uses Wave 1 table FK
3. Added the original three FK tests to Task W6 required test cases (with new acceptance criterion labels DB1.3.5–DB1.3.7).
4. Updated REQ-DB1.3 acceptance criteria: Wave 1 criteria are DB1.3.1–DB1.3.4 (PRAGMA test + Wave 1 FK tests); Wave 2 criteria are DB1.3.5–DB1.3.7 (WorkflowRun/WorkflowAuditLog tests), deferred to W6.
5. Added explicit note in P6 "Note on FK tests moved to Wave 2 (F1 correction)".

**Documents + sections updated:**
- `requirements.md` — REQ-DB1.3 acceptance criteria (split into Wave 1 and Wave 2 sets)
- `tasks.md` — Task P6 required test cases; Task W6 required test cases

---

### F2 — GitHubConfirmation persistence (HIGH)

**Original problem:** The `GitHubConfirmation` record was designed as a Pydantic `BaseModel` for in-memory use (design.md §8.2). The amendment report (`.agents/tasks/phase1-spec-amendments-report.md` §4, item 3) explicitly listed this as an open unresolved decision: "Reviewer should confirm whether database persistence is required (adds migration 006) or in-memory is acceptable for Phase 1." Decision: SQLite-backed persistence is mandatory. In-memory storage means confirmations are lost on service restart, concurrent duplicate-consumption cannot be prevented atomically, and the audit trail is incomplete.

**Exact fix applied:**

**requirements.md:**
- REQ-G1.4: Added persistence requirement paragraph specifying SQLAlchemy model + `GitHubConfirmationRepository` + migration 006. Added atomic `consume_atomic` specification. Added configurable TTL (`Settings.GITHUB_CONFIRMATION_TTL_SECONDS: int = 600`). Added concurrent duplicate-consumption prevention requirement. Added recovery/idempotency policy. Added "Never treat a client-supplied boolean as sufficient authorization." Added 6 new named acceptance criteria (G1.4.9–G1.4.14).
- REQ-DB1.1: Added migration 006 to the chain table; updated revision chain to `001 → 002 → 003 → 004 → 005 → 006`; updated DB1.1.1 to reference all 5 Phase 1 migrations.

**design.md:**
- §3.0: Added migration 006 to the migration sequence diagram and table.
- §3.7a (new section): Full `github_confirmations` SQL DDL, SQLAlchemy `GitHubConfirmation` model definition, `GitHubConfirmationRepository` interface (`get_by_id`, `create`, `consume_atomic`), and persistence rationale.
- §8.2: Updated `GitHubConfirmation` from Pydantic `BaseModel` to SQLAlchemy model; added SUPERSEDED label on old in-memory definition; added `consume_atomic` atomic update specification.
- §19: Updated REQ-DB1.1 task IDs to include G1.

**tasks.md:**
- G1 (expanded): Now includes `GitHubConfirmation` SQLAlchemy model, `GitHubConfirmationRepository`, and migration 006 as deliverables. Added full migration 006 content with exact `revision` and `down_revision` strings. Added 10 acceptance criteria (including migration 006 round-trip).
- G2: Updated key implementation notes to specify SQLite persistence and atomic `consume_atomic` (not in-memory). Added 6 new named tests (F2 requirement): `test_github_confirmation_persisted_to_db`, `test_confirmation_expires_after_ttl`, `test_replay_rejected_after_use`, `test_parameter_mismatch_rejected`, `test_concurrent_consumption_safe`, `test_recovery_after_github_api_failure`.
- G5: Added migration 006 round-trip to required test cases; added AC7 (migration 006 applied) and AC8 (all 6 confirmation tests pass).

**roadmap.md:**
- Migration chain section: Updated from 4 to 5 Phase 1 migrations, showing 006.
- Wave 5 completion gate: Added migration 006 applied and all 6 confirmation tests as gate requirements.

---

### F3 — MCP authorization consistency (MEDIUM)

**Original problem:** The MCP authorization sequence was described in several places but never stated as a mandatory 8-step sequence. The roadmap security summary table listed only "Tool in `MCPServerConfig.allowed_tools`" as the authorization mechanism for MCP tool calls, implying allow-list alone is sufficient — which is incorrect for consequential/unknown tools, which also require human approval.

**Exact fix applied:**

**requirements.md REQ-M1.7:**
- Added explicit mandatory 8-step authorization sequence (numbered 1–8) covering: server config check, allow-list check, classification, default-unknown-to-consequential, ApprovalRecord requirement, expiry/mismatch/missing rejection handling, MCPService gateway enforcement, audit event recording.
- Added clarification block: "Allow-list alone is NOT sufficient for consequential tool execution."
- Updated acceptance criteria to include M1.7.7 (allow-list ≠ sufficient negative test) and M1.7.8 (`test_expired_mcp_approval_emits_approval_expired_event`).

**design.md §7.5:**
- Updated `MCPService.invoke_tool` docstring to show the full 8-step sequence.
- Clarified: "IMPORTANT: mcp_approval_expired is NOT mcp_approval_denied. Expiry is not a human rejection."
- Note: "allow-list alone is NOT sufficient for consequential tools."

**roadmap.md Security Summary:**
- Updated MCP row from: "Tool in `MCPServerConfig.allowed_tools`" to: "(1) Tool in `MCPServerConfig.allowed_tools` AND (2) `ApprovalRecord` validated by `MCPService` for consequential/unknown tools" with note: "Allow-list alone is NOT sufficient for consequential/unknown tools; both checks are additive and sequential (F3 correction)".

**tasks.md:**
- I4: Added `test_allowlist_alone_insufficient_for_consequential_tool` to named tests.
- I7: Added the same test to all test cases.

---

### F4 — Superseded review guidance (MEDIUM)

**Original problem:** The review document (§9 and §11 Finding 7) contained `confirmed=True` language that was superseded by Amendment 2 but was not explicitly labelled as superseded.

**Exact fix applied:**

**review.md §9 item 5:** Added "SUPERSEDED — see §15 (Final Correction Pass)" label; struck through `confirmed=True` reference with ~~strikethrough~~.

**review.md §11 Finding 7:** Added historical note: "HISTORICAL — see §15 (Final Correction Pass) for current state." Added explanation that the `confirmed=True` language was superseded by Amendment 2 and further updated in F3. Struck through `confirmed=True` reference in resolution text.

**Scan for remaining active `confirmed=True` language:**
- `requirements.md`: No matches — clean.
- `design.md`: No matches in active sections — the §8.2 SUPERSEDED label is correctly historical.
- `tasks.md`: No matches for `confirmed=True`; one reference to `confirmed: bool` in G2 key implementation notes is correctly stated as "not `confirmed: bool`".
- `roadmap.md`: No matches — MCP row already corrected by F3.

---

### F5 — Document metadata (LOW)

**Original problem:** All five spec documents showed fabricated/placeholder `Last Updated` dates (`2025-01-21` or `2026-11-14`). No version history entry existed for this correction pass.

**Exact fix applied:**
- Updated `Last Updated` in all five documents to: `[current correction pass — implementer fills date at commit time]`
- Added `Version: 1.3.0` to all five documents.
- Added version history block to requirements.md, design.md, tasks.md, roadmap.md with entry: `v1.3.0 — Final specification correction: F1–F5 and D1–D4 applied`
- Updated `Supersedes` field to reference the correction report.

---

### D1 — Streamlit navigation (VERIFIED — no change needed)

**Finding to verify:** Pages 6 and 7 must reference `6_Workflows.py` and `7_History.py`.

**Result:** All documents already use the correct filenames:
- `requirements.md` REQ-U1.2.1: `src/devflow_ui/pages/6_Workflows.py` ✅
- `requirements.md` REQ-U1.3.1: `src/devflow_ui/pages/7_History.py` ✅
- `design.md` §12.1 page inventory: `6_Workflows.py`, `7_History.py` ✅
- `tasks.md` A4 deliverables: `6_Workflows.py`, `7_History.py` ✅

No change required.

---

### D2 — MCP binary trust (APPLIED)

**Finding:** The exact D2 trust statement was not present verbatim in design.md.

**Exact fix applied:**

**design.md §7.6:** Added the exact D2 statement as a labelled block:
> "For Phase 1, operator-configured MCP server binaries are trusted within the documented local single-user threat model. Environment-variable scoping is not an OS-level sandbox. Untrusted MCP binaries must not be executed. OS-level sandboxing (seccomp, namespaces, AppArmor) is deferred to a future phase."

**design.md §14.4:** Added `D2 exact statement` label to the same statement in the subprocess isolation section.

---

### D3 — GitHub confirmations (COVERED BY F2)

**Finding:** SQLite persistence is mandatory with migration 006 in Wave 5. Covered entirely by F2 above. See F2 for all evidence citations.

---

### D4 — MCP approval expiry audit event (APPLIED)

**Finding:** `mcp_approval_expired` and `mcp_approval_missing` were not defined as distinct audit events. The only event distinguishing expiry from denial was `mcp_approval_denied`, which silently conflated expiry with explicit human rejection.

**Exact fix applied:**

**requirements.md REQ-W1.7:** Updated audit event table to include:
- `mcp_approval_denied` — "explicitly rejected by a human approver (NOT expiry — expiry emits mcp_approval_expired)"
- `mcp_approval_expired` — "TTL timeout, NOT a human rejection"
- `mcp_approval_missing` — "No ApprovalRecord found"
Updated W1.7.8 to reference all 7 events and add: "mcp_approval_denied MUST NOT be emitted on expiry."

**requirements.md REQ-M1.7:** Updated audit event table to include all 7 events with "Distinct from" notes. Added M1.7.4 note (expired → `mcp_approval_expired`, NOT `mcp_approval_denied`). Added M1.7.8: `test_expired_mcp_approval_emits_approval_expired_event`.

**design.md §7.5:** Updated `MCPService` audit event table to 7 events with "Distinct from" column. Clarified Step 6: "IMPORTANT: mcp_approval_expired is NOT mcp_approval_denied."

**design.md §16:** Updated required audit event types table to include `mcp_approval_expired` and `mcp_approval_missing` with explicit "(NOT expiry)" and "(NOT mcp_approval_denied)" notes.

**tasks.md I4:** Added to named tests:
- `test_expired_mcp_approval_emits_approval_expired_event` (D4)
- `test_missing_approval_emits_approval_missing_event` (D4)

**tasks.md I7:** Added the same two tests to all test cases.

---

## 2. Files and Sections Changed

| File | Sections modified |
|---|---|
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | Header (version/date), REQ-DB1.3 (split criteria F1), REQ-DB1.1 (migration 006 F2), REQ-G1.4 (persistence + 6 named tests F2), REQ-W1.7 (7 MCP audit events D4), REQ-M1.7 (8-step sequence + 7 events F3/D4) |
| `.kiro/specs/phase1-functional-orchestration/design.md` | Header (version/date), §3.0 (migration 006 chain F2), §3.7a (new — github_confirmations DDL + model F2), §7.5 (8-step invoke_tool + 7 audit events F3/D4), §7.6 (D2 exact trust statement), §8.2 (SQLAlchemy model + SUPERSEDED label F2), §14.4 (D2 label), §16 (7 MCP audit events D4), §19 (REQ-DB1.1 task IDs) |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Header (version/date), Task P6 (Wave-1-only FK tests F1), Task W6 (3 FK tests added F1), Task G1 (expanded with model + migration 006 F2), Task G2 (atomic consume_atomic + 6+6 named tests F2), Task G5 (migration 006 round-trip + 6 confirmation tests + AC7/AC8 F2), Task I4 (3 new named tests F3/D4), Task I7 (3 new test cases F3/D4) |
| `docs/planning/phase1-roadmap.md` | Header (version/date), Alembic Migration Chain (006 added F2), Wave 5 completion gate (migration 006 + 6 confirmation tests F2), Security Summary MCP row (F3) |
| `docs/reviews/phase1-specification-review.md` | Header (version/date/status), §9 item 5 (SUPERSEDED label F4), §11 Finding 7 (HISTORICAL label F4), §15 (new — Final Correction Pass F1–F5 D1–D4), Final verdict |
| `.agents/tasks/phase1-final-spec-correction-report.md` | New file — this report |

---

## 3. Updated Migration Chain

```
001_create_initial_tables          (Phase 0 — None)
  └── 002_add_project_tags_column  (Wave 1 — Task P1)
        └── 003_add_workflow_tables  (Wave 2 — Task W2)
              └── 004_add_approval_audit_tables  (Wave 2 — Task W2)
                    └── 005_add_repository_tables  (Wave 2 — Task W2)
                          └── 006_add_github_confirmations  (Wave 5 — Task G1)
```

| Revision ID | `down_revision` | File | Wave | Tables |
|---|---|---|---|---|
| `"001_create_initial_tables"` | `None` | `001_create_initial_tables.py` | Phase 0 | projects, learning_items, integration_configs |
| `"002_add_project_tags_column"` | `"001_create_initial_tables"` | `002_add_project_tags_column.py` | Wave 1 | tags_json column |
| `"003_add_workflow_tables"` | `"002_add_project_tags_column"` | `003_add_workflow_tables.py` | Wave 2 | workflows, workflow_runs |
| `"004_add_approval_audit_tables"` | `"003_add_workflow_tables"` | `004_add_approval_audit_tables.py` | Wave 2 | approval_requests, workflow_audit_log |
| `"005_add_repository_tables"` | `"004_add_approval_audit_tables"` | `005_add_repository_tables.py` | Wave 2 | repository_configs |
| `"006_add_github_confirmations"` | `"005_add_repository_tables"` | `006_add_github_confirmations.py` | Wave 5 | github_confirmations |

---

## 4. Updated Wave Dependencies

| Wave | Depends on | Completion gate |
|---|---|---|
| Wave 1 | Phase 0 complete | `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits 0; migration 002 applied; Projects page renders; Wave-1-only FK tests pass (PRAGMA + Wave 1 cascade) |
| Wave 2 | Wave 1 merged | `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits 0; state machine enforced; `approval_requested` audit logged; migrations 003–005 round-trips pass; **Wave 2 FK tests pass** (WorkflowRun cascade, WorkflowAuditLog SET NULL) |
| Wave 3 | Wave 2 merged | `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits 0; approval 409 enforced; Dashboard no "Phase 0" text |
| Wave 4 | Wave 3 merged | `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits 0; registry.get_live works; MCP permission gate tested; secrets not in logs; subprocess env isolation tested |
| Wave 5 | Wave 4 merged | `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits 0; `mypy --strict src/` exits 0; `ruff check .` exits 0; docs/openapi.json no `/merge`; migration 006 applied (001→006 chain); all 6 GitHubConfirmation tests pass; all Phase 0 tests pass |

---

## 5. Security Decisions

### D2 — MCP Binary Trust
Exact statement (required verbatim in design.md §7.6 and §14.4):
> "For Phase 1, operator-configured MCP server binaries are trusted within the documented local single-user threat model. Environment-variable scoping is not an OS-level sandbox. Untrusted MCP binaries must not be executed. OS-level sandboxing (seccomp, namespaces, AppArmor) is deferred to a future phase."

Implications:
- Operator is responsible for binary trustworthiness.
- DevFlow AI does not verify binary signatures.
- Env-var scoping is Python-level only, not OS-level isolation.
- No seccomp, namespaces, cgroups, or AppArmor in Phase 1.

### D3 — GitHub Confirmations (see F2)
- SQLite-backed `github_confirmations` table (migration 006, Wave 5).
- `GitHubConfirmation` SQLAlchemy model with 9 fields (id UUID, repo_full_name, operation, parameters_hash, actor_id, workflow_run_id nullable FK, issued_at, expires_at, used_at nullable).
- Atomic `consume_atomic` via `UPDATE WHERE used_at IS NULL`.
- Configurable TTL default 10 minutes (`Settings.GITHUB_CONFIRMATION_TTL_SECONDS = 600`).
- Never treat client-supplied boolean as sufficient authorization.

### D4 — MCP Audit Event Distinctions
Three distinct audit events (never collapse):
- `mcp_approval_denied` — a **human** explicitly rejects an `ApprovalRequest` for an MCP tool call. Actor: `"user"`.
- `mcp_approval_expired` — `ApprovalRecord.expires_at` elapsed before consumption. TTL timeout, NOT a human rejection. Actor: `"system"`.
- `mcp_approval_missing` — no `ApprovalRecord` found when a consequential/unknown tool call is attempted. Actor: `"system"`.

Named test required: `test_expired_mcp_approval_emits_approval_expired_event` — verifies expired record emits `mcp_approval_expired`, NOT `mcp_approval_denied`.

---

## 6. Requirements-to-Task Traceability Matrix

| Req ID | Requirement summary | Design section | Task IDs |
|---|---|---|---|
| REQ-P1.1 | POST /projects persists to SQLite | §10.1, §4.1 | P3, P4, P6 |
| REQ-P1.2 | GET /projects with filter + pagination | §10.1, §4.1 | P3, P4, P6 |
| REQ-P1.3 | PUT /projects/{id} partial update, null=skip | §10.1, §4.1 | P3, P4, P6 |
| REQ-P1.4 | DELETE /projects/{id} removes record | §10.1, §4.1 | P3, P4, P6 |
| REQ-P1.5 | ProjectResponse + tags + timestamps | §3.1, §11.1 | P1, P2, P6 |
| REQ-P1.6 | Streamlit Projects page live CRUD | §12.1, §12.2 | P5, P6 |
| REQ-W1.1 | Workflow model | §3.2 | W1, W6 |
| REQ-W1.2 | WorkflowRun model + 6 states (no paused) | §3.3, §9 | W1, W6 |
| REQ-W1.3 | ApprovalRequest model | §3.4 | W1, W6 |
| REQ-W1.4 | Workflow CRUD endpoints | §10.2 | A1, A5 |
| REQ-W1.5 | WorkflowRun create + manage; no autonomous exec | §10.2, §9 | W3, W5, A1, A5 |
| REQ-W1.6 | Approval resolve endpoints | §10.3, §5.2 | W4, W5, A2, A5 |
| REQ-W1.7 | WorkflowAuditLog + 7 MCP events (D4 adds expired/missing) | §3.5, §16 | W1, W4, W5, W6 |
| REQ-I1.1 | GitHubAdapter live | §8.1, §6 | I2, I5, I7 |
| REQ-I1.2 | OllamaAdapter live | §6.1, §6.2 | I3, I5, I7 |
| REQ-I1.3 | FigmaAdapter live | §6.1, §6.2 | I3, I5, I7 |
| REQ-I1.4 | Registry get_live / fallback | §6 | I5, I7 |
| REQ-I1.5 | IntegrationExecutionError → 502 | §15 | I1, A3, I7 |
| REQ-I1.6 | Integrations page live status | §12.1 | I6, I7 |
| REQ-M1.1 | MCPServerConfig model | §7.1 | I4, I6, I7 |
| REQ-M1.2 | MCPClient subprocess + SIGTERM/SIGKILL | §7.2 | I4, I7 |
| REQ-M1.3 | MCP tool call structured logging (keys only) | §7.2, §16 | I4, I7 |
| REQ-M1.4 | MCP allowed_tools permission control | §7.1 | I4, I7 |
| REQ-M1.5 | MCP secret interpolation + env isolation | §14.4, §7.1 | I4, I7 |
| REQ-M1.6 | MCPLiveAdapter / MCPStubAdapter fallback | §6, §7.2 | I4, I5, I7 |
| REQ-M1.7 | MCP 8-step auth + 7 audit events (F3/D4 updated) | §7.5 | I4, I7 |
| REQ-M1.8 | MCP SDK version constraint + lockfile + offline tests | §7.6 | I4 |
| REQ-G1.1 | RepositoryConfig model (Wave 5); table created Wave 2 | §3.6, §4.4, §10.4 | G1, G3, G5 |
| REQ-G1.2 | Branch listing + status | §8.1, §10.4 | G2, G3, G5 |
| REQ-G1.3 | PR listing + detail | §8.1, §10.4 | G2, G3, G5 |
| REQ-G1.4 | Branch creation with SQLite GitHubConfirmation gate (F2) | §8.2, §14.1, §10.4, §3.7a | G1, G2, G3, G5 |
| REQ-G1.5 | PR creation with GitHubConfirmation gate; no merge | §8.2, §14.1, §10.4 | G2, G3, G5 |
| REQ-G1.6 | CI status via Check Runs API | §8.1, §10.4 | G2, G3, G5 |
| REQ-U1.1 | Dashboard live metrics | §12.1 | A4, A5 |
| REQ-U1.2 | Workflows page (6_Workflows.py — D1 verified) | §12.1 | A4, A5 |
| REQ-U1.3 | History page (7_History.py — D1 verified) | §12.1 | A4, A5 |
| REQ-U1.4 | APIClient extension for all Phase 1 endpoints | §12.2 | P5, A4, I7, G4 |
| REQ-U1.5 | Settings page Phase 1 config summary | §12.1 | I6, I7, G4, G5 |
| REQ-DB1.1 | 6 migrations: 001–006, exact revision IDs + chain (F2) | §3.0 | P1, W2, G1, G5 |
| REQ-DB1.2 | Migration 002 adds tags_json, applies from Phase 0 head | §3.1 | P1, P6 |
| REQ-DB1.3 | PRAGMA FK=ON; Wave 1 tests use Wave 1 tables only (F1) | §3.7 | P1, P6 (Wave 1), W6 (Wave 2) |
| REQ-S1.1 | GitHubConfirmation gates; credential ≠ authorization | §14.1, §14.2 | A3, G2, G3, G5, W5, W6 |
| REQ-S1.2 | Bounded timeouts; timeout test named in I7 | §8.1, §17 | I2, I3, I4, I6, I7 |
| REQ-S1.3 | Secrets not in logs; token test named in I7 | §14.3, §16 | I2, I3, I4, I7 |
| REQ-S1.4 | No /merge endpoint | §10.4, §18 ADR-0005 | G3, G5 |
| REQ-S1.5 | MCP env isolation (env-var scope only); subprocess env test | §14.4 | I4, I7 |
| REQ-T1.1 | 80% branch coverage; canonical pytest command | §13 test file list | P6, W6, A5, I7, G5 |
| REQ-T1.2 | AppTest smoke tests for all Phase 1 pages | §13 test file list | P6, A5, I7, G5 |
| REQ-T1.3 | Migration round-trip integration tests | §13 | P6, W6, G5 |
| REQ-T1.4 | Phase 0 tests continue to pass | §17 | P6, W6, A5, I7, G5 |

---

## 7. Remaining Risks or Unresolved Decisions

| Risk/Decision | Severity | Notes |
|---|---|---|
| `pyproject.toml` and `ci.yml` not in scope | Low | `branch = true` must be added to `[tool.coverage.run]` and `--cov-branch` to CI pytest command at implementation time (Wave 1, Task P1). Already noted in tasks.md P1 configuration ownership. |
| `MCP_SERVERS_CONFIG` already in Phase 0 `pyproject.toml` | Low | Task I6 notes that if `mcp` is already declared in `pyproject.toml`, that version takes precedence. Implementer must check at Wave 4. |
| `consume_atomic` SQLite concurrency | Medium | SQLite WAL mode + row-level `UPDATE WHERE used_at IS NULL` provides sufficient atomicity for single-node local use. Concurrent test must verify this works under asyncio concurrency. |
| `workflow_run_id` FK in `github_confirmations` | Low | The `github_confirmations.workflow_run_id` FK uses `ON DELETE SET NULL`. If a workflow run is deleted, the confirmation record remains but loses its run binding. This is correct for audit purposes — the confirmation record should be preserved. |
| All 11 integration adapters retain approved execution modes | Verified | No change to adapter modes in this correction pass. |
| Phase 1 non-autonomous execution boundary | Verified | No correction changes `definition_json` execution scope — still deferred to Phase 2. |
| No Android/React/TypeScript/Vite | Verified | Global constraint unchanged. |

---

## 8. Git Diff Summary

```
 .kiro/specs/phase1-functional-orchestration/design.md      | 672 ++++++++++++++++++---
 .kiro/specs/phase1-functional-orchestration/requirements.md | 305 ++++++++--
 .kiro/specs/phase1-functional-orchestration/tasks.md        | 358 ++++++++---
 docs/planning/phase1-roadmap.md                             | 101 +++-
 docs/reviews/phase1-specification-review.md                 | 493 +++++++++++++--
 5 files changed, 1653 insertions(+), 276 deletions(-)
```

No `src/`, `tests/`, `alembic/`, `.github/workflows/`, or `pyproject.toml` files modified. Only specification and planning files changed.

---

## 9. Final Readiness Verdict

**READY FOR FINAL INDEPENDENT REVIEW**

All five corrections (F1–F5) applied. All four architectural decisions (D1–D4) applied or verified. All eight prior findings (§11) remain resolved. All five prior amendments (§13) remain resolved. Cross-document consistency verified:

| Check | Result |
|---|---|
| Every requirement has unique ID and testable acceptance criteria | ✅ PASS |
| Every requirement maps to at least one design section | ✅ PASS |
| Every design component maps to at least one task | ✅ PASS |
| Every security requirement has at least one named negative test | ✅ PASS |
| Migration chain exactly 001→002→003→004→005→006, no gaps | ✅ PASS (F2 adds 006) |
| Wave 1 tasks reference only Wave 1 tables | ✅ PASS (F1 corrects P6) |
| Wave 2+ tables not referenced in Wave 1 tasks | ✅ PASS (F1 moves tests to W6) |
| Each wave's completion gate independently satisfiable | ✅ PASS |
| Phase 1 WorkflowRun execution non-autonomous | ✅ PASS |
| No automatic GitHub PR merging | ✅ PASS |
| All 11 integration adapters retain approved execution modes | ✅ PASS |
| Coverage gate consistent: `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` | ✅ PASS |
| No Android/React/TypeScript/Vite | ✅ PASS |
| No `confirmed=True` boolean as authorization gate remaining anywhere in active sections | ✅ PASS |
| D2 exact trust statement present in design.md | ✅ PASS |
| D4 audit event distinctions (denied/expired/missing) defined and tested | ✅ PASS |
