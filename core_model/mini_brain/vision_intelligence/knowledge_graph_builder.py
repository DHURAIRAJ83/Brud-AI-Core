"""MB-14: Knowledge Graph Builder -- pure. Converts admin-annotated
objects into a structured graph using real geometry from their own
admin-drawn bounding boxes (containment, overlap, and proximity) --
never a semantic or causal claim. "Mountain contains Fish" here means
exactly what it says: the Fish object's box sits inside the Mountain
object's box on the page, nothing more.
"""

from __future__ import annotations

from typing import Any

NEAR_DISTANCE_THRESHOLD = 0.3


def _corners(box: dict[str, float]) -> tuple[float, float, float, float]:
    x1, y1 = box["x"], box["y"]
    return x1, y1, x1 + box["width"], y1 + box["height"]


def _center(box: dict[str, float]) -> tuple[float, float]:
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _contains(a: dict[str, float], b: dict[str, float]) -> bool:
    ax1, ay1, ax2, ay2 = _corners(a)
    bx1, by1, bx2, by2 = _corners(b)
    return ax1 <= bx1 and ay1 <= by1 and ax2 >= bx2 and ay2 >= by2


def _overlaps(a: dict[str, float], b: dict[str, float]) -> bool:
    ax1, ay1, ax2, ay2 = _corners(a)
    bx1, by1, bx2, by2 = _corners(b)
    return ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2


def _distance(a: dict[str, float], b: dict[str, float]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _spatial_relationship(a: dict[str, float], b: dict[str, float]) -> str | None:
    if _contains(a, b):
        return "contains"
    if _contains(b, a):
        return "inside"
    if _overlaps(a, b):
        return "overlaps"
    if _distance(a, b) < NEAR_DISTANCE_THRESHOLD:
        return "near"
    return None


def build_knowledge_graph(*, objects: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [{"id": o["public_id"], "label": o["label"], "confidence": o["confidence"]} for o in objects]
    boxed = [o for o in objects if o.get("bounding_box")]

    edges: list[dict[str, str]] = []
    for i, a in enumerate(boxed):
        for b in boxed[i + 1 :]:
            relationship = _spatial_relationship(a["bounding_box"], b["bounding_box"])
            if relationship:
                edges.append({"from": a["public_id"], "to": b["public_id"], "relationship": relationship})

    return {
        "nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges),
        "unboxed_node_count": len(objects) - len(boxed),
        "disclosure": (
            "relationships are derived from real bounding-box geometry (containment/overlap/"
            "proximity) only -- never a semantic or causal claim about what the objects actually "
            "depict"
        ),
    }
