# DevFlow AI — Phase 2 Wave 3 Specification Readiness Report

**Version:** 1.0.0
**Branch:** `feature/phase2-wave3-coding-agent-integration`
**Git baseline:** `ee57dc7` (Wave 2 merged, develop HEAD)
**Spec version:** Wave 3 v1.0.0
**Date:** 2026-11-23

---

## 1. Git Baseline

| Item | Value |
|---|---|
| Branch | `feature/phase2-wave3-coding-agent-integration` |
| HEAD commit | `ee57dc7ea73cc8cbfb5a84b606e99da5a5d96519` |
| Branched from | `develop` at `ee57dc7` |
| Wave 2 PR | #24 merged 2026-11-23 |
| Wave 2 spec | v1.6.1 (frozen) |
| Migration head | `009_add_ai_specification_generation` |

---

## 2. Specification Summary

| File | Version | Status |
|---|---|---|
| `.kiro/specs/phase2-wave3-coding-agent-integration/requirements.md` | 1.0.0 | Written |
| `.kiro/specs/phase2-wave3-coding-agent-integration/design.md` | 1.0.0 | Written |
| `.kiro/specs/phase2-wave3-coding-agent-integration/tasks.md` | 1.0.0 | Written |

### Requirement Count

| Area | Requirement IDs | Count |
|---|---|---|
| W3.1 — Manual Workflow | REQ-W3.1.1–REQ-W3.1.4 | 4 |
| W3.2 — Kiro Guided Handoff | REQ-W3.2.1–REQ-W3.2.8 | 8 |
| W3.3 — Codex CLI Integration | REQ-W3.3.1–REQ-W3.3.5 | 5 |
| W3.4 — Implementation Authorization | REQ-W3.4.1–REQ-W3.4.5 | 5 |
| W3.5 — Workspace and Artifact Management | REQ-W3.5.1–REQ-W3.5.5 | 5 |
| W3.6 — Report Validation | REQ-W3.6.1–REQ-W3.6.4 | 4 |
| W3.7 — Execution Lifecycle | REQ-W3.7.1–REQ-W3.7.5 | 5 |
| W3.8 — Isolation Prerequisite Gate | REQ-W3.8.1–REQ-W3.8.4 | 4 |
| W3.9 — FastAPI API Contracts | REQ-W3.9.1–REQ-W3.9.5 | 5 |
| W3.10 — Streamlit UI | REQ-W3.10.1–REQ-W3.10.5 | 5 |
| Security requirements | REQ-W3.S.1–REQ-W3.S.10 | 10 |
| **Total** | | **60** |

Each numbered requirement has at least one EARS-style acceptance criterion. Each acceptance criterion has a unique REQ-W3.X.Y.Z identifier.

### Task Count

| Task | Description | Size |
|---|---|---|
| W3.T1 | IsolationGate + WorkspaceValidator + Configuration | M |
| W3.T2 | KiroHandoffExecutor | L |
| W3.T3 | ReportValidator: KiroVerificationReport | M |
| W3.T4 | CodexCLIExecutor | L |
| W3.T5 | ReportValidator: CodexImplementationReport | M |
| W3.T6 | Data Model: Migration 010 | M |
| W3.T7 | ExecutionPlanService + CodingAgentAuthorizationService | M |
| W3.T8 | FastAPI Routes | L |
| W3.T9 | Streamlit UI | M |
| W3.T10 | WorkflowOrchestrator Integration | M |
| W3.T11 | Offline Security Tests | M |
| W3.T12 | Full Wave 3 Acceptance Test Suite | L |
| **Total** | | **12 tasks** |

---

## 3. Architecture Summary

Wave 3 extends the Wave 1/Wave 2 architecture additively. The existing `WorkflowOrchestrator` and `ExecutorRegistry` are reused; two new executors (`KiroHandoffExecutor`, `CodexCLIExecutor`) are registered. Five new services are added (`IsolationGate`, `WorkspaceValidator`, `ReportValidator`, `ExecutionPlanService`, `CodingAgentAuthorizationService`). Migration 010 adds 6 new tables. No existing table, service signature, or test is changed.

```
WorkflowOrchestrator (Wave 1)
  └── ExecutorRegistry
        ├── MockExecutor (Wave 1)
        ├── SpecGeneratorExecutor (Wave 2)
        ├── SpecReviewerExecutor (Wave 2)
        ├── KiroHandoffExecutor (Wave 3, NEW)
        └── CodexCLIExecutor (Wave 3, NEW)
                │
                ├── IsolationGate (NEW)
                ├── WorkspaceValidator (NEW)
                ├── ReportValidator (NEW)
                └── CodingAgentAuthorizationService (NEW)
                        └── ApprovalService (Wave 1, reused)
```

---

## 4. Manual Workflow Description

The manual workflow operates without programmatic Kiro or Codex integration:

1. User describes a feature → DevFlow AI creates specification request
2. DevFlow AI generates requirements/design/tasks (Wave 2 SpecGeneratorExecutor)
3. DevFlow AI runs AI review (Wave 2 SpecReviewerExecutor)
4. User reviews findings; spec is approved via Wave 2 approval gate
5. DevFlow AI generates Kiro verification prompt; user exports it
6. User runs Kiro independently (outside DevFlow AI)
7. User imports Kiro verification report → DevFlow AI validates it
8. User approves specification post-verification
9. User independently authorizes implementation (separate `implementation_authorization` gate)
10. DevFlow AI generates Codex implementation prompt; user exports it
11. User runs Codex manually (outside DevFlow AI)
12. User imports Codex implementation report → DevFlow AI validates it
13. Validated artifacts stored; workflow transitions to completed

Manual mode is fully functional without any programmatic Kiro or Codex integration.

---

## 5. Automated Workflow Description (with Isolation Gate)

The automated workflow path (targeting Wave 6 real execution) follows the same stages, with the addition:

- After stage 9 (implementation authorization granted), the `IsolationGate` is checked.
- If prerequisites are not met: execution is blocked (`real_execution_blocked`), no subprocess is launched, authorization is not consumed.
- If prerequisites are met (Wave 6 only): `CodexCLIExecutor` invokes the Codex CLI binary in a sandboxed process.
- In Wave 3, all `real_when_isolated` requests hit the `real_execution_blocked` state because no isolation prerequisites are configured.

---

## 6. Kiro Capability Assessment Verdict

**Verdict: NO STABLE PROGRAMMATIC API EXISTS**

Kiro operates as an IDE-integrated assistant (Kiro IDE). No documented CLI entrypoint, REST API, SDK, or supported IPC mechanism exists for external callers. Wave 3 implements guided handoff as the primary and only supported integration mode. If a stable programmatic API is published in the future, a separate `AutomatedKiroExecutor` can be added without changing the lifecycle model.

---

## 7. Codex CLI Capability Assessment Verdict

**Verdict: CLI NOT INSTALLED ON THIS MACHINE; CONTRACT DOCUMENTED FOR WAVE 6**

`codex` command is not found (exit code 1). Based on published documentation:
- Non-interactive mode: supported via `--approval-mode full-auto`
- Working directory: `--cwd` flag
- Exit codes: 0 = success, non-zero = failure
- Authentication: `OPENAI_API_KEY` environment variable

The `CodexCLIExecutor` documents the full invocation contract without implementing real subprocess invocation. Wave 6 implements real execution after CLI installation and isolation prerequisites are met.

---

## 8. Security Boundaries

| Boundary | Mechanism |
|---|---|
| Imported reports (untrusted data) | Schema validation, string sanitization, no raw pass to AI prompts |
| Workspace paths | `Path.resolve()` + approved roots check |
| Symlinks | Policy: disabled by default |
| Credentials in logs | `SecretStr`, log redaction, audit sanitization |
| Approval replay | Single-use CAS on `consumed_at` |
| Stale execution input | Canonical hash + `STALE_EXECUTION_INPUT` |
| Config flag bypass | `IsolationGate` checks actual state, not flags |
| Git operations | None in Wave 3; deferred to Wave 4 |
| Auto cloud fallback | None; failures stay failed |

---

## 9. Isolation Gate Design

The `IsolationGate` is fail-closed:
- Empty `ISOLATION_PREREQUISITES` list → `not_configured` → real execution blocked
- Unrecognized prerequisite name → `prerequisites_not_met` → blocked
- Boolean config flag alone → does NOT satisfy gate
- Real execution passes only when all named prerequisites report met (Wave 6)

Machine-readable error code: `ISOLATION_PREREQUISITES_NOT_MET`

No subprocess is launched when the gate blocks. Authorization is not consumed when blocked. Tests verify no process spawn occurs.

---

## 10. Database Changes

**Migration 010** (`010_add_coding_agent_integration`, chains from `009`):

| Table | Purpose |
|---|---|
| `handoff_records` | Kiro handoff state machine records with prompt hash and artifact digest binding |
| `handoff_findings` | Individual findings from Kiro verification reports (sanitized) |
| `execution_plans` | Canonical execution input, authorization reference, and plan lifecycle |
| `execution_attempts` | Per-attempt execution state machine with deadline and audit timestamps |
| `report_artifacts` | Uploaded reports and implementation artifacts with SHA-256 content hashes |
| `capability_records` | Snapshots of CodexCLI and isolation capability checks |

No existing Phase 0/1/Wave 1/Wave 2 table is altered. Migration is fully reversible.

---

## 11. API Contracts Summary

17 endpoints under `/api/v1/coding-agent/`. All follow Wave 2 HTTP 202/200 async pattern and existing `{"error", "code"}` envelope. Key endpoints:

- `GET /capabilities` — synchronous capability report
- `GET /isolation-status` — IsolationGate current state
- `POST /handoffs` → 202 (Kiro handoff initiation)
- `POST /handoffs/{id}/submit-report` → 202 (async validation)
- `POST /executions` → 202 (mock or blocked execution)
- `GET /executions/{id}/artifacts/{artifact_id}` — file download with hash verification

All 17 endpoints appear in the OpenAPI schema. All require `LOCAL_OPERATOR_ID` actor.

---

## 12. UI Scope

The Wave 3 Streamlit UI covers:
- Mode selection (manual/mock/real_execution_blocked) with isolation status
- Kiro handoff screen with prompt display, export, and report upload
- Verification findings with blocker/major/minor classification
- Specification approval (reuses Wave 2 component)
- Implementation authorization with expiry display
- Codex prompt export
- Implementation report upload and validation results
- Audit timeline

The UI never shows "real execution succeeded" when isolation prerequisites are not met.

---

## 13. Testing Strategy

| Test | File | Coverage |
|---|---|---|
| Security invariants | `test_wave3_security.py` | Isolation gate, path traversal, prompt injection, replay, subprocess block |
| Full acceptance | `test_wave3_acceptance.py` | W3.T12.1–W3.T12.15 (15 sub-criteria) |
| Regression | Included in acceptance suite | Wave 1/Wave 2 all pass |

All tests are offline (no live services). Target: complete within 120 seconds on the reference environment (Python 3.12, SQLite in-memory, no-cov, sequential).

---

## 14. Traceability Results

**Every requirement has acceptance criteria:** ✅
All 60 requirements (REQ-W3.1.1 through REQ-W3.S.10) have one or more EARS-style acceptance criteria with sub-requirement IDs.

**Every task maps to at least one requirement:** ✅
See traceability table in `tasks.md` header.

**Every requirement maps to at least one task:** ✅
All 10 requirement areas are covered by the task traceability summary in `tasks.md`.

**Isolation gate is fail-closed:** ✅
Verified in design.md §5.1 and REQ-W3.8.1–W3.8.3. No config-flag bypass path exists.

**No real coding-agent execution without isolation:** ✅
`IsolationGate` blocks all `real_when_isolated` requests in Wave 3.

**Wave 1 `implementation_authorization` reused, not duplicated:** ✅
`CodingAgentAuthorizationService` calls `ApprovalService.request_bound_approval` with `operation = "implementation_authorization"`.

**All 10 ADRs documented:** ✅ ADR-W3-01 through ADR-W3-10 in design.md §13.

**No contradictory state machines with Wave 1/Wave 2:** ✅
Wave 3 state machines are additive; Wave 1 `WorkflowStepRun` and Wave 2 `SpecificationRequest` state machines are unchanged.

---

## 15. Open Decisions (Unresolved ADRs)

All 10 ADRs are marked **Decided** in design.md §13. No ADRs require user approval before implementation.

**Notable design choices not requiring user approval:**
- Kiro guided handoff (not programmatic) — forced by lack of Kiro API; no alternative exists
- Codex CLI not installed — contract documented; real execution deferred to Wave 6
- Migration 010 adds 6 new tables — no alternatives considered necessary

---

## 16. Implementation Grouping Recommendation

Recommended implementation order based on dependencies:

**Group A (foundation):**
- W3.T6 — Data model (migration 010) — no implementation deps
- W3.T1 — IsolationGate + WorkspaceValidator + config

**Group B (executors and validators):**
- W3.T2 — KiroHandoffExecutor (depends on T6, T1)
- W3.T3 — ReportValidator: Kiro (depends on T2, T6)
- W3.T4 — CodexCLIExecutor (depends on T1, T6)
- W3.T5 — ReportValidator: Codex (depends on T4, T6)

**Group C (services and API):**
- W3.T7 — ExecutionPlanService + AuthorizationService (depends on T6, Wave 1)
- W3.T10 — Orchestrator integration (depends on T2, T4, T7)
- W3.T8 — FastAPI routes (depends on T1–T7)

**Group D (UI and tests):**
- W3.T9 — Streamlit UI (depends on T8)
- W3.T11 — Security tests (depends on T1–T7)
- W3.T12 — Full acceptance suite (depends on all)

---

## 17. Readiness Verdict

**PHASE 2 WAVE 3 SPECIFICATION: READY FOR CHATGPT REVIEW**

The Wave 3 specification is complete with:
- 60 requirements across 10 areas + security requirements
- 12 implementation tasks with acceptance criteria and dependency ordering
- Full architecture design with 10 ADRs (all decided)
- 6-table data model (migration 010)
- 17 API endpoints documented
- Complete security threat analysis (15 threats with mitigations)
- Isolation gate designed fail-closed with no bypass path
- All traceability checks passed

No unresolved decisions require user approval before implementation can begin.
