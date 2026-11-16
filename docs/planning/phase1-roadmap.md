# DevFlow AI — Phase 1 Implementation Roadmap

**Version:** 1.5.7
**Status:** Wave 4 PENDING Approval Lifecycle Correction Applied
**Branch:** feature/phase1-wave4-integration-execution
**Base commit:** 756100d1166c64b001da4a044ad22513197ab408
**Last Updated:** 2026-11-16
**Supersedes:** v1.3.0 (F1–F3 corrections applied — see .agents/tasks/phase1-v1.4.0-correction-report.md)

**Version history:**
- v1.0.0 — Initial specification
- v1.1.0 — Eight independent-review findings applied
- v1.2.0 — Five amendment-round findings applied
- v1.3.0 — Final specification correction: F1–F5 and D1–D4 applied (FK test split, GitHubConfirmation persistence + migration 006, MCP authorization consistency, superseded guidance labelled, metadata corrected)
- v1.4.0 — 2026-11-15 — Corrections F1 (MCP approval authorization via approval_request_id), F2 (FK cascade test corrections), F3 (metadata), F6 (MCPApproval dedicated schema + migration 007), F7 (outdated MCP authorization references), F8 (Wave 1 FK tests), F9 (approval consumption and external failure handling). Branch: feature/phase1-specification-planning, Base: aaaaacb703124fc31b0e757b2bf1739c4fb225c9.
- v1.5.0 — Migration and dependency alignment: 006=mcp_approvals (Wave 4, Task I4), 007=github_confirmations (Wave 5, Task G1); down_revision chain updated; Wave 4 completion gate updated; Wave 5 task G1 and G5 updated. Branch: feature/phase1-specification-planning.
- v1.5.1 — MCP Security Hardening Pass (S1–S2): Wave 4 completion gate updated to require all 20 MCP negative tests passing; Security Summary table updated with workflow_run_id binding requirement and atomic consumption note. Branch: feature/phase1-specification-planning.
- v1.5.2 — 2026-11-15 — Type and Concurrency Alignment Pass (T1–T2): Wave 4 completion gate updated to require all 25 MCP negative tests (20 from S1/S2 + 5 new T2 tests); Security Summary MCP row updated to note int | None type for trusted_workflow_run_id and BEGIN IMMEDIATE transaction semantics; version metadata updated. Branch: feature/phase1-specification-planning.
- v1.5.3 — 2026-11-15 — Final PR Readiness Gate (C1–C2): C1 redundant workflow_run_id parameter removed from invoke_tool (single trusted_workflow_run_id: int | None); C2 consume_atomic extended with all binding fields; test_approval_modified_between_validation_and_consumption added; Wave 4 completion gate updated to require all 26 named tests; Security Summary MCP row updated. Branch: feature/phase1-specification-planning.
- v1.5.5 — 2026-11-16 — Wave 4 Specification Conflict Resolution (W4-CR): resolved four Wave 4 conflicts (see docs/reports/phase1-wave4-spec-resolution.md). Conflict A (MCP transport): explicit-environment subprocess + SDK `ClientSession`; SDK `stdio_client` dropped (parent-env merge; no grace control); 4 named subprocess tests added. Conflict B (approval binding): `mcp_approvals.workflow_run_id` FK `ON DELETE SET NULL` → `ON DELETE RESTRICT`; 5 named deletion/binding tests added; NULL-to-NULL bypass eliminated. Conflict C (live adapter capability): live adapters use `available_in_phase_0=False` (immutable `Literal[False]` schema). Conflict D (page numbering): Wave 4 UPDATEs existing `9_Integrations.py`/`10_Settings.py`; no new pages. Wave 4 completion gate updated with new test names. Branch: feature/phase1-wave4-integration-execution.
- v1.5.6 — 2026-11-16 — Wave 4 Final FK Contract Correction (W4-FK): resolved the v1.5.5 RESTRICT contradiction. SQLite's `ON DELETE RESTRICT` is unconditional — it blocks deletion whenever ANY referencing `mcp_approvals` row exists, regardless of approval status — so the v1.5.5 acceptance criteria (CONSUMED/PENDING/REJECTED/EXPIRED approvals permit deletion) were unimplementable. `mcp_approvals.workflow_run_id` FK changed from `ON DELETE RESTRICT` back to `ON DELETE SET NULL`, combined with a database-enforced BEFORE DELETE trigger on `workflow_runs` (`trg_workflow_runs_before_delete_expire_approved_mcp_approvals`) that expires APPROVED approvals before the FK clears the reference. Verified against real SQLite foreign-key enforcement (SQLite library 3.49.1, 17/17 checks pass). Wave 4 completion gate updated: migration 006 FK is `ON DELETE SET NULL` + the BEFORE DELETE trigger; the W4 deletion/binding test set is 9 tests (1 renamed from block→expire, 4 kept, 4 added). See docs/reports/phase1-wave4-fk-final-resolution.md. Branch: feature/phase1-wave4-integration-execution.
- v1.5.7 — 2026-11-16 — Wave 4 PENDING Approval Lifecycle Correction (W4-PA): resolved the remaining MCP authorization lifecycle gap. Wave 4 completion gate updated: BEFORE DELETE trigger updated to expire `status IN ('PENDING','APPROVED')` (renamed `trg_workflow_runs_before_delete_expire_mcp_approvals`); `test_workflow_run_deletion_allowed_with_pending_approval` renamed to `test_workflow_run_deletion_expires_pending_mcp_approval`; `test_cascaded_deletion_handles_mcp_approvals` updated; `test_trigger_rollback_restores_approval` updated; `test_orphaned_pending_approval_cannot_be_promoted` added. Total W4 deletion/binding tests: 10. See docs/reports/phase1-wave4-pending-approval-resolution.md. Branch: feature/phase1-wave4-integration-execution.

---

## Phase 1 Goal

Deliver the first functional release of DevFlow AI: a local-first development orchestrator with persistent project management, workflow state tracking with human approval gates, three live integration adapters (GitHub, Ollama, Figma), a full MCP client infrastructure, and GitHub workflow orchestration. The Streamlit UI presents real data throughout.

**Phase 1 workflow execution boundary:** WorkflowRun tracks state for human-approved processes. No autonomous AI provider invocation occurs in Phase 1. Autonomous execution of `definition_json` step definitions is deferred to Phase 2.

---

## Scope Boundaries

### In scope

| Capability | Key deliverables |
|---|---|
| Persistent project management | Live CRUD, tags, pagination, Streamlit Projects page |
| Workflow orchestration foundation | Workflow + WorkflowRun + ApprovalRequest models, state machine (6 states, no autonomous execution), audit log (6 event types) |
| Approval gates | Non-bypassable gates for all consequential actions; credential presence ≠ authorization |
| Live integration adapters | GitHub REST API, Ollama local API, Figma REST API |
| MCP client infrastructure | MCPServerConfig, MCPClient, subprocess env isolation (Python-level only), permission allow-list, secret interpolation |
| GitHub workflow orchestration | Branch listing/creation, PR listing/creation (read + confirmed write), CI status |
| Streamlit Phase 1 UI | Dashboard (live metrics), Projects, Workflows, History, Integrations, Settings |
| APIClient extension | All new backend routes exposed as typed `APIClient` methods |
| Database migrations | Alembic migrations 002–007 (linear chain from Phase 0 head) |
| Security hardening | Timeouts, credential isolation, approval enforcement, no auto-merge |

### Out of scope (deferred to Phase 2 or later)

| Capability | Reason |
|---|---|
| Autonomous AI step execution from `definition_json` | Requires safe execution sandbox and step-type dispatch — Phase 2 |
| ChatGPT / Claude live adapters | Requires paid API key; free-first policy |
| Codex CLI live execution | Real subprocess execution is a separate safety concern; stub approved for Phase 1 |
| NotebookLM, Kiro live adapters | No public programmatic API |
| Antigravity, Google Stitch | No public API documentation |
| Learning, Specifications, Design pages | Phase 2 scope |
| MCP SSE / HTTP transports | Phase 2 when connection pooling requirements are clearer |
| Multi-user access control | Local single-user tool in Phase 1 |
| PR auto-merge | Policy decision — will never be default; explicit scope exclusion |
| OS-level MCP sandbox isolation | seccomp, namespaces, cgroups — deferred; Phase 1 provides env-var scoping only |
| Android, React, TypeScript, Vite | Global constraint; not in scope for any phase |

---

## Alembic Migration Chain

Phase 0 head: `001_create_initial_tables`

Phase 1 adds six migrations in this exact chain:

```
001_create_initial_tables (Phase 0)
  └── 002_add_project_tags_column  (Wave 1 — Task P1)
        └── 003_add_workflow_tables  (Wave 2 — Task W2)
              └── 004_add_approval_audit_tables  (Wave 2 — Task W2)
                    └── 005_add_repository_tables  (Wave 2 — Task W2)
                          └── 006_add_mcp_approvals  (Wave 4 — Task I4)
                                └── 007_add_github_confirmations  (Wave 5 — Task G1)
```

| Revision ID | `down_revision` | File | Wave |
|---|---|---|---|
| `"001_create_initial_tables"` | `None` | `001_create_initial_tables.py` | Phase 0 |
| `"002_add_project_tags_column"` | `"001_create_initial_tables"` | `002_add_project_tags_column.py` | Wave 1 |
| `"003_add_workflow_tables"` | `"002_add_project_tags_column"` | `003_add_workflow_tables.py` | Wave 2 |
| `"004_add_approval_audit_tables"` | `"003_add_workflow_tables"` | `004_add_approval_audit_tables.py` | Wave 2 |
| `"005_add_repository_tables"` | `"004_add_approval_audit_tables"` | `005_add_repository_tables.py` | Wave 2 |
| `"006_add_mcp_approvals"` | `"005_add_repository_tables"` | `006_add_mcp_approvals.py` | Wave 4 |
| `"007_add_github_confirmations"` | `"006_add_mcp_approvals"` | `007_add_github_confirmations.py` | Wave 5 |

**Wave 1 migration independence:** Migration 002 chains directly from `001_create_initial_tables` (the Phase 0 head). `alembic upgrade head` in Wave 1 applies only migration 002. Wave 2 migrations (003, 004, 005) extend the chain further.

**Wave 4 migration (migration alignment):** Wave 4 delivers migration 006 (`mcp_approvals`). This migration chains from `005_add_repository_tables` (Wave 2). Wave 4 completion requires migration 006 applied and MCP approval tests passing. Wave 4 has no dependency on any Wave 5 deliverable.

**Wave 5 migration:** Wave 5 delivers migration 007 (`github_confirmations`), chaining from `006_add_mcp_approvals` (Wave 4). `alembic upgrade head` at Wave 5 completion reaches `007_add_github_confirmations`.

---

## Wave Summary

### Wave 1 — Persistent Project Management
**PR target:** `develop`
**Complexity:** Medium
**Gate:** All projects CRUD endpoints return real DB data; Projects page renders live

| Task | Description | Size |
|---|---|---|
| P1 | Alembic migration 002 (tags_json — chains from 001) | Small |
| P2 | Project model + schema extensions | Small |
| P3 | ProjectRepository + ProjectService | Medium |
| P4 | Projects router (live DB) | Medium |
| P5 | Streamlit Projects page + APIClient | Medium |
| P6 | Tests: Wave 1 | Medium |

**Wave 1 completion gate:** `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` passes; `POST /api/v1/projects` persists to SQLite; `alembic upgrade head` from Phase 0 head applies migration 002 without error; Projects page renders with live data via mocked `APIClient`.

---

### Wave 2 — Workflow Data Layer
**PR target:** `develop`
**Complexity:** High
**Gate:** Workflow + run + approval models exist; services enforce state machine; audit log populated; migrations 003–005 applied

| Task | Description | Size |
|---|---|---|
| W1 | Models: Workflow, WorkflowRun, ApprovalRequest, WorkflowAuditLog | Medium |
| W2 | Alembic migrations 003–005 | Medium |
| W3 | WorkflowRepository, WorkflowRunRepository | Medium |
| W4 | ApprovalRepository, AuditLogRepository | Medium |
| W5 | WorkflowService, ApprovalService | Medium |
| W6 | Tests: Wave 2 | Large |

**Wave 2 completion gate:** `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0; state machine transitions enforced in tests; `approval_requested` audit event logged; migration round-trips pass for all three Wave 2 migrations.

---

### Wave 3 — Workflow API and Streamlit
**PR target:** `develop`
**Complexity:** High
**Gate:** All workflow and approval endpoints live; Dashboard shows real metrics; Workflows and History pages render

| Task | Description | Size |
|---|---|---|
| A1 | Routers: workflows + workflow-runs | Medium |
| A2 | Router: approvals | Small |
| A3 | Exception handler extensions | Small |
| A4 | Streamlit: Dashboard, Workflows page, History page | Medium |
| A5 | Tests: Wave 3 | Large |

**Wave 3 completion gate:** `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0; `POST /api/v1/approvals/{id}/resolve` enforces 409 on re-resolution; Dashboard no longer shows "Phase 0" text.

---

### Wave 4 — Integration Execution
**PR target:** `develop`
**Complexity:** High
**Gate:** GitHub, Ollama, Figma live adapters tested with mocked httpx; MCP client tested with mocked subprocess; registry `get_live()` works; security tests pass

| Task | Description | Size |
|---|---|---|
| I1 | Adapter exceptions | Small |
| I2 | GitHubAdapter (live) | Medium |
| I3 | OllamaAdapter + FigmaAdapter (live) | Medium |
| I4 | MCPServerConfig + MCPClient + MCPLiveAdapter + MCPService + MCPApproval model/repository + migration 006 | Large |
| I5 | Registry: get_live, register_live | Small |
| I6 | Integrations router extension + Settings | Small |
| I7 | Streamlit: Integrations + Settings + Tests | Large |

**Wave 4 completion gate:** `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0; `registry.get_live("github")` returns live adapter when token is set, stub otherwise; MCP permission gate tested; secrets not in logs (test named `test_github_token_not_in_log_records`); subprocess env isolation tested (test named `test_mcp_subprocess_receives_explicit_env`); the 4 W4-CR Conflict A subprocess tests pass (`test_mcp_subprocess_receives_explicit_env`, `test_mcp_subprocess_does_not_inherit_parent_secrets`, `test_mcp_subprocess_terminated_on_timeout`, `test_mcp_subprocess_cleanup_in_finally_block`); timeout test named; migration 006 (`006_add_mcp_approvals`) applied with `mcp_approvals.workflow_run_id ON DELETE SET NULL` and the BEFORE DELETE trigger `trg_workflow_runs_before_delete_expire_mcp_approvals` (W4-FK / W4-PA: expires `status IN ('PENDING','APPROVED')`); MCP approval gate tests passing (all 26 named tests in `test_mcp_service.py`, including S1 workflow_run_id binding tests, S2 atomic consumption tests, T2 concurrency/BEGIN IMMEDIATE tests, and C2 modification-between-validation test); the 10 W4-FK+PA deletion/binding tests pass (`test_workflow_run_deletion_expires_approved_mcp_approval`, `test_workflow_run_deletion_allowed_after_approval_consumed`, `test_workflow_run_deletion_expires_pending_mcp_approval`, `test_null_to_null_match_rejected_for_originally_bound_approval`, `test_cascaded_deletion_handles_mcp_approvals`, `test_workflow_run_deletion_preserves_consumed_approval`, `test_workflow_run_deletion_preserves_rejected_approval`, `test_expired_approval_after_deletion_cannot_be_consumed`, `test_trigger_rollback_restores_approval`, `test_orphaned_pending_approval_cannot_be_promoted`). Wave 4 UPDATEs the existing `9_Integrations.py` and `10_Settings.py` pages (W4-CR Conflict D); no new Integrations/Settings pages are created. Wave 4 has no dependency on any Wave 5 deliverable.

---

### Wave 5 — GitHub Workflow Orchestration
**PR target:** `develop`
**Complexity:** High
**Gate:** Branch/PR creation gated by valid `GitHubConfirmation` record (`confirmation_id` in request); no merge endpoint; full migration round-trip (001→002→003→004→005); final CI green

| Task | Description | Size |
|---|---|---|
| G1 | RepositoryConfig model + repository (table created in W2); GitHubConfirmation model + repo + migration 007 | Medium |
| G2 | RepositoryService + GitHubAdapter extension | Large |
| G3 | Repositories router | Medium |
| G4 | Settings page: GitHub status | Small |
| G5 | Tests: Wave 5 + final CI verification | Large |

**Wave 5 completion gate (Phase 1 completion):**
- `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` ✓
- `mypy --strict src/` ✓
- `ruff check .` ✓
- `docs/openapi.json` regenerated, no `/merge` path
- Migrations 006 and 007 applied (`alembic upgrade head` reaches `"007_add_github_confirmations"`)
- All six GitHubConfirmation tests passing: `test_github_confirmation_persisted_to_db`, `test_confirmation_expires_after_ttl`, `test_replay_rejected_after_use`, `test_parameter_mismatch_rejected`, `test_concurrent_consumption_safe`, `test_recovery_after_github_api_failure`
- `test_github_confirmation_not_restored_after_api_failure` passing (F9)
- `test_mcp_approval_consume_atomic_safe` passing (migration 006, Wave 4 — verified in Wave 5 full round-trip)
- Full migration round-trip test passes for all 7 migrations (001→007)
- All Phase 0 tests still pass

---

## Task Dependency Graph

```
Phase 0 baseline (aaaaacb)
    │
    ├── P1 → P2 → P3 → P4 → P5 → P6 ─── Wave 1 PR → develop
    │
    ├── W1 → W2
    │    └── W3 ──┐
    │    └── W4 ──┴── W5 → W6 ──────── Wave 2 PR → develop
    │
    ├── A1 → A2 → A3
    │    └── A4 ──────── A5 ──────────── Wave 3 PR → develop
    │
    ├── I1 → I2 ──┐
    │         I3 ──┴── I5 → I6 → I7 ─── Wave 4 PR → develop
    │         I4 ──┘
    │
    └── G1 → G2 → G3 → G4 → G5 ──────── Wave 5 PR → develop
```

**Migration dependency:** G1 (Wave 5) requires that migration `005_add_repository_tables.py` exists in the database (created by W2 in Wave 2). The dependency `"Wave 4 merged"` transitively ensures Wave 2 was merged.

---

## Security Summary

Every consequential action in Phase 1 requires explicit authorization. No action modifies external state silently.

| Action | Authorization mechanism | Note |
|---|---|---|
| Create branch | `GitHubConfirmation` record (`confirmation_id` in request) | Explicit user acknowledgement; boolean flag alone rejected |
| Create PR | `GitHubConfirmation` record (`confirmation_id` in request) | Explicit user acknowledgement; boolean flag alone rejected |
| Workflow step with external side-effect | `ApprovalRequest` resolved to `approved` | Human approval gate |
| MCP tool call | (1) Tool in `MCPServerConfig.allowed_tools` AND (2) `MCPApproval` (UUID PK, `mcp_approvals` table) validated by `MCPService` for consequential/unknown tools AND (3) `workflow_run_id` binding verified against server-side trusted context (`trusted_workflow_run_id: int | None` — single parameter, C1; WorkflowRun.id is INTEGER PK, T1; resolved from server-side session only, never from tool arguments or client-supplied fields) AND (4) atomic consumption via `BEGIN IMMEDIATE` single-transaction UPDATE (C2/S2/T2; all binding fields verified in-transaction; SQLite write serialization is a database-engine guarantee, not an SQLAlchemy connection-pool guarantee) | Allow-list alone is NOT sufficient for consequential/unknown tools; all checks are additive and sequential (F3/F6/S1/S2/T1/T2/C1/C2). `MCPApproval` is DISTINCT from workflow `ApprovalRequest`. `trusted_workflow_run_id` comes from server-side session only; it is `int | None`. |
| Live adapter call | `GitHubConfirmation` record or approved `ApprovalRequest` | Credential presence is authentication only, not authorization |
| Any credential in log | Blocked by `RedactSecretsProcessor` | Applies to all log records |
| Auto PR merge | Not supported (no endpoint) | Permanent exclusion |
| MCP subprocess env | Explicit `env=resolved_env`; no parent env inheritance | Python-level env isolation only (not OS sandbox) |

---

## Complexity Estimates

| Wave | Tasks | Story points (rough) | Calendar estimate |
|---|---|---|---|
| Wave 1 | 6 | 12–16 | 1–2 days |
| Wave 2 | 6 | 18–24 | 2–3 days |
| Wave 3 | 5 | 16–22 | 2–3 days |
| Wave 4 | 7 | 22–30 | 3–4 days |
| Wave 5 | 5 | 18–24 | 2–3 days |
| **Total** | **29** | **86–116** | **10–15 days** |

Estimates assume a single developer (Codex) working on one task at a time per wave, with same-day independent review per wave PR.

---

## References

- Requirements: `.kiro/specs/phase1-functional-orchestration/requirements.md`
- Design: `.kiro/specs/phase1-functional-orchestration/design.md`
- Tasks: `.kiro/specs/phase1-functional-orchestration/tasks.md`
- Phase 0 requirements: `.kiro/specs/foundation-and-architecture/requirements.md`
- Phase 0 design: `.kiro/specs/foundation-and-architecture/design.md`
- Phase 0 tasks: `.kiro/specs/foundation-and-architecture/tasks.md`
