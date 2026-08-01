# Phase 6 Plan — Quality, Duplicate, Conflict & Approval Integration

Written before implementation, per this phase's Step 1.

## 1. Existing systems (confirmed by direct inspection)

**Dataset quality** (`backend/services/dataset_quality.py`, live since
the original build's own "Phase 6") is a mature, deterministic system
scoped to `dataset_records`: 7 dimensions (`completeness, structure,
language, text_quality, duplication, safety, provenance`) plus
`overall`, persisted in `dataset_quality_assessments`/
`dataset_quality_issues` (append-only history — a record's quality is
never mutated in place, only reassessed). Issue severity is already a
4-level enum (`info, warning, error, blocking`) with `blocking`
overriding readiness regardless of score — the exact "high score
cannot hide a blocking issue" invariant this phase must preserve
everywhere. `docs/dataset_quality.md` documents it as intentionally
conservative (script-based language checks, not ML).

**Manual Data quality** (`core_model/manual_data/quality.py`, Phase 3):
8 dimensions + a `blocking_issues: list[str]` array (not a per-issue
severity field) + `recommended_status`. Duplicate detection
(`core_model/manual_data/duplicates.py`) is exact/normalized
content-hash, plus a dictionary-specific `(word, primary_language)`
uniqueness key — already distinguishing "same word" from "same sense".

**Semantic chunk quality** (`core_model/semantic_chunk/quality.py`,
Phase 5): same shape as Manual Data's (8 dimensions,
`blocking_issues` list, `recommended_status`). Duplicate/conflict
detection (`core_model/semantic_chunk/duplicates.py`) already
implements exact-hash matching, same-locator matching, and — critically
— `detect_dictionary_conflict()`/`detect_qa_conflict()`/
`detect_translation_conflict()`, which **already** distinguish an
alternate valid dictionary sense from a true duplicate, and a
conflicting answer/translation from a duplicate one. Coverage
conflicts (`core_model/semantic_chunk/coverage.py`'s
`validate_page_coverage()`) already detect `SOURCE_TEXT_LOSS`
(gap) and `SOURCE_TEXT_OVERLAP` (overlap) per page.

**Structured-record usage policy** (`core_model/semantic_chunk/usage_policy.py`)
and **Manual Data usage policy** (`core_model/manual_data/usage_policy.py`)
already return the exact per-target-use shape Phase 6's Step 5 asks
for: `{allowed, decision_code, blocking_reasons, warnings,
required_actions}`, evaluated independently per target use — never one
global flag. Both already wrap Phase 2's `evaluate_source_usage()`
rather than duplicating rights logic.

**Lifecycles already reviewed/approved through their own workflows**:
`manual_data_records.status` (Phase 3), `document_pages.review_status`
(Phase 4), `semantic_chunks.status` /
`structured_record_candidates.status` (Phase 5), `dataset_records`
(driven by `DatasetRecordStatus` at the Pydantic layer — the column
itself is a plain, un-constrained `TEXT DEFAULT 'raw'`, validated in
`backend/models/domain.py`, not by a DB `CHECK`). Every one of these
already writes its own audit + domain-event trail. **None of this is
replaced.**

**What does not exist yet, confirmed by inspection**: no table
persists a *duplicate group* or *conflict group* with membership — every
existing duplicate/conflict check is a pairwise, on-demand comparison,
never grouped or tracked as an open, assignable item. No single queue
lists "everything that needs a human decision" across entity types.
No entity has *per-target* approval decisions with an expiry. No
export/RAG-handoff call path has a mandatory governance preflight
(Manual Data's and Structured Record's own export bridges only check
their own record's status + a live usage-policy call — sufficient for
correctness but not surfaced anywhere as a queue item if blocked).

## 2. Scoping `entity_type` to what safely exists

Per Step 2's explicit "only include entity types that exist and can be
reviewed safely": `document_page, manual_data_record, semantic_chunk,
structured_record_candidate, document_candidate, dataset_record` — six
concrete, already-reviewable entities.

`rag_candidate` (recommended in the prompt) and "future training
candidates" are **not** modeled as separate entity types: no
`rag_candidates` table exists anywhere in the schema (RAG's own
`rag_chunks`/`rag_chunk_sets`/`rag_source_versions` are a distinct,
already-ingested-content pipeline, not a pre-approval staging table),
and a "RAG candidate" in practice today *is* a
`structured_record_candidates` row with `record_type='rag_chunk'` —
already fully representable via `entity_type='structured_record_candidate'`.
Likewise a "training candidate" *is* a `dataset_record` once exported.
Inventing a phantom table to satisfy the recommended list would
violate both "only include entity types that exist" and "do not
duplicate existing review history merely to match this prompt".

## 3. Architecture decision

A new, additive **governance layer** sits *above* the six existing
systems, never replacing any of them:

- **`GovernanceQualityAdapterService`** reads each entity's own
  authoritative quality result (dataset: `DatasetQualityService.latest()`;
  manual data/chunk: their own `assess_quality()`/`assess_chunk_quality()`
  calls) and maps it into one normalized shape (Step 7) —
  canonical dimension buckets (`language, meaning, factual, source,
  structure, integrity, format, uniqueness`) with the original
  subsystem-specific dimension names preserved verbatim in
  `metadata.source_dimensions`. It never recomputes a score a subsystem
  already owns.
- **`GovernanceDuplicateService`**/**`GovernanceConflictService`** call
  the *existing* pairwise detectors per entity type (Phase 3/5's
  `duplicates.py` modules, dataset's own content-hash check) and
  persist the result as a **group** (new capability) so it becomes an
  assignable, resolvable queue item instead of a one-off API response.
- **`GovernanceApprovalService`** combines: entity lifecycle + active
  revision + the normalized quality result + the entity's own
  usage-policy call (Phase 2/3/5's `evaluate_*_usage()`) + open
  duplicate/conflict groups into one deterministic per-target decision
  — literally the same shape Step 5 asks for, because Phase 3/5 already
  return it; Phase 6 adds **persistence** (`governance_target_approvals`,
  with expiry) and **override** semantics on top.
- **`GovernanceReviewService`** is the actual new thing: a queue of
  `governance_review_items`, created idempotently from the conditions
  in Step 13 (submitted for review, blocking quality issue, duplicate/
  conflict group opened, rights blocked, verification expired, export
  attempted and blocked), each carrying issues, assignable, prioritized,
  and resolvable — all append-only audited, exactly like every prior
  phase's event tables.

Export/RAG-handoff preflight (Step 20) is added as a **new, additive
check function** called at the *start* of the existing export methods
(`ManualDataCandidateService.create_candidate()`,
`StructuredRecordCandidateService.export_to_dataset()`/
`create_rag_candidate()`) — a `ValidationError` (422) raised before any
existing logic runs if governance blocks it, with a dedicated
`GET .../export-readiness`-style read endpoint for the frontend to
check *before* attempting the action. The export methods' own response
shapes are unchanged; the only new behavior is an earlier, additive
guard clause.

## 4. Proposed schema (migration 027)

All additive; no existing table's columns, CHECK constraints, or
triggers change. `SCHEMA_VERSION` moves 26 -> 27.

| Table | Purpose |
|---|---|
| `governance_review_items` | The unified queue: one row per open (or resolved) review condition on one entity. |
| `governance_review_issues` | Normalized issues attached to a review item — severity + explicit `is_blocking`/`blocking_targets_json` (Step 4's example shape), never inferring blocking from severity alone. |
| `governance_duplicate_groups` / `governance_duplicate_group_members` | Persisted duplicate groups (exact/normalized/same-locator/export-duplicate) with membership, replacing nothing — the underlying pairwise detectors are reused verbatim to populate them. |
| `governance_conflict_groups` / `governance_conflict_group_members` | Persisted conflict groups (dictionary_sense/answer/translation/chunk_overlap/chunk_gap/source_fact/revision/classification). |
| `governance_resolutions` | Append-only record of every duplicate/conflict resolution action (keep-all/choose-canonical/alternate-sense/alternate-answer/merge-manually/reject/archive/not-a-duplicate), with required reason. |
| `governance_target_approvals` | Per-(review_item, target_use) decision with expiry — never one global flag. |
| `governance_review_events` | Append-only domain event log, mirrors every prior phase's `*_events` table — backs the review item's own History. |

`governance_review_issues`, `governance_resolutions`,
`governance_target_approvals` (its *history*, via
`governance_review_events`), and `governance_review_events` get the
standard append-only `BEFORE UPDATE/DELETE ... RAISE(ABORT, ...)`
trigger pair. `governance_review_items.status` is a normal mutable
column (a queue item's status legitimately changes — open ->
in_review -> resolved), exactly like `document_pages.review_status`
or `semantic_chunks.status` before it.

## 5. Issue taxonomy and severity

20 stable issue categories (language_quality, meaning_quality,
factual_accuracy, source_traceability, rights_restriction,
verification_missing, exact_duplicate, normalized_duplicate,
source_overlap, dictionary_sense_conflict, answer_conflict,
translation_conflict, chunk_overlap, chunk_gap, revision_conflict,
ai_assisted_unreviewed, high_risk_unverified, time_sensitive_expired,
format_invalid, export_duplicate) map 1:1 onto existing subsystem
issue codes already produced by Phase 3/4/5's own quality/usage-policy
modules — this phase's adapter is a *lookup table*, not a new
detector, for every one of these except the two genuinely new
capabilities: persisted duplicate/conflict *groups* and target-approval
*expiry*.

Severity (`info, warning, error, critical`) is explicit and
independent of `is_blocking`/`blocking_targets` (Step 4) — a deliberate
departure from the existing `dataset_quality_issues.severity`
convention (which uses a literal `'blocking'` severity value and
infers blocking from it). This phase's own normalized issues never
infer blocking from severity, per the task's explicit instruction; the
adapter maps a subsystem's `severity=='blocking'` (dataset quality) or
membership in `blocking_issues` (manual data/chunk) to
`severity='critical', is_blocking=True` in the normalized shape.

## 6. Compatibility risks

- **Risk**: `SCHEMA_VERSION` moving 26->27 triggers the same class of
  hardcoded-version-assertion regression hit in Phases 1-5.
  **Mitigation**: grep for `SCHEMA_VERSION == 2[0-9]` and hardcoded
  `applied_migrations` sets before the final verification pass.
- **Risk**: adding a preflight guard to
  `ManualDataCandidateService.create_candidate()`/
  `StructuredRecordCandidateService.export_to_dataset()`/
  `create_rag_candidate()` could regress Phase 3/5's own export tests
  if the guard is too strict by default. **Mitigation**: the guard only
  blocks when a *governance review item* actually exists and is
  unresolved for that entity — an entity with no review item at all
  (the common case for every existing passing test, since none of them
  ever created one) is never blocked by this phase's addition; the
  existing Phase 3/5 export test suites are re-run after every change
  to confirm zero regressions.
- **Risk**: normalizing quality dimensions from three different
  existing shapes (7 dataset dimensions, 8 manual-data dimensions, 8
  chunk dimensions) into 8 canonical buckets could silently misrepresent
  a subsystem's own score. **Mitigation**: the adapter is covered by a
  dedicated test per entity type asserting the canonical bucket values
  trace back to the exact source dimension(s), and the full original
  `dimension_scores`/`scores` dict is preserved verbatim in
  `metadata.source_dimensions` for audit.

## 7. Explicitly deferred (this phase)

Embedding-based semantic duplicate detection, LLM conflict resolution,
automatic source selection/factual adjudication, automatic record
merging, dataset-version builder redesign, pipeline-wide hard rights
enforcement (this phase adds preflight to the *specific* export/handoff
call sites Step 20 names, not every downstream pipeline), automatic
training start, automatic RAG indexing, Floating Admin Assistant,
public review workflows, web fact checking, legal advice — all per the
task's explicit out-of-scope list.
