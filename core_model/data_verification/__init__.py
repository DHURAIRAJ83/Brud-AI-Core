"""Phase 11: pure enums, bounds, and precedence rules for Licence
Evidence, Terms Snapshot & Dataset Verification.

Read-only and evidence-driven: nothing in this package (or anything it
describes) ever downloads a dataset payload file, imports records,
activates RAG, creates a training dataset version, or releases a
model. A verification case always links to exactly one existing Phase
10 candidate; nothing here mutates that candidate's own structurally
`not_approved`/`unknown` use-status columns. See
docs/data_verification/phase11_licence_evidence_verification_plan.md.
"""

from __future__ import annotations

# -- evidence hierarchy (Step 2) --------------------------------------------

EVIDENCE_TYPES = (
    "official_dataset_page", "dataset_card", "licence_file", "licence_url",
    "repository_licence_metadata", "terms_of_use", "privacy_policy",
    "consent_statement", "upstream_source", "citation_file", "readme",
    "provider_api_metadata", "government_notice", "institutional_policy",
    "manual_admin_evidence",
)

# Highest authority first -- the one fixed ordering every conflict
# resolution and licence-status decision consults, never a heuristic.
EVIDENCE_AUTHORITY_LEVELS = (
    "primary", "official_supporting", "secondary", "provider_declared",
    "community_supplied", "manual_unverified",
)
AUTHORITY_PRECEDENCE = EVIDENCE_AUTHORITY_LEVELS

# A starting default an admin/service may override per snapshot when the
# specific evidence genuinely warrants a different level (e.g. a
# `licence_url` pointing at the dataset's own dedicated licence page is
# `primary`) -- never silently auto-escalated beyond this table without
# an explicit override recorded on the snapshot itself.
EVIDENCE_TYPE_DEFAULT_AUTHORITY: dict[str, str] = {
    "official_dataset_page": "primary",
    "licence_file": "primary",
    "licence_url": "primary",
    "dataset_card": "official_supporting",
    "terms_of_use": "official_supporting",
    "privacy_policy": "official_supporting",
    "consent_statement": "official_supporting",
    "citation_file": "official_supporting",
    "government_notice": "official_supporting",
    "institutional_policy": "official_supporting",
    "upstream_source": "secondary",
    "repository_licence_metadata": "secondary",
    "readme": "secondary",
    "provider_api_metadata": "provider_declared",
    "manual_admin_evidence": "manual_unverified",
}


def authority_rank(level: str) -> int:
    """Lower rank number = higher authority. Raises `ValueError` for an
    unrecognized level rather than silently treating it as lowest --
    an unknown authority level must never be compared at all."""

    return AUTHORITY_PRECEDENCE.index(level)


def higher_or_equal_authority(a: str, b: str) -> bool:
    """True when authority level `a` is at least as authoritative as
    `b` -- the single function conflict resolution and licence-status
    decisions must consult so lower-authority evidence can never
    silently override higher-authority evidence."""

    return authority_rank(a) <= authority_rank(b)


def default_authority_for_evidence_type(evidence_type: str) -> str:
    return EVIDENCE_TYPE_DEFAULT_AUTHORITY.get(evidence_type, "manual_unverified")


# -- verification case lifecycle (Step 4) -----------------------------------

VERIFICATION_CASE_STATUSES = (
    "draft", "collecting_evidence", "needs_review", "in_review", "verified",
    "verified_with_conditions", "insufficient_evidence", "conflicting_evidence",
    "blocked", "cancelled", "expired", "withdrawn",
)
ACTIVE_VERIFICATION_CASE_STATUSES = ("draft", "collecting_evidence", "needs_review", "in_review")
TERMINAL_VERIFICATION_CASE_STATUSES = (
    "verified", "verified_with_conditions", "insufficient_evidence",
    "conflicting_evidence", "blocked", "cancelled", "expired", "withdrawn",
)
# A case may only be finalized (locked) from one of these -- never from
# a still-in-progress or already-terminal status.
FINALIZABLE_FROM_CASE_STATUSES = ("needs_review", "in_review")

# -- identity verification (Step 6) ------------------------------------------

IDENTITY_STATUSES = ("verified", "likely_match", "partial", "conflicting", "not_verified")
# Title-similarity alone can never reach these two -- a dedicated test
# enforces this against the identity-verification service.
STRONG_IDENTITY_STATUSES = ("verified",)

# -- licence normalization (Step 7) ------------------------------------------

LICENCE_STATUSES = (
    "unknown", "declared_only", "evidence_captured", "verified", "custom_needs_review",
    "missing", "conflicting", "restricted", "withdrawn",
)

# A small, explicit, hand-maintained exact-match table -- never a fuzzy
# or partial match, never an invented identifier. Keys are matched
# case/whitespace-insensitively against the *declared* licence string.
SPDX_EXACT_MATCHES: dict[str, str] = {
    "cc-by-4.0": "CC-BY-4.0", "cc by 4.0": "CC-BY-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0", "cc by-sa 4.0": "CC-BY-SA-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0", "cc by-nc 4.0": "CC-BY-NC-4.0",
    "cc-by-nc-sa-4.0": "CC-BY-NC-SA-4.0", "cc by-nc-sa 4.0": "CC-BY-NC-SA-4.0",
    "cc-by-nd-4.0": "CC-BY-ND-4.0",
    "cc0-1.0": "CC0-1.0", "cc0": "CC0-1.0", "public domain": "CC0-1.0",
    "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0", "apache license 2.0": "Apache-2.0",
    "mit": "MIT", "mit license": "MIT",
    "bsd-3-clause": "BSD-3-Clause", "bsd-2-clause": "BSD-2-Clause",
    "gpl-3.0": "GPL-3.0-only", "gpl-2.0": "GPL-2.0-only",
    "odbl-1.0": "ODbL-1.0", "odc-by-1.0": "ODC-By-1.0",
}


def normalize_spdx_identifier(declared_licence: str | None) -> str | None:
    """Exact-match only (case/whitespace-insensitive) -- `None` for
    anything not in the table, never a guessed/fuzzy identifier."""

    if not declared_licence:
        return None
    key = " ".join(declared_licence.strip().lower().split())
    return SPDX_EXACT_MATCHES.get(key)


# -- permission assessment (Step 8/9) ----------------------------------------

PERMISSION_TYPES = (
    "rag_use", "training_use", "evaluation_use", "commercial_use", "redistribution",
    "modification", "derivative_works", "attribution_required", "share_alike_required",
    "notice_required", "source_disclosure_required", "personal_data_restriction",
    "research_only", "non_commercial_only", "geographic_restriction",
    "gated_access_restriction",
)

# Settable only by an automated assessment pass
# (`ExternalDatasetPermissionAssessmentService.assess()`).
# `not_applicable` is included here (rather than admin-only) because
# determining "this permission dimension does not apply to this
# dataset" (e.g. `geographic_restriction` when no geographic marker
# was found anywhere in evidence) is an objective, evidence-derivable
# fact, not a sensitive rights grant.
AUTOMATED_PERMISSION_STATUSES = (
    "unknown", "not_applicable", "likely_allowed", "likely_restricted", "needs_legal_review",
)
# Settable only by an explicit, reasoned human Admin review
# (`ExternalDatasetPermissionAssessmentService.review()`) -- never by
# any automated code path. This is the structural gate Step 8 requires.
ADMIN_ONLY_PERMISSION_STATUSES = (
    "approved", "approved_with_conditions", "not_approved", "prohibited",
)
# Settable only by the withdrawal-notice processing path
# (`ExternalDatasetWithdrawalService`) when a notice affects this
# permission -- a factual state change triggered by an external event,
# not a subjective rights decision, so it is neither "automated
# assessment" nor "admin review" in the Step 8 sense.
SYSTEM_TRIGGERED_PERMISSION_STATUSES = ("withdrawn",)

PERMISSION_STATUSES = (
    AUTOMATED_PERMISSION_STATUSES
    + ADMIN_ONLY_PERMISSION_STATUSES
    + SYSTEM_TRIGGERED_PERMISSION_STATUSES
)


def is_admin_only_permission_status(status: str) -> bool:
    return status in ADMIN_ONLY_PERMISSION_STATUSES


COMMERCIAL_USE_INTENDED_CATEGORIES = (
    "internal_testing", "research", "free_public_service", "paid_commercial_product",
    "redistributed_dataset", "commercial_training_deployment",
)

# -- upstream sources (Step 10) -----------------------------------------------

UPSTREAM_RELATIONSHIP_TYPES = (
    "derived_from", "aggregated_from", "mirrored_from", "translated_from",
    "annotated_from", "converted_from", "subset_of", "unknown",
)

# -- conflicts (Step 12) -------------------------------------------------------

CONFLICT_SEVERITIES = ("informational", "low", "moderate", "high", "blocking")
BLOCKING_CONFLICT_SEVERITIES = ("blocking",)

# -- reverification & expiry (Step 14) ---------------------------------------

REVERIFICATION_STATUSES = ("current", "due_soon", "expired", "source_changed", "withdrawn")

# -- withdrawal notices (Step 15) ---------------------------------------------

WITHDRAWAL_NOTICE_TYPES = (
    "dataset_withdrawn", "licence_changed", "terms_changed", "rights_holder_request",
    "privacy_request", "provider_removed", "other",
)

# -- report field provenance (Step 13) ----------------------------------------

REPORT_FIELD_PROVENANCE = (
    "verified_fact", "provider_declared", "assistant_inference", "admin_decision", "unknown",
)

# -- case-level roll-up sections (Step 4) ------------------------------------

# Shared vocabulary for the case row's `evidence_status`/`terms_status`/
# `upstream_status`/`permission_status` roll-up columns -- these
# summarize a whole section's progress, not any single evidence item
# or permission's own (richer) status.
CASE_SECTION_STATUSES = ("not_started", "in_progress", "complete", "incomplete", "conflicting")

# -- evidence snapshots (Step 5) ----------------------------------------------

EVIDENCE_RETRIEVAL_STATUSES = ("success", "partial", "failed", "unavailable", "manual")

# -- evidence links (Step 3 table, general polymorphic purpose) --------------

EVIDENCE_LINK_ENTITY_TYPES = (
    "permission_assessment", "identity_check", "upstream_source",
    "licence_determination", "conflict_event",
)
EVIDENCE_LINK_ROLES = ("supports", "contradicts", "superseded_by", "reference")

# -- identity verification signals (Step 6) -----------------------------------

IDENTITY_SIGNAL_TYPES = (
    "provider_dataset_id", "canonical_dataset_url", "organization", "repository_owner",
    "official_domain", "dataset_name", "version", "revision", "dataset_card_identifier",
    "upstream_citation", "checksum_or_release_tag",
)

# -- upstream sources (Step 10, own table -- documented deviation from --------
# -- Step 3's "recommended" list, since Step 10's field set doesn't fit --------
# -- any of the other 8 named tables) ------------------------------------------

# Independent of the main case's own `identity_status` -- whether *this*
# upstream source's own identity/rights have themselves been verified.
UPSTREAM_VERIFICATION_STATUSES = ("not_verified", "partial", "verified", "conflicting")

# -- conflict detection (Step 12, folded into verification_events) -----------

CONFLICT_TYPES = (
    "declared_vs_licence_file", "provider_vs_repository_metadata",
    "permissive_language_vs_restrictive_terms", "licence_vs_upstream_unknown",
    "commercial_use_vs_consent_missing", "other",
)
CONFLICT_RESOLUTION_STATUSES = ("unresolved", "resolved", "accepted_risk", "dismissed")

# -- verification events (append-only case history) --------------------------

VERIFICATION_EVENT_TYPES = (
    "case_created", "evidence_collected", "evidence_collection_failed",
    "manual_evidence_added", "evidence_refreshed", "identity_assessed",
    "licence_normalized", "permission_assessed", "permission_reviewed",
    "upstream_added", "upstream_verified", "conflict_detected", "conflict_resolved",
    "case_finalized", "case_cancelled", "case_expired", "reverification_checked",
    "source_changed_detected", "withdrawal_notice_recorded",
)

# -- withdrawal notices (Step 15) ---------------------------------------------

WITHDRAWAL_IMPACT_STATUSES = ("pending_assessment", "assessed")

# -- bounded, safe evidence retrieval (Step 17) -------------------------------

EVIDENCE_CONTENT_TYPES = (
    "text/plain", "text/markdown", "text/html", "application/json", "application/pdf",
)
MAX_EVIDENCE_RESPONSE_BYTES = 2_000_000
MAX_EVIDENCE_CONTENT_CHARS = 200_000
MAX_RETRIES_PER_EVIDENCE_FETCH = 0
EVIDENCE_FETCH_TIMEOUT_SECONDS = 5.0
MAX_REDIRECTS_PER_EVIDENCE_FETCH = 1
