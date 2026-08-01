from core_model.knowledge_routing import (
    ALL_SUBDOMAINS,
    CONFIDENCE_BANDS,
    CONTEXT_TYPES,
    DOMAINS,
    EVIDENCE_REQUIREMENTS,
    EXECUTION_ROUTES,
    FRESHNESS_VALUES,
    INTENTS,
    LEARNING_TARGETS,
    SAFETY_REASON_CATEGORIES,
    SAFETY_RISK_VALUES,
    SUBDOMAINS_BY_DOMAIN,
)
from core_model.knowledge_routing.reason_codes import (
    DOMAIN_REASON_CODE_BY_VALUE,
    EVIDENCE_REASON_CODE_BY_VALUE,
    FRESHNESS_REASON_CODE_BY_VALUE,
    INTENT_REASON_CODE_BY_VALUE,
    REASON_CODE_REGISTRY,
    SAFETY_CATEGORY_REASON_CODE_BY_VALUE,
    SAFETY_REASON_CODE_BY_VALUE,
    TARGET_REASON_CODE_BY_VALUE,
    is_known_reason_code,
)


def test_execution_routes_and_learning_targets_are_disjoint_concepts() -> None:
    assert EXECUTION_ROUTES == (
        "core_model", "approved_rag", "trusted_web", "tool", "memory",
        "clarify", "refuse", "insufficient",
    )
    assert LEARNING_TARGETS == (
        "core_model", "rag_only", "web_preferred", "tool_required", "evaluation_only",
        "future_training_candidate", "do_not_learn", "blocked",
    )


def test_confidence_bands_never_include_a_numeric_score() -> None:
    assert CONFIDENCE_BANDS == ("high", "medium", "low", "unknown")


def test_every_subdomain_belongs_to_a_declared_parent_domain() -> None:
    for domain, subdomains in SUBDOMAINS_BY_DOMAIN.items():
        assert domain in DOMAINS
        for subdomain in subdomains:
            assert subdomain in ALL_SUBDOMAINS


def test_every_intent_reason_code_is_registered() -> None:
    for intent in INTENTS:
        code = INTENT_REASON_CODE_BY_VALUE[intent]
        assert is_known_reason_code(code), code


def test_every_domain_and_subdomain_reason_code_is_registered() -> None:
    for value in (*DOMAINS, *ALL_SUBDOMAINS):
        code = DOMAIN_REASON_CODE_BY_VALUE[value]
        assert is_known_reason_code(code), code


def test_every_freshness_reason_code_is_registered() -> None:
    for value in FRESHNESS_VALUES:
        assert is_known_reason_code(FRESHNESS_REASON_CODE_BY_VALUE[value])


def test_every_evidence_reason_code_is_registered() -> None:
    for value in EVIDENCE_REQUIREMENTS:
        assert is_known_reason_code(EVIDENCE_REASON_CODE_BY_VALUE[value])


def test_every_safety_and_safety_category_reason_code_is_registered() -> None:
    for value in SAFETY_RISK_VALUES:
        assert is_known_reason_code(SAFETY_REASON_CODE_BY_VALUE[value])
    for category in SAFETY_REASON_CATEGORIES:
        assert is_known_reason_code(SAFETY_CATEGORY_REASON_CODE_BY_VALUE[category])


def test_every_learning_target_reason_code_is_registered() -> None:
    for target in LEARNING_TARGETS:
        assert is_known_reason_code(TARGET_REASON_CODE_BY_VALUE[target])


def test_required_step21_example_codes_exist_verbatim() -> None:
    required = (
        "LANG_TAMIL_DETECTED", "LANG_TANGLISH_DETECTED", "INTENT_CURRENT_STATUS",
        "DOMAIN_TAMIL_GRAMMAR", "DOMAIN_SOFTWARE_DOCUMENTATION", "FRESHNESS_REAL_TIME",
        "FRESHNESS_TIME_SENSITIVE", "EVIDENCE_INTERNAL_REQUIRED",
        "EVIDENCE_EXTERNAL_REQUIRED", "EVIDENCE_TOOL_REQUIRED", "AMBIGUOUS_MISSING_CONTEXT",
        "SAFETY_LIKELY_DISALLOWED", "ROUTE_CORE_STABLE_LANGUAGE", "ROUTE_RAG_APPROVED_INTERNAL",
        "ROUTE_WEB_CURRENT_INFORMATION", "ROUTE_TOOL_DETERMINISTIC", "ROUTE_CLARIFY_AMBIGUOUS",
        "TARGET_CORE_LANGUAGE_SKILL",
        "TARGET_RAG_STABLE_FACT", "TARGET_WEB_VOLATILE_FACT", "TARGET_TOOL_CALCULATION",
        "TARGET_EVALUATION_ONLY", "TARGET_DO_NOT_LEARN_PERSONAL", "TARGET_BLOCKED_UNSAFE",
        "TAMIL_FIRST_POLICY_VIOLATION",
    )
    for code in required:
        assert code in REASON_CODE_REGISTRY, code


def test_context_types_cover_every_structured_record_kind() -> None:
    assert CONTEXT_TYPES == (
        "public_chat_question", "rag_record", "dataset_candidate", "training_candidate",
        "evaluation_prompt", "knowledge_gap_case",
    )
