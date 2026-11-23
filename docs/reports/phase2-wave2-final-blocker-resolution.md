# DevFlow AI — Wave 2 final blocker resolution

## Repository and baseline

The branch is `codex/phase2-wave2-group-d` at `a14bd7c`, the Group C checkpoint. The working tree retains the accepted Group D source, tests and documentation. This resolution adds acceptance tests, a deterministic provider retry clock and two reports. The frozen v1.6.0 specification is unchanged.

Preflight confirmed the saved Group D result of 690 passing tests, 92.03% combined coverage, 94.43% line coverage and 81.59% branch coverage. Installed MCP is 2.3.0 and Alembic lists `009_add_ai_specification_generation` as the sole head.

## W2.T11 acceptance matrix

`C` refers to `tests/integration/test_wave2_group_c.py`, `D` to `tests/integration/test_wave2_group_d.py`, `S` to `tests/unit/test_wave2_specification_services.py`, `P` to `tests/unit/test_wave2_providers.py` and `M` to `tests/unit/test_wave2_mcp_adapter.py`. The exact frozen text follows the matrix.

| Criterion | Implementation | Test or check | Expected and observed result | Verdict |
|---|---|---|---|---|
| 1 | Offline test fixtures and fake transports | `pytest tests/ -k wave2 --no-cov -q --durations=15` | All focused tests pass in under 60 seconds. Both runs passed all 113 tests. Wall times were 69.67 s and 75.48 s. | Fail |
| 2 | Wave 1 workflow and approvals | Non-Wave-2 selection within the single full invocation | The 581 tests outside the Wave 2 selection must pass. All 581 passed in the full suite. | Pass |
| 3 | Specification services, provider/adapter and executor boundary | D `test_wave2_service_and_adapter_sources_have_no_execution_calls` | Guard finds no prohibited execution calls in scope. | Pass |
| 4 | Generation artifact persistence and audit redaction | D `test_wave2_generation_redacts_configured_cloud_key` | Synthetic OpenAI key is absent from output and persistence. | Pass |
| 5 | Provider factory and HTTP client | P `test_ollama_unavailable_without_fallback`, C `test_provider_listing_never_pings_the_configured_cloud_provider` | Mock network observes no fallback cloud request. | Pass |
| 6 | Prompt assembly | S `test_generation_uses_untrusted_mcp_and_persists_a_verified_version` | Injection stays outside instructions and a marker cannot break the context boundary. | Pass |
| 7 | Lifespan and recovery service | D `test_wave2_startup_recovers_without_replaying_attempts` | Running generation becomes `failed/INTERRUPTED` and request returns to draft. | Pass |
| 8 | Standalone approval service | C `test_simultaneous_standalone_resolution_has_one_winner` | Exactly one concurrent approval resolves. | Pass |
| 9 | Specification router, error middleware and attempt services | Fifteen-code mapping below | Stage-specific exact codes are asserted. The literal HTTP status and envelope conflicts need approval. | Pending contract approval |
| 10 | MCP adapter over Phase 1 SDK transport | M `test_context_discovery_and_invocation` | Mock subprocess discovers and invokes the tool, then returns typed context. | Pass |
| 11 | Wave 2 Python source | `mypy --strict src tests` | Exit 0, all Wave 2 source included. | Pass |
| 12 | Wave 2 Python source | `ruff check .` | Exit 0, all Wave 2 source included. | Pass |
| 13a | Standalone approval repository | D `test_wave2_standalone_consumption_requires_matching_hash_and_one_winner` | Different hash raises `ApprovalBindingMismatch` and retains unconsumed state. | Pass |
| 13b | Standalone approval repository | Same D test | One consumption succeeds and the other returns `ApprovalAlreadyResolvedError`. | Pass |
| 13c | Workflow template schema | C `test_workflow_template_rejects_standalone_specification_operation` | Workflow operation validates, standalone operation raises Pydantic `ValidationError`. | Pass |
| 13d | Audit repository and specification generation | S `test_generation_uses_untrusted_mcp_and_persists_a_verified_version` | Standalone audit rows have null workflow ID. | Pass |
| 13e | Recovery service | D `test_wave2_startup_recovers_without_replaying_attempts` | Second sweep changes zero rows and writes no duplicate events. | Pass |
| 14a | Standalone authorization predicate | C `test_full_specification_lifecycle` | Isolated inconsistent fixture with approved spec and no consumption is denied. | Pass |
| 14b | Standalone resolution and consumption | Same C test | Approved state and consumed row precede positive authorization. | Pass |
| 14c | Bound approval service | C `test_bound_approval_preserves_independent_dispatch_gate[expired]` | Mock Wave 1 expiry propagates without specification transition. | Pass |
| 14d | Protected dispatch and Wave 1 re-gating | C `test_bound_approval_preserves_independent_dispatch_gate[interrupted]` | Direct protection rejects partial approval. Orchestrator re-gates and authorization stays false. | Pass |
| 14e | Orchestrator `_advance` | C `test_bound_approval_preserves_independent_dispatch_gate[False]` | Two advances return the same approval ID, with exactly one approval row before dispatch. | Pass |
| 14f | Bound authorization predicate | C `test_bound_approval_preserves_independent_dispatch_gate` | Ready but unapproved specification cannot authorize implementation. | Pass |
| 15a | Bound approval digest verification | C `test_bound_approval_preserves_independent_dispatch_gate[True]` | Isolated digest/artifact corruption leaves the human decision approved and unconsumed, specification ready and mismatch audit recorded. | Pass |
| 15b | Digest verification and dispatch transaction | Same C case | Authorization false, old decision rejected at dispatch before and after the correction. | Pass |
| 15c | Revision, regeneration, review and bound approval | Same C case | Correction creates a new version and digest, fresh approval resolves and is consumed, old approval stays unconsumed. | Pass |
| 15d | Orchestrator expiry reconciliation | C `test_bound_approval_preserves_independent_dispatch_gate[lease_expired]` | Past authorization expiry yields no dispatch plan, leaves old authorization unconsumed and issues a new pending gate. | Pass |

### W2.T11.9 error-code traceability

| Exact code | Evidence | Observed contract |
|---|---|---|
| `INVALID_SPECIFICATION_REQUEST` | C `test_full_specification_lifecycle` | 422, response code |
| `PROVIDER_UNAVAILABLE` | C `test_generation_provider_failure_and_cancellation_api` | 202 then 200, failed attempt code |
| `PROVIDER_TIMEOUT` | Same C test | 202 then 200, failed attempt code |
| `PROVIDER_NOT_CONFIGURED` | Same C test | 400, response code |
| `PROVIDER_CANCELLED` | Same C test | 200 cancellation acceptance, 200 poll with terminal cancellation code |
| `MALFORMED_OUTPUT` | Same C test | 202 then 200, failed attempt code |
| `MCP_CONTEXT_FAILURE` | S `test_generation_failures_keep_draft_and_no_artifacts[mcp_required]` | Failed generation attempt with exact persisted code |
| `SPEC_APPROVED_NO_OVERWRITE` | C `test_full_specification_lifecycle` | 409, response code |
| `SPEC_DIGEST_MISMATCH` | Same C test | 409, response code |
| `INVALID_SPEC_TRANSITION` | C `test_critical_review_revision_requires_fresh_human_approval` | 409, response code |
| `APPROVAL_EXPIRED` | C `test_review_acknowledgment_expired_approval_and_revision_api` | 409, response code |
| `APPROVAL_ALREADY_RESOLVED` | C `test_full_specification_lifecycle` | 409, response code |
| `GENERATION_ALREADY_IN_PROGRESS` | C `test_generation_provider_failure_and_cancellation_api` | 409, response code |
| `REVIEW_ALREADY_IN_PROGRESS` | C `test_review_cancel_and_resource_checks` | 409, response code |
| `TASK_NOT_CANCELLABLE` | C `test_full_specification_lifecycle` | 409, response code |

## Approval and revision scenarios

The bound integrity test changes both stored digest and artifact content directly in an isolated test fixture. The human decision remains durable, and dispatch rejects it without consumption. The repository revision path creates a version, which deterministic providers regenerate and review. The fresh approval is bound to the revised digest. The old decision still fails dispatch. The fresh decision is consumed and the downstream implementation step waits at its independent approval gate.

The critical finding test uses the ASGI API and mock provider responses across initial generation, critical review, denial, revision, generation, review and approval. It compares both artifact sets and verifies both digests and the historical findings and audit records. The first version fails eligibility before an approval record exists. The test submits the old version and digest against the new approval and verifies rejection before resolving the correct binding.

## Timing and release checks

Windows, Python 3.12.10, pytest 9.2.0, local SQLite and offline providers. The retry test uses a module-local mocked sleep and verifies the requested one- and two-second backoff values. Separate real-time timeout and retry-budget tests remain in place. Sequential runs use duration reporting for the same focused selection. All commands use the repository virtual environment. Coverage data uses `$env:COVERAGE_FILE = '.coverage.wave2-final-blocker'`.

| Sequential run | Result | Time |
|---|---|---|
| 1 | Exit 0, 113 passed and 581 deselected | 69.67 s |
| 2 | Exit 0, 113 passed and 581 deselected | 75.48 s |

Both commands were `python -m pytest tests/ -k wave2 --no-cov -q --durations=15`. The report of the first run ranked the Streamlit/FastAPI lifecycle (5.52 s), request-page AppTest (2.87 s) and deliberate MCP stall (2.03 s) as the largest individual calls. Multiple independent AppTest cases took about one to two seconds each. The focused suite exceeded the mandatory 60-second limit on both runs. It also missed the advisory 50-second target. The full suite applies the coverage gates separately.

| Command | Exit and result |
|---|---|
| `python -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=html:htmlcov/wave2-final-blocker` | Exit 0. 694 passed in 654.66 seconds, including 72 Phase 1 MCP tests and 304 Wave 1 workflow and approval tests. |
| `python -m coverage json -o .venv/wave2-final-blocker-coverage.json` | Exit 0. 92.11% combined, 94.47% line (5,967/6,316), 81.79% branch (1,186/1,450). The mandatory 80% branch floor passed. |
| `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy --strict src tests` | Exit 0. |
| `alembic heads` and isolated migration tests in the full suite | Head 009. Both isolated migration tests and the schema comparison passed. |
| `python scripts/export_openapi.py`, `git diff --exit-code -- docs/openapi.json` | Exit 0 on both commands. Generated OpenAPI is unchanged. |
| `python -m pip check` and `uv lock --check --offline --no-build-isolation --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` | Exit 0. No broken requirements. The offline lock check resolved 68 packages. |
| `python -m bandit -c pyproject.toml -r src/ -ll -f json -o .venv/wave2-final-blocker-bandit.json` | Exit 0. Zero medium or high findings. |
| `docker run --rm --pull never --network none --mount "type=bind,source=$scanRoot,target=/scan,readonly" trufflesecurity/trufflehog:3.90.0 filesystem /scan --no-update --no-verification --fail --json` | Exit 0. Zero verified and unverified secrets across 747 chunks in the read-only workspace snapshot. |
| `git diff --check` and `git diff --cached --check` | Exit 0 on both commands. |

## Readiness recommendation

The first full invocation was stopped after a test sent a stale client digest and expected the stored-artifact mismatch code. The corrected test verifies both failures separately. The definitive invocation is recorded above.

The [HTTP contract proposal](phase2-wave2-http-contract-resolution.md) identifies the narrow frozen-text changes needed before final PR readiness. It preserves asynchronous submission, polling and audited human approval. Changes to the frozen wording remain pending approval. W2.T11.1 also remains open because both final focused runs exceeded the mandatory limit.

## Frozen W2.T11 acceptance text

~~~text
W2.T11.1 — All Wave 2 tests run with `pytest tests/ -k wave2` and no live external service; total time < 60 seconds.
W2.T11.2 — Wave 1 tests are unaffected; `pytest tests/ -k "not wave2"` passes without change.
W2.T11.3 — AST guard test scans all Wave 2 service and adapter modules; asserts no `subprocess`, `os.system`, `exec`, `eval` calls.
W2.T11.4 — Secret redaction test: a generation attempt with `OPENAI_API_KEY` set confirms the key value does not appear in any log output or database column.
W2.T11.5 — No-OpenAI-egress test: `AI_PROVIDER="ollama"` with mocked network confirms zero requests to `api.openai.com`.
W2.T11.6 — Prompt-injection test: injected instruction in `repo_context` does not alter the instruction section of the constructed prompt.
W2.T11.7 — Startup recovery test: a `GenerationAttempt` left in `"running"` state is recovered to `"failed"` with `error_code="INTERRUPTED"` on simulated restart.
W2.T11.8 — Concurrent approval test: two simultaneous `resolve(approved)` calls → exactly one succeeds.
W2.T11.9 — All 15 error codes from REQ-W2.8.3 are covered by at least one test.
W2.T11.10 — MCP compatibility test: mocked subprocess verifies `MCPClientAdapter` contract without a live MCP server.
W2.T11.11 — `mypy --strict src/devflow_api/providers/ src/devflow_api/services/specification*.py src/devflow_api/repositories/specification*.py src/devflow_api/routers/specification*.py` exits with code 0.
W2.T11.12 — `ruff check src/` exits with code 0 on all new Wave 2 files.
W2.T11.13 — **F-FIN targeted tests:** (a) A test verifies `consume_atomic` raises `ApprovalBindingMismatch` when `expected_parameters_hash` does not match the stored hash. (b) A test verifies `consume_atomic` raises `ApprovalAlreadyResolvedError` when two concurrent calls attempt to consume the same standalone approval. (c) A test verifies that passing `protected_operation = "specification_approval"` (not `"approve_specification"`) to a workflow step template passes `WorkflowTemplate` Pydantic validation; passing `"approve_specification"` raises `ValidationError`. (d) A test verifies that standalone spec audit events are written with `workflow_run_id = None` to `WorkflowAuditLog`. (e) A test verifies `SpecificationRecoveryService.recover()` is idempotent over two calls.
W2.T11.14 — **A6 — Approval lifecycle targeted tests:**
  (a) **Approved-not-consumed (standalone):** A `SpecificationVersion` with `status = "approved"` and `consumed_at IS NULL` on the linked `specification_approval_requests` row causes `is_implementation_authorized` to return `False`.
  (b) **Successfully consumed (standalone):** After `resolve_standalone` completes, `consumed_at IS NOT NULL`, `SpecificationVersion.status = "approved"`, and `is_implementation_authorized` returns `True`.
  (c) **Expired authorization (workflow-bound):** A test mocks `ApprovalService.resolve` to simulate an expired approval (`ApprovalExpiredError`); verifies `resolve_bound` propagates the error and does NOT transition spec status.
  (d) **Failed or cancelled protected dispatch:** A test verifies that after `dispatch_protected_txn` raises `ApprovalNotConsumableError`, the orchestrator calls `request_bound_approval` again (re-gates); `is_implementation_authorized` still returns `False` because spec status is not `"approved"`.
  (e) **Replay / duplicate dispatch:** A test verifies the orchestrator's `_advance` idempotency: if an `ApprovalRequest` with `status = "approved"` and `consumed_at IS NULL` already exists for the step, `_advance` returns the same `DispatchPlan.approval_id` without creating a duplicate.
  (f) **No downstream authorization before gate:** A test verifies `is_implementation_authorized` returns `False` when spec is in `"ready_for_approval"` state.
W2.T11.15 — **C — Stale, mismatched, expired, and replayed approval tests (workflow-bound):**
  (a) **Stale digest at resolve time:** A test sets `spec_version.content_digest` to a different value after artifacts are saved, then calls `resolve_bound`; verifies `SPEC_DIGEST_MISMATCH`, spec stays at `"ready_for_approval"`, `spec_approval_digest_mismatch` audit event written, `ApprovalRequest.status` still `"approved"`.
  (b) **No silent approval of modified content:** A test verifies that `is_implementation_authorized` returns `False` after a digest-mismatch event (spec is at `"ready_for_approval"`, not `"approved"`).
  (c) **Fresh approval required:** A test verifies that after a digest-mismatch, calling `request_approval` again creates a new `ApprovalRequest` (or new `specification_approval_requests` row); the stale approval does not block the new request.
  (d) **Expired Wave 1 authorization:** A test mocks `ApprovalRequest.authorization_expires_at` to be in the past; verifies the orchestrator's `_advance` skips dispatch and re-gates via `request_bound_approval`.
~~~

WAVE 2 BLOCKED — ACTION REQUIRED
