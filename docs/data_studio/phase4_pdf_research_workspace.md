# Phase 4 — PDF Research Workspace

Status: complete. Schema version 24 -> 25 (migration `025_data_studio_phase4_pdf_research_workspace`).

A governed PDF research workspace built **on top of** the existing
Phase 5 document pipeline (`backend/services/document_service.py` +
`/api/admin/documents`) rather than a second, competing ingestion
system. See [phase4_pdf_research_workspace_plan.md](phase4_pdf_research_workspace_plan.md)
for the pre-implementation baseline audit and architectural decisions.

## 1. Architecture

Every new service in `backend/services/document_workspace_service.py`
composes the existing, **unmodified** `DocumentService`/`DocumentRepository`
for shared primitives (`process()`, `edit_page()`, `segment()`,
artifact paths, OCR capabilities) instead of re-implementing them:

- `PDFResearchWorkspaceService` — source/rights linking, workspace
  summary + computed readiness, page-image rendering, extraction with
  history, segmentation handoff.
- `DocumentPageRevisionService` — wraps the existing `edit_page()` with
  audit capture of `change_summary`/`correction_types` and the
  approved-page-reopens-to-`needs_correction` rule.
- `DocumentPageReviewService` — the page-level review lifecycle
  (approve/reject/exclude/reopen/request-correction/request-rerun).
- `DocumentCleanupService` — cleanup suggestions and repeated-element
  detection/review.

Source linking reuses `source_record_links(entity_type='document')`
directly — Phase 2 had already enumerated `'document'`/`'document_page'`
as valid entity types, so this needed **zero schema change**. Unknown
or pending-review source rights are surfaced as warnings but never
silently treated as training permission (§5).

## 2. Schema (migration 025)

Additive only — no existing table's columns, CHECK constraints, or
triggers were altered:

| Table | Purpose |
|---|---|
| `document_page_extractions` | Append-only history of every raw extraction/reprocess attempt per page — satisfies "raw text never overwritten" without changing the existing, legitimate reprocess-overwrites-`raw_text` behavior. |
| `document_page_review_events` | Append-only human review action log (approve/reject/exclude/request-correction/request-rerun/restore). |
| `document_repeated_elements` | Cross-page repeated header/footer/page-number suggestions with bulk accept/reject/apply actions. |

Plus `ALTER TABLE document_pages ADD COLUMN` (mirroring Phase 22's
`PHASE22_COLUMNS` convention — plain columns, no inline CHECK,
validated in the service layer): `review_status` (`TEXT NOT NULL
DEFAULT 'pending'`), `reviewed_by_admin_public_id`, `reviewed_at`,
`review_notes`, `approved_revision_number`.

Existing documents automatically get `review_status='pending'` from
the column default — no destructive backfill script was needed or
written (verified live, Flow F, §8).

## 3. Page-level review lifecycle

Layered on top of, not duplicating, the existing `extraction_status`
(which continues to mean extraction outcome only). `review_status`
(`core_model/document_workspace/lifecycle.py`) tracks human review
outcome only:

```
pending -> needs_correction | approved | rejected | excluded
needs_correction -> corrected | rejected | excluded
corrected -> approved | needs_correction | rejected | excluded
approved -> needs_correction   (correction pathway, mirrors Phase 3's approved -> draft)
rejected -> pending | needs_correction
excluded -> pending
```

A same-state transition (e.g. `pending -> pending`, used by
request-OCR-rerun/request-extraction-rerun regardless of current
status) is always a legal no-op — a real bug surfaced this during
manual testing (§9).

Approving a page with no prior manual revision first snapshots the
current `cleaned_text` as revision 1 (via the existing `edit_page()`),
so "raw extraction explicitly accepted" always has a concrete,
restorable revision behind it rather than an implicit "nothing was
ever revised" state.

## 4. Extraction strategy and cleanup suggestions

`core_model/document_workspace/extraction_decision.py` layers
Tamil-character ratio, replacement-glyph ratio, and lexical-content
signals on top of the existing character-count gate, returning the
chosen method plus an explicit reason and signal breakdown — the old
gate remains one signal among several, not replaced.

`core_model/document_workspace/cleanup_suggestions.py` generates
targeted, non-destructive suggestions (replacement-glyph warnings,
broken-word joins, repeated whitespace, suspicious Latin-in-Tamil,
duplicated lines, page-number lines, unbalanced punctuation) — each
carries `{suggestion_type, original_text, proposed_text, reason,
confidence}` and is never auto-applied; the admin accepts them
explicitly through `DocumentCleanupService.apply_suggestions()`, which
routes through the same revisioned `save_draft()` path as any manual
edit.

`core_model/document_workspace/repeated_elements.py` aggregates
boundary lines across every page of a document and flags a candidate
as repeated only past a confidence threshold based on page-occurrence
fraction — verified live against a real 4-page PDF with a constant
header and a varying page-number footer: the header was correctly
flagged (confidence 0.9, pages 1-4) and the footer was correctly
**not** flagged, since its text differs per page (§8, Flow D).

## 5. Source-rights integration and OCR confidence honesty

`workspace()` computes `source_status`/`rights_warnings` fresh on every
call (never a cached decision) and a `readiness` value
(`not_ready`/`partially_ready`/`ready_for_segmentation`) derived from
review-status counts and source-link status. `approve()` hard-refuses
(422) when no source is linked yet ("the document has no linked
source -- link a source before approving pages") — verified live
against the real API (§8, Flow A).

OCR confidence is passed through exactly as Tesseract reports it
(mean of per-word confidences, `None` when no confident words are
found) — never fabricated. Verified live: a genuinely scanned Tamil
page rendered a real `79%` confidence figure end-to-end from Tesseract
through the API into the Page Review UI (§8, Flow B); an embedded-text
page correctly shows "confidence unavailable" rather than a fake
number.

## 6. Backend: repository / service / API layers

- `backend/database/repositories/documents.py` — extended (not
  replaced) with `create_extraction`, `list_extractions`,
  `update_page_review`, `add_review_event`, `list_review_events`,
  `create_repeated_element`, `list_repeated_elements`,
  `update_repeated_element`, `clear_repeated_elements`.
- `backend/services/document_workspace_service.py` — the four services
  from §1.
- `backend/api/routes/documents.py` — ~21 new endpoints added under the
  existing `/api/admin/documents` prefix; the existing `edit_page`
  handler now routes through `DocumentPageRevisionService.save_draft()`
  instead of the raw repository call (a safe, additive enhancement,
  verified against the existing `test_document_pipeline.py` with zero
  regressions):

  ```
  GET    /api/admin/documents/{id}/workspace
  POST   /api/admin/documents/{id}/source-link
  GET    /api/admin/documents/{id}/pages/{page_number}/image
  GET    /api/admin/documents/{id}/pages/{page_number}/extractions
  GET    /api/admin/documents/{id}/pages/{page_number}/revisions
  POST   /api/admin/documents/{id}/pages/{page_number}/revisions/{revision_number}/restore
  POST   /api/admin/documents/{id}/pages/{page_number}/approve
  POST   /api/admin/documents/{id}/pages/{page_number}/reject
  POST   /api/admin/documents/{id}/pages/{page_number}/exclude
  POST   /api/admin/documents/{id}/pages/{page_number}/reopen
  POST   /api/admin/documents/{id}/pages/{page_number}/request-correction
  POST   /api/admin/documents/{id}/pages/{page_number}/request-ocr-rerun
  POST   /api/admin/documents/{id}/pages/{page_number}/request-extraction-rerun
  GET    /api/admin/documents/{id}/pages/{page_number}/review-events
  GET    /api/admin/documents/{id}/review-summary
  GET    /api/admin/documents/{id}/pages/{page_number}/cleanup-suggestions
  POST   /api/admin/documents/{id}/pages/{page_number}/apply-cleanup
  POST   /api/admin/documents/{id}/repeated-elements/detect
  GET    /api/admin/documents/{id}/repeated-elements
  POST   /api/admin/documents/{id}/repeated-elements/{element_id}/review
  POST   /api/admin/documents/{id}/send-to-segmentation
  ```

All existing document routes/tables/lifecycle states are unchanged;
`DocumentService.process()`/`.edit_page()`/`.segment()` are called
exactly as they already existed and were never modified in place.

## 7. Frontend

`DocumentsPage.jsx` enhanced in place (no second document list page):
tab bar extended from 5 to 6 tabs (`Overview, Upload, Processing, Page
Review, Repeated Elements, Candidates`).

- **Processing tab** gained a "Source & readiness" panel: source-link
  input/button, rights warnings, computed readiness, a review-status
  count grid, low-confidence/warning counts, and a "Send approved
  pages to existing segmentation" button (disabled until
  `readiness !== 'not_ready'`).
- **Page Review tab** gained a two-pane layout: the original page image
  (fit-width/fit-page toggle, rotate) alongside `Raw / Corrected /
  Compare / Metadata` sub-tabs (raw text read-only; corrected text
  editable with change-summary + Save Draft/Request OCR Rerun/Request
  Extraction Rerun/Reprocess actions; compare shows raw-vs-corrected
  plus full revision history with per-revision restore; metadata shows
  cleanup suggestions and the review-event history), and a review
  decision panel (Approve/Reject/Exclude/Reopen/Request Correction).
- **Repeated Elements tab** (new): detect button, per-suggestion
  accept/reject/apply-to-all-matching-pages actions.
- `helpRegistry.js`'s existing bilingual `documents` entry was updated
  (not duplicated) to describe source linking, the image/sub-tab
  review workflow, repeated-element cleanup, and the
  approval-is-not-training-approval safety note.

## 8. Manual browser verification (Flows A-F)

All six required flows were exercised end-to-end against the real dev
server + real backend (Playwright), each with a genuinely valid test
PDF (Tamil text rendered with Noto Sans Tamil, not a Latin-only font,
after an early test revealed a corrupted embedded-text PDF is a test-data
defect, not an app bug — see §9):

- **Flow A (embedded-text Tamil PDF)**: upload -> analyze -> process
  (2/2 pages, `embedded`, `success`) -> approve blocked with a clean
  422 before a source is linked -> link a real source -> Page Review
  shows the rendered page image and all four sub-tabs -> approve
  succeeds, snapshotting revision 1 -> status badge flips to
  `APPROVED`; workspace readiness correctly moves `not_ready ->
  partially_ready`.
- **Flow B (scanned Tamil PDF, no embedded text layer)**: extraction
  method auto-selected `ocr`; a real, non-fabricated `79%` confidence
  score rendered end-to-end; OCR misreadings visible in the raw text
  exactly as expected for a correction workflow to fix.
- **Flow C (mixed document + retry)**: a two-page document with page 1
  embedded-text and page 2 image-only correctly extracted with
  *different* per-page methods (`embedded` / `ocr`) and confidences
  (`null` / `0.72`) in the same `process()` call; a targeted
  single-page reprocess (`strategy=ocr`) on page 2 completed
  successfully, confirming per-page retry.
- **Flow D (repeated header/footer)**: a 4-page PDF with one constant
  header line and a varying footer -> detection correctly flagged only
  the header (confidence 0.9, pages 1-4), correctly excluding the
  varying footer.
- **Flow E (correction after approval)**: approving a page, then
  editing its corrected text, correctly reopened the page from
  `APPROVED` to `NEEDS_CORRECTION`; the Compare sub-tab showed both
  revisions with working Restore buttons; raw text remained untouched
  throughout.
- **Flow F (legacy document, uploaded before this phase existed)**:
  opening a pre-Phase-4 archived document worked with zero destructive
  backfill — `review_status` defaulted to `pending` from the column
  default, the page was fully readable/reviewable, and a missing
  archived page image degraded gracefully ("Original page image is
  unavailable.") instead of crashing.

Also verified directly against the real backend/API (outside the
browser): a linked source with unknown rights correctly surfaces a
"Source rights are unknown or still pending review." warning without
blocking the link itself; `readiness` genuinely recomputes on every
`workspace()` call rather than being cached.

## 9. Real bugs found and fixed during manual verification

1. **Self-transition (`pending -> pending`) incorrectly raised a 422.**
   `request_ocr_rerun`/`request_extraction_rerun` always transition to
   `pending` regardless of current status, but a fresh page's status
   is already `pending`; `can_transition()` didn't allow same-state
   transitions. Fixed by making same-state transitions always legal
   no-ops (a defensible general state-machine convention). Regression
   test added covering all 6 review statuses.
2. **`decide_extraction_method_preview()` had a dead `or True`** that
   made `has_renderable_image` always `True` regardless of the actual
   page. Fixed to key off OCR-capability availability instead (OCR
   renders the whole page via PyMuPDF regardless of embedded image
   count).
3. **`link_source()` transaction-scoping bug**: the link's public row
   was originally fetched using a connection from an already-closed,
   unrelated transaction block. Fixed by building the result inside
   the same transaction that created the link.
4. **Approving a page with no prior revision left no concrete
   "approved revision" to compare against or restore.** Fixed by
   snapshotting the current `cleaned_text` as revision 1 before
   transitioning to `approved` whenever no revision exists yet (§3).
5. **Repeated Elements/Candidates tab actions silently returned the
   admin to the Processing tab after every click** — caught by the new
   frontend test suite, not manual testing. The shared `action()`
   helper always called `open()`, which unconditionally reset the
   active tab to `Processing`; page-review actions were unaffected
   (they use a separate `reviewAction()` helper that reopens the
   current page instead). This would have made iterative repeated-
   element review effectively unusable (every accept/reject click
   would kick the admin back to Processing). Fixed by adding an
   opt-in `keepTab` option threaded through `action()`/`open()`,
   applied only to the new Repeated Elements actions (the pre-existing
   Candidates tab behavior was left untouched, since it predates this
   phase and touching it is out of scope). Also fixed: accepting or
   rejecting a repeated-element suggestion now reloads the list
   afterward, so a suggestion's status badge and button
   enabled/disabled state stay in sync with the backend.
6. **Test-data defect, not an app bug**: an early manual-verification
   PDF used the Helvetica font for Tamil text, which has no Tamil
   glyphs — PyMuPDF embedded only placeholder dots, causing every page
   to genuinely fail extraction (0/2 successful). Rebuilding the test
   PDF with an actual Tamil-glyph font (Noto Sans Tamil) confirmed
   extraction succeeds correctly; recorded here since it was initially
   indistinguishable from a real defect until traced to the source PDF.

## 10. Test evidence

New tests added this phase (all passing):

| File | Tests |
|---|---|
| `tests/database/test_phase25_migration.py` | 5 |
| `tests/database/test_document_workspace_repository.py` | 5 |
| `tests/core_model/test_document_workspace_extraction_decision.py` | 7 |
| `tests/core_model/test_document_workspace_cleanup_suggestions.py` | 13 |
| `tests/core_model/test_document_workspace_repeated_elements.py` | 6 |
| `tests/core_model/test_document_workspace_lifecycle.py` | 7 |
| `tests/backend/test_document_workspace_service.py` | 17 |
| `tests/backend/test_document_workspace_api.py` | 12 |
| `apps/admin-dashboard/src/pages/DocumentsPage.test.jsx` | 9 |
| **Total new** | **81** |

Regression-safety updates required by the schema-version bump
(24 -> 25, same class of issue hit in Phases 1-3): `tests/backend/test_system_api.py`
gained `"025_data_studio_phase4_pdf_research_workspace"` in the expected
`applied_migrations` set.

Final verification run (this session, 2026-07-26):

- `ruff check backend/ core_model/ tests/` — clean.
- `npm run test --prefix apps/admin-dashboard -- --run` — **53 passed**
  (5 files), including the 9 new `DocumentsPage.test.jsx` tests.
- `npm run build --prefix apps/admin-dashboard` — succeeds.
- Full `python -m pytest -q` (backend + core_model + database) —
  **770 passed**, 0 failed (18m25s). Run after clearing accumulated
  `/tmp/pytest-of-dhurai` tmp dirs from earlier phases (a known
  disk-pressure failure mode from this same long session, not a code
  defect).
- `python -m backend.database.migrations status` — current version 25,
  all 25 migrations listed as applied.
- `python -m backend.database.migrations verify` — `{"integrity_check":
  "ok", "foreign_key_violations": []}`.

## 11. Limitations / explicitly deferred

- `document_page_regions` (bounding-box/layout analysis) and
  `document_cleanup_profiles` (multiple configurable preprocessing
  profiles) are explicitly deferred, as documented in the plan doc —
  no CV/layout library is available in this environment, and the
  task's own out-of-scope list excludes "image understanding beyond
  page-region classification."
- Image preprocessing is limited to what's honestly deliverable
  CPU-only (rotation metadata capture); real deskew/denoise/adaptive-
  threshold would need OpenCV, not a current dependency.
- No existing document, page, or candidate record was backfilled or
  destructively modified — this phase only adds new tables/columns and
  new admin-facing workflows on top of the unmodified Phase 5 pipeline.
- Out of scope per the task's explicit list and left untouched:
  region-level bounding boxes, AI-based OCR correction beyond
  deterministic suggestions, semantic chunk editing, dictionary
  parsing, translation/Tanglish generation, semantic duplicate
  embeddings, hard rights enforcement inside the segmentation/
  candidate pipeline itself, floating Admin Assistant, web crawling,
  automated licence lookup, handwriting OCR.

**Do not proceed to Phase 5.**
