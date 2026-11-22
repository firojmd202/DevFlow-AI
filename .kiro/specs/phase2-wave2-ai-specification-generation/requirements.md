# DevFlow AI — Phase 2 Wave 2: AI Specification Generation and Review Requirements

**Version:** 1.0.0
**Status:** Draft
**Scope:** Phase 2 Wave 2 — AI Specification Generation and Review
**Branch:** `feature/phase2-wave2-ai-spec-generation`
**Base commit:** `b3b37ff` (Wave 1 implementation merged, develop HEAD)
**Last Updated:** 2026-11-18
**Supersedes:** None (first Wave 2 specification). Extends `.kiro/specs/phase2-wave1-workflow-execution-engine/` (v2.1.4); does not modify it.

**Version history:**
- v1.0.0 — 2026-11-18 — Initial Wave 2 specification draft.

---

## Overview

Wave 2 adds AI-driven specification generation and review to the DevFlow AI workflow engine delivered in Wave 1. A user describes a software feature; Wave 2 generates structured `requirements.md`, `design.md`, and `tasks.md` artifacts using Ollama (default) or optional OpenAI; an AI review pass evaluates the artifacts for completeness, consistency, and quality; and a human approval gate (reusing the Wave 1 approval framework) gates progression to Wave 3.

Wave 2 deliberately ships **no real coding-agent execution** (Codex CLI, Kiro automation, autonomous GitHub writes). Every external AI call is explicitly user-initiated and approval-gated where it produces authoritative artifacts. Wave 2 layers on the Wave 1 `WorkflowOrchestrator` and extends its persistence schema via Alembic migration 009.

**Wave 2 scope in one sentence:** Given a user-authored feature description, produce AI-generated specification artifacts, run an AI review, present findings to the user, and gate advancement on explicit human approval — without executing any generated code or commands.

### Global Constraints (apply to all requirements below)

- The application MUST remain local-first with free core functionality. Ollama is the default AI provider and is free to run locally; OpenAI is optional and must NEVER be invoked without explicit user configuration.
- All development services MUST bind exclusively to `127.0.0.1`.
- The codebase MUST NOT contain Android, React, TypeScript, or Vite artefacts.
- No hardcoded credentials or secrets MUST appear in source control.
- Architecture boundaries from Phase 0/1/Wave 1 MUST be preserved: UI → API → domain services → repositories → SQLite; services → adapters.
- Phase 0, Phase 1, and Wave 1 specification files and production tests MUST NOT be broken by Wave 2 implementation.
- `datetime.utcnow()` MUST NOT appear in any Wave 2 code; use `datetime.now(UTC)` exclusively.
- All new timestamp columns MUST use `UTCDateTime` from `src/devflow_api/models/base.py`.
- **LLM output is NOT inherently safe or deterministic.** Wave 2 MUST NOT claim otherwise. AI-generated review findings are recommendations, not guaranteed facts.
- Generated specification artifacts MUST NOT be executed as code or commands. No Wave 2 path invokes generated content.
- OpenAI MUST NEVER be invoked silently as a fallback when Ollama is unavailable. If Ollama fails and OpenAI is not explicitly configured, the operation MUST fail with a clear error.

### Out of Scope for Wave 2

| Capability | Deferral |
|---|---|
| Real Codex CLI or Kiro execution | Wave 3 |
| Autonomous GitHub PR creation | Wave 4 |
| Full Streamlit workflow dashboard | Wave 5 |
| OS-level process sandboxing | Wave 6 |
| Multi-user access control | Permanent exclusion for now |
| Executing or running generated spec content | Permanent exclusion |
| Merging PRs automatically | Permanent exclusion |

---

## Area W2.1 — AI Provider Abstraction

**Scope note (maps to task W2.T1, W2.T2):** A common interface supporting multiple AI providers with Ollama as the default and OpenAI as an optional, explicitly-configured alternative.

### REQ-W2.1.1
WHEN an AI operation is requested,
THEN the system MUST invoke it through an `AIProvider` abstract interface that is independent of any concrete provider SDK. The interface MUST define: `generate(prompt, model, options) → ProviderResponse`; `check_availability() → AvailabilityResult`; `check_capability(capability_name) → bool`; `provider_id: str`; `model_id: str`. No Wave 2 service MAY import a concrete provider class directly; all provider access MUST go through the interface.

**Acceptance Criteria:**
W2.1.1.1 — `AIProvider` is an abstract base class or Protocol in `src/devflow_api/schemas/ai_provider.py` or `src/devflow_api/providers/base.py`; `mypy --strict` passes.
W2.1.1.2 — `OllamaProvider` and `OpenAIProvider` both satisfy the `AIProvider` interface; a type-check test confirms this.
W2.1.1.3 — No service module imports `OllamaProvider` or `OpenAIProvider` directly; all provider access goes through the interface.

### REQ-W2.1.2
WHEN the system initialises an AI provider,
THEN `OllamaProvider` MUST be selected as the default when no provider is explicitly configured. The system MUST NOT select `OpenAIProvider` unless `Settings.AI_PROVIDER` is explicitly set to `"openai"` AND `Settings.OPENAI_API_KEY` is set to a non-empty value.

**Acceptance Criteria:**
W2.1.2.1 — With no AI provider setting, `ProviderFactory.create()` returns an `OllamaProvider`.
W2.1.2.2 — With `AI_PROVIDER="openai"` and no `OPENAI_API_KEY`, `ProviderFactory.create()` raises `ProviderConfigurationError`.
W2.1.2.3 — With `AI_PROVIDER="ollama"` explicitly set, `ProviderFactory.create()` always returns `OllamaProvider` regardless of whether `OPENAI_API_KEY` is set.

### REQ-W2.1.3
WHEN Ollama is unavailable and OpenAI is not configured,
THEN the system MUST fail the generation or review operation immediately with error code `PROVIDER_UNAVAILABLE` and MUST NOT attempt to call OpenAI. The error response MUST name the provider that was attempted.

**Acceptance Criteria:**
W2.1.3.1 — A test with Ollama returning a connection error (mocked) and no OpenAI config verifies `PROVIDER_UNAVAILABLE` is returned and OpenAI is never invoked.
W2.1.3.2 — The error message names `"ollama"` as the attempted provider.
W2.1.3.3 — No code path in `OllamaProvider` calls any OpenAI endpoint.

### REQ-W2.1.4
WHEN a provider request is made,
THEN the system MUST enforce a configurable request timeout (`Settings.AI_REQUEST_TIMEOUT_SECONDS`, default 120) and support cooperative cancellation. A timed-out request MUST surface as `PROVIDER_TIMEOUT`; a cancelled request as `PROVIDER_CANCELLED`.

**Acceptance Criteria:**
W2.1.4.1 — A mocked provider that sleeps beyond the timeout raises `PROVIDER_TIMEOUT`.
W2.1.4.2 — Cancellation via Python `asyncio.CancelledError` propagates correctly and surfaces as `PROVIDER_CANCELLED` at the service boundary.
W2.1.4.3 — `Settings.AI_REQUEST_TIMEOUT_SECONDS` is a declared setting with default 120.

### REQ-W2.1.5
WHEN a provider returns a response,
THEN the system MUST attempt to parse it into a structured `ProviderResponse` containing: `content: str`, `model: str`, `provider_id: str`, `usage: TokenUsage | None` (`prompt_tokens`, `completion_tokens`, `total_tokens`, all nullable), `finish_reason: str | None`, `request_id: str | None`. Providers that do not expose token metrics MUST set `usage = None`; callers MUST NOT treat `usage = None` as an error.

**Acceptance Criteria:**
W2.1.5.1 — `ProviderResponse` and `TokenUsage` are Pydantic v2 models with all fields typed.
W2.1.5.2 — `OllamaProvider` returns a valid `ProviderResponse` with `usage` populated when the Ollama API exposes token counts, and `usage = None` otherwise.
W2.1.5.3 — `OpenAIProvider` returns a valid `ProviderResponse` with `usage` populated from the OpenAI response `usage` field.

### REQ-W2.1.6
WHEN a provider error occurs,
THEN the system MUST normalize all provider-specific exceptions to a `ProviderError` hierarchy: `ProviderUnavailableError`, `ProviderTimeoutError`, `ProviderCancelledError`, `ProviderQuotaError`, `ProviderAuthError`, `ProviderMalformedResponseError`, `ProviderRateLimitError`. Each MUST carry `provider_id`, `model_id`, `error_code`, and `message`. Internal SDK exceptions MUST NOT leak to callers outside the provider implementation.

**Acceptance Criteria:**
W2.1.6.1 — Each `ProviderError` subclass carries `provider_id`, `model_id`, `error_code`, `message`.
W2.1.6.2 — An `httpx.ConnectError` from Ollama is wrapped in `ProviderUnavailableError`; an `httpx.TimeoutException` is wrapped in `ProviderTimeoutError`.
W2.1.6.3 — `mypy --strict` passes for all provider error classes.

### REQ-W2.1.7
WHEN a retryable provider error occurs (rate limit or transient connection error),
THEN the system MUST retry up to `Settings.AI_MAX_RETRIES` times (default 2) with exponential back-off, only for `ProviderRateLimitError` and `ProviderUnavailableError` with a transient flag. `ProviderAuthError`, `ProviderQuotaError`, and `ProviderMalformedResponseError` MUST NOT be retried. Total retry budget MUST NOT exceed `Settings.AI_RETRY_BUDGET_SECONDS` (default 30).

**Acceptance Criteria:**
W2.1.7.1 — A mocked provider that fails twice then succeeds completes successfully after two retries.
W2.1.7.2 — A `ProviderAuthError` is NOT retried; it surfaces immediately.
W2.1.7.3 — Retries do not exceed `AI_RETRY_BUDGET_SECONDS`; a mock that always fails terminates within budget.

### REQ-W2.1.8
WHEN provider configuration is loaded,
THEN it MUST be sourced exclusively from `Settings` (environment variables or `.env` file). No API key, base URL, or model name MAY appear in source code. The `ProviderConfig` schema MUST be validated at startup; invalid configuration MUST raise `ProviderConfigurationError` before any provider call is attempted.

**Acceptance Criteria:**
W2.1.8.1 — No literal API key, OpenAI URL, or model name appears in any `.py` file (enforced by a grep-based CI test).
W2.1.8.2 — `ProviderConfig` is a Pydantic v2 settings model; invalid values raise `ProviderConfigurationError` at construction.
W2.1.8.3 — `Settings` declares `AI_PROVIDER` (default `"ollama"`), `OLLAMA_MODEL` (default `"llama3.2"`), `OPENAI_MODEL` (default `"gpt-4o-mini"`), `AI_REQUEST_TIMEOUT_SECONDS` (default 120), `AI_MAX_RETRIES` (default 2), `AI_RETRY_BUDGET_SECONDS` (default 30).

---

## Area W2.2 — Feature Requirement Input

**Scope note (maps to task W2.T4 input layer):** The user-facing input model for describing a feature to be specified.

### REQ-W2.2.1
WHEN a user submits a specification request,
THEN the system MUST accept a `SpecificationRequest` containing: `title: str` (required, 1–200 chars), `description: str` (required, 1–4000 chars), `business_goal: str | None`, `functional_requirements: list[str]`, `nonfunctional_constraints: list[str]`, `acceptance_criteria: list[str]`, `repo_context: str | None` (project context summary, treated as untrusted per REQ-W2.9.1), `clarifying_questions: list[str]`, `workflow_id: int | None` (optional link to a `Workflow` for Wave 1 integration). Only `title` and `description` are required to start a draft.

**Acceptance Criteria:**
W2.2.1.1 — A request with only `title` and `description` is accepted (HTTP 201).
W2.2.1.2 — A request missing `title` or `description` returns HTTP 422 with `code = "INVALID_SPECIFICATION_REQUEST"`.
W2.2.1.3 — `title` exceeding 200 characters returns HTTP 422.
W2.2.1.4 — `description` exceeding 4000 characters returns HTTP 422.
W2.2.1.5 — All optional fields default to empty lists or `None`; the system does not require them before creating a draft.

### REQ-W2.2.2
WHEN a specification request is saved as a draft,
THEN the system MUST persist it with a unique `id`, `status = "draft"`, `version = 1`, `content_hash` (SHA-256 of the canonical request JSON), and UTC timestamps `created_at`, `updated_at`. The draft MUST survive process restart.

**Acceptance Criteria:**
W2.2.2.1 — After saving, `GET /api/v1/specification-requests/{id}` returns the persisted request with `status = "draft"` and `version = 1`.
W2.2.2.2 — `content_hash` equals `sha256(canonical_json(request_fields))`.
W2.2.2.3 — After a simulated restart, the draft is retrievable with the same `id`.

### REQ-W2.2.3
WHEN a draft specification request is updated,
THEN the system MUST increment `version`, recompute `content_hash`, update `updated_at`, and persist the new version while retaining the prior version in audit history. The state MUST remain `"draft"` after an update unless it has already been advanced.

**Acceptance Criteria:**
W2.2.3.1 — `PATCH /api/v1/specification-requests/{id}` increments `version` and updates `content_hash`.
W2.2.3.2 — An approved specification request MUST NOT be overwritten by a plain update; HTTP 409 `SPEC_APPROVED_NO_OVERWRITE` is returned.
W2.2.3.3 — The audit log records `spec_request_updated` with `prior_version`, `new_version`, `content_hash`.

### REQ-W2.2.4
WHEN provider and model selection is offered,
THEN the UI MUST allow the user to select the AI provider (`ollama` or `openai` if configured) and model name before initiating generation. The selected provider/model MUST be recorded on the `GenerationAttempt` and preserved for audit. If the user selects `openai` but it is not configured, the system MUST reject the request at submission with `PROVIDER_NOT_CONFIGURED` before any API call is made.

**Acceptance Criteria:**
W2.2.4.1 — Provider and model dropdowns appear in the UI; `openai` is only selectable when `Settings.AI_PROVIDER = "openai"` and `Settings.OPENAI_API_KEY` is set.
W2.2.4.2 — Selecting `openai` without configuration returns HTTP 400 `PROVIDER_NOT_CONFIGURED`.
W2.2.4.3 — `GenerationAttempt.provider_id` and `GenerationAttempt.model_id` are recorded on every generation attempt.

---

## Area W2.3 — MCP Context Integration

**Scope note (maps to task W2.T3):** An `MCPClientAdapter` that isolates MCP SDK-specific APIs and enforces strict access controls for context retrieval tools.

### REQ-W2.3.1
WHEN MCP server configuration is loaded,
THEN the system MUST source it from `MCPServerConfig` entries in `Settings` (or a config file referenced by `Settings`). Each entry MUST specify: `name`, `command`, `args`, `env`, `enabled`, `allowed_tools`, `timeout_seconds`. The `MCPClientAdapter` MUST reject calls to servers or tools not in the configured allowlist with `MCPPermissionError`.

**Acceptance Criteria:**
W2.3.1.1 — A call to a server not in the config raises `MCPServerNotFoundError`.
W2.3.1.2 — A call to a tool not in `allowed_tools` (and `"*"` not present) raises `MCPPermissionError`.
W2.3.1.3 — A disabled server (`enabled = False`) raises `MCPServerNotFoundError`.

### REQ-W2.3.2
WHEN the `MCPClientAdapter` is designed,
THEN it MUST wrap the existing `MCPClient` from `src/devflow_api/adapters/mcp_client.py` and add a Wave 2 adapter layer that: validates tool input against a registered JSON schema before invocation; normalizes `MCPToolResult` to a `ContextChunk` schema consumed by `SpecificationGenerationService`; records every tool call in the audit log with server name, tool name, argument hash (not raw arguments), and result status.

**Acceptance Criteria:**
W2.3.2.1 — Tool invocation arguments are validated against a registered schema before the subprocess is started; a schema violation raises `MCPToolSchemaError` without starting the subprocess.
W2.3.2.2 — Every MCP tool call writes an `mcp_tool_invoked` audit entry with `server_name`, `tool_name`, `argument_hash`, `result_status`.
W2.3.2.3 — `MCPClientAdapter` does not expose raw `MCPServerConfig.env` contents; credential values are not logged.

### REQ-W2.3.3
WHEN MCP tool invocations retrieve context for specification generation,
THEN the system MUST enforce strict access boundaries: MCP tools MUST NOT receive unrestricted filesystem access, shell execution rights, general network access, or repository-write access. The adapter MUST enforce these at the application level (not OS level). These are application-level controls; they are NOT OS sandboxing.

**Acceptance Criteria:**
W2.3.3.1 — The design explicitly documents that MCP controls are application-level and not OS sandboxing (matches Wave 1 REQ-E6.x boundary).
W2.3.3.2 — No `MCPServerConfig` in the codebase sets `allowed_tools = ["*"]` with unrestricted filesystem or shell commands.
W2.3.3.3 — A test verifies that a tool not in `allowed_tools` is rejected before subprocess launch.

### REQ-W2.3.4
WHEN an MCP invocation times out or fails,
THEN the system MUST surface a structured `MCPError` (wrapping `MCPTimeoutError`, `MCPConnectionError`, `MCPPermissionError`) to the calling service. Generation MAY proceed with reduced context if the MCP failure is non-critical (the service decides); a critical MCP failure MUST fail the generation attempt with `MCP_CONTEXT_FAILURE`.

**Acceptance Criteria:**
W2.3.4.1 — A timed-out MCP call raises `MCPTimeoutError` with `server_name`, `tool_name`, `timeout_seconds`.
W2.3.4.2 — `SpecificationGenerationService` distinguishes critical vs. non-critical MCP failures via a `ContextChunk.required` flag on the tool registration.
W2.3.4.3 — A non-critical MCP failure logs a warning and proceeds; a critical one sets `GenerationAttempt.status = "failed"` with `code = "MCP_CONTEXT_FAILURE"`.

### REQ-W2.3.5
WHEN MCP content is included in an AI prompt,
THEN it MUST be treated as untrusted input and sanitized according to REQ-W2.9.1 (prompt-injection defense). MCP tool output MUST be enclosed in clearly delimited content boundaries in the prompt template so the model cannot interpret it as instructions.

**Acceptance Criteria:**
W2.3.5.1 — Prompt templates include explicit delimiters around MCP-sourced content (e.g., `--- BEGIN CONTEXT (untrusted) ---` / `--- END CONTEXT ---`).
W2.3.5.2 — A test verifies that injected instruction strings in MCP content do not alter the prompt's instruction section.
W2.3.5.3 — Raw MCP tool output is never interpolated directly into the instruction portion of a prompt.

### REQ-W2.3.6
WHEN designing MCP compatibility,
THEN the `MCPClientAdapter` MUST be designed to work with the MCP Python SDK version declared in `requirements/base.txt` (`mcp>=1.0,<2.0`; target upgrade path `mcp>=2.3.0,<3.0` pending Dependabot PR #20 evaluation). The adapter MUST isolate all SDK-specific API calls behind the adapter boundary so that an SDK version upgrade requires changes only in the adapter, not in `SpecificationGenerationService` or other services. Compatibility tests MUST run offline without a live MCP server.

**Acceptance Criteria:**
W2.3.6.1 — No `SpecificationGenerationService`, `SpecificationReviewService`, or `SpecificationApprovalService` imports `mcp.*` directly; all MCP access is through `MCPClientAdapter`.
W2.3.6.2 — The compatibility test suite mocks the MCP subprocess and verifies the adapter contract without a live server.
W2.3.6.3 — `MCPClientAdapter` documents in its module docstring which `mcp` SDK version it was authored against.

---

## Area W2.4 — Specification Generation

**Scope note (maps to tasks W2.T4, W2.T6):** Generating structured `requirements.md`, `design.md`, and `tasks.md` artifacts from a user-authored feature description using the AI provider.

### REQ-W2.4.1
WHEN a specification generation is triggered,
THEN `SpecificationGenerationService` MUST produce three artifacts: `requirements.md` (requirements in EARS or numbered REQ-W2.x.y style, each with acceptance criteria), `design.md` (architecture, data models, APIs, failure modes, security, concurrency, integration boundaries), `tasks.md` (implementation tasks with dependencies and completion criteria). Each artifact MUST follow the existing project specification conventions (header, version, status, scope, branch, last-updated metadata block matching the format of Wave 1 specs).

**Acceptance Criteria:**
W2.4.1.1 — Generated `requirements.md` contains a metadata block with `Version`, `Status`, `Scope`, `Branch`, `Last Updated` fields.
W2.4.1.2 — Generated `design.md` contains sections for: Architecture Overview, Component Specifications, Data Models, API Contracts, Failure Modes, Security Architecture, Concurrency Model, Integration Boundaries.
W2.4.1.3 — Generated `tasks.md` contains numbered tasks each with: Description, Dependencies, Acceptance Criteria, Size Estimate.
W2.4.1.4 — Each requirement in `requirements.md` has at least one acceptance criterion.

### REQ-W2.4.2
WHEN generated requirements are evaluated,
THEN each requirement MUST be testable (a test can be written to confirm or refute it) and traceable (linked to a business goal or functional requirement from the input). The generation service MUST include a traceability table in `requirements.md` mapping each REQ to its source input field.

**Acceptance Criteria:**
W2.4.2.1 — Generated `requirements.md` contains a traceability table with columns `Requirement ID`, `Source Input Field`, `Business Goal`.
W2.4.2.2 — A structural validation step (deterministic, not AI) confirms every requirement has at least one acceptance criterion before the artifact is marked `Generated`.
W2.4.2.3 — Requirements with no source traceability are flagged as `Informational` review findings (REQ-W2.5.4).

### REQ-W2.4.3
WHEN generated design artifacts are evaluated,
THEN `design.md` MUST address: data models (entity names, fields, relationships), API contracts (route, method, request/response schema, error codes), failure modes (at least three named failure scenarios per major component), security considerations (authentication, authorization, data protection, injection defense), and concurrency model (async, synchronous, or hybrid with rationale). Missing sections trigger a `High` review finding (REQ-W2.5.4).

**Acceptance Criteria:**
W2.4.3.1 — Structural validation confirms the presence of all required sections before marking the artifact `Generated`.
W2.4.3.2 — A generated `design.md` missing the Failure Modes section is marked as requiring a `High` finding.
W2.4.3.3 — The design addresses security and concurrency; absence of either generates a `Critical` review finding.

### REQ-W2.4.4
WHEN generated tasks are evaluated,
THEN each task in `tasks.md` MUST have: a unique task ID, description, explicit dependencies (by task ID), numbered acceptance criteria, and a size estimate (S/M/L). Tasks that depend on undefined task IDs trigger a `High` review finding.

**Acceptance Criteria:**
W2.4.4.1 — Structural validation confirms each task has an ID, description, dependencies list, acceptance criteria, and size.
W2.4.4.2 — A task referencing an undefined dependency ID generates a `High` review finding.
W2.4.4.3 — All tasks trace to at least one requirement in `requirements.md`; orphan tasks generate a `Medium` review finding.

### REQ-W2.4.5
WHEN a generation attempt is recorded,
THEN the system MUST persist a `GenerationAttempt` with: `id`, `specification_request_id` (FK), `provider_id`, `model_id`, `prompt_hash` (SHA-256 of the prompt sent, not the prompt text), `status` (`pending`/`running`/`succeeded`/`failed`/`cancelled`), `started_at`, `completed_at`, `token_usage_json` (from `TokenUsage` or null), `error_code`, `error_message`. The prompt text MUST NOT be persisted; only the hash is stored.

**Acceptance Criteria:**
W2.4.5.1 — `GenerationAttempt` row is created before the AI call; `status` starts as `"pending"` then `"running"`.
W2.4.5.2 — On success, `status = "succeeded"`, `completed_at` set, `token_usage_json` populated if available.
W2.4.5.3 — On failure, `status = "failed"`, `error_code` and `error_message` set.
W2.4.5.4 — Prompt text is NEVER stored in any database column or log; only `prompt_hash` is persisted.

### REQ-W2.4.6
WHEN generated output is received from the provider,
THEN the system MUST validate it against an output schema before accepting it as a `SpecificationArtifact`. Malformed output (not parseable to the expected structure) MUST set `GenerationAttempt.status = "failed"` with `code = "MALFORMED_OUTPUT"` and NOT create a `SpecificationArtifact`. The user MUST be informed that generation failed and may retry.

**Acceptance Criteria:**
W2.4.6.1 — A mocked provider returning malformed JSON triggers `MALFORMED_OUTPUT` and no artifact is created.
W2.4.6.2 — HTTP 422 is returned to the client when output schema validation fails.
W2.4.6.3 — The UI presents a "Generation failed — retry?" option when `GenerationAttempt.status = "failed"`.

### REQ-W2.4.7
WHEN context size limits are approached,
THEN the system MUST enforce: maximum prompt size `Settings.AI_MAX_PROMPT_TOKENS` (default 8000 tokens estimated by character count ÷ 4); maximum output size `Settings.AI_MAX_OUTPUT_TOKENS` (default 4000 tokens). Requests exceeding the prompt limit MUST truncate the `repo_context` field first (with a logged warning), then `clarifying_questions`, then other optional fields. Truncation MUST be logged in the `GenerationAttempt` audit fields.

**Acceptance Criteria:**
W2.4.7.1 — A request with `repo_context` exceeding the token budget is truncated; `GenerationAttempt` records `context_truncated = true`.
W2.4.7.2 — `Settings.AI_MAX_PROMPT_TOKENS` and `Settings.AI_MAX_OUTPUT_TOKENS` are declared with documented defaults.
W2.4.7.3 — Truncation never removes `title`, `description`, or `functional_requirements` (required fields take precedence).

---

## Area W2.5 — AI Specification Review

**Scope note (maps to task W2.T5):** An AI-driven review pass that evaluates generated artifacts and classifies findings by severity.

### REQ-W2.5.1
WHEN a specification review is triggered,
THEN `SpecificationReviewService` MUST evaluate the three generated artifacts (`requirements.md`, `design.md`, `tasks.md`) for: completeness, requirements/design/tasks internal consistency, testability of requirements, security and privacy considerations, architecture compatibility with the existing Phase 0/1/Wave 1 codebase, missing edge cases, unclear assumptions, dependency feasibility, and scope creep.

**Acceptance Criteria:**
W2.5.1.1 — Each review dimension listed above has a named check in the review service.
W2.5.1.2 — A `ReviewAttempt` is created before the AI review call; it records `provider_id`, `model_id`, `artifact_hash` (SHA-256 of the concatenated artifact content), `status`.
W2.5.1.3 — Review is triggered by a separate API call (`POST /api/v1/specification-requests/{id}/review`), not automatically after generation.

### REQ-W2.5.2
WHEN review findings are classified,
THEN each `ReviewFinding` MUST have: `severity` (one of `Critical`, `High`, `Medium`, `Low`, `Informational`), `dimension` (one of the review dimensions from REQ-W2.5.1), `finding_text`, `location` (which artifact and section), `recommendation`, `source` (`"deterministic"` or `"ai"`). Deterministic findings (structural rule violations) MUST be computed without an AI call.

**Acceptance Criteria:**
W2.5.2.1 — `ReviewFinding` is a Pydantic v2 model with all named fields typed.
W2.5.2.2 — Deterministic findings (missing section, missing acceptance criteria, broken dependency reference) are computed before the AI call and do not require a provider.
W2.5.2.3 — AI findings carry `source = "ai"` and include a disclaimer that they are recommendations, not guaranteed facts.

### REQ-W2.5.3
WHEN deterministic validation runs,
THEN the system MUST check without AI assistance: (a) all required metadata fields present in each artifact; (b) every requirement has at least one acceptance criterion; (c) every task has an ID, description, dependencies list, acceptance criteria, and size; (d) no task references an undefined task ID; (e) no broken cross-references between artifacts; (f) all three artifact files are present and non-empty.

**Acceptance Criteria:**
W2.5.3.1 — Deterministic checks are implemented as pure functions that accept artifact text and return `list[ReviewFinding]`.
W2.5.3.2 — Tests run all deterministic checks with known-bad inputs and confirm correct findings are generated.
W2.5.3.3 — Deterministic checks do not make network calls or read from the database.

### REQ-W2.5.4
WHEN AI review findings are generated,
THEN they MUST be presented to the user as recommendations requiring human judgment. The UI MUST display a disclaimer: "AI review findings are suggestions generated by a language model. They may be incomplete, incorrect, or inconsistent. Human review is required before approval." AI findings MUST NOT block advancement automatically; only Critical findings MUST require explicit user acknowledgment before the approval gate proceeds.

**Acceptance Criteria:**
W2.5.4.1 — The disclaimer text is rendered in the Streamlit review findings page above the findings list.
W2.5.4.2 — Advancement to the approval gate is blocked only if one or more `Critical` findings exist and the user has not explicitly acknowledged them.
W2.5.4.3 — Acknowledgment of a `Critical` finding is recorded as an audit event `critical_finding_acknowledged` with `finding_id`, `actor_id`, `acknowledged_at`.

### REQ-W2.5.5
WHEN a review attempt is recorded,
THEN the system MUST persist a `ReviewAttempt` with: `id`, `specification_version_id` (FK), `provider_id`, `model_id`, `artifact_hash`, `status`, `started_at`, `completed_at`, `finding_count_by_severity` (JSON map), `error_code`. The artifact text sent to the AI MUST NOT be persisted; only the `artifact_hash` is stored.

**Acceptance Criteria:**
W2.5.5.1 — `ReviewAttempt` row is created before the AI call.
W2.5.5.2 — `artifact_hash` matches `sha256(requirements_text + design_text + tasks_text)` (concatenated in fixed order).
W2.5.5.3 — Artifact text is NEVER stored in any database column; only the hash is persisted.

---

## Area W2.6 — Revision Lifecycle

**Scope note (maps to tasks W2.T6, W2.T7):** The state machine governing the lifecycle of a specification from draft through approval.

### REQ-W2.6.1
WHEN a specification lifecycle is tracked,
THEN it MUST follow this state machine:

```
Draft → Generated → Under Review → Revision Required
                                 → Ready for Approval → Approved
```

Legal transitions:
- `Draft → Generated`: generation succeeds and all three artifacts are validated.
- `Generated → Under Review`: review is triggered by the user.
- `Under Review → Revision Required`: one or more `Critical` or `High` findings exist after review completes; or the user manually requests revision.
- `Under Review → Ready for Approval`: review completes with no `Critical` findings and no unacknowledged `High` findings.
- `Revision Required → Draft`: the user edits and resubmits the request; version increments.
- `Ready for Approval → Approved`: explicit human approval (REQ-W2.7).
- `Ready for Approval → Revision Required`: the user rejects before approving.
- Any state → `Cancelled`: user cancels; a cancellation is terminal.

**Acceptance Criteria:**
W2.6.1.1 — Each transition is enforced by `SpecificationVersionRepository.transition_status` with a CAS guard; invalid transitions return `INVALID_SPEC_TRANSITION`.
W2.6.1.2 — `Cancelled` is terminal; no transition out of `Cancelled` is permitted.
W2.6.1.3 — `Approved` is terminal; re-generation requires creating a new `SpecificationRequest` version (REQ-W2.2.3).

### REQ-W2.6.2
WHEN a new version of a specification is created,
THEN the prior version MUST be preserved as an immutable historical record. Each `SpecificationVersion` MUST carry a `content_digest` (SHA-256 of all three artifact texts concatenated in canonical order) computed at the time it enters `Generated` state. The digest MUST be recomputed and verified before the `Approved` transition; if the digest does not match, the transition MUST be rejected with `SPEC_DIGEST_MISMATCH`.

**Acceptance Criteria:**
W2.6.2.1 — `SpecificationVersion.content_digest` is set when status transitions to `Generated`.
W2.6.2.2 — Modifying an artifact after `Generated` without creating a new version causes `SPEC_DIGEST_MISMATCH` on the approval attempt.
W2.6.2.3 — Prior versions are readable via `GET /api/v1/specification-requests/{id}/versions`; they are never deleted.

### REQ-W2.6.3
WHEN a revision is required,
THEN the system MUST preserve the full review history (all `ReviewAttempt` rows and their `ReviewFinding` rows) for the version being revised. The new draft (incremented version) starts with `status = "Draft"` and no review artifacts; the prior version's review remains linked to the prior version and is readable.

**Acceptance Criteria:**
W2.6.3.1 — After revision, `GET /api/v1/specification-requests/{id}/versions/{prior_version}/review` still returns the prior review findings.
W2.6.3.2 — The new draft version has no review findings until a new review is triggered.
W2.6.3.3 — The audit log records `spec_revision_created` with `prior_version`, `new_version`, `actor_id`.

### REQ-W2.6.4
WHEN an approved specification exists,
THEN no AI-generated revision or automated process MAY silently replace it. Any attempt to transition an `Approved` specification to any non-terminal state MUST return HTTP 409 `SPEC_APPROVED_NO_OVERWRITE`. A new specification version requires explicit user initiation (new `SpecificationRequest` submission) with the prior approval linked by reference.

**Acceptance Criteria:**
W2.6.4.1 — `POST /api/v1/specification-requests/{id}/generate` on an `Approved` specification returns HTTP 409 `SPEC_APPROVED_NO_OVERWRITE`.
W2.6.4.2 — An automated sweep or background task MUST NOT transition an `Approved` specification.
W2.6.4.3 — Creating a new version after approval preserves the approved version and links to it via `supersedes_version_id`.

---

## Area W2.7 — Human Approval

**Scope note (maps to task W2.T7):** Integration with the Wave 1 approval framework for the specification approval gate.

### REQ-W2.7.1
WHEN a specification reaches `Ready for Approval`,
THEN the system MUST create an `ApprovalRequest` using the Wave 1 `ApprovalService.request_bound_approval` path. The approval MUST bind to: `operation = "approve_specification"`, `parameters_hash` (SHA-256 of `specification_version_id + content_digest`), `actor_id = Settings.LOCAL_OPERATOR_ID`, `workflow_step_run_id` (if the spec request is linked to a Wave 1 workflow step), `expires_at = now + Settings.APPROVAL_TTL_SECONDS`.

**Acceptance Criteria:**
W2.7.1.1 — The `ApprovalRequest` row carries `operation = "approve_specification"` and a correct `parameters_hash`.
W2.7.1.2 — The approval expires after `APPROVAL_TTL_SECONDS` seconds; resolution after expiry returns HTTP 409 `APPROVAL_EXPIRED`.
W2.7.1.3 — `SpecificationApprovalService` calls `ApprovalService.request_bound_approval`; it does NOT create `ApprovalRequest` rows directly.

### REQ-W2.7.2
WHEN a specification approval is resolved,
THEN `SpecificationApprovalService.resolve(approval_id, decision, resolved_by)` MUST delegate to `ApprovalService.resolve` (Wave 1) for all approval validity, TTL, and status checks. Wave 2 MUST NOT duplicate or shadow the Wave 1 approval resolution logic. After a successful `approved` resolution, `SpecificationApprovalService` MUST transition the specification to `Approved` and persist `approved_at`, `approved_by`, `approval_id`.

**Acceptance Criteria:**
W2.7.2.1 — All `APPROVAL_EXPIRED`, `APPROVAL_ALREADY_RESOLVED` error codes originate from Wave 1 `ApprovalService`; Wave 2 does not re-implement these checks.
W2.7.2.2 — `SpecificationVersion.status` transitions to `Approved` only after `ApprovalService.resolve` returns a successful `approved` decision.
W2.7.2.3 — `approved_at` is set to `datetime.now(UTC)` on the `SpecificationVersion` row; `approval_id` FK is set.

### REQ-W2.7.3
WHEN an approval is single-use,
THEN each `ApprovalRequest` for a specification MUST be consumed at most once. Wave 2 inherits the Wave 1 `consumed_at` mechanism: the approval is consumed atomically (CAS `UPDATE … WHERE consumed_at IS NULL`) when the `Approved` transition is executed. A second attempt to use the same approval returns HTTP 409 `APPROVAL_ALREADY_RESOLVED`.

**Acceptance Criteria:**
W2.7.3.1 — Concurrent resolution of the same approval: exactly one succeeds; the other returns HTTP 409.
W2.7.3.2 — `ApprovalRequest.consumed_at` is set atomically in the same transaction as the `Approved` status transition.
W2.7.3.3 — No code path clears `consumed_at` after it is set.

### REQ-W2.7.4
WHEN a specification is rejected,
THEN `SpecificationApprovalService` MUST transition the specification to `Revision Required` and record the rejection reason in the audit log as `spec_approval_rejected` with `approval_id`, `actor_id`, `reason`, `rejected_at`.

**Acceptance Criteria:**
W2.7.4.1 — Rejection transitions `Ready for Approval → Revision Required`.
W2.7.4.2 — `spec_approval_rejected` audit entry is written with all named fields.
W2.7.4.3 — The rejection reason is visible in the Streamlit audit timeline.

### REQ-W2.7.5
WHEN implementation is requested,
THEN the system MUST require an `Approved` specification version for the relevant `SpecificationRequest` before authorizing any downstream Wave 3 implementation task. The approval authorization MUST be checked by `SpecificationApprovalService.is_implementation_authorized(specification_request_id)` which verifies: a `SpecificationVersion` with `status = "Approved"` exists, its `content_digest` matches the current artifact content, and the approval has not been revoked.

**Acceptance Criteria:**
W2.7.5.1 — `is_implementation_authorized` returns `False` if no approved version exists for the request.
W2.7.5.2 — `is_implementation_authorized` returns `False` if the approved version's `content_digest` does not match the current artifact content.
W2.7.5.3 — No Wave 3 executor invocation path bypasses this check.

### REQ-W2.7.6
WHEN audit evidence is required,
THEN every approval gate event MUST be recorded in `WorkflowAuditLog` (reusing Wave 1 audit columns) with: `event_type`, `workflow_run_id` (nullable), `workflow_step_run_id` (nullable), `actor_id`, `specification_version_id` (new FK or denormalized ID), `approval_id`, `parameters_hash`, `timestamp`. The audit log MUST be append-only; no event is ever deleted or updated.

**Acceptance Criteria:**
W2.7.6.1 — `spec_approval_requested`, `spec_approved`, `spec_approval_rejected`, `spec_approval_expired` audit events are written for every corresponding state change.
W2.7.6.2 — `GET /api/v1/specification-requests/{id}/audit` returns all audit events for the specification in chronological order.
W2.7.6.3 — No DELETE or UPDATE SQL is executed on `workflow_audit_log` rows in any Wave 2 code path.

---

## Area W2.8 — API and Streamlit UI

**Scope note (maps to tasks W2.T9, W2.T10):** Minimal user-facing API and UI for the full Wave 2 specification workflow.

### REQ-W2.8.1
WHEN the Wave 2 API is designed,
THEN the following FastAPI routes MUST be implemented:

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/specification-requests` | Create a spec request (Draft) |
| `GET` | `/api/v1/specification-requests/{id}` | Get spec request with current version |
| `PATCH` | `/api/v1/specification-requests/{id}` | Update draft fields |
| `DELETE` | `/api/v1/specification-requests/{id}` | Cancel (soft delete, status = Cancelled) |
| `POST` | `/api/v1/specification-requests/{id}/generate` | Trigger generation |
| `GET` | `/api/v1/specification-requests/{id}/status` | Poll generation/review status |
| `POST` | `/api/v1/specification-requests/{id}/review` | Trigger AI review |
| `GET` | `/api/v1/specification-requests/{id}/review/findings` | Get review findings |
| `POST` | `/api/v1/specification-requests/{id}/approve` | Submit approval decision |
| `POST` | `/api/v1/specification-requests/{id}/findings/{finding_id}/acknowledge` | Acknowledge Critical finding |
| `GET` | `/api/v1/specification-requests/{id}/versions` | List version history |
| `GET` | `/api/v1/specification-requests/{id}/audit` | Get audit events |

**Acceptance Criteria:**
W2.8.1.1 — All routes return documented HTTP status codes; error responses carry `code` and `message` fields.
W2.8.1.2 — OpenAPI schema is generated for all routes; all request/response models are Pydantic v2.
W2.8.1.3 — `mypy --strict` passes for all route handlers.

### REQ-W2.8.2
WHEN asynchronous generation or review is in progress,
THEN the system MUST handle provider calls that exceed HTTP request timeouts using a background-task pattern. The trigger endpoints (`/generate`, `/review`) MUST return HTTP 202 Accepted with a `task_id`; the client polls `/status` to check progress. The background task MUST update `GenerationAttempt.status` or `ReviewAttempt.status` atomically; the status endpoint returns the current status without blocking.

**Acceptance Criteria:**
W2.8.2.1 — `POST /generate` returns HTTP 202 with `{"task_id": "...", "status": "pending"}`.
W2.8.2.2 — `GET /status` returns `{"status": "running" | "succeeded" | "failed" | "cancelled"}` without blocking.
W2.8.2.3 — Cancelling a pending or running task (via DELETE or a cancel endpoint) sets status to `cancelled` and does not leave orphaned background tasks.

### REQ-W2.8.3
WHEN API error states are defined,
THEN the API MUST return documented error codes for all named failure states:

| Error Code | HTTP Status | Trigger |
|---|---|---|
| `INVALID_SPECIFICATION_REQUEST` | 422 | Missing required fields |
| `PROVIDER_UNAVAILABLE` | 503 | AI provider not reachable |
| `PROVIDER_TIMEOUT` | 504 | AI request timed out |
| `PROVIDER_NOT_CONFIGURED` | 400 | OpenAI selected but not configured |
| `PROVIDER_CANCELLED` | 499 | Request cancelled by client |
| `MALFORMED_OUTPUT` | 422 | AI output failed schema validation |
| `MCP_CONTEXT_FAILURE` | 502 | Critical MCP context retrieval failed |
| `SPEC_APPROVED_NO_OVERWRITE` | 409 | Attempt to modify approved spec |
| `SPEC_DIGEST_MISMATCH` | 409 | Digest changed since Generated state |
| `INVALID_SPEC_TRANSITION` | 409 | Illegal lifecycle state transition |
| `APPROVAL_EXPIRED` | 409 | Approval TTL elapsed (from Wave 1) |
| `APPROVAL_ALREADY_RESOLVED` | 409 | Approval already resolved (from Wave 1) |

**Acceptance Criteria:**
W2.8.3.1 — Each error code maps to exactly one HTTP status code.
W2.8.3.2 — Error responses are Pydantic models with `code: str` and `message: str` fields.
W2.8.3.3 — Tests confirm each error code is returned in the documented scenario.

### REQ-W2.8.4
WHEN the Streamlit UI is designed,
THEN four pages MUST be implemented: (1) **Spec Request Form** — fields for all `SpecificationRequest` inputs, provider/model selection, submit button; (2) **Generation Status** — polling display of generation status, cancel button, generated artifact preview; (3) **Review Findings** — findings list with severity badges, disclaimer text, acknowledge button for Critical findings, trigger-review button; (4) **Approval** — version history, approve/reject buttons, audit timeline. Each page MUST handle and display: provider-unavailable, timeout, cancellation, validation failure, and incomplete-output states.

**Acceptance Criteria:**
W2.8.4.1 — Each named UI state renders a user-visible message; no blank or spinner-only state for error conditions.
W2.8.4.2 — The disclaimer from REQ-W2.5.4 appears on the Review Findings page above the findings list.
W2.8.4.3 — The Approval page shows `content_digest` (truncated to 12 hex chars) so the user can verify what they are approving.

### REQ-W2.8.5
WHEN the UI renders provider-unavailable state,
THEN it MUST display a message naming the provider and stating that it is unreachable, along with the error code `PROVIDER_UNAVAILABLE`. The message MUST NOT suggest OpenAI as a fallback if only Ollama is configured.

**Acceptance Criteria:**
W2.8.5.1 — Provider-unavailable UI state displays the provider name and error code.
W2.8.5.2 — No automatic fallback suggestion appears when only Ollama is configured.
W2.8.5.3 — The UI offers a "Retry" option that re-attempts with the same provider.

---

## Area W2.9 — Reliability and Security

**Scope note (maps to task W2.T11 security tests):** Cross-cutting reliability and security requirements applying to all Wave 2 components.

### REQ-W2.9.1
WHEN untrusted content (repo context, MCP tool output) is included in an AI prompt,
THEN the system MUST apply prompt-injection defense: all untrusted content MUST be enclosed in clearly delimited content boundaries in the prompt template; the instruction portion of the prompt MUST be a fixed template string not modifiable by user or MCP input; untrusted content fields MUST be sanitized to remove or escape prompt-injection payloads (control characters, instruction-mimicking strings). The system MUST NOT guarantee that sanitization is complete; defense-in-depth is applied but LLM output must still be validated independently.

**Acceptance Criteria:**
W2.9.1.1 — All prompt templates use fixed instruction strings with named placeholders for untrusted content.
W2.9.1.2 — A test injects a prompt-injection string into `repo_context` and verifies it does not appear in the instruction section of the constructed prompt.
W2.9.1.3 — The design documents that sanitization is a best-effort defense, not a guarantee.

### REQ-W2.9.2
WHEN secrets are handled,
THEN the system MUST redact all secret values from logs, audit entries, error messages, and API responses. `Settings` fields typed as `SecretStr` MUST NOT be converted to plain strings except at the point of use (e.g., HTTP Authorization header). No secret value MAY appear in `GenerationAttempt`, `ReviewAttempt`, or `AuditEvent` records.

**Acceptance Criteria:**
W2.9.2.1 — A test verifies that `str(Settings.OPENAI_API_KEY)` returns `"**********"` (Pydantic `SecretStr` behavior).
W2.9.2.2 — Log output during a generation attempt does not contain the literal API key value.
W2.9.2.3 — No `GenerationAttempt` or `ReviewAttempt` column stores a plain-text secret.

### REQ-W2.9.3
WHEN output schema validation is performed,
THEN the system MUST validate AI-generated specification artifacts against a defined output schema before accepting them. Schema validation is deterministic (not AI-assisted). A schema-valid artifact may still contain semantically incorrect content; validation is a structural check only. Schema validation failures MUST be reported as `MALFORMED_OUTPUT`.

**Acceptance Criteria:**
W2.9.3.1 — Output schema validators are pure functions; they make no AI calls.
W2.9.3.2 — A test with deliberately malformed output confirms `MALFORMED_OUTPUT` is raised.
W2.9.3.3 — The validation step is documented as structural-only; no claim is made that a valid output is semantically correct.

### REQ-W2.9.4
WHEN Ollama operates offline,
THEN the system MUST continue to serve previously generated and approved artifacts from the database. Generation and review operations requiring Ollama MUST fail with `PROVIDER_UNAVAILABLE` and NOT silently fall back to OpenAI. The system MUST remain operational for read-only operations (viewing existing specs, audit logs, version history) when Ollama is offline.

**Acceptance Criteria:**
W2.9.4.1 — With Ollama unavailable (mocked connection failure), `GET /specification-requests/{id}` returns HTTP 200 with the existing artifact.
W2.9.4.2 — `POST /specification-requests/{id}/generate` returns HTTP 503 `PROVIDER_UNAVAILABLE` with no OpenAI call when Ollama is unavailable and OpenAI is not configured.
W2.9.4.3 — The Streamlit UI remains navigable when Ollama is offline; only generation/review buttons are disabled.

### REQ-W2.9.5
WHEN no unintended OpenAI egress is permitted,
THEN the system MUST ensure that no HTTP call is made to any `openai.com` or `api.openai.com` endpoint unless `Settings.AI_PROVIDER = "openai"` AND `Settings.OPENAI_API_KEY` is non-empty. A test with `AI_PROVIDER = "ollama"` and a mocked network layer MUST verify zero calls to OpenAI endpoints.

**Acceptance Criteria:**
W2.9.5.1 — A test with Ollama as provider and an HTTP intercept confirms no request to `api.openai.com` is made.
W2.9.5.2 — `OpenAIProvider.__init__` raises `ProviderConfigurationError` if `OPENAI_API_KEY` is empty.
W2.9.5.3 — `ProviderFactory.create()` with `AI_PROVIDER = "ollama"` never instantiates `OpenAIProvider`.

### REQ-W2.9.6
WHEN generated code or commands appear in specification artifacts,
THEN the system MUST NOT execute them. No `subprocess`, `os.system`, `exec`, `eval`, or shell-equivalent call MAY be made on content from AI-generated artifacts. Wave 2 ships no executor that runs generated content. This constraint is enforced by a mandatory AST/import guard test (analogous to Wave 1 REQ-E5.4).

**Acceptance Criteria:**
W2.9.6.1 — An AST-based test scans all Wave 2 service and adapter modules and asserts that `subprocess`, `os.system`, `exec`, and `eval` calls are absent.
W2.9.6.2 — `SpecificationGenerationService` and `SpecificationReviewService` have no code paths that interpret or run artifact content.
W2.9.6.3 — The design documents that Wave 2 produces specification artifacts only; execution is out of scope (Wave 3 and later).

### REQ-W2.9.7
WHEN timeouts and retry budgets are enforced,
THEN every AI provider call MUST be subject to `Settings.AI_REQUEST_TIMEOUT_SECONDS`; every MCP tool call MUST be subject to `MCPServerConfig.timeout_seconds`; total retry budget for AI calls MUST NOT exceed `Settings.AI_RETRY_BUDGET_SECONDS`. These limits MUST be enforced in code, not documentation only. Exceeding any limit MUST result in a named error code (`PROVIDER_TIMEOUT` or `MCPTimeoutError`).

**Acceptance Criteria:**
W2.9.7.1 — A mocked provider that hangs is cancelled after `AI_REQUEST_TIMEOUT_SECONDS` seconds and returns `PROVIDER_TIMEOUT`.
W2.9.7.2 — Total retry duration does not exceed `AI_RETRY_BUDGET_SECONDS` in any test.
W2.9.7.3 — MCP timeouts are enforced by `asyncio.timeout(config.timeout_seconds)` (already present in `mcp_client.py`).

### REQ-W2.9.8
WHEN audit and error handling are designed,
THEN every Wave 2 state transition and external call MUST produce an audit event in `WorkflowAuditLog`. Audit events MUST be append-only. Every unhandled exception from a provider or MCP call MUST be caught at the service boundary, converted to a named `ProviderError` or `MCPError`, and produce an `error_recorded` audit event before being surfaced to the caller. No internal stack trace MAY appear in API responses.

**Acceptance Criteria:**
W2.9.8.1 — An unhandled `httpx.ReadTimeout` from Ollama is caught, converted to `ProviderTimeoutError`, and surfaces as HTTP 504 `PROVIDER_TIMEOUT` with no stack trace in the response body.
W2.9.8.2 — Every state transition (`spec_draft_created`, `spec_generated`, `spec_under_review`, etc.) produces an audit entry.
W2.9.8.3 — No `traceback.format_exc()` or raw exception string appears in an HTTP response body in any Wave 2 handler.

### REQ-W2.9.9
WHEN deterministic recovery is required,
THEN a `GenerationAttempt` or `ReviewAttempt` left in `running` state after a process restart MUST be recovered to `failed` with `error_code = "INTERRUPTED"` on next startup. Recovery MUST be idempotent and MUST NOT auto-retry; the user MUST explicitly re-trigger generation or review after a recovery event.

**Acceptance Criteria:**
W2.9.9.1 — On startup, the system scans for `GenerationAttempt` or `ReviewAttempt` rows with `status = "running"` and transitions them to `failed` with `error_code = "INTERRUPTED"`.
W2.9.9.2 — Recovery is idempotent; running it twice produces the same result.
W2.9.9.3 — Recovery does not auto-trigger a new generation or review; the user must explicitly do so.

---

## Cross-Reference: Wave 1 Requirements Reused

| Wave 2 Requirement | Wave 1 Requirement Reused |
|---|---|
| REQ-W2.7.1 — approval binding | REQ-E3.1 — `ApprovalRequest` binding columns |
| REQ-W2.7.2 — resolve delegation | REQ-E2.5 — `ApprovalService.resolve` |
| REQ-W2.7.3 — single-use consumption | REQ-E3.3, E3.7 — `consume_atomic`, pre-execution consumption |
| REQ-W2.7.4 — rejection handling | REQ-E2.6 — failure-stop / cancellation settle |
| REQ-W2.7.6 — audit log reuse | REQ-E8.3 — `WorkflowAuditLog` append-only |
| REQ-W2.9.4 — offline behavior | REQ-E6.x — honest isolation boundary |
| REQ-W2.9.6 — no code execution | REQ-E5.4 — mandatory executor security guards |
| REQ-W2.9.7 — timeout budgets | REQ-E4.6 — lease TTL / step timeout |

---

## Requirements Count Summary

| Area | Requirements |
|---|---|
| W2.1 — AI Provider Abstraction | 8 (REQ-W2.1.1 – W2.1.8) |
| W2.2 — Feature Requirement Input | 4 (REQ-W2.2.1 – W2.2.4) |
| W2.3 — MCP Context Integration | 6 (REQ-W2.3.1 – W2.3.6) |
| W2.4 — Specification Generation | 7 (REQ-W2.4.1 – W2.4.7) |
| W2.5 — AI Specification Review | 5 (REQ-W2.5.1 – W2.5.5) |
| W2.6 — Revision Lifecycle | 4 (REQ-W2.6.1 – W2.6.4) |
| W2.7 — Human Approval | 6 (REQ-W2.7.1 – W2.7.6) |
| W2.8 — API and Streamlit UI | 5 (REQ-W2.8.1 – W2.8.5) |
| W2.9 — Reliability and Security | 9 (REQ-W2.9.1 – W2.9.9) |
| **Total** | **54 requirements** |
