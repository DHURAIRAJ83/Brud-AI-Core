from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.config import Settings
from backend.core.json_utils import JsonValidationError, dumps_json


def test_invalid_timeout_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(database_busy_timeout_ms=-1)


def test_database_directory_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must identify a file"):
        Settings(database_path=tmp_path)


def test_wildcard_cors_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(chatbot_origin="*")


def test_metadata_size_and_depth_are_bounded() -> None:
    with pytest.raises(JsonValidationError, match="exceeds"):
        dumps_json({"large": "x" * 100}, max_bytes=20)
    nested = {
        "level": {
            "level": {"level": {"level": {"level": {"level": {"level": {"level": {"level": {}}}}}}}}
        }
    }
    with pytest.raises(JsonValidationError, match="depth"):
        dumps_json(nested)


def test_allowed_directories_must_remain_in_project(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="inside the Brud AI project"):
        Settings(allowed_data_dir=tmp_path)
