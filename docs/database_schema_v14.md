# Database Schema v14 (Phase 14)

Migration `014_phase14_model_release_registry` upgrades schema version
13 → 14. It is a separate, independent migration function (`_apply_v14`)
from migration 013 — Phase 13's `_apply_v13` is unchanged in behavior and
content.

## New tables

| Table | Purpose | Mutability |
|---|---|---|
| `model_release_families` | Groups compatible releases under one name/slug, intended use, supported languages, and compatibility policy. Stores `current_release_public_id`, updated only by release creation or a validated rollback. | Mutable lifecycle row |
| `model_release_candidates` | One row per candidate under consideration for release: links a core model version, checkpoint, tokenizer, and (optionally) dataset version, instruction-tuning candidate, and evaluation run. | Mutable lifecycle row |
| `model_release_artifacts` | One row per collected/verified artifact (checkpoint, config, tokenizer files, manifests, model card, release manifest, licence notice). | Append-only |
| `model_release_manifests` | Immutable release-manifest JSON + SHA-256 checksum. | Append-only |
| `model_release_model_cards` | Versioned model-card markdown + checksum + validation status/issues. | Append-only |
| `model_release_eligibility_assessments` | Deterministic eligibility verdicts across 14 dimensions, with a checksum approvals reference to detect staleness. | Append-only |
| `model_release_issues` | Per-candidate findings (28 fixed issue codes) with severity. | Append-only |
| `model_release_approvals` | Role-based approval decisions, each referencing the eligibility/manifest checksums current at submission time. | Append-only |
| `model_releases` | One row per semantic-style-versioned release within a family. | Mutable lifecycle row |
| `model_release_comparisons` | Compatibility assessment between two releases with a field diff. | Append-only |
| `model_release_rollback_plans` | Source→target rollback plans with compatibility/target-verification evidence. | Mutable lifecycle row |
| `model_release_rollback_events` | Append-only record of an executed rollback (previous/new release, approval evidence). | Append-only |
| `model_release_bundles` | Safe export-bundle inventory + checksum for a release. | Append-only |

All tables above except `model_release_families`, `model_release_candidates`,
`model_releases`, and `model_release_rollback_plans` carry `BEFORE
UPDATE`/`BEFORE DELETE` triggers that raise `RAISE(ABORT, ...)` — history
is genuinely append-only.

## Key columns

```
model_release_families:
  lifecycle_status CHECK IN (draft, active, deprecated, archived)
  current_release_public_id  (plain TEXT, not a hard FK — set only by
    release creation or execute_rollback_plan, never directly editable)
  UNIQUE(slug)

model_release_candidates:
  core_model_version_id  (FK core_model_versions, RESTRICT)
  checkpoint_id           (FK pretraining_checkpoints, RESTRICT — resolved
                            automatically at creation time, never accepted
                            as a raw path or arbitrary reference)
  tokenizer_version_id    (FK tokenizer_versions, RESTRICT)
  dataset_version_id, instruction_tuning_candidate_id,
  model_evaluation_run_id  (all nullable FKs — a candidate may originate
                             from a base-pretrained, instruction-tuned, or
                             evaluated model)
  status CHECK IN (draft, collecting_artifacts, validating, eligible,
    eligible_with_warnings, blocked, approved, released, rejected,
    superseded, archived)

model_release_artifacts:
  artifact_type CHECK IN (model_checkpoint, model_config, tokenizer_model,
    tokenizer_vocab, tokenizer_manifest, dataset_manifest,
    base_training_manifest, instruction_tuning_manifest, evaluation_manifest,
    model_card, release_manifest, licence_notice)
  verification_status CHECK IN (pending, verified, missing,
    checksum_mismatch, invalid, not_applicable)
  storage_key  (always a relative, confinement-checked path — never an
                absolute filesystem path accepted from a caller)

model_releases:
  status CHECK IN (draft, released, deprecated, retired, rolled_back, archived)
  deployment_eligibility CHECK IN (deployable, deployable_with_warnings,
    not_deployable)
  UNIQUE(model_release_family_id, version)

model_release_rollback_plans:
  status CHECK IN (draft, validated, approved, executed, rejected, cancelled)
```

## Relationship to existing tables

No Phase 1–13 table is duplicated. Phase 14 tables reference and reuse:

* `core_model_versions` / `pretraining_checkpoints` for the candidate's
  model and verified weights.
* `tokenizer_versions` for the candidate's inherited tokenizer.
* `dataset_versions` for training-data lineage.
* `instruction_tuning_candidates` when the candidate is instruction-tuned.
* `model_evaluation_runs` / `model_chat_readiness_assessments` /
  `model_evaluation_manifests` (Phase 13) for evaluation readiness
  evidence — Phase 14 never re-runs or duplicates evaluation.
* `audit_logs` for every mutating action.
* `admin_accounts` (via plain `created_by_admin_public_id`/
  `admin_public_id` text columns, matching the project-wide convention —
  never a hard FK to `admin_accounts`).

Phase 14 introduces one genuinely new comparison table
(`model_release_comparisons`) rather than reusing Phase 10's
`training_run_comparisons` or Phase 13's `model_evaluation_comparisons`,
because it compares a different entity (releases) with a different
compatibility contract (tokenizer version, model-config checksum,
evaluation-suite identity).

## Migration safety

* `_apply_v14` is guarded by `SELECT 1 FROM schema_migrations WHERE version = 14` — safe to call repeatedly.
* `initialize_database()`/`upgrade_database()` now include 13 in the set of versions that trigger a pre-upgrade verified backup (previously 1–12).
* Fresh databases go straight to v14; a v13 database upgrades additively; a v14 database is a no-op.
* Verified via `tests/database/test_phase14_migration.py`: fresh→14, isolated v13 behavior unchanged, v13→14 upgrade, v14→14 no-op, idempotent re-application, deterministic table/index/trigger sets, mutability of the four lifecycle tables, and append-only enforcement on the other nine.
* Real dev database migrated v13→v14 with a verified backup; `PRAGMA integrity_check` = `ok`, `PRAGMA foreign_key_check` = no violations.

## Not in this migration

No Phase 14 table stores absolute filesystem paths, secrets, raw
checkpoint tensors, or raw private dataset text. `model_release_artifacts`
stores a relative `storage_key` and a checksum, never the artifact's
contents. `model_release_manifests`/`model_release_model_cards` are
scanned for accidental absolute-path or secret-shaped content
(`core_model.release.manifest.scan_for_sensitive_content`) before being
persisted.
