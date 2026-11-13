# DevFlow AI — Phase 0 Specification Change Summary: v1.1.0 → v1.1.1

**Date:** 2026-11-14  
**Files Updated:**
- `.kiro/specs/foundation-and-architecture/requirements.md` → v1.1.1
- `.kiro/specs/foundation-and-architecture/design.md` → v1.1.1
- `.kiro/specs/foundation-and-architecture/tasks.md` → v1.1.1

---

## Summary

Four targeted corrections were applied to the Phase 0 specification. No requirements, task numbering, architecture decisions, or acceptance criteria were removed unless a specific correction required it. All approved v1.1.0 decisions are preserved. The 24-task structure, wave execution order, and task dependencies are unchanged.

---

## FIX 1 — Codex Integration Classification (`cli_handoff`)

**Root cause:** Codex was classified as `automated_api` in v1.1.0, implying a paid OpenAI API key dependency. DevFlow AI is local-first and free-tools-first; the Codex CLI is the preferred integration path and does not require an API key.

### requirements.md

| Section | Change |
|---|---|
| REQ-6.2 — Integration mode table | Codex row changed: `automated_api` → `cli_handoff`. Rationale column updated to explain CLI-first preference, absence of API key requirement, and documentation of auth/plan requirements. |
| REQ-6.2 — Acceptance Criteria | AC 6.2.4 added: Codex `execution_mode` must be `cli_handoff`. AC 6.2.5 added: no OpenAI API key required for Codex CLI stub. |
| REQ-6.5 — Phase 0 stub constraints | Added "subprocess calls" to the prohibition alongside network calls. |
| REQ-6.7 (new) | New requirement defining Codex CLI protocol contract: `CodexCLIRequest` and `CodexCLIResult` types, approval gate semantics, workspace restriction, timeout field, and execution log fields. Notes requirement documenting auth/plan caveats. |
| Assumptions | Assumption 4 updated (was "5" in v1.1.0): Codex CLI preferred; API key not required for CLI; API adapter is future option. |
| Out of Scope | Added: "Real Codex CLI execution or subprocess calls in Phase 0." |
| Review Findings Response | FIX 1 row added. |

### design.md

| Section | Change |
|---|---|
| §1 Architecture Overview | Added v1.1.1 correction note: Codex is `cli_handoff`, not `automated_api`. |
| §1 Technology table | Docker Compose entry now references Task 20. |
| §3 Module Boundary Diagram | `models/base.py` label updated to include `UTCDateTime` (combined with FIX 2). `codex.py` protocol comment updated to `cli_handoff`. |
| §4 Directory Layout | `protocols/codex.py` comment updated to `cli_handoff (request + approved execution)`. |
| §7.1 Capability Metadata | `auth_type` field: `"cli_auth"` added as a valid value alongside `"api_key"`, `"oauth"`, `"token"`. |
| §7.3 Per-Integration Protocol Scoping | Codex row updated: mode → `cli_handoff`; methods → `request_code_generation` + `execute_approved_request`. Rationale for `cli_handoff` added. |
| §7.4 (new) Codex CLI Request and Result Types | New section: full `CodexCLIRequest` and `CodexCLIResult` dataclass specs; `CodexAdapterProtocol` with docstrings enforcing approval gate. |
| §7.5 (new) Codex Stub Implementation Pattern | New section: complete `CodexStubAdapter` example with `IntegrationCapability.notes` documenting CLI auth/plan caveats and Phase 0 stub behaviour. |
| §7.6 Kiro stub (renumbered) | Renumbered from §7.4 to §7.6; content unchanged. |
| §7.7 Adapter Registry (renumbered) | Renumbered from §7.5 to §7.7; content unchanged. |
| §8.1 Settings Class | `CODEX_API_KEY` comment updated: "for optional future API-based adapter." |
| §15 Error Handling | Row added: `Codex stub execute_approved_request`, `request.approved == False`, raises `ValueError`. |
| §16 Testability Notes | Codex approval gate noted as unit-testable. |
| §17 Consistency Audit (new) | New section documenting post-fix verification across all ten audit points. |
| Review Findings Response | FIX 1 row added. |

### tasks.md

| Task | Change |
|---|---|
| Task 9 (Capability Metadata) | Criterion 5 added: `ExecutionMode.CLI_HANDOFF == "cli_handoff"` returns `True`. `auth_type` comment updated to include `"cli_auth"`. |
| Task 12 (Protocols + Stubs) | Description updated. Protocol scoping table updated: Codex → `cli_handoff` with `CodexCLIRequest`/`CodexCLIResult` methods. Codex-specific requirements section added (approval gate, `ValueError`, no subprocess). Criteria 6, 7, 8 added. |
| Task 13 (Registry) | Criterion 3 added: `registry.get("codex")` returns `CodexStubAdapter` with `execution_mode == "cli_handoff"`. |
| Task 16 (Router Tests) | `test_integrations_router.py` test list updated: `codex/health` asserts `cli_handoff`. |
| Task 17 (Adapter Tests) | Tests expanded: Codex `cli_handoff` assertions, approval gate `ValueError` test, approved execution returns stub without subprocess, `inspect.getfile` check for subprocess absence. Criterion 2 updated. |
| Task 24 (Documentation) | CONTRIBUTING adapter guide step 3 updated: `cli_handoff` approval gate noted. Criterion 4 updated. |
| Definition of Done | Codex `cli_handoff` checks added under Integration Adapter Contracts. `CODEX_API_KEY` check added (must be present as `SecretStr | None`). |
| Review Findings Response | FIX 1 row added. |

---

## FIX 2 — SQLite UTC Timestamp Round-Trip (`UTCDateTime` TypeDecorator)

**Root cause:** `DateTime(timezone=True)` is a no-op at the SQLite level. SQLite stores datetimes as TEXT; without a TypeDecorator, Python reads them back as naive datetimes. The correct fix is a `UTCDateTime` TypeDecorator that handles all Python-side conversion.

### requirements.md

| Section | Change |
|---|---|
| REQ-5.1 — SQLAlchemy Models | Criterion 5.1.4 updated: "use `UTCDateTime` TypeDecorator" (not `DateTime(timezone=True)` alone). Criterion 5.1.5 added: round-trip from SQLite returns `tzinfo=UTC`. Note added explaining the insufficiency of `DateTime(timezone=True)`. |
| REQ-5.6 (new) | New requirement: `UTCDateTime` TypeDecorator specification. Covers `impl = DateTime`, `process_bind_param` (UTC conversion, naive rejection with `ValueError`), `process_result_value` (always UTC), Alembic DDL compatibility, and `datetime.utcnow()` prohibition. Naive-datetime rejection policy documented. |
| REQ-8.7 (new) | New requirement: four dedicated UTCDateTime test cases (UTC, non-UTC, naive rejection, NULL). |
| Review Findings Response | FIX 2 row added. |

### design.md

| Section | Change |
|---|---|
| §5.1 (replaced) | Formerly "SQLAlchemy 2 Declarative Base." Now "UTCDateTime TypeDecorator" — full implementation spec including `process_bind_param`, `process_result_value`, naive rejection policy, `datetime.utcnow()` prohibition, and Alembic DDL note. |
| §5.2 (new, renumbered) | "SQLAlchemy 2 Declarative Base and TimestampMixin" — `TimestampMixin` now uses `UTCDateTime` (not `DateTime(timezone=True)`). Lambda rationale preserved. |
| §5.3 Phase 0 Schema (renumbered from §5.2) | Schema diagrams updated: timestamp columns annotated `(UTCDateTime — timezone-aware UTC)`. |
| §5.4 Async Session (renumbered from §5.3) | No content change; renumbered due to new §5.1/5.2. |
| §5.5 Repository Pattern (renumbered from §5.4) | No content change; renumbered. |
| §6.8 (new, in Alembic section) | Added: Alembic DDL compatibility note — `UTCDateTime.impl = DateTime` emits standard `DATETIME`; no `server_default=func.now()` used. |
| §15 Error Handling | Row added for `UTCDateTime.process_bind_param` naive datetime. |
| §16 Testability Notes | UTCDateTime round-trip added as unit-testable. Test case types listed. |
| §17 Consistency Audit | Point 4 updated for UTCDateTime. |
| Review Findings Response | FIX 2 row added. |

### tasks.md

| Task | Change |
|---|---|
| Task 7 (Database Models) | Description updated to emphasise `UTCDateTime` requirement. Deliverables: `base.py` label updated. Key implementation notes: `UTCDateTime` TypeDecorator spec, `process_bind_param` naive rejection, `process_result_value` UTC restore, `datetime.utcnow()` prohibition. Criterion 3 changed: was `DateTime(timezone=True)` check → now `UTCDateTime` TypeDecorator check. Criterion 5 added: naive datetime raises `ValueError`. Note added explaining the v1.1.1 correction. |
| Task 8 (Alembic Migration) | Note updated: "UTCDateTime.impl = DateTime emits DATETIME DDL; no server_default=func.now()." |
| Task 15 (Unit Tests) | Description updated: first task where `pytest --co -q` succeeds. `test_models.py` requirements expanded: UTC round-trip, non-UTC timezone, naive rejection, NULL, `datetime.utcnow()` grep check. Criterion 3 updated to reference REQ-8.7. Criterion 6 added: `pytest --co -q` exits 0 (REQ-1.2.4). |
| Definition of Done | Added: `datetime.utcnow()` prohibition check. UTC round-trip checks added. Naive datetime `ValueError` check added. |
| Review Findings Response | FIX 2 row added. |

---

## FIX 3 — Pytest Acceptance Criteria (Exit Code 5)

**Root cause:** REQ-1.2.4 and Task 1 criterion 3 previously accepted exit code 5 (no tests collected) as success for `pytest --collect-only`. This is incorrect — exit code 5 means no tests were found, which is a failure condition.

### requirements.md

| Section | Change |
|---|---|
| REQ-1.2.4 | Rewritten: requires at least one discoverable test; deferred to testing wave. Note added explaining the exit code 5 problem and that Task 1 uses TOML inspection, not pytest execution. |
| Review Findings Response | FIX 3 row added. |

### design.md

No changes required — FIX 3 is fully addressed by requirements.md and tasks.md.

### tasks.md

| Task | Change |
|---|---|
| Task 1 (pyproject.toml) | Criterion 3 rewritten: pytest is NOT run in Task 1; `pyproject.toml` is validated by TOML parsing (e.g., `python -c "import tomllib; ..."`). Note added explaining the fix. Definition of Done updated: criterion 3 is "verified in Task 15." |
| Task 15 (Unit Tests) | Criterion 6 added: `pytest --co -q` exits with code 0 (first point this is achievable). Description note added: this task satisfies REQ-1.2.4 for the first time. |
| Review Findings Response | FIX 3 row added. |

---

## FIX 4 — Docker Compose Task References

**Root cause:** Docker Compose is implemented in Task 20. Some references were not explicit about the task number, creating potential for confusion.

### requirements.md

| Section | Change |
|---|---|
| REQ-9.1 | Added "(Task 20)" after "Docker Compose" in the opening clause. |
| Review Findings Response | FIX 4 row added. |

### design.md

| Section | Change |
|---|---|
| §1 Architecture Overview | "containerised via Docker Compose (Task 20)" — task number added. |
| §1 Technology table | "Docker Compose v2 (Task 20)" — task number added. |
| §10 heading | Updated to "Docker Compose Service Topology (Task 20)". |
| §10.1 yaml comment | "see Task 20" added in topology comment. |
| Review Findings Response | FIX 4 row added. |

### tasks.md

| Task | Change |
|---|---|
| Task 20 | No structural changes — task is correctly numbered and scoped. Verified no stale references. |
| Definition of Done — Infrastructure | All six Docker Compose checks now explicitly reference "(Task 20)". |
| Review Findings Response | FIX 4 row added. |

**Cross-reference audit result:** All 24 tasks were reviewed. No task other than Task 18 contained a "Streamlit AppTest" reference. No task other than Task 20 contained a "Docker Compose" source reference. Task 19 correctly references Tasks 8 and 15. Task 21 correctly depends on Tasks 1–19. The wave execution order is unchanged. All dependency arrows are consistent.

---

## Consistency Audit Results (Post-Fix)

| Check | Result |
|---|---|
| Technology stack matches Python architecture | ✅ Python 3.12, Streamlit, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, Alembic, Pytest, structlog, httpx, Ruff, MyPy, Docker Compose, GitHub Actions |
| Streamlit and FastAPI responsibilities separate | ✅ Streamlit: pages + APIClient. FastAPI: routers + services + repositories + adapters. |
| Integration modes accurate | ✅ Codex=`cli_handoff`, ChatGPT/Claude/Figma/GitHub/Ollama/MCP=`automated_api`, Kiro/NotebookLM=`manual_handoff`, Antigravity/Stitch=`unknown` |
| SQLite timestamp requirements match design and tests | ✅ `UTCDateTime` TypeDecorator in design §5.1; REQ-5.6 in requirements; Task 7 criterion 3; Task 15 criterion 3; REQ-8.7 |
| All 24 tasks correct references and dependencies | ✅ Audited; Docker=Task 20, AppTest=Task 18, no stale references |
| Windows PowerShell support intact | ✅ `scripts/dev.ps1` in design §14, Task 4, REQ-2.3 |
| No Android, React, TypeScript, Vite | ✅ Absent from all three documents |
| No real AI execution in Phase 0 | ✅ All stubs return placeholders; Codex stub explicitly excludes `subprocess` |
| No mandatory paid API dependencies | ✅ All keys are `SecretStr | None`; Codex CLI requires no API key |
| Existing requirements and decisions preserved | ✅ All v1.1.0 approved content retained; only targeted corrections applied |

---

## Open Questions / Unresolved Issues

1. **Codex CLI availability and authentication:** The specification documents that Codex CLI authentication and plan limits may apply, but the specific CLI version and auth mechanism are not pinned. This should be resolved when implementation begins in Phase 1.

2. **`UTCDateTime` naive datetime policy in `process_result_value`:** When SQLite returns a string that cannot be parsed as ISO 8601 (data corruption or migration artefact), the current spec falls back to `datetime.fromisoformat()` without explicit error handling. The implementer should decide whether to raise or log-and-return-None for unparseable values and document the choice in the implementation.

3. **Codex workspace authorization:** REQ-6.7.2 and design §7.4 state that `execute_approved_request` MUST raise `ValueError` if `workspace_path` is not in the set of "authorized workspaces," but the mechanism for defining authorized workspaces (a `Settings` field, a whitelist file, etc.) is deferred to Phase 1. The Phase 0 stub skips this check; the Phase 1 implementation must define it.

4. **`pytest --co -q` vs `pytest --collect-only`:** Task 1 and REQ-1.2.4 use `--co -q` (short forms). Some pytest versions may require `--collect-only`. The implementer should confirm the short form works with the pinned pytest version and update if necessary.
