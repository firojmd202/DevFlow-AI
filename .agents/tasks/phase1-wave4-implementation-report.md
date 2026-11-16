# Phase 1 Wave 4 final verification Ã¢â‚¬â€ v1.5.7

**WAVE 4 IMPLEMENTATION COMPLETE Ã¢â‚¬â€ READY FOR REVIEW**

## Security correction

Migration `006_add_mcp_approvals` now creates `trg_workflow_runs_before_delete_expire_mcp_approvals`. On direct or cascaded workflow-run deletion, the trigger expires bound PENDING and APPROVED approvals before the existing `ON DELETE SET NULL` foreign key clears their binding. CONSUMED, REJECTED and EXPIRED rows retain their status. Originally unbound PENDING and APPROVED rows are unaffected. The deletion and its trigger changes roll back together. The migration downgrade drops the exact trigger with `IF EXISTS` before dropping the MCP approval table.

The new orphaned-PENDING regression verified that an atomic status update guarded by `status='PENDING'` affects zero rows after deletion and that `consume_atomic` also rejects the expired record. The MCP repository has no promotion method or route. The existing workflow-step resolution path targets the separate `approval_requests` table and already guards its update by the current pending status.

## Final Task status

| Task | Status | Evidence |
| --- | --- | --- |
| I1 | Complete | Typed adapter errors and safe error responses retained. |
| I2 | Complete | GitHub issue, branch, PR and check-run adapter regressions passed offline. |
| I3 | Complete | Ollama and Figma adapter, credential and timeout regressions passed offline. |
| I4 | Complete | SDK transport, explicit environment, cleanup, authorization, replay and concurrency tests passed. Migration 006 and all ten v1.5.7 deletion/binding tests passed. |
| I5 | Complete | App-scoped live registry and stub selection tests passed. |
| I6 | Complete | Configuration validation, integration mode reporting and OpenAPI consistency checks passed. |
| I7 | Complete | Streamlit and all 58 unique v1.5.7 named tests passed. This includes the approved rename and one additional named regression. |

## Validation

Python 3.12.10 from `.venv/wave3/Scripts/python.exe`. SQLite tests used disposable databases. The full suite used mocked HTTP and subprocess transports and the existing Windows asyncio loopback allowance.

| Gate | Exit | Result |
| --- | ---: | --- |
| `python -m ruff check .` | 0 | PASS |
| `python -m ruff format --check .` | 0 | PASS, 139 files |
| `python -m mypy --strict src tests alembic scripts/export_openapi.py` | 0 | PASS, 139 files |
| `python -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=xml:.venv/w57-coverage.xml` | 0 | PASS, 247 tests, 92.01% combined coverage |
| Branch threshold from coverage XML | 0 | PASS, 284 of 346 branches, 82.08% |
| `python -m pytest -m integration -v --no-cov` | 0 | PASS, 22 cases including migration 006 downgrade and re-upgrade |
| `python -m bandit -qr src` | 0 | PASS |
| `python -m pip check` | 0 | PASS |
| `python -m pip_audit -r requirements/requirements.lock --no-deps --format json` | 0 | PASS, no known vulnerabilities reported |
| `python -m detect_secrets scan <changed implementation paths>` | 0 | PASS, 39 files scanned, zero findings |
| `python -m build --no-isolation` | 0 | PASS, wheel and sdist built |
| `python -m uv lock --check --offline` and runtime lock export comparison | 0 | PASS, exported pins and markers match |
| Runtime OpenAPI snapshot and baseline compatibility comparison | 0 | PASS, prior paths and component schemas preserved except the approved integration mode field |
| `git diff --check` and `git diff --cached --check` | 0 each | PASS, line-ending notices only |

## Git and remaining verification

The active branch is `feature/phase1-wave4-integration-execution` at `8866eb58c99e551b3fdc3d21a54691d40512ddad`, the v1.5.7 specification commit. This pass changed only migration 006, `tests/unit/test_mcp_approval_repository.py`, and this report. Migrations 001Ã¢â‚¬â€œ005, approved documents, prior Wave 4 work and the index were preserved. No application database was created. No commit, push, PR, merge, branch switch, or Wave 5 work was performed.

No Wave 4 implementation blocker remains. Hosted GitHub Actions await the Git handoff. The local Docker Desktop Linux engine was unavailable, so the Docker-based TruffleHog job could not run locally. The local changed-file secret scan passed.

## Named v1.5.7 Task I7 results

- `test_allowlist_alone_insufficient_for_consequential_tool` Ã¢â‚¬â€ PASS
- `test_approval_bound_to_workflow_rejected_without_workflow_context` Ã¢â‚¬â€ PASS
- `test_approval_modified_between_validation_and_consumption` Ã¢â‚¬â€ PASS
- `test_approval_unbound_rejected_with_workflow_context` Ã¢â‚¬â€ PASS
- `test_approval_wrong_workflow_run_rejected` Ã¢â‚¬â€ PASS
- `test_begin_immediate_prevents_toctou` Ã¢â‚¬â€ PASS
- `test_busy_timeout_treated_as_authorization_failure` Ã¢â‚¬â€ PASS
- `test_cascaded_deletion_handles_mcp_approvals` Ã¢â‚¬â€ PASS
- `test_concurrent_consumption_only_one_succeeds` Ã¢â‚¬â€ PASS
- `test_concurrent_consumption_safe` Ã¢â‚¬â€ PASS
- `test_consequential_tool_denied_without_approval` Ã¢â‚¬â€ PASS
- `test_consumed_approval_cannot_be_reused` Ã¢â‚¬â€ PASS
- `test_direct_mcp_client_call_blocked_without_service_layer` Ã¢â‚¬â€ PASS
- `test_execution_failure_does_not_restore_approval` Ã¢â‚¬â€ PASS
- `test_execution_failure_does_not_restore_consumed_approval` Ã¢â‚¬â€ PASS
- `test_expired_approval_after_deletion_cannot_be_consumed` Ã¢â‚¬â€ PASS
- `test_expired_approval_rejected_at_invocation` Ã¢â‚¬â€ PASS
- `test_expired_at_consumption_time_rejected` Ã¢â‚¬â€ PASS
- `test_expired_mcp_approval_emits_approval_expired_event` Ã¢â‚¬â€ PASS
- `test_expired_mcp_approval_rejected` Ã¢â‚¬â€ PASS
- `test_figma_adapter_raises_missing_credential` Ã¢â‚¬â€ PASS
- `test_forged_approval_record_rejected` Ã¢â‚¬â€ PASS
- `test_github_adapter_creates_issue` Ã¢â‚¬â€ PASS
- `test_github_adapter_raises_missing_credential` Ã¢â‚¬â€ PASS
- `test_github_adapter_timeout_raises_integration_error` Ã¢â‚¬â€ PASS
- `test_github_token_not_in_log_records` Ã¢â‚¬â€ PASS
- `test_integrations_page_renders` Ã¢â‚¬â€ PASS
- `test_mcp_call_tool_returns_result` Ã¢â‚¬â€ PASS
- `test_mcp_client_uses_locked_sdk_version` Ã¢â‚¬â€ PASS
- `test_mcp_integration_runs_offline_with_mock_subprocess` Ã¢â‚¬â€ PASS
- `test_mcp_permission_denied_before_subprocess` Ã¢â‚¬â€ PASS
- `test_mcp_secret_values_not_in_log_records` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_cleanup_in_finally_block` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_does_not_inherit_parent_secrets` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_receives_explicit_env` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_terminated_on_timeout` Ã¢â‚¬â€ PASS
- `test_mismatched_arguments_hash_rejected` Ã¢â‚¬â€ PASS
- `test_mismatched_tool_name_rejected` Ã¢â‚¬â€ PASS
- `test_missing_approval_emits_approval_missing_event` Ã¢â‚¬â€ PASS
- `test_new_approval_required_for_retry_after_failure` Ã¢â‚¬â€ PASS
- `test_no_direct_mcp_client_bypass` Ã¢â‚¬â€ PASS
- `test_null_to_null_match_rejected_for_originally_bound_approval` Ã¢â‚¬â€ PASS
- `test_ollama_adapter_generate` Ã¢â‚¬â€ PASS
- `test_ollama_health_check_unavailable_when_not_running` Ã¢â‚¬â€ PASS
- `test_orphaned_pending_approval_cannot_be_promoted` Ã¢â‚¬â€ PASS
- `test_read_only_tool_no_approval_required` Ã¢â‚¬â€ PASS
- `test_read_only_tool_permitted_without_approval` Ã¢â‚¬â€ PASS
- `test_replay_after_consumption_rejected` Ã¢â‚¬â€ PASS
- `test_settings_page_renders` Ã¢â‚¬â€ PASS
- `test_timeout_recorded_as_indeterminate_in_audit` Ã¢â‚¬â€ PASS
- `test_trigger_rollback_restores_approval` Ã¢â‚¬â€ PASS
- `test_unknown_tool_denied_without_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_allowed_after_approval_consumed` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_expires_approved_mcp_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_expires_pending_mcp_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_preserves_consumed_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_preserves_rejected_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_id_from_arguments_not_trusted` Ã¢â‚¬â€ PASS

---

## Historical reports

# Phase 1 Wave 4 continuation Ã¢â‚¬â€ v1.5.6

## Verdict

**WAVE 4 BLOCKED Ã¢â‚¬â€ ACTION REQUIRED**

The v1.5.6 continuation implemented the live adapters, explicit-environment MCP transport, approval gateway, migration 006, integration registry, settings/API changes and Streamlit pages. The additional PENDING approval invariant remains blocked by the v1.5.6 retention contract. The original report is preserved below as historical context.

## Preflight and Git

- Repository `J:\Android\GenAI\DevFlow-AI`, branch `feature/phase1-wave4-integration-execution`, HEAD `756100d1166c64b001da4a044ad22513197ab408`.
- Preserved the existing Kiro v1.5.6 edits, roadmap, source work, and untracked reports. Reviewed both Wave 4 specification-resolution reports.
- Migration files 001Ã¢â‚¬â€œ005, existing provider stub contracts, and CI thresholds are unchanged. The CI dependency-install commands now consume the runtime lock. No Git index or publication changes were made.

## Task traceability

| Task | Requirements | Implementation and validation |
| --- | --- | --- |
| I1 | REQ-I1.5, REQ-M1.4Ã¢â‚¬â€œM1.5 | Adapter errors carry internal context and safe public messages. Existing middleware mappings remain in use. |
| I2 | REQ-I1.1, Design Ã‚Â§8.1, REQ-S1.2Ã¢â‚¬â€œS1.3 | GitHub adapter implements issue, branch, pull-request and check-run methods with typed results and 10-second HTTPX timeouts. Offline tests cover auth, structured responses and safe failures. Only read/reporting integrations are wired to the API. |
| I3 | REQ-I1.2Ã¢â‚¬â€œI1.3 | Ollama and Figma retain Phase 0 protocols and live result flags. HTTP mocks verify URLs, timeouts, tokens and unavailable health behavior. |
| I4 | REQ-M1.1Ã¢â‚¬â€œM1.8, REQ-M2.1Ã¢â‚¬â€œM2.5, Design Ã‚Â§Ã‚Â§3.7a, 7.2, 7.5 | Explicit Windows/POSIX environment allow-lists, SecretStr-only interpolation, SDK 1.30.0 ClientSession JSON-RPC pipes, and terminate/five-second grace/kill are exercised offline. Direct client and legacy adapter invocation are denied. Service snapshots JSON arguments and verifies every binding again under SQLite BEGIN IMMEDIATE. Consumption commits before launch and remains committed after tool/audit failure. Migration 006 covers trigger order, rollback and cascades. The additional PENDING invariant is blocked below. |
| I5 | REQ-I1.4, REQ-M1.6 | App-scoped registry supports live selection for registered adapters and stub fallback, without mutating the Phase 0 registry or adding tool endpoints. |
| I6 | REQ-I1.6, REQ-M1.1, REQ-S1.2 | Integration discovery exposes mode; health dispatch uses the selected adapter. Settings reject malformed MCP configs and duplicate server names without exposing raw config in the error message. |
| I7 | REQ-U1.5, REQ-T1.1Ã¢â‚¬â€œT1.2 | Existing pages 9 and 10 report mode, health and configuration state. AppTest covers navigation and unavailable/empty/live states. Task I7 names are audited below. |

## Remaining security decision Ã¢â‚¬â€ orphaned PENDING approval

The approved trigger expires only APPROVED rows. A PENDING approval bound to a deleted run remains PENDING and its foreign key becomes NULL. The migration test confirms that a later SQL status update can promote this row just as it can promote an originally unbound PENDING approval. The two rows carry the same authorization state and the existing columns provide no basis to distinguish them.

This wave exposes no approval-promotion operation. The gateway denies PENDING and EXPIRED rows. Before enabling promotion, Kiro must approve either expiring bound PENDING records in the same deletion trigger or adding durable original-binding metadata with a promotion guard. Existing v1.5.6 behavior, including retention of PENDING status, was preserved. The regression that reproduces the remaining gap is `test_pending_orphan_and_originally_unbound_share_authorization_state`.

## Files changed

- Adapters: `src/devflow_api/adapters/exceptions.py`, `registry.py`, `mcp_client.py`, and `live/{__init__,_http,github,figma,ollama,mcp_live}.py`.
- Authorization and migrations: `src/devflow_api/models/{__init__,mcp_approval}.py`, `repositories/{approval_request,mcp_approval}.py`, `services/mcp_service.py`, `database.py`, `alembic/versions/006_add_mcp_approvals.py`.
- Configuration and API: `src/devflow_core/{config,mcp_config}.py`, `.env.example`, `src/devflow_api/{main,routers/integrations,schemas/integration,schemas/github}.py`, `docs/openapi.json`.
- UI: `src/devflow_ui/api_client.py`, `pages/9_Integrations.py`, `pages/10_Settings.py`.
- Dependencies: `requirements/base.txt`, `requirements/requirements.lock`, `uv.lock`, `.github/workflows/ci.yml`.
- Tests: `tests/mcp_fakes.py`, `tests/unit/test_{live_adapters,integrations_router,mcp_client,mcp_service,mcp_approval_repository}.py`, `tests/integration/test_database.py`, `tests/smoke/test_ui_pages.py`.

## Local checks

| Command or verification | Exit | Result |
| --- | ---: | --- |
| `python -m ruff check .` | 0 | PASS |
| `python -m ruff format --check .` | 0 | PASS |
| `python -m mypy --strict src tests alembic scripts/export_openapi.py` | 0 | PASS |
| Focused adapter, registry and MCP tests | 0 | PASS, 77 tests |
| `python -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=xml:.venv/w56-coverage.xml` | 0 | PASS, 243 tests and 92.01% combined coverage |
| Separate branch threshold from coverage XML | 0 | PASS, 284 of 346 branches (82.08%) |
| `python -m pytest -m integration -v --no-cov` | 0 | PASS, 18 SQLite migration and lifecycle cases |
| `python -m bandit -qr src` | 0 | PASS |
| `python -m pip check` | 0 | PASS |
| `python -m pip_audit -r requirements/requirements.lock --no-deps --format json` | 0 | PASS, no known vulnerabilities reported |
| `python -m detect_secrets scan <changed implementation files>` | 0 | PASS, 39 files and no findings |
| `python -m build --no-isolation` | 0 | PASS, wheel and sdist built |
| `python -m pip install --dry-run -r requirements/requirements.lock -r requirements/test.txt -e .` | 0 | PASS, dependency resolution verified |
| `python scripts/export_openapi.py` and OpenAPI comparison | 0 | PASS, response schema adds integration mode; prior paths and other schemas preserved |
| `git diff --check` and `git diff --cached --check` | 0 | PASS, line-ending notices only |
| Docker-backed TruffleHog | Ã¢â‚¬â€ | BLOCKED locally. Docker Desktop Linux engine pipe unavailable. |
| GitHub Actions | Ã¢â‚¬â€ | Pending Kiro handoff |

All validations used Python 3.12.10. Tests used mocked HTTP/subprocess transports, disposable SQLite databases and the existing Windows asyncio loopback allowance. No application database was created. The source review used GitHub's REST endpoint contracts for [branches](https://docs.github.com/en/rest/branches/branches), [pull requests](https://docs.github.com/en/rest/pulls/pulls) and [check runs](https://docs.github.com/en/rest/checks/runs).

## Named I7 tests

All 57 unique names in Task I7 were found with PASS results in the final pytest log.

- `test_allowlist_alone_insufficient_for_consequential_tool` Ã¢â‚¬â€ PASS
- `test_approval_bound_to_workflow_rejected_without_workflow_context` Ã¢â‚¬â€ PASS
- `test_approval_modified_between_validation_and_consumption` Ã¢â‚¬â€ PASS
- `test_approval_unbound_rejected_with_workflow_context` Ã¢â‚¬â€ PASS
- `test_approval_wrong_workflow_run_rejected` Ã¢â‚¬â€ PASS
- `test_begin_immediate_prevents_toctou` Ã¢â‚¬â€ PASS
- `test_busy_timeout_treated_as_authorization_failure` Ã¢â‚¬â€ PASS
- `test_cascaded_deletion_handles_mcp_approvals` Ã¢â‚¬â€ PASS
- `test_concurrent_consumption_only_one_succeeds` Ã¢â‚¬â€ PASS
- `test_concurrent_consumption_safe` Ã¢â‚¬â€ PASS
- `test_consequential_tool_denied_without_approval` Ã¢â‚¬â€ PASS
- `test_consumed_approval_cannot_be_reused` Ã¢â‚¬â€ PASS
- `test_direct_mcp_client_call_blocked_without_service_layer` Ã¢â‚¬â€ PASS
- `test_execution_failure_does_not_restore_approval` Ã¢â‚¬â€ PASS
- `test_execution_failure_does_not_restore_consumed_approval` Ã¢â‚¬â€ PASS
- `test_expired_approval_after_deletion_cannot_be_consumed` Ã¢â‚¬â€ PASS
- `test_expired_approval_rejected_at_invocation` Ã¢â‚¬â€ PASS
- `test_expired_at_consumption_time_rejected` Ã¢â‚¬â€ PASS
- `test_expired_mcp_approval_emits_approval_expired_event` Ã¢â‚¬â€ PASS
- `test_expired_mcp_approval_rejected` Ã¢â‚¬â€ PASS
- `test_figma_adapter_raises_missing_credential` Ã¢â‚¬â€ PASS
- `test_forged_approval_record_rejected` Ã¢â‚¬â€ PASS
- `test_github_adapter_creates_issue` Ã¢â‚¬â€ PASS
- `test_github_adapter_raises_missing_credential` Ã¢â‚¬â€ PASS
- `test_github_adapter_timeout_raises_integration_error` Ã¢â‚¬â€ PASS
- `test_github_token_not_in_log_records` Ã¢â‚¬â€ PASS
- `test_integrations_page_renders` Ã¢â‚¬â€ PASS
- `test_mcp_call_tool_returns_result` Ã¢â‚¬â€ PASS
- `test_mcp_client_uses_locked_sdk_version` Ã¢â‚¬â€ PASS
- `test_mcp_integration_runs_offline_with_mock_subprocess` Ã¢â‚¬â€ PASS
- `test_mcp_permission_denied_before_subprocess` Ã¢â‚¬â€ PASS
- `test_mcp_secret_values_not_in_log_records` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_cleanup_in_finally_block` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_does_not_inherit_parent_secrets` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_receives_explicit_env` Ã¢â‚¬â€ PASS
- `test_mcp_subprocess_terminated_on_timeout` Ã¢â‚¬â€ PASS
- `test_mismatched_arguments_hash_rejected` Ã¢â‚¬â€ PASS
- `test_mismatched_tool_name_rejected` Ã¢â‚¬â€ PASS
- `test_missing_approval_emits_approval_missing_event` Ã¢â‚¬â€ PASS
- `test_new_approval_required_for_retry_after_failure` Ã¢â‚¬â€ PASS
- `test_no_direct_mcp_client_bypass` Ã¢â‚¬â€ PASS
- `test_null_to_null_match_rejected_for_originally_bound_approval` Ã¢â‚¬â€ PASS
- `test_ollama_adapter_generate` Ã¢â‚¬â€ PASS
- `test_ollama_health_check_unavailable_when_not_running` Ã¢â‚¬â€ PASS
- `test_read_only_tool_no_approval_required` Ã¢â‚¬â€ PASS
- `test_read_only_tool_permitted_without_approval` Ã¢â‚¬â€ PASS
- `test_replay_after_consumption_rejected` Ã¢â‚¬â€ PASS
- `test_settings_page_renders` Ã¢â‚¬â€ PASS
- `test_timeout_recorded_as_indeterminate_in_audit` Ã¢â‚¬â€ PASS
- `test_trigger_rollback_restores_approval` Ã¢â‚¬â€ PASS
- `test_unknown_tool_denied_without_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_allowed_after_approval_consumed` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_allowed_with_pending_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_expires_approved_mcp_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_preserves_consumed_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_deletion_preserves_rejected_approval` Ã¢â‚¬â€ PASS
- `test_workflow_run_id_from_arguments_not_trusted` Ã¢â‚¬â€ PASS

---

## Historical report Ã¢â‚¬â€ v1.5.4 attempt

# Phase 1 Wave 4 implementation report

## Decision

**WAVE 4 BLOCKED Ã¢â‚¬â€ ACTION REQUIRED**

Standalone GitHub, Ollama, and Figma HTTP adapter behavior and offline tests were implemented. Application wiring and MCP execution remain blocked by the security boundary below. The current API continues using the existing registry behavior.

## Preflight

- Repository `J:\Android\GenAI\DevFlow-AI`
- Branch `feature/phase1-wave4-integration-execution`
- HEAD and approved Wave 3 merge base `756100d1166c64b001da4a044ad22513197ab408`
- Confirmed Wave 3 ancestry with `git merge-base --is-ancestor` (exit 0). Reviewed the Phase 1 v1.5.4 Kiro trio, roadmap, and `docs/reports/git-preflight-wave4.md`.
- The starting tree contained untracked reports. All were preserved. No specification, migration, dependency lock, or CI threshold changed. The index remains unchanged.

## Security blockers

1. **MCP child environment and transport.** Design Ã‚Â§7.2 and Task I4 require the Python MCP SDK's `stdio_client`. REQ-M1.5 and REQ-S1.5 require the launched MCP process to receive the resolved configuration exactly, without inheriting parent variables. The SDK v1.29.1 launcher merges `get_default_environment()` into the supplied dictionary before spawning. For example, parent PATH and Windows USERPROFILE can be included when absent from the configuration. The same SDK transport uses a fixed cleanup timeout and does not expose the specified five-second termination grace period through `StdioServerParameters`. A mock that inspects only the requested parameters would miss both differences. Kiro needs to approve an explicit-environment transport using SDK ClientSession or amend the environment and cleanup contract to match the SDK. [MCP SDK v1.29.1 launcher and shutdown code](https://github.com/modelcontextprotocol/python-sdk/blob/v1.29.1/src/mcp/client/stdio/__init__.py#L97-L200)
2. **Approval binding after run deletion.** Design Ã‚Â§3.7a prescribes `ON DELETE SET NULL`, while REQ-M2.2 permits a null-to-null binding and design Ã‚Â§7.5 requires it to match trusted context. A local in-memory SQLite probe inserted a bound APPROVED record, deleted its run, and read back `(NULL, APPROVED)`. A later unbound invocation can then satisfy the null-to-null check even though the record was issued for a workflow run. The approved schema and lifecycle need a rule that makes affected approvals unusable, such as transactional revocation when the run is deleted. Atomic rechecking by itself cannot distinguish the resulting NULL from an originally unbound approval.

## Task status and traceability

| Task | Requirements | Status and evidence |
| --- | --- | --- |
| I1 | REQ-I1.5, REQ-M1.4, REQ-M1.5 | Partial. Added MCP connection, secret resolution and consumption exception declarations. Existing HTTP exception mappings remain in place. GitHub response bodies are retained on the exception separately from the safe message. MCP exception context and behavior remain pending I4. |
| I2 | REQ-I1.1, REQ-S1.2Ã¢â‚¬â€œS1.3 | Partial. Implemented the existing typed `create_issue` interface and health check. Mocked tests cover authentication, the ten-second timeout, missing credentials, HTTP errors and no token emission. The additional Ã‚Â§8.1 branch/PR/check-run methods and their typed contracts remain outstanding. |
| I3 | REQ-I1.2Ã¢â‚¬â€œI1.3 | Implemented standalone generation/file actions and graceful health behavior via HTTPX. Offline tests cover URL, timeout, credential handling and Figma failures. Capability metadata keeps the existing Phase 0 field value; design Ã‚Â§6.2 calls for True for live adapters while Ã‚Â§17 preserves the existing Literal[False] schema. |
| I4 | REQ-M1.1Ã¢â‚¬â€œM1.8, REQ-M2.1Ã¢â‚¬â€œM2.5 | BLOCKED. MCP transport, gateway, approval persistence, migration 006 and SDK lock are pending. No launch or authorization path was enabled. |
| I5 | REQ-I1.4 | Not started. Live registry and startup wiring depend on I4. |
| I6 | REQ-I1.6, REQ-M1.1, REQ-S1.2 | Partial. Added GitHub/Figma API origins and Ollama timeout settings, with dotenv entries. Mode reporting and MCP config validation remain pending. |
| I7 | REQ-I1.6, REQ-U1.5, REQ-T1.1Ã¢â‚¬â€œT1.2 | Partial. Added offline tests for three HTTP adapters. Integration and Settings pages and MCP tests remain pending. The brief names pages 3 and 4; approved Task I7 and design Ã‚Â§12.1 name existing pages 9 and 10, which govern implementation. |

## Changed files

- `src/devflow_api/adapters/live/{__init__,_http,github,ollama,figma}.py`
- `src/devflow_api/adapters/exceptions.py`
- `src/devflow_core/config.py` and `.env.example`
- `tests/unit/test_live_adapters.py`
- This report

## Validation

Python commands used `.venv/wave3/Scripts/python.exe`. No application database was created.

| Command | Exit | Result |
| --- | ---: | --- |
| `python -m ruff check .` | 0 | PASS |
| `python -m ruff format --check .` | 0 | PASS |
| `python -m mypy --strict src tests alembic scripts/export_openapi.py` | 0 | PASS, 126 source files |
| `python -m pytest -v --cov=src --cov-branch --cov-fail-under=80 --cov-report=term-missing --cov-report=xml:.venv/wave4-coverage.xml` | 0 | PASS, 172 tests and 92.59% combined coverage on serial rerun; first run exited 1 after one existing AppTest navigation timeout during concurrent validation |
| Branch-only coverage | 0 | PASS, 192 of 234 branches (82.05%) |
| `python -m pytest -m integration -v --no-cov` | 0 | PASS, four existing migration tests; head remains 005 |
| `python -m pip check` | 0 | PASS |
| `python -m bandit -qr src` | 0 | PASS |
| `python -m pip_audit -r requirements/base.txt --format json` | 0 | PASS, no known vulnerabilities reported in current dependencies |
| `python -m detect_secrets scan <changed files>` | 0 | PASS, nine files, zero findings |
| `python -m build --no-isolation` | 0 | PASS, wheel and sdist built |
| `git diff --check` | 0 | PASS, line-ending notices only |
| Runtime OpenAPI comparison to `docs/openapi.json` | 0 | PASS, identical |
| In-memory SQLite foreign-key probe | 0 | Reproduced the binding loss described above |
| Migration 006 and all named MCP tests | Ã¢â‚¬â€ | BLOCKED, no Wave 4 MCP migration or transport implemented |
| Hosted GitHub Actions | Ã¢â‚¬â€ | Pending Kiro's Git handoff |

## Task I7 MCP test inventory

Each named MCP test below is **BLOCKED / not run**. This inventory uses every MCP name enumerated in I7, including positive/offline checks. The roadmap's count of 26 refers to its security gate.

- `test_mcp_subprocess_launched_with_explicit_env`
- `test_mcp_secret_values_not_in_log_records`
- `test_mcp_call_tool_returns_result`
- `test_mcp_permission_denied_before_subprocess`
- `test_unknown_tool_denied_without_approval`
- `test_consequential_tool_denied_without_approval`
- `test_read_only_tool_permitted_without_approval`
- `test_direct_mcp_client_call_blocked_without_service_layer`
- `test_expired_mcp_approval_rejected`
- `test_expired_mcp_approval_emits_approval_expired_event`
- `test_missing_approval_emits_approval_missing_event`
- `test_allowlist_alone_insufficient_for_consequential_tool`
- `test_mcp_client_uses_locked_sdk_version`
- `test_mcp_integration_runs_offline_with_mock_subprocess`
- `test_forged_approval_record_rejected`
- `test_expired_approval_rejected_at_invocation`
- `test_mismatched_tool_name_rejected`
- `test_mismatched_arguments_hash_rejected`
- `test_replay_after_consumption_rejected`
- `test_concurrent_consumption_safe`
- `test_read_only_tool_no_approval_required`
- `test_no_direct_mcp_client_bypass`
- `test_execution_failure_does_not_restore_approval`
- `test_timeout_recorded_as_indeterminate_in_audit`
- `test_new_approval_required_for_retry_after_failure`
- `test_approval_wrong_workflow_run_rejected`
- `test_approval_bound_to_workflow_rejected_without_workflow_context`
- `test_approval_unbound_rejected_with_workflow_context`
- `test_workflow_run_id_from_arguments_not_trusted`
- `test_concurrent_consumption_only_one_succeeds`
- `test_expired_at_consumption_time_rejected`
- `test_consumed_approval_cannot_be_reused`
- `test_execution_failure_does_not_restore_consumed_approval`
- `test_busy_timeout_treated_as_authorization_failure`
- `test_begin_immediate_prevents_toctou`
- `test_approval_modified_between_validation_and_consumption`
No changes were committed, pushed, merged, or submitted as a PR.
