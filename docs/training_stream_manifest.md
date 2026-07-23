# Training Stream Manifest

## Overview

`training_stream_manifests` records the exact configuration used to build one
split (`train` or `valid`) of a pretraining job's token stream, plus the
resulting `stream_checksum_sha256`. It is written automatically whenever
`PretrainingService._blocks` builds a stream, and can be independently
recomputed and compared via
`POST /api/admin/pretraining/jobs/{public_id}/streams/verify`.

## Fields recorded

* `dataset_version_public_id` / `dataset_checksum_sha256` — which immutable dataset version, and its checksum at build time.
* `tokenizer_version_public_id` / `tokenizer_checksum_sha256` — which registered SentencePiece tokenizer, and its model checksum.
* `sequence_length`, `packing_policy` (`fixed_length`), `partial_block_policy` (`pad` or `drop`), `eos_policy`, `overlength_policy` (`split_oversized` or `drop_oversized`), `shuffle`, `seed`.
* `eligible_records`, `encoded_records`, `excluded_records`, `total_tokens`, `usable_tokens`, `block_count` — the same accounting produced by `core_model/training/coverage.py`, cross-checked here against the packed block count.
* `stream_checksum_sha256` — identical to the coverage checksum for that split; this is the value cross-checked at recovery time.
* `manifest_json` — reserved for future structured detail; never contains raw text or full token sequences.

## Determinism

Given the same dataset version, tokenizer version, and packing configuration,
`stream_checksum_sha256` is always identical — it is a pure hash over token
lengths and token IDs (see `core_model/training/coverage.py:generate_coverage`).
This is what lets recovery detect whether the underlying data or tokenizer
silently changed between a checkpoint being saved and being recovered from.

## Packing

`core_model/training/packing.py:pack_stream` wraps
`core_model/training/dataset_stream.py:packed_blocks` to add an explicit
`partial_block_policy`:

* `pad` (default) — the trailing partial block is padded with `pad_token_id` to `sequence_length`.
* `drop` — the trailing partial block is discarded entirely; no synthetic padding tokens ever reach the trainer.

## No leakage

Manifests store checksums and counts only — never full text, never a raw
token sequence, never an internal database ID (all references use public
IDs), never a filesystem path.
