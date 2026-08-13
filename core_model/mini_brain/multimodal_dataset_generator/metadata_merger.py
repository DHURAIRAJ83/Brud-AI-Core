"""MB-16: Metadata Merger -- pure assembly only. Combines the already-
built text section, image section, and knowledge graph reference into
one unified metadata object -- no new computation, just structure.
"""

from __future__ import annotations

from typing import Any


def merge_metadata(
    *, source_report: dict[str, Any], text_section: dict[str, Any], image_section: dict[str, Any],
    knowledge_graph: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sources": source_report["sources"],
        "text": text_section,
        "images": image_section,
        "knowledge_graph": knowledge_graph,
        "is_multimodal": text_section.get("ocr_char_count", 0) > 0 and image_section.get("image_count", 0) > 0,
    }
