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
