"""Workflow Resolver -- pure graph walk over Knowledge Core
relationships already fetched by the service layer. `flows_to` edges
define a workflow's step order; `depends_on` edges define
dependencies; every other relationship type counts as merely
"related". No graph algorithm beyond direct-neighbor lookup is used --
this deliberately does not attempt multi-hop path-finding or ranking,
which would start to resemble a learned model rather than a fixed
rule.
"""

from __future__ import annotations

from typing import Any


def resolve_workflow(
    current_item_id: int,
    relationships: list[dict[str, Any]],
    items_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    previous_steps = []
    next_steps = []
    dependencies = []
    related_steps = []

    for rel in relationships:
        from_id, to_id, rel_type = rel["from_item_id"], rel["to_item_id"], rel["relationship_type"]
        if rel_type == "flows_to":
            if to_id == current_item_id and from_id in items_by_id:
                previous_steps.append(items_by_id[from_id]["title"])
            if from_id == current_item_id and to_id in items_by_id:
                next_steps.append(items_by_id[to_id]["title"])
        elif rel_type == "depends_on" and from_id == current_item_id and to_id in items_by_id:
            dependencies.append(items_by_id[to_id]["title"])
        else:
            other_id = to_id if from_id == current_item_id else (from_id if to_id == current_item_id else None)
            if other_id is not None and other_id in items_by_id:
                related_steps.append(items_by_id[other_id]["title"])

    current_title = items_by_id.get(current_item_id, {}).get("title")
    return {
        "current_step": current_title,
        "previous_steps": sorted(set(previous_steps)),
        "next_steps": sorted(set(next_steps)),
        "dependencies": sorted(set(dependencies)),
        "related_steps": sorted(set(related_steps)),
        "in_a_workflow_chain": bool(previous_steps or next_steps),
    }
