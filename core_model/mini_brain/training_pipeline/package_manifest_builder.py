"""MB-18: Package Manifest builder -- pure. Assembles the manifest
listing every analysis artifact file this session produced. Reuses
`core_model.release.manifest.scan_for_sensitive_content()` directly to
defensively check the assembled manifest for absolute paths or secret-
shaped values before it is ever written to disk -- the same real,
already-tested scanner the Release Pipeline uses for its own
manifests, never a second implementation.

`manifest.json` and `reproducibility.json` are deliberately never
self-listed in `artifacts`/`artifact_count`: `reproducibility.json`'s
own content is a checksum *of* this manifest, and `manifest.json`
cannot checksum itself before it is written -- both are still tracked
as real rows in `mini_brain_training_packages` (the database, not this
JSON content, is the authoritative complete file list), disclosed
explicitly below rather than silently under-counted.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import scan_for_sensitive_content

MANIFEST_VERSION = 1


def build_package_manifest(
    *, session_public_id: str, topic: str, source_dataset_public_ids: list[str],
    source_rag_memory_public_ids: list[str], artifact_entries: list[dict[str, Any]], created_at: str,
) -> dict[str, Any]:
    manifest = {
        "manifest_version": MANIFEST_VERSION, "session_public_id": session_public_id, "topic": topic,
        "source_dataset_public_ids": source_dataset_public_ids,
        "source_rag_memory_public_ids": source_rag_memory_public_ids,
        "artifacts": [
            {
                "artifact_name": entry["artifact_name"], "relative_path": entry["relative_path"],
                "sha256": entry["sha256"], "file_size_bytes": entry["file_size_bytes"],
            }
            for entry in artifact_entries
        ],
        "artifact_count": len(artifact_entries), "created_at": created_at,
        "model_weights_included": False, "training_executed": False,
        "note": (
            "this manifest and reproducibility.json are not self-listed above -- the database's "
            "mini_brain_training_packages table is the authoritative complete file list (artifact_count "
            "+ 2 once both are written)"
        ),
    }
    warnings = scan_for_sensitive_content(manifest)
    manifest["sensitive_content_warnings"] = warnings
    return manifest
