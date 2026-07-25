# Phase 19 Report — Large Tamil Corpus Builder, Licence Governance, Data Cleaning, Deduplication, Privacy Filtering, and Corpus Quality Control

## 1. Baseline commit

`0faa7ed` (`feat: add Brud AI phase 18 feedback improvement pipeline`),
branch `master`. Working tree was clean before starting. Phase 18
verdict: `PHASE_18_COMPLETE`. Schema version 18, 377 tests passing —
confirmed exactly as expected before implementation began.

## 2. Files created

```
core_model/corpus/__init__.py
core_model/corpus/source_policy.py
core_model/corpus/licence_policy.py
core_model/corpus/provenance.py
core_model/corpus/source_snapshot.py
core_model/corpus/text_extraction.py
core_model/corpus/unicode_normalization.py
core_model/corpus/tamil_normalization.py
core_model/corpus/ocr_cleanup.py
core_model/corpus/boilerplate_removal.py
core_model/corpus/document_segmentation.py
core_model/corpus/language_detection.py
core_model/corpus/domain_classification.py
core_model/corpus/style_classification.py
core_model/corpus/pii_detection.py
core_model/corpus/secret_detection.py
core_model/corpus/safety_filter.py
core_model/corpus/quality_scoring.py
core_model/corpus/exact_deduplication.py
core_model/corpus/near_deduplication.py
core_model/corpus/contamination.py
core_model/corpus/balancing.py
core_model/corpus/partitioning.py
core_model/corpus/export_builder.py
core_model/corpus/comparison.py
core_model/corpus/manifest.py
backend/models/corpus.py
backend/database/repositories/corpus.py
backend/services/corpus_source_service.py
backend/services/corpus_processing_service.py
backend/services/corpus_quality_service.py
backend/services/corpus_build_service.py
backend/services/corpus_export_service.py
backend/api/routes/corpus.py
backend/corpus_cli.py
apps/admin-dashboard/src/pages/CorpusPage.jsx
tests/database/test_phase19_migration.py
tests/core_model/test_phase19_corpus.py
tests/backend/test_corpus_api.py
docs/database_schema_v19.md
docs/phase_19_report.md
```

24 pure-function `core_model/corpus/` modules (+ `__init__.py`), 5
services, 1 repository, 1 API router, 1 CLI, 1 admin dashboard page,
3 new test files, 2 new docs (including this report).

## 3. Files modified

```
backend/database/schema.py             (SCHEMA_VERSION 18→19, PHASE19_SCHEMA, 34 new tables,
                                         2 new columns on corpus_source_registries fixed during
                                         schema-design review before any test ran)
backend/database/migrations.py         (_apply_v19, backup-trigger version set extended to 18)
backend/core/config.py                 (24 new BRUD_CORPUS_* settings + approved-roots helpers)
backend/api/router.py                  (corpus router included)
tests/backend/test_system_api.py       (applied_migrations set + migration 019)
apps/admin-dashboard/src/App.jsx       (new "Corpus Builder" page wired in)
apps/admin-dashboard/src/components/Sidebar.jsx (nav item + phase tag updated)
apps/admin-dashboard/src/services/api.js        (~55 new API functions)
```

## 4. Migration name and schema version

`019_phase19_tamil_corpus_builder`, schema version 18 → 19.
Independent of migration 018 (verified directly:
`test_migration_018_is_unchanged_in_isolation`).

## 5. Backup and checksums

Real dev DB upgrade (`python -m backend.database.migrations upgrade`):

```
schema_version: 19
backup.filename: brud_ai_before_v19_20260725_061931_173032.db
backup.source_checksum: a639b0c337c6b910877f41599b2c0e3844ed83286da2045876c1773fb7c57725
backup.backup_checksum: eee32ffcc9588a9d6af1b9195ea76cbd41a2c6a845a378605ce1bfa366081f5c
integrity_check: ok
post_migration_checksum: e4e322ddf72105e9e751aa6474efb5dcd33a6deed148526a2e458ad9c316fb0e
```

Post-upgrade direct checks: `PRAGMA user_version` = 19, `PRAGMA
integrity_check` = `ok`, `PRAGMA foreign_key_check` = 0 rows, 34
`corpus_%` tables present.

## 6. Mutable/append-only classification (no deviation needed)

34 tables total: 14 mutable, 20 append-only. Unlike every prior phase
(16/17/18), this phase's own spec already correctly pre-classified
every two-phase create-then-execute table (`corpus_extraction_runs`,
`corpus_normalization_runs`, `corpus_deduplication_runs`,
`corpus_contamination_runs`, `corpus_exports`) as mutable, so no
literal-reading deviation was required — documented directly in
`schema.py` and exercised by a dedicated test
(`test_corpus_extraction_runs_are_mutable`). See
`docs/database_schema_v19.md` for the full table-by-table
classification and the circular-FK-avoidance decision for
`corpus_source_registries`/`corpus_source_licences`.

## 7. Corpus policy details

One policy created in manual verification with
`minimum_segment_characters=20` (lowered from the schema default of
100 to admit short-form dictionary/FAQ content), `maximum_source_bytes`,
`maximum_segment_characters`, and all six `require_*` flags left at
their fail-closed defaults (`true`).

## 8. Source registry, licence governance, and provenance

16 sources registered from hand-composed fixtures across 7 licence
families (`public_domain`, `cc0`, `government_open_data`, `cc_by`,
`organisation_owned`, `unknown`, `research_only`). 14 sources reached
`approved` status and passed training-eligibility; 2 were deliberately
constructed to be blocked:

- an `unknown`-licence source, blocked with reasons
  `licence_review_status_unknown`, `licence_not_approved`,
  `ai_training_permission_absent`;
- a `research_only`-licence source whose `intended_use` was
  `pretraining_corpus` (a purpose mismatch), blocked with reason
  `research_only_purpose_mismatch`.

Every source's origin was explicitly verified
(`verify_origin`/`origin_verified`) before approval — public-domain
status and website accessibility were never inferred, only explicit
admin evidence.

## 9. Immutable snapshots and approved-root enforcement

16 immutable snapshots created (one per source), each snapshot's file
inventory checksum computed from sorted `(filename, checksum)` pairs.
A direct attempt to snapshot a path outside every approved root
(`../../../etc/passwd`) was rejected with `ValidationError: invalid
source file path` — confirmed in both the manual verification script
and `test_corpus_api.py::test_snapshot_rejects_path_outside_approved_roots`.

## 10. Extraction, normalization, and segmentation

16 extraction runs (`plain_text` for `.txt` sources, `markdown_text`
for the one `.md` source), each producing exactly one extracted
document per source — zero failed files. 16 normalization runs, every
resulting document reporting `unicode_integrity_status: valid` and
preserved Tamil combining-mark counts. Segmentation used
`sentence_group` for 11 longer-prose sources and `paragraph` for the
5 record-like sources (dictionary entries, FAQ, and 3 short edge-case
fixtures), producing **123 segments** total (target range: 100-500).

## 11. Quality, language, domain, and style assessment

All 123 segments assessed across the 17 quality dimensions plus
language/domain/style classification:

```
language distribution:  ta: 12, en: 100, tgl: 6, mixed: 5
quality verdict:         pass: 111, fail: 5, warning: 7
```

Tamil, English, and Tanglish/mixed content are all present and
correctly classified — Tanglish was never folded into English merely
for sharing the Latin script (verified directly against the
`tanglish_conversation.md` fixture).

## 12. Privacy and safety filtering

7 privacy findings recorded (4 distinct PII categories from the
hand-composed privacy fixture — email, phone, precise-address, and
personal-medical-record mentions — plus 1 always-blocked secret
finding from a fixture containing a database connection string). 7
safety findings recorded across all 5 non-operational behavior classes
(descriptive, historical, educational, preventive) from one
deliberately-constructed fixture, plus 1 genuinely operational
"how to steal passwords" instruction from a second fixture, which was
the only safety finding to reach `blocked` status. Confirmed directly:
secrets are always blocked regardless of policy, while descriptive/
historical/educational/preventive safety content is flagged (or left
safe) rather than blocked outright — a genuine behavior-classification
distinction, not a keyword ban.

## 13. Deduplication

One deduplication run over all 123 segments: **9 exact duplicates**
(from a source deliberately duplicated byte-for-byte) and **3 near
duplicates** (from a source with minor punctuation/wording changes,
detected via `character_ngram_jaccard` at threshold 0.75) — 12 combined
duplicate examples (target: ≥10). Representative selection for every
cluster was deterministic (verified by the fixed sort key in
`select_representative`), never random.

## 14. Contamination checking

One contamination run using 6 real fixture texts that were themselves
copied from existing corpus segments (2 as `test`, 2 as `evaluation`,
2 as `regression` fixtures) plus 1 genuinely novel holdout sentence
never present in the corpus. Result: **12 findings**, all correctly
attributing leakage to the matching segments; the novel holdout
sentence produced zero false-positive findings.

## 15. Collections, balancing, builds, partitions, versions

A collection of all 123 segments was assembled; 118 were eligible
(5 excluded for failing quality/privacy/safety checks). With a
deliberately aggressive `maximum_single_source_share=0.2` balance
policy (chosen to exercise the capping logic directly, since several
individual sources — the 31-entry dictionary and 15-entry FAQ in
particular — would otherwise dominate a 123-segment corpus), the
resulting build included 23 segments and excluded 95 as
over-represented-source overflow, split train:20/validation:1/test:2
under seed 42. A second build/version using a different collection and
seed was created to exercise version comparison, which correctly
reported `incompatible` (different balance/partition configuration and
different source collections) rather than a misleading "compatible".

## 16. Export and manifest

Export produced 3 shards covering 23 records across all three splits;
the response's `notice` field read verbatim: *"Finalizing a corpus
does not automatically start model training."* A manifest was
generated with all 26 required fields present and a stable SHA-256
checksum, with zero disallowed sensitive-content matches during the
mandatory pre-persistence scan.

## 17. Manual verification (Paths A–K)

Executed against an isolated scratch SQLite database under
`data/manual_verification_phase19/` (never the real dev database),
using only hand-composed fixture text — 16 sources, 123 segments, 7
licence families, Tamil/English/Tanglish/mixed content, 12 combined
exact/near-duplicate examples, 7 privacy findings + 7 safety findings,
and 6 contamination-leakage fixtures plus 1 novel holdout. All 11
paths (A: source + licence governance; B: origin verification +
status transitions; C: immutable snapshot + approved-root path
enforcement; D: extraction; E: Tamil-safe normalization; F:
segmentation; G: quality/language/domain/style assessment; H: privacy
+ safety filtering; I: deduplication; J: contamination checking; K:
collections/balancing/build/partition/version/export/manifest/
compare) passed. Per the established "isolated scratch database,
cleaned up after" convention (Phase 12 onward), the fixture directory
was removed before this commit; the real, measured figures above are
preserved in this report.

## 18. Public chatbot status

Unchanged. `backend/api/routes/chat.py` remains the explicit
non-AI placeholder — confirmed directly after every corpus operation
exercised in this phase.

## 19. API/CLI/Admin Dashboard verification

All 26 routes under `/api/admin/corpus` registered (confirmed by
enumerating `app.routes` after `create_app()`) and exercised via real
in-process ASGI HTTP calls in `tests/backend/test_corpus_api.py`,
including explicit CSRF-required and authentication-required
assertions. `backend/corpus_cli.py` exercised directly against a
scratch database via `python -m backend.corpus_cli policies`/`sources`.
The Admin Dashboard's "Corpus Builder" page (11 tabs) was verified via
`npm run build`, which type-checks/bundles every import used by the
page; no live-browser interaction was performed, so this is a build/
static-import verification, not a claim of live-browser testing.

## 20. Tests

`tests/database/test_phase19_migration.py` (9 tests),
`tests/core_model/test_phase19_corpus.py` (44 tests),
`tests/backend/test_corpus_api.py` (5 tests) — all new, all passing.
Full project suite: **435 passed**, 0 failed (377 Phase-18 baseline +
58 new), run twice: once during implementation and once after the real
dev DB migration.

## 21. Ruff and diff-check

`python -m ruff check .` — clean. `git diff --check` — clean.

## 22. Frontend builds

`cd apps/admin-dashboard && npm run build` — succeeded (459.64 kB
bundle). `cd apps/chatbot && npm run build` — succeeded unchanged
(194.03 kB bundle, placeholder chat UI untouched).

## 23. Database integrity/FK

`PRAGMA user_version` = 19, `PRAGMA integrity_check` = `ok`, `PRAGMA
foreign_key_check` = 0 rows, both immediately after migration and
after the full verification pass.

## 24. Known limitations

- Domain and style classification are explicitly heuristic
  (keyword-rule-based, `classifier_version: v1`) and are always
  surfaced separately from measured dimensions via
  `quality_scoring.build_quality_details` — they are corpus-
  organization aids, never a claim of subject-matter or literary
  certification.
- OCR extraction (`tesseract_ocr`) and embedded-PDF extraction
  (`embedded_pdf_text`) reuse Phase 5's `fitz`/`pytesseract` integration
  directly and were implemented and code-reviewed, but manual
  verification exercised only `plain_text`/`markdown_text` extraction
  against hand-composed text fixtures — no PDF fixture was produced
  for this pass, so the OCR/PDF code paths are unit-covered by their
  shared pure-function dependencies but not end-to-end manually
  verified this phase.
- Balancing's source-cap enforcement is deliberately aggressive when
  `maximum_single_source_share` is set low relative to the number of
  distinct sources (as manual verification Path K intentionally
  demonstrated) — operators should size this setting relative to their
  actual source-count distribution, not treat 0.2 as a universal
  default.
- Contamination and deduplication both currently scan every segment in
  the database per run (no scope narrowing yet) — acceptable at
  hand-composed-fixture and early-corpus scale, but a future phase
  should add scoped/incremental scanning before this is run against a
  truly large corpus.
- Quality, language, domain, and style scores are corpus-preparation
  signals only, never a proof that any resulting model trained on this
  data would perform well — stated explicitly in every manifest's
  `known_limitations` field.

## 25. Phase 20 readiness

Schema v19 is additive and independent of migration 018. A future
phase could build on approved, exported corpus versions (already
immutable, checksummed, and manifest-verified) for actual pretraining
corpus assembly, without any further migration to this phase's tables.

## Final verdict

PHASE_19_COMPLETE_WITH_WARNINGS
