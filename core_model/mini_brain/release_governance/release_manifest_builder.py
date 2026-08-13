"""MB-20: Release Manifest builder -- pure. Assembles the manifest
listing every release artifact file this session produced. Reuses
`core_model.release.manifest.scan_for_sensitive_content()` directly --
the same real, already-tested scanner the Release Pipeline, MB-18's
Training Pipeline, and MB-19's Evaluation Center all use for their own
manifests, never a second implementation.

Like MB-18/19's own manifest builders, this manifest is never self-
listed in its own `artifacts`/`artifact_count` -- the database's
`mini_brain_release_governance_artifacts` table is the authoritative
complete file list.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import scan_for_sensitive_content

MANIFEST_VERSION = 1


def build_release_manifest(
    *, session_public_id: str, topic: str, source_dataset_public_ids: list[str],
    source_rag_session_public_ids: list[str], source_training_package_public_id: str | None,
    source_evaluation_session_public_id: str | None, release_recommendation: str,
    artifact_entries: list[dict[str, Any]], created_at: str,
) -> dict[str, Any]:
    manifest = {
        "manifest_version": MANIFEST_VERSION, "session_public_id": session_public_id, "topic": topic,
        "source_dataset_public_ids": source_dataset_public_ids,
        "source_rag_session_public_ids": source_rag_session_public_ids,
        "source_training_package_public_id": source_training_package_public_id,
        "source_evaluation_session_public_id": source_evaluation_session_public_id,
        "release_recommendation": release_recommendation,
        "artifacts": [
            {
                "artifact_name": entry["artifact_name"], "relative_path": entry["relative_path"],
                "sha256": entry["sha256"], "file_size_bytes": entry["file_size_bytes"],
            }
            for entry in artifact_entries
        ],
        "artifact_count": len(artifact_entries), "created_at": created_at,
        "model_weights_included": False, "deployment_performed": False, "runtime_activated": False,
        "note": (
            "this manifest is not self-listed above -- the database's "
            "mini_brain_release_governance_artifacts table is the authoritative complete file list "
            "(artifact_count + 1 once this file is written)"
        ),
    }
    warnings = scan_for_sensitive_content(manifest)
    manifest["sensitive_content_warnings"] = warnings
    return manifest
