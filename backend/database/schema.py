"""Initial SQLite schema for Brud AI Phase 1."""

SCHEMA_VERSION = 18

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

MIGRATION_015_NAME = "015_phase15_controlled_inference_runtime"

PHASE15_SCHEMA = """
CREATE TABLE IF NOT EXISTS inference_runtime_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    runtime_type TEXT NOT NULL DEFAULT 'local_cpu' CHECK (runtime_type IN ('local_cpu','local_gpu')),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    device TEXT NOT NULL DEFAULT 'cpu',
    dtype TEXT NOT NULL DEFAULT 'float32' CHECK (dtype IN ('float32')),
    maximum_loaded_models INTEGER NOT NULL DEFAULT 1,
    maximum_concurrent_requests INTEGER NOT NULL DEFAULT 1,
    maximum_context_length INTEGER NOT NULL,
    maximum_new_tokens INTEGER NOT NULL,
    request_timeout_seconds INTEGER NOT NULL DEFAULT 60,
    idle_unload_seconds INTEGER NOT NULL DEFAULT 900,
    minimum_available_memory_bytes INTEGER NOT NULL,
    minimum_available_disk_bytes INTEGER NOT NULL,
    resource_policy_json TEXT NOT NULL DEFAULT '{}',
    generation_defaults_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS inference_runtime_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    inference_runtime_profile_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'offline' CHECK (status IN (
        'offline','starting','idle','loading','ready','busy','unloading','degraded','failed','stopped'
    )),
    loaded_release_public_id TEXT,
    loaded_checkpoint_public_id TEXT,
    loaded_tokenizer_public_id TEXT,
    loaded_at TEXT,
    last_request_at TEXT,
    last_health_at TEXT,
    failure_code TEXT,
    failure_summary TEXT,
    memory_snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inference_runtime_profile_id) REFERENCES inference_runtime_profiles(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS inference_runtime_health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    inference_runtime_instance_id INTEGER NOT NULL,
    check_type TEXT NOT NULL CHECK (check_type IN (
        'runtime_process','model_loaded','tokenizer_loaded','checkpoint_verified',
        'memory_available','generation_smoke_test','latency_within_limit','special_token_output_safe'
    )),
    status TEXT NOT NULL CHECK (status IN ('healthy','degraded','unhealthy','not_checked')),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inference_runtime_instance_id) REFERENCES inference_runtime_instances(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inference_model_compatibility_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_release_id INTEGER NOT NULL,
    inference_runtime_profile_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('compatible','compatible_with_warnings','incompatible','not_assessed')),
    dimension_scores_json TEXT NOT NULL DEFAULT '{}',
    blocking_issue_count INTEGER NOT NULL DEFAULT 0,
    warning_issue_count INTEGER NOT NULL DEFAULT 0,
    rationale_json TEXT NOT NULL DEFAULT '{}',
    compatibility_checksum_sha256 TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_release_id) REFERENCES model_releases(id) ON DELETE RESTRICT,
    FOREIGN KEY (inference_runtime_profile_id) REFERENCES inference_runtime_profiles(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS inference_assignment_scopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    scope_key TEXT NOT NULL UNIQUE CHECK (scope_key IN (
        'admin_diagnostic','admin_chat_lab','internal_canary','public_chat'
    )),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    description TEXT NOT NULL DEFAULT '',
    policy_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS inference_model_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_assignment_scope_id INTEGER NOT NULL,
    model_release_id INTEGER NOT NULL,
    inference_runtime_profile_id INTEGER NOT NULL,
    generation_config_json TEXT NOT NULL DEFAULT '{}',
    context_policy_json TEXT NOT NULL DEFAULT '{}',
    fallback_policy_json TEXT NOT NULL DEFAULT '{}',
    canary_percentage INTEGER NOT NULL DEFAULT 0 CHECK (canary_percentage BETWEEN 0 AND 100),
    start_at TEXT,
    expire_at TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validating','approved','active','paused','rolled_back','rejected','expired','archived'
    )),
    current_version_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_assignment_scope_id) REFERENCES inference_assignment_scopes(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_release_id) REFERENCES model_releases(id) ON DELETE RESTRICT,
    FOREIGN KEY (inference_runtime_profile_id) REFERENCES inference_runtime_profiles(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS inference_assignment_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_assignment_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    model_release_id INTEGER NOT NULL,
    inference_runtime_profile_id INTEGER NOT NULL,
    generation_config_json TEXT NOT NULL DEFAULT '{}',
    context_policy_json TEXT NOT NULL DEFAULT '{}',
    fallback_policy_json TEXT NOT NULL DEFAULT '{}',
    canary_percentage INTEGER NOT NULL DEFAULT 0 CHECK (canary_percentage BETWEEN 0 AND 100),
    eligibility_checksum_sha256 TEXT NOT NULL,
    compatibility_checksum_sha256 TEXT NOT NULL,
    approval_checksum_sha256 TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (model_release_id) REFERENCES model_releases(id) ON DELETE RESTRICT,
    FOREIGN KEY (inference_runtime_profile_id) REFERENCES inference_runtime_profiles(id) ON DELETE RESTRICT,
    UNIQUE(model_assignment_id, version_number)
);
CREATE TABLE IF NOT EXISTS inference_assignment_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_assignment_id INTEGER NOT NULL,
    model_assignment_version_id INTEGER,
    admin_public_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('technical','evaluation','security','release')),
    decision TEXT NOT NULL CHECK (decision IN ('approve','approve_with_warning','reject','request_changes')),
    comment TEXT NOT NULL DEFAULT '',
    eligibility_checksum_sha256 TEXT,
    compatibility_checksum_sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (model_assignment_version_id) REFERENCES inference_assignment_versions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inference_assignment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_assignment_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'created','validated','approved','activated','paused','resumed','canary_started',
        'canary_stopped','fallback_used','rollback_started','rollback_completed',
        'rollback_failed','expired','rejected'
    )),
    details_json TEXT NOT NULL DEFAULT '{}',
    actor_admin_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inference_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_assignment_id INTEGER NOT NULL,
    inference_runtime_instance_id INTEGER,
    scope TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','expired','closed','failed')),
    turn_count INTEGER NOT NULL DEFAULT 0,
    max_turns INTEGER NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    closed_at TEXT,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE RESTRICT,
    FOREIGN KEY (inference_runtime_instance_id) REFERENCES inference_runtime_instances(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS inference_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    inference_runtime_instance_id INTEGER NOT NULL,
    model_assignment_id INTEGER NOT NULL,
    model_assignment_version_id INTEGER,
    scope TEXT NOT NULL,
    inference_session_id INTEGER,
    prompt_checksum_sha256 TEXT NOT NULL,
    input_token_count INTEGER NOT NULL DEFAULT 0,
    maximum_new_token_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN (
        'accepted','validating','queued','running','completed','completed_with_warning',
        'timed_out','cancelled','failed','rejected'
    )),
    started_at TEXT,
    ended_at TEXT,
    runtime_milliseconds INTEGER,
    stop_reason TEXT,
    failure_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inference_runtime_instance_id) REFERENCES inference_runtime_instances(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_assignment_version_id) REFERENCES inference_assignment_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (inference_session_id) REFERENCES inference_sessions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS inference_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    inference_request_id INTEGER NOT NULL,
    output_checksum_sha256 TEXT NOT NULL,
    generated_token_count INTEGER NOT NULL DEFAULT 0,
    stop_reason TEXT NOT NULL,
    runtime_milliseconds INTEGER NOT NULL DEFAULT 0,
    role_token_leakage_flag INTEGER NOT NULL DEFAULT 0 CHECK (role_token_leakage_flag IN (0,1)),
    prompt_leakage_flag INTEGER NOT NULL DEFAULT 0 CHECK (prompt_leakage_flag IN (0,1)),
    repetition_warning INTEGER NOT NULL DEFAULT 0 CHECK (repetition_warning IN (0,1)),
    unicode_valid_flag INTEGER NOT NULL DEFAULT 1 CHECK (unicode_valid_flag IN (0,1)),
    model_release_public_id TEXT NOT NULL,
    model_assignment_version_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inference_request_id) REFERENCES inference_requests(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inference_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    inference_runtime_instance_id INTEGER,
    inference_request_id INTEGER,
    model_assignment_id INTEGER,
    failure_code TEXT NOT NULL CHECK (failure_code IN (
        'release_not_eligible','assignment_not_active','assignment_scope_forbidden',
        'registry_fixture_forbidden','manifest_mismatch','artifact_verification_failed',
        'checkpoint_corrupt','tokenizer_invalid','model_config_mismatch','vocabulary_mismatch',
        'special_token_mismatch','memory_guard_failed','disk_guard_failed','model_load_failed',
        'context_too_long','generation_timeout','generation_cancelled','role_token_leakage',
        'prompt_leakage','unicode_invalid','runtime_busy','runtime_unavailable','fallback_used'
    )),
    failure_summary TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inference_runtime_instance_id) REFERENCES inference_runtime_instances(id) ON DELETE RESTRICT,
    FOREIGN KEY (inference_request_id) REFERENCES inference_requests(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS inference_canary_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_assignment_id INTEGER NOT NULL,
    run_status TEXT NOT NULL CHECK (run_status IN ('started','running','paused','stopped','completed')),
    percentage INTEGER NOT NULL DEFAULT 0 CHECK (percentage BETWEEN 0 AND 100),
    max_request_count INTEGER NOT NULL DEFAULT 0,
    requests_executed INTEGER NOT NULL DEFAULT 0,
    stop_reason TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inference_canary_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    inference_canary_run_id INTEGER NOT NULL,
    inference_request_id INTEGER,
    routing_key TEXT NOT NULL,
    used_model INTEGER NOT NULL DEFAULT 1 CHECK (used_model IN (0,1)),
    success INTEGER NOT NULL DEFAULT 0 CHECK (success IN (0,1)),
    timed_out INTEGER NOT NULL DEFAULT 0 CHECK (timed_out IN (0,1)),
    latency_ms INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    role_leakage INTEGER NOT NULL DEFAULT 0 CHECK (role_leakage IN (0,1)),
    prompt_leakage INTEGER NOT NULL DEFAULT 0 CHECK (prompt_leakage IN (0,1)),
    duplicate_output INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_output IN (0,1)),
    unicode_valid INTEGER NOT NULL DEFAULT 1 CHECK (unicode_valid IN (0,1)),
    stop_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inference_canary_run_id) REFERENCES inference_canary_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (inference_request_id) REFERENCES inference_requests(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS inference_runtime_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    model_assignment_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_inference_runtime_instances_profile ON inference_runtime_instances(inference_runtime_profile_id,status);
CREATE INDEX IF NOT EXISTS ix_inference_runtime_health_checks_instance ON inference_runtime_health_checks(inference_runtime_instance_id,check_type);
CREATE INDEX IF NOT EXISTS ix_inference_model_compatibility_release ON inference_model_compatibility_assessments(model_release_id,inference_runtime_profile_id);
CREATE INDEX IF NOT EXISTS ix_model_assignments_scope ON inference_model_assignments(model_assignment_scope_id,status);
CREATE INDEX IF NOT EXISTS ix_model_assignments_release ON inference_model_assignments(model_release_id);
CREATE INDEX IF NOT EXISTS ix_model_assignment_versions_assignment ON inference_assignment_versions(model_assignment_id,version_number);
CREATE INDEX IF NOT EXISTS ix_model_assignment_approvals_assignment ON inference_assignment_approvals(model_assignment_id,role);
CREATE INDEX IF NOT EXISTS ix_model_assignment_events_assignment ON inference_assignment_events(model_assignment_id,event_type);
CREATE INDEX IF NOT EXISTS ix_inference_sessions_assignment ON inference_sessions(model_assignment_id,status);
CREATE INDEX IF NOT EXISTS ix_inference_requests_assignment ON inference_requests(model_assignment_id,status);
CREATE INDEX IF NOT EXISTS ix_inference_requests_instance ON inference_requests(inference_runtime_instance_id);
CREATE INDEX IF NOT EXISTS ix_inference_results_request ON inference_results(inference_request_id);
CREATE INDEX IF NOT EXISTS ix_inference_failures_assignment ON inference_failures(model_assignment_id,failure_code);
CREATE INDEX IF NOT EXISTS ix_inference_canary_runs_assignment ON inference_canary_runs(model_assignment_id,run_status);
CREATE INDEX IF NOT EXISTS ix_inference_canary_results_run ON inference_canary_results(inference_canary_run_id);
CREATE INDEX IF NOT EXISTS ix_inference_runtime_manifests_assignment ON inference_runtime_manifests(model_assignment_id);
CREATE TRIGGER IF NOT EXISTS inference_runtime_health_checks_immutable_update BEFORE UPDATE ON inference_runtime_health_checks BEGIN SELECT RAISE(ABORT, 'runtime health checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_runtime_health_checks_immutable_delete BEFORE DELETE ON inference_runtime_health_checks BEGIN SELECT RAISE(ABORT, 'runtime health checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_model_compatibility_immutable_update BEFORE UPDATE ON inference_model_compatibility_assessments BEGIN SELECT RAISE(ABORT, 'compatibility assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_model_compatibility_immutable_delete BEFORE DELETE ON inference_model_compatibility_assessments BEGIN SELECT RAISE(ABORT, 'compatibility assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_assignment_versions_immutable_update BEFORE UPDATE ON inference_assignment_versions BEGIN SELECT RAISE(ABORT, 'assignment versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_assignment_versions_immutable_delete BEFORE DELETE ON inference_assignment_versions BEGIN SELECT RAISE(ABORT, 'assignment versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_assignment_approvals_immutable_update BEFORE UPDATE ON inference_assignment_approvals BEGIN SELECT RAISE(ABORT, 'assignment approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_assignment_approvals_immutable_delete BEFORE DELETE ON inference_assignment_approvals BEGIN SELECT RAISE(ABORT, 'assignment approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_assignment_events_immutable_update BEFORE UPDATE ON inference_assignment_events BEGIN SELECT RAISE(ABORT, 'assignment events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS model_assignment_events_immutable_delete BEFORE DELETE ON inference_assignment_events BEGIN SELECT RAISE(ABORT, 'assignment events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_requests_immutable_update BEFORE UPDATE ON inference_requests BEGIN SELECT RAISE(ABORT, 'inference requests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_requests_immutable_delete BEFORE DELETE ON inference_requests BEGIN SELECT RAISE(ABORT, 'inference requests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_results_immutable_update BEFORE UPDATE ON inference_results BEGIN SELECT RAISE(ABORT, 'inference results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_results_immutable_delete BEFORE DELETE ON inference_results BEGIN SELECT RAISE(ABORT, 'inference results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_failures_immutable_update BEFORE UPDATE ON inference_failures BEGIN SELECT RAISE(ABORT, 'inference failures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_failures_immutable_delete BEFORE DELETE ON inference_failures BEGIN SELECT RAISE(ABORT, 'inference failures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_canary_runs_immutable_update BEFORE UPDATE ON inference_canary_runs BEGIN SELECT RAISE(ABORT, 'canary runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_canary_runs_immutable_delete BEFORE DELETE ON inference_canary_runs BEGIN SELECT RAISE(ABORT, 'canary runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_canary_results_immutable_update BEFORE UPDATE ON inference_canary_results BEGIN SELECT RAISE(ABORT, 'canary results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_canary_results_immutable_delete BEFORE DELETE ON inference_canary_results BEGIN SELECT RAISE(ABORT, 'canary results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_runtime_manifests_immutable_update BEFORE UPDATE ON inference_runtime_manifests BEGIN SELECT RAISE(ABORT, 'runtime manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inference_runtime_manifests_immutable_delete BEFORE DELETE ON inference_runtime_manifests BEGIN SELECT RAISE(ABORT, 'runtime manifests are append-only'); END;
"""

MIGRATION_016_NAME = "016_phase16_rag_grounded_answering"

# Phase 16 deliberately reuses the existing `admin_diagnostic` assignment
# scope for RAG grounded generation rather than adding a new `admin_rag_lab`
# value to `inference_assignment_scopes.scope_key`'s CHECK constraint.
# SQLite's `foreign_keys` pragma cannot be toggled mid-transaction (verified
# directly: a `DROP TABLE` of a table with an incoming FK reference from
# rows in another table fails under `foreign_keys=ON` even after issuing
# `PRAGMA foreign_keys = OFF` inside an already-open transaction), and
# `initialize_database()` applies every migration inside one shared
# transaction — so a table rebuild to widen the CHECK constraint cannot
# safely happen inside `_apply_v16` without weakening FK enforcement for
# every other migration. The spec's own text allows this ("Add or reuse an
# explicit scope: admin_rag_lab"); RAG-specific requirements (active
# knowledge space, active indexes, active retrieval profile, no registry
# fixture) are enforced entirely inside `RagGenerationService`, not via a
# new schema-level scope value.
#
# `rag_grounded_requests` is classified MUTABLE here (no append-only
# trigger), not append-only as its evidence-adjacent name might suggest.
# It follows the same reasoning already used for `rag_embedding_runs` and
# `rag_evaluation_runs`: a request row is created once retrieval succeeds
# (status='accepted') and its status must be updated in place as
# generation proceeds to a terminal status (completed / insufficient_
# evidence / retrieval_failed / generation_failed / blocked_evidence) --
# a genuine two-phase create-then-resolve lifecycle, mirroring Phase 13's
# own precedent of documenting `model_evaluation_runs` as a "Mutable
# lifecycle row" despite sitting next to append-only evidence tables. The
# immutable evidence itself (the answer text checksum, citations, issues)
# still lives in true append-only tables below.

PHASE16_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_knowledge_spaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    supported_languages_json TEXT NOT NULL DEFAULT '["ta","en","tgl","mixed"]',
    access_policy_json TEXT NOT NULL DEFAULT '{}',
    default_retrieval_profile_public_id TEXT,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','active','read_only','deprecated','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);
CREATE TABLE IF NOT EXISTS rag_knowledge_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    knowledge_space_id INTEGER NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'dataset_version','pdf_document','plain_text','markdown','html_snapshot',
        'manual_admin_content','course_material','faq'
    )),
    source_entity_public_id TEXT,
    title TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'unknown',
    licence_status TEXT NOT NULL DEFAULT 'unknown' CHECK (licence_status IN (
        'unknown','open','restricted','blocked'
    )),
    approval_status TEXT NOT NULL DEFAULT 'draft' CHECK (approval_status IN (
        'draft','review_required','approved','rejected','quarantined','archived'
    )),
    content_checksum_sha256 TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_source_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    knowledge_source_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    content_checksum_sha256 TEXT NOT NULL,
    extraction_method TEXT NOT NULL DEFAULT 'direct',
    extraction_version TEXT NOT NULL DEFAULT 'v1',
    normalized_content_checksum_sha256 TEXT,
    character_count INTEGER NOT NULL DEFAULT 0,
    token_estimate INTEGER NOT NULL DEFAULT 0,
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN (
        'processing','ready','failed','superseded','archived'
    )),
    raw_content TEXT NOT NULL,
    normalized_content TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_source_id) REFERENCES rag_knowledge_sources(id) ON DELETE RESTRICT,
    UNIQUE(knowledge_source_id, version_number),
    UNIQUE(knowledge_source_id, content_checksum_sha256)
);
CREATE TABLE IF NOT EXISTS rag_chunk_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_version_id INTEGER NOT NULL,
    chunking_strategy TEXT NOT NULL DEFAULT 'heading_aware' CHECK (chunking_strategy IN (
        'paragraph','heading_aware','sentence_window','fixed_token_window','record_based'
    )),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','building','validated','active','superseded','failed'
    )),
    total_chunks INTEGER NOT NULL DEFAULT 0,
    accepted_chunks INTEGER NOT NULL DEFAULT 0,
    warning_chunks INTEGER NOT NULL DEFAULT 0,
    rejected_chunks INTEGER NOT NULL DEFAULT 0,
    quarantined_chunks INTEGER NOT NULL DEFAULT 0,
    chunk_manifest_checksum_sha256 TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_version_id) REFERENCES rag_source_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    chunk_set_id INTEGER NOT NULL,
    source_version_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    heading_path_json TEXT NOT NULL DEFAULT '[]',
    source_location_json TEXT NOT NULL DEFAULT '{}',
    language TEXT NOT NULL DEFAULT 'unknown',
    record_type TEXT,
    normalized_text TEXT NOT NULL,
    character_count INTEGER NOT NULL DEFAULT 0,
    estimated_token_count INTEGER NOT NULL DEFAULT 0,
    overlap_before_tokens INTEGER NOT NULL DEFAULT 0,
    overlap_after_tokens INTEGER NOT NULL DEFAULT 0,
    content_checksum_sha256 TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN (
        'accepted','accepted_with_warning','rejected','quarantined'
    )),
    quality_issues_json TEXT NOT NULL DEFAULT '[]',
    injection_status TEXT NOT NULL DEFAULT 'clean' CHECK (injection_status IN (
        'clean','warning','quarantined','blocked'
    )),
    injection_reasons_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_set_id) REFERENCES rag_chunk_sets(id) ON DELETE CASCADE,
    FOREIGN KEY (source_version_id) REFERENCES rag_source_versions(id) ON DELETE RESTRICT,
    UNIQUE(chunk_set_id, sequence_number)
);
CREATE TABLE IF NOT EXISTS rag_embedding_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    provider_type TEXT NOT NULL CHECK (provider_type IN (
        'local_sentence_transformer','local_custom_embedding','deterministic_test_embedding'
    )),
    architecture TEXT NOT NULL DEFAULT '',
    dimensions INTEGER NOT NULL,
    maximum_input_tokens INTEGER NOT NULL,
    supported_languages_json TEXT NOT NULL DEFAULT '[]',
    artifact_checksum TEXT,
    configuration_checksum TEXT,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','validated','active','deprecated','archived','failed'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);
CREATE TABLE IF NOT EXISTS rag_embedding_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    chunk_set_id INTEGER NOT NULL,
    embedding_model_id INTEGER NOT NULL,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    total_chunks INTEGER NOT NULL DEFAULT 0,
    embedded_chunks INTEGER NOT NULL DEFAULT 0,
    failed_chunks INTEGER NOT NULL DEFAULT 0,
    dimensions INTEGER,
    runtime_milliseconds INTEGER,
    peak_memory_bytes INTEGER,
    input_checksum_sha256 TEXT,
    output_manifest_checksum_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed','cancelled'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (chunk_set_id) REFERENCES rag_chunk_sets(id) ON DELETE RESTRICT,
    FOREIGN KEY (embedding_model_id) REFERENCES rag_embedding_models(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_chunk_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    embedding_run_id INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    dimensions INTEGER NOT NULL,
    vector_norm REAL NOT NULL,
    vector_checksum_sha256 TEXT NOT NULL,
    vector_blob BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (embedding_run_id) REFERENCES rag_embedding_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES rag_chunks(id) ON DELETE RESTRICT,
    UNIQUE(embedding_run_id, chunk_id)
);
CREATE TABLE IF NOT EXISTS rag_vector_indexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    knowledge_space_id INTEGER NOT NULL,
    chunk_set_id INTEGER NOT NULL,
    embedding_run_id INTEGER NOT NULL,
    index_type TEXT NOT NULL DEFAULT 'repository_flat' CHECK (index_type IN (
        'faiss_flat','repository_flat'
    )),
    distance_metric TEXT NOT NULL DEFAULT 'cosine' CHECK (distance_metric IN (
        'cosine','inner_product','l2'
    )),
    dimensions INTEGER,
    vector_count INTEGER NOT NULL DEFAULT 0,
    index_artifact_checksum_sha256 TEXT,
    mapping_manifest_checksum_sha256 TEXT,
    storage_key TEXT,
    status TEXT NOT NULL DEFAULT 'building' CHECK (status IN (
        'building','validated','active','deprecated','failed','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TEXT,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id) ON DELETE RESTRICT,
    FOREIGN KEY (chunk_set_id) REFERENCES rag_chunk_sets(id) ON DELETE RESTRICT,
    FOREIGN KEY (embedding_run_id) REFERENCES rag_embedding_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_keyword_indexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    knowledge_space_id INTEGER NOT NULL,
    chunk_set_id INTEGER NOT NULL,
    index_type TEXT NOT NULL DEFAULT 'fts5' CHECK (index_type IN ('fts5','repository_inverted')),
    tokenizer_notes TEXT NOT NULL DEFAULT '',
    document_count INTEGER NOT NULL DEFAULT 0,
    index_artifact_checksum_sha256 TEXT,
    storage_key TEXT,
    status TEXT NOT NULL DEFAULT 'building' CHECK (status IN (
        'building','validated','active','deprecated','failed','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TEXT,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id) ON DELETE RESTRICT,
    FOREIGN KEY (chunk_set_id) REFERENCES rag_chunk_sets(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_retrieval_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    knowledge_space_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    vector_top_k INTEGER NOT NULL DEFAULT 20,
    keyword_top_k INTEGER NOT NULL DEFAULT 20,
    final_top_k INTEGER NOT NULL DEFAULT 5,
    vector_weight REAL NOT NULL DEFAULT 0.6,
    keyword_weight REAL NOT NULL DEFAULT 0.4,
    heading_boost REAL NOT NULL DEFAULT 0.05,
    exact_match_boost REAL NOT NULL DEFAULT 0.1,
    language_match_boost REAL NOT NULL DEFAULT 0.05,
    source_priority_json TEXT NOT NULL DEFAULT '{}',
    minimum_score REAL NOT NULL DEFAULT 0.15,
    deduplication_policy TEXT NOT NULL DEFAULT 'exact_only' CHECK (deduplication_policy IN (
        'exact_only','exact_and_near'
    )),
    diversity_policy TEXT NOT NULL DEFAULT 'none' CHECK (diversity_policy IN (
        'none','source_diversity'
    )),
    context_token_budget INTEGER NOT NULL DEFAULT 800,
    injection_filter_policy TEXT NOT NULL DEFAULT 'block' CHECK (injection_filter_policy IN (
        'block','quarantine','warn'
    )),
    no_answer_threshold REAL NOT NULL DEFAULT 0.2,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validated','active','archived')),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_retrieval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    retrieval_profile_id INTEGER NOT NULL,
    knowledge_space_id INTEGER NOT NULL,
    vector_index_id INTEGER,
    keyword_index_id INTEGER,
    normalized_query TEXT NOT NULL,
    query_checksum_sha256 TEXT NOT NULL,
    query_language TEXT NOT NULL DEFAULT 'unknown',
    filters_json TEXT NOT NULL DEFAULT '{}',
    top_k_configuration_json TEXT NOT NULL DEFAULT '{}',
    runtime_milliseconds INTEGER,
    total_candidates INTEGER NOT NULL DEFAULT 0,
    final_result_count INTEGER NOT NULL DEFAULT 0,
    no_answer_score REAL,
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed','no_results','failed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (retrieval_profile_id) REFERENCES rag_retrieval_profiles(id) ON DELETE RESTRICT,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id) ON DELETE RESTRICT,
    FOREIGN KEY (vector_index_id) REFERENCES rag_vector_indexes(id) ON DELETE RESTRICT,
    FOREIGN KEY (keyword_index_id) REFERENCES rag_keyword_indexes(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_retrieved_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    retrieval_run_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    source_version_id INTEGER NOT NULL,
    vector_score REAL,
    keyword_score REAL,
    combined_score REAL,
    rerank_score REAL,
    injection_status TEXT NOT NULL DEFAULT 'clean',
    filter_evidence_json TEXT NOT NULL DEFAULT '{}',
    selected_for_context INTEGER NOT NULL DEFAULT 0 CHECK (selected_for_context IN (0,1)),
    exclusion_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (retrieval_run_id) REFERENCES rag_retrieval_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES rag_chunks(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id) REFERENCES rag_knowledge_sources(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_version_id) REFERENCES rag_source_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_context_assemblies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    retrieval_run_id INTEGER NOT NULL,
    maximum_model_context INTEGER NOT NULL,
    prompt_template_tokens INTEGER NOT NULL DEFAULT 0,
    query_tokens INTEGER NOT NULL DEFAULT 0,
    retrieved_context_tokens INTEGER NOT NULL DEFAULT 0,
    reserved_output_tokens INTEGER NOT NULL DEFAULT 0,
    safety_margin_tokens INTEGER NOT NULL DEFAULT 0,
    dropped_chunk_count INTEGER NOT NULL DEFAULT 0,
    final_context_checksum_sha256 TEXT,
    citation_map_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (retrieval_run_id) REFERENCES rag_retrieval_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rag_grounded_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    context_assembly_id INTEGER,
    retrieval_run_id INTEGER NOT NULL,
    model_assignment_id INTEGER,
    scope TEXT NOT NULL DEFAULT 'admin_rag_lab',
    session_id INTEGER,
    query_checksum_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN (
        'accepted','completed','insufficient_evidence','retrieval_failed',
        'generation_failed','blocked_evidence'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (context_assembly_id) REFERENCES rag_context_assemblies(id) ON DELETE RESTRICT,
    FOREIGN KEY (retrieval_run_id) REFERENCES rag_retrieval_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE RESTRICT,
    FOREIGN KEY (session_id) REFERENCES inference_sessions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_grounded_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    grounded_request_id INTEGER NOT NULL,
    answer_status TEXT NOT NULL CHECK (answer_status IN (
        'grounded_answer','insufficient_evidence','retrieval_failed',
        'generation_failed','blocked_evidence'
    )),
    answer_checksum_sha256 TEXT,
    answer_language TEXT NOT NULL DEFAULT 'unknown',
    citation_count INTEGER NOT NULL DEFAULT 0,
    stop_reason TEXT,
    runtime_milliseconds INTEGER,
    role_token_leakage INTEGER NOT NULL DEFAULT 0 CHECK (role_token_leakage IN (0,1)),
    prompt_leakage INTEGER NOT NULL DEFAULT 0 CHECK (prompt_leakage IN (0,1)),
    unicode_valid INTEGER NOT NULL DEFAULT 1 CHECK (unicode_valid IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grounded_request_id) REFERENCES rag_grounded_requests(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rag_answer_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    grounded_answer_id INTEGER NOT NULL,
    citation_label TEXT NOT NULL,
    chunk_id INTEGER,
    source_id INTEGER,
    source_version_id INTEGER,
    rank INTEGER,
    content_checksum_sha256 TEXT,
    validation_status TEXT NOT NULL DEFAULT 'valid' CHECK (validation_status IN (
        'valid','valid_with_warning','invalid','not_present'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grounded_answer_id) REFERENCES rag_grounded_answers(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES rag_chunks(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id) REFERENCES rag_knowledge_sources(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_version_id) REFERENCES rag_source_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_grounding_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    grounded_request_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL CHECK (issue_code IN (
        'no_retrieval_results','retrieval_score_below_threshold','retrieval_filter_excluded_all',
        'only_quarantined_chunks','context_budget_exceeded','context_empty',
        'prompt_injection_chunk_detected','prompt_injection_chunk_included','unknown_citation',
        'citation_not_in_context','citation_checksum_mismatch','citation_access_forbidden',
        'unsupported_answer_claim','uncited_factual_claim','evidence_conflict',
        'answer_language_mismatch','role_token_leakage','prompt_leakage','generation_timeout',
        'generation_failed','retrieval_failed','index_mismatch','embedding_model_mismatch'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','blocking')),
    message TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grounded_request_id) REFERENCES rag_grounded_requests(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rag_evaluation_suites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    knowledge_space_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    evaluation_type TEXT NOT NULL DEFAULT 'both' CHECK (evaluation_type IN (
        'retrieval','generation','both'
    )),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','validated','active','archived')),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id) ON DELETE RESTRICT,
    UNIQUE(name, version)
);
CREATE TABLE IF NOT EXISTS rag_evaluation_fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_suite_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'unknown',
    expected_relevant_chunk_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_relevant_source_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_no_answer INTEGER NOT NULL DEFAULT 0 CHECK (expected_no_answer IN (0,1)),
    required_keywords_json TEXT NOT NULL DEFAULT '[]',
    forbidden_claims_json TEXT NOT NULL DEFAULT '[]',
    expected_answer_language TEXT,
    injection_test INTEGER NOT NULL DEFAULT 0 CHECK (injection_test IN (0,1)),
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','warning','blocking')),
    fixture_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_suite_id) REFERENCES rag_evaluation_suites(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rag_evaluation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_suite_id INTEGER NOT NULL,
    retrieval_profile_id INTEGER,
    model_assignment_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed'
    )),
    total_fixtures INTEGER NOT NULL DEFAULT 0,
    completed_fixtures INTEGER NOT NULL DEFAULT 0,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (evaluation_suite_id) REFERENCES rag_evaluation_suites(id) ON DELETE RESTRICT,
    FOREIGN KEY (retrieval_profile_id) REFERENCES rag_retrieval_profiles(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_evaluation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_run_id INTEGER NOT NULL,
    metric_scope TEXT NOT NULL CHECK (metric_scope IN ('retrieval','generation')),
    metric_name TEXT NOT NULL,
    metric_value REAL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_run_id) REFERENCES rag_evaluation_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rag_index_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    left_vector_index_id INTEGER,
    right_vector_index_id INTEGER,
    left_keyword_index_id INTEGER,
    right_keyword_index_id INTEGER,
    evaluation_suite_id INTEGER,
    compatibility TEXT NOT NULL CHECK (compatibility IN (
        'compatible','partially_compatible','incompatible'
    )),
    ranked INTEGER NOT NULL DEFAULT 0 CHECK (ranked IN (0,1)),
    fields_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (left_vector_index_id) REFERENCES rag_vector_indexes(id) ON DELETE RESTRICT,
    FOREIGN KEY (right_vector_index_id) REFERENCES rag_vector_indexes(id) ON DELETE RESTRICT,
    FOREIGN KEY (left_keyword_index_id) REFERENCES rag_keyword_indexes(id) ON DELETE RESTRICT,
    FOREIGN KEY (right_keyword_index_id) REFERENCES rag_keyword_indexes(id) ON DELETE RESTRICT,
    FOREIGN KEY (evaluation_suite_id) REFERENCES rag_evaluation_suites(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS rag_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    knowledge_space_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_knowledge_sources_space ON rag_knowledge_sources(knowledge_space_id,approval_status);
CREATE INDEX IF NOT EXISTS ix_rag_source_versions_source ON rag_source_versions(knowledge_source_id,version_number);
CREATE INDEX IF NOT EXISTS ix_rag_chunk_sets_source_version ON rag_chunk_sets(source_version_id);
CREATE INDEX IF NOT EXISTS ix_rag_chunks_chunk_set ON rag_chunks(chunk_set_id,quality_status);
CREATE INDEX IF NOT EXISTS ix_rag_chunks_injection ON rag_chunks(injection_status);
CREATE INDEX IF NOT EXISTS ix_rag_embedding_runs_chunk_set ON rag_embedding_runs(chunk_set_id,status);
CREATE INDEX IF NOT EXISTS ix_rag_chunk_embeddings_run ON rag_chunk_embeddings(embedding_run_id);
CREATE INDEX IF NOT EXISTS ix_rag_vector_indexes_space ON rag_vector_indexes(knowledge_space_id,status);
CREATE INDEX IF NOT EXISTS ix_rag_keyword_indexes_space ON rag_keyword_indexes(knowledge_space_id,status);
CREATE INDEX IF NOT EXISTS ix_rag_retrieval_profiles_space ON rag_retrieval_profiles(knowledge_space_id,status);
CREATE INDEX IF NOT EXISTS ix_rag_retrieval_runs_profile ON rag_retrieval_runs(retrieval_profile_id);
CREATE INDEX IF NOT EXISTS ix_rag_retrieved_chunks_run ON rag_retrieved_chunks(retrieval_run_id,rank);
CREATE INDEX IF NOT EXISTS ix_rag_context_assemblies_run ON rag_context_assemblies(retrieval_run_id);
CREATE INDEX IF NOT EXISTS ix_rag_grounded_requests_status ON rag_grounded_requests(status);
CREATE INDEX IF NOT EXISTS ix_rag_grounded_answers_request ON rag_grounded_answers(grounded_request_id);
CREATE INDEX IF NOT EXISTS ix_rag_answer_citations_answer ON rag_answer_citations(grounded_answer_id);
CREATE INDEX IF NOT EXISTS ix_rag_grounding_issues_request ON rag_grounding_issues(grounded_request_id,severity);
CREATE INDEX IF NOT EXISTS ix_rag_evaluation_fixtures_suite ON rag_evaluation_fixtures(evaluation_suite_id);
CREATE INDEX IF NOT EXISTS ix_rag_evaluation_runs_suite ON rag_evaluation_runs(evaluation_suite_id,status);
CREATE INDEX IF NOT EXISTS ix_rag_evaluation_metrics_run ON rag_evaluation_metrics(evaluation_run_id,metric_scope);
CREATE INDEX IF NOT EXISTS ix_rag_index_comparisons_suite ON rag_index_comparisons(evaluation_suite_id);
CREATE INDEX IF NOT EXISTS ix_rag_manifests_space ON rag_manifests(knowledge_space_id);
CREATE TRIGGER IF NOT EXISTS rag_chunks_immutable_update BEFORE UPDATE ON rag_chunks BEGIN SELECT RAISE(ABORT, 'chunks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_chunks_immutable_delete BEFORE DELETE ON rag_chunks BEGIN SELECT RAISE(ABORT, 'chunks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_chunk_embeddings_immutable_update BEFORE UPDATE ON rag_chunk_embeddings BEGIN SELECT RAISE(ABORT, 'chunk embeddings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_chunk_embeddings_immutable_delete BEFORE DELETE ON rag_chunk_embeddings BEGIN SELECT RAISE(ABORT, 'chunk embeddings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_retrieval_runs_immutable_update BEFORE UPDATE ON rag_retrieval_runs BEGIN SELECT RAISE(ABORT, 'retrieval runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_retrieval_runs_immutable_delete BEFORE DELETE ON rag_retrieval_runs BEGIN SELECT RAISE(ABORT, 'retrieval runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_retrieved_chunks_immutable_update BEFORE UPDATE ON rag_retrieved_chunks BEGIN SELECT RAISE(ABORT, 'retrieved chunks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_retrieved_chunks_immutable_delete BEFORE DELETE ON rag_retrieved_chunks BEGIN SELECT RAISE(ABORT, 'retrieved chunks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_context_assemblies_immutable_update BEFORE UPDATE ON rag_context_assemblies BEGIN SELECT RAISE(ABORT, 'context assemblies are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_context_assemblies_immutable_delete BEFORE DELETE ON rag_context_assemblies BEGIN SELECT RAISE(ABORT, 'context assemblies are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_grounded_answers_immutable_update BEFORE UPDATE ON rag_grounded_answers BEGIN SELECT RAISE(ABORT, 'grounded answers are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_grounded_answers_immutable_delete BEFORE DELETE ON rag_grounded_answers BEGIN SELECT RAISE(ABORT, 'grounded answers are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_answer_citations_immutable_update BEFORE UPDATE ON rag_answer_citations BEGIN SELECT RAISE(ABORT, 'answer citations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_answer_citations_immutable_delete BEFORE DELETE ON rag_answer_citations BEGIN SELECT RAISE(ABORT, 'answer citations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_grounding_issues_immutable_update BEFORE UPDATE ON rag_grounding_issues BEGIN SELECT RAISE(ABORT, 'grounding issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_grounding_issues_immutable_delete BEFORE DELETE ON rag_grounding_issues BEGIN SELECT RAISE(ABORT, 'grounding issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_evaluation_fixtures_immutable_update BEFORE UPDATE ON rag_evaluation_fixtures BEGIN SELECT RAISE(ABORT, 'evaluation fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_evaluation_fixtures_immutable_delete BEFORE DELETE ON rag_evaluation_fixtures BEGIN SELECT RAISE(ABORT, 'evaluation fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_evaluation_metrics_immutable_update BEFORE UPDATE ON rag_evaluation_metrics BEGIN SELECT RAISE(ABORT, 'evaluation metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_evaluation_metrics_immutable_delete BEFORE DELETE ON rag_evaluation_metrics BEGIN SELECT RAISE(ABORT, 'evaluation metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_index_comparisons_immutable_update BEFORE UPDATE ON rag_index_comparisons BEGIN SELECT RAISE(ABORT, 'index comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_index_comparisons_immutable_delete BEFORE DELETE ON rag_index_comparisons BEGIN SELECT RAISE(ABORT, 'index comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_manifests_immutable_update BEFORE UPDATE ON rag_manifests BEGIN SELECT RAISE(ABORT, 'rag manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_manifests_immutable_delete BEFORE DELETE ON rag_manifests BEGIN SELECT RAISE(ABORT, 'rag manifests are append-only'); END;
"""

MIGRATION_017_NAME = "017_phase17_conversation_memory"

# Phase 17 stores conversation/memory ownership as a plain
# `participant_scope_key` TEXT column (e.g. "admin:<admin_public_id>" or
# "test:<label>") on `conversation_sessions`, `memory_consents`, and
# `memory_items`, rather than a foreign key to
# `conversation_session_participants`. A FK-based design would be
# circular (a session's owning participant row would itself need to
# reference the session), and the simple string-match boundary is also
# the safer, more auditable choice for the single security-critical
# check this phase depends on most: "one participant's memory is never
# retrieved by another." `conversation_session_participants` is a
# secondary table for tracking additional/observer participants attached
# to a session; it is never the source of truth for memory ownership.
#
# `memory_evaluation_runs` is classified MUTABLE here, not append-only
# as a literal reading of the table list might suggest, for the exact
# same reason already documented for `rag_embedding_runs`/
# `rag_evaluation_runs` in Phase 16 (see schema v16's note above): the
# required API surface has an explicit two-phase create-then-execute
# flow (`POST .../runs` creates a `draft` row, `POST
# .../runs/{id}/execute` must update it to a terminal status), which is
# fundamentally incompatible with an append-only trigger. This was
# learned from Phase 16's `rag_grounded_requests` bug (an append-only
# table that needed a post-creation status update) and is applied
# proactively here rather than discovered again the hard way.
#
# `chat_orchestration_runs` and `chat_grounded_responses` avoid that
# same trap differently: both are inserted exactly once, at the very
# end of `ChatOrchestrationService.send_message()`'s synchronous flow,
# only after the final status is already known -- never created early
# with a placeholder status and updated afterward. This keeps them
# genuinely append-only without needing a second schema-level
# exception.
PHASE17_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_memory_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    default_session_mode TEXT NOT NULL DEFAULT 'private_no_persist' CHECK (default_session_mode IN (
        'stateless','session_memory','consented_memory','private_no_persist'
    )),
    allow_short_term_context INTEGER NOT NULL DEFAULT 1,
    allow_session_summary INTEGER NOT NULL DEFAULT 1,
    allow_long_term_memory INTEGER NOT NULL DEFAULT 0,
    require_explicit_consent INTEGER NOT NULL DEFAULT 1,
    maximum_session_turns INTEGER NOT NULL DEFAULT 20,
    maximum_session_age_seconds INTEGER NOT NULL DEFAULT 3600,
    maximum_short_term_tokens INTEGER NOT NULL DEFAULT 800,
    maximum_summary_tokens INTEGER NOT NULL DEFAULT 200,
    maximum_memory_items INTEGER NOT NULL DEFAULT 50,
    default_memory_ttl_seconds INTEGER NOT NULL DEFAULT 7776000,
    allowed_memory_categories_json TEXT NOT NULL DEFAULT '[]',
    forbidden_content_categories_json TEXT NOT NULL DEFAULT '[]',
    retrieval_configuration_json TEXT NOT NULL DEFAULT '{}',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','validated','active','deprecated','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_mode TEXT NOT NULL CHECK (session_mode IN (
        'stateless','session_memory','consented_memory','private_no_persist'
    )),
    memory_policy_id INTEGER NOT NULL,
    participant_scope_key TEXT NOT NULL,
    language_preference TEXT NOT NULL DEFAULT 'unknown',
    model_assignment_id INTEGER,
    rag_retrieval_profile_id INTEGER,
    turn_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','active','paused','expired','closed','failed','archived'
    )),
    failure_code TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    closed_at TEXT,
    FOREIGN KEY (memory_policy_id) REFERENCES conversation_memory_policies(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE RESTRICT,
    FOREIGN KEY (rag_retrieval_profile_id) REFERENCES rag_retrieval_profiles(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS conversation_session_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    participant_type TEXT NOT NULL CHECK (participant_type IN (
        'admin','internal_test_user','future_user_reference'
    )),
    participant_scope_key TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'primary' CHECK (role IN ('primary','observer')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','removed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('system','user','assistant')),
    language_category TEXT NOT NULL DEFAULT 'unknown',
    content_checksum_sha256 TEXT NOT NULL,
    stored_content TEXT,
    token_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted','rejected')),
    redaction_status TEXT NOT NULL DEFAULT 'none' CHECK (redaction_status IN ('none','redacted')),
    parent_turn_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, sequence_number),
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE RESTRICT,
    FOREIGN KEY (parent_turn_id) REFERENCES conversation_turns(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS conversation_turn_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    turn_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (turn_id) REFERENCES conversation_turns(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    current_version_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validated','accepted','rejected','superseded'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE RESTRICT,
    FOREIGN KEY (current_version_id) REFERENCES conversation_summary_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS conversation_summary_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    summary_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    source_turn_start_sequence INTEGER NOT NULL,
    source_turn_end_sequence INTEGER NOT NULL,
    summary_language TEXT NOT NULL DEFAULT 'unknown',
    summary_text_checksum_sha256 TEXT NOT NULL,
    summary_text TEXT,
    summary_token_count INTEGER NOT NULL DEFAULT 0,
    generation_method TEXT NOT NULL CHECK (generation_method IN (
        'deterministic_extract','bounded_model_summary','hybrid'
    )),
    validation_status TEXT NOT NULL DEFAULT 'draft' CHECK (validation_status IN (
        'draft','validated','accepted','rejected','superseded'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(summary_id, version_number),
    FOREIGN KEY (summary_id) REFERENCES conversation_summaries(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    participant_scope_key TEXT NOT NULL,
    memory_policy_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    allowed_categories_json TEXT NOT NULL DEFAULT '[]',
    prohibited_categories_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','active','expired','revoked','rejected'
    )),
    granted_at TEXT,
    expires_at TEXT,
    revoked_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_policy_id) REFERENCES conversation_memory_policies(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    participant_scope_key TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'language_preference','format_preference','confirmed_name_or_alias',
        'learning_goal','course_progress','project_preference',
        'user_confirmed_fact','conversation_follow_up'
    )),
    purpose TEXT NOT NULL,
    creation_source TEXT NOT NULL CHECK (creation_source IN (
        'explicit_user_request','admin_created_for_test','assistant_proposed','system_derived'
    )),
    confidence_type TEXT NOT NULL CHECK (confidence_type IN (
        'user_confirmed','admin_test_fixture','deterministically_extracted','assistant_inferred'
    )),
    consent_id INTEGER,
    source_session_id INTEGER,
    source_turn_id INTEGER,
    current_version_id INTEGER,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN (
        'proposed','awaiting_confirmation','active','superseded','expired',
        'revoked','rejected','deleted','archived'
    )),
    valid_from TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consent_id) REFERENCES memory_consents(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_session_id) REFERENCES conversation_sessions(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_turn_id) REFERENCES conversation_turns(id) ON DELETE RESTRICT,
    FOREIGN KEY (current_version_id) REFERENCES memory_item_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_item_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    memory_item_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    normalized_value TEXT NOT NULL,
    display_value TEXT NOT NULL,
    source_reference TEXT NOT NULL DEFAULT '',
    change_reason TEXT NOT NULL DEFAULT 'initial_creation',
    checksum_sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(memory_item_id, version_number),
    FOREIGN KEY (memory_item_id) REFERENCES memory_items(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_item_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    memory_item_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_item_id) REFERENCES memory_items(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    memory_item_version_id INTEGER NOT NULL,
    embedding_model_id INTEGER NOT NULL,
    content_checksum_sha256 TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector_blob BLOB NOT NULL,
    vector_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_item_version_id) REFERENCES memory_item_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (embedding_model_id) REFERENCES rag_embedding_models(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_retrieval_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    allowed_categories_json TEXT NOT NULL DEFAULT '[]',
    allowed_purposes_json TEXT NOT NULL DEFAULT '[]',
    keyword_weight REAL NOT NULL DEFAULT 0.4,
    vector_weight REAL NOT NULL DEFAULT 0.6,
    recency_weight REAL NOT NULL DEFAULT 0.1,
    user_confirmed_boost REAL NOT NULL DEFAULT 0.2,
    maximum_results INTEGER NOT NULL DEFAULT 5,
    minimum_score REAL NOT NULL DEFAULT 0.15,
    maximum_memory_tokens INTEGER NOT NULL DEFAULT 200,
    conflict_policy TEXT NOT NULL DEFAULT 'prefer_recent' CHECK (conflict_policy IN (
        'prefer_recent','prefer_user_confirmed','exclude_conflicting'
    )),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validated','active','deprecated','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS memory_retrieval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    retrieval_profile_id INTEGER NOT NULL,
    participant_scope_key TEXT NOT NULL,
    query_checksum_sha256 TEXT NOT NULL,
    query_language TEXT NOT NULL DEFAULT 'unknown',
    total_candidates INTEGER NOT NULL DEFAULT 0,
    final_result_count INTEGER NOT NULL DEFAULT 0,
    runtime_milliseconds INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed','no_results')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (retrieval_profile_id) REFERENCES memory_retrieval_profiles(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_retrieval_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    retrieval_run_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    memory_item_id INTEGER NOT NULL,
    keyword_score REAL,
    vector_score REAL,
    recency_score REAL,
    combined_score REAL NOT NULL,
    conflict_status TEXT NOT NULL DEFAULT 'no_conflict' CHECK (conflict_status IN (
        'no_conflict','duplicate','supersedes_existing','conflict_requires_confirmation','stale_existing'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (retrieval_run_id) REFERENCES memory_retrieval_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (memory_item_id) REFERENCES memory_items(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chat_context_assemblies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    maximum_model_context INTEGER NOT NULL,
    system_tokens INTEGER NOT NULL DEFAULT 0,
    current_request_tokens INTEGER NOT NULL DEFAULT 0,
    conversation_tokens INTEGER NOT NULL DEFAULT 0,
    summary_tokens INTEGER NOT NULL DEFAULT 0,
    memory_tokens INTEGER NOT NULL DEFAULT 0,
    rag_tokens INTEGER NOT NULL DEFAULT 0,
    reserved_output_tokens INTEGER NOT NULL DEFAULT 0,
    dropped_item_count INTEGER NOT NULL DEFAULT 0,
    final_context_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chat_context_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    context_assembly_id INTEGER NOT NULL,
    item_type TEXT NOT NULL CHECK (item_type IN (
        'conversation_turn','conversation_summary','memory_item','rag_chunk',
        'system_instruction','current_request'
    )),
    source_public_id TEXT,
    rank INTEGER NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    included INTEGER NOT NULL DEFAULT 1,
    exclusion_reason TEXT,
    content_checksum_sha256 TEXT,
    access_verified INTEGER NOT NULL DEFAULT 1,
    injection_status TEXT NOT NULL DEFAULT 'clean' CHECK (injection_status IN (
        'clean','warning','quarantined','blocked'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (context_assembly_id) REFERENCES chat_context_assemblies(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chat_orchestration_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    request_turn_id INTEGER NOT NULL,
    memory_retrieval_run_id INTEGER,
    rag_retrieval_run_id INTEGER,
    context_assembly_id INTEGER,
    status TEXT NOT NULL CHECK (status IN (
        'completed','completed_with_warning','insufficient_evidence','memory_conflict',
        'consent_required','retrieval_failed','generation_failed','blocked_context','session_closed'
    )),
    language_decision TEXT NOT NULL DEFAULT 'unknown',
    runtime_milliseconds INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE RESTRICT,
    FOREIGN KEY (request_turn_id) REFERENCES conversation_turns(id) ON DELETE RESTRICT,
    FOREIGN KEY (memory_retrieval_run_id) REFERENCES memory_retrieval_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (rag_retrieval_run_id) REFERENCES rag_retrieval_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (context_assembly_id) REFERENCES chat_context_assemblies(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chat_grounded_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    orchestration_run_id INTEGER NOT NULL,
    response_turn_id INTEGER,
    answer_status TEXT NOT NULL CHECK (answer_status IN (
        'completed','completed_with_warning','insufficient_evidence','memory_conflict',
        'consent_required','retrieval_failed','generation_failed','blocked_context','session_closed'
    )),
    answer_checksum_sha256 TEXT,
    answer_language TEXT NOT NULL DEFAULT 'unknown',
    memory_used INTEGER NOT NULL DEFAULT 0,
    stop_reason TEXT,
    runtime_milliseconds INTEGER NOT NULL DEFAULT 0,
    role_token_leakage INTEGER NOT NULL DEFAULT 0,
    prompt_leakage INTEGER NOT NULL DEFAULT 0,
    unicode_valid INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (orchestration_run_id) REFERENCES chat_orchestration_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (response_turn_id) REFERENCES conversation_turns(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chat_response_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    grounded_response_id INTEGER NOT NULL,
    citation_label TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('rag_chunk','memory_item')),
    rag_chunk_id INTEGER,
    memory_item_id INTEGER,
    rank INTEGER,
    content_checksum_sha256 TEXT,
    validation_status TEXT NOT NULL CHECK (validation_status IN (
        'valid','valid_with_warning','invalid','not_present'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (grounded_response_id) REFERENCES chat_grounded_responses(id) ON DELETE RESTRICT,
    FOREIGN KEY (rag_chunk_id) REFERENCES rag_chunks(id) ON DELETE RESTRICT,
    FOREIGN KEY (memory_item_id) REFERENCES memory_items(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS chat_orchestration_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    orchestration_run_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('info','warning','error','critical')),
    message TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (orchestration_run_id) REFERENCES chat_orchestration_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_evaluation_suites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validated','active','retired','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS memory_evaluation_fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_suite_id INTEGER NOT NULL,
    participant_scope_key TEXT NOT NULL,
    session_mode TEXT NOT NULL,
    query TEXT NOT NULL,
    query_language TEXT NOT NULL DEFAULT 'unknown',
    expected_retrieved_memory_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_excluded_memory_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_language TEXT,
    expected_rag_use INTEGER NOT NULL DEFAULT 0,
    expected_no_memory_behavior INTEGER NOT NULL DEFAULT 0,
    expected_response_status TEXT,
    injection_test INTEGER NOT NULL DEFAULT 0,
    severity TEXT NOT NULL DEFAULT 'info',
    fixture_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_suite_id) REFERENCES memory_evaluation_suites(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_evaluation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_suite_id INTEGER NOT NULL,
    retrieval_profile_id INTEGER,
    total_fixtures INTEGER NOT NULL DEFAULT 0,
    completed_fixtures INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (evaluation_suite_id) REFERENCES memory_evaluation_suites(id) ON DELETE RESTRICT,
    FOREIGN KEY (retrieval_profile_id) REFERENCES memory_retrieval_profiles(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS memory_evaluation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_run_id INTEGER NOT NULL,
    metric_scope TEXT NOT NULL CHECK (metric_scope IN ('retrieval','orchestration')),
    metric_name TEXT NOT NULL,
    metric_value REAL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_run_id) REFERENCES memory_evaluation_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS conversation_memory_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    memory_policy_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (memory_policy_id) REFERENCES conversation_memory_policies(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_conversation_sessions_participant ON conversation_sessions(participant_scope_key);
CREATE INDEX IF NOT EXISTS ix_conversation_sessions_status ON conversation_sessions(status);
CREATE INDEX IF NOT EXISTS ix_conversation_session_participants_session ON conversation_session_participants(session_id);
CREATE INDEX IF NOT EXISTS ix_conversation_turns_session ON conversation_turns(session_id, sequence_number);
CREATE INDEX IF NOT EXISTS ix_conversation_turn_events_turn ON conversation_turn_events(turn_id);
CREATE INDEX IF NOT EXISTS ix_conversation_summaries_session ON conversation_summaries(session_id);
CREATE INDEX IF NOT EXISTS ix_conversation_summary_versions_summary ON conversation_summary_versions(summary_id);
CREATE INDEX IF NOT EXISTS ix_memory_consents_participant ON memory_consents(participant_scope_key, status);
CREATE INDEX IF NOT EXISTS ix_memory_items_participant ON memory_items(participant_scope_key, status);
CREATE INDEX IF NOT EXISTS ix_memory_items_category ON memory_items(category, purpose);
CREATE INDEX IF NOT EXISTS ix_memory_item_versions_item ON memory_item_versions(memory_item_id);
CREATE INDEX IF NOT EXISTS ix_memory_item_events_item ON memory_item_events(memory_item_id);
CREATE INDEX IF NOT EXISTS ix_memory_embeddings_version ON memory_embeddings(memory_item_version_id);
CREATE INDEX IF NOT EXISTS ix_memory_retrieval_runs_participant ON memory_retrieval_runs(participant_scope_key);
CREATE INDEX IF NOT EXISTS ix_memory_retrieval_results_run ON memory_retrieval_results(retrieval_run_id, rank);
CREATE INDEX IF NOT EXISTS ix_chat_context_items_assembly ON chat_context_items(context_assembly_id, rank);
CREATE INDEX IF NOT EXISTS ix_chat_orchestration_runs_session ON chat_orchestration_runs(session_id);
CREATE INDEX IF NOT EXISTS ix_chat_grounded_responses_run ON chat_grounded_responses(orchestration_run_id);
CREATE INDEX IF NOT EXISTS ix_chat_response_citations_response ON chat_response_citations(grounded_response_id);
CREATE INDEX IF NOT EXISTS ix_chat_orchestration_issues_run ON chat_orchestration_issues(orchestration_run_id, severity);
CREATE INDEX IF NOT EXISTS ix_memory_evaluation_fixtures_suite ON memory_evaluation_fixtures(evaluation_suite_id);
CREATE INDEX IF NOT EXISTS ix_memory_evaluation_runs_suite ON memory_evaluation_runs(evaluation_suite_id, status);
CREATE INDEX IF NOT EXISTS ix_memory_evaluation_metrics_run ON memory_evaluation_metrics(evaluation_run_id, metric_scope);
CREATE INDEX IF NOT EXISTS ix_conversation_memory_manifests_policy ON conversation_memory_manifests(memory_policy_id);
CREATE TRIGGER IF NOT EXISTS conversation_turns_immutable_update BEFORE UPDATE ON conversation_turns BEGIN SELECT RAISE(ABORT, 'conversation turns are append-only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_turns_immutable_delete BEFORE DELETE ON conversation_turns BEGIN SELECT RAISE(ABORT, 'conversation turns are append-only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_turn_events_immutable_update BEFORE UPDATE ON conversation_turn_events BEGIN SELECT RAISE(ABORT, 'conversation turn events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_turn_events_immutable_delete BEFORE DELETE ON conversation_turn_events BEGIN SELECT RAISE(ABORT, 'conversation turn events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_summary_versions_immutable_update BEFORE UPDATE ON conversation_summary_versions BEGIN SELECT RAISE(ABORT, 'summary versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_summary_versions_immutable_delete BEFORE DELETE ON conversation_summary_versions BEGIN SELECT RAISE(ABORT, 'summary versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_item_versions_immutable_update BEFORE UPDATE ON memory_item_versions BEGIN SELECT RAISE(ABORT, 'memory item versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_item_versions_immutable_delete BEFORE DELETE ON memory_item_versions BEGIN SELECT RAISE(ABORT, 'memory item versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_item_events_immutable_update BEFORE UPDATE ON memory_item_events BEGIN SELECT RAISE(ABORT, 'memory item events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_item_events_immutable_delete BEFORE DELETE ON memory_item_events BEGIN SELECT RAISE(ABORT, 'memory item events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_embeddings_immutable_update BEFORE UPDATE ON memory_embeddings BEGIN SELECT RAISE(ABORT, 'memory embeddings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_embeddings_immutable_delete BEFORE DELETE ON memory_embeddings BEGIN SELECT RAISE(ABORT, 'memory embeddings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_retrieval_runs_immutable_update BEFORE UPDATE ON memory_retrieval_runs BEGIN SELECT RAISE(ABORT, 'memory retrieval runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_retrieval_runs_immutable_delete BEFORE DELETE ON memory_retrieval_runs BEGIN SELECT RAISE(ABORT, 'memory retrieval runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_retrieval_results_immutable_update BEFORE UPDATE ON memory_retrieval_results BEGIN SELECT RAISE(ABORT, 'memory retrieval results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_retrieval_results_immutable_delete BEFORE DELETE ON memory_retrieval_results BEGIN SELECT RAISE(ABORT, 'memory retrieval results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_context_assemblies_immutable_update BEFORE UPDATE ON chat_context_assemblies BEGIN SELECT RAISE(ABORT, 'context assemblies are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_context_assemblies_immutable_delete BEFORE DELETE ON chat_context_assemblies BEGIN SELECT RAISE(ABORT, 'context assemblies are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_context_items_immutable_update BEFORE UPDATE ON chat_context_items BEGIN SELECT RAISE(ABORT, 'context items are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_context_items_immutable_delete BEFORE DELETE ON chat_context_items BEGIN SELECT RAISE(ABORT, 'context items are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_orchestration_runs_immutable_update BEFORE UPDATE ON chat_orchestration_runs BEGIN SELECT RAISE(ABORT, 'orchestration runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_orchestration_runs_immutable_delete BEFORE DELETE ON chat_orchestration_runs BEGIN SELECT RAISE(ABORT, 'orchestration runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_grounded_responses_immutable_update BEFORE UPDATE ON chat_grounded_responses BEGIN SELECT RAISE(ABORT, 'grounded responses are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_grounded_responses_immutable_delete BEFORE DELETE ON chat_grounded_responses BEGIN SELECT RAISE(ABORT, 'grounded responses are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_response_citations_immutable_update BEFORE UPDATE ON chat_response_citations BEGIN SELECT RAISE(ABORT, 'response citations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_response_citations_immutable_delete BEFORE DELETE ON chat_response_citations BEGIN SELECT RAISE(ABORT, 'response citations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_orchestration_issues_immutable_update BEFORE UPDATE ON chat_orchestration_issues BEGIN SELECT RAISE(ABORT, 'orchestration issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS chat_orchestration_issues_immutable_delete BEFORE DELETE ON chat_orchestration_issues BEGIN SELECT RAISE(ABORT, 'orchestration issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_evaluation_fixtures_immutable_update BEFORE UPDATE ON memory_evaluation_fixtures BEGIN SELECT RAISE(ABORT, 'evaluation fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_evaluation_fixtures_immutable_delete BEFORE DELETE ON memory_evaluation_fixtures BEGIN SELECT RAISE(ABORT, 'evaluation fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_evaluation_metrics_immutable_update BEFORE UPDATE ON memory_evaluation_metrics BEGIN SELECT RAISE(ABORT, 'evaluation metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_evaluation_metrics_immutable_delete BEFORE DELETE ON memory_evaluation_metrics BEGIN SELECT RAISE(ABORT, 'evaluation metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_memory_manifests_immutable_update BEFORE UPDATE ON conversation_memory_manifests BEGIN SELECT RAISE(ABORT, 'conversation memory manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS conversation_memory_manifests_immutable_delete BEFORE DELETE ON conversation_memory_manifests BEGIN SELECT RAISE(ABORT, 'conversation memory manifests are append-only'); END;
"""

MIGRATION_018_NAME = "018_phase18_feedback_learning_loop"

# Phase 18 stores a feedback event's subject lineage as one immutable
# snapshot row (`feedback_subjects`) created before the event itself,
# holding only public-ID references and checksums for whichever of the
# 7 subject types (inference_result, rag_grounded_answer,
# conversation_response, evaluation_output,
# memory_orchestration_response, release_candidate, model_release) the
# feedback is about -- never a dozen mostly-null FK columns, and never
# raw hidden system prompts or private content. `subject_type` +
# `subject_reference_public_id` is validated against the real owning
# table at the service layer (never an arbitrary string or filesystem
# reference), matching the "resolve to an existing public entity"
# requirement without needing a polymorphic FK (SQLite has none).
#
# Two deviations from a literal reading of the spec's append-only
# table list, both following the exact precedent already established
# in Phase 16 (`rag_grounded_requests`, `rag_evaluation_runs`) and
# Phase 17 (`memory_evaluation_runs`): a genuine two-phase
# create-then-transition API flow is incompatible with an append-only
# trigger, so is classified mutable here proactively instead of
# discovered again the hard way.
#
#   * `feedback_corrected_responses`: created `draft`, then
#     `POST .../validate` or `POST .../reject` must update the same
#     row's `validation_status` (and a later correction for the same
#     feedback event flips the prior row to `superseded`). This never
#     touches the original model output -- that stays an immutable
#     checksum on `feedback_subjects.output_checksum_sha256` --  only
#     the correction proposal's own lifecycle is mutable.
#   * `feedback_regression_runs`: `POST .../runs` creates a `draft`
#     row, `POST .../execute` must update it to a terminal status.
#     `feedback_regression_results` (the per-fixture pass/fail
#     evidence) and `feedback_model_comparisons` (a single computed
#     comparison, never re-executed in place) remain genuinely
#     append-only.
#
# `feedback_candidate_approvals` stays append-only by construction:
# each approval decision is one fully-formed row inserted exactly once
# (mirrors `rag_answer_citations`); a stale approval is detected by
# comparing its stored `candidate_version_id` snapshot against the
# candidate's current version at read time, never by mutating the old
# approval row.
PHASE18_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    allowed_subject_types_json TEXT NOT NULL DEFAULT '[]',
    allowed_feedback_types_json TEXT NOT NULL DEFAULT '[]',
    allow_free_text INTEGER NOT NULL DEFAULT 1 CHECK (allow_free_text IN (0,1)),
    allow_corrected_response INTEGER NOT NULL DEFAULT 1 CHECK (allow_corrected_response IN (0,1)),
    require_privacy_scan INTEGER NOT NULL DEFAULT 1 CHECK (require_privacy_scan IN (0,1)),
    require_safety_scan INTEGER NOT NULL DEFAULT 1 CHECK (require_safety_scan IN (0,1)),
    require_human_review INTEGER NOT NULL DEFAULT 1 CHECK (require_human_review IN (0,1)),
    require_dataset_approval INTEGER NOT NULL DEFAULT 1 CHECK (require_dataset_approval IN (0,1)),
    maximum_feedback_characters INTEGER NOT NULL DEFAULT 2000 CHECK (maximum_feedback_characters > 0),
    maximum_attachment_bytes INTEGER NOT NULL DEFAULT 2000000 CHECK (maximum_attachment_bytes >= 0),
    default_retention_seconds INTEGER NOT NULL DEFAULT 7776000 CHECK (default_retention_seconds >= 0),
    allow_regression_fixture_creation INTEGER NOT NULL DEFAULT 1 CHECK (allow_regression_fixture_creation IN (0,1)),
    allow_dataset_candidate_creation INTEGER NOT NULL DEFAULT 1 CHECK (allow_dataset_candidate_creation IN (0,1)),
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','validated','active','deprecated','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS feedback_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL CHECK (subject_type IN (
        'inference_result','rag_grounded_answer','conversation_response',
        'evaluation_output','memory_orchestration_response','release_candidate','model_release'
    )),
    subject_reference_public_id TEXT NOT NULL,
    model_release_public_id TEXT,
    model_version_public_id TEXT,
    checkpoint_checksum_sha256 TEXT,
    tokenizer_version_public_id TEXT,
    assignment_version_public_id TEXT,
    generation_configuration_json TEXT NOT NULL DEFAULT '{}',
    rag_retrieval_run_public_id TEXT,
    citation_public_ids_json TEXT NOT NULL DEFAULT '[]',
    memory_item_public_ids_json TEXT NOT NULL DEFAULT '[]',
    conversation_session_public_id TEXT,
    evaluation_suite_public_id TEXT,
    evaluation_run_public_id TEXT,
    output_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_policy_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    participant_scope_key TEXT NOT NULL,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN (
        'thumbs_up','thumbs_down','rating','issue_report','correction',
        'citation_report','safety_report','language_report','memory_report','retrieval_report'
    )),
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    comment_text TEXT,
    comment_checksum_sha256 TEXT,
    suggested_correction_text TEXT,
    suggested_correction_checksum_sha256 TEXT,
    expected_language TEXT,
    expected_citation_reference TEXT,
    expected_retrieval_source_reference TEXT,
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','low','medium','high','critical')),
    status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN (
        'submitted','triaged','in_review','reviewed','candidate_created',
        'resolved','rejected','expired','deleted','archived'
    )),
    privacy_status TEXT NOT NULL DEFAULT 'requires_review' CHECK (privacy_status IN (
        'safe','redacted','requires_review','blocked'
    )),
    safety_status TEXT NOT NULL DEFAULT 'requires_review' CHECK (safety_status IN (
        'safe','flagged','blocked','requires_review'
    )),
    retention_expires_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triaged_at TEXT,
    resolved_at TEXT,
    deleted_at TEXT,
    FOREIGN KEY (feedback_policy_id) REFERENCES feedback_policies(id) ON DELETE RESTRICT,
    FOREIGN KEY (subject_id) REFERENCES feedback_subjects(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_event_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'helpful','unhelpful','incorrect','partially_correct','unsupported_claim',
        'hallucination_like','wrong_language','poor_tamil','poor_tanglish','format_failure',
        'instruction_not_followed','citation_missing','citation_invalid','citation_wrong',
        'retrieval_irrelevant','retrieval_missing','unsafe_response','over_refusal',
        'under_refusal','prompt_leakage','role_token_leakage','repetition','memory_wrong',
        'memory_outdated','memory_privacy_issue','memory_not_used','memory_should_not_be_used',
        'too_long','too_short','unclear','other'
    )),
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','low','medium','high','critical')),
    assigned_by TEXT NOT NULL DEFAULT 'admin' CHECK (assigned_by IN ('system','admin')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_event_id INTEGER NOT NULL,
    attachment_type TEXT NOT NULL DEFAULT 'excerpt',
    checksum_sha256 TEXT NOT NULL,
    byte_size INTEGER NOT NULL DEFAULT 0 CHECK (byte_size >= 0),
    mime_type TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_review_queues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    queue_type TEXT NOT NULL CHECK (queue_type IN (
        'general_quality','language','tamil_quality','tanglish_quality','citation','retrieval',
        'safety','privacy','memory','dataset_candidate','regression'
    )),
    description TEXT NOT NULL DEFAULT '',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN ('draft','active','archived')),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS feedback_review_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    queue_id INTEGER NOT NULL,
    feedback_event_id INTEGER NOT NULL,
    reviewer_admin_public_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_at TEXT,
    status TEXT NOT NULL DEFAULT 'assigned' CHECK (status IN (
        'assigned','in_progress','completed','reassigned','cancelled','expired'
    )),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('info','low','medium','high','critical')),
    conflict_of_interest_flag INTEGER NOT NULL DEFAULT 0 CHECK (conflict_of_interest_flag IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (queue_id) REFERENCES feedback_review_queues(id) ON DELETE RESTRICT,
    FOREIGN KEY (feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_event_id INTEGER NOT NULL,
    reviewer_admin_public_id TEXT NOT NULL,
    rubric_version TEXT NOT NULL DEFAULT '1',
    classification_confirmed TEXT,
    severity_confirmed TEXT CHECK (severity_confirmed IS NULL OR severity_confirmed IN (
        'info','low','medium','high','critical'
    )),
    correctness_score INTEGER CHECK (correctness_score IS NULL OR correctness_score BETWEEN 1 AND 5),
    relevance_score INTEGER CHECK (relevance_score IS NULL OR relevance_score BETWEEN 1 AND 5),
    language_quality_score INTEGER CHECK (language_quality_score IS NULL OR language_quality_score BETWEEN 1 AND 5),
    safety_score INTEGER CHECK (safety_score IS NULL OR safety_score BETWEEN 1 AND 5),
    citation_score INTEGER CHECK (citation_score IS NULL OR citation_score BETWEEN 1 AND 5),
    retrieval_score INTEGER CHECK (retrieval_score IS NULL OR retrieval_score BETWEEN 1 AND 5),
    memory_use_score INTEGER CHECK (memory_use_score IS NULL OR memory_use_score BETWEEN 1 AND 5),
    overall_score INTEGER NOT NULL CHECK (overall_score BETWEEN 1 AND 5),
    verdict TEXT NOT NULL CHECK (verdict IN (
        'valid_feedback','partially_valid','invalid_feedback','needs_second_review',
        'privacy_blocked','safety_blocked','candidate_recommended','regression_recommended'
    )),
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_corrected_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_event_id INTEGER NOT NULL,
    original_output_checksum_sha256 TEXT NOT NULL,
    corrected_response_text TEXT NOT NULL,
    corrected_response_checksum_sha256 TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'unknown',
    citation_map_json TEXT NOT NULL DEFAULT '[]',
    memory_use_policy TEXT NOT NULL DEFAULT 'none' CHECK (memory_use_policy IN (
        'none','reference_existing','propose_new'
    )),
    validation_status TEXT NOT NULL DEFAULT 'draft' CHECK (validation_status IN (
        'draft','validated','validated_with_warnings','rejected','superseded'
    )),
    validation_issues_json TEXT NOT NULL DEFAULT '[]',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    validated_at TEXT,
    FOREIGN KEY (feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_privacy_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_event_id INTEGER,
    candidate_id INTEGER,
    category TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('safe','redacted','requires_review','blocked')),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_id) REFERENCES feedback_dataset_candidates(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_safety_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_event_id INTEGER,
    candidate_id INTEGER,
    category TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('safe','flagged','blocked')),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_id) REFERENCES feedback_dataset_candidates(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_quality_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    dimension TEXT NOT NULL CHECK (dimension IN (
        'clarity','correctness_support','instruction_quality','response_quality',
        'language_quality','format_quality','safety_quality','citation_quality',
        'provenance_completeness','licence_completeness','privacy_safety',
        'deduplication','contamination_safety'
    )),
    status TEXT NOT NULL DEFAULT 'not_assessed' CHECK (status IN ('pass','warning','fail','not_assessed')),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES feedback_dataset_candidates(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_dataset_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_feedback_event_id INTEGER NOT NULL,
    source_subject_id INTEGER NOT NULL,
    source_corrected_response_id INTEGER,
    candidate_type TEXT NOT NULL CHECK (candidate_type IN (
        'instruction','chat','translation','tanglish_pair','safety','preference','evaluation_only'
    )),
    failed_model_version_public_id TEXT,
    current_version_id INTEGER,
    privacy_status TEXT NOT NULL DEFAULT 'requires_review' CHECK (privacy_status IN (
        'safe','redacted','requires_review','blocked'
    )),
    safety_status TEXT NOT NULL DEFAULT 'requires_review' CHECK (safety_status IN (
        'safe','flagged','blocked','requires_review'
    )),
    licence_status TEXT NOT NULL DEFAULT 'unknown' CHECK (licence_status IN (
        'approved','restricted','unknown','blocked','not_applicable'
    )),
    deduplication_status TEXT NOT NULL DEFAULT 'unique' CHECK (deduplication_status IN (
        'unique','exact_duplicate','normalized_duplicate','near_duplicate',
        'prompt_duplicate','response_duplicate','prompt_response_duplicate'
    )),
    contamination_status TEXT NOT NULL DEFAULT 'clean' CHECK (contamination_status IN (
        'clean','training_duplicate','validation_leakage','test_leakage',
        'evaluation_fixture_leakage','regression_fixture_leakage',
        'subject_output_copy','hidden_prompt_leakage'
    )),
    intended_use TEXT NOT NULL DEFAULT 'training_candidate',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validating','review_required','approved','approved_with_warnings',
        'rejected','quarantined','exported','archived'
    )),
    exported_dataset_record_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_feedback_event_id) REFERENCES feedback_events(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_subject_id) REFERENCES feedback_subjects(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_corrected_response_id) REFERENCES feedback_corrected_responses(id) ON DELETE RESTRICT,
    FOREIGN KEY (current_version_id) REFERENCES feedback_candidate_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_candidate_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    input_text TEXT,
    output_text TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'unknown',
    prompt_checksum_sha256 TEXT NOT NULL,
    output_checksum_sha256 TEXT NOT NULL,
    metadata_checksum_sha256 TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(candidate_id, version_number),
    FOREIGN KEY (candidate_id) REFERENCES feedback_dataset_candidates(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_candidate_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('info','low','medium','high','critical')),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES feedback_dataset_candidates(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_candidate_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    candidate_version_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN (
        'approve','approve_with_warning','reject','request_changes','quarantine'
    )),
    review_evidence_checksum_sha256 TEXT,
    privacy_assessment TEXT NOT NULL,
    safety_assessment TEXT NOT NULL,
    deduplication_result TEXT NOT NULL,
    contamination_result TEXT NOT NULL,
    licence_result TEXT NOT NULL,
    intended_use_decision TEXT NOT NULL DEFAULT 'training_candidate',
    admin_public_id TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES feedback_dataset_candidates(id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_version_id) REFERENCES feedback_candidate_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_regression_suites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','validated','active','retired','archived'
    )),
    checksum_sha256 TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS feedback_regression_fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    suite_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'language_regression','tamil_quality_regression','tanglish_regression',
        'instruction_following_regression','citation_regression','retrieval_regression',
        'safety_regression','memory_regression','privacy_regression','format_regression',
        'repetition_regression'
    )),
    language TEXT NOT NULL DEFAULT 'unknown',
    input_text TEXT NOT NULL,
    controlled_context_json TEXT NOT NULL DEFAULT '{}',
    expected_behavior TEXT NOT NULL,
    forbidden_behavior TEXT,
    expected_citations_json TEXT NOT NULL DEFAULT '[]',
    expected_memory_behavior_json TEXT NOT NULL DEFAULT '{}',
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('info','low','medium','high','critical')),
    source_feedback_event_ids_json TEXT NOT NULL DEFAULT '[]',
    checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (suite_id) REFERENCES feedback_regression_suites(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_regression_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    suite_id INTEGER NOT NULL,
    model_assignment_id INTEGER NOT NULL,
    generation_configuration_checksum_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','queued','running','completed','failed'
    )),
    started_at TEXT,
    ended_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (suite_id) REFERENCES feedback_regression_suites(id) ON DELETE RESTRICT,
    FOREIGN KEY (model_assignment_id) REFERENCES inference_model_assignments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_regression_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    run_id INTEGER NOT NULL,
    fixture_id INTEGER NOT NULL,
    passed INTEGER NOT NULL CHECK (passed IN (0,1)),
    failure_reason TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES feedback_regression_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (fixture_id) REFERENCES feedback_regression_fixtures(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_model_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    regression_suite_id INTEGER NOT NULL,
    left_run_id INTEGER NOT NULL,
    right_run_id INTEGER NOT NULL,
    compatibility TEXT NOT NULL CHECK (compatibility IN ('compatible','partially_compatible','incompatible')),
    comparison_result TEXT NOT NULL CHECK (comparison_result IN (
        'improved','mixed','unchanged','regressed','incomparable'
    )),
    fixed_failure_rate REAL,
    persistent_failure_rate REAL,
    new_regression_rate REAL,
    language_regression_rate REAL,
    citation_regression_rate REAL,
    safety_regression_rate REAL,
    memory_regression_rate REAL,
    privacy_regression_rate REAL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (regression_suite_id) REFERENCES feedback_regression_suites(id) ON DELETE RESTRICT,
    FOREIGN KEY (left_run_id) REFERENCES feedback_regression_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (right_run_id) REFERENCES feedback_regression_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_improvement_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_policy_id INTEGER,
    regression_run_id INTEGER,
    comparison_id INTEGER,
    report_json TEXT NOT NULL,
    report_checksum_sha256 TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_policy_id) REFERENCES feedback_policies(id) ON DELETE RESTRICT,
    FOREIGN KEY (regression_run_id) REFERENCES feedback_regression_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (comparison_id) REFERENCES feedback_model_comparisons(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS feedback_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    feedback_policy_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_policy_id) REFERENCES feedback_policies(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_feedback_events_subject ON feedback_events(subject_id);
CREATE INDEX IF NOT EXISTS ix_feedback_events_participant ON feedback_events(participant_scope_key);
CREATE INDEX IF NOT EXISTS ix_feedback_events_status ON feedback_events(status);
CREATE INDEX IF NOT EXISTS ix_feedback_classifications_event ON feedback_classifications(feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_attachments_event ON feedback_attachments(feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_review_assignments_queue ON feedback_review_assignments(queue_id, status);
CREATE INDEX IF NOT EXISTS ix_feedback_review_assignments_event ON feedback_review_assignments(feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_human_reviews_event ON feedback_human_reviews(feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_corrected_responses_event ON feedback_corrected_responses(feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_privacy_findings_event ON feedback_privacy_findings(feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_privacy_findings_candidate ON feedback_privacy_findings(candidate_id);
CREATE INDEX IF NOT EXISTS ix_feedback_safety_findings_event ON feedback_safety_findings(feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_safety_findings_candidate ON feedback_safety_findings(candidate_id);
CREATE INDEX IF NOT EXISTS ix_feedback_quality_assessments_candidate ON feedback_quality_assessments(candidate_id);
CREATE INDEX IF NOT EXISTS ix_feedback_dataset_candidates_event ON feedback_dataset_candidates(source_feedback_event_id);
CREATE INDEX IF NOT EXISTS ix_feedback_dataset_candidates_status ON feedback_dataset_candidates(status);
CREATE INDEX IF NOT EXISTS ix_feedback_candidate_versions_candidate ON feedback_candidate_versions(candidate_id);
CREATE INDEX IF NOT EXISTS ix_feedback_candidate_issues_candidate ON feedback_candidate_issues(candidate_id);
CREATE INDEX IF NOT EXISTS ix_feedback_candidate_approvals_candidate ON feedback_candidate_approvals(candidate_id);
CREATE INDEX IF NOT EXISTS ix_feedback_regression_fixtures_suite ON feedback_regression_fixtures(suite_id);
CREATE INDEX IF NOT EXISTS ix_feedback_regression_runs_suite ON feedback_regression_runs(suite_id, status);
CREATE INDEX IF NOT EXISTS ix_feedback_regression_results_run ON feedback_regression_results(run_id);
CREATE INDEX IF NOT EXISTS ix_feedback_model_comparisons_suite ON feedback_model_comparisons(regression_suite_id);
CREATE INDEX IF NOT EXISTS ix_feedback_manifests_policy ON feedback_manifests(feedback_policy_id);
CREATE TRIGGER IF NOT EXISTS feedback_subjects_immutable_update BEFORE UPDATE ON feedback_subjects BEGIN SELECT RAISE(ABORT, 'feedback subjects are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_subjects_immutable_delete BEFORE DELETE ON feedback_subjects BEGIN SELECT RAISE(ABORT, 'feedback subjects are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_classifications_immutable_update BEFORE UPDATE ON feedback_classifications BEGIN SELECT RAISE(ABORT, 'feedback classifications are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_classifications_immutable_delete BEFORE DELETE ON feedback_classifications BEGIN SELECT RAISE(ABORT, 'feedback classifications are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_attachments_immutable_update BEFORE UPDATE ON feedback_attachments BEGIN SELECT RAISE(ABORT, 'feedback attachments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_attachments_immutable_delete BEFORE DELETE ON feedback_attachments BEGIN SELECT RAISE(ABORT, 'feedback attachments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_human_reviews_immutable_update BEFORE UPDATE ON feedback_human_reviews BEGIN SELECT RAISE(ABORT, 'human reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_human_reviews_immutable_delete BEFORE DELETE ON feedback_human_reviews BEGIN SELECT RAISE(ABORT, 'human reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_privacy_findings_immutable_update BEFORE UPDATE ON feedback_privacy_findings BEGIN SELECT RAISE(ABORT, 'privacy findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_privacy_findings_immutable_delete BEFORE DELETE ON feedback_privacy_findings BEGIN SELECT RAISE(ABORT, 'privacy findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_safety_findings_immutable_update BEFORE UPDATE ON feedback_safety_findings BEGIN SELECT RAISE(ABORT, 'safety findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_safety_findings_immutable_delete BEFORE DELETE ON feedback_safety_findings BEGIN SELECT RAISE(ABORT, 'safety findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_quality_assessments_immutable_update BEFORE UPDATE ON feedback_quality_assessments BEGIN SELECT RAISE(ABORT, 'quality assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_quality_assessments_immutable_delete BEFORE DELETE ON feedback_quality_assessments BEGIN SELECT RAISE(ABORT, 'quality assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_candidate_versions_immutable_update BEFORE UPDATE ON feedback_candidate_versions BEGIN SELECT RAISE(ABORT, 'candidate versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_candidate_versions_immutable_delete BEFORE DELETE ON feedback_candidate_versions BEGIN SELECT RAISE(ABORT, 'candidate versions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_candidate_issues_immutable_update BEFORE UPDATE ON feedback_candidate_issues BEGIN SELECT RAISE(ABORT, 'candidate issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_candidate_issues_immutable_delete BEFORE DELETE ON feedback_candidate_issues BEGIN SELECT RAISE(ABORT, 'candidate issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_candidate_approvals_immutable_update BEFORE UPDATE ON feedback_candidate_approvals BEGIN SELECT RAISE(ABORT, 'candidate approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_candidate_approvals_immutable_delete BEFORE DELETE ON feedback_candidate_approvals BEGIN SELECT RAISE(ABORT, 'candidate approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_regression_fixtures_immutable_update BEFORE UPDATE ON feedback_regression_fixtures BEGIN SELECT RAISE(ABORT, 'regression fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_regression_fixtures_immutable_delete BEFORE DELETE ON feedback_regression_fixtures BEGIN SELECT RAISE(ABORT, 'regression fixtures are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_regression_results_immutable_update BEFORE UPDATE ON feedback_regression_results BEGIN SELECT RAISE(ABORT, 'regression results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_regression_results_immutable_delete BEFORE DELETE ON feedback_regression_results BEGIN SELECT RAISE(ABORT, 'regression results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_model_comparisons_immutable_update BEFORE UPDATE ON feedback_model_comparisons BEGIN SELECT RAISE(ABORT, 'model comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_model_comparisons_immutable_delete BEFORE DELETE ON feedback_model_comparisons BEGIN SELECT RAISE(ABORT, 'model comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_improvement_reports_immutable_update BEFORE UPDATE ON feedback_improvement_reports BEGIN SELECT RAISE(ABORT, 'improvement reports are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_improvement_reports_immutable_delete BEFORE DELETE ON feedback_improvement_reports BEGIN SELECT RAISE(ABORT, 'improvement reports are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_manifests_immutable_update BEFORE UPDATE ON feedback_manifests BEGIN SELECT RAISE(ABORT, 'feedback manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS feedback_manifests_immutable_delete BEFORE DELETE ON feedback_manifests BEGIN SELECT RAISE(ABORT, 'feedback manifests are append-only'); END;
"""

