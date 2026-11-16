# DevFlow AI — Phase 1 Wave 5 Security Resolution Report

**Version:** 1.0
**Date:** 2026-11-16
**Branch:** feature/phase1-wave5-github-orchestration
**Base commit:** bceb9bab4328fe4ca5ed068a25fa9f541841f0ff
**Specification version after corrections:** v1.5.9
**Verdict:** WAVE 5 SECURITY CONTRACT RESOLVED — READY FOR CODEX

---

## 1. Root Cause of Each Conflict

### Conflict 1 — HTTP Outcome Classification

**Root cause:** v1.5.8 defined three outcomes (SUCCEEDED/FAILED/INDETERMINATE) but classified both 4xx and 5xx responses as FAILED. The key distinction — that 5xx responses are ambiguous because the server _may_ have received and acted on the request before returning an error — was not drawn. The implementation report (`.agents/tasks/phase1-wave5-implementation-report.md`) explicitly flagged this: *"A 5xx status by itself does not establish whether GitHub applied the write."*

**Effect:** An implementer following v1.5.8 would have treated HTTP 500 as a definitive failure (safe to retry immediately), when it should be INDETERMINATE (must verify GitHub state before retrying — the write may have happened).

### Conflict 2 — Canonical Parameter Binding

**Root cause:** v1.5.8 named `parameters_hash` and listed which parameters it covered (repo, branch name, base ref; or repo, title, body, base for PR) but did not define the exact canonical function: field names, JSON serialization options, normalization rules, or which function is used at issuance vs. consumption. Without a single authoritative canonical function, issuance and consumption could compute different hashes from the same logical parameters, or a client could manipulate parameters (e.g., changing `base_ref` or `head_ref`) and pass a matching hash only if the canonical function wasn't pinned.

**Effect:** Underspecification would have caused `parameters_hash` mismatches at consumption time (subtle bugs) or left open the possibility that parameter substitution after issuance was not reliably detected.

### Conflict 3 — Trusted Actor and Workflow Context

**Root cause:** v1.5.8 stated that `actor_id` comes from "server-side session context" but the actual FastAPI application (`main.py`, `config.py`) has no authenticated session system — no JWT, no cookie, no middleware-established identity. The gap between the spec's assumption and reality meant an implementer would not know where to source `actor_id`, risking one of two bad outcomes: (a) accept `actor_id` from the request body (spoofable), or (b) hardcode a string without documenting it as a configuration point.

Similarly, the spec mentioned `workflow_run_id` binding for confirmations without saying that Phase 1 has no server-side workflow session context, leaving it ambiguous whether workflow-bound confirmations should be supported or whether all Phase 1 operations are standalone.

**Effect:** Without resolution, the implementer would have needed to make a product-level architectural decision to unblock implementation.

---

## 2. Final Approved Decisions

### Decision 1 — HTTP Outcome Classification

**Approved:** 4xx responses are FAILED (definitively did NOT execute on GitHub). 5xx responses and all transport-level errors are INDETERMINATE (may or may not have executed on GitHub). This is the standard "server-received-but-status-unknown" pattern for distributed system idempotency.

| HTTP status or exception | Outcome | Key property |
|---|---|---|
| 2xx | SUCCEEDED | Definitively DID execute |
| 400, 401, 403, 404, 409, 422 | FAILED | Definitively did NOT execute |
| 500, 502, 503, 504 | INDETERMINATE | Execution status unknown |
| `httpx.TimeoutException` | INDETERMINATE | Execution status unknown |
| `asyncio.TimeoutError` | INDETERMINATE | Execution status unknown |
| `httpx.ConnectError` | INDETERMINATE | Execution status unknown |
| `httpx.ReadError` | INDETERMINATE | Execution status unknown |

Both FAILED and INDETERMINATE: confirmation stays USED; no restore; no auto-retry; `github_action_failed` audit event with `outcome` field.

### Decision 2 — Canonical Parameter Binding

**Approved:** One authoritative canonical payload function per operation. JSON serialization with `sort_keys=True` and `separators=(',', ':')` (no spaces). SHA-256 hex digest of UTF-8 encoding. Identical function at issuance and consumption. `repo_full_name` from server-side `RepositoryConfig`, never from client. See §3 for exact function definitions.

### Decision 3 — Trusted Actor and Workflow Context

**Approved:** `actor_id` for all Phase 1 GitHub operations is `Settings.LOCAL_OPERATOR_ID` (default `'local_operator'`). Never accepted from the request body. All Phase 1 operations are standalone (`workflow_run_id=None`). Workflow-bound confirmations are deferred to a future phase.

---

## 3. Exact Canonical Payloads

### Branch creation

```python
import json
import hashlib

def canonical_branch_create_payload(
    repo_full_name: str,   # lowercased, stripped
    branch_name: str,      # stripped (case preserved — Git refs are case-sensitive)
    base_ref: str,         # stripped (case preserved)
) -> str:
    """Canonical JSON for branch_create operations."""
    return json.dumps(
        {
            "operation": "branch_create",
            "repo_full_name": repo_full_name,
            "branch_name": branch_name,
            "base_ref": base_ref,
        },
        sort_keys=True,
        separators=(',', ':'),
    )

def hash_payload(payload: str) -> str:
    """SHA-256 hex digest of UTF-8 encoded canonical JSON."""
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
```

**Canonical JSON output example:**
```
{"base_ref":"develop","branch_name":"feature/x","operation":"branch_create","repo_full_name":"owner/repo"}
```

### Pull-request creation

```python
def canonical_pr_create_payload(
    repo_full_name: str,   # lowercased, stripped
    title: str,            # stripped
    body: str,             # '' if None/not provided; stripped
    head_ref: str,         # stripped (case preserved)
    base_ref: str,         # stripped (case preserved)
) -> str:
    """Canonical JSON for pr_create operations."""
    return json.dumps(
        {
            "operation": "pr_create",
            "repo_full_name": repo_full_name,
            "title": title,
            "body": body,
            "head_ref": head_ref,
            "base_ref": base_ref,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
```

### Serialization and normalization rules

| Rule | Detail |
|---|---|
| Serialization | `json.dumps(..., sort_keys=True, separators=(',', ':'))` |
| Hash algorithm | SHA-256 hex digest of UTF-8 encoding of the JSON string |
| `repo_full_name` | Lowercased before hashing (GitHub repos are case-insensitive) |
| `branch_name`, `base_ref`, `head_ref` | NOT lowercased (Git refs are case-sensitive) |
| All string fields | Stripped of leading/trailing whitespace before hashing |
| `body` | Empty string `''` if `None` or not provided |
| `repo_full_name` source | Server-side `RepositoryConfig` (looked up by `repo_config_id`), never client-supplied |
| Canonical function | Identical at `issue_confirmation` (issuance) and `consume_atomic` (consumption) |
| Immutability | Once issued, the `parameters_hash` is immutable; any parameter change → `ConfirmationMismatchError` |

---

## 4. HTTP Failure and Reconciliation Rules

### SUCCEEDED
- GitHub API returns HTTP 2xx with response body confirming the operation.
- `GitHubConfirmation.status = USED`, `used_at = now`.
- Audit: `github_action_executed`, then `branch_created` or `pr_created`.

### FAILED (definitive)
- HTTP 400, 401, 403, 404, 409, 422.
- Definitively did NOT execute on GitHub.
- `GitHubConfirmation.status` remains `USED` — not restored.
- Audit: `github_action_failed` with `outcome='FAILED'`.
- New confirmation required for retry (safe to retry immediately — operation did not happen).

### INDETERMINATE (ambiguous)
- HTTP 500/502/503/504 OR `httpx.TimeoutException` / `asyncio.TimeoutError` / `httpx.ConnectError` / `httpx.ReadError`.
- May or may not have executed on GitHub.
- `GitHubConfirmation.status` remains `USED` — not restored.
- Audit: `github_action_failed` with `outcome='INDETERMINATE'`.
- **No automatic retry.**
- User must verify GitHub state manually before issuing a new confirmation.
- Policy: *"DevFlow AI cannot guarantee exactly-once execution. Verify GitHub state before retrying."*
- If user reconciles and operation succeeded: do NOT issue a new confirmation for that resource.
- If operation did not complete: issue a new `GitHubConfirmation` and get it approved for the retry.

### Reconciliation flow

```
User: POST /api/v1/github-confirmations → receives confirmation_id
User: POST /api/v1/repositories/{id}/branches (confirmation_id=...)
  → RepositoryService: load → validate → consume_atomic (status→USED) → GitHubAdapter.create_branch
  → SUCCEEDED:       log github_action_executed → log branch_created → return 201
  → FAILED (4xx):    log github_action_failed(outcome=FAILED) → return 502
  → INDETERMINATE:   log github_action_failed(outcome=INDETERMINATE) → return 502
  → User checks GitHub manually → if branch exists: do not retry
                                → if branch missing: new confirmation → retry
```

---

## 5. Trusted Actor and Workflow-Context Contract

### Settings.LOCAL_OPERATOR_ID

```python
# src/devflow_core/config.py
class Settings(BaseSettings):
    ...
    LOCAL_OPERATOR_ID: str = "local_operator"
    GITHUB_CONFIRMATION_TTL_SECONDS: int = 600
```

### Actor identity rules

- `actor_id` for all Phase 1 GitHub operations = `settings.LOCAL_OPERATOR_ID`.
- Resolved by the application layer from `Settings` before any service call.
- **Never accepted from the HTTP request body, query parameters, or any client-supplied field.**
- Stored in `GitHubConfirmation.actor_id` at issuance time.
- Verified at consumption time (confirmation's `actor_id` must match the current actor).

### Standalone operation policy

- Phase 1 is explicitly local-first with a single operator.
- There is no multi-user authentication system in Phase 1.
- All Phase 1 GitHub operations are **standalone**: `workflow_run_id = None`.
- Workflow-bound GitHub operations (confirmations issued with a specific `workflow_run_id`) are deferred to a future phase when server-side session context is available.

Policy statement: *"Phase 1 GitHub operations are standalone (workflow_run_id=None). Workflow-bound GitHub operations are deferred to a future phase when server-side session context is available."*

### Deployment assumptions

| Assumption | Detail |
|---|---|
| Single local operator | No multi-user access control in Phase 1 |
| No network exposure | Binds exclusively to `127.0.0.1` |
| No multi-user auth | No JWT, session, or cookie middleware in Phase 1 FastAPI app |
| Operation-level gate | `GitHubConfirmation` is an operation-level authorization gate, not user authentication |
| Physical access assumed | Policy: *"GitHubConfirmation is an operation-level authorization gate, not a user authentication mechanism. It assumes the operator has physical access to the local instance."* |

---

## 6. Updated Acceptance Criteria (G1–G5 Key Changes)

### G1 — Migration 007 (verified correct — no change required)

| Criterion | Status |
|---|---|
| `status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED','EXPIRED','USED'))` column | ✓ already in v1.5.8 |
| BEFORE DELETE trigger `trg_workflow_runs_before_delete_expire_github_confirmations` in `upgrade()` | ✓ already in v1.5.8 |
| `DROP TRIGGER IF EXISTS` in `downgrade()` | ✓ already in v1.5.8 |
| `down_revision = "006_add_mcp_approvals"` | ✓ already in v1.5.8 |
| `consume_atomic` uses `WHERE status='ISSUED'` | ✓ already in v1.5.8 |

### G2 — RepositoryService (new requirements from W5-SR)

- `Settings.LOCAL_OPERATOR_ID` added to `Settings`; used as `actor_id` source.
- Canonical payload functions defined and specified (branch + PR).
- `consume_atomic` SQL updated: `WHERE id = ? AND status = 'ISSUED' AND expires_at > ?` (was `WHERE id = ? AND used_at IS NULL`).
- HTTP outcome classification: 4xx=FAILED, 5xx/transport=INDETERMINATE.
- `github_action_failed` audit event carries `outcome` field (`'FAILED'` or `'INDETERMINATE'`).

### G5 — New named tests added (26 total new from W5-SR; total W5 test count: 36+ named)

W5-SR adds 16 new named tests in three groups: HTTP outcome (6), canonical binding (6), actor/workflow context (4).

---

## 7. Named Regression Tests

All tests below are new from this resolution (W5-SR). Tests from W5-GC (G1.4.15–G1.4.24) are unchanged.

### HTTP outcome classification tests (REQ-G1.4.25–G1.4.30)

| Test name | Conflict | What it verifies |
|---|---|---|
| `test_http_5xx_treated_as_indeterminate` | Conflict 1 | GitHub HTTP 500 → INDETERMINATE; `github_action_failed(outcome='INDETERMINATE')`; confirmation USED |
| `test_http_4xx_treated_as_failed` | Conflict 1 | GitHub HTTP 422 → FAILED; `github_action_failed(outcome='FAILED')`; confirmation USED |
| `test_timeout_treated_as_indeterminate` | Conflict 1 | `httpx.TimeoutException` → INDETERMINATE; confirmation NOT restored |
| `test_indeterminate_outcome_does_not_restore_confirmation` | Conflict 1 | Confirmation stays USED after INDETERMINATE; no rollback, no status reset |
| `test_new_confirmation_required_after_indeterminate` | Conflict 1 | Re-submitting USED confirmation after INDETERMINATE → HTTP 409 |
| `test_reconciliation_documented_before_retry` | Conflict 1 | `RepositoryService` docstring contains the policy statement about verifying GitHub state |

### Canonical parameter binding tests (REQ-G1.4.31–G1.4.36)

| Test name | Conflict | What it verifies |
|---|---|---|
| `test_canonical_hash_deterministic` | Conflict 2 | Same inputs always produce same hash |
| `test_mismatched_base_ref_rejected` | Conflict 2 | Different `base_ref` at consumption → `ConfirmationMismatchError` |
| `test_mismatched_pr_head_rejected` | Conflict 2 | Different `head_ref` at consumption → `ConfirmationMismatchError` |
| `test_mismatched_repo_rejected_canonical` | Conflict 2 | Different `repo_full_name` at consumption → rejected |
| `test_canonical_hash_mismatch_rejected` | Conflict 2 | Any parameter change → `ConfirmationMismatchError` |
| `test_repo_identity_from_server_config_not_client` | Conflict 2 | `repo_full_name` comes from `RepositoryConfig`, not client field |

### Trusted actor and workflow-context tests (REQ-G1.4.37–G1.4.40)

| Test name | Conflict | What it verifies |
|---|---|---|
| `test_actor_id_from_settings_not_request_body` | Conflict 3 | `Settings.LOCAL_OPERATOR_ID` used; request body `actor_id` ignored |
| `test_actor_id_mismatch_rejected` | Conflict 3 | Confirmation with different `actor_id` → `ConfirmationMismatchError` |
| `test_standalone_operation_allowed_without_workflow_context` | Conflict 3 | `workflow_run_id=None` permitted for all Phase 1 operations |
| `test_workflow_run_mismatch_rejected` | Conflict 3 | Confirmation with `workflow_run_id=X` cannot be consumed for `workflow_run_id=Y` |

---

## 8. Files Modified

| File | Section | What changed |
|---|---|---|
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | Version header, history | Bumped to v1.5.9; added W5-SR history entry |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-G1.4 — GitHub execution outcomes | Refined 4xx=FAILED / 5xx+transport=INDETERMINATE with explicit HTTP codes and exception types; `outcome` field on audit event |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-G1.4 — NEW: Local operator identity | Added `Settings.LOCAL_OPERATOR_ID` field requirement |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-G1.4 — NEW: Canonical parameter binding | Added exact Python canonical payload functions, normalization rules, repo identity rule |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-G1.4 — NEW: Trusted actor and workflow context | Added `Settings.LOCAL_OPERATOR_ID` as actor source; standalone operation policy; deployment assumptions |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-G1.4 — Security contract | Updated rule 1 (actor_id from Settings.LOCAL_OPERATOR_ID), rule 3 (canonical payload functions), rule 5 (standalone policy), rule 11 (outcome field on audit event) |
| `.kiro/specs/phase1-functional-orchestration/requirements.md` | REQ-G1.4 — Acceptance criteria | Added G1.4.25–G1.4.40 (16 new named tests) |
| `.kiro/specs/phase1-functional-orchestration/design.md` | Version header, history | Bumped to v1.5.9; added W5-SR history entry |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §8.2 RepositoryService | Restructured into §8.2a (canonical payloads), §8.2b (HTTP outcome classification), §8.2c (trusted actor contract), §8.2d (RepositoryService interface) |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §8.2a NEW | Authoritative canonical payload Python functions; normalization rules; repo identity rule |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §8.2b NEW | HTTP outcome table (SUCCEEDED/FAILED/INDETERMINATE); reconciliation policy |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §8.2c NEW | `Settings.LOCAL_OPERATOR_ID`; standalone operation policy; deployment assumptions |
| `.kiro/specs/phase1-functional-orchestration/design.md` | §8.2d NEW | RepositoryService interface with refined validation sequence, actor_id source, outcome handling |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Version header, history | Bumped to v1.5.9; added W5-SR history entry |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task G2 key implementation notes | Added actor_id source (Settings.LOCAL_OPERATOR_ID); canonical payload functions; HTTP outcome classification; updated validation sequence; updated consume_atomic SQL |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task G5 required test cases | Added 16 new W5-SR named tests in three groups |
| `.kiro/specs/phase1-functional-orchestration/tasks.md` | Task G5 acceptance criteria | Added criteria 13–16 for W5-SR tests |
| `docs/planning/phase1-roadmap.md` | Version header, history | Bumped to v1.5.9; added W5-SR history entry |
| `docs/planning/phase1-roadmap.md` | Wave 5 completion gate | Added Settings.LOCAL_OPERATOR_ID requirement; standalone policy; 16 new W5-SR test groups |
| `docs/planning/phase1-roadmap.md` | Security Summary table | Updated Wave 5 rows with W5-SR canonical binding, actor contract, and outcome classification details |

**Files NOT modified (strict boundaries respected):**
- `src/` — no application code
- `tests/` — no test files
- `alembic/` — no migration files
- `.github/workflows/` — no CI changes
- `pyproject.toml` — unchanged
- `.kiro/specs/foundation-and-architecture/` — Phase 0 spec, untouched
- `alembic/versions/006_add_mcp_approvals.py` — migration 006, untouched

---

## 9. 10-Check Consistency Results

| # | Check | Status |
|---|---|---|
| 1 | FAILED vs INDETERMINATE definition consistent across requirements, design, tasks | **FIXED** (W5-SR: 4xx=FAILED, 5xx+transport=INDETERMINATE, explicit in all three files) |
| 2 | Canonical branch payload (fields, serialization, hash) matches across requirements, design, tasks | **FIXED** (W5-SR: exact Python functions in requirements §REQ-G1.4; design §8.2a; tasks G2 notes) |
| 3 | Canonical PR payload matches across requirements, design, tasks | **FIXED** (W5-SR: same canonical functions spec in all three locations) |
| 4 | Issuance and consumption use identical binding rules (same canonical function) | **FIXED** (W5-SR: explicit rule in requirements, design §8.2a, tasks G2 notes) |
| 5 | actor_id source explicitly defined as Settings.LOCAL_OPERATOR_ID in requirements and design | **FIXED** (W5-SR: requirements §REQ-G1.4, design §8.2c both specify Settings.LOCAL_OPERATOR_ID) |
| 6 | Standalone operation policy documented (workflow_run_id=None for Phase 1) | **FIXED** (W5-SR: explicit standalone policy in requirements, design §8.2c, tasks G2, roadmap) |
| 7 | Migration 007: status column, trigger, down_revision all correct | **PASS** (already correct in v1.5.8; verified unchanged) |
| 8 | All named negative tests listed consistently in requirements.md and tasks.md | **FIXED** (W5-SR: G1.4.25–G1.4.40 in requirements; matching tests in tasks G5) |
| 9 | No automatic merge functionality introduced | **PASS** (no merge endpoint; `test_no_automatic_pr_merge` / REQ-G1.4.22 / REQ-G1.5.5 unchanged) |
| 10 | All modified files at v1.5.9 | **PASS** (requirements.md, design.md, tasks.md, phase1-roadmap.md all at v1.5.9) |

---

## 10. Remaining Blockers

None. All three security-sensitive conflicts have been resolved at the specification level. The decisions are documented, the canonical functions are pinned, and the named regression tests are specified. No architectural decision is required beyond what is documented here.

The implementer (Codex) may proceed with Wave 5 implementation using the resolved v1.5.9 specification.

---

## 11. Final Verdict

**WAVE 5 SECURITY CONTRACT RESOLVED — READY FOR CODEX**

All four specification files (`requirements.md`, `design.md`, `tasks.md`, `docs/planning/phase1-roadmap.md`) are at version **v1.5.9** and are mutually consistent. The three security-sensitive conflicts reported by Codex have been resolved: (1) HTTP outcome classification corrects the FAILED/INDETERMINATE boundary (4xx=FAILED; 5xx+transport=INDETERMINATE); (2) canonical parameter binding pins the exact Python functions, serialization format, and normalization rules used identically at issuance and consumption; (3) the trusted actor contract defines `Settings.LOCAL_OPERATOR_ID` as the `actor_id` source and explicitly declares all Phase 1 GitHub operations as standalone (`workflow_run_id=None`). Sixteen new named regression tests (G1.4.25–G1.4.40) cover all three conflict areas. All 10 consistency checks pass or have been fixed. No application code, migration files, or migration 006 were modified.
