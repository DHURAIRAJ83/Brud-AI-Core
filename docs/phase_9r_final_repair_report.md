# Phase 9R — Final Repair Report

## Baseline

- Baseline commit: `2e9e75f feat: add Brud AI phase 9 bounded pretraining`
- Working tree at start of this repair: 8 modified files already carrying an in-progress, uncommitted repair
  (`backend/api/routes/admin.py`, `backend/api/routes/health.py`, `backend/database/migrations.py`,
  `backend/database/schema.py`, `backend/services/pretraining_service.py`,
  `backend/services/tokenizer_registry.py`, `tests/backend/test_api.py`,
  `tests/backend/test_pretraining_api.py`), plus one untracked file
  (`docs/current_state_audit_before_phase10.md`, an earlier self-audit, since superseded by this report).

## 1. Migration root cause

`HEAD`'s `_apply_v9` (`backend/database/migrations.py`) spliced Phase 10 reliability tables
(`training_dataset_coverage`, `training_recovery_attempts`, `worker_heartbeats`) into the Phase 9
migration function, under a guard that checks for `schema_migrations.version = 9`, but which then
recorded the applied migration as `version = 10`. This had two independent defects:

1. **Malformed table definition** — the `worker_heartbeats` entry in `PHASE10_TABLES`
   (`backend/database/schema.py`, committed HEAD) ends with a bare string,
   `("FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE")`,
   which Python parses as a plain string (no trailing comma to make it a tuple), not the
   `(col_name, col_def)` two-tuple every other entry is. The migration loop
   `for col_name, col_def in columns:` would raise `ValueError: too many values to unpack`
   the first time it reached that table on any fresh database initialization.
2. **Undefined names** — `_apply_v9` references `PHASE10_INDEXES` and `PHASE10_TRIGGERS`, but
   `migrations.py`'s import block only imports `PHASE10_TABLES` from `schema.py`. Both identifiers
   are undefined in `migrations.py`'s namespace (confirmed via `ruff` F821 on the pre-repair code),
   so execution would never even reach a clean state.
3. **Non-idempotent version bookkeeping** — even setting aside (1) and (2), the guard checked for
   `version = 9` but the `INSERT INTO schema_migrations` call recorded `version = 10`. Since the
   guard condition (`version = 9` present) would never become true after the first run, any
   already-migrated database would re-execute the entire faulty block on every subsequent process
   start, hitting the same two defects again — this is what would have surfaced as a startup crash
   in any long-running deployment, not just fresh installs.

## 2. Migration repair

The already-uncommitted working-tree changes (preserved, not discarded, per instructions) remove
the defective Phase 10 injection entirely rather than patching it in place:

- `backend/database/schema.py`: `SCHEMA_VERSION` reverted `10 → 9`; `MIGRATION_010_NAME`,
  `PHASE10_TABLES`, `PHASE10_INDEXES`, `PHASE10_TRIGGERS` deleted.
- `backend/database/migrations.py`: `_apply_v9` now only applies `PHASE9_SCHEMA` and records
  `schema_migrations(version=9, name=MIGRATION_009_NAME)` with `PRAGMA user_version = 9`; the
  `PHASE10_TABLES` import was removed.

This restores Phase 9 as a clean, self-consistent, idempotent baseline. Phase 10 is un-started
again (not half-built), which is the correct state to resume from later.

## 3. Final schema target and current version

Verified live against `data/database/brud_ai.db`:

```
python -m backend.database.migrations status
  → current_version: 9, target_version: 9, migration_status: current
python -m backend.database.migrations verify
  → integrity_check: ok, foreign_key_violations: []
sqlite3 data/database/brud_ai.db "PRAGMA user_version;"        → 9
sqlite3 data/database/brud_ai.db "PRAGMA integrity_check;"     → ok
sqlite3 data/database/brud_ai.db "PRAGMA foreign_key_check;"   → (no rows = no violations)
```

## 4. Test fixture root cause

`tests/backend/test_pretraining_api.py::_fixture_refs` (as left by the in-progress repair) already
trained a real SentencePiece tokenizer and wrote `tokenizer.model`/`tokenizer.vocab` plus an
`artifact_manifest.json` file to disk, with real checksums. However, its
`INSERT INTO tokenizer_versions(...)` column list did not include `artifact_manifest_json`, so the
row fell back to the schema default `'{}'`. `TokenizerService._verify_artifacts`
(`backend/services/tokenizer_registry.py:788-792`) treats an empty/falsy manifest as incomplete
regardless of whether the `.model`/`.vocab` files exist on disk, so every pretraining job in these
two tests failed immediately with `ValidationError: tokenizer artifacts are incomplete`, before
ever reaching real training/checkpointing.

## 5. Test fixture repair

- `_create_tokenizer_artifact` now returns the serialized manifest JSON alongside the vocab size
  and checksums it already computed.
- `_fixture_refs`'s `INSERT INTO tokenizer_versions(...)` now includes `artifact_manifest_json` in
  both the column list and the values tuple, using the exact manifest structure
  (`files`, `model_checksum_sha256`, `vocabulary_checksum_sha256`, `special_tokens`) that
  `TokenizerService.train()` itself produces — no shortcut/fake manifest shape was introduced.

No production validation was weakened, `_verify_artifacts()` was not bypassed, and no synthetic
token IDs were reintroduced anywhere in the fix.

## 6. Real SentencePiece pretraining-path verification

Read `backend/services/pretraining_service.py`, `backend/services/tokenizer_registry.py`, and
`core_model/training/dataset_stream.py` and confirmed normal pretraining jobs:

- Load the registered tokenizer version via `TokenizerService.processor_for_version(public_id)`.
- Verify the artifact manifest and both `.model`/`.vocab` file checksums (`_verify_artifacts`).
- Reject incomplete tokenizer artifacts (`ValidationError` if manifest or files are missing).
- Reject arbitrary tokenizer paths — `_artifact_dir`/`_corpus_dir` route every path component
  through `_safe_component()`, which rejects `.`/`..`/unsafe characters.
- Use a real `SentencePieceProcessor` to encode dataset text (`token_sequences()` in
  `core_model/training/dataset_stream.py`, called from `PretrainingService._blocks`).
- Validate every produced token id against the core model's vocabulary size
  (`PretrainingService._validate_token_ids`), raising `ValidationError` on out-of-range ids.
- Keep `train`/`valid` splits strictly separate — records are partitioned by `row["split"]` before
  tokenization, and packed into independent train/validation blocks.

No synthetic character-to-token mapping remains anywhere in the production service path.

## 7. Phase metadata repair

Added a single source of truth, `backend.PROJECT_PHASE = 9` (`backend/__init__.py`, alongside
`__version__`), and pointed every phase-reporting endpoint at it:

- `GET /api/version` (`backend/api/routes/health.py`)
- `GET /api/admin/overview` (`backend/api/routes/admin.py`)
- `POST /api/chat` (`backend/api/routes/chat.py`) — previously hardcoded `phase=1`, the one
  inconsistency the prior partial repair left behind.

The chat endpoint continues to report `"model": "placeholder"` unchanged — no claim of a trained
model was introduced; only the phase number was corrected to match the rest of the API.

## 8. Admin overview repair

`GET /api/admin/overview` (`backend/api/routes/admin.py`) previously returned hardcoded zeros for
`dataset_records`, `training_jobs`, and `registered_models`. It now runs parameterized `COUNT(*)`
queries directly against the existing SQLite tables through the existing `database_connection()`
helper (the same primitive `database_is_connected()` uses for the health check) — no new repository
class was introduced. The endpoint still requires `require_admin` (unchanged), returns no internal
numeric ids, no filesystem paths, and no secrets. Response fields, all real counts:

- `dataset_records`, `dataset_sources`, `ready_dataset_versions` (`dataset_versions` where
  `status='ready'`)
- `registered_tokenizer_versions` (`tokenizer_versions`), `registered_models`
  (`core_model_versions`, preserving the pre-existing key name)
- `training_jobs` (`pretraining_jobs`, preserving the pre-existing key name),
  `completed_training_jobs` (`pretraining_jobs` where `status='completed'`)

`chatbot_status`, `admin_dashboard_status`, and `core_model_status` are unchanged static fields —
they describe foundation readiness, not a countable resource.

## 9. Exact files modified in this repair (on top of the already-uncommitted repair)

- `tests/backend/test_pretraining_api.py` — added `artifact_manifest_json` to the tokenizer
  fixture insert; fixed import order and two line-length lint errors.
- `backend/services/pretraining_service.py` — wrapped one line to satisfy the 100-character limit
  (no logic change).
- `backend/__init__.py` — added `PROJECT_PHASE = 9`.
- `backend/api/routes/health.py` — `/api/version` now reads `PROJECT_PHASE`.
- `backend/api/routes/admin.py` — `/api/admin/overview` now reads `PROJECT_PHASE` and real DB
  counts instead of hardcoded values.
- `backend/api/routes/chat.py` — `phase` now reads `PROJECT_PHASE` instead of a hardcoded `1`.
- `tests/backend/test_api.py` — updated chat and admin-overview expectations to match.

## 10. Migration test results

```
python -m pytest tests/database -q
  → 29 passed
```
Covers: fresh DB → v9, v8 → v9 upgrade, v9 no-op re-run (idempotency), existing-data preservation,
and absence of any Phase 10 tables/columns in the resulting schema.

## 11. Full pytest result

```
python -m pytest -q
  → 125 passed
```
(123 pre-existing passes + the 2 previously-failing pretraining tests, now fixed. No tests were
deleted or skipped to reach this result.)

## 12. Ruff result

```
python -m ruff check .
  → All checks passed!
```
All 3 pre-existing errors (2 line-length, 1 import-sort) were fixed by reformatting the actual
code — no `noqa`, no config relaxation.

## 13. Diff-check result

```
git diff --check
  → (no output, exit 0)
```

## 14. Chatbot build

```
cd apps/chatbot && npm run build
  → vite build: 22 modules transformed, built in ~210-680ms, no errors
```

## 15. Admin dashboard build

```
cd apps/admin-dashboard && npm run build
  → vite build: 31 modules transformed, built in ~220-830ms, no errors
```
`OverviewPage.jsx` reads `data.dataset_records`, `data.training_jobs`, and `data.registered_models`
— all three keys were preserved unchanged, so the dashboard now shows real counts with no frontend
code changes required. `ChatPage.jsx` only renders the `reply` string, which still reads
"Brud AI chatbot foundation is working." — no false trained-model claim anywhere in the UI.

## 16. API verification (in-process ASGI, temporary DB/app instance)

Verified via an in-process `httpx.ASGITransport` client against a freshly initialized temporary
database (real admin login + CSRF flow, not a dependency override):

| Check | Result |
|---|---|
| `GET /api/health` | 200, `database: connected` |
| `GET /api/version` | 200, `phase: 9` |
| `POST /api/chat` | 200, `model: placeholder`, `phase: 9` |
| `GET /api/admin/overview` (unauthenticated) | 401 |
| `GET /api/admin/tokenizers/capabilities` (unauthenticated) | 401 |
| `GET /api/admin/core-models/capabilities` (unauthenticated) | 401 |
| `GET /api/admin/pretraining/capabilities` (unauthenticated) | 401 |
| Same 4 endpoints, authenticated | all 200 |
| `POST /api/admin/datasets/sources` without CSRF header | 403 |
| Same request with CSRF header | 200 |

No internal numeric ids, filesystem paths, or secret values appeared in any response body.
Since this was verified in-process (no external browser/localhost network dependency), the
frontend-facing portion of this check is: `BUILD_VERIFIED_ONLY` for browser rendering — the API
contract itself was exercised live, not just built.

## 17. Database integrity and foreign-key result

```
integrity_check: ok
foreign_key_check: no violations
```

## 18. Remaining technical debt (not addressed in this repair, by design)

- `backend/database/repositories/phase2.py` (853 lines) remains a large, unused, orphaned
  repository layer (`TrainingJobRepository`, `ModelRegistryRepository`, `ModelVersionRepository`,
  `ModelAssignmentRepository`, `FeedbackRepository`, `AdminApprovalRepository`, etc.) alongside
  their schema tables. It did not cause any test or runtime failure, so per instructions it was
  left untouched — flagged here for a future cleanup phase, not fixed now.
- `backend/training_worker.py` remains a bare poll loop with no heartbeat/lease/crash-recovery.
  The `training_worker_leases` schema table exists with zero code references.
- Three docs — `docs/training_worker_leases.md`, `docs/training_crash_recovery.md`, and
  `docs/training_dataset_coverage.md` — describe the `worker_heartbeats`,
  `training_recovery_attempts`, and `training_dataset_coverage` tables that were part of the
  reverted Phase 10 scaffolding and no longer exist in the schema. These docs now describe
  functionality that isn't implemented; they predate this repair and were left as-is per
  instructions to touch only documentation affected by this repair, but they should be
  reconciled or clearly marked as forward-looking design docs before Phase 10 work resumes.
- `pyproject.toml` and `requirements.txt` declare dependencies independently (`numpy>=2.2,<3.0`
  vs `numpy~=2.5`) — overlapping but not identical; a minor drift risk, not fixed here.
- No Dockerfile/CI pipeline exists in the repository; not in scope for this repair.
- `BRUD_ADMIN_COOKIE_SECURE` still defaults to `false`; fine for local dev, must be set `true`
  before any real deployment.

## 19. Phase 10 readiness

Phase 9 is now a clean, verified, idempotent baseline: schema target and dev-DB version both at 9,
all tests passing, lint clean, both frontend apps building, and the pretraining path genuinely
tokenizer-backed end to end. Phase 10 work can resume from this baseline without inheriting any of
the migration-ownership or version-bookkeeping defects that were present in `HEAD`. No Phase 10
features (heartbeats, leases, crash recovery, dataset coverage reporting) were implemented in this
repair, per instructions — only the ground they'll be built on was repaired.

## 20. Final verdict

```
PHASE_9R_COMPLETE_PHASE_10_READY
```
