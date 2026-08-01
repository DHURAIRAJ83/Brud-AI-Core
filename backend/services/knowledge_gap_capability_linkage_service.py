"""Phase 20 Step 26 -- knowledge-gap capability resolution linkage.

When a `trusted_web`/`tool` route genuinely succeeds, this appends
*resolution evidence* to at most one matching, still-open
`web_capability_gap`/`tool_capability_gap` case -- it never closes the
case itself (that stays a human/Admin decision via
`KnowledgeGapResolutionService`, unchanged), never resolves an
unrelated cluster, and never triggers RAG or training. Matching is
conservative: candidates are pre-filtered to the same
`(event_type, domain, intent, freshness)` (reusing the exact
repository-level bucket `KnowledgeGapClusteringService` already
established), then compared via that same, already-tested clustering
service's near-duplicate logic -- no new similarity math.
"""

from __future__ import annotations

import logging

from backend.core.config import Settings
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.database.repositories.trusted_web_tool_gateway import TrustedWebToolGatewayRepository
from backend.services.knowledge_gap_canonicalization_service import (
    KnowledgeGapCanonicalizationService,
)
from backend.services.knowledge_gap_clustering_service import (
    ClusterCandidate,
    KnowledgeGapClusteringService,
)
from backend.services.knowledge_gap_privacy_service import KnowledgeGapPrivacyService

logger = logging.getLogger(__name__)

_SYNTHETIC_INCOMING_ID = "__phase20_incoming_request__"

_EVENT_TYPE_BY_ROUTE = {"trusted_web": "web_capability_gap", "tool": "tool_capability_gap"}
_RESOLUTION_KIND_BY_ROUTE = {
    "trusted_web": "resolved_by_trusted_web", "tool": "resolved_by_tool",
}
_HIGH_CONFIDENCE_DECISIONS = frozenset({"same_case", "probable_duplicate"})


class KnowledgeGapCapabilityLinkageService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)
        self.gateway_repository = TrustedWebToolGatewayRepository(settings.resolved_database_path)
        self.privacy = KnowledgeGapPrivacyService()
        self.canonicalization = KnowledgeGapCanonicalizationService()
        self.clustering = KnowledgeGapClusteringService()

    def link_if_matched(
        self,
        *,
        resolved_route: str,
        message: str,
        detected_language: str,
        domain: str | None,
        intent: str | None,
        freshness: str | None,
        search_event_public_id: str | None = None,
        tool_execution_public_id: str | None = None,
    ) -> dict[str, object] | None:
        """Best-effort, fail-safe: never raises, returns `None` (no
        link recorded) on any error, missing candidates, or no
        confident match."""

        event_type = _EVENT_TYPE_BY_ROUTE.get(resolved_route)
        if event_type is None:
            return None
        try:
            return self._link(
                event_type=event_type,
                resolution_kind=_RESOLUTION_KIND_BY_ROUTE[resolved_route],
                message=message, detected_language=detected_language,
                domain=domain, intent=intent, freshness=freshness,
                search_event_public_id=search_event_public_id,
                tool_execution_public_id=tool_execution_public_id,
            )
        except Exception:
            logger.exception("knowledge_gap_capability_linkage_failed")
            return None

    def _link(
        self, *, event_type: str, resolution_kind: str, message: str, detected_language: str,
        domain: str | None, intent: str | None, freshness: str | None,
        search_event_public_id: str | None, tool_execution_public_id: str | None,
    ) -> dict[str, object] | None:
        candidates = self.repository.list_open_capability_gap_candidates(
            event_type=event_type, domain=domain, intent=intent, freshness=freshness,
        )
        if not candidates:
            return None

        privacy_result = self.privacy.process(message)
        if privacy_result.redacted_question is None:
            return None
        canonical = self.canonicalization.canonicalize(
            privacy_result.redacted_question, language_category=detected_language
        )

        cluster_candidates = [
            ClusterCandidate(
                case_public_id=_SYNTHETIC_INCOMING_ID,
                canonical_question=canonical.canonical_question,
                language=detected_language, domain=domain, intent=intent, freshness=freshness,
            )
        ]
        for case in candidates:
            cluster_candidates.append(
                ClusterCandidate(
                    case_public_id=case["public_id"],
                    canonical_question=case.get("canonical_question") or "",
                    language=case.get("language") or detected_language,
                    domain=case.get("domain"), intent=case.get("intent"),
                    freshness=case.get("freshness"),
                )
            )

        decisions = self.clustering.find_cluster_decisions(cluster_candidates)
        matched = [
            decision for decision in decisions
            if _SYNTHETIC_INCOMING_ID in (decision.case_public_id, decision.matched_case_public_id)
        ]
        if not matched:
            return None

        best = matched[0]
        matched_case_public_id = (
            best.matched_case_public_id
            if best.case_public_id == _SYNTHETIC_INCOMING_ID
            else best.case_public_id
        )
        confidence_band = "high" if best.decision in _HIGH_CONFIDENCE_DECISIONS else "medium"

        return self.gateway_repository.record_capability_resolution(
            matched_case_public_id,
            {
                "resolution_kind": resolution_kind,
                "search_event_public_id": search_event_public_id,
                "tool_execution_public_id": tool_execution_public_id,
                "matched_by": f"canonical_question_{best.decision}",
                "confidence_band": confidence_band,
            },
        )


__all__ = ["KnowledgeGapCapabilityLinkageService"]
