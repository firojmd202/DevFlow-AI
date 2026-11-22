# Phase 2 Wave 2 Group A blocker resolution

- **Date** · 22 November 2026
- **Branch** · `codex/phase2-wave2-group-a`
- **Base HEAD** · `1f9a076a724decca48b8b9b9ee1114c10755f8ae`
- **Specification** · Frozen v1.6.0

The starting working tree contained the uncommitted W2.T1 and W2.T2 changes and the original Group A report. This follow-up preserves that implementation and uses the new report for the MCP migration and verification evidence.

## MCP 2.3.0 root cause and fix

MCP 2.3.0 exports `JSONRPCMessage` as a union of JSON-RPC request, response, notification, and error models. The previous stdio reader called `JSONRPCMessage.model_validate_json` as if it were a Pydantic root model. The first initialization reply therefore failed before the SDK session could complete the handshake.

The reader now constructs one `TypeAdapter[JSONRPCMessage]` and validates each stdio line with `validate_json`. The validated concrete message enters the existing `SessionMessage` transport. The client uses the SDK's `CallToolResult.is_error` attribute and verifies the concrete result type. It rejects explicitly unsupported result tags at the wire boundary because legacy negotiation can strip newer tags before the SDK validates the payload.

The shared session path retains an explicit child environment, suppressed stderr, an outer operation deadline, and terminate/drain/kill cleanup. The SDK's client and dispatcher diagnostics are suppressed because their validation and logging paths can include untrusted protocol fields. Application errors and audit events use sanitized statuses.

| Integration point | MCP 2.3.0 evidence |
| --- | --- |
| Stdio initialization and shutdown | Initializes a real SDK session over fake subprocess pipes, emits the initialized notification, and closes the process and streams. |
| JSON-RPC inbound and outbound | Local fixtures exercise responses, a server ping request and client response, valid and malformed notifications, an error response, and invalid JSON. |
| Discovery | `ClientSession.list_tools` is exercised across cursor pages. The adapter exposes only explicitly allowlisted names locally classified as read-only. Pagination is bounded and rejects repeated cursors or unsupported results. |
| Invocation and results | Existing Phase 1 result shape and argument binding pass against 2.3.0. New tests reject absent tool capabilities, error replies, and unsupported result variants. |
| Deadline and lifecycle | Success, protocol failure, timeout including kill fallback, and cancellation exercise process cleanup with deterministic fakes. |
| Credential isolation | Phase 1 explicit-environment tests cover allowlisted interpolation and exclusion of parent-only secrets. The adapter redacts configured secrets from returned text and omits raw arguments and results from the audit event. |

## W2.T3 acceptance evidence

| Criterion | Evidence |
| --- | --- |
| W2.T3.1 | `MCPClientAdapter.retrieve_context` invokes through `MCPClient` and returns typed `ContextChunk` data. Only text blocks enter the chunk, with control characters stripped and output bounded by the configured prompt budget. |
| W2.T3.2 | Operator-registered JSON Schema is checked against a canonical snapshot before launch. The tests cover missing fields, wrong types, non-JSON values, oversized arguments, strict missing-schema mode, and remote reference rejection without retrieval. |
| W2.T3.3 | Every retrieval attempt records `mcp_tool_invoked` through the existing audit repository with outcome, safe configured identifiers, and the canonical argument hash when the arguments can be represented within the limit. |
| W2.T3.4 and W2.T3.8 | The adapter declares MCP 2.3.0 in its module docstring. An AST test verifies SDK imports stay in the Phase 1 client. |
| W2.T3.5 and W2.T3.9 | Unknown or disabled servers, unauthorized tools, and wildcard-only grants are rejected before launch. Even an allowed tool needs an active client authorization bound to its server, tool, and validated argument object. |
| W2.T3.6 and W2.T3.7 | Optional transport failures return an empty chunk and log a warning. Required failures surface `MCP_CONTEXT_FAILURE`. Policy and schema errors stay actionable and cancellation propagates after cleanup. |

The adapter admits only individually named tools classified as `read_only` in trusted operator configuration. The existing Phase 1 approval gateway still handles consequential and unknown tools under its existing policy. Discovered tool metadata cannot grant access or replace operator schemas. Returned context is data. The tool access policy is enforced by the application and depends on trusted server commands and local classifications.

## Dependencies and PR #20

`requirements/base.txt` declares `mcp>=2.3.0,<3.0`. Both `uv.lock` and its generated `requirements/requirements.lock` export pin `mcp==2.3.0`, `mcp-types==2.3.0`, `httpx2==2.16.2`, and `httpcore2==2.16.2`. The adapter declares its direct dependencies `jsonschema==4.26.0` and `referencing==0.37.0`, which were already transitively locked at those versions. The existing `httpx==0.28.1` provider dependency remains compatible alongside the SDK's separate `httpx2` package.

Dependabot PR #20 is open at `f7072c5676f1fc1a36bd9f169f0d6bebdd21a4e2` and changes only `requirements/base.txt`. `gh pr view 20 -R kotlinandfluttertutorial-lab/DevFlow-AI --json state,mergedAt,headRefOid,files` exited 0. The range agrees with this branch. The declaration-only PR lacks the compatible transport and regenerated locks needed for adoption.

## Streamlit readiness

The original report established that the two failures reproduced on archived baseline HEAD under coverage, and that both passed on each tree without coverage. The version-matched Streamlit testing documentation recommends setting a larger AppTest timeout for cold imports. The navigation test and the Projects parametrized test now use a 15-second per-run timeout. The fixtures and assertions are retained. No application initialization changes were needed for the smoke correction.

## Verification

Run from the repository root on Windows with Python 3.12.10. In the commands below, `$py` is `.venv/Scripts/python.exe`.

| Gate | Command | Result |
| --- | --- | --- |
| Phase 1 MCP before lock upgrade | `.venv-mcp2-preflight/Scripts/python.exe -c "import sys; sys.path.extend(['.venv/Lib/site-packages', 'src']); import pytest; raise SystemExit(pytest.main(['--no-cov','-q','tests/unit/test_mcp_client.py','tests/unit/test_mcp_service.py','-k','not locked_sdk_version']))"` | Exit 0, 46 passed. The only deselection was the old locked-major assertion. |
| Lock regeneration | `uv lock --refresh-package devflow-ai --upgrade-package mcp --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` then `uv export --locked --no-hashes --no-emit-project --format requirements.txt --output-file requirements/requirements.lock --cache-dir .venv/uv-check-cache` | Both exit 0, 68 packages resolved and MCP 2.3.0 exported. |
| Install verification environment | `uv pip install --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache --no-build-isolation -r requirements/requirements.lock -r requirements/test.txt -e .` | Exit 0. |
| Dependency consistency | `& $py -m pip check` and `uv lock --check --offline --no-build-isolation --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` | Both exit 0. Installed MCP and its companion packages match the locks. |
| Export consistency | `uv export --locked --offline --no-build-isolation --no-hashes --no-emit-project --format requirements.txt --output-file .venv/wave2-blocker-lock-check.txt --cache-dir .venv/uv-check-cache` | Exit 0. Export content matched after ignoring the generated command header. |
| Streamlit reproduction with correction | `$env:COVERAGE_FILE='.coverage.wave2-timeout-fix'; & $py -m pytest --cov-fail-under=0 --cov-report= -q tests/smoke/test_ui_pages.py::test_navigation 'tests/smoke/test_ui_pages.py::test_projects_page_renders[True]'` | Exit 0, both passed under coverage. |
| Ruff and whitespace | `& $py -m ruff check .`, `& $py -m ruff format --check .`, and `git diff --check` | All exit 0. Ruff format checked 188 files. |
| Strict MyPy | `& $py -m mypy --strict src/ tests/` | Exit 0, 178 source files checked. |
| Group A, Phase 1 MCP and Wave 1 | `& $py -m pytest --no-cov -q tests/unit/test_wave2_providers.py tests/unit/test_wave2_mcp_adapter.py tests/unit/test_mcp_client.py tests/unit/test_mcp_service.py tests/unit/test_mcp_approval_repository.py tests/unit/test_workflow_orchestration.py tests/unit/test_approval_service.py tests/unit/test_approvals_router.py` | Exit 0, 193 passed, including 38 provider and adapter tests and 155 Phase 1 MCP, workflow, and approval tests. |
| Offline Bandit | `& $py -m bandit -c pyproject.toml -r src/ -ll -f json -o .venv/wave2-blocker-bandit.json` | Exit 0, no findings at the configured threshold. |
| Offline TruffleHog | `docker run --rm --pull never --network none --mount "type=bind,source=$scanRoot,target=/scan,readonly" trufflesecurity/trufflehog:3.90.0 filesystem /scan --no-update --no-verification --fail --json` | Exit 0, zero findings in the read-only working-tree snapshot. |
| Full suite with branch coverage | `$env:COVERAGE_FILE='.coverage.wave2-blocker'; & $py -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=html:htmlcov/group-a-blocker` | Exit 0, 619 passed in 324.62 seconds. Combined coverage was 93.28%. |
| Line and branch rate | `& $py -m coverage json --data-file .coverage.wave2-blocker -o .venv/wave2-blocker-coverage.json` | Exit 0, 95.13% line coverage (4,181 of 4,395) and 84.52% branch coverage (786 of 930). Both exceed the 80% threshold. |

## Remaining blockers and readiness

The MCP migration, W2.T3 acceptance tests, Phase 1 regressions, and full-suite coverage gates passed. No blocker remains within the Group A follow-up scope. The original report records the frozen specification's conflicting provider-default and source-literal wording. The existing provider implementation was preserved as requested.

WAVE 2 GROUP A COMPLETE — READY FOR CHATGPT VERIFICATION
