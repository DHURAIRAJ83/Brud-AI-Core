# Dataset imports

## Formats and limits

Authenticated administrators may upload JSON arrays (or one explicitly selected top-level list field), JSONL objects, header-based CSV, and TXT. Defaults are 10 MB, 25,000 rows, 50 columns, 20,000 characters per cell, UTF-8/UTF-8-SIG, and 60-minute previews. JSON duplicate keys and excessive nesting are rejected. JSONL malformed lines remain individual invalid rows. CSV delimiters are comma, semicolon, or tab; formulas are plain text. TXT is explicitly one-record-per-line or whole-file pretrain.

## Upload security and retention

Uploads stream in 64 KiB chunks into `data/imports/pending`, are size-checked while receiving, SHA-256 hashed, mode `0600`, assigned random server filenames, and never publicly served. Original names are basename-sanitized metadata. Empty, null-byte, unsupported extension/MIME, decoding, and content/format failures are controlled; partial files are removed. Completed artifacts move to `processed`; cancelled artifacts move to `quarantine`. No background deletion runs in Phase 4, and cleanup never deletes dataset records.

## Mapping and preview

Mapping targets are allowlisted and a source cannot ambiguously populate multiple targets. Editable presets cover instruction/input/output, question/answer, Tanglish/Tamil/response, source/target, and text. Defaults supply record type/language; explicitly mapped row fields may override them. Parsing normalizes text, uses canonical Phase 3 validation, and persists valid, warning, duplicate, and invalid rows before any dataset record exists.

## Duplicate and confirmation behavior

Canonical normalized hashes are compared inside the file and against existing records. A raw logical hash distinguishes exact from normalization-equivalent conflicts. Existing record public IDs are shown where available. `create_only` blocks confirmation when preview duplicates exist. `skip_duplicates` records skips and imports only eligible valid/warning rows as drafts. Confirmation rechecks state, expiry, and database duplicates in one SQLite transaction; retrying a completed job returns the terminal result without new records.

## Reports, cancellation, and expiry

The CSV error report is bounded, exposes row/status/issues and safe public references only, and prefixes spreadsheet-formula characters. Cancellation is terminal and quarantines the artifact. Expired previews cannot confirm but can be identified through events/CLI. Reports and audit metadata omit storage paths and full row contents.

PDF, OCR, web scraping, remote URLs, broad encoding guessing, automatic merges, dataset-version building, and training are intentionally unavailable.
