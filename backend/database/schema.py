"""Initial SQLite schema for Brud AI Phase 1."""

SCHEMA_VERSION = 44

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

MIGRATION_019_NAME = "019_phase19_tamil_corpus_builder"

# Phase 19 reuses Phase 3's `dataset_sources`/`dataset_records`/
# `dataset_versions` and Phase 5's `document_sources`/`document_pages`
# unchanged as source-of-truth for already-registered/already-extracted
# content -- `corpus_source_registries` never duplicates them, it only
# ever references their public IDs (`origin_reference_public_id`) plus
# its own licence/provenance/quality layer on top. A `document_record`
# or `dataset_version` corpus source is extracted via
# `dataset_record_projection` (projecting already-extracted text
# straight out of the existing tables) rather than a second PDF/OCR
# pipeline.
#
# Unlike Phase 16/17/18, this phase's own spec already correctly
# pre-classifies every two-phase create-then-execute table
# (`corpus_extraction_runs`, `corpus_normalization_runs`,
# `corpus_deduplication_runs`, `corpus_contamination_runs`,
# `corpus_exports`) as mutable, so no literal-reading deviation is
# needed here the way it was in every prior phase.
#
# `corpus_quality_assessments`/`corpus_privacy_findings`/
# `corpus_safety_findings` use a polymorphic
# `subject_type` + `subject_reference_public_id` pair (never a raw FK)
# because quality/privacy/safety are assessed at five different
# levels (source, document, segment, collection, build) -- the same
# pattern already used for `feedback_subjects` in Phase 18.
#
# `corpus_source_registries` deliberately has no `licence_id` column:
# a source and its licence review are genuinely circular (a source
# references its licence, but a licence review always needs to
# reference the source it is reviewing), so `corpus_source_licences`
# is one-directional (`source_id -> corpus_source_registries.id`
# only), and the "current" licence for a source is always resolved by
# querying the latest `corpus_source_licences` row for that source
# rather than a stored pointer -- the same circular-FK-avoidance
# reasoning Phase 17 used for `participant_scope_key`.
PHASE19_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    supported_languages_json TEXT NOT NULL DEFAULT '["ta","en","tgl","mixed"]',
    allowed_source_types_json TEXT NOT NULL DEFAULT '[]',
    allowed_licence_statuses_json TEXT NOT NULL DEFAULT '["approved","approved_with_conditions"]',
    require_verified_origin INTEGER NOT NULL DEFAULT 1 CHECK (require_verified_origin IN (0,1)),
    require_licence_review INTEGER NOT NULL DEFAULT 1 CHECK (require_licence_review IN (0,1)),
    require_privacy_scan INTEGER NOT NULL DEFAULT 1 CHECK (require_privacy_scan IN (0,1)),
    require_safety_scan INTEGER NOT NULL DEFAULT 1 CHECK (require_safety_scan IN (0,1)),
    require_quality_assessment INTEGER NOT NULL DEFAULT 1 CHECK (require_quality_assessment IN (0,1)),
    require_deduplication INTEGER NOT NULL DEFAULT 1 CHECK (require_deduplication IN (0,1)),
    require_contamination_check INTEGER NOT NULL DEFAULT 1 CHECK (require_contamination_check IN (0,1)),
    maximum_source_bytes INTEGER NOT NULL DEFAULT 200000000 CHECK (maximum_source_bytes > 0),
    maximum_document_characters INTEGER NOT NULL DEFAULT 2000000 CHECK (maximum_document_characters > 0),
    maximum_segment_characters INTEGER NOT NULL DEFAULT 8000 CHECK (maximum_segment_characters > 0),
    minimum_segment_characters INTEGER NOT NULL DEFAULT 100 CHECK (minimum_segment_characters > 0),
    default_retention_seconds INTEGER NOT NULL DEFAULT 31536000 CHECK (default_retention_seconds >= 0),
    export_format_policy_json TEXT NOT NULL DEFAULT '{"formats":["jsonl"]}',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','validated','active','deprecated','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_source_registries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    corpus_policy_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'uploaded_pdf','uploaded_text','uploaded_markdown','uploaded_html_snapshot',
        'dataset_version','document_record','feedback_candidate_export','manual_admin_text',
        'public_domain_book','government_publication','educational_material','dictionary',
        'grammar_reference','parallel_corpus','conversation_corpus','tanglish_pair_corpus',
        'faq_collection'
    )),
    author_or_organisation TEXT,
    publisher TEXT,
    original_publication_date TEXT,
    source_reference TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'unknown',
    domain TEXT NOT NULL DEFAULT 'general',
    ownership_claim TEXT NOT NULL DEFAULT 'unknown',
    origin_reference_public_id TEXT,
    intended_use TEXT NOT NULL DEFAULT 'pretraining_corpus',
    content_checksum_sha256 TEXT,
    origin_verified INTEGER NOT NULL DEFAULT 0 CHECK (origin_verified IN (0,1)),
    origin_evidence TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','origin_review','licence_review','approved','approved_with_restrictions',
        'rejected','quarantined','disputed','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (corpus_policy_id) REFERENCES corpus_policies(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_source_licences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_id INTEGER NOT NULL,
    licence_family TEXT NOT NULL CHECK (licence_family IN (
        'public_domain','cc0','cc_by','cc_by_sa','government_open_data','organisation_owned',
        'user_owned_with_permission','custom_permissive','research_only','non_commercial',
        'all_rights_reserved','unknown'
    )),
    licence_name TEXT,
    licence_version TEXT,
    licence_text_reference TEXT,
    copyright_holder TEXT,
    allowed_uses_json TEXT NOT NULL DEFAULT '[]',
    prohibited_uses_json TEXT NOT NULL DEFAULT '[]',
    attribution_required INTEGER NOT NULL DEFAULT 0 CHECK (attribution_required IN (0,1)),
    share_alike_required INTEGER NOT NULL DEFAULT 0 CHECK (share_alike_required IN (0,1)),
    commercial_use_permitted INTEGER NOT NULL DEFAULT 0 CHECK (commercial_use_permitted IN (0,1)),
    modification_permitted INTEGER NOT NULL DEFAULT 0 CHECK (modification_permitted IN (0,1)),
    ai_training_permitted INTEGER NOT NULL DEFAULT 0 CHECK (ai_training_permitted IN (0,1)),
    redistribution_permitted INTEGER NOT NULL DEFAULT 0 CHECK (redistribution_permitted IN (0,1)),
    evidence_type TEXT NOT NULL DEFAULT 'admin_asserted',
    reviewer_admin_public_id TEXT,
    review_status TEXT NOT NULL DEFAULT 'unknown' CHECK (review_status IN (
        'approved','approved_with_conditions','restricted','unknown','blocked','disputed',
        'expired','not_applicable'
    )),
    review_notes TEXT NOT NULL DEFAULT '',
    valid_from TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES corpus_source_registries(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    source_checksum_sha256 TEXT NOT NULL,
    file_inventory_checksum_sha256 TEXT NOT NULL,
    total_bytes INTEGER NOT NULL DEFAULT 0 CHECK (total_bytes >= 0),
    total_files INTEGER NOT NULL DEFAULT 0 CHECK (total_files >= 0),
    status TEXT NOT NULL DEFAULT 'creating' CHECK (status IN (
        'creating','ready','failed','superseded','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, version_number),
    FOREIGN KEY (source_id) REFERENCES corpus_source_registries(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    snapshot_id INTEGER NOT NULL,
    logical_filename TEXT NOT NULL,
    safe_relative_storage_key TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    checksum_sha256 TEXT NOT NULL,
    page_count INTEGER,
    character_estimate INTEGER,
    extraction_eligible INTEGER NOT NULL DEFAULT 1 CHECK (extraction_eligible IN (0,1)),
    status TEXT NOT NULL DEFAULT 'registered' CHECK (status IN (
        'registered','verified','rejected'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES corpus_source_snapshots(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_extraction_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    snapshot_id INTEGER NOT NULL,
    extraction_method TEXT NOT NULL CHECK (extraction_method IN (
        'embedded_pdf_text','tesseract_ocr','plain_text','markdown_text','html_snapshot_text',
        'dataset_record_projection','manual_content'
    )),
    extraction_version TEXT NOT NULL DEFAULT 'v1',
    ocr_language_configuration TEXT NOT NULL DEFAULT 'tam+eng',
    files_processed INTEGER NOT NULL DEFAULT 0 CHECK (files_processed >= 0),
    documents_created INTEGER NOT NULL DEFAULT 0 CHECK (documents_created >= 0),
    failed_files INTEGER NOT NULL DEFAULT 0 CHECK (failed_files >= 0),
    runtime_milliseconds INTEGER,
    input_checksum_sha256 TEXT,
    output_manifest_checksum_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed','cancelled'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES corpus_source_snapshots(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_extracted_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    extraction_run_id INTEGER NOT NULL,
    source_file_id INTEGER NOT NULL,
    document_sequence INTEGER NOT NULL,
    raw_text TEXT NOT NULL DEFAULT '',
    raw_text_checksum_sha256 TEXT NOT NULL,
    page_or_section_range TEXT,
    extraction_confidence REAL CHECK (extraction_confidence IS NULL OR extraction_confidence BETWEEN 0 AND 1),
    ocr_used INTEGER NOT NULL DEFAULT 0 CHECK (ocr_used IN (0,1)),
    language_estimate TEXT NOT NULL DEFAULT 'unknown',
    character_count INTEGER NOT NULL DEFAULT 0 CHECK (character_count >= 0),
    issue_summary_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (extraction_run_id) REFERENCES corpus_extraction_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_file_id) REFERENCES corpus_source_files(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_normalization_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    extraction_run_id INTEGER NOT NULL,
    normalization_version TEXT NOT NULL DEFAULT 'v1',
    documents_processed INTEGER NOT NULL DEFAULT 0 CHECK (documents_processed >= 0),
    transformation_summary_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed','cancelled'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (extraction_run_id) REFERENCES corpus_extraction_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_normalized_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    normalization_run_id INTEGER NOT NULL,
    extracted_document_id INTEGER NOT NULL,
    normalized_text TEXT NOT NULL DEFAULT '',
    normalized_text_checksum_sha256 TEXT NOT NULL,
    unicode_integrity_status TEXT NOT NULL DEFAULT 'unknown' CHECK (unicode_integrity_status IN (
        'valid','mojibake_detected','replacement_characters_detected','invalid_utf8','unknown'
    )),
    ocr_corrections_applied INTEGER NOT NULL DEFAULT 0 CHECK (ocr_corrections_applied >= 0),
    boilerplate_removals_applied INTEGER NOT NULL DEFAULT 0 CHECK (boilerplate_removals_applied >= 0),
    transformation_counts_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (normalization_run_id) REFERENCES corpus_normalization_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (extracted_document_id) REFERENCES corpus_extracted_documents(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    normalized_document_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    segmentation_strategy TEXT NOT NULL CHECK (segmentation_strategy IN (
        'paragraph','sentence_group','heading_section','record_based',
        'fixed_character_window','fixed_token_estimate_window'
    )),
    heading_hierarchy_json TEXT NOT NULL DEFAULT '[]',
    text TEXT NOT NULL,
    text_checksum_sha256 TEXT NOT NULL,
    character_count INTEGER NOT NULL CHECK (character_count > 0),
    sentence_count INTEGER NOT NULL DEFAULT 0 CHECK (sentence_count >= 0),
    token_estimate INTEGER NOT NULL DEFAULT 0 CHECK (token_estimate >= 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','excluded','deleted')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(normalized_document_id, sequence_number),
    FOREIGN KEY (normalized_document_id) REFERENCES corpus_normalized_documents(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_segment_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    segment_id INTEGER NOT NULL,
    location_type TEXT NOT NULL DEFAULT 'character_range' CHECK (location_type IN (
        'character_range','page_range','line_range'
    )),
    range_start INTEGER NOT NULL DEFAULT 0,
    range_end INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_language_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    segment_id INTEGER NOT NULL,
    language_category TEXT NOT NULL CHECK (language_category IN (
        'ta','en','tgl','mixed','numeric','code','unknown'
    )),
    tamil_script_ratio REAL NOT NULL DEFAULT 0,
    latin_script_ratio REAL NOT NULL DEFAULT 0,
    digit_ratio REAL NOT NULL DEFAULT 0,
    symbol_ratio REAL NOT NULL DEFAULT 0,
    tamil_lexical_evidence REAL NOT NULL DEFAULT 0,
    tanglish_lexical_evidence REAL NOT NULL DEFAULT 0,
    mixed_language_evidence REAL NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0,
    unsupported_character_ratio REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_domain_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    segment_id INTEGER NOT NULL,
    primary_domain TEXT NOT NULL CHECK (primary_domain IN (
        'general','education','literature','grammar','dictionary','conversation','translation',
        'government','history','science','mathematics','technology','agriculture','business',
        'health_general','law_general','religion_cultural','children','faq','safety','code','other'
    )),
    secondary_domains_json TEXT NOT NULL DEFAULT '[]',
    rule_evidence_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0,
    classifier_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_style_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    segment_id INTEGER NOT NULL,
    style TEXT NOT NULL CHECK (style IN (
        'formal','conversational','instructional','narrative','reference','question_answer',
        'dialogue','translation_pair','dictionary_entry','poetry','code_mixed','technical',
        'administrative'
    )),
    confidence REAL NOT NULL DEFAULT 0,
    classifier_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_quality_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL CHECK (subject_type IN (
        'source','document','segment','collection','build'
    )),
    subject_reference_public_id TEXT NOT NULL,
    dimension TEXT NOT NULL CHECK (dimension IN (
        'unicode_integrity','tamil_integrity','ocr_quality','sentence_completeness',
        'language_confidence','content_density','boilerplate_ratio','duplicate_risk',
        'privacy_safety','safety_quality','licence_completeness','provenance_completeness',
        'domain_value','style_value','length_quality','readability','format_integrity'
    )),
    status TEXT NOT NULL DEFAULT 'not_assessed' CHECK (status IN ('pass','warning','fail','not_assessed')),
    score REAL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    quality_assessment_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('info','low','medium','high','critical')),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quality_assessment_id) REFERENCES corpus_quality_assessments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_privacy_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    segment_id INTEGER,
    category TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('safe','redacted','requires_review','blocked')),
    redaction_action TEXT,
    finding_count INTEGER NOT NULL DEFAULT 1 CHECK (finding_count >= 0),
    detector_version TEXT NOT NULL DEFAULT 'v1',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_safety_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    segment_id INTEGER,
    category TEXT NOT NULL,
    behavior_class TEXT NOT NULL DEFAULT 'descriptive' CHECK (behavior_class IN (
        'descriptive','educational','historical','preventive','operational_harmful'
    )),
    status TEXT NOT NULL CHECK (status IN ('safe','flagged','blocked','requires_review')),
    detector_version TEXT NOT NULL DEFAULT 'v1',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_deduplication_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    scope_description TEXT NOT NULL DEFAULT '',
    near_duplicate_method TEXT NOT NULL DEFAULT 'character_ngram_jaccard' CHECK (near_duplicate_method IN (
        'minhash','simhash','character_ngram_jaccard','token_ngram_jaccard'
    )),
    near_duplicate_threshold REAL NOT NULL DEFAULT 0.85,
    segments_scanned INTEGER NOT NULL DEFAULT 0 CHECK (segments_scanned >= 0),
    exact_duplicate_count INTEGER NOT NULL DEFAULT 0 CHECK (exact_duplicate_count >= 0),
    near_duplicate_count INTEGER NOT NULL DEFAULT 0 CHECK (near_duplicate_count >= 0),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed','cancelled'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_duplicate_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    deduplication_run_id INTEGER NOT NULL,
    cluster_type TEXT NOT NULL CHECK (cluster_type IN (
        'exact_duplicate','normalized_duplicate','near_duplicate'
    )),
    representative_segment_public_id TEXT NOT NULL,
    representative_selection_reason TEXT NOT NULL DEFAULT '',
    member_count INTEGER NOT NULL DEFAULT 0 CHECK (member_count >= 0),
    action TEXT NOT NULL DEFAULT 'keep_representative' CHECK (action IN (
        'keep_representative','exclude_duplicate','keep_both_with_reason','quarantine_cluster',
        'manual_review'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deduplication_run_id) REFERENCES corpus_deduplication_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_duplicate_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    cluster_id INTEGER NOT NULL,
    segment_id INTEGER NOT NULL,
    similarity_score REAL NOT NULL DEFAULT 1.0,
    is_representative INTEGER NOT NULL DEFAULT 0 CHECK (is_representative IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cluster_id) REFERENCES corpus_duplicate_clusters(id) ON DELETE RESTRICT,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_contamination_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    scope_description TEXT NOT NULL DEFAULT '',
    segments_scanned INTEGER NOT NULL DEFAULT 0 CHECK (segments_scanned >= 0),
    findings_count INTEGER NOT NULL DEFAULT 0 CHECK (findings_count >= 0),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed','cancelled'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_contamination_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    contamination_run_id INTEGER NOT NULL,
    segment_id INTEGER NOT NULL,
    issue_type TEXT NOT NULL CHECK (issue_type IN (
        'training_duplicate','validation_leakage','test_leakage','evaluation_fixture_leakage',
        'regression_fixture_leakage','holdout_leakage','hidden_prompt_leakage'
    )),
    matched_reference TEXT,
    blocks_training INTEGER NOT NULL DEFAULT 1 CHECK (blocks_training IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (contamination_run_id) REFERENCES corpus_contamination_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    intended_use TEXT NOT NULL DEFAULT 'pretraining_corpus',
    language_policy_json TEXT NOT NULL DEFAULT '{}',
    domain_policy_json TEXT NOT NULL DEFAULT '{}',
    style_policy_json TEXT NOT NULL DEFAULT '{}',
    licence_policy_json TEXT NOT NULL DEFAULT '{}',
    quality_policy_json TEXT NOT NULL DEFAULT '{}',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','validated','active','deprecated','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_collection_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    collection_id INTEGER NOT NULL,
    segment_id INTEGER NOT NULL,
    eligibility_status TEXT NOT NULL DEFAULT 'eligible' CHECK (eligibility_status IN (
        'eligible','ineligible'
    )),
    inclusion_reason TEXT NOT NULL DEFAULT '',
    exclusion_reason TEXT,
    licence_status TEXT NOT NULL DEFAULT 'unknown',
    quality_status TEXT NOT NULL DEFAULT 'not_assessed',
    duplicate_status TEXT NOT NULL DEFAULT 'unique',
    contamination_status TEXT NOT NULL DEFAULT 'clean',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES corpus_collections(id) ON DELETE RESTRICT,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_balance_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    language_targets_json TEXT NOT NULL DEFAULT '{}',
    domain_targets_json TEXT NOT NULL DEFAULT '{}',
    style_targets_json TEXT NOT NULL DEFAULT '{}',
    source_type_targets_json TEXT NOT NULL DEFAULT '{}',
    licence_family_targets_json TEXT NOT NULL DEFAULT '{}',
    content_length_targets_json TEXT NOT NULL DEFAULT '{}',
    quality_band_targets_json TEXT NOT NULL DEFAULT '{}',
    maximum_single_source_share REAL NOT NULL DEFAULT 0.3,
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','validated','active','deprecated','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    corpus_policy_id INTEGER NOT NULL,
    balance_policy_id INTEGER NOT NULL,
    deduplication_run_id INTEGER,
    contamination_run_id INTEGER,
    collection_ids_json TEXT NOT NULL DEFAULT '[]',
    partition_configuration_json TEXT NOT NULL DEFAULT '{"train":0.98,"validation":0.01,"test":0.01,"seed":42}',
    export_policy_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validating','ready','building','completed','completed_with_warnings','failed',
        'cancelled','archived'
    )),
    included_segment_count INTEGER NOT NULL DEFAULT 0 CHECK (included_segment_count >= 0),
    excluded_segment_count INTEGER NOT NULL DEFAULT 0 CHECK (excluded_segment_count >= 0),
    failure_code TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (corpus_policy_id) REFERENCES corpus_policies(id) ON DELETE RESTRICT,
    FOREIGN KEY (balance_policy_id) REFERENCES corpus_balance_policies(id) ON DELETE RESTRICT,
    FOREIGN KEY (deduplication_run_id) REFERENCES corpus_deduplication_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (contamination_run_id) REFERENCES corpus_contamination_runs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_build_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_id INTEGER NOT NULL,
    segment_id INTEGER NOT NULL,
    collection_id INTEGER NOT NULL,
    selection_rank INTEGER NOT NULL DEFAULT 0,
    balance_bucket TEXT NOT NULL DEFAULT '',
    inclusion_weight REAL NOT NULL DEFAULT 1.0,
    included INTEGER NOT NULL DEFAULT 1 CHECK (included IN (0,1)),
    exclusion_reason TEXT,
    final_quality_band TEXT NOT NULL DEFAULT 'unassessed',
    final_licence_decision TEXT NOT NULL DEFAULT 'unknown',
    split TEXT CHECK (split IS NULL OR split IN ('train','validation','test')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (build_id) REFERENCES corpus_builds(id) ON DELETE RESTRICT,
    FOREIGN KEY (segment_id) REFERENCES corpus_segments(id) ON DELETE RESTRICT,
    FOREIGN KEY (collection_id) REFERENCES corpus_collections(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_partitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_id INTEGER NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('train','validation','test')),
    segment_count INTEGER NOT NULL DEFAULT 0 CHECK (segment_count >= 0),
    seed INTEGER NOT NULL DEFAULT 42,
    checksum_sha256 TEXT NOT NULL,
    holdout_evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(build_id, split),
    FOREIGN KEY (build_id) REFERENCES corpus_builds(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_id INTEGER NOT NULL,
    semantic_version TEXT NOT NULL,
    train_segment_count INTEGER NOT NULL DEFAULT 0 CHECK (train_segment_count >= 0),
    validation_segment_count INTEGER NOT NULL DEFAULT 0 CHECK (validation_segment_count >= 0),
    test_segment_count INTEGER NOT NULL DEFAULT 0 CHECK (test_segment_count >= 0),
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    domain_distribution_json TEXT NOT NULL DEFAULT '{}',
    style_distribution_json TEXT NOT NULL DEFAULT '{}',
    source_distribution_json TEXT NOT NULL DEFAULT '{}',
    licence_distribution_json TEXT NOT NULL DEFAULT '{}',
    total_characters INTEGER NOT NULL DEFAULT 0 CHECK (total_characters >= 0),
    estimated_tokens INTEGER NOT NULL DEFAULT 0 CHECK (estimated_tokens >= 0),
    manifest_checksum_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validating','ready','deprecated','retired','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(semantic_version),
    FOREIGN KEY (build_id) REFERENCES corpus_builds(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    corpus_version_id INTEGER NOT NULL,
    export_format TEXT NOT NULL CHECK (export_format IN ('jsonl','plain_text_shards','metadata_jsonl')),
    shard_max_bytes INTEGER NOT NULL DEFAULT 50000000 CHECK (shard_max_bytes > 0),
    relative_storage_directory TEXT,
    total_shards INTEGER NOT NULL DEFAULT 0 CHECK (total_shards >= 0),
    total_records INTEGER NOT NULL DEFAULT 0 CHECK (total_records >= 0),
    total_bytes INTEGER NOT NULL DEFAULT 0 CHECK (total_bytes >= 0),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed','cancelled'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (corpus_version_id) REFERENCES corpus_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_export_shards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    export_id INTEGER NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('train','validation','test')),
    shard_number INTEGER NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    total_characters INTEGER NOT NULL DEFAULT 0 CHECK (total_characters >= 0),
    estimated_tokens INTEGER NOT NULL DEFAULT 0 CHECK (estimated_tokens >= 0),
    relative_storage_key TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (file_size_bytes >= 0),
    checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(export_id, split, shard_number),
    FOREIGN KEY (export_id) REFERENCES corpus_exports(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_manifests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    corpus_version_id INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (corpus_version_id) REFERENCES corpus_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    left_version_id INTEGER NOT NULL,
    right_version_id INTEGER NOT NULL,
    compatibility TEXT NOT NULL CHECK (compatibility IN ('compatible','partially_compatible','incompatible')),
    comparison_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (left_version_id) REFERENCES corpus_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (right_version_id) REFERENCES corpus_versions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_corpus_source_registries_status ON corpus_source_registries(status);
CREATE INDEX IF NOT EXISTS ix_corpus_source_licences_source ON corpus_source_licences(source_id);
CREATE INDEX IF NOT EXISTS ix_corpus_source_snapshots_source ON corpus_source_snapshots(source_id);
CREATE INDEX IF NOT EXISTS ix_corpus_source_files_snapshot ON corpus_source_files(snapshot_id);
CREATE INDEX IF NOT EXISTS ix_corpus_extraction_runs_snapshot ON corpus_extraction_runs(snapshot_id);
CREATE INDEX IF NOT EXISTS ix_corpus_extracted_documents_run ON corpus_extracted_documents(extraction_run_id);
CREATE INDEX IF NOT EXISTS ix_corpus_normalization_runs_extraction ON corpus_normalization_runs(extraction_run_id);
CREATE INDEX IF NOT EXISTS ix_corpus_normalized_documents_run ON corpus_normalized_documents(normalization_run_id);
CREATE INDEX IF NOT EXISTS ix_corpus_segments_document ON corpus_segments(normalized_document_id);
CREATE INDEX IF NOT EXISTS ix_corpus_segment_locations_segment ON corpus_segment_locations(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_language_assessments_segment ON corpus_language_assessments(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_domain_assessments_segment ON corpus_domain_assessments(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_style_assessments_segment ON corpus_style_assessments(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_quality_assessments_subject ON corpus_quality_assessments(subject_type, subject_reference_public_id);
CREATE INDEX IF NOT EXISTS ix_corpus_quality_issues_assessment ON corpus_quality_issues(quality_assessment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_privacy_findings_segment ON corpus_privacy_findings(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_safety_findings_segment ON corpus_safety_findings(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_duplicate_clusters_run ON corpus_duplicate_clusters(deduplication_run_id);
CREATE INDEX IF NOT EXISTS ix_corpus_duplicate_members_cluster ON corpus_duplicate_members(cluster_id);
CREATE INDEX IF NOT EXISTS ix_corpus_duplicate_members_segment ON corpus_duplicate_members(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_contamination_findings_run ON corpus_contamination_findings(contamination_run_id);
CREATE INDEX IF NOT EXISTS ix_corpus_collection_members_collection ON corpus_collection_members(collection_id);
CREATE INDEX IF NOT EXISTS ix_corpus_collection_members_segment ON corpus_collection_members(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_build_members_build ON corpus_build_members(build_id, split);
CREATE INDEX IF NOT EXISTS ix_corpus_build_members_segment ON corpus_build_members(segment_id);
CREATE INDEX IF NOT EXISTS ix_corpus_partitions_build ON corpus_partitions(build_id);
CREATE INDEX IF NOT EXISTS ix_corpus_versions_build ON corpus_versions(build_id);
CREATE INDEX IF NOT EXISTS ix_corpus_exports_version ON corpus_exports(corpus_version_id);
CREATE INDEX IF NOT EXISTS ix_corpus_export_shards_export ON corpus_export_shards(export_id, split);
CREATE INDEX IF NOT EXISTS ix_corpus_manifests_version ON corpus_manifests(corpus_version_id);
CREATE TRIGGER IF NOT EXISTS corpus_extracted_documents_immutable_update BEFORE UPDATE ON corpus_extracted_documents BEGIN SELECT RAISE(ABORT, 'extracted documents are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_extracted_documents_immutable_delete BEFORE DELETE ON corpus_extracted_documents BEGIN SELECT RAISE(ABORT, 'extracted documents are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_normalized_documents_immutable_update BEFORE UPDATE ON corpus_normalized_documents BEGIN SELECT RAISE(ABORT, 'normalized documents are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_normalized_documents_immutable_delete BEFORE DELETE ON corpus_normalized_documents BEGIN SELECT RAISE(ABORT, 'normalized documents are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_segments_immutable_update BEFORE UPDATE ON corpus_segments BEGIN SELECT RAISE(ABORT, 'segments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_segments_immutable_delete BEFORE DELETE ON corpus_segments BEGIN SELECT RAISE(ABORT, 'segments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_segment_locations_immutable_update BEFORE UPDATE ON corpus_segment_locations BEGIN SELECT RAISE(ABORT, 'segment locations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_segment_locations_immutable_delete BEFORE DELETE ON corpus_segment_locations BEGIN SELECT RAISE(ABORT, 'segment locations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_language_assessments_immutable_update BEFORE UPDATE ON corpus_language_assessments BEGIN SELECT RAISE(ABORT, 'language assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_language_assessments_immutable_delete BEFORE DELETE ON corpus_language_assessments BEGIN SELECT RAISE(ABORT, 'language assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_domain_assessments_immutable_update BEFORE UPDATE ON corpus_domain_assessments BEGIN SELECT RAISE(ABORT, 'domain assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_domain_assessments_immutable_delete BEFORE DELETE ON corpus_domain_assessments BEGIN SELECT RAISE(ABORT, 'domain assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_style_assessments_immutable_update BEFORE UPDATE ON corpus_style_assessments BEGIN SELECT RAISE(ABORT, 'style assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_style_assessments_immutable_delete BEFORE DELETE ON corpus_style_assessments BEGIN SELECT RAISE(ABORT, 'style assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_quality_assessments_immutable_update BEFORE UPDATE ON corpus_quality_assessments BEGIN SELECT RAISE(ABORT, 'quality assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_quality_assessments_immutable_delete BEFORE DELETE ON corpus_quality_assessments BEGIN SELECT RAISE(ABORT, 'quality assessments are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_quality_issues_immutable_update BEFORE UPDATE ON corpus_quality_issues BEGIN SELECT RAISE(ABORT, 'quality issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_quality_issues_immutable_delete BEFORE DELETE ON corpus_quality_issues BEGIN SELECT RAISE(ABORT, 'quality issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_privacy_findings_immutable_update BEFORE UPDATE ON corpus_privacy_findings BEGIN SELECT RAISE(ABORT, 'privacy findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_privacy_findings_immutable_delete BEFORE DELETE ON corpus_privacy_findings BEGIN SELECT RAISE(ABORT, 'privacy findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_safety_findings_immutable_update BEFORE UPDATE ON corpus_safety_findings BEGIN SELECT RAISE(ABORT, 'safety findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_safety_findings_immutable_delete BEFORE DELETE ON corpus_safety_findings BEGIN SELECT RAISE(ABORT, 'safety findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_duplicate_clusters_immutable_update BEFORE UPDATE ON corpus_duplicate_clusters BEGIN SELECT RAISE(ABORT, 'duplicate clusters are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_duplicate_clusters_immutable_delete BEFORE DELETE ON corpus_duplicate_clusters BEGIN SELECT RAISE(ABORT, 'duplicate clusters are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_duplicate_members_immutable_update BEFORE UPDATE ON corpus_duplicate_members BEGIN SELECT RAISE(ABORT, 'duplicate members are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_duplicate_members_immutable_delete BEFORE DELETE ON corpus_duplicate_members BEGIN SELECT RAISE(ABORT, 'duplicate members are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_contamination_findings_immutable_update BEFORE UPDATE ON corpus_contamination_findings BEGIN SELECT RAISE(ABORT, 'contamination findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_contamination_findings_immutable_delete BEFORE DELETE ON corpus_contamination_findings BEGIN SELECT RAISE(ABORT, 'contamination findings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_collection_members_immutable_update BEFORE UPDATE ON corpus_collection_members BEGIN SELECT RAISE(ABORT, 'collection members are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_collection_members_immutable_delete BEFORE DELETE ON corpus_collection_members BEGIN SELECT RAISE(ABORT, 'collection members are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_build_members_immutable_update BEFORE UPDATE ON corpus_build_members BEGIN SELECT RAISE(ABORT, 'build members are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_build_members_immutable_delete BEFORE DELETE ON corpus_build_members BEGIN SELECT RAISE(ABORT, 'build members are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_partitions_immutable_update BEFORE UPDATE ON corpus_partitions BEGIN SELECT RAISE(ABORT, 'partitions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_partitions_immutable_delete BEFORE DELETE ON corpus_partitions BEGIN SELECT RAISE(ABORT, 'partitions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_export_shards_immutable_update BEFORE UPDATE ON corpus_export_shards BEGIN SELECT RAISE(ABORT, 'export shards are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_export_shards_immutable_delete BEFORE DELETE ON corpus_export_shards BEGIN SELECT RAISE(ABORT, 'export shards are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_manifests_immutable_update BEFORE UPDATE ON corpus_manifests BEGIN SELECT RAISE(ABORT, 'corpus manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_manifests_immutable_delete BEFORE DELETE ON corpus_manifests BEGIN SELECT RAISE(ABORT, 'corpus manifests are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_comparisons_immutable_update BEFORE UPDATE ON corpus_comparisons BEGIN SELECT RAISE(ABORT, 'comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_comparisons_immutable_delete BEFORE DELETE ON corpus_comparisons BEGIN SELECT RAISE(ABORT, 'comparisons are append-only'); END;
"""

MIGRATION_020_NAME = "020_phase20_production_corpus_expansion"

# Phase 20 extends Phase 19's corpus builder toward production scale:
# multi-format ingestion jobs, versioned normalization/segmentation
# profiles, a persistent protected-content contamination registry,
# tokenizer compatibility analysis (reusing Phase 7's
# `TokenizerService.processor_for_version`), a formal pretraining-
# readiness gate, and an immutable release lifecycle wrapping a
# `corpus_versions` row. No new quality/privacy/safety/deduplication/
# contamination/balancing/partitioning/collection/build/version/
# export/manifest table is created here -- Phase 19's tables and pure
# functions are reused unchanged; Phase 20 only adds what Phase 19
# genuinely lacked (job orchestration, profile versioning, a real
# protected-content registry, tokenizer analysis, a formal readiness
# gate, and a release approval workflow).
#
# `corpus_source_registries.status` (Phase 19's CHECK'd lifecycle:
# draft/origin_review/licence_review/approved/approved_with_restrictions/
# rejected/quarantined/disputed/archived) is never altered -- SQLite
# cannot modify a CHECK constraint without a full table rebuild, and
# this table is referenced by five other Phase 19 tables. Phase 20's
# required production lifecycle
# (draft -> provenance_verified -> licence_reviewed -> approved ->
# ingested -> retired) is layered on top as a new, additive
# `production_lifecycle_status` column rather than replacing the
# existing one; `provenance_verified` maps to the existing
# `origin_verified` flag being true, and `licence_reviewed` maps to
# the source's latest licence review_status no longer being
# 'unknown'. Both lifecycles coexist deliberately.
#
# Labelling's "method"/"review_status" fields (Section 9) are added as
# new columns directly on the existing, already-append-only
# `corpus_language_assessments`/`corpus_domain_assessments`/
# `corpus_style_assessments` tables rather than a new
# `corpus_label_assignments` table -- a human correction is simply a
# new row with `method='human_correction'`, appended on top of the
# original heuristic row, which the repository's existing
# "latest row wins" read pattern already surfaces first. This satisfies
# "human correction without mutating original evidence" without a
# fifth table duplicating what append-only assessment tables already do.
PHASE20_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "corpus_source_registries": [
        ("production_lifecycle_status", "TEXT NOT NULL DEFAULT 'draft'"),
        ("original_url", "TEXT"),
        ("acquisition_date", "TEXT"),
        ("reviewed_by_admin_public_id", "TEXT"),
        ("reviewed_at", "TEXT"),
    ],
    "corpus_language_assessments": [
        ("method", "TEXT NOT NULL DEFAULT 'heuristic'"),
        ("review_status", "TEXT NOT NULL DEFAULT 'unreviewed'"),
    ],
    "corpus_domain_assessments": [
        ("method", "TEXT NOT NULL DEFAULT 'heuristic'"),
        ("review_status", "TEXT NOT NULL DEFAULT 'unreviewed'"),
    ],
    "corpus_style_assessments": [
        ("method", "TEXT NOT NULL DEFAULT 'heuristic'"),
        ("review_status", "TEXT NOT NULL DEFAULT 'unreviewed'"),
    ],
}

PHASE20_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_normalization_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    profile_key TEXT NOT NULL CHECK (profile_key IN (
        'tamil_conservative','tamil_ocr_cleanup','tamil_education_text','tamil_web_text',
        'tamil_mixed_tanglish'
    )),
    version TEXT NOT NULL DEFAULT 'v1',
    operations_json TEXT NOT NULL DEFAULT '{}',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','active','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(profile_key, version)
);
CREATE TABLE IF NOT EXISTS corpus_segmentation_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN (
        'books','school_textbooks','articles','government_documents','agriculture_content',
        'literature','conversational_text','faq_instructional','mixed_tamil_english'
    )),
    strategy TEXT NOT NULL CHECK (strategy IN (
        'heading_section','paragraph','sentence_window','token_window','document_preserving'
    )),
    version TEXT NOT NULL DEFAULT 'v1',
    configuration_json TEXT NOT NULL DEFAULT '{}',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','active','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_type, version)
);
CREATE TABLE IF NOT EXISTS corpus_ingestion_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_id INTEGER NOT NULL,
    snapshot_id INTEGER,
    extraction_run_id INTEGER,
    normalization_run_id INTEGER,
    normalization_profile_id INTEGER,
    segmentation_profile_id INTEGER,
    format TEXT NOT NULL CHECK (format IN (
        'pdf','txt','json','jsonl','csv','docx','html','markdown'
    )),
    idempotency_key TEXT,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued','running','paused','completed','completed_with_warnings','failed','cancelled'
    )),
    current_stage TEXT NOT NULL DEFAULT 'queued' CHECK (current_stage IN (
        'queued','inspecting','snapshotting','extracting','normalizing','segmenting',
        'completed','failed'
    )),
    files_processed INTEGER NOT NULL DEFAULT 0 CHECK (files_processed >= 0),
    documents_created INTEGER NOT NULL DEFAULT 0 CHECK (documents_created >= 0),
    bytes_processed INTEGER NOT NULL DEFAULT 0 CHECK (bytes_processed >= 0),
    characters_extracted INTEGER NOT NULL DEFAULT 0 CHECK (characters_extracted >= 0),
    pages_processed INTEGER NOT NULL DEFAULT 0 CHECK (pages_processed >= 0),
    warnings_count INTEGER NOT NULL DEFAULT 0 CHECK (warnings_count >= 0),
    errors_count INTEGER NOT NULL DEFAULT 0 CHECK (errors_count >= 0),
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    worker_id TEXT,
    last_heartbeat_at TEXT,
    output_manifest_checksum_sha256 TEXT,
    error_details_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, idempotency_key),
    FOREIGN KEY (source_id) REFERENCES corpus_source_registries(id) ON DELETE RESTRICT,
    FOREIGN KEY (snapshot_id) REFERENCES corpus_source_snapshots(id) ON DELETE RESTRICT,
    FOREIGN KEY (extraction_run_id) REFERENCES corpus_extraction_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (normalization_run_id) REFERENCES corpus_normalization_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (normalization_profile_id)
        REFERENCES corpus_normalization_profiles(id) ON DELETE RESTRICT,
    FOREIGN KEY (segmentation_profile_id)
        REFERENCES corpus_segmentation_profiles(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_ingestion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    job_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'queued','started','stage_changed','progress','warning','error','retried',
        'cancelled','completed'
    )),
    stage TEXT,
    message TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES corpus_ingestion_jobs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_protected_content_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    set_type TEXT NOT NULL CHECK (set_type IN (
        'validation_dataset','test_dataset','benchmark_prompts','benchmark_answers',
        'regression_fixtures','safety_test_sets','human_evaluation_sets',
        'release_acceptance_sets'
    )),
    description TEXT NOT NULL DEFAULT '',
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','active','archived'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_protected_content_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    protected_content_set_id INTEGER NOT NULL,
    raw_checksum_sha256 TEXT NOT NULL,
    normalized_checksum_sha256 TEXT NOT NULL,
    evidence_reference TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (protected_content_set_id)
        REFERENCES corpus_protected_content_sets(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_partition_previews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    collection_id INTEGER NOT NULL,
    seed INTEGER NOT NULL DEFAULT 42,
    proportions_json TEXT NOT NULL DEFAULT '{}',
    strict_mode INTEGER NOT NULL DEFAULT 1 CHECK (strict_mode IN (0,1)),
    distribution_json TEXT NOT NULL DEFAULT '{}',
    isolation_report_json TEXT NOT NULL DEFAULT '{}',
    preview_checksum_sha256 TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES corpus_collections(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_tokenizer_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_version_id INTEGER NOT NULL,
    collection_id INTEGER,
    build_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed','cancelled'
    )),
    total_characters INTEGER NOT NULL DEFAULT 0 CHECK (total_characters >= 0),
    total_tokens INTEGER NOT NULL DEFAULT 0 CHECK (total_tokens >= 0),
    total_segments INTEGER NOT NULL DEFAULT 0 CHECK (total_segments >= 0),
    characters_per_token REAL,
    unknown_token_rate REAL,
    long_sequence_rate REAL,
    round_trip_integrity_rate REAL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (collection_id) REFERENCES corpus_collections(id) ON DELETE RESTRICT,
    FOREIGN KEY (build_id) REFERENCES corpus_builds(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_tokenizer_analysis_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    analysis_id INTEGER NOT NULL,
    breakdown_type TEXT NOT NULL CHECK (breakdown_type IN (
        'language','domain','style','source','split','overall'
    )),
    breakdown_value TEXT NOT NULL,
    total_characters INTEGER NOT NULL DEFAULT 0 CHECK (total_characters >= 0),
    total_tokens INTEGER NOT NULL DEFAULT 0 CHECK (total_tokens >= 0),
    characters_per_token REAL,
    unknown_token_rate REAL,
    long_sequence_rate REAL,
    truncation_risk_rate REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES corpus_tokenizer_analyses(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_readiness_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_id INTEGER NOT NULL,
    tokenizer_analysis_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','failed'
    )),
    overall_result TEXT NOT NULL DEFAULT 'not_ready' CHECK (overall_result IN (
        'not_ready','ready_with_warnings','ready'
    )),
    hard_failure_reasons_json TEXT NOT NULL DEFAULT '[]',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (build_id) REFERENCES corpus_builds(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_analysis_id)
        REFERENCES corpus_tokenizer_analyses(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_readiness_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_id INTEGER NOT NULL,
    dimension TEXT NOT NULL CHECK (dimension IN (
        'source_governance','licence_compliance','provenance_completeness','privacy_safety',
        'content_safety','extraction_quality','normalization_integrity','segment_quality',
        'deduplication_completion','contamination_completion','balance_adequacy',
        'partition_integrity','tokenizer_compatibility','manifest_integrity','export_integrity'
    )),
    status TEXT NOT NULL DEFAULT 'not_evaluated' CHECK (status IN (
        'pass','warning','fail','not_evaluated'
    )),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_id) REFERENCES corpus_readiness_evaluations(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    corpus_version_id INTEGER NOT NULL,
    readiness_evaluation_id INTEGER,
    export_id INTEGER,
    semantic_version TEXT NOT NULL,
    release_name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','validated','approved','finalized','exported','retired'
    )),
    manifest_checksum_sha256 TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    approved_by_admin_public_id TEXT,
    finalized_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(semantic_version),
    FOREIGN KEY (corpus_version_id) REFERENCES corpus_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (readiness_evaluation_id)
        REFERENCES corpus_readiness_evaluations(id) ON DELETE RESTRICT,
    FOREIGN KEY (export_id) REFERENCES corpus_exports(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS corpus_release_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    release_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approve','reject')),
    comment TEXT NOT NULL DEFAULT '',
    approved_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (release_id) REFERENCES corpus_releases(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_corpus_ingestion_jobs_source ON corpus_ingestion_jobs(source_id);
CREATE INDEX IF NOT EXISTS ix_corpus_ingestion_jobs_status ON corpus_ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS ix_corpus_ingestion_events_job ON corpus_ingestion_events(job_id);
CREATE INDEX IF NOT EXISTS ix_corpus_protected_content_entries_set
    ON corpus_protected_content_entries(protected_content_set_id);
CREATE INDEX IF NOT EXISTS ix_corpus_protected_content_entries_checksum
    ON corpus_protected_content_entries(normalized_checksum_sha256);
CREATE INDEX IF NOT EXISTS ix_corpus_partition_previews_collection
    ON corpus_partition_previews(collection_id);
CREATE INDEX IF NOT EXISTS ix_corpus_tokenizer_analyses_tokenizer
    ON corpus_tokenizer_analyses(tokenizer_version_id);
CREATE INDEX IF NOT EXISTS ix_corpus_tokenizer_analysis_metrics_analysis
    ON corpus_tokenizer_analysis_metrics(analysis_id);
CREATE INDEX IF NOT EXISTS ix_corpus_readiness_evaluations_build
    ON corpus_readiness_evaluations(build_id);
CREATE INDEX IF NOT EXISTS ix_corpus_readiness_dimensions_evaluation
    ON corpus_readiness_dimensions(evaluation_id);
CREATE INDEX IF NOT EXISTS ix_corpus_releases_version ON corpus_releases(corpus_version_id);
CREATE INDEX IF NOT EXISTS ix_corpus_release_approvals_release
    ON corpus_release_approvals(release_id);
CREATE TRIGGER IF NOT EXISTS corpus_ingestion_events_immutable_update BEFORE UPDATE ON corpus_ingestion_events BEGIN SELECT RAISE(ABORT, 'ingestion events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_ingestion_events_immutable_delete BEFORE DELETE ON corpus_ingestion_events BEGIN SELECT RAISE(ABORT, 'ingestion events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_protected_content_entries_immutable_update BEFORE UPDATE ON corpus_protected_content_entries BEGIN SELECT RAISE(ABORT, 'protected content entries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_protected_content_entries_immutable_delete BEFORE DELETE ON corpus_protected_content_entries BEGIN SELECT RAISE(ABORT, 'protected content entries are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_partition_previews_immutable_update BEFORE UPDATE ON corpus_partition_previews BEGIN SELECT RAISE(ABORT, 'partition previews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_partition_previews_immutable_delete BEFORE DELETE ON corpus_partition_previews BEGIN SELECT RAISE(ABORT, 'partition previews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_tokenizer_analysis_metrics_immutable_update BEFORE UPDATE ON corpus_tokenizer_analysis_metrics BEGIN SELECT RAISE(ABORT, 'tokenizer analysis metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_tokenizer_analysis_metrics_immutable_delete BEFORE DELETE ON corpus_tokenizer_analysis_metrics BEGIN SELECT RAISE(ABORT, 'tokenizer analysis metrics are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_readiness_dimensions_immutable_update BEFORE UPDATE ON corpus_readiness_dimensions BEGIN SELECT RAISE(ABORT, 'readiness dimensions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_readiness_dimensions_immutable_delete BEFORE DELETE ON corpus_readiness_dimensions BEGIN SELECT RAISE(ABORT, 'readiness dimensions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_release_approvals_immutable_update BEFORE UPDATE ON corpus_release_approvals BEGIN SELECT RAISE(ABORT, 'release approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS corpus_release_approvals_immutable_delete BEFORE DELETE ON corpus_release_approvals BEGIN SELECT RAISE(ABORT, 'release approvals are append-only'); END;
"""

MIGRATION_021_NAME = "021_phase21a_tokenizer_pretraining_readiness"

# Phase 21A is a preparation/safety gate for future base-model
# pretraining -- it deliberately does not add a parallel training or
# tokenizer engine. Instead it bridges an approved, exported Phase 20
# corpus release into the *existing* Phase 6 dataset-version format
# (`dataset_records`/`dataset_versions`/`dataset_version_items`) so
# that Phase 7's `TokenizerService` and Phase 9's `PretrainingService`
# run completely unchanged against real corpus content. Only the
# genuinely new concepts get new tables: which corpus release fed a
# tokenizer-training corpus (with sufficiency analysis), how tokenizer
# candidates compared against each other, the frozen pretraining
# dataset snapshot's own metadata (checksums/counts/seed, distinct
# from the underlying dataset_version because a snapshot is Phase
# 21A's own immutability boundary), a model's resource-estimate audit
# trail, the smoke-pretraining run's outcome, and a 17-dimension
# readiness gate mirroring Phase 20's `corpus_readiness_*` pattern.
PHASE21A_SCHEMA = """
CREATE TABLE IF NOT EXISTS tokenizer_corpus_builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    corpus_release_id INTEGER NOT NULL,
    dataset_version_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','building','completed','failed'
    )),
    eligible_segment_count INTEGER NOT NULL DEFAULT 0 CHECK (eligible_segment_count >= 0),
    excluded_segment_count INTEGER NOT NULL DEFAULT 0 CHECK (excluded_segment_count >= 0),
    exclusion_reasons_json TEXT NOT NULL DEFAULT '{}',
    total_records INTEGER NOT NULL DEFAULT 0 CHECK (total_records >= 0),
    total_characters INTEGER NOT NULL DEFAULT 0 CHECK (total_characters >= 0),
    total_utf8_bytes INTEGER NOT NULL DEFAULT 0 CHECK (total_utf8_bytes >= 0),
    total_words INTEGER NOT NULL DEFAULT 0 CHECK (total_words >= 0),
    unique_character_count INTEGER NOT NULL DEFAULT 0 CHECK (unique_character_count >= 0),
    tamil_character_count INTEGER NOT NULL DEFAULT 0 CHECK (tamil_character_count >= 0),
    english_character_count INTEGER NOT NULL DEFAULT 0 CHECK (english_character_count >= 0),
    digit_count INTEGER NOT NULL DEFAULT 0 CHECK (digit_count >= 0),
    punctuation_count INTEGER NOT NULL DEFAULT 0 CHECK (punctuation_count >= 0),
    tamil_only_record_count INTEGER NOT NULL DEFAULT 0 CHECK (tamil_only_record_count >= 0),
    english_only_record_count INTEGER NOT NULL DEFAULT 0 CHECK (english_only_record_count >= 0),
    tanglish_record_count INTEGER NOT NULL DEFAULT 0 CHECK (tanglish_record_count >= 0),
    mixed_record_count INTEGER NOT NULL DEFAULT 0 CHECK (mixed_record_count >= 0),
    domain_distribution_json TEXT NOT NULL DEFAULT '{}',
    style_distribution_json TEXT NOT NULL DEFAULT '{}',
    source_distribution_json TEXT NOT NULL DEFAULT '{}',
    licence_distribution_json TEXT NOT NULL DEFAULT '{}',
    duplicate_exclusion_count INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_exclusion_count >= 0),
    contamination_exclusion_count INTEGER NOT NULL DEFAULT 0
        CHECK (contamination_exclusion_count >= 0),
    sufficiency_state TEXT NOT NULL DEFAULT 'insufficient' CHECK (sufficiency_state IN (
        'insufficient','experimental','candidate','production_candidate'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (corpus_release_id) REFERENCES corpus_releases(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS tokenizer_candidate_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_corpus_build_id INTEGER NOT NULL,
    candidate_tokenizer_version_ids_json TEXT NOT NULL DEFAULT '[]',
    recommended_tokenizer_version_id INTEGER,
    comparison_checksum_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','completed')),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_corpus_build_id) REFERENCES tokenizer_corpus_builds(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (recommended_tokenizer_version_id) REFERENCES tokenizer_versions(id)
        ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS tokenizer_selection_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    tokenizer_candidate_comparison_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    vocabulary_size INTEGER NOT NULL CHECK (vocabulary_size > 0),
    dimensions_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    final_status TEXT NOT NULL DEFAULT 'rejected' CHECK (final_status IN (
        'rejected','experimental','recommended','production_candidate'
    )),
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tokenizer_candidate_comparison_id) REFERENCES tokenizer_candidate_comparisons(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS pretraining_dataset_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    corpus_release_id INTEGER NOT NULL,
    dataset_version_id INTEGER NOT NULL,
    tokenizer_version_id INTEGER NOT NULL,
    manifest_checksum_sha256 TEXT NOT NULL,
    export_checksums_json TEXT NOT NULL DEFAULT '[]',
    tokenizer_checksum_sha256 TEXT NOT NULL,
    train_record_count INTEGER NOT NULL DEFAULT 0 CHECK (train_record_count >= 0),
    validation_record_count INTEGER NOT NULL DEFAULT 0 CHECK (validation_record_count >= 0),
    test_record_count INTEGER NOT NULL DEFAULT 0 CHECK (test_record_count >= 0),
    train_token_count INTEGER NOT NULL DEFAULT 0 CHECK (train_token_count >= 0),
    validation_token_count INTEGER NOT NULL DEFAULT 0 CHECK (validation_token_count >= 0),
    test_token_count INTEGER NOT NULL DEFAULT 0 CHECK (test_token_count >= 0),
    maximum_sequence_length INTEGER NOT NULL CHECK (maximum_sequence_length > 0),
    partition_algorithm_version TEXT NOT NULL DEFAULT 'v1',
    deterministic_seed INTEGER NOT NULL DEFAULT 42,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (corpus_release_id) REFERENCES corpus_releases(id) ON DELETE RESTRICT,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS base_model_resource_estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    profile_name TEXT NOT NULL CHECK (profile_name IN (
        'micro_smoke_test','small_experimental','maximum_safe_local'
    )),
    vocabulary_size INTEGER NOT NULL CHECK (vocabulary_size > 0),
    context_length INTEGER NOT NULL CHECK (context_length > 0),
    hidden_size INTEGER NOT NULL CHECK (hidden_size > 0),
    num_hidden_layers INTEGER NOT NULL CHECK (num_hidden_layers > 0),
    num_attention_heads INTEGER NOT NULL CHECK (num_attention_heads > 0),
    intermediate_size INTEGER NOT NULL CHECK (intermediate_size > 0),
    parameter_count INTEGER NOT NULL CHECK (parameter_count > 0),
    parameter_memory_bytes INTEGER NOT NULL CHECK (parameter_memory_bytes >= 0),
    gradient_memory_bytes INTEGER NOT NULL CHECK (gradient_memory_bytes >= 0),
    optimizer_state_memory_bytes INTEGER NOT NULL CHECK (optimizer_state_memory_bytes >= 0),
    activation_memory_bytes INTEGER NOT NULL CHECK (activation_memory_bytes >= 0),
    estimated_peak_ram_bytes INTEGER NOT NULL CHECK (estimated_peak_ram_bytes >= 0),
    checkpoint_disk_bytes INTEGER NOT NULL CHECK (checkpoint_disk_bytes >= 0),
    optimizer_disk_bytes INTEGER NOT NULL CHECK (optimizer_disk_bytes >= 0),
    estimated_tokens_per_second REAL NOT NULL CHECK (estimated_tokens_per_second >= 0),
    estimated_training_duration_seconds_min INTEGER NOT NULL
        CHECK (estimated_training_duration_seconds_min >= 0),
    estimated_training_duration_seconds_max INTEGER NOT NULL
        CHECK (estimated_training_duration_seconds_max >= 0),
    safe_ram_ceiling_bytes INTEGER NOT NULL CHECK (safe_ram_ceiling_bytes > 0),
    within_safe_limit INTEGER NOT NULL CHECK (within_safe_limit IN (0,1)),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pretraining_smoke_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_dataset_snapshot_id INTEGER NOT NULL,
    base_model_resource_estimate_id INTEGER NOT NULL,
    pretraining_job_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','running','completed','completed_with_warnings','failed'
    )),
    total_steps INTEGER NOT NULL DEFAULT 0 CHECK (total_steps >= 0),
    checkpoint_public_id TEXT,
    checkpoint_checksum_sha256 TEXT,
    resume_verified INTEGER NOT NULL DEFAULT 0 CHECK (resume_verified IN (0,1)),
    initial_training_loss REAL,
    final_training_loss REAL,
    validation_loss REAL,
    maximum_gradient_norm REAL,
    tokens_processed INTEGER NOT NULL DEFAULT 0 CHECK (tokens_processed >= 0),
    tokens_per_second REAL,
    peak_process_memory_bytes INTEGER,
    degeneration_findings_json TEXT NOT NULL DEFAULT '[]',
    error_details_json TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (pretraining_dataset_snapshot_id) REFERENCES pretraining_dataset_snapshots(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (base_model_resource_estimate_id) REFERENCES base_model_resource_estimates(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (pretraining_job_id) REFERENCES pretraining_jobs(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS base_model_readiness_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    pretraining_dataset_snapshot_id INTEGER NOT NULL,
    tokenizer_candidate_comparison_id INTEGER,
    base_model_resource_estimate_id INTEGER,
    pretraining_smoke_run_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','running','completed','failed')),
    overall_result TEXT NOT NULL DEFAULT 'not_ready' CHECK (overall_result IN (
        'not_ready','ready_for_experimental_pretraining','ready_for_bounded_pretraining'
    )),
    hard_failure_reasons_json TEXT NOT NULL DEFAULT '[]',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pretraining_dataset_snapshot_id) REFERENCES pretraining_dataset_snapshots(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tokenizer_candidate_comparison_id) REFERENCES tokenizer_candidate_comparisons(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (base_model_resource_estimate_id) REFERENCES base_model_resource_estimates(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (pretraining_smoke_run_id) REFERENCES pretraining_smoke_runs(id)
        ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS base_model_readiness_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evaluation_id INTEGER NOT NULL,
    dimension TEXT NOT NULL CHECK (dimension IN (
        'tokenizer_corpus_sufficiency','tokenizer_quality','tokenizer_artifact_integrity',
        'tokenizer_activation','corpus_release_integrity','dataset_snapshot_integrity',
        'partition_isolation','tokenization_statistics','model_configuration_safety',
        'data_loader_reliability','training_configuration_validity',
        'forward_backward_stability','checkpoint_integrity','resume_integrity',
        'validation_execution','resource_safety','audit_completeness'
    )),
    status TEXT NOT NULL DEFAULT 'not_evaluated' CHECK (status IN (
        'pass','warning','fail','not_evaluated'
    )),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_id) REFERENCES base_model_readiness_evaluations(id)
        ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_tokenizer_corpus_builds_release
    ON tokenizer_corpus_builds(corpus_release_id);
CREATE INDEX IF NOT EXISTS ix_tokenizer_candidate_comparisons_build
    ON tokenizer_candidate_comparisons(tokenizer_corpus_build_id);
CREATE INDEX IF NOT EXISTS ix_tokenizer_selection_evaluations_comparison
    ON tokenizer_selection_evaluations(tokenizer_candidate_comparison_id);
CREATE INDEX IF NOT EXISTS ix_pretraining_dataset_snapshots_release
    ON pretraining_dataset_snapshots(corpus_release_id);
CREATE INDEX IF NOT EXISTS ix_pretraining_smoke_runs_snapshot
    ON pretraining_smoke_runs(pretraining_dataset_snapshot_id);
CREATE INDEX IF NOT EXISTS ix_base_model_readiness_dimensions_evaluation
    ON base_model_readiness_dimensions(evaluation_id);
CREATE TRIGGER IF NOT EXISTS tokenizer_selection_evaluations_immutable_update BEFORE UPDATE ON tokenizer_selection_evaluations BEGIN SELECT RAISE(ABORT, 'tokenizer selection evaluations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS tokenizer_selection_evaluations_immutable_delete BEFORE DELETE ON tokenizer_selection_evaluations BEGIN SELECT RAISE(ABORT, 'tokenizer selection evaluations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS pretraining_dataset_snapshots_immutable_update BEFORE UPDATE ON pretraining_dataset_snapshots BEGIN SELECT RAISE(ABORT, 'pretraining dataset snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS pretraining_dataset_snapshots_immutable_delete BEFORE DELETE ON pretraining_dataset_snapshots BEGIN SELECT RAISE(ABORT, 'pretraining dataset snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS base_model_readiness_dimensions_immutable_update BEFORE UPDATE ON base_model_readiness_dimensions BEGIN SELECT RAISE(ABORT, 'readiness dimensions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS base_model_readiness_dimensions_immutable_delete BEFORE DELETE ON base_model_readiness_dimensions BEGIN SELECT RAISE(ABORT, 'readiness dimensions are append-only'); END;
"""

MIGRATION_022_NAME = "022_phase22_admin_assistant_execution_tracking"

# Phase 22 turns the Phase 2 `admin_approvals` table (previously created
# but never wired to a caller) into the governed execution record for the
# Admin Assistant: a proposal is created pending, an admin reviews it
# (approve/reject, already modeled by `status`), and only an approved
# proposal may be executed exactly once through an allowlisted existing
# service call. The three new columns record that execution outcome
# without a separate table, since execution is 1:1 with an approval and
# never has its own independent lifecycle. `summary` is a short
# human-readable description surfaced in review queues so an admin does
# not have to parse `request_payload_json` to decide.
PHASE22_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "admin_approvals": [
        ("summary", "TEXT NOT NULL DEFAULT ''"),
        ("execution_status", "TEXT NOT NULL DEFAULT 'not_applicable'"),
        ("executed_at", "TEXT"),
        ("execution_result_json", "TEXT"),
        ("executor_public_id", "TEXT"),
    ],
}

MIGRATION_023_NAME = "023_data_studio_phase2_source_rights_registry"

# Data Studio Phase 2 adds a general-purpose Source, Rights & Usage
# Registry covering *any* data entering Brud AI -- not a duplicate of
# Phase 19/20's `corpus_source_registries`/`corpus_source_licences`
# (which remain untouched here). That system requires every source to
# belong to a `corpus_policy_id` and is scoped to the corpus-builder
# pipeline; this registry deliberately has no such requirement, so an
# admin can register e.g. their own spoken-Tamil phrasing as a source
# without first creating a corpus policy. Where the two systems overlap
# conceptually (deciding whether a piece of content may be used for a
# given purpose), they share one policy brain
# (`core_model.data_governance.usage_policy.evaluate_source_usage`) fed
# by a small adapter for each table shape, rather than forking the
# decision logic -- see docs/data_studio/phase2_source_rights_registry_plan.md.
#
# `data_sources` is the canonical source record. `source_rights` holds
# the single current rights declaration for a source (one row per
# source, mutably updated as review progresses -- traceability comes
# from `source_verification_events`, not from versioning this table).
# `source_verification_events` and `source_usage_decisions` are
# append-only history (immutability enforced by trigger, matching the
# Phase 19/20 convention) so a verification action or a usage-eligibility
# check can never be silently overwritten after the fact.
# `source_record_links` is a governed polymorphic link -- mirroring the
# `target_type`/`target_public_id` shape `admin_approvals` already uses
# -- from a source to any entity (a dataset record, a document, a corpus
# item, a RAG source, ...) identified by its public_id rather than its
# internal numeric id, since a link table spanning many different entity
# tables cannot hold a real foreign key to all of them. Unlike the other
# four tables, links may be deleted (unlinking), because the task
# explicitly calls for that and a stale link is not evidence of anything.
PHASE23_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'human_created','admin_created','teacher_created','institution_created',
        'document_derived','government_source','public_domain','open_dataset',
        'licensed_dataset','permission_granted','user_contributed','ai_assisted',
        'ai_generated','web_source','unknown'
    )),
    owner_name TEXT,
    author_name TEXT,
    publisher_name TEXT,
    organization_name TEXT,
    source_url TEXT,
    source_reference TEXT,
    publication_year INTEGER,
    edition TEXT,
    language_codes_json TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT '',
    knowledge_risk TEXT NOT NULL DEFAULT 'unknown' CHECK (knowledge_risk IN (
        'low','medium','high','unknown'
    )),
    fact_dependency TEXT NOT NULL DEFAULT 'unknown' CHECK (fact_dependency IN (
        'low','medium','high','unknown'
    )),
    verification_required INTEGER NOT NULL DEFAULT 0 CHECK (verification_required IN (0,1)),
    independent_reviewer_required INTEGER NOT NULL DEFAULT 0
        CHECK (independent_reviewer_required IN (0,1)),
    internal_rag_policy_allows_unknown_rights INTEGER NOT NULL DEFAULT 0
        CHECK (internal_rag_policy_allows_unknown_rights IN (0,1)),
    acquired_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','needs_review','verified','restricted','rejected','archived'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_data_sources_status ON data_sources(status);
CREATE INDEX IF NOT EXISTS ix_data_sources_source_type ON data_sources(source_type);

CREATE TABLE IF NOT EXISTS source_rights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    data_source_id INTEGER NOT NULL UNIQUE,
    rights_status TEXT NOT NULL DEFAULT 'unknown' CHECK (rights_status IN (
        'unknown','pending_review','public_domain','open_license','licensed',
        'permission_granted','internal_only','restricted','prohibited','expired'
    )),
    license_name TEXT,
    license_identifier TEXT,
    license_url TEXT,
    copyright_owner TEXT,
    permission_reference TEXT,
    permission_document_reference TEXT,
    permission_received_at TEXT,
    permission_expires_at TEXT,
    attribution_required INTEGER NOT NULL DEFAULT 0 CHECK (attribution_required IN (0,1)),
    attribution_text TEXT,
    share_alike_required INTEGER NOT NULL DEFAULT 0 CHECK (share_alike_required IN (0,1)),
    modification_allowed INTEGER NOT NULL DEFAULT 0 CHECK (modification_allowed IN (0,1)),
    commercial_use_allowed INTEGER NOT NULL DEFAULT 0 CHECK (commercial_use_allowed IN (0,1)),
    rag_use_allowed INTEGER NOT NULL DEFAULT 0 CHECK (rag_use_allowed IN (0,1)),
    training_use_allowed INTEGER NOT NULL DEFAULT 0 CHECK (training_use_allowed IN (0,1)),
    evaluation_use_allowed INTEGER NOT NULL DEFAULT 0 CHECK (evaluation_use_allowed IN (0,1)),
    public_export_allowed INTEGER NOT NULL DEFAULT 0 CHECK (public_export_allowed IN (0,1)),
    redistribution_allowed INTEGER NOT NULL DEFAULT 0 CHECK (redistribution_allowed IN (0,1)),
    internal_only INTEGER NOT NULL DEFAULT 0 CHECK (internal_only IN (0,1)),
    verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK (verification_status IN (
        'unverified','self_declared','document_verified','owner_confirmed',
        'legal_reviewed','rejected'
    )),
    verified_by_admin_public_id TEXT,
    verified_at TEXT,
    review_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_source_rights_data_source ON source_rights(data_source_id);
CREATE INDEX IF NOT EXISTS ix_source_rights_status ON source_rights(rights_status);

CREATE TABLE IF NOT EXISTS source_verification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    data_source_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'self_declare','document_verify','owner_confirm','legal_review','reject',
        'expire','restrict'
    )),
    verification_status_after TEXT NOT NULL,
    performed_by_admin_public_id TEXT NOT NULL,
    evidence_reference TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_source_verification_events_data_source
    ON source_verification_events(data_source_id);

CREATE TABLE IF NOT EXISTS source_usage_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    data_source_id INTEGER NOT NULL,
    target_use TEXT NOT NULL CHECK (target_use IN (
        'rag','training','evaluation','commercial','public_export','redistribution'
    )),
    allowed INTEGER NOT NULL CHECK (allowed IN (0,1)),
    decision_code TEXT NOT NULL,
    blocking_reasons_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    required_actions_json TEXT NOT NULL DEFAULT '[]',
    evaluated_by_admin_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_source_usage_decisions_data_source_target
    ON source_usage_decisions(data_source_id, target_use);

CREATE TABLE IF NOT EXISTS source_record_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    data_source_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN (
        'dataset_record','dataset_source','dataset_version','import_job','document',
        'document_page','corpus_source_registry','corpus_item','chunk',
        'rag_knowledge_source','rag_item','evaluation_case'
    )),
    entity_public_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'primary_source' CHECK (relationship_type IN (
        'primary_source','supporting_source','derived_from','verified_against',
        'translated_from','generated_from'
    )),
    source_page TEXT,
    source_section TEXT,
    source_locator TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE RESTRICT,
    UNIQUE(data_source_id, entity_type, entity_public_id, relationship_type)
);
CREATE INDEX IF NOT EXISTS ix_source_record_links_entity
    ON source_record_links(entity_type, entity_public_id);
CREATE INDEX IF NOT EXISTS ix_source_record_links_source
    ON source_record_links(data_source_id);

CREATE TRIGGER IF NOT EXISTS source_verification_events_immutable_update
    BEFORE UPDATE ON source_verification_events
    BEGIN SELECT RAISE(ABORT, 'verification events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS source_verification_events_immutable_delete
    BEFORE DELETE ON source_verification_events
    BEGIN SELECT RAISE(ABORT, 'verification events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS source_usage_decisions_immutable_update
    BEFORE UPDATE ON source_usage_decisions
    BEGIN SELECT RAISE(ABORT, 'usage decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS source_usage_decisions_immutable_delete
    BEFORE DELETE ON source_usage_decisions
    BEGIN SELECT RAISE(ABORT, 'usage decisions are append-only'); END;
"""

MIGRATION_024_NAME = "024_data_studio_phase3_manual_data_studio"

# Data Studio Phase 3 adds a governed Manual Data Studio: a staging layer
# for hand-authored Tamil/English/Tanglish language data, conversations,
# Q&A, instructions, dictionary entries, translations, and knowledge notes
# that the existing `dataset_records` manual-entry API has no columns for.
# It does not compete with that system -- an approved manual record only
# becomes a real `dataset_records` row through the explicit
# "create dataset candidate" action, which calls
# `DatasetService.create_record()` directly (the same bridge
# `feedback_dataset_service.export_candidate()` already uses), so every
# manual-derived record still passes through the existing duplicate-hash
# check, quality assessment, and dataset lifecycle unchanged.
#
# `manual_data_records` is the canonical record; `source_id` is a required
# link to a Phase 2 `data_sources` row (every manual record must be
# traceable to a source). `manual_data_record_revisions` is the append
# (never edit) content history -- `active_revision_id` points at the
# currently active one; approving a record never mutates its active
# revision, and a later edit creates a new draft revision instead,
# mirroring `feedback_candidate_versions`. `manual_data_reviews` and
# `manual_data_verifications` record human review/verification actions
# (a supporting or fact-checked-against source is linked via
# `manual_data_verifications.source_id`, separate from the record's
# primary source, covering the "primary source + supporting source"
# scenario without widening `source_record_links`'s CHECK constraint,
# which migration 023 cannot be altered to do). `manual_data_usage_decisions`
# and `manual_data_events` are append-only history (immutability enforced
# by trigger, matching the Phase 2 convention) so a usage-eligibility check
# or a lifecycle action can never be silently overwritten after the fact.
PHASE24_SCHEMA = """
CREATE TABLE IF NOT EXISTS manual_data_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_code TEXT NOT NULL UNIQUE,
    record_type TEXT NOT NULL CHECK (record_type IN (
        'plain_text','language_example','conversation','question_answer',
        'instruction_response','dictionary_entry','translation_pair',
        'tanglish_normalization','knowledge_note','grammar_example',
        'evaluation_case_draft'
    )),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','needs_review','needs_source_verification','needs_domain_review',
        'approved','rejected','archived'
    )),
    active_revision_id INTEGER,
    source_id INTEGER NOT NULL,
    primary_language TEXT NOT NULL DEFAULT 'unknown' CHECK (primary_language IN (
        'ta','en','tgl','mixed','unknown'
    )),
    input_language TEXT CHECK (input_language IN ('ta','en','tgl','mixed','unknown')),
    output_language TEXT CHECK (output_language IN ('ta','en','tgl','mixed','unknown')),
    domain TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    difficulty TEXT,
    audience TEXT,
    style TEXT,
    fact_dependency TEXT NOT NULL DEFAULT 'none' CHECK (fact_dependency IN (
        'none','low','medium','high'
    )),
    knowledge_risk TEXT NOT NULL DEFAULT 'language_only' CHECK (knowledge_risk IN (
        'language_only','general','domain_specific','high_risk','time_sensitive'
    )),
    creation_method TEXT NOT NULL DEFAULT 'admin_created' CHECK (creation_method IN (
        'human_created','admin_created','teacher_created','ai_assisted',
        'imported_manual','derived_manual'
    )),
    requested_uses_json TEXT NOT NULL DEFAULT '[]',
    approved_uses_json TEXT NOT NULL DEFAULT '[]',
    review_expiry_at TEXT,
    exported_dataset_record_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT,
    FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE RESTRICT,
    FOREIGN KEY (active_revision_id) REFERENCES manual_data_record_revisions(id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_manual_data_records_status ON manual_data_records(status);
CREATE INDEX IF NOT EXISTS ix_manual_data_records_record_type
    ON manual_data_records(record_type);
CREATE INDEX IF NOT EXISTS ix_manual_data_records_source ON manual_data_records(source_id);

CREATE TABLE IF NOT EXISTS manual_data_record_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_id INTEGER NOT NULL,
    revision_number INTEGER NOT NULL,
    title TEXT,
    input_text TEXT,
    output_text TEXT,
    instruction_text TEXT,
    response_text TEXT,
    question_text TEXT,
    answer_text TEXT,
    tamil_text TEXT,
    english_text TEXT,
    tanglish_text TEXT,
    word TEXT,
    part_of_speech TEXT,
    meanings_json TEXT NOT NULL DEFAULT '[]',
    examples_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL,
    change_summary TEXT NOT NULL DEFAULT '',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES manual_data_records(id) ON DELETE RESTRICT,
    UNIQUE(record_id, revision_number)
);
CREATE INDEX IF NOT EXISTS ix_manual_data_record_revisions_record
    ON manual_data_record_revisions(record_id);
CREATE INDEX IF NOT EXISTS ix_manual_data_record_revisions_hash
    ON manual_data_record_revisions(content_hash);

CREATE TABLE IF NOT EXISTS manual_data_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    review_type TEXT NOT NULL CHECK (review_type IN (
        'language','translation','factual','domain','general'
    )),
    review_status TEXT NOT NULL CHECK (review_status IN (
        'approved','rejected','changes_requested'
    )),
    reviewer_admin_public_id TEXT NOT NULL,
    comments TEXT NOT NULL DEFAULT '',
    language_score REAL,
    meaning_score REAL,
    naturalness_score REAL,
    factual_score REAL,
    source_score REAL,
    overall_score REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES manual_data_records(id) ON DELETE RESTRICT,
    FOREIGN KEY (revision_id) REFERENCES manual_data_record_revisions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_manual_data_reviews_record ON manual_data_reviews(record_id);

CREATE TABLE IF NOT EXISTS manual_data_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    verification_type TEXT NOT NULL CHECK (verification_type IN (
        'source_verification','factual_verification','domain_verification',
        'time_sensitivity_revalidation'
    )),
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK (verification_status IN (
        'pending','verified','rejected','expired'
    )),
    source_id INTEGER,
    verified_by_admin_public_id TEXT,
    verification_notes TEXT NOT NULL DEFAULT '',
    verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES manual_data_records(id) ON DELETE RESTRICT,
    FOREIGN KEY (revision_id) REFERENCES manual_data_record_revisions(id) ON DELETE RESTRICT,
    FOREIGN KEY (source_id) REFERENCES data_sources(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_manual_data_verifications_record
    ON manual_data_verifications(record_id);

CREATE TABLE IF NOT EXISTS manual_data_usage_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    target_use TEXT NOT NULL CHECK (target_use IN (
        'rag','training','evaluation','commercial','public_export','redistribution'
    )),
    allowed INTEGER NOT NULL CHECK (allowed IN (0,1)),
    decision_code TEXT NOT NULL,
    blocking_reasons_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    evaluated_by_admin_public_id TEXT,
    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES manual_data_records(id) ON DELETE RESTRICT,
    FOREIGN KEY (revision_id) REFERENCES manual_data_record_revisions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_manual_data_usage_decisions_record_target
    ON manual_data_usage_decisions(record_id, target_use);

CREATE TABLE IF NOT EXISTS manual_data_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    status_before TEXT,
    status_after TEXT,
    performed_by_admin_public_id TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (record_id) REFERENCES manual_data_records(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_manual_data_events_record ON manual_data_events(record_id);

CREATE TRIGGER IF NOT EXISTS manual_data_usage_decisions_immutable_update
    BEFORE UPDATE ON manual_data_usage_decisions
    BEGIN SELECT RAISE(ABORT, 'usage decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS manual_data_usage_decisions_immutable_delete
    BEFORE DELETE ON manual_data_usage_decisions
    BEGIN SELECT RAISE(ABORT, 'usage decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS manual_data_events_immutable_update
    BEFORE UPDATE ON manual_data_events
    BEGIN SELECT RAISE(ABORT, 'manual data events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS manual_data_events_immutable_delete
    BEFORE DELETE ON manual_data_events
    BEGIN SELECT RAISE(ABORT, 'manual data events are append-only'); END;
"""

MIGRATION_025_NAME = "025_data_studio_phase4_pdf_research_workspace"

# Data Studio Phase 4 enhances the existing Phase 5 (`005_phase5_document_processing`)
# PDF pipeline with a governed review workspace -- it does not replace or
# duplicate that pipeline. `document_pages.raw_text`/`cleaned_text` and the
# existing `document_page_revisions` table (already append-only, already
# immutable by trigger) continue to work exactly as before; `edit_page()`
# already never overwrites `raw_text`. What was missing:
#
# - a durable, append-only record of every *extraction attempt* itself
#   (today, re-running extraction legitimately overwrites
#   `document_pages.raw_text` with the newest attempt -- desired behavior,
#   but it previously left no trace of the prior attempt at all).
#   `document_page_extractions` fills that gap without changing what
#   `document_pages.raw_text` means or how reprocessing works.
# - a human *review* outcome, which is a different question from
#   *extraction* outcome (`document_pages.extraction_status` already
#   answers "did extraction succeed"; nothing previously answered "has an
#   admin approved this page's content"). Modeled as new columns on
#   `document_pages` (`review_status` et al.) plus an append-only
#   `document_page_review_events` history table, mirroring
#   `source_verification_events`'s shape.
# - cross-page repeated header/footer/page-number detection with a bulk
#   accept/reject action. The existing `clean_document_text()` only ever
#   flagged a single page's boundary lines as a *candidate*; nothing
#   aggregated that signal across a document or offered removal.
#   `document_repeated_elements` fills that gap.
#
# `document_page_regions` (bounding-box layout analysis) and
# `document_cleanup_profiles` (multiple configurable preprocessing
# profiles) are deliberately not created here -- see
# docs/data_studio/phase4_pdf_research_workspace_plan.md section 2 for
# why. Source linking uses the *existing* `source_record_links` table
# (`entity_type='document'`, already a valid enum value since Phase 2)
# rather than a new column, so no document_sources schema change is
# needed for that at all.
PHASE25_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "document_pages": [
        ("review_status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("reviewed_by_admin_public_id", "TEXT"),
        ("reviewed_at", "TEXT"),
        ("review_notes", "TEXT NOT NULL DEFAULT ''"),
        ("approved_revision_number", "INTEGER"),
    ],
}

PHASE25_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_page_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_page_id INTEGER NOT NULL,
    extraction_method TEXT NOT NULL CHECK (extraction_method IN (
        'embedded','ocr','hybrid','manual','failed'
    )),
    raw_text TEXT,
    raw_text_hash TEXT,
    ocr_engine TEXT,
    ocr_engine_version TEXT,
    ocr_language_mode TEXT,
    ocr_confidence REAL CHECK (ocr_confidence IS NULL OR ocr_confidence BETWEEN 0 AND 1),
    preprocessing_metadata_json TEXT NOT NULL DEFAULT '{}',
    extraction_warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_admin_public_id TEXT NOT NULL,
    FOREIGN KEY (document_page_id) REFERENCES document_pages(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_document_page_extractions_page
    ON document_page_extractions(document_page_id);

CREATE TABLE IF NOT EXISTS document_page_review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_page_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'approve','reject','exclude','request_correction','request_ocr_rerun',
        'request_extraction_rerun','restore_previous_revision','reopen'
    )),
    review_status_after TEXT NOT NULL,
    performed_by_admin_public_id TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_page_id) REFERENCES document_pages(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_document_page_review_events_page
    ON document_page_review_events(document_page_id);

CREATE TABLE IF NOT EXISTS document_repeated_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    normalized_text TEXT NOT NULL,
    element_type TEXT NOT NULL CHECK (element_type IN (
        'header','footer','page_number','unknown'
    )),
    page_occurrences_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status TEXT NOT NULL DEFAULT 'suggested' CHECK (status IN (
        'suggested','accepted','rejected','applied'
    )),
    reviewed_by_admin_public_id TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_document_repeated_elements_document
    ON document_repeated_elements(document_source_id);
CREATE INDEX IF NOT EXISTS ix_document_repeated_elements_status
    ON document_repeated_elements(document_source_id, status);

CREATE TRIGGER IF NOT EXISTS document_page_extractions_immutable_update
    BEFORE UPDATE ON document_page_extractions
    BEGIN SELECT RAISE(ABORT, 'document page extractions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS document_page_extractions_immutable_delete
    BEFORE DELETE ON document_page_extractions
    BEGIN SELECT RAISE(ABORT, 'document page extractions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS document_page_review_events_immutable_update
    BEFORE UPDATE ON document_page_review_events
    BEGIN SELECT RAISE(ABORT, 'document page review events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS document_page_review_events_immutable_delete
    BEFORE DELETE ON document_page_review_events
    BEGIN SELECT RAISE(ABORT, 'document page review events are append-only'); END;
"""

MIGRATION_026_NAME = "026_data_studio_phase5_semantic_chunk_structured_record_studio"

# Data Studio Phase 5 enhances the existing segmentation/candidate pipeline
# (`DocumentService.segment()`/`document_candidates`, Phase 5 of the original
# document-processing build) with chunk-level typing, hierarchy, and
# fine-grained provenance -- it does not replace or duplicate that pipeline.
# `document_candidates` continues to serve the plain pretrain-window
# Candidates tab exactly as before.
#
# `semantic_chunks`/`semantic_chunk_revisions`/`semantic_chunk_relations`/
# `semantic_chunk_reviews`/`semantic_chunk_events` are new because nothing
# existing provides chunk typing (heading/definition/dictionary_entry/...),
# hierarchy (parent/child, reading order), or sub-page provenance (character
# offsets/locators) -- `document_candidates` only ever had a flat page range.
#
# `structured_record_candidates`/`structured_record_candidate_revisions`/
# `structured_record_reviews` are a new, independent staging layer mirroring
# `manual_data_records`'s shape and lifecycle style but NOT reusing that
# table directly -- see docs/data_studio/phase5_semantic_chunk_structured_record_plan.md
# section 4 for why (the codebase's own convention is multiple independent
# candidate-staging tables, each with its own thin bridge into
# `dataset_records`, rather than retrofitting an already-shipped table with
# new chunk-lineage columns it was never designed to hold). The
# `record_type -> DatasetRecordType` mapping is imported directly from
# `core_model.manual_data.DATASET_RECORD_TYPE_MAP` (not duplicated).
PHASE26_SCHEMA = """
CREATE TABLE IF NOT EXISTS semantic_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    chunk_code TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    data_source_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','needs_review','needs_structure_review','needs_content_review',
        'approved','rejected','excluded','archived'
    )),
    chunk_type TEXT NOT NULL DEFAULT 'unknown' CHECK (chunk_type IN (
        'heading','subheading','paragraph','definition','example','dictionary_entry',
        'grammar_rule','question','answer','instruction','response','translation_source',
        'translation_target','tanglish_text','tamil_text','english_text','table','table_row',
        'list','footnote','caption','reference','metadata','irrelevant','unknown'
    )),
    active_revision_id INTEGER,
    parent_chunk_id INTEGER,
    reading_order INTEGER NOT NULL DEFAULT 0,
    language TEXT NOT NULL DEFAULT 'unknown',
    domain TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE RESTRICT,
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE RESTRICT,
    FOREIGN KEY (parent_chunk_id) REFERENCES semantic_chunks(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_semantic_chunks_document ON semantic_chunks(document_source_id);
CREATE INDEX IF NOT EXISTS ix_semantic_chunks_status ON semantic_chunks(document_source_id,status);
CREATE INDEX IF NOT EXISTS ix_semantic_chunks_parent ON semantic_chunks(parent_chunk_id);

CREATE TABLE IF NOT EXISTS semantic_chunk_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    chunk_id INTEGER NOT NULL,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    document_page_id INTEGER,
    page_number INTEGER,
    extraction_id INTEGER,
    page_revision_id INTEGER,
    start_locator_json TEXT NOT NULL DEFAULT '{}',
    end_locator_json TEXT NOT NULL DEFAULT '{}',
    generation_method TEXT NOT NULL DEFAULT 'manual' CHECK (generation_method IN (
        'existing_segmenter','paragraph_boundary','heading_boundary','manual','imported'
    )),
    confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    warnings_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    change_summary TEXT NOT NULL DEFAULT '',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES semantic_chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (document_page_id) REFERENCES document_pages(id) ON DELETE SET NULL,
    FOREIGN KEY (extraction_id) REFERENCES document_page_extractions(id) ON DELETE SET NULL,
    FOREIGN KEY (page_revision_id) REFERENCES document_page_revisions(id) ON DELETE SET NULL,
    UNIQUE(chunk_id, revision_number)
);
CREATE INDEX IF NOT EXISTS ix_semantic_chunk_revisions_chunk ON semantic_chunk_revisions(chunk_id);
CREATE INDEX IF NOT EXISTS ix_semantic_chunk_revisions_hash ON semantic_chunk_revisions(content_hash);

CREATE TABLE IF NOT EXISTS semantic_chunk_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    source_chunk_id INTEGER NOT NULL,
    target_chunk_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'derived_from_page','continues_from','continues_to','child_of','table_contains',
        'definition_of','example_of','answer_to','translation_of'
    )),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_chunk_id) REFERENCES semantic_chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (target_chunk_id) REFERENCES semantic_chunks(id) ON DELETE CASCADE,
    UNIQUE(source_chunk_id, target_chunk_id, relationship_type)
);
CREATE INDEX IF NOT EXISTS ix_semantic_chunk_relations_source ON semantic_chunk_relations(source_chunk_id);
CREATE INDEX IF NOT EXISTS ix_semantic_chunk_relations_target ON semantic_chunk_relations(target_chunk_id);

CREATE TABLE IF NOT EXISTS semantic_chunk_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    chunk_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'approve','request_boundary_correction','request_classification_correction',
        'reject','exclude','archive','reopen'
    )),
    status_after TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES semantic_chunks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_semantic_chunk_reviews_chunk ON semantic_chunk_reviews(chunk_id);

CREATE TABLE IF NOT EXISTS semantic_chunk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    chunk_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    performed_by_admin_public_id TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES semantic_chunks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_semantic_chunk_events_chunk ON semantic_chunk_events(chunk_id);

CREATE TABLE IF NOT EXISTS structured_record_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_code TEXT NOT NULL UNIQUE,
    record_type TEXT NOT NULL CHECK (record_type IN (
        'plain_text','language_example','conversation','question_answer',
        'instruction_response','dictionary_entry','translation_pair',
        'tanglish_normalization','knowledge_note','grammar_example','rag_chunk'
    )),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','needs_review','approved','rejected','archived'
    )),
    data_source_id INTEGER NOT NULL,
    document_source_id INTEGER,
    primary_chunk_id INTEGER,
    active_revision_id INTEGER,
    requested_uses_json TEXT NOT NULL DEFAULT '[]',
    approved_uses_json TEXT NOT NULL DEFAULT '[]',
    exported_dataset_record_public_id TEXT,
    rag_handoff_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT,
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE RESTRICT,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE SET NULL,
    FOREIGN KEY (primary_chunk_id) REFERENCES semantic_chunks(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_structured_record_candidates_status
    ON structured_record_candidates(status);
CREATE INDEX IF NOT EXISTS ix_structured_record_candidates_type
    ON structured_record_candidates(record_type);

CREATE TABLE IF NOT EXISTS structured_record_candidate_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'evidence',
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (candidate_id) REFERENCES structured_record_candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES semantic_chunks(id) ON DELETE RESTRICT,
    UNIQUE(candidate_id, chunk_id, role)
);
CREATE INDEX IF NOT EXISTS ix_structured_record_candidate_chunks_candidate
    ON structured_record_candidate_chunks(candidate_id);

CREATE TABLE IF NOT EXISTS structured_record_candidate_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    title TEXT,
    text TEXT,
    question TEXT,
    answer TEXT,
    instruction TEXT,
    context TEXT,
    response TEXT,
    word TEXT,
    part_of_speech TEXT,
    meanings_json TEXT NOT NULL DEFAULT '[]',
    examples_json TEXT NOT NULL DEFAULT '[]',
    synonyms_json TEXT NOT NULL DEFAULT '[]',
    antonyms_json TEXT NOT NULL DEFAULT '[]',
    related_words_json TEXT NOT NULL DEFAULT '[]',
    source_language TEXT,
    source_text TEXT,
    target_language TEXT,
    target_text TEXT,
    tanglish_text TEXT,
    normalized_tamil TEXT,
    english_meaning TEXT,
    grammar_rule TEXT,
    correct_example TEXT,
    incorrect_example TEXT,
    correction TEXT,
    origin TEXT NOT NULL DEFAULT 'source_grounded' CHECK (origin IN (
        'source_grounded','admin_authored','human_synthesized'
    )),
    content_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    change_summary TEXT NOT NULL DEFAULT '',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES structured_record_candidates(id) ON DELETE CASCADE,
    UNIQUE(candidate_id, revision_number)
);
CREATE INDEX IF NOT EXISTS ix_structured_record_candidate_revisions_candidate
    ON structured_record_candidate_revisions(candidate_id);
CREATE INDEX IF NOT EXISTS ix_structured_record_candidate_revisions_hash
    ON structured_record_candidate_revisions(content_hash);

CREATE TABLE IF NOT EXISTS structured_record_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN (
        'approved','rejected','changes_requested'
    )),
    comments TEXT NOT NULL DEFAULT '',
    reviewer_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES structured_record_candidates(id) ON DELETE RESTRICT,
    FOREIGN KEY (revision_id) REFERENCES structured_record_candidate_revisions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_structured_record_reviews_candidate
    ON structured_record_reviews(candidate_id);

CREATE TRIGGER IF NOT EXISTS semantic_chunk_revisions_immutable_update
    BEFORE UPDATE ON semantic_chunk_revisions
    BEGIN SELECT RAISE(ABORT, 'semantic chunk revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS semantic_chunk_revisions_immutable_delete
    BEFORE DELETE ON semantic_chunk_revisions
    BEGIN SELECT RAISE(ABORT, 'semantic chunk revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS semantic_chunk_events_immutable_update
    BEFORE UPDATE ON semantic_chunk_events
    BEGIN SELECT RAISE(ABORT, 'semantic chunk events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS semantic_chunk_events_immutable_delete
    BEFORE DELETE ON semantic_chunk_events
    BEGIN SELECT RAISE(ABORT, 'semantic chunk events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS structured_record_candidate_revisions_immutable_update
    BEFORE UPDATE ON structured_record_candidate_revisions
    BEGIN SELECT RAISE(ABORT, 'structured record candidate revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS structured_record_candidate_revisions_immutable_delete
    BEFORE DELETE ON structured_record_candidate_revisions
    BEGIN SELECT RAISE(ABORT, 'structured record candidate revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS structured_record_reviews_immutable_update
    BEFORE UPDATE ON structured_record_reviews
    BEGIN SELECT RAISE(ABORT, 'structured record reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS structured_record_reviews_immutable_delete
    BEFORE DELETE ON structured_record_reviews
    BEGIN SELECT RAISE(ABORT, 'structured record reviews are append-only'); END;
"""

MIGRATION_027_NAME = "027_data_studio_phase6_quality_duplicate_conflict_approval"

# Data Studio Phase 6 adds a governance layer *above* six existing,
# independently-reviewed entity types (document_pages, manual_data_records,
# semantic_chunks, structured_record_candidates, document_candidates,
# dataset_records) rather than replacing any of their own lifecycles,
# quality scoring, or duplicate/conflict detection. See
# docs/data_studio/phase6_quality_duplicate_conflict_approval_plan.md
# section 3 for the full architecture rationale. Entities are referenced
# polymorphically (entity_type, entity_public_id), mirroring Phase 2's
# `source_record_links` convention, rather than by internal FK, since
# the six entity types live in six different tables with independent id
# sequences.
PHASE27_SCHEMA = """
CREATE TABLE IF NOT EXISTS governance_review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    review_code TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL CHECK (entity_type IN (
        'document_page','manual_data_record','semantic_chunk',
        'structured_record_candidate','document_candidate','dataset_record'
    )),
    entity_public_id TEXT NOT NULL,
    entity_revision_public_id TEXT,
    source_public_id TEXT,
    document_public_id TEXT,
    page_public_id TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
        'open','in_review','waiting_for_correction','waiting_for_source',
        'waiting_for_verification','resolved','rejected','archived'
    )),
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN (
        'low','normal','high','urgent'
    )),
    assigned_admin_public_id TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);
-- A partial (not table-wide) uniqueness rule: only one *unresolved*
-- review item may exist per entity at a time. A table-wide
-- UNIQUE(entity_type, entity_public_id, status) would also block a
-- second-ever "resolved" row for the same entity, which is wrong --
-- an entity can legitimately be opened, resolved, reopened, and
-- resolved again many times over its life.
CREATE UNIQUE INDEX IF NOT EXISTS ux_governance_review_items_open_entity
    ON governance_review_items(entity_type, entity_public_id)
    WHERE status NOT IN ('resolved','rejected','archived');
CREATE INDEX IF NOT EXISTS ix_governance_review_items_entity
    ON governance_review_items(entity_type, entity_public_id);
CREATE INDEX IF NOT EXISTS ix_governance_review_items_status
    ON governance_review_items(status);
CREATE INDEX IF NOT EXISTS ix_governance_review_items_priority
    ON governance_review_items(priority);

CREATE TABLE IF NOT EXISTS governance_review_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    review_item_id INTEGER NOT NULL,
    issue_code TEXT NOT NULL,
    issue_category TEXT NOT NULL CHECK (issue_category IN (
        'language_quality','meaning_quality','factual_accuracy','source_traceability',
        'rights_restriction','verification_missing','exact_duplicate','normalized_duplicate',
        'source_overlap','dictionary_sense_conflict','answer_conflict','translation_conflict',
        'chunk_overlap','chunk_gap','revision_conflict','ai_assisted_unreviewed',
        'high_risk_unverified','time_sensitive_expired','format_invalid','export_duplicate'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','critical')),
    is_blocking INTEGER NOT NULL DEFAULT 0 CHECK (is_blocking IN (0,1)),
    blocking_targets_json TEXT NOT NULL DEFAULT '[]',
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    detector TEXT NOT NULL,
    detector_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    FOREIGN KEY (review_item_id) REFERENCES governance_review_items(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_governance_review_issues_item
    ON governance_review_issues(review_item_id);

CREATE TABLE IF NOT EXISTS governance_duplicate_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    group_code TEXT NOT NULL UNIQUE,
    duplicate_type TEXT NOT NULL CHECK (duplicate_type IN (
        'exact','normalized','source_locator','export_duplicate'
    )),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
    canonical_entity_type TEXT,
    canonical_entity_public_id TEXT,
    match_reason TEXT NOT NULL,
    match_value TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_governance_duplicate_groups_status
    ON governance_duplicate_groups(status);

CREATE TABLE IF NOT EXISTS governance_duplicate_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_public_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member','canonical')),
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES governance_duplicate_groups(id) ON DELETE CASCADE,
    UNIQUE(group_id, entity_type, entity_public_id)
);
CREATE INDEX IF NOT EXISTS ix_governance_duplicate_group_members_group
    ON governance_duplicate_group_members(group_id);

CREATE TABLE IF NOT EXISTS governance_conflict_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    group_code TEXT NOT NULL UNIQUE,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN (
        'dictionary_sense','answer','translation','source_fact',
        'chunk_overlap','chunk_gap','revision','classification'
    )),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
    match_reason TEXT NOT NULL,
    match_value TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_governance_conflict_groups_status
    ON governance_conflict_groups(status);

CREATE TABLE IF NOT EXISTS governance_conflict_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_public_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES governance_conflict_groups(id) ON DELETE CASCADE,
    UNIQUE(group_id, entity_type, entity_public_id)
);
CREATE INDEX IF NOT EXISTS ix_governance_conflict_group_members_group
    ON governance_conflict_group_members(group_id);

CREATE TABLE IF NOT EXISTS governance_resolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    duplicate_group_id INTEGER,
    conflict_group_id INTEGER,
    resolution_action TEXT NOT NULL CHECK (resolution_action IN (
        'keep_all','choose_canonical','mark_alternate','merge_manually','reject_selected',
        'archive_selected','not_a_duplicate','keep_both_with_context','mark_alternate_sense',
        'mark_alternate_answer','choose_preferred_translation','request_domain_review',
        'request_source_verification','resolve_with_new_revision'
    )),
    resolution_reason TEXT NOT NULL,
    selected_entities_json TEXT NOT NULL DEFAULT '[]',
    created_revision_ids_json TEXT NOT NULL DEFAULT '[]',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (duplicate_group_id) REFERENCES governance_duplicate_groups(id) ON DELETE SET NULL,
    FOREIGN KEY (conflict_group_id) REFERENCES governance_conflict_groups(id) ON DELETE SET NULL,
    CHECK ((duplicate_group_id IS NOT NULL) OR (conflict_group_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_governance_resolutions_duplicate_group
    ON governance_resolutions(duplicate_group_id);
CREATE INDEX IF NOT EXISTS ix_governance_resolutions_conflict_group
    ON governance_resolutions(conflict_group_id);

CREATE TABLE IF NOT EXISTS governance_target_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    review_item_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_public_id TEXT NOT NULL,
    target_use TEXT NOT NULL CHECK (target_use IN (
        'rag','training','evaluation','commercial','public_export',
        'redistribution','dataset_export','rag_handoff'
    )),
    decision TEXT NOT NULL CHECK (decision IN (
        'allowed','blocked','needs_review','not_requested'
    )),
    decision_code TEXT NOT NULL,
    blocking_issue_ids_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    required_actions_json TEXT NOT NULL DEFAULT '[]',
    is_override INTEGER NOT NULL DEFAULT 0 CHECK (is_override IN (0,1)),
    override_reason TEXT,
    decided_by_admin_public_id TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    FOREIGN KEY (review_item_id) REFERENCES governance_review_items(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_governance_target_approvals_entity
    ON governance_target_approvals(entity_type, entity_public_id, target_use);
CREATE INDEX IF NOT EXISTS ix_governance_target_approvals_item
    ON governance_target_approvals(review_item_id);

CREATE TABLE IF NOT EXISTS governance_review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    review_item_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    performed_by_admin_public_id TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_item_id) REFERENCES governance_review_items(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_governance_review_events_item
    ON governance_review_events(review_item_id);

CREATE TRIGGER IF NOT EXISTS governance_review_issues_immutable_update
    BEFORE UPDATE OF issue_code, issue_category, severity, message, detector, created_at
    ON governance_review_issues
    BEGIN SELECT RAISE(ABORT, 'governance review issue facts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governance_review_issues_immutable_delete
    BEFORE DELETE ON governance_review_issues
    BEGIN SELECT RAISE(ABORT, 'governance review issues are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governance_resolutions_immutable_update
    BEFORE UPDATE ON governance_resolutions
    BEGIN SELECT RAISE(ABORT, 'governance resolutions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governance_resolutions_immutable_delete
    BEFORE DELETE ON governance_resolutions
    BEGIN SELECT RAISE(ABORT, 'governance resolutions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governance_target_approvals_immutable_update
    BEFORE UPDATE ON governance_target_approvals
    BEGIN SELECT RAISE(ABORT, 'governance target approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governance_target_approvals_immutable_delete
    BEFORE DELETE ON governance_target_approvals
    BEGIN SELECT RAISE(ABORT, 'governance target approvals are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governance_review_events_immutable_update
    BEFORE UPDATE ON governance_review_events
    BEGIN SELECT RAISE(ABORT, 'governance review events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governance_review_events_immutable_delete
    BEFORE DELETE ON governance_review_events
    BEGIN SELECT RAISE(ABORT, 'governance review events are append-only'); END;
"""

MIGRATION_028_NAME = "028_data_studio_phase7_dataset_rag_training_integration"

# Data Studio Phase 7 adds a governed build/preflight/lineage layer
# *above* the existing dataset build/versioning system
# (`dataset_versions`/`dataset_version_items`/`dataset_build_jobs`/
# `dataset_exports`, unchanged), the existing RAG ingestion system, and
# the existing tokenizer/pretraining-readiness/instruction-tuning/
# evaluation/model-release systems -- see
# docs/data_studio/phase7_dataset_rag_training_integration_plan.md
# section 2 for the full architecture rationale. A governed build
# always produces its artifact (most commonly a real, existing
# `dataset_versions` row) through the *existing* builder; this phase
# never creates a second dataset-versioning system. Entities are
# referenced polymorphically (entity_type, entity_public_id), mirroring
# Phase 2's `source_record_links` and Phase 6's `governance_*`
# convention.
PHASE28_SCHEMA = """
CREATE TABLE IF NOT EXISTS governed_build_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_code TEXT NOT NULL UNIQUE,
    target_pipeline TEXT NOT NULL CHECK (target_pipeline IN (
        'dataset_version','rag','tokenizer','pretraining','instruction_tuning',
        'evaluation','commercial_release','public_export'
    )),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','preflight_running','preflight_ready','blocked','approved_to_build',
        'building','completed','failed','cancelled'
    )),
    build_label TEXT NOT NULL DEFAULT '',
    configuration_json TEXT NOT NULL DEFAULT '{}',
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    result_entity_type TEXT,
    result_entity_public_id TEXT,
    manifest_extension_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_governed_build_requests_status
    ON governed_build_requests(status);
CREATE INDEX IF NOT EXISTS ix_governed_build_requests_target
    ON governed_build_requests(target_pipeline);

CREATE TABLE IF NOT EXISTS governed_build_preflight_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_request_id INTEGER NOT NULL,
    target_pipeline TEXT NOT NULL,
    eligible_count INTEGER NOT NULL DEFAULT 0,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    excluded_count INTEGER NOT NULL DEFAULT 0,
    decision_summary_json TEXT NOT NULL DEFAULT '{}',
    source_summary_json TEXT NOT NULL DEFAULT '{}',
    rights_summary_json TEXT NOT NULL DEFAULT '{}',
    quality_summary_json TEXT NOT NULL DEFAULT '{}',
    duplicate_summary_json TEXT NOT NULL DEFAULT '{}',
    conflict_summary_json TEXT NOT NULL DEFAULT '{}',
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    record_type_distribution_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_admin_public_id TEXT NOT NULL,
    FOREIGN KEY (build_request_id) REFERENCES governed_build_requests(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_governed_build_preflight_results_request
    ON governed_build_preflight_results(build_request_id);

CREATE TABLE IF NOT EXISTS governed_build_request_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_request_id INTEGER NOT NULL,
    preflight_result_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_public_id TEXT NOT NULL,
    entity_revision_public_id TEXT,
    source_public_id TEXT,
    decision TEXT NOT NULL CHECK (decision IN ('eligible','blocked','warning','excluded')),
    decision_code TEXT NOT NULL,
    blocking_reasons_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    included INTEGER NOT NULL DEFAULT 0 CHECK (included IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (build_request_id) REFERENCES governed_build_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (preflight_result_id)
        REFERENCES governed_build_preflight_results(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_governed_build_request_items_request
    ON governed_build_request_items(build_request_id);
CREATE INDEX IF NOT EXISTS ix_governed_build_request_items_preflight
    ON governed_build_request_items(preflight_result_id);
CREATE INDEX IF NOT EXISTS ix_governed_build_request_items_entity
    ON governed_build_request_items(entity_type, entity_public_id);

CREATE TABLE IF NOT EXISTS pipeline_artifact_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_request_id INTEGER NOT NULL,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN (
        'dataset_version','rag_source','rag_index','tokenizer_corpus_build',
        'pretraining_job','instruction_tuning_experiment','evaluation_run',
        'model_release','export'
    )),
    artifact_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_admin_public_id TEXT NOT NULL,
    FOREIGN KEY (build_request_id) REFERENCES governed_build_requests(id) ON DELETE CASCADE,
    UNIQUE(build_request_id, artifact_type, artifact_public_id)
);
CREATE INDEX IF NOT EXISTS ix_pipeline_artifact_links_request
    ON pipeline_artifact_links(build_request_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_artifact_links_artifact
    ON pipeline_artifact_links(artifact_type, artifact_public_id);

CREATE TABLE IF NOT EXISTS lineage_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    upstream_entity_type TEXT NOT NULL,
    upstream_entity_id TEXT NOT NULL,
    downstream_entity_type TEXT NOT NULL,
    downstream_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'derived_from','included_in','exported_as','indexed_into','tokenized_into',
        'trained_from','evaluated_with','released_from','supersedes'
    )),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_admin_public_id TEXT NOT NULL,
    UNIQUE(upstream_entity_type, upstream_entity_id, downstream_entity_type,
        downstream_entity_id, relationship_type)
);
CREATE INDEX IF NOT EXISTS ix_lineage_edges_upstream
    ON lineage_edges(upstream_entity_type, upstream_entity_id);
CREATE INDEX IF NOT EXISTS ix_lineage_edges_downstream
    ON lineage_edges(downstream_entity_type, downstream_entity_id);

CREATE TABLE IF NOT EXISTS lineage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    build_request_id INTEGER,
    lineage_edge_id INTEGER,
    event_type TEXT NOT NULL,
    performed_by_admin_public_id TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (build_request_id) REFERENCES governed_build_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (lineage_edge_id) REFERENCES lineage_edges(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_lineage_events_request
    ON lineage_events(build_request_id);
CREATE INDEX IF NOT EXISTS ix_lineage_events_edge
    ON lineage_events(lineage_edge_id);

CREATE TRIGGER IF NOT EXISTS governed_build_preflight_results_immutable_update
    BEFORE UPDATE ON governed_build_preflight_results
    BEGIN SELECT RAISE(ABORT, 'governed build preflight results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS governed_build_preflight_results_immutable_delete
    BEFORE DELETE ON governed_build_preflight_results
    BEGIN SELECT RAISE(ABORT, 'governed build preflight results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS pipeline_artifact_links_immutable_update
    BEFORE UPDATE ON pipeline_artifact_links
    BEGIN SELECT RAISE(ABORT, 'pipeline artifact links are append-only'); END;
CREATE TRIGGER IF NOT EXISTS pipeline_artifact_links_immutable_delete
    BEFORE DELETE ON pipeline_artifact_links
    BEGIN SELECT RAISE(ABORT, 'pipeline artifact links are append-only'); END;
CREATE TRIGGER IF NOT EXISTS lineage_edges_immutable_update
    BEFORE UPDATE ON lineage_edges
    BEGIN SELECT RAISE(ABORT, 'lineage edges are append-only'); END;
CREATE TRIGGER IF NOT EXISTS lineage_edges_immutable_delete
    BEFORE DELETE ON lineage_edges
    BEGIN SELECT RAISE(ABORT, 'lineage edges are append-only'); END;
CREATE TRIGGER IF NOT EXISTS lineage_events_immutable_update
    BEFORE UPDATE ON lineage_events
    BEGIN SELECT RAISE(ABORT, 'lineage events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS lineage_events_immutable_delete
    BEFORE DELETE ON lineage_events
    BEGIN SELECT RAISE(ABORT, 'lineage events are append-only'); END;
"""

MIGRATION_029_NAME = "029_admin_assistant_phase8_floating_context_aware_assistant"

# Phase 8 extends the existing Admin Assistant (Phase 2's `admin_approvals`
# table, wired to a governed propose->review->execute lifecycle by
# migration 022) with richer preview/expiry/stale-detection columns --
# never a second proposal/execution table. Phase 8's own richer
# conceptual lifecycle (draft/preview_ready/awaiting_confirmation/
# confirmed/executing/completed/failed/cancelled/expired/rejected) is a
# derived, presentation-layer state computed from the existing `status`
# + `execution_status` + the new `expires_at` -- the existing 5-value
# `status` CHECK constraint is never touched. See
# docs/admin_assistant/phase8_floating_context_aware_admin_assistant_plan.md
# section 2-3 for the full rationale.
PHASE29_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "admin_approvals": [
        ("expires_at", "TEXT"),
        ("risk_level", "TEXT NOT NULL DEFAULT 'moderate'"),
        ("preview_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("stale_check_json", "TEXT NOT NULL DEFAULT '{}'"),
    ],
}

# Only genuinely new capabilities get new tables: bounded page-context
# snapshots (no equivalent exists anywhere), read-only tool-call logging
# (no equivalent exists anywhere), and structured feedback (no
# equivalent exists anywhere). Conversation storage itself reuses Phase
# 17's `conversation_sessions`/`conversation_turns`/`memory_items` via a
# new `participant_scope_key` convention rather than a new table.
PHASE29_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_assistant_context_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    conversation_session_id INTEGER,
    page_id TEXT NOT NULL,
    tab_id TEXT,
    entity_type TEXT,
    entity_public_id TEXT,
    revision_public_id TEXT,
    sanitized_context_json TEXT NOT NULL DEFAULT '{}',
    registry_version TEXT NOT NULL,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_session_id) REFERENCES conversation_sessions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_admin_assistant_context_snapshots_session
    ON admin_assistant_context_snapshots(conversation_session_id);
CREATE INDEX IF NOT EXISTS ix_admin_assistant_context_snapshots_page
    ON admin_assistant_context_snapshots(page_id);

CREATE TABLE IF NOT EXISTS admin_assistant_tool_invocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    conversation_session_id INTEGER,
    proposal_public_id TEXT,
    tool_name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'guide' CHECK (mode IN (
        'guide','data','governance','rag','model','system'
    )),
    input_summary_json TEXT NOT NULL DEFAULT '{}',
    result_summary_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'succeeded' CHECK (status IN (
        'succeeded','failed','denied','unavailable'
    )),
    error_code TEXT,
    performed_by_admin_public_id TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (conversation_session_id) REFERENCES conversation_sessions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_admin_assistant_tool_invocations_session
    ON admin_assistant_tool_invocations(conversation_session_id);
CREATE INDEX IF NOT EXISTS ix_admin_assistant_tool_invocations_tool
    ON admin_assistant_tool_invocations(tool_name);

CREATE TABLE IF NOT EXISTS admin_assistant_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    conversation_session_id INTEGER,
    message_reference TEXT,
    page_id TEXT,
    action_id TEXT,
    rating TEXT NOT NULL CHECK (rating IN (
        'helpful','not_helpful','incorrect_guidance','action_failed'
    )),
    comment TEXT NOT NULL DEFAULT '',
    registry_version TEXT NOT NULL,
    submitted_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_session_id) REFERENCES conversation_sessions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_admin_assistant_feedback_session
    ON admin_assistant_feedback(conversation_session_id);

CREATE TRIGGER IF NOT EXISTS admin_assistant_context_snapshots_immutable_update
    BEFORE UPDATE ON admin_assistant_context_snapshots
    BEGIN SELECT RAISE(ABORT, 'admin assistant context snapshots are append-only'); END;
CREATE TRIGGER IF NOT EXISTS admin_assistant_context_snapshots_immutable_delete
    BEFORE DELETE ON admin_assistant_context_snapshots
    BEGIN SELECT RAISE(ABORT, 'admin assistant context snapshots are append-only'); END;
CREATE TRIGGER IF NOT EXISTS admin_assistant_tool_invocations_immutable_delete
    BEFORE DELETE ON admin_assistant_tool_invocations
    BEGIN SELECT RAISE(ABORT, 'admin assistant tool invocations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS admin_assistant_feedback_immutable_update
    BEFORE UPDATE ON admin_assistant_feedback
    BEGIN SELECT RAISE(ABORT, 'admin assistant feedback is append-only'); END;
CREATE TRIGGER IF NOT EXISTS admin_assistant_feedback_immutable_delete
    BEFORE DELETE ON admin_assistant_feedback
    BEGIN SELECT RAISE(ABORT, 'admin assistant feedback is append-only'); END;
"""

MIGRATION_030_NAME = "030_external_data_provider_registry"

# Phase 9: a registry of *external data providers* (organizations,
# websites, APIs Brud AI could potentially pull training/RAG source
# material from) -- structurally separate from both the existing
# Source & Rights Registry (`data_sources`, one row per piece of
# content already inside Brud AI with rights decided) and Phase 15's
# inference-model routing (`inference_model_assignments`, which model
# answers a chat request). Registering, verifying, or enabling a
# provider here never writes to `data_sources` or any governance/
# lineage table -- provider approval structurally cannot imply dataset,
# RAG, training, or commercial approval. See
# docs/data_providers/phase9_external_data_provider_registry_plan.md.
#
# No encrypted/reversible secret storage exists anywhere in this
# codebase (confirmed by direct inspection -- `pwdlib.PasswordHash` is
# a one-way password hash, not usable for a credential that must later
# be sent to an external API). `external_data_provider_credentials`
# therefore stores only a `reference_key` (an environment variable
# name) and derived status -- never a secret value. See plan.md
# section 5 for the full, honestly-documented limitation.
PHASE30_SCHEMA = """
CREATE TABLE IF NOT EXISTS external_data_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    provider_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL CHECK (provider_type IN (
        'dataset_catalogue','repository_host','government_portal',
        'research_institution','university_library','public_api',
        'file_repository','custom_api','manual_source'
    )),
    description TEXT NOT NULL DEFAULT '',
    official_website TEXT,
    catalogue_url TEXT,
    access_mode TEXT NOT NULL CHECK (access_mode IN (
        'public','gated','private','mixed','manual'
    )),
    authentication_type TEXT NOT NULL DEFAULT 'none' CHECK (authentication_type IN (
        'none','api_key','bearer_token','oauth','username_password',
        'custom_header','manual_login'
    )),
    trust_status TEXT NOT NULL DEFAULT 'unverified' CHECK (trust_status IN (
        'unverified','domain_verified','organization_verified','government_verified',
        'research_verified','community_reviewed','restricted','blocked'
    )),
    lifecycle_status TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_status IN (
        'draft','connection_tested','needs_review','approved','enabled',
        'disabled','restricted','blocked','archived'
    )),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    supports_anonymous_read INTEGER NOT NULL DEFAULT 0 CHECK (supports_anonymous_read IN (0,1)),
    supports_authenticated_read INTEGER NOT NULL DEFAULT 0 CHECK (supports_authenticated_read IN (0,1)),
    supports_download INTEGER NOT NULL DEFAULT 0 CHECK (supports_download IN (0,1)),
    supports_api_search INTEGER NOT NULL DEFAULT 0 CHECK (supports_api_search IN (0,1)),
    supports_manual_discovery INTEGER NOT NULL DEFAULT 0 CHECK (supports_manual_discovery IN (0,1)),
    supports_write INTEGER NOT NULL DEFAULT 0 CHECK (supports_write IN (0,1)),
    rate_limit_notes TEXT NOT NULL DEFAULT '',
    terms_url TEXT,
    privacy_url TEXT,
    support_url TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_external_data_providers_type
    ON external_data_providers(provider_type);
CREATE INDEX IF NOT EXISTS ix_external_data_providers_lifecycle
    ON external_data_providers(lifecycle_status);

CREATE TABLE IF NOT EXISTS external_data_provider_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    provider_id INTEGER NOT NULL,
    domain TEXT NOT NULL,
    domain_type TEXT NOT NULL CHECK (domain_type IN (
        'official','api','download','documentation','authentication','mirror'
    )),
    verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK (verification_status IN (
        'unverified','verified','failed'
    )),
    verified_at TEXT,
    verification_evidence TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id) ON DELETE CASCADE,
    UNIQUE(provider_id, domain, domain_type)
);
CREATE INDEX IF NOT EXISTS ix_external_data_provider_domains_provider
    ON external_data_provider_domains(provider_id);

CREATE TABLE IF NOT EXISTS external_data_provider_capabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    provider_id INTEGER NOT NULL,
    capability_type TEXT NOT NULL CHECK (capability_type IN (
        'search_datasets','read_metadata','read_dataset_card','read_licence',
        'list_files','download_sample','download_full','upload','write_metadata'
    )),
    language_codes_json TEXT NOT NULL DEFAULT '[]',
    dataset_categories_json TEXT NOT NULL DEFAULT '[]',
    connector_type TEXT,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id) ON DELETE CASCADE,
    UNIQUE(provider_id, capability_type)
);
CREATE INDEX IF NOT EXISTS ix_external_data_provider_capabilities_provider
    ON external_data_provider_capabilities(provider_id);

CREATE TABLE IF NOT EXISTS external_data_provider_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    provider_id INTEGER NOT NULL,
    credential_type TEXT NOT NULL CHECK (credential_type IN (
        'api_key','bearer_token','oauth','username_password','custom_header','manual_login'
    )),
    reference_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_configured' CHECK (status IN (
        'not_configured','configured','test_succeeded','test_failed','revoked'
    )),
    last_rotated_at TEXT,
    last_tested_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT,
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id) ON DELETE CASCADE,
    UNIQUE(provider_id, credential_type)
);
CREATE INDEX IF NOT EXISTS ix_external_data_provider_credentials_provider
    ON external_data_provider_credentials(provider_id);

CREATE TABLE IF NOT EXISTS external_data_provider_connection_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    provider_id INTEGER NOT NULL,
    result TEXT NOT NULL CHECK (result IN (
        'success','partial','failed','authentication_required','rate_limited','unsupported'
    )),
    capability_type TEXT,
    latency_ms INTEGER,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    error_code TEXT,
    tested_by_admin_public_id TEXT NOT NULL,
    tested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_data_provider_connection_tests_provider
    ON external_data_provider_connection_tests(provider_id);

CREATE TABLE IF NOT EXISTS external_data_provider_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    provider_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'provider_registered','provider_updated','domain_added','domain_verified',
        'capability_updated','credential_configured','credential_revoked',
        'connection_tested','verification_evaluated','provider_enabled',
        'provider_disabled','provider_restricted','provider_blocked','provider_archived'
    )),
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_data_provider_events_provider
    ON external_data_provider_events(provider_id);

CREATE TRIGGER IF NOT EXISTS external_data_providers_immutable_delete
    BEFORE DELETE ON external_data_providers
    BEGIN SELECT RAISE(ABORT, 'external data providers are archived, never deleted'); END;
CREATE TRIGGER IF NOT EXISTS external_data_provider_domains_immutable_delete
    BEFORE DELETE ON external_data_provider_domains
    BEGIN SELECT RAISE(ABORT, 'external data provider domains are never deleted'); END;
CREATE TRIGGER IF NOT EXISTS external_data_provider_capabilities_immutable_delete
    BEFORE DELETE ON external_data_provider_capabilities
    BEGIN SELECT RAISE(ABORT, 'external data provider capabilities are never deleted'); END;
CREATE TRIGGER IF NOT EXISTS external_data_provider_credentials_immutable_delete
    BEFORE DELETE ON external_data_provider_credentials
    BEGIN SELECT RAISE(ABORT, 'external data provider credentials are revoked, never deleted'); END;
CREATE TRIGGER IF NOT EXISTS external_data_provider_connection_tests_immutable_update
    BEFORE UPDATE ON external_data_provider_connection_tests
    BEGIN SELECT RAISE(ABORT, 'connection test results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_data_provider_connection_tests_immutable_delete
    BEFORE DELETE ON external_data_provider_connection_tests
    BEGIN SELECT RAISE(ABORT, 'connection test results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_data_provider_events_immutable_update
    BEFORE UPDATE ON external_data_provider_events
    BEGIN SELECT RAISE(ABORT, 'provider events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_data_provider_events_immutable_delete
    BEFORE DELETE ON external_data_provider_events
    BEGIN SELECT RAISE(ABORT, 'provider events are append-only'); END;
"""

MIGRATION_031_NAME = "031_live_dataset_discovery_normalization_comparison"

# Phase 10: live, read-only dataset discovery and comparison across the
# Phase 9 provider registry. No dataset is ever downloaded, imported,
# licence-verified, or approved by anything in this schema block --
# `licence_status`/`commercial_use_status`/`training_use_status`/
# `rag_use_status`/`evaluation_use_status` are structurally incapable of
# reaching an "approved"/"verified" value here (see
# core_model.data_discovery.USE_APPROVAL_STATUSES /
# LICENCE_STATUSES -- neither CHECK constraint below includes one). See
# docs/data_discovery/phase10_live_dataset_discovery_plan.md.
PHASE31_SCHEMA = """
CREATE TABLE IF NOT EXISTS external_dataset_search_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    session_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','ready','running','partial','completed','failed','cancelled','expired'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    assistant_conversation_session_id INTEGER,
    current_stage TEXT NOT NULL DEFAULT 'requirement',
    result_count INTEGER NOT NULL DEFAULT 0,
    provider_count INTEGER NOT NULL DEFAULT 0,
    successful_provider_count INTEGER NOT NULL DEFAULT 0,
    failed_provider_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    expires_at TEXT,
    FOREIGN KEY (assistant_conversation_session_id)
        REFERENCES conversation_sessions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_search_sessions_status
    ON external_dataset_search_sessions(status);
CREATE INDEX IF NOT EXISTS ix_external_dataset_search_sessions_requester
    ON external_dataset_search_sessions(requested_by_admin_public_id);

CREATE TABLE IF NOT EXISTS external_dataset_search_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    search_session_id INTEGER NOT NULL UNIQUE,
    modality TEXT NOT NULL DEFAULT 'text' CHECK (modality IN (
        'text','image','audio','video','multimodal'
    )),
    languages_json TEXT NOT NULL DEFAULT '[]',
    tasks_json TEXT NOT NULL DEFAULT '[]',
    intended_uses_json TEXT NOT NULL DEFAULT '[]',
    commercial_requirement TEXT NOT NULL DEFAULT 'unknown' CHECK (commercial_requirement IN (
        'required','preferred','not_required','unknown'
    )),
    domain_tags_json TEXT NOT NULL DEFAULT '[]',
    preferred_providers_json TEXT NOT NULL DEFAULT '[]',
    excluded_providers_json TEXT NOT NULL DEFAULT '[]',
    minimum_records INTEGER,
    maximum_download_size_bytes INTEGER,
    preferred_file_formats_json TEXT NOT NULL DEFAULT '[]',
    quality_preferences_json TEXT NOT NULL DEFAULT '{}',
    licence_preferences_json TEXT NOT NULL DEFAULT '{}',
    free_text_requirement TEXT NOT NULL DEFAULT '',
    inferred_fields_json TEXT NOT NULL DEFAULT '{}',
    confirmed_fields_json TEXT NOT NULL DEFAULT '{}',
    unknown_fields_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_session_id)
        REFERENCES external_dataset_search_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS external_dataset_search_provider_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    search_session_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'success' CHECK (status IN (
        'success','partial','authentication_required','rate_limited','timeout',
        'unsupported','failed'
    )),
    query_used TEXT NOT NULL DEFAULT '',
    result_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    latency_ms INTEGER,
    FOREIGN KEY (search_session_id)
        REFERENCES external_dataset_search_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_search_provider_runs_session
    ON external_dataset_search_provider_runs(search_session_id);

CREATE TABLE IF NOT EXISTS external_dataset_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    search_session_id INTEGER NOT NULL,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    provider_count INTEGER NOT NULL DEFAULT 1,
    primary_provider_id INTEGER,
    modality TEXT CHECK (modality IN ('text','image','audio','video','multimodal')),
    languages_json TEXT NOT NULL DEFAULT '[]',
    tasks_json TEXT NOT NULL DEFAULT '[]',
    intended_use_fit_json TEXT NOT NULL DEFAULT '{}',
    description TEXT NOT NULL DEFAULT '',
    organization TEXT,
    authors_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    declared_licence TEXT,
    licence_status TEXT NOT NULL DEFAULT 'unknown' CHECK (licence_status IN (
        'unknown','declared','missing','conflicting','needs_verification'
    )),
    commercial_use_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (commercial_use_status IN ('not_approved','unknown')),
    training_use_status TEXT NOT NULL DEFAULT 'not_approved'
        CHECK (training_use_status IN ('not_approved','unknown')),
    rag_use_status TEXT NOT NULL DEFAULT 'not_approved'
        CHECK (rag_use_status IN ('not_approved','unknown')),
    evaluation_use_status TEXT NOT NULL DEFAULT 'not_approved'
        CHECK (evaluation_use_status IN ('not_approved','unknown')),
    record_count INTEGER,
    download_size_bytes INTEGER,
    file_formats_json TEXT NOT NULL DEFAULT '[]',
    dataset_card_present INTEGER NOT NULL DEFAULT 0 CHECK (dataset_card_present IN (0,1)),
    dataset_card_url TEXT,
    homepage_url TEXT,
    repository_url TEXT,
    gated INTEGER NOT NULL DEFAULT 0 CHECK (gated IN (0,1)),
    private INTEGER NOT NULL DEFAULT 0 CHECK (private IN (0,1)),
    authentication_required INTEGER NOT NULL DEFAULT 0 CHECK (authentication_required IN (0,1)),
    version TEXT,
    revision TEXT,
    last_modified_at TEXT,
    freshness_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (freshness_status IN ('fresh','aging','stale','unknown')),
    metadata_completeness_score REAL,
    quality_signal_score REAL,
    suitability_score REAL,
    risk_score REAL,
    recommendation_status TEXT NOT NULL DEFAULT 'insufficient_metadata' CHECK (recommendation_status IN (
        'recommended_for_review','possible','low_fit','high_risk','insufficient_metadata','excluded'
    )),
    warnings_json TEXT NOT NULL DEFAULT '[]',
    blocking_reasons_json TEXT NOT NULL DEFAULT '[]',
    excluded INTEGER NOT NULL DEFAULT 0 CHECK (excluded IN (0,1)),
    possible_duplicate_of_candidate_id INTEGER,
    candidate_entry_method TEXT NOT NULL DEFAULT 'provider_search'
        CHECK (candidate_entry_method IN ('provider_search','manual')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_session_id)
        REFERENCES external_dataset_search_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (primary_provider_id) REFERENCES external_data_providers(id),
    FOREIGN KEY (possible_duplicate_of_candidate_id)
        REFERENCES external_dataset_candidates(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_candidates_session
    ON external_dataset_candidates(search_session_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_candidates_recommendation
    ON external_dataset_candidates(recommendation_status);

CREATE TABLE IF NOT EXISTS external_dataset_candidate_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    provider_dataset_id TEXT NOT NULL,
    source_url TEXT,
    dataset_card_url TEXT,
    metadata_url TEXT,
    version TEXT,
    revision TEXT,
    raw_metadata_json TEXT NOT NULL DEFAULT '{}',
    raw_metadata_checksum TEXT,
    retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response_status TEXT NOT NULL DEFAULT 'success',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id),
    UNIQUE(candidate_id, provider_id, provider_dataset_id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_candidate_sources_candidate
    ON external_dataset_candidate_sources(candidate_id);

CREATE TABLE IF NOT EXISTS external_dataset_candidate_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    dimension TEXT NOT NULL CHECK (dimension IN (
        'requirement_fit','language_fit','task_fit','modality_fit','intended_use_fit',
        'metadata_completeness','provider_trust','dataset_card_presence','version_traceability',
        'size_suitability','format_suitability','recency','accessibility','risk_penalty',
        'unknown_licence_penalty','gated_access_penalty','conflict_penalty'
    )),
    raw_value REAL NOT NULL,
    weight REAL NOT NULL,
    score REAL NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id) ON DELETE CASCADE,
    UNIQUE(candidate_id, dimension)
);

CREATE TABLE IF NOT EXISTS external_dataset_candidate_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    search_session_id INTEGER NOT NULL,
    candidate_ids_json TEXT NOT NULL DEFAULT '[]',
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_session_id)
        REFERENCES external_dataset_search_sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_candidate_comparisons_session
    ON external_dataset_candidate_comparisons(search_session_id);

CREATE TABLE IF NOT EXISTS external_dataset_search_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    search_session_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'session_created','requirements_updated','requirements_confirmed','search_started',
        'provider_run_completed','provider_run_failed','search_completed','search_partial',
        'search_failed','search_cancelled','candidate_excluded','candidate_restored',
        'manual_candidate_added','comparison_created','report_finalized'
    )),
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_session_id)
        REFERENCES external_dataset_search_sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_search_events_session
    ON external_dataset_search_events(search_session_id);

CREATE TRIGGER IF NOT EXISTS external_dataset_search_sessions_immutable_delete
    BEFORE DELETE ON external_dataset_search_sessions
    BEGIN SELECT RAISE(ABORT, 'search sessions are never deleted, only cancelled/expired'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_search_provider_runs_immutable_delete
    BEFORE DELETE ON external_dataset_search_provider_runs
    BEGIN SELECT RAISE(ABORT, 'provider run history is never deleted'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_candidates_immutable_delete
    BEFORE DELETE ON external_dataset_candidates
    BEGIN SELECT RAISE(ABORT, 'candidates are excluded, never deleted'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_candidate_sources_immutable_delete
    BEFORE DELETE ON external_dataset_candidate_sources
    BEGIN SELECT RAISE(ABORT, 'candidate source evidence is never deleted'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_search_events_immutable_update
    BEFORE UPDATE ON external_dataset_search_events
    BEGIN SELECT RAISE(ABORT, 'search events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_search_events_immutable_delete
    BEFORE DELETE ON external_dataset_search_events
    BEGIN SELECT RAISE(ABORT, 'search events are append-only'); END;
"""

MIGRATION_032_NAME = "032_admin_assistant_response_language_preference"

# Phase 10A: a single, additive column on the existing `admin_accounts`
# table (one row per admin already) -- never a new preferences table,
# per plan.md section 2. Every existing admin row backfills to 'auto'
# via the NOT NULL DEFAULT, so no admin created in any earlier phase
# needs a data migration of its own.
PHASE32_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "admin_accounts": [
        (
            "admin_assistant_response_language",
            "TEXT NOT NULL DEFAULT 'auto' CHECK (admin_assistant_response_language "
            "IN ('tamil','english','tanglish','auto'))",
        ),
    ],
}

MIGRATION_033_NAME = "033_licence_evidence_terms_snapshot_dataset_verification"

# Phase 11: a governed, evidence-backed licence/terms/rights verification
# workflow layered on top of the read-only Phase 10 candidate rows --
# never a rewrite of dataset discovery, the provider registry, the
# Source & Rights Registry, or governance. Nothing in this schema block
# can ever download a dataset payload file, import records, activate
# RAG, create a training dataset version, or release a model -- there
# is no column here for any of those actions. `external_dataset_
# permission_assessments.status` accepts all 10 values structurally
# (Step 8), but only an explicit, reasoned Admin review may write one of
# the 4 admin-only values (`approved`/`approved_with_conditions`/
# `not_approved`/`prohibited`); this is enforced in the service layer
# (only `.review()`, never `.assess()`, may pass one) and reinforced
# here by a dedicated trigger requiring `reviewed_by`/`reviewed_at`/a
# non-empty `reason` in the same statement -- defense in depth, not the
# sole guard. 9 additive tables: Step 3's exact list of 8, plus one
# documented deviation -- `external_dataset_upstream_sources`, added
# because Step 10's own upstream field list does not fit any of the
# other 8 named tables (`external_dataset_evidence_links` is instead
# used for its more literal, general purpose: a polymorphic link from
# an evidence snapshot to whichever permission assessment/identity
# check/upstream source/licence determination/conflict event it
# supports). Conflicts (Step 12) are not a 10th table -- they are
# `external_dataset_verification_events` rows with
# `event_type='conflict_detected'` plus dedicated `conflict_type`/
# `conflict_severity`/`resolution_status` columns on that same event
# row, since Step 3's table list has no separate conflicts table. See
# docs/data_verification/phase11_licence_evidence_verification_plan.md.
PHASE33_SCHEMA = """
CREATE TABLE IF NOT EXISTS external_dataset_verification_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_code TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    search_session_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','collecting_evidence','needs_review','in_review','verified',
        'verified_with_conditions','insufficient_evidence','conflicting_evidence',
        'blocked','cancelled','expired','withdrawn'
    )),
    verification_scope TEXT NOT NULL DEFAULT '',
    requested_by_admin_public_id TEXT NOT NULL,
    assigned_reviewer_admin_public_id TEXT,
    current_stage TEXT NOT NULL DEFAULT 'evidence_collection',
    identity_status TEXT NOT NULL DEFAULT 'not_verified' CHECK (identity_status IN (
        'verified','likely_match','partial','conflicting','not_verified'
    )),
    evidence_status TEXT NOT NULL DEFAULT 'not_started' CHECK (evidence_status IN (
        'not_started','in_progress','complete','incomplete','conflicting'
    )),
    licence_status TEXT NOT NULL DEFAULT 'unknown' CHECK (licence_status IN (
        'unknown','declared_only','evidence_captured','verified','custom_needs_review',
        'missing','conflicting','restricted','withdrawn'
    )),
    terms_status TEXT NOT NULL DEFAULT 'not_started' CHECK (terms_status IN (
        'not_started','in_progress','complete','incomplete','conflicting'
    )),
    upstream_status TEXT NOT NULL DEFAULT 'not_started' CHECK (upstream_status IN (
        'not_started','in_progress','complete','incomplete','conflicting'
    )),
    permission_status TEXT NOT NULL DEFAULT 'not_started' CHECK (permission_status IN (
        'not_started','in_progress','complete','incomplete','conflicting'
    )),
    conflict_count INTEGER NOT NULL DEFAULT 0 CHECK (conflict_count >= 0),
    warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
    blocking_reason_count INTEGER NOT NULL DEFAULT 0 CHECK (blocking_reason_count >= 0),
    approved_upstream_domains_json TEXT NOT NULL DEFAULT '[]',
    report_json TEXT NOT NULL DEFAULT '{}',
    verification_expiry_status TEXT NOT NULL DEFAULT 'current'
        CHECK (verification_expiry_status IN (
            'current','due_soon','expired','source_changed','withdrawn'
        )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    expired_at TEXT,
    last_verified_at TEXT,
    next_reverification_at TEXT,
    locked_at TEXT,
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id),
    FOREIGN KEY (search_session_id) REFERENCES external_dataset_search_sessions(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_verification_cases_candidate
    ON external_dataset_verification_cases(candidate_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_verification_cases_status
    ON external_dataset_verification_cases(status);

CREATE TABLE IF NOT EXISTS external_dataset_evidence_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    provider_id INTEGER,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN (
        'official_dataset_page','dataset_card','licence_file','licence_url',
        'repository_licence_metadata','terms_of_use','privacy_policy',
        'consent_statement','upstream_source','citation_file','readme',
        'provider_api_metadata','government_notice','institutional_policy',
        'manual_admin_evidence'
    )),
    authority_level TEXT NOT NULL CHECK (authority_level IN (
        'primary','official_supporting','secondary','provider_declared',
        'community_supplied','manual_unverified'
    )),
    source_url TEXT,
    resolved_url TEXT,
    source_domain TEXT,
    source_title TEXT,
    content_type TEXT NOT NULL CHECK (content_type IN (
        'text/plain','text/markdown','text/html','application/json','application/pdf'
    )),
    language TEXT,
    retrieval_status TEXT NOT NULL DEFAULT 'success' CHECK (retrieval_status IN (
        'success','partial','failed','unavailable','manual'
    )),
    http_status INTEGER,
    retrieved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_date TEXT,
    last_modified_at TEXT,
    content_text TEXT NOT NULL DEFAULT '',
    content_excerpt TEXT NOT NULL DEFAULT '',
    content_checksum TEXT NOT NULL,
    response_headers_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    redaction_summary_json TEXT NOT NULL DEFAULT '{}',
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    supersedes_evidence_id INTEGER,
    ocr_derived INTEGER NOT NULL DEFAULT 0 CHECK (ocr_derived IN (0,1)),
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verification_case_id)
        REFERENCES external_dataset_verification_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id),
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id),
    FOREIGN KEY (supersedes_evidence_id) REFERENCES external_dataset_evidence_snapshots(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_evidence_snapshots_case
    ON external_dataset_evidence_snapshots(verification_case_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_evidence_snapshots_type
    ON external_dataset_evidence_snapshots(evidence_type);

CREATE TABLE IF NOT EXISTS external_dataset_evidence_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    evidence_snapshot_id INTEGER NOT NULL,
    linked_entity_type TEXT NOT NULL CHECK (linked_entity_type IN (
        'permission_assessment','identity_check','upstream_source',
        'licence_determination','conflict_event'
    )),
    linked_entity_id INTEGER NOT NULL,
    link_role TEXT NOT NULL DEFAULT 'supports' CHECK (link_role IN (
        'supports','contradicts','superseded_by','reference'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evidence_snapshot_id)
        REFERENCES external_dataset_evidence_snapshots(id) ON DELETE CASCADE,
    UNIQUE(evidence_snapshot_id, linked_entity_type, linked_entity_id, link_role)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_evidence_links_entity
    ON external_dataset_evidence_links(linked_entity_type, linked_entity_id);

CREATE TABLE IF NOT EXISTS external_dataset_identity_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    signal_type TEXT NOT NULL CHECK (signal_type IN (
        'provider_dataset_id','canonical_dataset_url','organization','repository_owner',
        'official_domain','dataset_name','version','revision','dataset_card_identifier',
        'upstream_citation','checksum_or_release_tag'
    )),
    expected_value TEXT,
    observed_value TEXT,
    matched INTEGER NOT NULL DEFAULT 0 CHECK (matched IN (0,1)),
    reason TEXT NOT NULL DEFAULT '',
    evidence_snapshot_id INTEGER,
    assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verification_case_id)
        REFERENCES external_dataset_verification_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id),
    FOREIGN KEY (evidence_snapshot_id) REFERENCES external_dataset_evidence_snapshots(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_identity_checks_case
    ON external_dataset_identity_checks(verification_case_id);

CREATE TABLE IF NOT EXISTS external_dataset_permission_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    permission_type TEXT NOT NULL CHECK (permission_type IN (
        'rag_use','training_use','evaluation_use','commercial_use','redistribution',
        'modification','derivative_works','attribution_required','share_alike_required',
        'notice_required','source_disclosure_required','personal_data_restriction',
        'research_only','non_commercial_only','geographic_restriction',
        'gated_access_restriction'
    )),
    status TEXT NOT NULL DEFAULT 'unknown' CHECK (status IN (
        'unknown','not_applicable','likely_allowed','likely_restricted','needs_legal_review',
        'approved','approved_with_conditions','not_approved','prohibited','withdrawn'
    )),
    decision_basis TEXT NOT NULL DEFAULT '',
    evidence_snapshot_ids_json TEXT NOT NULL DEFAULT '[]',
    conditions_json TEXT NOT NULL DEFAULT '{}',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    blocking_reasons_json TEXT NOT NULL DEFAULT '[]',
    assessed_by TEXT NOT NULL DEFAULT 'system',
    assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by TEXT,
    reviewed_at TEXT,
    reason TEXT,
    evidence_checksum_set_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verification_case_id)
        REFERENCES external_dataset_verification_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id),
    UNIQUE(verification_case_id, permission_type)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_permission_assessments_case
    ON external_dataset_permission_assessments(verification_case_id);

CREATE TABLE IF NOT EXISTS external_dataset_verification_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    permission_assessment_id INTEGER,
    permission_type TEXT,
    decision TEXT NOT NULL CHECK (decision IN (
        'approved','approved_with_conditions','not_approved','prohibited'
    )),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    conditions_json TEXT NOT NULL DEFAULT '{}',
    reviewer_admin_public_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    evidence_checksum_set_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verification_case_id)
        REFERENCES external_dataset_verification_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_assessment_id)
        REFERENCES external_dataset_permission_assessments(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_verification_reviews_case
    ON external_dataset_verification_reviews(verification_case_id);

CREATE TABLE IF NOT EXISTS external_dataset_verification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'case_created','evidence_collected','evidence_collection_failed',
        'manual_evidence_added','evidence_refreshed','identity_assessed',
        'licence_normalized','permission_assessed','permission_reviewed',
        'upstream_added','upstream_verified','conflict_detected','conflict_resolved',
        'case_finalized','case_cancelled','case_expired','reverification_checked',
        'source_changed_detected','withdrawal_notice_recorded'
    )),
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    conflict_type TEXT CHECK (conflict_type IS NULL OR conflict_type IN (
        'declared_vs_licence_file','provider_vs_repository_metadata',
        'permissive_language_vs_restrictive_terms','licence_vs_upstream_unknown',
        'commercial_use_vs_consent_missing','other'
    )),
    conflict_severity TEXT CHECK (conflict_severity IS NULL OR conflict_severity IN (
        'informational','low','moderate','high','blocking'
    )),
    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
    resolution_status TEXT CHECK (resolution_status IS NULL OR resolution_status IN (
        'unresolved','resolved','accepted_risk','dismissed'
    )),
    resolution_reason TEXT,
    resolved_by_admin_public_id TEXT,
    resolved_at TEXT,
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verification_case_id)
        REFERENCES external_dataset_verification_cases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_verification_events_case
    ON external_dataset_verification_events(verification_case_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_verification_events_type
    ON external_dataset_verification_events(event_type);

CREATE TABLE IF NOT EXISTS external_dataset_withdrawal_notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    notice_type TEXT NOT NULL CHECK (notice_type IN (
        'dataset_withdrawn','licence_changed','terms_changed','rights_holder_request',
        'privacy_request','provider_removed','other'
    )),
    source_url TEXT,
    notice_text TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_at TEXT,
    recorded_by_admin_public_id TEXT NOT NULL,
    impact_status TEXT NOT NULL DEFAULT 'pending_assessment' CHECK (impact_status IN (
        'pending_assessment','assessed'
    )),
    impact_summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verification_case_id)
        REFERENCES external_dataset_verification_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_withdrawal_notices_case
    ON external_dataset_withdrawal_notices(verification_case_id);

CREATE TABLE IF NOT EXISTS external_dataset_upstream_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    upstream_name TEXT NOT NULL,
    upstream_url TEXT,
    upstream_organization TEXT,
    upstream_licence TEXT,
    upstream_terms TEXT,
    upstream_permission_status TEXT NOT NULL DEFAULT 'unknown' CHECK (
        upstream_permission_status IN (
            'unknown','not_applicable','likely_allowed','likely_restricted',
            'needs_legal_review','approved','approved_with_conditions','not_approved',
            'prohibited','withdrawn'
        )
    ),
    relationship_type TEXT NOT NULL DEFAULT 'unknown' CHECK (relationship_type IN (
        'derived_from','aggregated_from','mirrored_from','translated_from',
        'annotated_from','converted_from','subset_of','unknown'
    )),
    coverage_notes TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'not_verified' CHECK (verification_status IN (
        'not_verified','partial','verified','conflicting'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verification_case_id)
        REFERENCES external_dataset_verification_cases(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_upstream_sources_case
    ON external_dataset_upstream_sources(verification_case_id);

CREATE TRIGGER IF NOT EXISTS external_dataset_evidence_snapshots_immutable_delete
    BEFORE DELETE ON external_dataset_evidence_snapshots
    BEGIN SELECT RAISE(ABORT, 'evidence snapshots are never deleted, only superseded'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_verification_reviews_immutable_update
    BEFORE UPDATE ON external_dataset_verification_reviews
    BEGIN SELECT RAISE(ABORT, 'verification reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_verification_reviews_immutable_delete
    BEFORE DELETE ON external_dataset_verification_reviews
    BEGIN SELECT RAISE(ABORT, 'verification reviews are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_verification_events_immutable_update
    BEFORE UPDATE ON external_dataset_verification_events
    BEGIN SELECT RAISE(ABORT, 'verification events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_verification_events_immutable_delete
    BEFORE DELETE ON external_dataset_verification_events
    BEGIN SELECT RAISE(ABORT, 'verification events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_withdrawal_notices_immutable_update
    BEFORE UPDATE ON external_dataset_withdrawal_notices
    BEGIN SELECT RAISE(ABORT, 'withdrawal notices are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_withdrawal_notices_immutable_delete
    BEFORE DELETE ON external_dataset_withdrawal_notices
    BEGIN SELECT RAISE(ABORT, 'withdrawal notices are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_permission_assessments_admin_only_guard_insert
    BEFORE INSERT ON external_dataset_permission_assessments
    WHEN NEW.status IN ('approved','approved_with_conditions','not_approved','prohibited')
        AND (NEW.reviewed_by IS NULL OR NEW.reviewed_at IS NULL
             OR NEW.reason IS NULL OR length(trim(NEW.reason)) = 0)
    BEGIN
        SELECT RAISE(ABORT,
            'admin-only permission status requires reviewed_by, reviewed_at, and a reason');
    END;
CREATE TRIGGER IF NOT EXISTS external_dataset_permission_assessments_admin_only_guard_update
    BEFORE UPDATE ON external_dataset_permission_assessments
    WHEN NEW.status IN ('approved','approved_with_conditions','not_approved','prohibited')
        AND (NEW.reviewed_by IS NULL OR NEW.reviewed_at IS NULL
             OR NEW.reason IS NULL OR length(trim(NEW.reason)) = 0)
    BEGIN
        SELECT RAISE(ABORT,
            'admin-only permission status requires reviewed_by, reviewed_at, and a reason');
    END;
"""

MIGRATION_034_NAME = "034_dataset_verification_licence_normalization_columns"

# Phase 11 (Step 7): two additive columns discovered as genuinely
# needed only once the licence-normalization service was being
# designed -- `declared_licence` (the value under independent Phase 11
# review, copied read-only from the Phase 10 candidate at case-
# creation time so it survives even if the candidate's own field is
# later reinterpreted) and `normalized_licence_identifier` (populated
# only via `core_model.data_verification.normalize_spdx_identifier()`'s
# exact-match table -- never guessed). Both live on the mutable case
# row (updatable only while `locked_at IS NULL`, same as every other
# case column), not migration 033's already-shipped table shape.
PHASE34_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "external_dataset_verification_cases": [
        ("declared_licence", "TEXT"),
        ("normalized_licence_identifier", "TEXT"),
    ],
}


MIGRATION_035_NAME = "035_approved_sample_import_quarantine_file_safety_validation"

# Phase 12: a governed, bounded-sample import and quarantine workflow
# layered on top of a *finalized* Phase 11 verification case -- never a
# rewrite of dataset verification, the Provider Registry, Dataset
# Discovery, the Source & Rights Registry, the existing dataset import
# pipeline, or governance. Nothing in this schema block can ever
# download a full external dataset, clone a repository, execute
# downloaded content, extract an unbounded archive, insert a
# quarantined record into `dataset_records`/RAG/training tables,
# activate RAG, create a training dataset version, or release a model
# -- there is no column here for any of those actions, and no status
# value anywhere in this block spells "training_approved". All 12
# tables Step 3 names are used as named -- no collapsing, no 13th
# table. Steps 16-21's PII/safety/quality/duplicate/conflict/
# contamination/poisoning findings all share one generically-shaped
# `external_dataset_sample_record_issues` table (an `issue_category`
# column distinguishes them), matching Step 3's singular table name;
# Step 12's file-level malware/executable scan gets its own
# `external_dataset_sample_scan_results` table. Human-review
# corrections to derived content (Step 22: "corrections must be
# revisioned") are stored as new append-only rows directly on
# `external_dataset_sample_reviews` (`derived_content_text`/
# `derived_content_checksum`) rather than a 13th "derived revisions"
# table -- reviews are already append-only, so each edit is already its
# own immutable version; the original file/record is never touched by
# any review row. See
# docs/sample_import/phase12_sample_import_quarantine_plan.md.
PHASE35_SCHEMA = """
CREATE TABLE IF NOT EXISTS external_dataset_sample_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_code TEXT NOT NULL UNIQUE,
    verification_case_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    provider_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','awaiting_approval','approved','downloading','downloaded',
        'quarantined','scanning','parsing','needs_review','validated',
        'validated_with_conditions','rejected','failed','cancelled','expired',
        'withdrawn','deleted'
    )),
    current_stage TEXT NOT NULL DEFAULT 'eligibility_check' CHECK (current_stage IN (
        'eligibility_check','approval','download','file_validation','archive_extraction',
        'security_scan','content_parsing','pii_scan','quality_scan','duplicate_scan',
        'contamination_scan','human_review','final_report'
    )),
    purpose TEXT NOT NULL CHECK (purpose IN (
        'manual_review','quality_evaluation','rag_sandbox_preparation',
        'format_validation','language_validation','security_validation'
    )),
    dataset_version TEXT,
    revision TEXT,
    selection_method TEXT NOT NULL CHECK (selection_method IN (
        'provider_sample_endpoint','provider_file_metadata','bounded_row_range',
        'bounded_split_subset','specific_approved_files','deterministic_first_n',
        'deterministic_seeded_sample','manual_file_selection'
    )),
    selection_seed TEXT,
    source_split TEXT,
    source_file TEXT,
    row_start INTEGER,
    row_end INTEGER,
    requested_count INTEGER NOT NULL DEFAULT 0 CHECK (requested_count >= 0),
    actual_count INTEGER NOT NULL DEFAULT 0 CHECK (actual_count >= 0),
    expected_modality TEXT NOT NULL DEFAULT 'text' CHECK (expected_modality IN (
        'text','image','audio','video','multimodal'
    )),
    quarantine_relative_path TEXT,
    quarantine_bytes_used INTEGER NOT NULL DEFAULT 0 CHECK (quarantine_bytes_used >= 0),
    rag_sandbox_eligible INTEGER CHECK (rag_sandbox_eligible IS NULL
        OR rag_sandbox_eligible IN (0,1)),
    training_assessment_status TEXT CHECK (training_assessment_status IS NULL
        OR training_assessment_status IN (
            'not_assessed','potentially_suitable','needs_more_review','not_suitable','blocked'
        )),
    report_json TEXT NOT NULL DEFAULT '{}',
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finalized_at TEXT,
    cancelled_at TEXT,
    expired_at TEXT,
    deleted_at TEXT,
    locked_at TEXT,
    FOREIGN KEY (verification_case_id) REFERENCES external_dataset_verification_cases(id),
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id),
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_imports_case
    ON external_dataset_sample_imports(verification_case_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_imports_status
    ON external_dataset_sample_imports(status);

CREATE TABLE IF NOT EXISTS external_dataset_sample_import_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    verification_case_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    provider_id INTEGER,
    approved_by_admin_id TEXT,
    approved_at TEXT,
    expires_at TEXT,
    purpose TEXT NOT NULL CHECK (purpose IN (
        'manual_review','quality_evaluation','rag_sandbox_preparation',
        'format_validation','language_validation','security_validation'
    )),
    requested_record_limit INTEGER NOT NULL CHECK (requested_record_limit > 0),
    approved_record_limit INTEGER CHECK (approved_record_limit IS NULL
        OR approved_record_limit > 0),
    requested_byte_limit INTEGER NOT NULL CHECK (requested_byte_limit > 0),
    approved_byte_limit INTEGER CHECK (approved_byte_limit IS NULL OR approved_byte_limit > 0),
    allowed_file_ids_json TEXT NOT NULL DEFAULT '[]',
    allowed_file_patterns_json TEXT NOT NULL DEFAULT '[]',
    allowed_formats_json TEXT NOT NULL DEFAULT '[]',
    expected_modality TEXT NOT NULL DEFAULT 'text' CHECK (expected_modality IN (
        'text','image','audio','video','multimodal'
    )),
    expected_languages_json TEXT NOT NULL DEFAULT '[]',
    expected_tasks_json TEXT NOT NULL DEFAULT '[]',
    dataset_version TEXT,
    revision TEXT,
    source_checksum TEXT,
    target_fingerprint TEXT NOT NULL,
    approval_reason TEXT,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','approved','rejected','expired','superseded'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE,
    FOREIGN KEY (verification_case_id) REFERENCES external_dataset_verification_cases(id),
    FOREIGN KEY (candidate_id) REFERENCES external_dataset_candidates(id),
    FOREIGN KEY (provider_id) REFERENCES external_data_providers(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_import_approvals_import
    ON external_dataset_sample_import_approvals(sample_import_id);

CREATE TABLE IF NOT EXISTS external_dataset_sample_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    source_file_id TEXT,
    original_filename TEXT NOT NULL,
    safe_filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    declared_format TEXT,
    detected_mime TEXT,
    detected_signature TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    checksum TEXT,
    encoding TEXT,
    compression_type TEXT,
    container_format TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','safe_for_scan','unsupported','suspicious','blocked','corrupt',
        'oversized','validated'
    )),
    blocked_class TEXT CHECK (blocked_class IS NULL OR blocked_class IN (
        'executable','shared_library','shell_script','batch_script','powershell_script',
        'macro_document','java_archive','android_package','disk_image','device_file',
        'encrypted_archive','password_protected_archive','unknown_binary_blob',
        'model_weight_file'
    )),
    rejection_reason TEXT,
    is_archive INTEGER NOT NULL DEFAULT 0 CHECK (is_archive IN (0,1)),
    archive_format TEXT CHECK (archive_format IS NULL OR archive_format IN ('zip','tar','tar.gz')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_files_import
    ON external_dataset_sample_files(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_files_status
    ON external_dataset_sample_files(status);

CREATE TABLE IF NOT EXISTS external_dataset_sample_download_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    file_id INTEGER,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'started','progress','completed','failed','aborted_byte_limit','cancelled'
    )),
    source_url TEXT,
    resolved_domain TEXT,
    bytes_downloaded INTEGER NOT NULL DEFAULT 0 CHECK (bytes_downloaded >= 0),
    byte_limit INTEGER,
    checksum TEXT,
    http_status INTEGER,
    error_reason TEXT,
    started_at TEXT,
    completed_at TEXT,
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES external_dataset_sample_files(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_download_events_import
    ON external_dataset_sample_download_events(sample_import_id);

CREATE TABLE IF NOT EXISTS external_dataset_sample_extraction_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    archive_file_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'started','member_extracted','member_rejected','completed','failed',
        'aborted_bomb_detected','aborted_timeout','cancelled'
    )),
    member_path TEXT,
    rejection_reason TEXT CHECK (rejection_reason IS NULL OR rejection_reason IN (
        'path_traversal','absolute_path','symlink','hard_link','device_file',
        'encrypted_entry','duplicate_path','depth_exceeded','nested_archive_depth_exceeded'
    )),
    expanded_bytes INTEGER,
    member_count INTEGER,
    depth INTEGER,
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE,
    FOREIGN KEY (archive_file_id) REFERENCES external_dataset_sample_files(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_extraction_events_import
    ON external_dataset_sample_extraction_events(sample_import_id);

CREATE TABLE IF NOT EXISTS external_dataset_sample_scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN (
        'clean_by_policy','suspicious','blocked','unsupported','scanner_unavailable',
        'needs_review'
    )),
    matched_signals_json TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL DEFAULT '',
    scanner_version TEXT NOT NULL DEFAULT '',
    scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES external_dataset_sample_files(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_scan_results_import
    ON external_dataset_sample_scan_results(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_scan_results_file
    ON external_dataset_sample_scan_results(file_id);

CREATE TABLE IF NOT EXISTS external_dataset_sample_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    source_file_id INTEGER NOT NULL,
    source_row_or_page TEXT,
    modality TEXT NOT NULL DEFAULT 'text' CHECK (modality IN (
        'text','image','audio','video','multimodal'
    )),
    language TEXT CHECK (language IS NULL OR language IN (
        'tamil','english','tanglish','mixed','other','unknown'
    )),
    task TEXT,
    raw_content TEXT NOT NULL DEFAULT '',
    normalized_content TEXT NOT NULL DEFAULT '',
    structured_payload_json TEXT NOT NULL DEFAULT '{}',
    source_checksum TEXT NOT NULL,
    record_checksum TEXT NOT NULL,
    parser_version TEXT NOT NULL DEFAULT '',
    normalizer_version TEXT NOT NULL DEFAULT '',
    ocr_derived INTEGER NOT NULL DEFAULT 0 CHECK (ocr_derived IN (0,1)),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','normalized','flagged','excluded','accepted','rejected'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE,
    FOREIGN KEY (source_file_id) REFERENCES external_dataset_sample_files(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_records_import
    ON external_dataset_sample_records(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_records_file
    ON external_dataset_sample_records(source_file_id);

CREATE TABLE IF NOT EXISTS external_dataset_sample_record_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    record_id INTEGER,
    file_id INTEGER,
    issue_category TEXT NOT NULL CHECK (issue_category IN (
        'pii','safety','quality','duplicate','conflict','contamination','poisoning'
    )),
    issue_type TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT,
    confidence TEXT,
    location_json TEXT NOT NULL DEFAULT '{}',
    related_group_id TEXT,
    contamination_reference TEXT,
    reviewer_decision TEXT CHECK (reviewer_decision IS NULL OR reviewer_decision IN (
        'accept','accept_with_conditions','edit_derived_copy','redact_derived_copy',
        'exclude','reject_file','reject_sample','needs_more_evidence'
    )),
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_reason TEXT,
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE,
    FOREIGN KEY (record_id) REFERENCES external_dataset_sample_records(id),
    FOREIGN KEY (file_id) REFERENCES external_dataset_sample_files(id)
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_record_issues_import
    ON external_dataset_sample_record_issues(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_record_issues_record
    ON external_dataset_sample_record_issues(record_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_record_issues_category
    ON external_dataset_sample_record_issues(issue_category);

CREATE TABLE IF NOT EXISTS external_dataset_sample_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN (
        'file','record','issue','duplicate_group','conflict','pii','safety','quality',
        'contamination','language','ocr_correction'
    )),
    target_id INTEGER,
    decision TEXT NOT NULL CHECK (decision IN (
        'accept','accept_with_conditions','edit_derived_copy','redact_derived_copy',
        'exclude','reject_file','reject_sample','needs_more_evidence'
    )),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    derived_content_text TEXT,
    derived_content_checksum TEXT,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    reviewer_admin_public_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_reviews_import
    ON external_dataset_sample_reviews(sample_import_id);

CREATE TABLE IF NOT EXISTS external_dataset_sample_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    report_version INTEGER NOT NULL DEFAULT 1 CHECK (report_version > 0),
    rag_sandbox_eligible INTEGER NOT NULL CHECK (rag_sandbox_eligible IN (0,1)),
    training_assessment_status TEXT NOT NULL CHECK (training_assessment_status IN (
        'not_assessed','potentially_suitable','needs_more_review','not_suitable','blocked'
    )),
    report_json TEXT NOT NULL DEFAULT '{}',
    finalized_by_admin_public_id TEXT NOT NULL,
    finalized_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sample_import_id, report_version),
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_reports_import
    ON external_dataset_sample_reports(sample_import_id);

CREATE TABLE IF NOT EXISTS external_dataset_sample_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'import_created','eligibility_checked','eligibility_blocked','approval_requested',
        'approved','approval_rejected','approval_expired','download_started',
        'download_completed','download_failed','quarantined','extraction_completed',
        'security_scan_completed','parsing_completed','pii_scan_completed',
        'safety_scan_completed','quality_scan_completed','duplicate_scan_completed',
        'contamination_scan_completed','poisoning_scan_completed','review_recorded',
        'finalized','deletion_requested','deletion_executed','deletion_cancelled',
        'cancelled','expired','withdrawal_blocked'
    )),
    from_status TEXT,
    to_status TEXT,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_events_import
    ON external_dataset_sample_events(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_events_type
    ON external_dataset_sample_events(event_type);

CREATE TABLE IF NOT EXISTS external_dataset_sample_deletion_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    deletion_request_code TEXT NOT NULL,
    sample_import_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN (
        'requested','confirmed','executed','cancelled'
    )),
    lineage_impact_summary_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    requested_by_admin_public_id TEXT NOT NULL,
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_by_admin_public_id TEXT,
    confirmed_at TEXT,
    executed_at TEXT,
    cancelled_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id)
        REFERENCES external_dataset_sample_imports(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_deletion_requests_import
    ON external_dataset_sample_deletion_requests(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_external_dataset_sample_deletion_requests_code
    ON external_dataset_sample_deletion_requests(deletion_request_code);

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_download_events_immutable_update
    BEFORE UPDATE ON external_dataset_sample_download_events
    BEGIN SELECT RAISE(ABORT, 'download events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_sample_download_events_immutable_delete
    BEFORE DELETE ON external_dataset_sample_download_events
    BEGIN SELECT RAISE(ABORT, 'download events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_extraction_events_immutable_update
    BEFORE UPDATE ON external_dataset_sample_extraction_events
    BEGIN SELECT RAISE(ABORT, 'extraction events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_sample_extraction_events_immutable_delete
    BEFORE DELETE ON external_dataset_sample_extraction_events
    BEGIN SELECT RAISE(ABORT, 'extraction events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_scan_results_immutable_update
    BEFORE UPDATE ON external_dataset_sample_scan_results
    BEGIN SELECT RAISE(ABORT, 'scan results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_sample_scan_results_immutable_delete
    BEFORE DELETE ON external_dataset_sample_scan_results
    BEGIN SELECT RAISE(ABORT, 'scan results are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_reviews_immutable_update
    BEFORE UPDATE ON external_dataset_sample_reviews
    BEGIN SELECT RAISE(ABORT, 'sample reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_sample_reviews_immutable_delete
    BEFORE DELETE ON external_dataset_sample_reviews
    BEGIN SELECT RAISE(ABORT, 'sample reviews are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_reports_immutable_update
    BEFORE UPDATE ON external_dataset_sample_reports
    BEGIN SELECT RAISE(ABORT, 'sample reports are append-only and immutable once finalized'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_sample_reports_immutable_delete
    BEFORE DELETE ON external_dataset_sample_reports
    BEGIN SELECT RAISE(ABORT, 'sample reports are append-only and immutable once finalized'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_events_immutable_update
    BEFORE UPDATE ON external_dataset_sample_events
    BEGIN SELECT RAISE(ABORT, 'sample events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_sample_events_immutable_delete
    BEFORE DELETE ON external_dataset_sample_events
    BEGIN SELECT RAISE(ABORT, 'sample events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_deletion_requests_immutable_update
    BEFORE UPDATE ON external_dataset_sample_deletion_requests
    BEGIN SELECT RAISE(ABORT, 'deletion request events are append-only -- each transition is a new row'); END;
CREATE TRIGGER IF NOT EXISTS external_dataset_sample_deletion_requests_immutable_delete
    BEFORE DELETE ON external_dataset_sample_deletion_requests
    BEGIN SELECT RAISE(ABORT, 'deletion request events are append-only -- each transition is a new row'); END;

CREATE TRIGGER IF NOT EXISTS external_dataset_sample_import_approvals_immutable_once_approved
    BEFORE UPDATE ON external_dataset_sample_import_approvals
    WHEN OLD.status = 'approved' AND (
        NEW.status NOT IN ('approved','expired','superseded')
        OR NEW.approved_record_limit IS NOT OLD.approved_record_limit
        OR NEW.approved_byte_limit IS NOT OLD.approved_byte_limit
        OR NEW.allowed_file_ids_json IS NOT OLD.allowed_file_ids_json
        OR NEW.allowed_file_patterns_json IS NOT OLD.allowed_file_patterns_json
        OR NEW.allowed_formats_json IS NOT OLD.allowed_formats_json
        OR NEW.dataset_version IS NOT OLD.dataset_version
        OR NEW.revision IS NOT OLD.revision
        OR NEW.source_checksum IS NOT OLD.source_checksum
        OR NEW.target_fingerprint IS NOT OLD.target_fingerprint
    )
    BEGIN
        SELECT RAISE(ABORT,
            'an approved sample-import approval is immutable except transitioning to expired/superseded');
    END;
"""

MIGRATION_036_NAME = "036_isolated_rag_sandbox_retrieval_evaluation_grounded_answer_testing"

# Phase 13: a governed, structurally-isolated RAG sandbox layered on top
# of *finalized, accepted* Phase 12 sample records -- never a rewrite of
# Phase 16's RAG ingestion/retrieval/generation/evaluation, and never a
# production-activation path. Isolation is expressed by reusing the
# existing `rag_knowledge_spaces` table itself as the sandbox namespace:
# every experiment creates its own dedicated knowledge_space row (see
# `rag_sandbox_corpora.knowledge_space_id`), and every retrieval/
# generation call for that experiment goes through the *existing*,
# unmodified Phase 16 services scoped to that one space -- structurally
# impossible to cross-contaminate with the admin-only production RAG
# lab, and unreachable from the public chatbot (which has no RAG wiring
# at all -- see docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md
# section 2). `rag_sandbox_corpora.production_visible` is hard-CHECKed
# to 0 -- there is no column, status value, or code path anywhere in
# this schema block that can ever flip it. Nothing here can create a
# training dataset version, start training, release a model, or
# activate anything -- there is no such column or status value. All 17
# tables (16 recommended + `rag_sandbox_acceptances`, justified in the
# plan doc) are used as named.
PHASE36_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_sandbox_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_code TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER NOT NULL,
    sample_report_id INTEGER,
    verification_case_id INTEGER NOT NULL,
    knowledge_space_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','awaiting_approval','approved','preparing_corpus','building_index','ready',
        'running_retrieval','running_generation','needs_review','accepted',
        'accepted_with_conditions','rejected','failed','cancelled','expired','withdrawn','deleted'
    )),
    current_stage TEXT NOT NULL DEFAULT 'eligibility' CHECK (current_stage IN (
        'eligibility','approval','record_selection','corpus_creation','index_build',
        'query_preparation','retrieval_evaluation','answer_generation','citation_evaluation',
        'safety_evaluation','human_review','final_report','acceptance'
    )),
    purpose TEXT NOT NULL CHECK (purpose IN (
        'retrieval_validation','grounded_answer_validation','multilingual_validation',
        'citation_validation','conflict_handling_validation','injection_resistance_validation',
        'production_rag_readiness','training_data_suitability_research'
    )),
    sample_report_checksum TEXT,
    accepted_record_checksum_set_hash TEXT,
    maximum_records INTEGER NOT NULL DEFAULT 500 CHECK (maximum_records > 0),
    maximum_total_characters INTEGER NOT NULL DEFAULT 2000000 CHECK (maximum_total_characters > 0),
    maximum_total_tokens INTEGER NOT NULL DEFAULT 500000 CHECK (maximum_total_tokens > 0),
    threshold_version TEXT NOT NULL DEFAULT 'v1',
    evaluation_version TEXT NOT NULL DEFAULT 'v1',
    production_rag_readiness TEXT NOT NULL DEFAULT 'not_assessed' CHECK (production_rag_readiness IN (
        'not_assessed','potentially_ready','ready_with_conditions','not_ready','blocked'
    )),
    training_data_observation TEXT NOT NULL DEFAULT 'not_assessed' CHECK (training_data_observation IN (
        'not_assessed','potentially_useful','needs_transformation','not_suitable','blocked'
    )),
    eligible_for_production_rag_proposal INTEGER CHECK (eligible_for_production_rag_proposal IS NULL
        OR eligible_for_production_rag_proposal IN (0,1)),
    eligible_for_training_assessment INTEGER CHECK (eligible_for_training_assessment IS NULL
        OR eligible_for_training_assessment IN (0,1)),
    expires_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TEXT,
    FOREIGN KEY (sample_import_id) REFERENCES external_dataset_sample_imports(id),
    FOREIGN KEY (sample_report_id) REFERENCES external_dataset_sample_reports(id),
    FOREIGN KEY (verification_case_id) REFERENCES external_dataset_verification_cases(id),
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_experiments_sample_import
    ON rag_sandbox_experiments(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_experiments_status
    ON rag_sandbox_experiments(status);

CREATE TABLE IF NOT EXISTS rag_sandbox_query_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','finalized')),
    query_count INTEGER NOT NULL DEFAULT 0 CHECK (query_count >= 0),
    finalized_by_admin_public_id TEXT,
    finalized_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_query_sets_experiment
    ON rag_sandbox_query_sets(experiment_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    query_set_id INTEGER NOT NULL,
    query_text TEXT NOT NULL CHECK (length(trim(query_text)) > 0),
    language TEXT NOT NULL DEFAULT 'unknown' CHECK (language IN (
        'tamil','english','tanglish','mixed','other','unknown'
    )),
    query_type TEXT NOT NULL CHECK (query_type IN (
        'fact_lookup','explanation','comparison','summary','translation','definition',
        'multi_hop','insufficient_evidence','conflicting_sources','prompt_injection',
        'language_routing','citation_required'
    )),
    expected_source_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_answer_notes TEXT NOT NULL DEFAULT '',
    must_refuse_if_insufficient INTEGER NOT NULL DEFAULT 0 CHECK (must_refuse_if_insufficient IN (0,1)),
    conflict_expected INTEGER NOT NULL DEFAULT 0 CHECK (conflict_expected IN (0,1)),
    injection_test INTEGER NOT NULL DEFAULT 0 CHECK (injection_test IN (0,1)),
    human_authored INTEGER NOT NULL DEFAULT 1 CHECK (human_authored IN (0,1)),
    reviewed_by_admin_public_id TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_set_id) REFERENCES rag_sandbox_query_sets(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_queries_query_set
    ON rag_sandbox_queries(query_set_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_queries_type
    ON rag_sandbox_queries(query_type);

CREATE TABLE IF NOT EXISTS rag_sandbox_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    sample_import_id INTEGER NOT NULL,
    sample_report_id INTEGER NOT NULL,
    verification_case_id INTEGER NOT NULL,
    approved_by_admin_id TEXT,
    approved_at TEXT,
    expires_at TEXT,
    purpose TEXT NOT NULL CHECK (purpose IN (
        'retrieval_validation','grounded_answer_validation','multilingual_validation',
        'citation_validation','conflict_handling_validation','injection_resistance_validation',
        'production_rag_readiness','training_data_suitability_research'
    )),
    accepted_record_ids_json TEXT NOT NULL DEFAULT '[]',
    accepted_record_checksums_json TEXT NOT NULL DEFAULT '[]',
    maximum_records INTEGER NOT NULL CHECK (maximum_records > 0),
    maximum_total_characters INTEGER NOT NULL CHECK (maximum_total_characters > 0),
    maximum_total_tokens INTEGER NOT NULL CHECK (maximum_total_tokens > 0),
    chunking_configuration_json TEXT NOT NULL DEFAULT '{}',
    retrieval_configuration_json TEXT NOT NULL DEFAULT '{}',
    embedding_assignment_key TEXT,
    generation_assignment_key TEXT,
    query_set_id INTEGER,
    target_fingerprint TEXT NOT NULL,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','approved','rejected','expired','superseded'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_import_id) REFERENCES external_dataset_sample_imports(id),
    FOREIGN KEY (sample_report_id) REFERENCES external_dataset_sample_reports(id),
    FOREIGN KEY (verification_case_id) REFERENCES external_dataset_verification_cases(id),
    FOREIGN KEY (query_set_id) REFERENCES rag_sandbox_query_sets(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_approvals_experiment
    ON rag_sandbox_approvals(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_approvals_status
    ON rag_sandbox_approvals(status);

CREATE TABLE IF NOT EXISTS rag_sandbox_corpora (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL UNIQUE,
    knowledge_space_id INTEGER NOT NULL UNIQUE,
    sandbox_scope_key TEXT NOT NULL UNIQUE,
    production_visible INTEGER NOT NULL DEFAULT 0 CHECK (production_visible = 0),
    status TEXT NOT NULL DEFAULT 'preparing' CHECK (status IN (
        'preparing','ready','failed','deleted'
    )),
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    total_characters INTEGER NOT NULL DEFAULT 0 CHECK (total_characters >= 0),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id)
);

CREATE TABLE IF NOT EXISTS rag_sandbox_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    corpus_id INTEGER NOT NULL,
    sample_record_id INTEGER NOT NULL,
    selected_revision_id INTEGER,
    content TEXT NOT NULL,
    content_checksum TEXT NOT NULL,
    language TEXT CHECK (language IS NULL OR language IN (
        'tamil','english','tanglish','mixed','other','unknown'
    )),
    task TEXT,
    source_file_id INTEGER,
    source_location TEXT NOT NULL DEFAULT '',
    rights_reference TEXT NOT NULL DEFAULT '',
    conditions_json TEXT NOT NULL DEFAULT '{}',
    contamination_flagged INTEGER NOT NULL DEFAULT 0 CHECK (contamination_flagged IN (0,1)),
    rag_source_id INTEGER,
    rag_source_version_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (corpus_id) REFERENCES rag_sandbox_corpora(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_record_id) REFERENCES external_dataset_sample_records(id),
    FOREIGN KEY (selected_revision_id) REFERENCES external_dataset_sample_reviews(id),
    FOREIGN KEY (source_file_id) REFERENCES external_dataset_sample_files(id),
    FOREIGN KEY (rag_source_id) REFERENCES rag_knowledge_sources(id),
    FOREIGN KEY (rag_source_version_id) REFERENCES rag_source_versions(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_records_experiment
    ON rag_sandbox_records(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_records_sample_record
    ON rag_sandbox_records(sample_record_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_indexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    corpus_id INTEGER NOT NULL,
    index_kind TEXT NOT NULL CHECK (index_kind IN ('bm25','vector','hybrid')),
    chunk_set_id INTEGER,
    embedding_model_id INTEGER,
    rag_vector_index_id INTEGER,
    rag_keyword_index_id INTEGER,
    retrieval_profile_id INTEGER,
    build_config_json TEXT NOT NULL DEFAULT '{}',
    chunk_count INTEGER NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    build_checksum TEXT,
    resource_usage_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'building' CHECK (status IN (
        'building','validated','active','failed','deleted'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (corpus_id) REFERENCES rag_sandbox_corpora(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_set_id) REFERENCES rag_chunk_sets(id),
    FOREIGN KEY (embedding_model_id) REFERENCES rag_embedding_models(id),
    FOREIGN KEY (rag_vector_index_id) REFERENCES rag_vector_indexes(id),
    FOREIGN KEY (rag_keyword_index_id) REFERENCES rag_keyword_indexes(id),
    FOREIGN KEY (retrieval_profile_id) REFERENCES rag_retrieval_profiles(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_indexes_experiment
    ON rag_sandbox_indexes(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_indexes_status
    ON rag_sandbox_indexes(status);

CREATE TABLE IF NOT EXISTS rag_sandbox_retrieval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    index_id INTEGER NOT NULL,
    query_set_id INTEGER NOT NULL,
    config_label TEXT NOT NULL DEFAULT '',
    total_queries INTEGER NOT NULL DEFAULT 0 CHECK (total_queries >= 0),
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed','failed','cancelled')),
    performed_by_admin_public_id TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (index_id) REFERENCES rag_sandbox_indexes(id),
    FOREIGN KEY (query_set_id) REFERENCES rag_sandbox_query_sets(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_retrieval_runs_experiment
    ON rag_sandbox_retrieval_runs(experiment_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_retrieval_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    retrieval_run_id INTEGER NOT NULL,
    query_id INTEGER NOT NULL,
    rag_retrieval_run_id INTEGER,
    metric_availability TEXT NOT NULL DEFAULT 'not_available' CHECK (metric_availability IN (
        'full','partial','not_available'
    )),
    expected_source_hit INTEGER CHECK (expected_source_hit IS NULL OR expected_source_hit IN (0,1)),
    source_rank INTEGER,
    recall_at_k REAL,
    precision_at_k REAL,
    reciprocal_rank REAL,
    language_match INTEGER CHECK (language_match IS NULL OR language_match IN (0,1)),
    duplicate_result_rate REAL,
    conflicting_source_retrieved INTEGER NOT NULL DEFAULT 0
        CHECK (conflicting_source_retrieved IN (0,1)),
    insufficient_evidence_behavior TEXT CHECK (insufficient_evidence_behavior IS NULL
        OR insufficient_evidence_behavior IN ('correct_no_results','unexpected_results')),
    latency_milliseconds INTEGER,
    result_count INTEGER NOT NULL DEFAULT 0 CHECK (result_count >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (retrieval_run_id) REFERENCES rag_sandbox_retrieval_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (query_id) REFERENCES rag_sandbox_queries(id),
    FOREIGN KEY (rag_retrieval_run_id) REFERENCES rag_retrieval_runs(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_retrieval_results_run
    ON rag_sandbox_retrieval_results(retrieval_run_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_retrieval_results_query
    ON rag_sandbox_retrieval_results(query_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_answer_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    retrieval_result_id INTEGER NOT NULL,
    query_id INTEGER NOT NULL,
    rag_grounded_request_id INTEGER,
    generation_assignment_key TEXT,
    prompt_version TEXT NOT NULL DEFAULT 'v1',
    answer_text TEXT NOT NULL DEFAULT '',
    answer_checksum TEXT,
    answer_language TEXT NOT NULL DEFAULT 'unknown',
    used_source_ids_json TEXT NOT NULL DEFAULT '[]',
    citation_count INTEGER NOT NULL DEFAULT 0 CHECK (citation_count >= 0),
    unsupported_claim_count INTEGER NOT NULL DEFAULT 0 CHECK (unsupported_claim_count >= 0),
    insufficient_evidence_detected INTEGER NOT NULL DEFAULT 0
        CHECK (insufficient_evidence_detected IN (0,1)),
    conflict_detected INTEGER NOT NULL DEFAULT 0 CHECK (conflict_detected IN (0,1)),
    refusal_used INTEGER NOT NULL DEFAULT 0 CHECK (refusal_used IN (0,1)),
    latency_milliseconds INTEGER,
    token_usage_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK (status IN (
        'grounded_answer','insufficient_evidence','retrieval_failed','generation_failed',
        'blocked_evidence'
    )),
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (retrieval_result_id) REFERENCES rag_sandbox_retrieval_results(id),
    FOREIGN KEY (query_id) REFERENCES rag_sandbox_queries(id),
    FOREIGN KEY (rag_grounded_request_id) REFERENCES rag_grounded_requests(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_answer_runs_experiment
    ON rag_sandbox_answer_runs(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_answer_runs_query
    ON rag_sandbox_answer_runs(query_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    answer_run_id INTEGER NOT NULL,
    citation_label TEXT NOT NULL,
    rag_citation_id INTEGER,
    references_retrieved_source INTEGER NOT NULL DEFAULT 0
        CHECK (references_retrieved_source IN (0,1)),
    source_exists INTEGER NOT NULL DEFAULT 0 CHECK (source_exists IN (0,1)),
    checksum_matches INTEGER CHECK (checksum_matches IS NULL OR checksum_matches IN (0,1)),
    supports_nearby_claim INTEGER CHECK (supports_nearby_claim IS NULL OR supports_nearby_claim IN (0,1)),
    is_duplicate INTEGER NOT NULL DEFAULT 0 CHECK (is_duplicate IN (0,1)),
    is_orphan INTEGER NOT NULL DEFAULT 0 CHECK (is_orphan IN (0,1)),
    validation_status TEXT NOT NULL CHECK (validation_status IN (
        'valid','partially_supporting','unsupported','missing','invalid','conflicting'
    )),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (answer_run_id) REFERENCES rag_sandbox_answer_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (rag_citation_id) REFERENCES rag_answer_citations(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_citations_answer_run
    ON rag_sandbox_citations(answer_run_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    answer_run_id INTEGER,
    query_id INTEGER,
    evaluation_type TEXT NOT NULL CHECK (evaluation_type IN (
        'unsupported_claim','insufficient_evidence','conflict_handling','prompt_injection',
        'language_compliance','answer_quality'
    )),
    result_status TEXT NOT NULL,
    automated INTEGER NOT NULL DEFAULT 1 CHECK (automated IN (0,1)),
    score REAL,
    details_json TEXT NOT NULL DEFAULT '{}',
    evaluation_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (answer_run_id) REFERENCES rag_sandbox_answer_runs(id),
    FOREIGN KEY (query_id) REFERENCES rag_sandbox_queries(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_evaluations_experiment
    ON rag_sandbox_evaluations(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_evaluations_type
    ON rag_sandbox_evaluations(evaluation_type);

CREATE TABLE IF NOT EXISTS rag_sandbox_human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    query_id INTEGER NOT NULL,
    answer_run_id INTEGER,
    retrieval_relevant INTEGER CHECK (retrieval_relevant IS NULL OR retrieval_relevant IN (0,1)),
    answer_grounded INTEGER CHECK (answer_grounded IS NULL OR answer_grounded IN (0,1)),
    citations_correct INTEGER CHECK (citations_correct IS NULL OR citations_correct IN (0,1)),
    language_appropriate INTEGER CHECK (language_appropriate IS NULL OR language_appropriate IN (0,1)),
    refusal_correct INTEGER CHECK (refusal_correct IS NULL OR refusal_correct IN (0,1)),
    conflict_handled INTEGER CHECK (conflict_handled IS NULL OR conflict_handled IN (0,1)),
    injection_resisted INTEGER CHECK (injection_resisted IS NULL OR injection_resisted IN (0,1)),
    decision TEXT NOT NULL CHECK (decision IN (
        'pass','pass_with_conditions','fail','needs_revision','exclude_query','needs_more_evidence'
    )),
    notes TEXT NOT NULL DEFAULT '',
    reviewer_admin_public_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (query_id) REFERENCES rag_sandbox_queries(id),
    FOREIGN KEY (answer_run_id) REFERENCES rag_sandbox_answer_runs(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_human_reviews_experiment
    ON rag_sandbox_human_reviews(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_human_reviews_query
    ON rag_sandbox_human_reviews(query_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    report_version INTEGER NOT NULL DEFAULT 1 CHECK (report_version > 0),
    report_json TEXT NOT NULL DEFAULT '{}',
    report_checksum_sha256 TEXT NOT NULL,
    production_rag_readiness TEXT NOT NULL CHECK (production_rag_readiness IN (
        'not_assessed','potentially_ready','ready_with_conditions','not_ready','blocked'
    )),
    training_data_observation TEXT NOT NULL CHECK (training_data_observation IN (
        'not_assessed','potentially_useful','needs_transformation','not_suitable','blocked'
    )),
    recommended_next_action TEXT NOT NULL DEFAULT '',
    finalized_by_admin_public_id TEXT NOT NULL,
    finalized_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment_id, report_version),
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_reports_experiment
    ON rag_sandbox_reports(experiment_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_acceptances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    report_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN (
        'accepted','accepted_with_conditions','rejected','needs_more_testing'
    )),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    conditions_json TEXT NOT NULL DEFAULT '{}',
    reviewer_admin_public_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    report_checksum_sha256 TEXT NOT NULL,
    target_fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES rag_sandbox_reports(id)
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_acceptances_experiment
    ON rag_sandbox_acceptances(experiment_id);

CREATE TABLE IF NOT EXISTS rag_sandbox_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    experiment_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'experiment_created','eligibility_checked','eligibility_blocked','approval_requested',
        'approved','approval_rejected','approval_expired','corpus_prepared',
        'record_promoted','record_promotion_blocked','index_build_started','index_build_completed',
        'index_build_failed','index_deleted','query_set_created','query_set_finalized',
        'retrieval_run_completed','answer_run_completed','evaluation_completed',
        'human_review_recorded','report_finalized','accepted','rejected',
        'deletion_requested','deletion_executed','deletion_cancelled',
        'cancelled','expired','withdrawal_blocked'
    )),
    from_status TEXT,
    to_status TEXT,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_events_experiment
    ON rag_sandbox_events(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_events_type
    ON rag_sandbox_events(event_type);

CREATE TABLE IF NOT EXISTS rag_sandbox_deletion_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    deletion_request_code TEXT NOT NULL,
    experiment_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN (
        'requested','confirmed','executed','cancelled'
    )),
    impact_preview_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    requested_by_admin_public_id TEXT NOT NULL,
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_by_admin_public_id TEXT,
    confirmed_at TEXT,
    executed_at TEXT,
    cancelled_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES rag_sandbox_experiments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_deletion_requests_experiment
    ON rag_sandbox_deletion_requests(experiment_id);
CREATE INDEX IF NOT EXISTS ix_rag_sandbox_deletion_requests_code
    ON rag_sandbox_deletion_requests(deletion_request_code);

CREATE TRIGGER IF NOT EXISTS rag_sandbox_records_immutable_update
    BEFORE UPDATE ON rag_sandbox_records
    BEGIN SELECT RAISE(ABORT, 'sandbox records are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_records_immutable_delete
    BEFORE DELETE ON rag_sandbox_records
    BEGIN SELECT RAISE(ABORT, 'sandbox records are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_retrieval_runs_immutable_update
    BEFORE UPDATE ON rag_sandbox_retrieval_runs
    BEGIN SELECT RAISE(ABORT, 'sandbox retrieval runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_retrieval_runs_immutable_delete
    BEFORE DELETE ON rag_sandbox_retrieval_runs
    BEGIN SELECT RAISE(ABORT, 'sandbox retrieval runs are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_retrieval_results_immutable_update
    BEFORE UPDATE ON rag_sandbox_retrieval_results
    BEGIN SELECT RAISE(ABORT, 'sandbox retrieval results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_retrieval_results_immutable_delete
    BEFORE DELETE ON rag_sandbox_retrieval_results
    BEGIN SELECT RAISE(ABORT, 'sandbox retrieval results are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_answer_runs_immutable_update
    BEFORE UPDATE ON rag_sandbox_answer_runs
    BEGIN SELECT RAISE(ABORT, 'sandbox answer runs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_answer_runs_immutable_delete
    BEFORE DELETE ON rag_sandbox_answer_runs
    BEGIN SELECT RAISE(ABORT, 'sandbox answer runs are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_citations_immutable_update
    BEFORE UPDATE ON rag_sandbox_citations
    BEGIN SELECT RAISE(ABORT, 'sandbox citations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_citations_immutable_delete
    BEFORE DELETE ON rag_sandbox_citations
    BEGIN SELECT RAISE(ABORT, 'sandbox citations are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_evaluations_immutable_update
    BEFORE UPDATE ON rag_sandbox_evaluations
    BEGIN SELECT RAISE(ABORT, 'sandbox evaluations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_evaluations_immutable_delete
    BEFORE DELETE ON rag_sandbox_evaluations
    BEGIN SELECT RAISE(ABORT, 'sandbox evaluations are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_human_reviews_immutable_update
    BEFORE UPDATE ON rag_sandbox_human_reviews
    BEGIN SELECT RAISE(ABORT, 'sandbox human reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_human_reviews_immutable_delete
    BEFORE DELETE ON rag_sandbox_human_reviews
    BEGIN SELECT RAISE(ABORT, 'sandbox human reviews are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_reports_immutable_update
    BEFORE UPDATE ON rag_sandbox_reports
    BEGIN SELECT RAISE(ABORT, 'sandbox reports are append-only and immutable once finalized'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_reports_immutable_delete
    BEFORE DELETE ON rag_sandbox_reports
    BEGIN SELECT RAISE(ABORT, 'sandbox reports are append-only and immutable once finalized'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_acceptances_immutable_update
    BEFORE UPDATE ON rag_sandbox_acceptances
    BEGIN SELECT RAISE(ABORT, 'sandbox acceptance decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_acceptances_immutable_delete
    BEFORE DELETE ON rag_sandbox_acceptances
    BEGIN SELECT RAISE(ABORT, 'sandbox acceptance decisions are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_events_immutable_update
    BEFORE UPDATE ON rag_sandbox_events
    BEGIN SELECT RAISE(ABORT, 'sandbox events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_events_immutable_delete
    BEFORE DELETE ON rag_sandbox_events
    BEGIN SELECT RAISE(ABORT, 'sandbox events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_deletion_requests_immutable_update
    BEFORE UPDATE ON rag_sandbox_deletion_requests
    BEGIN SELECT RAISE(ABORT, 'deletion request events are append-only -- each transition is a new row'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_deletion_requests_immutable_delete
    BEFORE DELETE ON rag_sandbox_deletion_requests
    BEGIN SELECT RAISE(ABORT, 'deletion request events are append-only -- each transition is a new row'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_queries_immutable_insert_after_finalize
    BEFORE INSERT ON rag_sandbox_queries
    WHEN (SELECT status FROM rag_sandbox_query_sets WHERE id = NEW.query_set_id) = 'finalized'
    BEGIN SELECT RAISE(ABORT, 'query set is finalized -- no new queries may be added'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_queries_immutable_update_after_finalize
    BEFORE UPDATE ON rag_sandbox_queries
    WHEN (SELECT status FROM rag_sandbox_query_sets WHERE id = OLD.query_set_id) = 'finalized'
    BEGIN SELECT RAISE(ABORT, 'query set is finalized -- queries are immutable'); END;
CREATE TRIGGER IF NOT EXISTS rag_sandbox_queries_immutable_delete_after_finalize
    BEFORE DELETE ON rag_sandbox_queries
    WHEN (SELECT status FROM rag_sandbox_query_sets WHERE id = OLD.query_set_id) = 'finalized'
    BEGIN SELECT RAISE(ABORT, 'query set is finalized -- queries are immutable'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_query_sets_immutable_after_finalize
    BEFORE UPDATE ON rag_sandbox_query_sets
    WHEN OLD.status = 'finalized' AND NEW.status = 'finalized'
    BEGIN SELECT RAISE(ABORT, 'query set is finalized and immutable'); END;

CREATE TRIGGER IF NOT EXISTS rag_sandbox_approvals_immutable_once_approved
    BEFORE UPDATE ON rag_sandbox_approvals
    WHEN OLD.status = 'approved' AND (
        NEW.status NOT IN ('approved','expired','superseded')
        OR NEW.accepted_record_ids_json IS NOT OLD.accepted_record_ids_json
        OR NEW.accepted_record_checksums_json IS NOT OLD.accepted_record_checksums_json
        OR NEW.maximum_records IS NOT OLD.maximum_records
        OR NEW.maximum_total_characters IS NOT OLD.maximum_total_characters
        OR NEW.maximum_total_tokens IS NOT OLD.maximum_total_tokens
        OR NEW.chunking_configuration_json IS NOT OLD.chunking_configuration_json
        OR NEW.retrieval_configuration_json IS NOT OLD.retrieval_configuration_json
        OR NEW.embedding_assignment_key IS NOT OLD.embedding_assignment_key
        OR NEW.generation_assignment_key IS NOT OLD.generation_assignment_key
        OR NEW.query_set_id IS NOT OLD.query_set_id
        OR NEW.target_fingerprint IS NOT OLD.target_fingerprint
    )
    BEGIN
        SELECT RAISE(ABORT,
            'an approved rag-sandbox approval is immutable except transitioning to expired/superseded');
    END;
"""



MIGRATION_037_NAME = "037_training_dataset_promotion_incremental_training_checkpoint_evaluation"

# Phase 14: governed training-dataset promotion and incremental
# language training built entirely on Phase 7-15's existing
# tokenizer/pretraining/instruction-tuning/training-reliability/
# checkpoint/evaluation/model-registry systems -- never a rewrite or
# duplicate of any of them. New data enters `dataset_records` (the
# existing Phase 1/2 table) only through governed, reviewed,
# lineage-preserving transformation of *accepted* Phase 12/13 records;
# from there, `DatasetVersioningService`'s existing, unmodified
# build/split/leakage/manifest/checksum pipeline produces the
# immutable training dataset version. Incremental training itself
# always creates a real `instruction_tuning_experiment` or
# `pretraining_job` through the existing, unmodified services -- this
# schema only adds the governance layer around them (separate dataset-
# promotion and training-run approvals, checkpoint acceptance,
# regression/memorization checks). No table or trigger here can ever
# set `core_model_versions.lifecycle_status='active'`, and nothing
# here calls into `ModelReleaseService` -- production release and
# production activation remain entirely outside this phase. See
# docs/training/phase14_incremental_language_training_plan.md.
PHASE37_SCHEMA = """
CREATE TABLE IF NOT EXISTS training_data_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    assessment_code TEXT NOT NULL UNIQUE,
    sample_import_id INTEGER,
    rag_sandbox_experiment_id INTEGER,
    verification_case_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_assessed' CHECK (status IN (
        'not_assessed','assessing','assessed','failed'
    )),
    current_stage TEXT NOT NULL DEFAULT 'lineage_check' CHECK (current_stage IN (
        'lineage_check','permission_check','classification','contamination_check',
        'candidate_review','replay_plan','dataset_promotion','complete'
    )),
    sample_report_checksum TEXT,
    rag_sandbox_report_checksum TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sample_import_id) REFERENCES external_dataset_sample_imports(id),
    FOREIGN KEY (rag_sandbox_experiment_id) REFERENCES rag_sandbox_experiments(id),
    FOREIGN KEY (verification_case_id) REFERENCES external_dataset_verification_cases(id)
);
CREATE INDEX IF NOT EXISTS ix_training_data_assessments_sample_import
    ON training_data_assessments(sample_import_id);
CREATE INDEX IF NOT EXISTS ix_training_data_assessments_rag_sandbox_experiment
    ON training_data_assessments(rag_sandbox_experiment_id);
CREATE INDEX IF NOT EXISTS ix_training_data_assessments_status
    ON training_data_assessments(status);

CREATE TABLE IF NOT EXISTS training_data_assessment_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    assessment_id INTEGER NOT NULL,
    sample_record_id INTEGER,
    rag_sandbox_record_id INTEGER,
    record_category TEXT NOT NULL CHECK (record_category IN (
        'language_pattern','grammar','conversation','instruction_response','translation_pair',
        'summarization_pair','correction_pair','classification_example','reasoning_example',
        'general_text_corpus','stable_knowledge','volatile_knowledge','source_specific_fact',
        'evaluation_example','unsafe_or_blocked'
    )),
    suitability_status TEXT NOT NULL DEFAULT 'not_assessed' CHECK (suitability_status IN (
        'not_assessed','potentially_suitable','suitable_with_transformation','suitable_for_sft',
        'suitable_for_pretraining','suitable_for_tokenizer','evaluation_only','rag_only',
        'not_suitable','blocked'
    )),
    dimension_results_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL DEFAULT '',
    contamination_flagged INTEGER NOT NULL DEFAULT 0 CHECK (contamination_flagged IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_id) REFERENCES training_data_assessments(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_record_id) REFERENCES external_dataset_sample_records(id),
    FOREIGN KEY (rag_sandbox_record_id) REFERENCES rag_sandbox_records(id)
);
CREATE INDEX IF NOT EXISTS ix_training_data_assessment_items_assessment
    ON training_data_assessment_items(assessment_id);
CREATE INDEX IF NOT EXISTS ix_training_data_assessment_items_category
    ON training_data_assessment_items(record_category);
CREATE INDEX IF NOT EXISTS ix_training_data_assessment_items_suitability
    ON training_data_assessment_items(suitability_status);

CREATE TABLE IF NOT EXISTS training_example_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    assessment_item_id INTEGER NOT NULL,
    source_sample_record_id INTEGER,
    source_rag_sandbox_record_id INTEGER,
    transformation_type TEXT NOT NULL CHECK (transformation_type IN (
        'clean_language_sample','question_answer_pair','summary_pair','translation_pair',
        'tanglish_normalization_pair','correction_pair','instruction_response_pair',
        'conversation_turn_sequence'
    )),
    prompt_text TEXT NOT NULL DEFAULT '',
    assistant_text TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'unknown',
    task TEXT NOT NULL DEFAULT '',
    source_checksum TEXT NOT NULL,
    candidate_checksum TEXT NOT NULL,
    transformation_version TEXT NOT NULL DEFAULT 'v1',
    review_status TEXT NOT NULL DEFAULT 'pending_review' CHECK (review_status IN (
        'pending_review','approved','rejected','needs_revision'
    )),
    reviewed_by TEXT,
    reviewed_at TEXT,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    dataset_record_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_item_id) REFERENCES training_data_assessment_items(id) ON DELETE CASCADE,
    FOREIGN KEY (source_sample_record_id) REFERENCES external_dataset_sample_records(id),
    FOREIGN KEY (source_rag_sandbox_record_id) REFERENCES rag_sandbox_records(id),
    FOREIGN KEY (dataset_record_id) REFERENCES dataset_records(id)
);
CREATE INDEX IF NOT EXISTS ix_training_example_candidates_assessment_item
    ON training_example_candidates(assessment_item_id);
CREATE INDEX IF NOT EXISTS ix_training_example_candidates_review_status
    ON training_example_candidates(review_status);

CREATE TABLE IF NOT EXISTS training_example_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved','rejected','needs_revision')),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    revised_prompt_text TEXT,
    revised_assistant_text TEXT,
    revised_checksum TEXT,
    reviewer_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES training_example_candidates(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_training_example_revisions_candidate
    ON training_example_revisions(candidate_id);

CREATE TABLE IF NOT EXISTS training_replay_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    assessment_id INTEGER NOT NULL,
    new_record_count INTEGER NOT NULL CHECK (new_record_count >= 0),
    replay_record_count INTEGER NOT NULL CHECK (replay_record_count >= 0),
    new_data_ratio REAL NOT NULL,
    replay_data_ratio REAL NOT NULL,
    replay_source_version_ids_json TEXT NOT NULL DEFAULT '[]',
    replay_record_ids_json TEXT NOT NULL DEFAULT '[]',
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    task_distribution_json TEXT NOT NULL DEFAULT '{}',
    domain_distribution_json TEXT NOT NULL DEFAULT '{}',
    selection_method TEXT NOT NULL DEFAULT 'deterministic_representative_sample',
    selection_seed INTEGER NOT NULL DEFAULT 42,
    reason TEXT NOT NULL DEFAULT '',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_id) REFERENCES training_data_assessments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_training_replay_plans_assessment
    ON training_replay_plans(assessment_id);

CREATE TABLE IF NOT EXISTS training_dataset_promotion_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    assessment_id INTEGER NOT NULL,
    replay_plan_id INTEGER,
    selected_candidate_ids_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','awaiting_approval','approved','rejected','expired','superseded',
        'building','ready','failed'
    )),
    approved_by_admin_id TEXT,
    approved_at TEXT,
    expires_at TEXT,
    target_fingerprint TEXT,
    dataset_version_id INTEGER,
    train_split_checksum TEXT,
    validation_split_checksum TEXT,
    test_split_checksum TEXT,
    lineage_manifest_json TEXT NOT NULL DEFAULT '{}',
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assessment_id) REFERENCES training_data_assessments(id) ON DELETE CASCADE,
    FOREIGN KEY (replay_plan_id) REFERENCES training_replay_plans(id),
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id)
);
CREATE INDEX IF NOT EXISTS ix_training_dataset_promotion_requests_assessment
    ON training_dataset_promotion_requests(assessment_id);
CREATE INDEX IF NOT EXISTS ix_training_dataset_promotion_requests_status
    ON training_dataset_promotion_requests(status);

CREATE TABLE IF NOT EXISTS incremental_training_run_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    promotion_request_id INTEGER NOT NULL,
    dataset_version_id INTEGER NOT NULL,
    base_checkpoint_id INTEGER,
    tokenizer_version_id INTEGER,
    training_strategy TEXT NOT NULL CHECK (training_strategy IN (
        'incremental_sft','continued_pretraining','tokenizer_only_assessment','no_training_rag_only'
    )),
    configuration_json TEXT NOT NULL DEFAULT '{}',
    configuration_checksum TEXT,
    resource_preview_json TEXT NOT NULL DEFAULT '{}',
    resource_preview_checksum TEXT,
    execution_target TEXT NOT NULL DEFAULT 'local_cpu' CHECK (execution_target IN (
        'local_cpu','cpu_vps','external_gpu_manual'
    )),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','awaiting_approval','approved','rejected','expired','superseded','started',
        'cancelled'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (promotion_request_id) REFERENCES training_dataset_promotion_requests(id),
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id),
    FOREIGN KEY (base_checkpoint_id) REFERENCES pretraining_checkpoints(id),
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id)
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_run_requests_promotion
    ON incremental_training_run_requests(promotion_request_id);
CREATE INDEX IF NOT EXISTS ix_incremental_training_run_requests_status
    ON incremental_training_run_requests(status);

CREATE TABLE IF NOT EXISTS incremental_training_run_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    run_request_id INTEGER NOT NULL,
    dataset_version_id INTEGER NOT NULL,
    base_checkpoint_id INTEGER,
    tokenizer_version_id INTEGER,
    training_strategy TEXT NOT NULL,
    configuration_checksum TEXT NOT NULL,
    resource_preview_checksum TEXT NOT NULL,
    replay_plan_id INTEGER,
    train_split_checksum TEXT,
    validation_split_checksum TEXT,
    test_split_checksum TEXT,
    approved_by_admin_id TEXT,
    approved_at TEXT,
    expires_at TEXT,
    target_fingerprint TEXT NOT NULL,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','approved','rejected','expired','superseded'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_request_id) REFERENCES incremental_training_run_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id),
    FOREIGN KEY (base_checkpoint_id) REFERENCES pretraining_checkpoints(id),
    FOREIGN KEY (tokenizer_version_id) REFERENCES tokenizer_versions(id),
    FOREIGN KEY (replay_plan_id) REFERENCES training_replay_plans(id)
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_run_approvals_request
    ON incremental_training_run_approvals(run_request_id);
CREATE INDEX IF NOT EXISTS ix_incremental_training_run_approvals_status
    ON incremental_training_run_approvals(status);

CREATE TABLE IF NOT EXISTS incremental_training_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    run_request_id INTEGER NOT NULL,
    run_approval_id INTEGER NOT NULL,
    underlying_run_kind TEXT NOT NULL CHECK (underlying_run_kind IN (
        'instruction_tuning_run','pretraining_job'
    )),
    underlying_run_public_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued','running','completed','completed_with_warnings','failed','cancelled'
    )),
    current_epoch INTEGER,
    current_step INTEGER,
    latest_training_loss REAL,
    latest_validation_loss REAL,
    started_at TEXT,
    completed_at TEXT,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_request_id) REFERENCES incremental_training_run_requests(id),
    FOREIGN KEY (run_approval_id) REFERENCES incremental_training_run_approvals(id)
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_runs_request
    ON incremental_training_runs(run_request_id);
CREATE INDEX IF NOT EXISTS ix_incremental_training_runs_status
    ON incremental_training_runs(status);

CREATE TABLE IF NOT EXISTS incremental_training_run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    run_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES incremental_training_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_run_events_run
    ON incremental_training_run_events(run_id);

CREATE TABLE IF NOT EXISTS incremental_training_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    run_id INTEGER NOT NULL,
    underlying_checkpoint_public_id TEXT NOT NULL,
    parent_checkpoint_id INTEGER,
    epoch INTEGER,
    step INTEGER,
    tokens_seen INTEGER,
    training_loss REAL,
    validation_loss REAL,
    checkpoint_checksum TEXT,
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN (
        'created','verified','evaluation_pending','evaluated','accepted_candidate','rejected',
        'corrupt','superseded'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES incremental_training_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_checkpoint_id) REFERENCES incremental_training_checkpoints(id)
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_checkpoints_run
    ON incremental_training_checkpoints(run_id);
CREATE INDEX IF NOT EXISTS ix_incremental_training_checkpoints_status
    ON incremental_training_checkpoints(status);

CREATE TABLE IF NOT EXISTS incremental_training_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    checkpoint_id INTEGER NOT NULL,
    evaluation_type TEXT NOT NULL,
    result_status TEXT NOT NULL,
    automated INTEGER NOT NULL DEFAULT 1 CHECK (automated IN (0,1)),
    score REAL,
    details_json TEXT NOT NULL DEFAULT '{}',
    evaluation_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (checkpoint_id) REFERENCES incremental_training_checkpoints(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_evaluations_checkpoint
    ON incremental_training_evaluations(checkpoint_id);
CREATE INDEX IF NOT EXISTS ix_incremental_training_evaluations_type
    ON incremental_training_evaluations(evaluation_type);

CREATE TABLE IF NOT EXISTS incremental_training_comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    checkpoint_id INTEGER NOT NULL,
    parent_checkpoint_id INTEGER,
    comparison_type TEXT NOT NULL CHECK (comparison_type IN (
        'general_comparison','forgetting_check'
    )),
    dimension TEXT NOT NULL DEFAULT 'overall',
    result_status TEXT NOT NULL CHECK (result_status IN (
        'improved','unchanged','minor_regression','major_regression','not_comparable'
    )),
    metrics_json TEXT NOT NULL DEFAULT '{}',
    source_evaluation_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (checkpoint_id) REFERENCES incremental_training_checkpoints(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_checkpoint_id) REFERENCES incremental_training_checkpoints(id)
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_comparisons_checkpoint
    ON incremental_training_comparisons(checkpoint_id);
CREATE INDEX IF NOT EXISTS ix_incremental_training_comparisons_type
    ON incremental_training_comparisons(comparison_type);

CREATE TABLE IF NOT EXISTS incremental_training_human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    checkpoint_id INTEGER NOT NULL,
    prompt_text TEXT NOT NULL DEFAULT '',
    tamil_fluency INTEGER CHECK (tamil_fluency IS NULL OR tamil_fluency IN (0,1)),
    english_fluency INTEGER CHECK (english_fluency IS NULL OR english_fluency IN (0,1)),
    tanglish_readability INTEGER CHECK (tanglish_readability IS NULL OR tanglish_readability IN (0,1)),
    instruction_following INTEGER CHECK (instruction_following IS NULL OR instruction_following IN (0,1)),
    helpfulness INTEGER CHECK (helpfulness IS NULL OR helpfulness IN (0,1)),
    correct_refusal INTEGER CHECK (correct_refusal IS NULL OR correct_refusal IN (0,1)),
    hallucination_risk INTEGER CHECK (hallucination_risk IS NULL OR hallucination_risk IN (0,1)),
    repetition INTEGER CHECK (repetition IS NULL OR repetition IN (0,1)),
    formatting INTEGER CHECK (formatting IS NULL OR formatting IN (0,1)),
    regression INTEGER CHECK (regression IS NULL OR regression IN (0,1)),
    decision TEXT NOT NULL CHECK (decision IN (
        'pass','pass_with_conditions','fail','needs_more_testing'
    )),
    notes TEXT NOT NULL DEFAULT '',
    reviewer_admin_public_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (checkpoint_id) REFERENCES incremental_training_checkpoints(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_human_reviews_checkpoint
    ON incremental_training_human_reviews(checkpoint_id);

CREATE TABLE IF NOT EXISTS incremental_training_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    run_id INTEGER NOT NULL,
    report_version INTEGER NOT NULL DEFAULT 1 CHECK (report_version > 0),
    report_json TEXT NOT NULL DEFAULT '{}',
    report_checksum_sha256 TEXT NOT NULL,
    checkpoint_recommendation TEXT NOT NULL CHECK (checkpoint_recommendation IN (
        'accept_candidate','accept_with_conditions','reject','needs_more_training',
        'needs_more_evaluation'
    )),
    production_release_readiness TEXT NOT NULL DEFAULT 'not_assessed',
    recommended_next_action TEXT NOT NULL DEFAULT '',
    finalized_by_admin_public_id TEXT NOT NULL,
    finalized_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, report_version),
    FOREIGN KEY (run_id) REFERENCES incremental_training_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_reports_run
    ON incremental_training_reports(run_id);

CREATE TABLE IF NOT EXISTS incremental_training_checkpoint_acceptances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    checkpoint_id INTEGER NOT NULL,
    report_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN (
        'accepted_candidate','accepted_with_conditions','rejected','needs_more_testing'
    )),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    conditions_json TEXT NOT NULL DEFAULT '{}',
    reviewer_admin_public_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    report_checksum_sha256 TEXT NOT NULL,
    checkpoint_checksum TEXT,
    target_fingerprint TEXT NOT NULL,
    model_candidate_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (checkpoint_id) REFERENCES incremental_training_checkpoints(id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES incremental_training_reports(id)
);
CREATE INDEX IF NOT EXISTS ix_incremental_training_checkpoint_acceptances_checkpoint
    ON incremental_training_checkpoint_acceptances(checkpoint_id);

CREATE TRIGGER IF NOT EXISTS training_data_assessment_items_immutable_update
    BEFORE UPDATE ON training_data_assessment_items
    BEGIN SELECT RAISE(ABORT, 'assessment items are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_data_assessment_items_immutable_delete
    BEFORE DELETE ON training_data_assessment_items
    BEGIN SELECT RAISE(ABORT, 'assessment items are append-only'); END;

CREATE TRIGGER IF NOT EXISTS training_example_revisions_immutable_update
    BEFORE UPDATE ON training_example_revisions
    BEGIN SELECT RAISE(ABORT, 'example revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_example_revisions_immutable_delete
    BEFORE DELETE ON training_example_revisions
    BEGIN SELECT RAISE(ABORT, 'example revisions are append-only'); END;

CREATE TRIGGER IF NOT EXISTS training_replay_plans_immutable_update
    BEFORE UPDATE ON training_replay_plans
    BEGIN SELECT RAISE(ABORT, 'replay plans are append-only'); END;
CREATE TRIGGER IF NOT EXISTS training_replay_plans_immutable_delete
    BEFORE DELETE ON training_replay_plans
    BEGIN SELECT RAISE(ABORT, 'replay plans are append-only'); END;

CREATE TRIGGER IF NOT EXISTS incremental_training_run_events_immutable_update
    BEFORE UPDATE ON incremental_training_run_events
    BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS incremental_training_run_events_immutable_delete
    BEFORE DELETE ON incremental_training_run_events
    BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS incremental_training_checkpoints_immutable_update
    BEFORE UPDATE ON incremental_training_checkpoints
    WHEN NEW.underlying_checkpoint_public_id IS NOT OLD.underlying_checkpoint_public_id
    OR (OLD.status NOT IN ('created','verified','evaluation_pending')
        AND NOT (OLD.status='evaluated' AND NEW.status IN ('accepted_candidate','rejected','superseded')))
    BEGIN SELECT RAISE(ABORT, 'checkpoint lineage fields are immutable once evaluated'); END;
CREATE TRIGGER IF NOT EXISTS incremental_training_checkpoints_immutable_delete
    BEFORE DELETE ON incremental_training_checkpoints
    BEGIN SELECT RAISE(ABORT, 'checkpoints are append-only'); END;

CREATE TRIGGER IF NOT EXISTS incremental_training_evaluations_immutable_update
    BEFORE UPDATE ON incremental_training_evaluations
    BEGIN SELECT RAISE(ABORT, 'evaluations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS incremental_training_evaluations_immutable_delete
    BEFORE DELETE ON incremental_training_evaluations
    BEGIN SELECT RAISE(ABORT, 'evaluations are append-only'); END;

CREATE TRIGGER IF NOT EXISTS incremental_training_comparisons_immutable_update
    BEFORE UPDATE ON incremental_training_comparisons
    BEGIN SELECT RAISE(ABORT, 'comparisons are append-only'); END;
CREATE TRIGGER IF NOT EXISTS incremental_training_comparisons_immutable_delete
    BEFORE DELETE ON incremental_training_comparisons
    BEGIN SELECT RAISE(ABORT, 'comparisons are append-only'); END;

CREATE TRIGGER IF NOT EXISTS incremental_training_human_reviews_immutable_update
    BEFORE UPDATE ON incremental_training_human_reviews
    BEGIN SELECT RAISE(ABORT, 'human reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS incremental_training_human_reviews_immutable_delete
    BEFORE DELETE ON incremental_training_human_reviews
    BEGIN SELECT RAISE(ABORT, 'human reviews are append-only'); END;

CREATE TRIGGER IF NOT EXISTS incremental_training_reports_immutable_update
    BEFORE UPDATE ON incremental_training_reports
    BEGIN SELECT RAISE(ABORT, 'reports are append-only'); END;
CREATE TRIGGER IF NOT EXISTS incremental_training_reports_immutable_delete
    BEFORE DELETE ON incremental_training_reports
    BEGIN SELECT RAISE(ABORT, 'reports are append-only'); END;

CREATE TRIGGER IF NOT EXISTS incremental_training_checkpoint_acceptances_immutable_update
    BEFORE UPDATE ON incremental_training_checkpoint_acceptances
    BEGIN SELECT RAISE(ABORT, 'checkpoint acceptances are append-only'); END;
CREATE TRIGGER IF NOT EXISTS incremental_training_checkpoint_acceptances_immutable_delete
    BEFORE DELETE ON incremental_training_checkpoint_acceptances
    BEGIN SELECT RAISE(ABORT, 'checkpoint acceptances are append-only'); END;

CREATE TRIGGER IF NOT EXISTS training_dataset_promotion_requests_immutable_once_approved
    BEFORE UPDATE ON training_dataset_promotion_requests
    WHEN OLD.status = 'approved' AND (
        NEW.status NOT IN ('approved','expired','superseded','building','ready','failed')
        OR NEW.selected_candidate_ids_json IS NOT OLD.selected_candidate_ids_json
        OR NEW.replay_plan_id IS NOT OLD.replay_plan_id
        OR NEW.target_fingerprint IS NOT OLD.target_fingerprint
    )
    BEGIN
        SELECT RAISE(ABORT,
            'an approved dataset promotion request is immutable except transitioning to expired/superseded or progressing to building/ready/failed');
    END;

CREATE TRIGGER IF NOT EXISTS incremental_training_run_approvals_immutable_once_approved
    BEFORE UPDATE ON incremental_training_run_approvals
    WHEN OLD.status = 'approved' AND (
        NEW.status NOT IN ('approved','expired','superseded')
        OR NEW.dataset_version_id IS NOT OLD.dataset_version_id
        OR NEW.base_checkpoint_id IS NOT OLD.base_checkpoint_id
        OR NEW.tokenizer_version_id IS NOT OLD.tokenizer_version_id
        OR NEW.configuration_checksum IS NOT OLD.configuration_checksum
        OR NEW.resource_preview_checksum IS NOT OLD.resource_preview_checksum
        OR NEW.replay_plan_id IS NOT OLD.replay_plan_id
        OR NEW.target_fingerprint IS NOT OLD.target_fingerprint
    )
    BEGIN
        SELECT RAISE(ABORT,
            'an approved incremental-training run approval is immutable except transitioning to expired/superseded');
    END;
"""

MIGRATION_038_NAME = "038_text_nlp_production_readiness"
PHASE38_SCHEMA = """
CREATE TABLE IF NOT EXISTS production_rag_promotion_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    promotion_code TEXT NOT NULL UNIQUE,
    rag_sandbox_experiment_id INTEGER NOT NULL,
    rag_sandbox_report_id INTEGER NOT NULL,
    knowledge_space_id INTEGER NOT NULL,
    selected_record_ids_json TEXT NOT NULL DEFAULT '[]',
    selected_record_checksum_set_hash TEXT NOT NULL,
    chunking_configuration_json TEXT NOT NULL DEFAULT '{}',
    embedding_assignment_key TEXT,
    retrieval_configuration_json TEXT NOT NULL DEFAULT '{}',
    generation_assignment_key TEXT,
    citation_policy_version TEXT NOT NULL DEFAULT 'v1',
    grounding_policy_version TEXT NOT NULL DEFAULT 'v1',
    injection_policy_version TEXT NOT NULL DEFAULT 'v1',
    commercial_use_context TEXT NOT NULL DEFAULT 'unknown' CHECK (commercial_use_context IN (
        'commercial','non_commercial','unknown'
    )),
    resource_preview_json TEXT NOT NULL DEFAULT '{}',
    target_fingerprint TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','awaiting_review','approved','building_candidate','candidate_ready',
        'validation_failed','ready_for_activation','rejected','cancelled','expired','superseded'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rag_sandbox_experiment_id) REFERENCES rag_sandbox_experiments(id),
    FOREIGN KEY (rag_sandbox_report_id) REFERENCES rag_sandbox_reports(id),
    FOREIGN KEY (knowledge_space_id) REFERENCES rag_knowledge_spaces(id)
);
CREATE INDEX IF NOT EXISTS ix_production_rag_promotion_requests_status
    ON production_rag_promotion_requests(status);
CREATE INDEX IF NOT EXISTS ix_production_rag_promotion_requests_experiment
    ON production_rag_promotion_requests(rag_sandbox_experiment_id);

CREATE TABLE IF NOT EXISTS production_rag_promotion_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    promotion_request_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','approved','rejected','expired','superseded'
    )),
    approved_by_admin_id TEXT,
    approved_at TEXT,
    expires_at TEXT,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    target_fingerprint TEXT NOT NULL,
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (promotion_request_id) REFERENCES production_rag_promotion_requests(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_production_rag_promotion_approvals_request
    ON production_rag_promotion_approvals(promotion_request_id);

CREATE TABLE IF NOT EXISTS production_rag_release_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    promotion_request_id INTEGER NOT NULL,
    knowledge_source_id INTEGER,
    retrieval_profile_id INTEGER,
    record_checksum_set_hash TEXT NOT NULL,
    chunk_checksum_set_hash TEXT,
    embedding_model_reference TEXT,
    index_checksum_sha256 TEXT,
    configuration_manifest_json TEXT NOT NULL DEFAULT '{}',
    build_log_json TEXT NOT NULL DEFAULT '{}',
    resource_usage_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'building' CHECK (status IN (
        'building','built','validating','validated','validation_failed','activated','superseded','failed'
    )),
    production_visible INTEGER NOT NULL DEFAULT 0 CHECK (production_visible IN (0,1)),
    rollback_plan_id INTEGER,
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (promotion_request_id) REFERENCES production_rag_promotion_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_source_id) REFERENCES rag_knowledge_sources(id),
    FOREIGN KEY (retrieval_profile_id) REFERENCES rag_retrieval_profiles(id)
);
CREATE INDEX IF NOT EXISTS ix_production_rag_release_candidates_promotion
    ON production_rag_release_candidates(promotion_request_id);
CREATE INDEX IF NOT EXISTS ix_production_rag_release_candidates_status
    ON production_rag_release_candidates(status);

CREATE TABLE IF NOT EXISTS production_rag_validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    rag_release_candidate_id INTEGER NOT NULL,
    validation_type TEXT NOT NULL,
    result_status TEXT NOT NULL CHECK (result_status IN (
        'passed','passed_with_warning','failed','not_applicable'
    )),
    metrics_json TEXT NOT NULL DEFAULT '{}',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rag_release_candidate_id) REFERENCES production_rag_release_candidates(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_production_rag_validation_results_candidate
    ON production_rag_validation_results(rag_release_candidate_id);

CREATE TABLE IF NOT EXISTS production_rag_activation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    rag_release_candidate_id INTEGER NOT NULL,
    promotion_approval_id INTEGER,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'pre_activation_snapshot','activated','post_activation_check_passed',
        'post_activation_check_failed','rolled_back','activation_failed'
    )),
    previous_active_profile_public_id TEXT,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rag_release_candidate_id) REFERENCES production_rag_release_candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (promotion_approval_id) REFERENCES production_rag_promotion_approvals(id)
);
CREATE INDEX IF NOT EXISTS ix_production_rag_activation_events_candidate
    ON production_rag_activation_events(rag_release_candidate_id);

CREATE TABLE IF NOT EXISTS production_model_release_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    request_code TEXT NOT NULL UNIQUE,
    model_candidate_core_model_version_id INTEGER NOT NULL,
    incremental_training_checkpoint_id INTEGER,
    model_release_candidate_id INTEGER,
    release_type TEXT NOT NULL DEFAULT 'experimental' CHECK (release_type IN (
        'patch','minor','major','experimental','internal'
    )),
    target_assignment_keys_json TEXT NOT NULL DEFAULT '[]',
    canary_requested INTEGER NOT NULL DEFAULT 1 CHECK (canary_requested IN (0,1)),
    canary_percentage_or_scope TEXT NOT NULL DEFAULT 'admin_diagnostic',
    resource_preview_json TEXT NOT NULL DEFAULT '{}',
    security_check_version TEXT NOT NULL DEFAULT 'v1',
    evaluation_policy_version TEXT NOT NULL DEFAULT 'v1',
    rollback_plan_id INTEGER,
    target_fingerprint TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','awaiting_review','validating','validated','validation_failed','approved',
        'canary','canary_failed','activating','activated','activation_failed','rejected',
        'cancelled','expired','superseded'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_candidate_core_model_version_id) REFERENCES core_model_versions(id),
    FOREIGN KEY (incremental_training_checkpoint_id) REFERENCES incremental_training_checkpoints(id),
    FOREIGN KEY (model_release_candidate_id) REFERENCES model_release_candidates(id)
);
CREATE INDEX IF NOT EXISTS ix_production_model_release_requests_status
    ON production_model_release_requests(status);
CREATE INDEX IF NOT EXISTS ix_production_model_release_requests_candidate
    ON production_model_release_requests(model_candidate_core_model_version_id);

CREATE TABLE IF NOT EXISTS production_model_release_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    release_request_id INTEGER NOT NULL,
    checkpoint_checksum TEXT,
    tokenizer_checksum TEXT,
    config_checksum TEXT,
    manifest_checksum TEXT,
    evaluation_report_checksum TEXT,
    training_report_checksum TEXT,
    security_report_checksum TEXT,
    target_assignment_keys_json TEXT NOT NULL DEFAULT '[]',
    canary_configuration_json TEXT NOT NULL DEFAULT '{}',
    rollback_plan_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','approved','rejected','expired','superseded'
    )),
    approved_by_admin_id TEXT,
    approved_at TEXT,
    expires_at TEXT,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    target_fingerprint TEXT NOT NULL,
    requested_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (release_request_id) REFERENCES production_model_release_requests(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_production_model_release_approvals_request
    ON production_model_release_approvals(release_request_id);

CREATE TABLE IF NOT EXISTS production_model_activation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    release_request_id INTEGER NOT NULL,
    release_approval_id INTEGER,
    inference_model_assignment_id INTEGER,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'pre_activation_snapshot','canary_started','canary_passed','canary_failed',
        'activated','activation_failed','rolled_back'
    )),
    previous_assignment_snapshot_json TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (release_request_id) REFERENCES production_model_release_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (release_approval_id) REFERENCES production_model_release_approvals(id),
    FOREIGN KEY (inference_model_assignment_id) REFERENCES inference_model_assignments(id)
);
CREATE INDEX IF NOT EXISTS ix_production_model_activation_events_request
    ON production_model_activation_events(release_request_id);

CREATE TABLE IF NOT EXISTS production_model_post_activation_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    release_request_id INTEGER NOT NULL,
    check_type TEXT NOT NULL,
    result_status TEXT NOT NULL CHECK (result_status IN (
        'passed','passed_with_warning','failed','not_applicable'
    )),
    metrics_json TEXT NOT NULL DEFAULT '{}',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (release_request_id) REFERENCES production_model_release_requests(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_production_model_post_activation_checks_request
    ON production_model_post_activation_checks(release_request_id);

CREATE TABLE IF NOT EXISTS production_rollback_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    target_type TEXT NOT NULL CHECK (target_type IN ('rag','model')),
    current_active_version TEXT,
    candidate_version TEXT,
    previous_assignment_snapshot_json TEXT NOT NULL DEFAULT '{}',
    previous_rag_state_snapshot_json TEXT NOT NULL DEFAULT '{}',
    backup_reference TEXT,
    rollback_steps_json TEXT NOT NULL DEFAULT '[]',
    validation_steps_json TEXT NOT NULL DEFAULT '[]',
    maximum_recovery_time_target_seconds INTEGER NOT NULL DEFAULT 900,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','verified','used','failed','superseded'
    )),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_production_rollback_plans_target_type
    ON production_rollback_plans(target_type);

CREATE TABLE IF NOT EXISTS production_rollback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    rollback_plan_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'validated','executed','execution_failed','verified_recovered'
    )),
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rollback_plan_id) REFERENCES production_rollback_plans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_production_rollback_events_plan
    ON production_rollback_events(rollback_plan_id);

CREATE TABLE IF NOT EXISTS production_artifact_security_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN (
        'checkpoint','tokenizer','rag_index','dataset_manifest','training_manifest',
        'release_manifest','backup','configuration'
    )),
    artifact_reference TEXT NOT NULL,
    result_status TEXT NOT NULL CHECK (result_status IN (
        'passed','passed_with_warning','failed','not_configured','not_applicable'
    )),
    checks_json TEXT NOT NULL DEFAULT '{}',
    findings_json TEXT NOT NULL DEFAULT '[]',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_production_artifact_security_checks_type
    ON production_artifact_security_checks(artifact_type);

CREATE TABLE IF NOT EXISTS production_backup_readiness_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    check_type TEXT NOT NULL CHECK (check_type IN ('backup','restore')),
    result_status TEXT NOT NULL CHECK (result_status IN (
        'passed','passed_with_warning','failed','not_configured','not_applicable'
    )),
    latest_backup_filename TEXT,
    latest_backup_age_seconds INTEGER,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_production_backup_readiness_checks_type
    ON production_backup_readiness_checks(check_type);

CREATE TABLE IF NOT EXISTS production_deployment_readiness_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    result_status TEXT NOT NULL CHECK (result_status IN (
        'ready','ready_with_conditions','not_ready','blocked'
    )),
    checks_json TEXT NOT NULL DEFAULT '{}',
    blocking_reasons_json TEXT NOT NULL DEFAULT '[]',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS production_regression_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    run_code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN (
        'in_progress','completed','completed_with_failures','environment_incomplete'
    )),
    batch_plan_json TEXT NOT NULL DEFAULT '[]',
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalized_at TEXT
);

CREATE TABLE IF NOT EXISTS production_regression_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    regression_run_id INTEGER NOT NULL,
    batch_name TEXT NOT NULL,
    command TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'passed','failed','environment_incomplete'
    )),
    passed_count INTEGER NOT NULL DEFAULT 0 CHECK (passed_count >= 0),
    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    error_count INTEGER NOT NULL DEFAULT 0 CHECK (error_count >= 0),
    duration_seconds REAL,
    raw_summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (regression_run_id) REFERENCES production_regression_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_production_regression_results_run
    ON production_regression_results(regression_run_id);

CREATE TABLE IF NOT EXISTS production_readiness_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    report_version INTEGER NOT NULL DEFAULT 1 CHECK (report_version > 0),
    report_json TEXT NOT NULL DEFAULT '{}',
    report_checksum_sha256 TEXT NOT NULL,
    recommendation TEXT NOT NULL CHECK (recommendation IN (
        'ready_for_text_nlp_production','ready_with_conditions','not_ready','blocked'
    )),
    finalized_by_admin_public_id TEXT NOT NULL,
    finalized_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(report_version)
);

CREATE TABLE IF NOT EXISTS production_acceptance_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    production_readiness_report_id INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN (
        'accepted','accepted_with_conditions','rejected','needs_remediation'
    )),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    conditions_json TEXT NOT NULL DEFAULT '{}',
    reviewer_admin_public_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    report_checksum TEXT NOT NULL,
    active_model_checksum TEXT,
    active_rag_checksum TEXT,
    target_fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (production_readiness_report_id) REFERENCES production_readiness_reports(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_production_acceptance_reviews_report
    ON production_acceptance_reviews(production_readiness_report_id);

CREATE TABLE IF NOT EXISTS production_readiness_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_public_id TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    performed_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_production_readiness_events_resource
    ON production_readiness_events(resource_type, resource_public_id);

CREATE TRIGGER IF NOT EXISTS production_rag_promotion_approvals_immutable_once_approved
    BEFORE UPDATE ON production_rag_promotion_approvals
    WHEN OLD.status = 'approved' AND NEW.status NOT IN ('approved','expired','superseded')
    BEGIN SELECT RAISE(ABORT, 'an approved production RAG promotion approval is immutable except transitioning to expired/superseded'); END;

CREATE TRIGGER IF NOT EXISTS production_rag_validation_results_immutable_update
    BEFORE UPDATE ON production_rag_validation_results
    BEGIN SELECT RAISE(ABORT, 'validation results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_rag_validation_results_immutable_delete
    BEFORE DELETE ON production_rag_validation_results
    BEGIN SELECT RAISE(ABORT, 'validation results are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_rag_activation_events_immutable_update
    BEFORE UPDATE ON production_rag_activation_events
    BEGIN SELECT RAISE(ABORT, 'activation events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_rag_activation_events_immutable_delete
    BEFORE DELETE ON production_rag_activation_events
    BEGIN SELECT RAISE(ABORT, 'activation events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_model_release_approvals_immutable_once_approved
    BEFORE UPDATE ON production_model_release_approvals
    WHEN OLD.status = 'approved' AND NEW.status NOT IN ('approved','expired','superseded')
    BEGIN SELECT RAISE(ABORT, 'an approved production model release approval is immutable except transitioning to expired/superseded'); END;

CREATE TRIGGER IF NOT EXISTS production_model_activation_events_immutable_update
    BEFORE UPDATE ON production_model_activation_events
    BEGIN SELECT RAISE(ABORT, 'activation events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_model_activation_events_immutable_delete
    BEFORE DELETE ON production_model_activation_events
    BEGIN SELECT RAISE(ABORT, 'activation events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_model_post_activation_checks_immutable_update
    BEFORE UPDATE ON production_model_post_activation_checks
    BEGIN SELECT RAISE(ABORT, 'post-activation checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_model_post_activation_checks_immutable_delete
    BEFORE DELETE ON production_model_post_activation_checks
    BEGIN SELECT RAISE(ABORT, 'post-activation checks are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_rollback_events_immutable_update
    BEFORE UPDATE ON production_rollback_events
    BEGIN SELECT RAISE(ABORT, 'rollback events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_rollback_events_immutable_delete
    BEFORE DELETE ON production_rollback_events
    BEGIN SELECT RAISE(ABORT, 'rollback events are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_artifact_security_checks_immutable_update
    BEFORE UPDATE ON production_artifact_security_checks
    BEGIN SELECT RAISE(ABORT, 'security checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_artifact_security_checks_immutable_delete
    BEFORE DELETE ON production_artifact_security_checks
    BEGIN SELECT RAISE(ABORT, 'security checks are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_backup_readiness_checks_immutable_update
    BEFORE UPDATE ON production_backup_readiness_checks
    BEGIN SELECT RAISE(ABORT, 'backup readiness checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_backup_readiness_checks_immutable_delete
    BEFORE DELETE ON production_backup_readiness_checks
    BEGIN SELECT RAISE(ABORT, 'backup readiness checks are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_deployment_readiness_checks_immutable_update
    BEFORE UPDATE ON production_deployment_readiness_checks
    BEGIN SELECT RAISE(ABORT, 'deployment readiness checks are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_deployment_readiness_checks_immutable_delete
    BEFORE DELETE ON production_deployment_readiness_checks
    BEGIN SELECT RAISE(ABORT, 'deployment readiness checks are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_regression_results_immutable_update
    BEFORE UPDATE ON production_regression_results
    BEGIN SELECT RAISE(ABORT, 'regression results are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_regression_results_immutable_delete
    BEFORE DELETE ON production_regression_results
    BEGIN SELECT RAISE(ABORT, 'regression results are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_readiness_reports_immutable_update
    BEFORE UPDATE ON production_readiness_reports
    BEGIN SELECT RAISE(ABORT, 'readiness reports are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_readiness_reports_immutable_delete
    BEFORE DELETE ON production_readiness_reports
    BEGIN SELECT RAISE(ABORT, 'readiness reports are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_acceptance_reviews_immutable_update
    BEFORE UPDATE ON production_acceptance_reviews
    BEGIN SELECT RAISE(ABORT, 'acceptance reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_acceptance_reviews_immutable_delete
    BEFORE DELETE ON production_acceptance_reviews
    BEGIN SELECT RAISE(ABORT, 'acceptance reviews are append-only'); END;

CREATE TRIGGER IF NOT EXISTS production_readiness_events_immutable_update
    BEFORE UPDATE ON production_readiness_events
    BEGIN SELECT RAISE(ABORT, 'readiness events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS production_readiness_events_immutable_delete
    BEFORE DELETE ON production_readiness_events
    BEGIN SELECT RAISE(ABORT, 'readiness events are append-only'); END;
"""

MIGRATION_039_NAME = "039_knowledge_routing_classification"
PHASE39_SCHEMA = """
CREATE TABLE IF NOT EXISTS routing_classification_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    input_hash TEXT NOT NULL,
    context_type TEXT NOT NULL CHECK (context_type IN (
        'public_chat_question','rag_record','dataset_candidate','training_candidate',
        'evaluation_prompt','knowledge_gap_case'
    )),
    language_category TEXT NOT NULL,
    intent TEXT NOT NULL,
    domain TEXT NOT NULL,
    subdomain TEXT,
    freshness TEXT NOT NULL,
    ambiguity TEXT NOT NULL,
    safety_risk TEXT NOT NULL,
    evidence_requirement TEXT NOT NULL,
    execution_route TEXT NOT NULL CHECK (execution_route IN (
        'core_model','approved_rag','trusted_web','tool','memory','clarify','refuse','insufficient'
    )),
    learning_target TEXT NOT NULL CHECK (learning_target IN (
        'core_model','rag_only','web_preferred','tool_required','evaluation_only',
        'future_training_candidate','do_not_learn','blocked'
    )),
    requires_human_review INTEGER NOT NULL DEFAULT 0 CHECK (requires_human_review IN (0,1)),
    input_truncated INTEGER NOT NULL DEFAULT 0 CHECK (input_truncated IN (0,1)),
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    policy_version TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    created_by_admin_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_routing_classification_decisions_context_type
    ON routing_classification_decisions(context_type);
CREATE INDEX IF NOT EXISTS ix_routing_classification_decisions_execution_route
    ON routing_classification_decisions(execution_route);
CREATE INDEX IF NOT EXISTS ix_routing_classification_decisions_domain
    ON routing_classification_decisions(domain);
CREATE INDEX IF NOT EXISTS ix_routing_classification_decisions_created_at
    ON routing_classification_decisions(created_at);

CREATE TRIGGER IF NOT EXISTS routing_classification_decisions_immutable_update
    BEFORE UPDATE ON routing_classification_decisions
    BEGIN SELECT RAISE(ABORT, 'routing classification decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS routing_classification_decisions_immutable_delete
    BEFORE DELETE ON routing_classification_decisions
    BEGIN SELECT RAISE(ABORT, 'routing classification decisions are append-only'); END;
"""

MIGRATION_040_NAME = "040_public_chat_routing_events"
PHASE40_SCHEMA = """
CREATE TABLE IF NOT EXISTS public_chat_routing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    classification_decision_public_id TEXT,
    recommended_route TEXT NOT NULL CHECK (recommended_route IN (
        'core_model','approved_rag','memory','clarify','refuse','insufficient',
        'trusted_web','tool'
    )),
    resolved_route TEXT NOT NULL CHECK (resolved_route IN (
        'core_model','approved_rag','memory','clarify','refuse','insufficient'
    )),
    route_status TEXT NOT NULL CHECK (route_status IN ('executable','unavailable','blocked')),
    evidence_status TEXT NOT NULL CHECK (evidence_status IN (
        'grounded','partially_grounded','insufficient','conflicting','model_only','none'
    )),
    detected_language TEXT NOT NULL,
    answer_language TEXT,
    safety_status TEXT NOT NULL CHECK (safety_status IN (
        'safe','caution','refused','output_blocked','review_flagged'
    )),
    fallbacks_attempted_json TEXT NOT NULL DEFAULT '[]',
    latency_ms INTEGER,
    error_code TEXT,
    conversation_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_public_chat_routing_events_resolved_route
    ON public_chat_routing_events(resolved_route);
CREATE INDEX IF NOT EXISTS ix_public_chat_routing_events_created_at
    ON public_chat_routing_events(created_at);
CREATE INDEX IF NOT EXISTS ix_public_chat_routing_events_request_id
    ON public_chat_routing_events(request_id);

CREATE TRIGGER IF NOT EXISTS public_chat_routing_events_immutable_update
    BEFORE UPDATE ON public_chat_routing_events
    BEGIN SELECT RAISE(ABORT, 'public chat routing events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS public_chat_routing_events_immutable_delete
    BEFORE DELETE ON public_chat_routing_events
    BEGIN SELECT RAISE(ABORT, 'public chat routing events are append-only'); END;

CREATE TABLE IF NOT EXISTS public_chat_feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL,
    route_used TEXT NOT NULL,
    answer_hash TEXT NOT NULL,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN (
        'thumbs_up','thumbs_down','language_report','safety_report'
    )),
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_public_chat_feedback_events_request_id
    ON public_chat_feedback_events(request_id);

CREATE TRIGGER IF NOT EXISTS public_chat_feedback_events_immutable_update
    BEFORE UPDATE ON public_chat_feedback_events
    BEGIN SELECT RAISE(ABORT, 'public chat feedback events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS public_chat_feedback_events_immutable_delete
    BEFORE DELETE ON public_chat_feedback_events
    BEGIN SELECT RAISE(ABORT, 'public chat feedback events are append-only'); END;
"""

MIGRATION_041_NAME = "041_knowledge_gap_registry"
PHASE41_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_gap_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    canonical_question TEXT NOT NULL,
    primary_language TEXT NOT NULL,
    domain TEXT,
    intent TEXT,
    freshness TEXT,
    cluster_type TEXT NOT NULL DEFAULT 'knowledge_gap',
    frequency INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    priority_score REAL NOT NULL DEFAULT 0,
    priority_band TEXT NOT NULL DEFAULT 'informational' CHECK (priority_band IN (
        'critical','high','medium','low','informational'
    )),
    priority_reason_codes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_clusters_status
    ON knowledge_gap_clusters(status);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_clusters_priority_band
    ON knowledge_gap_clusters(priority_band);

CREATE TABLE IF NOT EXISTS knowledge_gap_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    cluster_id INTEGER REFERENCES knowledge_gap_clusters(id),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'knowledge_gap','clarification_event','safety_event','operational_failure',
        'language_failure','source_failure','tool_capability_gap','web_capability_gap',
        'feedback_issue','not_applicable'
    )),
    primary_reason_code TEXT NOT NULL,
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN (
        'new','classified','needs_clarification','evidence_search','answer_draft',
        'review_required','rag_trial','monitored','training_assessment_candidate',
        'resolved','rejected','blocked','archived','deleted_payload'
    )),
    stage TEXT NOT NULL DEFAULT 'capture' CHECK (stage IN (
        'capture','privacy_processing','classification','deduplication','prioritization',
        'research','drafting','human_review','rag_handoff','monitoring','training_handoff',
        'resolution','retention'
    )),
    language TEXT,
    domain TEXT,
    intent TEXT,
    freshness TEXT,
    input_hash TEXT NOT NULL,
    canonical_question TEXT,
    redacted_question TEXT,
    content_unavailable_for_review INTEGER NOT NULL DEFAULT 0,
    retention_policy TEXT NOT NULL DEFAULT 'standard' CHECK (retention_policy IN (
        'standard','extended_review','hash_only','not_retained'
    )),
    frequency INTEGER NOT NULL DEFAULT 1,
    priority_score REAL NOT NULL DEFAULT 0,
    priority_band TEXT NOT NULL DEFAULT 'informational' CHECK (priority_band IN (
        'critical','high','medium','low','informational'
    )),
    priority_reason_codes_json TEXT NOT NULL DEFAULT '[]',
    eligible_for_rag_research INTEGER NOT NULL DEFAULT 0,
    eligible_for_rag_trial_proposal INTEGER NOT NULL DEFAULT 0,
    rag_handoff_reason_codes_json TEXT NOT NULL DEFAULT '[]',
    eligible_for_training_assessment INTEGER NOT NULL DEFAULT 0,
    training_handoff_reason_codes_json TEXT NOT NULL DEFAULT '[]',
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cases_status ON knowledge_gap_cases(status);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cases_event_type ON knowledge_gap_cases(event_type);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cases_input_hash ON knowledge_gap_cases(input_hash);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cases_cluster_id ON knowledge_gap_cases(cluster_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cases_priority_band
    ON knowledge_gap_cases(priority_band);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cases_language_domain_intent
    ON knowledge_gap_cases(language, domain, intent);

CREATE TABLE IF NOT EXISTS knowledge_gap_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    case_id INTEGER REFERENCES knowledge_gap_cases(id),
    routing_event_public_id TEXT,
    feedback_event_public_id TEXT,
    request_hash TEXT NOT NULL,
    route_recommended TEXT,
    route_used TEXT,
    evidence_status TEXT,
    confidence_band TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'knowledge_gap','clarification_event','safety_event','operational_failure',
        'language_failure','source_failure','tool_capability_gap','web_capability_gap',
        'feedback_issue','not_applicable'
    )),
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    language TEXT,
    domain TEXT,
    intent TEXT,
    freshness TEXT,
    privacy_status TEXT NOT NULL DEFAULT 'standard',
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_occurrences_case_id
    ON knowledge_gap_occurrences(case_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_occurrences_request_hash
    ON knowledge_gap_occurrences(request_hash);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_occurrences_occurred_at
    ON knowledge_gap_occurrences(occurred_at);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_occurrences_immutable_update
    BEFORE UPDATE ON knowledge_gap_occurrences
    BEGIN SELECT RAISE(ABORT, 'knowledge gap occurrences are append-only'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_occurrences_immutable_delete
    BEFORE DELETE ON knowledge_gap_occurrences
    BEGIN SELECT RAISE(ABORT, 'knowledge gap occurrences are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_cluster_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    cluster_id INTEGER NOT NULL REFERENCES knowledge_gap_clusters(id),
    case_id INTEGER NOT NULL REFERENCES knowledge_gap_cases(id),
    member_status TEXT NOT NULL DEFAULT 'active' CHECK (member_status IN ('active','removed')),
    decision TEXT NOT NULL CHECK (decision IN (
        'same_case','probable_duplicate','possible_duplicate','distinct','needs_review'
    )),
    confirmed_by_admin_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cluster_members_cluster_id
    ON knowledge_gap_cluster_members(cluster_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_cluster_members_case_id
    ON knowledge_gap_cluster_members(case_id);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_cluster_members_immutable_update
    BEFORE UPDATE ON knowledge_gap_cluster_members
    BEGIN SELECT RAISE(ABORT,
        'knowledge gap cluster members are append-only -- insert a new row to unmerge'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_cluster_members_immutable_delete
    BEFORE DELETE ON knowledge_gap_cluster_members
    BEGIN SELECT RAISE(ABORT, 'knowledge gap cluster members are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    case_id INTEGER NOT NULL REFERENCES knowledge_gap_cases(id),
    decision TEXT NOT NULL CHECK (decision IN (
        'confirm_gap','reclassify','merge','keep_separate','needs_evidence',
        'send_to_rag_research','send_to_evaluation','mark_training_assessment_candidate',
        'resolve','reject','block','archive'
    )),
    comment TEXT,
    reviewed_by_admin_public_id TEXT NOT NULL,
    stale_check_fingerprint TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_reviews_case_id ON knowledge_gap_reviews(case_id);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_reviews_immutable_update
    BEFORE UPDATE ON knowledge_gap_reviews
    BEGIN SELECT RAISE(ABORT, 'knowledge gap reviews are append-only'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_reviews_immutable_delete
    BEFORE DELETE ON knowledge_gap_reviews
    BEGIN SELECT RAISE(ABORT, 'knowledge gap reviews are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_research_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    case_id INTEGER NOT NULL REFERENCES knowledge_gap_cases(id),
    note_type TEXT NOT NULL CHECK (note_type IN (
        'investigation','possible_source','rights_concern','answer_draft','routing_issue',
        'language_issue','safety_issue','operational_issue','resolution_note'
    )),
    note_text_redacted TEXT NOT NULL,
    source_reference TEXT,
    author_admin_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_research_notes_case_id
    ON knowledge_gap_research_notes(case_id);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_research_notes_immutable_update
    BEFORE UPDATE ON knowledge_gap_research_notes
    BEGIN SELECT RAISE(ABORT, 'knowledge gap research notes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_research_notes_immutable_delete
    BEFORE DELETE ON knowledge_gap_research_notes
    BEGIN SELECT RAISE(ABORT, 'knowledge gap research notes are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_resolution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    case_id INTEGER NOT NULL REFERENCES knowledge_gap_cases(id),
    resolution_type TEXT NOT NULL CHECK (resolution_type IN (
        'answered_by_existing_model','resolved_by_routing_rule','resolved_by_approved_rag',
        'requires_trusted_web','requires_tool','requires_translation',
        'requires_language_policy_fix','requires_safety_policy_fix','requires_operational_fix',
        'evaluation_case_created','future_training_assessment','not_reproducible',
        'duplicate_resolved','rejected','blocked'
    )),
    notes TEXT,
    resolved_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_resolution_events_case_id
    ON knowledge_gap_resolution_events(case_id);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_resolution_events_immutable_update
    BEFORE UPDATE ON knowledge_gap_resolution_events
    BEGIN SELECT RAISE(ABORT, 'knowledge gap resolution events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_resolution_events_immutable_delete
    BEFORE DELETE ON knowledge_gap_resolution_events
    BEGIN SELECT RAISE(ABORT, 'knowledge gap resolution events are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_status_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    case_id INTEGER NOT NULL REFERENCES knowledge_gap_cases(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    reason TEXT,
    changed_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_status_events_case_id
    ON knowledge_gap_status_events(case_id);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_status_events_immutable_update
    BEFORE UPDATE ON knowledge_gap_status_events
    BEGIN SELECT RAISE(ABORT, 'knowledge gap status events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_status_events_immutable_delete
    BEFORE DELETE ON knowledge_gap_status_events
    BEGIN SELECT RAISE(ABORT, 'knowledge gap status events are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_deletion_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    case_id INTEGER NOT NULL REFERENCES knowledge_gap_cases(id),
    state TEXT NOT NULL CHECK (state IN (
        'requested','confirmed','executed','rejected','cancelled'
    )),
    requested_by_admin_public_id TEXT NOT NULL,
    confirmed_by_admin_public_id TEXT,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_deletion_requests_case_id
    ON knowledge_gap_deletion_requests(case_id);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_deletion_requests_immutable_update
    BEFORE UPDATE ON knowledge_gap_deletion_requests
    BEGIN SELECT RAISE(ABORT,
        'knowledge gap deletion requests are append-only -- insert a new row to advance state');
    END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_deletion_requests_immutable_delete
    BEFORE DELETE ON knowledge_gap_deletion_requests
    BEGIN SELECT RAISE(ABORT, 'knowledge gap deletion requests are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    report_date TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_daily_reports_report_date
    ON knowledge_gap_daily_reports(report_date);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_daily_reports_immutable_update
    BEFORE UPDATE ON knowledge_gap_daily_reports
    BEGIN SELECT RAISE(ABORT, 'knowledge gap daily reports are append-only'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_daily_reports_immutable_delete
    BEFORE DELETE ON knowledge_gap_daily_reports
    BEGIN SELECT RAISE(ABORT, 'knowledge gap daily reports are append-only'); END;
"""

MIGRATION_042_NAME = "042_trusted_web_tool_gateway"
PHASE42_SCHEMA = """
CREATE TABLE IF NOT EXISTS trusted_web_search_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    web_category TEXT NOT NULL CHECK (web_category IN (
        'current_software_documentation','government_service_information',
        'current_rules_and_regulations','current_general_information',
        'official_product_documentation'
    )),
    provider_name TEXT,
    policy_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'success','provider_unavailable','quota_exceeded','no_trusted_source',
        'source_conflict','evidence_insufficient','fetch_blocked','error'
    )),
    result_count INTEGER NOT NULL DEFAULT 0,
    conflict_status TEXT NOT NULL DEFAULT 'no_conflict' CHECK (conflict_status IN (
        'no_conflict','minor_difference','material_conflict','date_version_conflict',
        'unresolved_conflict'
    )),
    overall_freshness_status TEXT CHECK (overall_freshness_status IN (
        'fresh','possibly_stale','stale','undated','conflicting'
    )),
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_trusted_web_search_events_request_id
    ON trusted_web_search_events(request_id);
CREATE INDEX IF NOT EXISTS ix_trusted_web_search_events_status
    ON trusted_web_search_events(status);
CREATE INDEX IF NOT EXISTS ix_trusted_web_search_events_web_category
    ON trusted_web_search_events(web_category);
CREATE INDEX IF NOT EXISTS ix_trusted_web_search_events_created_at
    ON trusted_web_search_events(created_at);

CREATE TRIGGER IF NOT EXISTS trusted_web_search_events_immutable_update
    BEFORE UPDATE ON trusted_web_search_events
    BEGIN SELECT RAISE(ABORT, 'trusted web search events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS trusted_web_search_events_immutable_delete
    BEFORE DELETE ON trusted_web_search_events
    BEGIN SELECT RAISE(ABORT, 'trusted web search events are append-only'); END;

CREATE TABLE IF NOT EXISTS trusted_web_source_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    search_event_id INTEGER NOT NULL REFERENCES trusted_web_search_events(id),
    source_url_normalized TEXT NOT NULL,
    source_domain TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    updated_at TEXT,
    retrieved_at TEXT NOT NULL,
    trust_level TEXT NOT NULL CHECK (trust_level IN (
        'official','authoritative','reputable_secondary','community','unknown','blocked'
    )),
    verification_level TEXT NOT NULL CHECK (verification_level IN (
        'search_result_only','domain_verified','page_fetched','content_verified',
        'cross_source_verified','official_source_verified'
    )),
    freshness_status TEXT NOT NULL CHECK (freshness_status IN (
        'fresh','possibly_stale','stale','undated','conflicting'
    )),
    support_status TEXT NOT NULL CHECK (support_status IN (
        'directly_supports','partially_supports','background_context','contradicts'
    )),
    content_hash TEXT,
    excerpt_redacted TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_trusted_web_source_evidence_search_event_id
    ON trusted_web_source_evidence(search_event_id);
CREATE INDEX IF NOT EXISTS ix_trusted_web_source_evidence_source_domain
    ON trusted_web_source_evidence(source_domain);

CREATE TRIGGER IF NOT EXISTS trusted_web_source_evidence_immutable_update
    BEFORE UPDATE ON trusted_web_source_evidence
    BEGIN SELECT RAISE(ABORT, 'trusted web source evidence is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trusted_web_source_evidence_immutable_delete
    BEFORE DELETE ON trusted_web_source_evidence
    BEGIN SELECT RAISE(ABORT, 'trusted web source evidence is append-only'); END;

CREATE TABLE IF NOT EXISTS trusted_web_fetch_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    search_event_id INTEGER REFERENCES trusted_web_search_events(id),
    url_domain TEXT NOT NULL,
    http_status INTEGER,
    content_type TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'success','blocked','timeout','error'
    )),
    block_reason TEXT,
    injection_status TEXT CHECK (injection_status IN (
        'clean','warning','quarantined','blocked'
    )),
    bytes_fetched INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_trusted_web_fetch_events_search_event_id
    ON trusted_web_fetch_events(search_event_id);
CREATE INDEX IF NOT EXISTS ix_trusted_web_fetch_events_outcome
    ON trusted_web_fetch_events(outcome);

CREATE TRIGGER IF NOT EXISTS trusted_web_fetch_events_immutable_update
    BEFORE UPDATE ON trusted_web_fetch_events
    BEGIN SELECT RAISE(ABORT, 'trusted web fetch events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS trusted_web_fetch_events_immutable_delete
    BEFORE DELETE ON trusted_web_fetch_events
    BEGIN SELECT RAISE(ABORT, 'trusted web fetch events are append-only'); END;

CREATE TABLE IF NOT EXISTS trusted_web_policy_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'loaded','reload_proposed','reload_confirmed','validation_failed',
        'source_block_proposed','source_block_confirmed',
        'issue_flagged','allowlist_review_proposed'
    )),
    policy_version TEXT,
    policy_checksum_sha256 TEXT,
    admin_public_id TEXT,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_trusted_web_policy_events_event_type
    ON trusted_web_policy_events(event_type);

CREATE TRIGGER IF NOT EXISTS trusted_web_policy_events_immutable_update
    BEFORE UPDATE ON trusted_web_policy_events
    BEGIN SELECT RAISE(ABORT, 'trusted web policy events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS trusted_web_policy_events_immutable_delete
    BEFORE DELETE ON trusted_web_policy_events
    BEGIN SELECT RAISE(ABORT, 'trusted web policy events are append-only'); END;

CREATE TABLE IF NOT EXISTS deterministic_tool_execution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL,
    tool_name TEXT NOT NULL CHECK (tool_name IN (
        'calculator','unit_conversion','date_time_arithmetic','unknown'
    )),
    tool_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'success','input_invalid','disabled','unsupported','timeout','execution_failed',
        'rate_limited'
    )),
    input_summary TEXT,
    result_summary TEXT,
    error_code TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_deterministic_tool_execution_events_request_id
    ON deterministic_tool_execution_events(request_id);
CREATE INDEX IF NOT EXISTS ix_deterministic_tool_execution_events_tool_name
    ON deterministic_tool_execution_events(tool_name);
CREATE INDEX IF NOT EXISTS ix_deterministic_tool_execution_events_status
    ON deterministic_tool_execution_events(status);

CREATE TRIGGER IF NOT EXISTS deterministic_tool_execution_events_immutable_update
    BEFORE UPDATE ON deterministic_tool_execution_events
    BEGIN SELECT RAISE(ABORT, 'deterministic tool execution events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS deterministic_tool_execution_events_immutable_delete
    BEFORE DELETE ON deterministic_tool_execution_events
    BEGIN SELECT RAISE(ABORT, 'deterministic tool execution events are append-only'); END;

CREATE TABLE IF NOT EXISTS knowledge_gap_capability_resolutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    case_id INTEGER NOT NULL REFERENCES knowledge_gap_cases(id),
    resolution_kind TEXT NOT NULL CHECK (resolution_kind IN (
        'resolved_by_trusted_web','resolved_by_tool'
    )),
    search_event_id INTEGER REFERENCES trusted_web_search_events(id),
    tool_execution_id INTEGER REFERENCES deterministic_tool_execution_events(id),
    matched_by TEXT NOT NULL,
    confidence_band TEXT NOT NULL DEFAULT 'medium' CHECK (confidence_band IN (
        'high','medium','low','unknown'
    )),
    linked_by_admin_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_capability_resolutions_case_id
    ON knowledge_gap_capability_resolutions(case_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_gap_capability_resolutions_resolution_kind
    ON knowledge_gap_capability_resolutions(resolution_kind);

CREATE TRIGGER IF NOT EXISTS knowledge_gap_capability_resolutions_immutable_update
    BEFORE UPDATE ON knowledge_gap_capability_resolutions
    BEGIN SELECT RAISE(ABORT, 'knowledge gap capability resolutions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_gap_capability_resolutions_immutable_delete
    BEFORE DELETE ON knowledge_gap_capability_resolutions
    BEGIN SELECT RAISE(ABORT, 'knowledge gap capability resolutions are append-only'); END;
"""

MIGRATION_043_NAME = "043_document_sft_workflow"
PHASE43_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_sft_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    source_chunk_id INTEGER,
    source_page_start INTEGER NOT NULL CHECK (source_page_start > 0),
    source_page_end INTEGER NOT NULL CHECK (source_page_end >= source_page_start),
    task TEXT NOT NULL CHECK (task IN (
        'definition','fact_answer','explanation','contextual_meaning','multiple_meanings',
        'grammar','spelling_correction','grammar_correction','instruction_following',
        'summarization','clarification_request','Tamil_to_English','English_to_Tamil',
        'Tanglish_input_to_Tamil','basic_math_reasoning','computer_basics','safety_response'
    )),
    domain TEXT NOT NULL DEFAULT 'general',
    difficulty TEXT NOT NULL DEFAULT 'basic' CHECK (difficulty IN (
        'basic','intermediate','advanced'
    )),
    instruction TEXT NOT NULL CHECK (length(trim(instruction)) > 0),
    context TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL CHECK (length(trim(response)) > 0),
    input_language TEXT NOT NULL,
    output_language TEXT NOT NULL,
    rights_status TEXT NOT NULL CHECK (rights_status IN ('verified','pending','blocked')),
    quality_status TEXT NOT NULL DEFAULT 'draft' CHECK (quality_status IN (
        'draft','pending_review','needs_correction','approved','rejected','duplicate'
    )),
    generation_method TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    duplicate_of_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE,
    FOREIGN KEY (source_chunk_id) REFERENCES semantic_chunks(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_document_sft_candidates_status
    ON document_sft_candidates(document_source_id, quality_status);
CREATE INDEX IF NOT EXISTS ix_document_sft_candidates_hash
    ON document_sft_candidates(content_hash);
CREATE INDEX IF NOT EXISTS ix_document_sft_candidates_task
    ON document_sft_candidates(task);

CREATE TABLE IF NOT EXISTS document_tamil_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL CHECK (page_number > 0),
    issue_type TEXT NOT NULL CHECK (issue_type IN (
        'broken_combining_mark','misplaced_pulli','broken_vowel_sign','invalid_unicode',
        'ocr_character_substitution','non_tamil_glyph_contamination','zero_width_corruption',
        'spelling_issue','grammar_mismatch'
    )),
    context TEXT NOT NULL DEFAULT '',
    original_text TEXT NOT NULL,
    suggested_text TEXT NOT NULL DEFAULT '',
    confidence_band TEXT NOT NULL DEFAULT 'medium' CHECK (confidence_band IN (
        'high','medium','low','unknown'
    )),
    reason_code TEXT NOT NULL,
    correction_risk TEXT NOT NULL CHECK (correction_risk IN (
        'mechanical','preview_required','mandatory_review'
    )),
    human_review_required INTEGER NOT NULL DEFAULT 0 CHECK (human_review_required IN (0,1)),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN (
        'pending','accepted','rejected','edited','ignored'
    )),
    reviewed_by_admin_public_id TEXT,
    reviewed_at TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_document_tamil_quality_issues_document
    ON document_tamil_quality_issues(document_source_id, review_status);
CREATE INDEX IF NOT EXISTS ix_document_tamil_quality_issues_hash
    ON document_tamil_quality_issues(content_hash);

CREATE TABLE IF NOT EXISTS document_sft_candidate_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('approve','reject','edit','needs_correction')),
    actor_reference TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES document_sft_candidates(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_document_sft_candidate_reviews_candidate_id
    ON document_sft_candidate_reviews(candidate_id);

CREATE TRIGGER IF NOT EXISTS document_sft_candidate_reviews_immutable_update
    BEFORE UPDATE ON document_sft_candidate_reviews
    BEGIN SELECT RAISE(ABORT, 'document sft candidate reviews are immutable'); END;
CREATE TRIGGER IF NOT EXISTS document_sft_candidate_reviews_immutable_delete
    BEFORE DELETE ON document_sft_candidate_reviews
    BEGIN SELECT RAISE(ABORT, 'document sft candidate reviews are immutable'); END;

CREATE TABLE IF NOT EXISTS document_sft_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_count INTEGER NOT NULL,
    excluded_count INTEGER NOT NULL,
    task_distribution_json TEXT NOT NULL DEFAULT '{}',
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    domain_distribution_json TEXT NOT NULL DEFAULT '{}',
    source_document_ids_json TEXT NOT NULL DEFAULT '[]',
    rights_summary_json TEXT NOT NULL DEFAULT '{}',
    quality_summary_json TEXT NOT NULL DEFAULT '{}',
    checksum_sha256 TEXT NOT NULL,
    export_path TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_sft_exports_created_at
    ON document_sft_exports(created_at);

CREATE TRIGGER IF NOT EXISTS document_sft_exports_immutable_update
    BEFORE UPDATE ON document_sft_exports
    BEGIN SELECT RAISE(ABORT, 'document sft exports are append-only'); END;
CREATE TRIGGER IF NOT EXISTS document_sft_exports_immutable_delete
    BEFORE DELETE ON document_sft_exports
    BEGIN SELECT RAISE(ABORT, 'document sft exports are append-only'); END;
"""

MIGRATION_044_NAME = "044_document_sft_finalization"
PHASE44_SCHEMA = """
-- Widen document_repeated_elements.element_type (migration 025) to add the
-- 4 new content-pattern-based cleanup categories from Task Finalization §12
-- (copyright_notice, navigation_text, watermark_text, logo_text). SQLite
-- cannot loosen a CHECK constraint in place, so this rebuilds the table --
-- the table has no triggers and a small, well-understood column set, so a
-- rebuild is safe; every row's data is preserved unchanged. This is the
-- only structural change PHASE44_SCHEMA makes to a pre-existing table;
-- migration 043 itself is never edited.
CREATE TABLE document_repeated_elements_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    normalized_text TEXT NOT NULL,
    element_type TEXT NOT NULL CHECK (element_type IN (
        'header','footer','page_number','unknown',
        'copyright_notice','navigation_text','watermark_text','logo_text'
    )),
    page_occurrences_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status TEXT NOT NULL DEFAULT 'suggested' CHECK (status IN (
        'suggested','accepted','rejected','applied'
    )),
    reviewed_by_admin_public_id TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE
);
INSERT INTO document_repeated_elements_v2(
    id,public_id,document_source_id,normalized_text,element_type,page_occurrences_json,
    confidence,status,reviewed_by_admin_public_id,reviewed_at,created_at
) SELECT
    id,public_id,document_source_id,normalized_text,element_type,page_occurrences_json,
    confidence,status,reviewed_by_admin_public_id,reviewed_at,created_at
FROM document_repeated_elements;
DROP TABLE document_repeated_elements;
ALTER TABLE document_repeated_elements_v2 RENAME TO document_repeated_elements;
CREATE INDEX IF NOT EXISTS ix_document_repeated_elements_document
    ON document_repeated_elements(document_source_id);
CREATE INDEX IF NOT EXISTS ix_document_repeated_elements_status
    ON document_repeated_elements(document_source_id, status);

CREATE TABLE IF NOT EXISTS document_sft_dataset_handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    export_public_id TEXT NOT NULL UNIQUE,
    export_checksum_sha256 TEXT NOT NULL,
    dataset_source_public_id TEXT NOT NULL,
    dataset_version_public_id TEXT,
    dataset_build_public_id TEXT,
    imported_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    rights_blocked_count INTEGER NOT NULL DEFAULT 0,
    security_blocked_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN (
        'imported','version_proposed','version_built','blocked'
    )),
    created_by TEXT NOT NULL,
    confirmed_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_sft_dataset_handoffs_status
    ON document_sft_dataset_handoffs(status);

CREATE TABLE IF NOT EXISTS document_tamil_correction_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    incorrect_form TEXT NOT NULL,
    approved_correction TEXT NOT NULL,
    issue_category TEXT NOT NULL CHECK (issue_category IN (
        'known_ocr_substitution','pulli_error','vowel_sign_error','grapheme_integrity',
        'zero_width_contamination','unicode_normalization_mismatch','spelling_variant',
        'word_boundary_anomaly','punctuation_spacing','mixed_script_contamination'
    )),
    evidence TEXT NOT NULL DEFAULT '',
    confidence_band TEXT NOT NULL DEFAULT 'medium' CHECK (confidence_band IN (
        'high','medium','low','unknown'
    )),
    meaning_change_risk TEXT NOT NULL CHECK (meaning_change_risk IN (
        'mechanical','spelling','grammatical','meaning_sensitive','ambiguous'
    )),
    automatic_proposal_allowed INTEGER NOT NULL DEFAULT 0 CHECK (automatic_proposal_allowed IN (0,1)),
    human_review_required INTEGER NOT NULL DEFAULT 1 CHECK (human_review_required IN (0,1)),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft','needs_review','approved','active','rejected'
    )),
    rule_version INTEGER NOT NULL DEFAULT 1 CHECK (rule_version > 0),
    created_by_admin_public_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_tamil_correction_rules_status
    ON document_tamil_correction_rules(status);

CREATE TABLE IF NOT EXISTS document_tamil_correction_rule_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    rule_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('submit_review','approve','activate','reject')),
    actor_reference TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rule_id) REFERENCES document_tamil_correction_rules(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_document_tamil_correction_rule_reviews_rule_id
    ON document_tamil_correction_rule_reviews(rule_id);
CREATE TRIGGER IF NOT EXISTS document_tamil_correction_rule_reviews_immutable_update
    BEFORE UPDATE ON document_tamil_correction_rule_reviews
    BEGIN SELECT RAISE(ABORT, 'document tamil correction rule reviews are immutable'); END;
CREATE TRIGGER IF NOT EXISTS document_tamil_correction_rule_reviews_immutable_delete
    BEFORE DELETE ON document_tamil_correction_rule_reviews
    BEGIN SELECT RAISE(ABORT, 'document tamil correction rule reviews are immutable'); END;

CREATE TABLE IF NOT EXISTS document_content_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL CHECK (page_number > 0),
    content_type TEXT NOT NULL CHECK (content_type IN (
        'text_only','image_with_caption','image_with_explanation','diagram_with_labels',
        'table','mixed_content','image_without_usable_text'
    )),
    caption_text TEXT NOT NULL DEFAULT '',
    nearby_text TEXT NOT NULL DEFAULT '',
    table_data_json TEXT NOT NULL DEFAULT '{}',
    vision_required INTEGER NOT NULL DEFAULT 0 CHECK (vision_required IN (0,1)),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN (
        'pending','reviewed','approved','excluded'
    )),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE,
    UNIQUE(document_source_id, page_number)
);
CREATE INDEX IF NOT EXISTS ix_document_content_classifications_type
    ON document_content_classifications(document_source_id, content_type);

CREATE TABLE IF NOT EXISTS document_security_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL CHECK (page_number > 0),
    finding_type TEXT NOT NULL CHECK (finding_type IN (
        'prompt_injection','pii_email','pii_phone','pii_address','pii_government_id',
        'pii_bank','pii_secret','pii_path'
    )),
    matched_text TEXT NOT NULL,
    confidence_band TEXT NOT NULL DEFAULT 'medium' CHECK (confidence_band IN (
        'high','medium','low','unknown'
    )),
    reason_code TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'allow','mask_for_preview','exclude_from_sft','require_review','block_export'
    )),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN (
        'pending','reviewed','dismissed'
    )),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_document_security_findings_document
    ON document_security_findings(document_source_id, finding_type);
CREATE INDEX IF NOT EXISTS ix_document_security_findings_hash
    ON document_security_findings(content_hash);
"""
