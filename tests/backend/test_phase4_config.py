from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.config import Settings


def test_import_defaults_are_bounded_and_inside_data_storage() -> None:
    settings = Settings()
    assert settings.import_max_file_bytes == 10 * 1024 * 1024
    assert settings.import_max_rows == 25_000
    assert settings.import_max_columns == 50
    assert settings.import_max_cell_chars == 20_000
    assert settings.import_preview_ttl_minutes == 60
    assert settings.resolved_import_dir.is_relative_to(settings.resolved_allowed_data_dir)
    assert settings.allowed_import_extensions == {".json", ".jsonl", ".csv", ".txt"}


@pytest.mark.parametrize(
    "override",
    [
        {"import_max_file_bytes": -1},
        {"import_max_rows": 0},
        {"import_max_columns": 0},
        {"import_max_cell_chars": 0},
        {"import_allowed_mime_types": "*/*"},
        {"import_allowed_extensions": ".json,.exe"},
        {"import_default_encoding": "latin-1"},
    ],
)
def test_invalid_import_configuration_is_rejected(override) -> None:
    with pytest.raises(ValidationError):
        Settings(**override)


def test_external_import_storage_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(import_dir=Path("/tmp/outside-brud-imports"))
    with pytest.raises(ValidationError):
        Settings(import_dir=Path("models/not-approved-import-storage"))
