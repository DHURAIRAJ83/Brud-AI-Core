"""P4-A & P4-B: Production readiness, health probes, configuration & lifecycle tests."""

from pathlib import Path
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    db_path = tmp_path / "test_p4.db"
    backup_dir = tmp_path / "backups"
    settings = Settings(
        database_path=db_path,
        database_backup_dir=backup_dir,
        allowed_data_dir=tmp_path,
        allowed_model_dir=tmp_path / "models",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def test_app(test_settings: Settings) -> FastAPI:
    return create_app(test_settings)


async def test_root_and_api_health_probes(test_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp_root = await client.get("/health")
        assert resp_root.status_code == 200
        data_root = resp_root.json()
        assert data_root["status"] == "healthy"
        assert data_root["database"] == "connected"

        resp_api = await client.get("/api/health")
        assert resp_api.status_code == 200
        data_api = resp_api.json()
        assert data_api["status"] == "healthy"
        assert data_api["database"] == "connected"


async def test_root_and_api_ready_probes(test_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp_root = await client.get("/ready")
        assert resp_root.status_code == 200
        assert resp_root.json()["status"] == "ready"
        assert resp_root.json()["database"] == "connected"

        resp_api = await client.get("/api/ready")
        assert resp_api.status_code == 200
        assert resp_api.json()["status"] == "ready"
        assert resp_api.json()["database"] == "connected"


async def test_ready_probe_returns_503_when_db_unavailable(tmp_path: Path) -> None:
    # Point settings to a non-existent unwritable directory
    broken_settings = Settings(
        database_path=tmp_path / "nonexistent_dir" / "cannot_open.db",
        allowed_data_dir=tmp_path,
        allowed_model_dir=tmp_path / "models",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    app = create_app(broken_settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["detail"]["status"] == "not_ready"
        assert data["detail"]["database"] == "unavailable"


async def test_root_and_api_status_probes(test_app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp_root = await client.get("/status")
        assert resp_root.status_code == 200
        data_root = resp_root.json()
        assert data_root["status"] == "operational"
        assert data_root["database"] == "connected"
        assert "version" in data_root
        assert "environment" in data_root

        resp_api = await client.get("/api/status")
        assert resp_api.status_code == 200
        data_api = resp_api.json()
        assert data_api["status"] == "operational"


async def test_production_configuration_enforcement(tmp_path: Path) -> None:
    # 1. Production with debug=True must fail validation
    with pytest.raises(ValidationError) as exc:
        Settings(
            env="production",
            debug=True,
            admin_cookie_secure=True,
            trust_proxy_headers=True,
            allow_external_storage=False,
            database_path=tmp_path / "prod.db",
        )
    assert "BRUD_DEBUG must be False in production" in str(exc.value)

    # 2. Production without admin_cookie_secure must fail validation
    with pytest.raises(ValidationError) as exc:
        Settings(
            env="production",
            debug=False,
            admin_cookie_secure=False,
            trust_proxy_headers=True,
            allow_external_storage=False,
            database_path=tmp_path / "prod.db",
        )
    assert "BRUD_ADMIN_COOKIE_SECURE must be True in production" in str(exc.value)

    # 3. Production with allow_external_storage=True must fail validation
    with pytest.raises(ValidationError) as exc:
        Settings(
            env="production",
            debug=False,
            admin_cookie_secure=True,
            trust_proxy_headers=True,
            allow_external_storage=True,
            database_path=tmp_path / "prod.db",
        )
    assert "BRUD_ALLOW_EXTERNAL_STORAGE must be False in production" in str(exc.value)

    # 4. Production without trust_proxy_headers must fail validation
    with pytest.raises(ValidationError) as exc:
        Settings(
            env="production",
            debug=False,
            admin_cookie_secure=True,
            trust_proxy_headers=False,
            allow_external_storage=False,
            database_path=tmp_path / "prod.db",
        )
    assert "BRUD_TRUST_PROXY_HEADERS must be True in production" in str(exc.value)

    # 5. Valid production configuration must succeed
    prod_valid = Settings(
        env="production",
        debug=False,
        admin_cookie_secure=True,
        trust_proxy_headers=True,
        allow_external_storage=False,
        database_path=tmp_path / "prod.db",
    )
    assert prod_valid.env == "production"
    assert prod_valid.debug is False
    assert prod_valid.admin_cookie_secure is True
    assert prod_valid.trust_proxy_headers is True
