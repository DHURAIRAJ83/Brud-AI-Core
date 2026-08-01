from backend.services.dataset_sample_security_scan_service import (
    ExternalDatasetSecurityScanService,
)

VALIDATION_SAFE = {"status": "safe_for_scan", "extension": ".txt", "detected_mime": "text/plain"}


def _service() -> ExternalDatasetSecurityScanService:
    return ExternalDatasetSecurityScanService()


def test_clean_text_content_is_clean_by_policy() -> None:
    result = _service().scan_file(
        b"hello world, this is a normal training example",
        original_filename="note.txt",
        file_validation_result=VALIDATION_SAFE,
    )
    assert result["verdict"] == "clean_by_policy"
    assert result["matched_signals"] == []


def test_already_blocked_file_validation_result_carries_forward() -> None:
    result = _service().scan_file(
        b"MZ\x90\x00",
        original_filename="innocuous.txt",
        file_validation_result={"status": "blocked", "blocked_class": "executable"},
    )
    assert result["verdict"] == "blocked"
    assert "executable" in result["matched_signals"]


def test_html_script_tag_is_suspicious() -> None:
    result = _service().scan_file(
        b'some text <script>alert(1)</script> more text',
        original_filename="note.txt",
        file_validation_result=VALIDATION_SAFE,
    )
    assert result["verdict"] == "suspicious"
    assert "html_script_tag" in result["matched_signals"]


def test_csv_formula_injection_is_suspicious() -> None:
    result = _service().scan_file(
        b"name,amount\nJohn,=cmd|'/c calc'!A1\n",
        original_filename="data.csv",
        file_validation_result={"status": "safe_for_scan", "extension": ".csv"},
    )
    assert result["verdict"] == "suspicious"
    assert "csv_formula_injection" in result["matched_signals"]


def test_notebook_code_cell_in_json_is_flagged() -> None:
    content = b'{"cells": [{"cell_type": "code", "source": ["import os"]}]}'
    result = _service().scan_file(
        content, original_filename="data.json",
        file_validation_result={"status": "safe_for_scan", "extension": ".json"},
    )
    assert "notebook_code_cell" in result["matched_signals"]


def test_pickle_signature_is_blocked() -> None:
    result = _service().scan_file(
        b"\x80\x04\x95\x00\x00\x00\x00\x00\x00\x00\x00",
        original_filename="data.json",
        file_validation_result={"status": "safe_for_scan", "extension": ".json"},
    )
    assert result["verdict"] == "blocked"
    assert "pickle_or_joblib_signature" in result["matched_signals"]


def test_pdf_with_javascript_marker_is_blocked() -> None:
    content = b"%PDF-1.4\n/JavaScript (app.alert('hi'))\n"
    result = _service().scan_file(
        content, original_filename="doc.pdf",
        file_validation_result={"status": "safe_for_scan", "extension": ".pdf"},
    )
    assert result["verdict"] == "blocked"
    assert "pdf_embedded_executable_object" in result["matched_signals"]


def test_rtlo_filename_trick_is_suspicious() -> None:
    result = _service().scan_file(
        b"hello",
        original_filename="invoice‮gnp.exe",
        file_validation_result={"status": "safe_for_scan", "extension": ".exe"},
    )
    assert result["verdict"] == "suspicious"
    assert "malicious_filename_pattern" in result["matched_signals"]


def test_polyglot_mismatch_csv_with_zip_signature() -> None:
    result = _service().scan_file(
        b"PK\x03\x04" + b"\x00" * 20,
        original_filename="data.csv",
        file_validation_result={"status": "safe_for_scan", "extension": ".csv"},
    )
    assert "polyglot_mismatch" in result["matched_signals"]


def test_binary_content_in_declared_text_file_is_flagged() -> None:
    result = _service().scan_file(
        bytes(range(256)) * 4,
        original_filename="data.txt",
        file_validation_result={"status": "safe_for_scan", "extension": ".txt"},
    )
    assert "binary_content_in_text_file" in result["matched_signals"]


def test_shell_command_text_content_is_never_flagged() -> None:
    # A record merely *describing* or *quoting* a shell command in its
    # own text content is inert data, not an executable script file --
    # this must never trigger a security-scan signal.
    content = b"name,instruction\nexample,Run `rm -rf /tmp/cache` to clear the cache\n"
    result = _service().scan_file(
        content, original_filename="examples.csv",
        file_validation_result={"status": "safe_for_scan", "extension": ".csv"},
    )
    assert result["verdict"] == "clean_by_policy"
    assert result["matched_signals"] == []


def test_suspicious_archive_contents_flagged_via_rejected_reasons() -> None:
    result = _service().scan_file(
        b"placeholder",
        original_filename="bundle.zip",
        file_validation_result={"status": "safe_for_scan", "extension": ".zip", "is_archive": True},
        archive_rejected_reasons=["symlink", "duplicate_path"],
    )
    assert result["verdict"] == "suspicious"
    assert "suspicious_archive_contents" in result["matched_signals"]


def test_clean_by_policy_never_used_when_signals_matched() -> None:
    result = _service().scan_file(
        b'<script>x</script>', original_filename="note.txt", file_validation_result=VALIDATION_SAFE
    )
    assert result["matched_signals"]
    assert result["verdict"] != "clean_by_policy"
