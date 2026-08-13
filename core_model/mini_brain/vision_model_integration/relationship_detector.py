"""MB-15: Relationship Detection -- pure. Zero new geometry logic:
this is a direct re-export of MB-14's own already-tested `core_model.
mini_brain.vision_intelligence.knowledge_graph_builder.
build_knowledge_graph`. A relationship between two objects is the same
bounding-box geometry problem whether the boxes came from an admin
(MB-14 Stage 7) or a vision provider's own predicted boxes (MB-15) --
duplicating that math here would violate "never duplicate existing
logic."
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.vision_intelligence.knowledge_graph_builder import build_knowledge_graph


def detect_relationships(*, objects: list[dict[str, Any]]) -> dict[str, Any]:
    return build_knowledge_graph(objects=objects)
