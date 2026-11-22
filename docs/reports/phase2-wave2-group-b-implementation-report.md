# Phase 2 Wave 2 Group B implementation report

- **Date** · 23 November 2026
- **Branch** · `codex/phase2-wave2-group-b`
- **HEAD** · `bb6d4aa`, the local Group A checkpoint based on `1f9a076`
- **Specification** · Frozen v1.6.0
- **Working tree** · Group B changes are local and uncommitted on top of the Group A checkpoint.

The preflight verified all provider and MCP adapter files, both Group A reports, and the MCP 2.3.0 locks. The Group A working tree was checkpointed before Group B implementation. Alembic reported `008_add_workflow_execution_engine` as the starting head.

## Completion matrix

| Task | Implementation | Acceptance evidence |
| --- | --- | --- |
| W2.T4 — Generation | Durable pending and running attempts, trusted MCP context selection, fixed prompts, provider/model metadata, typed structured artifacts, deadlines and cancellation | Offline tests cover all three artifacts, provider and MCP failures, optional context, prompt injection, truncation, concurrent claiming, and persistence rollback |
| W2.T5 — Review | Pure structural checks followed by advisory AI review when no critical structural defect is present, with findings and counts stored per attempt | Tests cover critical and high outcomes, deterministic and AI sources, malformed output, history, cancellation, and manual revision |
| W2.T6 — Versioning | SQLite write serialization, compare-and-swap state changes, immutable artifact inserts, per-artifact hashes and canonical version digest | Tests cover deterministic hashes, digest tampering, concurrent state transitions, history preservation, and explicit supersession of an approved version |
| W2.T8 — Migration 009 | Seven tables and fifteen named indexes, including separate approval foreign keys and references to existing workflow runs and steps | Isolated, populated SQLite upgrade/downgrade and 001 → 009 → 001 tests. Alembic schema comparison reports no drift. |

## Migration and data preservation

Migration `009_add_ai_specification_generation` chains directly from `008_add_workflow_execution_engine`. It creates `specification_requests`, `specification_approval_requests`, `specification_versions`, `specification_artifacts`, `generation_attempts`, `review_attempts`, and `review_findings`. The migration declares the circular standalone approval reference with SQLite-compatible foreign keys. For downgrade, it clears the circular link while both new tables still exist, then drops all fifteen indexes and seven tables.

The populated test seeds a legacy workflow and run, checks foreign keys and uniqueness in the upgraded database, and verifies that legacy rows and schema objects remain present after downgrade. All migration writes used temporary test databases. The Wave 1 migration tests now pin their 008-specific checks to that revision and run Alembic metadata comparisons at the new head.

## Generation and review

Generation reserves the current draft version under a write lock and creates a pending attempt. A worker claims the attempt as running before MCP retrieval, so a second worker cannot repeat MCP calls and a later recovery service can recognize work interrupted during context retrieval. Trusted context plans are limited to 16 calls per attempt. The worker builds the budgeted prompt from fixed instructions and separately delimited feature, repository, and MCP data. Repository context is shortened before clarifying questions and other optional fields. Required input that exceeds the budget fails before the provider call.

The service calls the selected Group A provider through the protocol and uses its bounded retries. The specification attempt adds an outer deadline and polls persisted cancellation. Its final transaction writes the three artifacts, version digest, attempt outcome, and audit event together. It stores the provider input hash without the assembled prompt. MCP audit events can carry the specification request ID and workflow run ID while keeping the existing invocation policy.

The review first checks metadata, acceptance criteria, design sections, task requirements, dependencies, and cross-artifact references. AI semantic review covers completeness, consistency, testability, security and privacy, architecture compatibility, edge cases, dependency assumptions, and scope creep. Findings retain severity, location, evidence in `finding_text`, recommendation, and source. AI findings carry the frozen disclaimer. Malformed AI results produce a persisted High deterministic `AI_REVIEW_MALFORMED` finding and a corresponding attempt error code. Review attempts store the artifact digest, without a second copy of the complete artifact payload.

The frozen F7 rule resolves the conflicting W2.T5 task summary. Critical findings require revision. A High finding alone leaves the version ready for approval with the finding visible for the later human gate.

## Versioning and security

Version mutations use the existing Wave 1 `BEGIN IMMEDIATE` transaction helper, plus a conditional update for state transitions. Artifact rows are insert-only through the repository. Digest verification checks each artifact hash and the aggregate SHA-256 using the frozen requirements/design/tasks order and `
---
` separator. Draft edits create a new version and audit the prior/current version and new request hash. The exact schema stores the latest request fields and historical hashes, artifacts, and review findings. It provides no per-version snapshot column for historical raw draft inputs.

After approval, repository writes cannot change the approved version. An explicit new request may link to a prior verified approved version. Group B has no approval transition that can bypass the human gate. Original Wave 1 protected dispatch and Group A provider opt-in are exercised by regression tests. Prompt data has control characters and delimiter escapes applied before inference. Configured secrets are removed from draft text, generated artifacts, findings, and audit metadata. The services do not interpret or execute generated content.

## Verification

Commands ran from the repository root on Windows with Python 3.12.10. `$py` is `.venv/Scripts/python.exe`.

| Gate | Command | Result |
| --- | --- | --- |
| Migration head | `& $py -m alembic heads` | Exit 0, 009_add_ai_specification_generation is the sole head. |
| Migration and legacy regressions | `& $py -m pytest --no-cov -q tests/integration/test_specification_migration.py tests/integration/test_workflow_execution_migration.py tests/integration/test_database.py tests/unit/test_github_confirmation_repository.py::test_migration_full_round_trip` | Exit 0, 9 passed. |
| Group B focused | `& $py -m pytest --no-cov -q tests/unit/test_wave2_specification_services.py tests/integration/test_specification_migration.py` | Exit 0, 27 passed. |
| Group A, Phase 1 and Wave 1 | `& $py -m pytest --no-cov -q tests/unit/test_wave2_providers.py tests/unit/test_wave2_mcp_adapter.py tests/unit/test_mcp_client.py tests/unit/test_mcp_service.py tests/unit/test_mcp_approval_repository.py tests/unit/test_workflow_orchestration.py tests/unit/test_approval_service.py tests/unit/test_approvals_router.py` | Exit 0, 193 passed, including provider and MCP, workflow, and approval tests. |
| Strict MyPy and migration typing | `& $py -m mypy --strict src/ tests/ alembic/versions/009_add_ai_specification_generation.py` | Exit 0, 191 source files checked. |
| Ruff and whitespace | `& $py -m ruff check .`, `& $py -m ruff format --check .`, `git diff --check` | All exit 0, 201 files already formatted. |
| Dependency and lock consistency | `& $py -m pip check` and `uv lock --check --offline --no-build-isolation --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` | Both exit 0, no broken requirements and 68 locked packages resolved offline. |
| Offline Bandit | `& $py -m bandit -c pyproject.toml -r src/ -ll -f json -o .venv/wave2-group-b-bandit.json` | Exit 0, zero findings at the configured threshold. |
| Offline TruffleHog | `docker run --rm --pull never --network none --mount "type=bind,source=$scanRoot,target=/scan,readonly" trufflesecurity/trufflehog:3.90.0 filesystem /scan --no-update --no-verification --fail --json` | Exit 0, zero findings with networking and verification disabled. |
| Full pytest with branch coverage | `$env:COVERAGE_FILE='.coverage.wave2-group-b-final'; & $py -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=html:htmlcov/group-b-final` | Exit 0, 646 passed in 407.70 seconds. Combined coverage was 92.52%. |
| Separate coverage rates | `& $py -m coverage json --data-file .coverage.wave2-group-b-final -o .venv/wave2-group-b-coverage.json` | Exit 0, 94.67% line coverage (5,006 of 5,288) and 82.54% branch coverage (941 of 1,140). |

The first full run used the same pytest options with coverage data in .coverage.wave2-group-b and HTML in htmlcov/group-b. It exited 1 with 645 passed and one failure when a migration 008 regression called Alembic schema comparison at 008 after the head moved to 009. The corrected migration tests passed separately before the full rerun.

## Remaining risks and Group C readiness

All Group B acceptance and regression gates passed. Group C can proceed after verification against this branch. The approval implementation should consume the verified version digest and enforce the frozen finding and Wave 1 dispatch gates. Lifecycle recovery and external entry points remain assigned to their later groups.

WAVE 2 GROUP B COMPLETE — READY FOR CHATGPT VERIFICATION
