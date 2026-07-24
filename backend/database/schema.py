"""Initial SQLite schema for Brud AI Phase 1."""

SCHEMA_VERSION = 14

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

MIGRATION_005_NAME = "005_phase5_document_processing"

PHASE5_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    dataset_source_public_id TEXT,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL UNIQUE,
    document_type TEXT NOT NULL CHECK (document_type IN ('pdf','text')),
    mime_type TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL CHECK (file_size_bytes > 0),
    checksum_sha256 TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0 CHECK (page_count >= 0),
    detected_language TEXT NOT NULL DEFAULT 'unknown',
    extraction_strategy TEXT NOT NULL CHECK (extraction_strategy IN ('auto','embedded_text','ocr','hybrid')),
    status TEXT NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','validating','ready','processing','review_ready','completed','completed_with_warnings','failed','cancelled','archived')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS document_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL CHECK (page_number > 0),
    width_points REAL,
    height_points REAL,
    rotation INTEGER NOT NULL DEFAULT 0,
    embedded_text_available INTEGER NOT NULL DEFAULT 0 CHECK (embedded_text_available IN (0,1)),
    image_count INTEGER NOT NULL DEFAULT 0 CHECK (image_count >= 0),
    extraction_method TEXT NOT NULL DEFAULT 'none' CHECK (extraction_method IN ('none','embedded','ocr','hybrid','manual')),
    extraction_status TEXT NOT NULL DEFAULT 'pending' CHECK (extraction_status IN ('pending','extracting','success','warning','failed','skipped')),
    raw_text TEXT,
    cleaned_text TEXT,
    text_length INTEGER NOT NULL DEFAULT 0 CHECK (text_length >= 0),
    confidence_score REAL CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1),
    language TEXT NOT NULL DEFAULT 'unknown',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error_code TEXT,
    error_message TEXT,
    processing_duration_ms INTEGER CHECK (processing_duration_ms IS NULL OR processing_duration_ms >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE,
    UNIQUE(document_source_id,page_number)
);
CREATE TABLE IF NOT EXISTS document_page_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_page_id INTEGER NOT NULL,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    cleaned_text TEXT NOT NULL,
    edited_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_page_id) REFERENCES document_pages(id) ON DELETE CASCADE,
    UNIQUE(document_page_id,revision_number)
);
CREATE TABLE IF NOT EXISTS document_processing_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    job_type TEXT NOT NULL CHECK (job_type IN ('analyze','extract','ocr','reprocess_pages','segment','candidate_import')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validating','queued','running','paused','completed','completed_with_warnings','failed','cancelled')),
    requested_strategy TEXT NOT NULL,
    selected_pages_json TEXT NOT NULL DEFAULT '[]',
    configuration_json TEXT NOT NULL DEFAULT '{}',
    total_pages INTEGER NOT NULL DEFAULT 0 CHECK (total_pages >= 0),
    processed_pages INTEGER NOT NULL DEFAULT 0 CHECK (processed_pages >= 0),
    successful_pages INTEGER NOT NULL DEFAULT 0 CHECK (successful_pages >= 0),
    warning_pages INTEGER NOT NULL DEFAULT 0 CHECK (warning_pages >= 0),
    failed_pages INTEGER NOT NULL DEFAULT 0 CHECK (failed_pages >= 0),
    progress REAL NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    error_code TEXT,
    error_message TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS document_processing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processing_job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    page_number INTEGER,
    previous_status TEXT,
    new_status TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (processing_job_id) REFERENCES document_processing_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS document_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    source_page_start INTEGER NOT NULL CHECK (source_page_start > 0),
    source_page_end INTEGER NOT NULL CHECK (source_page_end >= source_page_start),
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    candidate_type TEXT NOT NULL CHECK (candidate_type IN ('pretrain','instruction','chat','translation','tanglish_pair','safety','preference')),
    language TEXT NOT NULL,
    instruction TEXT,
    input_text TEXT,
    output_text TEXT,
    normalized_input TEXT,
    candidate_text TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','valid','warning','duplicate','invalid','selected','rejected','imported')),
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    validation_warnings_json TEXT NOT NULL DEFAULT '[]',
    duplicate_record_public_id TEXT,
    imported_record_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imported_at TEXT,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE,
    UNIQUE(document_source_id,sequence_number)
);
CREATE INDEX IF NOT EXISTS ix_documents_checksum ON document_sources(checksum_sha256);
CREATE INDEX IF NOT EXISTS ix_documents_status ON document_sources(status);
CREATE INDEX IF NOT EXISTS ix_documents_created ON document_sources(created_at);
CREATE INDEX IF NOT EXISTS ix_document_pages_number ON document_pages(document_source_id,page_number);
CREATE INDEX IF NOT EXISTS ix_document_pages_status ON document_pages(document_source_id,extraction_status);
CREATE INDEX IF NOT EXISTS ix_document_jobs_status ON document_processing_jobs(status);
CREATE INDEX IF NOT EXISTS ix_document_candidates_status ON document_candidates(document_source_id,status);
CREATE INDEX IF NOT EXISTS ix_document_candidates_hash ON document_candidates(content_hash);
CREATE INDEX IF NOT EXISTS ix_document_candidates_duplicate ON document_candidates(duplicate_record_public_id);
CREATE TRIGGER IF NOT EXISTS document_events_immutable_update BEFORE UPDATE ON document_processing_events BEGIN SELECT RAISE(ABORT, 'document processing events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS document_events_immutable_delete BEFORE DELETE ON document_processing_events BEGIN SELECT RAISE(ABORT, 'document processing events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS document_revisions_immutable_update BEFORE UPDATE ON document_page_revisions BEGIN SELECT RAISE(ABORT, 'document page revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS document_revisions_immutable_delete BEFORE DELETE ON document_page_revisions BEGIN SELECT RAISE(ABORT, 'document page revisions are immutable'); END;
"""

MIGRATION_006_NAME = "006_phase6_dataset_versioning"

PHASE6_SCHEMA = """
ALTER TABLE dataset_versions ADD COLUMN quality_summary_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE dataset_versions ADD COLUMN source_distribution_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE dataset_versions ADD COLUMN record_type_distribution_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE dataset_versions ADD COLUMN build_configuration_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE dataset_versions ADD COLUMN parent_dataset_version_id INTEGER REFERENCES dataset_versions(id) ON DELETE SET NULL;
ALTER TABLE dataset_versions ADD COLUMN export_status TEXT NOT NULL DEFAULT 'not_exported';

CREATE TABLE IF NOT EXISTS dataset_quality_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    dataset_record_id INTEGER NOT NULL,
    assessment_version TEXT NOT NULL,
    overall_score REAL NOT NULL CHECK (overall_score BETWEEN 0 AND 1),
    completeness_score REAL NOT NULL CHECK (completeness_score BETWEEN 0 AND 1),
    structure_score REAL NOT NULL CHECK (structure_score BETWEEN 0 AND 1),
    language_score REAL NOT NULL CHECK (language_score BETWEEN 0 AND 1),
    text_quality_score REAL NOT NULL CHECK (text_quality_score BETWEEN 0 AND 1),
    duplication_score REAL NOT NULL CHECK (duplication_score BETWEEN 0 AND 1),
    safety_score REAL NOT NULL CHECK (safety_score BETWEEN 0 AND 1),
    provenance_score REAL NOT NULL CHECK (provenance_score BETWEEN 0 AND 1),
    readiness_status TEXT NOT NULL CHECK (readiness_status IN ('ready','warning','blocked','not_assessed')),
    summary_json TEXT NOT NULL DEFAULT '{}',
    assessed_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_record_id) REFERENCES dataset_records(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS dataset_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    quality_assessment_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','blocking')),
    field_name TEXT,
    message TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quality_assessment_id) REFERENCES dataset_quality_assessments(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS dataset_build_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    dataset_version_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validating','building','completed','completed_with_warnings','failed','cancelled')),
    selection_filters_json TEXT NOT NULL DEFAULT '{}',
    split_configuration_json TEXT NOT NULL DEFAULT '{}',
    deduplication_configuration_json TEXT NOT NULL DEFAULT '{}',
    total_candidate_records INTEGER NOT NULL DEFAULT 0 CHECK (total_candidate_records >= 0),
    selected_records INTEGER NOT NULL DEFAULT 0 CHECK (selected_records >= 0),
    excluded_records INTEGER NOT NULL DEFAULT 0 CHECK (excluded_records >= 0),
    train_records INTEGER NOT NULL DEFAULT 0 CHECK (train_records >= 0),
    validation_records INTEGER NOT NULL DEFAULT 0 CHECK (validation_records >= 0),
    test_records INTEGER NOT NULL DEFAULT 0 CHECK (test_records >= 0),
    warning_records INTEGER NOT NULL DEFAULT 0 CHECK (warning_records >= 0),
    error_records INTEGER NOT NULL DEFAULT 0 CHECK (error_records >= 0),
    progress REAL NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    error_code TEXT,
    error_message TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS dataset_build_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (build_job_id) REFERENCES dataset_build_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS dataset_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    dataset_version_id INTEGER NOT NULL,
    export_format TEXT NOT NULL CHECK (export_format IN ('jsonl','manifest_json','split_jsonl_bundle')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','exporting','completed','failed','cancelled')),
    safe_name TEXT NOT NULL UNIQUE,
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    checksum_sha256 TEXT,
    file_manifest_json TEXT NOT NULL DEFAULT '{}',
    error_code TEXT,
    error_message TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_quality_assessments_record ON dataset_quality_assessments(dataset_record_id,created_at);
CREATE INDEX IF NOT EXISTS ix_quality_assessments_readiness ON dataset_quality_assessments(readiness_status);
CREATE INDEX IF NOT EXISTS ix_quality_issues_code ON dataset_quality_issues(issue_code);
CREATE INDEX IF NOT EXISTS ix_quality_issues_severity ON dataset_quality_issues(severity);
CREATE INDEX IF NOT EXISTS ix_build_jobs_status ON dataset_build_jobs(status);
CREATE INDEX IF NOT EXISTS ix_build_jobs_dataset_version ON dataset_build_jobs(dataset_version_id);
CREATE INDEX IF NOT EXISTS ix_build_events_job ON dataset_build_events(build_job_id,created_at);
CREATE INDEX IF NOT EXISTS ix_dataset_exports_version ON dataset_exports(dataset_version_id);
CREATE INDEX IF NOT EXISTS ix_dataset_exports_status ON dataset_exports(status);
CREATE TRIGGER IF NOT EXISTS dataset_build_events_immutable_update BEFORE UPDATE ON dataset_build_events BEGIN SELECT RAISE(ABORT, 'dataset build events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS dataset_build_events_immutable_delete BEFORE DELETE ON dataset_build_events BEGIN SELECT RAISE(ABORT, 'dataset build events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS dataset_quality_issues_immutable_update BEFORE UPDATE ON dataset_quality_issues BEGIN SELECT RAISE(ABORT, 'dataset quality issues are immutable'); END;
CREATE TRIGGER IF NOT EXISTS dataset_quality_issues_immutable_delete BEFORE DELETE ON dataset_quality_issues BEGIN SELECT RAISE(ABORT, 'dataset quality issues are immutable'); END;
"""

MIGRATION_007_NAME = "007_phase7_tokenizer_training"

PHASE7_SCHEMA = """
CREATE TABLE IF NOT EXISTS tokenizer_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    tokenizer_type TEXT NOT NULL DEFAULT 'sentencepiece' CHECK (tokenizer_type IN ('sentencepiece')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','inactive','archived')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tokenizer_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_family_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN ('draft','validating','training','evaluating','staging','active','failed','retired','archived')),
    algorithm TEXT NOT NULL CHECK (algorithm IN ('bpe','unigram')),
    vocabulary_size INTEGER NOT NULL CHECK (vocabulary_size > 0),
    character_coverage REAL NOT NULL CHECK (character_coverage > 0 AND character_coverage <= 1),
    normalization_rule_name TEXT NOT NULL,
    model_type TEXT NOT NULL DEFAULT 'sentencepiece',
    dataset_version_id INTEGER NOT NULL,
    training_job_id INTEGER,
    corpus_checksum_sha256 TEXT,
    model_checksum_sha256 TEXT,
    vocabulary_checksum_sha256 TEXT,
    artifact_manifest_json TEXT NOT NULL DEFAULT '{}',
    special_tokens_json TEXT NOT NULL DEFAULT '[]',
    configuration_json TEXT NOT NULL DEFAULT '{}',
    metrics_summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    training_completed_at TEXT,
    activated_at TEXT,
    retired_at TEXT,
    FOREIGN KEY (tokenizer_family_id) REFERENCES tokenizer_families(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (training_job_id) REFERENCES tokenizer_training_jobs(id) ON DELETE SET NULL,
    UNIQUE(tokenizer_family_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tokenizer_one_active
ON tokenizer_versions(tokenizer_family_id) WHERE lifecycle_status = 'active';
CREATE TABLE IF NOT EXISTS tokenizer_training_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_version_id INTEGER NOT NULL,
    dataset_version_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validating','queued','running','completed','completed_with_warnings','failed','cancelled')),
    job_type TEXT NOT NULL CHECK (job_type IN ('corpus_build','dry_run','train','evaluate','full_pipeline')),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    hardware_profile TEXT NOT NULL DEFAULT 'cpu',
    corpus_record_count INTEGER NOT NULL DEFAULT 0 CHECK (corpus_record_count >= 0),
    corpus_line_count INTEGER NOT NULL DEFAULT 0 CHECK (corpus_line_count >= 0),
    corpus_character_count INTEGER NOT NULL DEFAULT 0 CHECK (corpus_character_count >= 0),
    progress REAL NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    current_stage TEXT NOT NULL DEFAULT 'draft',
    error_code TEXT,
    error_message TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS tokenizer_training_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    training_job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    stage TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (training_job_id) REFERENCES tokenizer_training_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tokenizer_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_version_id INTEGER NOT NULL,
    evaluation_name TEXT NOT NULL,
    evaluation_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','running','completed','completed_with_warnings','failed')),
    dataset_version_id INTEGER,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS tokenizer_evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_evaluation_id INTEGER NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('ta','en','tgl','mixed','overall')),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0 CHECK (sample_count >= 0),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_evaluation_id) REFERENCES tokenizer_evaluations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tokenizer_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_key TEXT NOT NULL UNIQUE CHECK (assignment_key IN ('core_model_training','chat_input','dataset_preview','default')),
    tokenizer_version_id INTEGER,
    fallback_tokenizer_version_id INTEGER,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE SET NULL,
    FOREIGN KEY (fallback_tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS tokenizer_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_version_id INTEGER NOT NULL,
    export_format TEXT NOT NULL CHECK (export_format IN ('sentencepiece_bundle','huggingface_tokenizer_files','manifest_only')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','exporting','completed','failed','cancelled')),
    safe_name TEXT NOT NULL UNIQUE,
    checksum_sha256 TEXT,
    artifact_manifest_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    error_code TEXT,
    error_message TEXT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_tokenizer_families_name ON tokenizer_families(name);
CREATE INDEX IF NOT EXISTS ix_tokenizer_versions_status ON tokenizer_versions(lifecycle_status);
CREATE INDEX IF NOT EXISTS ix_tokenizer_versions_dataset ON tokenizer_versions(dataset_version_id);
CREATE INDEX IF NOT EXISTS ix_tokenizer_jobs_status_created ON tokenizer_training_jobs(status,created_at);
CREATE INDEX IF NOT EXISTS ix_tokenizer_eval_version_language ON tokenizer_evaluation_results(tokenizer_evaluation_id,language);
CREATE INDEX IF NOT EXISTS ix_tokenizer_assignments_key ON tokenizer_assignments(assignment_key);
CREATE INDEX IF NOT EXISTS ix_tokenizer_versions_model_checksum ON tokenizer_versions(model_checksum_sha256);
CREATE INDEX IF NOT EXISTS ix_tokenizer_exports_checksum ON tokenizer_exports(checksum_sha256);
CREATE TRIGGER IF NOT EXISTS tokenizer_training_events_immutable_update BEFORE UPDATE ON tokenizer_training_events BEGIN SELECT RAISE(ABORT, 'tokenizer training events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS tokenizer_training_events_immutable_delete BEFORE DELETE ON tokenizer_training_events BEGIN SELECT RAISE(ABORT, 'tokenizer training events are immutable'); END;
"""

MIGRATION_008_NAME = "008_phase8_core_model_architecture"

PHASE8_SCHEMA = """
CREATE TABLE IF NOT EXISTS core_model_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    architecture_type TEXT NOT NULL DEFAULT 'brud_decoder_transformer' CHECK (architecture_type IN ('brud_decoder_transformer')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','inactive','archived')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS core_model_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    config_version TEXT NOT NULL,
    vocabulary_size INTEGER NOT NULL CHECK (vocabulary_size > 0),
    context_length INTEGER NOT NULL CHECK (context_length > 0),
    hidden_size INTEGER NOT NULL CHECK (hidden_size > 0),
    intermediate_size INTEGER NOT NULL CHECK (intermediate_size > 0),
    num_hidden_layers INTEGER NOT NULL CHECK (num_hidden_layers > 0),
    num_attention_heads INTEGER NOT NULL CHECK (num_attention_heads > 0),
    num_key_value_heads INTEGER NOT NULL CHECK (num_key_value_heads > 0),
    head_dimension INTEGER NOT NULL CHECK (head_dimension > 0),
    rope_theta REAL NOT NULL,
    rms_norm_epsilon REAL NOT NULL,
    attention_dropout REAL NOT NULL CHECK (attention_dropout BETWEEN 0 AND 1),
    residual_dropout REAL NOT NULL CHECK (residual_dropout BETWEEN 0 AND 1),
    embedding_dropout REAL NOT NULL CHECK (embedding_dropout BETWEEN 0 AND 1),
    initializer_range REAL NOT NULL,
    tie_word_embeddings INTEGER NOT NULL CHECK (tie_word_embeddings IN (0,1)),
    use_bias INTEGER NOT NULL CHECK (use_bias IN (0,1)),
    pad_token_id INTEGER NOT NULL,
    bos_token_id INTEGER NOT NULL,
    eos_token_id INTEGER NOT NULL,
    unk_token_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    parameter_count_estimate INTEGER NOT NULL CHECK (parameter_count_estimate > 0),
    memory_estimate_bytes INTEGER NOT NULL CHECK (memory_estimate_bytes > 0),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    config_checksum_sha256 TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validated','invalid','archived')),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    UNIQUE(name, config_version)
);
CREATE TABLE IF NOT EXISTS core_model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    core_model_family_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN ('draft','validating','initialized','architecture_verified','smoke_tested','staging','active','failed','retired','archived')),
    config_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    architecture_name TEXT NOT NULL,
    estimated_parameter_count INTEGER NOT NULL,
    actual_parameter_count INTEGER,
    estimated_inference_memory_bytes INTEGER NOT NULL,
    estimated_training_memory_bytes INTEGER NOT NULL,
    initialization_seed INTEGER NOT NULL,
    weights_checksum_sha256 TEXT,
    config_checksum_sha256 TEXT NOT NULL,
    architecture_summary_json TEXT NOT NULL DEFAULT '{}',
    metrics_summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    initialized_at TEXT,
    validated_at TEXT,
    activated_at TEXT,
    retired_at TEXT,
    FOREIGN KEY (core_model_family_id) REFERENCES core_model_families(id) ON DELETE RESTRICT,
    FOREIGN KEY (config_id) REFERENCES core_model_configs(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    UNIQUE(core_model_family_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_core_model_one_active
ON core_model_versions(core_model_family_id) WHERE lifecycle_status = 'active';
CREATE TABLE IF NOT EXISTS core_model_architecture_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    core_model_version_id INTEGER NOT NULL,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pass','warning','fail')),
    metric_value REAL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS core_model_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    core_model_version_id INTEGER NOT NULL,
    checkpoint_type TEXT NOT NULL CHECK (checkpoint_type IN ('initialization','smoke_test','training','manual')),
    status TEXT NOT NULL DEFAULT 'creating' CHECK (status IN ('creating','completed','verified','failed','corrupt','archived')),
    step INTEGER NOT NULL DEFAULT 0 CHECK (step >= 0),
    safe_name TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (file_size_bytes >= 0),
    checksum_sha256 TEXT,
    manifest_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_at TEXT,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS core_model_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    core_model_version_id INTEGER,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS core_model_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_key TEXT NOT NULL UNIQUE CHECK (assignment_key IN ('architecture_default','smoke_training_default','future_pretraining_base')),
    core_model_version_id INTEGER,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_core_model_families_name ON core_model_families(name);
CREATE INDEX IF NOT EXISTS ix_core_model_versions_status ON core_model_versions(lifecycle_status);
CREATE INDEX IF NOT EXISTS ix_core_model_versions_tokenizer ON core_model_versions(tokenizer_version_id);
CREATE INDEX IF NOT EXISTS ix_core_model_configs_checksum ON core_model_configs(config_checksum_sha256);
CREATE INDEX IF NOT EXISTS ix_core_model_checkpoints_checksum ON core_model_checkpoints(checksum_sha256);
CREATE INDEX IF NOT EXISTS ix_core_model_assignments_key ON core_model_assignments(assignment_key);
CREATE INDEX IF NOT EXISTS ix_core_model_versions_created ON core_model_versions(created_at);
CREATE TRIGGER IF NOT EXISTS core_model_events_immutable_update BEFORE UPDATE ON core_model_events BEGIN SELECT RAISE(ABORT, 'core model events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS core_model_events_immutable_delete BEFORE DELETE ON core_model_events BEGIN SELECT RAISE(ABORT, 'core model events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS core_model_checks_immutable_update BEFORE UPDATE ON core_model_architecture_checks BEGIN SELECT RAISE(ABORT, 'core model checks are immutable'); END;
CREATE TRIGGER IF NOT EXISTS core_model_checks_immutable_delete BEFORE DELETE ON core_model_architecture_checks BEGIN SELECT RAISE(ABORT, 'core model checks are immutable'); END;
"""

MIGRATION_009_NAME = "009_phase9_core_pretraining"

PHASE9_SCHEMA = """
CREATE TABLE IF NOT EXISTS pretraining_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validating','queued','running','pause_requested','paused','resume_requested','completed','completed_with_warnings','failed','cancel_requested','cancelled')),
    dataset_version_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    core_model_version_id INTEGER NOT NULL,
    source_checkpoint_id INTEGER,
    job_mode TEXT NOT NULL CHECK (job_mode IN ('smoke_pretraining','bounded_pretraining','resume_pretraining')),
    configuration_json TEXT NOT NULL,
    config_checksum_sha256 TEXT NOT NULL,
    initialization_seed INTEGER NOT NULL,
    sampling_seed INTEGER NOT NULL,
    device TEXT NOT NULL DEFAULT 'cpu',
    dtype TEXT NOT NULL DEFAULT 'float32',
    optimizer_name TEXT NOT NULL DEFAULT 'adamw',
    scheduler_name TEXT NOT NULL DEFAULT 'constant',
    total_steps INTEGER NOT NULL CHECK (total_steps > 0),
    completed_steps INTEGER NOT NULL DEFAULT 0 CHECK (completed_steps >= 0),
    total_tokens_target INTEGER NOT NULL DEFAULT 0 CHECK (total_tokens_target >= 0),
    processed_tokens INTEGER NOT NULL DEFAULT 0 CHECK (processed_tokens >= 0),
    gradient_accumulation_steps INTEGER NOT NULL DEFAULT 1 CHECK (gradient_accumulation_steps > 0),
    current_epoch_fraction REAL NOT NULL DEFAULT 0 CHECK (current_epoch_fraction BETWEEN 0 AND 1),
    latest_training_loss REAL,
    latest_validation_loss REAL,
    best_validation_loss REAL,
    learning_rate REAL,
    tokens_per_second REAL,
    estimated_remaining_steps INTEGER,
    progress REAL NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    worker_id TEXT,
    lease_expires_at TEXT,
    pause_requested INTEGER NOT NULL DEFAULT 0 CHECK (pause_requested IN (0,1)),
    cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
    error_code TEXT,
    error_message TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    queued_at TEXT,
    started_at TEXT,
    paused_at TEXT,
    resumed_at TEXT,
    completed_at TEXT,
    failed_at TEXT,
    cancelled_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_checkpoint_id) REFERENCES core_model_checkpoints(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS pretraining_job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pretraining_job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS pretraining_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    step INTEGER NOT NULL,
    processed_tokens INTEGER NOT NULL,
    epoch_fraction REAL NOT NULL DEFAULT 0,
    training_loss REAL,
    validation_loss REAL,
    learning_rate REAL NOT NULL,
    gradient_norm REAL,
    tokens_per_second REAL,
    step_duration_ms INTEGER NOT NULL DEFAULT 0,
    cpu_percent REAL,
    process_memory_bytes INTEGER,
    system_available_memory_bytes INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE,
    UNIQUE(pretraining_job_id, step)
);
CREATE TABLE IF NOT EXISTS pretraining_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    core_model_version_id INTEGER NOT NULL,
    checkpoint_kind TEXT NOT NULL CHECK (checkpoint_kind IN ('periodic','best_validation','pause','final','recovery')),
    status TEXT NOT NULL DEFAULT 'creating' CHECK (status IN ('creating','completed','verified','failed','corrupt','archived')),
    step INTEGER NOT NULL,
    processed_tokens INTEGER NOT NULL,
    safe_name TEXT NOT NULL UNIQUE,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    manifest_json TEXT NOT NULL DEFAULT '{}',
    model_checksum_sha256 TEXT NOT NULL,
    optimizer_checksum_sha256 TEXT,
    scheduler_checksum_sha256 TEXT,
    trainer_state_checksum_sha256 TEXT NOT NULL,
    combined_checksum_sha256 TEXT NOT NULL,
    training_loss REAL,
    validation_loss REAL,
    is_best INTEGER NOT NULL DEFAULT 0 CHECK (is_best IN (0,1)),
    is_latest INTEGER NOT NULL DEFAULT 0 CHECK (is_latest IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_at TEXT,
    archived_at TEXT,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS pretraining_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    evaluation_type TEXT NOT NULL CHECK (evaluation_type IN ('validation_loss','checkpoint_comparison','resume_consistency')),
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('draft','running','completed','failed')),
    checkpoint_public_id TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS pretraining_evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_evaluation_id INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_evaluation_id) REFERENCES pretraining_evaluations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_worker_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER,
    status TEXT NOT NULL DEFAULT 'idle',
    lease_expires_at TEXT,
    heartbeat_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_pretraining_jobs_status ON pretraining_jobs(status,created_at);
CREATE INDEX IF NOT EXISTS ix_pretraining_jobs_refs ON pretraining_jobs(dataset_version_id,tokenizer_version_id,core_model_version_id);
CREATE INDEX IF NOT EXISTS ix_pretraining_metrics_job_step ON pretraining_metrics(pretraining_job_id,step);
CREATE INDEX IF NOT EXISTS ix_pretraining_checkpoints_job ON pretraining_checkpoints(pretraining_job_id,step);
CREATE INDEX IF NOT EXISTS ix_pretraining_checkpoints_checksum ON pretraining_checkpoints(combined_checksum_sha256);
CREATE INDEX IF NOT EXISTS ix_pretraining_evaluations_job ON pretraining_evaluations(pretraining_job_id);
CREATE INDEX IF NOT EXISTS ix_training_worker_leases_job ON training_worker_leases(pretraining_job_id);
CREATE TRIGGER IF NOT EXISTS pretraining_events_immutable_update BEFORE UPDATE ON pretraining_job_events BEGIN SELECT RAISE(ABORT, 'pretraining events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS pretraining_events_immutable_delete BEFORE DELETE ON pretraining_job_events BEGIN SELECT RAISE(ABORT, 'pretraining events are immutable'); END;
"""

MIGRATION_010_NAME = "010_phase10_training_reliability"

PHASE10_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "pretraining_jobs": [
        ("lease_generation", "INTEGER NOT NULL DEFAULT 0"),
        ("recovery_required", "INTEGER NOT NULL DEFAULT 0"),
        ("latest_stream_checksum_sha256", "TEXT"),
        ("latest_coverage_public_id", "TEXT"),
        ("quality_readiness_status", "TEXT NOT NULL DEFAULT 'not_assessed'"),
        ("best_checkpoint_public_id", "TEXT"),
    ],
    "training_worker_leases": [
        ("lease_generation", "INTEGER NOT NULL DEFAULT 0"),
        ("owner_public_id", "TEXT"),
        ("released_at", "TEXT"),
        ("release_reason", "TEXT"),
    ],
}

PHASE10_SCHEMA = """
CREATE TABLE IF NOT EXISTS worker_heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    worker_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'starting' CHECK (status IN ('starting','idle','claiming','running','pausing','recovering','stopping','stopped','failed')),
    current_job_public_id TEXT,
    lease_generation INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lease_expires_at TEXT,
    shutdown_requested INTEGER NOT NULL DEFAULT 0 CHECK (shutdown_requested IN (0,1)),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS training_recovery_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    recovery_type TEXT NOT NULL CHECK (recovery_type IN ('pause_resume','manual_resume','stale_lease','worker_crash','checkpoint_recovery')),
    status TEXT NOT NULL CHECK (status IN ('validating','recovering','completed','completed_with_warnings','failed','cancelled')),
    source_worker_id TEXT,
    recovering_worker_id TEXT NOT NULL,
    source_checkpoint_public_id TEXT,
    previous_lease_generation INTEGER NOT NULL,
    new_lease_generation INTEGER NOT NULL,
    recovered_step INTEGER,
    recovered_tokens INTEGER,
    validation_summary_json TEXT NOT NULL DEFAULT '{}',
    error_code TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_dataset_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('train','valid')),
    total_records INTEGER NOT NULL DEFAULT 0,
    eligible_records INTEGER NOT NULL DEFAULT 0,
    encoded_records INTEGER NOT NULL DEFAULT 0,
    excluded_records INTEGER NOT NULL DEFAULT 0,
    zero_token_records INTEGER NOT NULL DEFAULT 0,
    oversized_records INTEGER NOT NULL DEFAULT 0,
    split_records INTEGER NOT NULL DEFAULT 0,
    dropped_records INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    usable_tokens INTEGER NOT NULL DEFAULT 0,
    padding_tokens INTEGER NOT NULL DEFAULT 0,
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    record_type_distribution_json TEXT NOT NULL DEFAULT '{}',
    source_type_distribution_json TEXT NOT NULL DEFAULT '{}',
    exclusion_reasons_json TEXT NOT NULL DEFAULT '{}',
    coverage_ratio REAL NOT NULL DEFAULT 0 CHECK (coverage_ratio BETWEEN 0 AND 1),
    stream_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_stream_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('train','valid')),
    dataset_version_public_id TEXT NOT NULL,
    dataset_checksum_sha256 TEXT NOT NULL,
    tokenizer_version_public_id TEXT NOT NULL,
    tokenizer_checksum_sha256 TEXT NOT NULL,
    sequence_length INTEGER NOT NULL,
    packing_policy TEXT NOT NULL,
    partial_block_policy TEXT NOT NULL,
    eos_policy TEXT NOT NULL,
    overlength_policy TEXT NOT NULL,
    shuffle INTEGER NOT NULL DEFAULT 0 CHECK (shuffle IN (0,1)),
    seed INTEGER NOT NULL,
    eligible_records INTEGER NOT NULL,
    encoded_records INTEGER NOT NULL,
    excluded_records INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    usable_tokens INTEGER NOT NULL,
    block_count INTEGER NOT NULL,
    stream_checksum_sha256 TEXT NOT NULL,
    manifest_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_run_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    initial_step INTEGER NOT NULL DEFAULT 0,
    final_step INTEGER NOT NULL DEFAULT 0,
    initial_training_loss REAL,
    final_training_loss REAL,
    best_training_loss REAL,
    initial_validation_loss REAL,
    final_validation_loss REAL,
    best_validation_loss REAL,
    initial_perplexity REAL,
    final_perplexity REAL,
    processed_tokens INTEGER NOT NULL DEFAULT 0,
    optimizer_steps INTEGER NOT NULL DEFAULT 0,
    elapsed_seconds REAL NOT NULL DEFAULT 0,
    average_tokens_per_second REAL,
    peak_process_memory_bytes INTEGER,
    checkpoint_count INTEGER NOT NULL DEFAULT 0,
    pause_count INTEGER NOT NULL DEFAULT 0,
    resume_count INTEGER NOT NULL DEFAULT 0,
    recovery_count INTEGER NOT NULL DEFAULT 0,
    non_finite_event_count INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_quality_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    assessment_version TEXT NOT NULL,
    overall_score REAL NOT NULL CHECK (overall_score BETWEEN 0 AND 1),
    dimension_scores_json TEXT NOT NULL DEFAULT '{}',
    readiness_status TEXT NOT NULL CHECK (readiness_status IN ('ready_for_staging','warning','blocked','not_assessed')),
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    training_quality_assessment_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL CHECK (issue_code IN (
        'dataset_checksum_mismatch','tokenizer_checksum_mismatch','model_config_mismatch',
        'stream_checksum_mismatch','coverage_too_low','too_many_excluded_records',
        'insufficient_training_tokens','loss_not_improving','loss_divergence',
        'non_finite_loss','non_finite_gradient','validation_loss_missing',
        'validation_loss_worsening','train_validation_gap_high','too_few_validation_tokens',
        'checkpoint_corrupt','resume_inconsistent','worker_lease_conflict',
        'stale_worker_write','worker_recovery_failed','memory_limit_exceeded',
        'disk_limit_exceeded','throughput_unusually_low'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','blocking')),
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (training_quality_assessment_id) REFERENCES training_quality_assessments(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS training_checkpoint_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    left_checkpoint_public_id TEXT NOT NULL,
    right_checkpoint_public_id TEXT NOT NULL,
    compatibility TEXT NOT NULL CHECK (compatibility IN ('compatible','partially_compatible','incompatible')),
    comparison_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS training_run_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    left_job_public_id TEXT NOT NULL,
    right_job_public_id TEXT NOT NULL,
    compatibility TEXT NOT NULL CHECK (compatibility IN ('compatible','partially_compatible','incompatible')),
    comparison_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS checkpoint_retention_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_job_id INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('preview','apply')),
    checkpoint_public_id TEXT NOT NULL,
    classification TEXT NOT NULL CHECK (classification IN ('protected','eligible','archived')),
    protection_reason TEXT,
    dry_run INTEGER NOT NULL DEFAULT 0 CHECK (dry_run IN (0,1)),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_worker_heartbeats_status ON worker_heartbeats(status,last_heartbeat_at);
CREATE INDEX IF NOT EXISTS ix_worker_heartbeats_job ON worker_heartbeats(current_job_public_id);
CREATE INDEX IF NOT EXISTS ix_training_recovery_attempts_job ON training_recovery_attempts(pretraining_job_id);
CREATE INDEX IF NOT EXISTS ix_training_recovery_attempts_status ON training_recovery_attempts(status,completed_at);
CREATE INDEX IF NOT EXISTS ix_training_dataset_coverage_job ON training_dataset_coverage(pretraining_job_id,split);
CREATE INDEX IF NOT EXISTS ix_training_stream_manifests_job ON training_stream_manifests(pretraining_job_id,split);
CREATE INDEX IF NOT EXISTS ix_training_run_summaries_job ON training_run_summaries(pretraining_job_id);
CREATE INDEX IF NOT EXISTS ix_training_quality_assessments_job ON training_quality_assessments(pretraining_job_id);
CREATE INDEX IF NOT EXISTS ix_training_quality_issues_assessment ON training_quality_issues(training_quality_assessment_id);
CREATE INDEX IF NOT EXISTS ix_training_quality_issues_severity ON training_quality_issues(severity);
CREATE INDEX IF NOT EXISTS ix_checkpoint_retention_actions_job ON checkpoint_retention_actions(pretraining_job_id);
CREATE TRIGGER IF NOT EXISTS training_recovery_attempts_immutable_update BEFORE UPDATE ON training_recovery_attempts BEGIN SELECT RAISE(ABORT, 'recovery attempts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_recovery_attempts_immutable_delete BEFORE DELETE ON training_recovery_attempts BEGIN SELECT RAISE(ABORT, 'recovery attempts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_dataset_coverage_immutable_update BEFORE UPDATE ON training_dataset_coverage BEGIN SELECT RAISE(ABORT, 'dataset coverage records are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_dataset_coverage_immutable_delete BEFORE DELETE ON training_dataset_coverage BEGIN SELECT RAISE(ABORT, 'dataset coverage records are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_stream_manifests_immutable_update BEFORE UPDATE ON training_stream_manifests BEGIN SELECT RAISE(ABORT, 'stream manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_stream_manifests_immutable_delete BEFORE DELETE ON training_stream_manifests BEGIN SELECT RAISE(ABORT, 'stream manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_run_summaries_immutable_update BEFORE UPDATE ON training_run_summaries BEGIN SELECT RAISE(ABORT, 'run summaries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_run_summaries_immutable_delete BEFORE DELETE ON training_run_summaries BEGIN SELECT RAISE(ABORT, 'run summaries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_quality_assessments_immutable_update BEFORE UPDATE ON training_quality_assessments BEGIN SELECT RAISE(ABORT, 'quality assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_quality_assessments_immutable_delete BEFORE DELETE ON training_quality_assessments BEGIN SELECT RAISE(ABORT, 'quality assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_quality_issues_immutable_update BEFORE UPDATE ON training_quality_issues BEGIN SELECT RAISE(ABORT, 'quality issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_quality_issues_immutable_delete BEFORE DELETE ON training_quality_issues BEGIN SELECT RAISE(ABORT, 'quality issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_checkpoint_comparisons_immutable_update BEFORE UPDATE ON training_checkpoint_comparisons BEGIN SELECT RAISE(ABORT, 'checkpoint comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_checkpoint_comparisons_immutable_delete BEFORE DELETE ON training_checkpoint_comparisons BEGIN SELECT RAISE(ABORT, 'checkpoint comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_run_comparisons_immutable_update BEFORE UPDATE ON training_run_comparisons BEGIN SELECT RAISE(ABORT, 'run comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_run_comparisons_immutable_delete BEFORE DELETE ON training_run_comparisons BEGIN SELECT RAISE(ABORT, 'run comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS checkpoint_retention_actions_immutable_update BEFORE UPDATE ON checkpoint_retention_actions BEGIN SELECT RAISE(ABORT, 'retention actions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS checkpoint_retention_actions_immutable_delete BEFORE DELETE ON checkpoint_retention_actions BEGIN SELECT RAISE(ABORT, 'retention actions are append-only'); END;
"""

MIGRATION_011_NAME = "011_phase11_base_pretraining_evaluation"

PHASE11_SCHEMA = """
CREATE TABLE IF NOT EXISTS base_training_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','profiled','tokenizer_evaluated','ready','running','completed','archived')),
    dataset_version_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER,
    core_model_version_id INTEGER,
    initialization_seed INTEGER NOT NULL DEFAULT 42,
    sampling_seed INTEGER NOT NULL DEFAULT 42,
    tokenizer_decision TEXT NOT NULL DEFAULT 'not_evaluated' CHECK (tokenizer_decision IN ('not_evaluated','reuse_existing_tokenizer','train_new_tokenizer_version','blocked_tokenizer_unsuitable')),
    tokenizer_evaluation_json TEXT NOT NULL DEFAULT '{}',
    training_configuration_json TEXT NOT NULL DEFAULT '{}',
    evaluation_configuration_json TEXT NOT NULL DEFAULT '{}',
    resource_limits_json TEXT NOT NULL DEFAULT '{}',
    latest_profile_public_id TEXT,
    latest_candidate_selection_public_id TEXT,
    latest_manifest_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS base_training_experiment_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    base_training_experiment_id INTEGER NOT NULL,
    pretraining_job_id INTEGER,
    run_label TEXT NOT NULL,
    run_index INTEGER NOT NULL CHECK (run_index > 0),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','queued','running','completed','completed_with_warnings','failed','cancelled')),
    config_diff_json TEXT NOT NULL DEFAULT '{}',
    test_evaluated INTEGER NOT NULL DEFAULT 0 CHECK (test_evaluated IN (0,1)),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (base_training_experiment_id) REFERENCES base_training_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE SET NULL,
    UNIQUE(base_training_experiment_id, run_index)
);
CREATE TABLE IF NOT EXISTS base_training_dataset_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    base_training_experiment_id INTEGER NOT NULL,
    dataset_version_id INTEGER NOT NULL,
    total_records INTEGER NOT NULL DEFAULT 0,
    approved_records INTEGER NOT NULL DEFAULT 0,
    train_count INTEGER NOT NULL DEFAULT 0,
    validation_count INTEGER NOT NULL DEFAULT 0,
    test_count INTEGER NOT NULL DEFAULT 0,
    total_characters INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    unique_token_count INTEGER NOT NULL DEFAULT 0,
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    record_type_distribution_json TEXT NOT NULL DEFAULT '{}',
    source_distribution_json TEXT NOT NULL DEFAULT '{}',
    licence_distribution_json TEXT NOT NULL DEFAULT '{}',
    average_record_length REAL NOT NULL DEFAULT 0,
    median_record_length REAL NOT NULL DEFAULT 0,
    maximum_record_length INTEGER NOT NULL DEFAULT 0,
    duplicate_rate REAL NOT NULL DEFAULT 0,
    near_duplicate_rate REAL NOT NULL DEFAULT 0,
    zero_token_rate REAL NOT NULL DEFAULT 0,
    oversized_record_rate REAL NOT NULL DEFAULT 0,
    validation_representativeness_json TEXT NOT NULL DEFAULT '{}',
    test_representativeness_json TEXT NOT NULL DEFAULT '{}',
    tamil_script_coverage REAL NOT NULL DEFAULT 0,
    english_latin_coverage REAL NOT NULL DEFAULT 0,
    tanglish_coverage REAL NOT NULL DEFAULT 0,
    mixed_script_coverage REAL NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    data_sufficiency_status TEXT NOT NULL DEFAULT 'insufficient' CHECK (data_sufficiency_status IN ('sufficient','limited_experiment','insufficient')),
    profile_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (base_training_experiment_id) REFERENCES base_training_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS base_training_language_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_run_id INTEGER NOT NULL,
    checkpoint_public_id TEXT,
    split TEXT NOT NULL CHECK (split IN ('train','valid','test')),
    language TEXT NOT NULL CHECK (language IN ('ta','en','tgl','mixed','overall')),
    evaluated_records INTEGER NOT NULL DEFAULT 0,
    evaluated_tokens INTEGER NOT NULL DEFAULT 0,
    loss REAL,
    perplexity REAL,
    unknown_token_rate REAL NOT NULL DEFAULT 0,
    average_tokens_per_record REAL NOT NULL DEFAULT 0,
    maximum_tokens_per_record INTEGER NOT NULL DEFAULT 0,
    long_sequence_rate REAL NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_run_id) REFERENCES base_training_experiment_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS base_training_learning_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_run_id INTEGER NOT NULL,
    check_code TEXT NOT NULL CHECK (check_code IN (
        'training_loss_improves','validation_loss_finite','test_loss_finite',
        'no_non_finite_gradients','checkpoint_integrity','dataset_stream_integrity',
        'language_metrics_complete','generalization_gap_bounded','memorization_risk_bounded',
        'tokenizer_coverage_adequate','resource_limits_respected'
    )),
    status TEXT NOT NULL CHECK (status IN ('pass','warning','fail')),
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_run_id) REFERENCES base_training_experiment_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS base_training_candidate_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    base_training_experiment_id INTEGER NOT NULL,
    selected_run_id INTEGER,
    selected_checkpoint_public_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('selected_base_candidate','selected_with_warnings','rejected')),
    generalization_result TEXT NOT NULL CHECK (generalization_result IN ('optimization_success_only','limited_generalization_evidence','not_assessed')),
    memorization_warning_count INTEGER NOT NULL DEFAULT 0,
    rationale_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (base_training_experiment_id) REFERENCES base_training_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (selected_run_id) REFERENCES base_training_experiment_runs(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS base_training_reproducibility_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    base_training_experiment_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (base_training_experiment_id) REFERENCES base_training_experiments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_base_training_experiments_status ON base_training_experiments(status,created_at);
CREATE INDEX IF NOT EXISTS ix_base_training_experiment_runs_experiment ON base_training_experiment_runs(base_training_experiment_id,run_index);
CREATE INDEX IF NOT EXISTS ix_base_training_experiment_runs_job ON base_training_experiment_runs(pretraining_job_id);
CREATE INDEX IF NOT EXISTS ix_base_training_dataset_profiles_experiment ON base_training_dataset_profiles(base_training_experiment_id);
CREATE INDEX IF NOT EXISTS ix_base_training_language_metrics_run ON base_training_language_metrics(experiment_run_id,split,language);
CREATE INDEX IF NOT EXISTS ix_base_training_learning_checks_run ON base_training_learning_checks(experiment_run_id,status);
CREATE INDEX IF NOT EXISTS ix_base_training_candidate_selections_experiment ON base_training_candidate_selections(base_training_experiment_id);
CREATE INDEX IF NOT EXISTS ix_base_training_reproducibility_manifests_experiment ON base_training_reproducibility_manifests(base_training_experiment_id);
CREATE TRIGGER IF NOT EXISTS base_training_dataset_profiles_immutable_update BEFORE UPDATE ON base_training_dataset_profiles BEGIN SELECT RAISE(ABORT, 'dataset profiles are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_dataset_profiles_immutable_delete BEFORE DELETE ON base_training_dataset_profiles BEGIN SELECT RAISE(ABORT, 'dataset profiles are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_language_metrics_immutable_update BEFORE UPDATE ON base_training_language_metrics BEGIN SELECT RAISE(ABORT, 'language metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_language_metrics_immutable_delete BEFORE DELETE ON base_training_language_metrics BEGIN SELECT RAISE(ABORT, 'language metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_learning_checks_immutable_update BEFORE UPDATE ON base_training_learning_checks BEGIN SELECT RAISE(ABORT, 'learning checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_learning_checks_immutable_delete BEFORE DELETE ON base_training_learning_checks BEGIN SELECT RAISE(ABORT, 'learning checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_candidate_selections_immutable_update BEFORE UPDATE ON base_training_candidate_selections BEGIN SELECT RAISE(ABORT, 'candidate selections are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_candidate_selections_immutable_delete BEFORE DELETE ON base_training_candidate_selections BEGIN SELECT RAISE(ABORT, 'candidate selections are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_reproducibility_manifests_immutable_update BEFORE UPDATE ON base_training_reproducibility_manifests BEGIN SELECT RAISE(ABORT, 'reproducibility manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_training_reproducibility_manifests_immutable_delete BEFORE DELETE ON base_training_reproducibility_manifests BEGIN SELECT RAISE(ABORT, 'reproducibility manifests are append-only'); END;
"""

MIGRATION_012_NAME = "012_phase12_instruction_tuning"

PHASE12_SCHEMA = """
CREATE TABLE IF NOT EXISTS instruction_tuning_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','profiled','template_validated','ready','running','completed','completed_with_warnings','failed','archived')),
    base_core_model_version_id INTEGER NOT NULL,
    source_base_checkpoint_id INTEGER NOT NULL,
    dataset_version_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    instruction_template_id INTEGER,
    initialization_seed INTEGER NOT NULL DEFAULT 42,
    sampling_seed INTEGER NOT NULL DEFAULT 42,
    training_configuration_json TEXT NOT NULL DEFAULT '{}',
    evaluation_configuration_json TEXT NOT NULL DEFAULT '{}',
    resource_limits_json TEXT NOT NULL DEFAULT '{}',
    latest_profile_public_id TEXT,
    latest_candidate_public_id TEXT,
    latest_manifest_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    archived_at TEXT,
    FOREIGN KEY (base_core_model_version_id) REFERENCES core_model_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_base_checkpoint_id) REFERENCES pretraining_checkpoints(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (instruction_template_id) REFERENCES instruction_format_templates(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS instruction_tuning_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_experiment_id INTEGER NOT NULL,
    pretraining_job_id INTEGER,
    instruction_template_id INTEGER,
    run_label TEXT NOT NULL,
    run_index INTEGER NOT NULL CHECK (run_index > 0),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','queued','running','completed','completed_with_warnings','failed','cancelled')),
    config_diff_json TEXT NOT NULL DEFAULT '{}',
    truncation_policy TEXT NOT NULL DEFAULT 'truncate_prompt_first' CHECK (truncation_policy IN ('reject','truncate_prompt_first','truncate_response_tail')),
    input_stream_checksum_sha256 TEXT,
    label_stream_checksum_sha256 TEXT,
    assistant_target_tokens INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    ignored_tokens INTEGER NOT NULL DEFAULT 0,
    processed_examples INTEGER NOT NULL DEFAULT 0,
    test_evaluated INTEGER NOT NULL DEFAULT 0 CHECK (test_evaluated IN (0,1)),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (instruction_tuning_experiment_id) REFERENCES instruction_tuning_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (instruction_template_id) REFERENCES instruction_format_templates(id) ON DELETE SET NULL,
    UNIQUE(instruction_tuning_experiment_id, run_index)
);
CREATE TABLE IF NOT EXISTS instruction_format_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    template_json TEXT NOT NULL,
    required_special_tokens_json TEXT NOT NULL DEFAULT '[]',
    special_token_validation_json TEXT NOT NULL DEFAULT '{}',
    is_valid INTEGER NOT NULL DEFAULT 0 CHECK (is_valid IN (0,1)),
    template_checksum_sha256 TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    UNIQUE(name, version)
);
CREATE TABLE IF NOT EXISTS instruction_dataset_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_experiment_id INTEGER NOT NULL,
    dataset_version_id INTEGER NOT NULL,
    total_records INTEGER NOT NULL DEFAULT 0,
    eligible_records INTEGER NOT NULL DEFAULT 0,
    invalid_records INTEGER NOT NULL DEFAULT 0,
    excluded_records INTEGER NOT NULL DEFAULT 0,
    train_count INTEGER NOT NULL DEFAULT 0,
    validation_count INTEGER NOT NULL DEFAULT 0,
    test_count INTEGER NOT NULL DEFAULT 0,
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    record_type_distribution_json TEXT NOT NULL DEFAULT '{}',
    source_distribution_json TEXT NOT NULL DEFAULT '{}',
    licence_distribution_json TEXT NOT NULL DEFAULT '{}',
    system_prompt_count INTEGER NOT NULL DEFAULT 0,
    input_field_count INTEGER NOT NULL DEFAULT 0,
    synthesized_flat_chat_count INTEGER NOT NULL DEFAULT 0,
    average_prompt_tokens REAL NOT NULL DEFAULT 0,
    average_response_tokens REAL NOT NULL DEFAULT 0,
    maximum_prompt_tokens INTEGER NOT NULL DEFAULT 0,
    maximum_response_tokens INTEGER NOT NULL DEFAULT 0,
    empty_response_count INTEGER NOT NULL DEFAULT 0,
    duplicate_prompt_count INTEGER NOT NULL DEFAULT 0,
    duplicate_response_count INTEGER NOT NULL DEFAULT 0,
    exact_prompt_response_duplicate_count INTEGER NOT NULL DEFAULT 0,
    response_language_mismatch_count INTEGER NOT NULL DEFAULT 0,
    special_token_collision_count INTEGER NOT NULL DEFAULT 0,
    truncation_risk_count INTEGER NOT NULL DEFAULT 0,
    maskable_assistant_token_count INTEGER NOT NULL DEFAULT 0,
    exclusion_reasons_json TEXT NOT NULL DEFAULT '{}',
    input_stream_checksum_sha256 TEXT NOT NULL,
    label_stream_checksum_sha256 TEXT NOT NULL,
    data_sufficiency_status TEXT NOT NULL DEFAULT 'insufficient' CHECK (data_sufficiency_status IN ('sufficient','limited_instruction_experiment','insufficient')),
    profile_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instruction_tuning_experiment_id) REFERENCES instruction_tuning_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS instruction_tuning_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_run_id INTEGER NOT NULL,
    step INTEGER NOT NULL,
    examples_processed INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    target_tokens INTEGER NOT NULL DEFAULT 0,
    ignored_tokens INTEGER NOT NULL DEFAULT 0,
    training_loss REAL,
    validation_response_loss REAL,
    learning_rate REAL NOT NULL,
    gradient_norm REAL,
    tokens_per_second REAL,
    step_duration_ms INTEGER NOT NULL DEFAULT 0,
    process_memory_bytes INTEGER,
    system_available_memory_bytes INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instruction_tuning_run_id) REFERENCES instruction_tuning_runs(id) ON DELETE CASCADE,
    UNIQUE(instruction_tuning_run_id, step)
);
CREATE TABLE IF NOT EXISTS instruction_tuning_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_run_id INTEGER NOT NULL,
    evaluation_type TEXT NOT NULL CHECK (evaluation_type IN ('validation_response_loss','test_response_loss','language_compliance','leakage_check','memorization_check','bounded_generation_sample')),
    split TEXT CHECK (split IS NULL OR split IN ('validation','test')),
    checkpoint_public_id TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (instruction_tuning_run_id) REFERENCES instruction_tuning_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS instruction_tuning_evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_evaluation_id INTEGER NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('ta','en','tgl','mixed','overall')),
    metric_name TEXT NOT NULL,
    metric_value REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instruction_tuning_evaluation_id) REFERENCES instruction_tuning_evaluations(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS instruction_learning_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_run_id INTEGER NOT NULL,
    check_code TEXT NOT NULL CHECK (check_code IN (
        'response_only_masking_verified','training_loss_improves','validation_response_loss_finite',
        'language_metrics_complete','instruction_format_compliance','role_token_leakage_bounded',
        'prompt_leakage_bounded','repetition_bounded','memorization_risk_bounded',
        'checkpoint_integrity','base_model_lineage_complete','resource_limits_respected'
    )),
    status TEXT NOT NULL CHECK (status IN ('pass','warning','fail')),
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instruction_tuning_run_id) REFERENCES instruction_tuning_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS instruction_tuning_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_experiment_id INTEGER NOT NULL,
    selected_run_id INTEGER,
    selected_checkpoint_public_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('instruction_tuned_candidate','instruction_tuned_with_warnings','rejected')),
    role_leakage_result TEXT NOT NULL DEFAULT 'not_assessed',
    memorization_warning_count INTEGER NOT NULL DEFAULT 0,
    base_checkpoint_checksum_before TEXT,
    base_checkpoint_checksum_after TEXT,
    rationale_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instruction_tuning_experiment_id) REFERENCES instruction_tuning_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (selected_run_id) REFERENCES instruction_tuning_runs(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS instruction_reproducibility_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    instruction_tuning_experiment_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instruction_tuning_experiment_id) REFERENCES instruction_tuning_experiments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_instruction_tuning_experiments_status ON instruction_tuning_experiments(status,created_at);
CREATE INDEX IF NOT EXISTS ix_instruction_tuning_runs_experiment ON instruction_tuning_runs(instruction_tuning_experiment_id,run_index);
CREATE INDEX IF NOT EXISTS ix_instruction_tuning_runs_job ON instruction_tuning_runs(pretraining_job_id);
CREATE INDEX IF NOT EXISTS ix_instruction_format_templates_tokenizer ON instruction_format_templates(tokenizer_version_id);
CREATE INDEX IF NOT EXISTS ix_instruction_dataset_profiles_experiment ON instruction_dataset_profiles(instruction_tuning_experiment_id);
CREATE INDEX IF NOT EXISTS ix_instruction_tuning_metrics_run ON instruction_tuning_metrics(instruction_tuning_run_id,step);
CREATE INDEX IF NOT EXISTS ix_instruction_tuning_evaluations_run ON instruction_tuning_evaluations(instruction_tuning_run_id,evaluation_type);
CREATE INDEX IF NOT EXISTS ix_instruction_tuning_evaluation_results_eval ON instruction_tuning_evaluation_results(instruction_tuning_evaluation_id,language);
CREATE INDEX IF NOT EXISTS ix_instruction_learning_checks_run ON instruction_learning_checks(instruction_tuning_run_id,status);
CREATE INDEX IF NOT EXISTS ix_instruction_tuning_candidates_experiment ON instruction_tuning_candidates(instruction_tuning_experiment_id);
CREATE INDEX IF NOT EXISTS ix_instruction_reproducibility_manifests_experiment ON instruction_reproducibility_manifests(instruction_tuning_experiment_id);
CREATE TRIGGER IF NOT EXISTS instruction_format_templates_immutable_update BEFORE UPDATE ON instruction_format_templates BEGIN SELECT RAISE(ABORT, 'instruction format templates are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_format_templates_immutable_delete BEFORE DELETE ON instruction_format_templates BEGIN SELECT RAISE(ABORT, 'instruction format templates are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_dataset_profiles_immutable_update BEFORE UPDATE ON instruction_dataset_profiles BEGIN SELECT RAISE(ABORT, 'instruction dataset profiles are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_dataset_profiles_immutable_delete BEFORE DELETE ON instruction_dataset_profiles BEGIN SELECT RAISE(ABORT, 'instruction dataset profiles are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_metrics_immutable_update BEFORE UPDATE ON instruction_tuning_metrics BEGIN SELECT RAISE(ABORT, 'instruction tuning metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_metrics_immutable_delete BEFORE DELETE ON instruction_tuning_metrics BEGIN SELECT RAISE(ABORT, 'instruction tuning metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_evaluations_immutable_update BEFORE UPDATE ON instruction_tuning_evaluations BEGIN SELECT RAISE(ABORT, 'instruction tuning evaluations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_evaluations_immutable_delete BEFORE DELETE ON instruction_tuning_evaluations BEGIN SELECT RAISE(ABORT, 'instruction tuning evaluations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_evaluation_results_immutable_update BEFORE UPDATE ON instruction_tuning_evaluation_results BEGIN SELECT RAISE(ABORT, 'instruction tuning evaluation results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_evaluation_results_immutable_delete BEFORE DELETE ON instruction_tuning_evaluation_results BEGIN SELECT RAISE(ABORT, 'instruction tuning evaluation results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_learning_checks_immutable_update BEFORE UPDATE ON instruction_learning_checks BEGIN SELECT RAISE(ABORT, 'instruction learning checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_learning_checks_immutable_delete BEFORE DELETE ON instruction_learning_checks BEGIN SELECT RAISE(ABORT, 'instruction learning checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_candidates_immutable_update BEFORE UPDATE ON instruction_tuning_candidates BEGIN SELECT RAISE(ABORT, 'instruction tuning candidates are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_tuning_candidates_immutable_delete BEFORE DELETE ON instruction_tuning_candidates BEGIN SELECT RAISE(ABORT, 'instruction tuning candidates are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_reproducibility_manifests_immutable_update BEFORE UPDATE ON instruction_reproducibility_manifests BEGIN SELECT RAISE(ABORT, 'instruction reproducibility manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS instruction_reproducibility_manifests_immutable_delete BEFORE DELETE ON instruction_reproducibility_manifests BEGIN SELECT RAISE(ABORT, 'instruction reproducibility manifests are append-only'); END;
"""

MIGRATION_013_NAME = "013_phase13_multilingual_evaluation"

PHASE13_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_evaluation_suites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    supported_languages_json TEXT NOT NULL DEFAULT '["ta","en","tgl","mixed"]',
    generation_configuration_json TEXT NOT NULL DEFAULT '{}',
    automated_thresholds_json TEXT NOT NULL DEFAULT '{}',
    human_review_rubric_json TEXT NOT NULL DEFAULT '{}',
    readiness_gate_configuration_json TEXT NOT NULL DEFAULT '{}',
    suite_checksum_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validated','active','retired','archived')),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TEXT,
    UNIQUE(name, version)
);
CREATE TABLE IF NOT EXISTS model_evaluation_fixture_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_suite_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    fixture_count INTEGER NOT NULL DEFAULT 0,
    checksum_sha256 TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_suite_id) REFERENCES model_evaluation_suites(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_evaluation_fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_fixture_set_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'language_compliance','instruction_following','response_relevance','format_compliance',
        'translation','definition','summarization','classification','transformation',
        'reasoning_basic','code_switching','tanglish_understanding','safety_refusal',
        'unsafe_instruction_handling','prompt_leakage','role_leakage','system_prompt_leakage',
        'repetition','robustness','unicode_handling'
    )),
    language TEXT NOT NULL CHECK (language IN ('ta','en','tgl','mixed')),
    prompt TEXT NOT NULL,
    system_prompt TEXT,
    expected_response_language TEXT,
    expected_format TEXT,
    expected_keywords_json TEXT NOT NULL DEFAULT '[]',
    forbidden_keywords_json TEXT NOT NULL DEFAULT '[]',
    reference_answer TEXT,
    reference_facts_json TEXT NOT NULL DEFAULT '[]',
    refusal_expected INTEGER NOT NULL DEFAULT 0 CHECK (refusal_expected IN (0,1)),
    max_new_tokens INTEGER NOT NULL DEFAULT 32,
    timeout_seconds REAL NOT NULL DEFAULT 5.0,
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('low','medium','high','critical')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_fixture_set_id) REFERENCES model_evaluation_fixture_sets(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_evaluation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_suite_id INTEGER NOT NULL,
    candidate_core_model_version_id INTEGER NOT NULL,
    checkpoint_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    generation_configuration_json TEXT NOT NULL DEFAULT '{}',
    generation_config_checksum_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validated','queued','running','completed','completed_with_warnings',
        'failed','cancelled','archived'
    )),
    fixture_count INTEGER NOT NULL DEFAULT 0,
    completed_fixture_count INTEGER NOT NULL DEFAULT 0,
    failed_fixture_count INTEGER NOT NULL DEFAULT 0,
    runtime_seconds REAL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    queued_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (model_evaluation_suite_id) REFERENCES model_evaluation_suites(id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_core_model_version_id) REFERENCES core_model_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (checkpoint_id) REFERENCES pretraining_checkpoints(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS model_evaluation_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_run_id INTEGER NOT NULL,
    model_evaluation_fixture_id INTEGER NOT NULL,
    generated_text TEXT NOT NULL DEFAULT '',
    prompt_token_count INTEGER NOT NULL DEFAULT 0,
    generated_token_count INTEGER NOT NULL DEFAULT 0,
    stop_reason TEXT NOT NULL DEFAULT 'unknown',
    runtime_ms INTEGER NOT NULL DEFAULT 0,
    output_checksum_sha256 TEXT NOT NULL,
    error_status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_run_id) REFERENCES model_evaluation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (model_evaluation_fixture_id) REFERENCES model_evaluation_fixtures(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS model_evaluation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_run_id INTEGER NOT NULL,
    language TEXT CHECK (language IS NULL OR language IN ('ta','en','tgl','mixed','overall')),
    category TEXT,
    severity TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_run_id) REFERENCES model_evaluation_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_evaluation_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_run_id INTEGER NOT NULL,
    model_evaluation_output_id INTEGER,
    issue_code TEXT NOT NULL CHECK (issue_code IN (
        'missing_language_coverage','tiny_fixture_set','evaluation_timeout','generation_failed',
        'empty_response','wrong_response_language','format_noncompliance','surface_relevance_low',
        'unsupported_claim','contradictory_claim','fabricated_citation','fabricated_url',
        'unsafe_compliance','incorrect_refusal','over_refusal','prompt_leakage',
        'role_token_leakage','system_prompt_leakage','internal_metadata_leakage',
        'high_duplicate_output_rate','token_loop_detected','phrase_loop_detected',
        'generic_response_collapse','unicode_invalid','tamil_combining_mark_issue',
        'eos_termination_failure','human_review_failed','human_review_disagreement',
        'insufficient_human_review'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','blocking')),
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_run_id) REFERENCES model_evaluation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (model_evaluation_output_id) REFERENCES model_evaluation_outputs(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS model_evaluation_human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_output_id INTEGER NOT NULL,
    reviewer_admin_public_id TEXT NOT NULL,
    rubric_version TEXT NOT NULL DEFAULT '1',
    language TEXT NOT NULL CHECK (language IN ('ta','en','tgl','mixed')),
    category TEXT NOT NULL,
    relevance_score INTEGER NOT NULL CHECK (relevance_score BETWEEN 1 AND 5),
    correctness_score INTEGER CHECK (correctness_score IS NULL OR correctness_score BETWEEN 1 AND 5),
    instruction_following_score INTEGER NOT NULL CHECK (instruction_following_score BETWEEN 1 AND 5),
    language_quality_score INTEGER NOT NULL CHECK (language_quality_score BETWEEN 1 AND 5),
    safety_score INTEGER NOT NULL CHECK (safety_score BETWEEN 1 AND 5),
    overall_score INTEGER NOT NULL CHECK (overall_score BETWEEN 1 AND 5),
    verdict TEXT NOT NULL CHECK (verdict IN ('pass','pass_with_warning','fail','needs_second_review')),
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_output_id) REFERENCES model_evaluation_outputs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_evaluation_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    left_run_id INTEGER NOT NULL,
    right_run_id INTEGER NOT NULL,
    compatibility TEXT NOT NULL CHECK (compatibility IN ('compatible','partially_compatible','incompatible')),
    ranked INTEGER NOT NULL DEFAULT 0 CHECK (ranked IN (0,1)),
    fields_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (left_run_id) REFERENCES model_evaluation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (right_run_id) REFERENCES model_evaluation_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_chat_readiness_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_run_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'evaluation_passed_with_limits','evaluation_warning','evaluation_blocked','not_assessed'
    )),
    dimension_scores_json TEXT NOT NULL DEFAULT '{}',
    blocking_issue_count INTEGER NOT NULL DEFAULT 0,
    warning_issue_count INTEGER NOT NULL DEFAULT 0,
    rationale_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_run_id) REFERENCES model_evaluation_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_evaluation_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_evaluation_run_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_evaluation_run_id) REFERENCES model_evaluation_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_suites_status ON model_evaluation_suites(status,created_at);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_fixture_sets_suite ON model_evaluation_fixture_sets(model_evaluation_suite_id);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_fixtures_set ON model_evaluation_fixtures(model_evaluation_fixture_set_id,category,language);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_runs_suite ON model_evaluation_runs(model_evaluation_suite_id,status);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_runs_candidate ON model_evaluation_runs(candidate_core_model_version_id);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_outputs_run ON model_evaluation_outputs(model_evaluation_run_id,model_evaluation_fixture_id);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_metrics_run ON model_evaluation_metrics(model_evaluation_run_id,language,category);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_issues_run ON model_evaluation_issues(model_evaluation_run_id,severity);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_human_reviews_output ON model_evaluation_human_reviews(model_evaluation_output_id);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_comparisons_runs ON model_evaluation_comparisons(left_run_id,right_run_id);
CREATE INDEX IF NOT EXISTS ix_model_chat_readiness_assessments_run ON model_chat_readiness_assessments(model_evaluation_run_id);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_manifests_run ON model_evaluation_manifests(model_evaluation_run_id);
CREATE TRIGGER IF NOT EXISTS model_evaluation_fixture_sets_immutable_update BEFORE UPDATE ON model_evaluation_fixture_sets BEGIN SELECT RAISE(ABORT, 'evaluation fixture sets are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_fixture_sets_immutable_delete BEFORE DELETE ON model_evaluation_fixture_sets BEGIN SELECT RAISE(ABORT, 'evaluation fixture sets are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_fixtures_immutable_update BEFORE UPDATE ON model_evaluation_fixtures BEGIN SELECT RAISE(ABORT, 'evaluation fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_fixtures_immutable_delete BEFORE DELETE ON model_evaluation_fixtures BEGIN SELECT RAISE(ABORT, 'evaluation fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_outputs_immutable_update BEFORE UPDATE ON model_evaluation_outputs BEGIN SELECT RAISE(ABORT, 'evaluation outputs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_outputs_immutable_delete BEFORE DELETE ON model_evaluation_outputs BEGIN SELECT RAISE(ABORT, 'evaluation outputs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_metrics_immutable_update BEFORE UPDATE ON model_evaluation_metrics BEGIN SELECT RAISE(ABORT, 'evaluation metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_metrics_immutable_delete BEFORE DELETE ON model_evaluation_metrics BEGIN SELECT RAISE(ABORT, 'evaluation metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_issues_immutable_update BEFORE UPDATE ON model_evaluation_issues BEGIN SELECT RAISE(ABORT, 'evaluation issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_issues_immutable_delete BEFORE DELETE ON model_evaluation_issues BEGIN SELECT RAISE(ABORT, 'evaluation issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_human_reviews_immutable_update BEFORE UPDATE ON model_evaluation_human_reviews BEGIN SELECT RAISE(ABORT, 'human reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_human_reviews_immutable_delete BEFORE DELETE ON model_evaluation_human_reviews BEGIN SELECT RAISE(ABORT, 'human reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_comparisons_immutable_update BEFORE UPDATE ON model_evaluation_comparisons BEGIN SELECT RAISE(ABORT, 'evaluation comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_comparisons_immutable_delete BEFORE DELETE ON model_evaluation_comparisons BEGIN SELECT RAISE(ABORT, 'evaluation comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_chat_readiness_assessments_immutable_update BEFORE UPDATE ON model_chat_readiness_assessments BEGIN SELECT RAISE(ABORT, 'chat readiness assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_chat_readiness_assessments_immutable_delete BEFORE DELETE ON model_chat_readiness_assessments BEGIN SELECT RAISE(ABORT, 'chat readiness assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_manifests_immutable_update BEFORE UPDATE ON model_evaluation_manifests BEGIN SELECT RAISE(ABORT, 'evaluation manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_evaluation_manifests_immutable_delete BEFORE DELETE ON model_evaluation_manifests BEGIN SELECT RAISE(ABORT, 'evaluation manifests are append-only'); END;
"""

MIGRATION_014_NAME = "014_phase14_model_release_registry"

PHASE14_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_release_families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    intended_use TEXT NOT NULL DEFAULT '',
    supported_languages_json TEXT NOT NULL DEFAULT '["ta","en","tgl","mixed"]',
    compatibility_policy_json TEXT NOT NULL DEFAULT '{}',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN ('draft','active','deprecated','archived')),
    current_release_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS model_release_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_family_id INTEGER NOT NULL,
    core_model_version_id INTEGER NOT NULL,
    checkpoint_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    dataset_version_id INTEGER,
    instruction_tuning_candidate_id INTEGER,
    model_evaluation_run_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','collecting_artifacts','validating','eligible','eligible_with_warnings',
        'blocked','approved','released','rejected','superseded','archived'
    )),
    label TEXT,
    notes TEXT NOT NULL DEFAULT '',
    latest_eligibility_status TEXT NOT NULL DEFAULT 'not_assessed',
    latest_eligibility_public_id TEXT,
    latest_model_card_public_id TEXT,
    latest_manifest_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_family_id) REFERENCES model_release_families(id) ON DELETE RESTRICT,
    FOREIGN KEY (core_model_version_id) REFERENCES core_model_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (checkpoint_id) REFERENCES pretraining_checkpoints(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (instruction_tuning_candidate_id) REFERENCES instruction_tuning_candidates(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_evaluation_run_id) REFERENCES model_evaluation_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS model_release_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_candidate_id INTEGER NOT NULL,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN (
        'model_checkpoint','model_config','tokenizer_model','tokenizer_vocab',
        'tokenizer_manifest','dataset_manifest','base_training_manifest',
        'instruction_tuning_manifest','evaluation_manifest','model_card',
        'release_manifest','licence_notice'
    )),
    source_entity_public_id TEXT,
    logical_name TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum_algorithm TEXT NOT NULL DEFAULT 'sha256',
    checksum TEXT,
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK (verification_status IN (
        'pending','verified','missing','checksum_mismatch','invalid','not_applicable'
    )),
    required INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0,1)),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_at TEXT,
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_release_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_candidate_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_release_model_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_candidate_id INTEGER NOT NULL,
    card_markdown TEXT NOT NULL,
    card_checksum_sha256 TEXT NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'not_validated' CHECK (validation_status IN ('not_validated','valid','invalid')),
    validation_issues_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_release_eligibility_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_candidate_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('eligible','eligible_with_warnings','blocked','not_assessed')),
    dimension_scores_json TEXT NOT NULL DEFAULT '{}',
    blocking_issue_count INTEGER NOT NULL DEFAULT 0,
    warning_issue_count INTEGER NOT NULL DEFAULT 0,
    rationale_json TEXT NOT NULL DEFAULT '{}',
    eligibility_checksum_sha256 TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_release_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_candidate_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL CHECK (issue_code IN (
        'artifact_missing','artifact_checksum_mismatch','artifact_path_invalid',
        'checkpoint_corrupt','model_config_mismatch','tokenizer_missing',
        'tokenizer_vocab_mismatch','special_token_mismatch','dataset_lineage_missing',
        'training_manifest_missing','instruction_manifest_missing',
        'evaluation_manifest_missing','evaluation_blocked','evaluation_warning',
        'safety_blocking_issue','licence_missing','licence_unsupported',
        'model_card_incomplete','model_card_misleading','release_manifest_mismatch',
        'approval_missing','approval_stale','version_conflict',
        'resource_requirement_unknown','rollback_target_missing',
        'rollback_target_ineligible','bundle_generation_failed','bundle_checksum_mismatch'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','blocking')),
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_release_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_candidate_id INTEGER NOT NULL,
    admin_public_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('technical','evaluation','security','release')),
    decision TEXT NOT NULL CHECK (decision IN ('approve','approve_with_warning','reject','request_changes')),
    comment TEXT NOT NULL DEFAULT '',
    eligibility_checksum_sha256 TEXT NOT NULL,
    manifest_checksum_sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_family_id INTEGER NOT NULL,
    model_release_candidate_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    prerelease_label TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','released','deprecated','retired','rolled_back','archived')),
    deployment_eligibility TEXT NOT NULL DEFAULT 'not_deployable' CHECK (deployment_eligibility IN ('deployable','deployable_with_warnings','not_deployable')),
    release_manifest_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    released_at TEXT,
    deprecated_at TEXT,
    retired_at TEXT,
    FOREIGN KEY (model_release_family_id) REFERENCES model_release_families(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id) ON DELETE RESTRICT,
    UNIQUE(model_release_family_id, version)
);
CREATE TABLE IF NOT EXISTS model_release_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    left_release_id INTEGER NOT NULL,
    right_release_id INTEGER NOT NULL,
    compatibility TEXT NOT NULL CHECK (compatibility IN ('compatible','partially_compatible','incompatible')),
    ranked INTEGER NOT NULL DEFAULT 0 CHECK (ranked IN (0,1)),
    fields_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (left_release_id) REFERENCES model_releases(id) ON DELETE CASCADE,
    FOREIGN KEY (right_release_id) REFERENCES model_releases(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_release_rollback_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_release_id INTEGER NOT NULL,
    target_release_id INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validated','approved','executed','rejected','cancelled')),
    compatibility_result_json TEXT NOT NULL DEFAULT '{}',
    target_verification_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    validated_at TEXT,
    approved_at TEXT,
    executed_at TEXT,
    FOREIGN KEY (source_release_id) REFERENCES model_releases(id) ON DELETE RESTRICT,
    FOREIGN KEY (target_release_id) REFERENCES model_releases(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS model_release_rollback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_rollback_plan_id INTEGER NOT NULL,
    previous_release_public_id TEXT NOT NULL,
    new_release_public_id TEXT NOT NULL,
    approval_evidence_json TEXT NOT NULL DEFAULT '{}',
    executed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_rollback_plan_id) REFERENCES model_release_rollback_plans(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS model_release_bundles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_id INTEGER NOT NULL,
    bundle_format TEXT NOT NULL DEFAULT 'zip' CHECK (bundle_format IN ('zip','tar_gz')),
    inventory_json TEXT NOT NULL DEFAULT '[]',
    bundle_checksum_sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    storage_key TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_id) REFERENCES model_releases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_model_release_families_status ON model_release_families(lifecycle_status);
CREATE INDEX IF NOT EXISTS ix_model_release_candidates_family ON model_release_candidates(model_release_family_id,status);
CREATE INDEX IF NOT EXISTS ix_model_release_candidates_core_model ON model_release_candidates(core_model_version_id);
CREATE INDEX IF NOT EXISTS ix_model_release_artifacts_candidate ON model_release_artifacts(model_release_candidate_id,artifact_type);
CREATE INDEX IF NOT EXISTS ix_model_release_manifests_candidate ON model_release_manifests(model_release_candidate_id);
CREATE INDEX IF NOT EXISTS ix_model_release_model_cards_candidate ON model_release_model_cards(model_release_candidate_id);
CREATE INDEX IF NOT EXISTS ix_model_release_eligibility_candidate ON model_release_eligibility_assessments(model_release_candidate_id);
CREATE INDEX IF NOT EXISTS ix_model_release_issues_candidate ON model_release_issues(model_release_candidate_id,severity);
CREATE INDEX IF NOT EXISTS ix_model_release_approvals_candidate ON model_release_approvals(model_release_candidate_id,role);
CREATE INDEX IF NOT EXISTS ix_model_releases_family ON model_releases(model_release_family_id,status);
CREATE INDEX IF NOT EXISTS ix_model_release_comparisons_releases ON model_release_comparisons(left_release_id,right_release_id);
CREATE INDEX IF NOT EXISTS ix_model_release_rollback_plans_releases ON model_release_rollback_plans(source_release_id,target_release_id);
CREATE INDEX IF NOT EXISTS ix_model_release_rollback_events_plan ON model_release_rollback_events(model_release_rollback_plan_id);
CREATE INDEX IF NOT EXISTS ix_model_release_bundles_release ON model_release_bundles(model_release_id);
CREATE TRIGGER IF NOT EXISTS model_release_artifacts_immutable_update BEFORE UPDATE ON model_release_artifacts BEGIN SELECT RAISE(ABORT, 'release artifacts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_artifacts_immutable_delete BEFORE DELETE ON model_release_artifacts BEGIN SELECT RAISE(ABORT, 'release artifacts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_manifests_immutable_update BEFORE UPDATE ON model_release_manifests BEGIN SELECT RAISE(ABORT, 'release manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_manifests_immutable_delete BEFORE DELETE ON model_release_manifests BEGIN SELECT RAISE(ABORT, 'release manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_model_cards_immutable_update BEFORE UPDATE ON model_release_model_cards BEGIN SELECT RAISE(ABORT, 'release model cards are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_model_cards_immutable_delete BEFORE DELETE ON model_release_model_cards BEGIN SELECT RAISE(ABORT, 'release model cards are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_eligibility_immutable_update BEFORE UPDATE ON model_release_eligibility_assessments BEGIN SELECT RAISE(ABORT, 'release eligibility assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_eligibility_immutable_delete BEFORE DELETE ON model_release_eligibility_assessments BEGIN SELECT RAISE(ABORT, 'release eligibility assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_issues_immutable_update BEFORE UPDATE ON model_release_issues BEGIN SELECT RAISE(ABORT, 'release issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_issues_immutable_delete BEFORE DELETE ON model_release_issues BEGIN SELECT RAISE(ABORT, 'release issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_approvals_immutable_update BEFORE UPDATE ON model_release_approvals BEGIN SELECT RAISE(ABORT, 'release approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_approvals_immutable_delete BEFORE DELETE ON model_release_approvals BEGIN SELECT RAISE(ABORT, 'release approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_comparisons_immutable_update BEFORE UPDATE ON model_release_comparisons BEGIN SELECT RAISE(ABORT, 'release comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_comparisons_immutable_delete BEFORE DELETE ON model_release_comparisons BEGIN SELECT RAISE(ABORT, 'release comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_rollback_events_immutable_update BEFORE UPDATE ON model_release_rollback_events BEGIN SELECT RAISE(ABORT, 'release rollback events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_rollback_events_immutable_delete BEFORE DELETE ON model_release_rollback_events BEGIN SELECT RAISE(ABORT, 'release rollback events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_bundles_immutable_update BEFORE UPDATE ON model_release_bundles BEGIN SELECT RAISE(ABORT, 'release bundles are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_release_bundles_immutable_delete BEFORE DELETE ON model_release_bundles BEGIN SELECT RAISE(ABORT, 'release bundles are append-only'); END;
"""

