"""Phase 16 pure-function package: knowledge retrieval, hybrid search,
citation grounding, and answer policy.

None of this package fetches remote content, trains anything, or loads
a model. It only reasons about already-registered, already-approved
knowledge sources and produces deterministic, verifiable retrieval and
grounding decisions. Retrieved text existing is never treated as proof
an answer is correct — retrieval quality, context quality, citation
validity, answer grounding, and model generation quality are always
kept as separate, independently reported concerns.
"""

from __future__ import annotations

SOURCE_TYPES = (
    "dataset_version",
    "pdf_document",
    "plain_text",
    "markdown",
    "html_snapshot",
    "manual_admin_content",
    "course_material",
    "faq",
)

SOURCE_APPROVAL_STATUSES = (
    "draft",
    "review_required",
    "approved",
    "rejected",
    "quarantined",
    "archived",
)

LICENCE_STATUSES = ("unknown", "open", "restricted", "blocked")

SOURCE_VERSION_STATUSES = ("processing", "ready", "failed", "superseded", "archived")

CHUNKING_STRATEGIES = (
    "paragraph",
    "heading_aware",
    "sentence_window",
    "fixed_token_window",
    "record_based",
)

CHUNK_QUALITY_STATUSES = ("accepted", "accepted_with_warning", "rejected", "quarantined")

CHUNK_ISSUE_REASONS = (
    "empty_content",
    "too_short",
    "too_long",
    "ocr_noise_high",
    "duplicate_chunk",
    "near_duplicate_chunk",
    "unsupported_language",
    "invalid_unicode",
    "metadata_leak",
    "prompt_injection_risk",
    "licence_blocked",
    "source_not_approved",
)

INJECTION_STATUSES = ("clean", "warning", "quarantined", "blocked")

EMBEDDING_PROVIDER_TYPES = (
    "local_sentence_transformer",
    "local_custom_embedding",
    "deterministic_test_embedding",
)

EMBEDDING_MODEL_STATUSES = ("draft", "validated", "active", "deprecated", "archived", "failed")

EMBEDDING_RUN_STATUSES = (
    "draft",
    "running",
    "completed",
    "completed_with_warnings",
    "failed",
    "cancelled",
)

VECTOR_INDEX_TYPES = ("faiss_flat", "repository_flat")

DISTANCE_METRICS = ("cosine", "inner_product", "l2")

INDEX_STATUSES = ("building", "validated", "active", "deprecated", "failed", "archived")

KEYWORD_INDEX_TYPES = ("fts5", "repository_inverted")

LANGUAGE_CATEGORIES = ("ta", "en", "tgl", "mixed", "unknown")

DEDUPLICATION_POLICIES = ("exact_only", "exact_and_near")

DIVERSITY_POLICIES = ("none", "source_diversity")

INJECTION_FILTER_POLICIES = ("block", "quarantine", "warn")

RETRIEVAL_RUN_STATUSES = ("completed", "no_results", "failed")

ANSWER_STATUSES = (
    "grounded_answer",
    "insufficient_evidence",
    "retrieval_failed",
    "generation_failed",
    "blocked_evidence",
)

CITATION_VALIDATION_STATUSES = ("valid", "valid_with_warning", "invalid", "not_present")

GROUNDING_ISSUE_CODES = (
    "no_retrieval_results",
    "retrieval_score_below_threshold",
    "retrieval_filter_excluded_all",
    "only_quarantined_chunks",
    "context_budget_exceeded",
    "context_empty",
    "prompt_injection_chunk_detected",
    "prompt_injection_chunk_included",
    "unknown_citation",
    "citation_not_in_context",
    "citation_checksum_mismatch",
    "citation_access_forbidden",
    "unsupported_answer_claim",
    "uncited_factual_claim",
    "evidence_conflict",
    "answer_language_mismatch",
    "role_token_leakage",
    "prompt_leakage",
    "generation_timeout",
    "generation_failed",
    "retrieval_failed",
    "index_mismatch",
    "embedding_model_mismatch",
)

SEVERITIES = ("info", "warning", "error", "blocking")

EVALUATION_SEVERITIES = ("info", "warning", "blocking")

INSUFFICIENT_EVIDENCE_MESSAGE_TA = (
    "இந்த கேள்விக்கு போதுமான உறுதிப்படுத்தப்பட்ட தகவல் கிடைக்கவில்லை."
)
INSUFFICIENT_EVIDENCE_MESSAGE_EN = (
    "There is not enough verified evidence to answer this question."
)

REGISTRY_FIXTURE_MARKERS = ("registry_workflow_fixture", "not_production_model")
RAG_TEST_FIXTURE_MARKERS = ("test_only_rag_runtime_fixture", "not_production_model")
