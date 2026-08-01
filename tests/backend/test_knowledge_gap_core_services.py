"""Phase 19 Step 34 -- pure-function-level tests for eligibility,
privacy/redaction, canonicalization, clustering, and priority scoring.
No database involved; these are all deterministic pure services."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.services.knowledge_gap_canonicalization_service import (
    KnowledgeGapCanonicalizationService,
)
from backend.services.knowledge_gap_clustering_service import (
    ClusterCandidate,
    KnowledgeGapClusteringService,
)
from backend.services.knowledge_gap_priority_service import (
    KnowledgeGapPriorityService,
    PriorityInput,
)
from backend.services.knowledge_gap_privacy_service import KnowledgeGapPrivacyService
from core_model.knowledge_gap.eligibility import determine_gap_eligibility

# -- eligibility ------------------------------------------------------------------------------


def test_model_knowledge_missing_is_eligible_knowledge_gap() -> None:
    result = determine_gap_eligibility(
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        fallbacks_attempted=(),
    )
    assert result.event_type == "knowledge_gap"
    assert result.eligible_for_gap_registry is True


def test_rag_missing_evidence_is_eligible_knowledge_gap() -> None:
    result = determine_gap_eligibility(
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="insufficient",
        fallbacks_attempted=("rag_scope_unavailable",),
    )
    assert result.event_type == "knowledge_gap"
    assert "rag_content_missing" in result.reason_codes
    assert result.eligible_for_gap_registry is True


def test_low_confidence_alone_without_feedback_is_not_auto_captured() -> None:
    result = determine_gap_eligibility(
        resolved_route="core_model",
        safety_status="safe",
        evidence_status="none",
        confidence_band="low",
    )
    assert result.eligible_for_gap_registry is False


def test_low_confidence_with_negative_feedback_is_eligible() -> None:
    result = determine_gap_eligibility(
        resolved_route="core_model",
        safety_status="safe",
        evidence_status="insufficient",
        confidence_band="low",
        negative_feedback_reason="wrong_answer",
    )
    assert result.eligible_for_gap_registry is True
    assert result.event_type == "feedback_issue"


def test_outdated_information_web_unavailable_is_capability_gap() -> None:
    result = determine_gap_eligibility(
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        fallbacks_attempted=("trusted_web_unavailable",),
    )
    assert result.event_type == "web_capability_gap"
    assert result.eligible_for_gap_registry is True


def test_tool_unavailable_is_capability_gap() -> None:
    result = determine_gap_eligibility(
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        fallbacks_attempted=("tool_unavailable",),
    )
    assert result.event_type == "tool_capability_gap"


def test_wrong_language_feedback_is_language_failure() -> None:
    result = determine_gap_eligibility(
        resolved_route="core_model",
        safety_status="safe",
        evidence_status="model_only",
        negative_feedback_reason="wrong_language",
    )
    assert result.event_type == "language_failure"
    assert result.eligible_for_gap_registry is True


def test_safety_refusal_is_excluded_from_knowledge_gap_registry() -> None:
    result = determine_gap_eligibility(
        resolved_route="refuse", safety_status="refused", evidence_status="none"
    )
    assert result.event_type == "safety_event"
    assert result.eligible_for_gap_registry is False
    assert result.retention_policy == "not_retained"


def test_output_safety_block_is_safety_event() -> None:
    result = determine_gap_eligibility(
        resolved_route="insufficient",
        safety_status="output_blocked",
        evidence_status="none",
        fallbacks_attempted=("output_safety_blocked",),
    )
    assert result.event_type == "safety_event"
    assert result.eligible_for_gap_registry is False


def test_operational_failure_is_separated_from_knowledge_gap() -> None:
    result = determine_gap_eligibility(
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        fallbacks_attempted=("model_assignment_unavailable",),
    )
    assert result.event_type == "operational_failure"
    assert result.event_type != "knowledge_gap"


def test_clarification_first_attempt_is_not_yet_a_reviewable_gap() -> None:
    result = determine_gap_eligibility(
        resolved_route="clarify",
        safety_status="safe",
        evidence_status="none",
        clarification_required=True,
    )
    assert result.event_type == "clarification_event"
    assert result.review_required is False


def test_clarification_unresolved_after_attempts_becomes_knowledge_gap() -> None:
    result = determine_gap_eligibility(
        resolved_route="clarify",
        safety_status="safe",
        evidence_status="none",
        clarification_required=True,
        unresolved_after_clarification=True,
    )
    assert result.event_type == "knowledge_gap"
    assert "unresolved_after_clarification" in result.reason_codes
    assert result.eligible_for_gap_registry is True


def test_successful_answer_is_not_applicable_and_not_eligible() -> None:
    result = determine_gap_eligibility(
        resolved_route="core_model",
        safety_status="safe",
        evidence_status="model_only",
        confidence_band="medium",
    )
    assert result.event_type == "not_applicable"
    assert result.eligible_for_gap_registry is False


# -- privacy ----------------------------------------------------------------------------------


@pytest.fixture
def privacy_service() -> KnowledgeGapPrivacyService:
    return KnowledgeGapPrivacyService()


def test_phone_number_is_redacted(privacy_service: KnowledgeGapPrivacyService) -> None:
    result = privacy_service.process("call me at 9876543210 please")
    assert "9876543210" not in result.redacted_question
    assert "[PHONE]" in result.redacted_question


def test_email_is_redacted(privacy_service: KnowledgeGapPrivacyService) -> None:
    result = privacy_service.process("reach me at test@example.com")
    assert "test@example.com" not in result.redacted_question
    assert "[EMAIL]" in result.redacted_question


def test_address_is_redacted(privacy_service: KnowledgeGapPrivacyService) -> None:
    result = privacy_service.process("I live at 42 Gandhi Road near the signal")
    assert "[ADDRESS]" in result.redacted_question


def test_identifier_like_aadhaar_is_redacted(privacy_service: KnowledgeGapPrivacyService) -> None:
    result = privacy_service.process("my id number is 1234 5678 9012")
    assert "1234 5678 9012" not in result.redacted_question
    assert "[IDENTIFIER]" in result.redacted_question


def test_credential_falls_back_to_hash_only(privacy_service: KnowledgeGapPrivacyService) -> None:
    result = privacy_service.process("password: Sup3rSecret! help me log in")
    assert result.content_unavailable_for_review is True
    assert result.redacted_question is None
    assert result.input_hash


def test_private_memory_context_is_redacted_when_memory_involved(
    privacy_service: KnowledgeGapPrivacyService,
) -> None:
    result = privacy_service.process(
        "what about that thing i told you earlier?", involves_memory=True
    )
    assert "[PRIVATE_CONTEXT]" in result.redacted_question


def test_redaction_failure_falls_back_to_hash_only(
    privacy_service: KnowledgeGapPrivacyService,
) -> None:
    result = privacy_service.process("use sk-abcdefghijklmnopqrstuvwxyz123456 to authenticate")
    assert result.content_unavailable_for_review is True
    assert result.redacted_question is None


def test_ordinary_question_is_retained_unmodified(
    privacy_service: KnowledgeGapPrivacyService,
) -> None:
    result = privacy_service.process("தமிழில் பெயர்ச்சொல் என்றால் என்ன?")
    assert result.content_unavailable_for_review is False
    assert result.redacted_question == "தமிழில் பெயர்ச்சொல் என்றால் என்ன?"


# -- canonicalization ---------------------------------------------------------------------------


@pytest.fixture
def canon_service() -> KnowledgeGapCanonicalizationService:
    return KnowledgeGapCanonicalizationService()


def test_tamil_text_preserved_untouched(canon_service: KnowledgeGapCanonicalizationService) -> None:
    result = canon_service.canonicalize("தமிழில் பெயர்ச்சொல் என்றால் என்ன?", language_category="ta")
    assert "தமிழில்" in result.canonical_question


def test_english_text_is_lowercased(canon_service: KnowledgeGapCanonicalizationService) -> None:
    result = canon_service.canonicalize(
        "What Is The Latest Python Version?", language_category="en"
    )
    assert result.canonical_question == "what is the latest python version?"


def test_punctuation_variants_are_normalized(
    canon_service: KnowledgeGapCanonicalizationService,
) -> None:
    result = canon_service.canonicalize("what's the version…", language_category="en")
    assert "…" not in result.canonical_question
    assert "..." in result.canonical_question


def test_whitespace_is_collapsed(canon_service: KnowledgeGapCanonicalizationService) -> None:
    result = canon_service.canonicalize("what   is    the version", language_category="en")
    assert result.canonical_question == "what is the version"


def test_unicode_is_nfc_normalized(canon_service: KnowledgeGapCanonicalizationService) -> None:
    combining = "é"  # "e" + combining acute accent
    result = canon_service.canonicalize(combining, language_category="en")
    assert result.canonical_question == "é"


def test_semantic_distinction_preserved_between_current_and_definition_question(
    canon_service: KnowledgeGapCanonicalizationService,
) -> None:
    current = canon_service.canonicalize("latest python version", language_category="en")
    definition = canon_service.canonicalize("python version means what", language_category="en")
    assert current.canonical_question != definition.canonical_question


# -- clustering -----------------------------------------------------------------------------------


@pytest.fixture
def clustering_service() -> KnowledgeGapClusteringService:
    return KnowledgeGapClusteringService()


def test_exact_duplicate_is_same_case(clustering_service: KnowledgeGapClusteringService) -> None:
    candidates = [
        ClusterCandidate(
            "c1",
            "what is the latest python version",
            "en",
            "software",
            "ask_current_status",
            "time_sensitive",
        ),
        ClusterCandidate(
            "c2",
            "what is the latest python version",
            "en",
            "software",
            "ask_current_status",
            "time_sensitive",
        ),
    ]
    decisions = clustering_service.find_cluster_decisions(candidates)
    assert len(decisions) == 1
    assert decisions[0].decision == "same_case"


def test_normalized_duplicate_with_whitespace_variance(
    clustering_service: KnowledgeGapClusteringService,
) -> None:
    candidates = [
        ClusterCandidate(
            "c1",
            "what is  the latest python version",
            "en",
            "software",
            "ask_current_status",
            "time_sensitive",
        ),
        ClusterCandidate(
            "c2",
            "what is the latest python version",
            "en",
            "software",
            "ask_current_status",
            "time_sensitive",
        ),
    ]
    decisions = clustering_service.find_cluster_decisions(candidates)
    assert len(decisions) == 1
    assert decisions[0].decision in ("same_case", "probable_duplicate")


def test_near_duplicate_requires_review_not_auto_merge(
    clustering_service: KnowledgeGapClusteringService,
) -> None:
    candidates = [
        ClusterCandidate(
            "c1",
            "what is the latest stable python release version available today",
            "en",
            "software",
            "ask_current_status",
            "time_sensitive",
        ),
        ClusterCandidate(
            "c2",
            "what is the latest stable python release version out there today",
            "en",
            "software",
            "ask_current_status",
            "time_sensitive",
        ),
    ]
    decisions = clustering_service.find_cluster_decisions(candidates)
    if decisions:
        assert decisions[0].decision == "possible_duplicate"


def test_current_version_vs_stable_definition_stay_distinct(
    clustering_service: KnowledgeGapClusteringService,
) -> None:
    candidates = [
        ClusterCandidate(
            "c1", "latest python version", "en", "software", "ask_current_status", "time_sensitive"
        ),
        ClusterCandidate(
            "c2", "python version means what", "en", "software", "ask_definition", "timeless"
        ),
    ]
    decisions = clustering_service.find_cluster_decisions(candidates)
    assert decisions == []


def test_merge_only_returns_decisions_never_mutates_input(
    clustering_service: KnowledgeGapClusteringService,
) -> None:
    candidates = [
        ClusterCandidate("c1", "same question here", "en", "d", "i", "f"),
        ClusterCandidate("c2", "same question here", "en", "d", "i", "f"),
    ]
    before = list(candidates)
    clustering_service.find_cluster_decisions(candidates)
    assert candidates == before


# -- priority ---------------------------------------------------------------------------------


@pytest.fixture
def priority_service() -> KnowledgeGapPriorityService:
    return KnowledgeGapPriorityService()


def test_higher_frequency_yields_higher_score(
    priority_service: KnowledgeGapPriorityService,
) -> None:
    now = datetime.now(UTC)
    low = priority_service.score(
        PriorityInput(event_type="knowledge_gap", reason_codes=(), frequency=1, last_seen_at=now)
    )
    high = priority_service.score(
        PriorityInput(event_type="knowledge_gap", reason_codes=(), frequency=15, last_seen_at=now)
    )
    assert high.priority_score > low.priority_score


def test_recent_occurrence_scores_higher_than_stale(
    priority_service: KnowledgeGapPriorityService,
) -> None:
    now = datetime.now(UTC)
    recent = priority_service.score(
        PriorityInput(
            event_type="knowledge_gap",
            reason_codes=(),
            frequency=3,
            last_seen_at=now - timedelta(hours=1),
        )
    )
    stale = priority_service.score(
        PriorityInput(
            event_type="knowledge_gap",
            reason_codes=(),
            frequency=3,
            last_seen_at=now - timedelta(days=90),
        )
    )
    assert recent.priority_score > stale.priority_score


def test_tamil_capability_reason_gets_boost(priority_service: KnowledgeGapPriorityService) -> None:
    now = datetime.now(UTC)
    result = priority_service.score(
        PriorityInput(
            event_type="language_failure",
            reason_codes=("tamil_grammar",),
            frequency=2,
            last_seen_at=now,
        )
    )
    assert "TAMIL_FIRST_PRIORITY_APPLIED" in result.priority_reason_codes


def test_tamil_current_affairs_does_not_get_tamil_boost(
    priority_service: KnowledgeGapPriorityService,
) -> None:
    now = datetime.now(UTC)
    result = priority_service.score(
        PriorityInput(
            event_type="web_capability_gap",
            reason_codes=("web_search_unavailable",),
            frequency=2,
            last_seen_at=now,
        )
    )
    assert "TAMIL_FIRST_PRIORITY_APPLIED" not in result.priority_reason_codes


def test_wrong_language_severity_contributes_to_score(
    priority_service: KnowledgeGapPriorityService,
) -> None:
    now = datetime.now(UTC)
    with_feedback = priority_service.score(
        PriorityInput(
            event_type="language_failure",
            reason_codes=(),
            frequency=1,
            last_seen_at=now,
            negative_feedback_reasons=("wrong_language",),
        )
    )
    without_feedback = priority_service.score(
        PriorityInput(event_type="language_failure", reason_codes=(), frequency=1, last_seen_at=now)
    )
    assert with_feedback.priority_score > without_feedback.priority_score


def test_repeated_rag_failure_increases_score(
    priority_service: KnowledgeGapPriorityService,
) -> None:
    now = datetime.now(UTC)
    repeated = priority_service.score(
        PriorityInput(
            event_type="knowledge_gap",
            reason_codes=(),
            frequency=1,
            last_seen_at=now,
            repeated_rag_failure_count=4,
        )
    )
    once = priority_service.score(
        PriorityInput(event_type="knowledge_gap", reason_codes=(), frequency=1, last_seen_at=now)
    )
    assert repeated.priority_score > once.priority_score
    assert "repeated_rag_failure" in repeated.priority_reason_codes


def test_privacy_risk_is_a_penalty(priority_service: KnowledgeGapPriorityService) -> None:
    now = datetime.now(UTC)
    risky = priority_service.score(
        PriorityInput(
            event_type="knowledge_gap",
            reason_codes=(),
            frequency=5,
            last_seen_at=now,
            privacy_risk=True,
        )
    )
    safe = priority_service.score(
        PriorityInput(event_type="knowledge_gap", reason_codes=(), frequency=5, last_seen_at=now)
    )
    assert risky.priority_score < safe.priority_score
    assert "penalty_privacy_risk" in risky.priority_reason_codes


def test_priority_scoring_is_deterministic(priority_service: KnowledgeGapPriorityService) -> None:
    now = datetime.now(UTC)
    inputs = PriorityInput(
        event_type="knowledge_gap", reason_codes=("tamil_grammar",), frequency=4, last_seen_at=now
    )
    first = priority_service.score(inputs, now=now)
    second = priority_service.score(inputs, now=now)
    assert first == second


def test_critical_priority_result_has_no_resolution_flag() -> None:
    """A critical priority score alone must never carry any
    resolution/training/RAG-approval semantics -- `PriorityResult` has
    no such field at all, which this test locks in structurally."""

    from dataclasses import fields

    field_names = {
        f.name
        for f in fields(
            __import__(
                "backend.services.knowledge_gap_priority_service", fromlist=["PriorityResult"]
            ).PriorityResult
        )
    }
    assert field_names == {"priority_score", "priority_band", "priority_reason_codes"}
