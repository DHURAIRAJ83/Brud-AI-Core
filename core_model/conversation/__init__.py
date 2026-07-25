"""Phase 17 conversation-memory pure-function package.

Conversation memory is purpose-bound, consent-aware, inspectable,
correctable, and deletable -- never hidden permanent profiling. Every
enum below is the single source of truth shared by the backend
services, matching the corresponding CHECK constraints in
``backend/database/schema.py``'s ``PHASE17_SCHEMA``.
"""

from __future__ import annotations

SESSION_MODES = ("stateless", "session_memory", "consented_memory", "private_no_persist")
SESSION_STATUSES = ("draft", "active", "paused", "expired", "closed", "failed", "archived")
PARTICIPANT_TYPES = ("admin", "internal_test_user", "future_user_reference")
TURN_ROLES = ("system", "user", "assistant")
POLICY_LIFECYCLE_STATUSES = ("draft", "validated", "active", "deprecated", "archived")

SUMMARY_STATUSES = ("draft", "validated", "accepted", "rejected", "superseded")
SUMMARY_GENERATION_METHODS = ("deterministic_extract", "bounded_model_summary", "hybrid")

CONSENT_STATUSES = ("pending", "active", "expired", "revoked", "rejected")

MEMORY_CATEGORIES = (
    "language_preference",
    "format_preference",
    "confirmed_name_or_alias",
    "learning_goal",
    "course_progress",
    "project_preference",
    "user_confirmed_fact",
    "conversation_follow_up",
)

# Sensitive categories are rejected structurally: they are not members of
# MEMORY_CATEGORIES, so the database CHECK constraint on
# memory_items.category can never accept them. This tuple exists only so
# a proposed category can be given an honest, specific rejection reason
# instead of a generic "invalid category" error.
FORBIDDEN_MEMORY_CATEGORIES = (
    "password",
    "api_key",
    "access_token",
    "private_key",
    "payment_card",
    "bank_account",
    "authentication_cookie",
    "precise_location",
    "medical_diagnosis",
    "political_affiliation",
    "religion",
    "sexual_information",
    "criminal_record",
    "biometric_data",
)

MEMORY_PURPOSES = (
    "language_preference",
    "response_format_preference",
    "course_progress",
    "learning_goal",
    "project_context",
    "user_confirmed_profile",
    "conversation_continuity",
)

MEMORY_ITEM_STATUSES = (
    "proposed",
    "awaiting_confirmation",
    "active",
    "superseded",
    "expired",
    "revoked",
    "rejected",
    "deleted",
    "archived",
)
MEMORY_CREATION_SOURCES = (
    "explicit_user_request",
    "admin_created_for_test",
    "assistant_proposed",
    "system_derived",
)
MEMORY_CONFIDENCE_TYPES = (
    "user_confirmed",
    "admin_test_fixture",
    "deterministically_extracted",
    "assistant_inferred",
)

RETRIEVAL_PROFILE_STATUSES = ("draft", "validated", "active", "deprecated", "archived")
CONFLICT_POLICIES = ("prefer_recent", "prefer_user_confirmed", "exclude_conflicting")
CONFLICT_STATUSES = (
    "no_conflict",
    "duplicate",
    "supersedes_existing",
    "conflict_requires_confirmation",
    "stale_existing",
)

CONTEXT_ITEM_TYPES = (
    "conversation_turn",
    "conversation_summary",
    "memory_item",
    "rag_chunk",
    "system_instruction",
    "current_request",
)
INJECTION_STATUSES = ("clean", "warning", "quarantined", "blocked")

RESPONSE_STATUSES = (
    "completed",
    "completed_with_warning",
    "insufficient_evidence",
    "memory_conflict",
    "consent_required",
    "retrieval_failed",
    "generation_failed",
    "blocked_context",
    "session_closed",
)

EVALUATION_SUITE_STATUSES = ("draft", "validated", "active", "retired", "archived")
LANGUAGE_CATEGORIES = ("ta", "en", "tgl", "mixed", "unknown")
SAFETY_STATUSES = ("safe", "warning", "blocked", "requires_review")

CONSENT_REQUIRED_MESSAGE_TA = "இந்த தகவலை நினைவில் வைக்க உங்கள் ஒப்புதல் தேவை."
CONSENT_REQUIRED_MESSAGE_EN = "Your consent is required before this can be remembered."
