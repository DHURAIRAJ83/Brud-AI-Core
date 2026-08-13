"""MB-21: Reproducibility Hasher -- pure. Reuses `core_model.release.
manifest.manifest_checksum()` directly -- the same real SHA-256-over-
canonical-JSON checksum function the Release Pipeline and MB-18/19/20
all already use, never a second hashing implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import manifest_checksum


def build_reproducibility_record(
    *, gateway_report: dict[str, Any], sanitized_prompt_hash: str | None,
    source_dataset_public_ids: list[str], source_rag_session_public_id: str | None,
) -> dict[str, Any]:
    report_hash = manifest_checksum(gateway_report)
    inputs_hash = manifest_checksum({
        "sanitized_prompt_hash": sanitized_prompt_hash,
        "source_dataset_public_ids": sorted(source_dataset_public_ids),
        "source_rag_session_public_id": source_rag_session_public_id,
    })
    return {
        "report_checksum_sha256": report_hash, "input_set_checksum_sha256": inputs_hash,
        "disclosure": (
            "the same sanitized-prompt hash and source public_id set will always reproduce this "
            "identical input_set_checksum_sha256 -- provider responses themselves are never "
            "deterministic across runs, so only the inputs are checked for reproducibility, never the "
            "provider output"
        ),
    }
