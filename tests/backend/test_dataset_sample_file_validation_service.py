import hashlib
import os
from pathlib import Path

import pytest

from backend.services.dataset_sample_file_validation_service import (
    ExternalDatasetFileValidationService,
)


@pytest.fixture
def service() -> ExternalDatasetFileValidationService:
    return ExternalDatasetFileValidationService()


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_plain_text_file_is_safe_for_scan(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "note.txt", b"hello world")
    result = service.validate_file(path, original_filename="note.txt")
    assert result["status"] == "safe_for_scan"
    assert result["detected_mime"] == "text/plain"
    assert result["encoding"] == "utf-8"


def test_pdf_signature_is_safe_for_scan(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "doc.pdf", b"%PDF-1.4\n...")
    result = service.validate_file(path, original_filename="doc.pdf")
    assert result["status"] == "safe_for_scan"
    assert result["detected_mime"] == "application/pdf"


def test_zip_archive_is_safe_for_scan_and_flagged_as_archive(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "bundle.zip", b"PK\x03\x04" + b"\x00" * 20)
    result = service.validate_file(path, original_filename="bundle.zip")
    assert result["status"] == "safe_for_scan"
    assert result["is_archive"] is True
    assert result["archive_format"] == "zip"


def test_windows_executable_signature_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "innocuous.txt", b"MZ" + b"\x90" * 30)
    result = service.validate_file(path, original_filename="innocuous.txt")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "executable"


def test_elf_executable_signature_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "binary", b"\x7fELF" + b"\x00" * 30)
    result = service.validate_file(path, original_filename="binary")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "executable"


def test_shell_script_extension_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "run.sh", b"#!/bin/bash\necho hi\n")
    result = service.validate_file(path, original_filename="run.sh")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "shell_script"


def test_shebang_alone_without_sh_extension_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "data.txt", b"#!/usr/bin/env python\nprint('hi')\n")
    result = service.validate_file(path, original_filename="data.txt")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "shell_script"


def test_powershell_extension_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "run.ps1", b"Write-Host hi")
    result = service.validate_file(path, original_filename="run.ps1")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "powershell_script"


def test_java_archive_extension_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "app.jar", b"PK\x03\x04" + b"\x00" * 20)
    result = service.validate_file(path, original_filename="app.jar")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "java_archive"


def test_model_weight_extension_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "weights.safetensors", b"\x00" * 40)
    result = service.validate_file(path, original_filename="weights.safetensors")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "model_weight_file"


def test_ole_signature_is_blocked_as_macro_document(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "legacy.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 20)
    result = service.validate_file(path, original_filename="legacy.doc")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "macro_document"


def test_oversized_file_is_flagged(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "big.txt", b"x" * 1000)
    result = service.validate_file(path, original_filename="big.txt", max_bytes=100)
    assert result["status"] == "oversized"


def test_checksum_mismatch_is_flagged_as_corrupt(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "note.txt", b"hello")
    wrong_checksum = hashlib.sha256(b"different content").hexdigest()
    result = service.validate_file(
        path, original_filename="note.txt", expected_checksum=wrong_checksum
    )
    assert result["status"] == "corrupt"


def test_unknown_binary_content_is_blocked(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "mystery.dat", bytes(range(256)) * 4)
    result = service.validate_file(path, original_filename="mystery.dat")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "unknown_binary_blob"


def test_unsupported_text_like_extension_is_unsupported(tmp_path: Path, service) -> None:
    path = _write(tmp_path, "config.xml", b"<config></config>")
    result = service.validate_file(path, original_filename="config.xml")
    assert result["status"] == "unsupported"


def test_device_special_file_is_blocked(tmp_path: Path, service) -> None:
    fifo_path = tmp_path / "pipe"
    os.mkfifo(fifo_path)
    result = service.validate_file(fifo_path, original_filename="pipe")
    assert result["status"] == "blocked"
    assert result["blocked_class"] == "device_file"


def test_malformed_unicode_text_file_flags_encoding_warning(tmp_path: Path, service) -> None:
    path = tmp_path / "broken.txt"
    path.write_bytes(b"hello \xff\xfe world")
    result = service.validate_file(path, original_filename="broken.txt")
    assert result["status"] == "safe_for_scan"
    assert result["encoding"] == "utf-8-with-replacement"
    assert "encoding_not_valid_utf8" in result["warnings"]
