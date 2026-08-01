"""Phase 2 (Data Studio) source, rights, and usage-policy pure-function
package.

This governs *any* data entering Brud AI through the general registry
(``data_sources``/``source_rights``), independent of the corpus-builder
pipeline's own ``corpus_source_registries``/``corpus_source_licences``
(``core_model.corpus.licence_policy``). The two systems share a policy
*shape* (deterministic decision + explicit blocking reasons, never a
bare boolean) but are never merged into one table, because a corpus
source is required to belong to a ``corpus_policy_id`` and this
registry deliberately is not (see
``docs/data_studio/phase2_source_rights_registry_plan.md`` section 1.3
for why).

Every enum below is the single source of truth shared by the backend
services, matching the corresponding CHECK constraints in
``backend/database/schema.py``'s Phase 2 (Data Studio) schema block.
"""

from __future__ import annotations

SOURCE_TYPES = (
    "human_created", "admin_created", "teacher_created", "institution_created",
    "document_derived", "government_source", "public_domain", "open_dataset",
    "licensed_dataset", "permission_granted", "user_contributed", "ai_assisted",
    "ai_generated", "web_source", "unknown",
)

SOURCE_STATUSES = (
    "draft", "needs_review", "verified", "restricted", "rejected", "archived",
)

RISK_LEVELS = ("low", "medium", "high", "unknown")

RIGHTS_STATUSES = (
    "unknown", "pending_review", "public_domain", "open_license", "licensed",
    "permission_granted", "internal_only", "restricted", "prohibited", "expired",
)

VERIFICATION_STATUSES = (
    "unverified", "self_declared", "document_verified", "owner_confirmed",
    "legal_reviewed", "rejected",
)

VERIFICATION_ACTIONS = (
    "self_declare", "document_verify", "owner_confirm", "legal_review", "reject",
    "expire", "restrict",
)

TARGET_USES = ("rag", "training", "evaluation", "commercial", "public_export", "redistribution")

ENTITY_TYPES = (
    "dataset_record", "dataset_source", "dataset_version", "import_job", "document",
    "document_page", "corpus_source_registry", "corpus_item", "chunk",
    "rag_knowledge_source", "rag_item", "evaluation_case",
)

RELATIONSHIP_TYPES = (
    "primary_source", "supporting_source", "derived_from", "verified_against",
    "translated_from", "generated_from",
)

# Source types that structurally require human verification before their
# content may be used for anything beyond internal RAG (rule 11).
AI_ORIGIN_SOURCE_TYPES = frozenset({"ai_assisted", "ai_generated"})

# Verification statuses strong enough to count as "a human independently
# checked this", as opposed to a bare unverified/self-declared assertion.
INDEPENDENT_VERIFICATION_STATUSES = frozenset({"owner_confirmed", "legal_reviewed"})
STRONG_VERIFICATION_STATUSES = frozenset(
    {"document_verified", "owner_confirmed", "legal_reviewed"}
)
