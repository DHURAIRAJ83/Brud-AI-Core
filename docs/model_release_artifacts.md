# Artifact Inventory and Verification (Phase 14)

`core_model/release/artifact_inventory.py` provides bounded, deterministic
artifact validation. It never accepts an arbitrary filesystem path — every
storage key is resolved and confinement-checked against one of a small set
of approved roots (`BRUD_RELEASE_ALLOWED_ARTIFACT_ROOTS`) before any file
is touched.

## 12 artifact types

```
model_checkpoint, model_config, tokenizer_model, tokenizer_vocab,
tokenizer_manifest, dataset_manifest, base_training_manifest,
instruction_tuning_manifest, evaluation_manifest, model_card,
release_manifest, licence_notice
```

`model_checkpoint`, `tokenizer_model`, and `tokenizer_vocab` reference
existing, already-confined files in place (the checkpoint directory under
`pretraining_dir`, the tokenizer files under `tokenizer_dir`) — they are
never copied. `model_config`, `dataset_manifest`, `base_training_manifest`,
`instruction_tuning_manifest`, `evaluation_manifest`, and `licence_notice`
are materialized as canonical JSON/text snapshots under a
server-controlled directory (`BRUD_RELEASE_ARTIFACT_DIR`), never from a
caller-supplied path. `model_card` and `release_manifest` artifacts are
recorded automatically at the moment their content is generated (see
`docs/model_cards.md` and `docs/model_release_manifests.md`) — a bundle
can only include them once they exist as verified artifact rows.

## Path confinement

`resolve_confined_path(root, relative_key)`:

* rejects an absolute `relative_key` outright;
* resolves `root / relative_key` and rejects it if the resolved path
  (following any symlink) is not `.is_relative_to(root)` — the same
  confinement contract `TrainingCheckpointManager.verify()` already
  enforces for checkpoints, reused here for the generic artifact case.

## Verification statuses

```
pending, verified, missing, checksum_mismatch, invalid, not_applicable
```

`classify_artifact_verification()` is a small deterministic decision
table: an unconfined path is always `invalid`; a confined-but-absent
path is `missing`; an oversized or structurally invalid file is
`invalid`; a checksum mismatch is `checksum_mismatch`; otherwise
`verified`.

## Required artifact set

`required_artifact_types(instruction_tuned, evaluation_available)`
returns the minimum artifact-type set a candidate must collect: the
checkpoint/config/tokenizer trio plus the base-training manifest always,
the instruction-tuning manifest when the candidate is instruction-tuned,
and the evaluation manifest when evaluation evidence is linked. Any
artifact type absent or not `verified` blocks eligibility (see
`docs/model_release_eligibility.md`).

## Additional checks performed at collection/verification time

* `detect_unexpected_executable()` flags unexpected executable
  suffixes/permission bits — a release artifact should never be a
  script or binary outside the checkpoint's own known file set.
* Checksums are always SHA-256 (`BRUD_RELEASE_CHECKSUM_ALGORITHM`
  currently supports only `sha256`), computed with the same streaming
  `file_checksum()` helper for every artifact type.
* File size is bounded by `BRUD_RELEASE_MAX_ARTIFACT_SIZE_BYTES`.
