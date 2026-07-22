# Phase 7 Report

## Baseline

- Baseline command: `git log -1 --oneline`
- Baseline commit: `99372c6 feat: add Brud AI phase 6 dataset quality and versioning`
- Working directory: `/home/dhurai/Projects/brud-ai`
- Initial working tree: clean

## Migration and schema

- Migration: `007_phase7_tokenizer_training`
- Schema version: `7`
- Additive tables: `tokenizer_families`, `tokenizer_versions`, `tokenizer_training_jobs`, `tokenizer_training_events`, `tokenizer_evaluations`, `tokenizer_evaluation_results`, `tokenizer_assignments`, `tokenizer_exports`
- Existing Phase 1–6 tables were preserved.

## Backup

- Backup filename: `brud_ai_before_v7_20260722_080331_044216.db`
- Pre-migration checksum: `4da0b4dab13236591009f73850c832871d042ede43468ab486403cfe9bb7693f`
- Backup checksum: `2e40d62c6bb52434a019c2d04545f5c6df3264a65a9762f5432ba4a7644e3ec4`
- Post-migration checksum: `1b354e14e546231e4aafce3b5b33c83cf7e44fd96f4c9284db4b9a08ffb1c4e3`
- Integrity checks: `ok` before and after migration
- Foreign-key checks: no violations before and after migration

## Files created and modified

Phase 7 adds tokenizer models, repository, service, API routes, CLI, tests, admin UI, configuration, schema migration, and documentation. The exact final file list is recorded in Git for commit `feat: add Brud AI phase 7 tokenizer training`.

## SentencePiece capability

- Installed package version: `0.2.2`
- BPE training verified in automated tests with a small deterministic corpus.
- Unigram is supported by schema/configuration/API and SentencePiece capability, but a separate manual unigram training run was not performed in this terminal-only pass.

## Tokenizer architecture

Tokenizer families represent logical tokenizer lines. Versions reference immutable dataset versions and store algorithm, vocabulary size, corpus checksum, artifact checksums, special tokens, configuration, metrics summary, and lifecycle state.

## Corpus-building behavior

Ready or archived dataset versions produce deterministic UTF-8 corpora. Corpus generation preserves Tamil Unicode, extracts fields by record type, excludes empty lines, records truncation warnings, writes a corpus manifest, and calculates a stable SHA-256 checksum.

## Dry-run results

Automated tests verified that dry run passes or returns warnings only after corpus creation and checksum validation. Dry run does not activate a tokenizer.

## Training configuration

The default local configuration uses BPE, vocabulary size 16,000, character coverage 0.9995, bounded corpus sizes, bounded line lengths, and one CPU thread. Tests use a small vocabulary-compatible fixture while still exercising real SentencePiece BPE training.

## Artifact checksums

Training validates generated `tokenizer.model` and `tokenizer.vocab`, writes an artifact manifest and checksums file, and stores model/vocabulary checksums in `tokenizer_versions`. Artifact verification recalculates checksums from registered files.

## Evaluation results

Evaluation persists deterministic metrics for Tamil, English, Tanglish, mixed, and overall samples. Metrics include total characters, total tokens, characters per token, tokens per word, unknown-token rate, byte-fallback rate, round-trip success rate, Tamil grapheme warning rate, long-sequence rate, and compression ratio.

## Encode/decode verification

Automated tests verified Tamil-containing encode/decode through registered tokenizer versions. Arbitrary tokenizer filesystem paths are not accepted.

## Lifecycle and activation

Successful training produces a staging tokenizer. Activation requires artifact verification and passing evaluation summary. Activation retires any previous active version in the same family and updates the default tokenizer assignment.

## Assignment verification

Assignments are stored separately in `tokenizer_assignments`. Automated tests verified assignment visibility after activation.

## Export verification

Tokenizer export supports `sentencepiece_bundle` and `manifest_only`. Automated tests verified export creation, authenticated download, and checksum verification.

## Audit and events

Tokenizer family/version/job/corpus/dry-run/training/evaluation/verification/activation/export actions create audit or tokenizer event records without full corpus text, artifact bytes, internal paths, session tokens, CSRF tokens, or passwords.

## API verification

Automated API tests verified:

- `GET /api/admin/tokenizers/capabilities`
- `POST /api/admin/tokenizers/families`
- `GET /api/admin/tokenizers/families`
- `POST /api/admin/tokenizers/versions`
- `GET /api/admin/tokenizers/versions/{public_id}`
- `POST /api/admin/tokenizers/versions/{public_id}/verify`
- `POST /api/admin/tokenizers/versions/{public_id}/activate`
- `POST /api/admin/tokenizers/jobs`
- `POST /api/admin/tokenizers/jobs/{public_id}/build-corpus`
- `POST /api/admin/tokenizers/jobs/{public_id}/dry-run`
- `POST /api/admin/tokenizers/jobs/{public_id}/train`
- `POST /api/admin/tokenizers/jobs/{public_id}/evaluate`
- `GET /api/admin/tokenizers/evaluations/{evaluation_public_id}/results`
- `POST /api/admin/tokenizers/versions/{public_id}/encode`
- `POST /api/admin/tokenizers/versions/{public_id}/decode`
- `GET /api/admin/tokenizers/assignments`
- `POST /api/admin/tokenizers/versions/{public_id}/exports`
- `GET /api/admin/tokenizers/exports/{export_public_id}/download`
- `POST /api/admin/tokenizers/exports/{export_public_id}/verify`

Tests also verified missing CSRF rejection and draft dataset-version rejection.

## Admin Dashboard verification

The admin dashboard production build includes Tokenizer navigation and pages for overview, families, versions, training jobs, test lab, and assignments. Manual browser verification was not run in this terminal-only pass.

## Test, lint, diff-check, and build results

```text
python -c "import sentencepiece as spm; print(spm.__version__)" → 0.2.2
python -m backend.database.migrations status → current_version 6 before upgrade, 7 after upgrade
python -m backend.database.migrations verify → integrity ok, no foreign-key violations
python -m backend.database.migrations upgrade → schema_version 7
sqlite3 data/database/brud_ai.db "PRAGMA integrity_check;" → ok
sqlite3 data/database/brud_ai.db "PRAGMA foreign_key_check;" → no rows
sqlite3 data/database/brud_ai.db "PRAGMA user_version;" → 7
python -m pytest -q → 106 passed in 141.15s
python -m ruff check . → All checks passed
git diff --check → passed
npm run build (apps/chatbot) → built successfully
npm run build (apps/admin-dashboard) → built successfully
```

## Known limitations

- Tokenizer workflows are local and synchronous.
- Hugging Face tokenizer export is not implemented.
- Tokenizer comparison is basic and depends on available persisted evaluations.
- Unigram is supported but not separately manually verified in this report.
- The public chatbot is not connected to tokenizers.
- No core model training, inference, RAG, or external providers were added.

## Phase 8 readiness

Phase 8 can consume ready dataset versions and the active tokenizer assignment for core-model training design. Required registry metadata, tokenizer artifacts, checksums, and evaluation evidence are now available.

## Final verdict

PHASE_7_COMPLETE_WITH_WARNINGS
