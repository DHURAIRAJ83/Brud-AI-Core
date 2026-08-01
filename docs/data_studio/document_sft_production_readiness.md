# Document SFT — Production Readiness (Production Integration pass)

## Summary

The Schema-44 Document SFT subsystems (dataset handoff, expanded generators, cleanup
detectors, Tamil correction governance, media/table classification, security/PII
review) built in the prior pass are now reachable through governed Admin REST APIs
and a real Admin Dashboard workflow, not only through Python service calls and the
Admin Assistant's tools/proposals. `vision_required` content is now structurally
excluded from text-only SFT generation. Performance bounds exist for every named
service. No new database migration was required.

## Security boundaries (unchanged from the prior pass, re-verified this pass)

- Every mutation route requires Admin auth + CSRF, matching every other document
  route in this router.
- Secrets and absolute filesystem paths always block export
  (`DocumentSftExportService.export()`'s security gate, unchanged); this is
  independently re-verified via the new `handoff-ingest` idempotency test path,
  which never bypasses the export-time gate.
- Detected prompt-injection content is stored and flagged only -- no code path in
  this repository feeds document text into an LLM/instruction-following context, so
  it is structurally incapable of altering Admin Assistant or system behavior.
- The security-finding review endpoint cannot flip a `block_export`/`exclude_from_sft`
  finding's own `action` -- only `reviewed`/`dismissed` on the review-status field
  (see `document_sft_admin_api.md`).

## vision-required behavior

`generate()` excludes any approved chunk whose page has
`document_content_classifications.vision_required=1`, reports each exclusion with
page number, classification, and reason, and only blocks generation entirely if
*every* approved chunk is excluded. Verified by 3 new tests in
`tests/backend/test_document_sft_vision_blocking.py`.

## Handoff idempotency / dataset-version build

Unchanged, reused service logic; re-verified end-to-end via HTTP in
`test_document_sft_production_integration_api.py`: same export ingested twice
produces the same handoff record with `imported_count` unchanged; a tampered stored
checksum returns 409; `training_jobs` row count is asserted `0` after a full
propose→preview→confirm-build cycle.

## Performance bounds

| Setting | Default | Enforced in |
|---|---|---|
| `document_sft_handoff_max_records` | 500 | `DocumentSftDatasetHandoffService.preview()`/`ingest()` |
| `document_sft_generator_max_candidates` | 100 | `DocumentSftCandidateGenerationService.generate()` |
| `document_cleanup_max_findings_per_page` | 50 | `DocumentCleanupService.suggestions()` |
| `document_tamil_max_findings_per_page` | 50 | `DocumentTamilQualityService.detect()` |
| `document_security_max_findings_per_page` | 50 | `DocumentSecurityReviewService.scan_document()` |
| `document_classification_max_pages_per_job` | 200 | `DocumentContentClassificationService.classify_document()` |
| `document_sft_split_preview_max_records` | 1,000 | documented against the existing, already-bounded `DatasetVersioningService._preview()` (excluded list capped at 100) |
| `document_sft_api_page_size_max` | 200 | matches the literal `le=200` already used on the new list endpoints, consistent with every existing document list endpoint in this router |

No job-ID/progress-tracking infrastructure was added for these operations: every
one of them (candidate generation, handoff ingest, security/classification scans)
already completes synchronously within a single bounded request, the same as every
other document-workspace mutation in this codebase (page approval, cleanup
application, Tamil quality detection). Adding asynchronous job tracking for
operations that are already fast and bounded was judged unnecessary scope.

## Test evidence (see final report for exact commands/counts)

- 58 new/updated backend unit tests for vision blocking + the new REST API surface.
- 163 backend tests re-run across every touched file plus adjacent regression-risk
  areas (workflow service/API/security/admin-assistant, workspace API, finalization
  detectors, repeated elements, system API, dataset API, semantic chunks, handoff),
  all passing.
- 202 admin-dashboard frontend tests (full suite), all passing, including 6 new
  tests for the extended Wizard and the 3 new Dashboard tabs.
- `ruff check .` (whole repo): all checks passed.
- `git diff --check`: clean.
- `npm run build` (admin-dashboard): succeeds.

## Known limitations (see final report for the complete list)

No new REST-level deep-link navigation; no dedicated 10th "Dataset Handoff" tab
(consolidated into the Wizard); Admin Assistant answers are not yet wired to
Dashboard deep-links; no new Playwright browser run this pass (API-layer integration
test used instead, see `document_sft_browser_workflow.md`); full 70-batch canonical
regression manifest not attempted; 6 SFT generator types remain deferred for lack of
non-fabricated source data.
