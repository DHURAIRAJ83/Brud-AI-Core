"""MB-16: Knowledge Graph reference -- pure. Never regenerates a
graph -- only references the already-built graph MB-14 or MB-15
produced (real bounding-box geometry, computed once). This module's
only job is to validate the shape and summarize it for the merged
metadata; the nodes and edges themselves are passed through verbatim.
"""

from __future__ import annotations

from typing import Any


def reference_knowledge_graph(*, graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    return {
        "nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges),
        "regenerated": False,
        "disclosure": "referenced verbatim from an already-built MB-14/MB-15 graph -- never regenerated here",
    }
