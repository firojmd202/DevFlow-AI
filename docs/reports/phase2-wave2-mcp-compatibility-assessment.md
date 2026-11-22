# DevFlow AI — Phase 2 Wave 2: MCP Compatibility Assessment

**Version:** 1.0.0
**Status:** Draft
**Branch:** `feature/phase2-wave2-ai-spec-generation`
**Last Updated:** 2026-11-18

---

## 1. MCP Python SDK Version Declared

**File:** `requirements/base.txt`
**Declared constraint:** `mcp>=1.0,<2.0`

The codebase currently targets MCP Python SDK 1.x. The existing `MCPClient` implementation (`src/devflow_api/adapters/mcp_client.py`) imports from:
- `mcp.ClientSession`
- `mcp.shared.message.SessionMessage`
- `mcp.types.JSONRPCMessage`
- `mcp.types.LoggingMessageNotificationParams`

These imports are confirmed by reading the production source file.

---

## 2. Target Version Range for Wave 2

**Wave 2 target (from approved decisions):** `mcp>=2.3.0,<3.0`

This is the range specified in the Wave 2 approved decisions. It is a **proposed upgrade**, not the currently declared version. The declared version remains `mcp>=1.0,<2.0` at the time Wave 2 specs are authored.

---

## 3. Known API Surface (mcp 1.x — from codebase inspection)

The following `mcp` SDK symbols are used in the production codebase (`src/devflow_api/adapters/mcp_client.py`):

| Symbol | Usage |
|---|---|
| `mcp.ClientSession` | Session management; `initialize()` and `call_tool(tool_name, arguments)` methods |
| `mcp.shared.message.SessionMessage` | Typed message wrapper for in-memory transport streams |
| `mcp.types.JSONRPCMessage` | Message validation via `model_validate_json(line)` |
| `mcp.types.LoggingMessageNotificationParams` | Callback type for `logging_callback` parameter of `ClientSession` |

The existing code does **not** use: `mcp.StdioServerParameters`, `mcp.stdio_client`, or any MCP server-side classes. The client-only surface is used.

---

## 4. API Surface for mcp 2.x (Assessment)

The MCP Python SDK 2.x line is not installed in the current environment (only `>=1.0,<2.0` is declared). Based on the Wave 2 approved decisions and design intent:

**What the `MCPClientAdapter` requires from the SDK:**
1. A `ClientSession`-equivalent that accepts an in-memory or stdio transport and exposes `initialize()` and `call_tool(name, arguments)`.
2. A mechanism to serialize/deserialize `JSONRPCMessage` (Pydantic v2 model with `model_validate_json`).
3. A `SessionMessage` wrapper for the in-memory stream protocol.
4. A `logging_callback` or equivalent to discard server log payloads (security: logs may contain credentials).

**Known risk:** The mcp SDK 2.x release notes are not available in the current environment. It is not confirmed whether `mcp.ClientSession` signature, `SessionMessage`, or `JSONRPCMessage` paths changed between 1.x and 2.3.x. The existing `MCPClient` implementation uses a custom `_stdio_session` context manager and `anyio` streams rather than the SDK's higher-level transport helpers, which may reduce the surface area of breaking changes.

---

## 5. Compatibility Verdict

**Verdict: UNKNOWN**

**Rationale:**
- The declared version is `mcp>=1.0,<2.0`; the target is `mcp>=2.3.0,<3.0`. These are mutually exclusive ranges.
- The existing `MCPClient` uses a narrow subset of the SDK (`ClientSession`, `SessionMessage`, `JSONRPCMessage`, `LoggingMessageNotificationParams`).
- The `MCPClientAdapter` design (design §3.5) isolates all `mcp.*` imports behind `MCPClient`; Wave 2 services do not import `mcp.*` directly.
- Whether the `mcp` 2.x API surface for these four symbols is backward-compatible with 1.x is not determinable from the codebase alone; it requires reviewing the mcp 2.x changelog or source.
- Until Dependabot PR #20 is evaluated (see §6), upgrading `requirements/base.txt` to `mcp>=2.3.0,<3.0` is not authorized.

**Risk level:** Medium. The existing code uses a custom stdio transport layer rather than the SDK's high-level helpers, which likely reduces (but does not eliminate) breaking change risk.

---

## 6. Dependabot PR #20 Impact Assessment

**Status at time of spec authoring:** PR #20 is confirmed open (not merged, not closed) based on the approved Wave 2 decisions (Decision 8: "Dependabot PR #20 must be evaluated separately; do not merge it automatically").

**What PR #20 likely changes:**
Dependabot PRs for the `mcp` package at version 2.x would update `requirements/base.txt` from `mcp>=1.0,<2.0` to a 2.x constraint. The exact diff is not inspected in this assessment (consistent with the decision to not merge it without evaluation).

**Impact on Wave 2:**
- If PR #20 upgrades to `mcp>=2.3.0,<3.0`, it aligns with the Wave 2 target range and would change the `MCPClientAdapter`'s compatibility requirements.
- The `MCPClientAdapter` design is specifically architected so that an SDK upgrade only requires changes in `MCPClient` and `MCPClientAdapter`, not in any service.
- If `ClientSession.call_tool()` or `JSONRPCMessage.model_validate_json()` changed signatures in 2.x, `MCPClient` would need updating before `MCPClientAdapter` tests could be verified.

**Recommendation:**
1. Review PR #20 diff and mcp 2.x changelog before merging.
2. Run the `MCPClientAdapter` compatibility test suite (W2.T3, W2.T11.10) against both 1.x and 2.x in CI.
3. If the 2.x API surface for the four used symbols is backward-compatible, update `requirements/base.txt` to `mcp>=2.3.0,<3.0` as a separate commit, not in this spec branch.
4. Do NOT merge PR #20 automatically as part of Wave 2 spec authoring.

---

## 7. Design Constraints for `MCPClientAdapter` to Remain SDK-Version-Isolated

The following constraints MUST be respected to ensure an mcp SDK version upgrade touches only `MCPClient` and `MCPClientAdapter`:

1. **No `mcp.*` import outside `MCPClient`.** `SpecificationGenerationService`, `SpecificationReviewService`, `SpecificationApprovalService`, and all routers MUST import only `MCPClientAdapter`, never `mcp.*` symbols directly. This is enforced by an AST import guard test (W2.T3.4).

2. **`ContextChunk` as the stable output type.** `MCPClientAdapter.retrieve_context()` returns `ContextChunk`, a Wave 2-owned Pydantic v2 model. Services depend on `ContextChunk`, not on `MCPToolResult`. An SDK change to the internal result format requires changing only the `ContextChunk` construction in `MCPClientAdapter`.

3. **Transport layer ownership in `MCPClient`.** The custom `_stdio_session` context manager and `anyio` stream wiring are entirely within `MCPClient`. If the SDK changes its session initialization API, only `MCPClient._stdio_session` needs updating.

4. **No SDK-specific exception types outside the adapter.** `MCPClient` catches all `mcp.*`-originating exceptions and re-raises them as `MCPConnectionError`, `MCPTimeoutError`, `MCPPermissionError` (all defined in `src/devflow_api/adapters/exceptions.py`). `MCPClientAdapter` catches these and converts them to `ContextChunk` (non-critical) or `MCPContextFailureError` (critical). Services catch only `MCPContextFailureError`.

5. **SDK version pinned in `MCPClientAdapter` docstring.** Each release of `MCPClientAdapter` documents which `mcp` SDK version it was authored and tested against, making the compatibility boundary explicit.

---

## 8. Recommended Compatibility Tests

The following tests MUST run offline (no live MCP server) and MUST be part of the W2.T11 test suite:

| Test | Description |
|---|---|
| `test_mcp_adapter_tool_allowlist` | Calls a non-allowlisted tool; expects `MCPPermissionError` before subprocess starts |
| `test_mcp_adapter_schema_validation` | Passes invalid arguments; expects `MCPToolSchemaError` before subprocess starts |
| `test_mcp_adapter_timeout` | Mocked subprocess that hangs; expects `MCPTimeoutError` after `timeout_seconds` |
| `test_mcp_adapter_connection_error` | Mocked subprocess that fails to start; expects `MCPConnectionError` |
| `test_mcp_adapter_audit_event` | Verifies `mcp_tool_invoked` audit event written with `argument_hash` not raw args |
| `test_mcp_adapter_no_sdk_imports_in_services` | AST scan of service modules; asserts no `mcp.*` imports |
| `test_mcp_adapter_context_chunk_normalization` | Mocked `MCPToolResult`; verifies `ContextChunk` output has correct fields |
| `test_mcp_adapter_critical_failure` | Required tool fails; expects `MCPContextFailureError` |
| `test_mcp_adapter_non_critical_failure` | Optional tool fails; generation proceeds with warning |
| `test_mcp_adapter_credential_redaction` | Env variable with secret; confirms secret not in audit log |

---

## 9. Summary

| Item | Value |
|---|---|
| Declared SDK version | `mcp>=1.0,<2.0` |
| Target SDK version | `mcp>=2.3.0,<3.0` |
| Compatibility verdict | **UNKNOWN** (requires PR #20 evaluation and 2.x changelog review) |
| Upgrade risk | Medium (narrow SDK surface; custom transport reduces risk) |
| Dependabot PR #20 | Open; must be evaluated separately before merge |
| Adapter isolation | Strong: all `mcp.*` imports confined to `MCPClient`; services use only `MCPClientAdapter` |
| Action required before Wave 2 implementation | Evaluate PR #20; test `MCPClient` against `mcp>=2.3.0,<3.0` on a branch |
