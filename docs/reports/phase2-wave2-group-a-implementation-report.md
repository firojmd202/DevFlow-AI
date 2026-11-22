# Phase 2 Wave 2 Group A implementation report

- **Date** · 22 November 2026
- **Branch** · `codex/phase2-wave2-group-a`
- **HEAD** · `1f9a076a724decca48b8b9b9ee1114c10755f8ae`
- **Specification** · v1.6.0, merged by PR #23

## Git and task status

The working tree was clean before editing. `git fetch --all` fetched both `origin` and `fork` (exit 0). `git merge-base --is-ancestor 1f9a076 develop` returned 0. Local `develop` and fetched `origin/develop` were both at the approved merge. `git switch -c codex/phase2-wave2-group-a origin/develop` returned 0.

| Task | Status | Evidence |
| --- | --- | --- |
| W2.T1 — Interface and Ollama | Implemented | Typed provider contract, factory, startup validation, configurable model and endpoint, availability and capability checks, optional JSON object mode, timeout, cancellation and bounded retry policy |
| W2.T2 — OpenAI | Implemented | Explicit selection and non-empty `SecretStr` credential, HTTP Chat Completions, typed token usage and request metadata, normalized auth, quota and rate-limit errors |
| W2.T3 — MCP adapter | Blocked by MCP 2.x preflight | MCP 2.3.0 breaks the existing Phase 1 stdio handshake. Adapter implementation and its discovery, schema, allowlist and invocation tests remain pending. |

### Frozen-spec and brief discrepancies

- The brief places Ollama in W2.T2. The frozen task list assigns Ollama to W2.T1 and OpenAI to W2.T2. The task status follows the frozen assignments.
- W2.T3 describes an adapter over the current 1.x dependency, while the brief makes successful 2.x compatibility verification a prerequisite. The dependency remains declared as `mcp>=1.0,<2.0` and locked to `1.30.0`. W2.T3 stops at the unsuccessful prerequisite.
- REQ-W2.1.1 includes a model argument. Design §3.1 shows `generate(prompt, options=None)`. The implementation preserves that positional signature and accepts an optional keyword-only `model` override.
- W2.T1.8 and REQ-W2.1.8.1 ban URL and model literals in Python, while the same spec requires the named model defaults in `Settings` and a fixed OpenAI URL. The mandated defaults and fixed endpoint are centralized in `Settings`. No literal key is present. The literal-ban criterion remains unresolved as written.
- REQ-W2.1.3 says to fail immediately when Ollama is unavailable and REQ-W2.1.7 requires bounded transient retries. The provider fails without switching providers, retries only eligible transient failures under the configured budgets, and fails on the first attempt when retries are disabled.
- Cooperative cancellation propagates as Python `CancelledError`, as required by W2.1.4.2. Recording `PROVIDER_CANCELLED` at the service boundary and domain-specific artifact schema validation belong to later tasks. Group A validates the typed HTTP response and checks that optional structured mode returns a JSON object.
- The selected Chat Completions endpoint supplies token usage when available and does not supply per-request monetary cost. No cost estimate is fabricated.

## MCP 2.x compatibility matrix

The preflight resolved `mcp==2.3.0` from PyPI in `.venv-mcp2-preflight`, with `mcp-types==2.3.0`, `httpx2==2.16.2`, `pydantic==2.14.4` and `anyio==4.16.0`. SDK signatures were inspected in that environment. The targeted tests used the isolated SDK and its dependencies first and appended the project test dependencies afterward. All transport tests used the repository's local fake subprocess.

| Phase 1 integration point | MCP 2.3.0 observation | Verdict |
| --- | --- | --- |
| `mcp.ClientSession(read, write, logging_callback=...)` and async context manager | Export and constructor arguments resolve. Default signature adds optional arguments and uses SDK stream protocols. Session constructs and enters with the project's AnyIO streams. | Signature and entry verified. End-to-end lifecycle fails during initialization. |
| `mcp.shared.message.SessionMessage(message)` | Import and constructor resolve. `message` now expects concrete JSON-RPC request, notification, response or error models from `mcp_types.jsonrpc`. | Wrapper exists. Current inbound decoder cannot produce a message. |
| `mcp.types.JSONRPCMessage.model_validate_json(line)` | `JSONRPCMessage` is a Python union without `model_validate_json`. The first fake subprocess response raises `AttributeError: 'types.UnionType' object has no attribute 'model_validate_json'` in `mcp_client.py:73`. | Incompatible. |
| Outbound `SessionMessage.message.model_dump_json(by_alias=True, exclude_none=True)` | The existing write path sends the initialize request to the fake subprocess. The inbound read fails on its reply. | Initialize write exercised. Round trip fails. |
| `mcp.types.LoggingMessageNotificationParams` and discard callback | Type export and `logging_callback` parameter resolve. The read failure prevents confirming notification delivery. | Signature available. Delivery unverified. |
| `ClientSession.initialize()` | Signature resolves. Local lifecycle probe also reports `mcp.shared.exceptions.MCPError: Connection closed` during initialization after the reader fails. | Runtime fails. |
| `ClientSession.call_tool(name, arguments=...)`, `result.content`, `result.isError` | Arguments still exist. The return annotation now also admits `InputRequiredResult` and `Result`. `CallToolResult` itself still has `content` and `isError`. | Signature partially compatible. Invocation and result handling are unverified after handshake failure. |
| `ClientSession.list_tools(*, params=None)` and SDK-provided `stdio_client` | Both signatures resolve. Phase 1 uses its own explicit-environment subprocess transport and does not call these APIs. | Inspected for Group A. Discovery and SDK stdio behavior were not exercised. |
| Application-owned allowlist, per-invocation grant, secret environment and cleanup | Existing unmodified guards still run. Success-path tests involving actual SDK message exchange fail with the replaced decoder. | Phase 1 regression gate passes on locked 1.x only. |

The MCP 2.3.0 regression run had **8 failures and 39 passes**. The failing tests were:

- `test_mcp_client.py::test_mcp_call_tool_returns_result`
- `test_mcp_client.py::test_mcp_subprocess_receives_explicit_env`
- `test_mcp_client.py::test_mcp_subprocess_launched_with_explicit_env`
- `test_mcp_client.py::test_mcp_subprocess_does_not_inherit_parent_secrets`
- `test_mcp_client.py::test_mcp_secret_values_not_in_log_records`
- `test_mcp_client.py::test_mcp_subprocess_cleanup_in_finally_block[success]`
- `test_mcp_service.py::test_mcp_client_uses_locked_sdk_version`
- `test_mcp_service.py::test_mcp_integration_runs_offline_with_mock_subprocess`

Dependabot PR #20 is **open** with `mergedAt: null` and head `f7072c5676f1fc1a36bd9f169f0d6bebdd21a4e2`, as reported by `gh pr view 20 -R kotlinandfluttertutorial-lab/DevFlow-AI --json state,mergedAt,headRefOid` (exit 0). Its sole change replaces the 1.x range in `requirements/base.txt`. The tested version breaks the existing Phase 1 transport, so the PR cannot be adopted as-is. An upgrade also needs coordinated lock regeneration and a repeat of the Phase 1 tests.

## Files and implemented security controls

| File | Change |
| --- | --- |
| `.env.example`, `src/devflow_core/config.py` | Provider selection, model defaults, budgets and optional OpenAI secret |
| `src/devflow_api/main.py` | Builds and validates the selected provider at application initialization without making provider requests |
| `src/devflow_api/providers/__init__.py`, `base.py`, `factory.py` | Package, SDK-independent protocol and provider selection |
| `src/devflow_api/providers/exceptions.py`, `http.py` | Normalized failures, bounded transport and retry policy |
| `src/devflow_api/providers/ollama_provider.py`, `openai_provider.py` | HTTP integrations and typed vendor response parsing |
| `src/devflow_api/schemas/ai_provider.py` | Typed options, settings, availability, usage and response models |
| `tests/unit/test_wave2_providers.py` | Mock-transport regression and startup tests |
| `docs/reports/phase2-wave2-group-a-implementation-report.md` | Implementation and verification evidence |

Ollama is the default and does not import OpenAI on selection or attach its credential to local requests. OpenAI uses a fixed HTTPS origin, loads only after opt-in, and requires a non-empty credential. Both HTTP clients disable environment proxies and redirects. Provider errors use static public messages that exclude raw request and response data. The HTTP layer bounds prompt size using a character-based estimate, caps requested output tokens, and rejects HTTP response bodies beyond 2 MiB. External task cancellation propagates to HTTP I/O. The provider layer has no tool dispatch, execution or persistence hooks. The 1.x MCP and Workflow Wave 1 protected-dispatch regression suite passed, including the existing approval path.

## Verification

Commands below ran from the repository root on Python 3.12.10. `$py` is `.venv/Scripts/python.exe` and `$mcp2` is `.venv-mcp2-preflight/Scripts/python.exe`.

| Gate | Command | Exit and result |
| --- | --- | --- |
| MCP 2.x resolution | `& $mcp2 -m pip --isolated install --disable-pip-version-check --retries 0 --index-url https://pypi.org/simple 'mcp>=2.3.0,<3.0'` | 0 · installed MCP 2.3.0 |
| MCP 2.x regression | `& $mcp2 -c "import sys; sys.path.extend(['.venv/Lib/site-packages', 'src']); import pytest; raise SystemExit(pytest.main(['--no-cov','-q','tests/unit/test_mcp_client.py','tests/unit/test_mcp_service.py']))"` | 1 · 39 passed, 8 failed |
| Group A providers | `& $py -m pytest --no-cov -q tests/unit/test_wave2_providers.py` | 0 · 20 passed |
| Phase 1 MCP and Workflow Wave 1 | `& $py -m pytest --no-cov -q tests/unit/test_mcp_client.py tests/unit/test_mcp_service.py tests/unit/test_mcp_approval_repository.py tests/unit/test_workflow_orchestration.py` | 0 · 121 passed with MCP 1.30.0 |
| Ruff lint | `& $py -m ruff check .` | 0 · all checks passed |
| Ruff format | `& $py -m ruff format --check .` | 0 · 184 files already formatted |
| Strict MyPy | `& $py -m mypy --strict src/ tests/` | 0 · 174 source files checked |
| Dependency consistency | `& $py -m pip check` | 0 · no broken requirements |
| Lock consistency | `uv lock --check --offline --no-build-isolation --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` | 0 · 64 packages resolved using the installed build backend. The initial isolated offline check lacked cached setuptools. |
| Offline SAST | `& $py -m bandit -c pyproject.toml -r src/ -ll -f json -o $env:TEMP/devflow-wave2-bandit.json` | 0 · no findings at the configured threshold |
| Offline credential scan | `docker run --rm --pull never --network none --mount "type=bind,source=$scanRoot,target=/scan,readonly" trufflesecurity/trufflehog:3.90.0 filesystem /scan --no-update --no-verification --fail --json` | 0 · zero findings on the working-tree snapshot after rewriting a synthetic URL fixture that triggered the URI detector |
| Whitespace | `git diff --check` | 0 |
| Provider-only coverage | `$env:COVERAGE_FILE='.coverage.wave2-providers'; & $py -m pytest -o 'addopts=-v --tb=short' --cov=devflow_api.providers --cov=devflow_api.schemas.ai_provider --cov-branch --cov-report=term-missing tests/unit/test_wave2_providers.py` | 0 · 20 passed with 93.20% combined statement and branch coverage |
| Integration marker | `& $py -m pytest -m integration -v --no-cov` | 0 · 25 passed, 569 deselected |
| Baseline smoke reproduction with coverage | From a `git archive` of HEAD with its `src` on `PYTHONPATH`, `& $py -m pytest --cov-fail-under=0 -q tests/smoke/test_ui_pages.py::test_navigation 'tests/smoke/test_ui_pages.py::test_projects_page_renders[True]'` | 1 · both timed out at AppTest's three-second limit. The same command in the implementation tree also timed out (exit 1). |
| Smoke control without coverage | From the archived HEAD and the implementation tree, `& $py -m pytest --no-cov -q tests/smoke/test_ui_pages.py::test_navigation 'tests/smoke/test_ui_pages.py::test_projects_page_renders[True]'` | 0 on each tree · both passed |
| Full pytest with coverage | `$env:COVERAGE_FILE='.coverage.wave2-full'; & $py -m pytest -v --cov=src --cov-report=term-missing --cov-report=html:htmlcov/group-a-final --cov-fail-under=80` | 1 · 592 passed and 2 existing Streamlit smoke tests timed out. The combined coverage threshold passed at 92.92%. |
| Separate line and branch coverage | `& $py -m coverage json --data-file .coverage.wave2-full -o $env:TEMP/devflow-wave2-coverage.json` | 0 · 94.84% line coverage (4,026 of 4,245) and 83.78% branch coverage (749 of 894). The CI branch threshold of 80% was met. |

The fixture tests use mocked HTTP and local MCP streams. No live model inference or live MCP server was required.

## Readiness

Hold Group B. The existing Phase 1 transport must pass a verified MCP 2.x migration, or the mandatory 2.x prerequisite must be explicitly revised to permit W2.T3 on the locked 1.x SDK. Group A readiness also depends on implementing and testing W2.T3 against the resulting approved baseline.

WAVE 2 GROUP A BLOCKED — ACTION REQUIRED
