# Git Preflight — Phase 1 Wave 4 Branch Preparation

**Date:** 2026-11-16
**Repository:** `kotlinandfluttertutorial-lab/DevFlow-AI`

---

## Wave 3 PR Verification

| Field | Value |
|-------|-------|
| PR number | #11 |
| PR URL | https://github.com/kotlinandfluttertutorial-lab/DevFlow-AI/pull/11 |
| PR state | MERGED |
| Target branch | `develop` |
| Merge timestamp | 2026-11-16T04:34:38Z |
| Merge commit SHA | `756100d1166c64b001da4a044ad22513197ab408` |
| Merge commit reachability | Confirmed (exit code 0) |
| CI checks | 6/6 SUCCESS (lint, typecheck, test, secret-detection, dependency-scan, sast) |
| Spec version | v1.5.4 (confirmed) |

## Repository State

| Field | Value |
|-------|-------|
| Repository path | `J:\Android\GenAI\DevFlow-AI` |
| Remote URL | `https://github.com/kotlinandfluttertutorial-lab/DevFlow-AI.git` |
| Local develop SHA | `756100d1166c64b001da4a044ad22513197ab408` |
| Origin develop SHA | `756100d1166c64b001da4a044ad22513197ab408` |
| Match | Yes (local = origin) |
| Working-tree status | Clean (only untracked report files) |

## New Branch

| Field | Value |
|-------|-------|
| Branch name | `feature/phase1-wave4-integration-execution` |
| Branch base SHA | `756100d1166c64b001da4a044ad22513197ab408` |
| Current HEAD SHA | `756100d1166c64b001da4a044ad22513197ab408` |
| Branch creation result | Created successfully from `develop` |
| Working-tree status | Clean |
| Push status | Not pushed (as instructed) |

## Wave 4 Specification Scope

**Specification paths:**
- `.kiro/specs/phase1-functional-orchestration/requirements.md` (v1.5.4)
- `.kiro/specs/phase1-functional-orchestration/design.md` (v1.5.4)
- `.kiro/specs/phase1-functional-orchestration/tasks.md` (v1.5.4)
- `docs/planning/phase1-roadmap.md`

**Wave 4 — Integration Execution (Tasks I1–I7):**

| Task | Title | Requirements | Depends on | Key deliverables |
|------|-------|-------------|------------|-------------------|
| I1 | Adapter exceptions | REQ-I1.5, M1.4, M1.5 | Wave 3 merged | `adapters/exceptions.py` — IntegrationExecutionError, MCP errors |
| I2 | Live GitHubAdapter | REQ-I1.1 | I1 | `adapters/live/github.py` — httpx async, 10s timeout, MissingCredentialError |
| I3 | Live OllamaAdapter + FigmaAdapter | REQ-I1.2, I1.3 | I1 | `adapters/live/{ollama,figma}.py` — configurable timeout, graceful health check |
| I4 | MCP client, MCPApproval, MCPService | REQ-M1.1–M1.8 | I1 | `mcp_client.py`, `mcp_live.py`, `mcp_service.py`, `models/mcp_approval.py`, `repositories/mcp_approval.py`, migration 006, lockfile, `mcp>=1.0,<2.0` |
| I5 | Registry extension (get_live, register_live) | REQ-I1.4 | I2, I3, I4 | `registry.py`, `main.py` — live/stub fallback |
| I6 | Integrations router + Settings extension | REQ-I1.6, M1.1, S1.2 | I5 | `routers/integrations.py`, `config.py`, `.env.example` — mode field, MCP config validator |
| I7 | Streamlit Integrations/Settings pages + Wave 4 tests | REQ-I1.6, U1.5, T1.1 | I5 | `pages/3_Integrations.py`, `pages/4_Settings.py`, all Wave 4 tests |

**Dependencies:** I1 → I2, I3, I4 → I5 → I6 → I7

## Migration 006 Chain Verification

| Field | Value |
|-------|-------|
| Migration name | `006_add_mcp_approvals` |
| down_revision | `005_add_repository_tables` |
| Tables created | `mcp_approvals` |
| Wave assignment | Wave 4 |
| Full chain | `001 → 002 → 003 → 004 → 005 → 006` |

**MCPApproval model fields:**
- `id`: UUID (TEXT PK)
- `mcp_server_id`: TEXT NOT NULL
- `tool_name`: TEXT NOT NULL
- `arguments_hash`: TEXT NOT NULL
- `actor_id`: TEXT NOT NULL
- `workflow_run_id`: INTEGER (FK → workflow_runs.id, ON DELETE SET NULL, nullable)
- `status`: TEXT (CHECK: PENDING, APPROVED, REJECTED, EXPIRED, CONSUMED)
- `requested_at`, `resolved_at`, `expires_at`, `consumed_at`: UTCDateTime

**Indexes:** idx_mcp_approvals_server, idx_mcp_approvals_status, idx_mcp_approvals_expires

## MCP Security Acceptance Criteria

**MCPService.invoke_tool — 9-step authorization sequence:**
1. Verify MCP server configured and enabled
2. Verify tool on allow-list
3. Classify tool (read_only | consequential | unknown)
4. Default unknown → consequential
5. Retrieve MCPApproval from MCPApprovalRepository by mcp_approval_id (UUID)
6. Validate: status=APPROVED, not expired, all bindings match (server, tool, arguments_hash, actor, workflow_run_id)
7. `consume_atomic` — single SQLite BEGIN IMMEDIATE transaction (TOCTOU-safe, rowcount=1 required, commit before subprocess)
8. Invoke MCP tool through MCPClient
9. Record audit events (mcp_tool_invoked / mcp_tool_failed)

**Workflow run binding (trusted_workflow_run_id: int | None — server-side only):**
- approval.workflow_run_id = X, trusted = Y (X≠Y) → reject (workflow_run_mismatch)
- approval.workflow_run_id non-NULL, trusted = NULL → reject (missing_workflow_context)
- approval.workflow_run_id = NULL, trusted non-NULL → reject (unexpected_workflow_context)
- Rejected binding does NOT consume the approval

**Atomic consumption (consume_atomic):**
- BEGIN IMMEDIATE acquires write lock before SELECT (prevents TOCTOU)
- All 7 binding fields validated within the same transaction
- Conditional UPDATE: `WHERE id=? AND status='APPROVED' AND expires_at > :now AND consumed_at IS NULL`
- rowcount == 1 required; 0 rows → ConsumedError
- COMMIT before subprocess launch; no rollback on failure
- `datetime.now(UTC)` as the timestamp source
- busy_timeout: 5000ms recommended; lock contention = DB-only retry, never MCP invocation retry

**26 named negative tests:**
- Forged/expired/mismatched/replayed approval rejected
- Concurrent consumption only one succeeds
- Workflow run binding mismatches (wrong, missing, unexpected context)
- Allow-list alone insufficient for consequential tools
- No direct MCPClient bypass
- Stale in-memory approval rejected at consumption
- Approval modified between validation and consumption
- Execution failure does not restore consumed approval
- Busy timeout treated as authorization failure
- BEGIN IMMEDIATE prevents TOCTOU
- Consumed approval cannot be reused
- Expired at consumption time rejected (in-transaction check)

## Wave 4 Completion Gate

1. All new tests pass (including 26 MCP security negative tests)
2. No prior test broken
3. `pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing` exits 0
4. All tests complete without network access
5. Migration 006 applied and round-trip tested
6. Streamlit Integrations and Settings pages render (AppTest, mocked)

## Scope Boundaries

- No autonomous workflow execution (Phase 1 is non-autonomous)
- No GitHub confirmation (Wave 5, migration 007)
- No OS-level sandbox claim (environment-variable scoping only)
- MCP server binaries are operator-configured and trusted within local single-user threat model
- `mcp>=1.0,<2.0` SDK constraint with reproducible lockfile
- All MCP tests runnable offline with mocked subprocess
- No changes to existing migrations 001–005
- No Phase 0 specification modifications

## Blockers

None.

## Final Decision

**READY FOR CODEX — WAVE 4 BRANCH PREPARED**
