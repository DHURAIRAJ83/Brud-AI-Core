# Training Run and Checkpoint Comparison

## Overview

Two independent, append-only comparison tables exist:

* `training_checkpoint_comparisons` — `core_model/checkpoints/comparison.py`, via `POST /api/admin/pretraining/checkpoints/compare`.
* `training_run_comparisons` — `core_model/training/run_comparison.py`, via `POST /api/admin/pretraining/jobs/compare`.

Both share the same compatibility model and both persist a row per comparison
(`GET /api/admin/pretraining/comparisons/{public_id}` looks up either table).

## Compatibility levels

* **compatible** — same tokenizer version, same core-model config, same dataset version. Metrics can be directly ranked.
* **partially_compatible** — same tokenizer and model config, different dataset version. Loss values are on the same scale but not a like-for-like comparison.
* **incompatible** — different tokenizer or different model config. Loss/perplexity values are not comparable at all (different vocabulary or architecture changes what a given loss value means).

`ranked` in the response is `true` only for `compatible` pairs. Neither
comparison ever silently presents incompatible items as equivalent — the
compatibility level is always returned alongside the raw field-by-field diff
so the caller can decide what, if anything, to rank.

## Checkpoint comparison fields

step, processed_tokens, training_loss, validation_loss, perplexity,
learning_rate, checksum_status, core_model_config_public_id,
dataset_version_public_id, tokenizer_version_public_id, file_size_bytes,
promotion_eligible.

## Run comparison fields

dataset/tokenizer/core-model-config public IDs, seeds, sequence_length,
steps, processed_tokens, initial/final training loss, validation loss,
perplexity, average tokens/sec, peak memory, recovery_count, quality overall
score and readiness status.

## Why this matters

A Micro-preset model retrained after a config change, or a job trained
against a different tokenizer vocabulary, will naturally have different loss
scales. Presenting those as a simple "lower loss wins" comparison would be
actively misleading — hence every comparison leads with compatibility, not a
ranking.
