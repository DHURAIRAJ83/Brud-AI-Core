# Database Schema v10 (Phase 10)

Migration `010_phase10_training_reliability` upgrades schema version 9 → 10. It
is a separate, independent migration function (`_apply_v10`) from migration
009 — Phase 9's `_apply_v9` is unchanged in behavior and content.

## New tables

| Table | Purpose |
|---|---|
| `worker_heartbeats` | One row per worker process; tracks status, current job, lease generation, and last heartbeat. Mutable — heartbeats are renewed in place. |
| `training_worker_leases` | Existing Phase 9 table, extended with `lease_generation`, `owner_public_id`, `released_at`, `release_reason` (additive columns, no `UNIQUE` added via `ALTER TABLE`). |
| `training_recovery_attempts` | Append-only record of every recovery attempt (pause/resume, stale-lease takeover, worker crash, manual, checkpoint recovery), including full validation results. |
| `training_dataset_coverage` | Append-only per-split (`train`/`valid`) accounting of how many records were encoded, excluded, zero-token, or oversized, plus token/coverage-ratio statistics. |
| `training_stream_manifests` | Append-only record of the exact tokenizer/dataset/packing configuration and checksum used to build a job's train/validation stream. |
| `training_run_summaries` | Append-only summary of a completed job: loss trajectory, tokens, throughput, pause/resume/recovery counts. |
| `training_quality_assessments` | Append-only training-process quality score (10 dimensions) and readiness status. |
| `training_quality_issues` | Append-only issues linked to a quality assessment, each with a fixed `issue_code` and `severity`. |
| `training_checkpoint_comparisons` | Append-only record of a checkpoint-vs-checkpoint comparison and its compatibility level. |
| `training_run_comparisons` | Append-only record of a job-vs-job comparison and its compatibility level. |
| `checkpoint_retention_actions` | Append-only record of every retention preview/apply decision, per checkpoint. |

All tables above except `worker_heartbeats` and `training_worker_leases` carry
`BEFORE UPDATE`/`BEFORE DELETE` triggers that raise `RAISE(ABORT, ...)` —
history is genuinely append-only, not just append-only by convention.

## Additive columns

```
pretraining_jobs:
  lease_generation                 INTEGER NOT NULL DEFAULT 0
  recovery_required                INTEGER NOT NULL DEFAULT 0
  latest_stream_checksum_sha256    TEXT
  latest_coverage_public_id        TEXT
  quality_readiness_status         TEXT NOT NULL DEFAULT 'not_assessed'
  best_checkpoint_public_id        TEXT

training_worker_leases:
  lease_generation   INTEGER NOT NULL DEFAULT 0
  owner_public_id    TEXT
  released_at        TEXT
  release_reason      TEXT
```

Every `ALTER TABLE ... ADD COLUMN` uses the same `_has_column()` idempotency
guard Phase 2 introduced — no `UNIQUE` constraint is added via `ALTER TABLE`
(SQLite does not support that), and no column is required without a default,
so existing Phase 1–9 rows remain valid without backfill.

## Migration safety

* `_apply_v10` is guarded by `SELECT 1 FROM schema_migrations WHERE version = 10` — safe to call repeatedly.
* `initialize_database()`/`upgrade_database()` now include 9 in the set of versions that trigger a pre-upgrade verified backup (previously 1–8).
* Fresh databases go straight to v10; a v9 database upgrades additively; a v10 database is a no-op.
* Verified via `tests/database/test_phase10_migration.py`: fresh→10, isolated v9 behavior unchanged, v9→10 upgrade with backup+data preservation, v10→10 no-op, idempotent re-application, deterministic table/index/trigger sets, and append-only enforcement.

## Not in this migration

No Phase 10 table stores full text, raw tensors, absolute paths, or secrets.
`training_stream_manifests.manifest_json` and coverage distribution columns
hold counts and checksums only.
