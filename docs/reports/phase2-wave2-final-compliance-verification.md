# Phase 2 Wave 2 v1.6.1 final compliance verification

**Verification date** 2026-11-23

**Branch and baseline** `codex/phase2-wave2-group-d`, HEAD `431b406` (approved v1.6.1 amendments), based on Group C checkpoint `a14bd7c`. The working tree retains the existing Group D changes and contains local MCP wiring, tests, OpenAPI and documentation changes. No additional checkpoint was created. The local integration target is `develop` at `1f9a076`, four commits behind this HEAD with no divergent local commits.

The amendment authority is the project owner's explicit statement: “I approve the following Wave 2 specification amendments: asynchronous HTTP contract with existing error envelope; 120-second focused test budget with a 60-second advisory target.” No normative specification was changed here. The specification has 54 requirements and 14 implementation tasks. The prior 694 tests, 113 focused tests and 28.71-second focused result are historical evidence.

## HTTP context trace

The earlier code dropped the context plan on both entry paths. The configured adapter alone did not retrieve context. The correction carries typed plans through the HTTP background task and provides the same policy-enforcing adapter to workflow generation.

| Source | Function or class | Actual input, output and boundary |
|---|---|---|
| `src/devflow_ui/components/specifications.py` | Feature request and generation page | The UI collects untrusted repository text and submits ordinary generation for the selected request. The frozen UI contract has no MCP selector. |
| `src/devflow_ui/api_client.py` | `APIClient.specifications`, request helper | Serializes a supplied payload as JSON. There are no client-side command or tool-authorization controls. |
| `src/devflow_api/schemas/specification_http.py` | `AttemptTrigger`, `GenerationTrigger` | The generation-only subtype accepts at most 16 `mcp_contexts`. Review retains its original schema. |
| `src/devflow_api/schemas/specification.py` | `MCPContextRequest` | Validates server/tool names, argument object and required flag. Extra fields such as process commands are rejected. |
| `src/devflow_api/routers/specification_requests.py` | `generate` | Copies each plan deeply. Resolves request and configured provider, creates the attempt, and schedules the attempt ID with the copied tuple. Returns 202. |
| `src/devflow_api/services/specification_generation.py` | `start`, `_claim` | The write transaction checks the current draft, version and active attempts. Only a pending attempt can be claimed. The request/version binding is derived from the attempt. |
| `src/devflow_api/routers/specification_requests.py` | `_run_generation` | Builds an adapter from trusted settings and an audit session. Forwards attempt ID, copied plan and configured local actor to `run`. |
| `src/devflow_api/services/specification_generation.py` | `run`, `_context` | Checks cancellation, iterates the bounded plan, and passes request, attempt and applicable workflow IDs to the adapter. Required errors fail the attempt. Optional errors retain audit evidence and allow generation. |
| `src/devflow_api/adapters/mcp_adapter.py` | `retrieve_context` | Enforces enabled server, named allowed tool, operator read-only classification, argument size and configured schema. Canonicalizes and snapshots arguments before entering per-call authorization. |
| `src/devflow_api/adapters/mcp_client.py` | `_authorized`, `call_tool` | Checks the invocation capability and canonical argument binding. MCP 2.3.0 exchanges validated JSON-RPC with a configured subprocess and explicit environment, then returns a typed tool result. |
| `src/devflow_api/adapters/mcp_adapter.py` | `ContextChunk` creation and audit | Redacts tool output, removes control characters and bounds text. Audit contains sanitized names, argument hash, outcome and correlation IDs. |
| `src/devflow_api/services/specification_prompts.py` | `generation_prompt` | Puts MCP text in a delimited untrusted section and bounds the aggregate prompt. |
| `src/devflow_api/services/specification_generation.py` | Provider call and finalization | Calls only the selected provider with the bounded prompt. Validates the result and commits artifacts, digest and audit only for a valid running attempt. |

The plan stays in the scheduled job. It is independent of mutable request input, and it is not persisted or replayed at startup. The per-call allowlist and schema authorization occurs in the background worker, so expected policy denials use the approved asynchronous failure contract.

## Workflow context trace

`WorkflowOrchestrator` validates and snapshots workflow step inputs, then supplies them in `ExecutionContext` to the registered `SpecGeneratorExecutor`. `GeneratorInput` validates the same bounded plan. `SpecificationExecution.generate` deep-copies that validated input, checks the specification's workflow binding, builds the same operator-configured adapter and starts and runs the new attempt. The MCP audit records the actual workflow run and attempt. An existing pending or failed attempt is never adopted with a different plan. A new context-bearing workflow step cannot reuse an earlier successful attempt without proof of the prior plan. An already successful step in the same workflow is not rerun. The independent implementation step remains subject to Wave 1 protected dispatch.

## Direct offline evidence

Tests in `tests/integration/test_wave2_mcp_wiring.py` use ASGI, isolated SQLite, an injected offline provider and a pipe-level fake MCP subprocess.

| Scenario | Test and observed result |
|---|---|
| A | `test_mcp_context_through_http_generation[success…]` verifies 202, named configured subprocess, canonical arguments, bounded/redacted untrusted prompt text, valid digest, audit and 200 terminal poll. |
| B | Same test, required failure. HTTP 200 poll contains `failed/MCP_CONTEXT_FAILURE` after 202. Draft and empty artifacts are preserved and the provider is never called. Private protocol data is absent. |
| C | Same test, optional failure. Failed MCP audit survives, generation succeeds and no cloud fallback or extra tool call occurs. |
| D | Same test, unknown server, prohibited tool, wildcard and invalid arguments. No subprocess is launched, audit records denial or argument error, and required attempts fail. |
| E | `test_mcp_context_through_registered_workflow_executor` invokes the real registry, orchestration, adapter and client. Context reaches the provider. Attempt and workflow IDs correlate, and implementation stays waiting for independent approval after resume. |
| F | HTTP no-context case. No launch or MCP audit and valid artifacts are generated. |
| G | Not applicable to this frozen UI. The UI can submit repository context and normal generation, and configuration and named MCP selection remain API/workflow inputs. |
| Duplicate | `test_duplicate_http_generation_cannot_launch_another_context_tool` holds the first launch open, obtains 409 from the second request and verifies exactly one process and one provider call. |

These controls are application-level. Operators must trust configured MCP executables and constrain their OS access. Explicit named allowlists, read-only classification, schema checks, canonical binding, bounded transport and prompt text, redaction and the authorization context remain active. Delimiters and structured output validation reduce prompt-injection risk.

## Approved HTTP code inventory

`C` refers to `tests/integration/test_wave2_group_c.py`. `M` refers to `tests/integration/test_wave2_mcp_wiring.py`.

| Code | Observed stage | Exact assertion |
|---|---|---|
| `INVALID_SPECIFICATION_REQUEST` | 422 | C `test_full_specification_lifecycle` |
| `PROVIDER_NOT_CONFIGURED` | 400 | C `test_generation_provider_failure_and_cancellation_api` |
| `SPEC_APPROVED_NO_OVERWRITE` | 409 | C `test_full_specification_lifecycle` |
| `SPEC_DIGEST_MISMATCH` | 409 | C `test_full_specification_lifecycle` |
| `INVALID_SPEC_TRANSITION` | 409 | C `test_critical_review_revision_requires_fresh_human_approval` |
| `APPROVAL_EXPIRED` | 409 | C `test_review_acknowledgment_expired_approval_and_revision_api` |
| `APPROVAL_ALREADY_RESOLVED` | 409 | C `test_full_specification_lifecycle` |
| `GENERATION_ALREADY_IN_PROGRESS` | 409 | M `test_duplicate_http_generation_cannot_launch_another_context_tool` |
| `REVIEW_ALREADY_IN_PROGRESS` | 409 | C `test_review_cancel_and_resource_checks` |
| `TASK_NOT_CANCELLABLE` | 409 after completion | C `test_full_specification_lifecycle` |
| `PROVIDER_UNAVAILABLE` | 202 then 200 with failed state and code | C `test_generation_provider_failure_and_cancellation_api` |
| `PROVIDER_TIMEOUT` | 202 then 200 with failed state and code | Same C test |
| `MALFORMED_OUTPUT` | 202 then 200 with failed state and code | Same C test |
| `MCP_CONTEXT_FAILURE` | 202 then 200 with failed state and code | M required failure case |
| `PROVIDER_CANCELLED` | 200 cancellation acceptance, 200 poll with cancelled state and code | C `test_generation_provider_failure_and_cancellation_api` |
| `AI_REVIEW_MALFORMED` | Additional review-specific code, 202 then 200 with failed state and code | C `test_review_findings_cannot_bypass_approval` |

The original 15 codes comprise ten synchronous and five background codes. The sixth background code is additional and review-specific. The shared synchronous response model serializes `error` and `code`. A standalone ASGI check submitted an unknown `command` field under `mcp_contexts` and asserted 422 with exactly those two keys, including `INVALID_SPECIFICATION_REQUEST`. Polling serializes `status` and `error_code`, with an optional safe `error_message`. The owner-approved behavior preserves 202 for accepted generation/review, 200 for polling and accepted cancellation, and 409 for invalid cancellation.

## W2.T11 criteria

The approval subcriteria 13a–e, 14a–f and 15a–d remain itemized in the [prior acceptance matrix](phase2-wave2-final-blocker-resolution.md#w2t11-acceptance-matrix) and were rerun on this tree. `D` is `tests/integration/test_wave2_group_d.py`, `S` is `tests/unit/test_wave2_specification_services.py` and `P` is `tests/unit/test_wave2_providers.py`.

| v1.6.1 criterion | Implementation and test | Expected and observed result | Verdict |
|---|---|---|---|
| W2.T11.1 offline and <120 s | Focused pytest in §Gates | All focused tests pass twice within 120 s. Exit 0 on both runs. 123 passed and 581 deselected in 37.22 s and 36.17 s. Both meet the mandatory 120 s limit and advisory 60 s target. | Pass |
| W2.T11.2 Wave 1 unaffected | `orchestration.py`, `tests/unit/test_workflow_orchestration.py::test_authorization_expiry_and_replay_regate` and remaining non-focused cases | Non-Wave-2 cases pass in the full invocation. | Pass |
| W2.T11.3 AST guard | Wave 2 services/adapters, D `test_wave2_service_and_adapter_sources_have_no_execution_calls` | No prohibited execution call. | Pass |
| W2.T11.4 key redaction | Spec persistence/audit, D `test_wave2_generation_redacts_configured_cloud_key` | Synthetic key absent from inspected logs and persistence. | Pass |
| W2.T11.5 egress | Provider selection/HTTP, P `test_ollama_unavailable_without_fallback` | Mock HTTP transport confirms no cloud fallback. | Pass |
| W2.T11.6 injection | Prompt template, S `test_generation_uses_untrusted_mcp_and_persists_a_verified_version` and M success | Instructions stay fixed and MCP data is delimited. | Pass |
| W2.T11.7 startup recovery | FastAPI lifespan and recovery, D `test_wave2_startup_recovers_without_replaying_attempts` | Running attempt fails with `INTERRUPTED`, state restored and provider never called. | Pass |
| W2.T11.8 concurrent approval | Approval service, C `test_simultaneous_standalone_resolution_has_one_winner` | One decision succeeds, one is rejected. | Pass |
| W2.T11.9 codes and stages | Router, error middleware and worker, inventory above | Original 15 codes plus review-specific code at approved stages. | Pass |
| W2.T11.10 MCP offline | SDK transport and adapter, M HTTP/workflow tests and `tests/unit/test_wave2_mcp_adapter.py::test_context_discovery_and_invocation` | Fake subprocess exercises real typed SDK transport. | Pass |
| W2.T11.11 strict MyPy | `mypy --strict src tests` | Exit 0. | Pass |
| W2.T11.12 Ruff | `ruff check .` | Exit 0. | Pass |
| W2.T11.13 F-FIN | D `test_wave2_standalone_consumption_requires_matching_hash_and_one_winner`, startup recovery, S injection, C `test_workflow_template_rejects_standalone_specification_operation` | Hash binding, one-use consumption, template distinction, null workflow audit and idempotent recovery. | Pass |
| W2.T11.14 approval lifecycle | Approval service and Wave 1 orchestration, C `test_full_specification_lifecycle` and bound-gate cases | Approval consumption, expiry, re-gating, duplicate dispatch and upfront denial. | Pass |
| W2.T11.15 bound approval integrity | C bound-gate cases and `test_critical_review_revision_requires_fresh_human_approval` | Stale artifact/digest fails before dispatch, corrected version receives fresh approval, old decision cannot replay and separate implementation authorization remains required. | Pass |

## All task statuses

| Task | Implementation evidence | Status |
|---|---|---|
| T1 | Typed provider contract and default Ollama exercised with mock HTTP | Pass |
| T2 | OpenAI opt-in and no fallback | Pass |
| T3 | MCP 2.3.0 adapter policy and HTTP/workflow fake subprocess | Pass |
| T4 | Generation, bounded context, validation and artifact persistence | Pass |
| T5 | Deterministic and AI review and malformed review handling | Pass |
| T6 | Versions, stable digests and historical immutability | Pass |
| T7 | Standalone consumption, workflow-bound approval and protected dispatch | Pass |
| T8 | Isolated 009 upgrade, parity and downgrade covering seven tables and 15 indexes | Pass |
| T9 | FastAPI and OpenAPI, including generation context input | Pass |
| T10 | Streamlit API-backed specification lifecycle | Pass |
| T11 | Matrix above | Pass |
| T12 | Readiness, operator and verification documentation | Pass |
| T13 | Startup recovery and expiry audit | Pass |
| T14 | Registered specification executors and workflow integration | Pass |

## Gates

Commands use `.venv/Scripts/python.exe` on Windows with Python 3.12.10 and pytest 9.2.0. Coverage commands use `COVERAGE_FILE=.coverage.wave2-compliance`.

| Command | Result |
|---|---|
| `python -m pytest tests/integration/test_wave2_mcp_wiring.py tests/integration/test_wave2_group_c.py -k 'mcp_context or duplicate_http or openapi_export or executor_dispatch' --no-cov -q` | Exit 0, 12 passed and 41 deselected in 5.70 s. |
| `python -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=html:htmlcov/wave2-compliance` | Exit 0, 704 passed in 341.69 s, including all 581 non-focused cases. |
| `python -m coverage json -o .venv/wave2-compliance-coverage.json` | Exit 0. 92.17% combined, 94.50% line (5,982/6,330) and 82.00% branch (1,189/1,450). The mandatory 80% branch floor passed. |
| `python -m pytest tests/ -k wave2 --no-cov -q --durations=15` twice sequentially | Exit 0 on both runs. 123 passed and 581 deselected in 37.22 s and 36.17 s. Both meet the mandatory 120 s limit and advisory 60 s target. |
| `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy --strict src tests` | Exit 0, 217 files formatted and 206 files type-checked. |
| `alembic heads`, isolated migration tests in full suite | Exit 0 for sole head `009_add_ai_specification_generation`. Isolated 009 parity and round-trip tests in the full invocation. |
| `python scripts/export_openapi.py`, `test_openapi_export_parity` | Exit 0. Checked-in export regenerated with generation context schema and matched the live schema. |
| `python -m pip check`, `uv lock --check --offline --no-build-isolation --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` | Exit 0, no broken requirements and 68 locked packages. |
| `python -m bandit -c pyproject.toml -r src/ -ll -f json -o .venv/wave2-compliance-bandit.json` | Exit 0 without medium or high findings. |
| `docker run --rm --pull never --network none --mount "type=bind,source=$scanRoot,target=/scan,readonly" trufflesecurity/trufflehog:3.90.0 filesystem /scan --no-update --no-verification --fail --json` | Exit 0, zero verified and unverified secrets across 756 chunks. The first attempt found the local engine stopped. The offline check passed after starting it. |
| `git diff --check`, `git diff --cached --check`, pre-push | Exit 0 for whitespace checks. No active pre-push hook or separate repository script found. Direct quality checks ran in check-only mode. |

## Readiness and limitations

No operational database was migrated. The plan is scoped to one accepted attempt or validated workflow snapshot and is not reconstructed after process interruption. Workflow inputs are durable snapshot data, so operators should keep secrets in the configured server environment instead of tool arguments. The configured local MCP executable remains an operator trust boundary. There is no Wave 3, real coding-agent invocation or automatic PR action.

PHASE 2 WAVE 2 v1.6.1 — ALL 14 TASKS VERIFIED

MCP END-TO-END CONTEXT WIRING VERIFIED

READY FOR KIRO IMPLEMENTATION PR
