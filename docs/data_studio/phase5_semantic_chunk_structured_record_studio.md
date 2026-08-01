# Phase 5 — Semantic Chunk & Structured Record Studio

Status: complete. Schema version 25 -> 26 (migration
`026_data_studio_phase5_semantic_chunk_structured_record_studio`).

A governed layer that enhances the existing segmentation/candidate
pipeline (`DocumentService.segment()`/`document_candidates`, live since
the original Phase 5 document-processing build) with chunk-level
typing, hierarchy, and fine-grained provenance, then bridges reviewed
chunks into structured, dataset-compatible record candidates. See
[phase5_semantic_chunk_structured_record_plan.md](phase5_semantic_chunk_structured_record_plan.md)
for the pre-implementation baseline audit and architectural decisions.

## 1. Architecture

`document_candidates` (flat pretrain-window segmentation) is untouched
and continues to serve the existing Candidates tab. `semantic_chunks`
is a new, independent layer for content that needs a real type
(heading/definition/dictionary_entry/...), hierarchy, and per-chunk
source lineage finer than a page range — capabilities
`document_candidates` never had.

`structured_record_candidates` is a new, independent staging table for
chunk-derived structured content (dictionary/grammar/Q&A/translation/
Tanglish/knowledge/RAG), mirroring `manual_data_records`'s shape and
lifecycle style but **not** reusing that table directly — the
codebase's own convention is multiple independent candidate-staging
tables, each with its own thin bridge into `dataset_records`
(`document_candidates`, `manual_data_records`, and now
`structured_record_candidates`), rather than retrofitting an
already-shipped table with lineage columns it was never designed to
hold. The `record_type -> DatasetRecordType` mapping is imported
directly from `core_model.manual_data.DATASET_RECORD_TYPE_MAP` (not
duplicated), and the export bridge
(`StructuredRecordCandidateService.export_to_dataset()`) mirrors
`ManualDataCandidateService`'s exact transaction shape.

## 2. Schema (migration 026)

All additive; no existing table's columns, CHECK constraints, or
triggers changed.

| Table | Purpose |
|---|---|
| `semantic_chunks` | Canonical chunk: type, status, hierarchy (`parent_chunk_id`, `reading_order`), classification, `active_revision_id`. |
| `semantic_chunk_revisions` | Append-only content history: text, normalized text, full provenance (page/extraction/page-revision IDs), `start_locator_json`/`end_locator_json`, `generation_method`, `confidence` (nullable, never fabricated). |
| `semantic_chunk_relations` | Typed edges between chunks (`child_of`, `continues_from`, `table_contains`, `definition_of`, `example_of`, `answer_to`, `translation_of`, `derived_from_page`). |
| `semantic_chunk_reviews` | Human review decisions (approve/reject/exclude/request-boundary-correction/request-classification-correction/archive/reopen). |
| `semantic_chunk_events` | Append-only domain event log — backs the chunk's own History tab. |
| `structured_record_candidates` | Canonical structured record: type, status, `primary_chunk_id`, `active_revision_id`, `requested_uses_json`, `exported_dataset_record_public_id`, `rag_handoff_at`. |
| `structured_record_candidate_chunks` | Join table linking a candidate to every evidence chunk it was built from. |
| `structured_record_candidate_revisions` | Typed common fields (title/text/question/answer/instruction/response/word/senses/translation pair/tanglish fields/grammar fields) plus `origin` (`source_grounded`/`admin_authored`/`human_synthesized`) — never one opaque JSON blob for primary content. |
| `structured_record_reviews` | Human review decisions on a structured-record revision. |

## 3. Chunk types and lifecycle

25 stable machine-readable chunk types (heading, subheading, paragraph,
definition, example, dictionary_entry, grammar_rule, question, answer,
instruction, response, translation_source, translation_target,
tanglish_text, tamil_text, english_text, table, table_row, list,
footnote, caption, reference, metadata, irrelevant, unknown).

```
draft -> needs_review -> needs_structure_review | needs_content_review -> approved -> rejected -> excluded -> archived
approved -> needs_review   (correction pathway: editing text always reopens it)
```

Structured records use a simpler 5-state lifecycle
(`draft/needs_review/approved/rejected/archived`) with the identical
`approved -> needs_review` correction pathway on revision.

## 4. Provenance

Every chunk revision carries `data_source_id` (Phase 2 source, resolved
from the document's linked source), `document_page_id`, `page_number`,
`extraction_id` (`document_page_extractions.id`), `page_revision_id`
(the exact `document_page_revisions.id` the text was read from —
never the page's possibly-since-edited live text), and
`start_locator_json`/`end_locator_json` (`{"page": N, "offset": N}` for
character-offset locators; a bare `{"page": N}` when offsets aren't
derivable, honestly reported as `coverage_computable: false` rather
than assumed covered). `generation_method` records exactly how a chunk
was produced (`existing_segmenter, paragraph_boundary, heading_boundary,
manual, imported`) — never fabricated.

## 5. Split/merge/boundary invariants

`core_model/semantic_chunk/coverage.py` provides pure, deterministic
validators:

- **Split**: rejects a split point outside the chunk's own bounds or
  one that would produce an empty fragment; the two resulting
  fragments always concatenate back to the exact original text.
- **Merge**: requires the two chunks to be non-overlapping and in
  order; reconstructs the merged text as the literal source substring
  between their outer bounds when both share a page (preserving any
  intervening separator whitespace exactly, rather than naive
  concatenation, which would silently drop it) — verified live: a
  merge of two paragraph-boundary-generated chunks correctly restored
  the exact original two-sentence text, separator included. Cross-page
  merges are allowed but flagged with a `cross_page_merge` warning.
- **Boundary move**: moves a shared edge between a chunk and its
  neighbor, re-slicing both from the full source text; rejects a move
  that would produce an empty fragment on either side.
- **Coverage report**: for every offset-locatable chunk on a page,
  computes assigned/unassigned ratios and flags `SOURCE_TEXT_LOSS`
  (gap) / `SOURCE_TEXT_OVERLAP` (overlap) — excludes
  `excluded`/`rejected`/`archived` chunks so a superseded chunk's stale
  locator never produces a false-positive conflict against the chunk
  that replaced it (a real bug caught during manual verification, see
  §9).

An approved chunk cannot be split, merged, or have a boundary moved
directly — those structural operations require `request_boundary_correction`
first. A pure text correction (`edit_text()`) is always permitted,
including on an approved chunk, and reopens it to `needs_review`.

## 6. Hierarchy

Optional parent/child assignment (`assign_parent`) with cycle
prevention (`core_model/semantic_chunk/hierarchy.py` walks the
proposed ancestor chain before committing); reading order is a plain
integer, reassignable via `reorder()`. No document is required to have
any hierarchy at all.

## 7. Quality rules

`core_model/semantic_chunk/quality.py` — 8 dimensions
(boundary_completeness, semantic_coherence, language_correctness,
source_traceability, structure_completeness, content_integrity,
format_validity, uniqueness) plus blocking issue codes
(`MISSING_SOURCE_LINEAGE, UNAPPROVED_PAGE_SOURCE, EMPTY_CHUNK,
BROKEN_SENTENCE_BOUNDARY, SOURCE_TEXT_LOSS, SOURCE_TEXT_OVERLAP,
INVALID_RELATION, UNRESOLVED_TABLE_STRUCTURE, UNREVIEWED_ADMIN_SYNTHESIS,
RIGHTS_BLOCK_TARGET_USE`) that always override the recommended status
regardless of average score.

## 8. Duplicate and conflict handling

Exact/normalized duplicate detection mirrors
`dataset_service.normalize_text`/`content_hash` exactly (NFC + collapse
whitespace + optional casefold, SHA-256 of canonical JSON) — no
embedding-based semantic engine, per explicit scope. A same-locator
second chunk is a duplicate regardless of later text edits. Conflicts
(same dictionary word/different meaning, same question/different
answer, same source text/different translation) are surfaced as
`alternate_sense`/`conflicting_answer`/`inconsistent_translation` for
manual review — never auto-resolved or auto-merged; verified live
(§9, Flow G's structured-record conflict check).

## 9. Source-rights integration

`core_model/semantic_chunk/usage_policy.py`'s
`evaluate_structured_record_usage()` calls Phase 2's
`evaluate_source_usage()` directly, layering only candidate-status and
human-synthesized-content gates on top — never duplicating rights
logic. Returns `{allowed, decision_code, blocking_reasons, warnings,
required_actions}` per target use (rag/training/evaluation/commercial/
public_export/redistribution); never one global approval flag.

## 10. Dataset export and RAG handoff

`export_to_dataset()` requires `approved` status, an un-exported
candidate, and a `record_type` present in `DATASET_RECORD_TYPE_MAP`
(everything except `rag_chunk`); finds-or-creates a dedicated
`dataset_sources` row (`source_type='structured_record_studio'`,
mirroring `ManualDataCandidateService`'s own bridge-source pattern —
`dataset_sources` is a different table from the Phase 2 `data_sources`
the candidate itself links to, a real bug caught and fixed during
service-level testing, see §12); calls `DatasetService.create_record()`
as a separate, self-committing call; then marks the candidate exported
in a final transaction. Prevents duplicate export
(`ConflictError` on a second attempt). `rag_chunk` candidates are
explicitly blocked from dataset export and instead use
`create_rag_candidate()` — an explicit handoff marker
(`rag_handoff_at`), never automatic indexing.

## 11. Backend: repository / service / API layers

- `backend/database/repositories/semantic_chunks.py` — `SemanticChunkRepository`.
- `backend/database/repositories/structured_records.py` — `StructuredRecordRepository`.
- `backend/services/semantic_chunk_service.py` — `SemanticChunkService`
  (generate/split/merge/move-boundary/classify/hierarchy/manual-create/
  archive-restore), `SemanticChunkReviewService`, `SemanticChunkQualityService`,
  `ChunkConflictService`.
- `backend/services/structured_record_service.py` — `StructuredRecordCandidateService`.
- `backend/api/routes/semantic_chunks.py` (24 endpoints) and
  `backend/api/routes/structured_records.py` (13 endpoints) under
  `/api/admin/semantic-chunks` and `/api/admin/structured-records`,
  behind `require_admin` + `CsrfDependency`.
- No existing document/segmentation/dataset/manual-data endpoint
  changed shape.

## 12. Frontend

New sidebar entry **Chunk & Record Studio** under the `Data` group
(between Documents and Corpus Builder); `ChunkStudioPage.jsx` with the
9 required tabs (Overview, Documents, Chunk Editor, Structure, Record
Builder, Review Queue, Conflicts, Approved, History), reusing the
existing `.dataset-tabs`/`.metric-grid`/`.status-card`/`.panel-controls`/
`.history-panel`/`.candidate-list`/`.review-actions` design-system
classes. Boundary editing uses deterministic numeric offset/edge
controls rather than drag handles, per the fallback the task itself
recommends when drag is unreliable. Existing bilingual `documents`
help entry left in place; a new bilingual `chunk_studio` entry added.

## 13. Tests

| File | Tests |
|---|---|
| `tests/database/test_phase26_migration.py` | 6 |
| `tests/database/test_semantic_chunk_repository.py` | 4 |
| `tests/database/test_structured_record_repository.py` | 4 |
| `tests/core_model/test_semantic_chunk_lifecycle.py` | 8 |
| `tests/core_model/test_semantic_chunk_coverage.py` | 14 |
| `tests/core_model/test_semantic_chunk_quality.py` | 12 |
| `tests/core_model/test_semantic_chunk_duplicates.py` | 11 |
| `tests/core_model/test_semantic_chunk_classification.py` | 7 |
| `tests/core_model/test_semantic_chunk_hierarchy.py` | 5 |
| `tests/backend/test_semantic_chunk_service.py` | 20 |
| `tests/backend/test_structured_record_service.py` | 11 |
| `tests/backend/test_semantic_chunk_api.py` | 9 |
| `tests/backend/test_structured_record_api.py` | 5 |
| `apps/admin-dashboard/src/pages/ChunkStudioPage.test.jsx` | 11 |
| **Total new** | **127** |

`tests/backend/test_system_api.py` updated with migration 026 in the
expected `applied_migrations` set.

Final verification run (this session, 2026-07-27):

- `python -m pytest -q` (full repository suite) — **884 passed**, 0
  failed (27m39s).
- `ruff check backend/ core_model/ tests/` — clean.
- `npm run test --prefix apps/admin-dashboard -- --run` — 64 passed
  (6 files), including the 11 new `ChunkStudioPage.test.jsx` tests.
- `npm run build --prefix apps/admin-dashboard` — succeeds.
- `python -m backend.database.migrations status` — current version 26,
  all 26 migrations listed as applied.
- `python -m backend.database.migrations verify` — `{"integrity_check":
  "ok", "foreign_key_violations": []}`.

## 14. Manual browser verification (Flows A-H)

All eight required flows were exercised end-to-end against the real
dev server + real backend (Playwright), using a genuinely valid
Tamil-glyph test PDF (Noto Sans Tamil) and a document already taken
through the existing Phase 4 Documents workspace (upload -> process ->
link source -> approve page):

- **Flow A (paragraph chunks)**: generate -> one paragraph chunk ->
  split at an interior offset (two fragments concatenate back to the
  exact original text) -> merge them back (exact original text
  restored, separator included) -> submit for review -> approve.
- **Flow B (dictionary)**: dictionary_entry candidate with two
  meanings preserved as a JSON array from the approved chunk.
- **Flow C (grammar)**: grammar_example candidate with rule, correct
  example, and incorrect example.
- **Flow D (Q&A)**: question_answer candidate with an admin-written
  question and a source-grounded answer.
- **Flow E (translation)**: translation_pair candidate with distinct
  source/target languages and text.
- **Flow F (Tanglish)**: tanglish_normalization candidate with
  Tanglish text, normalized Tamil, and an English meaning.
- **Flow G (coverage conflict)**: the structured-record Conflicts tab
  correctly flagged an `alternate_sense` conflict between two
  dictionary candidates sharing a word with different meanings; the
  page-coverage report caught a real false-positive overlap bug (§9).
- **Flow H (approved chunk revision)**: editing an approved chunk's
  text created a new revision, reopened it to `needs_review`, and
  preserved every prior revision (4 total across generate/split/merge/
  edit) with a complete, correctly-ordered event history.

Also verified directly: the Approved tab's per-use usage-eligibility
check (`training?` -> `Allowed` with full rights granted) and
Export-to-Existing-Dataset-Record (confirmed via a real
`exported_dataset_record_public_id` written back to the candidate).

## 15. Real bugs found and fixed during verification

1. **`SemanticChunkReviewService._transition()` returned data from a
   closed connection.** The final `return` statement was dedented
   outside its own `with self.repository.transaction()` block,
   raising `sqlite3.ProgrammingError: Cannot operate on a closed
   database` the moment a transition actually succeeded (previously
   masked because every test run hit an earlier failure first). Fixed
   by re-opening a fresh transaction for the final read.
2. **`submit_review()` tried to write an invalid review `action`.**
   `semantic_chunk_reviews.action`'s CHECK constraint intentionally
   only accepts genuine reviewer verdicts (approve/reject/exclude/
   request_*/archive/reopen); "submitted_for_review" is a status
   advance, not a verdict. Fixed by skipping the `create_review()` row
   for that one action and relying on the event log instead.
3. **Merging two adjacent, real paragraph-generated chunks failed.**
   The initial `plan_merge()` required byte-exact adjacency, but a
   generated paragraph chunk's own bounds never include the blank-line
   separator that split it from its neighbor — a real gap always
   exists between them. Fixed by allowing a gap and reconstructing the
   merged text from the literal page substring (preserving the
   separator) rather than requiring exact adjacency.
4. **Coverage and duplicate-check reports included superseded chunks.**
   `locators_for_document()`/`content_hashes_for_document()` queried
   every chunk regardless of status, so a chunk excluded by a merge
   left a stale locator/hash behind that produced a false-positive
   `SOURCE_TEXT_OVERLAP`/duplicate warning against the chunk that
   replaced it — caught live via the Conflicts tab showing "overlaps 1"
   on a document with exactly one, correctly-merged chunk. Fixed by
   excluding `excluded`/`rejected`/`archived` chunks from both queries.
5. **`export_to_dataset()` used the wrong source table.**
   `DatasetService.create_record()`/`RecordCreate.source_public_id`
   points at the older `dataset_sources` table (Phase 1), a different
   table from the Phase 2 `data_sources` a structured-record candidate
   actually links to — the exact gap `ManualDataCandidateService`
   already solved for Manual Data Studio. Fixed by adding an equivalent
   `_find_or_create_dataset_source()` bridge-source helper, caught by a
   service-level test before it ever reached manual verification.
6. **`DatasetService` was constructed with the wrong argument type**
   (`Settings` instead of a `DatasetAdminRepository`), and a stray
   duplicate `)` left over from an earlier edit — both caught
   immediately by the first structured-record service test run.

## 16. Limitations / explicitly deferred

- No AI-based classification, automatic dictionary parsing, automatic
  translation/Tanglish generation, or automatic conflict resolution —
  all per the task's explicit out-of-scope list.
- No embedding-based semantic duplicate detection — exact/normalized
  hash matching only, matching every prior phase's same deferral.
- Table content is preserved as raw text with a `table_structure`
  warning when row/column structure can't be confidently recovered;
  no automatic table reconstruction.
- Boundary editing uses deterministic numeric offset controls, not
  drag handles, per the task's own accessibility fallback guidance.
- No existing document, page, candidate, or manual-data record was
  backfilled or destructively modified — this phase only adds new
  tables/columns and new admin-facing workflows on top of the
  unmodified existing segmentation/candidate pipeline.

**Do not proceed to Phase 6.**
