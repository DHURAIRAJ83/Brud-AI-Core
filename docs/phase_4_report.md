# Phase 4 implementation report

## Baseline and scope

Phase 4 started from clean commit `c509ec5 feat: add Brud AI phase 3 dataset administration`. It implements bounded JSON/JSONL/CSV/TXT ingestion, deterministic multilingual cleaning, persistent review previews, explicit confirmation, transactional draft creation, safe reports, and import history. It adds no PDF/OCR, scraping, remote import, version building, tokenizer/model work, inference, RAG, providers, billing, or deployment.

## Schema migration and backup

Additive migration `004_phase4_dataset_import` raises the schema to 4 and creates `dataset_import_jobs`, `dataset_import_rows`, `dataset_import_events`, six lookup indexes, and append-only event triggers. No earlier table was dropped or rebuilt.

- Pre-migration SHA-256: `cb21ae49957e214a8622cdfa4294d29af9578a266054818782aad82f6c014e3c`
- Verified backup: `brud_ai_before_v4_20260722_054434_720287.db`
- Backup SHA-256: `37717a84343ac9de075aa0230712710d87aaeb9fb4394ed89a31bc5fbe9bdac7`
- Immediate post-migration SHA-256: `ea078a0d1e45b1e3e8f09c7afe559f76e43fbbb5d36eb7274f349212e6462e4c`
- Final audited development checksum: `df25145595aad2a9b69e24e027eddfcb552f8cb14bd8ca47a4198571059ac7c9`
- Pre/post integrity: `ok`
- Pre/post foreign-key violations: none
- Schema version: `4`

The active checksum changed after migration because startup, upload, parse, confirmation, report, cancellation, session, and browser-verification audits were appended.

## Files

Created: `apps/admin-dashboard/src/pages/ImportsPage.jsx`, `backend/api/routes/imports.py`, `backend/database/repositories/imports.py`, `backend/import_cli.py`, `backend/models/imports.py`, `backend/services/import_service.py`, `backend/services/text_normalization.py`, `docs/database_schema_v4.md`, `docs/dataset_imports.md`, `docs/text_normalization.md`, `docs/phase_4_report.md`, `tests/backend/test_import_pipeline.py`, `tests/backend/test_phase4_config.py`, `tests/backend/test_text_normalization.py`, and `tests/database/test_phase4_migration.py`.

Modified: `.env.example`, `.gitignore`, `README.md`, `apps/admin-dashboard/src/components/Sidebar.jsx`, `apps/admin-dashboard/src/index.css`, `apps/admin-dashboard/src/pages/DatasetsPage.jsx`, `apps/admin-dashboard/src/services/api.js`, `backend/api/router.py`, `backend/core/config.py`, `backend/database/migrations.py`, `backend/database/schema.py`, `docs/architecture.md`, `docs/database_schema_v2.md`, `docs/dataset_management.md`, `docs/development.md`, `pyproject.toml`, `requirements.txt`, `tests/backend/conftest.py`, `tests/backend/test_system_api.py`, and `tests/database/test_phase3_migration.py`.

## Upload and parser security

Multipart uploads stream in 64 KiB chunks, enforce size while receiving, hash SHA-256, use random server names and mode `0600`, sanitize original basenames, validate extension/MIME/UTF encoding and JSON signatures, remove partial failures, and remain below non-public controlled directories. No uploaded bytes are executed or deserialized beyond ordinary bounded JSON/CSV/text.

JSON supports arrays or an explicitly named top-level list and detects duplicate keys. JSONL retains nonblank line numbers and individual malformed lines. CSV requires a bounded header and comma/semicolon/tab delimiter; formulas stay text. TXT requires one-record-per-line or whole-file-pretrain mode. UTF-8 and UTF-8-SIG are the only encodings.

## Normalization, mapping, and duplicates

The reusable normalizer applies NFC, line-ending/whitespace bounds, safe null/zero-width removal, comparison case folding, and structured script/Unicode warnings while preserving Tamil marks, punctuation, emoji, Tanglish originals, and mixed code-switching. It performs no transliteration, spelling correction, or ML detection.

Mapping targets are allowlisted, incompatible repeated sources are rejected, presets are editable, and explicit row fields may override selected defaults. Imported rows reuse Phase 3 `validate_record` and `content_hash`. A second raw logical hash distinguishes exact from normalization-equivalent matches against the file and database.

## Preview, transaction, reports, and idempotency

Upload, mapping, parsing, normalization, validation, duplicates, and persisted preview occur before record insertion. `create_only` blocks duplicate previews; `skip_duplicates` retains and records skips. Confirmation rechecks state, TTL, and current database duplicates in one SQLite transaction, imports eligible valid/warning rows as drafts, links public IDs, writes row/job events and audit, and is idempotent for completed jobs. Cancellation is terminal and quarantines its artifact.

Reports are bounded CSV with row/status/structured issues and public references only. Spreadsheet formula prefixes are escaped; paths and full row payloads are omitted. CLI list/inspect/confirmed expiry accepts registered public IDs, never paths.

## Verification evidence

- Automated tests: `82 passed in 74.91s` on the final implementation.
- Ruff: `All checks passed!`.
- Chatbot production build: 22 modules, 955 ms.
- Final Admin production build: 27 modules, 493 ms.
- Live JSONL preview: 6 total, 3 valid, 0 warnings, 1 duplicate, 2 invalid.
- Live confirmation: `completed_with_warnings`, 3 draft records imported, 0 failed; retry behavior is covered by tests.
- Live CSV: upload/parse HTTP 200, Tamil preserved, then cancellation HTTP 200.
- Live TXT: upload/parse HTTP 200, then cancellation HTTP 200.
- Authentication/CSRF: unauthenticated list HTTP 401; missing-CSRF upload HTTP 403.
- Invalid extension: controlled HTTP 422.
- Every required import endpoint returned HTTP 200 in its valid workflow.
- Response scans found no internal paths, stored filenames, numeric IDs, password/session/CSRF hashes, or large raw content.
- Import events included upload, mapping, parse start/completion, preview, confirmation/import start, row imports/skips, completion, and cancellation. Audit counts verified upload accept/reject, mapping, parsing, preview, confirmation, completion, report, and cancellation.
- Headless Chromium verified login, active Imports navigation, upload controls, mapping preset, parse action, summary cards, preview tabs, explicit confirmation control, expanded Tamil content, completed history/details, no rendered error, and logout redirect. The inspected screenshot was 258,883 bytes.

The manual workflow intentionally leaves three small draft records and one completed verification job. Three non-imported sample jobs are cancelled; their artifacts are quarantined. No large sample dataset remains.

## Known limitations and Phase 5 readiness

There is no asynchronous worker or retention scheduler; expiry is request/CLI driven. Import confirmation uses a single job-level SQLite transaction suited to the 25,000-row local bound. Encoding guessing, automatic merge, linguistic Tanglish conversion, content moderation, PDF/OCR, remote import, dataset-version building, and training remain unavailable.

The project is ready for Phase 5 dataset-version construction or deeper review tooling: imports now produce canonical draft records with source provenance, deterministic hashes, structured errors, immutable events, and audit evidence.

## Git

The verified implementation is committed as `feat: add Brud AI phase 4 dataset import pipeline`; no push was performed.

## Final verdict

`PHASE_4_COMPLETE`
