"""Phase 17 knowledge-domain, freshness, evidence, execution-route, and
learning-target classification taxonomy. Every enum below is the single
source of truth (mirrors `backend/database/schema.py`'s CHECK
constraint on `routing_classification_decisions`), following the exact
pattern already established by `core_model/feedback/__init__.py`.

Nothing in this package executes Model, RAG, Web, Tool, or Memory
actions -- it only classifies and recommends. See
docs/smart_routing/phase17_domain_learning_router_plan.md.
"""

from __future__ import annotations

POLICY_VERSION = "v1"
TAXONOMY_VERSION = "v1"

CONFIDENCE_BANDS = ("high", "medium", "low", "unknown")

# -- knowledge domain (Step 3) -----------------------------------------------------------------

DOMAINS = (
    "tamil_language",
    "english_language",
    "tanglish_input",
    "mathematics",
    "computer_and_coding",
    "science",
    "social_science",
    "government_services",
    "industry_knowledge",
    "current_affairs",
    "general_knowledge",
    "personal_context",
    "translation",
    "creative_writing",
    "administrative_action",
    "safety_sensitive",
    "unknown",
)

# Deliberately bounded (plan doc §3): the subset of the task's
# "recommended optional" subdomains actually implemented, chosen to
# cover every worked example in Steps 22-23 plus close siblings.
SUBDOMAINS_BY_DOMAIN: dict[str, tuple[str, ...]] = {
    "tamil_language": ("tamil_grammar", "tamil_orthography", "tamil_meaning", "tamil_translation"),
    "mathematics": ("basic_arithmetic", "advanced_calculation"),
    "computer_and_coding": (
        "software_usage", "software_documentation", "programming", "cybersecurity",
    ),
    "science": ("physics", "chemistry", "biology"),
    "social_science": ("history", "geography", "civics"),
    "government_services": (
        "government_scheme", "application_guidance", "legal_or_regulatory_current",
    ),
    "industry_knowledge": ("business_process", "technical_industry"),
    "current_affairs": ("news", "weather", "prices", "sports"),
    "general_knowledge": ("stable_general_fact",),
}

ALL_SUBDOMAINS: tuple[str, ...] = tuple(
    sub for subs in SUBDOMAINS_BY_DOMAIN.values() for sub in subs
)

# -- intent (Step 4) ---------------------------------------------------------------------------

INTENTS = (
    "ask_fact",
    "ask_explanation",
    "ask_definition",
    "ask_how_to",
    "ask_calculation",
    "ask_translation",
    "ask_summarization",
    "ask_comparison",
    "ask_recommendation",
    "ask_current_status",
    "ask_navigation",
    "ask_personal_memory",
    "ask_code",
    "ask_creative_generation",
    "ask_action",
    "ask_clarification",
    "unsafe_operational",
    "unknown",
)

# -- freshness / volatility (Step 5) -----------------------------------------------------------

FRESHNESS_VALUES = (
    "timeless",
    "slow_changing",
    "time_sensitive",
    "real_time",
    "historical",
    "unknown",
)

# -- evidence requirement (Step 6) -------------------------------------------------------------

EVIDENCE_REQUIREMENTS = (
    "none",
    "model_knowledge_ok",
    "internal_evidence_required",
    "external_verified_evidence_required",
    "deterministic_tool_required",
    "clarification_required",
    "blocked",
)

# -- safety-risk signal (Step 8) ---------------------------------------------------------------

SAFETY_RISK_VALUES = (
    "safe",
    "sensitive_but_allowed",
    "requires_policy_review",
    "likely_disallowed",
    "unknown",
)

# Reused verbatim from core_model.model_evaluation.SAFETY_CATEGORIES,
# plus the "must still allow" categories the task explicitly names.
SAFETY_REASON_CATEGORIES = (
    "violent_operational",
    "weapon_instruction",
    "malware_or_credential_theft",
    "fraud_or_forgery",
    "personal_data_extraction",
    "dangerous_substance",
    "self_harm_instruction",
    "deliberate_disinformation",
    "benign_cybersecurity",
    "political_discussion",
    "government_criticism",
    "legal_information",
)

# -- execution route (Steps 9, 24) -------------------------------------------------------------

EXECUTION_ROUTES = (
    "core_model",
    "approved_rag",
    "trusted_web",
    "tool",
    "memory",
    "clarify",
    "refuse",
    "insufficient",
)

# -- learning target (Steps 10, 24) ------------------------------------------------------------

LEARNING_TARGETS = (
    "core_model",
    "rag_only",
    "web_preferred",
    "tool_required",
    "evaluation_only",
    "future_training_candidate",
    "do_not_learn",
    "blocked",
)

# -- structured-record context types (Step 13) --------------------------------------------------

CONTEXT_TYPES = (
    "public_chat_question",
    "rag_record",
    "dataset_candidate",
    "training_candidate",
    "evaluation_prompt",
    "knowledge_gap_case",
)

__all__ = [
    "ALL_SUBDOMAINS",
    "CONFIDENCE_BANDS",
    "CONTEXT_TYPES",
    "DOMAINS",
    "EVIDENCE_REQUIREMENTS",
    "EXECUTION_ROUTES",
    "FRESHNESS_VALUES",
    "INTENTS",
    "LEARNING_TARGETS",
    "POLICY_VERSION",
    "SAFETY_REASON_CATEGORIES",
    "SAFETY_RISK_VALUES",
    "SUBDOMAINS_BY_DOMAIN",
    "TAXONOMY_VERSION",
]
