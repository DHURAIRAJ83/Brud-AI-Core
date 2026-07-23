# Instruction-Tuning Reproducibility Manifest (Phase 12)

`generate_manifest()` produces a single deterministic record of everything
needed to understand an instruction-tuning experiment's result, without
including raw prompts, raw responses, secrets, absolute paths, or numeric
database IDs.

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
  "base_model_public_id": "...",
  "base_checkpoint_checksum_sha256": "...",
  "instruction_template_checksum_sha256": "...",
  "initialization_seed": 42,
  "sampling_seed": 42,
  "training_configuration": {"...": "..."},
  "optimizer": "adamw",
  "software_versions": {"pytorch": "...", "fixture_version": "phase12-instruction-eval-v1"},
  "runs": [
    {
      "run_public_id": "...", "run_label": "...", "job_status": "completed",
      "config_diff": {"...": "..."},
      "assistant_target_tokens": 1435, "prompt_tokens": 2116, "ignored_tokens": 4009,
      "input_stream_checksum_sha256": "...", "label_stream_checksum_sha256": "...",
      "checkpoint_checksums": [
        {"public_id": "...", "combined_checksum_sha256": "...", "step": 60, "is_best": true}
      ]
    }
  ],
  "candidate_selection": {"status": "instruction_tuned_with_warnings", "...": "..."},
  "known_limitations": {
    "data_sufficiency_status": "limited_instruction_experiment",
    "test_evaluation_reliable": false,
    "test_evaluation_notice": "TEST_EVALUATION_NOT_RELIABLE",
    "data_sufficiency_notice": "dataset is below the recommended 1,000-record minimum; this experiment is a limited-scale trial, not a representative-scale result",
    "generation_evidence_notice": "instruction tuning teaches response behavior and formatting; it does not prove factual accuracy, safety, or production chat readiness"
  }
}
```

Only public IDs, checksums, seeds, configuration values, and counts appear.

## Known limitations, always computed

`_known_limitations()` always reports `data_sufficiency_status` (copied from
the latest dataset profile), whether the test split was large enough to be
statistically reliable (`test_evaluation_reliable`, with the literal marker
string `TEST_EVALUATION_NOT_RELIABLE` when below
`BRUD_INSTRUCTION_TUNING_MIN_TEST_RECORDS`), and always includes the
`generation_evidence_notice` reminding readers that instruction tuning
proves response behavior/formatting, not correctness or safety.

## Verification

Manifests are append-only (`instruction_reproducibility_manifests` has
`BEFORE UPDATE`/`BEFORE DELETE` triggers — see
[database_schema_v12.md](database_schema_v12.md)). `verify_manifest()`
recomputes `sha256(manifest_json)` and compares it to the stored
`manifest_checksum_sha256`. `POST /experiments/{id}/manifest/verify` and
`base_training_cli.py`'s sibling `instruction_tuning_cli.py verify-manifest`
both surface a non-matching checksum loudly (the CLI exits with status 1)
rather than trusting the stored value silently. Tamper detection was
verified directly by test: inserting a second manifest row (append-only
tables allow new rows, just not in-place edits) with a deliberately
mismatched checksum causes `verify_manifest()` to correctly report
`matches: false`.
