"""Phase 19 Step 19/20 -- advisory RAG/training handoff eligibility.

Both outputs are boolean + reason-code flags only. This service never
creates a RAG source, never starts a RAG sandbox trial, never creates
a training dataset, and never starts a training run -- Phase 24/future
phases own the actual bridges. `eligible_for_rag_research=True` still
requires a separate, existing source-rights review before anything
downstream happens; this service only decides whether a case is even
worth that review.
"""

from __future__ import annotations

from backend.core.config import Settings
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

_MIN_REPRODUCIBLE_FREQUENCY = 2
_VOLATILE_FRESHNESS = frozenset({"time_sensitive", "real_time"})

_RAG_ELIGIBLE_REASONS = frozenset(
    {"rag_content_missing", "rag_retrieval_insufficient", "domain_understanding_missing",
     "model_knowledge_missing"}
)

_TRAINING_ELIGIBLE_REASONS = frozenset(
    {"tamil_grammar", "tamil_meaning", "tamil_orthography", "tamil_instruction_following",
     "tanglish_comprehension", "tamil_ambiguity_handling", "wrong_output_language",
     "domain_understanding_missing", "answer_quality_failure"}
)

_TRAINING_INELIGIBLE_EVENT_TYPES = frozenset(
    {"web_capability_gap", "tool_capability_gap", "operational_failure", "safety_event",
     "source_failure"}
)


class KnowledgeGapHandoffAssessmentService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)

    def assess(self, case_public_id: str) -> dict[str, object]:
        case = self.repository.get_case(case_public_id)

        rag_research = False
        rag_trial = False
        rag_reasons: list[str] = []
        if (
            case["event_type"] == "knowledge_gap"
            and not case["content_unavailable_for_review"]
            and case["canonical_question"]
            and any(code in _RAG_ELIGIBLE_REASONS for code in case["reason_codes"])
        ):
            if case["freshness"] in _VOLATILE_FRESHNESS:
                rag_reasons.append("volatile_freshness_excluded_from_permanent_rag")
            else:
                rag_research = True
                rag_reasons.append("static_knowledge_gap_with_missing_rag_evidence")
                if case["frequency"] >= _MIN_REPRODUCIBLE_FREQUENCY:
                    rag_trial = True
                    rag_reasons.append("reproducible_across_multiple_occurrences")

        training_assessment = False
        training_reasons: list[str] = []
        if (
            case["event_type"] not in _TRAINING_INELIGIBLE_EVENT_TYPES
            and not case["content_unavailable_for_review"]
            and case["frequency"] >= _MIN_REPRODUCIBLE_FREQUENCY
            and case["freshness"] not in _VOLATILE_FRESHNESS
            and any(code in _TRAINING_ELIGIBLE_REASONS for code in case["reason_codes"])
        ):
            training_assessment = True
            training_reasons.append("repeatable_language_or_reasoning_capability_failure")

        return self.repository.update_case_handoff_eligibility(
            case_public_id,
            rag_research=rag_research,
            rag_trial=rag_trial,
            rag_reason_codes=rag_reasons,
            training_assessment=training_assessment,
            training_reason_codes=training_reasons,
        )


__all__ = ["KnowledgeGapHandoffAssessmentService"]
