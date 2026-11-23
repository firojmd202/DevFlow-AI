# DevFlow AI — Phase 2 Wave 2: AI Specification Generation and Review Tasks

**Version:** 1.6.1
**Status:** Final — Async HTTP contract and focused test runtime aligned, PR-ready
**Scope:** Phase 2 Wave 2 — AI Specification Generation and Review
**Branch:** `feature/phase2-wave2-ai-spec-generation`
**Base commit:** `b3b37ff` (Wave 1 implementation merged, develop HEAD)
**Last Updated:** 2026-11-24
**Companions:** `requirements.md` (v1.6.1), `design.md` (v1.6.1).

**Version history:**
- v1.0.0–v1.5.0 — See prior version history.
- v1.6.0 — 2026-11-18 — Final approval-contract alignment: W2.T7.20 added (digest-mismatch in workflow-bound path), W2.T11.15 added (stale/mismatched/expired/replayed approval tests).
- v1.6.1 — 2026-11-24 — Amendment A (async HTTP contract): W2.T9.2, W2.T9.5, W2.T11.9 updated to reflect HTTP 202 for accepted submissions, HTTP 200 for all poll states, error codes asserted at correct lifecycle stage, error envelope field names locked. Amendment B (focused test runtime): W2.T11.1 mandatory limit raised from 60 s to 120 s; advisory target retained as 60 s; reference environment documented.

---

## Task Sizing Legend

- **S** — Small: a single model/schema/migration/test cluster; < 1 day.
- **M** — Medium: a service or router with tests; 1–2 days.
- **L** — Large: a cross-cutting component with extensive tests; 2–3 days.

---

## Tasks

### W2.T1 — `AIProvider` abstract interface and `OllamaProvider`

**Area:** REQ-W2.1.1, W2.1.2, W2.1.3, W2.1.4, W2.1.5, W2.1.6, W2.1.7, W2.1.8
**Size:** M
**Depends on:** Wave 1 baseline (commit `b3b37ff`); nothing else.

**Description:**
Create the `AIProvider` Protocol in `src/devflow_api/providers/base.py` with methods `generate`, `check_availability`, `check_capability` and supporting Pydantic v2 schemas (`GenerationOptions`, `ProviderResponse`, `TokenUsage`, `AvailabilityResult`) in `src/devflow_api/schemas/ai_provider.py`. Create `OllamaProvider` in `src/devflow_api/providers/ollama_provider.py`; it communicates directly with the Ollama HTTP API via `httpx.AsyncClient` (identical pattern to `OpenAIProvider`) and does NOT wrap `OllamaAdapter` for generation calls (see design §3.2 F1 resolution). Create `ProviderFactory` in `src/devflow_api/providers/factory.py`.

**F4 resolution — New `Settings` fields added in W2.T1** (to `src/devflow_core/config.py`):
- `AI_PROVIDER` (default `"ollama"`)
- `AI_REQUEST_TIMEOUT_SECONDS` (default 120)
- `AI_MAX_RETRIES` (default 2)
- `AI_RETRY_BUDGET_SECONDS` (default 30)
- `AI_MAX_PROMPT_TOKENS` (default 8000)
- `AI_MAX_OUTPUT_TOKENS` (default 4000)
- `OPENAI_API_KEY: SecretStr | None` (default `None`)
- `OPENAI_MODEL` (default `"gpt-4o-mini"`)
- `OLLAMA_MODEL` (default `"llama3.2"`)
- `OLLAMA_BASE_URL` — already exists in `Settings`; no change.
- `OLLAMA_TIMEOUT_SECONDS` — already exists in `Settings`; no change. Used only by `OllamaAdapter` for health-check pings, NOT by `OllamaProvider.generate()`.
- `APPROVAL_TTL_SECONDS` — already exists in `Settings` (default 3600). Wave 2 uses this existing field for the standalone approval `expires_at` computation (`expires_at = now + APPROVAL_TTL_SECONDS`). No new `APPROVAL_EXPIRY_SECONDS` field is added; the existing field is reused.

**Acceptance Criteria:**
W2.T1.1 — `AIProvider` Protocol is importable from `devflow_api.providers.base`; `mypy --strict` passes.
W2.T1.2 — `ProviderFactory.create(settings)` with no `AI_PROVIDER` returns an `OllamaProvider`.
W2.T1.3 — `OllamaProvider.generate()` with a mocked `httpx.AsyncClient` returning a valid Ollama JSON response produces a `ProviderResponse` with correct `content`, `usage.prompt_tokens`, and `usage.completion_tokens` fields (mapped from `prompt_eval_count` and `eval_count` respectively).
W2.T1.4 — `OllamaProvider` wraps `httpx.ConnectError` → `ProviderUnavailableError`; `httpx.TimeoutException` → `ProviderTimeoutError`.
W2.T1.5 — Retry logic: a mock that fails twice then succeeds completes after two retries; a `ProviderAuthError` mock never retries.
W2.T1.6 — A test with `AI_PROVIDER="ollama"` confirms `ProviderFactory.create()` never imports or instantiates `OpenAIProvider`.
W2.T1.7 — `asyncio.timeout(AI_REQUEST_TIMEOUT_SECONDS)` is applied in `OllamaProvider.generate`; a hanging mock raises `ProviderTimeoutError` after the configured timeout.
W2.T1.8 — No literal API key, OpenAI URL, or hardcoded model name appears in any `.py` file (CI grep test passes).

---

### W2.T2 — `OpenAIProvider` (optional, config-gated)

**Area:** REQ-W2.1.1, W2.1.2, W2.1.3, W2.1.5, W2.1.6, W2.1.7, W2.1.8
**Size:** M
**Depends on:** W2.T1.

**Description:**
Create `OpenAIProvider` in `src/devflow_api/providers/openai_provider.py`. Use `httpx.AsyncClient` directly (no openai SDK); call `POST https://api.openai.com/v1/chat/completions`. Map response to `ProviderResponse`. Update `ProviderFactory.create()` to instantiate `OpenAIProvider` only when `AI_PROVIDER="openai"` AND `OPENAI_API_KEY` is non-empty. Add `Settings` fields: `OPENAI_MODEL` (default `"gpt-4o-mini"`), `OPENAI_API_KEY: SecretStr | None`.

**Acceptance Criteria:**
W2.T2.1 — `ProviderFactory.create(settings)` with `AI_PROVIDER="openai"` and empty `OPENAI_API_KEY` raises `ProviderConfigurationError`.
W2.T2.2 — `ProviderFactory.create(settings)` with `AI_PROVIDER="ollama"` NEVER instantiates `OpenAIProvider` even if `OPENAI_API_KEY` is set.
W2.T2.3 — `OpenAIProvider` raises `ProviderConfigurationError` at `__init__` if `OPENAI_API_KEY` is empty.
W2.T2.4 — A mocked HTTP intercept confirms no request to `api.openai.com` is made when `AI_PROVIDER="ollama"`.
W2.T2.5 — `HTTP 401` from OpenAI is mapped to `ProviderAuthError`; `HTTP 429` to `ProviderRateLimitError`.
W2.T2.6 — `str(Settings.OPENAI_API_KEY)` returns `"**********"` (Pydantic `SecretStr`).
W2.T2.7 — `OpenAIProvider` satisfies the `AIProvider` Protocol; `mypy --strict` passes.

---

### W2.T3 — `MCPClientAdapter` with allowlist policy and credential isolation

**Area:** REQ-W2.3.1, W2.3.2, W2.3.3, W2.3.4, W2.3.5, W2.3.6
**Size:** M
**Depends on:** Wave 1 baseline (existing `MCPClient` in `src/devflow_api/adapters/mcp_client.py`).

**Description:**
Create `MCPClientAdapter` in `src/devflow_api/adapters/mcp_adapter.py`. Wrap `MCPClient` with: tool JSON schema validation before subprocess launch; `ContextChunk` normalization; `mcp_tool_invoked` audit logging (server, tool, argument_hash, result_status). Add `ContextChunk` Pydantic v2 model with `content: str`, `server: str`, `tool: str`, `required: bool`, `truncated: bool`. Confirm MCP SDK version in module docstring (currently `mcp>=1.0,<2.0` per `requirements/base.txt`). No `mcp.*` import outside `MCPClient`.

**Acceptance Criteria:**
W2.T3.1 — `MCPClientAdapter.retrieve_context()` calls `MCPClient.call_tool()` and returns a `ContextChunk`.
W2.T3.2 — Tool arguments failing JSON schema validation raise `MCPToolSchemaError` before subprocess launch; a test verifies no subprocess is started.
W2.T3.3 — Every call to `retrieve_context()` writes an `mcp_tool_invoked` audit event with `argument_hash` (not raw arguments).
W2.T3.4 — `MCPClientAdapter` module imports no `mcp.*` symbols; test verifies via `ast.parse`.
W2.T3.5 — A call to a tool not in `allowed_tools` raises `MCPPermissionError` before any subprocess is started.
W2.T3.6 — A non-critical MCP failure (`required=False`) returns a `ContextChunk` with `content=""` and logs a warning; no exception propagated.
W2.T3.7 — A critical MCP failure (`required=True`) raises `MCPContextFailureError` with `code="MCP_CONTEXT_FAILURE"`.
W2.T3.8 — Module docstring states MCP SDK version the adapter was authored against.
W2.T3.9 — **F5:** A test verifies that calling `MCPClient.call_tool()` without first entering the `MCPClient._authorized(server_name, tool_name, arguments, on_launch)` context manager raises `MCPPermissionError`. `MCPClientAdapter.retrieve_context()` MUST always use `async with self._mcp_client._authorized(...)` before calling `call_tool`; a test confirms `MCPPermissionError` is raised when the context manager is bypassed.

---

### W2.T4 — `SpecificationGenerationService` and prompt engineering

**Area:** REQ-W2.2.1, W2.2.2, W2.2.3, W2.2.4, W2.4.1, W2.4.2, W2.4.3, W2.4.4, W2.4.5, W2.4.6, W2.4.7, W2.9.1
**Size:** L
**Depends on:** W2.T1, W2.T3, W2.T6 (repository), W2.T8 (migration).

**Description:**
Create `SpecificationGenerationService` in `src/devflow_api/services/specification_generation.py`. Implement the 13-step generation pipeline (design §3.6). Create prompt templates as fixed-structure strings with named placeholders; untrusted content in delimited sections. Create `SpecificationOutputSchema` validator (structural, not AI). Implement context truncation with priority order: truncate `repo_context` first, then `clarifying_questions`. Persist `SpecificationRequest`, `SpecificationVersion`, `SpecificationArtifact`, `GenerationAttempt` via repositories. Write all named audit events.

**Acceptance Criteria:**
W2.T4.1 — End-to-end generation test with mocked `AIProvider` and mocked `MCPClientAdapter` creates all three artifact rows and sets `GenerationAttempt.status = "succeeded"`.
W2.T4.2 — A mocked provider returning malformed output sets `GenerationAttempt.status = "failed"` with `code = "MALFORMED_OUTPUT"` and creates no artifact rows.
W2.T4.3 — Prompt text is NEVER stored in any database column; only `prompt_hash` is persisted; a test verifies no database column contains the literal prompt string.
W2.T4.4 — `repo_context` injection test: an injected instruction string in `repo_context` does not appear in the instruction section of the constructed prompt.
W2.T4.5 — Context truncation test: a `repo_context` exceeding `AI_MAX_PROMPT_TOKENS` is truncated; `GenerationAttempt.context_truncated = True`.
W2.T4.6 — `SpecificationRequest` with only `title` and `description` is accepted and generates successfully with optional fields empty.
W2.T4.7 — `GenerationAttempt` row is created before the AI call; `status` starts as `"pending"` then `"running"`.
W2.T4.8 — Non-critical MCP failure proceeds with generation; critical MCP failure sets `status = "failed"` with `code = "MCP_CONTEXT_FAILURE"`.
W2.T4.9 — `SpecificationGenerationService` imports neither `OllamaProvider` nor `OpenAIProvider` directly; test via `ast.parse`.
W2.T4.10 — `subprocess`, `os.system`, `exec`, `eval` calls are absent from the service module; mandatory AST guard test passes.

---

### W2.T5 — `SpecificationReviewService` and finding classification

**Area:** REQ-W2.5.1, W2.5.2, W2.5.3, W2.5.4, W2.5.5, W2.4.2, W2.4.3, W2.4.4
**Size:** M
**Depends on:** W2.T1, W2.T6 (repository), W2.T8 (migration).

**Description:**
Create `SpecificationReviewService` in `src/devflow_api/services/specification_review.py`. Implement deterministic checks (Phase 1: pure functions, no AI, no network). Implement AI semantic review (Phase 2: structured prompt, `ReviewOutputSchema` validator). Create `ReviewFinding` Pydantic v2 model and persist via repository. Implement `finding_count_by_severity` computation. Implement lifecycle transition: `Critical`/`High` → `Revision Required`; none → `Ready for Approval`. Write all named audit events.

**Acceptance Criteria:**
W2.T5.1 — Deterministic check functions are pure (no network, no DB); unit tested with known-bad inputs.
W2.T5.2 — An artifact missing the required metadata block triggers a deterministic `Critical` finding without any AI call.
W2.T5.3 — An artifact with no acceptance criteria on a requirement triggers a deterministic `High` finding.
W2.T5.4 — AI review findings carry `source="ai"` and include the disclaimer string in `recommendation`.
W2.T5.5 — `ReviewAttempt.artifact_hash = sha256((requirements_text + "\n---\n" + design_text + "\n---\n" + tasks_text).encode("utf-8")).hexdigest()` (concatenated in fixed order using `\n---\n` as separator, identical to `content_digest`); test verifies the hash is deterministic.
W2.T5.6 — With a `Critical` finding, `SpecificationVersion.status` transitions to `"revision_required"`.
W2.T5.7 — With no `Critical` findings, `SpecificationVersion.status` transitions to `"ready_for_approval"`.
W2.T5.8 — Artifact text is NEVER stored in any database column; only `artifact_hash` is persisted; test verifies.
W2.T5.9 — Malformed AI review response triggers a `High` deterministic finding `AI_REVIEW_MALFORMED`.
W2.T5.10 — `subprocess`, `os.system`, `exec`, `eval` absent from the service module; AST guard test passes.

---

### W2.T6 — `SpecificationVersionRepository` and content hashing

**Area:** REQ-W2.2.2, W2.2.3, W2.4.5, W2.5.5, W2.6.1, W2.6.2, W2.6.3, W2.6.4
**Size:** M
**Depends on:** W2.T8 (migration must exist for the tables).

**Description:**
Create `SpecificationVersionRepository` in `src/devflow_api/repositories/specification_version.py`. Implement methods: `create_request`, `get_request`, `update_request`, `create_version`, `transition_status` (CAS with `BEGIN IMMEDIATE`), `compute_and_set_digest`, `verify_digest`, `save_artifact`, `get_artifact`, `list_versions`, `list_requests`. **F15:** Content digest computation MUST use the canonical separator defined in `design.md §3.8`: `sha256((requirements_text + "\n---\n" + design_text + "\n---\n" + tasks_text).encode("utf-8")).hexdigest()`. Do not use simple concatenation. `transition_status` raises `InvalidSpecTransitionError` on CAS failure.

**Acceptance Criteria:**
W2.T6.1 — `transition_status` with correct `from_status` succeeds; with wrong `from_status` raises `InvalidSpecTransitionError` without mutating the row.
W2.T6.2 — `compute_and_set_digest` returns a 64-character hex string; calling it twice on unchanged artifacts produces the same digest.
W2.T6.3 — `verify_digest` returns `True` when artifacts are unchanged; `False` when any artifact is modified.
W2.T6.4 — An approved version cannot be transitioned; `transition_status` raises `InvalidSpecTransitionError` for any transition from `"approved"`.
W2.T6.5 — `list_versions` returns all versions for a request in ascending `version_number` order; prior versions are never deleted.
W2.T6.6 — `BEGIN IMMEDIATE` is used for all write transactions; a concurrent CAS test confirms only one succeeds.
W2.T6.7 — `mypy --strict` passes for the repository module.

---

### W2.T7 — `SpecificationApprovalService` integrating Wave 1 approval framework

**Area:** REQ-W2.7.1, W2.7.2, W2.7.3, W2.7.4, W2.7.5, W2.7.6
**Size:** M
**Depends on:** W2.T6, Wave 1 `ApprovalService` (existing in `src/devflow_api/services/approval.py`).

**Description:**
Create `SpecificationApprovalService` in `src/devflow_api/services/specification_approval.py` and `SpecificationApprovalRepository` in `src/devflow_api/repositories/specification_approval.py`. Implement `request_approval`, `resolve_standalone`, `resolve_bound`, `is_implementation_authorized`. Do NOT create `ApprovalRequest` rows in `approval_requests` directly.

**F9 — Canonical `parameters_hash`:**
```python
parameters_hash = hashlib.sha256(
    f"{version_id}:{content_digest}".encode("utf-8")
).hexdigest()
```
(colon separator; `version_id` as decimal string; `content_digest` as 64-char hex). Used in both paths.

**F-FIN-1/F-FIN-5 — Standalone path (when `SpecificationRequest.workflow_run_id IS NULL`):**
Implement `SpecificationApprovalRepository` with:
- `create(version_id, parameters_hash, actor_id, expires_at)`: `BEGIN IMMEDIATE`; idempotent (return existing pending row if unexpired); INSERT into `specification_approval_requests`.
- `consume_atomic(approval_id, expected_version_id, expected_parameters_hash, expected_actor_id)`: `BEGIN IMMEDIATE`; validate all binding fields; CAS `UPDATE … WHERE consumed_at IS NULL`; raise `ApprovalAlreadyResolvedError` if rowcount=0.
- `reject(approval_id)`: `BEGIN IMMEDIATE`; CAS `UPDATE … SET rejected_at = now() WHERE consumed_at IS NULL AND rejected_at IS NULL`; raise `ApprovalAlreadyResolvedError` if rowcount=0.
- `get(approval_id)`: simple SELECT.

**F-FIN-3 — Workflow-bound path (when `SpecificationRequest.workflow_run_id IS NOT NULL`):**
Call `ApprovalService.request_bound_approval(run_id=spec_request.workflow_run_id, step_run_id=spec_request.workflow_step_id)`.

**F-FIN-4 — `ApprovalOperation` enum:** The workflow-bound step template MUST have `protected_operation = "specification_approval"` (the actual enum value in `src/devflow_api/schemas/workflow_template.py`). The value `"approve_specification"` is NOT in the enum and MUST NOT be passed to Wave 1. The standalone `specification_approval_requests.operation` field uses `"approve_specification"` as a free TEXT value only.

**F-FIN-2 — Path-discriminated approval columns:** On `Approved` transition, set `spec_standalone_approval_id` (standalone path) or `spec_bound_approval_id` (bound path) on the `SpecificationVersion` row. The old single `approval_id` column is replaced by these two columns.

Write all named audit events. All standalone audit calls pass `workflow_run_id = None` to `AuditLogRepository.log_event`.

**Acceptance Criteria:**
W2.T7.1 — **Standalone path:** `request_approval` calls `SpecificationApprovalRepository.create`; a row is inserted into `specification_approval_requests` with `consumed_at = NULL` and `rejected_at = NULL`. No row is written to `approval_requests`. **Workflow-bound path:** `request_approval` calls `ApprovalService.request_bound_approval(run_id=spec_request.workflow_run_id, step_run_id=spec_request.workflow_step_id)`.
W2.T7.2 — `resolve_standalone(approved)` calls `SpecificationApprovalRepository.consume_atomic`; on success, transitions `SpecificationVersion.status` to `"approved"` and sets `spec_standalone_approval_id`. All four operations (consume, verify_digest, transition_status, log_event) run inside a single `BEGIN IMMEDIATE` transaction; a simulated digest-mismatch mid-transaction rolls back the consume.
W2.T7.3 — `resolve_bound(approved)` calls `ApprovalService.resolve` (Phase 1); on `"approved"` return, verifies digest and transitions `SpecificationVersion.status` to `"approved"` and sets `spec_bound_approval_id`. `resolve_bound` MUST NOT call `ApprovalRepository.consume_atomic` or `dispatch_protected_txn`; test verifies via mock that neither is called.
W2.T7.4 — Rejection transitions spec to `"revision_required"` and writes `spec_approval_rejected` audit event.
W2.T7.5 — Concurrent resolution test: two simultaneous `resolve_standalone` calls → exactly one succeeds; the other raises `APPROVAL_ALREADY_RESOLVED`.
W2.T7.6 — `is_implementation_authorized` returns `False` when no approved version exists.
W2.T7.7 — `is_implementation_authorized` returns `False` when `verify_digest` returns `False` for the approved version.
W2.T7.16 — **A3/A6 — Standalone path approved-not-consumed:** `is_implementation_authorized` returns `False` when `SpecificationVersion.status = "approved"` but `specification_approval_requests.consumed_at IS NULL` (approval was set up but consume_atomic was never called). This guards against a state where `resolve_standalone` was called but the transaction rolled back after setting spec status.
W2.T7.17 — **A6 — Standalone path successfully consumed:** `is_implementation_authorized` returns `True` when `SpecificationVersion.status = "approved"`, `verify_digest` passes, and `consumed_at IS NOT NULL`.
W2.T7.18 — **A6 — Workflow-bound path approved:** `is_implementation_authorized` returns `True` when `SpecificationVersion.status = "approved"` and `verify_digest` passes; it does NOT require checking `authorization_expires_at` or `consumed_at` on `approval_requests` (those are Wave 1's gate at dispatch time).
W2.T7.19 — **A6 — No implementation authorization before approval gate:** A test verifies that `is_implementation_authorized` returns `False` for a spec that is in `"ready_for_approval"` state (approval requested but not yet resolved). No downstream Wave 3 invocation can proceed.
W2.T7.20 — **C — Digest-mismatch in workflow-bound path:** A test mocks `ApprovalService.resolve` to return `("approved", run_mock)` and then returns `False` from `verify_digest`. Verifies: (a) `SPEC_DIGEST_MISMATCH` is raised; (b) `SpecificationVersion.status` remains `"ready_for_approval"`; (c) `spec_approval_digest_mismatch` audit event is written; (d) Wave 2 does NOT call `ApprovalRepository.resolve` again or any cancellation method on the already-resolved `ApprovalRequest`.
W2.T7.8 — `APPROVAL_EXPIRED` and `APPROVAL_ALREADY_RESOLVED` for bound approvals originate from Wave 1 `ApprovalService`; test verifies via mock.
W2.T7.9 — `APPROVAL_EXPIRED` and `APPROVAL_ALREADY_RESOLVED` for standalone approvals are raised by `SpecificationApprovalRepository`; test verifies both expiry (past `expires_at`) and double-consume scenarios.
W2.T7.10 — Approving an already-approved version returns HTTP 409 `SPEC_APPROVED_NO_OVERWRITE`.
W2.T7.11 — All audit events pass `workflow_run_id = None` for the standalone path; none attempt to write a non-null FK into `workflow_audit_log.workflow_run_id` for standalone events.
W2.T7.12 — Six approval audit events are written (`spec_approval_requested`, `spec_approved`, `spec_approval_rejected`, `spec_approval_expired`, `spec_draft_created`, `critical_finding_acknowledged`); tests verify each.
W2.T7.13 — `consume_atomic` validates `expected_version_id`, `expected_parameters_hash`, and `expected_actor_id` before consuming; mismatched binding raises `ApprovalBindingMismatch` (not `ApprovalAlreadyResolvedError`).
W2.T7.14 — **C1 atomicity test:** A test injects a failure after `consume_atomic` succeeds but before `transition_status` is called (simulating a crash mid-transaction); the test verifies the transaction rolls back and `consumed_at` is NOT set on the `specification_approval_requests` row.
W2.T7.15 — **C2 non-consumption test:** For the workflow-bound path, a test mocks `ApprovalService.resolve` to return `("approved", run_mock)` and verifies that `ApprovalRepository.consume_atomic` is never called by `resolve_bound`. Consumption is Wave 1's responsibility at dispatch time.

---

### W2.T8 — Alembic migration `009_add_ai_specification_generation`

**Area:** Design §9; REQ-W2.2.2, W2.4.5, W2.5.5, W2.6.1, W2.6.2
**Size:** M
**Depends on:** Wave 1 migration `008_add_workflow_execution_engine` (must be verified as head before authoring).

**Description:**
Author `alembic/versions/009_add_ai_specification_generation.py` chaining from `008`. Create all seven tables (`specification_requests`, `specification_approval_requests`, `specification_versions`, `specification_artifacts`, `generation_attempts`, `review_attempts`, `review_findings`) with CHECK constraints, FKs, and all fifteen indexes as specified in design §9. The table creation order matters: `specification_approval_requests` must be created before `specification_versions` to satisfy the FK from `specification_versions.spec_standalone_approval_id`. Reversible `downgrade()` drops all seven tables and all fifteen indexes. Do NOT alter any Phase 0/1/Wave 1 table.

**F-FIN-3:** `specification_requests.workflow_run_id` references `workflow_runs(id)` (NOT `workflows(id)`). Column renamed from `workflow_id` to `workflow_run_id`.

**F-FIN-2:** `specification_versions` replaces `approval_id INTEGER REFERENCES approval_requests(id)` with two columns: `spec_standalone_approval_id INTEGER REFERENCES specification_approval_requests(id) ON DELETE SET NULL` and `spec_bound_approval_id INTEGER REFERENCES approval_requests(id) ON DELETE SET NULL`.

**Acceptance Criteria:**
W2.T8.1 — `alembic upgrade head` from `008` reaches `009` with no errors.
W2.T8.2 — `alembic downgrade -1` from `009` returns to `008` with no errors; all seven tables and all fifteen indexes are dropped.
W2.T8.3 — Round-trip `001 → 009 → 001` completes without error (run on a fresh database).
W2.T8.4 — After `upgrade()`, all Phase 1 rows remain valid; `SELECT COUNT(*) FROM workflows` matches the pre-migration count.
W2.T8.5 — After `downgrade()`, all Phase 1 rows remain valid.
W2.T8.6 — `mypy --strict` passes for the migration file.
W2.T8.7 — Alembic head is confirmed before migration is authored; the migration file's `down_revision` equals `'008_add_workflow_execution_engine'` (or the confirmed hash).

---

### W2.T9 — FastAPI routes and OpenAPI schemas

**Area:** REQ-W2.8.1, W2.8.2, W2.8.3
**Size:** M
**Depends on:** W2.T4, W2.T5, W2.T7, W2.T8.

**Description:**
Create `src/devflow_api/routers/specification_requests.py` with all fourteen routes listed in design §4.1. Create all request/response Pydantic v2 schemas in `src/devflow_api/schemas/specification.py`. The `SpecificationRequestCreate` schema uses `workflow_run_id: int | None = None` (FK to `WorkflowRun.id`) and `workflow_step_id: int | None = None`. Implement 202 Accepted + background-task pattern for `/generate` and `/review`. Implement `/status` poll endpoint reading `GenerationAttempt` or `ReviewAttempt` status. Register router in `src/devflow_api/main.py`. Add `ErrorResponse` schema. Implement HTTP 500 guard: no stack trace in response body.

**Acceptance Criteria:**
W2.T9.1 — `POST /api/v1/specification-requests` with valid body returns HTTP 201 with all required response fields.
W2.T9.2 — `POST /api/v1/specification-requests/{id}/generate` returns **HTTP 202** with `task_id`, `poll_url`, and `status = "pending"`. The HTTP connection is not held open during inference.
W2.T9.3 — `GET /api/v1/specification-requests/{id}/status` returns **HTTP 200** for all attempt states (pending, running, succeeded, failed, cancelled). The response body includes `status`, `error_code` (nullable), and `error_message` (nullable).
W2.T9.4 — All fourteen routes appear in `/openapi.json` (twelve original + two cancellation routes).
W2.T9.5 — All 15 error codes from REQ-W2.8.3 are covered by at least one test, asserted at the correct lifecycle stage: synchronous codes verified as direct HTTP status codes; asynchronous codes verified as `error_code` values in HTTP 200 poll responses.
W2.T9.6 — An unhandled exception in a handler returns HTTP 500 with `{"code":"INTERNAL_ERROR","error":"An internal error occurred."}` and no stack trace.
W2.T9.7 — `actor_id` is NEVER read from request bodies; it always equals `Settings.LOCAL_OPERATOR_ID`.
W2.T9.8 — `mypy --strict` passes for the router and schema modules.
W2.T9.9 — **F6:** `DELETE /api/v1/specification-requests/{id}/generate` returns HTTP 200 `{"status": "cancellation_requested"}` when the generation attempt is in `pending` or `running` state; returns HTTP 409 `{"code": "TASK_NOT_CANCELLABLE", "error": "..."}` when the attempt is absent or in a terminal state.
W2.T9.10 — **F6:** `DELETE /api/v1/specification-requests/{id}/review` returns HTTP 200 `{"status": "cancellation_requested"}` when the review attempt is in `pending` or `running` state; returns HTTP 409 `{"code": "TASK_NOT_CANCELLABLE", "error": "..."}` when the attempt is absent or in a terminal state.

---

### W2.T10 — Streamlit pages (spec request, generation status, review findings, approval)

**Area:** REQ-W2.8.4, W2.8.5, W2.5.4
**Size:** M
**Depends on:** W2.T9.

**Description:**
Create four Streamlit page files: `src/devflow_ui/pages/7_Spec_Request.py`, `8_Generation_Status.py`, `9_Review_Findings.py`, `10_Approval.py`. Implement all named UI states (design §5). Implement polling (3-second `st.rerun`) for generation and review status pages. Add disclaimer text (REQ-W2.5.4) to review findings page. Add `content_digest` (12-char prefix) display to approval page. Implement provider-unavailable state without suggesting fallback.

**Acceptance Criteria:**
W2.T10.1 — Each named UI state renders a user-visible message; no blank or spinner-only state for error conditions.
W2.T10.2 — The disclaimer from REQ-W2.5.4 appears on `9_Review_Findings.py` above the findings list.
W2.T10.3 — Provider-unavailable state displays provider name and `PROVIDER_UNAVAILABLE` without suggesting OpenAI fallback.
W2.T10.4 — Approval page displays `content_digest[:12]` for the current version.
W2.T10.5 — Acknowledge button appears on `Critical` findings and writes `critical_finding_acknowledged` audit event via API call.
W2.T10.6 — Approve/Reject buttons are present; approve triggers `POST /api/v1/specification-requests/{id}/approve`; reject includes rejection reason field.
W2.T10.7 — Streamlit `import` test: all four pages import without error when the API is not running (mocked `APIClient`).

---

### W2.T11 — Test suite (offline/mocked providers; CI offline)

**Area:** REQ-W2.9.1 through W2.9.9; all requirements areas
**Size:** L
**Depends on:** W2.T1 through W2.T10.

**Description:**
Author the Wave 2 test suite in `tests/test_wave2_*.py`. All tests MUST run without live Ollama, OpenAI, or MCP servers. Use `pytest` fixtures with mocked providers, `httpx.MockTransport`, and in-memory SQLite. Include: provider unit tests, MCP adapter tests, generation service tests, review service tests, approval service tests, repository tests, router integration tests, security tests (prompt injection, secret redaction, no-OpenAI-egress, AST guards, no-execution), startup recovery test, and concurrency tests. CI pipeline MUST NOT require any external service.

**Acceptance Criteria:**
W2.T11.1 — **Amendment B (v1.6.1):** All Wave 2 focused tests MUST pass, run without live external services, use deterministic providers/fixtures, and complete in **under 120 seconds** on the documented reference environment. Advisory target: under 60 seconds (optimization target, not a release blocker).

**Reference environment:**
- OS: Windows
- Python: 3.12.10
- pytest: 9.2.0
- DB: SQLite in-memory
- Coverage: `--no-cov` for focused runs (coverage applied in full suite only)
- Command: `python -m pytest tests/ -k wave2 --no-cov -q --durations=15`
- Execution mode: sequential

The mandatory gate is 120 seconds. Tests MUST NOT be removed, skipped, or have assertions reduced to meet this limit. The 80% branch coverage floor applies to the full suite run, not focused runs.
W2.T11.2 — Wave 1 tests are unaffected; `pytest tests/ -k "not wave2"` passes without change.
W2.T11.3 — AST guard test scans all Wave 2 service and adapter modules; asserts no `subprocess`, `os.system`, `exec`, `eval` calls.
W2.T11.4 — Secret redaction test: a generation attempt with `OPENAI_API_KEY` set confirms the key value does not appear in any log output or database column.
W2.T11.5 — No-OpenAI-egress test: `AI_PROVIDER="ollama"` with mocked network confirms zero requests to `api.openai.com`.
W2.T11.6 — Prompt-injection test: injected instruction in `repo_context` does not alter the instruction section of the constructed prompt.
W2.T11.7 — Startup recovery test: a `GenerationAttempt` left in `"running"` state is recovered to `"failed"` with `error_code="INTERRUPTED"` on simulated restart.
W2.T11.8 — Concurrent approval test: two simultaneous `resolve(approved)` calls → exactly one succeeds.
W2.T11.9 — **Amendment A7 (v1.6.1):** All 15 error codes from REQ-W2.8.3 are covered by at least one test, asserted at the **correct lifecycle stage**:
  - **Synchronous codes** (verified as direct HTTP status codes, not in poll response): `INVALID_SPECIFICATION_REQUEST` (422), `PROVIDER_NOT_CONFIGURED` (400), `GENERATION_ALREADY_IN_PROGRESS` (409), `REVIEW_ALREADY_IN_PROGRESS` (409), `SPEC_APPROVED_NO_OVERWRITE` (409), `INVALID_SPEC_TRANSITION` (409), `APPROVAL_EXPIRED` (409), `APPROVAL_ALREADY_RESOLVED` (409), `SPEC_DIGEST_MISMATCH` (409), `TASK_NOT_CANCELLABLE` (409).
  - **Asynchronous codes** (verified as `error_code` field in HTTP 200 poll response body, NOT as direct HTTP error statuses): `PROVIDER_UNAVAILABLE`, `PROVIDER_TIMEOUT`, `MALFORMED_OUTPUT`, `MCP_CONTEXT_FAILURE`, `PROVIDER_CANCELLED`.
  - **Review-specific async code** (verified as `error_code` in HTTP 200 poll response): `AI_REVIEW_MALFORMED`.
  Full 15-code inventory is preserved; no code is removed or reclassified.
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

---

### W2.T13 — `SpecificationRecoveryService`

**Area:** REQ-W2.9.9
**Size:** S
**Depends on:** W2.T6, W2.T7, W2.T8 (tables must exist).

**Description:**
Create `SpecificationRecoveryService` in `src/devflow_api/services/specification_recovery.py`. This is NOT a subclass of or replacement for the Wave 1 `RecoveryService`; it runs alongside it. Implement `recover() -> dict[str, int]` returning counts of recovered generations, reviews, and expired approvals.

**F-FIN-6:** Implements the three recovery sweeps defined in design §7:
1. Recover `GenerationAttempt` rows in `"running"` state: `UPDATE … SET status = 'failed', error_code = 'INTERRUPTED'`; cascade to `SpecificationRequest.status = 'draft'` and `SpecificationVersion.status = 'draft'`; write `spec_generation_failed` audit event with `workflow_run_id = None`.
2. Recover `ReviewAttempt` rows in `"running"` state; cascade to `SpecificationVersion.status = 'generated'`; write `spec_review_failed` audit event with `workflow_run_id = None`.
3. Write `spec_approval_expired` audit events for standalone approvals past `expires_at` (no row mutation needed).

Call `SpecificationRecoveryService.recover()` from the FastAPI lifespan startup handler, after Wave 1 `RecoveryService.recover()`.

**Acceptance Criteria:**
W2.T13.1 — A `GenerationAttempt` left in `"running"` at startup is recovered to `"failed"` with `error_code = "INTERRUPTED"`; `SpecificationRequest.status` returns to `"draft"`.
W2.T13.2 — A `ReviewAttempt` left in `"running"` at startup is recovered to `"failed"` with `error_code = "INTERRUPTED"`; `SpecificationVersion.status` returns to `"generated"`.
W2.T13.3 — Recovery is idempotent: calling `recover()` twice on the same state produces the same result.
W2.T13.4 — Recovery does not auto-trigger new generation or review.
W2.T13.5 — All audit events written by recovery pass `workflow_run_id = None` to `AuditLogRepository.log_event`.
W2.T13.6 — `SpecificationRecoveryService.recover()` is registered in the FastAPI lifespan startup handler; `RecoveryService.recover()` runs first.
W2.T13.7 — `mypy --strict` passes for the recovery module.

---

### W2.T14 — `ExecutorRegistry` extension and Wave 2 executor registration

**Area:** Design §6.1
**Size:** S
**Depends on:** W2.T4, W2.T5, W2.T8.

**Description:**

**A1/A2 — Source-verified prerequisite.** `ExecutorRegistry.register()` currently enforces a hardcoded guard `if executor.identifier.id != "mock": raise ExecutorSelectionError`. This guard must be extended to allow Wave 2 executors before `SpecGeneratorExecutor` or `SpecReviewerExecutor` can be registered.

Extend `src/devflow_api/executors/registry.py` `ExecutorRegistry.register()` to accept any executor whose `identifier.id` is in a configured allowlist (or simply remove the mock-only guard while keeping uniqueness enforcement). Then implement and register:

- `SpecGeneratorExecutor` in `src/devflow_api/executors/specification_generator.py`
- `SpecReviewerExecutor` in `src/devflow_api/executors/specification_reviewer.py`

No `SpecApproverExecutor` is required. The Wave 1 orchestrator handles the approval gate automatically for any step with `approvable = True` and `protected_operation = "specification_approval"`.

**Acceptance Criteria:**
W2.T14.1 — `ExecutorRegistry.register(SpecGeneratorExecutor())` succeeds without raising `ExecutorSelectionError`.
W2.T14.2 — `ExecutorRegistry.register(SpecReviewerExecutor())` succeeds without raising `ExecutorSelectionError`.
W2.T14.3 — `ExecutorRegistry.select("spec_generator", ...)` returns a `SpecGeneratorExecutor` instance; `select("spec_reviewer", ...)` returns a `SpecReviewerExecutor` instance.
W2.T14.4 — `ExecutorRegistry.select("mock", ...)` still returns a `MockExecutor` (backward compatibility preserved).
W2.T14.5 — A test verifies that a workflow step template with `executor_id = "spec_generator"` and `approvable = True` and `protected_operation = "specification_approval"` passes `WorkflowTemplate` validation (this is the approval-gate pattern; no separate approver executor is needed).
W2.T14.6 — `mypy --strict` passes for the registry and both new executor modules.

---

### W2.T12 — Wave 2 readiness report

**Area:** Specification completeness; quality gate
**Size:** S
**Depends on:** W2.T1 through W2.T11.

**Description:**
Author `docs/reports/phase2-wave2-spec-readiness.md` and `docs/reports/phase2-wave2-mcp-compatibility-assessment.md`. Run the quality gate checklist. Update `docs/planning/phase2-roadmap.md` Wave 2 section with approved decisions. Confirm spec files are committed on `feature/phase2-wave2-ai-spec-generation`.

**Acceptance Criteria:**
W2.T12.1 — Readiness report lists all spec files with line counts.
W2.T12.2 — Readiness report lists all 54 requirements by area with counts.
W2.T12.3 — Readiness report states MCP compatibility verdict with rationale.
W2.T12.4 — Quality gate section confirms all nine checklist items are satisfied or notes remaining blockers.
W2.T12.5 — MCP compatibility assessment covers SDK version declared, target range, compatibility verdict, Dependabot PR #20 impact.
W2.T12.6 — Readiness report ends with `PHASE 2 WAVE 2 SPECIFICATIONS READY — AWAITING CHATGPT REVIEW`.
W2.T12.7 — All spec files (`requirements.md`, `design.md`, `tasks.md`) are committed to the branch.

---

## Task Dependency Graph (Wave 2)

```
Wave 1 baseline (b3b37ff)
    │
    ├── W2.T1 (AIProvider + OllamaProvider)
    │       │
    │       └── W2.T2 (OpenAIProvider)
    │
    ├── W2.T1 ─────────────────────────────── W2.T4 (SpecificationGenerationService) ──────────────┐
    │                                                                                                │
    ├── W2.T3 (MCPClientAdapter) ───────────────────────────────────────────────────────────────────┤
    │                                                                                                │
    ├── W2.T8 (Migration 009) ─── W2.T6 (VersionRepository) ───────────────────────────────────────┤
    │                                     │                                                          │
    │                                     └── W2.T7 (ApprovalService) ──────────────────────────────┤
    │                                                │                                               │
    │                                     W2.T13 (SpecificationRecoveryService) ────────────────────┤
    │                                                                                                │
    │                                     W2.T5 (ReviewService) ────────────────────────────────────┤
    │                                                                                                │
    │                        W2.T4 + W2.T5 ──── W2.T14 (ExecutorRegistry + Executors) ─────────────┤
    │                                                                                                │
    │                                              All ──── W2.T9 (Routers) ───────────────────────┤
    │                                                              │                                 │
    │                                                              └── W2.T10 (UI) ─────────────────┤
    │                                                                                                │
    │                                              All ──── W2.T11 (Tests) ─────────────────────────┤
    │                                                                                                │
    └────────────────────────────────────────── W2.T12 (Readiness Report) ◄──────────────────────────┘
```

---

## Requirements Traceability

| Task | Requirements Covered |
|---|---|
| W2.T1 | REQ-W2.1.1 – W2.1.8 |
| W2.T2 | REQ-W2.1.1 – W2.1.3, W2.1.5 – W2.1.8 |
| W2.T3 | REQ-W2.3.1 – W2.3.6 |
| W2.T4 | REQ-W2.2.1 – W2.2.4, W2.4.1 – W2.4.7, W2.9.1 |
| W2.T5 | REQ-W2.4.2 – W2.4.4, W2.5.1 – W2.5.5 |
| W2.T6 | REQ-W2.2.2, W2.2.3, W2.4.5, W2.5.5, W2.6.1 – W2.6.4 |
| W2.T7 | REQ-W2.7.1 – W2.7.6 |
| W2.T8 | REQ-W2.2.2, W2.4.5, W2.5.5, W2.6.1, W2.6.2 (persistence) |
| W2.T9 | REQ-W2.8.1 – W2.8.3 |
| W2.T10 | REQ-W2.8.4, W2.8.5, W2.5.4 |
| W2.T11 | REQ-W2.9.1 – W2.9.9 (security/reliability test coverage) |
| W2.T12 | All (quality gate verification) |
| W2.T13 | REQ-W2.9.9 (SpecificationRecoveryService) |
| W2.T14 | Design §6.1 (ExecutorRegistry extension, SpecGeneratorExecutor, SpecReviewerExecutor) |
