"""Environment-backed application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("BRUD_LOG_LEVEL must be a standard Python log level")
        return level

    @property
    def resolved_database_path(self) -> Path:
        """Return an absolute database path without requiring a fixed launch directory."""

        if self.database_path.is_absolute():
            return self.database_path
        return PROJECT_ROOT / self.database_path

    @property
    def cors_origins(self) -> list[str]:
        return [self.chatbot_origin, self.admin_origin]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
