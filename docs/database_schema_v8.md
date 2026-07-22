# Brud AI Database Schema v8

Schema v8 is additive on top of schema v7. It adds the Core Model architecture foundation without altering immutable dataset or tokenizer contents. It is historical after Phase 9; see [database_schema_v9.md](database_schema_v9.md) for the current schema.

## New tables

- `core_model_families`: logical model families such as `brud-core`.
- `core_model_configs`: validated architecture configurations, tokenizer reference, parameter and memory estimates, and config checksum.
- `core_model_versions`: model version lifecycle, config/tokenizer references, seed, parameter counts, checksums, and architecture summaries.
- `core_model_architecture_checks`: append-only check evidence for configuration, causal masking, loss, backward pass, checkpoint round trip, and smoke overfit.
- `core_model_checkpoints`: registered checkpoint metadata with safe names and checksums.
- `core_model_events`: append-only model lifecycle events.
- `core_model_assignments`: architecture-only assignments.

## Public boundary

APIs use public IDs only. Numeric IDs, absolute checkpoint paths, tensor contents, logits, secrets, session tokens, and CSRF values are not exposed.

## Lifecycle

Version statuses are `draft`, `validating`, `initialized`, `architecture_verified`, `smoke_tested`, `staging`, `active`, `failed`, `retired`, and `archived`.

Phase 8 `active` means the architecture default for future training. It does not mean the model can answer chat requests.
