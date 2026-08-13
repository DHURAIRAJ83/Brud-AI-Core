"""Knowledge Validator -- pure structural checks over already-fetched
knowledge items/relationships. No semantic understanding: duplicate
detection is exact-match on (domain, title), "missing documentation"
is an empty description/related_documentation field, "broken
reference" is a relationship pointing at an item id that isn't in the
provided item set. None of this requires a model.
"""

from __future__ import annotations

import re
from typing import Any

_VERSION_PATTERN = re.compile(r"^\d+(\.\d+){1,2}$")


def find_duplicate_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[int, str], list[str]] = {}
    for item in items:
        key = (item["domain_id"], item["title"].strip().lower())
        seen.setdefault(key, []).append(item["public_id"])
    return [
        {"type": "duplicate_item", "public_ids": ids, "title": key[1]}
        for key, ids in seen.items()
        if len(ids) > 1
    ]


def find_missing_documentation(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    for item in items:
        if not item.get("description", "").strip():
            issues.append({
                "type": "missing_documentation", "public_id": item["public_id"],
                "message": "empty description",
            })
        elif not item.get("related_documentation"):
            issues.append({
                "type": "missing_documentation", "public_id": item["public_id"],
                "message": "no related documentation referenced",
            })
    return issues


def find_missing_categories(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"type": "missing_category", "public_id": item["public_id"]}
        for item in items
        if not item.get("category", "").strip()
    ]


def find_missing_relationships(
    items: list[dict[str, Any]], relationships: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    connected = {r["from_item_id"] for r in relationships} | {
        r["to_item_id"] for r in relationships
    }
    return [
        {"type": "missing_relationship", "public_id": item["public_id"]}
        for item in items
        if item["id"] not in connected
    ]


def find_broken_references(
    items: list[dict[str, Any]], relationships: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    valid_ids = {item["id"] for item in items}
    issues = []
    for rel in relationships:
        if rel["from_item_id"] not in valid_ids or rel["to_item_id"] not in valid_ids:
            issues.append({"type": "broken_reference", "public_id": rel["public_id"]})
    return issues


def find_invalid_versions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"type": "invalid_version", "public_id": item["public_id"], "version": item.get("version")}
        for item in items
        if not _VERSION_PATTERN.match(str(item.get("version", "")))
    ]


def run_validation(
    items: list[dict[str, Any]], relationships: list[dict[str, Any]]
) -> dict[str, Any]:
    issues = (
        find_duplicate_items(items)
        + find_missing_documentation(items)
        + find_missing_categories(items)
        + find_missing_relationships(items, relationships)
        + find_broken_references(items, relationships)
        + find_invalid_versions(items)
    )
    summary: dict[str, int] = {}
    for issue in issues:
        summary[issue["type"]] = summary.get(issue["type"], 0) + 1
    return {"issues": issues, "summary": summary, "issue_count": len(issues)}
