# Phase 4 Plan — PDF Research Workspace

Written before implementation, per this phase's Step 1.

## 1. Existing functionality (confirmed by direct inspection)

Phase 5 (`005_phase5_document_processing`, `backend/database/schema.py:412-548`)
already built a substantial, working PDF pipeline — this phase is a real
*enhancement*, not a greenfield build:

- **`document_sources`**: upload metadata, `status` CHECK (`uploaded,
  validating, ready, processing, review_ready, completed,
  completed_with_warnings, failed, cancelled, archived`),
  `extraction_strategy` CHECK (`auto, embedded_text, ocr, hybrid`).
- **`document_pages`**: `raw_text` and `cleaned_text` are **already
  separate columns**; `confidence_score REAL` is **already nullable**
  and constrained to `0-1 or NULL` (never fabricated already);
  `extraction_method` CHECK (`none, embedded, ocr, hybrid, manual`);
  `extraction_status` CHECK (`pending, extracting, success, warning,
  failed, skipped`); `warnings_json`.
- **`document_page_revisions`**: an append-only, trigger-immutable
  (`document_revisions_immutable_update/_delete`) correction-history
  table **already exists** for `cleaned_text` edits (`revision_number`,
  `edited_by_admin_public_id`) — `backend/services/document_service.py`'s
  `edit_page()` (line 708) already never touches `raw_text`, inserts a
  new revision row, then updates `document_pages.cleaned_text` to the
  latest value. This is precisely the "raw immutable, corrections
  revisioned" behavior Step 9 asks for — **already built**, for
  corrected text.
- **`document_processing_jobs`**/**`document_processing_events`**:
  bounded job tracking (already has `queued/running/paused/completed/
  completed_with_warnings/failed/cancelled`) with an append-only,
  trigger-immutable event log — this already satisfies most of Step
  14's "job safety" requirements (per-page failure isolation, progress
  reporting, crash-safe state via `try/except` + job status update).
- **`document_candidates`**: the existing segmentation/candidate output
  table, feeding `import_candidates()` (line 1021) — the existing
  document→dataset-record bridge (a direct `INSERT INTO
  dataset_records`, structurally independent of Phase 3's
  `ManualDataCandidateService`/`feedback_dataset_service` bridge, but
  serving the identical purpose for documents). **This must not be
  touched or duplicated.**
- **`clean_document_text()`** (document_service.py:102): NFC normalize,
  CRLF/CR→LF, NUL/ZWSP/BOM strip, whitespace/blank-line collapse, and
  already emits warning codes: `replacement_character`,
  `repeated_garbage`, `high_non_letter_ratio`, `very_short_text`,
  `header_footer_candidate` (a single-page, single-pass heuristic —
  no cross-page aggregation or removal action yet: a real gap this
  phase fills).
- **OCR** (`_ocr_page()`, line 654): `pytesseract.image_to_data(...,
  output_type=Output.DICT)`, page confidence is **already** the mean of
  per-word confidences (`score/100` for `conf >= 0`), returns `None`
  when no confident words are found — confidence is **never fabricated
  today either**. `ocr_capabilities()` (line 142) already degrades
  gracefully (`ocr_available: False`, no exception) when Tesseract or
  the Tamil/English language packs are missing.
- **Extraction-method decision** (`process()`, line 433): **character-
  count only** (`len(embedded.strip()) < settings.ocr_min_text_length`)
  — a genuine gap; Step 5 asks for Tamil-ratio/glyph/lexical signals.
- **No page-image persistence**: pages are rendered to a `Pixmap`
  on-the-fly via PyMuPDF only during OCR, never saved to disk — the
  frontend's Page Review tab today shows raw text only in a collapsed
  `<details>`, no original-page image at all.
- **No page-level human review state**: `extraction_status` reflects
  *extraction* outcome only, never human-review outcome. There is no
  approve/reject/exclude action anywhere today.
- **No Phase 2 source link**: `document_sources.dataset_source_public_id`
  links to the *old* `dataset_sources` table (used by
  `import_candidates()`'s own source resolution), not Phase 2's
  `data_sources`. However, Phase 2's `core_model/data_governance/__init__.py`
  `ENTITY_TYPES` tuple **already includes `'document'` and
  `'document_page'`** as valid `source_record_links.entity_type`
  values — the mechanism was designed for, just never wired up.

## 2. Architecture decision

Two duplicate-cleanup implementations already exist in the repo
(`document_service.clean_document_text()` for the PDF-workspace
pipeline specifically, and the separate, unrelated
`core_model/corpus/ocr_cleanup.py` for the Phase 19/20 corpus-builder
pipeline). Phase 4 extends the **first** one (the one actually wired
into `document_pages`) with a new *suggestion-generating* layer
(original span, proposed replacement, reason, confidence — never
auto-applied), reusing its detection regex style rather than importing
`ocr_cleanup.py`, which belongs to a different, unrelated pipeline.

**Source linking**: reuse `source_record_links(entity_type='document',
entity_public_id=<document public_id>)` directly — no schema change
needed at all for this, since Phase 2 already enumerated `'document'`
as a supported entity type. This differs from Phase 3's choice (a
direct FK column), because a document naturally fits the "polymorphic
link to any entity" model Phase 2 built, and unlike Manual Data
Studio's *mandatory-at-creation* source, an upload may reasonably
happen before a source is chosen (legacy documents included) —
`source_record_links` already supports zero-or-one links gracefully
(reported as `unlinked` when absent, per Phase 2's own convention).

**Raw-text immutability across *reprocessing*** (rule 6) is subtly
different from raw-text immutability within a single extraction (which
already holds — `edit_page()` never touches `raw_text`). Today,
*re-running* extraction (`process(..., reprocess=True)`) legitimately
overwrites `document_pages.raw_text` with a fresh attempt — necessary,
existing, desired behavior (a bad scan should be re-extractable). To
satisfy rule 6 without breaking that, Phase 4 adds an **append-only**
`document_page_extractions` history table: every extraction/reprocess
attempt is additionally recorded here in full (immutable by trigger),
while `document_pages.raw_text`/`cleaned_text` continue to serve as
"current" convenience columns exactly as before. Nothing is ever
destroyed; the current-pointer columns and the full history simply
coexist, exactly mirroring how `document_page_revisions` already
coexists with `document_pages.cleaned_text`.

**`document_page_extraction_revisions`** (recommended in the task) is
**not created** — `document_page_revisions` already is this table,
just under an established name; creating a second one would be exactly
the "second parallel system" rule 5 forbids.

**`document_page_regions`** (bounding-box region classification) is
**deferred, not built**. True layout/region detection needs image
analysis capability this environment doesn't have configured, and the
task's own out-of-scope list excludes "image understanding beyond
page-region classification." The Step 19 approval workflow is
fundamentally page-level, not region-level, so nothing in this phase's
required completion criteria depends on it. Documented here as
explicitly deferred, not silently dropped.

**`document_cleanup_profiles`** (configurable preprocessing profiles)
is **not built as a table** — Step 6's image preprocessing is scoped
down to what's honestly deliverable without new heavy dependencies in
a CPU-only environment (grayscale via Pillow, already-available
`page.rotation` from PyMuPDF) rather than real deskew/denoise/adaptive-
threshold algorithms, which would need OpenCV (not currently a
dependency). What preprocessing *is* applied is still recorded per
extraction attempt (`preprocessing_metadata_json` on
`document_page_extractions`: `rotation_applied`, `preprocessing_profile
= "default_v1"`, `preprocessing_version = 1`) — satisfying the
metadata-storage requirement without a redundant profile-config table
for a single fixed profile.

## 3. Page-level review lifecycle (Step 2)

Layered **on top of**, not duplicating, the existing `extraction_status`
(which stays exactly as-is — `pending/extracting/success/warning/
failed/skipped` continues to mean extraction outcome only). A new
`document_pages.review_status` column (added via `ALTER TABLE ADD
COLUMN`, mirroring Phase 22's `PHASE22_COLUMNS` convention — plain
`TEXT NOT NULL DEFAULT`, no inline CHECK, validated in the service
layer, exactly like that precedent) tracks human review outcome only:

```
pending -> needs_correction | approved | rejected | excluded
needs_correction -> corrected | rejected | excluded
corrected -> approved | needs_correction | rejected | excluded
approved -> needs_correction   (correction pathway, mirrors Phase 3's approved -> draft)
rejected -> pending | needs_correction
excluded -> pending
```

Document-level status is **not extended** — the existing `status`
CHECK already covers every state the task's Step 2 list maps to
(`uploaded/validating/ready≈ready_for_extraction/processing≈extracting
+needs_ocr+processing_ocr/review_ready≈needs_page_review/completed/
completed_with_warnings/failed/cancelled/archived`). The two genuinely
new ideas — "partially reviewed" and "review complete" — are **computed
readiness states** (Step 21), not stored columns, since they're derived
from page review-status counts rather than being an independent fact
about the document.

## 4. Proposed additive schema (migration 025)

| Table | Purpose |
|---|---|
| `document_page_extractions` | Append-only history of every raw extraction/reprocess attempt per page (satisfies rule 6 without altering existing reprocess behavior). |
| `document_page_review_events` | Append-only human review action log (approve/reject/exclude/request-correction/request-rerun/restore), mirrors `source_verification_events`. |
| `document_repeated_elements` | Cross-page repeated header/footer/page-number suggestions with bulk accept/reject actions. |

Plus `ALTER TABLE document_pages ADD COLUMN`: `review_status`,
`reviewed_by_admin_public_id`, `reviewed_at`, `review_notes`,
`approved_revision_number` (records which `document_page_revisions.revision_number`
was the one approved, so a later correction can be compared against it
and the approved snapshot is never mutated).

No existing table's columns, CHECK constraints, or triggers are
altered. `SCHEMA_VERSION` moves 24 -> 25.

## 5. Extraction strategy enhancement (Step 5)

`process()`'s `needs_ocr`/method decision gains a pure helper
(`core_model/document_workspace/extraction_decision.py`) that layers
Tamil-character ratio, replacement-glyph ratio, and lexical-content
signals on top of the existing character-count check, returning the
method **and a reason string** (stored in
`document_page_extractions.extraction_warnings_json`) — the existing
character-count gate remains as one signal among several, not replaced.

## 6. API plan

Additive only, under the existing `/admin/documents` prefix (Step 13's
list, using `page_number` in the URL exactly like every existing page
route, not `page_id`): workspace summary, page-image render, cleanup
suggestions, repeated-element list/review, page review actions
(approve/reject/exclude/request-correction/request-rerun), and a
segmentation-readiness/handoff endpoint. No existing endpoint's path,
method, or response shape changes.

## 7. Frontend plan

Enhance `DocumentsPage.jsx` with a new **PDF Workspace** tab/section
(reusing its existing tab bar, `.dataset-tabs`/`.metric-grid`/
`.status-card`/`.data-list`/`.panel-controls`/`.history-panel`
conventions) rather than a second, competing document list page — the
existing 5 tabs (`Overview, Upload, Processing, Page Review,
Candidates`) stay exactly as they are; `Page Review` gains the new
raw/corrected/compare/metadata sub-tabs and the original-page image
pane alongside its existing text editor, and a new top-level workspace
overview + repeated-element review surface is added as new tabs on the
same page rather than a new sidebar entry, per Step 15's "either
enhance the existing Documents page... or add a new item" — enhancing
in place avoids nav duplication risk entirely and keeps one page
listing documents.

## 8. Compatibility risks

- **Risk**: modifying `process()`/`edit_page()` in place could break
  `tests/backend/test_document_pipeline.py`'s existing assertions
  (exact `document_page_revisions` count, exact audit-event counts,
  page response shape). **Mitigation**: every change is additive (new
  columns default to `'pending'`/NULL, new tables are separate INSERTs
  alongside existing ones); the existing test file is re-run after every
  change to confirm zero regressions before writing new tests.
- **Risk**: `SCHEMA_VERSION` moving 24->25 triggers the same class of
  hardcoded-version-assertion regression hit in Phases 1-3.
  **Mitigation**: grep for `SCHEMA_VERSION == 2[0-9]` and hardcoded
  `applied_migrations` sets before the final verification pass.
- **Risk**: page-image rendering could be resource-intensive.
  **Mitigation**: reuse the existing `pdf_render_dpi`/
  `pdf_max_render_pixels` settings guards already enforced in
  `_ocr_page()`, applied identically to the new render endpoint.

## 9. Explicitly deferred (this phase)

`document_page_regions` (region-level bounding boxes/layout analysis),
`document_cleanup_profiles` (multiple configurable preprocessing
profiles — one fixed profile is implemented instead), real image
deskew/denoise/adaptive-threshold (CPU-only, Pillow-level operations
only), AI-based OCR correction, semantic chunk editing, dictionary
parsing, translation/Tanglish generation, semantic duplicate
embeddings, hard rights enforcement in every pipeline, floating Admin
Assistant, web crawling, automated license lookup, handwriting OCR —
all per the task's explicit out-of-scope list.
