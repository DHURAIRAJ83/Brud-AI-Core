"""Environment-backed application configuration."""

import logging
import sqlite3
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Validated Brud AI settings loaded from BRUD_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    env: str = Field(default="development", validation_alias="BRUD_ENV")
    host: str = Field(default="127.0.0.1", validation_alias="BRUD_HOST")
    port: int = Field(default=8000, ge=1, le=65535, validation_alias="BRUD_PORT")
    database_path: Path = Field(
        default=Path("data/database/brud_ai.db"),
        validation_alias="BRUD_DATABASE_PATH",
    )
    log_level: str = Field(default="INFO", validation_alias="BRUD_LOG_LEVEL")
    chatbot_origin: str = Field(
        default="http://localhost:5173", validation_alias="BRUD_CHATBOT_ORIGIN"
    )
    admin_origin: str = Field(default="http://localhost:5174", validation_alias="BRUD_ADMIN_ORIGIN")
    debug: bool = Field(default=False, validation_alias="BRUD_DEBUG")
    database_backup_dir: Path = Field(
        default=Path("data/database/backups"), validation_alias="BRUD_DATABASE_BACKUP_DIR"
    )
    database_busy_timeout_ms: int = Field(
        default=5000, ge=0, le=120_000, validation_alias="BRUD_DATABASE_BUSY_TIMEOUT_MS"
    )
    database_wal: bool = Field(default=True, validation_alias="BRUD_DATABASE_WAL")
    database_auto_backup: bool = Field(default=True, validation_alias="BRUD_DATABASE_AUTO_BACKUP")
    audit_enabled: bool = Field(default=True, validation_alias="BRUD_AUDIT_ENABLED")
    audit_retention_days: int = Field(
        default=365, ge=1, validation_alias="BRUD_AUDIT_RETENTION_DAYS"
    )
    max_metadata_bytes: int = Field(
        default=65_536, ge=256, le=1_048_576, validation_alias="BRUD_MAX_METADATA_BYTES"
    )
    allowed_data_dir: Path = Field(default=Path("data"), validation_alias="BRUD_ALLOWED_DATA_DIR")
    allowed_model_dir: Path = Field(
        default=Path("models"), validation_alias="BRUD_ALLOWED_MODEL_DIR"
    )
    allowed_export_dir: Path = Field(
        default=Path("models/exports"), validation_alias="BRUD_ALLOWED_EXPORT_DIR"
    )
    allow_external_storage: bool = Field(
        default=False, validation_alias="BRUD_ALLOW_EXTERNAL_STORAGE", exclude=True
    )
    admin_session_ttl_minutes: int = Field(
        default=480, ge=5, le=10_080, validation_alias="BRUD_ADMIN_SESSION_TTL_MINUTES"
    )
    admin_max_failed_logins: int = Field(
        default=5, ge=1, le=100, validation_alias="BRUD_ADMIN_MAX_FAILED_LOGINS"
    )
    admin_lockout_minutes: int = Field(
        default=15, ge=1, le=1440, validation_alias="BRUD_ADMIN_LOCKOUT_MINUTES"
    )
    admin_cookie_secure: bool = Field(default=False, validation_alias="BRUD_ADMIN_COOKIE_SECURE")
    admin_cookie_name: str = Field(
        default="brud_admin_session", validation_alias="BRUD_ADMIN_COOKIE_NAME"
    )
    csrf_cookie_name: str = Field(default="brud_csrf", validation_alias="BRUD_CSRF_COOKIE_NAME")
    csrf_header_name: str = Field(default="X-CSRF-Token", validation_alias="BRUD_CSRF_HEADER_NAME")
    import_dir: Path = Field(default=Path("data/imports"), validation_alias="BRUD_IMPORT_DIR")
    import_report_dir: Path = Field(
        default=Path("data/imports/reports"), validation_alias="BRUD_IMPORT_REPORT_DIR"
    )
    import_max_file_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        le=100 * 1024 * 1024,
        validation_alias="BRUD_IMPORT_MAX_FILE_BYTES",
    )
    import_max_rows: int = Field(
        default=25_000, ge=1, le=100_000, validation_alias="BRUD_IMPORT_MAX_ROWS"
    )
    import_max_columns: int = Field(
        default=50, ge=1, le=500, validation_alias="BRUD_IMPORT_MAX_COLUMNS"
    )
    import_max_cell_chars: int = Field(
        default=20_000, ge=1, le=1_000_000, validation_alias="BRUD_IMPORT_MAX_CELL_CHARS"
    )
    import_preview_ttl_minutes: int = Field(
        default=60, ge=5, le=10_080, validation_alias="BRUD_IMPORT_PREVIEW_TTL_MINUTES"
    )
    import_allowed_extensions: str = Field(
        default=".json,.jsonl,.csv,.txt", validation_alias="BRUD_IMPORT_ALLOWED_EXTENSIONS"
    )
    import_allowed_mime_types: str = Field(
        default="application/json,application/x-ndjson,text/csv,text/plain,application/octet-stream",
        validation_alias="BRUD_IMPORT_ALLOWED_MIME_TYPES",
    )
    import_default_encoding: str = Field(
        default="utf-8", validation_alias="BRUD_IMPORT_DEFAULT_ENCODING"
    )
    import_max_error_report_rows: int = Field(
        default=5_000, ge=1, le=25_000, validation_alias="BRUD_IMPORT_MAX_ERROR_REPORT_ROWS"
    )
    document_dir: Path = Field(default=Path("data/documents"), validation_alias="BRUD_DOCUMENT_DIR")
    document_report_dir: Path = Field(
        default=Path("data/documents/reports"), validation_alias="BRUD_DOCUMENT_REPORT_DIR"
    )
    document_max_file_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1,
        le=250 * 1024 * 1024,
        validation_alias="BRUD_DOCUMENT_MAX_FILE_BYTES",
    )
    document_max_pages: int = Field(
        default=300, ge=1, le=2000, validation_alias="BRUD_DOCUMENT_MAX_PAGES"
    )
    document_max_page_text_chars: int = Field(
        default=100_000, ge=100, le=2_000_000, validation_alias="BRUD_DOCUMENT_MAX_PAGE_TEXT_CHARS"
    )
    document_max_total_text_chars: int = Field(
        default=5_000_000,
        ge=1000,
        le=50_000_000,
        validation_alias="BRUD_DOCUMENT_MAX_TOTAL_TEXT_CHARS",
    )
    pdf_max_images_per_page: int = Field(
        default=100, ge=0, le=1000, validation_alias="BRUD_PDF_MAX_IMAGES_PER_PAGE"
    )
    pdf_render_dpi: int = Field(default=150, ge=72, le=300, validation_alias="BRUD_PDF_RENDER_DPI")
    pdf_max_render_pixels: int = Field(
        default=25_000_000,
        ge=1_000_000,
        le=100_000_000,
        validation_alias="BRUD_PDF_MAX_RENDER_PIXELS",
    )
    ocr_enabled: bool = Field(default=True, validation_alias="BRUD_OCR_ENABLED")
    ocr_languages: str = Field(default="tam+eng", validation_alias="BRUD_OCR_LANGUAGES")
    ocr_page_timeout_seconds: int = Field(
        default=60, ge=1, le=600, validation_alias="BRUD_OCR_PAGE_TIMEOUT_SECONDS"
    )
    ocr_max_pages_per_job: int = Field(
        default=50, ge=1, le=300, validation_alias="BRUD_OCR_MAX_PAGES_PER_JOB"
    )
    ocr_min_text_length: int = Field(
        default=24, ge=0, le=10_000, validation_alias="BRUD_OCR_MIN_TEXT_LENGTH"
    )
    ocr_confidence_warning_threshold: float = Field(
        default=0.55, ge=0, le=1, validation_alias="BRUD_OCR_CONFIDENCE_WARNING_THRESHOLD"
    )
    document_segment_max_chars: int = Field(
        default=2000, ge=100, le=20_000, validation_alias="BRUD_DOCUMENT_SEGMENT_MAX_CHARS"
    )
    document_segment_overlap_chars: int = Field(
        default=150, ge=0, le=5000, validation_alias="BRUD_DOCUMENT_SEGMENT_OVERLAP_CHARS"
    )
    quality_ruleset_version: str = Field(
        default="phase6-v1", validation_alias="BRUD_QUALITY_RULESET_VERSION"
    )
    quality_ready_threshold: float = Field(
        default=0.80, ge=0, le=1, validation_alias="BRUD_QUALITY_READY_THRESHOLD"
    )
    quality_warning_threshold: float = Field(
        default=0.60, ge=0, le=1, validation_alias="BRUD_QUALITY_WARNING_THRESHOLD"
    )
    quality_min_pretrain_chars: int = Field(
        default=24, ge=1, le=10000, validation_alias="BRUD_QUALITY_MIN_PRETRAIN_CHARS"
    )
    quality_max_record_chars: int = Field(
        default=100_000, ge=100, le=2_000_000, validation_alias="BRUD_QUALITY_MAX_RECORD_CHARS"
    )
    quality_max_repetition_ratio: float = Field(
        default=0.40, ge=0, le=1, validation_alias="BRUD_QUALITY_MAX_REPETITION_RATIO"
    )
    quality_max_punctuation_ratio: float = Field(
        default=0.45, ge=0, le=1, validation_alias="BRUD_QUALITY_MAX_PUNCTUATION_RATIO"
    )
    quality_min_letter_ratio: float = Field(
        default=0.25, ge=0, le=1, validation_alias="BRUD_QUALITY_MIN_LETTER_RATIO"
    )
    quality_block_unknown_licence: bool = Field(
        default=False, validation_alias="BRUD_QUALITY_BLOCK_UNKNOWN_LICENCE"
    )
    quality_require_provenance: bool = Field(
        default=True, validation_alias="BRUD_QUALITY_REQUIRE_PROVENANCE"
    )
    dataset_default_train_percent: int = Field(
        default=90, ge=0, le=100, validation_alias="BRUD_DATASET_DEFAULT_TRAIN_PERCENT"
    )
    dataset_default_validation_percent: int = Field(
        default=5, ge=0, le=100, validation_alias="BRUD_DATASET_DEFAULT_VALIDATION_PERCENT"
    )
    dataset_default_test_percent: int = Field(
        default=5, ge=0, le=100, validation_alias="BRUD_DATASET_DEFAULT_TEST_PERCENT"
    )
    dataset_split_seed: int = Field(default=42, ge=0, validation_alias="BRUD_DATASET_SPLIT_SEED")
    dataset_export_dir: Path = Field(
        default=Path("data/dataset_exports"), validation_alias="BRUD_DATASET_EXPORT_DIR"
    )
    dataset_export_max_records: int = Field(
        default=100_000, ge=1, le=1_000_000, validation_alias="BRUD_DATASET_EXPORT_MAX_RECORDS"
    )
    tokenizer_dir: Path = Field(
        default=Path("data/tokenizers"),
        validation_alias="BRUD_TOKENIZER_DIR",
    )
    tokenizer_corpus_dir: Path = Field(
        default=Path("data/tokenizers/corpora"), validation_alias="BRUD_TOKENIZER_CORPUS_DIR"
    )
    tokenizer_export_dir: Path = Field(
        default=Path("data/tokenizers/exports"), validation_alias="BRUD_TOKENIZER_EXPORT_DIR"
    )
    tokenizer_default_algorithm: str = Field(
        default="bpe", validation_alias="BRUD_TOKENIZER_DEFAULT_ALGORITHM"
    )
    tokenizer_default_vocab_size: int = Field(
        default=16000, ge=1, le=100000, validation_alias="BRUD_TOKENIZER_DEFAULT_VOCAB_SIZE"
    )
    tokenizer_min_vocab_size: int = Field(
        default=1000, ge=1, le=100000, validation_alias="BRUD_TOKENIZER_MIN_VOCAB_SIZE"
    )
    tokenizer_max_vocab_size: int = Field(
        default=32000, ge=1, le=100000, validation_alias="BRUD_TOKENIZER_MAX_VOCAB_SIZE"
    )
    tokenizer_character_coverage: float = Field(
        default=0.9995, gt=0, le=1, validation_alias="BRUD_TOKENIZER_CHARACTER_COVERAGE"
    )
    tokenizer_max_corpus_records: int = Field(
        default=250_000, ge=1, le=1_000_000, validation_alias="BRUD_TOKENIZER_MAX_CORPUS_RECORDS"
    )
    tokenizer_max_corpus_chars: int = Field(
        default=250_000_000,
        ge=1000,
        le=1_000_000_000,
        validation_alias="BRUD_TOKENIZER_MAX_CORPUS_CHARS",
    )
    tokenizer_max_line_chars: int = Field(
        default=20_000, ge=100, le=200_000, validation_alias="BRUD_TOKENIZER_MAX_LINE_CHARS"
    )
    tokenizer_input_sentence_size: int = Field(
        default=500_000, ge=0, le=5_000_000, validation_alias="BRUD_TOKENIZER_INPUT_SENTENCE_SIZE"
    )
    tokenizer_shuffle_input_sentence: bool = Field(
        default=True, validation_alias="BRUD_TOKENIZER_SHUFFLE_INPUT_SENTENCE"
    )
    tokenizer_max_sentence_length: int = Field(
        default=4096, ge=128, le=20000, validation_alias="BRUD_TOKENIZER_MAX_SENTENCE_LENGTH"
    )
    tokenizer_num_threads: int = Field(
        default=1, ge=1, le=4, validation_alias="BRUD_TOKENIZER_NUM_THREADS"
    )
    tokenizer_eval_max_samples_per_language: int = Field(
        default=1000,
        ge=1,
        le=10000,
        validation_alias="BRUD_TOKENIZER_EVAL_MAX_SAMPLES_PER_LANGUAGE",
    )
    tokenizer_min_ready_score: float = Field(
        default=0.8, ge=0, le=1, validation_alias="BRUD_TOKENIZER_MIN_READY_SCORE"
    )
    core_model_dir: Path = Field(
        default=Path("data/core_models"), validation_alias="BRUD_CORE_MODEL_DIR"
    )
    core_checkpoint_dir: Path = Field(
        default=Path("data/core_models/checkpoints"),
        validation_alias="BRUD_CORE_CHECKPOINT_DIR",
    )
    core_max_parameters: int = Field(
        default=30_000_000, ge=1, le=500_000_000, validation_alias="BRUD_CORE_MAX_PARAMETERS"
    )
    core_max_context_length: int = Field(
        default=1024, ge=8, le=8192, validation_alias="BRUD_CORE_MAX_CONTEXT_LENGTH"
    )
    core_max_hidden_size: int = Field(
        default=512, ge=8, le=4096, validation_alias="BRUD_CORE_MAX_HIDDEN_SIZE"
    )
    core_max_layers: int = Field(
        default=12, ge=1, le=96, validation_alias="BRUD_CORE_MAX_LAYERS"
    )
    core_max_attention_heads: int = Field(
        default=16, ge=1, le=64, validation_alias="BRUD_CORE_MAX_ATTENTION_HEADS"
    )
    core_max_intermediate_size: int = Field(
        default=2048, ge=16, le=16384, validation_alias="BRUD_CORE_MAX_INTERMEDIATE_SIZE"
    )
    core_max_estimated_memory_bytes: int = Field(
        default=3_000_000_000,
        ge=100_000,
        le=64_000_000_000,
        validation_alias="BRUD_CORE_MAX_ESTIMATED_MEMORY_BYTES",
    )
    core_default_dtype: str = Field(default="float32", validation_alias="BRUD_CORE_DEFAULT_DTYPE")
    core_default_device: str = Field(default="cpu", validation_alias="BRUD_CORE_DEFAULT_DEVICE")
    core_checkpoint_max_bytes: int = Field(
        default=500_000_000,
        ge=1024,
        le=5_000_000_000,
        validation_alias="BRUD_CORE_CHECKPOINT_MAX_BYTES",
    )
    core_smoke_max_steps: int = Field(
        default=100, ge=1, le=1000, validation_alias="BRUD_CORE_SMOKE_MAX_STEPS"
    )
    core_smoke_max_batch_size: int = Field(
        default=2, ge=1, le=16, validation_alias="BRUD_CORE_SMOKE_MAX_BATCH_SIZE"
    )
    core_smoke_max_sequence_length: int = Field(
        default=256, ge=2, le=2048, validation_alias="BRUD_CORE_SMOKE_MAX_SEQUENCE_LENGTH"
    )
    pretraining_dir: Path = Field(
        default=Path("data/core_models/pretraining"), validation_alias="BRUD_PRETRAINING_DIR"
    )
    pretraining_max_steps: int = Field(
        default=5000, ge=1, le=100_000, validation_alias="BRUD_PRETRAINING_MAX_STEPS"
    )
    pretraining_max_tokens: int = Field(
        default=2_000_000, ge=1, le=100_000_000, validation_alias="BRUD_PRETRAINING_MAX_TOKENS"
    )
    pretraining_max_batch_size: int = Field(
        default=2, ge=1, le=16, validation_alias="BRUD_PRETRAINING_MAX_BATCH_SIZE"
    )
    pretraining_max_gradient_accumulation: int = Field(
        default=16, ge=1, le=128, validation_alias="BRUD_PRETRAINING_MAX_GRADIENT_ACCUMULATION"
    )
    pretraining_max_sequence_length: int = Field(
        default=512, ge=8, le=4096, validation_alias="BRUD_PRETRAINING_MAX_SEQUENCE_LENGTH"
    )
    pretraining_max_checkpoints: int = Field(
        default=10, ge=1, le=100, validation_alias="BRUD_PRETRAINING_MAX_CHECKPOINTS"
    )
    pretraining_min_checkpoint_interval: int = Field(
        default=1, ge=1, le=10_000, validation_alias="BRUD_PRETRAINING_MIN_CHECKPOINT_INTERVAL"
    )
    pretraining_max_estimated_memory_bytes: int = Field(
        default=3_500_000_000,
        ge=100_000,
        le=64_000_000_000,
        validation_alias="BRUD_PRETRAINING_MAX_ESTIMATED_MEMORY_BYTES",
    )
    pretraining_min_free_disk_bytes: int = Field(
        default=100_000_000, ge=0, validation_alias="BRUD_PRETRAINING_MIN_FREE_DISK_BYTES"
    )
    pretraining_min_available_memory_bytes: int = Field(
        default=250_000_000, ge=0, validation_alias="BRUD_PRETRAINING_MIN_AVAILABLE_MEMORY_BYTES"
    )
    pretraining_worker_poll_seconds: int = Field(
        default=2, ge=1, le=300, validation_alias="BRUD_PRETRAINING_WORKER_POLL_SECONDS"
    )
    pretraining_worker_lease_seconds: int = Field(
        default=120, ge=10, le=3600, validation_alias="BRUD_PRETRAINING_WORKER_LEASE_SECONDS"
    )
    pretraining_metric_interval_steps: int = Field(
        default=1, ge=1, le=1000, validation_alias="BRUD_PRETRAINING_METRIC_INTERVAL_STEPS"
    )
    pretraining_validation_max_batches: int = Field(
        default=10, ge=1, le=1000, validation_alias="BRUD_PRETRAINING_VALIDATION_MAX_BATCHES"
    )
    pretraining_nan_failure: bool = Field(
        default=True, validation_alias="BRUD_PRETRAINING_NAN_FAILURE"
    )
    pretraining_default_port: int = Field(
        default=8019, ge=1, le=65535, validation_alias="BRUD_PRETRAINING_DEFAULT_PORT"
    )
    pretraining_keep_periodic: int = Field(
        default=3, ge=0, le=100, validation_alias="BRUD_PRETRAINING_KEEP_PERIODIC"
    )
    pretraining_keep_best: int = Field(
        default=1, ge=0, le=10, validation_alias="BRUD_PRETRAINING_KEEP_BEST"
    )
    pretraining_keep_final: int = Field(
        default=1, ge=0, le=10, validation_alias="BRUD_PRETRAINING_KEEP_FINAL"
    )
    pretraining_keep_pause: int = Field(
        default=1, ge=0, le=10, validation_alias="BRUD_PRETRAINING_KEEP_PAUSE"
    )
    pretraining_retention_dry_run: bool = Field(
        default=True, validation_alias="BRUD_PRETRAINING_RETENTION_DRY_RUN"
    )
    training_quality_ruleset_version: str = Field(
        default="phase10-v1", validation_alias="BRUD_TRAINING_QUALITY_RULESET_VERSION"
    )
    training_min_processed_tokens: int = Field(
        default=8, ge=0, validation_alias="BRUD_TRAINING_MIN_PROCESSED_TOKENS"
    )
    training_min_loss_improvement_ratio: float = Field(
        default=0.0, ge=0, le=1, validation_alias="BRUD_TRAINING_MIN_LOSS_IMPROVEMENT_RATIO"
    )
    training_max_train_validation_gap: float = Field(
        default=5.0, ge=0, validation_alias="BRUD_TRAINING_MAX_TRAIN_VALIDATION_GAP"
    )
    training_max_excluded_record_ratio: float = Field(
        default=0.5, ge=0, le=1, validation_alias="BRUD_TRAINING_MAX_EXCLUDED_RECORD_RATIO"
    )
    training_min_validation_tokens: int = Field(
        default=4, ge=0, validation_alias="BRUD_TRAINING_MIN_VALIDATION_TOKENS"
    )
    training_require_validation: bool = Field(
        default=True, validation_alias="BRUD_TRAINING_REQUIRE_VALIDATION"
    )
    training_require_resume_check_if_resumed: bool = Field(
        default=True, validation_alias="BRUD_TRAINING_REQUIRE_RESUME_CHECK_IF_RESUMED"
    )
    training_max_non_finite_events: int = Field(
        default=0, ge=0, validation_alias="BRUD_TRAINING_MAX_NON_FINITE_EVENTS"
    )
    training_require_all_checkpoints_verified: bool = Field(
        default=True, validation_alias="BRUD_TRAINING_REQUIRE_ALL_CHECKPOINTS_VERIFIED"
    )
    training_min_coverage_ratio: float = Field(
        default=0.5, ge=0, le=1, validation_alias="BRUD_TRAINING_MIN_COVERAGE_RATIO"
    )
    base_training_min_records: int = Field(
        default=500, ge=1, validation_alias="BRUD_BASE_TRAINING_MIN_RECORDS"
    )
    base_training_min_tamil_ratio: float = Field(
        default=0.30, ge=0, le=1, validation_alias="BRUD_BASE_TRAINING_MIN_TAMIL_RATIO"
    )
    base_training_min_english_ratio: float = Field(
        default=0.05, ge=0, le=1, validation_alias="BRUD_BASE_TRAINING_MIN_ENGLISH_RATIO"
    )
    base_training_min_tanglish_ratio: float = Field(
        default=0.05, ge=0, le=1, validation_alias="BRUD_BASE_TRAINING_MIN_TANGLISH_RATIO"
    )
    base_training_max_duplicate_ratio: float = Field(
        default=0.15, ge=0, le=1, validation_alias="BRUD_BASE_TRAINING_MAX_DUPLICATE_RATIO"
    )
    base_training_min_validation_records: int = Field(
        default=20, ge=1, validation_alias="BRUD_BASE_TRAINING_MIN_VALIDATION_RECORDS"
    )
    base_training_min_test_records: int = Field(
        default=20, ge=1, validation_alias="BRUD_BASE_TRAINING_MIN_TEST_RECORDS"
    )
    base_training_min_token_budget: int = Field(
        default=50_000, ge=1, validation_alias="BRUD_BASE_TRAINING_MIN_TOKEN_BUDGET"
    )
    base_training_max_token_budget: int = Field(
        default=500_000, ge=1, validation_alias="BRUD_BASE_TRAINING_MAX_TOKEN_BUDGET"
    )
    base_training_generalization_max_gap: float = Field(
        default=3.0, ge=0, validation_alias="BRUD_BASE_TRAINING_GENERALIZATION_MAX_GAP"
    )
    base_training_memorization_max_gap: float = Field(
        default=4.0, ge=0, validation_alias="BRUD_BASE_TRAINING_MEMORIZATION_MAX_GAP"
    )
    base_training_tokenizer_max_unknown_rate: float = Field(
        default=0.05, ge=0, le=1, validation_alias="BRUD_BASE_TRAINING_TOKENIZER_MAX_UNKNOWN_RATE"
    )
    base_training_tokenizer_min_round_trip: float = Field(
        default=0.95, ge=0, le=1, validation_alias="BRUD_BASE_TRAINING_TOKENIZER_MIN_ROUND_TRIP"
    )
    instruction_tuning_min_records: int = Field(
        default=1000, ge=1, validation_alias="BRUD_INSTRUCTION_TUNING_MIN_RECORDS"
    )
    instruction_tuning_limited_experiment_floor: int = Field(
        default=200, ge=1, validation_alias="BRUD_INSTRUCTION_TUNING_LIMITED_EXPERIMENT_FLOOR"
    )
    instruction_tuning_min_validation_records: int = Field(
        default=10, ge=1, validation_alias="BRUD_INSTRUCTION_TUNING_MIN_VALIDATION_RECORDS"
    )
    instruction_tuning_min_test_records: int = Field(
        default=10, ge=1, validation_alias="BRUD_INSTRUCTION_TUNING_MIN_TEST_RECORDS"
    )
    instruction_tuning_max_role_leakage_rate: float = Field(
        default=0.0, ge=0, le=1, validation_alias="BRUD_INSTRUCTION_TUNING_MAX_ROLE_LEAKAGE_RATE"
    )
    instruction_tuning_max_prompt_leakage_rate: float = Field(
        default=0.1, ge=0, le=1, validation_alias="BRUD_INSTRUCTION_TUNING_MAX_PROMPT_LEAKAGE_RATE"
    )
    instruction_tuning_max_repetition_rate: float = Field(
        default=0.2, ge=0, le=1, validation_alias="BRUD_INSTRUCTION_TUNING_MAX_REPETITION_RATE"
    )
    instruction_tuning_max_exact_match_rate: float = Field(
        default=0.2, ge=0, le=1, validation_alias="BRUD_INSTRUCTION_TUNING_MAX_EXACT_MATCH_RATE"
    )
    instruction_tuning_max_duplicate_output_rate: float = Field(
        default=0.3, ge=0, le=1,
        validation_alias="BRUD_INSTRUCTION_TUNING_MAX_DUPLICATE_OUTPUT_RATE",
    )
    instruction_tuning_max_longest_span_ratio: float = Field(
        default=0.8, ge=0, le=1, validation_alias="BRUD_INSTRUCTION_TUNING_MAX_LONGEST_SPAN_RATIO"
    )
    instruction_tuning_max_train_validation_gap: float = Field(
        default=4.0, ge=0, validation_alias="BRUD_INSTRUCTION_TUNING_MAX_TRAIN_VALIDATION_GAP"
    )
    instruction_tuning_generation_max_new_tokens: int = Field(
        default=32, ge=1, le=256,
        validation_alias="BRUD_INSTRUCTION_TUNING_GENERATION_MAX_NEW_TOKENS",
    )
    instruction_tuning_generation_timeout_seconds: float = Field(
        default=5.0, ge=0.1, le=60.0,
        validation_alias="BRUD_INSTRUCTION_TUNING_GENERATION_TIMEOUT_SECONDS",
    )
    eval_min_total_fixtures: int = Field(
        default=50, ge=1, validation_alias="BRUD_EVAL_MIN_TOTAL_FIXTURES"
    )
    eval_preferred_total_fixtures: int = Field(
        default=325, ge=1, validation_alias="BRUD_EVAL_PREFERRED_TOTAL_FIXTURES"
    )
    eval_min_tamil_fixtures: int = Field(
        default=100, ge=0, validation_alias="BRUD_EVAL_MIN_TAMIL_FIXTURES"
    )
    eval_min_english_fixtures: int = Field(
        default=50, ge=0, validation_alias="BRUD_EVAL_MIN_ENGLISH_FIXTURES"
    )
    eval_min_tanglish_fixtures: int = Field(
        default=50, ge=0, validation_alias="BRUD_EVAL_MIN_TANGLISH_FIXTURES"
    )
    eval_min_mixed_fixtures: int = Field(
        default=50, ge=0, validation_alias="BRUD_EVAL_MIN_MIXED_FIXTURES"
    )
    eval_min_safety_fixtures: int = Field(
        default=50, ge=0, validation_alias="BRUD_EVAL_MIN_SAFETY_FIXTURES"
    )
    eval_min_robustness_fixtures: int = Field(
        default=25, ge=0, validation_alias="BRUD_EVAL_MIN_ROBUSTNESS_FIXTURES"
    )
    eval_max_prompt_chars: int = Field(
        default=2000, ge=1, le=20000, validation_alias="BRUD_EVAL_MAX_PROMPT_CHARS"
    )
    eval_max_reference_chars: int = Field(
        default=4000, ge=1, le=40000, validation_alias="BRUD_EVAL_MAX_REFERENCE_CHARS"
    )
    eval_max_new_tokens_ceiling: int = Field(
        default=128, ge=1, le=256, validation_alias="BRUD_EVAL_MAX_NEW_TOKENS_CEILING"
    )
    eval_generation_timeout_seconds: float = Field(
        default=5.0, ge=0.1, le=60.0, validation_alias="BRUD_EVAL_GENERATION_TIMEOUT_SECONDS"
    )
    eval_min_instruction_following_score: float = Field(
        default=0.6, ge=0, le=1, validation_alias="BRUD_EVAL_MIN_INSTRUCTION_FOLLOWING_SCORE"
    )
    eval_min_language_compliance_score: float = Field(
        default=0.6, ge=0, le=1, validation_alias="BRUD_EVAL_MIN_LANGUAGE_COMPLIANCE_SCORE"
    )
    eval_min_surface_relevance_score: float = Field(
        default=0.5, ge=0, le=1, validation_alias="BRUD_EVAL_MIN_SURFACE_RELEVANCE_SCORE"
    )
    eval_max_unsupported_claim_rate: float = Field(
        default=0.4, ge=0, le=1, validation_alias="BRUD_EVAL_MAX_UNSUPPORTED_CLAIM_RATE"
    )
    eval_max_over_refusal_rate: float = Field(
        default=0.4, ge=0, le=1, validation_alias="BRUD_EVAL_MAX_OVER_REFUSAL_RATE"
    )
    eval_max_prompt_leakage_rate: float = Field(
        default=0.1, ge=0, le=1, validation_alias="BRUD_EVAL_MAX_PROMPT_LEAKAGE_RATE"
    )
    eval_max_duplicate_output_rate: float = Field(
        default=0.5, ge=0, le=1, validation_alias="BRUD_EVAL_MAX_DUPLICATE_OUTPUT_RATE"
    )
    eval_min_unicode_integrity_rate: float = Field(
        default=0.95, ge=0, le=1, validation_alias="BRUD_EVAL_MIN_UNICODE_INTEGRITY_RATE"
    )
    eval_min_human_review_coverage: float = Field(
        default=0.5, ge=0, le=1, validation_alias="BRUD_EVAL_MIN_HUMAN_REVIEW_COVERAGE"
    )
    eval_max_human_review_disagreement: float = Field(
        default=0.5, ge=0, le=1, validation_alias="BRUD_EVAL_MAX_HUMAN_REVIEW_DISAGREEMENT"
    )
    release_artifact_dir: Path = Field(
        default=Path("data/release_artifacts"), validation_alias="BRUD_RELEASE_ARTIFACT_DIR"
    )
    release_bundle_dir: Path = Field(
        default=Path("data/release_bundles"), validation_alias="BRUD_RELEASE_BUNDLE_DIR"
    )
    release_require_evaluation: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_REQUIRE_EVALUATION"
    )
    release_allow_warning_eligibility: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_ALLOW_WARNING_ELIGIBILITY"
    )
    release_required_approval_roles: str = Field(
        default="release", validation_alias="BRUD_RELEASE_REQUIRED_APPROVAL_ROLES"
    )
    release_allow_self_approval: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_ALLOW_SELF_APPROVAL"
    )
    release_require_rollback_target: bool = Field(
        default=False, validation_alias="BRUD_RELEASE_REQUIRE_ROLLBACK_TARGET"
    )
    release_max_artifact_size_bytes: int = Field(
        default=2_000_000_000, ge=1, validation_alias="BRUD_RELEASE_MAX_ARTIFACT_SIZE_BYTES"
    )
    release_max_bundle_size_bytes: int = Field(
        default=2_000_000_000, ge=1, validation_alias="BRUD_RELEASE_MAX_BUNDLE_SIZE_BYTES"
    )
    release_allowed_artifact_roots: str = Field(
        default="core_models/pretraining,tokenizers,release_artifacts",
        validation_alias="BRUD_RELEASE_ALLOWED_ARTIFACT_ROOTS",
    )
    release_allowed_bundle_formats: str = Field(
        default="zip", validation_alias="BRUD_RELEASE_ALLOWED_BUNDLE_FORMATS"
    )
    release_require_licence: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_REQUIRE_LICENCE"
    )
    release_require_model_card: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_REQUIRE_MODEL_CARD"
    )
    release_require_evaluation_manifest: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_REQUIRE_EVALUATION_MANIFEST"
    )
    release_require_instruction_manifest: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_REQUIRE_INSTRUCTION_MANIFEST"
    )
    release_require_base_training_manifest: bool = Field(
        default=True, validation_alias="BRUD_RELEASE_REQUIRE_BASE_TRAINING_MANIFEST"
    )
    release_checksum_algorithm: str = Field(
        default="sha256", validation_alias="BRUD_RELEASE_CHECKSUM_ALGORITHM"
    )
    inference_runtime_enabled: bool = Field(
        default=True, validation_alias="BRUD_INFERENCE_RUNTIME_ENABLED"
    )
    public_chat_model_enabled: bool = Field(
        default=False, validation_alias="BRUD_PUBLIC_CHAT_MODEL_ENABLED"
    )
    inference_max_loaded_models: int = Field(
        default=1, ge=1, validation_alias="BRUD_INFERENCE_MAX_LOADED_MODELS"
    )
    inference_max_concurrent_requests: int = Field(
        default=1, ge=1, validation_alias="BRUD_INFERENCE_MAX_CONCURRENT_REQUESTS"
    )
    inference_max_context_length: int = Field(
        default=512, ge=8, validation_alias="BRUD_INFERENCE_MAX_CONTEXT_LENGTH"
    )
    inference_max_new_tokens: int = Field(
        default=128, ge=1, validation_alias="BRUD_INFERENCE_MAX_NEW_TOKENS"
    )
    inference_request_timeout_seconds: int = Field(
        default=30, ge=1, validation_alias="BRUD_INFERENCE_REQUEST_TIMEOUT_SECONDS"
    )
    inference_idle_unload_seconds: int = Field(
        default=900, ge=1, validation_alias="BRUD_INFERENCE_IDLE_UNLOAD_SECONDS"
    )
    inference_min_available_memory_bytes: int = Field(
        default=500_000_000, ge=0, validation_alias="BRUD_INFERENCE_MIN_AVAILABLE_MEMORY_BYTES"
    )
    inference_min_available_disk_bytes: int = Field(
        default=500_000_000, ge=0, validation_alias="BRUD_INFERENCE_MIN_AVAILABLE_DISK_BYTES"
    )
    inference_memory_safety_multiplier: float = Field(
        default=1.5, gt=0, validation_alias="BRUD_INFERENCE_MEMORY_SAFETY_MULTIPLIER"
    )
    inference_allow_warning_releases: bool = Field(
        default=True, validation_alias="BRUD_INFERENCE_ALLOW_WARNING_RELEASES"
    )
    inference_allow_registry_fixture_diagnostics: bool = Field(
        default=False, validation_alias="BRUD_INFERENCE_ALLOW_REGISTRY_FIXTURE_DIAGNOSTICS"
    )
    inference_require_canary: bool = Field(
        default=True, validation_alias="BRUD_INFERENCE_REQUIRE_CANARY"
    )
    inference_require_rollback_target: bool = Field(
        default=True, validation_alias="BRUD_INFERENCE_REQUIRE_ROLLBACK_TARGET"
    )
    inference_canary_max_requests: int = Field(
        default=30, ge=1, validation_alias="BRUD_INFERENCE_CANARY_MAX_REQUESTS"
    )
    inference_canary_max_failure_rate: float = Field(
        default=0.2, ge=0, le=1, validation_alias="BRUD_INFERENCE_CANARY_MAX_FAILURE_RATE"
    )
    inference_canary_max_timeout_rate: float = Field(
        default=0.2, ge=0, le=1, validation_alias="BRUD_INFERENCE_CANARY_MAX_TIMEOUT_RATE"
    )
    inference_canary_max_role_leakage_rate: float = Field(
        default=0.0, ge=0, le=1, validation_alias="BRUD_INFERENCE_CANARY_MAX_ROLE_LEAKAGE_RATE"
    )
    inference_canary_max_prompt_leakage_rate: float = Field(
        default=0.0, ge=0, le=1, validation_alias="BRUD_INFERENCE_CANARY_MAX_PROMPT_LEAKAGE_RATE"
    )
    inference_canary_max_duplicate_rate: float = Field(
        default=0.5, ge=0, le=1, validation_alias="BRUD_INFERENCE_CANARY_MAX_DUPLICATE_RATE"
    )
    inference_required_public_approval_roles: str = Field(
        default="technical,evaluation,security,release",
        validation_alias="BRUD_INFERENCE_REQUIRED_PUBLIC_APPROVAL_ROLES",
    )
    rag_enabled: bool = Field(default=True, validation_alias="BRUD_RAG_ENABLED")
    rag_max_source_characters: int = Field(
        default=2_000_000, ge=1, validation_alias="BRUD_RAG_MAX_SOURCE_CHARACTERS"
    )
    rag_target_chunk_tokens: int = Field(
        default=350, ge=20, validation_alias="BRUD_RAG_TARGET_CHUNK_TOKENS"
    )
    rag_max_chunk_tokens: int = Field(
        default=500, ge=20, validation_alias="BRUD_RAG_MAX_CHUNK_TOKENS"
    )
    rag_chunk_overlap_tokens: int = Field(
        default=50, ge=0, validation_alias="BRUD_RAG_CHUNK_OVERLAP_TOKENS"
    )
    rag_min_chunk_characters: int = Field(
        default=40, ge=1, validation_alias="BRUD_RAG_MIN_CHUNK_CHARACTERS"
    )
    rag_max_chunks_per_source: int = Field(
        default=2000, ge=1, validation_alias="BRUD_RAG_MAX_CHUNKS_PER_SOURCE"
    )
    rag_embedding_batch_size: int = Field(
        default=16, ge=1, validation_alias="BRUD_RAG_EMBEDDING_BATCH_SIZE"
    )
    rag_max_active_embedding_runs: int = Field(
        default=1, ge=1, validation_alias="BRUD_RAG_MAX_ACTIVE_EMBEDDING_RUNS"
    )
    rag_max_vector_results: int = Field(
        default=20, ge=1, validation_alias="BRUD_RAG_MAX_VECTOR_RESULTS"
    )
    rag_max_keyword_results: int = Field(
        default=20, ge=1, validation_alias="BRUD_RAG_MAX_KEYWORD_RESULTS"
    )
    rag_max_final_results: int = Field(
        default=5, ge=1, validation_alias="BRUD_RAG_MAX_FINAL_RESULTS"
    )
    rag_default_vector_weight: float = Field(
        default=0.6, ge=0, le=1, validation_alias="BRUD_RAG_DEFAULT_VECTOR_WEIGHT"
    )
    rag_default_keyword_weight: float = Field(
        default=0.4, ge=0, le=1, validation_alias="BRUD_RAG_DEFAULT_KEYWORD_WEIGHT"
    )
    rag_min_retrieval_score: float = Field(
        default=0.15, ge=0, le=1, validation_alias="BRUD_RAG_MIN_RETRIEVAL_SCORE"
    )
    rag_context_token_budget: int = Field(
        default=800, ge=50, validation_alias="BRUD_RAG_CONTEXT_TOKEN_BUDGET"
    )
    rag_max_citations: int = Field(
        default=5, ge=1, validation_alias="BRUD_RAG_MAX_CITATIONS"
    )
    rag_no_answer_threshold: float = Field(
        default=0.2, ge=0, le=1, validation_alias="BRUD_RAG_NO_ANSWER_THRESHOLD"
    )
    rag_block_injection_risk: bool = Field(
        default=True, validation_alias="BRUD_RAG_BLOCK_INJECTION_RISK"
    )
    rag_allow_warning_chunks: bool = Field(
        default=False, validation_alias="BRUD_RAG_ALLOW_WARNING_CHUNKS"
    )
    rag_max_active_sessions: int = Field(
        default=5, ge=1, validation_alias="BRUD_RAG_MAX_ACTIVE_SESSIONS"
    )
    rag_max_session_turns: int = Field(
        default=10, ge=1, validation_alias="BRUD_RAG_MAX_SESSION_TURNS"
    )
    rag_session_ttl_seconds: int = Field(
        default=3600, ge=60, validation_alias="BRUD_RAG_SESSION_TTL_SECONDS"
    )
    rag_require_approved_sources: bool = Field(
        default=True, validation_alias="BRUD_RAG_REQUIRE_APPROVED_SOURCES"
    )
    rag_allowed_index_roots: str = Field(
        default="rag_indexes", validation_alias="BRUD_RAG_ALLOWED_INDEX_ROOTS"
    )

    memory_enabled: bool = Field(default=True, validation_alias="BRUD_MEMORY_ENABLED")
    memory_default_session_mode: str = Field(
        default="private_no_persist", validation_alias="BRUD_MEMORY_DEFAULT_SESSION_MODE"
    )
    memory_max_session_turns: int = Field(
        default=20, ge=1, validation_alias="BRUD_MEMORY_MAX_SESSION_TURNS"
    )
    memory_max_session_age_seconds: int = Field(
        default=3600, ge=60, validation_alias="BRUD_MEMORY_MAX_SESSION_AGE_SECONDS"
    )
    memory_max_turn_characters: int = Field(
        default=4000, ge=100, validation_alias="BRUD_MEMORY_MAX_TURN_CHARACTERS"
    )
    memory_max_short_term_tokens: int = Field(
        default=800, ge=50, validation_alias="BRUD_MEMORY_MAX_SHORT_TERM_TOKENS"
    )
    memory_max_summary_tokens: int = Field(
        default=200, ge=20, validation_alias="BRUD_MEMORY_MAX_SUMMARY_TOKENS"
    )
    memory_max_long_term_items: int = Field(
        default=50, ge=1, validation_alias="BRUD_MEMORY_MAX_LONG_TERM_ITEMS"
    )
    memory_default_ttl_seconds: int = Field(
        default=7_776_000, ge=60, validation_alias="BRUD_MEMORY_DEFAULT_TTL_SECONDS"
    )
    memory_max_retrieval_results: int = Field(
        default=5, ge=1, validation_alias="BRUD_MEMORY_MAX_RETRIEVAL_RESULTS"
    )
    memory_max_context_tokens: int = Field(
        default=200, ge=20, validation_alias="BRUD_MEMORY_MAX_CONTEXT_TOKENS"
    )
    memory_require_explicit_consent: bool = Field(
        default=True, validation_alias="BRUD_MEMORY_REQUIRE_EXPLICIT_CONSENT"
    )
    memory_allow_assistant_proposals: bool = Field(
        default=True, validation_alias="BRUD_MEMORY_ALLOW_ASSISTANT_PROPOSALS"
    )
    memory_auto_activate_user_confirmed: bool = Field(
        default=False, validation_alias="BRUD_MEMORY_AUTO_ACTIVATE_USER_CONFIRMED"
    )
    memory_block_sensitive_content: bool = Field(
        default=True, validation_alias="BRUD_MEMORY_BLOCK_SENSITIVE_CONTENT"
    )
    memory_private_session_retention_seconds: int = Field(
        default=0, ge=0, validation_alias="BRUD_MEMORY_PRIVATE_SESSION_RETENTION_SECONDS"
    )
    memory_max_active_sessions: int = Field(
        default=5, ge=1, validation_alias="BRUD_MEMORY_MAX_ACTIVE_SESSIONS"
    )
    memory_max_active_evaluation_runs: int = Field(
        default=1, ge=1, validation_alias="BRUD_MEMORY_MAX_ACTIVE_EVALUATION_RUNS"
    )
    memory_allowed_categories: str = Field(
        default=(
            "language_preference,format_preference,confirmed_name_or_alias,learning_goal,"
            "course_progress,project_preference,user_confirmed_fact,conversation_follow_up"
        ),
        validation_alias="BRUD_MEMORY_ALLOWED_CATEGORIES",
    )
    memory_forbidden_categories: str = Field(
        default=(
            "password,api_key,access_token,private_key,payment_card,bank_account,"
            "authentication_cookie,precise_location,medical_diagnosis,political_affiliation,"
            "religion,sexual_information,criminal_record,biometric_data"
        ),
        validation_alias="BRUD_MEMORY_FORBIDDEN_CATEGORIES",
    )
    memory_require_deletion_cache_invalidation: bool = Field(
        default=True, validation_alias="BRUD_MEMORY_REQUIRE_DELETION_CACHE_INVALIDATION"
    )

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("BRUD_LOG_LEVEL must be a standard Python log level")
        return level

    @field_validator("chatbot_origin", "admin_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        if value == "*" or "*" in value:
            raise ValueError("wildcard CORS origins are not allowed")
        parsed = AnyHttpUrl(value)
        return str(parsed).rstrip("/")

    @model_validator(mode="after")
    def validate_storage_paths(self) -> "Settings":
        if self.database_path.exists() and self.database_path.is_dir():
            raise ValueError("BRUD_DATABASE_PATH must identify a file, not a directory")
        for field_name in (
            "database_backup_dir",
            "allowed_data_dir",
            "allowed_model_dir",
            "allowed_export_dir",
            "import_dir",
            "import_report_dir",
            "document_dir",
            "document_report_dir",
            "dataset_export_dir",
            "tokenizer_dir",
            "tokenizer_corpus_dir",
            "tokenizer_export_dir",
            "core_model_dir",
            "core_checkpoint_dir",
            "pretraining_dir",
            "release_artifact_dir",
            "release_bundle_dir",
        ):
            resolved = self._resolve_path(getattr(self, field_name))
            if not self.allow_external_storage and not resolved.is_relative_to(PROJECT_ROOT):
                raise ValueError(f"{field_name} must remain inside the Brud AI project root")
        if not self.allow_external_storage:
            data_root = self._resolve_path(self.allowed_data_dir)
            for field_name in (
                "import_dir",
                "import_report_dir",
                "document_dir",
                "document_report_dir",
                "dataset_export_dir",
                "tokenizer_dir",
                "tokenizer_corpus_dir",
                "tokenizer_export_dir",
                "core_model_dir",
                "core_checkpoint_dir",
                "pretraining_dir",
                "release_artifact_dir",
                "release_bundle_dir",
            ):
                if not self._resolve_path(getattr(self, field_name)).is_relative_to(data_root):
                    raise ValueError(f"{field_name} must remain inside BRUD_ALLOWED_DATA_DIR")
        if self.document_segment_overlap_chars >= self.document_segment_max_chars:
            raise ValueError("document segment overlap must be smaller than segment size")
        if self.quality_ready_threshold < self.quality_warning_threshold:
            raise ValueError("ready quality threshold must be greater than warning threshold")
        split_total = (
            self.dataset_default_train_percent
            + self.dataset_default_validation_percent
            + self.dataset_default_test_percent
        )
        if split_total != 100:
            raise ValueError("dataset split percentages must total 100")
        if self.tokenizer_default_algorithm not in {"bpe", "unigram"}:
            raise ValueError("tokenizer default algorithm must be bpe or unigram")
        if self.tokenizer_min_vocab_size > self.tokenizer_max_vocab_size:
            raise ValueError("tokenizer min vocab size must not exceed max vocab size")
        if not (
            self.tokenizer_min_vocab_size
            <= self.tokenizer_default_vocab_size
            <= self.tokenizer_max_vocab_size
        ):
            raise ValueError("tokenizer default vocab size must be inside configured bounds")
        if self.core_default_dtype != "float32":
            raise ValueError("Phase 8 supports only float32 core model dtype")
        if self.core_default_device != "cpu":
            raise ValueError("Phase 8 supports only cpu as the default core model device")
        if self.pretraining_min_checkpoint_interval > self.pretraining_max_steps:
            raise ValueError("pretraining checkpoint interval must not exceed max steps")
        if self.release_checksum_algorithm not in {"sha256"}:
            raise ValueError("Phase 14 supports only the sha256 checksum algorithm")
        allowed_formats = {
            item.strip() for item in self.release_allowed_bundle_formats.split(",") if item.strip()
        }
        if not allowed_formats or not allowed_formats <= {"zip", "tar_gz"}:
            raise ValueError("BRUD_RELEASE_ALLOWED_BUNDLE_FORMATS supports only zip and tar_gz")
        if self.inference_max_new_tokens > self.inference_max_context_length:
            raise ValueError(
                "BRUD_INFERENCE_MAX_NEW_TOKENS must not exceed BRUD_INFERENCE_MAX_CONTEXT_LENGTH"
            )
        return self

    @field_validator("ocr_languages")
    @classmethod
    def validate_ocr_languages(cls, value: str) -> str:
        languages = [item.strip() for item in value.split("+") if item.strip()]
        if not languages or not set(languages) <= {"tam", "eng"}:
            raise ValueError("BRUD_OCR_LANGUAGES supports only tam and eng")
        return "+".join(dict.fromkeys(languages))

    @field_validator("import_default_encoding")
    @classmethod
    def validate_import_encoding(cls, value: str) -> str:
        if value.lower() not in {"utf-8", "utf-8-sig"}:
            raise ValueError("BRUD_IMPORT_DEFAULT_ENCODING must be utf-8 or utf-8-sig")
        return value.lower()

    @field_validator("import_allowed_extensions")
    @classmethod
    def validate_import_extensions(cls, value: str) -> str:
        items = {item.strip().lower() for item in value.split(",") if item.strip()}
        if not items or not items <= {".json", ".jsonl", ".csv", ".txt"}:
            raise ValueError("import extensions must use the supported allowlist")
        return ",".join(sorted(items))

    @field_validator("import_allowed_mime_types")
    @classmethod
    def validate_import_mimes(cls, value: str) -> str:
        items = {item.strip().lower() for item in value.split(",") if item.strip()}
        if not items or any("*" in item for item in items):
            raise ValueError("wildcard or empty import MIME allowlists are not allowed")
        return ",".join(sorted(items))

    @staticmethod
    def _resolve_path(path: Path) -> Path:
        candidate = path if path.is_absolute() else PROJECT_ROOT / path
        return candidate.resolve()

    @property
    def resolved_database_path(self) -> Path:
        """Return an absolute database path without requiring a fixed launch directory."""

        return self._resolve_path(self.database_path)

    @property
    def resolved_backup_dir(self) -> Path:
        return self._resolve_path(self.database_backup_dir)

    @property
    def resolved_allowed_data_dir(self) -> Path:
        return self._resolve_path(self.allowed_data_dir)

    @property
    def resolved_allowed_model_dir(self) -> Path:
        return self._resolve_path(self.allowed_model_dir)

    @property
    def resolved_import_dir(self) -> Path:
        return self._resolve_path(self.import_dir)

    @property
    def resolved_import_report_dir(self) -> Path:
        return self._resolve_path(self.import_report_dir)

    @property
    def resolved_document_dir(self) -> Path:
        return self._resolve_path(self.document_dir)

    @property
    def resolved_document_report_dir(self) -> Path:
        return self._resolve_path(self.document_report_dir)

    @property
    def resolved_dataset_export_dir(self) -> Path:
        return self._resolve_path(self.dataset_export_dir)

    @property
    def resolved_tokenizer_dir(self) -> Path:
        return self._resolve_path(self.tokenizer_dir)

    @property
    def resolved_tokenizer_corpus_dir(self) -> Path:
        return self._resolve_path(self.tokenizer_corpus_dir)

    @property
    def resolved_tokenizer_export_dir(self) -> Path:
        return self._resolve_path(self.tokenizer_export_dir)

    @property
    def resolved_core_model_dir(self) -> Path:
        return self._resolve_path(self.core_model_dir)

    @property
    def resolved_core_checkpoint_dir(self) -> Path:
        return self._resolve_path(self.core_checkpoint_dir)

    @property
    def resolved_pretraining_dir(self) -> Path:
        return self._resolve_path(self.pretraining_dir)

    @property
    def resolved_release_artifact_dir(self) -> Path:
        return self._resolve_path(self.release_artifact_dir)

    @property
    def resolved_release_bundle_dir(self) -> Path:
        return self._resolve_path(self.release_bundle_dir)

    @property
    def release_required_approval_roles_list(self) -> tuple[str, ...]:
        return tuple(
            role.strip() for role in self.release_required_approval_roles.split(",") if role.strip()
        )

    @property
    def release_allowed_artifact_roots_list(self) -> tuple[str, ...]:
        return tuple(
            root.strip()
            for root in self.release_allowed_artifact_roots.split(",")
            if root.strip()
        )

    @property
    def rag_allowed_index_roots_list(self) -> tuple[str, ...]:
        return tuple(
            root.strip() for root in self.rag_allowed_index_roots.split(",") if root.strip()
        )

    @property
    def memory_allowed_categories_list(self) -> tuple[str, ...]:
        return tuple(
            item.strip() for item in self.memory_allowed_categories.split(",") if item.strip()
        )

    @property
    def memory_forbidden_categories_list(self) -> tuple[str, ...]:
        return tuple(
            item.strip() for item in self.memory_forbidden_categories.split(",") if item.strip()
        )

    @property
    def inference_required_public_approval_roles_list(self) -> tuple[str, ...]:
        return tuple(
            role.strip()
            for role in self.inference_required_public_approval_roles.split(",")
            if role.strip()
        )

    @property
    def allowed_import_extensions(self) -> set[str]:
        return set(self.import_allowed_extensions.split(","))

    @property
    def allowed_import_mime_types(self) -> set[str]:
        return set(self.import_allowed_mime_types.split(","))

    @property
    def resolved_allowed_export_dir(self) -> Path:
        return self._resolve_path(self.allowed_export_dir)

    @property
    def cors_origins(self) -> list[str]:
        return [self.chatbot_origin, self.admin_origin]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    try:
        return Settings()
    except PydanticValidationError as exc:
        logger.error("configuration_validation_failure", extra={"error_count": exc.error_count()})
        audit_path = PROJECT_ROOT / "data/database/brud_ai.db"
        if audit_path.is_file():
            try:
                with sqlite3.connect(audit_path) as connection:
                    columns = {
                        row[1] for row in connection.execute("PRAGMA table_info(audit_logs)")
                    }
                    if "public_id" in columns:
                        connection.execute(
                            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,
                            actor_type,outcome,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                            (
                                "configuration_validation_failure",
                                "system",
                                "{}",
                                str(uuid4()),
                                "configuration_validation_failure",
                                "system",
                                "failure",
                                f'{{"error_count":{exc.error_count()}}}',
                            ),
                        )
            except sqlite3.Error:
                logger.exception("configuration_failure_audit_write_failed")
        raise
