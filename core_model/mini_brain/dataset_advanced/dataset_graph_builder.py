"""MB-05.1: Dataset Graph Builder -- Topic -> Subtopic -> Lesson ->
Question -> Answer, as a plain node/edge structure. Graph data only,
no visualization library, no rendering. Built entirely from Coverage
Analyzer's already-computed subtopic/matched-record data -- never
re-scans record text.

Bounded: at most `MAX_LESSONS_PER_SUBTOPIC` lesson branches per
subtopic, so one call cannot produce an unbounded graph from a large
dataset.
"""

from __future__ import annotations

from typing import Any

MAX_LESSONS_PER_SUBTOPIC = 5
PREVIEW_CHARS = 80


def _preview(text: str | None) -> str:
    text = (text or "").strip()
    return text[:PREVIEW_CHARS] + ("…" if len(text) > PREVIEW_CHARS else "")


def build_graph(*, coverage: dict[str, Any], records_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    for domain, data in coverage.items():
        domain_id = f"topic:{domain}"
        nodes.append({"id": domain_id, "type": "topic", "label": domain})

        for subtopic, info in data["subtopics"].items():
            if info["status"] == "Missing":
                continue
            subtopic_id = f"subtopic:{domain}:{subtopic}"
            nodes.append({"id": subtopic_id, "type": "subtopic", "label": subtopic, "status": info["status"]})
            edges.append({"from": domain_id, "to": subtopic_id, "relationship": "has_subtopic"})

            for record_id in info["matched_record_ids"][:MAX_LESSONS_PER_SUBTOPIC]:
                record = records_by_id.get(record_id, {})
                lesson_id = f"lesson:{record_id}"
                question_id = f"question:{record_id}"
                answer_id = f"answer:{record_id}"

                nodes.append({"id": lesson_id, "type": "lesson", "label": record_id})
                edges.append({"from": subtopic_id, "to": lesson_id, "relationship": "has_lesson"})

                nodes.append({"id": question_id, "type": "question", "label": _preview(record.get("instruction"))})
                edges.append({"from": lesson_id, "to": question_id, "relationship": "has_question"})

                nodes.append({"id": answer_id, "type": "answer", "label": _preview(record.get("output_text"))})
                edges.append({"from": question_id, "to": answer_id, "relationship": "has_answer"})

    return {"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)}
