"""MB-02: Brud Knowledge Core -- service layer.

Composes `MiniBrainKnowledgeRepository` (storage + structured search)
with the pure `core_model.mini_brain.knowledge` functions (validation,
coverage). No embeddings, no vector index, no semantic search --
`search()` below is a parameterized SQL filter, nothing more.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_knowledge import (
    MiniBrainKnowledgeRepository,
    public_row,
)
from core_model.mini_brain.knowledge.coverage import compute_domain_coverage, compute_overall_coverage
from core_model.mini_brain.knowledge.seed_data import DOMAINS, ITEMS, REFERENCE_COUNTS, RELATIONSHIPS
from core_model.mini_brain.knowledge.validation import run_validation


class MiniBrainKnowledgeService:
    def __init__(self, repository: MiniBrainKnowledgeRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # -- seeding -----------------------------------------------------------

    def seed_defaults(self, admin_id: str) -> dict[str, Any]:
        """Idempotent: does nothing if any domain already exists. Loads
        the real, verified seed content from
        `core_model.mini_brain.knowledge.seed_data` -- never generates
        content itself."""

        with self.repository.transaction() as connection:
            if self.repository.is_seeded(connection):
                return {"seeded": False, "reason": "already_seeded"}

            domain_ids: dict[str, int] = {}
            for domain in DOMAINS:
                self.repository.create_domain(
                    connection, key=domain["key"], name=domain["name"],
                    description=domain["description"],
                )
                domain_ids[domain["key"]] = self.repository.domain_by_key(
                    connection, domain["key"]
                )["id"]

            item_ids: dict[str, int] = {}
            item_count = 0
            for domain_key, items in ITEMS.items():
                for item in items:
                    public_id = self.repository.create_item(
                        connection, domain_id=domain_ids[domain_key], payload=item,
                        admin_public_id=admin_id,
                    )
                    row = self.repository.item(connection, public_id)
                    item_ids[item["title"]] = row["id"]
                    item_count += 1

            relationship_count = 0
            for from_title, to_title, rel_type, description in RELATIONSHIPS:
                self.repository.create_relationship(
                    connection, from_item_id=item_ids[from_title], to_item_id=item_ids[to_title],
                    relationship_type=rel_type, description=description,
                )
                relationship_count += 1

        return {
            "seeded": True, "domains": len(DOMAINS), "items": item_count,
            "relationships": relationship_count,
        }

    # -- domains -------------------------------------------------------------

    def list_domains(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            domains = [public_row(row) for row in self.repository.list_domains(connection)]
            for domain in domains:
                items = self.repository.list_items(
                    connection,
                    domain_id=self.repository.domain_by_key(connection, domain["key"])["id"],
                    limit=100,
                )
                domain["item_count"] = len(items)
        return {"items": domains}

    # -- items -------------------------------------------------------------

    def create_item(self, domain_key: str, payload: dict[str, Any], admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            domain_row = self.repository.domain_by_key(connection, domain_key)
            if domain_row is None:
                raise ValidationError(f"unknown knowledge domain: {domain_key}")
            if self.repository.item_by_title(connection, domain_row["id"], payload["title"]):
                raise ValidationError(
                    f"a knowledge item titled {payload['title']!r} already exists in this domain"
                )
            public_id = self.repository.create_item(
                connection, domain_id=domain_row["id"], payload=payload, admin_public_id=admin_id,
            )
            return public_row(self.repository.item(connection, public_id))

    def get_item(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            row = public_row(self.repository.item(connection, public_id))
            item_row = self.repository.item(connection, public_id)
            relationships = []
            for rel in self.repository.relationships_for_item(connection, item_row["id"]):
                other_id = (
                    rel["to_item_id"] if rel["from_item_id"] == item_row["id"] else rel["from_item_id"]
                )
                other = self.repository.all_items(connection)
                other_title = next((i["title"] for i in other if i["id"] == other_id), "unknown")
                relationships.append({
                    "public_id": rel["public_id"],
                    "direction": "outgoing" if rel["from_item_id"] == item_row["id"] else "incoming",
                    "relationship_type": rel["relationship_type"],
                    "description": rel["description"],
                    "related_item_title": other_title,
                })
        return {**row, "relationships": relationships}

    def list_items(self, domain_key: str | None, limit: int, offset: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            domain_id = None
            if domain_key is not None:
                domain_row = self.repository.domain_by_key(connection, domain_key)
                if domain_row is None:
                    raise ValidationError(f"unknown knowledge domain: {domain_key}")
                domain_id = domain_row["id"]
            rows = [
                public_row(row)
                for row in self.repository.list_items(
                    connection, domain_id=domain_id, limit=limit, offset=offset
                )
            ]
        return {"items": rows, "limit": limit, "offset": offset}

    def search(
        self, *, query: str | None, category: str | None, tag: str | None,
        domain_key: str | None, status: str | None, limit: int, offset: int,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = [
                public_row(row)
                for row in self.repository.search_items(
                    connection, query=query, category=category, tag=tag,
                    domain_key=domain_key, status=status, limit=limit, offset=offset,
                )
            ]
        return {
            "items": rows,
            "filters": {
                "query": query, "category": category, "tag": tag,
                "domain": domain_key, "status": status,
            },
        }

    # -- relationships -------------------------------------------------------

    def create_relationship(
        self, from_public_id: str, to_public_id: str, relationship_type: str,
        description: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            from_row = self.repository.item(connection, from_public_id)
            to_row = self.repository.item(connection, to_public_id)
            public_id = self.repository.create_relationship(
                connection, from_item_id=from_row["id"], to_item_id=to_row["id"],
                relationship_type=relationship_type, description=description,
            )
        return {"public_id": public_id}

    # -- validation ----------------------------------------------------------

    def run_validation(self, admin_id: str | None) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            items = [public_row(row) | {"id": row["id"], "domain_id": row["domain_id"]}
                     for row in self.repository.all_items(connection)]
            relationships = [public_row(row) for row in self.repository.all_relationships(connection)]
            result = run_validation(items, relationships)
            self.repository.record_validation_report(
                connection, issues=result["issues"], summary=result["summary"],
                admin_public_id=admin_id,
            )
        return result

    def latest_validation_report(self) -> dict[str, Any] | None:
        with self.repository.transaction() as connection:
            row = self.repository.latest_validation_report(connection)
            return public_row(row) if row is not None else None

    def list_validation_reports(self, limit: int = 10) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = [public_row(r) for r in self.repository.list_validation_reports(connection, limit=limit)]
        return {"items": rows}

    # -- coverage --------------------------------------------------------------

    def coverage(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            domains = [public_row(row) for row in self.repository.list_domains(connection)]
            domain_stats = []
            for domain in domains:
                domain_row = self.repository.domain_by_key(connection, domain["key"])
                items = [
                    public_row(row)
                    for row in self.repository.list_items(connection, domain_id=domain_row["id"], limit=100)
                ]
                domain_stats.append(
                    compute_domain_coverage(
                        domain["key"], items, reference_count=REFERENCE_COUNTS.get(domain["key"])
                    )
                )
        return {"domains": domain_stats, "overall": compute_overall_coverage(domain_stats)}

    # -- diagnostics -----------------------------------------------------------

    def diagnostics(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            domains = self.repository.list_domains(connection)
            items = self.repository.all_items(connection)
            relationships = self.repository.all_relationships(connection)
            latest_report = self.repository.latest_validation_report(connection)
        categories = sorted({item["category"] for item in items})
        return {
            "domain_count": len(domains),
            "item_count": len(items),
            "relationship_count": len(relationships),
            "category_count": len(categories),
            "categories": categories,
            "latest_validation": public_row(latest_report) if latest_report is not None else None,
            "seeded": len(domains) > 0,
        }
