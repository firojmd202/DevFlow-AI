# DevFlow AI — Phase 1 Specification Planning Report

**Generated:** 2026-11-14  
**Branch:** `feature/phase1-specification-planning`  
**Base commit:** `aaaaacb703124fc31b0e757b2bf1739c4fb225c9`  
**Status:** READY FOR INDEPENDENT SPECIFICATION REVIEW

---

## 1. Specification Summary

### Phase 1 Goals

Phase 1 is the first functional release of DevFlow AI. It replaces Phase 0 stubs with real, database-backed behaviour, introduces an AI workflow orchestration layer with explicit approval gates, brings three live integration adapters online, implements a full MCP client infrastructure, and adds GitHub workflow orchestration support. The Streamlit UI advances from placeholder pages to working CRUD interfaces backed by real API data.

### In-Scope Capabilities

| Capability | Key deliverables |
|---|---|
| Persistent project management | Live `POST/GET/PUT/DELETE /api/v1/projects`, `ProjectRepository`, `ProjectService`, Streamlit Projects page, `tags_json` column via migration 005 |
| Workflow orchestration | `Workflow`, `WorkflowRun`, `ApprovalRequest`, `WorkflowAuditLog` models; `WorkflowService`, `ApprovalService`; `/api/v1/workflows`, `/api/v1/approvals` endpoints |
| Approval gates | Non-bypassable `ApprovalRequest` gates for consequential workflow actions; `confirmed: bool` body field for direct API calls |
| Live integration adapters | `GitHubAdapter`, `OllamaAdapter`, `FigmaAdapter` — real HTTP calls, offline-safe mocked tests |
| MCP client infrastructure | `MCPServerConfig`, `MCPClient`, `MCPLiveAdapter`; stdio subprocess transport; tool permission allow-list; secret interpolation |
| GitHub workflow orchestration | Branch listing/creation, PR listing/creation (read + confirmed write), CI check status; no auto-merge |
| Streamlit Phase 1 UI | Dashboard (live metrics), Projects (live CRUD), Workflows, History, Integrations, Settings (extended) |
| APIClient extension | All new backend routes exposed as typed `APIClient` methods with consistent error-absorbing contracts |
| Database migrations | Alembic migrations 002–005 (hand-authored, reviewed, round-trip tested) |
| Security hardening | Timeouts, credential isolation in `SecretStr`, approval enforcement, `RedactSecretsProcessor`, no merge endpoint |

### Out-of-Scope Capabilities

| Capability | Reason |
|---|---|
| ChatGPT / Claude live adapters | Require paid API keys; free-first policy |
| Codex CLI live execution | Real subprocess execution is a distinct safety concern; stub approved for Phase 1 |
| NotebookLM, Kiro live adapters | No public programmatic API available |
| Antigravity, Google Stitch | No public API documentation |
| Learning, Specifications, Design pages | Phase 2 scope |
| MCP SSE / HTTP transports | Phase 2 when connection pooling requirements are clearer |
| Multi-user access control | Local single-user tool in Phase 1 |
| PR auto-merge | Policy decision — will never be default; explicitly prohibited by REQ-S1.4 |
| Android, React, TypeScript, Vite | Global architectural constraint; excluded from all phases |

### Architecture Decisions

1. **Phase 0 modular monolith preserved.** No structural change to the two-process (Streamlit + FastAPI) architecture, the `APIClient`/router/service/repository/adapter layering, or any Phase 0 module interface.

2. **Registry dual-mode (`get` vs `get_live`).** The Phase 0 `AdapterRegistry.get()` method is unchanged and always returns the stub. A new `get_live()` method returns the live adapter when credentials are present, falling back to the stub transparently. This keeps Phase 0 tests intact.

3. **Service layer introduced for Phase 1 domains.** `ProjectService`, `WorkflowService`, `ApprovalService`, and `RepositoryService` own all business logic, state machine enforcement, and audit logging. Routers remain thin injection points.

4. **State machine enforced at the repository layer.** `WorkflowRunRepository.transition_status(run_id, new_status, valid_from=[...])` raises `InvalidStatusTransitionError` for disallowed transitions, returning HTTP 422 to callers. This prevents status corruption regardless of which code path triggers the transition.

5. **MCP via stdio transport only.** The MCP Python SDK's `stdio_client` is used in Phase 1. SSE and HTTP transports are deferred to Phase 2. This is simpler, isolates subprocess lifetime per call, and avoids long-lived connection state.

6. **Confirmation gate pattern.** GitHub branch creation and PR creation require `confirmed: bool = True` in the request body. Workflow step actions reaching an approval gate require a resolved `ApprovalRequest`. These are independent mechanisms covering direct API callers and orchestrated workflows respectively.

7. **UTCDateTime on all new timestamps.** All Phase 1 models use the Phase 0 `UTCDateTime` TypeDecorator, consistent with the global constraint prohibiting `datetime.utcnow()`.

8. **Streamlit pages 6 and 7 renamed.** `6_Coding.py` → `6_Workflows.py`, `7_Testing.py` → `7_History.py`. Navigation registration in `app.py` is updated. Phase 2 restores coding and testing pages at new numbers or replaces with appropriate content.

### Integration Execution Modes (All 11 Adapters)

| Integration | Phase 0 mode | Phase 1 planned mode | Notes |
|---|---|---|---|
| ChatGPT | `automated_api` (stub) | `automated_api` (stub, unchanged) | Requires paid key; deferred to Phase 2 |
| Codex | `cli_handoff` (stub) | `cli_handoff` (stub, unchanged) | Real CLI execution deferred; safety concern |
| Kiro | `manual_handoff` (stub) | `manual_handoff` (stub, unchanged) | No public programmatic API |
| Claude | `automated_api` (stub) | `automated_api` (stub, unchanged) | Requires paid key; deferred to Phase 2 |
| Antigravity | `unknown` (stub) | `unknown` (stub, unchanged) | No public API documentation |
| Google Stitch | `unknown` (stub) | `unknown` (stub, unchanged) | No public API documentation |
| Figma | `automated_api` (stub) | `automated_api` (**live** when `FIGMA_TOKEN` present) | Official REST API v1 |
| NotebookLM | `manual_handoff` (stub) | `manual_handoff` (stub, unchanged) | No public programmatic API |
| GitHub | `automated_api` (stub) | `automated_api` (**live** when `GITHUB_TOKEN` present) | REST API v3 + GraphQL Check Runs API |
| Ollama | `automated_api` (stub) | `automated_api` (**live** when local binary running) | Local REST API; no key required |
| MCP Servers | `automated_api` (stub) | `automated_api` (**live** when `MCP_SERVERS_CONFIG` configured) | stdio transport via MCP Python SDK |

---

## 2. Implementation Roadmap

### Wave 1 — Persistent Project Management

**PR target:** `develop`  
**Estimated complexity:** Medium (12–16 story points, 1–2 days)  
**Gate:** `POST /api/v1/projects` persists to SQLite; Projects page renders live data via mocked `APIClient`

| Task ID | Description | Size | Dependencies |
|---|---|---|---|
| P1 | Alembic migration 005: `tags_json` column | Small | Phase 0 complete |
| P2 | Project model + schema extensions (`ProjectResponse`, `ProjectUpdate`) | Small | P1 |
| P3 | `ProjectRepository` + `ProjectService` | Medium | P2 |
| P4 | Projects router (live DB calls, HTTP 201 on create) | Medium | P3 |
| P5 | Streamlit Projects page + `APIClient` project methods | Medium | P4 |
| P6 | Tests: service, router, smoke, migration 005 round-trip | Medium | P1–P5 |

**Requirements:** REQ-P1.1–P1.6, REQ-DB1.1, REQ-DB1.2, REQ-T1.1, REQ-T1.4

---

### Wave 2 — Workflow Data Layer

**PR target:** `develop`  
**Estimated complexity:** High (18–24 story points, 2–3 days)  
**Gate:** State machine transitions enforced in tests; approval resolve gates tested; migration round-trips pass

| Task ID | Description | Size | Dependencies |
|---|---|---|---|
| W1 | Models: `Workflow`, `WorkflowRun`, `ApprovalRequest`, `WorkflowAuditLog` | Medium | Wave 1 merged |
| W2 | Alembic migrations 002–004 | Medium | W1 |
| W3 | Repositories: `WorkflowRepository`, `WorkflowRunRepository` | Medium | W1, W2 |
| W4 | Repositories: `ApprovalRepository`, `AuditLogRepository` | Medium | W1, W2 |
| W5 | Services: `WorkflowService`, `ApprovalService` | Medium | W3, W4 |
| W6 | Tests: service tests, migration 002–004 round-trips | Large | W1–W5 |

**Requirements:** REQ-W1.1–W1.7, REQ-DB1.1, REQ-T1.1, REQ-T1.3, REQ-T1.4

---

### Wave 3 — Workflow API and Streamlit

**PR target:** `develop`  
**Estimated complexity:** High (16–22 story points, 2–3 days)  
**Gate:** All workflow/approval endpoints live; Dashboard removes "Phase 0" text; Workflows and History pages render

| Task ID | Description | Size | Dependencies |
|---|---|---|---|
| A1 | Routers: `workflows`, `workflow-runs` endpoints | Medium | Wave 2 merged |
| A2 | Router: `approvals` endpoints | Small | A1 |
| A3 | Exception handler extensions (`ApprovalAlreadyResolvedError` → 409, etc.) | Small | A1, A2 |
| A4 | Streamlit: Dashboard (live metrics), `6_Workflows.py`, `7_History.py`; `APIClient` extension | Medium | A1, A2 |
| A5 | Tests: router tests, smoke tests for new pages | Large | A1–A4 |

**Requirements:** REQ-W1.4–W1.6, REQ-I1.5, REQ-S1.1, REQ-U1.1–U1.4, REQ-T1.1, REQ-T1.2, REQ-T1.4

---

### Wave 4 — Integration Execution

**PR target:** `develop`  
**Estimated complexity:** High (22–30 story points, 3–4 days)  
**Gate:** `registry.get_live("github")` returns live adapter when token set; MCP permission gate tested; secrets not in logs

| Task ID | Description | Size | Dependencies |
|---|---|---|---|
| I1 | Adapter exceptions: `IntegrationExecutionError`, MCP errors | Small | Wave 3 merged |
| I2 | Live adapter: `GitHubAdapter` | Medium | I1 |
| I3 | Live adapters: `OllamaAdapter` + `FigmaAdapter` | Medium | I1 |
| I4 | MCP client: `MCPServerConfig`, `MCPClient`, `MCPLiveAdapter` | Large | I1 |
| I5 | Registry extension: `get_live`, `register_live` | Small | I2, I3, I4 |
| I6 | Integrations router extension + Settings field additions | Small | I5 |
| I7 | Streamlit: Integrations page, Settings page; Tests: Wave 4 | Large | I1–I6 |

**Requirements:** REQ-I1.1–I1.6, REQ-M1.1–M1.6, REQ-S1.2–S1.3, REQ-S1.5, REQ-U1.5, REQ-T1.1, REQ-T1.2, REQ-T1.4

---

### Wave 5 — GitHub Workflow Orchestration

**PR target:** `develop`  
**Estimated complexity:** High (18–24 story points, 2–3 days)  
**Gate:** Branch/PR creation gated by `confirmed=True`; no merge endpoint; full migration round-trip; final CI green

| Task ID | Description | Size | Dependencies |
|---|---|---|---|
| G1 | `RepositoryConfig` model + migration 004 + `RepositoryConfigRepository` | Medium | Wave 4 merged |
| G2 | `RepositoryService` + `GitHubAdapter` extension (branches, PRs, CI checks) | Large | G1 |
| G3 | Repositories router (all branch/PR/CI endpoints) | Medium | G2 |
| G4 | Settings page: GitHub connection status display | Small | G3 |
| G5 | Tests: Wave 5 + final CI verification (`mypy`, `ruff`, `pytest --cov`) | Large | G1–G4 |

**Requirements:** REQ-G1.1–G1.6, REQ-S1.1, REQ-S1.4, REQ-T1.1–T1.4

### Phase 1 Completion (Definition of Done)

- `pytest --cov=src --cov-fail-under=80` ✓
- `mypy --strict src/` ✓
- `ruff check .` ✓
- All Phase 0 tests still pass ✓
- `docs/openapi.json` regenerated; no `/merge` path present ✓
- All five waves merged to `develop` ✓
- `docs/reviews/phase1-specification-review.md` verdict: READY ✓

---

## 3. Files Created

| File | Absolute Path | Size |
|---|---|---|
| Phase 1 requirements | `j:\Android\GenAI\DevFlow-AI\.kiro\specs\phase1-functional-orchestration\requirements.md` | 36,582 bytes |
| Phase 1 design | `j:\Android\GenAI\DevFlow-AI\.kiro\specs\phase1-functional-orchestration\design.md` | 41,045 bytes |
| Phase 1 tasks | `j:\Android\GenAI\DevFlow-AI\.kiro\specs\phase1-functional-orchestration\tasks.md` | 39,646 bytes |
| Phase 1 roadmap | `j:\Android\GenAI\DevFlow-AI\docs\planning\phase1-roadmap.md` | 8,271 bytes |
| Phase 1 specification review | `j:\Android\GenAI\DevFlow-AI\docs\reviews\phase1-specification-review.md` | 13,668 bytes |

**Total specification content:** ~139,212 bytes across five files.

---

## 4. Git State

| Field | Value |
|---|---|
| Current branch | `feature/phase1-specification-planning` |
| Base commit | `aaaaacb703124fc31b0e757b2bf1739c4fb225c9` |
| Phase 0 merge PR | #7 (merged to `develop` 2026-11-14T06:07:16Z) |
| Working-tree untracked | `.agents/` (new), `kiro-specs.zip` (new) |
| Implementation files modified | **None** |

### Confirmation of No Implementation Changes

The following directories and files are **unchanged** from the Phase 0 baseline:

| Path | Status |
|---|---|
| `src/` | Unmodified — all Phase 0 source files intact |
| `tests/` | Unmodified — no test files added or changed |
| `alembic/` | Unmodified — no new migration files |
| `docker-compose.yml` | Unmodified |
| `pyproject.toml` | Unmodified |
| `requirements/` | Unmodified |
| `.kiro/specs/foundation-and-architecture/` | Unmodified — Phase 0 specs preserved |

The five specification and planning files were written exclusively to:
- `.kiro/specs/phase1-functional-orchestration/` (3 files)
- `docs/planning/` (1 file)
- `docs/reviews/` (1 file)

This report is written to `.agents/tasks/` (1 file). No other paths were touched.

---

## 5. Specification Content Summary

### requirements.md

- **47 numbered EARS-style requirements** in nine areas:
  - Area 1 — Persistent Project Management (REQ-P1.1–P1.6)
  - Area 2 — AI Workflow Orchestration Foundation (REQ-W1.1–W1.7)
  - Area 3 — Integration Execution (REQ-I1.1–I1.6)
  - Area 4 — MCP Client Infrastructure (REQ-M1.1–M1.6)
  - Area 5 — GitHub Workflow Orchestration (REQ-G1.1–G1.6)
  - Area 6 — Streamlit Phase 1 Experience (REQ-U1.1–U1.5)
  - Area 7 — Database Migrations (REQ-DB1.1–DB1.2)
  - Area 8 — Security Requirements (REQ-S1.1–S1.5)
  - Area 9 — Testing Requirements (REQ-T1.1–T1.4)
- Each requirement uses WHEN/THEN/IF-THEN EARS format with numbered acceptance criteria
- Security requirements are explicit and independently testable

### design.md

- Full architecture diagram (Phase 1 ASCII system diagram)
- Complete new database schema (5 tables: `workflows`, `workflow_runs`, `approval_requests`, `workflow_audit_log`, `repository_configs`) with SQL DDL
- Workflow state machine diagram with valid/invalid transitions table
- Repository, service, and adapter layer design with typed Python interfaces
- MCP client design with `MCPServerConfig`, `MCPClient`, exception hierarchy
- GitHub service split (`GitHubAdapter` for REST, `RepositoryService` for business logic)
- Complete API contracts for all new routes (§10.1–10.5)
- Pydantic v2 schema additions (§11)
- Streamlit page inventory table with Phase 0 → Phase 1 state (§12.1)
- `APIClient` full extension interface (§12.2)
- Full new file layout (§13)
- Security model: confirmation gates, approval gates, credential handling, MCP isolation (§14)
- Exception-to-HTTP-status mapping for all Phase 1 exceptions (§15)
- Observability: structured logging additions, audit trail design (§16)
- Testing strategy: offline-first, mocked adapters, `tmp_path` migrations (§17)
- Design-to-requirement traceability throughout each section

### tasks.md

- **5 implementation waves**, each targeting a dedicated GitHub PR to `develop`
- **29 implementation tasks** (P1–P6, W1–W6, A1–A5, I1–I7, G1–G5)
- Each task specifies: objective, deliverables, key implementation notes, numbered acceptance criteria, definition of done
- Wave completion gates defined
- Phase 1 definition of done explicitly stated

### phase1-roadmap.md

- Phase 1 goals summary
- In-scope / out-of-scope tables
- Wave summary with task IDs, complexity estimates, and completion gates
- Integration execution modes table (all 11 adapters, Phase 0 → Phase 1)
- Security summary table (action → authorization mechanism)
- Complexity estimates (story points + calendar days per wave; total 86–116 points, 10–15 days)

### phase1-specification-review.md

- 10-section independent review readiness checklist
- All 10 items: **PASS**
- Open questions for independent reviewer (5 items for human judgment)
- Final verdict: **READY FOR INDEPENDENT SPECIFICATION REVIEW**

---

## 6. Final Decision

**READY FOR INDEPENDENT SPECIFICATION REVIEW**

All five specification and planning files are complete, traceable, and internally consistent. No implementation work has been performed. Phase 0 specifications, source, and tests are intact. The specification is ready for independent review before Codex implementation begins.
