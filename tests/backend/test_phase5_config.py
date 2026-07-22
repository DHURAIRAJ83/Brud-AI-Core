from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.config import Settings


def test_document_configuration_defaults_and_bounds(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "db.sqlite",
        allowed_data_dir=tmp_path,
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True,
    )
    assert settings.document_max_file_bytes == 25 * 1024 * 1024
    assert settings.document_max_pages == 300
    assert settings.ocr_languages == "tam+eng"


@pytest.mark.parametrize(
    "values",
    [
        {"document_max_pages": 0},
        {"pdf_render_dpi": 500},
        {"ocr_languages": "tam+fra"},
        {"document_segment_max_chars": 100, "document_segment_overlap_chars": 100},
    ],
)
def test_invalid_document_configuration_rejected(tmp_path: Path, values: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_path=tmp_path / "db.sqlite",
            allowed_data_dir=tmp_path,
            document_dir=tmp_path / "documents",
            document_report_dir=tmp_path / "documents" / "reports",
            allow_external_storage=True,
            **values,
        )
