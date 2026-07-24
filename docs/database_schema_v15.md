# Database Schema v15 (Phase 15)

Migration `015_phase15_controlled_inference_runtime` upgrades schema
version 14 → 15. It is a separate, independent migration function
(`_apply_v15`) from migration 014 — Phase 14's `_apply_v14` is unchanged
in behavior and content.

## New tables

| Table | Purpose | Mutability |
|---|---|---|
| `inference_runtime_profiles` | Bounded local runtime configuration (dtype/device, context/token limits, timeouts, resource minimums). | Mutable lifecycle row |
| `inference_runtime_instances` | One row per runtime slot: status, loaded release/checkpoint/tokenizer public IDs, memory snapshot. | Mutable lifecycle row |
| `inference_runtime_health_checks` | One row per health-check execution (8 fixed check types). | Append-only |
| `inference_model_compatibility_assessments` | Deterministic 14-dimension release/runtime compatibility verdicts. | Append-only |
| `inference_assignment_scopes` | The four fixed scopes (`admin_diagnostic`, `admin_chat_lab`, `internal_canary`, `public_chat`) and their enabled flag. | Mutable lifecycle row |
| `inference_model_assignments` | One row per scope-specific assignment of a release to a runtime profile. | Mutable lifecycle row |
| `inference_assignment_versions` | Immutable snapshot created at each approval — release, profile, generation/context/fallback config, and the eligibility/compatibility/approval checksums current at that moment. | Append-only |
| `inference_assignment_approvals` | Role-based approval decisions. | Append-only |
| `inference_assignment_events` | Lifecycle event log (created/validated/approved/activated/paused/…/rollback_completed). | Append-only |
| `inference_sessions` | Admin chat-lab session state (turn count, max turns, expiry). | Mutable lifecycle row |
| `inference_requests` | One row per generation request (prompt checksum only, never raw text). | Append-only |
| `inference_results` | Output checksum, token counts, stop reason, leakage/unicode flags. | Append-only |
| `inference_failures` | Fixed 23-code failure evidence. | Append-only |
| `inference_canary_runs` | Canary lifecycle snapshots — a new row per meaningful transition (started → stopped/completed/paused), never an `UPDATE` of a row results are attached to. | Append-only |
| `inference_canary_results` | Per-fixture-prompt canary outcome (routing decision, latency, leakage/unicode flags). | Append-only |
| `inference_runtime_manifests` | Deterministic runtime manifest JSON + SHA-256 checksum per assignment. | Append-only |

All tables above except `inference_runtime_profiles`,
`inference_runtime_instances`, `inference_assignment_scopes`,
`inference_model_assignments`, and `inference_sessions` carry `BEFORE
UPDATE`/`BEFORE DELETE` triggers that raise `RAISE(ABORT, ...)`.

## Naming note: avoiding a Phase 1 collision

Phase 1 already defined a `model_assignments` table (the placeholder
public-chat/admin-chat-test model-assignment slots). Phase 15's
assignment tables are therefore named `inference_model_assignments`,
`inference_assignment_scopes`, `inference_assignment_versions`,
`inference_assignment_approvals`, and `inference_assignment_events` —
distinct tables, no relationship to the Phase 1 table, discovered and
fixed during migration development (`initialize_database()` raised
`no such column: model_assignment_scope_id` against the Phase 1 table
before the rename).

## Key columns

```
inference_runtime_profiles:
  runtime_type CHECK IN (local_cpu, local_gpu)   -- default local_cpu
  dtype CHECK IN (float32)                        -- only float32 supported
  maximum_loaded_models, maximum_concurrent_requests  -- default 1, 1

inference_runtime_instances:
  status CHECK IN (offline, starting, idle, loading, ready, busy,
    unloading, degraded, failed, stopped)
  loaded_release_public_id, loaded_checkpoint_public_id,
    loaded_tokenizer_public_id  (all nullable TEXT — soft references,
    never exposing PID/hostname/absolute paths)

inference_model_assignments:
  status CHECK IN (draft, validating, approved, active, paused,
    rolled_back, rejected, expired, archived)
  canary_percentage CHECK BETWEEN 0 AND 100
  current_version_public_id  (plain TEXT, updated only by approval or
    execute_rollback)

inference_requests:
  status CHECK IN (accepted, validating, queued, running, completed,
    completed_with_warning, timed_out, cancelled, failed, rejected)
  prompt_checksum_sha256  (never the raw prompt text)

inference_failures:
  failure_code CHECK IN (23 fixed codes: release_not_eligible,
    assignment_not_active, assignment_scope_forbidden,
    registry_fixture_forbidden, manifest_mismatch,
    artifact_verification_failed, checkpoint_corrupt, tokenizer_invalid,
    model_config_mismatch, vocabulary_mismatch, special_token_mismatch,
    memory_guard_failed, disk_guard_failed, model_load_failed,
    context_too_long, generation_timeout, generation_cancelled,
    role_token_leakage, prompt_leakage, unicode_invalid, runtime_busy,
    runtime_unavailable, fallback_used)
```

## Relationship to existing tables

No Phase 1–14 table is duplicated. Phase 15 tables reference and reuse:

* `model_releases` (Phase 14) — the only source of assignable models;
  `inference_model_assignments.model_release_id` is a hard FK (`RESTRICT`).
* `model_release_candidates` / `model_release_manifests` — read via the
  Phase 14 repository to derive checkpoint/tokenizer/config checksums
  and registry-fixture markers, never re-verified from scratch.
* `model_chat_readiness_assessments` (Phase 13) — read live at every
  eligibility check, never cached on the assignment row, so a
  newly-appended blocking assessment takes effect immediately even for
  an already-`released` model.
* `audit_logs` for every mutating action.

## Migration safety

* `_apply_v15` is guarded by `SELECT 1 FROM schema_migrations WHERE version = 15` — safe to call repeatedly.
* `initialize_database()`/`upgrade_database()` now include 14 in the set of versions that trigger a pre-upgrade verified backup (previously 1–13).
* Fresh databases go straight to v15; a v14 database upgrades additively; a v15 database is a no-op.
* Verified via `tests/database/test_phase15_migration.py`: fresh→15, isolated v14 behavior unchanged, v14→15 upgrade with data preservation, v15→15 no-op, idempotent re-application, deterministic table/index/trigger sets, mutability of the five lifecycle tables, and append-only enforcement on the other eleven.
* Real dev database migrated v14→v15 with a verified backup; `PRAGMA integrity_check` = `ok`, `PRAGMA foreign_key_check` = no violations.

## Not in this migration

No Phase 15 table stores absolute filesystem paths, secrets, raw prompt
or output text, raw tensors, or numeric database IDs. `inference_requests`
stores only a prompt checksum; `inference_results` stores only an output
checksum plus structural flags. `inference_runtime_manifests` is scanned
for accidental absolute-path or secret-shaped content
(`core_model.release.manifest.scan_for_sensitive_content`, reused
unchanged from Phase 14) before being persisted.
