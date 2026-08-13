"""MB-17: Knowledge Graph Retrieval -- pure. Never regenerates a
graph -- only filters MB-14/MB-15's already-built graph (real
bounding-box geometry, computed once) down to the edges whose node
labels textually relate to the query. The same "reference, never
rebuild" discipline MB-16's own `knowledge_graph_reference.py` uses.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.keyword_index import tokenize_for_keyword_index


def retrieve_graph_edges(*, normalized_query: str, graph: dict[str, Any]) -> dict[str, Any]:
    query_tokens = set(tokenize_for_keyword_index(normalized_query))
    edges = graph.get("edges", [])
    nodes_by_id = {node["id"]: node["label"] for node in graph.get("nodes", [])}

    matched = []
    for edge in edges:
        from_label = nodes_by_id.get(edge["from"], edge["from"])
        to_label = nodes_by_id.get(edge["to"], edge["to"])
        edge_tokens = set(tokenize_for_keyword_index(f"{from_label} {to_label}"))
        if query_tokens & edge_tokens:
            matched.append({"from": from_label, "to": to_label, "relationship": edge["relationship"]})

    return {
        "matched_edges": matched, "total_edge_count": len(edges), "matched_edge_count": len(matched),
        "regenerated": False,
        "disclosure": "referenced verbatim from an already-built MB-14/MB-15 graph -- never regenerated here",
    }
