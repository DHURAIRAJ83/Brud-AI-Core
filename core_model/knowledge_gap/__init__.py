"""Phase 19 Knowledge-Gap Registry taxonomy. Single source of truth
for every enum the gap-capture/classification/clustering/priority
pipeline uses -- mirrors `core_model/public_chat/__init__.py` (Phase
18) and `core_model/knowledge_routing/__init__.py` (Phase 17) exactly.

Every event class below is independent -- never merged into one
generic "failure" field (Step 2's explicit requirement). A `knowledge_gap`
is a *factual* gap; the other nine top-level types exist precisely so
that safety refusals, temporary operational incidents, ambiguity, and
capability gaps are never miscounted as one.
"""

from __future__ import annotations

POLICY_VERSION = "v1"

# -- top-level event types (Step 2)

EVENT_TYPES = (
    "knowledge_gap",
    "clarification_event",
    "safety_event",
    "operational_failure",
    "language_failure",
    "source_failure",
    "tool_capability_gap",
    "web_capability_gap",
    "feedback_issue",
    "not_applicable",
)

# -- per-event-type reason codes (Step 2)

KNOWLEDGE_GAP_REASONS = (
    "model_knowledge_missing",
    "rag_content_missing",
    "rag_retrieval_insufficient",
    "rag_retrieval_failed",
    "low_confidence",
    "insufficient_evidence",
    "outdated_information",
    "domain_understanding_missing",
    "answer_quality_failure",
    "unresolved_after_clarification",
)

OPERATIONAL_REASONS = (
    "model_unavailable",
    "model_timeout",
    "rag_timeout",
    "database_failure",
    "provider_failure",
    "rate_limited",
    "internal_error",
    "memory_unavailable",
)

LANGUAGE_REASONS = (
    "language_detection_failed",
    "wrong_output_language",
    "tanglish_output_leakage",
    "mixed_language_policy_failure",
    "tamil_quality_failure",
    "unsupported_language",
)

SAFETY_REASONS = (
    "unsafe_operational_request",
    "policy_refusal",
    "output_safety_block",
    "prompt_injection_block",
    "secret_extraction_attempt",
    "personal_data_extraction_attempt",
)

SOURCE_FAILURE_REASONS = (
    "source_unavailable",
    "source_rights_blocked",
    "source_retrieval_error",
)

WEB_CAPABILITY_REASONS = (
    "web_search_unavailable",
    # Phase 20: the route was attempted (a healthy provider was
    # reached), not merely unavailable -- additive, versioned taxonomy
    # per phase19_gap_taxonomy_and_priority_policy.md Step 26.
    "web_no_trusted_source",
    "web_evidence_insufficient",
    "web_quota_exceeded",
    "web_fetch_blocked",
)

TOOL_CAPABILITY_REASONS = (
    "tool_execution_unavailable",
    # Phase 20: the tool route was attempted but couldn't complete.
    "tool_unsupported_operation",
    "tool_input_invalid",
)

CLARIFICATION_REASONS = (
    "clarification_pending_followup",
    "clarification_resolved",
)

# Step 16 -- additive feedback-issue categories, attached as knowledge-gap
# reason codes rather than widening the sealed `public_chat_feedback_events
# .feedback_type` CHECK constraint (see plan doc section 11).
FEEDBACK_ISSUE_REASONS = (
    "stale_information",
    "source_conflict",
    "unknown_question",
    "wrong_answer",
    "missing_evidence",
    "wrong_language",
    "unsafe_answer",
    "unhelpful",
)

NOT_APPLICABLE_REASONS = (
    "successful_but_disliked",
    "user_cancelled_request",
    "no_actionable_signal",
)

REASON_CODES_BY_EVENT_TYPE: dict[str, tuple[str, ...]] = {
    "knowledge_gap": KNOWLEDGE_GAP_REASONS,
    "clarification_event": CLARIFICATION_REASONS,
    "safety_event": SAFETY_REASONS,
    "operational_failure": OPERATIONAL_REASONS,
    "language_failure": LANGUAGE_REASONS,
    "source_failure": SOURCE_FAILURE_REASONS,
    "tool_capability_gap": TOOL_CAPABILITY_REASONS,
    "web_capability_gap": WEB_CAPABILITY_REASONS,
    "feedback_issue": FEEDBACK_ISSUE_REASONS,
    "not_applicable": NOT_APPLICABLE_REASONS,
}

ALL_REASON_CODES: tuple[str, ...] = tuple(
    sorted({code for codes in REASON_CODES_BY_EVENT_TYPE.values() for code in codes})
)

# -- retention policy (Step 3/6)

RETENTION_POLICIES = ("standard", "extended_review", "hash_only", "not_retained")

# -- lifecycle (Step 5)

CASE_STATUSES = (
    "new",
    "classified",
    "needs_clarification",
    "evidence_search",
    "answer_draft",
    "review_required",
    "rag_trial",
    "monitored",
    "training_assessment_candidate",
    "resolved",
    "rejected",
    "blocked",
    "archived",
    "deleted_payload",
)

CASE_STAGES = (
    "capture",
    "privacy_processing",
    "classification",
    "deduplication",
    "prioritization",
    "research",
    "drafting",
    "human_review",
    "rag_handoff",
    "monitoring",
    "training_handoff",
    "resolution",
    "retention",
)

# -- clustering (Step 9)

CLUSTER_DECISIONS = (
    "same_case",
    "probable_duplicate",
    "possible_duplicate",
    "distinct",
    "needs_review",
)

# -- priority (Step 11)

PRIORITY_BANDS = ("critical", "high", "medium", "low", "informational")

TAMIL_FIRST_PRIORITY_REASON_CODES = (
    "tamil_grammar",
    "tamil_meaning",
    "tamil_orthography",
    "tamil_instruction_following",
    "tanglish_comprehension",
    "tamil_output_language_failure",
    "tamil_ambiguity_handling",
)

# -- resolution types (Step 18)

RESOLUTION_TYPES = (
    "answered_by_existing_model",
    "resolved_by_routing_rule",
    "resolved_by_approved_rag",
    "requires_trusted_web",
    "requires_tool",
    "requires_translation",
    "requires_language_policy_fix",
    "requires_safety_policy_fix",
    "requires_operational_fix",
    "evaluation_case_created",
    "future_training_assessment",
    "not_reproducible",
    "duplicate_resolved",
    "rejected",
    "blocked",
)

# -- review decisions (Step 22)

REVIEW_DECISIONS = (
    "confirm_gap",
    "reclassify",
    "merge",
    "keep_separate",
    "needs_evidence",
    "send_to_rag_research",
    "send_to_evaluation",
    "mark_training_assessment_candidate",
    "resolve",
    "reject",
    "block",
    "archive",
)

# -- deletion lifecycle (Step 24)

DELETION_STATES = ("requested", "confirmed", "executed", "rejected", "cancelled")

# -- redaction placeholders (Step 6)

REDACTION_PLACEHOLDERS = {
    "person": "[PERSON]",
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "address": "[ADDRESS]",
    "identifier": "[IDENTIFIER]",
    "secret": "[SECRET]",
    "private_context": "[PRIVATE_CONTEXT]",
}

# -- research note types (Step 17)

RESEARCH_NOTE_TYPES = (
    "investigation",
    "possible_source",
    "rights_concern",
    "answer_draft",
    "routing_issue",
    "language_issue",
    "safety_issue",
    "operational_issue",
    "resolution_note",
)

__all__ = [
    "ALL_REASON_CODES",
    "CASE_STAGES",
    "CASE_STATUSES",
    "CLARIFICATION_REASONS",
    "CLUSTER_DECISIONS",
    "DELETION_STATES",
    "EVENT_TYPES",
    "FEEDBACK_ISSUE_REASONS",
    "KNOWLEDGE_GAP_REASONS",
    "LANGUAGE_REASONS",
    "NOT_APPLICABLE_REASONS",
    "OPERATIONAL_REASONS",
    "POLICY_VERSION",
    "PRIORITY_BANDS",
    "REASON_CODES_BY_EVENT_TYPE",
    "REDACTION_PLACEHOLDERS",
    "RESEARCH_NOTE_TYPES",
    "RESOLUTION_TYPES",
    "RETENTION_POLICIES",
    "REVIEW_DECISIONS",
    "SAFETY_REASONS",
    "SOURCE_FAILURE_REASONS",
    "TAMIL_FIRST_PRIORITY_REASON_CODES",
    "TOOL_CAPABILITY_REASONS",
    "WEB_CAPABILITY_REASONS",
]
