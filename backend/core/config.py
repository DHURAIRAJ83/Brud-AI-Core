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
        ):
            resolved = self._resolve_path(getattr(self, field_name))
            if not self.allow_external_storage and not resolved.is_relative_to(PROJECT_ROOT):
                raise ValueError(f"{field_name} must remain inside the Brud AI project root")
        return self

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
