# Phase 2 Wave 3 — ChatGPT Verification Index

**Package:** Phase 2 Wave 3 Specification Review
**Date:** 2026-11-23
**Branch:** `feature/phase2-wave3-coding-agent-integration`
**Git baseline:** `ee57dc7` (Wave 2 merged, develop HEAD)

---

## What This Package Is

This package contains the complete specification for Phase 2 Wave 3 of DevFlow AI: **Kiro Guided Handoff and Codex CLI Integration**. The specification covers the design, requirements, and implementation tasks for integrating Kiro (spec verification) and Codex CLI (implementation) into the existing DevFlow AI workflow engine.

This is a **specification review package only**. No production code has been implemented. The reviewer's job is to verify correctness, consistency, completeness, security, and coherence of the specification documents.

---

## Where to Start

1. Read `docs/reports/phase2-wave3-spec-readiness.md` — this is the high-level summary with architecture overview, capability verdicts, and readiness assessment.
2. Read `.kiro/specs/phase2-wave3-coding-agent-integration/requirements.md` — the complete requirements specification.
3. Read `.kiro/specs/phase2-wave3-coding-agent-integration/design.md` — the architecture and design decisions.
4. Read `.kiro/specs/phase2-wave3-coding-agent-integration/tasks.md` — the implementation task breakdown.
5. Use `docs/reports/phase2-wave2-closure-verification.md` as background on what was delivered in Wave 2.
6. Use `docs/planning/phase2-roadmap.md` to understand the overall six-wave plan.

---

## File Index

| File | Purpose |
|---|---|
| `.kiro/specs/phase2-wave3-coding-agent-integration/requirements.md` | Primary review target: 60 requirements across 10 areas + security, with EARS-style acceptance criteria |
| `.kiro/specs/phase2-wave3-coding-agent-integration/design.md` | Architecture, state machines, data model (6 new tables), API route table, 10 ADRs, security architecture |
| `.kiro/specs/phase2-wave3-coding-agent-integration/tasks.md` | 12 implementation tasks (W3.T1–W3.T12) with acceptance criteria and 15-criterion acceptance test suite |
| `docs/reports/phase2-wave3-spec-readiness.md` | Readiness report: architecture summary, capability verdicts, traceability results, open decisions |
| `docs/reports/phase2-wave2-closure-verification.md` | Wave 2 closure evidence: merge verification, TruffleHog scan (0 secrets), Alembic head, Dependabot PR #20 |
| `docs/planning/phase2-roadmap.md` | Phase 2 six-wave roadmap: context for where Wave 3 fits in the overall plan |

---

## What to Check

### In `requirements.md`

1. **Requirement completeness:** Do all 10 requirement areas provide sufficient coverage for the stated Wave 3 objective? Are there gaps?
2. **Acceptance criteria:** Do all acceptance criteria have unique IDs (REQ-W3.X.Y.Z)? Are they testable?
3. **Isolation gate requirements (W3.8):** Is the fail-closed design correctly specified? Is there any path that bypasses the gate via configuration?
4. **Security requirements (W3.S):** Do the security requirements cover all threats in the threat analysis table? Are any threats under-mitigated?
5. **Manual workflow (W3.1):** Does the 14-stage manual workflow cover the full user journey without gaps?
6. **Handoff state machine (W3.2):** Are all state transitions correct? Are all terminal states identified?
7. **Report validation (W3.6):** Is the deterministic validation design sufficient to prevent malicious reports from influencing system state?
8. **Implementation authorization (W3.4):** Does the reuse of Wave 1 `implementation_authorization` correctly cover all required binding fields?

### In `design.md`

1. **Architecture consistency:** Does the design preserve Phase 0/1/Wave 1/Wave 2 layering? Are there any changes to existing service contracts?
2. **State machines (§3.1, §9.1):** Are the state machines complete? Are there any missing transitions or unreachable terminal states?
3. **Data model (§10):** Do the 6 new tables have correct schemas, FK references, and indexes? Does migration 010 chain correctly from 009?
4. **IsolationGate (§5):** Is the fail-closed design correctly implemented? Does the pseudocode in §5.1 correctly block execution when prerequisites are empty or unrecognized?
5. **WorkspaceValidator (§6.1):** Is the canonical path algorithm correct on both Windows and Linux? Does it correctly handle symlinks?
6. **ADRs (§13):** Are all 10 ADRs decided? Are the tradeoffs correctly described? Are any decisions missing?
7. **API route table (§11):** Are all 17 endpoints listed? Do HTTP status codes match the Wave 2 async pattern?
8. **Canonical execution input hash (§8.1):** Is the hash construction correct and sufficient to detect all stale input cases?

### In `tasks.md`

1. **Traceability:** Does every task map to at least one requirement? Does every requirement map to at least one task?
2. **Dependencies:** Are the task dependencies correctly ordered (no circular dependencies)?
3. **W3.T12 acceptance criteria:** Do the 15 sub-criteria cover all security invariants? Is the test suite comprehensive enough?
4. **Task sizing:** Are the L/M/S estimates reasonable for the described work?
5. **Mock execution test (W3.T12.9):** Does the test correctly verify no subprocess is launched?
6. **Recovery test (W3.T12.10):** Does the test correctly verify no AI redispatch occurs on restart?

### Cross-document checks

1. **Consistency:** Do the state machine in `design.md §9.1` and the requirements in `requirements.md §W3.7` describe the same states and transitions?
2. **Data model vs requirements:** Does the `handoff_records` table (design.md §10.1) contain all fields required by REQ-W3.2.1?
3. **API routes vs requirements:** Do the 17 API endpoints (design.md §11) cover all REQ-W3.9.1–W3.9.5 requirements?
4. **Security:** Does the threat analysis (requirements.md threat table) map to mitigations in design.md §14.2?
5. **Wave 1/Wave 2 non-regression:** Does any Wave 3 design element change or contradict an existing Wave 1/Wave 2 contract?

---

## Key Design Decisions for Review

| Decision | Location | What to Verify |
|---|---|---|
| Kiro guided handoff only (no programmatic API) | ADR-W3-02, design §3 | Is the absence of a Kiro API correctly documented? Is the handoff design robust without a programmatic API? |
| Codex CLI contract but not implemented | ADR-W3-03, design §4 | Is the contract sufficient for Wave 6 implementation? Are any required flags missing or invented? |
| IsolationGate fail-closed | ADR-W3-07, design §5, REQ-W3.8 | Can the gate be bypassed via any code path shown? |
| Reuse Wave 1 `implementation_authorization` | ADR-W3-04, design §8 | Is the binding sufficient? Are the CAS and expiry mechanisms correct? |
| Migration 010 additive only | ADR-W3-09, design §10 | Does the migration alter any existing table? Is it correctly chained from 009? |
| No GitHub operations in Wave 3 | ADR-W3-10, REQ-W3.S.7 | Is this restriction correctly enforced throughout the spec? |

---

## Background Context

- **Wave 1** delivered the `WorkflowOrchestrator`, `ExecutorRegistry`, `ApprovalService`, and 8-state step lifecycle (migration 008).
- **Wave 2** delivered AI specification generation/review, `SpecificationApprovalService`, and 7 new tables (migration 009).
- **Wave 3** (this spec) adds Kiro handoff and Codex CLI contract, 2 new executors, 5 new services, 6 new tables (migration 010).
- **Wave 6** (future) will add OS-level isolation that enables real Codex execution.

The Wave 3 spec deliberately ships no real coding-agent execution. All `real_when_isolated` requests are blocked by `IsolationGate` returning `ISOLATION_PREREQUISITES_NOT_MET`.

---

## Reviewer Notes

- The Kiro integration section (W3.2, design §3) reflects the confirmed finding that no stable programmatic Kiro API exists. If this is incorrect or outdated, the entire handoff model needs redesign.
- The Codex CLI section (W3.3, design §4) is based on published documentation as of November 2026. If the CLI has changed, the invocation contract (§4.1) needs updating.
- Security requirements (W3.S) are intentionally conservative. If any security requirement is too restrictive for the intended use case, please flag specifically which one and why.
- The 60-requirement count (requirements.md) includes both the 50 numbered WHEN/THEN requirements and the 10 security requirements (REQ-W3.S.1–W3.S.10). The readiness report treats these as the full set.
