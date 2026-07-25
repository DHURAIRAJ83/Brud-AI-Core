"""Phase 19 Tamil corpus builder pure-function package.

Large amounts of text are never assumed to be usable training data.
Every enum below is the single source of truth shared by the backend
services, matching the corresponding CHECK constraints in
``backend/database/schema.py``'s ``PHASE19_SCHEMA``. The core
principle: content must prove origin, prove allowed use, prove
quality, prove privacy safety, prove contamination safety, before
explicit approval -- never the other way around.
"""

from __future__ import annotations

SOURCE_TYPES = (
    "uploaded_pdf", "uploaded_text", "uploaded_markdown", "uploaded_html_snapshot",
    "dataset_version", "document_record", "feedback_candidate_export", "manual_admin_text",
    "public_domain_book", "government_publication", "educational_material", "dictionary",
    "grammar_reference", "parallel_corpus", "conversation_corpus", "tanglish_pair_corpus",
    "faq_collection",
)

SOURCE_STATUSES = (
    "draft", "origin_review", "licence_review", "approved", "approved_with_restrictions",
    "rejected", "quarantined", "disputed", "archived",
)

LICENCE_FAMILIES = (
    "public_domain", "cc0", "cc_by", "cc_by_sa", "government_open_data", "organisation_owned",
    "user_owned_with_permission", "custom_permissive", "research_only", "non_commercial",
    "all_rights_reserved", "unknown",
)

# Families a policy may map to "approved" without further conditions --
# never assumed, always explicit. Everything else defaults unapproved.
DEFAULT_APPROVED_LICENCE_FAMILIES = frozenset({"public_domain", "cc0"})
DEFAULT_CONDITIONAL_LICENCE_FAMILIES = frozenset(
    {"cc_by", "cc_by_sa", "government_open_data", "organisation_owned",
     "user_owned_with_permission", "custom_permissive"}
)

LICENCE_REVIEW_STATUSES = (
    "approved", "approved_with_conditions", "restricted", "unknown", "blocked", "disputed",
    "expired", "not_applicable",
)

# Licence statuses that always block training export outright.
BLOCKING_LICENCE_STATUSES = frozenset({"unknown", "blocked", "disputed", "expired", "restricted"})

SNAPSHOT_STATUSES = ("creating", "ready", "failed", "superseded", "archived")

EXTRACTION_METHODS = (
    "embedded_pdf_text", "tesseract_ocr", "plain_text", "markdown_text", "html_snapshot_text",
    "dataset_record_projection", "manual_content",
)

RUN_STATUSES = ("draft", "running", "completed", "completed_with_warnings", "failed", "cancelled")

SEGMENTATION_STRATEGIES = (
    "paragraph", "sentence_group", "heading_section", "record_based",
    "fixed_character_window", "fixed_token_estimate_window",
)

LANGUAGE_CATEGORIES = ("ta", "en", "tgl", "mixed", "numeric", "code", "unknown")

DOMAINS = (
    "general", "education", "literature", "grammar", "dictionary", "conversation", "translation",
    "government", "history", "science", "mathematics", "technology", "agriculture", "business",
    "health_general", "law_general", "religion_cultural", "children", "faq", "safety", "code",
    "other",
)

STYLES = (
    "formal", "conversational", "instructional", "narrative", "reference", "question_answer",
    "dialogue", "translation_pair", "dictionary_entry", "poetry", "code_mixed", "technical",
    "administrative",
)

PRIVACY_STATUSES = ("safe", "redacted", "requires_review", "blocked")
SAFETY_STATUSES = ("safe", "flagged", "blocked", "requires_review")
SAFETY_BEHAVIOR_CLASSES = (
    "descriptive", "educational", "historical", "preventive", "operational_harmful",
)

QUALITY_DIMENSIONS = (
    "unicode_integrity", "tamil_integrity", "ocr_quality", "sentence_completeness",
    "language_confidence", "content_density", "boilerplate_ratio", "duplicate_risk",
    "privacy_safety", "safety_quality", "licence_completeness", "provenance_completeness",
    "domain_value", "style_value", "length_quality", "readability", "format_integrity",
)
QUALITY_STATUSES = ("pass", "warning", "fail", "not_assessed")
QUALITY_SUBJECT_TYPES = ("source", "document", "segment", "collection", "build")

DUPLICATE_STATUSES = ("unique", "exact_duplicate", "normalized_duplicate")
NEAR_DUPLICATE_METHODS = (
    "minhash", "simhash", "character_ngram_jaccard", "token_ngram_jaccard",
)
DUPLICATE_CLUSTER_ACTIONS = (
    "keep_representative", "exclude_duplicate", "keep_both_with_reason", "quarantine_cluster",
    "manual_review",
)

CONTAMINATION_ISSUE_TYPES = (
    "training_duplicate", "validation_leakage", "test_leakage", "evaluation_fixture_leakage",
    "regression_fixture_leakage", "holdout_leakage", "hidden_prompt_leakage",
)
BLOCKING_CONTAMINATION_ISSUES = frozenset(
    {
        "validation_leakage", "test_leakage", "evaluation_fixture_leakage",
        "regression_fixture_leakage", "holdout_leakage", "hidden_prompt_leakage",
    }
)

COLLECTION_STATUSES = ("draft", "validated", "active", "deprecated", "archived")
BUILD_STATUSES = (
    "draft", "validating", "ready", "building", "completed", "completed_with_warnings",
    "failed", "cancelled", "archived",
)
SPLITS = ("train", "validation", "test")
VERSION_STATUSES = ("draft", "validating", "ready", "deprecated", "retired", "archived")
EXPORT_FORMATS = ("jsonl", "plain_text_shards", "metadata_jsonl")
EXPORT_STATUSES = (
    "draft", "running", "completed", "completed_with_warnings", "failed", "cancelled"
)

COMPARISON_COMPATIBILITIES = ("compatible", "partially_compatible", "incompatible")

PUBLICLY_ACCESSIBLE_NOT_TRAINING_SAFE_NOTICE = (
    "Public accessibility does not automatically mean the content is permitted for AI training."
)
NO_AUTOMATIC_TRAINING_NOTICE = (
    "Only approved, provenance-complete, licence-compatible, privacy-safe content may enter a "
    "Brud AI training corpus."
)
EXPORT_NOT_TRAINING_TRIGGER_NOTICE = (
    "Finalizing a corpus does not automatically start model training."
)
