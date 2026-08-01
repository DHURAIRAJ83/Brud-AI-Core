"""Phase 3 (Data Studio) Manual Data Studio pure-function package.

Governs hand-authored records (language examples, conversations, Q&A,
instructions, dictionary entries, translations, Tanglish normalization,
knowledge notes, grammar examples, evaluation drafts) that the existing
``dataset_records`` manual-entry system (``backend/services/dataset_service.py``)
has no columns for. This is a staging layer in front of that system, not
a replacement -- an approved manual record only becomes a real
``dataset_records`` row through an explicit "create dataset candidate"
action (see ``backend/services/manual_data_candidate_service.py``).

Every enum below is the single source of truth shared by the schema
(``backend/database/schema.py``'s Phase 3 block), the backend models,
and the policy modules in this package.
"""

from __future__ import annotations

RECORD_TYPES = (
    "plain_text",
    "language_example",
    "conversation",
    "question_answer",
    "instruction_response",
    "dictionary_entry",
    "translation_pair",
    "tanglish_normalization",
    "knowledge_note",
    "grammar_example",
    "evaluation_case_draft",
)

RECORD_STATUSES = (
    "draft",
    "needs_review",
    "needs_source_verification",
    "needs_domain_review",
    "approved",
    "rejected",
    "archived",
)

CREATION_METHODS = (
    "human_created",
    "admin_created",
    "teacher_created",
    "ai_assisted",
    "imported_manual",
    "derived_manual",
)

FACT_DEPENDENCIES = ("none", "low", "medium", "high")

KNOWLEDGE_RISKS = ("language_only", "general", "domain_specific", "high_risk", "time_sensitive")

LANGUAGE_CODES = ("ta", "en", "tgl", "mixed", "unknown")

TARGET_USES = ("rag", "training", "evaluation", "commercial", "public_export", "redistribution")

REVIEW_TYPES = ("language", "translation", "factual", "domain", "general")

REVIEW_STATUSES = ("approved", "rejected", "changes_requested")

VERIFICATION_TYPES = (
    "source_verification",
    "factual_verification",
    "domain_verification",
    "time_sensitivity_revalidation",
)

VERIFICATION_STATUSES = ("pending", "verified", "rejected", "expired")

# Creation methods that structurally require human review before their
# content may be used for anything beyond internal RAG (rule 10).
AI_ORIGIN_CREATION_METHODS = frozenset({"ai_assisted"})

# Knowledge-risk / fact-dependency values that require a completed
# verification before approval for production RAG or training (rule 9).
HIGH_RISK_KNOWLEDGE = frozenset({"high_risk", "time_sensitive"})
HIGH_FACT_DEPENDENCY = frozenset({"high"})

# Manual record_type -> existing DatasetRecordType, for the "create
# dataset candidate" bridge (Step 17). `evaluation_case_draft` is
# deliberately absent: evaluation drafts are regression evidence and
# must never be exported into the training dataset pipeline, mirroring
# `feedback_dataset_service.export_candidate()`'s refusal to export
# `evaluation_only` candidates.
DATASET_RECORD_TYPE_MAP = {
    "plain_text": "pretrain",
    "language_example": "pretrain",
    "grammar_example": "pretrain",
    "dictionary_entry": "pretrain",
    "knowledge_note": "pretrain",
    "conversation": "chat",
    "question_answer": "instruction",
    "instruction_response": "instruction",
    "translation_pair": "translation",
    "tanglish_normalization": "tanglish_pair",
}
