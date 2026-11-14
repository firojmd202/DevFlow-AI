# DevFlow AI — Phase 1 Implementation Roadmap

**Version:** 1.0.0
**Status:** Draft — Awaiting Independent Review
**Branch:** feature/phase1-specification-planning
**Base commit:** aaaaacb703124fc31b0e757b2bf1739c4fb225c9
**Last Updated:** 2026-11-14

---

## Phase 1 Goal

Deliver the first functional release of DevFlow AI: a local-first development orchestrator with persistent project management, AI workflow tracking with approval gates, three live integration adapters (GitHub, Ollama, Figma), a full MCP client infrastructure, and GitHub workflow orchestration. The Streamlit UI presents real data throughout.

---

## Scope Boundaries

### In scope

| Capability | Key deliverables |
|---|---|
| Persistent project management | Live CRUD, tags, pagination, Streamlit Projects page |
| Workflow orchestration | Workflow + WorkflowRun + ApprovalRequest models, state machine, audit log |
| Approval gates | Non-bypassable gates for all consequential actions |
| Live integration adapters | GitHub REST API, Ollama local API, Figma REST API |
| MCP client infrastructure | MCPServerConfig, MCPClient, subprocess isolation, permission allow-list, secret interpolation |
| GitHub workflow orchestration | Branch listing/creation, PR listing/creation (read + confirmed write), CI status |
| Streamlit Phase 1 UI | Dashboard (live metrics), Projects, Workflows, History, Integrations, Settings |
| APIClient extension | All new backend routes exposed as typed `APIClient` methods |
| Database migrations | Alembic migrations 002–005 |
| Security hardening | Timeouts, credential isolation, approval enforcement, no auto-merge |

### Out of scope (deferred to Phase 2 or later)

| Capability | Reason |
|---|---|
| ChatGPT / Claude live adapters | Requires paid API key; free-first policy |
| Codex CLI live execution | Real subprocess execution is a separate safety concern; stub approved for Phase 1 |
| NotebookLM, Kiro live adapters | No public programmatic API |
| Antigravity, Google Stitch | No public API documentation |
| Learning, Specifications, Design pages | Phase 2 scope |
| MCP SSE / HTTP transports | Phase 2 when connection pooling requirements are clearer |
| Multi-user access control | Local single-user tool in Phase 1 |
| PR auto-merge | Policy decision — will never be default; explicit scope exclusion |
| Android, React, TypeScript, Vite | Global constraint; not in scope for any phase |

---

## Wave Summary

### Wave 1 — Persistent Project Management
**PR target:** `develop`
**Complexity:** Medium
**Gate:** All projects CRUD endpoints return real DB data; Projects page renders live

| Task | Description | Size |
|---|---|---|
| P1 | Alembic migration 005 (tags_json) | Small |
| P2 | Project model + schema extensions | Small |
| P3 | ProjectRepository + ProjectService | Medium |
| P4 | Projects router (live DB) | Medium |
| P5 | Streamlit Projects page + APIClient | Medium |
| P6 | Tests: Wave 1 | Medium |

**Wave 1 completion gate:** `pytest --cov=src --cov-fail-under=80` passes; `POST /api/v1/projects` persists to SQLite; Projects page renders with live data via mocked `APIClient`.

---

### Wave 2 — Workflow Data Layer
**PR target:** `develop`
**Complexity:** High
**Gate:** Workflow + run + approval models exist; services enforce state machine; audit log populated

| Task | Description | Size |
|---|---|---|
| W1 | Models: Workflow, WorkflowRun, ApprovalRequest, WorkflowAuditLog | Medium |
| W2 | Alembic migrations 002–004 | Medium |
| W3 | WorkflowRepository, WorkflowRunRepository | Medium |
| W4 | ApprovalRepository, AuditLogRepository | Medium |
| W5 | WorkflowService, ApprovalService | Medium |
| W6 | Tests: Wave 2 | Large |

**Wave 2 completion gate:** State machine transitions enforced in tests; approval resolve gates tested; migration round-trips pass.

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

**Wave 3 completion gate:** `POST /api/v1/approvals/{id}/resolve` enforces 409 on re-resolution; Dashboard no longer shows "Phase 0" text.

---

### Wave 4 — Integration Execution
**PR target:** `develop`
**Complexity:** High
**Gate:** GitHub, Ollama, Figma live adapters tested with mocked httpx; MCP client tested with mocked subprocess; registry `get_live()` works

| Task | Description | Size |
|---|---|---|
| I1 | Adapter exceptions | Small |
| I2 | GitHubAdapter (live) | Medium |
| I3 | OllamaAdapter + FigmaAdapter (live) | Medium |
| I4 | MCPServerConfig + MCPClient + MCPLiveAdapter | Large |
| I5 | Registry: get_live, register_live | Small |
| I6 | Integrations router extension + Settings | Small |
| I7 | Streamlit: Integrations + Settings + Tests | Large |

**Wave 4 completion gate:** `registry.get_live("github")` returns live adapter when token is set, stub otherwise; MCP permission gate tested; secrets not in logs.

---

### Wave 5 — GitHub Workflow Orchestration
**PR target:** `develop`
**Complexity:** High
**Gate:** Branch/PR creation gated by `confirmed=True`; no merge endpoint; full migration round-trip; final CI green

| Task | Description | Size |
|---|---|---|
| G1 | RepositoryConfig model + repository | Medium |
| G2 | RepositoryService + GitHubAdapter extension | Large |
| G3 | Repositories router | Medium |
| G4 | Settings page: GitHub status | Small |
| G5 | Tests: Wave 5 + final CI verification | Large |

**Wave 5 completion gate (Phase 1 completion):**
- `pytest --cov=src --cov-fail-under=80` ✓
- `mypy --strict src/` ✓
- `ruff check .` ✓
- `docs/openapi.json` regenerated, no `/merge` path
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

---

## Security Summary

Every consequential action in Phase 1 requires explicit authorization. No action modifies external state silently.

| Action | Authorization mechanism |
|---|---|
| Create branch | `confirmed=True` in request body |
| Create PR | `confirmed=True` in request body |
| Workflow step with external side-effect | `ApprovalRequest` resolved to `approved` |
| MCP tool call | Tool in `MCPServerConfig.allowed_tools` |
| Live adapter call | Credential present in `Settings` |
| Any credential in log | Blocked by `RedactSecretsProcessor` |
| Auto PR merge | Not supported (no endpoint) |

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
