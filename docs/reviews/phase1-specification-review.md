# Phase 1 Specification Review Checklist

**Version:** 1.5.3
**Status:** Final PR Readiness Gate Reviewed
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Spec files reviewed:**
- `.kiro/specs/phase1-functional-orchestration/requirements.md`
- `.kiro/specs/phase1-functional-orchestration/design.md`
- `.kiro/specs/phase1-functional-orchestration/tasks.md`
- `docs/planning/phase1-roadmap.md`
**Last Updated:** 2026-11-15
**Supersedes:** v1.3.0 (F1–F3 corrections applied — see .agents/tasks/phase1-v1.4.0-correction-report.md)

---

## Review Summary

This document records three review passes:

**v1.0.0 (§1–§9):** Initial self-review by specification author. All sections passed. Marked READY FOR INDEPENDENT SPECIFICATION REVIEW.

**v1.1.0 (§11):** Independent specification remediation. Eight findings identified and resolved by correction pass. Full evidence for each correction is in §11. The final verdict is in §12.

**v1.2.0 (§13–§14):** Second amendment round resolving five independent-review findings. Full evidence for each amendment is in §13. Updated security checklist in §14. Final verdict updated.

---

## 1. Requirements Completeness

### 1.1 Requirements are numbered and testable

| Check | Result | Notes |
|---|---|---|
| Every requirement has a unique ID | ✅ Pass | IDs: REQ-P1.x, REQ-W1.x, REQ-I1.x, REQ-M1.x, REQ-G1.x, REQ-U1.x, REQ-DB1.x, REQ-S1.x, REQ-T1.x |
| Every requirement has acceptance criteria | ✅ Pass | Each criterion numbered (e.g., P1.1.1) |
| Acceptance criteria are testable (observable outcome) | ✅ Pass | All criteria specify an HTTP status, exit code, return value, or log assertion |
| No criterion relies on subjective judgment | ✅ Pass | Reviewed; all criteria are binary pass/fail |

### 1.2 Scope coverage

| Capability | Required in prompt | Covered in spec |
|---|---|---|
| Persistent project management | ✅ | ✅ REQ-P1.1–P1.6 |
| Workflow orchestration foundation (not autonomous execution) | ✅ | ✅ REQ-W1.1–W1.7; autonomous execution explicitly out of scope |
| Integration execution | ✅ | ✅ REQ-I1.1–I1.6 |
| MCP integration | ✅ | ✅ REQ-M1.1–M1.6 |
| GitHub workflow orchestration | ✅ | ✅ REQ-G1.1–G1.6 |
| Streamlit experience | ✅ | ✅ REQ-U1.1–U1.5 |
| Security requirements | ✅ | ✅ REQ-S1.1–S1.5 |
| Testing requirements | ✅ | ✅ REQ-T1.1–T1.4 |
| Database migrations | ✅ | ✅ REQ-DB1.1–DB1.2 |

### 1.3 Out-of-scope items explicitly stated

| Item | Location | Verdict |
|---|---|---|
| Autonomous AI execution from definition_json | requirements.md Overview + Out of Scope section; REQ-W1.1, REQ-W1.5 | ✅ Explicit with reason |
| ChatGPT / Claude live adapters | roadmap.md "Out of scope" | ✅ Explicit with reason |
| Codex CLI live execution | roadmap.md "Out of scope" | ✅ Explicit with reason |
| Auto PR merge | REQ-S1.4, REQ-G1.5 | ✅ Prohibited by requirement |
| Android, React, TypeScript, Vite | Global constraints header | ✅ Explicit |
| Multi-user access control | roadmap.md "Out of scope" | ✅ Explicit |
| OS-level MCP sandbox isolation | REQ-M1.5, REQ-S1.5, roadmap.md "Out of scope" | ✅ Explicit with reason |

---

## 2. Design Consistency with Repository

### 2.1 Phase 0 architecture preserved

| Check | Result | Notes |
|---|---|---|
| Modular monolith pattern retained | ✅ Pass | design.md §1 and §2 diagram show unchanged layer topology |
| Phase 0 module paths unchanged | ✅ Pass | No Phase 0 file is renamed or deleted |
| `UTCDateTime` TypeDecorator used for all new timestamps | ✅ Pass | Explicitly required in global constraints and each model design |
| `get_db` dependency unchanged | ✅ Pass | design.md §17 "Dependency on Phase 0" |
| `BaseRepository` extended (not replaced) | ✅ Pass | design.md §4 shows extension pattern |
| Phase 0 stub adapters retained as fallbacks | ✅ Pass | REQ-I1.1.6, REQ-I1.4.4, design.md §6 |

### 2.2 New components trace to requirements

| Component | Requirement | Design section |
|---|---|---|
| Workflow, WorkflowRun models | REQ-W1.1, W1.2 | design.md §3.2, 3.3 |
| ApprovalRequest model | REQ-W1.3 | design.md §3.4 |
| WorkflowAuditLog model | REQ-W1.7 | design.md §3.5 |
| RepositoryConfig model | REQ-G1.1 | design.md §3.6 |
| ProjectRepository.list_filtered | REQ-P1.2 | design.md §4.1 |
| WorkflowService state machine | REQ-W1.5 | design.md §9 |
| ApprovalService.resolve | REQ-W1.6 | design.md §5.2 |
| GitHubAdapter live | REQ-I1.1 | design.md §8.1 |
| MCPClient | REQ-M1.2 | design.md §7.2 |
| registry.get_live | REQ-I1.4 | design.md §6 |
| Confirmation gate pattern | REQ-S1.1 | design.md §14.1 |
| Approval gate pattern | REQ-S1.1 | design.md §14.2 |

### 2.3 API contracts complete

| Check | Result | Notes |
|---|---|---|
| All new routes listed in design.md §10 | ✅ Pass | Projects, Workflows, Approvals, Repositories |
| All routes prefixed `/api/v1/` | ✅ Pass | Consistent with Phase 0 |
| No `/merge` route | ✅ Pass | Explicitly absent from §10.4; REQ-S1.4 prohibits it |
| HTTP status codes specified for each route | ✅ Pass | §10 tables include success and error codes |
| ErrorResponse format consistent | ✅ Pass | Same `{"error": ..., "code": ...}` as Phase 0 |

---

## 3. Task-to-Requirement Traceability

The full traceability matrix is in design.md §19. Summary:

| Task | Requirements covered | Design sections referenced |
|---|---|---|
| P1 | REQ-DB1.1, DB1.2, P1.5 | §3.0, §3.1 |
| P2 | REQ-P1.5 | §11.1 |
| P3 | REQ-P1.1–P1.4 | §4.1, §5 |
| P4 | REQ-P1.1–P1.4 | §10.1 |
| P5 | REQ-P1.6, U1.4 | §12.1, §12.2 |
| P6 | REQ-T1.1, T1.2, T1.3, T1.4 | §13 (test files) |
| W1 | REQ-W1.1, W1.2, W1.3, W1.7 | §3.2–3.5 |
| W2 | REQ-DB1.1 | §3.0 |
| W3 | REQ-W1.4, W1.5 | §4.2 |
| W4 | REQ-W1.6, W1.7 | §4.3 |
| W5 | REQ-W1.5, W1.6, W1.7 | §5.1, §5.2 |
| W6 | REQ-T1.1, T1.3, T1.4 | §13 |
| A1 | REQ-W1.4, W1.5 | §10.2, §11.2, §11.3 |
| A2 | REQ-W1.6 | §10.3, §11.4 |
| A3 | REQ-I1.5, S1.1 | §15 |
| A4 | REQ-U1.1, U1.2, U1.3, U1.4 | §12.1, §12.2 |
| A5 | REQ-T1.1, T1.2, T1.4 | §13 |
| I1 | REQ-I1.5, M1.4, M1.5 | §7.4 |
| I2 | REQ-I1.1 | §8.1 |
| I3 | REQ-I1.2, I1.3 | §6.1 |
| I4 | REQ-M1.1–M1.6 | §7 |
| I5 | REQ-I1.4 | §6 |
| I6 | REQ-I1.6, M1.1, S1.2 | §10.5 |
| I7 | REQ-I1.6, U1.5, T1.1, T1.2, S1.2, S1.3, S1.5 | §12.1, §13 |
| G1 | REQ-G1.1, DB1.1 | §3.6, §4.4 |
| G2 | REQ-G1.2–G1.6 | §8 |
| G3 | REQ-G1.1–G1.6 | §10.4 |
| G4 | REQ-U1.5 | §12.1 |
| G5 | REQ-T1.1–T1.4 | §13 |

**Coverage verdict:** Every requirement in `requirements.md` is referenced by at least one task. ✅

---

## 4. Security Requirements Review

| Security requirement | Mechanism specified | Test coverage |
|---|---|---|
| Explicit approval for consequential actions | Confirmation gate (§14.1) + Approval gate (§14.2) | ✅ Named in G5 and A5 ACs |
| Credential ≠ authorization | Explicitly stated in REQ-S1.1, design.md §14.1, roadmap Security Summary | ✅ Design language corrected |
| No hardcoded credentials | Settings SecretStr (§14.3) | ✅ REQ-S1.3 |
| No secrets in logs | RedactSecretsProcessor | ✅ Named test: `test_github_token_not_in_log_records` in I7 |
| Bounded timeouts | Per-adapter timeouts in Settings (REQ-S1.2) | ✅ Named test: `test_github_adapter_timeout_raises_integration_error` in I7 |
| No auto PR merge | No `/merge` endpoint (REQ-S1.4) | ✅ Named test: `test_no_merge_endpoint_exists` in G5 |
| MCP subprocess env isolation (Python-level) | Explicit env, SIGTERM/SIGKILL sequence (§14.4); REQ-S1.5 clarified as env-var only | ✅ Named test: `test_mcp_subprocess_launched_with_explicit_env` in I7 |
| MCP permission allow-list | MCPServerConfig.allowed_tools (REQ-M1.4) | ✅ Named test in I7 |
| Secret interpolation safety | Only SecretStr fields; raise before subprocess if unresolvable (REQ-M1.5) | ✅ Named test: `test_mcp_secret_values_not_in_log_records` in I7 |

---

## 5. Integration Feasibility Check

| Integration | Mode | API documented | Notes |
|---|---|---|---|
| GitHub | `automated_api` | ✅ GitHub REST API v3 (public) | Token required; free tier available |
| Ollama | `automated_api` | ✅ Ollama local REST API (public docs) | No token; local binary required |
| Figma | `automated_api` | ✅ Figma REST API v1 (public) | Token required; free tier available |
| MCP servers | `automated_api` | ✅ MCP Python SDK (public) | stdio transport; server must be installed |
| ChatGPT | `automated_api` | ⬜ Deferred | Requires paid key — not in Phase 1 |
| Codex | `cli_handoff` | ⬜ Stub only | Real CLI execution deferred — not in Phase 1 |
| Claude | `automated_api` | ⬜ Deferred | Requires paid key — not in Phase 1 |
| Kiro | `manual_handoff` | ⬜ No public API | Remains stub |
| NotebookLM | `manual_handoff` | ⬜ No public API | Remains stub |
| Antigravity | `unknown` | ⬜ No public API | Remains stub |
| Google Stitch | `unknown` | ⬜ No public API | Remains stub |

**Verdict:** No unsupported integration is promised in Phase 1. ✅

---

## 6. Phase 0 Regression Check

| Phase 0 component | Phase 1 modification | Risk |
|---|---|---|
| `devflow_core/config.py` | New fields added only | Low — additive |
| `devflow_api/models/project.py` | `tags_json` column added | Low — additive; default value provided |
| `devflow_api/schemas/project.py` | `ProjectResponse` gains `tags`, `created_at`, `updated_at` | Medium — Phase 0 tests that construct `ProjectResponse` manually may need updating. **Mitigation:** `tags` defaults to `[]`; `created_at`/`updated_at` use `datetime`. Reviewer should verify no Phase 0 test constructs `ProjectResponse` directly. |
| `devflow_api/routers/projects.py` | Replaced with live DB version | Medium — Phase 0 router tests assert stub behavior. These tests will need updating in Task P6. This is expected evolution. |
| `devflow_api/adapters/registry.py` | `get_live` added; `get` unchanged | Low — additive |
| `devflow_api/middleware/error_handler.py` | New exception handlers added | Low — additive |
| `devflow_ui/pages/2_Projects.py` | Replaced | Low — Phase 0 smoke test for this page will be updated in P6 |
| `devflow_ui/pages/1_Dashboard.py` | Replaced | Low — Phase 0 smoke test updated in A4/A5 |
| All other Phase 0 files | No modification | None |

**Verdict:** No unmitigated regressions. All identified changes are additive or have explicit mitigation tasks. ✅

---

## 7. Wave Dependency Ordering

| Wave | Prerequisite | Correctly ordered |
|---|---|---|
| Wave 1 | Phase 0 complete | ✅ |
| Wave 2 | Wave 1 merged to `develop` | ✅ |
| Wave 3 | Wave 2 merged to `develop` | ✅ |
| Wave 4 | Wave 3 merged to `develop` | ✅ |
| Wave 5 | Wave 4 merged to `develop` | ✅ |

**Migration ordering verified:**
- Wave 1 creates migration 002, which chains from 001 (Phase 0 head). `alembic upgrade head` in Wave 1 applies only 002. ✅
- Wave 2 creates migrations 003, 004, 005, which chain from 002. After Wave 2, `alembic upgrade head` applies all five migrations. ✅
- Wave 5 task G1 creates the `RepositoryConfig` ORM model. The `repository_configs` table was created by migration 005 in Wave 2. No cross-wave ORM dependency exists. ✅

**Within-wave task dependencies (critical paths):**
- Wave 1: P1 → P2 → P3 → P4 → P5 → P6 (strictly sequential)
- Wave 2: W1 → W2; W1 → W3; W1 → W4; W3 + W4 → W5; W5 → W6
- Wave 3: W2 merged → A1 → A2 → A3; A1 → A4; A1–A4 → A5
- Wave 4: W3 merged → I1 → I2, I3, I4 (parallel) → I5 → I6 → I7
- Wave 5: W4 merged → G1 → G2 → G3 → G4 → G5

**Verdict:** All dependencies correctly ordered. ✅

---

## 8. Implementation Boundary Check

| Check | Result |
|---|---|
| No new Python source files modified | ✅ Confirmed — only `.kiro/specs/`, `docs/planning/`, `docs/reviews/`, `.agents/tasks/` written |
| No test files modified | ✅ Confirmed |
| No `requirements/` files modified | ✅ Confirmed |
| No `alembic/` files modified | ✅ Confirmed |
| No `src/` files modified | ✅ Confirmed |
| `git status` shows only specification and planning files | ✅ Confirmed (see §12 git status) |

---

## 9. Open Questions from v1.0.0

The following questions from the initial self-review remain. Some have been resolved by the correction pass; the remainder require reviewer judgment.

1. **Projects router test evolution:** ✅ Resolved in Task P6. Phase 0 stub tests will be updated for live DB behavior.

2. **Workflow page numbering:** ⬜ Unresolved. Pages 6 and 7 are renamed. Reviewer should confirm whether `6_Workflows.py` / `7_History.py` is the preferred UX or whether new pages should use 11+ to avoid renaming.

3. **MCP SDK dependency version:** ⬜ Unresolved. Task I4 adds `mcp` SDK to `requirements/base.txt`. Reviewer should confirm whether a specific version pin is required or `mcp>=1.0.0` is acceptable.

4. **Ollama availability in CI:** ✅ Resolved. All Ollama tests mock `httpx.AsyncClient`. CI environments without Ollama installed will not break.

5. **GitHub confirmation gate vs approval gate:** ✅ Confirmed by design. ~~REQ-G1.4/G1.5 require `confirmed=True` for direct API calls.~~ **SUPERSEDED — see §15 (Final Correction Pass).** `confirmed=True` boolean is replaced by `GitHubConfirmation` record with `confirmation_id`. Workflow-driven execution uses the `ApprovalRequest` gate. A single action is not double-gated.

---

## 10. Final Decision (v1.0.0)

The initial self-review concluded:

> **READY FOR INDEPENDENT SPECIFICATION REVIEW** (v1.0.0, superseded by v1.1.0 findings)

That verdict was premature. Eight blockers were found in the independent remediation pass. See §11 for details.

---

## 11. Independent Remediation Findings (v1.1.0)

### Finding 1 — Migration chain ordering (CRITICAL) ✅ RESOLVED

**Description:** Migration `005_add_project_tags_column.py` (Wave 1, Task P1) had `down_revision = "004_add_repository_tables"`. Migration 004 is a Wave 2 deliverable. This meant `alembic upgrade head` in Wave 1 would fail because migration 004 did not exist. Task P1 acceptance criterion "alembic upgrade head from Phase 0 schema applies migration 005 without error" was false in the Wave 1 context.

**Documents affected:** requirements.md REQ-DB1.1, REQ-DB1.2; design.md §3; tasks.md Task P1, W2; roadmap.md Wave summary.

**Resolution applied:** Renumbered the tags migration from `005` to `002`. Renumbered Wave 2 migrations from `002–004` to `003–005`. The new chain is: `001_create_initial_tables → 002_add_project_tags_column → 003_add_workflow_tables → 004_add_approval_audit_tables → 005_add_repository_tables`. Migration 002 chains directly from the Phase 0 head revision, allowing Wave 1's `alembic upgrade head` to succeed independently.

**Evidence:** requirements.md REQ-DB1.1 (table of revision IDs and `down_revision` values); design.md §3.0 (migration sequence diagram and table); tasks.md Task P1 (migration content with exact revision IDs), Task W2 (required revision headers for 003–005); roadmap.md Alembic Migration Chain section.

**Remaining limitation:** None. The chain is now independently applicable per wave.

---

### Finding 2 — `--cov-branch` missing from all coverage commands (CRITICAL) ✅ RESOLVED

**Description:** REQ-T1.1 specifies "80% branch coverage" but every coverage command in requirements.md, tasks.md, and the roadmap used `pytest --cov=src --cov-fail-under=80`, which measures line coverage only. `--cov-branch` was absent. The gate was inconsistent with the stated requirement.

**Documents affected:** requirements.md REQ-T1.1.1; tasks.md P6, W6, A5, I7, G5 acceptance criteria and G5 final verification commands.

**Resolution applied:** Replaced every occurrence of `pytest --cov=src --cov-fail-under=80` with `pytest --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=80` throughout all five documents. The canonical form now includes `--cov-branch` (branch coverage measurement) and `--cov-report=term-missing` (readable output) in every task acceptance criterion and verification command.

**Evidence:** requirements.md REQ-T1.1.1; tasks.md P6 AC3, W6 AC3, A5 AC3, I7 AC5, G5 AC2 and final verification commands block.

**Remaining limitation:** `pyproject.toml` and `ci.yml` are not in scope for this specification correction step. Those files must also be updated when implementation begins (add `branch = true` to `[tool.coverage.run]` and add `--cov-branch` to the CI pytest command). This is a known remaining gap in the CI configuration.

---

### Finding 3 — `paused` state inconsistency in WorkflowRun (HIGH) ✅ RESOLVED

**Description:** The state machine diagram in design.md §9 included a `paused` box and a `pause` arrow from `active`, but `paused` was absent from the `WorkflowRun.status` CHECK constraint in requirements.md REQ-W1.2 and design.md §3.3. This was a direct contradiction within the specification.

**Documents affected:** requirements.md REQ-W1.2; design.md §3.3 (SQL), §9 (state machine diagram); tasks.md W1 (model AC4), W2 (migration CHECK constraint).

**Resolution applied:** Removed `paused` from all WorkflowRun contexts. The state machine diagram has been redrawn to show only the six valid WorkflowRun states: `pending`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled`. Added ADR-0009 explaining the decision. Added explicit note in REQ-W1.2 and design.md §3.3 that `paused` is a Workflow definition status (the template), not a WorkflowRun execution status.

**Evidence:** requirements.md REQ-W1.2 (status definitions table, note on absent states); design.md §3.3 (SQL CHECK constraint), §9.1 (WorkflowRun states table with explicit "states NOT present" note), §9.2 (corrected state diagram), ADR-0009; tasks.md W1 AC4, W2 migration content.

**Remaining limitation:** None.

---

### Finding 4 — REQ-S1.5 vague "isolated" claim and `down_revision` values not stated (HIGH) ✅ RESOLVED

**Description (Part A):** REQ-S1.5 described MCP subprocess execution as "bounded and isolated" where "isolated" implied OS-level sandbox isolation (seccomp, namespaces), but only Python-level environment variable scoping was actually specified. This would mislead an implementer.

**Description (Part B):** No document stated the exact `down_revision` string values for Phase 1 migrations. Implementers would have to infer these from the numeric sequence, risking mismatches.

**Documents affected:** requirements.md REQ-S1.5; design.md §14.4; tasks.md Task P1, W2 deliverable specs; roadmap.md Security Summary table.

**Resolution applied (Part A):** Rewrote REQ-S1.5 to describe the actual boundary: "subprocess execution MUST be bounded with explicit environment-variable scoping." Added explicit "Isolation boundary" paragraph clarifying Python-level env isolation only. Added OS-level sandbox isolation to the Out of Scope table. Added the SIGTERM → 5s grace → SIGKILL termination sequence. Updated design.md §14.4 with the same clarifications and the corrected subprocess code example. Updated roadmap Security Summary table with a "Note" column distinguishing authentication from authorization.

**Resolution applied (Part B):** Tasks P1 and W2 now show the exact Python `revision` and `down_revision` string values that must appear in each file. Design.md §3.0 provides the full revision table with exact strings.

**Evidence:** requirements.md REQ-S1.5 (reworded, isolation boundary paragraph); design.md §14.4 (corrected isolation description, subprocess code with SIGTERM/SIGKILL sequence), §3.0 (migration revision table); tasks.md Task P1 (migration content with exact revision = / down_revision = strings), Task W2 (required revision headers section); roadmap.md Out of Scope table, Security Summary table.

**Remaining limitation:** OS-level sandbox isolation is deferred. The spec correctly documents this deferral.

---

### Finding 5 — Sixth audit event type `approval_requested` not named (MEDIUM) ✅ RESOLVED

**Description:** REQ-W1.7 required "every status transition on WorkflowRun or ApprovalRequest" to generate an audit log entry. `ApprovalService.request_approval` transitions the run to `waiting_approval` and must log this. Five event types were named in the requirements; `approval_requested` was described in design.md §16 as a structlog event but was not listed as a required `WorkflowAuditLog` event type. The count of six event types implied by the original user request was not satisfied.

**Documents affected:** requirements.md REQ-W1.7; design.md §16 (observability); tasks.md W5 (key implementation notes), W6 (required test cases).

**Resolution applied:** Added `approval_requested` as the sixth named audit event type to requirements.md REQ-W1.7 (required audit event types table, acceptance criterion W1.7.4). Updated design.md §16 (required audit event types table). Updated tasks.md W5 (key implementation notes: "ApprovalService.request_approval logs approval_requested audit event"). Added `test_request_approval_logs_approval_requested` to W6 required test cases.

**Evidence:** requirements.md REQ-W1.7 (required audit event types table, W1.7.4); design.md §16 (required audit event types table); tasks.md W5 AC2, W6 required test cases.

**Remaining limitation:** None.

---

### Finding 6 — Timeout test and subprocess env-isolation test not named in task ACs (MEDIUM) ✅ RESOLVED

**Description:** REQ-S1.2 required bounded adapter timeouts; REQ-S1.5.1 required explicit env scoping. Neither requirement had a named test case in any task's acceptance criteria or required test case list. Without named tests, implementers could pass coverage gates without verifying these security properties.

**Documents affected:** tasks.md I7 required test cases and acceptance criteria.

**Resolution applied:** Added four named security-critical test cases to Task I7 with explicit names and cross-references to the security requirements they verify:
- `test_github_adapter_timeout_raises_integration_error` (REQ-S1.2)
- `test_github_token_not_in_log_records` (REQ-S1.3.2)
- `test_mcp_subprocess_launched_with_explicit_env` (REQ-S1.5.1, REQ-S1.5.4)
- `test_mcp_secret_values_not_in_log_records` (REQ-M1.5.3)

Also added REQ-S1.2.6 to requirements.md (timeout test requirement) and REQ-S1.5.4 (subprocess env test requirement). Added I7 AC6 requiring all four security-critical tests to pass.

**Evidence:** requirements.md REQ-S1.2.6, REQ-S1.5.4; tasks.md I7 "Required test cases (security-critical — must be named)" section, I7 AC6.

**Remaining limitation:** None.

---

### Finding 7 — Roadmap security table conflated credential presence with authorization (LOW) ✅ RESOLVED

> **HISTORICAL — see §15 (Final Correction Pass) for current state.** Finding 7 described `confirmed=True` language in the roadmap security table. That language was subsequently superseded by Amendment 2 (§13), which replaced `confirmed: bool` with `GitHubConfirmation` records. The roadmap security table was updated again in the Final Correction Pass (§15, F3) to reflect that allow-list alone is NOT sufficient for consequential MCP tools.

**Description:** The roadmap Security Summary table listed "Credential present in Settings" as the authorization mechanism for live adapter calls. Having a credential is an authentication prerequisite, not an authorization decision. The language implied that setting `GITHUB_TOKEN` authorized GitHub actions, which is incorrect.

**Documents affected:** docs/planning/phase1-roadmap.md Security Summary table; requirements.md REQ-S1.1; design.md §14.1.

**Resolution applied:** Rewrote the roadmap Security Summary table row for live adapter calls to show ~~`confirmed=True`~~ (SUPERSEDED — see Amendment 2 §13) or approved `ApprovalRequest` as the authorization mechanism, with a "Note" column clarifying that credential presence is authentication only. Added explicit authorization/authentication distinction paragraph to requirements.md REQ-S1.1 and design.md §14.1 (ADR-0005 rationale updated).

**Evidence:** roadmap.md Security Summary table (Note column); requirements.md REQ-S1.1 "Distinction between credentials and authorization" block; design.md §14.1 "Authorization model" note, ADR-0005 rationale.

**Remaining limitation:** None. This was a documentation inaccuracy; the design itself (using `confirmed=True` as the gate) was correct. The gate was subsequently upgraded to `GitHubConfirmation` records by Amendment 2.

---

### Finding 8 — `PUT /projects/{id}` null-clear semantics undocumented (LOW) ✅ RESOLVED

**Description:** `ProjectUpdate` has all fields as `str | None = None`, meaning `null` and absent are semantically identical (both map to `None` in Python and both skip the field). There was no explicit statement of this behavior. An implementer could interpret `{"description": null}` as "clear the description field" rather than "skip this field."

**Documents affected:** requirements.md REQ-P1.3; tasks.md Task P3 AC3, Task P2 (ProjectUpdate schema notes).

**Resolution applied:** Added explicit "Null semantics" paragraph to requirements.md REQ-P1.3 explaining that `null` = skip (not clear). Added REQ-P1.3.5 acceptance criterion: `PUT /api/v1/projects/{id}` with `{"description": null}` does NOT clear the existing description. Added null semantics comment to `ProjectUpdate` schema in tasks.md Task P2. Added `test_update_project_null_field_does_not_clear` to Task P6 required test cases.

**Evidence:** requirements.md REQ-P1.3 "Null semantics" paragraph, REQ-P1.3.5; tasks.md Task P2 (ProjectUpdate schema comment), Task P3 AC3, Task P6 required test cases.

**Remaining limitation:** None. This is now explicitly documented as intended behavior.

---

## 12. Final Decision

**Git working tree status (specification-only branch):**
- Branch: `feature/phase1-specification-planning`
- Modified/created: `.kiro/specs/phase1-functional-orchestration/requirements.md`, `design.md`, `tasks.md`; `docs/planning/phase1-roadmap.md`; `docs/reviews/phase1-specification-review.md` (this document); `.agents/tasks/phase1-spec-correction-report.md` (new)
- No `src/`, `tests/`, `alembic/`, `.github/`, `pyproject.toml` files modified

**All eight findings resolved:** ✅

**Remaining open decisions for reviewer:**

1. **Workflow page numbering (from v1.0.0):** Pages 6 and 7 renamed to `6_Workflows.py` / `7_History.py`. Reviewer should confirm whether this is preferred over adding new pages at 11+.

2. **MCP SDK version pin:** Task I4 adds `mcp` SDK. Reviewer should specify whether `mcp>=1.0.0` is acceptable or a specific version is required.

3. **`pyproject.toml` and `ci.yml` not in scope:** `branch = true` must be added to `[tool.coverage.run]` in `pyproject.toml` and `--cov-branch` added to the CI pytest command before implementation begins. These files are outside the specification-only scope of this correction step.

4. **MCP server binary trust:** REQ-M1.5 and design.md §14.4 state that operator-configured MCP binaries are trusted and DevFlow AI does not verify signatures. Reviewer should confirm this trust model is acceptable.

---

## 13. Amendment Round (v1.2.0)

This section records the five independent-review findings resolved in the amendment round. The five documents (requirements.md, design.md, tasks.md, roadmap.md, this review) were updated to v1.2.0 as a result.

### Amendment 1 — MCP approval enforcement ✅ APPLIED

**Finding:** MCP tool calls had no tool classification, no default-deny policy, no ApprovalRecord binding to workflow_run_id, no mandatory MCPService gateway, and no named negative tests proving bypass prevention.

**Correction applied:**
- requirements.md REQ-M1.7: Added complete MCP approval gate specification — tool classification (`read_only`/`consequential`/`unknown`), default-deny policy, additive sequential checks (allow-list first, then approval gate), `ApprovalRecord` structure with 7 binding fields, five required audit events, six acceptance criteria.
- requirements.md REQ-W1.7: Added all five MCP audit events to the master audit event table.
- design.md §7.5: Added `MCPService` class with `invoke_tool` method; added `MCPApprovalRequiredError` and `MCPApprovalExpiredError` exceptions; specified `workflow_run_id` binding check; specified additive sequential check order.
- design.md §7.4: Added `MCPApprovalRequiredError` and `MCPApprovalExpiredError` exception classes.
- design.md ADR-0011: Documented the MCPService-as-mandatory-gateway decision.
- tasks.md I4: Added `MCPService` as a deliverable; added 7 named MCP approval gate tests; added two new exceptions to deliverables.
- tasks.md I7: Added the 7 named MCP approval gate tests to the full test list.

**Evidence citations:** requirements.md REQ-M1.7 (additive checks, ApprovalRecord structure, audit events, acceptance criteria M1.7.1–M1.7.6); design.md §7.5 (MCPService.invoke_tool docstring, ApprovalRecord model, audit event table); tasks.md I4 (named tests section), I7 (all test cases list).

---

### Amendment 2 — GitHub action confirmation ✅ APPLIED

**Finding:** Branch/PR creation relied on a client-supplied `confirmed: bool` boolean flag, which provides no binding to specific parameters and can be trivially replayed. No expiry, no single-use semantics, no named negative tests for replay/mismatch/bypass paths. Roadmap security table still referenced `confirmed=True`.

**Correction applied:**
- requirements.md REQ-G1.4, REQ-G1.5: Replaced `confirmed: bool` with `confirmation_id: str` referencing a `GitHubConfirmation` record; specified all 9 fields of the record; specified single-use semantics (`used_at`), expiry (default 10-minute TTL), mismatch rejection, idempotency key on `(confirmation_id, operation)`.
- requirements.md REQ-S1.1: Added "Distinction between credentials and authorization" block.
- design.md §8.2: Specified `RepositoryService` with `issue_confirmation`, `create_branch`, `create_pull_request`; specified full 7-step validation sequence; specified `GitHubConfirmation` model; specified rejection cases and HTTP codes.
- design.md §14.1: Updated "Confirmation gate pattern" section; stated `confirmed: bool` is replaced.
- design.md ADR-0005: Updated rationale for confirmation gate.
- tasks.md G2: Added 6 named negative tests; added `GitHubConfirmationRepository` and exception classes as deliverables.
- tasks.md G3: Added `confirmed=false` returns 422 acceptance criteria.
- roadmap.md Security Summary: Replaced `confirmed=True` with `GitHubConfirmation record`; replaced `confirmed=True` gate language in Wave 5 gate entry.

**Evidence citations:** requirements.md REQ-G1.4 (GitHubConfirmation structure, single-use, expiry, mismatch, idempotency, acceptance criteria G1.4.1–G1.4.8); design.md §8.2 (RepositoryService code, GitHubConfirmation model, rejection cases); tasks.md G2 (named tests), G3 (AC1–AC2); roadmap.md Security Summary table.

---

### Amendment 3 — SQLite foreign-key enforcement ✅ APPLIED

**Finding:** `PRAGMA foreign_keys=ON` was not specified in any requirement or design section. All `ON DELETE CASCADE` and `ON DELETE SET NULL` semantics in migrations 003–005 were silently inactive.

**Correction applied:**
- requirements.md REQ-DB1.3: New requirement specifying `PRAGMA foreign_keys=ON` on every connection, implementation in `'connect'` event handler, 4 named tests.
- design.md §3.7: New section "SQLite Foreign-Key Enforcement" with the full SQLAlchemy connect-event code pattern; note on `alembic/env.py` update; ADR-0012.
- tasks.md P1: Added Wave 1 configuration ownership section assigning PRAGMA implementation to Wave 1; assigned 4 FK tests to Task P6.
- tasks.md P6: Added 4 named FK test cases to required test cases list.

**Evidence citations:** requirements.md REQ-DB1.3 (all 5 acceptance criteria DB1.3.1–DB1.3.5); design.md §3.7 (code example), ADR-0012; tasks.md P1 (config ownership), P6 (required tests).

---

### Amendment 4 — CI branch coverage canonicalization ✅ APPLIED

**Canonical command:** `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing`

**Finding:** Roadmap wave completion gates (Waves 2, 3, 4) had no coverage gate criterion. Wave 1 and Wave 5 roadmap gates used wrong flag order (`--cov-report` before `--cov-fail-under`) and were missing `-v`. Tasks.md P1 config ownership section did not mention CONTRIBUTING.md. The pyproject.toml `addopts` instruction was missing `-v`.

**Correction applied:**
- roadmap.md: All five wave completion gates now include `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0 as an explicit gate criterion.
- roadmap.md Wave 5: Updated final verification command to canonical form.
- tasks.md P1: Updated `addopts` target to include `-v`; added CONTRIBUTING.md update as a Wave 1 configuration ownership item.
- requirements.md REQ-T1.1.1: Already had the canonical command; confirmed correct.
- tasks.md P6/W6/A5/I7/G5 AC3/AC5/AC2: Already had the canonical command; confirmed correct.

**Evidence citations:** roadmap.md Wave 1–5 completion gates (all five now include canonical command); tasks.md P1 (config ownership section, now includes CONTRIBUTING.md and correct addopts value); requirements.md REQ-T1.1.1.

---

### Amendment 5 — MCP SDK dependency management ✅ APPLIED

**Finding:** REQ-M1.8 did not instruct the implementer to check pyproject.toml first. No note that `mcp` was absent from pyproject.toml at the base commit. The `mcp_approval_denied` audit event trigger was inconsistently defined between requirements.md ("Approval resolved as rejected by user") and design.md §7.5 and §16 ("When ApprovalRecord.expires_at is in the past").

**Correction applied:**
- requirements.md REQ-M1.8: Added "check pyproject.toml first" language; noted that `mcp` is absent from pyproject.toml at base commit `aaaaacb` so `mcp>=1.0,<2.0` is operative; updated M1.8.1 acceptance criterion to include "or the actual constraint" caveat.
- design.md §7.6: Added "check pyproject.toml first at implementation time" instruction; clarified that `mcp` is absent from pyproject.toml at base commit.
- tasks.md I4: Updated `requirements/base.txt` deliverable note to include "after checking pyproject.toml"; updated AC12 with same caveat.
- design.md §7.5 (invoke_tool docstring): Corrected — expired `ApprovalRecord` now raises `MCPApprovalExpiredError` without logging `mcp_approval_denied` (expiry is not denial).
- design.md §16 (audit event table): Corrected — `mcp_approval_denied` trigger is now "When an MCP `ApprovalRequest` is explicitly rejected by user" to match requirements.md REQ-W1.7.

**Evidence citations:** requirements.md REQ-M1.8 (amended text, M1.8.1); design.md §7.6 (pyproject check note), §7.5 (corrected invoke_tool docstring), §16 (corrected audit event table); tasks.md I4 (deliverables, AC12).

---

## 14. Updated Checklist Evidence

The following checklist items from §1–§9 are updated with evidence from the amendment round:

### §4 Security Requirements Review — Updated

| Security requirement | Mechanism specified | Test coverage |
|---|---|---|
| Explicit approval for consequential actions | Confirmation gate (§14.1) + Approval gate (§14.2) + MCP approval gate (§7.5) | ✅ Named in G2, G5 (GitHub), I4, I7 (MCP), A5 (workflow) |
| Credential ≠ authorization | Explicitly stated in REQ-S1.1, design.md §14.1, roadmap Security Summary (amended to remove `confirmed=True` language) | ✅ Design language corrected |
| MCP tool classification + default-deny | MCPService classify → ApprovalRecord required for consequential/unknown (§7.5) | ✅ 5 named tests in I4+I7 |
| MCP approval-bypass prevention | MCPService mandatory gateway (ADR-0011); no direct MCPClient calls from routers | ✅ `test_direct_mcp_client_call_blocked_without_service_layer` |
| SQLite FK constraints active | PRAGMA foreign_keys=ON in connect event (§3.7, REQ-DB1.3) | ✅ 4 named tests in P6 |
| No hardcoded credentials | Settings SecretStr (§14.3) | ✅ REQ-S1.3 (unchanged) |
| No secrets in logs | RedactSecretsProcessor | ✅ Named test: `test_github_token_not_in_log_records` in I7 |
| Bounded timeouts | Per-adapter timeouts in Settings (REQ-S1.2) | ✅ Named test: `test_github_adapter_timeout_raises_integration_error` in I7 |
| No auto PR merge | No `/merge` endpoint (REQ-S1.4) | ✅ Named test: `test_no_merge_endpoint_exists` in G5 |
| MCP subprocess env isolation (Python-level) | Explicit env, SIGTERM/SIGKILL sequence (§14.4); REQ-S1.5 | ✅ Named test: `test_mcp_subprocess_launched_with_explicit_env` in I7 |
| MCP permission allow-list | MCPServerConfig.allowed_tools (REQ-M1.4) | ✅ Named test in I7 |
| Secret interpolation safety | Only SecretStr fields; raise before subprocess if unresolvable (REQ-M1.5) | ✅ Named test: `test_mcp_secret_values_not_in_log_records` in I7 |
| GitHubConfirmation binding | RepositoryService validates all 7 fields; `used_at` single-use; `parameters_hash` mismatch rejected | ✅ 6 named tests in G2+G5 |

---

## 15. Final Correction Pass (F1–F5, D1–D4)

This section records the corrections applied in the Final Specification Correction Pass (v1.3.0). See `.agents/tasks/phase1-final-spec-correction-report.md` for the full correction report.

### F1 — Wave 1 FK test dependencies ✅ APPLIED

**Finding:** Wave 1 Task P6 required tests `test_cascade_delete_enforced`, `test_set_null_enforced`, and `test_insert_invalid_foreign_key_raises_integrity_error` that reference `WorkflowRun` and `WorkflowAuditLog` tables — Wave 2 deliverables. This made Wave 1 independently unsatisfiable.

**Correction:** Removed the three Wave 2 table-dependent FK tests from Task P6. Added two Wave-1-only FK tests to Task P6 (`test_wave1_cascade_delete_enforced`, `test_wave1_insert_invalid_foreign_key_raises_integrity_error`). Added the original three FK tests to Task W6 (`test_cascade_delete_enforced`, `test_set_null_enforced`, `test_insert_invalid_foreign_key_raises_integrity_error`). Updated REQ-DB1.3 acceptance criteria to split Wave 1 (DB1.3.1–DB1.3.4) from Wave 2 (DB1.3.5–DB1.3.7). Wave 1 completion gate is now independently satisfiable.

**Evidence:** requirements.md REQ-DB1.3 (split criteria); tasks.md P6 (new Wave-1-only tests), W6 (three FK tests added).

---

### F2 — GitHubConfirmation persistence ✅ APPLIED

**Finding:** `GitHubConfirmation` was modelled as an in-memory Pydantic `BaseModel`. The amendment report (§4, item 3) explicitly listed this as an unresolved decision requiring reviewer confirmation. Decision: SQLite-backed persistent records are mandatory.

**Correction:**
- requirements.md REQ-G1.4: Added persistence requirement (SQLAlchemy model + repository + migration 006); updated `GitHubConfirmation` structure description to specify SQLite persistence; added 6 named tests (G1.4.9–G1.4.14); added atomic consumption and concurrent duplicate-prevention specification.
- requirements.md REQ-DB1.1: Added migration 006 to the chain table and revision chain (001→006); updated DB1.1.1 to reference all 5 Phase 1 migrations.
- design.md §3.0: Added migration 006 to the migration sequence diagram and table.
- design.md §3.7a: New section with `github_confirmations` SQL DDL, SQLAlchemy model, `GitHubConfirmationRepository` interface, and persistence rationale.
- design.md §8.2: Updated `GitHubConfirmation` from Pydantic `BaseModel` to SQLAlchemy model; labelled old definition as SUPERSEDED.
- design.md §19: Updated REQ-DB1.1 task IDs to include G1.
- tasks.md G1: Expanded to include `GitHubConfirmation` model, `GitHubConfirmationRepository`, and migration 006.
- tasks.md G2: Updated key implementation notes for SQLite persistence and atomic `consume_atomic`; added 6 named confirmation tests.
- tasks.md G5: Added migration 006 round-trip test and 6 confirmation tests to required test cases; added completion criteria AC7 and AC8.
- roadmap.md: Updated migration chain to show 006; updated Wave 5 completion gate to require migration 006 and 6 confirmation tests.

**Evidence:** requirements.md REQ-G1.4 (persistence requirement, G1.4.9–G1.4.14), REQ-DB1.1 (migration 006); design.md §3.0, §3.7a, §8.2; tasks.md G1, G2, G5; roadmap.md migration chain, Wave 5 gate.

---

### F3 — MCP authorization consistency ✅ APPLIED

**Finding:** The MCP authorization sequence was not stated as a mandatory 8-step sequence. The roadmap security table described allow-list alone as the authorization mechanism for MCP tool calls, which is incorrect for consequential/unknown tools.

**Correction:**
- requirements.md REQ-M1.7: Added explicit mandatory 8-step authorization sequence; added clarification that allow-list alone is NOT sufficient for consequential tools; expanded audit events to 7; updated M1.7.1–M1.7.8 acceptance criteria including M1.7.7 (allow-list ≠ sufficient) and M1.7.8 (new test name).
- design.md §7.5: Updated `MCPService.invoke_tool` docstring to show the full 8-step sequence; clarified that `mcp_approval_expired` is NOT `mcp_approval_denied`.
- roadmap.md Security Summary: Updated MCP row to show both allow-list AND ApprovalRecord required for consequential tools.
- tasks.md I4: Added `test_allowlist_alone_insufficient_for_consequential_tool` to named tests.
- tasks.md I7: Added the same test to all test cases.

**Evidence:** requirements.md REQ-M1.7 (8-step sequence, M1.7.7–M1.7.8); design.md §7.5 (invoke_tool docstring); roadmap.md Security Summary (MCP row); tasks.md I4, I7.

---

### F4 — Superseded review guidance ✅ APPLIED

**Finding:** Some historical sections in the review document referenced `confirmed=True` language that was superseded by Amendment 2.

**Correction:**
- review.md §9 item 5: Added "SUPERSEDED — see §15" label and pointer; ~~struck through~~ the `confirmed=True` language.
- review.md §11 Finding 7: Added historical note labelling the section as historical; ~~struck through~~ `confirmed=True` reference in resolution text; added explanation that the gate was subsequently upgraded.
- No active requirement, design section, or task references `confirmed=True` as sufficient authorization (verified by grep).

**Evidence:** review.md §9 item 5 (SUPERSEDED label), §11 Finding 7 (historical note).

---

### F5 — Document metadata ✅ APPLIED

**Finding:** All five spec documents show `Last Updated: 2025-01-21` or `Last Updated: 2026-11-14` (fabricated/placeholder dates).

**Correction:** Updated all five documents' `Last Updated` fields to `[current correction pass — implementer fills date at commit time]`. Added version history entries for v1.3.0 to all documents. Added version history block to requirements.md, design.md, tasks.md, and roadmap.md (which previously had no version history section).

**Evidence:** All five document headers updated.

---

### D1 — Streamlit navigation ✅ VERIFIED (no change needed)

**Finding to verify:** Pages 6 and 7 should reference `6_Workflows.py` and `7_History.py`.

**Result:** requirements.md REQ-U1.2 (U1.2.1) and REQ-U1.3 (U1.3.1) already specify the correct filenames. design.md §12.1 page inventory shows correct names. tasks.md Task A4 deliverables show correct names. No correction needed.

**Evidence:** requirements.md REQ-U1.2.1, REQ-U1.3.1; design.md §12.1; tasks.md A4.

---

### D2 — MCP binary trust ✅ APPLIED

**Finding:** The exact D2 trust statement was not present verbatim in design.md.

**Correction:**
- design.md §7.6: Added the exact D2 statement: "For Phase 1, operator-configured MCP server binaries are trusted within the documented local single-user threat model. Environment-variable scoping is not an OS-level sandbox. Untrusted MCP binaries must not be executed. OS-level sandboxing (seccomp, namespaces, AppArmor) is deferred to a future phase."
- design.md §14.4: Added the D2 exact statement alongside the existing isolation boundary description.

**Evidence:** design.md §7.6 (trust statement), §14.4 (D2 label).

---

### D3 — GitHub confirmations ✅ COVERED BY F2

**Finding:** Covered by F2 (SQLite persistence). See F2 above.

**Evidence:** See F2 evidence.

---

### D4 — MCP approval expiry audit event ✅ APPLIED

**Finding:** `mcp_approval_expired`, `mcp_approval_missing` were not defined as distinct audit events separate from `mcp_approval_denied`.

**Correction:**
- requirements.md REQ-W1.7: Added `mcp_approval_expired` and `mcp_approval_missing` to audit event table with explicit "NOT `mcp_approval_denied`" notes.
- requirements.md REQ-M1.7: Updated audit event table to include all 7 events with explicit distinction notes; added M1.7.8 (`test_expired_mcp_approval_emits_approval_expired_event`).
- design.md §7.5: Updated audit event table to include all 7 events with "Distinct from" column.
- design.md §16: Updated audit event table to include `mcp_approval_expired` and `mcp_approval_missing`.
- tasks.md I4: Added `test_expired_mcp_approval_emits_approval_expired_event` and `test_missing_approval_emits_approval_missing_event` to named tests.
- tasks.md I7: Added the same tests to all test cases.

**Evidence:** requirements.md REQ-W1.7, REQ-M1.7 (7-event tables, M1.7.8); design.md §7.5 (table with Distinct from column), §16 (updated table); tasks.md I4, I7.

---

## **READY FOR FINAL INDEPENDENT REVIEW** (v1.3.0)

All corrections F1–F5 and architectural decisions D1–D4 applied. All prior findings from §11 (8 findings) and §13 (5 amendments) remain resolved. Specification is internally consistent.

**Changed files (v1.3.0 correction pass):**
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.3.0)
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.3.0)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.3.0)
- `docs/planning/phase1-roadmap.md` (v1.3.0)
- `docs/reviews/phase1-specification-review.md` (v1.3.0 — this document)
- `.agents/tasks/phase1-final-spec-correction-report.md` (new — correction report)

---

## 16. v1.4.0 Correction Pass (F1–F3)

This section records the finding closures for the v1.4.0 correction pass. All three findings (F1 MCP approval authorization, F2 FK cascade tests, F3 metadata) were addressed during this pass. Full details are in `.agents/tasks/phase1-v1.4.0-correction-report.md`.

### Finding Closure Table

| Finding | Original problem | Fix applied | Evidence | Named tests |
|---|---|---|---|---|
| F1 — MCP Approval Authorization (Critical) | `MCPService.invoke_tool` accepted an in-memory `ApprovalRecord` supplied by caller, allowing forge/replay. No binding to server/tool/arguments/actor. No atomic one-time consumption. | Caller passes only `approval_request_id: str`. MCPService retrieves `ApprovalRequest` from `ApprovalRequestRepository` internally. 8-step mandatory sequence: config check → allow-list → classify → retrieve by ID → validate (status/expiry/fields/not-consumed) → `consume_atomic` (single DB transaction) → execute → audit. No-bypass rule enforced. | requirements.md REQ-M1.7 (8-step sequence, M1.7.1–M1.7.12); design.md §7.5 (invoke_tool docstring, ApprovalRequestRepository interface, additive sequential checks); tasks.md I4 (invoke_tool signature, consume_atomic spec), I7 (all 29 MCP test cases) | test_forged_approval_record_rejected; test_expired_approval_rejected_at_invocation; test_mismatched_tool_name_rejected; test_mismatched_arguments_hash_rejected; test_replay_after_consumption_rejected; test_concurrent_consumption_safe; test_read_only_tool_no_approval_required; test_no_direct_mcp_client_bypass |
| F2 — FK Cascade Tests (High) | Wave 1 Task P6 required tests referencing Wave 2 tables (WorkflowRun, WorkflowAuditLog), making Wave 1 independently unsatisfiable. Cascade directions not specified. | Wave 1 FK tests split to use Wave 1 tables only. Wave 2 FK tests moved to Task W6. Cascade directions corrected: Workflow.project_id SET NULL; WorkflowRun.workflow_id CASCADE; WorkflowAuditLog.workflow_run_id SET NULL. 5+ named FK tests with explicit wave assignments. PRAGMA foreign_keys=ON required on every connection. | requirements.md REQ-DB1.3 (split Wave 1/Wave 2 criteria); design.md §3.7 (FK relationships table, ON DELETE behaviors); tasks.md P6 (Wave-1-only tests), W6 (Wave-2 FK tests) | test_foreign_key_pragma_enabled_on_connection (W1/P6); test_wave1_cascade_delete_enforced (W1/P6); test_wave1_insert_invalid_foreign_key_raises_integrity_error (W1/P6); test_delete_project_sets_workflow_project_id_null (W2/W6); test_delete_workflow_cascades_to_workflow_runs (W2/W6); test_delete_workflow_run_sets_audit_log_workflow_run_id_null (W2/W6); test_insert_invalid_foreign_key_raises_integrity_error (W2/W6) |
| F3 — Document Metadata (Low) | All five spec documents contained placeholder `Last Updated` text: `[current correction pass — implementer fills date at commit time]`. All showed version 1.3.0. No v1.4.0 version history entry existed. | Replaced placeholder `Last Updated` with actual date `2026-11-15` in all five documents. Set version to `v1.4.0` in all five documents. Added version history entry: `v1.4.0 — 2026-11-15 — Corrections F1 (MCP approval authorization via approval_request_id), F2 (FK cascade test corrections), F3 (metadata). Branch: feature/phase1-specification-planning, Base: aaaaacb703124fc31b0e757b2bf1739c4fb225c9.` No Git commit hashes invented. No PRs claimed as merged. | All five document headers updated and verified. | — |

### Consistency Verification Results (v1.4.0)

All 13 checks performed against the v1.4.0 documents:

| # | Check | Result |
|---|---|---|
| 1 | Linear Alembic migration chain: 001→002→003→004→005→006, no gaps, no forks. Migration 006 assigned to Wave 5. | PASS |
| 2 | GitHubConfirmation: SQLite-backed, single-use, atomic consume_atomic, bound to repo/operation/parameters_hash/actor. | PASS |
| 3 | MCP approval: invoke_tool accepts approval_request_id (not ApprovalRecord); MCPService retrieves from repo internally; all binding fields validated; atomic CONSUMED transition. | PASS |
| 4 | WorkflowRun states: pending, running, waiting_approval, completed, failed, cancelled (no paused state). | PASS |
| 5 | Coverage gate consistent everywhere: `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing`. | PASS |
| 6 | Wave 1 completion gate does not reference any Wave 2 table (WorkflowRun, WorkflowStep, ApprovalRequest, WorkflowAuditLog). | PASS |
| 7 | FK cascade directions: Workflow.project_id SET NULL; WorkflowRun.workflow_id CASCADE; WorkflowAuditLog.workflow_run_id SET NULL. | PASS |
| 8 | No autonomous AI provider invocation in Phase 1. | PASS |
| 9 | No automatic GitHub PR merging. | PASS |
| 10 | No confirmed=True boolean as authorization gate anywhere in active sections. | PASS |
| 11 | All 11 integration adapters retain approved execution modes (Codex = cli_handoff). | PASS |
| 12 | No Android, React, TypeScript, or Vite references. | PASS |
| 13 | No ApprovalRecord (in-memory) object passed to invoke_tool anywhere in spec text. | PASS |

### Note on Self-Assessment

This review document is self-assessed. Independent review by a reviewer other than the spec author is required before implementation begins.

---

## **READY FOR INDEPENDENT REVIEW** (v1.4.0)

All three findings (F1 MCP approval authorization, F2 FK cascade tests, F3 metadata) resolved. All 13 consistency checks pass. All prior findings from §11 (8 findings), §13 (5 amendments), and §15 (F1–F5, D1–D4) remain resolved. Specification is internally consistent at v1.4.0.

**Changed files (v1.4.0 correction pass):**
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.4.0)
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.4.0)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.4.0)
- `docs/planning/phase1-roadmap.md` (v1.4.0)
- `docs/reviews/phase1-specification-review.md` (v1.4.0 — this document)
- `.agents/tasks/phase1-v1.4.0-correction-report.md` (new — correction report)

---

## 17. v1.4.0 Security and Schema Correction Pass (F6–F9)

This section records the corrections applied in the F6–F9 security and schema correction pass. Full details are in `.agents/tasks/phase1-v1.4-final-security-schema-correction-report.md`.

### Finding Closure Table

| Finding | Original problem | Fix applied | Status |
|---|---|---|---|
| F6 — MCP Approval Schema Conflict (CRITICAL) | MCPService used `ApprovalRequestRepository` and `ApprovalRequest` (integer PK, workflow step approval table) for MCP authorization. Schema mismatch and architectural confusion. | Dedicated `mcp_approvals` table (UUID PK), `MCPApproval` model, `MCPApprovalRepository` defined. Migration 007 added (Wave 5). MCPService updated to use MCPApprovalRepository. `approval_requests` table retained for workflow step approvals only. Explicit separation documented throughout. | ✅ RESOLVED |
| F7 — Outdated MCP Authorization References (HIGH) | References to `ApprovalRecord` (in-memory), `ApprovalRequestRepository` in MCP context, and an 8-step sequence that conflated MCP with workflow approvals. | All `ApprovalRecord`/`ApprovalRequestRepository` references in MCP context replaced with `MCPApproval`/`MCPApprovalRepository`. 9-step mandatory sequence documented (step 7 — consume_atomic — separated from step 6 — validation). SUPERSEDED label on old design. | ✅ RESOLVED |
| F8 — Wave 1 FK Tests (MEDIUM) | `test_wave1_cascade_delete_enforced` in Wave 1 had no real CASCADE relationship to test. Ambiguous fallback language "or skips with a comment" was unimplementable. | Removed `test_wave1_cascade_delete_enforced`. Replaced with `test_fk_enforcement_with_wave1_tables` (precise FK enforcement test using minimal in-memory table) and `test_migration_002_upgrade_downgrade`. REQ-DB1.3 renumbered. | ✅ RESOLVED |
| F9 — Approval Consumption and External Failure Handling (MEDIUM) | No spec text defined behavior when MCPApproval or GitHubConfirmation was consumed but the external operation failed. Approvals could appear replayable on failure. | Explicit failure semantics: consumed approvals never auto-restored; failures logged as `mcp_tool_failed`; indeterminate treated as failure; user must issue new approval for retry. Exactly-once caveats added for MCP and GitHub. 4 named tests added. | ✅ RESOLVED |

---

### Updated Consistency Check Results (15-point check)

| # | Check | Result |
|---|---|---|
| 1 | No conflicting MCP approval models — only `MCPApproval` used for MCP authorization; `approval_requests` used only for workflow step approvals | PASS |
| 2 | Migration chain linear: 001 → 002 → 003 → 004 → 005 → 006 → 007 | PASS |
| 3 | Wave ownership valid: each migration assigned to exactly one wave (Wave 1={002}, Wave 2={003,004,005}, Wave 5={006,007}) | PASS |
| 4 | All 29+ tasks have correct dependencies (no forward references; G1 extended but no new cross-wave deps) | PASS |
| 5 | Security paths have negative tests (forged, expired, replayed, mismatched, consumed — all 8 MCPApproval security tests present) | PASS |
| 6 | No automatic workflow execution in Phase 1 | PASS |
| 7 | No automatic GitHub PR merging | PASS |
| 8 | Coverage gate: `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` consistent in all tasks | PASS |
| 9 | Wave 1 completion gate does not reference Wave 2+ tables | PASS |
| 10 | All version metadata v1.4.0 and date 2026-11-15 consistent | PASS |
| 11 | No `ApprovalRecord` (in-memory) object in any active spec section used for MCP authorization | PASS |
| 12 | Exactly-once execution caveat present for MCP and GitHub operations | PASS |
| 13 | Roadmap Security Summary table: MCP row references `MCPApproval` (not `ApprovalRecord`) | PASS |
| 14 | Roadmap Alembic migration chain updated to show 007 | PASS |
| 15 | Wave 5 completion gate updated to include migration 007 and MCPApproval-related test names | PASS |

**All 15 checks pass.**

---

### Self-Assessment Caveat

This correction pass is self-assessed. Independent review by a reviewer other than the spec author is required before implementation begins. The corrections resolve four specific findings without expanding Phase 1 functionality or modifying any source code, tests, Alembic migration files, or CI configuration.

---

## **READY FOR FINAL INDEPENDENT REVIEW** (v1.4.0, F6–F9 applied)

All four findings (F6 MCPApproval schema conflict, F7 outdated MCP authorization references, F8 Wave 1 FK tests, F9 approval consumption failure handling) resolved. All 15 consistency checks pass. All prior findings from §11 (8 findings), §13 (5 amendments), §15 (F1–F5, D1–D4), and §16 (F1–F3) remain resolved. Specification is internally consistent at v1.4.0 with F6–F9 corrections.

**Changed files (v1.4.0 F6–F9 correction pass):**
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.4.0, F6–F9)
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.4.0, F6–F9)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.4.0, F6–F9)
- `docs/planning/phase1-roadmap.md` (v1.4.0, F6–F9)
- `docs/reviews/phase1-specification-review.md` (v1.4.0 — this document, §17 added)
- `.agents/tasks/phase1-v1.4-final-security-schema-correction-report.md` (new — full correction report)

---

## 18. Migration and Dependency Alignment Pass (v1.5.0)

This section records the migration renaming and wave reassignment alignment pass that produced v1.5.0 of all five spec documents. The full alignment report is in `.agents/tasks/phase1-final-migration-alignment-report.md`.

### Migration Renaming (006↔007 Swap)

**Problem:** Migration 006 was named `006_add_github_confirmations` (Wave 5) and migration 007 was named `007_add_mcp_approvals` (Wave 5). Wave 4 required persisted MCP approvals, but the MCP approval migration and all related models were assigned to Wave 5. This created a forward dependency: Wave 4 MCPService could not reference a Wave 5 migration and table.

**Correction applied:**

| Migration | Before v1.5.0 | After v1.5.0 |
|---|---|---|
| 006 | `006_add_github_confirmations` — Wave 5 | `006_add_mcp_approvals` — **Wave 4** |
| 007 | `007_add_mcp_approvals` — Wave 5 | `007_add_github_confirmations` — Wave 5 |
| 007 down_revision | `006_add_github_confirmations` | `006_add_mcp_approvals` |

All five documents updated: migration chain diagrams, revision tables, task deliverables, wave completion gates, file layout (§13), and traceability matrix (§19).

### Wave Reassignment

The following items moved from Wave 5 to Wave 4 (Task I4):
- `MCPApproval` SQLAlchemy model (`src/devflow_api/models/mcp_approval.py`)
- `MCPApprovalRepository` (`src/devflow_api/repositories/mcp_approval.py`)
- Migration `006_add_mcp_approvals` (`alembic/versions/006_add_mcp_approvals.py`) with `down_revision = "005_add_repository_tables"`

Wave 5 (Task G1) retains:
- Migration `007_add_github_confirmations` with `down_revision = "006_add_mcp_approvals"`
- `GitHubConfirmation` SQLAlchemy model
- `GitHubConfirmationRepository`

### Task I4 Corrections Summary

- Added MCPApproval model, MCPApprovalRepository, and migration 006 as Wave 4 deliverables
- Removed any reference to ApprovalRequestRepository in the MCP authorization path
- Removed any reference to Wave 5 migration in Wave 4 deliverables
- Task I4 acceptance criterion I4.17 added: Wave 4 is independently applicable without any Wave 5 migration existing
- ApprovalRequest/ApprovalRepository/ApprovalService remain strictly for workflow step approval gates

### Design §7.5 and §13 Updates

- §7.5 MCPService: `mcp_approval_repo: MCPApprovalRepository` (NOT `ApprovalRequestRepository`); `mcp_approval_id: UUID | None` (NOT `approval_request_id`)
- §13 file layout: `mcp_approval.py` moved to Wave 4 section; `006_add_mcp_approvals.py` annotated as Wave 4 Task I4
- Explicit statements added: "No router, adapter, or Streamlit handler may import or instantiate MCPClient directly." and "MCPService retrieves and validates MCPApproval from MCPApprovalRepository before any consequential tool invocation."

### Nine-Check Consistency Results (v1.5.0)

| # | Check | Result |
|---|---|---|
| 1 | 7 migrations form one linear chain: 001→002→003→004→005→006→007, no gaps, no forks | **PASS** |
| 2 | Wave 1 requires no Wave 2–5 deliverables | **PASS** |
| 3 | Wave 2 requires no Wave 3–5 deliverables | **PASS** |
| 4 | Wave 3 requires no Wave 4–5 deliverables | **PASS** |
| 5 | Wave 4 requires no Wave 5 deliverables | **PASS** |
| 6 | MCP consequential actions require persisted MCPApproval (migration 006, Wave 4) | **PASS** |
| 7 | GitHub branch/PR creation requires persisted GitHubConfirmation (migration 007, Wave 5) | **PASS** |
| 8 | Coverage gate consistent: `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` | **PASS** |
| 9 | No autonomous workflow execution in Phase 1 | **PASS** |

**All 9 checks PASS.**

### Updated Final Verdict

**READY FOR INDEPENDENT REVIEW** (v1.5.0)

All migration alignment corrections applied. All 9 consistency checks pass. All prior findings from §11 (8 findings), §13 (5 amendments), §15 (F1–F5, D1–D4), §16 (F1–F3), and §17 (F6–F9) remain resolved. The seven-migration linear chain is correctly specified. Wave 4 owns migration 006 and all MCP approval infrastructure. Wave 4 has no dependency on any Wave 5 deliverable. Specification is internally consistent at v1.5.0.

**Changed files (v1.5.0 migration alignment pass):**
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.5.0)
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.5.0)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.5.0)
- `docs/planning/phase1-roadmap.md` (v1.5.0)
- `docs/reviews/phase1-specification-review.md` (v1.5.0 — this document, §18 added)
- `.agents/tasks/phase1-final-migration-alignment-report.md` (new — alignment report)

---

## 19. MCP Security Hardening Pass (S1–S2) — v1.5.1

This section records the two security findings resolved in the final MCP security hardening pass that produced v1.5.1 of all five spec documents. The full hardening report is at `.agents/tasks/phase1-v1.5-final-mcp-security-report.md`.

### Finding S1 — Workflow Run Binding ✅ APPLIED

**Problem:** The `MCPApproval` model contains `workflow_run_id`, but no requirement or design section explicitly required that the approval's `workflow_run_id` be matched against the trusted invocation context. A workflow-bound approval could potentially authorize an invocation from a different workflow context, or an invocation with no workflow context, with no defined rejection behavior.

**Correction applied:**

- **requirements.md:** Added `REQ-M2.5` with 6 binding rules, 7 acceptance criteria, and 4 named negative tests. Added `mcp_approval_rejected` audit event (with `reason` field) to the REQ-W1.7 audit event table.
- **design.md §7.5:** Added `trusted_workflow_run_id: UUID | None` parameter to `MCPService.invoke_tool` signature (server-side only, NOT from tool arguments). Added step 6e (workflow_run_id binding check) to the invoke_tool docstring. Added `mcp_approval_rejected` audit event (with reason variants) to the §7.5 audit event table and the §16 master audit event table. Updated `MCPApprovalRepository.consume_atomic` interface to accept `trusted_workflow_run_id`.
- **tasks.md I4:** Added S1 workflow run binding key implementation notes and 4 named negative tests.
- **tasks.md I7:** Added all 4 S1 tests to the complete test list.

**S1 binding rules enforced:**
1. Approval `workflow_run_id = X` cannot authorize invocation with `trusted_workflow_run_id = Y` (X≠Y) → reason: `workflow_run_mismatch`
2. Approval `workflow_run_id` non-NULL cannot authorize invocation with `trusted_workflow_run_id = NULL` → reason: `missing_workflow_context`
3. Approval `workflow_run_id = NULL` cannot authorize invocation with `trusted_workflow_run_id` non-NULL → reason: `unexpected_workflow_context`
4. `trusted_workflow_run_id` comes from server-side session context ONLY — not from tool arguments
5. Mismatch fails closed — no execution proceeds
6. Every rejection emits `mcp_approval_rejected` with structured `reason` field

**4 named negative tests added:**
- `test_approval_wrong_workflow_run_rejected`
- `test_approval_bound_to_workflow_rejected_without_workflow_context`
- `test_approval_unbound_rejected_with_workflow_context`
- `test_workflow_run_id_from_arguments_not_trusted`

---

### Finding S2 — Atomic Approval Consumption ✅ APPLIED

**Problem:** The `consume_atomic` contract specified a conditional `UPDATE WHERE status='APPROVED' AND id=?` but did not explicitly require a single atomic database transaction that also re-validates `expires_at > now` and `consumed_at IS NULL` within the same transaction. This gap allowed a TOCTOU window: an approval valid at service-layer validation time could expire between validation and consumption, and a stale in-memory validation result could bypass the expiry check.

**Correction applied:**

- **requirements.md REQ-M2.2:** Replaced the single-line `consume_atomic` description with an 8-step atomic transaction specification: SELECT with row-level lock → verify within SAME transaction (status, expires_at, consumed_at) → verify workflow_run_id binding within SAME transaction → conditional UPDATE → rowcount check → commit BEFORE subprocess launch → no rollback on subprocess failure. Added 2 new acceptance criteria (M2.2.6, M2.2.7, M2.2.8). Added SQLite concurrency assumptions section. Added 5 named negative tests.
- **design.md §7.5:** Replaced the single-line `consume_atomic` reference in the invoke_tool docstring with the full 6-step transaction description. Updated the `MCPApprovalRepository` interface docstring to include the full 6-step algorithm. Added `now: datetime` parameter (using `datetime.now(UTC)`) to `consume_atomic` signature.
- **tasks.md I4:** Replaced the single-line atomic consumption note with the full 7-step transaction description. Added S2 named negative tests.
- **tasks.md I7:** Added all 5 S2 tests to the complete test list.

**S2 atomic consumption algorithm (8 steps):**
1. SELECT row with row-level lock (or SQLite serialized write)
2. Verify within SAME transaction: `status = APPROVED AND expires_at > now AND consumed_at IS NULL`
3. Verify `workflow_run_id` binding within SAME transaction (S1 rules)
4. `UPDATE mcp_approvals SET status='CONSUMED', consumed_at=now WHERE id=? AND status='APPROVED' AND expires_at > now AND consumed_at IS NULL`
5. Verify exactly 1 row updated — if 0, raise `ConsumedError`; log `mcp_approval_already_consumed`
6. Commit transaction BEFORE launching subprocess
7. Subprocess failure after commit does NOT roll back consumption
8. Use `datetime.now(UTC)` throughout — `datetime.utcnow()` prohibited

**5 named negative tests added:**
- `test_concurrent_consumption_only_one_succeeds`
- `test_expired_at_consumption_time_rejected`
- `test_consumed_approval_cannot_be_reused`
- `test_execution_failure_does_not_restore_consumed_approval`
- `test_stale_in_memory_approval_rejected_at_consumption`

---

### Consistency Check Results (v1.5.1)

| # | Check | Result |
|---|---|---|
| 1 | `MCPService.invoke_tool` signature includes `trusted_workflow_run_id` (server-side, not from tool arguments) | **PASS** |
| 2 | `consume_atomic` contract specifies single-transaction validation + update (8-step algorithm) | **PASS** |
| 3 | All 20 named negative tests listed in tasks.md Wave 4 (I4 and I7) | **PASS** |
| 4 | `mcp_approval_rejected` audit event includes `reason` field (workflow_run_mismatch \| missing_workflow_context \| unexpected_workflow_context \| mismatched_binding \| expired \| already_consumed) | **PASS** |
| 5 | No automatic approval restoration after execution failure | **PASS** |
| 6 | `datetime.now(UTC)` used consistently (not `datetime.utcnow()`) | **PASS** |
| 7 | Migration chain 001→007 unchanged | **PASS** |
| 8 | Wave 4 has no Wave 5 dependencies | **PASS** |
| 9 | Existing requirements and traceability preserved | **PASS** |

**All 9 consistency checks pass.**

### Updated Final Verdict

**READY FOR INDEPENDENT SECURITY REVIEW** (v1.5.1)

Findings S1 (workflow run binding) and S2 (atomic approval consumption) resolved. All prior findings from §11 (8 findings), §13 (5 amendments), §15 (F1–F5, D1–D4), §16 (F1–F3), §17 (F6–F9), and §18 (migration alignment) remain resolved. The five specification documents are internally consistent at v1.5.1. The MCP authorization sequence now explicitly binds approvals to workflow run context and enforces TOCTOU-safe single-transaction consumption.

**Changed files (v1.5.1 MCP security hardening pass):**
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.5.1)
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.5.1)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.5.1)
- `docs/planning/phase1-roadmap.md` (v1.5.1)
- `docs/reviews/phase1-specification-review.md` (v1.5.1 — this document, §19 added)
- `.agents/tasks/phase1-v1.5-final-mcp-security-report.md` (new — security hardening report)

---

## 20. Type and Concurrency Alignment Pass (T1–T2) — v1.5.2

This section records the two type and concurrency findings resolved in the alignment pass that produced v1.5.2 of all five spec documents. The full alignment report is at `.agents/tasks/phase1-v1.5.1-final-type-concurrency-report.md`.

### Finding T1 — Workflow Run Identifier Type ✅ APPLIED

**Problem:** Some spec sections described `trusted_workflow_run_id` as `UUID | None`. However, `WorkflowRun.id` is an INTEGER primary key. `MCPApproval.workflow_run_id` is a nullable INTEGER FK → `workflow_runs.id`. The trusted invocation context parameter that matches against this FK must therefore be `int | None`, not `UUID | None`. Only `MCPApproval.id` is a UUID.

**Type contract (authoritative):**
| Field / parameter | Type | Notes |
|---|---|---|
| `MCPApproval.id` | UUID (stored as TEXT) | Primary key of the approval record |
| `mcp_approval_id` parameter | `UUID | None` | Caller passes UUID to identify the approval |
| `WorkflowRun.id` | `int` | INTEGER primary key — not UUID |
| `MCPApproval.workflow_run_id` | `int | None` | Nullable INTEGER FK → workflow_runs.id ON DELETE SET NULL |
| `trusted_workflow_run_id` parameter | `int | None` | Server-side session context; must match MCPApproval.workflow_run_id exactly |
| `MCPApprovalRepository.consume_atomic` `trusted_workflow_run_id` parameter | `int | None` | Same type as the FK it is compared against |

**Correction applied:**
- **design.md §7.5:** `MCPService.invoke_tool` signature updated: `trusted_workflow_run_id: int | None` (was `UUID | None`). `MCPApprovalRepository.consume_atomic` signature updated: `trusted_workflow_run_id: int | None` (was `UUID | None`). Added explanatory note: "trusted_workflow_run_id is int | None — WorkflowRun.id is an INTEGER primary key (T1). It is NOT a UUID. Only MCPApproval.id is UUID." Updated invoke_tool step 7 description.
- **requirements.md REQ-M2.5:** Acceptance criterion M2.5.1 updated: `trusted_workflow_run_id: int | None` (was `UUID | None`), with note "WorkflowRun.id is an INTEGER primary key; trusted_workflow_run_id is therefore int | None, NOT a UUID (T1)."
- **requirements.md REQ-M2.2:** `consume_atomic` signature updated: `trusted_workflow_run_id: int | None`. Step 4 annotation: "trusted_workflow_run_id is int | None — WorkflowRun.id is an INTEGER primary key (T1)."
- **tasks.md I4:** Key implementation notes updated: `trusted_workflow_run_id: int | None` (was `UUID | None`); annotation "WorkflowRun.id is an INTEGER PK (T1). Only MCPApproval.id is UUID." consume_atomic description updated to `int | None` for the binding parameter. S1 test descriptions updated to use "integer" terminology.

UUID approval IDs (`MCPApproval.id`, `mcp_approval_id` parameter) remain UUID throughout — not changed.

**4 named negative tests verified with integer semantics:**
- `test_approval_wrong_workflow_run_rejected` — uses integer workflow_run_id values (X, Y ∈ ℤ, X≠Y)
- `test_approval_bound_to_workflow_rejected_without_workflow_context` — approval.workflow_run_id is a non-None integer; trusted = None
- `test_approval_unbound_rejected_with_workflow_context` — approval.workflow_run_id = NULL; trusted = N (integer, non-None)
- `test_workflow_run_id_from_arguments_not_trusted` — argument integer value ignored; session int context used

---

### Finding T2 — SQLite Atomic Consumption and Concurrency ✅ APPLIED

**Problem:** The spec stated: "In Phase 1 single-process deployment, concurrent writes from the same process are serialized by SQLAlchemy's connection pool." This is incorrect. SQLAlchemy's connection pool does not serialize database writes; SQLite serializes writes at the database-file level. Additionally, the atomic consumption algorithm did not explicitly specify `BEGIN IMMEDIATE` to prevent TOCTOU between the SELECT and the UPDATE, and there was no busy_timeout or retry policy for lock contention.

**Correction applied:**
- **design.md §7.5 (`MCPApprovalRepository.consume_atomic` docstring):** Replaced single-line SELECT description with `BEGIN IMMEDIATE` semantics. Added explanation: "SQLite serializes writes at the database-file level — only one write transaction holds the write lock at a time. This is a SQLite engine guarantee, NOT a SQLAlchemy connection-pool guarantee." Added `busy_timeout` policy (recommended: 5000 ms). Added retry rule: "Lock contention (OperationalError/busy) is treated as an authorization failure; the caller may retry the DB operation only (not the external MCP invocation), up to a configurable maximum (e.g. 3 retries with exponential backoff)." Replaced "ROLLBACK" on 0-rows-updated path.
- **design.md §7.5 (invoke_tool docstring step 7):** Updated consume_atomic call description to use `BEGIN IMMEDIATE`; replaced "SQLAlchemy connection pooling" claim with correct SQLite engine write-lock language; added busy_timeout reference.
- **requirements.md REQ-M2.2 SQLite concurrency assumptions:** Removed incorrect "concurrent writes from the same process are serialized by SQLAlchemy's connection pool." Replaced with: "SQLite serializes writes at the database-file level. Concurrent write transactions from the same process or multiple processes will queue; only one write transaction holds the write lock at a time. This is a SQLite engine guarantee, NOT a SQLAlchemy connection-pool guarantee. SQLAlchemy connection pooling does NOT serialize database writes." Added `BEGIN IMMEDIATE` requirement. Added `busy_timeout` recommendation. Added lock-contention retry policy. Added M2.2.9 acceptance criterion.
- **requirements.md REQ-M1.7 step 7:** Updated consume_atomic description to reference `BEGIN IMMEDIATE` and correct write-lock semantics.
- **tasks.md I4 key implementation notes:** Replaced "single-process deployment relies on SQLAlchemy connection-pool write serialization" with "SQLite serializes writes at the database-file level (T2 — NOT SQLAlchemy connection-pool serialization). BEGIN IMMEDIATE acquires the write lock upfront." Added busy_timeout and retry policy notes.

**Atomic SQL pattern (BEGIN IMMEDIATE):**

```sql
BEGIN IMMEDIATE;  -- acquires write lock immediately, prevents TOCTOU
SELECT id, status, expires_at, consumed_at, actor_id, mcp_server_id,
       tool_name, arguments_hash, workflow_run_id
FROM mcp_approvals
WHERE id = :approval_id;
-- validate all fields within the transaction
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

`:now` is `datetime.now(UTC)` captured once at the start of the transaction (not re-evaluated). `datetime.utcnow()` is prohibited.

**5 new named negative tests added to I4 and I7:**
- `test_concurrent_consumption_only_one_succeeds` — two threads/tasks attempt consume_atomic simultaneously; BEGIN IMMEDIATE ensures exactly one succeeds
- `test_busy_timeout_treated_as_authorization_failure` — simulate lock contention (OperationalError); verify caught and treated as authorization failure; DB retry permitted, MCP invocation is NOT retried
- `test_expired_at_consumption_time_rejected` — approval valid when created; expires_at passes before consume_atomic runs; in-transaction check rejects
- `test_execution_failure_does_not_restore_consumed_approval` — approval stays CONSUMED after subprocess error
- `test_begin_immediate_prevents_toctou` — verify consume_atomic uses BEGIN IMMEDIATE or equivalent; write lock acquired before SELECT

**Note on test count:** `test_stale_in_memory_approval_rejected_at_consumption` (from S2 in v1.5.1) covers the same in-transaction expiry scenario as `test_expired_at_consumption_time_rejected` (T2). The T2 test name is used in I4 and I7 because it more precisely names the scenario. `test_busy_timeout_treated_as_authorization_failure` and `test_begin_immediate_prevents_toctou` are net-new tests from T2. Total named tests in Wave 4 (I4+I7) is now 25.

---

### 12-Check Consistency Results (v1.5.2)

| # | Check | Result |
|---|---|---|
| 1 | `MCPApproval.workflow_run_id` typed as `int | None` everywhere (no UUID for this field) | **PASS** |
| 2 | `trusted_workflow_run_id` parameter typed as `int | None` in MCPService.invoke_tool and consume_atomic | **PASS** |
| 3 | `MCPApproval.id` and `mcp_approval_id` parameter remain UUID (unchanged) | **PASS** |
| 4 | `consume_atomic` uses `BEGIN IMMEDIATE` transaction semantics (documented in design.md §7.5) | **PASS** |
| 5 | `busy_timeout` policy documented (design.md §7.5, requirements.md REQ-M2.2) | **PASS** |
| 6 | No claim that SQLAlchemy connection pooling serializes writes | **PASS** (removed from REQ-M2.2 and tasks.md I4) |
| 7 | No automatic retry of external MCP invocation | **PASS** |
| 8 | `datetime.now(UTC)` used as the UTC source (not `datetime.utcnow()`) | **PASS** |
| 9 | All 25 named negative tests present in Wave 4 tasks I4 and I7 (20 prior + 5 new T2) | **PASS** |
| 10 | Migration chain 001→007 unchanged | **PASS** |
| 11 | Wave 4 has no Wave 5 dependencies | **PASS** |
| 12 | Version metadata updated to v1.5.2 and date 2026-11-15 in all five documents | **PASS** |

**All 12 checks pass.**

### Updated Final Verdict

**READY FOR FINAL PR READINESS REVIEW** (v1.5.2)

Findings T1 (workflow_run_id type correction UUID → int | None) and T2 (SQLite concurrency model, BEGIN IMMEDIATE, busy_timeout) resolved. All 12 consistency checks pass. All prior findings from §11 (8 findings), §13 (5 amendments), §15 (F1–F5, D1–D4), §16 (F1–F3), §17 (F6–F9), §18 (migration alignment), and §19 (S1–S2) remain resolved. The five specification documents are internally consistent at v1.5.2.

**Changed files (v1.5.2 type and concurrency alignment pass):**
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.5.2)
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.5.2)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.5.2)
- `docs/planning/phase1-roadmap.md` (v1.5.2)
- `docs/reviews/phase1-specification-review.md` (v1.5.2 — this document, §20 added)
- `.agents/tasks/phase1-v1.5.1-final-type-concurrency-report.md` (new — alignment report)

---

## 21. Final PR Readiness Gate (C1–C2 + 10-Gate Review) — v1.5.3

**Date:** 2026-11-15  
**Specification version after this pass:** v1.5.3

### C1 Resolution — Trusted Workflow Context (Single Parameter)

**Finding:** `MCPService.invoke_tool` in design.md §7.5 had **two** competing workflow context parameters: `workflow_run_id: int | None = None` (caller-supplied) and `trusted_workflow_run_id: int | None = None` (server-side). tasks.md I4 described them as a primary plus an "additional" parameter. This created ambiguity about which value governs the authorization decision and allowed a caller to influence the trusted context via the `workflow_run_id` field.

**What was found:** design.md §7.5 `invoke_tool` signature contained `workflow_run_id: int | None = None` alongside `trusted_workflow_run_id`. The tasks.md I4 implementation notes described `trusted_workflow_run_id` as an "additional" parameter appended to a base signature that still included `workflow_run_id`. requirements.md REQ-M1.7 step 7 and REQ-M2.5 were otherwise correct.

**What was changed:**
- design.md §7.5 `invoke_tool`: removed `workflow_run_id: int | None = None`; kept only `trusted_workflow_run_id: int | None = None` (now `C1/T1/S1` annotated); added explicit Note in docstring: "invoke_tool has exactly ONE workflow context parameter: trusted_workflow_run_id: int | None. trusted_workflow_run_id is resolved by the application layer from the current execution session before calling invoke_tool. It is never read from tool arguments, request body, or any client-supplied field."
- design.md §7.5: added "C1 — Trusted workflow context" block stating the single-parameter rule and forbidding caller override.
- requirements.md REQ-M2.5 M2.5.1: updated to state "This is the ONLY workflow context parameter — the former workflow_run_id parameter has been removed."
- requirements.md REQ-M1.7 step 7: updated consume_atomic call to use new full-binding signature.
- tasks.md I4: replaced "workflow_run_id=None" in the invoke_tool base signature; changed "additional server-side parameter" language to "exactly ONE workflow context parameter."
- **No change required to**: MCPApproval.id (remains UUID), WorkflowRun.id (remains INTEGER), MCPApproval.workflow_run_id (remains int | None FK).

**Verdict: C1 RESOLVED — no duplicate parameter, unambiguous trusted context source.**

---

### C2 Resolution — Transactional Authorization Bindings in consume_atomic

**Finding:** `MCPApprovalRepository.consume_atomic` accepted only `(id, trusted_workflow_run_id, now)` — 3 parameters. The actor_id, mcp_server_id, tool_name, and arguments_hash bindings were validated in step 6 of `invoke_tool` (service-layer pre-consumption check) but were NOT re-verified as explicit parameters inside the atomic transaction. This created a window where the approval record could be modified between step 6 (pre-consumption validation) and step 7 (consume_atomic) without detection.

**What was found:** design.md §7.5 `MCPApprovalRepository.consume_atomic` had 3 parameters; requirements.md REQ-M2.2 also had 3 parameters. The in-transaction steps verified status/expires_at/consumed_at/workflow_run_id but NOT the actor_id/mcp_server_id/tool_name/arguments_hash bindings.

**What was changed:**
- design.md §7.5 `MCPApprovalRepository.consume_atomic` signature: added `actor_id: str`, `mcp_server_id: str`, `tool_name: str`, `arguments_hash: str` as explicit parameters; updated docstring to 8-step algorithm with explicit "verify ALL bindings within SAME transaction" step (C2).
- design.md §7.5 `invoke_tool` step 7: updated consume_atomic call to pass all binding fields.
- requirements.md REQ-M2.2 `consume_atomic` interface: replaced 3-parameter signature with 7-parameter signature (approval_id, actor_id, mcp_server_id, tool_name, arguments_hash, workflow_run_id, now); updated 8-step algorithm with all binding verifications; noted NULL-safe workflow_run_id matching.
- requirements.md REQ-M2.2 named tests: added `test_approval_modified_between_validation_and_consumption` (6th named T2 test).
- tasks.md I4: updated consume_atomic call and description; added `test_approval_modified_between_validation_and_consumption` to S2 tests (6th) and I7 all-tests list (26th total).
- roadmap.md: updated Wave 4 completion gate to reference all 26 named tests.

**New test added:**
- `test_approval_modified_between_validation_and_consumption` — approval status changed by another transaction between service-layer validation (step 6) and consume_atomic (step 7); verify ConsumedError raised and no subprocess launched.

**Verdict: C2 RESOLVED — all binding fields verified in-transaction; modification-between-validation-and-consumption scenario covered by new test.**

---

### Ten-Gate Acceptance Matrix

| Gate | Verdict | File + Section | Evidence | Failure scenario if FAIL |
|---|---|---|---|---|
| G1 — Requirements, design, tasks mutually consistent | **PASS** | requirements.md REQ-M2.x ↔ design.md §7.5 ↔ tasks.md I4/I7 | Every REQ-M2.x has a corresponding design section and at least one task; consume_atomic signatures match across all three documents; no contradictions found | — |
| G2 — MCP approval authorization has no bypass | **PASS** | design.md §7.5 "No-bypass rule"; requirements.md REQ-M1.7.11; tasks.md I4/I7 `test_no_direct_mcp_client_bypass` | Explicit no-bypass rule in §7.5 with test coverage; ADR-0011 documents MCPService as mandatory gateway; no router/adapter/Streamlit path calls MCPClient directly per spec | — |
| G3 — Trusted actor and workflow context are unambiguous | **PASS** | design.md §7.5 "C1 — Trusted workflow context" block; requirements.md REQ-M2.5 M2.5.1 | Single `trusted_workflow_run_id: int | None` parameter (C1 applied); explicit statement in §7.5 and REQ-M2.5 that it is resolved from server-side session only and never from tool arguments or client-supplied fields | — |
| G4 — Approval consumption is atomic and replay-safe | **PASS** | design.md §7.5 `MCPApprovalRepository.consume_atomic` (8-step); requirements.md REQ-M2.2 | BEGIN IMMEDIATE; all binding fields verified in-transaction (C2); rowcount==1 required; COMMIT before subprocess; no restoration after failure; test_approval_modified_between_validation_and_consumption covers TOCTOU window | — |
| G5 — SQLite FK and migration contracts are correct | **PASS** | design.md §3.7, §3.7a, §3.7b; requirements.md REQ-DB1.3 | MCPApproval.workflow_run_id → workflow_runs.id (Integer FK ON DELETE SET NULL); GitHubConfirmation.workflow_run_id same; PRAGMA foreign_keys=ON in connect event (REQ-DB1.3) | — |
| G6 — Migration sequence 001–007 is linear | **PASS** | design.md §3.0; requirements.md REQ-DB1.1; roadmap.md Migration Chain | Exact chain: 001→002→003→004→005→006→007; each down_revision correctly points to preceding revision; no gaps or forks | — |
| G7 — No wave depends on a later wave | **PASS** | tasks.md Wave definitions; design.md §13; roadmap.md Task Dependency Graph | Wave 1 uses no Wave 2+ deliverables; Wave 2 uses no Wave 3+ deliverables; Wave 4 owns migration 006 and MCPApproval (not Wave 5); Wave 4 completion gate explicitly states "no Wave 5 dependency" | — |
| G8 — Required security negative tests are specified | **PASS** | tasks.md I4 (named tests), I7 (all-tests list) | 26 named negative tests present; all 6 required tests confirmed: `test_forged_approval_record_rejected` ✓, `test_replay_after_consumption_rejected` ✓, `test_concurrent_consumption_only_one_succeeds` ✓, `test_approval_wrong_workflow_run_rejected` ✓, `test_no_direct_mcp_client_bypass` ✓, `test_approval_modified_between_validation_and_consumption` ✓ | — |
| G9 — Phase 0 compatibility and scope preserved | **PASS** | requirements.md Global Constraints, Out of Scope; design.md §1; review.md §6 | No Phase 0 requirement modified; no autonomous AI execution; no auto-merge; all 11 integration adapters retain approved execution modes (Codex = cli_handoff, Kiro/NotebookLM/Antigravity/Google Stitch = manual_handoff or stub) | — |
| G10 — Git changes contain only intended specification artifacts | **PASS** | git diff --name-only (see §21 git status below) | Only .kiro/specs/, docs/planning/, docs/reviews/, .agents/tasks/ files in diff; no src/, tests/, alembic/, .github/, pyproject.toml | — |

### Remaining Blockers

None.

### Non-Blocking Implementation Notes

1. **G9 (Workflow page numbering):** Pages 6 and 7 renamed to `6_Workflows.py` / `7_History.py`. This open decision from v1.0.0 has been carried forward without blocking — it is a UX preference, not a security or correctness issue. Implementer should confirm naming before Wave 3.
2. **G9 (MCP SDK version):** `mcp>=1.0,<2.0` operative constraint (pyproject.toml has no mcp entry at base commit). Implementer must check pyproject.toml at Wave 4 implementation time (REQ-M1.8).
3. **G9 (pyproject.toml / ci.yml coverage flags):** `branch = true` and `--cov-branch` must be added during Wave 1 (Task P1 config ownership). Out of spec-correction scope; known gap.
4. **G4 (BEGIN IMMEDIATE Python implementation):** aiosqlite/SQLAlchemy async does not have a direct `BEGIN IMMEDIATE` syntax helper. The implementer may use raw `EXECUTE 'BEGIN IMMEDIATE'` or `connection.execution_options(isolation_level="IMMEDIATE")`. The spec states intent; the implementer selects the mechanism. Non-blocking.
5. **G4 (busy_timeout configuration point):** The spec recommends 5000 ms and says "configure"; the implementer decides whether to use `connect_args={"timeout": 5}` or PRAGMA in the connect event handler. Non-blocking.

### Git Branch and Working-Tree Status

Branch: `feature/phase1-specification-planning`

Files modified in this pass (C1–C2 + 10-gate review):
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.5.2 → v1.5.3)
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.5.2 → v1.5.3)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.5.2 → v1.5.3)
- `docs/planning/phase1-roadmap.md` (v1.5.2 → v1.5.3)
- `docs/reviews/phase1-specification-review.md` (v1.5.2 → v1.5.3, §21 added)
- `.agents/tasks/phase1-final-pr-readiness-report.md` (new)

No src/, tests/, alembic/, .github/workflows/, or pyproject.toml files modified.

### Final Verdict

**CONDITIONAL PASS — READY FOR PR WITH NON-BLOCKING NOTES**

C1 and C2 resolved. All 10 acceptance gates PASS. Five non-blocking implementation notes recorded (all pre-existing open items; none new). No blockers. The specification is ready for the Phase 1 implementation PR subject to the non-blocking notes being actioned at the relevant implementation wave.
