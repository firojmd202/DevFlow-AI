# DevFlow AI — Phase 2 Wave 3: Kiro Guided Handoff and Codex CLI Integration Design

**Version:** 1.0.0
**Status:** Draft — Ready for ChatGPT review
**Scope:** Phase 2 Wave 3 — Kiro Guided Handoff and Codex CLI Integration
**Branch:** `feature/phase2-wave3-coding-agent-integration`
**Base commit:** `ee57dc7` (Wave 2 merged, develop HEAD)
**Last Updated:** 2026-11-23
**Companion:** `requirements.md` (v1.0.0), `tasks.md` (v1.0.0).

---

## 1. Design Principles

Wave 3 extends Wave 1 and Wave 2 without structural change to their models or contracts. The layering is preserved:

```
Streamlit UI → APIClient (httpx) → FastAPI routers → Domain services → Repositories → SQLite
                                                   → WorkflowOrchestrator (Wave 1, reused)
                                                   → KiroHandoffExecutor (new, Wave 3)
                                                   → CodexCLIExecutor (new, Wave 3)
                                                   → IsolationGate (new, Wave 3)
                                                   → WorkspaceValidator (new, Wave 3)
                                                   → ReportValidator (new, Wave 3)
```

Ten rules govern Wave 3:

1. **Phase 0/1/Wave 1/Wave 2 contracts are immutable.** No existing `CHECK` constraint, enum, service signature, or test is changed. Wave 3 extensions are additive.
2. **Real coding-agent execution is blocked until Wave 6.** `IsolationGate` is fail-closed; a configuration flag alone does not bypass it.
3. **All imported report content is untrusted.** Report fields are data, never instructions. Validation is deterministic.
4. **Implementation authorization reuses Wave 1 `implementation_authorization`.** No new approval model is introduced.
5. **No automatic GitHub operations.** Wave 3 introduces no git write, commit, push, merge, or deploy path.
6. **No automatic cloud fallback.** Execution failures stay failed; no silent retry to a cloud provider.
7. **Workspace validation is explicit.** Approved workspace roots are operator-configured, not auto-discovered.
8. **Mock execution produces clearly labelled synthetic output.** It never claims to be real execution.
9. **Offline credential scanning preserved.** TruffleHog offline policy from Wave 2 continues to apply.
10. **Backward compatibility.** Phase 0/1/Wave 1/Wave 2 runs, approvals, and audit events continue to work unchanged after migration 010.

---

## 2. Architecture Overview

```
  Developer Machine — 127.0.0.1 only
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │  Browser :8501                                      CLI / Postman :8000                │
  │  ┌────────────────────────────────────┐    ┌─────────────────────────────────────────┐ │
  │  │ devflow-ui (Streamlit)              │    │ devflow-api (FastAPI/Uvicorn)            │ │
  │  │  Mode Selection                     │───▶│ Routers: /api/v1/coding-agent/...       │ │
  │  │  Kiro Handoff Screen                │    │ Services:                               │ │
  │  │  Kiro Prompt Export/Import          │    │   ExecutionPlanService (NEW)             │ │
  │  │  Verification Findings              │    │   CodingAgentAuthorizationService (NEW) │ │
  │  │  Spec Approval (reuse Wave 2)       │    │   KiroHandoffExecutor (NEW)              │ │
  │  │  Impl Authorization                 │    │   CodexCLIExecutor (NEW)                │ │
  │  │  Codex Prompt Export/Import         │    │   IsolationGate (NEW)                   │ │
  │  │  Isolation Status                   │    │   WorkspaceValidator (NEW)              │ │
  │  │  Impl Report Upload                 │    │   ReportValidator (NEW)                 │ │
  │  │  Artifact Preview                   │    │   ApprovalService (Wave 1, reused)      │ │
  │  │  Audit Timeline                     │    │   SpecificationApprovalService (W2)     │ │
  │  └────────────────────────────────────┘    │   WorkflowOrchestrator (Wave 1)         │ │
  │                                             │   ExecutorRegistry (Wave 1, extended)   │ │
  │                                             └──────────────────┬──────────────────────┘ │
  │                                                      ┌─────────▼──────────┐             │
  │                                                      │ devflow.db (SQLite) │             │
  │                                                      │ [Wave 1/2 tables]   │             │
  │                                                      │ + handoff_records   │             │
  │                                                      │ + execution_plans   │             │
  │                                                      │ + execution_attempts│             │
  │                                                      │ + report_artifacts  │             │
  │                                                      │ + capability_records│             │
  │                                                      └────────────────────┘             │
  │                                                                                          │
  │  External: Codex CLI binary (blocked in Wave 3; path prepared for Wave 6)               │
  └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. KiroHandoffExecutor

**Location:** `src/devflow_api/executors/kiro_handoff.py`

Implements the `Executor` Protocol (Wave 1 `src/devflow_api/executors/base.py`).

### 3.1 State Machine

```
handoff_created
    │  (prompt exported; user confirms receipt)
    ▼
awaiting_report  ───────────────────────────► expired
    │  (user submits report)                  (TTL exceeded)
    ▼
report_submitted
    │  (async validation begins)
    ▼
report_validated  ◄──── failed
    │  (validation OK; may have findings)
    ▼
correction_requested (optional; loop back to Wave 2 spec update)
    │  (findings resolved; new handoff)
    ▼  [or skip if no blockers]
[handoff terminal: validated / failed / expired / cancelled]
```

Terminal states: `validated`, `failed`, `expired`, `cancelled`, `correction_requested`.

### 3.2 Prompt Template Structure

The Kiro verification prompt is a structured text artifact containing:

```
=== KIRO VERIFICATION PROMPT ===
Schema Version: 1.0
Handoff ID: {handoff_id}
Specification Version ID: {specification_version_id}
Artifact Digest: {artifact_digest}
Selected Tasks: {task_ids_comma_separated}
Generated At: {iso8601_timestamp}

=== REQUESTED VERIFICATION CRITERIA ===
1. All stated requirements have clear, testable acceptance criteria.
2. Design is consistent with requirements; no undeclared dependencies.
3. Task list covers all requirements; every task maps to at least one requirement.
4. No security vulnerabilities are introduced by the specification.
5. All ADRs have decisions recorded; unresolved decisions are flagged.

=== SPECIFICATION ARTIFACTS ===
--- requirements.md ---
{requirements_content}
--- design.md ---
{design_content}
--- tasks.md ---
{tasks_content}

=== VERIFICATION REPORT FORMAT ===
Submit a JSON report conforming to the KiroVerificationReport schema (see design.md §6.1).
=================================
```

The template is reproducible: the same inputs always produce the same prompt text. The template does not include any instruction that could be misinterpreted as a command if echoed back.

### 3.3 KiroVerificationReport Schema

```python
class KiroFinding(BaseModel):
    finding_id: str                    # unique within report
    category: Literal["blocker", "major", "minor", "informational"]
    affected_artifact: str             # "requirements", "design", "tasks"
    description: str                   # max 4096 chars after sanitization
    suggested_fix: str | None          # max 2048 chars after sanitization

class KiroVerificationReport(BaseModel):
    schema_version: str                # "1.0"
    handoff_id: str
    specification_version_id: int
    artifact_digest: str               # must match handoff record
    verdict: Literal["PASS", "PASS_WITH_FINDINGS", "FAIL", "INCONCLUSIVE"]
    findings: list[KiroFinding]        # max 200 findings
    reviewer_notes: str | None         # max 8192 chars after sanitization
    reviewed_at: str                   # ISO 8601 UTC
```

### 3.4 Digest Binding

The `artifact_digest` in the handoff record is computed at handoff creation time from the concatenation of the three approved artifact texts (requirements + design + tasks), SHA-256 hashed. The report's `artifact_digest` field MUST equal the handoff record's `artifact_digest` for validation to pass. This prevents a report being accepted for a stale or modified specification version.

### 3.5 Expiry

`KIRO_HANDOFF_EXPIRY_SECONDS` (default 86400 — 24 hours) is added to `Settings`. The recovery service checks handoffs in `awaiting_report` state and transitions them to `expired` if `awaiting_since + KIRO_HANDOFF_EXPIRY_SECONDS < now()`. This is equivalent to the Wave 2 standalone approval TTL pattern.

---

## 4. CodexCLIExecutor

**Location:** `src/devflow_api/executors/codex_cli.py`

Implements the `Executor` Protocol.

### 4.1 Invocation Contract

The CodexCLIExecutor defines the contract for future Codex CLI invocation. In Wave 3, the executor supports only `mock` and `real_execution_blocked` modes.

```python
class CodexExecutionInput(ExecutorModel):
    specification_request_id: int
    specification_version_id: int
    artifact_digest: str
    task_ids: list[str]                # non-empty; no wildcard "*"
    repo_identity: str                 # canonical repository path or URL
    workspace_identity: str            # canonical absolute workspace path
    execution_mode: Literal["mock", "real_when_isolated"]
    deadline_at: datetime              # UTC; must be future
    canonical_execution_input_hash: str  # pre-computed by ExecutionPlanService

class CodexExecutionOutput(ExecutorModel):
    execution_attempt_id: str
    execution_mode: Literal["mock", "real", "blocked"]
    verdict: Literal["PASS", "PASS_WITH_WARNINGS", "FAIL", "INCOMPLETE", "BLOCKED"]
    task_results: list[TaskResult]
    changed_files: list[str]
    artifact_refs: list[str]
    authorization_ref: str             # links to consumed authorization record
    exit_code: int | None              # None for mock/blocked
    stdout_summary: str | None         # sanitized; None for mock/blocked
    completed_at: datetime
```

### 4.2 Execution Modes

**Mock mode (`execution_mode = "mock"`):**
- No subprocess is launched.
- No filesystem access outside approved workspace roots.
- No network calls.
- Produces a synthetic `CodexImplementationReport` with `execution_mode = "mock"` and `verdict = "PASS_WITH_WARNINGS"` (indicating synthetic output).
- All audit events include `"execution_mode": "mock"`.

**Real-execution-blocked mode (`execution_mode = "real_when_isolated"` with gate not met):**
- IsolationGate is checked first; if not met, return `real_execution_blocked` state.
- No subprocess launched.
- No authorization consumed.
- Error code: `ISOLATION_PREREQUISITES_NOT_MET`.

**Real mode (future, Wave 6):**
Invocation contract (documented here, not implemented in Wave 3):
```
codex --approval-mode full-auto --cwd {workspace} --model {model} {task_prompt}
```
Where `{task_prompt}` is derived from approved task descriptions. Exit code 0 = success. All subprocess stdout/stderr is captured, sanitized (credential patterns redacted), and stored as an artifact.

### 4.3 Structured Output

For real mode (future):
- Codex stdout is captured line-by-line.
- Credential patterns (`token`, `key`, `secret`, `password`, `credential`) are redacted before storage.
- A git diff is computed after execution to produce `changed_files`.
- Output is validated against `CodexImplementationReport` schema before acceptance.

### 4.4 CodexImplementationReport Schema

```python
class TaskResult(BaseModel):
    task_id: str
    status: Literal["completed", "failed", "skipped", "partial"]
    notes: str | None                  # max 2048 chars; sanitized

class TestSummary(BaseModel):
    total: int
    passed: int
    failed: int
    skipped: int
    coverage_percent: float | None

class CodexImplementationReport(BaseModel):
    schema_version: str                # "1.0"
    execution_attempt_id: str
    execution_mode: Literal["mock", "real"]
    verdict: Literal["PASS", "PASS_WITH_WARNINGS", "FAIL", "INCOMPLETE"]
    task_results: list[TaskResult]     # task IDs must be subset of authorized task_ids
    changed_files: list[str]           # max 1000 entries
    test_summary: TestSummary | None
    artifact_refs: list[str]           # max 100 entries
    completed_at: str                  # ISO 8601 UTC
```

---

## 5. IsolationGate

**Location:** `src/devflow_api/services/isolation_gate.py`

### 5.1 Fail-Closed Design

```python
class IsolationGateResult(BaseModel):
    status: Literal["not_configured", "prerequisites_not_met", "prerequisites_met"]
    unmet_prerequisites: list[str]
    checked_at: datetime

class IsolationGate:
    def __init__(self, settings: Settings) -> None:
        self._prerequisites = settings.ISOLATION_PREREQUISITES  # list[str], default []

    async def check(self) -> IsolationGateResult:
        if not self._prerequisites:
            return IsolationGateResult(
                status="not_configured",
                unmet_prerequisites=[],
                checked_at=datetime.now(UTC),
            )
        # Check each prerequisite against actual system state
        # Unrecognized prerequisite names → not_met (fail-closed)
        ...
```

A config flag alone (`CODEX_ISOLATION_OVERRIDE`) does NOT satisfy the gate. The gate checks actual system state against the named prerequisites. Recognized prerequisite names (defined in Wave 6): `os_job_objects_enabled` (Windows), `linux_namespaces_enabled`, `seccomp_enabled`, `filesystem_allowlist_active`, `network_egress_blocked`.

In Wave 3, no recognizable prerequisite names are implemented, so the gate always returns `not_configured` or `prerequisites_not_met`. This is intentional and correct for Wave 3.

### 5.2 Gate Check Sequence

```
Real execution request received
        │
        ▼
  IsolationGate.check()  ──► not_met ──► return ISOLATION_PREREQUISITES_NOT_MET
        │                                (no authorization consumed, no subprocess)
        ▼ met (Wave 6 only)
  WorkspaceValidator.validate()
        │
        ▼
  CodingAgentAuthorizationService.consume_authorization()
        │
        ▼
  [real execution — Wave 6 only]
```

---

## 6. WorkspaceValidator

**Location:** `src/devflow_api/services/workspace_validator.py`

### 6.1 Canonical Path Algorithm

```python
import os
from pathlib import Path

class WorkspaceValidator:
    def __init__(self, settings: Settings) -> None:
        self._approved_roots = [
            Path(r).resolve() for r in settings.APPROVED_WORKSPACE_ROOTS
        ]
        self._follow_symlinks = settings.WORKSPACE_FOLLOW_SYMLINKS  # default False

    def validate(self, raw_path: str) -> Path:
        # 1. Normalize separators (Windows backslash → forward slash)
        normalized = raw_path.replace("\\", "/")
        # 2. Resolve to canonical absolute path
        candidate = Path(normalized).resolve()
        # 3. Check for symlink (before or after resolution)
        if candidate.is_symlink() and not self._follow_symlinks:
            raise WorkspaceError("SYMLINKS_DISALLOWED", sanitize(raw_path))
        # 4. If following symlinks, re-resolve the target
        if self._follow_symlinks:
            candidate = candidate.resolve()
        # 5. Check against approved roots
        for root in self._approved_roots:
            try:
                candidate.relative_to(root)
                return candidate  # accepted
            except ValueError:
                continue
        raise WorkspaceError("PATH_NOT_IN_APPROVED_WORKSPACE", sanitize(raw_path))
```

Path traversal is prevented by `Path.resolve()` which eliminates all `..` components. Any path that resolves outside approved roots is rejected regardless of the number of `..` components in the input.

### 6.2 Git Identity Verification

After path validation:
1. Check for `.git` directory at `candidate / ".git"`.
2. If not present, raise `WorkspaceError("NOT_A_GIT_REPOSITORY")`.
3. Read `git remote get-url origin` (or parse `.git/config`) to extract the remote URL.
4. Compare against `execution_input.repo_identity`.
5. If mismatch, raise `WorkspaceError("REPOSITORY_IDENTITY_MISMATCH")`.
6. Record the current HEAD commit SHA as `baseline_commit` in the execution attempt record.

---

## 7. ReportValidator

**Location:** `src/devflow_api/services/report_validator.py`

### 7.1 KiroVerificationReport Validation

```
Validation steps (all deterministic, in order):
  1. Parse JSON — schema_validation_error on failure
  2. Validate against KiroVerificationReport Pydantic schema
  3. Check schema_version == "1.0"
  4. Check handoff_id matches handoff record
  5. Check specification_version_id matches handoff record
  6. Check artifact_digest matches handoff record — DIGEST_MISMATCH on failure
  7. For each finding: check category is one of the allowed enum values
  8. Sanitize all string fields (strip control chars, limit length)
  9. Check for prompt injection patterns; audit-log if found
  10. Record PASS verdict only if all checks pass
```

### 7.2 CodexImplementationReport Validation

```
Validation steps:
  1. Parse JSON — schema_validation_error on failure
  2. Validate against CodexImplementationReport Pydantic schema
  3. Check schema_version == "1.0"
  4. Check execution_attempt_id matches execution attempt record
  5. Check execution_mode matches the mode in the execution attempt — EXECUTION_MODE_MISMATCH
  6. For each task_result: check task_id is in the authorized task_ids — UNAUTHORIZED_TASK_IN_REPORT
  7. Sanitize all string fields
  8. Check for prompt injection patterns
  9. Record PASS verdict only if all checks pass
```

### 7.3 Untrusted Data Handling

Report content is treated as adversarial input at all times:
- No field is passed to `eval()`, `exec()`, `subprocess`, `os.system()`, or any equivalent.
- No field is passed to an AI provider prompt without hard delimiter wrapping (same pattern as Wave 2 MCP context).
- String fields are sanitized: strip `\x00`–`\x08`, `\x0b`–`\x0c`, `\x0e`–`\x1f`, truncate to `REPORT_FIELD_MAX_BYTES` (32768).
- JSON parsing uses `json.loads()` with no custom object hooks.

---

## 8. Implementation Authorization

Wave 3 reuses the Wave 1 `ApprovalService.request_bound_approval()` with `operation = "implementation_authorization"`. No new approval model is introduced.

### 8.1 CAS Binding

The authorization is bound to a canonical execution input hash computed as:

```python
import hashlib, json

def canonical_execution_input_hash(
    specification_version_id: int,
    artifact_digest: str,
    task_ids: list[str],
    repo_identity: str,
    workspace_identity: str,
    execution_mode: str,
) -> str:
    payload = json.dumps({
        "specification_version_id": specification_version_id,
        "artifact_digest": artifact_digest,
        "task_ids": sorted(task_ids),          # sort for canonicality
        "repo_identity": repo_identity,
        "workspace_identity": workspace_identity,
        "execution_mode": execution_mode,
    }, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

This hash is stored as `parameters_hash` in the `approval_requests` table alongside the `implementation_authorization` operation name. Any change to any input field produces a different hash, triggering `STALE_EXECUTION_INPUT`.

### 8.2 Expiry, Replay Prevention, Single-Use

- **Expiry:** `authorization_expires_at = created_at + APPROVAL_AUTHORIZATION_VALIDITY_SECONDS` (default 3600). Checked before consumption.
- **Single-use CAS:** `UPDATE approval_requests SET consumed_at = now() WHERE id = ? AND consumed_at IS NULL`. If 0 rows updated: `AUTHORIZATION_ALREADY_CONSUMED`.
- **Replay prevention:** Consumed authorization record is not deleted; `consumed_at` is set permanently. Presenting the same authorization ID twice returns `AUTHORIZATION_ALREADY_CONSUMED`.

### 8.3 Replacement Authorization

If the execution input changes (new spec version, different tasks), a new authorization is required. The old authorization (if unused) is superseded automatically when a new one is created for the same `workflow_step_run_id`. The old record is preserved for audit.

---

## 9. Execution Lifecycle

### 9.1 Full State Machine

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                WAVE 3 EXECUTION LIFECYCLE               │
                    └─────────────────────────────────────────────────────────┘

[HANDOFF_CREATED]
       │ prompt exported + user confirms
       ▼
[AWAITING_REPORT] ──────────────────────────────────────────► [EXPIRED]
       │ user submits report                                   (TTL exceeded)
       ▼
[REPORT_SUBMITTED]
       │ async validation starts
       ├─────────────────────────────────────────────────────► [FAILED]
       ▼ validation OK                                         (schema/digest/finding error)
[REPORT_VALIDATED]
       │ [optional] findings require correction
       ├──────────────────────────────────────────────────────► [CORRECTION_REQUESTED]
       │                                                        (loop back to Wave 2)
       ▼ findings OK / override recorded
[AWAITING_IMPL_AUTHORIZATION]
       │ user grants authorization
       ▼
[IMPL_PREPARATION]
       │ workspace validation, plan assembly
       ▼
[ELIGIBILITY_CHECK]
       │ IsolationGate + hash match + expiry check
       ├──── mock_mode ──────────────────────────────────────► [MOCK_EXECUTION]
       │                                                        → [COMPLETED]
       ├──── real_when_isolated + gate_blocked ──────────────► [REAL_EXECUTION_BLOCKED]
       │                                                        (stays pending, no auto-retry)
       └──── real_when_isolated + gate_met (Wave 6 only) ───► [EXECUTING]
                                                               → [COMPLETED] / [FAILED]
                                                               / [TIMEOUT] / [INTERRUPTED]

Any non-terminal state: user may cancel → [CANCELLED]
```

### 9.2 Durable Transitions

All state transitions are performed within `BEGIN IMMEDIATE` SQLite transactions using CAS (compare-and-swap on the current state). This matches the Wave 1 `WorkflowStepRun` CAS pattern.

### 9.3 Recovery (No AI Redispatch)

On application startup, `CodingAgentRecoveryService` runs:
1. Find all `execution_attempts` with status in `{"executing", "impl_preparation", "eligibility_check"}`.
2. Transition each to `interrupted`.
3. Emit an audit event for each.
4. Find all `handoff_records` with status `awaiting_report` and `awaiting_since + KIRO_HANDOFF_EXPIRY_SECONDS < now()`.
5. Transition each to `expired`.
6. Emit an audit event for each.

No execution is re-dispatched automatically. The user must start a new execution attempt after recovery.

### 9.4 Cancellation

Cancellation from any non-terminal state:
1. CAS: `UPDATE handoff_records SET status = 'cancelled', cancelled_at = now() WHERE id = ? AND status NOT IN ('validated','failed','expired','cancelled','correction_requested')`.
2. Update the associated authorization record to `cancelled` (if not already consumed).
3. Emit `execution_cancelled` audit event.

---

## 10. Data Model

### 10.1 New Tables (migration 010)

Migration: `010_add_coding_agent_integration` (chains from `009_add_ai_specification_generation`).

#### handoff_records

```sql
CREATE TABLE handoff_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    specification_request_id INTEGER NOT NULL REFERENCES specification_requests(id) ON DELETE CASCADE,
    specification_version_id INTEGER NOT NULL REFERENCES specification_versions(id),
    artifact_digest TEXT NOT NULL,
    task_ids_json TEXT NOT NULL,                -- JSON array of task ID strings
    prompt_text_hash TEXT NOT NULL,             -- SHA-256 of exported prompt
    actor_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'handoff_created'
        CHECK (status IN ('handoff_created','awaiting_report','report_submitted',
                          'report_validated','failed','expired','cancelled',
                          'correction_requested')),
    prompt_exported_at DATETIME,
    awaiting_since DATETIME,
    report_submitted_at DATETIME,
    validated_at DATETIME,
    failed_at DATETIME,
    expired_at DATETIME,
    cancelled_at DATETIME,
    raw_report_json TEXT,                       -- stored verbatim; treated as untrusted
    validation_error_json TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX idx_handoff_spec_version ON handoff_records(specification_version_id);
CREATE INDEX idx_handoff_status ON handoff_records(status);
CREATE INDEX idx_handoff_awaiting_since ON handoff_records(awaiting_since);
```

#### handoff_findings

```sql
CREATE TABLE handoff_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    handoff_record_id INTEGER NOT NULL REFERENCES handoff_records(id) ON DELETE CASCADE,
    finding_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('blocker','major','minor','informational')),
    affected_artifact TEXT NOT NULL,
    description TEXT NOT NULL,                  -- sanitized
    suggested_fix TEXT,                         -- sanitized
    override_justification TEXT,
    created_at DATETIME NOT NULL
);
CREATE INDEX idx_hf_handoff_id ON handoff_findings(handoff_record_id);
CREATE INDEX idx_hf_category ON handoff_findings(category);
```

#### execution_plans

```sql
CREATE TABLE execution_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    handoff_record_id INTEGER NOT NULL REFERENCES handoff_records(id),
    specification_version_id INTEGER NOT NULL REFERENCES specification_versions(id),
    artifact_digest TEXT NOT NULL,
    task_ids_json TEXT NOT NULL,
    repo_identity TEXT NOT NULL,
    workspace_identity TEXT NOT NULL,
    execution_mode TEXT NOT NULL CHECK (execution_mode IN ('mock','real_when_isolated')),
    canonical_execution_input_hash TEXT NOT NULL,
    authorization_id INTEGER REFERENCES approval_requests(id),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','authorized','consumed','cancelled','stale')),
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE UNIQUE INDEX idx_ep_hash ON execution_plans(canonical_execution_input_hash);
CREATE INDEX idx_ep_handoff ON execution_plans(handoff_record_id);
```

#### execution_attempts

```sql
CREATE TABLE execution_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_plan_id INTEGER NOT NULL REFERENCES execution_plans(id),
    workflow_run_id INTEGER REFERENCES workflow_runs(id),
    workflow_step_run_id INTEGER REFERENCES workflow_step_runs(id),
    execution_mode TEXT NOT NULL CHECK (execution_mode IN ('mock','real','blocked')),
    status TEXT NOT NULL DEFAULT 'handoff_created'
        CHECK (status IN ('handoff_created','awaiting_report','report_submitted',
                          'report_validated','awaiting_impl_authorization',
                          'impl_preparation','eligibility_check','mock_execution',
                          'real_execution_blocked','executing','completed',
                          'failed','cancelled','timeout','interrupted')),
    canonical_execution_input_hash TEXT NOT NULL,
    baseline_commit TEXT,
    deadline_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME,
    timed_out_at DATETIME,
    cancelled_at DATETIME,
    interrupted_at DATETIME,
    result_json TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
CREATE INDEX idx_ea_plan ON execution_attempts(execution_plan_id);
CREATE INDEX idx_ea_status ON execution_attempts(status);
CREATE INDEX idx_ea_step_run ON execution_attempts(workflow_step_run_id);
```

#### report_artifacts

```sql
CREATE TABLE report_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_attempt_id INTEGER NOT NULL REFERENCES execution_attempts(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('kiro_report','codex_report',
                                                          'diff','patch','test_report','log')),
    file_name TEXT NOT NULL,
    content_hash TEXT NOT NULL,                  -- SHA-256
    content_size_bytes INTEGER NOT NULL,
    storage_path TEXT,                           -- relative path within artifacts dir
    created_at DATETIME NOT NULL
);
CREATE INDEX idx_ra_attempt ON report_artifacts(execution_attempt_id);
CREATE INDEX idx_ra_hash ON report_artifacts(content_hash);
```

#### capability_records

```sql
CREATE TABLE capability_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at DATETIME NOT NULL,
    codex_cli_installed INTEGER NOT NULL CHECK (codex_cli_installed IN (0,1)),
    codex_cli_version TEXT,
    kiro_integration_type TEXT NOT NULL DEFAULT 'guided_handoff',
    isolation_status TEXT NOT NULL CHECK (isolation_status IN ('not_configured',
                                           'prerequisites_not_met','prerequisites_met')),
    unmet_prerequisites_json TEXT,
    created_at DATETIME NOT NULL
);
```

### 10.2 Migration 010

**File:** `alembic/versions/010_add_coding_agent_integration.py`

- **revision:** `010_add_coding_agent_integration`
- **down_revision:** `009_add_ai_specification_generation`
- **Upgrade:** Creates the 6 tables above with all indexes and constraints.
- **Downgrade:** Drops all 6 tables in reverse dependency order.
- **Reversibility:** Fully reversible. Does NOT alter any Phase 0/1/Wave 1/Wave 2 table.

---

## 11. API Route Table

All routes under prefix `/api/v1/coding-agent/`. All require `actor_id = Settings.LOCAL_OPERATOR_ID`.

| Method | Path | Request Schema | Response Schema | Success HTTP | Error Codes |
|--------|------|----------------|-----------------|--------------|-------------|
| GET | `/capabilities` | — | `CapabilitiesResponse` | 200 | — |
| GET | `/isolation-status` | — | `IsolationStatusResponse` | 200 | — |
| POST | `/handoffs` | `HandoffCreate` | `HandoffResponse` | 202 | 400, 409 |
| GET | `/handoffs/{id}` | — | `HandoffResponse` | 200 | 404 |
| POST | `/handoffs/{id}/export-prompt` | `ExportPromptRequest` | `ExportPromptResponse` | 202 | 404, 409 |
| POST | `/handoffs/{id}/submit-report` | `ReportSubmission` (file upload) | `ReportSubmissionResponse` | 202 | 404, 409 |
| GET | `/handoffs/{id}/validation-status` | — | `ValidationStatusResponse` | 200 | 404 |
| POST | `/handoffs/{id}/cancel` | `CancelRequest` | `CancelResponse` | 200 | 404, 409 |
| POST | `/execution-plans` | `ExecutionPlanCreate` | `ExecutionPlanResponse` | 201 | 400, 403, 409 |
| POST | `/execution-plans/{id}/authorize` | `AuthorizationRequest` | `AuthorizationResponse` | 202 | 404, 403, 409 |
| GET | `/execution-plans/{id}/authorization-status` | — | `AuthorizationStatusResponse` | 200 | 404 |
| POST | `/executions` | `ExecutionRequest` | `ExecutionResponse` | 202 | 400, 403, 409 |
| GET | `/executions/{id}` | — | `ExecutionStatusResponse` | 200 | 404 |
| POST | `/executions/{id}/cancel` | `CancelRequest` | `CancelResponse` | 200 | 404, 409 |
| POST | `/executions/{id}/submit-impl-report` | `ImplReportSubmission` | `ImplReportResponse` | 202 | 404, 409 |
| GET | `/executions/{id}/artifacts/{artifact_id}` | — | File download | 200 | 404, 403, 409 |
| GET | `/executions/{id}/audit` | — | `AuditHistoryResponse` | 200 | 404 |

**Error envelope** (synchronous): `{"error": "<sanitized>", "code": "<DOMAIN_CODE>"}` — consistent with Wave 2 REQ-W2.8.3.

**Async polling**: 202 responses include `{"record_id": N, "status_url": "/api/v1/coding-agent/.../{id}"}`.

---

## 12. Streamlit Page Design

### 12.1 Component Hierarchy

```
CodingAgentPage
  ├── ModeSelectionPanel
  │     ├── ManualModeCard
  │     ├── MockModeCard
  │     └── RealBlockedCard (shows unmet prerequisites)
  ├── IsolationStatusBanner
  ├── KiroHandoffPanel
  │     ├── PromptPreviewBlock (st.code)
  │     ├── ExportPromptButton (download)
  │     ├── HandoffStateIndicator
  │     └── ReportUploadWidget
  ├── VerificationFindingsPanel
  │     ├── FindingSummary (blocker/major/minor counts)
  │     └── FindingList (classified, with override UI)
  ├── SpecApprovalPanel (reuses Wave 2 component)
  ├── ImplAuthorizationPanel
  │     ├── AuthorizationSummary
  │     ├── ExpiryIndicator
  │     └── AuthorizeButton
  ├── CodexPromptPanel
  │     ├── ImplPromptPreviewBlock
  │     └── ExportImplPromptButton
  ├── ImplReportUploadPanel
  ├── ValidationResultsPanel
  └── AuditTimelinePanel
```

### 12.2 State Flow

```
[mode_not_selected] → [mode_selected]
       ↓
[handoff_not_started] → [handoff_created] → [awaiting_report]
       ↓
[report_submitted] → [report_validated]
       ↓
[awaiting_approval] → [approved]
       ↓
[awaiting_authorization] → [authorized]
       ↓
[impl_prompt_ready] → [awaiting_impl_report]
       ↓
[impl_report_submitted] → [impl_validated] → [completed]
```

### 12.3 Real-Execution-Blocked Display

When `isolation_status != "prerequisites_met"`:
- The "Real Execution" mode card is shown with a red "BLOCKED" badge.
- Unmet prerequisites are listed by name.
- The "Start Real Execution" button is replaced with a disabled "Waiting for Wave 6 isolation setup" indicator.
- No path in the UI simulates a successful real execution when blocked.

---

## 13. Architecture Decision Records

### ADR-W3-01: Manual + Automated Workflow Support

**Decision:** Wave 3 supports both manual workflow (user exports/imports all artifacts) and guided handoff (DevFlow AI manages state; user provides only report import). Both workflows share the same execution lifecycle and approval model. The manual workflow is a special case of guided handoff where the state machine waits for user input at each stage.

**Rationale:** Kiro has no stable programmatic API; the manual workflow is not a temporary workaround but the primary supported mode. Guided handoff provides structure around it. When a programmatic Kiro API becomes available, the executor can be extended without changing the approval or lifecycle model.

**Status:** Decided.

### ADR-W3-02: Kiro Handoff vs Programmatic Integration

**Decision:** `KiroHandoffExecutor` implements guided handoff only. No unsupported UI automation, undocumented IPC, or screen-scraping is used. The handoff creates a prompt, waits for a user-imported report, and validates the report.

**Rationale:** The Kiro IDE has no documented external automation API as of November 2026. Using unsupported interfaces would create fragile, unmaintainable integration with undefined behavior. If a stable API is published, an `AutomatedKiroExecutor` can be added alongside the handoff executor without changing the lifecycle model.

**Status:** Decided. No stable Kiro programmatic API exists; guided handoff is the only valid option.

### ADR-W3-03: Codex CLI Contract

**Decision:** The CodexCLIExecutor defines the invocation contract (flags, exit codes, output format) based on published Codex CLI documentation. The contract is verified against the installed CLI version at runtime before any real execution attempt. Wave 3 ships with mock and blocked modes only; the contract documents the real invocation path for Wave 6.

**Rationale:** Codex CLI is not installed on the current machine. Inventing flags or APIs that differ from the actual CLI would produce broken code. The contract is documented as a typed specification; Wave 6 implements it once the CLI is verified installed and isolation prerequisites are met.

**Status:** Decided. Codex CLI not installed; contract documented for Wave 6.

### ADR-W3-04: Implementation Authorization Binding

**Decision:** Reuse Wave 1 `ApprovalService` with `operation = "implementation_authorization"`. Bind to canonical execution input hash. No new approval model or table is introduced.

**Rationale:** Wave 1 already has the correct single-use, digest-bound, expiry-aware, CAS approval model. Duplicating it would create inconsistency and maintenance overhead. Reuse preserves the invariant that all approval records are in the `approval_requests` table.

**Status:** Decided.

### ADR-W3-05: Workspace Validation Strategy

**Decision:** Use `Path.resolve()` for canonical path computation. Approved workspace roots are operator-configured via `Settings.APPROVED_WORKSPACE_ROOTS`. Symlink following is disabled by default (`WORKSPACE_FOLLOW_SYMLINKS = false`). Git identity is verified by reading the remote URL from `.git/config`.

**Rationale:** `Path.resolve()` handles all `..` traversal on both Windows and Linux without custom parsing. Operator-configured roots avoid auto-discovery which could be exploited. Symlinks are off by default because symlink targets can escape approved roots in ways that are non-obvious to operators.

**Status:** Decided.

### ADR-W3-06: Report Trust Model

**Decision:** All imported report content is treated as adversarial data. Schema validation occurs first. String fields are sanitized (control characters stripped, length capped). No field is passed to AI prompts, eval(), exec(), or subprocess. Validation is deterministic and independent of the report's self-asserted verdict.

**Rationale:** A maliciously crafted Kiro or Codex report could contain prompt injection, embedded commands, or oversized payloads. Treating all imports as untrusted data and performing independent deterministic validation is the only safe approach.

**Status:** Decided.

### ADR-W3-07: Isolation Gate Enforcement

**Decision:** `IsolationGate` is fail-closed. With no prerequisites configured, real execution is blocked. A boolean configuration flag alone does not satisfy the gate. Prerequisite names are operator-configured and checked against actual system state. Unrecognized prerequisite names cause the gate to block (fail on unknown).

**Rationale:** A fail-open isolation gate would allow real coding-agent execution without safety guarantees. The cost of a false negative (failing to run) is much lower than the cost of a false positive (running without isolation). Configuration flags are not safety mechanisms; they are UI helpers.

**Status:** Decided.

### ADR-W3-08: Recovery and Cancellation

**Decision:** On restart, the recovery service transitions active executions to `interrupted` state. No execution is re-dispatched automatically. Cancellation uses CAS state transitions. Cancelled authorizations are marked cancelled rather than consumed, allowing a fresh authorization to be granted.

**Rationale:** Automatic re-dispatch could resume an execution in an inconsistent workspace state. Human review of interrupted executions is required before restart. This matches the Wave 1 recovery invariant (no auto-dispatch).

**Status:** Decided.

### ADR-W3-09: Persistence Strategy

**Decision:** Wave 3 adds migration 010 with 6 new tables. All new tables use `UTCTextDateTime` for timestamp columns. No existing table is altered. The migration is fully reversible.

**Rationale:** Additive-only migration strategy prevents regressions in Phase 0/1/Wave 1/Wave 2 functionality. Each wave owns its migration; the chain is 007 → 008 → 009 → 010.

**Status:** Decided.

### ADR-W3-10: GitHub Automation Deferral

**Decision:** Wave 3 introduces no GitHub write operations (commit, push, PR creation, merge). These are deferred to Wave 4. Wave 3 records git identity and baseline commit for audit purposes only.

**Rationale:** GitHub automation requires additional approval gates (Wave 4 `pr_creation_approval`, `merge_approval`). Introducing any git write in Wave 3 would bypass those gates. The permanent exclusion of auto-merge is maintained.

**Status:** Decided. All GitHub write operations deferred to Wave 4.

---

## 14. Security Architecture

### 14.1 Trust Boundary Diagram

```
 TRUSTED                          │                     UNTRUSTED
─────────────────────────────────│──────────────────────────────────
 DevFlow AI process (127.0.0.1)   │   User-imported reports
 SQLite database                  │   Kiro verification report (file)
 Operator configuration           │   Codex implementation report (file)
 Wave 1/2 approval records        │   Workspace files (future real exec)
 Audit log                        │   Codex CLI stdout/stderr (future)
                                  │   External AI provider responses
```

Every crossing from UNTRUSTED to TRUSTED requires:
1. Schema validation (Pydantic model)
2. String field sanitization (control chars, length)
3. Explicit field-by-field transfer (no `**untrusted_dict` expansion)
4. Digest/identity verification

### 14.2 Threat Mitigations

| Threat | Mitigation in Design |
|--------|---------------------|
| Prompt injection via report | `ReportValidator` sanitizes all string fields; never passes raw report to AI prompt |
| Malicious report claiming PASS | Deterministic validation checks (§7.1, §7.2) must all pass independently of report's self-asserted verdict |
| Arbitrary command execution | `IsolationGate` blocks all subprocess launch; `WorkspaceValidator` enforces approved roots |
| Path traversal | `Path.resolve()` eliminates `..`; approved root check prevents escape |
| Credential leakage | `SecretStr` on all credential fields; log sanitization (redact token/key/secret patterns) |
| Approval replay | Single-use CAS on `consumed_at` (§8.2) |
| Stale execution plan | Canonical hash check; `STALE_EXECUTION_INPUT` on mismatch (§8.1) |
| Duplicate execution | CAS on step run record (REQ-W3.4.5) |
| Symlink escape | Symlink policy in `WorkspaceValidator` (§6.1) |
| Config flag bypass of isolation | `IsolationGate` checks actual system state, not flags (§5.1) |
| Startup interruption | Recovery service marks executing → interrupted; no auto-redispatch (§9.3) |
| Unauthorized git ops | No git write in Wave 3 (ADR-W3-10) |
