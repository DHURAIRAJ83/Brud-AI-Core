"""MB-23: pure-module unit tests for core_model/mini_brain/public_chat_runtime/.

Covers session hashing, conversation window bounding, query
classification/topic normalization, tool/RAG/vision usage derivation,
response safety escalation, gap detection, feedback signal extraction,
failure clustering, candidate building, priority ranking, admin
handoff construction, report generation, and -- per the task spec's
own Step 13 -- explicit sanitization tests for every named privacy
category: emails, phone numbers, URLs carrying a token, API keys,
JWTs, access tokens, filesystem paths, and database identifiers.
"""

import pytest

from core_model.mini_brain.public_chat_runtime.admin_handoff_builder import build_admin_handoff
from core_model.mini_brain.public_chat_runtime.conversation_window import (
    MAX_MESSAGE_CHARACTERS,
    bound_window,
    cap_message_size,
)
from core_model.mini_brain.public_chat_runtime.failure_clusterer import cluster_failures
from core_model.mini_brain.public_chat_runtime.feedback_sanitizer import sanitize_text
from core_model.mini_brain.public_chat_runtime.feedback_signal_extractor import extract_feedback_signals
from core_model.mini_brain.public_chat_runtime.gap_detector import (
    detect_explicit_negative,
    detect_gaps,
    detect_insufficient_evidence,
    detect_low_confidence,
    detect_repeated_question,
)
from core_model.mini_brain.public_chat_runtime.improvement_candidate_builder import (
    build_candidate,
    compute_impact_score,
    dominant_signal_type,
    recommend_action,
)
from core_model.mini_brain.public_chat_runtime.priority_ranker import compute_priority_score, rank_candidates
from core_model.mini_brain.public_chat_runtime.query_classifier import classify_query, normalize_topic_key
from core_model.mini_brain.public_chat_runtime.rag_orchestrator import derive_rag_usage
from core_model.mini_brain.public_chat_runtime.response_safety_filter import evaluate_response_safety
from core_model.mini_brain.public_chat_runtime.runtime_report_generator import (
    generate_runtime_analytics_summary,
    generate_session_report,
)
from core_model.mini_brain.public_chat_runtime.session_builder import build_session, hash_client_key
from core_model.mini_brain.public_chat_runtime.tool_routing_policy import derive_tool_usage
from core_model.mini_brain.public_chat_runtime.vision_request_router import derive_vision_usage

# -- session_builder -------------------------------------------------------------------------


def test_hash_client_key_is_deterministic() -> None:
    first = hash_client_key(raw_client_key="1.2.3.4", salt="pepper")
    second = hash_client_key(raw_client_key="1.2.3.4", salt="pepper")
    assert first == second
    assert len(first) == 64


def test_hash_client_key_differs_by_salt() -> None:
    a = hash_client_key(raw_client_key="1.2.3.4", salt="pepper1")
    b = hash_client_key(raw_client_key="1.2.3.4", salt="pepper2")
    assert a != b


def test_hash_client_key_rejects_empty_inputs() -> None:
    with pytest.raises(ValueError):
        hash_client_key(raw_client_key="", salt="pepper")
    with pytest.raises(ValueError):
        hash_client_key(raw_client_key="1.2.3.4", salt="")


def test_build_session_never_includes_raw_client_key() -> None:
    session = build_session(raw_client_key="203.0.113.9", salt="pepper", language="en")
    assert "203.0.113.9" not in str(session)
    assert session["status"] == "active"
    assert session["message_count"] == 0


def test_build_session_falls_back_to_auto_for_unsupported_language() -> None:
    session = build_session(raw_client_key="203.0.113.9", salt="pepper", language="fr")
    assert session["language"] == "auto"


# -- conversation_window -------------------------------------------------------------------------


def test_bound_window_truncates_to_most_recent() -> None:
    messages = [{"i": i} for i in range(30)]
    result = bound_window(messages=messages, window_size=10)
    assert result["truncated"] is True
    assert result["returned_count"] == 10
    assert result["messages"][-1]["i"] == 29


def test_bound_window_no_truncation_when_within_bound() -> None:
    messages = [{"i": i} for i in range(5)]
    result = bound_window(messages=messages, window_size=10)
    assert result["truncated"] is False
    assert result["returned_count"] == 5


def test_bound_window_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError):
        bound_window(messages=[], window_size=0)


def test_cap_message_size_truncates_oversized_text() -> None:
    result = cap_message_size(text="x" * (MAX_MESSAGE_CHARACTERS + 500))
    assert result["capped"] is True
    assert len(result["text"]) == MAX_MESSAGE_CHARACTERS


def test_cap_message_size_leaves_short_text_untouched() -> None:
    result = cap_message_size(text="hello")
    assert result["capped"] is False
    assert result["text"] == "hello"


# -- query_classifier -------------------------------------------------------------------------


def test_classify_query_detects_vision_keyword() -> None:
    result = classify_query(text="what is in this photo?")
    assert result["category"] == "vision"


def test_classify_query_detects_tool_keyword() -> None:
    result = classify_query(text="please calculate 12 plus 30")
    assert result["category"] == "tool"


def test_classify_query_falls_back_to_factual_for_question_mark() -> None:
    result = classify_query(text="what is the capital of India?")
    assert result["category"] == "factual"


def test_normalize_topic_key_strips_stopwords_and_punctuation() -> None:
    key = normalize_topic_key(text="What is the capital of Tamil Nadu?")
    assert key == "capital tamil nadu"


def test_normalize_topic_key_is_deterministic() -> None:
    a = normalize_topic_key(text="Where is the river?")
    b = normalize_topic_key(text="Where is the river?")
    assert a == b


def test_normalize_topic_key_handles_stopword_only_text() -> None:
    key = normalize_topic_key(text="what is the")
    assert key  # never empty -- falls back rather than raising


# -- tool_routing_policy / rag_orchestrator / vision_request_router -----------------------------


def test_derive_tool_usage_true_when_tool_route() -> None:
    result = derive_tool_usage(route_used="tool", tool_name="calculator", tool_status="success")
    assert result["used_tool"] is True
    assert result["tool_succeeded"] is True


def test_derive_tool_usage_false_without_tool_signal() -> None:
    result = derive_tool_usage(route_used="approved_rag", tool_name=None, tool_status=None)
    assert result["used_tool"] is False


def test_derive_rag_usage_sufficient_evidence() -> None:
    result = derive_rag_usage(source_types=["rag"], evidence_status="grounded", citation_count=3, insufficient_evidence=False)
    assert result["used_rag"] is True
    assert result["evidence_sufficient"] is True


def test_derive_rag_usage_insufficient_evidence() -> None:
    result = derive_rag_usage(source_types=[], evidence_status="insufficient", citation_count=0, insufficient_evidence=True)
    assert result["used_rag"] is False
    assert result["evidence_sufficient"] is False


def test_derive_vision_usage_from_query_category() -> None:
    result = derive_vision_usage(query_category="vision", source_types=[])
    assert result["used_vision"] is True


def test_derive_vision_usage_false_otherwise() -> None:
    result = derive_vision_usage(query_category="factual", source_types=["rag"])
    assert result["used_vision"] is False


# -- response_safety_filter -------------------------------------------------------------------------


def test_evaluate_response_safety_escalates_on_review_flagged() -> None:
    result = evaluate_response_safety(safety_status="review_flagged")
    assert result["escalate_severity"] is True
    assert result["raise_safety_flag_signal"] is True


def test_evaluate_response_safety_no_escalation_when_safe() -> None:
    result = evaluate_response_safety(safety_status="safe")
    assert result["escalate_severity"] is False
    assert result["raise_safety_flag_signal"] is False


# -- feedback_sanitizer -- Step 13's own explicitly-named privacy categories --------------------


def test_sanitize_text_redacts_email() -> None:
    result = sanitize_text(raw_text="reach me at jane.doe@example.com please")
    assert "jane.doe@example.com" not in result["sanitized_text"]
    assert "email" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_phone_number() -> None:
    result = sanitize_text(raw_text="call me at 555-234-9876 tomorrow")
    assert "555-234-9876" not in result["sanitized_text"]
    assert "phone_number" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_url_with_token() -> None:
    result = sanitize_text(raw_text="see https://example.com/reset?token=abcd1234xyz for details")
    assert "abcd1234xyz" not in result["sanitized_text"]
    assert "url_with_token" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_api_key() -> None:
    result = sanitize_text(raw_text="my api_key=sk-abc123def456 is not working")
    assert "sk-abc123def456" not in result["sanitized_text"]
    assert "secret_like_content" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_jwt() -> None:
    fake_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    result = sanitize_text(raw_text=f"here is my token {fake_jwt}")
    assert fake_jwt not in result["sanitized_text"]
    assert "jwt" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_bearer_access_token() -> None:
    result = sanitize_text(raw_text="Authorization: Bearer abcdef1234567890xyz")
    assert "abcdef1234567890xyz" not in result["sanitized_text"]
    assert "access_token" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_filesystem_path() -> None:
    result = sanitize_text(raw_text="the error is in /home/dhurai/secrets/config.yaml")
    assert "/home/dhurai/secrets" not in result["sanitized_text"]
    assert "filesystem_path" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_database_identifier_uuid() -> None:
    result = sanitize_text(raw_text="my record is 123e4567-e89b-12d3-a456-426614174000")
    assert "123e4567-e89b-12d3-a456-426614174000" not in result["sanitized_text"]
    assert "database_identifier_uuid" in result["redaction_categories_applied"]


def test_sanitize_text_redacts_database_identifier_numeric() -> None:
    result = sanitize_text(raw_text="please check record_id=48213 for me")
    assert "48213" not in result["sanitized_text"]
    assert "database_identifier_numeric" in result["redaction_categories_applied"]


def test_sanitize_text_truncates_oversized_payload() -> None:
    result = sanitize_text(raw_text="x" * 5000)
    assert result["truncated"] is True
    assert "truncated_oversized_payload" in result["redaction_categories_applied"]


def test_sanitize_text_leaves_clean_text_unchanged() -> None:
    result = sanitize_text(raw_text="what is a noun in Tamil grammar?")
    assert result["changed"] is False
    assert result["sanitized_text"] == "what is a noun in Tamil grammar?"


def test_sanitize_text_never_returns_original_when_redacted() -> None:
    result = sanitize_text(raw_text="email me at a@b.com")
    assert result["sanitized_text"] != "email me at a@b.com"
    assert result["original_hash_sha256"] != result["sanitized_hash_sha256"]


# -- gap_detector -------------------------------------------------------------------------


def test_detect_explicit_negative_matches_known_phrase() -> None:
    result = detect_explicit_negative(sanitized_user_text="that is wrong, try again")
    assert result["detected"] is True


def test_detect_explicit_negative_no_match_on_neutral_text() -> None:
    result = detect_explicit_negative(sanitized_user_text="thanks, that helps")
    assert result["detected"] is False


def test_detect_low_confidence_true_for_low_band() -> None:
    assert detect_low_confidence(confidence_band="low")["detected"] is True
    assert detect_low_confidence(confidence_band="high")["detected"] is False


def test_detect_insufficient_evidence_true_when_flagged() -> None:
    assert detect_insufficient_evidence(evidence_sufficient=False, insufficient_evidence_flag=True)["detected"] is True
    assert detect_insufficient_evidence(evidence_sufficient=True, insufficient_evidence_flag=False)["detected"] is False


def test_detect_repeated_question_true_at_threshold() -> None:
    result = detect_repeated_question(current_topic_key="capital tamil nadu", recent_topic_keys=["capital tamil nadu", "capital tamil nadu"], threshold=2)
    assert result["detected"] is True
    assert result["occurrences"] == 2


def test_detect_gaps_combines_all_rules() -> None:
    signals = detect_gaps(
        sanitized_user_text="that is wrong", confidence_band="low", evidence_sufficient=False,
        insufficient_evidence_flag=True, current_topic_key="k", recent_topic_keys=["k", "k"],
    )
    signal_types = {s["signal_type"] for s in signals}
    assert signal_types == {"explicit_negative", "low_confidence", "insufficient_evidence", "repeated_question"}


def test_detect_gaps_empty_for_clean_confident_answer() -> None:
    signals = detect_gaps(
        sanitized_user_text="thanks that helps", confidence_band="high", evidence_sufficient=True,
        insufficient_evidence_flag=False, current_topic_key="k", recent_topic_keys=[],
    )
    assert signals == []


# -- feedback_signal_extractor -------------------------------------------------------------------------


def test_extract_feedback_signals_escalates_severity_on_safety_flag() -> None:
    gap_signals = [{"signal_type": "low_confidence", "severity": "medium", "reason": "r"}]
    safety_evaluation = {"escalate_severity": True, "raise_safety_flag_signal": True, "safety_status": "review_flagged"}
    signals = extract_feedback_signals(
        sanitized_text="text", topic_key="k", gap_signals=gap_signals, safety_evaluation=safety_evaluation,
    )
    assert any(s["signal_type"] == "safety_flag" for s in signals)
    low_confidence_signal = next(s for s in signals if s["signal_type"] == "low_confidence")
    assert low_confidence_signal["severity"] == "high"


def test_extract_feedback_signals_no_escalation_when_safe() -> None:
    gap_signals = [{"signal_type": "low_confidence", "severity": "medium", "reason": "r"}]
    safety_evaluation = {"escalate_severity": False, "raise_safety_flag_signal": False, "safety_status": "safe"}
    signals = extract_feedback_signals(
        sanitized_text="text", topic_key="k", gap_signals=gap_signals, safety_evaluation=safety_evaluation,
    )
    assert len(signals) == 1
    assert signals[0]["severity"] == "medium"


# -- failure_clusterer -------------------------------------------------------------------------


def test_cluster_failures_groups_by_topic_key() -> None:
    signals = [
        {"topic_key": "k1", "session_id": 1, "severity": "high", "signal_type": "explicit_negative", "normalized_text": "a", "created_at": "2026-01-01"},
        {"topic_key": "k1", "session_id": 2, "severity": "medium", "signal_type": "low_confidence", "normalized_text": "b", "created_at": "2026-01-02"},
        {"topic_key": "k2", "session_id": 1, "severity": "low", "signal_type": "low_confidence", "normalized_text": "c", "created_at": "2026-01-01"},
    ]
    clusters = cluster_failures(signals=signals)
    assert clusters[0]["topic_key"] == "k1"
    assert clusters[0]["frequency"] == 2
    assert clusters[0]["distinct_session_count"] == 2
    assert clusters[0]["most_recent_at"] == "2026-01-02"


def test_cluster_failures_empty_input() -> None:
    assert cluster_failures(signals=[]) == []


# -- improvement_candidate_builder -------------------------------------------------------------------------


def test_compute_impact_score_weights_severity() -> None:
    score = compute_impact_score(severity_counts={"low": 1, "medium": 1, "high": 1})
    assert score == 6.0


def test_dominant_signal_type_picks_highest_count() -> None:
    assert dominant_signal_type(signal_type_counts={"low_confidence": 1, "explicit_negative": 3}) == "explicit_negative"


def test_dominant_signal_type_empty_returns_unclassified() -> None:
    assert dominant_signal_type(signal_type_counts={}) == "unclassified"


def test_recommend_action_known_mapping() -> None:
    assert recommend_action(signal_type="repeated_question") == "mb18_package_refresh"
    assert recommend_action(signal_type="safety_flag") == "mb21_external_evaluation"


def test_build_candidate_is_born_pending_admin_review() -> None:
    cluster = {
        "topic_key": "capital tamil nadu", "frequency": 3, "distinct_session_count": 2,
        "severity_counts": {"low": 0, "medium": 1, "high": 2}, "signal_type_counts": {"explicit_negative": 2, "low_confidence": 1},
        "most_recent_at": "2026-01-01", "example_texts": ["what is the capital"],
    }
    candidate = build_candidate(cluster=cluster)
    assert candidate["status"] == "pending_admin_review"
    assert candidate["topic"] == "Capital Tamil Nadu"
    assert candidate["recommended_action"] == "mb13_cleanup"


# -- priority_ranker -------------------------------------------------------------------------


def test_compute_priority_score_increases_with_frequency() -> None:
    now = 1_700_000_000.0
    low = compute_priority_score(
        frequency=1, distinct_session_count=1, most_recent_at_epoch_seconds=now, now_epoch_seconds=now,
        unresolved_rate=0.0, dissatisfaction_rate=0.0,
    )
    high = compute_priority_score(
        frequency=10, distinct_session_count=10, most_recent_at_epoch_seconds=now, now_epoch_seconds=now,
        unresolved_rate=0.5, dissatisfaction_rate=0.5,
    )
    assert high["priority_score"] > low["priority_score"]


def test_compute_priority_score_rejects_out_of_range_rates() -> None:
    with pytest.raises(ValueError):
        compute_priority_score(
            frequency=1, distinct_session_count=1, most_recent_at_epoch_seconds=0, now_epoch_seconds=0,
            unresolved_rate=1.5, dissatisfaction_rate=0.0,
        )


def test_rank_candidates_orders_by_priority_score_descending() -> None:
    candidates = [{"priority_score": 1.0}, {"priority_score": 5.0}, {"priority_score": 3.0}]
    ranked = rank_candidates(candidates=candidates)
    assert [c["priority_score"] for c in ranked] == [5.0, 3.0, 1.0]


# -- admin_handoff_builder -------------------------------------------------------------------------


def test_build_admin_handoff_is_advisory_only() -> None:
    handoff = build_admin_handoff(
        topic="Capital Tamil Nadu", topic_key="capital tamil nadu", frequency=3, priority_score=10.0,
        recommended_action="mb16_dataset_draft", example_questions=["what is the capital"],
        suggested_missing_knowledge={"topic_key": "capital tamil nadu"},
    )
    assert handoff["advisory_only"] is True
    assert handoff["recommended_next_phase"] == "MB-16 dataset draft"


def test_build_admin_handoff_falls_back_for_unknown_action() -> None:
    handoff = build_admin_handoff(
        topic="t", topic_key="k", frequency=1, priority_score=1.0, recommended_action="bogus_action",
        example_questions=[], suggested_missing_knowledge={},
    )
    assert handoff["recommended_next_phase"] == "MB-13 cleanup"


# -- runtime_report_generator -------------------------------------------------------------------------


def test_generate_session_report_discloses_no_automatic_training() -> None:
    report = generate_session_report(
        session_public_id="s1", message_count=4, used_rag_count=2, used_vision_count=0, used_tool_count=0,
        signal_counts_by_type={"low_confidence": 1}, satisfaction_score=0.8, unresolved_count=0,
        started_at="t0", ended_at="t1",
    )
    assert report["no_automatic_learning_occurred"] is True
    assert report["no_automatic_training_occurred"] is True


def test_generate_runtime_analytics_summary_discloses_heuristics() -> None:
    summary = generate_runtime_analytics_summary(
        total_sessions=5, total_messages=20, total_signals_by_type={"low_confidence": 3},
        top_candidates=[], generated_at="now",
    )
    assert summary["clustering_is_heuristic"] is True
    assert summary["ranking_is_heuristic"] is True
