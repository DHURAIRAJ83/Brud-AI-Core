# Brud AI Database Schema v7

Schema v7 is additive on top of schema v6. It preserves all dataset quality, versioning, import, document, authentication, and audit behavior while adding tokenizer control-plane tables.

The current project schema is v8. See [database_schema_v8.md](database_schema_v8.md) for core-model architecture additions.

## New tables

- `tokenizer_families`: logical tokenizer lines such as `brud-multilingual-tokenizer`.
- `tokenizer_versions`: tokenizer metadata, dataset reference, configuration, checksums, special tokens, and lifecycle state.
- `tokenizer_training_jobs`: bounded local corpus-build, dry-run, train, evaluate, or full-pipeline jobs.
- `tokenizer_training_events`: append-only job and lifecycle events.
- `tokenizer_evaluations`: tokenizer evaluation runs.
- `tokenizer_evaluation_results`: per-language metric rows.
- `tokenizer_assignments`: explicit assignment keys such as `core_model_training` and `default`.
- `tokenizer_exports`: server-generated export bundle metadata and checksums.

## Relationships

- Tokenizer versions reference tokenizer families and ready or archived dataset versions.
- Training jobs reference tokenizer versions and source dataset versions.
- Training events reference training jobs.
- Evaluations and exports reference tokenizer versions.
- Evaluation results reference evaluations.
- Assignments may reference primary and fallback tokenizer versions.

## Lifecycle

Tokenizer version statuses are `draft`, `validating`, `training`, `evaluating`, `staging`, `active`, `failed`, `retired`, and `archived`.

Only staging or deliberately reactivated retired versions may become active. Activation retires any prior active version in the same family transactionally. Failed versions cannot activate.

## Public boundary

Public APIs expose public IDs, safe names, lifecycle state, metrics, and checksum values. They do not expose numeric database IDs, absolute artifact paths, session data, secrets, corpus text, or tokenizer binary contents.

## Append-only guarantees

`tokenizer_training_events` has triggers rejecting update and delete operations. Audit logs separately record administrative mutations without storing full corpus text or artifact bytes.
