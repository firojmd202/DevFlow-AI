# Phase 1 Wave 3 — Specification Conflict Resolution

**Branch:** `feature/phase1-wave3-integration-execution`
**Wave 2 merge basis:** PR #10, commit `d3956da4f2543a6b498ffcb3d2b0cabcb162de59` (per `docs/reports/phase1-wave3-codex-report.md`)
**Spec version after correction:** 1.5.4 (was 1.5.3)
**Correction ID:** W3-RC (Wave 3 Response Contract)
**Mode:** Specification correction only. No `src/`, `tests/`, `alembic/`, `.github/workflows/`, or `pyproject.toml` modified. No commit, push, or PR.

---

## 1. Root cause

The Codex blocker report (`docs/reports/phase1-wave3-codex-report.md`) flagged a material ambiguity between two approved v1.5.3 clauses that govern the workflow-run detail response:

- **REQ-W1.5.4** (`.kiro/specs/phase1-functional-orchestration/requirements.md`):
  > "`GET /api/v1/workflow-runs/{run_id}` returns the full run including any associated `ApprovalRequest` records."

  "Any associated" + "full run" means *every* `ApprovalRequest` linked to the run, regardless of status — including resolved (`approved`/`rejected`) and `expired` records. The phrasing does not restrict to pending.

- **Design §11.3 — `WorkflowRunResponse`** (`.kiro/specs/phase1-functional-orchestration/design.md`):
  ```python
  class WorkflowRunResponse(BaseModel):
      ...
      pending_approvals: list[ApprovalResponse] = []
      ...
  ```
  The schema exposed exactly one approval collection, named `pending_approvals`, whose name and intent carry only pending approvals. There was no field for resolved/expired approvals.

**Why it blocks:** The divergence becomes observable immediately after a resolution. Once an `ApprovalRequest` is resolved (or expires), REQ-W1.5.4 still requires it to appear in the run-detail response ("any associated … records"), but §11.3's `pending_approvals` would exclude it by definition. Codex could not determine whether the detail response should expose only pending approvals (following the §11.3 field) or all approvals (following REQ-W1.5.4), because each reading invalidates the other clause. The report asked for a single, unambiguous public response contract and stopped Wave 3 (`A1`–`A5`) at the response-contract preflight.

**Answers to the four analysis questions:**
1. REQ-W1.5.4 requires exposing **all** associated approval records, including resolved and historical ones — "any associated `ApprovalRequest` records" is not status-scoped.
2. §11.3 `WorkflowRunResponse` exposed **only** `pending_approvals` — a single, implicitly pending-filtered collection. No field covered resolved/expired approvals.
3. The Wave 2 **model** supports querying both pending and resolved approvals for a run (`ApprovalRequest` has `workflow_run_id` FK, `status`, and `created_at`). The Wave 2 **repository** (`src/devflow_api/repositories/approval.py`) currently exposes only `list_pending()` (all runs, pending only) and `resolve()`; it has no per-run query. The data model supports the query; a read method was missing from the design.
4. Adding both an `approvals` (all) field and a `pending_approvals` (pending-only) field breaks **no** existing consumer: `schemas/workflow.py`, `routers/workflows.py`, and `routers/approvals.py` do not exist yet (they are Wave 3 `A1`/`A2` deliverables), and `grep` confirms `pending_approvals`/`WorkflowRunResponse` appear nowhere in `src/`. The Codex report confirms no endpoints or Streamlit changes were made. The change is therefore additive to a not-yet-implemented contract.

---

## 2. Final response contract

`WorkflowRunResponse` (design §11.3) now carries **two** approval fields. This is the single authoritative public contract for `GET /api/v1/workflow-runs/{run_id}` (and the run-list endpoints):

```python
class WorkflowRunResponse(BaseModel):
    id: int
    workflow_id: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    approvals: list[ApprovalResponse] = []          # NEW — all statuses
    pending_approvals: list[ApprovalResponse] = []  # backward-compat filter
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

| Field | Type | Contents | Ordering | Empty case |
|---|---|---|---|---|
| `approvals` | `list[ApprovalResponse]` | **Every** `ApprovalRequest` for the run, all statuses (`pending`, `approved`, `rejected`, `expired`) | `created_at` ascending (ties by `id`) | `[]` (never `null`) |
| `pending_approvals` | `list[ApprovalResponse]` | The subset of `approvals` where `status == "pending"` | same order as `approvals` | `[]` (never `null`) |

**Invariants:**
- `pending_approvals == [a for a in approvals if a.status == "pending"]` always holds (it is a derived filter of `approvals`, not an independent query).
- Both fields default to `[]`; a run with no approvals serialises both as an empty array, never `null`. The `= []` schema default enforces this.
- This is a **read-only projection**. Building the response does not mutate `ApprovalRequest.status`, `resolved_at`, or `resolved_by`; it does not reopen or restore resolved/expired approvals; it writes no audit log entry. The approval lifecycle (REQ-W1.6, design §5.2) and the `approval_requests` schema are unchanged.
- `approvals` includes the `expired` status — REQ-W1.5.4 says "any associated" with no status exclusion, and expired approvals are part of the run's history.
- Data source: the response is assembled in the service/router layer (following the existing `ProjectService` pattern) from the `WorkflowRun` (by id via `WorkflowRunRepository.get`) plus `ApprovalRepository.list_for_run(run_id)` (design §4.3). `pending_approvals` is derived in that layer by filtering the fetched list — no second query is required.

---

## 3. Specification changes

Spec trio bumped to **v1.5.4** with a W3-RC version-history bullet in each file. `docs/planning/phase1-roadmap.md` was intentionally left at v1.5.3 (planning overview; this micro-correction is recorded in the spec trio's v1.5.4 trail).

### `requirements.md`
- **REQ-W1.5.4** — refined to state the run-detail response exposes ALL associated `ApprovalRequest` records via an `approvals` field plus a `pending_approvals` pending-only subset, and that this is a read-only projection that does not change the approval lifecycle (cross-references REQ-W1.6).
- **W1.5.4a** (new) — `approvals: list[ApprovalResponse]` includes every status, ordered by `created_at` ascending; `pending_approvals: list[ApprovalResponse]` is the pending subset of `approvals`.
- **W1.5.4b** (new) — when a run has no approvals, both fields return `[]`, never `null`.
- **W1.5.4c** (new) — resolved approvals remain visible in `approvals`; reading them changes no `ApprovalRequest` field or audit entry; the lifecycle in REQ-W1.6 is unchanged.
- Version header → `1.5.4`, `Last Updated` → `2026-11-16`; W3-RC history bullet appended.

### `design.md`
- **§11.3 `WorkflowRunResponse`** — added `approvals: list[ApprovalResponse] = []` alongside the existing `pending_approvals`; appended the "Approval projection contract" note (types, ordering, empty-list semantics, read-only guarantee, data source).
- **§4.3 `ApprovalRepository`** — added `list_for_run(run_id) -> list[ApprovalRequest]` as the read-only data source (all statuses, `created_at` ascending, `[]` when none). This is additive to the existing `list_pending`/`resolve`; no existing method changes.
- **ADR-0013** (new) — records the dual-field decision and the rejected alternatives (replace `pending_approvals`; query-parameter toggle; exclude expired).
- **§19 traceability matrix** — `REQ-W1.5` design-section column updated from `§10.2, §9` to `§10.2, §9, §11.3`; summary text notes "run-detail exposes all approvals (W3-RC)".
- Version header → `1.5.4`, `Last Updated` → `2026-11-16`; W3-RC history bullet appended.

### `tasks.md`
- **Task A1 (Description)** — added a note that the run-detail endpoint assembles `WorkflowRunResponse` from the run plus `ApprovalRepository.list_for_run(run_id)` (design §4.3, §11.3), with `approvals` carrying all statuses ordered by `created_at` and `pending_approvals` the pending subset; `list_for_run` is a read-only addition to the Wave 2 repository with no migration.
- **Task A1 (Acceptance Criteria)** — added criterion 4: `GET /api/v1/workflow-runs/{run_id}` returns HTTP 200 with `WorkflowRunResponse` whose `approvals` contains every associated `ApprovalRequest` (all statuses) ordered by `created_at` ascending and whose `pending_approvals` contains only the pending subset; both `[]` (never `null`) when empty. Audit (→5), delete (→6), mypy (→7) renumbered.
- **Task A5 (Required test cases)** — added three named tests (see §5 below).
- Version header → `1.5.4`, `Last Updated` → `2026-11-16`; W3-RC history bullet appended.

**Files verified modified (git status):**
```
 M .kiro/specs/phase1-functional-orchestration/design.md
 M .kiro/specs/phase1-functional-orchestration/requirements.md
 M .kiro/specs/phase1-functional-orchestration/tasks.md
```
No other tracked files changed; no protected path touched.

---

## 4. Compatibility analysis

1. **`approvals` is additive.** It did not exist in any code (`grep` of `src/` for `pending_approvals`/`WorkflowRunResponse` returns nothing) and no router/schema file exists yet (`schemas/workflow.py`, `routers/workflows.py`, `routers/approvals.py` are absent — Wave 3 `A1`/`A2` deliverables). Adding a field to a not-yet-implemented schema cannot break a consumer.
2. **`pending_approvals` is preserved for backward compatibility.** It remains in §11.3 with its original semantics (pending-only). Any consumer (current spec readers, the Streamlit Workflows page "Approve" action for `waiting_approval` runs, or future code) that relied on the pending-focused contract is unaffected.
3. **Both fields together are additive.** No existing field is removed or renamed; no existing type changes. The new field is a superset view, and the retained field is a defined filter of it (`pending_approvals == approvals.filter(status == "pending")`).
4. **Wave 2 repository supports the query (no migration).** `ApprovalRequest` already has the `workflow_run_id` FK (non-null, `ON DELETE CASCADE`), `status`, and `created_at`. `ApprovalRepository.list_for_run(run_id)` is a new read query against existing columns — a code addition in Wave 3 `A1`, not a database migration. The Wave 2 `list_pending()` and `resolve()` methods and their tests are untouched.
5. **No migration required.** This is a response-schema change only. The `approval_requests` DDL (migration `004_add_approval_audit_tables`) is unchanged. The migration chain remains `001 → 002 → 003 → 004 → 005` through Wave 2; no new revision is introduced.
6. **Approval lifecycle unchanged.** `ApprovalService.resolve` (REQ-W1.6, design §5.2) still sets `status`, `resolved_at`, `resolved_by` and transitions the run (`approved → running`, `rejected → cancelled`). The response projection only *reads* those rows; it performs no status mutation, no restoration, and no audit writes. Resolved approvals stay resolved; the read does not reopen them.

**Conclusion:** the dual-field representation is a non-breaking, additive, read-only change. No compatibility or contract problem was found, so there is no reason to stop.

---

## 5. Test requirements

Three named tests were added to **Task A5** (`tests/unit/test_workflows_router.py`):

- **`test_workflow_run_response_includes_all_approvals`** — `GET /api/v1/workflow-runs/{run_id}` returns `approvals` containing every associated `ApprovalRequest` (both pending and resolved/expired), ordered by `created_at` ascending (REQ-W1.5.4a, design §11.3).
- **`test_workflow_run_response_pending_approvals_filters_resolved`** — the same response's `pending_approvals` contains only approvals with `status == "pending"` (excludes `approved`, `rejected`, `expired`) and equals the pending subset of `approvals` (REQ-W1.5.4a).
- **`test_workflow_run_response_empty_approvals_returns_empty_list`** — for a run with no approvals, both `approvals` and `pending_approvals` serialise as `[]`, not `null` (REQ-W1.5.4b).

These are unit/integration tests against the router+schema with an in-memory SQLite fixture (consistent with the Wave 3 test model and the existing `test_*_router.py` pattern). They are offline and require no network.

---

## 6. Remaining blockers

- **None for the specification.** The REQ-W1.5.4 ↔ §11.3 conflict is resolved; the public response contract is single and unambiguous.
- **Implementation work (not a spec blocker), to be done by Codex in Wave 3:** (a) add `ApprovalRepository.list_for_run(run_id)` to `src/devflow_api/repositories/approval.py` (read-only, no migration); (b) implement `WorkflowRunResponse` with both fields in `src/devflow_api/schemas/workflow.py` and assemble it in the run-detail route; (c) add the three named tests in Task A5.
- **Pre-existing, unchanged by this correction:** Task `A1` depends on `ApprovalResponse`, which is first delivered in Task `A2` (`schemas/approval.py`). This `A1`↔`A2` schema dependency already existed (the prior §11.3 referenced `ApprovalResponse` in `pending_approvals`); adding `approvals: list[ApprovalResponse]` introduces no new dependency. The implementer resolves the ordering as before (e.g., create `ApprovalResponse` within `A1` or implement `A1`/`A2` together).
- **Roadmap versioning:** `docs/planning/phase1-roadmap.md` remains at v1.5.3 by design (planning overview). The authoritative correction trail lives in the spec trio's v1.5.4 history bullets. A trivial roadmap bump can be done in a later housekeeping pass if desired; it is not a blocker.

---

## 7. Final decision

**READY_FOR_CODEX**

The blocking conflict between REQ-W1.5.4 and design §11.3 is resolved by establishing one unambiguous public response contract: `WorkflowRunResponse` now exposes **all** associated approval records via `approvals: list[ApprovalResponse]` (every status, ordered by `created_at` ascending) **and** preserves the pending-only view via `pending_approvals: list[ApprovalResponse]` for backward compatibility, with both fields returning empty lists (never `null`) when no approvals exist. The change is additive, read-only, requires no migration, and leaves the approval lifecycle untouched. Requirements, design (§11.3, §4.3, ADR-0013, traceability), and tasks (A1, A5) are updated to v1.5.4 with three new named tests. Wave 3 implementation may proceed.
