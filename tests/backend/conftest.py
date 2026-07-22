from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.api.auth import AdminContext, require_admin
from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app
from backend.models.auth import AdminPublic, SessionPublic


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


@pytest.fixture
def protected_api_app(api_app: FastAPI) -> FastAPI:
    async def authenticated_admin() -> AdminContext:
        now = datetime.now(UTC)
        return AdminContext(
            admin=AdminPublic(
                public_id="00000000-0000-0000-0000-000000000001",
                username="test-admin",
                display_name="Test Admin",
            ),
            session=SessionPublic(expires_at=now + timedelta(hours=1), last_used_at=now),
            session_id=1,
            token="test-token",
        )

    api_app.dependency_overrides[require_admin] = authenticated_admin
    return api_app
