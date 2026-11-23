# Phase 2 Wave 2 Group C implementation report

- **Date** · 23 November 2026
- **Branch** · `codex/phase2-wave2-group-c`
- **HEAD** · `affc230`, the local Group B checkpoint on Group A checkpoint `bb6d4aa`
- **Working tree** · Group C changes are local and uncommitted.
- **Baseline** · Group B verification artifacts confirm 646 passing tests, 92.52% combined coverage, 94.67% line coverage, and 82.54% branch coverage. Preflight confirmed migration 009 and MCP 2.3.0.

## Task matrix

| Task | Implementation and evidence |
| --- | --- |
| W2.T7 | Standalone and workflow-bound approval services, digest and version binding, expiry, replay checks, finding acknowledgment, and dispatch validation. |
| W2.T9 | Typed local-operator FastAPI routes, durable attempt creation, in-process job scheduling, resource checks, provider metadata, and updated OpenAPI export. |
| W2.T10 | Four Streamlit specification views using APIClient. AppTest drives the real FastAPI endpoints through an in-process ASGI bridge with deterministic inference. |
| W2.T14 | SpecGeneratorExecutor and SpecReviewerExecutor registered with the default orchestrator. Executors use injected handlers, validate contracts, and reuse durable attempt results. MockExecutor remains available. |

## Approval and dispatch

Standalone approval checks the configured actor and operation, current version, canonical digest, and expiry. New standalone approval deadlines use APPROVAL_TTL_SECONDS. An immediate SQLite write transaction owns the approval consumption CAS, digest verification, specification state CAS, and audit write. A digest failure rolls back consumption. A rejection records its own terminal timestamp, preserves the attempt, and transitions the specification to revision required.

Workflow-bound approval validates run and step ownership, then uses the Wave 1 ApprovalService. The version-to-digest binding is recorded with the approval request in the existing append-only audit log. The Wave 1 approval row still carries the workflow input hash. Approving it commits the human decision before a separate transaction verifies the specification digest and records the specification state. Dispatch validates the current approved specification and matching approval ID inside the existing protected-dispatch transaction before consuming authorization. Legacy unlinked Wave 1 gates follow their existing path. The tampering test verifies that a resolved Wave 1 approval remains unconsumed and cannot dispatch a mismatched specification.

The specification eligibility predicate checks Group C prerequisites. It is independent of Wave 1's `implementation_authorization` operation, which still requires its own approval and atomic consumption. The bound integration test resolves a valid specification approval, runs the specification gate, and confirms the downstream implementation step stays in `WAITING_APPROVAL`.

The frozen F7 rule reserves revision for Critical findings. High findings remain advisory and must be acknowledged before approval. The malformed review result remains in Group B's attempt history with its error code and deterministic finding. The HTTP status and executor report failure, and the approval service refuses it.

## Endpoint inventory

All paths below use `/api/v1/specification-requests`.

| Path | Methods |
| --- | --- |
| `/` | GET list, POST create |
| `/providers` | GET provider selection and availability |
| `/{id}` | GET retrieve, PATCH draft revision, DELETE cancel |
| `/{id}/generate` | POST start, DELETE request cancellation |
| `/{id}/status` | GET generation or review status |
| `/{id}/review` | POST start, DELETE request cancellation |
| `/{id}/review/findings` | GET current or historical findings |
| `/{id}/findings/{finding_id}/acknowledge` | POST acknowledge |
| `/{id}/revision` | POST request revision |
| `/{id}/approval` | POST issue or retrieve a digest-bound pending approval |
| `/{id}/approve` | POST resolve approval or rejection |
| `/{id}/versions` | GET version history |
| `/{id}/versions/{version_id}/artifacts/{artifact_type}` | GET a stored artifact |
| `/{id}/audit` | GET paginated audit history |

The approval response exposes the decision, version, approval identifier, and expiry. This common response works for standalone requests without a workflow foreign key and omits Wave 1 dispatch fields. The server derives actor identity from local settings. Generation and review persist attempts before scheduling in-process background work. Process-restart recovery belongs to Group D.

## UI and executor integration

The Streamlit navigation includes Feature request, Generation, Review findings, and Specification approval. The views show model choices, generation and review progress, cancellation, artifacts and side-by-side versions, finding severity and source, revisions, digest confirmation, and audit history. Approval controls are disabled for failed reviews and blocking findings. Approval and state rules remain enforced by FastAPI. Ollama is the local default. The provider listing exposes OpenAI only when it has been configured and performs its health check only for the local provider.

The orchestrator injects typed generation and review handlers. Executors return validated artifact references and review severity counts. Existing workflow snapshot, lease, fencing, timeout, and cancellation handling owns dispatch. An attempt that is already complete is read from storage. No generated artifact is executed.

## Verification

`$py` denotes `.venv/Scripts/python.exe`. Tests use isolated SQLite, ASGI transport and AppTest, with mocked inference.

| Gate | Command | Result |
| --- | --- | --- |
| Focused and UI regressions | `& $py -m pytest --no-cov -q tests/integration/test_wave2_group_c.py tests/smoke/test_ui_pages.py tests/unit/test_health.py` | Exit 0, 46 passed. |
| Group A, B, Phase 1 and Wave 1 | `& $py -m pytest --no-cov -q tests/unit/test_wave2_providers.py tests/unit/test_wave2_mcp_adapter.py tests/unit/test_wave2_specification_services.py tests/unit/test_mcp_client.py tests/unit/test_mcp_service.py tests/unit/test_mcp_approval_repository.py tests/unit/test_workflow_orchestration.py tests/unit/test_approval_service.py tests/unit/test_approvals_router.py tests/unit/test_workflow_executors.py tests/integration/test_specification_migration.py` | Exit 0, 236 passed. |
| Full suite | `$env:COVERAGE_FILE='.coverage.wave2-group-c-release'; & $py -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=html:htmlcov/group-c-release` | Exit 0, 684 passed in 544.16 seconds. Combined coverage was 92.11%. |
| Separate coverage rates | `& $py -m coverage json --data-file .coverage.wave2-group-c-release -o .venv/wave2-group-c-release-coverage.json` | Exit 0, 94.48% line coverage (5,890 of 6,234) and 81.72% branch coverage (1,162 of 1,422). The separate branch gate exceeded 80%. |
| Ruff, typing and whitespace | `& $py -m ruff check .`, `& $py -m ruff format --check .`, `& $py -m mypy --strict src/ tests/`, `git diff --check` | All exit 0, 214 files formatted and 203 source files type-checked. |
| OpenAPI | `& $py scripts/export_openapi.py` and the focused API parity test | Export exit 0. Parity covered by focused tests. |
| Alembic, dependencies and lock | `& $py -m alembic heads`, `& $py -m pip check`, `uv lock --check --offline --no-build-isolation --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` | Exit 0 on each. Head 009, 68 locked packages. Isolated schema comparison covered by migration regression. |
| Offline Bandit | `& $py -m bandit -c pyproject.toml -r src/ -ll -f json -o .venv/wave2-group-c-bandit.json` | Exit 0, no findings at the configured threshold. |
| Offline TruffleHog | `docker run --rm --pull never --network none --mount "type=bind,source=$scanRoot,target=/scan,readonly" trufflesecurity/trufflehog:3.90.0 filesystem /scan --no-update --no-verification --fail --json` | Exit 0, zero candidate secrets, with networking and verification disabled. |

An initial full run passed 657 tests with 76.30% branch coverage. An overlapped intermediate run had two legacy AppTest timeouts. The next full run passed 669 tests and measured 79.11% branch coverage. The branch-focused run, `$env:COVERAGE_FILE='.coverage.wave2-group-c-supplement'; & $py -m pytest -q --cov=src --cov-branch --cov-fail-under=0 --cov-report= tests/integration/test_wave2_group_c.py`, exited 0 with 38 tests passed. Combining that data with the 669-test run using `$env:COVERAGE_FILE='.coverage.wave2-group-c-verified'; & $py -m coverage combine --keep .coverage.wave2-group-c-complete .coverage.wave2-group-c-supplement` gave 94.51% line, 81.72% branch and 92.14% combined coverage. The expanded, single-invocation full result appears in the table above.
## Remaining risks and Group D readiness

Group C passed its final full-suite and coverage gates. Group D may proceed after verification of this branch. The remaining lifecycle risk is a process restart after an attempt is persisted and before its in-process job completes. Startup recovery remains assigned to Group D.

WAVE 2 GROUP C COMPLETE — READY FOR CHATGPT VERIFICATION
