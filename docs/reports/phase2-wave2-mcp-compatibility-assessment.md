# DevFlow AI — Wave 2 MCP compatibility assessment

**Updated:** 2026-11-23
**Verdict:** Compatible at the tested and locked SDK version, MCP 2.3.0.

| Item | Result |
|---|---|
| Declaration and frozen target | `requirements/base.txt` declares `mcp>=2.3.0,<3.0`. |
| Resolution | `requirements/requirements.lock` and `uv.lock` pin 2.3.0. |
| Protocol validation | `JSONRPCMessage` became a union. A Pydantic `TypeAdapter[JSONRPCMessage]` validates each received JSON message before it enters `SessionMessage`. |
| Session and result handling | The transport uses SDK `ClientSession`, typed messages and completed tool results. Unexpected result variants fail closed. |
| Adapter boundary | SDK imports stay in the Phase 1 transport. Wave 2 consumes typed context through `MCPClientAdapter`, with per-server tool allowlists, explicit authorization and optional strict schema validation. |
| Process and credential safeguards | The transport builds the child environment explicitly, discards MCP server log payloads and applies timeout and cleanup behavior. |

Phase 1 transport tests use fake subprocesses for initialization, tool discovery and invocation, protocol validation and cleanup. Wave 2 adapter tests cover permissions, schema checks, typed error and result handling, cancellation and secret redaction. See the [Group A blocker resolution](phase2-wave2-group-a-blocker-resolution.md) and [Wave 2 implementation report](phase2-wave2-final-implementation-report.md) for test evidence. Later 2.x versions within the declaration need their own lock update and compatibility run.

## Dependabot PR #20

On 2026-11-23, `gh pr view 20 -R kotlinandfluttertutorial-lab/DevFlow-AI --json state,mergedAt,headRefOid,files` returned OPEN and unmerged at `f7072c5676f1fc1a36bd9f169f0d6bebdd21a4e2`. The corresponding `gh pr diff 20 -R kotlinandfluttertutorial-lab/DevFlow-AI --patch` showed one file, `requirements/base.txt`, replacing `mcp>=1.0,<2.0` with `mcp>=2.3.0,<3.0`. That declaration already exists in Wave 2 alongside both updated locks and the compatibility code. Reassess and close the redundant PR after Wave 2 lands on the intended base. [Dependabot PR #20](https://github.com/kotlinandfluttertutorial-lab/DevFlow-AI/pull/20)
