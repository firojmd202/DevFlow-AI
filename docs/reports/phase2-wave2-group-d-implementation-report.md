# DevFlow AI — Wave 2 Group D implementation report

**Branch:** `codex/phase2-wave2-group-d`
**HEAD:** `a14bd7c`, the local Group C checkpoint on Group B's `affc230`
**Working tree:** Group D source, tests and documentation are local changes. The frozen requirements, design and tasks are unchanged.
**Assessment date:** 2026-11-23

## Completion matrix

| Task | Outcome | Evidence |
|---|---|---|
| W2.T11 | Acceptance open | The final focused run met the timing limit. Offline regressions cover provider, MCP, lifecycle, API, UI and protected-dispatch behavior. Literal HTTP error-contract coverage is incomplete. |
| W2.T12 | Documentation complete | The existing readiness and compatibility reports and roadmap reflect the frozen v1.6.0 decisions and tested MCP pin. The implementation reports record the outstanding gates. |
| W2.T13 | Implemented | FastAPI startup, running and pending attempts, cancellation flags, rollback, concurrent recovery, expiry audit deduplication and no replay are exercised by deterministic SQLite tests. |

The preflight verified Group C's saved 684-test run and measured 92.11% combined, 94.48% line and 81.72% branch coverage. Group C was checkpointed locally before Group D changes.

## Startup recovery and approval interruption

FastAPI checks the schema and runs Wave 1 recovery first. The specification sweep settles durable pending and running attempts with `failed / INTERRUPTED`. A per-attempt SQLite immediate transaction compares the prior status and commits the failure, applicable state restoration and audit together. Restoration requires the current version, expected states and absence of a newer attempt. A completed attempt is outside the sweep. Generation returns the affected request to draft. Review restores generated status and preserves the digest and artifacts. The existing attempt finalizers require the running state, which fences a terminal attempt. Recovery submits no provider work and acquires no dispatch authorization.

Expired unresolved standalone approvals get one audit event and retain their original persisted state. The expiry handler shares the audit deduplication operation. Recovery audit rows have a null workflow ID. The concurrency test forces an audit failure, verifies the attempt and request rolled back, then confirms that two concurrent sweeps produce a single terminal event.

The workflow-bound interruption test commits the Wave 1 human decision while the specification is still ready for approval. Two recovery passes preserve the incomplete decision and the ready state. The authorization predicate remains false, protected dispatch rejects the decision without consuming it, and an eligible version can acquire a new approval ID. Existing digest mismatch and replay tests cover the separate binding checks and independent downstream gate.

## End-to-end scenario evidence

| Scenario | Offline evidence |
|---|---|
| A — Standalone success | Group C API lifecycle and Streamlit-to-ASGI lifecycle. Group B verifies hashes, digest, finding persistence and audit metadata. |
| B — Critical finding and revision | Group C tests verify critical findings block approval and exercise revision and historical findings. Group B tests cover immutable prior artifacts. A single critical-to-revised-approval end-to-end test remains open. |
| C — Workflow-bound | Group C executor dispatch test verifies both specification executors and artifact references. The bound approval integration test covers dispatch and the independent downstream gate. These are separate tests. |
| D — Provider failure | Provider and attempt tests cover unavailable Ollama, timeout, malformed output, retry exhaustion and no cloud fallback. |
| E — MCP security failure | Adapter and generation tests cover denial before invocation, strict schemas, no remote schema references, oversized text, failures and untrusted context delimiters. |
| F — Restart | Group D simulates actual FastAPI lifespan startup over persisted pending and running work, then checks terminal state, audit and no replay. |
| G — Approval integrity | Group C covers stale bindings, expiry, rejection, replay and digest tampering. Group D adds direct concurrent consumption with a hash mismatch case and the bound interruption case. Wave 1 regressions cover expiry and failed-consume re-gating. |

## Security review

- Provider settings require explicit OpenAI selection and a key. Mock transport tests cover zero cloud requests in Ollama mode. The new generation test verifies a configured cloud key is redacted from generated content, captured output and the relevant specification and audit tables.
- The MCP adapter enforces server, tool, classification, authorization and schema policy. The transport isolates child environment entries. Configured MCP binaries and the operator's local Ollama endpoint remain trusted infrastructure.
- Prompt delimiters, context and output limits, structured validation and immutable artifacts limit impact from untrusted text. A model can still follow injected instructions or return misleading output. Review findings require human judgment.
- API ownership and bounded inputs are checked at the service and router boundaries. Streamlit uses the API. The local operator identity depends on a trusted local deployment. API processes share SQLite data and recovery assumes a single active application process for background jobs.
- The no-execution AST guard covers Wave 2 service, provider, adapter and executor code. The Phase 1 transport retains its intended local MCP subprocess boundary. Audit payloads use allowlisted metadata or redacted values.

## Verification

Run locations are the repository root. `$py` is `.venv/Scripts/python.exe`.

| Exact command | Result |
|---|---|
| `& $py -m pytest tests/ -k wave2 --no-cov -q --durations=20` | Final exit 0, 109 passed, 581 deselected in 58.66 s. An earlier run passed 108 tests in 71.99 s. |
| `& $py -m pytest tests/integration/test_wave2_group_d.py --no-cov -q` | Exit 0, five passed in 6.56 s. |
| `& $py -m pytest tests/integration/test_wave2_group_c.py -k interrupted --no-cov -q` | Exit 0, one passed, 38 deselected in 4.68 s. |
| `& $py -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=html:htmlcov/group-d` | Exit 0, 690 passed in 537.37 s. Phase 1 MCP, Wave 1 workflow and approvals, isolated migration/schema checks and OpenAPI parity all passed in this invocation. |
| `& $py -m coverage json -o .venv/wave2-group-d-release-coverage.json` | Exit 0, 92.03% combined, 94.43% line (5,964/6,316), 81.59% branch (1,183/1,450). Branch coverage meets the 80% floor and remains below the 85% advisory target. |
| `& $py -m ruff check .` and `& $py -m ruff format --check .` | Exit 0. |
| `& $py -m mypy --strict src tests` | Exit 0. |
| `& $py -m alembic heads` | Exit 0, sole head `009_add_ai_specification_generation`. |
| `& $py scripts/export_openapi.py` and `git diff --exit-code -- docs/openapi.json` | Exit 0, generated contract unchanged. |
| `& $py -m pip check` | Exit 0, no broken requirements. |
| `uv lock --check --offline --no-build-isolation --python .venv/Scripts/python.exe --cache-dir .venv/uv-check-cache` | Exit 0, 68 resolved packages. Both locks pin MCP 2.3.0. |
| `& $py -m bandit -c pyproject.toml -r src/ -ll -f json -o .venv/wave2-group-d-bandit.json` | Exit 0, zero medium/high findings. |
| `docker run --rm --pull never --network none --mount "type=bind,source=$scanRoot,target=/scan,readonly" trufflesecurity/trufflehog:3.90.0 filesystem /scan --no-update --no-verification --fail --json` | Exit 0, zero verified and unverified secrets across 743 chunks. `$scanRoot` is an isolated snapshot of tracked and unignored workspace files. |
| `git diff --check` | Exit 0. |
| `git config --get core.hooksPath` and `Get-ChildItem .git/hooks -File` | No configured override and only sample hooks present. The direct quality checks above were run in check-only mode. |

The full run used `$env:COVERAGE_FILE = '.coverage.wave2-group-d-release'` for pytest and the JSON export. The invocation includes two isolated migration 009 tests, OpenAPI runtime/export parity, 72 Phase 1 MCP regressions and 304 Wave 1 workflow and approval regressions. All 581 tests outside the `wave2` selection passed in the full run. The operational database was outside the verification paths.

A separate Python schema check confirmed `WorkflowTemplate.model_validate` accepts `specification_approval` and raises Pydantic `ValidationError` for the standalone operation `approve_specification`.

## Remaining acceptance gaps

- The final focused run met W2.T11.1 with 1.34 seconds of margin on this host. The most time-consuming case was the Streamlit/FastAPI lifecycle at 6.98 seconds. Earlier timings show this gate is sensitive to host load.
- Frozen design §5 specifies 202 submission and 200 status polling. Provider unavailable, provider timeout, malformed output and required MCP failure appear as persisted attempt codes. REQ-W2.8.3 assigns them 503, 504, 422 and 502 respectively. The frozen design also specifies 200 for accepted cancellation requests, while REQ-W2.8.3 lists 409 with `PROVIDER_CANCELLED` for explicit cancellation. These differences leave the literal HTTP gate open.
- The broad approval regressions and targeted extensions cover the principal denial paths. A full one-to-one reproduction of every W2.T11.14/15 fixture and assertion is still open, including a genuinely changed digest followed by restoring eligibility and issuing a replacement workflow approval. The new replacement test covers the interruption case with unchanged, eligible content.
- See the [operator guide](../phase2-wave2-operator-guide.md) for deployment trust assumptions and the [final report](phase2-wave2-final-implementation-report.md) for traceability and readiness.

WAVE 2 GROUP D BLOCKED — ACTION REQUIRED
