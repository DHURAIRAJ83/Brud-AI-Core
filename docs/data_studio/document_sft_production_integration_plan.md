# Document SFT Production Integration — Plan

## Reuse

- `DocumentSftDatasetHandoffService`, `DocumentContentClassificationService`,
  `DocumentSecurityReviewService`, `DocumentTamilCorrectionRegistryService`,
  `DocumentSftCandidateGenerationService`, `DocumentSftExportService` — unchanged
  business logic, called directly from new REST routes exactly as the Admin Assistant
  already calls them. No second implementation of dedup, checksum, split/leakage, or
  lifecycle-transition logic.
- `backend/core/exceptions.py`'s existing `NotFoundError`→404 / `ConflictError`→409 /
  `ValidationError`→422 mapping — reused as the stable error schema. No new
  `rights_blocked`/`security_blocked`/`checksum_conflict` error codes were invented;
  those conditions already raise the correct existing exception types with a
  descriptive message, which is what every other document endpoint in this codebase
  does.
- `CsrfDependency`/`AdminDependency`/`require_admin`, `SettingsDependency` — reused
  unchanged for every new endpoint.
- `DocumentsPage.jsx` / `DocumentWizardPage.jsx` — extended, not replaced.

## Admin API design

Extend `backend/api/routes/documents.py` (the established document Admin router)
rather than a new routing module, per the repository's own convention of one router
per resource family. The one exception is Tamil correction rules: that table has no
`document_source_id` column (it is a global, versioned registry, not a per-document
resource), so it gets a second `APIRouter` instance in the same file
(`tamil_correction_rules_router`, prefix `/admin/document-tamil-correction-rules`),
registered once in `backend/api/router.py`. This avoids forcing a global resource into
a `{document_id}`-scoped URL it doesn't belong under, while still keeping the routing
in one file.

## State transitions

No new state machines were introduced. Handoff status
(`imported→version_proposed→version_built`), export validation (stateless, re-derives
checksum from disk), and Tamil rule lifecycle
(`draft→needs_review→approved→active`, `→rejected` from any state) are the existing
service-layer state machines, invoked unchanged from the new routes.

## CSRF/auth

Every mutation route uses `CsrfDependency` (matches `apply-cleanup`, `sft-export`,
etc.); every read route requires only `require_admin` via the router's shared
`dependencies=[Depends(require_admin)]`. No new auth path.

## Idempotency

`ingest()` already keys on `export_public_id` (unique) and compares
`export_checksum_sha256` on retry — reused unchanged. The new `handoff-ingest` route
adds no additional idempotency logic.

## vision-required enforcement

`DocumentSftCandidateGenerationService.generate()` now queries
`document_content_classifications` for `vision_required=1` pages belonging to the
document, splits the approved-chunk set into eligible/blocked before calling any
generator, and raises `ValidationError` only if *every* approved chunk is blocked.
Each blocked chunk is reported with `page_number`, `content_classification`,
`review_status`, and `blocking_reason` in the response's new `vision_blocked` key.
This is additive: documents with no classification rows (the common case before
`content-classifications/scan` is ever run) are completely unaffected.

## Remaining generator decisions

Re-reviewed all 6 deferred generators against the evidence each would require
(§12 of the task). None of the required source data exists in this repository today:
- `contextual_meaning` / `multiple_meanings`: would need reviewed target-word +
  context + approved-meaning records; no such reviewed table exists.
- `clarification_request`: would need an approved ambiguity registry; none exists.
- `computer_basics`: would need a stable, approved computer-domain chunk source with
  version-sensitive facts excluded; no such curated source exists.
- `safety_response`: would need existing approved safety policy templates; none exist
  in this codebase.
Generating any of these now would mean inventing a heuristic from document content,
which the task explicitly forbids ("Do not invent low-quality heuristics simply to
claim 17/17 support"). They remain deferred, and the new `generator-eligibility`
endpoint surfaces the reason for each so an Admin can see exactly why.

## Performance bounds

8 new `Settings` fields (`document_sft_handoff_max_records`,
`document_sft_generator_max_candidates`, `document_cleanup_max_findings_per_page`,
`document_tamil_max_findings_per_page`, `document_security_max_findings_per_page`,
`document_classification_max_pages_per_job`, `document_sft_split_preview_max_records`,
`document_sft_api_page_size_max`), each with a conservative default sized for ~6GB
RAM, wired directly into the relevant service loop (per-page finding caps, per-job
page caps, per-request record caps) rather than left as unused configuration.
`document_sft_split_preview_max_records` documents the existing, already-bounded
`DatasetVersioningService._preview()` behavior (excluded list capped at 100 records)
rather than duplicating a second bound on a service this task explicitly says to reuse
unchanged.

## Browser test design (as executed)

Given tight session RAM (see final report), the full upload→...→build browser path was
not re-run through Playwright this pass. The identical flow is instead exercised at
the HTTP layer in `tests/backend/test_document_sft_production_integration_api.py`
against the real FastAPI app + a real SQLite database via `httpx.AsyncClient`,
including the idempotent-retry, checksum-conflict, and training_jobs-unchanged
assertions the task requires.

## Canonical regression strategy

Same policy as the prior two passes: a large, sequential, resource-conscious targeted
regression sweep across every touched file plus adjacent regression-risk areas,
documented with real pass counts; the full 70-batch `ProductionRegressionService`
manifest is disclosed as not attempted, consistent with 6+ earlier failed attempts
this session that were host/harness restarts, not product bugs.

## Explicit out-of-scope for this pass

- New REST-level deep-link query-string navigation between Dashboard tabs.
- Admin Assistant UI wiring that turns its answers into clickable Dashboard links
  (the read-only tools that back those answers already existed and are unchanged).
- A 10th `DocumentsPage` tab duplicating the Wizard's Dataset Handoff steps.
- Vision models, image embeddings, voice, video, external MCP, payments, automatic
  training/release/activation/promotion, live web ingestion — unchanged exclusions
  from every prior pass.
