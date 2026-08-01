# Phase 6 — Quality, Duplicate, Conflict & Approval Integration

Status: complete. Schema version 26 -> 27 (migration
`027_data_studio_phase6_quality_duplicate_conflict_approval`).

A unified governance layer sitting *above* six existing,
independently-owned entity systems (`document_pages`,
`manual_data_records`, `semantic_chunks`, `structured_record_candidates`,
`document_candidates`, `dataset_records`) — never a replacement for any
of their own lifecycles, quality scoring, or duplicate/conflict
detection. See
[phase6_quality_duplicate_conflict_approval_plan.md](phase6_quality_duplicate_conflict_approval_plan.md)
for the pre-implementation baseline audit and architectural decisions.

## 1. Architecture

Three existing, structurally different quality/blocking conventions
were found at baseline: `backend.services.dataset_quality`'s 7
dimensions + a `severity` literal including `'blocking'`;
`core_model.manual_data.quality`/`core_model.semantic_chunk.quality`'s
8 dimensions + a separate `blocking_issues: list[str]` array. Phase 6
adds a fourth, explicit shape (`severity` independent of
`is_blocking`/`blocking_targets`) and a `GovernanceQualityAdapterService`
whose only job is to normalize the other three into it — never
recomputing a score a subsystem already owns, and never fabricating a
canonical dimension a source system doesn't measure (left `None`
instead).

No `rag_candidate` or "training candidate" phantom entity was invented:
a RAG candidate is already a `structured_record_candidates` row with
`record_type='rag_chunk'`; a training candidate is already a
`dataset_record`. The six real entity types are the only
`entity_type` values the schema accepts.

Duplicate/conflict detection reuses the *existing* pairwise detectors
(`core_model.manual_data.duplicates`, `core_model.semantic_chunk.duplicates`,
`ManualDataQualityService.check_duplicates()`,
`SemanticChunkQualityService.duplicate_check()`,
`StructuredRecordCandidateService.conflict_check()`) verbatim — this
phase's only new capability is *persisting* a match as an assignable,
resolvable group instead of a one-off API response.

## 2. Schema (migration 027)

All additive; no existing table's columns, CHECK constraints, or
triggers changed.

| Table | Purpose |
|---|---|
| `governance_review_items` | The unified queue: one row per review condition on one polymorphic `(entity_type, entity_public_id)` entity. A partial unique index (`WHERE status NOT IN ('resolved','rejected','archived')`) allows exactly one *open* item per entity while letting historical resolved/rejected/archived rows accumulate. |
| `governance_review_issues` | Normalized issues: explicit `severity` + independent `is_blocking`/`blocking_targets_json` — blocking is never inferred from severity alone. Append-only for its fact columns via a column-scoped trigger that still allows `resolved_at` to be set later. |
| `governance_duplicate_groups` / `_members` | Persisted duplicate groups (`exact`/`normalized`/`source_locator`/`export_duplicate`) with membership. |
| `governance_conflict_groups` / `_members` | Persisted conflict groups (`dictionary_sense`/`answer`/`translation`/`source_fact`/`chunk_overlap`/`chunk_gap`/`revision`/`classification`). |
| `governance_resolutions` | Append-only record of every duplicate/conflict resolution action, always requiring a non-empty reason. |
| `governance_target_approvals` | Per-`(entity, target_use)` decision, fully append-only (a re-decision is always a new row; "current" = latest row per key) — supports override history and expiry without ever mutating a past decision. |
| `governance_review_events` | Append-only domain event log backing a review item's own History tab. |

## 3. Issue taxonomy and severity

20 stable `issue_category` values map 1:1 onto issue codes the *existing*
subsystems already produce (`core_model.data_governance.issue_taxonomy`
is a lookup table, not a new detector) — it raises rather than guesses
for an unmapped code, so an issue this phase has never seen is never
silently mis-filed.

`severity` (`info`/`warning`/`error`/`critical`) is independent of
`is_blocking`/`blocking_targets`: a critical issue is not necessarily
blocking, and a blocking issue can be scoped to specific target uses
(`blocking_targets`) so it never blocks an unrelated use.

## 4. Quality normalization

`core_model.data_governance.quality_adapter` maps each subsystem's own
dimensions into 8 canonical buckets (`language, meaning, factual,
source, structure, integrity, format, uniqueness`) via an explicit
per-source-system bucket table; `overall_score` is always the
subsystem's own reported score, verbatim, never re-averaged from a
subset of buckets. `GovernanceQualityService.assess()` calls the
entity's own existing quality assessor
(`DatasetQualityService`/`ManualDataQualityService`/
`SemanticChunkQualityService`), normalizes the result, and — only when
blocked — opens (or reuses) a `governance_review_items` row and creates
one `governance_review_issues` row per blocking code, with priority
computed deterministically from severity/blocking membership
(`core_model.data_governance.review.compute_review_priority`).

## 5. Duplicate and conflict resolution

`GovernanceDuplicateService.sync_manual_data_duplicate()`/
`sync_chunk_duplicate()` and `GovernanceConflictService.sync_structured_record_conflict()`
call the existing detectors and persist a group only when a real match
is found; an *alternate* dictionary sense/answer/translation is routed
to a **conflict** group, never a duplicate group (mirroring
`detect_dictionary_conflict()`'s own `alternate_sense` vs
`duplicate_sense` distinction). Resolving either kind of group always
requires an explicit `resolution_action` + non-empty `resolution_reason`
and is always audited — nothing is ever auto-deleted, auto-merged, or
auto-rejected.

## 6. Approval model

`GovernanceApprovalService.evaluate()` combines, per `(entity_type,
entity_public_id, target_use)`: the entity's own rights-usage decision
(via `ManualDataUsageService.evaluate()` /
`StructuredRecordCandidateService.usage_check()` for the two entity
types that have one wired; `dataset_export`/`rag_handoff` never consult
a rights evaluator at all, since neither existing usage-policy module
knows about those two handoff-only target uses) + open blocking issues
scoped to that target + open duplicate/conflict groups. Every gate is a
hard AND (`core_model.data_governance.gate_rules.evaluate_target_approval()`):
a target use is `allowed` only when *every* check clears, and the
function never reads an overall quality score to decide `allowed` —
only `is_blocked`/blocking-issue membership. There is no single
record-wide `approved` flag; a `manual_data_record` can be `allowed`
for `rag` and `blocked` for `commercial` simultaneously.

`GovernanceApprovalService.override()` always requires a non-empty
reason, always sets `is_override=True`, and is always audited.
`GovernanceApprovalService.status()` returns the full per-target-use
matrix, expiry-aware (`is_approval_expired()` marks a stale decision
`needs_review` without mutating the historical row).

## 7. Export/RAG-handoff preflight integration

`GovernanceExportReadinessService.require_allowed()` is called as an
additive guard clause at the very start of
`ManualDataCandidateService.create_candidate()`,
`StructuredRecordCandidateService.export_to_dataset()`, and
`StructuredRecordCandidateService.create_rag_candidate()` (via a
function-local import to avoid a circular import with
`governance_service`'s own use of those two services for usage/conflict
checks) — raising `ValidationError` (422) before any existing export
logic runs if governance blocks it. Critically, an entity with **no**
governance review item, duplicate group, or conflict group at all is
never blocked by this addition (verified by the full existing Phase
3/5 export test suites passing unchanged, and by a dedicated
regression test asserting export still proceeds with zero governance
activity). `GET .../export-readiness/{entity_type}/{entity_public_id}/{target_use}`
exposes the identical read-only check for the frontend to call before
attempting the action.

## 8. Backend services and API

`backend/services/governance_service.py`: `GovernanceReviewService`
(queue/open/assign/status/note/history), `GovernanceQualityService`,
`GovernanceDuplicateService`, `GovernanceConflictService`,
`GovernanceApprovalService`, `GovernanceExportReadinessService`.

`backend/api/routes/governance.py` under `/api/admin/data-governance`:
queue listing/filtering, review-item open/get/assign/status/note/history,
quality assessment, duplicate/conflict group listing/sync/resolve,
approval status/evaluate/override, and export readiness — 20 endpoints,
all behind `require_admin` and CSRF-protected for mutations.

## 9. Frontend

`GovernancePage.jsx` ("Quality & Approval" in the Data submenu, after
Chunk & Record Studio): 9 tabs (Overview, Queue, Review Detail, Quality,
Duplicates, Conflicts, Approvals, Export Readiness, History). Boundary
between tabs uses the same flat, deterministic-controls style as every
prior Data Studio page (no drag/drop, no client-side score
recomputation). Bilingual (Tamil/English) contextual help entry added
to `helpRegistry.js` (`quality_approval`), chained from `chunk_studio`.

## 10. Tests

- 26 new `core_model` unit tests (`test_data_governance_review.py`,
  `test_data_governance_issue_taxonomy.py`,
  `test_data_governance_quality_adapter.py`,
  `test_data_governance_gate_rules.py`).
- 17 migration tests (`test_phase27_migration.py`): fresh-database and
  upgrade-from-26 reach schema 27; CHECK constraints for every new
  table; the partial-unique-index behavior; append-only triggers for
  issues/resolutions/target-approvals/events, including the
  column-scoped issues trigger that still allows `resolved_at`.
  Plus `test_system_api.py` updated with migration 027 in the expected
  set.
- 15 repository tests (`test_governance_repository.py`).
- 22 service tests (`test_governance_service.py`), including a
  dedicated `TestExportPreflightIntegration` class asserting the
  preflight guard both blocks (an open blocking issue) and never
  regresses (zero governance activity) for both the Manual Data and
  Structured Record export/RAG-handoff call sites.
- 6 API tests (`test_governance_api.py`): auth/CSRF enforcement, queue
  idempotency, assign/status/note, approval evaluate/override/status
  matrix, export readiness, duplicate/conflict group listing.
- 10 new frontend tests (`GovernancePage.test.jsx`): all nine tabs
  render, overview counts, queue open/manual-open, review-detail
  assign/note, quality assessment, override reason gating, export
  readiness.

All 962 backend tests, 74 frontend tests, and both production builds
(backend import + `vite build`) pass with zero regressions.

## 11. Manual browser verification (Flows A-J)

Verified live against the real `uvicorn --reload` backend, the real
Vite admin-dashboard dev server, and the persistent dev database
(already at schema 27), via Playwright driving an actual Chromium
browser through a real authenticated admin session:

- **Flow A**: login, navigate to Quality & Approval, all nine tabs
  render.
- **Flow B**: Overview shows real queue status counts, including zero
  states.
- **Flow C**: manually opening a review item via the Queue tab form
  succeeds and appears in the list.
- **Flow D**: opening that item into Review Detail, assigning it to an
  admin, adding a note, and updating its status to `resolved` (no
  blocking issues present) all succeed and are reflected immediately.
- **Flow E**: History tab loads the complete event trail (`opened`,
  `assigned`, `note_added`, `status_changed`) in order.
- **Flow F**: Approvals tab's override control is disabled with an
  empty reason and enables only once a reason is typed.
- **Flow G**: Export Readiness tab returns a decision for an
  entity/target-use pair with no governance activity (allowed by
  default).
- **Flow H**: Duplicates and Conflicts tabs load their (empty) group
  lists without error.
- **Flow I**: Quality tab renders and accepts entity-type/entity-id
  input.
- **Flow J (the critical end-to-end case)**: created a real, high-risk,
  fact-dependent, unverified `manual_data_record` via the live API in
  the same authenticated session; ran a real quality assessment through
  the Quality tab, which reported `Blocked: yes` with
  `HIGH_RISK_UNVERIFIED` and opened a genuine review item; opened that
  item and confirmed the blocking issue is listed; attempted to
  resolve it and confirmed the backend refused with "cannot resolve a
  review item with unresolved blocking issues" — a live, real-database
  confirmation that a review item can never be closed while a blocking
  issue remains open, regardless of any quality score.

All 22 browser-level checks passed; screenshot captured of the final
Review Detail state showing the blocking issue and the refused resolve
attempt.

## 12. Real bugs found and fixed during verification/testing

1. **`GovernanceQualityService._sync()` looked up a review item by the
   wrong key.** Its final read called
   `self.repository.review_item(connection, item["id"])` — but
   `review_item()` looks up by `public_id`, and `item["id"]` is the
   internal integer id. This raised `NotFoundError` the moment a
   quality assessment actually opened or reused a review item
   (previously masked because the "no issues, no review item" path
   never reached that line). Caught by a dedicated regression test
   (reopening a page for correction after its chunk was already
   generated) before manual verification. Fixed by calling
   `review_item_by_id()` instead.
2. **`governance_target_approvals`' original `UNIQUE(entity_type,
   entity_public_id, target_use, decided_at)` constraint collided on
   rapid re-decisions.** SQLite's `CURRENT_TIMESTAMP` has only
   second-level resolution, so two decisions on the same entity/target
   within the same second raised a spurious `ConflictError` — directly
   undermining the table's own "new row per decision" append-only
   design. Caught immediately by the first repository test exercising
   two decisions back-to-back. Fixed by dropping the constraint
   entirely (the surrogate `id` primary key already guarantees row
   identity; the append-only trigger already prevents mutation).
3. **`governance_review_items`' original table-wide
   `UNIQUE(entity_type, entity_public_id, status)` constraint would
   have permanently blocked a second-ever resolution of the same
   entity.** A table-wide unique constraint on `status` also applies
   to `resolved`/`rejected`/`archived` rows, so an entity opened,
   resolved, reopened, and resolved again would collide on its second
   `resolved` row. Caught during design review before any test was
   written against it. Fixed by replacing it with a partial unique
   index scoped to `WHERE status NOT IN ('resolved','rejected',
   'archived')`, preserving the real invariant ("only one open item at
   a time") without blocking legitimate historical reopenings.
4. **`GovernancePage.jsx`'s `reviewAction()` helper discarded its
   callback's return value.** The Quality tab's "Run quality
   assessment" button and the Queue tab's "Open review item" button
   both route through `reviewAction()`, but it never returned the
   awaited result — so `setResult(await assess())` always received
   `undefined`. Caught by the frontend test suite (`assess calls
   assessGovernanceQuality...` failed to find the rendered result)
   before manual browser verification; fixed by having `reviewAction()`
   return its callback's result.

## 13. Limitations / explicitly deferred

- No embedding-based semantic duplicate detection, LLM conflict
  resolution, or automatic factual adjudication/source selection — all
  per the task's explicit out-of-scope list; every duplicate/conflict
  is a deterministic pairwise match surfaced for human resolution.
- No automatic record merging, automatic training start, or automatic
  RAG indexing.
- A rights-usage evaluator is wired into the approval gate for
  `manual_data_record` and `structured_record_candidate` only (the two
  entity types that already had one before this phase); `document_page`,
  `semantic_chunk`, `document_candidate`, and `dataset_record` approval
  decisions for rights-bearing target uses (`rag`/`training`/etc.) rest
  on quality/duplicate/conflict/review-state gates only until a
  dedicated rights evaluator exists for those entity types -- this is a
  scope boundary, not a fabricated rights check.
- No existing document, page, candidate, manual-data record, semantic
  chunk, structured record, or dataset record was backfilled or
  destructively modified — this phase only adds new tables and a new
  admin-facing governance workflow on top of the unmodified existing
  six entity systems.

**Do not proceed to Phase 7.**
