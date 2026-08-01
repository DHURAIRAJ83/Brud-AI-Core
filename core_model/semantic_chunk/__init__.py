"""Pure, framework-agnostic policy for the Semantic Chunk & Structured
Record Studio (Phase 5). No DB/IO here -- mirrors the shape of
`core_model/manual_data/__init__.py` and `core_model/document_workspace/__init__.py`.
"""

from __future__ import annotations

CHUNK_TYPES = (
    "heading",
    "subheading",
    "paragraph",
    "definition",
    "example",
    "dictionary_entry",
    "grammar_rule",
    "question",
    "answer",
    "instruction",
    "response",
    "translation_source",
    "translation_target",
    "tanglish_text",
    "tamil_text",
    "english_text",
    "table",
    "table_row",
    "list",
    "footnote",
    "caption",
    "reference",
    "metadata",
    "irrelevant",
    "unknown",
)

CHUNK_STATUSES = (
    "draft",
    "needs_review",
    "needs_structure_review",
    "needs_content_review",
    "approved",
    "rejected",
    "excluded",
    "archived",
)

CHUNK_REVIEW_ACTIONS = (
    "approve",
    "request_boundary_correction",
    "request_classification_correction",
    "reject",
    "exclude",
    "archive",
    "reopen",
)

GENERATION_METHODS = (
    "existing_segmenter",
    "paragraph_boundary",
    "heading_boundary",
    "manual",
    "imported",
)

RELATIONSHIP_TYPES = (
    "derived_from_page",
    "continues_from",
    "continues_to",
    "child_of",
    "table_contains",
    "definition_of",
    "example_of",
    "answer_to",
    "translation_of",
)

# Reuses `core_model.manual_data.DATASET_RECORD_TYPE_MAP`'s vocabulary
# directly (Step 11: "use existing record types where possible"); adds
# only `rag_chunk`, which never maps to a `DatasetRecordType` and is
# handed off to RAG instead of dataset export (Step 24).
STRUCTURED_RECORD_TYPES = (
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
    "rag_chunk",
)

STRUCTURED_RECORD_STATUSES = ("draft", "needs_review", "approved", "rejected", "archived")

# Origin of structured-record content that is not directly copyable from
# a source chunk (an answer, a translation, a grammar explanation, ...).
# Never silently treated as "source_grounded" -- Steps 15/16/17 require
# this to be explicit and to require review.
CONTENT_ORIGINS = ("source_grounded", "admin_authored", "human_synthesized")

__all__ = [
    "CHUNK_TYPES",
    "CHUNK_STATUSES",
    "CHUNK_REVIEW_ACTIONS",
    "GENERATION_METHODS",
    "RELATIONSHIP_TYPES",
    "STRUCTURED_RECORD_TYPES",
    "STRUCTURED_RECORD_STATUSES",
    "CONTENT_ORIGINS",
]
