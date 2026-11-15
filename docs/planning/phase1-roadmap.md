# DevFlow AI — Phase 1 Implementation Roadmap

**Version:** 1.4.0
**Status:** Amendment Round Applied — Awaiting Final Independent Review
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Last Updated:** 2026-11-15
**Supersedes:** v1.3.0 (F1–F3 corrections applied — see .agents/tasks/phase1-v1.4.0-correction-report.md)

**Version history:**
- v1.0.0 — Initial specification
- v1.1.0 — Eight independent-review findings applied
- v1.2.0 — Five amendment-round findings applied
- v1.3.0 — Final specification correction: F1–F5 and D1–D4 applied (FK test split, GitHubConfirmation persistence + migration 006, MCP authorization consistency, superseded guidance labelled, metadata corrected)
- v1.4.0 — 2026-11-15 — Corrections F1 (MCP approval authorization via approval_request_id), F2 (FK cascade test corrections), F3 (metadata), F6 (MCPApproval dedicated schema + migration 007), F7 (outdated MCP authorization references), F8 (Wave 1 FK tests), F9 (approval consumption and external failure handling). Branch: feature/phase1-specification-planning, Base: aaaaacb703124fc31b0e757b2bf1739c4fb225c9.

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
                          └── 006_add_github_confirmations  (Wave 5 — Task G1)
                                └── 007_add_mcp_approvals  (Wave 5 — Task G1 extended)
```

| Revision ID | `down_revision` | File | Wave |
|---|---|---|---|
| `"001_create_initial_tables"` | `None` | `001_create_initial_tables.py` | Phase 0 |
| `"002_add_project_tags_column"` | `"001_create_initial_tables"` | `002_add_project_tags_column.py` | Wave 1 |
| `"003_add_workflow_tables"` | `"002_add_project_tags_column"` | `003_add_workflow_tables.py` | Wave 2 |
| `"004_add_approval_audit_tables"` | `"003_add_workflow_tables"` | `004_add_approval_audit_tables.py` | Wave 2 |
| `"005_add_repository_tables"` | `"004_add_approval_audit_tables"` | `005_add_repository_tables.py` | Wave 2 |
| `"006_add_github_confirmations"` | `"005_add_repository_tables"` | `006_add_github_confirmations.py` | Wave 5 |
| `"007_add_mcp_approvals"` | `"006_add_github_confirmations"` | `007_add_mcp_approvals.py` | Wave 5 |

**Wave 1 migration independence:** Migration 002 chains directly from `001_create_initial_tables` (the Phase 0 head). `alembic upgrade head` in Wave 1 applies only migration 002. Wave 2 migrations (003, 004, 005) extend the chain further.

**Wave 5 migration reassignment (F6):** Wave 5 now delivers two migrations: 006 (`github_confirmations`) and 007 (`mcp_approvals`). Both are Task G1 deliverables. `alembic upgrade head` at Wave 5 completion reaches `007_add_mcp_approvals`.

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
| I4 | MCPServerConfig + MCPClient + MCPLiveAdapter | Large |
| I5 | Registry: get_live, register_live | Small |
| I6 | Integrations router extension + Settings | Small |
| I7 | Streamlit: Integrations + Settings + Tests | Large |

**Wave 4 completion gate:** `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits with code 0; `registry.get_live("github")` returns live adapter when token is set, stub otherwise; MCP permission gate tested; secrets not in logs (test named `test_github_token_not_in_log_records`); subprocess env isolation tested (test named `test_mcp_subprocess_launched_with_explicit_env`); timeout test named.

---

### Wave 5 — GitHub Workflow Orchestration
**PR target:** `develop`
**Complexity:** High
**Gate:** Branch/PR creation gated by valid `GitHubConfirmation` record (`confirmation_id` in request); no merge endpoint; full migration round-trip (001→002→003→004→005); final CI green

| Task | Description | Size |
|---|---|---|
| G1 | RepositoryConfig model + repository (table created in W2); GitHubConfirmation model + repo + migration 006; MCPApproval model + repo + migration 007 | Medium |
| G2 | RepositoryService + GitHubAdapter extension | Large |
| G3 | Repositories router | Medium |
| G4 | Settings page: GitHub status | Small |
| G5 | Tests: Wave 5 + final CI verification | Large |

**Wave 5 completion gate (Phase 1 completion):**
- `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` ✓
- `mypy --strict src/` ✓
- `ruff check .` ✓
- `docs/openapi.json` regenerated, no `/merge` path
- Migrations 006 and 007 applied (`alembic upgrade head` reaches `"007_add_mcp_approvals"`)
- All six GitHubConfirmation tests passing: `test_github_confirmation_persisted_to_db`, `test_confirmation_expires_after_ttl`, `test_replay_rejected_after_use`, `test_parameter_mismatch_rejected`, `test_concurrent_consumption_safe`, `test_recovery_after_github_api_failure`
- `test_github_confirmation_not_restored_after_api_failure` passing (F9)
- `test_mcp_approval_consume_atomic_safe` passing (F6)
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
| MCP tool call | (1) Tool in `MCPServerConfig.allowed_tools` AND (2) `MCPApproval` (UUID PK, `mcp_approvals` table) validated by `MCPService` for consequential/unknown tools | Allow-list alone is NOT sufficient for consequential/unknown tools; both checks are additive and sequential (F3/F6 correction). `MCPApproval` is DISTINCT from workflow `ApprovalRequest`. |
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
