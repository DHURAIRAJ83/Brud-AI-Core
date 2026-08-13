"""MB-07: Integrity Validation -- pure. Confirms the produced GGUF file
itself (not the source checkpoint -- that's the Checkpoint Validator's
job) is complete and internally consistent: it exists, its size and
checksum were actually computed, its tensor count matches the export
plan, and its vocabulary size matches the tokenizer it was built with.
"""

from __future__ import annotations

from typing import Any


def validate_integrity(
    *,
    file_exists: bool,
    file_size_bytes: int,
    checksum_sha256: str | None,
    expected_tensor_count: int,
    actual_tensor_count: int | None,
    vocabulary_size_expected: int,
    vocabulary_size_in_file: int | None,
    architecture_in_file: str | None,
    expected_architecture: str,
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    checks["file_exists"] = file_exists
    if not file_exists:
        reasons.append("GGUF file does not exist on disk")

    checks["file_size_positive"] = file_size_bytes > 0
    if file_size_bytes <= 0:
        reasons.append("GGUF file is empty")

    checks["checksum_computed"] = checksum_sha256 is not None and len(checksum_sha256) == 64
    if not checks["checksum_computed"]:
        reasons.append("SHA-256 checksum could not be computed")

    checks["tensor_count_matches"] = actual_tensor_count == expected_tensor_count
    if actual_tensor_count != expected_tensor_count:
        reasons.append(
            f"tensor count mismatch: expected {expected_tensor_count}, found {actual_tensor_count}"
        )

    checks["vocabulary_size_matches"] = vocabulary_size_in_file == vocabulary_size_expected
    if vocabulary_size_in_file != vocabulary_size_expected:
        reasons.append(
            f"vocabulary size mismatch: expected {vocabulary_size_expected}, "
            f"found {vocabulary_size_in_file}"
        )

    checks["architecture_matches"] = architecture_in_file == expected_architecture
    if architecture_in_file != expected_architecture:
        reasons.append(
            f"architecture mismatch: expected {expected_architecture!r}, found {architecture_in_file!r}"
        )

    valid = all(checks.values())
    return {
        "status": "Valid" if valid else "Invalid",
        "checks": checks,
        "reasons": reasons,
        "file_size_bytes": file_size_bytes,
        "checksum_sha256": checksum_sha256,
    }
