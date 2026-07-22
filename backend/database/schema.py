"""Initial SQLite schema for Brud AI Phase 1."""

SCHEMA_VERSION = 2

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
