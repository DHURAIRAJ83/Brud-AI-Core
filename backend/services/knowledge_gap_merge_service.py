"""Phase 19 Step 23 -- governed merge workflow.

`propose_merge` is a pure preview -- it never writes anything.
`confirm_merge` requires the caller to re-supply the exact preview
fingerprint it was shown (a stale-state check, mirroring the pattern
`admin_assistant_service.py` already uses for its own propose/confirm
pipeline) so a case that changed underneath the preview is refused
rather than silently merged.
"""

from __future__ import annotations

from backend.core.config import Settings
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.services.knowledge_gap_clustering_service import (
    ClusterCandidate,
    KnowledgeGapClusteringService,
)


def _fingerprint(cases: list[dict[str, object]]) -> str:
    return "|".join(sorted(f"{case['public_id']}:{case['updated_at']}" for case in cases))


class KnowledgeGapMergeService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)
        self.clustering = KnowledgeGapClusteringService()

    def propose_merge(self, case_public_ids: list[str]) -> dict[str, object]:
        if len(case_public_ids) < 2:
            raise ValidationError("propose_merge requires at least two case ids")
        cases = [self.repository.get_case(public_id) for public_id in case_public_ids]
        candidates = [
            ClusterCandidate(
                case_public_id=case["public_id"],
                canonical_question=case["canonical_question"] or "",
                language=case["language"] or "unknown",
                domain=case["domain"],
                intent=case["intent"],
                freshness=case["freshness"],
            )
            for case in cases
            if not case["content_unavailable_for_review"]
        ]
        decisions = self.clustering.find_cluster_decisions(candidates)
        return {
            "case_public_ids": case_public_ids,
            "decisions": [
                {
                    "case_public_id": d.case_public_id,
                    "matched_case_public_id": d.matched_case_public_id,
                    "decision": d.decision,
                }
                for d in decisions
            ],
            "stale_check_fingerprint": _fingerprint(cases),
        }

    def confirm_merge(
        self,
        *,
        case_public_ids: list[str],
        stale_check_fingerprint: str,
        admin_public_id: str,
        canonical_question: str,
        primary_language: str,
    ) -> dict[str, object]:
        cases = [self.repository.get_case(public_id) for public_id in case_public_ids]
        current_fingerprint = _fingerprint(cases)
        if current_fingerprint != stale_check_fingerprint:
            raise ConflictError(
                "one or more cases changed since this merge was proposed -- "
                "re-run propose_merge and confirm again"
            )

        cluster = self.repository.create_cluster(
            {
                "canonical_question": canonical_question,
                "primary_language": primary_language,
                "domain": cases[0]["domain"],
                "intent": cases[0]["intent"],
                "freshness": cases[0]["freshness"],
            }
        )
        for case in cases:
            self.repository.add_cluster_member(
                {
                    "cluster_public_id": cluster["public_id"],
                    "case_public_id": case["public_id"],
                    "decision": "same_case",
                    "confirmed_by_admin_public_id": admin_public_id,
                }
            )
        return self.repository.recalculate_cluster_frequency(cluster["public_id"])


__all__ = ["KnowledgeGapMergeService"]
