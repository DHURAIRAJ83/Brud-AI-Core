# Phase 5 Plan — Semantic Chunk & Structured Record Studio

Written before implementation, per this phase's Step 1.

## 1. Existing functionality (confirmed by direct inspection)

**Segmentation** (`DocumentService.segment()`, `document_service.py:759`)
is a real, working feature — this phase enhances it, does not replace
it:

- Reads `document_pages` filtered only by `extraction_status IN
  ('success','warning')` — **not** filtered by Phase 4's
  `review_status`. Segmentation today processes every successfully
  extracted page regardless of human review outcome. This is the gap
  Step 6 asks Phase 5 to close for its *own* chunk generation (chunk
  generation must additionally require `review_status='approved'`),
  without changing `segment()`'s own existing behavior (still used by
  the pre-existing Candidates tab/pipeline).
- Produces flat `document_candidates` rows: `candidate_type` (`pretrain,
  instruction, chat, translation, tanglish_pair, safety, preference` —
  note this is **already `DatasetRecordType`'s own vocabulary**, not a
  separate one), `source_page_start/end`, `sequence_number`,
  `content_hash`, `status` (`draft, valid, warning, duplicate, invalid,
  selected, rejected, imported`), `duplicate_record_public_id`. No
  chunk type (heading/definition/dictionary_entry/...), no hierarchy,
  no per-chunk locator finer than a page range, no revision history.
  This is the genuine capability gap Phase 5's `semantic_chunks` fills.
- `import_candidates()` bridges `selected` candidates directly into
  `dataset_records` (via a dedicated `dataset_sources` row of
  `source_type='manual'`... actually `'pdf'`/`document_public_id`
  metadata), immutably marking them `imported`. **Must not be touched
  or duplicated.**

**Manual Data Studio's bridge pattern** (`ManualDataCandidateService`,
Phase 3) is the pattern Step 23 explicitly asks Phase 5 to reuse:
reads+validates the source record in its own transaction, calls
`DatasetService.create_record()` as a separate self-committing call
(never nested inside the reading transaction), then marks the source
row exported in a final transaction. Its `record_type ->
DatasetRecordType` map — `core_model.manual_data.DATASET_RECORD_TYPE_MAP`
— is **already almost exactly** Phase 5's requested structured-record
vocabulary (`plain_text, language_example, conversation,
question_answer, instruction_response, dictionary_entry,
translation_pair, tanglish_normalization, knowledge_note,
grammar_example` all map 1:1; only `evaluation_case_draft` is absent
and `rag_chunk` is new). **This map will be imported and reused
directly, not duplicated**, satisfying Step 11's "use existing record
types where possible."

**Manual Data Studio's lifecycle/quality/duplicate conventions**
(`core_model/manual_data/{lifecycle,quality,duplicates}.py`) are the
shape Steps 3/20/21 ask Phase 5 to mirror: a plain
`STATUS_TRANSITIONS: dict[str, frozenset[str]]` + `can_transition()`/
`validate_transition()`; deterministic per-dimension 0-100 scores plus
severity-independent blocking-issue codes that always override the
recommended status; exact-hash duplicate detection via NFC-normalize +
whitespace-collapse + SHA-256 of a canonical JSON dict (matching
`dataset_service.normalize_text`/`content_hash` exactly). Phase 5's own
`core_model/semantic_chunk/` modules will follow the identical shape,
not a new style.

**RAG's own chunk shape** (`rag_chunks`, `schema.py:2665`) already
demonstrates the established convention for chunk-lineage-as-JSON in
this codebase: `heading_path_json`, `source_location_json`,
`sequence_number`. Phase 5's `start_locator_json`/`end_locator_json`
on `semantic_chunk_revisions` follows this same convention, not a new
one.

**Phase 2 source-rights** (`core_model.data_governance.usage_policy`)
is reused directly for structured-record usage eligibility (Step 22),
exactly as Phase 3 and Phase 4 already reuse it — never re-implemented.

**Phase 4 page approval** already provides everything Step 6 needs to
gate chunk generation: `document_pages.review_status='approved'`,
`document_pages.approved_revision_number` (a concrete
`document_page_revisions.revision_number` to read `cleaned_text` from),
`source_record_links(entity_type='document')` for the linked-source
check, and `document_page_extractions` for the extraction-attempt
lineage. All read-only reuse; nothing here is modified.

## 2. Candidate lifecycle (existing, unmodified)

```
draft -> valid | warning | duplicate | invalid -> selected -> imported
                                                -> rejected
```
`imported` is terminal/immutable (`ConflictError` on any further edit).
This lifecycle continues to serve the plain pretrain-window Candidates
tab exactly as before; Phase 5's chunk/structured-record lifecycles are
new and independent, layered alongside it, not replacing it.

## 3. Missing capabilities (the actual gap this phase fills)

- No chunk type classification (heading, definition, dictionary_entry,
  grammar_rule, question, answer, table, ...).
- No chunk hierarchy (parent/child, reading order beyond a flat
  sequence number).
- No sub-page provenance (character offsets/locators) — only a page
  range.
- No split/merge/boundary-move operations or coverage validation.
- No dictionary-sense, grammar-rule, Q&A, translation-pair, or
  Tanglish-normalization *structured* editors driven by reviewed source
  chunks (Manual Data Studio's editors exist but are driven by
  freehand admin typing, not by selecting/aggregating reviewed PDF
  chunks with locked-in page/extraction lineage).
- No chunk-level quality/duplicate/conflict review queue.
- No RAG-readiness marker independent of dataset export.

## 4. Architecture decision

**`semantic_chunks`/`semantic_chunk_revisions`/`semantic_chunk_relations`/
`semantic_chunk_reviews`/`semantic_chunk_events` are new, additive
tables** — nothing in `document_candidates` provides chunk typing,
hierarchy, or fine-grained provenance, so this is genuine new
capability, not duplication.

**`structured_record_candidates`/`structured_record_candidate_revisions`/
`structured_record_reviews` are also new, additive tables**, built as
their own lightweight staging layer — **not** written directly into
`manual_data_records`. Two considerations drove this:

1. The codebase's own established convention is *multiple independent
   candidate-staging tables*, each with its own thin bridge into
   `dataset_records` (`document_candidates` for PDF segmentation
   windows, `manual_data_records` for freehand admin content). A third,
   `structured_record_candidates`, for *chunk-derived, chunk-linked*
   structured content is consistent with that convention, not a
   deviation from it.
2. Retrofitting `manual_data_records` with chunk-lineage columns
   (`primary_chunk_id`, per-chunk provenance) would mean altering an
   already-shipped, already-tested Phase 3 table and risking its
   existing lifecycle/tests, for no benefit the task actually asks for
   (Step 23 asks to reuse the *export bridge pattern* and *map to an
   existing `DatasetRecordType`* — it does not ask to reuse
   `manual_data_records` as storage).

What **is** reused directly, not reimplemented: the
`DATASET_RECORD_TYPE_MAP` (§1), the `ManualDataCandidateService`
transaction-shape (§1), Phase 2's usage-policy evaluator, and
`dataset_service.normalize_text`/`content_hash`.

**`rag_chunk`** as a structured-record type never goes through
`DatasetService.create_record()` (it is not in
`DATASET_RECORD_TYPE_MAP` and never will be) — Step 24 explicitly asks
for an explicit *handoff*, not automatic indexing, so a `rag_chunk`
candidate's "export" action is a distinct, additive
`mark-ready-for-rag`/handoff action that never writes to
`dataset_records`.

## 5. Proposed schema (migration 026)

All additive; no existing table's columns, CHECK constraints, or
triggers change. `SCHEMA_VERSION` moves 25 -> 26.

| Table | Purpose |
|---|---|
| `semantic_chunks` | Canonical chunk: type, status, hierarchy (`parent_chunk_id`, `reading_order`), classification, `active_revision_id`. |
| `semantic_chunk_revisions` | Append-only content history: `text`, `normalized_text`, `start_locator_json`/`end_locator_json` (page/offset/region), full provenance columns, `generation_method`, `confidence`, `change_summary`. |
| `semantic_chunk_relations` | Typed edges between chunks (`continues_from`, `child_of`, `table_contains`, `definition_of`, `example_of`, `answer_to`, `translation_of`) with `sort_order`. |
| `semantic_chunk_reviews` | Human review actions (approve/request-boundary-correction/request-classification-correction/reject/exclude). |
| `semantic_chunk_events` | Append-only domain event log (mirrors `manual_data_events`) — backs the History tab. |
| `structured_record_candidates` | Canonical structured record: `record_type` (reusing the vocabulary in §1), status, `primary_chunk_id`, linked chunk set, `active_revision_id`, `requested_uses_json`. |
| `structured_record_candidate_revisions` | Typed common fields per Step 5 (title/text/question/answer/instruction/response/word/senses/translation pair/tanglish fields/grammar fields), `metadata_json` for anything structured but not universally common, never one opaque blob for primary content. |
| `structured_record_reviews` | Human review actions on a structured-record revision. |

`semantic_chunk_revisions`, `semantic_chunk_events`,
`structured_record_reviews` get the standard append-only
`BEFORE UPDATE/DELETE ... RAISE(ABORT, ...)` trigger pair. Approved
chunk/record bodies are protected at the service layer (an edit to an
`approved` row always creates a new revision + reopens to
`needs_correction`-equivalent, mirroring Phase 3's `approved -> draft`
and Phase 4's `approved -> needs_correction`), exactly like both prior
phases.

## 6. Chunk lifecycle

```
draft -> needs_review -> needs_structure_review | needs_content_review -> approved -> rejected -> excluded -> archived
approved -> needs_review   (correction pathway: editing an approved chunk always reopens it)
```

## 7. Provenance

Every `semantic_chunk_revisions` row carries: `source_id` (Phase 2
`data_sources.id`, resolved from the document's linked source — never
nullable at generation time since Step 6 requires a linked source
before generation), `document_id`, `page_id`, `page_number`,
`extraction_id` (`document_page_extractions.id`), `page_revision_id`
(`document_page_revisions.id` — the specific approved revision text
was read from), `start_locator_json`/`end_locator_json`. Character
offsets are used when the source text is a single approved page's
`cleaned_text` (the common case); an explicit `{"page": N}` or
`{"pages": [N, M]}` locator is used for anything spanning more than one
page. Never guessed — `generation_method` records exactly how a chunk
was produced (`existing_segmenter, paragraph_boundary,
heading_boundary, manual, imported`), and offsets are only ever
computed from the literal source text, never approximated.

## 8. Migration to segmentation readiness (Step 6)

`SemanticChunkService.generate()` requires, per page: `review_status =
'approved'`, `approved_revision_number IS NOT NULL`, the document has a
linked source (`source_record_links(entity_type='document')`), and
`extraction_status != 'failed'`. A document with some approved and some
not-yet-approved pages generates chunks **only from the approved
subset**, and the response is explicitly labeled `partial_document:
true` with the excluded page count — never implying full-document
coverage.

## 9. API and frontend plan

Additive only, under two new prefixes (`/api/admin/semantic-chunks`,
`/api/admin/structured-records`) per Step 26's list — no existing
document/segmentation/dataset/manual-data endpoint changes shape.
Frontend: one new sidebar entry ("Chunk & Record Studio") under the
existing `Data` group, a new `ChunkStudioPage.jsx` with the 9 tabs from
Step 28, reusing `.dataset-tabs`/`.metric-grid`/`.status-card`/
`.panel-controls`/`.history-panel`/`.candidate-list` conventions
already established across `DocumentsPage.jsx`/`ManualDataPage.jsx`.

## 10. Compatibility risks

- **Risk**: `SCHEMA_VERSION` moving 25->26 triggers the same class of
  hardcoded-version-assertion regression hit in Phases 1-4.
  **Mitigation**: grep for `SCHEMA_VERSION == 2[0-9]` and hardcoded
  `applied_migrations` sets before the final verification pass.
- **Risk**: reading `document_pages`/`document_page_revisions` for
  chunk generation could regress existing segmentation tests if done
  carelessly. **Mitigation**: purely additive, read-only reuse; existing
  `test_document_pipeline.py` re-run after every change.
- **Risk**: importing `DATASET_RECORD_TYPE_MAP` from
  `core_model.manual_data` creates a cross-phase dependency.
  **Mitigation**: this is the same module Phase 3 already ships as a
  stable, tested, pure `core_model` constant — importing a constant is
  far safer than duplicating the map and letting the two drift.

## 11. Explicitly deferred (this phase)

Automatic dictionary parsing, AI-generated Q&A, automatic translation/
Tanglish generation, LLM-based classification, embedding-based semantic
duplicate detection, automatic conflict resolution, immutable
dataset-version builder changes, pipeline-wide hard rights enforcement,
Floating Admin Assistant, public submission, web crawling, external
fact checking — all per the task's explicit out-of-scope list. Real
advanced table-structure reconstruction is also deferred (Step 18):
tables are preserved as `table_raw` with a warning when structure can't
be confidently recovered, matching the same "don't fabricate" principle
applied everywhere else in this phase.
