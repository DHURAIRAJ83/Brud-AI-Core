"""MB-07: Release Report Generator -- pure assembly only. Merges
already-computed stage reports into the single structured document
Stage 11 hands to the admin. Never recomputes anything; every field
here is a direct pass-through of an earlier stage's own real output.
"""

from __future__ import annotations

from typing import Any


def generate_release_report(
    *,
    session_public_id: str,
    checkpoint_validation_report: dict[str, Any] | None,
    conversion_report: dict[str, Any] | None,
    quantization_report: dict[str, Any] | None,
    integrity_report: dict[str, Any] | None,
    compatibility_report: dict[str, Any] | None,
    performance_report: dict[str, Any] | None,
    version_string: str | None,
    model_release_public_id: str | None,
) -> dict[str, Any]:
    sections_present = {
        "checkpoint_validation_report": checkpoint_validation_report is not None,
        "conversion_report": conversion_report is not None,
        "quantization_report": quantization_report is not None,
        "integrity_report": integrity_report is not None,
        "compatibility_report": compatibility_report is not None,
        "performance_report": performance_report is not None,
    }

    blocking_reasons: list[str] = []
    if checkpoint_validation_report and checkpoint_validation_report.get("status") == "Invalid":
        blocking_reasons.extend(checkpoint_validation_report.get("reasons", []))
    if integrity_report and integrity_report.get("status") == "Invalid":
        blocking_reasons.extend(integrity_report.get("reasons", []))
    if compatibility_report and compatibility_report.get("status") == "Incompatible":
        blocking_reasons.append("produced GGUF file failed compatibility validation")

    return {
        "session_public_id": session_public_id,
        "sections_present": sections_present,
        "checkpoint_validation_report": checkpoint_validation_report,
        "conversion_report": conversion_report,
        "quantization_report": quantization_report,
        "integrity_report": integrity_report,
        "compatibility_report": compatibility_report,
        "performance_report": performance_report,
        "version_string": version_string,
        "model_release_public_id": model_release_public_id,
        "has_blocking_findings": bool(blocking_reasons),
        "blocking_reasons": blocking_reasons,
        "ready_for_admin_review": not blocking_reasons,
    }
