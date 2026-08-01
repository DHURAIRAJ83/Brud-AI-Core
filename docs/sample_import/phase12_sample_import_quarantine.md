# Phase 12 — Approved Sample Import, Quarantine, File Safety, PII & Data Quality Validation

Status: **implemented**. Supersedes the planning assumptions in
`phase12_sample_import_quarantine_plan.md` where the two diverge.

## Purpose

Lets an Admin take a **finalized** Phase 11 dataset verification case and safely inspect a small,
bounded sample of real file content: download into isolated quarantine, validate file safety, scan
for malware-like content, safely extract archives, parse supported formats, and check for PII,
safety issues, quality problems, duplicates, and evaluation contamination — producing an immutable
sample-validation report and a `rag_sandbox_eligible` boolean. Phase 12 never downloads a full
dataset, clones a repository, executes downloaded content, activates RAG, creates a training
dataset version, starts training, or releases a model, and it can never grant training approval —
no status value spelling "training_approved" exists anywhere in its code.

## Architecture

12 additive tables (migration 035, schema 34 → 35), all under `external_dataset_sample_*`:
`_imports`, `_import_approvals`, `_files`, `_download_events`, `_extraction_events`,
`_scan_results`, `_records`, `_record_issues`, `_reviews`, `_reports`, `_events`,
`_deletion_requests`. Download/extraction events, scan results, reviews, reports, and events are
append-only (delete- and update-blocked by trigger); deletion requests are append-only transitions
(`requested` → `confirmed` → `executed`/`cancelled`, each its own row sharing a
`deletion_request_code`); the approval table is immutable once `status='approved'` except
transitioning to `expired`/`superseded` (trigger-enforced).

## Schema

18 lifecycle statuses, 13 stages (tracked as its own column, never conflated with status), 6
approval purposes (`production_rag`/`training`/`model_release` are structurally rejected by
`core_model.sample_import.validate_sample_import_purpose()`), 8 file statuses, 6 scan verdicts, 6
sample languages, 17 PII categories with 7 finding statuses, 12 safety categories, 4 quality
states, 3 duplicate/conflict grouping dimensions, 4 contamination statuses, 5 poisoning results, 8
review decisions, 5 training-assessment statuses (no "approved" value exists in this enum).

## Eligibility gate (Step 6)

`ExternalDatasetSampleEligibilityService.check_eligibility()` verifies: verification case
finalized, identity in `STRONG_IDENTITY_STATUSES`, verification not expired/source-changed, no
active withdrawal notice, no unresolved upstream source, the purpose-relevant permission
(`rag_use` for `rag_sandbox_preparation`, `evaluation_use` otherwise) not `not_approved`/
`prohibited`, provider enabled and not blocked (`core_model.data_providers.is_usable_for_
discovery()`, reused unchanged), and dataset version/revision pinned (warning only, non-blocking).
Training permission is never required for a RAG-oriented sample. `.create_sample_import()` is the
only entry point that turns a passing check into a real `draft` row; a failing check raises
`DatasetSampleImportError` and creates nothing.

## Approval binding (Step 5)

A separate `external_dataset_sample_import_approvals` row binds candidate/case/provider/version/
revision/sample_size/allowed_files/formats/max_bytes/purpose/expiry. `compute_target_fingerprint()`
digests the live case's status/expiry/licence fields plus the bound dataset_version/revision; this
same pure function is registered into the Admin Assistant's `STALE_CHECK_FINGERPRINTS` (checked at
both `review()` and `execute()`) **and** re-checked defense-in-depth by
`ExternalDatasetSampleDownloadService._require_approved()` immediately before every download —
covering both the Assistant path and any direct API call. An **expiry-date check** was added during
Step 37's security pass after a gap was found: the approval's own `expires_at` field was stored but
never enforced at download time; `_is_expired()` now rejects any download against an
expired-but-otherwise-valid approval.

## Safe download (Step 8)

`dataset_sample_download_transport.stream_download_to_file()` extends Phase 11's domain-allowlist/
SSRF pattern (`is_domain_allowed()`/`default_resolver()`, reused unchanged) with genuine chunked
streaming: the byte cap is enforced per chunk during the stream (never only after completion), the
destination is written to a temporary name and atomically `os.replace()`d into place only once the
stream finishes cleanly, checksums are computed incrementally, at most one re-validated redirect is
followed, credentials-in-URL are rejected outright, and any failure deletes the partial file.

## Quarantine storage (Step 9)

`data/quarantine/external-samples/<sample_import_id>/{original,derived,reports}/` +
`manifest.json`, one directory per import, `0o700` dirs / `0o600` files, never registered on any
static-file route. Deliberately **not** the same directory as the pre-existing, narrower
`data/imports/quarantine/`/`data/documents/quarantine/` "failed validation" buckets from the
existing import/document pipelines. `get_safe_text_preview()` is the only path that can reach an
API response with file content — bounded, decoded-with-replacement, never a raw byte stream.

## File validation & archive safety (Steps 10-11)

`ExternalDatasetFileValidationService` classifies by extension-based block table (scripts, macros,
Java/Android archives, disk images, model-weight files) layered with magic-byte signatures
(MZ/ELF/Mach-O executables, OLE2 macro documents, ZIP/PDF/gzip) and a shebang check — never trusts
an extension alone. `ExternalDatasetArchiveSafetyService` opens zip/tar/tar.gz member-by-member
(never `extractall()`), rejecting path traversal, absolute paths, symlinks, hard links, device
files, encrypted entries, duplicate paths, excessive depth, and nested archives (never
auto-recursed), enforcing a member-count cap, an expanded-bytes cap, and a compression-ratio
threshold, all under a wall-clock timeout.

## Security scan (Step 12)

`ExternalDatasetSecurityScanService` — deterministic only, verdicts are honestly named
(`clean_by_policy`, never a bare "clean"): carries forward file-validation's blocked-class verdict,
plus its own checks for HTML `<script>` tags, CSV formula injection, notebook code cells embedded
in JSON, pickle/joblib signatures, PDF `/JavaScript`/`/EmbeddedFile` markers, polyglot mismatches,
binary content in a declared text file, and filename tricks (RTLO character, hidden double
extensions). Never flags shell-command *text* inside a record's own content — only an actual script
*file* is ever blocked.

## Parsing & normalization (Steps 13-14)

`ExternalDatasetSampleParsingService` supports TXT/Markdown (single record), CSV (delimiter
sniffing, per-row records, malformed-row reporting), JSON (array-or-object, bounded nesting-depth
check), JSONL (per-line, malformed lines reported without aborting), and PDF (embedded-text via
PyMuPDF, encrypted PDFs rejected, page limit, OCR only via an explicitly-injected `ocr_engine`
callable — never automatic). `ExternalDatasetSampleNormalizationService` wraps
`core_model.corpus.unicode_normalization.normalize_unicode()` unchanged, keeping `raw_content` and
`normalized_content` as two separate, always-both-persisted fields.

## Language/Tamil validation (Step 15)

`ExternalDatasetSampleLanguageService` reuses `core_model.corpus.language_detection.assess_
language()` for Tamil/English/Tanglish/Mixed/Other/Unknown classification and
`unicode_normalization.assess_unicode_integrity()` for replacement-character/mojibake detection,
adding an orphaned-combining-mark regex and `tamil_normalization.apply_tamil_ocr_substitutions()`'s
substitution count as OCR-corruption signals. Never silently corrects — every signal only sets
`requires_review=True`; the service returns signals, never a "corrected" text.

## PII, sensitive-data & safety scanning (Steps 16-17)

`ExternalDatasetPIIScanService` wraps `core_model.corpus.pii_detection.detect_pii()`/`redact_pii()`
(email/phone/government-ID-like/address/medical-record patterns) and `secret_detection.
detect_secrets()` (password/API-key/token/private-key/payment-card/bank-account/credentials —
always `blocked`, matching that module's own "no redact-and-keep" rule for genuine secrets).
Government-ID-like patterns start at `possible` (real false-positive risk); everything ambiguous
requires human review. `ExternalDatasetSafetyScanService` wraps `core_model.corpus.safety_filter.
assess_safety()` unchanged, carrying its descriptive/educational/historical/preventive/
operational_harmful behavior classification straight through. Both public APIs report match
*counts*, not offsets — `evidence_location` is count-based by design, never exposing a raw matched
value.

## Quality, duplicates, contamination, poisoning (Steps 18-21)

`ExternalDatasetQualityService` — deterministic structural checks (empty/short/long, encoding
corruption, template repetition, low-information content, broken markup, missing required
fields/invalid labels/question-answer mismatch/unbalanced turns when the record's own structured
payload declares those fields). `ExternalDatasetDuplicateService` — exact/normalized/near-duplicate
grouping (bounded Jaccard word-shingle similarity within one batch only) plus a generic
key-field/value-field conflict detector. `ExternalDatasetContaminationService` calls
`core_model.corpus.contamination.check_contamination()` directly; `status="unknown"` when no
comparison set was supplied, `"confirmed_overlap"` on any exact match (never a fuzzy
`"possible_overlap"` — an honest, disclosed gap). `ExternalDatasetPoisoningCheckService` reuses
`core_model.rag.injection_filter.detect_injection_signals()` unchanged plus new bounded checks for
zero-width/hidden-control/bidi-override characters, a small explicit homoglyph confusable set, and
extreme character/word repetition; batch-level `detect_length_outliers()` uses a z-score threshold.

## Human review (Step 22)

`ExternalDatasetSampleReviewService.review_target()` — every decision is an append-only
`external_dataset_sample_reviews` row; `edit_derived_copy`/`redact_derived_copy` decisions carry
the new derived text directly on that same row (each edit is already its own immutable version, no
separate "derived revisions" table needed). Reviewing an `issue` also updates that issue's own
queryable `reviewer_decision` columns via the repository. The original file/record is never
touched by any review.

## Validation report, RAG-sandbox eligibility, training-assessment signal (Steps 23-25)

`ExternalDatasetSampleReportService.finalize()` refuses outright while any `blocked` scan result or
`blocked` record issue remains unreviewed (mirrors Phase 11's "blocking conflict prevents
finalization" precedent). Once clear, it re-runs the Step 6 eligibility check fresh (never cached
from approval time) and computes `rag_sandbox_eligible = eligible AND no unresolved PII AND at
least one accepted record AND not withdrawn` — a plain boolean; finalize never creates a RAG index.
`training_assessment_status` is one of `core_model.sample_import.TRAINING_ASSESSMENT_STATUSES` (5
advisory values); `blocked` on any confirmed contamination, `needs_more_review` on any unresolved
ambiguous issue, else `potentially_suitable`/`not_suitable` based on accepted-record presence.
Confirmed contamination blocks training assessment but never automatically disqualifies RAG-sandbox
eligibility on its own (matches the spec's evaluation-only retention carve-out).

## Deletion (Step 26)

`ExternalDatasetSampleDeletionService`: request (captures a lineage-impact summary) → confirm →
execute (removes only `original/`+`derived/`; `manifest.json`/`reports/` retained) → the sample
import's own row is marked `deleted` via a narrow, whitelisted lock-bypass method
(`mark_sample_import_deleted()`, mirroring Phase 11's reverification lock-bypass precedent) so
deletion remains possible even on an already-finalized import without weakening general
immutability elsewhere. No auto-cleanup scheduler exists.

## Backend modules

18 services under `backend/services/dataset_sample_*.py`; `dataset_sample_pipeline_service.py`
consolidates the validate/extract/scan/parse/quality-check/duplicate-check/contamination-check
orchestration into one shared module both the REST API and the Admin Assistant executors call —
avoiding two independent copies of the same logic.

## APIs

29 endpoints under `/api/admin/dataset-sample-imports`, admin-only + CSRF-protected, mirroring
Phase 11's route conventions exactly (no raw SQL in the route layer).

## Admin Assistant integration

9 read-only tools (`get_sample_import`, `list_sample_files`, `get_sample_scan_summary`,
`get_sample_quality_summary`, `get_sample_pii_summary` — counts/categories only, never a raw
value —, `get_sample_duplicate_summary`, `get_sample_contamination_summary`,
`get_sample_validation_report`, `get_sample_rag_eligibility`); 15 actions, all through the same
propose → preview → review → stale-check → execute → verify → audit pipeline as every other
Assistant action, full parity confirmed (every registered action has an executor, fingerprint, and
preview generator, and vice versa). 8-entry deterministic FAQ
(`core_model/admin_assistant/sample_import_help.py`) in the same Tamil/English/Tanglish/Auto
pattern as Phase 11's own FAQ module — Tanglish always derived, never hand-written a third time.

## Frontend

`DatasetSampleImportPage.jsx` — 13 tabs (Overview, Sample Imports, Approval, Files, Security Scan,
Parsed Records, PII & Sensitive Data, Quality, Duplicates & Conflicts, Contamination, Human Review,
Final Report, Deletion & History). File metadata never includes the internal `relative_path`; text
preview is the only content-reachable API response, bounded and text-only. The Final Report tab
renders only "Eligible for RAG Sandbox" / "Not Eligible for RAG Sandbox" — never "Training Approved"
or "Production RAG Approved" (confirmed by a dedicated frontend test).

## Integrations

Dataset Verification's Final Report tab gained "Create Sample Import Proposal"/"Open Existing
Sample Import" buttons (finalized cases only), navigating to the new page. No Phase 12 code path
writes to `dataset_records`/`manual_data_records`/`semantic_chunks`/`structured_record_candidates`/
any RAG/training/evaluation table — confirmed both by design and by a dedicated structural-scan
security test. Data Overview gained 9 real metrics (`sampleImportOverview` group) and an "Open
Sample Import & Quarantine" action, following the exact same per-subsystem fetch-group pattern as
every other Data Overview metric (never a fabricated number).

## Performance controls

Streaming downloads/hashes, bounded parsers (row/line/nesting/page limits from
`core_model.sample_import`), archive member-count/expanded-bytes/compression-ratio/depth caps under
a wall-clock timeout, `RECORD_BATCH_SIZE` batching, `quarantine_max_bytes_per_import`/
`quarantine_total_quota_bytes` settings fields. No background-job infrastructure exists anywhere in
this codebase (confirmed during baseline inspection); every step here is synchronous
request/response, consistent with every prior phase.

## Security controls

SSRF/private-IP/redirect protections on every download, credentials-in-URL rejection, structural
no-`eval`/`exec`/`subprocess`/`os.system` scan across all 21 Phase 12 modules, no-git-clone scan,
no-forbidden-table-write scan (dataset_records/manual_data/semantic_chunks/RAG/training/evaluation),
no-"training_approved"-string scan, PII/secret redaction in scan summaries and audit metadata,
expired/stale approval rejection, path-traversal/symlink/archive-bomb rejection, no public
quarantine file URL, audit completeness verified by grepping real `action="..."` strings.

## Tests

- `tests/core_model/test_sample_import_policy.py` — 17
- `tests/database/test_phase35_migration.py` — 23
- `tests/database/test_dataset_sample_import_repository.py` — 27
- `tests/backend/test_dataset_sample_eligibility_service.py` — 16
- `tests/backend/test_dataset_sample_download_transport.py` — 12
- `tests/backend/test_dataset_sample_quarantine_service.py` — 12
- `tests/backend/test_dataset_sample_download_service.py` — 6
- `tests/backend/test_dataset_sample_file_validation_service.py` — 17
- `tests/backend/test_dataset_sample_archive_safety_service.py` — 15
- `tests/backend/test_dataset_sample_security_scan_service.py` — 13
- `tests/backend/test_dataset_sample_parsing_service.py` — 17
- `tests/backend/test_dataset_sample_normalization_service.py` — 9
- `tests/backend/test_dataset_sample_language_service.py` — 9
- `tests/backend/test_dataset_sample_pii_safety_service.py` — 12
- `tests/backend/test_dataset_sample_quality_service.py` — 14
- `tests/backend/test_dataset_sample_duplicate_service.py` — 9
- `tests/backend/test_dataset_sample_contamination_service.py` — 5
- `tests/backend/test_dataset_sample_poisoning_service.py` — 12
- `tests/backend/test_dataset_sample_review_service.py` — 7
- `tests/backend/test_dataset_sample_report_service.py` — 9
- `tests/backend/test_dataset_sample_deletion_service.py` — 7
- `tests/backend/test_dataset_sample_import_api.py` — 10
- `tests/backend/test_dataset_sample_import_admin_assistant.py` — 11
- `tests/backend/test_dataset_sample_import_security.py` — 73
- Frontend: `DatasetSampleImportPage.test.jsx` — 8, plus updated `DataOverviewPage.test.jsx`

Total: 362 Phase 12-specific backend tests + 8 new frontend tests, all passing. Whole-repo
`ruff check .` clean.

## Manual browser verification

See the final Phase 12 completion report delivered in-conversation for Flow A-G results.

## Known limitations

- The full unfiltered `tests/backend/` (and `tests/core_model/`+`tests/database/`) regression could
  not be completed end-to-end in this environment — background runs of that size are killed with no
  output after several minutes, independent of Phase 12's own changes (the identical limitation was
  documented in Phase 11). Regression confidence rests on the 362 Phase 12-specific tests, the
  isolated Phase 11 regression evidence from the prior phase, and a clean whole-repo `ruff check .`.
- Quality/duplicate/contamination check results are not yet cross-referenced against a real
  external corpus of existing approved-dataset/RAG-corpus/evaluation-set checksums in this phase —
  `ExternalDatasetContaminationService`/`ExternalDatasetDuplicateService` accept caller-supplied
  comparison sets (by design, per Step 19/20's "the service never queries those tables itself"), but
  no orchestration layer yet wires real checksum sets from those tables into the pipeline
  automatically; today the pipeline service calls contamination/duplicate checks with empty
  comparison sets, so `status="unknown"`/no-duplicates-found is the practical default until a
  follow-up wires real comparison-set sourcing.
- OCR for PDF parsing requires an explicitly-injected `ocr_engine` callable; no real OCR engine
  (e.g. Tesseract) is wired into the pipeline service's `parse_files()` call by default — a page
  with no embedded text simply yields no record plus a warning, honestly reflecting "OCR only when
  required" rather than silently attempting one.

## Phase 13 handoff

The finalized report's `rag_sandbox_eligible` boolean is the only signal Phase 13 may read. Phase
12 performs zero writes to any RAG table and creates no index anywhere in its code.

Do not proceed to Phase 13.
