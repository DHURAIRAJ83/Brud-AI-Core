"""MB-19: Benchmark Export Manifest builder -- pure. Assembles the
manifest listing every export artifact file this evaluation session
produced. Reuses `core_model.release.manifest.scan_for_sensitive_
content()` directly -- the same real, already-tested scanner the
Release Pipeline and MB-18's own Training Pipeline use for their own
manifests, never a second implementation.

Like MB-18's own `package_manifest_builder.py`, this manifest is
never self-listed in its own `artifacts`/`artifact_count` -- the
database's `mini_brain_benchmark_results`-adjacent export-file table
is the authoritative complete file list.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import scan_for_sensitive_content

MANIFEST_VERSION = 1


def build_export_manifest(
    *, session_public_id: str, topic: str, overall_score: float | None, release_readiness_status: str,
    artifact_entries: list[dict[str, Any]], created_at: str,
) -> dict[str, Any]:
    manifest = {
        "manifest_version": MANIFEST_VERSION, "session_public_id": session_public_id, "topic": topic,
        "overall_score": overall_score, "release_readiness_status": release_readiness_status,
        "artifacts": [
            {
                "artifact_name": entry["artifact_name"], "relative_path": entry["relative_path"],
                "sha256": entry["sha256"], "file_size_bytes": entry["file_size_bytes"],
            }
            for entry in artifact_entries
        ],
        "artifact_count": len(artifact_entries), "created_at": created_at,
        "model_weights_included": False, "training_performed": False, "model_inference_performed": False,
        "note": (
            "this manifest is not self-listed above -- the database's mini_brain_evaluation_sessions "
            "export table is the authoritative complete file list (artifact_count + 1 once this file "
            "is written)"
        ),
    }
    warnings = scan_for_sensitive_content(manifest)
    manifest["sensitive_content_warnings"] = warnings
    return manifest
