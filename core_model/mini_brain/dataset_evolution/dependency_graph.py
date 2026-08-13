"""MB-11: Knowledge Dependency Graph -- pure. Reasons over MB-05.1's
already-built Topic -> Subtopic -> Lesson -> Question -> Answer graph
(`dataset_graph_builder.build_graph`) to detect missing, broken, and
circular dependencies, plus depth and breadth. Never re-scans dataset
records itself and never rebuilds the graph -- the node/edge structure
is entirely MB-05.1's own real output, read-only.

Disclosure: the task's own eight-level target taxonomy (Topic -> Sub
Topic -> Concept -> Skill -> Example -> Exercise -> Reasoning ->
Advanced) is not what any existing system in this codebase builds.
MB-05.1's graph reaches five real levels (topic/subtopic/lesson/
question/answer) -- this module analyzes exactly those five, and does
not invent Concept/Skill/Reasoning/Advanced nodes that no real data
backs.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

TARGET_TAXONOMY = ("topic", "subtopic", "concept", "skill", "example", "exercise", "reasoning", "advanced")
REAL_LEVELS = ("topic", "subtopic", "lesson", "question", "answer")


def analyze_dependencies(*, graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = {n["id"] for n in nodes}
    nodes_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        nodes_by_type[node["type"]].append(node)

    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        children[edge["from"]].append(edge["to"])

    broken_dependencies = [
        edge for edge in edges if edge["from"] not in node_ids or edge["to"] not in node_ids
    ]

    missing_dependencies = []
    for topic in nodes_by_type.get("topic", []):
        if not children.get(topic["id"]):
            missing_dependencies.append({"node_id": topic["id"], "reason": "topic has no subtopics"})
    for subtopic in nodes_by_type.get("subtopic", []):
        if not children.get(subtopic["id"]):
            missing_dependencies.append({"node_id": subtopic["id"], "reason": "subtopic has no lessons"})

    circular_dependencies: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def _dfs(node_id: str) -> None:
        if node_id in visiting:
            cycle_start = path.index(node_id)
            circular_dependencies.append(path[cycle_start:] + [node_id])
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        path.append(node_id)
        for child in children.get(node_id, []):
            _dfs(child)
        path.pop()
        visiting.discard(node_id)
        visited.add(node_id)

    for node in nodes:
        if node["id"] not in visited:
            _dfs(node["id"])

    depth = len(REAL_LEVELS) - 1 if any(nodes_by_type.get(level) for level in REAL_LEVELS) else 0
    populated_levels = [level for level in REAL_LEVELS if nodes_by_type.get(level)]
    breadth_by_level = {
        level: round(len(nodes_by_type[level]) / max(len(nodes_by_type.get(_parent_level(level), [])), 1), 2)
        for level in REAL_LEVELS if nodes_by_type.get(level)
    }

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "missing_dependencies": missing_dependencies,
        "broken_dependencies": broken_dependencies,
        "circular_dependencies": circular_dependencies,
        "has_broken_or_circular": bool(broken_dependencies or circular_dependencies),
        "depth": depth,
        "breadth_by_level": breadth_by_level,
        "populated_levels": populated_levels,
        "target_taxonomy": list(TARGET_TAXONOMY),
        "unpopulated_target_levels": [lvl for lvl in TARGET_TAXONOMY if lvl not in populated_levels],
    }


def _parent_level(level: str) -> str:
    index = REAL_LEVELS.index(level)
    return REAL_LEVELS[max(index - 1, 0)]
