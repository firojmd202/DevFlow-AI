# DevFlow AI — Wave 2 HTTP contract clarification

This is the historical v1.6.0 proposal. The project owner approved the asynchronous contract and existing error envelope for v1.6.1. The current HTTP evidence includes required MCP failure through FastAPI. [Final compliance verification](phase2-wave2-final-compliance-verification.md)

**Approval status** Pending. The frozen v1.6.0 files remain unchanged.

## Conflict and proposed amendment

Design §§5 and 7 define asynchronous generation and review. Submission returns 202 and a poll URL, and status retrieval returns 200 with the attempt state and, when present, a stored error code. REQ-W2.8.3 assigns HTTP 503, 504, 422 and 502 to provider unavailability, provider timeout, malformed output and required MCP failure. Those conditions are discovered in background work after the submission response. REQ-W2.8.3 also assigns 409 to explicit cancellation, while the design returns 200 for acceptance and distinguishes acceptance from terminal cancellation.

Amend REQ-W2.8.3 and its acceptance bullets to apply synchronous HTTP mappings to errors discovered before accepting a request. Preserve 202 for accepted submission and 200 for successful status retrieval. Assert terminal `failed` with the exact applicable domain code in the poll body. Cancellation acceptance returns 200 with `status=cancellation_requested`. When the worker settles cancellation, status retrieval returns 200 with `status=cancelled` and `error_code=PROVIDER_CANCELLED`. A cancellation request for an absent or terminal current attempt returns 409 with `code=TASK_NOT_CANCELLABLE`. Preserve typed, sanitized errors. No provider or MCP probe is added to the synchronous request path.

Clarify REQ-W2.8.3.2 separately. The shared API model currently serializes the public text as `error` and the machine identifier as `code`, while the frozen requirement names `message` and `code`. Retain the existing wire field for compatibility and document its text semantics, or explicitly approve a migration for clients. A terminal status payload uses `error_code` and an optional `error_message`. W2.T11.9 should assert the contract at the stage where each error occurs.

## Endpoint mapping

Paths below are relative to `/api/v1/specification-requests`. Request validation can return 422 `INVALID_SPECIFICATION_REQUEST` at any endpoint with invalid path, query or body input. A missing specification resource or foreign artifact returns 404 `SPEC_NOT_FOUND`. The table lists additional domain outcomes.

| Method and path | Success | Synchronous errors and background outcomes |
|---|---|---|
| GET /providers | 200 | Availability is returned as provider information. No OpenAI availability probe. |
| GET / | 200 | Invalid filters or pagination use request validation. |
| POST / | 201 | 400 `PROVIDER_NOT_CONFIGURED`; 409 `INVALID_SPEC_TRANSITION` for an invalid workflow or unapproved predecessor and `SPEC_DIGEST_MISMATCH` for a corrupt predecessor; 404 `SPEC_NOT_FOUND` for an unknown predecessor. |
| GET /{id} | 200 | Missing request uses the resource error. |
| PATCH /{id} | 200 | 409 `INVALID_SPEC_TRANSITION` for stale revision or invalid lifecycle, `SPEC_APPROVED_NO_OVERWRITE` for approved versions. |
| DELETE /{id} | 204 | 409 `SPEC_APPROVED_NO_OVERWRITE` or `INVALID_SPEC_TRANSITION` when cancellation of the specification is forbidden. |
| POST /{id}/generate | 202 | 400 `PROVIDER_NOT_CONFIGURED`, 409 `GENERATION_ALREADY_IN_PROGRESS`, `INVALID_SPEC_TRANSITION`, `SPEC_APPROVED_NO_OVERWRITE`. Worker failures are reported by status polling. |
| POST /{id}/review | 202 | 400 `PROVIDER_NOT_CONFIGURED`; 409 `REVIEW_ALREADY_IN_PROGRESS`, `INVALID_SPEC_TRANSITION`, `SPEC_APPROVED_NO_OVERWRITE` or `SPEC_DIGEST_MISMATCH` if stored artifacts fail pre-review verification. Worker failures are reported by status polling. |
| GET /{id}/status | 200 | Successful retrieval can report failed `PROVIDER_UNAVAILABLE`, `PROVIDER_TIMEOUT`, `MALFORMED_OUTPUT` or `MCP_CONTEXT_FAILURE` for generation, or `cancelled/PROVIDER_CANCELLED`. Review preserves its specific failure codes, including `AI_REVIEW_MALFORMED`. |
| DELETE /{id}/generate, DELETE /{id}/review | 200 | 409 `TASK_NOT_CANCELLABLE` for an absent or terminal attempt. |
| POST /{id}/revision | 200 | 409 `INVALID_SPEC_TRANSITION` when revision cannot begin from the current state or `SPEC_APPROVED_NO_OVERWRITE` for an approved specification. |
| GET /{id}/versions | 200 | Missing request uses the resource error. |
| GET /{id}/versions/{version_id}/artifacts/{artifact_type} | 200 | Missing or foreign version/artifact uses the resource error. |
| GET /{id}/review/findings | 200 | Missing or foreign version uses the resource error. |
| POST /{id}/findings/{finding_id}/acknowledge | 200 | 409 `INVALID_SPEC_TRANSITION` when the finding cannot be acknowledged in the current state. |
| POST /{id}/approval | 200 | 409 `APPROVAL_BINDING_MISMATCH`, `INVALID_SPEC_TRANSITION`, `SPEC_DIGEST_MISMATCH` or `SPEC_APPROVED_NO_OVERWRITE`. Workflow eligibility can also raise `OPERATION_NOT_PERMITTED`. |
| POST /{id}/approve | 200 | 409 `APPROVAL_EXPIRED`, `APPROVAL_ALREADY_RESOLVED`, `APPROVAL_BINDING_MISMATCH`, `SPEC_DIGEST_MISMATCH` or `INVALID_SPEC_TRANSITION`. |
| GET /{id}/audit | 200 | Missing request uses the resource error. |

The APIClient catches HTTP status errors and records the machine code from the response. It treats successful polls as data and the Streamlit views render the attempt state separately. A required MCP context failure is reachable through the generation service with authorized context inputs. The specification HTTP submission currently supplies no MCP context arguments. Where the caller supplies a stale binding digest, the approval route returns `APPROVAL_BINDING_MISMATCH`. A matching submitted digest with invalid stored artifacts returns `SPEC_DIGEST_MISMATCH` during verification.

## Acceptance evidence

- `test_generation_provider_failure_and_cancellation_api` verifies 202 submission, 200 failed polling for unavailable, timeout and malformed output, 400 provider configuration, 200 cancellation acceptance, and terminal cancellation with its exact code.
- `test_generation_failures_keep_draft_and_no_artifacts` verifies required MCP failure persists `MCP_CONTEXT_FAILURE`, keeps the request in draft, and emits no artifacts. `test_optional_context_failure_and_critical_failure` verifies the adapter failure contract.
- `test_full_specification_lifecycle`, `test_review_cancel_and_resource_checks`, `test_review_acknowledgment_expired_approval_and_revision_api` and the bound approval tests verify synchronous validation, duplicate-attempt, lifecycle and approval errors. The detailed matrix is in the [blocker resolution](phase2-wave2-final-blocker-resolution.md).

Approval is required for the narrow wording changes to REQ-W2.8.3, design §5 error documentation and W2.T11.9. Until then, the existing asynchronous HTTP behavior is the verified implementation and the literal conflicting checks remain pending.
