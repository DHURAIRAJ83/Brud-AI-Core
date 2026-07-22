# Database schema v2

This document remains the reference for the Phase 2 data/control-plane tables. Phase 3 preserves every v2 table and constraint, then applies additive migration `003_phase3_admin_dataset` with schema version 3.

## Phase 3 extension

- `admin_accounts` stores normalized unique usernames, Argon2 password hashes, account state, failure counters, lockout, and login timestamps. Public UUIDs are exposed; numeric IDs and hashes are private.
- `admin_sessions` stores only SHA-256 hashes of secure random session and CSRF values, plus expiry, last-use, and revocation timestamps.
- Dataset lookup indexes support bounded Phase 3 filters without changing dataset content.
- Database triggers make `dataset_reviews` update/delete immutable.

No Phase 2 table is dropped or rebuilt by migration 003.

Migration `002_phase2_foundation` extends the Phase 1 database without dropping or recreating its tables. Every externally referenced entity uses a UUID public ID; integer IDs remain internal foreign-key implementation details.

## Tables and relationships

- `app_settings` stores typed settings and secret markers. Repository reads redact secret values.
- `chat_sessions` owns `chat_messages` and may later reference an active `model_versions` row.
- `dataset_sources` owns raw `dataset_records`; content hashes support explicit duplicate detection.
- `dataset_reviews` records status decisions for dataset records without losing history.
- `dataset_versions` contains immutable manifests; `dataset_version_items` links each record once to a deterministic train, validation, or test sequence.
- `training_jobs` optionally references a dataset/model version; `training_job_events` records lifecycle changes.
- `model_registry` represents logical families and owns unique `model_versions` labels.
- `model_assignments` maps a bounded assignment key to optional primary and fallback model versions.
- `user_feedback` may reference a chat message and can later be reviewed or converted into dataset work.
- `admin_approvals` persists future approval requests and their outcomes.
- `audit_logs` stores redacted operational metadata and is append-only.

## Lifecycles

Dataset records move among draft, pending review, approved, rejected, and archived states through recorded reviews. Dataset versions move from draft through building to ready; ready manifest/content fields and membership rows cannot be mutated.

Training jobs use explicit validated transitions across draft, validating, queued, running, paused, completed, failed, and cancelled. Phase 2 never starts training.

Model versions move through draft, training, evaluating, staging, active, failed, and retired. A partial unique index supports only one active version per family, and repositories never activate a model automatically.

## Audit guarantees

Audit metadata is deterministic JSON, recursively redacted for secret-like keys, size/depth bounded, and excludes chat content. Database triggers reject updates and deletes. System reads are audited without making non-critical audit failures fatal.
