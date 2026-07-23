# Base Training Reproducibility Manifest (Phase 11)

`generate_manifest()` produces a single deterministic record of everything
needed to understand — and in principle reproduce — an experiment's
result, without ever including raw text, absolute paths, secrets, or
tensors.

## Manifest contents

```json
{
  "experiment_public_id": "...",
  "run_public_ids": ["...", "..."],
  "dataset_version_public_id": "...",
  "dataset_checksum_sha256": "...",
  "dataset_profile_checksum_sha256": "...",
  "tokenizer_version_public_id": "...",
  "tokenizer_checksum_sha256": "...",
  "core_model_config_checksum_sha256": "...",
  "initialization_seed": 42,
  "sampling_seed": 42,
  "training_configuration": { "...": "..." },
  "optimizer": "adamw",
  "software_versions": {"pytorch": "...", "fixture_version": "phase11-fixed-eval-v1"},
  "runs": [
    {
      "run_public_id": "...", "run_label": "...", "job_public_id": "...",
      "job_status": "completed", "config_diff": {"...": "..."},
      "config_checksum_sha256": "...",
      "checkpoint_checksums": [
        {"public_id": "...", "combined_checksum_sha256": "...", "step": 200, "is_best": true}
      ]
    }
  ],
  "candidate_selection": { "status": "selected_with_warnings", "...": "..." },
  "known_limitations": {
    "data_sufficiency_status": "limited_experiment",
    "test_evaluation_reliable": false,
    "test_evaluation_notice": "TEST_EVALUATION_NOT_RELIABLE",
    "data_sufficiency_notice": "dataset is below the recommended 500-record minimum; this experiment is a limited-scale trial, not a representative-scale result"
  }
}
```

Only public IDs, checksums, seeds, configuration values, and counts appear
— never dataset text, model weights, or filesystem paths.

## Known limitations

`_known_limitations()` inspects the experiment's latest dataset profile and
always reports:

- `data_sufficiency_status` — copied from [[base_training_dataset_profile]].
- `test_evaluation_reliable` — `false` whenever `test_count` is below
  `BRUD_BASE_TRAINING_MIN_TEST_RECORDS` (20 default); in that case
  `test_evaluation_notice` is set to the literal string
  `"TEST_EVALUATION_NOT_RELIABLE"`, so any consumer of the manifest
  (including the Phase 11 report) can detect this programmatically rather
  than parsing prose.
- `data_sufficiency_notice` — a human-readable warning whenever sufficiency
  is not `sufficient`, i.e. whenever the dataset is a limited-scale trial
  rather than a representative-scale run.

## Verification

`verify_manifest()` recomputes `sha256(manifest_json)` and compares it to
the stored `manifest_checksum_sha256`. Manifests are append-only
(`base_training_reproducibility_manifests` has `BEFORE UPDATE`/`BEFORE
DELETE` triggers, see [[database_schema_v11]]) — a mismatch can only mean
the stored JSON or checksum was corrupted at rest (e.g. filesystem/database
corruption), not an in-place edit, since no code path can update a manifest
row after insert.

`POST /experiments/{id}/manifest/verify` and
`base_training_cli.py verify-manifest` both return a non-`matches: true`
result loudly (the CLI exits with status 1) rather than silently trusting
the stored checksum.
