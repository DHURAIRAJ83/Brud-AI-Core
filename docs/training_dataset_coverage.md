# Training Dataset Coverage

## Overview

`training_dataset_coverage` (implemented in `core_model/training/coverage.py`,
persisted via `backend/database/repositories/training_reliability.py`) reports
exactly what happened to every record in a dataset-version split when it was
tokenized for a pretraining job. Coverage is generated automatically the first
time a job's stream is built (`PretrainingService._blocks`), and can also be
generated on demand — before a job is even queued — via
`POST /api/admin/pretraining/jobs/{public_id}/coverage`.

## Fields

* **total_records** — every record in the split, before any filtering.
* **eligible_records** — records with at least one non-empty extractable text field.
* **encoded_records** — eligible records that produced at least one real token sequence.
* **excluded_records** — `total_records - encoded_records`; every excluded record has a reason in `exclusion_reasons_json`.
* **zero_token_records** — eligible records whose text tokenized to zero tokens.
* **oversized_records** — records that produced at least one sequence longer than `sequence_length`.
* **split_records** — records whose oversized sequence was split into multiple blocks (only under `overlength_policy="split_oversized"`).
* **dropped_records** — records that contributed zero tokens to the stream (no extractable text, zero-token, or fully dropped as oversized).
* **total_tokens / usable_tokens / padding_tokens** — token accounting for the split; `padding_tokens` is the padding added to fill the final fixed-length block.
* **language_distribution_json / record_type_distribution_json / source_type_distribution_json** — per-record counts by `language`, `record_type`, and `source_type`.
* **exclusion_reasons_json** — counts by reason (`no_extractable_text`, `zero_token_sequence`, `oversized_dropped`).
* **coverage_ratio** — `usable_tokens / total_tokens`, clamped to `[0, 1]`.
* **stream_checksum_sha256** — a SHA-256 fingerprint over every produced token sequence's length and token IDs, in record order.

## Determinism

Coverage is a pure function of `(records, tokenizer processor, eos_id,
sequence_length, overlength_policy)` — identical inputs always produce an
identical `stream_checksum_sha256` and identical counts. There is no shuffling
or sampling in coverage generation itself.

## Storage model

Every generation appends a new row (`train` and `valid` computed together);
nothing is overwritten. `GET /api/admin/pretraining/jobs/{public_id}/coverage`
returns the latest row per split. `pretraining_jobs.latest_coverage_public_id`
points at the most recent `train`-split coverage row.

## No silent exclusion

Every record not reflected in `encoded_records` is accounted for in
`exclusion_reasons_json`, and `total_records == encoded_records +
dropped_records` always holds. Coverage never has to guess why a record didn't
make it into the stream.

## Test split isolation

Coverage is only ever generated for `train` and `valid` splits.
`PretrainingService._blocks` explicitly skips `split == "test"` rows before
any tokenization happens, so test-split records never appear in coverage,
streams, or the trained model.
