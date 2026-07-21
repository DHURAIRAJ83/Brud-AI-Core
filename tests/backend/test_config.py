from pathlib import Path

from backend.core.config import Settings


def test_configuration_loading(monkeypatch, tmp_path: Path) -> None:
    database_path = tmp_path / "configured.db"
    monkeypatch.setenv("BRUD_ENV", "test")
    monkeypatch.setenv("BRUD_PORT", "8123")
    monkeypatch.setenv("BRUD_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("BRUD_DEBUG", "true")
    settings = Settings(_env_file=None)
    assert settings.env == "test"
    assert settings.port == 8123
    assert settings.resolved_database_path == database_path
    assert settings.debug is True
    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:5174"]
