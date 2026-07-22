"""Initial SQLite schema for Brud AI Phase 1."""

SCHEMA_VERSION = 10

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

MIGRATION_010_NAME = "010_phase10_pretraining_reliability"

PHASE10_TABLES: dict[str, list[tuple[str, str]]] = {
    "training_dataset_coverage": [
        ("public_id", "TEXT NOT NULL UNIQUE"),
        ("pretraining_job_id", "INTEGER NOT NULL"),
        ("split", "TEXT NOT NULL CHECK (split IN ('train','valid'))"),
        ("total_records", "INTEGER NOT NULL DEFAULT 0"),
        ("eligible_records", "INTEGER NOT NULL DEFAULT 0"),
        ("encoded_records", "INTEGER NOT NULL DEFAULT 0"),
        ("excluded_records", "INTEGER NOT NULL DEFAULT 0"),
        ("zero_token_records", "INTEGER NOT NULL DEFAULT 0"),
        ("split_records", "INTEGER NOT NULL DEFAULT 0"),
        ("truncated_records", "INTEGER NOT NULL DEFAULT 0"),
        ("total_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("usable_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("padding_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("language_distribution_json", "TEXT DEFAULT '{}'"),
        ("record_type_distribution_json", "TEXT DEFAULT '{}'"),
        ("source_type_distribution_json", "TEXT DEFAULT '{}'"),
        ("stream_checksum_sha256", "TEXT NOT NULL"),
        ("exclusion_reasons_json", "TEXT DEFAULT '{}'"),
        ("created_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ],
    "training_recovery_attempts": [
        ("public_id", "TEXT NOT NULL UNIQUE"),
        ("pretraining_job_id", "INTEGER NOT NULL"),
        ("source_worker_id", "TEXT"),
        ("recovering_worker_id", "TEXT NOT NULL"),
        ("recovery_type", "TEXT NOT NULL CHECK (recovery_type IN ('stale_lease','worker_crash','manual_resume','pause_resume','checkpoint_recovery'))"),
        ("status", "TEXT NOT NULL CHECK (status IN ('validating','recovering','completed','completed_with_warnings','failed','cancelled'))"),
        ("source_checkpoint_public_id", "TEXT"),
        ("recovered_step", "INTEGER"),
        ("recovered_tokens", "INTEGER"),
        ("previous_lease_generation", "INTEGER NOT NULL"),
        ("new_lease_generation", "INTEGER NOT NULL"),
        ("validation_summary_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("error_code", "TEXT"),
        ("error_message", "TEXT"),
        ("started_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("completed_at", "TEXT"),
    ],
    "worker_heartbeats": [
        ("public_id", "TEXT NOT NULL UNIQUE"),
        ("worker_id", "TEXT NOT NULL UNIQUE"),
        ("pretraining_job_id", "INTEGER"),
        ("status", "TEXT NOT NULL DEFAULT 'starting' CHECK (status IN ('starting','idle','claiming','running','pausing','recovering','stopping','stopped','failed'))"),
        ("current_job_public_id", "TEXT"),
        ("hostname_hash", "TEXT NOT NULL"),
        ("process_started_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("last_heartbeat_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("lease_expires_at", "TEXT"),
        ("lease_generation", "INTEGER NOT NULL DEFAULT 1"),
        ("shutdown_requested", "INTEGER NOT NULL DEFAULT 0 CHECK (shutdown_requested IN (0,1))"),
        ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("created_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"),
        ("FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE CASCADE"),
    ],
}

PHASE10_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_training_dataset_coverage_job ON training_dataset_coverage(pretraining_job_id)",
    "CREATE INDEX IF NOT EXISTS ix_training_dataset_coverage_checksum ON training_dataset_coverage(stream_checksum_sha256)",
    "CREATE INDEX IF NOT EXISTS ix_training_recovery_attempts_job ON training_recovery_attempts(pretraining_job_id)",
    "CREATE INDEX IF NOT EXISTS ix_training_recovery_attempts_status ON training_recovery_attempts(status,completed_at)",
    "CREATE INDEX IF NOT EXISTS ix_training_recovery_attempts_recovery_type ON training_recovery_attempts(recovery_type)",
    "CREATE INDEX IF NOT EXISTS ix_worker_heartbeats_job ON worker_heartbeats(pretraining_job_id)",
    "CREATE INDEX IF NOT EXISTS ix_worker_heartbeats_status ON worker_heartbeats(status,updated_at)",
    "CREATE INDEX IF NOT EXISTS ix_worker_heartbeats_lease ON worker_heartbeats(worker_id,lease_generation,lease_expires_at)",
]

PHASE10_TRIGGERS = [
    "CREATE TRIGGER IF NOT EXISTS training_dataset_coverage_updated_at BEFORE UPDATE ON training_dataset_coverage BEGIN SELECT RAISE(ABORT, 'coverage records are immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS worker_heartbeats_updated_at BEFORE UPDATE ON worker_heartbeats BEGIN SELECT RAISE(ABORT, 'worker heartbeats are immutable'); END",
]

