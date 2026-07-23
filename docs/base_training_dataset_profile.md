# Base Training Dataset Profile (Phase 11)

`core_model/training/dataset_profile.py` computes a deterministic profile of
a dataset version before any base-pretraining run starts. It never calls a
model, never rewrites data, and never fabricates records to reach a target
count — it reports what the approved dataset actually contains.

## What is computed

- Total / train / validation / test record counts.
- Total characters, total tokens (via the experiment's resolved tokenizer),
  and unique token count.
- Language, record-type, source-type, and licence distributions.
- Average / median / maximum record length.
- `duplicate_rate` (exact `content_hash` collisions) and
  `near_duplicate_rate` (case/whitespace-normalized text collisions).
- `zero_token_rate` (records that encode to no tokens) and
  `oversized_record_rate` (records longer than the evaluation sequence
  length).
- `validation_representativeness` / `test_representativeness`: language
  coverage ratio of each split against the train split's language set.
- `tamil_script_coverage`, `english_latin_coverage`, `tanglish_coverage`,
  `mixed_script_coverage` — script-presence ratios, not ML language
  detection.
- `profile_checksum_sha256` — SHA-256 of the serialized profile, so two
  profiles of the same dataset+tokenizer+sequence-length are byte-identical.

No raw record text is stored in the profile — only aggregate counts,
distributions, and the checksum.

## Warnings (non-blocking)

`evaluate_warnings()` never rebalances or drops data; it only reports:
`too_little_tamil`, `too_little_english`, `too_little_tanglish`,
`tiny_validation_set`, `tiny_test_set`, `high_duplication`,
`very_short_records`, `dominant_single_source`, `low_licence_diversity`,
`high_ocr_derived_ratio`.

Thresholds come from `ProfileThresholds`, built from the
`BRUD_BASE_TRAINING_MIN_TAMIL_RATIO` (0.30 default), `..._MIN_ENGLISH_RATIO`
(0.05), `..._MIN_TANGLISH_RATIO` (0.05), `..._MAX_DUPLICATE_RATIO` (0.15),
`..._MIN_VALIDATION_RECORDS` (20), and `..._MIN_TEST_RECORDS` (20) settings.

## Data sufficiency

`data_sufficiency_status()` returns exactly one of:

- `sufficient` — total records ≥ `BRUD_BASE_TRAINING_MIN_RECORDS` (default 500).
- `limited_experiment` — some approved records exist, but below the minimum.
  The experiment may still proceed, but every downstream report (manifest,
  candidate rationale, phase report) must carry this as an explicit
  limitation, not a silent gap.
- `insufficient` — no approved records at all.

## Where it is stored

Every call to `POST /api/admin/base-training/experiments/{id}/profile`
persists a new append-only row in `base_training_dataset_profiles` (Phase 11
schema, [[database_schema_v11]]) and updates the experiment's
`latest_profile_public_id`. Profiles are never overwritten — re-profiling
after a dataset change produces a new row with a new checksum.
