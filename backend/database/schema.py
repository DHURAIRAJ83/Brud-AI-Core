"""Initial SQLite schema for Brud AI Phase 1."""

SCHEMA_VERSION = 4

INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL DEFAULT 'auto',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dataset_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dataset_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    content TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'raw',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES dataset_sources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS training_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'pending',
    configuration TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'registered',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

MIGRATION_002_NAME = "002_phase2_foundation"

PHASE2_NEW_TABLES = """
CREATE TABLE IF NOT EXISTS dataset_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    dataset_record_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approve','reject','request_changes','edit','restore')),
    reviewer_type TEXT NOT NULL CHECK (reviewer_type IN ('admin','system','admin_assistant')),
    reviewer_reference TEXT,
    comments TEXT,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_record_id) REFERENCES dataset_records(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','building','ready','failed','archived')),
    manifest_json TEXT NOT NULL DEFAULT '{}',
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    split_distribution_json TEXT NOT NULL DEFAULT '{}',
    checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalized_at TEXT,
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS dataset_version_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_version_id INTEGER NOT NULL,
    dataset_record_id INTEGER NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('train','validation','test')),
    sequence_number INTEGER NOT NULL CHECK (sequence_number >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_record_id) REFERENCES dataset_records(id) ON DELETE RESTRICT,
    UNIQUE(dataset_version_id, dataset_record_id),
    UNIQUE(dataset_version_id, split, sequence_number)
);

CREATE TABLE IF NOT EXISTS training_job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    training_job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (training_job_id) REFERENCES training_jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_registry_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN ('draft','training','evaluating','staging','active','failed','retired')),
    architecture TEXT NOT NULL,
    parameter_count INTEGER CHECK (parameter_count IS NULL OR parameter_count >= 0),
    context_length INTEGER CHECK (context_length IS NULL OR context_length > 0),
    vocabulary_size INTEGER CHECK (vocabulary_size IS NULL OR vocabulary_size > 0),
    tokenizer_reference TEXT,
    checkpoint_path TEXT,
    export_path TEXT,
    quantization TEXT,
    dataset_version_id INTEGER,
    training_job_id INTEGER,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    checksum_sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TEXT,
    FOREIGN KEY (model_registry_id) REFERENCES model_registry(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE SET NULL,
    FOREIGN KEY (training_job_id) REFERENCES training_jobs(id) ON DELETE SET NULL,
    UNIQUE(model_registry_id, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_model_versions_one_active
ON model_versions(model_registry_id) WHERE lifecycle_status = 'active';

CREATE TABLE IF NOT EXISTS model_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_key TEXT NOT NULL UNIQUE CHECK (assignment_key IN ('public_chat','admin_chat_test','admin_assistant','tanglish_normalizer','embedding','fallback')),
    model_version_id INTEGER,
    fallback_model_version_id INTEGER,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL,
    FOREIGN KEY (fallback_model_version_id) REFERENCES model_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    chat_message_id INTEGER,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('like','dislike','wrong_answer','language_issue','unsafe_answer','incomplete_answer','suggested_correction')),
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    comment TEXT,
    suggested_answer TEXT,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','under_review','accepted','rejected','converted_to_dataset','archived')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    FOREIGN KEY (chat_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS admin_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    action_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_public_id TEXT NOT NULL,
    request_payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','cancelled','expired')),
    requested_by TEXT NOT NULL,
    reviewed_by TEXT,
    review_comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT
);
"""

PHASE2_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "schema_migrations": [("name", "TEXT")],
    "app_settings": [
        ("value_type", "TEXT NOT NULL DEFAULT 'string'"),
        ("is_secret", "INTEGER NOT NULL DEFAULT 0"),
        ("description", "TEXT"),
    ],
    "chat_sessions": [
        ("public_id", "TEXT"),
        ("title", "TEXT"),
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("preferred_language", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("active_model_version_id", "INTEGER REFERENCES model_versions(id) ON DELETE SET NULL"),
        ("archived_at", "TEXT"),
    ],
    "chat_messages": [
        ("public_id", "TEXT"),
        ("detected_language", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("normalized_content", "TEXT"),
        ("model_version_id", "INTEGER REFERENCES model_versions(id) ON DELETE SET NULL"),
        ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
    ],
    "dataset_sources": [
        ("public_id", "TEXT"),
        ("original_filename", "TEXT"),
        ("source_uri", "TEXT"),
        ("language", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("licence_name", "TEXT"),
        ("licence_status", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("checksum_sha256", "TEXT"),
        ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
    ],
    "dataset_records": [
        ("public_id", "TEXT"),
        ("record_type", "TEXT NOT NULL DEFAULT 'instruction'"),
        ("instruction", "TEXT"),
        ("input_text", "TEXT"),
        ("output_text", "TEXT"),
        ("normalized_input", "TEXT"),
        ("content_hash", "TEXT"),
        ("quality_score", "REAL"),
        ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
    ],
    "training_jobs": [
        ("public_id", "TEXT"),
        ("name", "TEXT NOT NULL DEFAULT 'unnamed'"),
        ("training_type", "TEXT NOT NULL DEFAULT 'smoke_test'"),
        ("dataset_version_id", "INTEGER REFERENCES dataset_versions(id) ON DELETE SET NULL"),
        ("base_model_version_id", "INTEGER REFERENCES model_versions(id) ON DELETE SET NULL"),
        ("tokenizer_reference", "TEXT"),
        ("config_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("hardware_profile", "TEXT NOT NULL DEFAULT 'unspecified'"),
        ("progress", "REAL NOT NULL DEFAULT 0"),
        ("current_step", "INTEGER NOT NULL DEFAULT 0"),
        ("total_steps", "INTEGER NOT NULL DEFAULT 0"),
        ("error_code", "TEXT"),
        ("error_message", "TEXT"),
        ("started_at", "TEXT"),
        ("completed_at", "TEXT"),
    ],
    "model_registry": [
        ("public_id", "TEXT"),
        ("model_type", "TEXT NOT NULL DEFAULT 'core'"),
        ("description", "TEXT"),
    ],
    "audit_logs": [
        ("public_id", "TEXT"),
        ("event_type", "TEXT NOT NULL DEFAULT 'legacy_event'"),
        ("actor_type", "TEXT NOT NULL DEFAULT 'system'"),
        ("actor_reference", "TEXT"),
        ("resource_type", "TEXT"),
        ("resource_public_id", "TEXT"),
        ("outcome", "TEXT NOT NULL DEFAULT 'success'"),
        ("request_id", "TEXT"),
        ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
    ],
}

MIGRATION_003_NAME = "003_phase3_admin_dataset"

PHASE3_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','locked')),
    failed_login_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_login_count >= 0),
    locked_until TEXT,
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admin_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    admin_account_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_account_id) REFERENCES admin_accounts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_admin_sessions_account ON admin_sessions(admin_account_id);
CREATE INDEX IF NOT EXISTS ix_dataset_records_status ON dataset_records(status);
CREATE INDEX IF NOT EXISTS ix_dataset_records_content_hash ON dataset_records(content_hash);
CREATE INDEX IF NOT EXISTS ix_dataset_sources_status ON dataset_sources(status);
CREATE TRIGGER IF NOT EXISTS dataset_reviews_immutable_update
BEFORE UPDATE ON dataset_reviews
BEGIN SELECT RAISE(ABORT, 'dataset reviews are immutable'); END;
CREATE TRIGGER IF NOT EXISTS dataset_reviews_immutable_delete
BEFORE DELETE ON dataset_reviews
BEGIN SELECT RAISE(ABORT, 'dataset reviews are immutable'); END;
"""

MIGRATION_004_NAME = "004_phase4_dataset_import"

PHASE4_SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset_import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_public_id TEXT,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL UNIQUE,
    detected_file_type TEXT NOT NULL CHECK (detected_file_type IN ('json','jsonl','csv','txt')),
    declared_file_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL CHECK (file_size_bytes > 0),
    checksum_sha256 TEXT NOT NULL,
    encoding TEXT NOT NULL CHECK (encoding IN ('utf-8','utf-8-sig')),
    status TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','parsing','preview_ready','confirmed','importing','completed','completed_with_warnings','failed','cancelled','expired')),
    import_mode TEXT NOT NULL CHECK (import_mode IN ('create_only','skip_duplicates')),
    record_type TEXT NOT NULL,
    default_language TEXT NOT NULL,
    field_mapping_json TEXT NOT NULL DEFAULT '{}',
    parser_options_json TEXT NOT NULL DEFAULT '{}',
    total_rows INTEGER NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
    valid_rows INTEGER NOT NULL DEFAULT 0 CHECK (valid_rows >= 0),
    warning_rows INTEGER NOT NULL DEFAULT 0 CHECK (warning_rows >= 0),
    duplicate_rows INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_rows >= 0),
    invalid_rows INTEGER NOT NULL DEFAULT 0 CHECK (invalid_rows >= 0),
    imported_rows INTEGER NOT NULL DEFAULT 0 CHECK (imported_rows >= 0),
    failed_rows INTEGER NOT NULL DEFAULT 0 CHECK (failed_rows >= 0),
    error_code TEXT,
    error_message TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    previewed_at TEXT,
    confirmed_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS dataset_import_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    import_job_id INTEGER NOT NULL,
    row_number INTEGER NOT NULL CHECK (row_number > 0),
    raw_data_json TEXT NOT NULL DEFAULT '{}',
    normalized_data_json TEXT NOT NULL DEFAULT '{}',
    record_type TEXT NOT NULL,
    language TEXT NOT NULL,
    instruction TEXT,
    input_text TEXT,
    output_text TEXT,
    normalized_input TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT,
    row_status TEXT NOT NULL CHECK (row_status IN ('valid','warning','duplicate','invalid','imported','skipped','failed')),
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    validation_warnings_json TEXT NOT NULL DEFAULT '[]',
    duplicate_record_public_id TEXT,
    imported_record_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (import_job_id) REFERENCES dataset_import_jobs(id) ON DELETE CASCADE,
    UNIQUE(import_job_id, row_number)
);
CREATE TABLE IF NOT EXISTS dataset_import_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (import_job_id) REFERENCES dataset_import_jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_import_jobs_status ON dataset_import_jobs(status);
CREATE INDEX IF NOT EXISTS ix_import_jobs_created ON dataset_import_jobs(created_at);
CREATE INDEX IF NOT EXISTS ix_import_rows_status ON dataset_import_rows(import_job_id,row_status);
CREATE INDEX IF NOT EXISTS ix_import_rows_number ON dataset_import_rows(import_job_id,row_number);
CREATE INDEX IF NOT EXISTS ix_import_rows_hash ON dataset_import_rows(content_hash);
CREATE INDEX IF NOT EXISTS ix_import_rows_duplicate ON dataset_import_rows(duplicate_record_public_id);
CREATE TRIGGER IF NOT EXISTS dataset_import_events_immutable_update
BEFORE UPDATE ON dataset_import_events
BEGIN SELECT RAISE(ABORT, 'dataset import events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS dataset_import_events_immutable_delete
BEFORE DELETE ON dataset_import_events
BEGIN SELECT RAISE(ABORT, 'dataset import events are immutable'); END;
"""
