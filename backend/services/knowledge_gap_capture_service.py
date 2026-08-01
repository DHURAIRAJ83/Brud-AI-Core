"""Phase 19 Step 13/14 -- `KnowledgeGapCaptureService`.

The single integration point between Phase 18's public router and the
knowledge-gap registry. Consumes already-computed routing/feedback
evidence; never searches the web, never touches RAG, never starts a
RAG trial or training dataset. Real-time capture only performs an
O(1) exact-hash duplicate lookup (`find_case_by_input_hash`) -- cross-
phrasing near-duplicate clustering is a separate, bounded, Admin-
triggered batch operation (`KnowledgeGapClusteringService` +
`POST /clusters/propose-merge`), never run per-request, per Step 33's
CPU-first constraint.

Every public entry point here is designed to never raise -- the
caller (`PublicChatRoutingService`) wraps it in a broad `except
Exception` regardless (defense in depth), but this service also
degrades internally wherever it reasonably can, since a broken gap
capture must never break the public chat response it is attached to.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.core.config import Settings
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.services.knowledge_gap_canonicalization_service import (
    KnowledgeGapCanonicalizationService,
)
from backend.services.knowledge_gap_priority_service import (
    KnowledgeGapPriorityService,
    PriorityInput,
)
from backend.services.knowledge_gap_privacy_service import KnowledgeGapPrivacyService
from core_model.knowledge_gap import TAMIL_FIRST_PRIORITY_REASON_CODES
from core_model.knowledge_gap.eligibility import determine_gap_eligibility

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_ATTEMPTS = 2

# Phase 17's own `tamil_language` domain subdomains (tamil_grammar,
# tamil_orthography, tamil_meaning) already match
# `TAMIL_FIRST_PRIORITY_REASON_CODES` exactly -- reused as a reason
# code directly rather than re-deriving a Tamil-capability signal from
# scratch. `tamil_translation` is deliberately excluded: translation
# quality is a different capability than grammar/meaning/orthography
# and isn't one of Step 12's listed boost categories.
_TAMIL_DOMAIN_SUBDOMAIN_REASON_CODES = frozenset(
    {"tamil_grammar", "tamil_orthography", "tamil_meaning"}
)


def _augment_with_tamil_capability_reason_codes(
    reason_codes: tuple[str, ...],
    *,
    event_type: str,
    domain: str | None,
    subdomain: str | None,
    language: str,
) -> tuple[str, ...]:
    extra: list[str] = []
    if (
        domain == "tamil_language"
        and subdomain in _TAMIL_DOMAIN_SUBDOMAIN_REASON_CODES
        and event_type in ("knowledge_gap", "language_failure", "feedback_issue")
    ):
        extra.append(subdomain)
    if (
        event_type == "language_failure"
        and "wrong_output_language" in reason_codes
        and language == "ta"
    ):
        extra.append("tamil_output_language_failure")
    if not extra:
        return reason_codes
    assert all(code in TAMIL_FIRST_PRIORITY_REASON_CODES for code in extra)
    return tuple(dict.fromkeys((*reason_codes, *extra)))


class KnowledgeGapCaptureService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)
        self.privacy = KnowledgeGapPrivacyService()
        self.canonicalization = KnowledgeGapCanonicalizationService()
        self.priority = KnowledgeGapPriorityService()

    def capture(
        self,
        *,
        message: str,
        resolved_route: str,
        safety_status: str,
        evidence_status: str,
        confidence_band: str,
        fallbacks_attempted: tuple[str, ...],
        clarification_required: bool,
        detected_language: str,
        domain: str | None = None,
        subdomain: str | None = None,
        intent: str | None = None,
        freshness: str | None = None,
        unresolved_after_clarification: bool = False,
        negative_feedback_reason: str | None = None,
        involves_memory: bool = False,
        routing_event_public_id: str | None = None,
        feedback_event_public_id: str | None = None,
    ) -> dict[str, object] | None:
        eligibility = determine_gap_eligibility(
            resolved_route=resolved_route,
            safety_status=safety_status,
            evidence_status=evidence_status,
            confidence_band=confidence_band,
            fallbacks_attempted=fallbacks_attempted,
            clarification_required=clarification_required,
            unresolved_after_clarification=unresolved_after_clarification,
            negative_feedback_reason=negative_feedback_reason,
        )
        if not eligibility.eligible_for_gap_registry:
            return None

        reason_codes = _augment_with_tamil_capability_reason_codes(
            eligibility.reason_codes,
            event_type=eligibility.event_type,
            domain=domain,
            subdomain=subdomain,
            language=detected_language,
        )

        privacy_result = self.privacy.process(message, involves_memory=involves_memory)

        canonical_question: str | None = None
        if not privacy_result.content_unavailable_for_review and privacy_result.redacted_question:
            canonical_question = self.canonicalization.canonicalize(
                privacy_result.redacted_question, language_category=detected_language
            ).canonical_question

        existing = self.repository.find_case_by_input_hash(privacy_result.input_hash)
        if existing is not None:
            case = self.repository.touch_case_occurrence(existing["public_id"])
        else:
            case = self.repository.create_case(
                {
                    "event_type": eligibility.event_type,
                    "primary_reason_code": reason_codes[0]
                    if reason_codes
                    else "model_knowledge_missing",
                    "reason_codes": list(reason_codes),
                    "status": "needs_clarification"
                    if eligibility.event_type == "clarification_event"
                    else ("review_required" if eligibility.review_required else "new"),
                    "stage": "human_review" if eligibility.review_required else "classification",
                    "language": detected_language,
                    "domain": domain,
                    "intent": intent,
                    "freshness": freshness,
                    "input_hash": privacy_result.input_hash,
                    "canonical_question": canonical_question,
                    "redacted_question": privacy_result.redacted_question,
                    "content_unavailable_for_review": privacy_result.content_unavailable_for_review,
                    "retention_policy": "hash_only"
                    if privacy_result.content_unavailable_for_review
                    else "standard",
                }
            )

        self.repository.record_occurrence(
            {
                "case_public_id": case["public_id"],
                "routing_event_public_id": routing_event_public_id,
                "feedback_event_public_id": feedback_event_public_id,
                "request_hash": privacy_result.input_hash,
                "route_recommended": None,
                "route_used": resolved_route,
                "evidence_status": evidence_status,
                "confidence_band": confidence_band,
                "event_type": eligibility.event_type,
                "reason_codes": list(reason_codes),
                "language": detected_language,
                "domain": domain,
                "intent": intent,
                "freshness": freshness,
                "privacy_status": "hash_only" if privacy_result.content_unavailable_for_review
                else "standard",
            }
        )

        priority_result = self.priority.score(
            PriorityInput(
                event_type=eligibility.event_type,
                reason_codes=reason_codes,
                frequency=case["frequency"],
                last_seen_at=datetime.now(UTC),
                negative_feedback_reasons=(negative_feedback_reason,)
                if negative_feedback_reason
                else (),
                privacy_risk=privacy_result.content_unavailable_for_review,
            )
        )
        case = self.repository.update_case_priority(
            case["public_id"],
            priority_score=priority_result.priority_score,
            priority_band=priority_result.priority_band,
            priority_reason_codes=list(priority_result.priority_reason_codes),
        )
        return case

    def capture_safe(self, **kwargs: object) -> dict[str, object] | None:
        """Never raises -- used by the live public chat integration
        point, which must never fail a real user's chat response
        because gap capture broke."""

        try:
            return self.capture(**kwargs)  # type: ignore[arg-type]
        except Exception:
            logger.exception("knowledge_gap_capture_failed")
            return None


__all__ = ["MAX_CLARIFICATION_ATTEMPTS", "KnowledgeGapCaptureService"]
