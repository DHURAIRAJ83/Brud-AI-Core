"""MB-19: Package Integrity Benchmark -- pure. Scores pre-computed,
already-verified per-package facts (real SHA-256 comparisons and file-
existence checks the service layer performed against disk) -- this
module itself never touches the filesystem, matching the
core_model/backend split every other Mini Brain phase follows.
"""

from __future__ import annotations

from typing import Any


def run_package_integrity_benchmark(*, package_checks: list[dict[str, Any]]) -> dict[str, Any]:
    """`package_checks`: one entry per evaluated MB-18 package, each
    ``{"session_public_id": str, "manifest_checksum_valid": bool | None,
    "artifact_count_consistent": bool, "missing_or_corrupt_file_count": int}``,
    already computed by the service layer via real file reads."""
    if not package_checks:
        return {
            "package_count": 0, "manifest_checksum_validity_rate": None,
            "artifact_count_consistency_rate": None, "missing_file_count": 0,
            "disclosure": "no MB-18 training package was supplied -- package integrity is honestly unavailable",
        }

    total = len(package_checks)
    checksum_checked = [p for p in package_checks if p["manifest_checksum_valid"] is not None]
    checksum_valid_count = sum(1 for p in checksum_checked if p["manifest_checksum_valid"])
    count_consistent_count = sum(1 for p in package_checks if p["artifact_count_consistent"])
    total_missing = sum(p["missing_or_corrupt_file_count"] for p in package_checks)

    return {
        "package_count": total,
        "manifest_checksum_validity_rate": (
            round(checksum_valid_count / len(checksum_checked), 3) if checksum_checked else None
        ),
        "artifact_count_consistency_rate": round(count_consistent_count / total, 3),
        "missing_file_count": total_missing,
        "per_package": package_checks,
        "disclosure": (
            "every checksum and file-existence check was performed by the service layer against real "
            "files on disk before this module ever ran -- this module only scores those already-"
            "verified facts, it never reads a file itself"
        ),
    }
