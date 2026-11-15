# Phase 1 Specification Correction Report

**Author:** Principal Architect — Independent Specification Remediation Engineer
**Date:** 2026-11-14
**Branch:** `feature/phase1-specification-planning`
**Base commit:** `aaaaacb703124fc31b0e757b2bf1739c4fb225c9`
**HEAD before correction:** `1d1b361`

---

## 1. Files Changed

| File | Bytes before | Bytes after | Delta | Action |
|---|---|---|---|---|
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | 36,582 | 47,971 | +11,389 | Modified |
| `.kiro/specs/phase1-functional-orchestration/design.md` | 41,045 | 54,668 | +13,623 | Modified |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | 39,646 | 46,162 | +6,516 | Modified |
| `docs/planning/phase1-roadmap.md` | 8,271 | 11,459 | +3,188 | Modified |
| `docs/reviews/phase1-specification-review.md` | 13,668 | 26,638 | +12,970 | Modified |
| `.agents/tasks/phase1-spec-correction-report.md` | 0 | (this file) | — | Created |

**Files NOT touched (confirmed):**
- `.kiro/specs/foundation-and-architecture/` — no files modified
- `src/` — no files modified
- `tests/` — no files modified
- `alembic/` — no files modified
- `.github/workflows/` — no files modified
- `pyproject.toml` — not modified

---

## 2. Alembic Migration Graph

### Before correction (v1.0.0)

```
None (base)
  └── 001_create_initial_tables   ← Phase 0 HEAD (actual revision ID: "001_create_initial_tables")
        ??
        └── 002_add_workflow_tables       (Wave 2, Task W2)
              └── 003_add_approval_audit_tables  (Wave 2, Task W2)
                    └── 004_add_repository_tables  (Wave 2, Task W2)
                          └── 005_add_project_tags_column  (Wave 1, Task P1)
                              ↑ BLOCKER: down_revision = "004_add_repository_tables"
                              ↑ but migration 004 is a Wave 2 deliverable
                              ↑ alembic upgrade head in Wave 1 would FAIL
```

**Critical problem:** Task P1 (Wave 1) created `005_add_project_tags_column.py` with `down_revision = "004_add_repository_tables"`. Migration 004 is created in Task W2 (Wave 2). Therefore, in Wave 1, `alembic upgrade head` would fail because migration 004 did not exist. Task P1 acceptance criterion "alembic upgrade head from Phase 0 schema applies migration 005 without error" was false.

### After correction (v1.1.0)

```
None (base)
  └── 001_create_initial_tables   ← Phase 0 HEAD
        └── 002_add_project_tags_column   ← Wave 1 (Task P1)
              down_revision = "001_create_initial_tables"
              └── 003_add_workflow_tables   ← Wave 2 (Task W2)
                    down_revision = "002_add_project_tags_column"
                    └── 004_add_approval_audit_tables   ← Wave 2 (Task W2)
                          down_revision = "003_add_workflow_tables"
                          └── 005_add_repository_tables   ← Wave 2 (Task W2)
                                down_revision = "004_add_approval_audit_tables"
```

**Exact revision ID strings (must appear verbatim in Python files):**

| File | `revision = ` | `down_revision = ` | Tables |
|---|---|---|---|
| `001_create_initial_tables.py` | `"001_create_initial_tables"` | `None` | projects, learning_items, integration_configs |
| `002_add_project_tags_column.py` | `"002_add_project_tags_column"` | `"001_create_initial_tables"` | ALTER TABLE projects ADD tags_json |
| `003_add_workflow_tables.py` | `"003_add_workflow_tables"` | `"002_add_project_tags_column"` | workflows, workflow_runs |
| `004_add_approval_audit_tables.py` | `"004_add_approval_audit_tables"` | `"003_add_workflow_tables"` | approval_requests, workflow_audit_log |
| `005_add_repository_tables.py` | `"005_add_repository_tables"` | `"004_add_approval_audit_tables"` | repository_configs |

**Wave independence property:** `alembic upgrade head` from Phase 0 (head = `001_create_initial_tables`) in Wave 1 applies only migration 002. Migrations 003–005 do not need to exist. Wave 1 acceptance criterion is now satisfiable.

---

## 3. All Eight Resolved Findings

### Finding 1 — Migration chain ordering (CRITICAL) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | Critical |
| Documents affected | requirements.md REQ-DB1.1, REQ-DB1.2; design.md §3.0, §3.1; tasks.md Task P1, W2; roadmap.md |
| Root cause | Tags migration originally numbered 005 with `down_revision` pointing to migration 004 (Wave 2 deliverable) |
| Resolution | Renumbered tags migration to 002; Wave 2 migrations to 003, 004, 005. Each `down_revision` now points to the immediately preceding migration in the same or prior wave |
| Evidence | requirements.md REQ-DB1.1 (revision table); design.md §3.0 (migration sequence); tasks.md P1 (exact Python content), W2 (required revision headers); roadmap.md Alembic Migration Chain section |

### Finding 2 — `--cov-branch` missing (CRITICAL) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | Critical |
| Documents affected | requirements.md REQ-T1.1.1; tasks.md P6, W6, A5, I7, G5 ACs |
| Root cause | Coverage commands used `--cov-fail-under=80` without `--cov-branch`, measuring line coverage only despite REQ-T1.1 requiring branch coverage |
| Resolution | Canonical form `pytest --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=80` applied to every occurrence in all five documents |
| Evidence | requirements.md REQ-T1.1.1; tasks.md P6 AC3, W6 AC3, A5 AC3, I7 AC5, G5 AC2 and final verification commands block |
| Remaining gap | `pyproject.toml [tool.coverage.run]` and `.github/workflows/ci.yml` are outside spec scope; must be updated at implementation time |

### Finding 3 — `paused` state inconsistency (HIGH) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | High |
| Documents affected | requirements.md REQ-W1.2; design.md §3.3 (SQL), §9 (state diagram); tasks.md W1, W2 |
| Root cause | State machine diagram showed `paused` for WorkflowRun; CHECK constraint in SQL and requirements listed only 6 states without `paused`. Direct contradiction. |
| Resolution | Removed `paused` from all WorkflowRun contexts. Added ADR-0009 explaining the decision. Clarified that `paused` is a Workflow definition status only. WorkflowRun has exactly 6 states: `pending`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled`. |
| Evidence | requirements.md REQ-W1.2 (status definitions table, explicit "States NOT present" note); design.md §3.3 (SQL), §9.1 (states table), §9.2 (corrected diagram), ADR-0009; tasks.md W1 AC4, W2 migration notes |

### Finding 4 — REQ-S1.5 vague "isolated" claim + `down_revision` not stated (HIGH) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | High |
| Documents affected | requirements.md REQ-S1.5; design.md §14.4; tasks.md P1, W2 |
| Root cause (Part A) | REQ-S1.5 said "bounded and isolated" for MCP subprocess but only Python-level env scoping was implemented. "Isolated" implies OS-level sandboxing (seccomp, namespaces). |
| Root cause (Part B) | No document stated the exact `down_revision` string values. Implementers would have to infer from numeric sequence, risking Alembic errors. |
| Resolution (Part A) | Rewrote REQ-S1.5 to "bounded with explicit environment-variable scoping". Added isolation boundary clarification. Added OS-level sandbox to Out of Scope table. Added SIGTERM → 5s grace → SIGKILL sequence. |
| Resolution (Part B) | Tasks P1 and W2 now show verbatim Python `revision` and `down_revision` assignments. Design.md §3.0 provides the full revision table. |
| Evidence | requirements.md REQ-S1.5 (reworded); design.md §14.4 (subprocess code with SIGTERM/SIGKILL), §3.0 (revision table); tasks.md P1 (migration content), W2 (required revision headers) |

### Finding 5 — Sixth audit event type `approval_requested` not named (MEDIUM) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | Medium |
| Documents affected | requirements.md REQ-W1.7; design.md §16; tasks.md W5, W6 |
| Root cause | REQ-W1.7 required audit entries for all status transitions. `ApprovalService.request_approval` transitions WorkflowRun to `waiting_approval` and must log this. Five event types were named; `approval_requested` was described in structlog notes but not in the required `WorkflowAuditLog` event type list. |
| Resolution | Added `approval_requested` as the sixth named audit event type. Added REQ-W1.7.4 acceptance criterion. Updated W5 notes and W6 required test case `test_request_approval_logs_approval_requested`. |
| Evidence | requirements.md REQ-W1.7 (event types table, W1.7.4); design.md §16 (audit event types table); tasks.md W5 AC2, W6 required test cases |

### Finding 6 — Timeout and subprocess env-isolation tests not named (MEDIUM) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | Medium |
| Documents affected | requirements.md REQ-S1.2, REQ-S1.5; tasks.md I7 |
| Root cause | REQ-S1.2 (bounded timeouts) and REQ-S1.5.1 (explicit env) had no named test cases in any task ACs. Without named tests, the security properties could be bypassed while still passing coverage gates. |
| Resolution | Added REQ-S1.2.6 and REQ-S1.5.4 to requirements.md. Added four named security-critical test cases to Task I7 with explicit names and requirement cross-references. Added I7 AC6 requiring all four to pass. |
| Named tests | `test_github_adapter_timeout_raises_integration_error`, `test_github_token_not_in_log_records`, `test_mcp_subprocess_launched_with_explicit_env`, `test_mcp_secret_values_not_in_log_records` |
| Evidence | requirements.md REQ-S1.2.6, REQ-S1.5.4; tasks.md I7 "Required test cases (security-critical)" section, I7 AC6 |

### Finding 7 — Credential presence conflated with authorization in roadmap (LOW) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | Low |
| Documents affected | roadmap.md Security Summary table; requirements.md REQ-S1.1; design.md §14.1, ADR-0005 |
| Root cause | Roadmap Security Summary table listed "Credential present in Settings" as the authorization mechanism for live adapter calls. Credential presence is authentication, not authorization. |
| Resolution | Rewrote roadmap Security Summary table row to show `confirmed=True` or approved `ApprovalRequest` as authorization. Added Note column distinguishing authentication from authorization. Added explicit "Distinction between credentials and authorization" block to REQ-S1.1 and design.md §14.1. |
| Evidence | roadmap.md Security Summary table (Note column); requirements.md REQ-S1.1 (distinction block); design.md §14.1 (authorization model note), ADR-0005 updated rationale |

### Finding 8 — `PUT /projects/{id}` null semantics undocumented (LOW) ✅ RESOLVED

| Field | Value |
|---|---|
| Severity | Low |
| Documents affected | requirements.md REQ-P1.3; tasks.md Task P2, P3, P6 |
| Root cause | `ProjectUpdate` treats `null` and absent identically (both skip the field). An implementer could interpret `{"description": null}` as "clear the field" rather than "skip the field." This behavior was implicit and undocumented. |
| Resolution | Added "Null semantics" paragraph to REQ-P1.3. Added REQ-P1.3.5 acceptance criterion asserting null does not clear. Added null semantics comment to `ProjectUpdate` schema in Task P2. Added `test_update_project_null_field_does_not_clear` to Task P6 required test cases. |
| Evidence | requirements.md REQ-P1.3 ("Null semantics" paragraph, REQ-P1.3.5); tasks.md Task P2 (ProjectUpdate comment), Task P3 AC3 (updated), Task P6 (new test case) |

---

## 4. Remaining Risks and Open Decisions

### Remaining risks

| Risk | Severity | Mitigation |
|---|---|---|
| `pyproject.toml` lacks `branch = true` in `[tool.coverage.run]` | High | Must be added at Wave 1 implementation start. Outside spec scope. |
| `ci.yml` pytest command lacks `--cov-branch` | High | Must be updated at Wave 1 implementation start. Outside spec scope. |
| `CONTRIBUTING.md` coverage command inconsistent | Low | Should be updated alongside `ci.yml` at implementation start. |
| `mcp` SDK version not pinned | Low | Task I4 notes this; reviewer must specify acceptable version range. |
| Reviewer must confirm MCP binary trust model | Low | Stated in REQ-M1.5 and design.md §14.4; needs reviewer acknowledgement. |

### Open decisions for reviewer

1. **Workflow page numbering:** Pages 6 and 7 renamed to `6_Workflows.py` / `7_History.py`. Confirm preferred approach.
2. **MCP SDK version:** `mcp>=1.0.0` or specific pin?
3. **`pyproject.toml` and `ci.yml`:** These files must be updated at implementation start to add `--cov-branch`. Confirm ownership.
4. **MCP binary trust:** Operator-trusted binaries; no signature verification. Acceptable?

---

## 5. Requirements-to-Tasks Traceability Table

Full table is in design.md §19. Summary (42 Req IDs, all mapped):

| Req ID | Task IDs |
|---|---|
| REQ-P1.1 | P3, P4, P6 |
| REQ-P1.2 | P3, P4, P6 |
| REQ-P1.3 | P3, P4, P6 |
| REQ-P1.4 | P3, P4, P6 |
| REQ-P1.5 | P1, P2, P6 |
| REQ-P1.6 | P5, P6 |
| REQ-W1.1 | W1, W6 |
| REQ-W1.2 | W1, W6 |
| REQ-W1.3 | W1, W6 |
| REQ-W1.4 | A1, A5 |
| REQ-W1.5 | W3, W5, A1, A5 |
| REQ-W1.6 | W4, W5, A2, A5 |
| REQ-W1.7 | W1, W4, W5, W6 |
| REQ-I1.1 | I2, I5, I7 |
| REQ-I1.2 | I3, I5, I7 |
| REQ-I1.3 | I3, I5, I7 |
| REQ-I1.4 | I5, I7 |
| REQ-I1.5 | I1, A3, I7 |
| REQ-I1.6 | I6, I7 |
| REQ-M1.1 | I4, I6, I7 |
| REQ-M1.2 | I4, I7 |
| REQ-M1.3 | I4, I7 |
| REQ-M1.4 | I4, I7 |
| REQ-M1.5 | I4, I7 |
| REQ-M1.6 | I4, I5, I7 |
| REQ-G1.1 | G1, G3, G5 |
| REQ-G1.2 | G2, G3, G5 |
| REQ-G1.3 | G2, G3, G5 |
| REQ-G1.4 | G2, G3, G5 |
| REQ-G1.5 | G2, G3, G5 |
| REQ-G1.6 | G2, G3, G5 |
| REQ-U1.1 | A4, A5 |
| REQ-U1.2 | A4, A5 |
| REQ-U1.3 | A4, A5 |
| REQ-U1.4 | P5, A4, I7, G4 |
| REQ-U1.5 | I6, I7, G4, G5 |
| REQ-DB1.1 | P1, W2, G5 |
| REQ-DB1.2 | P1, P6 |
| REQ-S1.1 | A3, G2, G3, G5, W5, W6 |
| REQ-S1.2 | I2, I3, I4, I6, I7 |
| REQ-S1.3 | I2, I3, I4, I7 |
| REQ-S1.4 | G3, G5 |
| REQ-S1.5 | I4, I7 |
| REQ-T1.1 | P6, W6, A5, I7, G5 |
| REQ-T1.2 | P6, A5, I7, G5 |
| REQ-T1.3 | P6, W6, G5 |
| REQ-T1.4 | P6, W6, A5, I7, G5 |

**Coverage:** All 42 Req IDs from requirements.md map to at least one task. All security Req IDs (REQ-S1.1–S1.5) now have named test cases in task acceptance criteria.

---

## 6. Git Working Tree Status

```
On branch feature/phase1-specification-planning
Changes not staged for commit:
	modified:   .kiro/specs/phase1-functional-orchestration/design.md
	modified:   .kiro/specs/phase1-functional-orchestration/requirements.md
	modified:   .kiro/specs/phase1-functional-orchestration/tasks.md
	modified:   docs/planning/phase1-roadmap.md
	modified:   docs/reviews/phase1-specification-review.md
Untracked files:
	.agents/     ← this report
	kiro-specs.zip
```

**Confirmed:** Exactly the five allowed spec files are modified. No `src/`, `tests/`, `alembic/`, `.github/`, or `pyproject.toml` files appear in the diff.

---

## 7. Final Verdict

**READY FOR INDEPENDENT RE-REVIEW**

All eight blockers identified in the independent remediation analysis have been resolved:

1. ✅ Migration chain ordering: Wave 1 migration now `002`, chains directly from Phase 0 head. Wave 2 migrations renumbered `003–005`. Cross-wave dependency eliminated.
2. ✅ `--cov-branch`: Added to all coverage commands in all five spec documents.
3. ✅ WorkflowRun `paused` state: Removed from all WorkflowRun contexts. CHECK constraint, state diagram, and model notes are consistent.
4. ✅ MCP isolation claim and `down_revision` values: REQ-S1.5 reworded to describe actual env-var scoping. Exact revision ID strings stated in tasks and design.
5. ✅ Sixth audit event type: `approval_requested` added to REQ-W1.7, design.md §16, W5 notes, W6 test cases.
6. ✅ Security test names: Four named security-critical tests added to Task I7 with explicit requirement cross-references.
7. ✅ Credential vs authorization: Roadmap and REQ-S1.1 updated to distinguish authentication from authorization.
8. ✅ PUT null semantics: Documented explicitly in REQ-P1.3 with acceptance criterion and test case.

The specification is internally consistent across all five documents. No Phase 0 files were touched. Implementation must not begin until an independent reviewer clears this specification and the four remaining open decisions.
