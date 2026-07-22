# Phase 6 Report

## Baseline

- Baseline commit: `5048529 feat: add Brud AI phase 5 document extraction pipeline`
- Migration: `006_phase6_dataset_versioning`
- Target schema version: `6`

## Files created

- `backend/database/repositories/dataset_quality.py`
- `backend/models/dataset_quality.py`
- `backend/models/dataset_versions.py`
- `backend/services/dataset_quality.py`
- `backend/services/dataset_versioning.py`
- `backend/dataset_cli.py`
- `tests/backend/test_dataset_phase6.py`
- `tests/database/test_phase6_migration.py`
- `docs/database_schema_v6.md`
- `docs/dataset_quality.md`
- `docs/dataset_versioning.md`
- `docs/dataset_splitting.md`
- `docs/dataset_export.md`
- `docs/phase_6_report.md`

## Files modified

- `.env.example`
- `README.md`
- `apps/admin-dashboard/src/pages/DatasetsPage.jsx`
- `apps/admin-dashboard/src/services/api.js`
- `backend/api/routes/datasets.py`
- `backend/core/config.py`
- `backend/database/migrations.py`
- `backend/database/schema.py`
- `backend/services/dataset_service.py`
- `tests/backend/test_system_api.py`
- `tests/database/test_phase3_migration.py`
- `tests/database/test_phase4_migration.py`
- `tests/database/test_phase5_migration.py`

## Implementation

Quality scoring uses deterministic rules for completeness, structure, language/script compatibility, text quality, duplication, safety, and provenance. Assessment history is preserved and records are not edited by assessment.

Dataset builds select approved records only, exclude rejected licences and duplicate hashes, create deterministic small-dataset-aware splits, generate immutable version items, produce a manifest, and calculate a stable SHA-256 checksum.

Exports write UTF-8 manifest and split JSONL files under configured project storage. APIs expose checksums and safe names only.

## Verification

Automated verification before development database migration:

```text
python -m pytest -q
98 passed in 116.60s

python -m ruff check backend tests
All checks passed.

npm run build --prefix apps/admin-dashboard
passed

npm run build --prefix apps/chatbot
passed
```

Development database migration:

```text
pre-upgrade schema: 5
target schema: 6
backup: brud_ai_before_v6_20260722_073148_829941.db
pre-migration checksum: f5d79c8ffb7ffb00c303a053aeac0884c2c0dd5ecbbb43147d771fabf68b7b85
backup checksum: 0c67ca40174cf22ad43dbb421fc74fa0bc2e8be87e45f860d2fdf77eb0f0e4c7
post-migration checksum: d6b60434a4a9b5d8443c475e3051ea191073197a8eb24ddf9540c7eac3344d88
integrity_check: ok
foreign_key_check: []
PRAGMA user_version: 6
```

Final verification:

```text
python -m pytest -q
98 passed in 107.23s

python -m ruff check .
All checks passed.

git diff --check
passed

npm run build --prefix apps/chatbot
passed

npm run build --prefix apps/admin-dashboard
passed
```

API verification was completed through the FastAPI ASGI app because local shell `curl` calls could not connect to the Uvicorn process even when Uvicorn reported it was listening. Verified endpoints included public health/version/chat, authentication, CSRF rejection, quality summary/issues/bulk assessment, version/build list, build creation/validation/run/events, version detail/items/manifest/verify, export creation/detail/download/verify.

Small retained verification data:

- admin account: `phase6-verifier`
- source: `Phase 6 Sample Source`
- version: `phase6_sample v1`
- export safe name prefix: `phase6_sample_v1`

## Known limitations

- No tokenizer or model training.
- No AI-generated quality scoring.
- Override workflows are intentionally minimal.
- Export download currently returns the bounded manifest file.

## Final verdict

PHASE_6_COMPLETE_WITH_WARNINGS
