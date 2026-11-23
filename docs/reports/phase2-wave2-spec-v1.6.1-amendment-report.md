# DevFlow AI — Phase 2 Wave 2: Spec v1.6.1 Amendment Report

**Branch:** `codex/phase2-wave2-group-d`
**HEAD:** `a14bd7c` (pre-commit baseline)
**Spec version:** v1.6.0 → v1.6.1
**Amendment commit date:** 2026-11-23 (Asia/Calcutta, `431b406`)
**Amendment authority:** User-approved via workflow session `wf_09580cc65549f924`

---

## 1. User Approval Record

Both amendments were approved by the project owner in this explicit statement: “I approve the following Wave 2 specification amendments: asynchronous HTTP contract with existing error envelope; 120-second focused test budget with a 60-second advisory target.”

### Amendment A — Asynchronous HTTP contract

User-approved changes:
- A1: HTTP 202 for accepted generation/review; connection not held open during inference.
- A2: HTTP 200 for all attempt states in poll response; failed attempt is not represented as HTTP failure.
- A3: Background domain error codes (`PROVIDER_UNAVAILABLE`, `PROVIDER_TIMEOUT`, `MALFORMED_OUTPUT`, `MCP_CONTEXT_FAILURE`, `PROVIDER_CANCELLED`, `AI_REVIEW_MALFORMED`) preserved in status response body.
- A4: Synchronous failures retain HTTP error statuses (400, 401, 403, 409); no synchronous provider probe added.
- A5: Cancellation: HTTP 200 `status=cancellation_requested` for active attempt; HTTP 200 `status=cancelled, error_code=PROVIDER_CANCELLED` via poll; HTTP 409 `TASK_NOT_CANCELLABLE` for absent/terminal attempt.
- A6: Error envelope `error` field (not `message`) preserved for wire compatibility; async status uses `error_code` + `error_message`.
- A7: W2.T11.9 updated to assert all 15 codes at correct lifecycle stage.

### Amendment B — Focused test runtime

User-approved changes:
- Mandatory limit: **under 120 seconds** (raised from 60 s).
- Advisory target: under 60 seconds (optimization target, not a release blocker).
- Reference environment documented: Windows, Python 3.12.10, pytest 9.2.0, SQLite in-memory, `--no-cov`, sequential execution.
- Existing tests, skip criteria, assertions, and 80% coverage threshold are unchanged.

---

## 2. Exact Changes — Diff Summary

### `requirements.md`

| Section | Change |
|---|---|
| Header | Version `1.6.0` → `1.6.1`; status updated; last-updated date updated; companion ref updated; v1.6.1 entry added to version history |
| Amendment Record (new) | Full amendment record section added: approval authority, Amendment A detail (A1–A6), Amendment B detail, affected requirements, affected design sections, affected acceptance criteria, unchanged invariants list |
| REQ-W2.8.2 | Rewritten: HTTP 202 explicit, HTTP 200 for all states, `poll_url` required, cancellation settlement returns HTTP 200 with `error_code`, `TASK_NOT_CANCELLABLE` returns HTTP 409; 5 acceptance criteria (W2.8.2.1–W2.8.2.5) |
| REQ-W2.8.3 | Rewritten: split into synchronous (10 codes) and asynchronous (6 codes) tables; HTTP statuses assigned correctly; 6 sub-requirements (W2.8.3.1–W2.8.3.6) added; `AI_REVIEW_MALFORMED` added to async table; full 15-code inventory preserved |

### `design.md`

| Section | Change |
|---|---|
| Header | Version `1.6.0` → `1.6.1`; status updated; last-updated date updated; companion refs updated; v1.6.1 entry added to version history |
| §4.3–4.4 (Error Response) | `ErrorResponse.message` renamed to `error` for wire compatibility; Amendment A6 note added |
| §7 (Synchronous vs. Async) | Trigger endpoint wording updated to explicit HTTP 202; poll endpoint rewritten — HTTP 200 for all states, error codes in response body; synchronous pre-acceptance errors listed; cancellation HTTP response updated (`error` not `message`); test reference environment block added (Amendment B) |

### `tasks.md`

| Section | Change |
|---|---|
| Header | Version `1.6.0` → `1.6.1`; status updated; last-updated date updated; companion refs updated; v1.6.1 entry added to version history |
| W2.T9.2 | Updated: HTTP 202 explicit, `poll_url` required, connection not held open |
| W2.T9.3 | Updated: HTTP 200 for all states, `error_code` and `error_message` in response body |
| W2.T9.5 | Updated: 15 codes verified at correct lifecycle stage (synchronous vs. async poll body) |
| W2.T9.6 | Updated: `error` field (not `message`) in HTTP 500 response |
| W2.T9.9 | Updated: `error` field in HTTP 409 `TASK_NOT_CANCELLABLE` response |
| W2.T9.10 | Updated: `error` field in HTTP 409 `TASK_NOT_CANCELLABLE` response |
| W2.T11.1 | Rewritten: mandatory 120 s limit, advisory 60 s, reference environment documented, 80% coverage floor preserved |
| W2.T11.9 | Rewritten: all 15 codes listed by lifecycle stage; full inventory preserved |

---

## 3. Affected Requirements

| ID | Amendment |
|---|---|
| REQ-W2.8.2 (W2.8.2.1–W2.8.2.5) | A1, A2, A5 |
| REQ-W2.8.3 (W2.8.3.1–W2.8.3.6) | A1, A2, A3, A4, A5, A6, A7 |
| W2.T11.1 | B |

## 4. Affected Design Sections

| Section | Amendment |
|---|---|
| Design §4.3 (Error Response) | A6 |
| Design §7 (Synchronous vs. Asynchronous Processing) | A1–A5, B |

## 5. Affected Acceptance Criteria

| ID | Amendment |
|---|---|
| W2.T9.2 | A1 |
| W2.T9.3 | A2 |
| W2.T9.5 | A7 |
| W2.T9.6 | A6 |
| W2.T9.9 | A5, A6 |
| W2.T9.10 | A5, A6 |
| W2.T11.1 | B |
| W2.T11.9 | A7 |

---

## 6. Unchanged Architecture and Security Controls

The following are explicitly unchanged by both amendments:

- Architecture layering: Streamlit → APIClient → FastAPI → Domain services → Repositories → SQLite
- MCP security controls: allowlist, `_authorized` context manager, `read_only` classification, JSON schema validation, argument bounds (REQ-W2.3.1–W2.3.6)
- Secret redaction: `SecretStr` on all credential fields; no secrets in logs, audit, or DB (REQ-W2.9.2)
- No arbitrary shell/filesystem access from HTTP input (REQ-W2.9.6)
- No wildcard MCP tool authorization (REQ-W2.3.3.2)
- Bounded context retrieval (REQ-W2.4.7)
- Prompt injection defense: untrusted content in delimited sections (REQ-W2.9.1)
- Approval atomicity and digest binding (REQ-W2.7.2, W2.7.3)
- 54 requirements, 14 tasks — counts unchanged
- 80% branch coverage floor — unchanged
- All 15 domain error codes preserved (10 synchronous + 5 async background + AI_REVIEW_MALFORMED)
- Wave 1 backward compatibility — unchanged

---

## 7. Implementation Compatibility Assessment

The v1.6.1 amendments are **backward-compatible with the Group D implementation**:

- The HTTP contract in the implementation (HTTP 202, HTTP 200 poll, `error_code` in body) already matches Amendment A. The Group D report explicitly noted the conflict between REQ-W2.8.3 (which assigned 503/504 to async failures) and the actual implementation. Amendment A resolves this conflict in favor of the implemented behavior.
- The W2.T11.1 timing: Group D reported focused test runs of 69.67 s and 75.48 s. The 120-second mandatory limit accommodates this. The current run on this branch measured 28.71 s (well within both the mandatory and advisory limits).
- No code changes are required by these amendments. The spec is now aligned with the implementation.

---

## 8. Validation Results

| Command | Exit Code | Result |
|---|---|---|
| `git status` | 0 | 3 spec files modified, Group D working-tree files preserved |
| `python -m ruff check src/ tests/` | 0 | All checks passed |
| `python -m mypy src/ --config-file pyproject.toml` | 0 | No issues found in 158 source files |
| `python -m pytest tests/ -k wave2 --no-cov -q --durations=15` | 0 | 113 passed, 581 deselected in **28.71 s** |
| `git diff --stat HEAD -- '.kiro/specs/'` | 0 | 3 files changed, 179 insertions, 54 deletions |

Focused test time of 28.71 s is well under both the 120-second mandatory limit and the 60-second advisory target.
