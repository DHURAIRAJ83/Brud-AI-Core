from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)
