# Phase 1 Wave 4 — Specification Conflict Resolution Report

**Date:** 2026-11-16
**Repository:** `J:\Android\GenAI\DevFlow-AI`
**Branch:** `feature/phase1-wave4-integration-execution`
**Specification version:** Phase 1 **v1.5.5** (corrected from v1.5.4 by this pass)
**Scope:** Specification correction only — no application code, migrations, or CI changed
**Author role:** Principal Software Architect, MCP Security Engineer, Specification Maintainer
**Mode:** SPECIFICATION CORRECTION ONLY

---

## 0. Executive summary

Four material Wave 4 specification conflicts (A–D) identified by the Codex Wave 4
implementation report (`.agents/tasks/phase1-wave4-implementation-report.md`) are
resolved at the specification layer. No source, tests, alembic migrations, CI, or
`pyproject.toml` were modified. The MCP authorization boundary was strengthened, not
weakened. All Codex working-tree changes and untracked reports were preserved.

**Final verdict: READY FOR CODEX — WAVE 4 SPECIFICATION RESOLVED.**

One-paragraph summary of the four resolutions:

- **Conflict A (MCP transport):** the approved spec simultaneously required the SDK
  `stdio_client` transport, an explicit-only child environment, and a `SIGTERM → 5 s →
  SIGKILL` grace — three requirements the SDK `stdio_client` cannot satisfy together
  (it merges `get_default_environment()` into the supplied env and exposes no
  configurable grace). The spec now mandates an explicit-environment subprocess
  (`asyncio.create_subprocess_exec(..., env=resolved_env)`) feeding SDK
  `ClientSession`, with `MCPClient` owning the deterministic cleanup; four named
  subprocess tests were added.
- **Conflict B (approval binding):** `mcp_approvals.workflow_run_id` was
  `ON DELETE SET NULL`, which lets an APPROVED approval lose its run binding and
  become a valid unbound (NULL) authorization via a NULL-to-NULL context match. The
  FK is now `ON DELETE RESTRICT` (database-enforced), eliminating the bypass; five
  named deletion/binding tests were added.
- **Conflict C (live adapter capability metadata):** design §6.2 required live
  adapters to return `IntegrationCapability(available_in_phase_0=True)`, but the
  Phase 0 schema field is the immutable `Literal[False]` (pydantic would reject
  `True`). The contract now mandates `available_in_phase_0=False`; the live/stub
  distinction is carried by `execution_mode`, the `mode` field, and `stub=False`.
- **Conflict D (Streamlit page numbering):** the canonical Wave 4 pages are the
  EXISTING `9_Integrations.py` and `10_Settings.py` (verified against the actual
  `src/devflow_ui/pages/` tree); Wave 4 UPDATEs them in place. The brief's premise
  of `3_Integrations.py`/`4_Settings.py` does not match the repository (page 3 is
  `3_Learning.py`, page 4 is `4_Specifications.py`). No new pages are created.

---

## 1. Root cause of each conflict

### Conflict A — MCP subprocess environment and transport

The approved v1.5.4 spec carried three mutually incompatible MCP transport
requirements:

1. REQ-M1.2 and design §7.2 / Task I4 required launching the server "using the MCP
   Python SDK's `stdio_client`".
2. REQ-M1.5.5 / REQ-S1.5.1 and Task I4 required the subprocess to be launched with
   `env=resolved_env` (not `env=None`), and a unit test (`test_mcp_subprocess_launched_with_explicit_env`)
   asserted `asyncio.create_subprocess_exec` is called with `env=resolved_env`.
3. REQ-M1.2.5 / REQ-S1.5.2 required a `SIGTERM → 5 s grace → SIGKILL` cleanup.

The SDK `stdio_client` owns the subprocess: callers do not call
`asyncio.create_subprocess_exec` directly, and the SDK merges the parent
environment and uses a fixed cleanup timeout. Requirements 1–3 therefore cannot all
hold when `stdio_client` is the transport. The contradiction was latent in the spec
and was surfaced by Codex's v1.29.1 SDK inspection.

### Conflict B — Workflow-run deletion and approval binding

`mcp_approvals.workflow_run_id` was declared `ON DELETE SET NULL` (design §3.7a
SQL + model, REQ-M2.1 description + M2.1.3, Task I4 migration 006). The
authorization check (REQ-M2.2 step 3.e / REQ-M2.5) is NULL-safe: an approval with
`workflow_run_id = NULL` authorizes an invocation with `trusted_workflow_run_id =
NULL`. If an APPROVED approval originally bound to run X has its `workflow_run_id`
cleared to NULL by a run deletion, a later unbound invocation (`trusted_workflow_run_id
= NULL`) satisfies the NULL-to-NULL match and the approval becomes a valid unbound
authorization — a privilege-escalation bypass of the run binding. Codex reproduced
this with an in-memory SQLite probe (`(NULL, APPROVED)` after run delete).

### Conflict C — Live adapter capability metadata

Design §6.2 stated each live adapter exposes `capability` as a `@property` returning
`IntegrationCapability(available_in_phase_0=True)`. The Phase 0
`IntegrationCapability` schema
(`src/devflow_api/adapters/capability.py`) declares
`available_in_phase_0: Literal[False]` — a fixed type accepting only `False`.
Instantiating `IntegrationCapability(..., available_in_phase_0=True)` raises a
pydantic `ValidationError`. The spec therefore demanded behaviour the schema
forbids. The Phase 0 schema is immutable and out of scope to modify (strict boundary:
no `src/` changes), so the design — not the schema — must yield.

### Conflict D — Streamlit page numbering

The resolution brief assumed the existing pages were
`3_Integrations.py`/`4_Settings.py`. The actual `src/devflow_ui/pages/` tree is:
`1_Dashboard.py`, `2_Projects.py`, `3_Learning.py`, `4_Specifications.py`,
`5_Design.py`, `6_Workflows.py`, `7_History.py`, `8_Documentation.py`,
`9_Integrations.py`, `10_Settings.py`. The approved spec (Task I7, design §12.1
page inventory, REQ-I1.6, REQ-U1.5) already referenced `9_Integrations.py` and
`10_Settings.py` and used the verbs "Replace"/"Extend" — i.e. UPDATE existing pages.
So the spec was already correct; the brief's premise was inaccurate. The conflict to
resolve was to *confirm* consistency and make the "UPDATE existing, not create new"
intent explicit so the implementer does not invent `3_Integrations.py`/`4_Settings.py`.

---

## 2. Evidence from SDK / source inspection

### MCP SDK inspection

The `mcp` package is **not installed** in any workspace virtualenv:
- `& .venv\Scripts\python.exe -c "import mcp"` → `ModuleNotFoundError: No module named 'mcp'`
- `& .venv\wave3\Scripts\python.exe -c "import mcp"` → `ModuleNotFoundError: No module named 'mcp'`
- A filesystem search for any `mcp*` package directory under `.venv` returned nothing.
- `pyproject.toml` and `requirements/**/*.txt` declare no `mcp` constraint (grep for `mcp` → no matches).

Local SDK source could therefore not be read. The transport evidence comes from:

1. **Codex Wave 4 implementation report** (`.agents/tasks/phase1-wave4-implementation-report.md`,
   Security blocker #1), which inspected **MCP SDK v1.29.1** and stated:
   - "The SDK v1.29.1 launcher merges `get_default_environment()` into the supplied
     dictionary before spawning. For example, parent PATH and Windows USERPROFILE
     can be included when absent from the configuration."
   - "The same SDK transport uses a fixed cleanup timeout and does not expose the
     specified five-second termination grace period through `StdioServerParameters`."
   - Cited source: `mcp/client/stdio/__init__.py#L97-L200`.
2. **Public MCP Python SDK v1.x API** (`mcp>=1.0,<2.0`, the operative constraint per
   REQ-M1.8): `mcp.client.stdio.stdio_client(server: StdioServerParameters)` is an
   async context manager that spawns the subprocess and yields
   `(MemoryObjectReceiveStream, MemoryObjectSendStream)`; `mcp.client.session.ClientSession(read_stream, write_stream, …)`
   wraps those streams into the protocol session. Because `stdio_client` owns the
   subprocess, the caller cannot pass a fully-resolved-only env (the launcher merges
   defaults) and cannot drive a custom `SIGTERM → 5 s → SIGKILL` sequence through its
   context-manager cleanup. `ClientSession`, by contrast, is stream-oriented and can
   be constructed over any stdio pair — including a subprocess we own.

This is sufficient to establish that an explicit-environment transport using
`ClientSession` is feasible and that `stdio_client` is not compatible with the
isolation + grace requirements. The decision does not rely on an unverified
assumption about an uninstalled SDK; it relies on Codex's v1.29.1 finding plus the
stable, documented `ClientSession` constructor signature.

### Existing source inspection (read-only)

- `src/devflow_api/adapters/capability.py` — `IntegrationCapability` declares
  `available_in_phase_0: Literal[False]` (only `False` is valid). Confirms Conflict C.
- `src/devflow_api/adapters/protocols/base.py` — `BaseAdapterProtocol` requires
  `name`, `capability: IntegrationCapability`, and `async def health_check() -> dict[str, str]`.
  The live adapter contract must conform to this Protocol.
- `src/devflow_api/adapters/protocols/mcp.py` — `MCPAdapterProtocol(BaseAdapterProtocol)`
  adds `async def call_tool(server, tool, args) -> MCPResponse`. `MCPLiveAdapter` must
  implement this; no capability-metadata change is needed for MCP.
- `src/devflow_api/adapters/stubs/_base.py` — `OfflineAdapter` exposes `capability` as
  a `@property` returning a deep copy of a `ClassVar[IntegrationCapability]`. Live
  adapters may use the same `@property` pattern but with live values
  (`available_in_phase_0=False`).
- `src/devflow_api/adapters/live/github.py`, `live/ollama.py` (Codex, already on the
  working tree) — extend a shared `LiveHTTPAdapter` base; set `stub=False` in
  responses; do not touch `IntegrationCapability.available_in_phase_0` (they use the
  existing Phase 0 value). This confirms the implementable direction for Conflict C:
  keep `available_in_phase_0=False`.
- `src/devflow_ui/pages/` tree — confirms `9_Integrations.py` and `10_Settings.py`
  exist (Conflict D), and that `3_Integrations.py`/`4_Settings.py` do not.
- `docs/reports/git-preflight-wave4.md` — confirms branch base `756100d…`, Wave 3 PR
  #11 merged, spec v1.5.4.

---

## 3. Final authoritative contracts

### 3.1 MCP transport contract (Conflict A)

`MCPClient` launches each configured MCP server as an **explicit-environment
subprocess** and drives the MCP protocol over its stdio using the SDK
`ClientSession`:

1. Compose `resolved_env`:
   - interpolated `MCPServerConfig.env` (secrets via `${SECRET_NAME}` resolved only
     from `SecretStr` Settings fields; unresolvable → `MCPSecretResolutionError`);
   - PLUS a minimal, explicitly-named set of system variables required for the child
     to start, copied **by name** from the parent env (not by wholesale inheritance):
     Windows `PATH`, `SYSTEMROOT`, `WINDIR`, `TEMP`, `TMP`, `PATHEXT`, `COMSPEC`;
     POSIX `PATH`, `HOME`, `LANG`, `LC_ALL`, `TMPDIR`;
   - NO other parent variables; NO parent secrets.
2. Launch: `proc = await asyncio.create_subprocess_exec(*command, *args,
   env=resolved_env, stdin=PIPE, stdout=PIPE, stderr=…)`. The child receives ONLY
   `resolved_env`.
3. Bridge `proc.stdout`/`proc.stdin` to anyio memory streams and construct
   `ClientSession(read_stream, write_stream)` (SDK). `ClientSession.initialize()`
   performs tool discovery; `call_tool` invokes the tool within
   `MCPServerConfig.timeout_seconds`.
4. Cleanup (owned by `MCPClient`, in a `finally` block): send `SIGTERM`; wait up to
   5 s for exit; if still alive, send `SIGKILL`. On Windows, `SIGTERM` maps to
   `Process.terminate()`; the 5 s grace and kill fallback are unchanged.

**The SDK `stdio_client` is NOT used.** It merges `get_default_environment()` into
the supplied env (breaking explicit isolation) and exposes no configurable
termination grace (making the 5 s sequence impossible via its context-manager API).
`ClientSession` is the supported SDK interface retained; subprocess ownership and
cleanup remain entirely within `MCPClient`. No OS-level sandbox
(seccomp/namespaces/cgroups/AppArmor) is claimed or implemented (Phase 2).

Satisfies all six transport requirements: (1) explicit env isolation; (2) no silent
parent-secret inheritance; (3) uses a supported SDK interface (`ClientSession`);
(4) deterministic `SIGTERM → 5 s → SIGKILL` cleanup; (5) testable offline (mock
`asyncio.create_subprocess_exec` + `ClientSession`); (6) no OS-sandbox claim.

### 3.2 MCPApproval FK strategy (Conflict B)

`mcp_approvals.workflow_run_id` is **`ON DELETE RESTRICT`** (not `SET NULL`), enforced
by the database FK layer with `PRAGMA foreign_keys=ON` (REQ-DB1.3):

- Deleting a `workflow_runs` row still referenced by a **non-consumed APPROVED**
  `MCPApproval` raises `IntegrityError`; the run cannot be deleted until that
  approval is consumed/expired/rejected.
- A **CONSUMED** approval does not block deletion (it is already resolved).
- A **PENDING**/**REJECTED**/**EXPIRED** approval does not block deletion (PENDING
  is not an active APPROVED binding; REJECTED/EXPIRED are resolved).
- **Originally-unbound** approvals (`workflow_run_id IS NULL` at creation) keep their
  NULL-to-NULL authorization semantics per REQ-M2.5; `RESTRICT` does not alter that
  case — it only prevents an approval that was *originally bound* from silently
  becoming unbound via run deletion.

This is Option 4 (ON DELETE RESTRICT) from the analysis, chosen because it is the
simplest database-enforced solution: the NULL-to-NULL bypass is impossible for
originally-bound approvals because the deletion that would clear the binding is
rejected at the FK layer. It preserves audit history (approvals are not deleted),
handles direct and cascaded deletion (the RESTRICT fires on any path that would
clear the binding), is unaffected by concurrent consumption (the FK constraint is
independent of the `consume_atomic` transaction), and is auditable (the approval
record and its binding are retained). Application-level checks remain as
defense-in-depth (REQ-M2.5), but the invariant is owned by the DB FK layer because
application checks are bypassable via concurrent deletion and transaction rollback.

### 3.3 Live adapter capability contract (Conflict C)

The authoritative contract is the **Phase 0 `IntegrationCapability` schema**:
`available_in_phase_0: Literal[False]` (immutable; `src/` is out of scope to modify).
Live adapters MUST return `IntegrationCapability(available_in_phase_0=False)` —
`True` is impossible (pydantic `ValidationError`). The live/stub distinction is
expressed through:

- `execution_mode` — `ExecutionMode.AUTOMATED_API` for live adapters
  (`MANUAL_HANDOFF`/`UNKNOWN` for stubs);
- the per-response `stub: bool = False` flag on live adapter responses;
- the `mode: Literal["live","stub"]` field added to `IntegrationSummary` (Task I6).

Live adapters populate `supported_actions`, `auth_required`, `auth_type`, and `notes`
from the live integration's real capabilities (e.g. `auth_required=True`,
`auth_type="bearer"` for GitHub/Figma; `auth_required=False` for Ollama). The Phase 0
`BaseAdapterProtocol` (`name`, `capability`, `health_check`) is unchanged.

### 3.4 Streamlit page numbering (Conflict D)

Canonical Wave 4 pages (verified against `src/devflow_ui/pages/`):

| File | Wave 4 action |
|---|---|
| `9_Integrations.py` (exists) | UPDATE in place — placeholder → live integration status |
| `10_Settings.py` (exists) | UPDATE in place — health check → extended with integration/MCP/GitHub status |

No new Integrations/Settings pages are created; no pages are renumbered; `app.py`
navigation for pages 9 and 10 is unchanged. (Pages 6 and 7 were renamed in Wave 3:
`6_Coding.py → 6_Workflows.py`, `7_Testing.py → 7_History.py` — already done and
unchanged by Wave 4.)

---

## 4. Security implications

### Conflict B — how the NULL-to-NULL bypass is prevented

**The bypass (v1.5.4):** an APPROVED `MCPApproval` bound to run X, combined with
deletion of run X, set `workflow_run_id` to NULL (`ON DELETE SET NULL`). A subsequent
unbound invocation with `trusted_workflow_run_id = NULL` then matched the
NULL-to-NULL rule (REQ-M2.2 step 3.e / REQ-M2.5) and the approval authorized an
unbound action it was never granted for — the run binding was silently destroyed.

**The fix (v1.5.5):** `ON DELETE RESTRICT` makes the deletion that would clear the
binding fail at the FK layer (`IntegrityError`, requires `PRAGMA foreign_keys=ON`).
The approval cannot lose its binding via run deletion; therefore the NULL-to-NULL
match can never be reached for an originally-bound approval. The invariant is owned
by the database (not application code) because:

- **Direct deletion** — rejected (`IntegrityError`) while an APPROVED approval
  references the run.
- **Cascaded deletion** (e.g. project delete → workflow delete → run delete) — the
  RESTRICT fires when the cascade reaches the run that has an APPROVED MCP approval;
  deletion of the workflow/project is rejected unless those approvals are first
  consumed/expired/rejected.
- **Concurrent consumption** — the FK constraint is independent of the
  `consume_atomic` transaction; a concurrent consumer that sets the approval to
  CONSUMED (which no longer blocks deletion) is the only path that then permits run
  deletion, and CONSUMED approvals cannot be replayed (REQ-M2.4).
- **Already consumed** — CONSUMED approvals do not block deletion (already resolved).
- **Originally unbound** — `workflow_run_id IS NULL` at creation is unaffected; such
  approvals remain valid only against unbound invocations (REQ-M2.5). `RESTRICT`
  never fires on a NULL FK.
- **Transaction rollback** — a rolled-back run deletion leaves the binding intact;
  the FK constraint is ACID with the deletion transaction.

**No authorization requirement was weakened.** REQ-M1.7 (9-step authorization
sequence), REQ-M2.2 (`consume_atomic` 8-step in-transaction verification),
REQ-M2.5 (workflow_run_id binding rules), and REQ-S1.1 (consequential-action
gates) are unchanged. Conflict B only strengthens the boundary (RESTRICT vs SET
NULL) and adds defense-in-depth application checks + tests.

### Conflict A — security implications

The explicit-environment transport preserves the env-isolation invariant
(REQ-M1.5, REQ-S1.5): the child receives ONLY `resolved_env` (required system vars +
interpolated secrets), never the parent environment as a whole, so parent-only
secrets cannot leak into the MCP server subprocess. The deterministic
`SIGTERM → 5 s → SIGKILL` cleanup guarantees no orphaned subprocess on timeout/error.
No OS-level sandbox is claimed (consistent with the documented local single-user
threat model).

### Conflicts C and D — security implications

None. Conflict C is a schema-conformance correction (no authorization impact).
Conflict D is a page-numbering clarification (no authorization impact). Neither
weakens any gate.

---

## 5. Compatibility analysis

| Change | Breaks existing consumers? | Additive? |
|---|---|---|
| Conflict A: `stdio_client` → explicit subprocess + `ClientSession` | No production code exists yet for `MCPClient` (Wave 4 Task I4 is not implemented — Codex blocked it). The implementer builds `MCPClient` per the new contract. The old test name `test_mcp_subprocess_launched_with_explicit_env` is renamed to `test_mcp_subprocess_receives_explicit_env` (same intent, stronger assertion). | Additive: 3 new subprocess tests; transport contract clarified. |
| Conflict B: `mcp_approvals.workflow_run_id` SET NULL → RESTRICT | Migration 006 is a Wave 4 deliverable not yet applied (Codex blocked it). No existing migration 001–005 is changed. RESTRICT requires `PRAGMA foreign_keys=ON` (already mandated by REQ-DB1.3 / ADR-0012). | Additive: 5 new deletion/binding tests. Strengthens integrity. |
| Conflict C: `available_in_phase_0=True` → `False` (design §6.2) | No. The Phase 0 schema already forbids `True`; the design was unimplementable. Codex's live adapters already use `available_in_phase_0=False`. No consumer (registry, routers, tests) depended on `True`. | Corrective: makes the design implementable. |
| Conflict D: confirm UPDATE existing `9_Integrations.py`/`10_Settings.py` | No. The spec already said Replace/Extend; this makes "UPDATE existing, not create new" explicit. The actual pages exist. | Clarifying; no structural change. |

**What does NOT change:** Phase 0 contracts (immutable), all 11 adapter protocols,
the 11 stubs, `IntegrationCapability` schema, migrations 001–005, the `consume_atomic`
algorithm, the 9-step authorization sequence, the workflow_run_id binding rules, the
audit event set, the GitHubConfirmation gate, and the no-merge / no-autonomous-execution
boundaries.

**What is additive:** 4 Conflict A named tests, 5 Conflict B named tests (9 total new
named tests), the explicit `resolved_env` composition rule, the RESTRICT deletion
invariant, and explicit page-numbering notes.

---

## 6. Required test changes (all new named tests)

### Conflict A — 4 named subprocess tests (`tests/unit/test_mcp_client.py`)

- `test_mcp_subprocess_receives_explicit_env` — `asyncio.create_subprocess_exec`
  called with `env=resolved_env` exactly; `ClientSession` wraps the subprocess stdio;
  child receives only `resolved_env` (no parent-env merge). *(Renames/supersedes the
  old `test_mcp_subprocess_launched_with_explicit_env`.)*
- `test_mcp_subprocess_does_not_inherit_parent_secrets` — a secret present only in
  the parent/test environment is absent from the `env` passed to the spawned
  subprocess; the `stdio_client`/`get_default_environment()` parent-merge path is
  not used.
- `test_mcp_subprocess_terminated_on_timeout` — on `timeout_seconds` expiry, SIGTERM
  → 5 s grace → SIGKILL; `MCPTimeoutError` raised.
- `test_mcp_subprocess_cleanup_in_finally_block` — on every exit path (success,
  error, timeout) the subprocess is terminated in `finally`.

### Conflict B — 5 named deletion/binding tests
(`tests/unit/test_mcp_approval_repository.py` or `tests/unit/test_mcp_service.py`)

- `test_workflow_run_deletion_blocked_with_approved_mcp_approval` — deleting a run
  referenced by a non-consumed APPROVED `MCPApproval` raises `IntegrityError`
  (RESTRICT; `PRAGMA foreign_keys=ON`).
- `test_workflow_run_deletion_allowed_after_approval_consumed` — a CONSUMED approval
  does not block run deletion.
- `test_workflow_run_deletion_allowed_with_pending_approval` — a PENDING approval
  does not block run deletion.
- `test_null_to_null_match_rejected_for_originally_bound_approval` — defense-in-depth:
  an approval originally bound to run X is not invokable with
  `trusted_workflow_run_id = NULL` (reason `missing_workflow_context`);
  RESTRICT prevents the binding from being cleared in the first place.
- `test_cascaded_deletion_handles_mcp_approvals` — deleting a workflow whose runs
  still have APPROVED MCP approvals raises `IntegrityError`; deleting a workflow
  whose run approvals are all CONSUMED/PENDING proceeds.

All 9 are now present in `tasks.md` (Task I4 named-tests blocks + Task I7
required-test-cases block + Task I7 all-test-cases list) and in `requirements.md`
(REQ-S1.5 named subprocess tests + REQ-M2.1 deletion/binding tests).

---

## 7. Exact files modified

### `.kiro/specs/phase1-functional-orchestration/requirements.md`
- **Metadata** — version 1.5.4 → 1.5.5; branch → `feature/phase1-wave4-integration-execution`; base `756100d…`.
- **Version history** — added v1.5.5 (W4-CR) entry.
- **REQ-M1.2** — transport rewritten: explicit-environment subprocess + `ClientSession`;
  `stdio_client` dropped; transport contract bullets; M1.2.5/M1.2.6 updated.
- **REQ-M1.5** — isolation boundary expanded (`resolved_env` composition + system vars); added transport note; M1.5.5 strengthened; added M1.5.6/M1.5.7.
- **REQ-M2.1** — `workflow_run_id` FK description SET NULL → RESTRICT; M2.1.3 → RESTRICT; added M2.1.7 (deletion binding invariant); added 5 deletion/binding named tests.
- **REQ-S1.5** — isolation boundary + transport note; S1.5.1/S1.5.2/S1.5.4 updated; added S1.5.5/S1.5.6; added 4 subprocess named tests.
- **REQ-I1.6** — added page-numbering note (UPDATE existing `9_Integrations.py`).
- **REQ-U1.5** — added page-numbering note (EXTEND existing `10_Settings.py`).

### `.kiro/specs/phase1-functional-orchestration/design.md`
- **Metadata** — version 1.5.4 → 1.5.5; branch → wave4; base `756100d…`.
- **Version history** — added v1.5.5 (W4-CR) entry.
- **§3.7a (mcp_approvals SQL DDL)** — `workflow_run_id … ON DELETE SET NULL` → `RESTRICT`.
- **§3.7a (MCPApproval model)** — `ondelete="SET NULL"` → `"RESTRICT"` + comment.
- **§3.7 FK behaviors table** — added `MCPApproval.workflow_run_id RESTRICT` row; added deletion-invariant note.
- **§6.2 (live adapter interface contract)** — `available_in_phase_0=True` → `False`; documented `execution_mode`/`mode`/`stub=False` as the live/stub distinction.
- **§7.2 (MCPClient.call_tool docstring)** — rewritten to the explicit-environment subprocess + `ClientSession` transport with the W4-CR Conflict A decision rationale.
- **§7.5 (MCPApproval model notes comment)** — FK `ON DELETE SET NULL` → `RESTRICT`.
- **§7.6 (offline testing note)** — `stdio_client` not imported/called in production; `ClientSession` is the imported SDK interface.
- **§12.1 (page inventory)** — added Wave 4 page-numbering confirmation (UPDATE existing 9/10; no new pages).
- **ADR-0007** — Decision rewritten: explicit subprocess + `ClientSession`; `stdio_client` rejected with rationale; alternatives updated.

### `.kiro/specs/phase1-functional-orchestration/tasks.md`
- **Metadata** — version 1.5.4 → 1.5.5; branch → wave4; base `756100d…`.
- **Version history** — added v1.5.5 (W4-CR) entry.
- **Task I4 (migration 006 SQL)** — `sa.ForeignKey("workflow_runs.id", ondelete="SET NULL")` → `"RESTRICT"`.
- **Task I4 (key implementation notes)** — transport: `stdio_client` → explicit-environment subprocess + `ClientSession`; added `resolved_env` composition bullet; system-vars bullet.
- **Task I4 (acceptance criterion 6)** — strengthened to assert `asyncio.create_subprocess_exec` with `env=resolved_env` exactly + `ClientSession`; `stdio_client` not used.
- **Task I4 (named tests)** — added W4-CR Conflict A (4) and Conflict B (5) named-tests blocks.
- **Task I7 (required test cases)** — renamed `test_mcp_subprocess_launched_with_explicit_env` → `test_mcp_subprocess_receives_explicit_env`; added the other 3 Conflict A tests.
- **Task I7 (all test cases list)** — replaced old name with the 4 Conflict A tests; added the 5 Conflict B tests.
- **Task I7 (description)** — added page-numbering note (UPDATE existing `9_Integrations.py`/`10_Settings.py`).

### `docs/planning/phase1-roadmap.md`
- **Metadata** — version 1.5.3 → 1.5.5; status → "Wave 4 Specification Conflict Resolution Applied"; branch → wave4; base `756100d…`; date 2026-11-16.
- **Version history** — added v1.5.5 (W4-CR) entry.
- **Wave 4 completion gate** — test name `test_mcp_subprocess_launched_with_explicit_env` → `test_mcp_subprocess_receives_explicit_env`; added the 4 Conflict A + 5 Conflict B test names; added RESTRICT note; added page-numbering note.

### Created
- `docs/reports/phase1-wave4-spec-resolution.md` — this report.

### NOT modified (per strict boundaries)
- `src/**`, `tests/**`, `alembic/**`, `.github/workflows/**`, `pyproject.toml`,
  `.kiro/specs/foundation-and-architecture/**`, migrations 001–005, the
  `github_confirmations` migration 007 (Wave 5 — `workflow_run_id ON DELETE SET NULL`
  intentionally retained; out of scope). No commit, push, or PR. All Codex
  working-tree changes and untracked reports preserved.

---

## 8. Remaining blockers

None at the specification layer. The four conflicts are resolved and the spec trio
(+ roadmap) is internally consistent (see §9 verification).

Implementation-time notes for Codex (not blockers):
- `mcp` is not yet installed in any workspace venv; Wave 4 Task I4 must add
  `mcp>=1.0,<2.0` to `requirements/base.txt`, generate/commit a lockfile, and install
  it (REQ-M1.8). The transport decision does not require `stdio_client` to be
  importable in production — only `ClientSession` (and `anyio` memory streams, already
  a transitive dependency of the SDK) are used.
- `PRAGMA foreign_keys=ON` (REQ-DB1.3 / ADR-0012) MUST be active at runtime for
  `ON DELETE RESTRICT` to be enforced; this is already mandated and is the
  implementer's responsibility alongside `src/devflow_api/database.py`.
- The `alembic/env.py` `'connect'` handler (out of spec-correction scope) must also
  set `PRAGMA foreign_keys=ON` so migration-time FK behaviour matches runtime.

---

## 9. Cross-document consistency verification

1. **No conflicting MCP transport descriptions** — PASS. Every remaining
   `stdio_client` mention is in a W4-CR *rejection* context (version history,
   ADR-0007 "rejected", §7.2/§7.6/I4 notes "NOT used"). No document selects
   `stdio_client` as the transport.
2. **No `ON DELETE SET NULL` for `mcp_approvals.workflow_run_id`** — PASS. The
   mcp_approvals SQL DDL, model, FK table row, and §7.5 notes are all `RESTRICT`.
   Remaining `SET NULL` references are the legitimate non-MCP FKs
   (`Workflow.project_id`, `WorkflowAuditLog.workflow_run_id`, and the Wave 5
   `github_confirmations.workflow_run_id`, which is out of scope and intentionally
   retained) plus descriptive history/ADR text.
3. **Live adapter contract unambiguous** — PASS. No document instructs live adapters
   to set `available_in_phase_0=True`; §6.2 mandates `False`.
4. **Page numbering consistent between tasks.md and design.md §12.1** — PASS. Both
   reference `9_Integrations.py` and `10_Settings.py` as existing pages being
   UPDATEd; REQ-I1.6 and REQ-U1.5 carry matching notes.
5. **All 4 Conflict A test names present in tasks.md** — PASS.
   (`test_mcp_subprocess_receives_explicit_env`,
   `test_mcp_subprocess_does_not_inherit_parent_secrets`,
   `test_mcp_subprocess_terminated_on_timeout`,
   `test_mcp_subprocess_cleanup_in_finally_block`.)
6. **All 5 Conflict B test names present in tasks.md** — PASS.
   (`test_workflow_run_deletion_blocked_with_approved_mcp_approval`,
   `test_workflow_run_deletion_allowed_after_approval_consumed`,
   `test_workflow_run_deletion_allowed_with_pending_approval`,
   `test_null_to_null_match_rejected_for_originally_bound_approval`,
   `test_cascaded_deletion_handles_mcp_approvals`.)
7. **Migration 006 FK definition updated to RESTRICT** — PASS. `tasks.md` migration
   006 uses `ondelete="RESTRICT"`; `design.md` §3.7a SQL + model use `RESTRICT`.
8. **No weakening of MCP authorization** — PASS. REQ-M1.7, REQ-M2.2, REQ-M2.5,
   REQ-S1.1 unchanged; Conflict B strengthens the boundary (RESTRICT > SET NULL);
   Conflict A preserves env isolation.
9. **Version bumped to v1.5.5 and date 2026-11-16** — PASS (all four documents).
10. **No Wave 5 functionality introduced** — PASS. Migration 007 / GitHubConfirmation
    / RepositoryService untouched; their `workflow_run_id ON DELETE SET NULL` is
    intentionally retained (Wave 5 scope).
11. **No changes to migrations 001–005** — PASS. Only migration 006 (Wave 4) SQL was
    updated; 001–005 untouched.

---

## 10. Final verdict

**READY FOR CODEX — WAVE 4 SPECIFICATION RESOLVED.**

The Wave 4 security boundary is unambiguous. Codex may resume implementation
against Phase 1 v1.5.5 (`requirements.md`, `design.md`, `tasks.md`) and the updated
`docs/planning/phase1-roadmap.md`, building `MCPClient` per the explicit-environment
transport contract, `MCPApproval` per the `ON DELETE RESTRICT` FK, live adapters per
the `available_in_phase_0=False` contract, and the Streamlit Integrations/Settings
pages as in-place UPDATEs of `9_Integrations.py` / `10_Settings.py`.
