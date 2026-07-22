# Local development

## First-time setup

From the repository root, run `./scripts/setup.sh`. It verifies Python 3.11+, Node.js, and npm; creates `venv`; installs all dependencies; preserves any existing `.env`; and initializes SQLite. Re-run it safely when dependencies change.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `BRUD_ENV` | `development` | Runtime environment label |
| `BRUD_HOST` | `127.0.0.1` | Backend bind host for direct launch |
| `BRUD_PORT` | `8000` | Backend port |
| `BRUD_DATABASE_PATH` | `data/database/brud_ai.db` | Absolute path or repository-relative SQLite path |
| `BRUD_LOG_LEVEL` | `INFO` | Standard Python logging level |
| `BRUD_CHATBOT_ORIGIN` | `http://localhost:5173` | Allowed chatbot CORS origin |
| `BRUD_ADMIN_ORIGIN` | `http://localhost:5174` | Allowed admin CORS origin |
| `BRUD_DEBUG` | `false` | FastAPI debug flag |
| `BRUD_DATABASE_BACKUP_DIR` | `data/database/backups` | Verified migration backups |
| `BRUD_DATABASE_BUSY_TIMEOUT_MS` | `5000` | SQLite lock wait bound |
| `BRUD_DATABASE_WAL` | `true` | Enable WAL journaling |
| `BRUD_DATABASE_AUTO_BACKUP` | `true` | Require backup before an existing-schema upgrade |
| `BRUD_AUDIT_ENABLED` | `true` | Record control-plane audit events |
| `BRUD_AUDIT_RETENTION_DAYS` | `365` | Future retention-policy input |
| `BRUD_MAX_METADATA_BYTES` | `65536` | Maximum serialized JSON metadata size |
| `BRUD_ALLOWED_DATA_DIR` | `data` | Permitted data storage root |
| `BRUD_ALLOWED_MODEL_DIR` | `models` | Permitted model storage root |
| `BRUD_ALLOWED_EXPORT_DIR` | `models/exports` | Permitted export storage root |
| `BRUD_ALLOW_EXTERNAL_STORAGE` | `false` | Explicit local override for external storage roots |
| `BRUD_ADMIN_SESSION_TTL_MINUTES` | `480` | Server-side admin-session lifetime |
| `BRUD_ADMIN_MAX_FAILED_LOGINS` | `5` | Failures before temporary lockout |
| `BRUD_ADMIN_LOCKOUT_MINUTES` | `15` | Temporary lockout duration |
| `BRUD_ADMIN_COOKIE_SECURE` | `false` | Require HTTPS for the session cookie; enable in production |
| `BRUD_ADMIN_COOKIE_NAME` | `brud_admin_session` | HttpOnly session-cookie name |
| `BRUD_CSRF_COOKIE_NAME` | `brud_csrf` | CSRF double-submit cookie name |
| `BRUD_CSRF_HEADER_NAME` | `X-CSRF-Token` | Header required for admin mutations |
| `BRUD_IMPORT_DIR` | `data/imports` | Controlled pending/processed/quarantine artifact root |
| `BRUD_IMPORT_REPORT_DIR` | `data/imports/reports` | Bounded generated-report root |
| `BRUD_IMPORT_MAX_FILE_BYTES` | `10485760` | Maximum streamed upload size |
| `BRUD_IMPORT_MAX_ROWS` | `25000` | Maximum parsed rows per job |
| `BRUD_IMPORT_MAX_COLUMNS` | `50` | Maximum structured columns |
| `BRUD_IMPORT_MAX_CELL_CHARS` | `20000` | Maximum cell or line characters |
| `BRUD_IMPORT_PREVIEW_TTL_MINUTES` | `60` | Preview confirmation lifetime |
| `BRUD_IMPORT_ALLOWED_EXTENSIONS` | `.json,.jsonl,.csv,.txt` | Extension allowlist |
| `BRUD_IMPORT_ALLOWED_MIME_TYPES` | bounded local allowlist | MIME allowlist without wildcards |
| `BRUD_IMPORT_DEFAULT_ENCODING` | `utf-8` | UTF decoding policy |
| `BRUD_IMPORT_MAX_ERROR_REPORT_ROWS` | `5000` | Maximum report rows |
| `BRUD_QUALITY_RULESET_VERSION` | `phase6-v1` | Deterministic quality ruleset label |
| `BRUD_QUALITY_READY_THRESHOLD` | `0.8` | Minimum score for ready quality |
| `BRUD_QUALITY_WARNING_THRESHOLD` | `0.6` | Minimum score for warning quality |
| `BRUD_QUALITY_MIN_PRETRAIN_CHARS` | `24` | Minimum pretrain text length before warning |
| `BRUD_QUALITY_MAX_RECORD_CHARS` | `100000` | Maximum record text before quality error |
| `BRUD_DATASET_DEFAULT_TRAIN_PERCENT` | `90` | Default train split |
| `BRUD_DATASET_DEFAULT_VALIDATION_PERCENT` | `5` | Default validation split |
| `BRUD_DATASET_DEFAULT_TEST_PERCENT` | `5` | Default test split |
| `BRUD_DATASET_SPLIT_SEED` | `42` | Reproducible split seed |
| `BRUD_DATASET_EXPORT_DIR` | `data/dataset_exports` | Controlled dataset export root |
| `BRUD_DATASET_EXPORT_MAX_RECORDS` | `100000` | Maximum records in one export |

Do not store secrets in `.env`; it is ignored by Git. The system requires no API keys. Use HTTPS and set `BRUD_ADMIN_COOKIE_SECURE=true` outside local development.

## Common commands

`make backend`, `make chatbot`, and `make admin` run individual services. `make dev` runs all services and terminates the remaining children if any service exits. `make test`, `make lint`, and `make format` operate on Python code. Use `make db-status`, `make db-verify`, `make db-backup`, and `make db-upgrade` for database operations.

Create and maintain local administrators with:

```bash
python -m backend.admin_cli create-admin
python -m backend.admin_cli list-admins
python -m backend.admin_cli disable-admin
python -m backend.admin_cli enable-admin
python -m backend.admin_cli reset-password
```

Security-sensitive commands prompt interactively. The browser obtains CSRF state after login; command-line clients must preserve both cookies and send the token returned by `GET /api/admin/auth/csrf` in the configured header.

Registered import jobs can be inspected with `python -m backend.import_cli list` and `python -m backend.import_cli inspect <public_id>`. `python -m backend.import_cli expire-old` requires typed confirmation and operates only on registered preview jobs; it accepts no paths.

Dataset quality and versioning can be inspected with `python -m backend.dataset_cli quality-summary`, `assess-record <public_id>`, `list-versions`, `inspect-version <public_id>`, `verify-version <public_id>`, and `export-version <public_id>`. Mutating commands require typed confirmation.

## Troubleshooting

- **Missing `venv` or `node_modules`:** run `make setup`.
- **Port already in use:** stop the process using 8000, 5173, or 5174. The Vite configurations use strict ports so a wrong URL is never selected silently.
- **Frontend reports backend offline:** start `make backend` and confirm `curl http://127.0.0.1:8000/api/health`.
- **CORS rejection:** ensure the browser origin exactly matches one of the configured local origins.
- **Admin API returns 401:** create an admin if necessary and sign in again; expired, revoked, disabled, and locked sessions are rejected.
- **Admin mutation returns 403:** refresh CSRF state and send both session/CSRF cookies plus the configured CSRF header.
- **Import stays uploaded:** open its mapping, verify the selected preset/options, and explicitly run Parse and preview.
- **Preview expired:** reparse the registered pending artifact to produce a fresh bounded preview.
- **Dataset build selects no records:** confirm records are approved, quality filters are not too strict, and source licences are not rejected.
- **Export rejected:** only ready or archived dataset versions can be exported.
- **SQLite locked:** close long-running SQLite clients. Connections use WAL mode and a 5000 ms busy timeout but cannot recover from indefinitely held transactions.

## Database reset

Database reset destroys local Brud AI development data. Stop the backend, run `make db-verify` and `make db-backup`, verify `BRUD_DATABASE_PATH`, then move—not overwrite—the active database and its optional `-wal`/`-shm` companions. Run `make db-init` to create a new schema. Never point the variable at an unrelated project. Tests always use temporary databases and never touch this path. See [database_backup_and_recovery.md](database_backup_and_recovery.md).
