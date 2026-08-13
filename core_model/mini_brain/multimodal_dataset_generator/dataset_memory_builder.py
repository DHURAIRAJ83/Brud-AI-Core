"""MB-16: Dataset Memory -- pure. Assembles the permanent rollup
record a future phase (MB-17/18/19/20) can reuse: dataset version,
generation time, every linked source session, total records, and a
provider-information summary drawn from MB-15's own already-selected
provider (when a Vision Model session is linked). Never a new
measurement -- every field is already-known data.
"""

from __future__ import annotations

from typing import Any


def build_dataset_memory(
    *, generated_at: str, source_document_public_id: str, source_dataset_public_id: str | None,
    source_language_session_public_id: str | None, source_vision_session_public_id: str | None,
    source_vision_model_session_public_id: str | None, total_records: int,
    correction_history: list[dict[str, Any]], learning_memory: list[dict[str, Any]],
    provider_key: str | None,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "source_document_public_id": source_document_public_id,
        "source_dataset_public_id": source_dataset_public_id,
        "source_language_session_public_id": source_language_session_public_id,
        "source_vision_session_public_id": source_vision_session_public_id,
        "source_vision_model_session_public_id": source_vision_model_session_public_id,
        "total_records": total_records,
        "correction_history": correction_history,
        "learning_memory": learning_memory,
        "provider_information": {"provider_key": provider_key} if provider_key else {},
    }
