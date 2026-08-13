"""MB-03: Brud Intelligence Engine -- service layer.

The only impure module in MB-03. Its only I/O is a **read-only** call
into MB-02's `MiniBrainKnowledgeRepository` (never a write -- this
service has no create/update/delete path into Knowledge Core at all)
plus wall-clock timing for the Diagnostics stage. No new database
table exists for MB-03: every pipeline result is computed fresh on
each call and returned directly, never persisted -- matching MB-03's
own deliverable list, which (unlike MB-01 and MB-02) never asks for a
database design.
"""

from __future__ import annotations

import time
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.mini_brain_knowledge import (
    MiniBrainKnowledgeRepository,
    public_row,
)
from core_model.mini_brain.intelligence.confidence import calculate_confidence
from core_model.mini_brain.intelligence.context_resolver import build_context, score_items
from core_model.mini_brain.intelligence.feature_resolver import resolve_features
from core_model.mini_brain.intelligence.knowledge_planner import INTENT_TO_DOMAIN, plan_knowledge
from core_model.mini_brain.intelligence.question_analyzer import analyze_question
from core_model.mini_brain.intelligence.response_plan import build_response_plan
from core_model.mini_brain.intelligence.rule_engine import apply_rules
from core_model.mini_brain.intelligence.workflow_graph import resolve_workflow


class MiniBrainIntelligenceService:
    def __init__(self, knowledge_repository: MiniBrainKnowledgeRepository, settings: Settings) -> None:
        self.knowledge_repository = knowledge_repository
        self.settings = settings

    def _fetch_candidate_items(self, connection, domain_key: str | None) -> list[dict[str, Any]]:
        domains = {
            public_row(row)["key"]: row["id"]
            for row in self.knowledge_repository.list_domains(connection)
        }
        id_to_key = {v: k for k, v in domains.items()}
        if domain_key is not None and domain_key in domains:
            rows = self.knowledge_repository.list_items(
                connection, domain_id=domains[domain_key], limit=100
            )
        else:
            rows = self.knowledge_repository.all_items(connection)
        items = []
        for row in rows:
            item = public_row(row)
            item["_id"] = row["id"]
            item["domain_key"] = id_to_key.get(row["domain_id"])
            items.append(item)
        return items

    def analyze(self, question: str) -> dict[str, Any]:
        started = time.perf_counter()

        question_analysis = analyze_question(question)
        intent = question_analysis["intent"]
        expected_domain = INTENT_TO_DOMAIN.get(intent)

        with self.knowledge_repository.transaction() as connection:
            candidates = self._fetch_candidate_items(connection, expected_domain)
            scored = score_items(candidates, question_analysis["subject_candidates"])
            context = build_context(scored)

            all_relationships = [
                public_row(r) | {
                    "from_item_id": r["from_item_id"], "to_item_id": r["to_item_id"],
                }
                for r in self.knowledge_repository.all_relationships(connection)
            ]
            items_by_id = {c["_id"]: c for c in candidates}
            # Widen items_by_id with every item referenced by a
            # relationship, even outside the scored/candidate domain,
            # so workflow neighbors resolve to a real title instead of
            # "unknown" just because they live in a different domain.
            referenced_ids = {r["from_item_id"] for r in all_relationships} | {
                r["to_item_id"] for r in all_relationships
            }
            missing_ids = referenced_ids - set(items_by_id)
            if missing_ids:
                for row in self.knowledge_repository.all_items(connection):
                    if row["id"] in missing_ids:
                        items_by_id[row["id"]] = public_row(row) | {"_id": row["id"]}

        current_item_id = scored[0]["item"]["_id"] if scored else None
        workflow = (
            resolve_workflow(current_item_id, all_relationships, items_by_id)
            if current_item_id is not None
            else {
                "current_step": None, "previous_steps": [], "next_steps": [],
                "dependencies": [], "related_steps": [], "in_a_workflow_chain": False,
            }
        )
        related_titles = set(
            workflow["previous_steps"] + workflow["next_steps"]
            + workflow["dependencies"] + workflow["related_steps"]
        )

        features = resolve_features([entry["item"] for entry in scored])
        knowledge_plan = plan_knowledge(scored, intent=intent, related_titles=related_titles)
        rules = apply_rules(
            question=question, intent=intent, knowledge_plan=knowledge_plan,
            excluded_knowledge=knowledge_plan["excluded_knowledge"],
        )
        confidence = calculate_confidence(
            intent_confidence_signal=question_analysis["intent_confidence_signal"],
            intent=intent, knowledge_plan=knowledge_plan, workflow=workflow,
            rule_flags=rules["flags"],
        )
        response_plan = build_response_plan(
            question_analysis=question_analysis, context=context, workflow=workflow,
            knowledge_plan=knowledge_plan, rules=rules, confidence=confidence,
        )

        processing_ms = round((time.perf_counter() - started) * 1000, 2)

        return {
            "question_analysis": question_analysis,
            "context": context,
            "workflow": workflow,
            "features": features,
            "knowledge_plan": knowledge_plan,
            "rules": rules,
            "response_plan": response_plan,
            "confidence": confidence,
            "diagnostics": {
                "processing_time_ms": processing_ms,
                "candidate_item_count": len(candidates),
                "scored_item_count": len(scored),
                "domain_used": expected_domain,
            },
        }
