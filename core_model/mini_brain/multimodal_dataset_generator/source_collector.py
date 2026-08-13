"""MB-16: Source Collector -- pure. Stage 1 summarizes which upstream
sessions are actually linked to this generation cycle -- never assumes
a session exists; every downstream stage must check `available` before
reading a source's data.
"""

from __future__ import annotations

from typing import Any


def collect_sources(
    *, document_source_public_id: str, dataset_source_public_id: str | None,
    language_session_public_id: str | None, vision_session_public_id: str | None,
    vision_model_session_public_id: str | None,
) -> dict[str, Any]:
    sources = {
        "document": {"available": True, "public_id": document_source_public_id},
        "dataset": {"available": dataset_source_public_id is not None, "public_id": dataset_source_public_id},
        "language": {"available": language_session_public_id is not None, "public_id": language_session_public_id},
        "vision": {"available": vision_session_public_id is not None, "public_id": vision_session_public_id},
        "vision_model": {
            "available": vision_model_session_public_id is not None,
            "public_id": vision_model_session_public_id,
        },
    }
    return {
        "sources": sources,
        "available_source_count": sum(1 for s in sources.values() if s["available"]),
        "text_capable": sources["language"]["available"] or sources["document"]["available"],
        "image_capable": sources["vision"]["available"],
    }
