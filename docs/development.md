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
| `BRUD_TOKENIZER_DIR` | `data/tokenizers` | Controlled tokenizer artifact root |
| `BRUD_TOKENIZER_CORPUS_DIR` | `data/tokenizers/corpora` | Deterministic tokenizer corpus root |
| `BRUD_TOKENIZER_EXPORT_DIR` | `data/tokenizers/exports` | Tokenizer export bundle root |
| `BRUD_TOKENIZER_DEFAULT_ALGORITHM` | `bpe` | Default SentencePiece algorithm |
| `BRUD_TOKENIZER_DEFAULT_VOCAB_SIZE` | `16000` | Default vocabulary size |
| `BRUD_TOKENIZER_MIN_VOCAB_SIZE` | `1000` | Minimum accepted vocabulary size |
| `BRUD_TOKENIZER_MAX_VOCAB_SIZE` | `32000` | Maximum accepted vocabulary size |
| `BRUD_TOKENIZER_CHARACTER_COVERAGE` | `0.9995` | SentencePiece character coverage |
| `BRUD_TOKENIZER_MAX_CORPUS_RECORDS` | `250000` | Corpus record limit |
| `BRUD_TOKENIZER_MAX_CORPUS_CHARS` | `250000000` | Corpus character limit |
| `BRUD_TOKENIZER_MAX_LINE_CHARS` | `20000` | Maximum corpus line length |
| `BRUD_TOKENIZER_INPUT_SENTENCE_SIZE` | `500000` | SentencePiece input sentence limit |
| `BRUD_TOKENIZER_SHUFFLE_INPUT_SENTENCE` | `true` | SentencePiece sentence shuffling flag |
| `BRUD_TOKENIZER_MAX_SENTENCE_LENGTH` | `4096` | SentencePiece maximum sentence length |
| `BRUD_TOKENIZER_NUM_THREADS` | `1` | Bounded local training thread count |
| `BRUD_TOKENIZER_EVAL_MAX_SAMPLES_PER_LANGUAGE` | `1000` | Bounded tokenizer evaluation samples |
| `BRUD_TOKENIZER_MIN_READY_SCORE` | `0.8` | Minimum round-trip readiness score |
| `BRUD_CORE_MODEL_DIR` | `data/core_models` | Controlled core model artifact root |
| `BRUD_CORE_CHECKPOINT_DIR` | `data/core_models/checkpoints` | Registered checkpoint root |
| `BRUD_CORE_MAX_PARAMETERS` | `30000000` | Pre-allocation parameter limit |
| `BRUD_CORE_MAX_CONTEXT_LENGTH` | `1024` | Context length limit |
| `BRUD_CORE_MAX_HIDDEN_SIZE` | `512` | Hidden size limit |
| `BRUD_CORE_MAX_LAYERS` | `12` | Layer count limit |
| `BRUD_CORE_MAX_ATTENTION_HEADS` | `16` | Attention head limit |
| `BRUD_CORE_MAX_INTERMEDIATE_SIZE` | `2048` | Feed-forward size limit |
| `BRUD_CORE_MAX_ESTIMATED_MEMORY_BYTES` | `3000000000` | Conservative training-memory estimate limit |
| `BRUD_CORE_DEFAULT_DTYPE` | `float32` | Phase 8 dtype |
| `BRUD_CORE_DEFAULT_DEVICE` | `cpu` | Phase 8 device |
| `BRUD_CORE_CHECKPOINT_MAX_BYTES` | `500000000` | Checkpoint file size bound |
| `BRUD_CORE_SMOKE_MAX_STEPS` | `100` | Smoke-test step limit |
| `BRUD_CORE_SMOKE_MAX_BATCH_SIZE` | `2` | Smoke-test batch limit |
| `BRUD_CORE_SMOKE_MAX_SEQUENCE_LENGTH` | `256` | Smoke-test sequence limit |
| `BRUD_PRETRAINING_DIR` | `data/core_models/pretraining` | Registered bounded pretraining checkpoint root |
| `BRUD_PRETRAINING_MAX_STEPS` | `5000` | Hard cap for one bounded job |
| `BRUD_PRETRAINING_MAX_TOKENS` | `5000000` | Maximum processed token target |
| `BRUD_PRETRAINING_MAX_BATCH_SIZE` | `2` | CPU-safe batch-size cap |
| `BRUD_PRETRAINING_MAX_GRADIENT_ACCUMULATION` | `16` | Gradient accumulation cap |
| `BRUD_PRETRAINING_MAX_SEQUENCE_LENGTH` | `512` | Sequence length cap |
| `BRUD_PRETRAINING_MAX_CHECKPOINTS` | `20` | Retention-policy input |
| `BRUD_PRETRAINING_MIN_CHECKPOINT_INTERVAL` | `5` | Minimum checkpoint interval |
| `BRUD_PRETRAINING_MAX_ESTIMATED_MEMORY_BYTES` | `3000000000` | Preflight memory cap |
| `BRUD_PRETRAINING_MIN_FREE_DISK_BYTES` | `500000000` | Preflight disk-space floor |
| `BRUD_PRETRAINING_MIN_AVAILABLE_MEMORY_BYTES` | `500000000` | Preflight memory floor |
| `BRUD_PRETRAINING_WORKER_POLL_SECONDS` | `5` | Local worker idle poll interval |
| `BRUD_PRETRAINING_WORKER_LEASE_SECONDS` | `300` | Worker lease duration |
| `BRUD_PRETRAINING_METRIC_INTERVAL_STEPS` | `1` | Default metric persistence interval |
| `BRUD_PRETRAINING_VALIDATION_MAX_BATCHES` | `10` | Validation-loss batch bound |
| `BRUD_PRETRAINING_NAN_FAILURE` | `true` | Treat non-finite values as failure |
| `BRUD_PRETRAINING_DEFAULT_PORT` | `8001` | Alternate local verification port |
| `BRUD_PRETRAINING_KEEP_PERIODIC` | `3` | Periodic checkpoints retained per job (newest first) |
| `BRUD_PRETRAINING_KEEP_BEST` | `1` | Best-validation checkpoints retained per job |
| `BRUD_PRETRAINING_KEEP_FINAL` | `1` | Final checkpoints retained per job |
| `BRUD_PRETRAINING_KEEP_PAUSE` | `1` | Pause checkpoints retained per job |
| `BRUD_PRETRAINING_RETENTION_DRY_RUN` | `true` | Retention apply records actions without archiving when true |
| `BRUD_TRAINING_QUALITY_RULESET_VERSION` | `phase10-v1` | Deterministic training-quality ruleset label |
| `BRUD_TRAINING_MIN_PROCESSED_TOKENS` | `8` | Minimum processed tokens before an insufficient-tokens issue |
| `BRUD_TRAINING_MIN_LOSS_IMPROVEMENT_RATIO` | `0.0` | Minimum required training-loss improvement ratio |
| `BRUD_TRAINING_MAX_TRAIN_VALIDATION_GAP` | `5.0` | Maximum allowed validation-minus-training loss gap |
| `BRUD_TRAINING_MAX_EXCLUDED_RECORD_RATIO` | `0.5` | Maximum allowed excluded-record ratio |
| `BRUD_TRAINING_MIN_VALIDATION_TOKENS` | `4` | Minimum validation-split tokens |
| `BRUD_TRAINING_REQUIRE_VALIDATION` | `true` | Require a validation loss before ready-for-staging |
| `BRUD_TRAINING_REQUIRE_RESUME_CHECK_IF_RESUMED` | `true` | Require resume-integrity pass for resumed jobs |
| `BRUD_TRAINING_MAX_NON_FINITE_EVENTS` | `0` | Maximum tolerated non-finite loss/gradient events |
| `BRUD_TRAINING_REQUIRE_ALL_CHECKPOINTS_VERIFIED` | `true` | Require every checkpoint verified before ready-for-staging |
| `BRUD_TRAINING_MIN_COVERAGE_RATIO` | `0.5` | Minimum dataset coverage ratio before a coverage warning |
| `BRUD_BASE_TRAINING_MIN_RECORDS` | `500` | Recommended minimum approved records for a representative-scale experiment |
| `BRUD_BASE_TRAINING_MIN_TAMIL_RATIO` | `0.30` | Minimum Tamil share before a dataset-profile warning |
| `BRUD_BASE_TRAINING_MIN_ENGLISH_RATIO` | `0.05` | Minimum English share before a dataset-profile warning |
| `BRUD_BASE_TRAINING_MIN_TANGLISH_RATIO` | `0.05` | Minimum Tanglish share before a dataset-profile warning |
| `BRUD_BASE_TRAINING_MAX_DUPLICATE_RATIO` | `0.15` | Maximum duplicate/near-duplicate rate before a warning |
| `BRUD_BASE_TRAINING_MIN_VALIDATION_RECORDS` | `20` | Minimum validation-split records before a tiny-split warning |
| `BRUD_BASE_TRAINING_MIN_TEST_RECORDS` | `20` | Minimum test-split records before test evaluation is marked unreliable |
| `BRUD_BASE_TRAINING_MIN_TOKEN_BUDGET` | `50000` | Minimum processed-token budget for a base-training run |
| `BRUD_BASE_TRAINING_MAX_TOKEN_BUDGET` | `500000` | Maximum processed-token budget for a base-training run |
| `BRUD_BASE_TRAINING_GENERALIZATION_MAX_GAP` | `3.0` | Maximum validation-minus-training loss gap before a generalization warning |
| `BRUD_BASE_TRAINING_MEMORIZATION_MAX_GAP` | `4.0` | Gap threshold (with near-zero training loss) that triggers a memorization warning |
| `BRUD_BASE_TRAINING_TOKENIZER_MAX_UNKNOWN_RATE` | `0.05` | Maximum unknown-token rate before tokenizer suitability is downgraded |
| `BRUD_BASE_TRAINING_TOKENIZER_MIN_ROUND_TRIP` | `0.95` | Minimum round-trip success rate before a tokenizer is blocked as unsuitable |
| `BRUD_INSTRUCTION_TUNING_MIN_RECORDS` | `1000` | Recommended minimum eligible instruction examples for a representative-scale experiment |
| `BRUD_INSTRUCTION_TUNING_LIMITED_EXPERIMENT_FLOOR` | `200` | Minimum eligible examples for a limited-scale experiment |
| `BRUD_INSTRUCTION_TUNING_MIN_VALIDATION_RECORDS` | `10` | Minimum validation-split records before a tiny-split warning |
| `BRUD_INSTRUCTION_TUNING_MIN_TEST_RECORDS` | `10` | Minimum test-split records before test evaluation is marked unreliable |
| `BRUD_INSTRUCTION_TUNING_MAX_ROLE_LEAKAGE_RATE` | `0.0` | Maximum tolerated role-token leakage rate before the learning check fails |
| `BRUD_INSTRUCTION_TUNING_MAX_PROMPT_LEAKAGE_RATE` | `0.1` | Maximum tolerated prompt-leakage rate before a warning |
| `BRUD_INSTRUCTION_TUNING_MAX_REPETITION_RATE` | `0.2` | Maximum tolerated repetition rate before a warning |
| `BRUD_INSTRUCTION_TUNING_MAX_EXACT_MATCH_RATE` | `0.2` | Maximum tolerated exact training-response reproduction rate |
| `BRUD_INSTRUCTION_TUNING_MAX_DUPLICATE_OUTPUT_RATE` | `0.3` | Maximum tolerated duplicate-output rate across fixture generations |
| `BRUD_INSTRUCTION_TUNING_MAX_LONGEST_SPAN_RATIO` | `0.8` | Maximum tolerated longest-matching-span ratio against training responses |
| `BRUD_INSTRUCTION_TUNING_MAX_TRAIN_VALIDATION_GAP` | `4.0` | Gap threshold (with near-zero training loss) that triggers a memorization warning |
| `BRUD_INSTRUCTION_TUNING_GENERATION_MAX_NEW_TOKENS` | `32` | Hard cap on tokens generated by bounded diagnostic generation |
| `BRUD_INSTRUCTION_TUNING_GENERATION_TIMEOUT_SECONDS` | `5.0` | Wall-clock timeout for one bounded diagnostic generation call |

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

Tokenizer work can be inspected with `python -m backend.tokenizer_cli capabilities`, `list`, `inspect <public_id>`, `build-corpus <job_public_id>`, `dry-run <job_public_id>`, `train <job_public_id>`, `evaluate <version_public_id>`, `verify <version_public_id>`, and `activate <version_public_id>`. Training and activation require typed confirmation and operate only on registered public IDs.

Core model architecture work can be inspected with `python -m backend.core_model_cli capabilities`, `list-configs`, `inspect-config <public_id>`, `list-versions`, `inspect-version <public_id>`, `initialize <public_id>`, `verify <public_id>`, `smoke-test <public_id>`, and `verify-checkpoint <public_id>`. Initialization and smoke tests require typed confirmation and operate only on registered public IDs.

Bounded pretraining can be inspected with `python -m backend.pretraining_cli capabilities`, `list`, `inspect <job_public_id>`, `preflight <job_public_id>`, `queue <job_public_id>`, `pause <job_public_id>`, `resume <job_public_id>`, `cancel <job_public_id>`, `metrics <job_public_id>`, `list-checkpoints <job_public_id>`, `verify-checkpoint <checkpoint_public_id>`, and `promote <checkpoint_public_id>`. Mutating commands require typed confirmation. Run the local worker separately with `python -m backend.training_worker`; add `--once` for a single claim-and-exit verification run, `--poll-seconds <n>` to override the poll interval, and `--worker-name <name>` to set a stable worker identity across restarts.

Training reliability and recovery can be inspected and controlled with `python -m backend.training_recovery_cli status`, `stale-jobs`, `inspect <job_public_id>`, `verify-resume <job_public_id>` (read-only dry check), and `recover <job_public_id>` (mutating; requires typing `recover` to confirm). Every command operates on public IDs only. See [training_crash_recovery.md](training_crash_recovery.md).

## Troubleshooting

- **Missing `venv` or `node_modules`:** run `make setup`.
- **Port already in use:** inspect ownership non-destructively, for example `ss -ltnp | grep ':8000'` when permissions allow. Do not kill unknown processes automatically. Use an alternate backend port such as `8001` for verification if needed. The Vite configurations use strict ports so a wrong frontend URL is never selected silently.
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
