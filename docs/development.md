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

Do not store secrets in `.env`; it is ignored by Git. The Phase 1 system requires no API keys.

## Common commands

`make backend`, `make chatbot`, and `make admin` run individual services. `make dev` runs all services and terminates the remaining children if any service exits. `make test`, `make lint`, and `make format` operate on Python code. Use `make db-status`, `make db-verify`, `make db-backup`, and `make db-upgrade` for database operations.

## Troubleshooting

- **Missing `venv` or `node_modules`:** run `make setup`.
- **Port already in use:** stop the process using 8000, 5173, or 5174. The Vite configurations use strict ports so a wrong URL is never selected silently.
- **Frontend reports backend offline:** start `make backend` and confirm `curl http://127.0.0.1:8000/api/health`.
- **CORS rejection:** ensure the browser origin exactly matches one of the configured local origins.
- **SQLite locked:** close long-running SQLite clients. Connections use WAL mode and a 5000 ms busy timeout but cannot recover from indefinitely held transactions.

## Database reset

Database reset destroys local Brud AI development data. Stop the backend, run `make db-verify` and `make db-backup`, verify `BRUD_DATABASE_PATH`, then move—not overwrite—the active database and its optional `-wal`/`-shm` companions. Run `make db-init` to create a new schema. Never point the variable at an unrelated project. Tests always use temporary databases and never touch this path. See [database_backup_and_recovery.md](database_backup_and_recovery.md).
