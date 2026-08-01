"""Pure policy constants and small combinators for the Phase 6 unified
governance layer (Quality, Duplicate, Conflict & Approval Integration).

No DB/IO here -- mirrors `core_model.manual_data`/`core_model.semantic_chunk`.
Every enum below is the single source of truth shared by the backend
services, matching the corresponding CHECK constraints in
`backend/database/schema.py`'s `PHASE27_SCHEMA` block.

This module governs six *existing*, independently-reviewed entity types
(see docs/data_studio/phase6_quality_duplicate_conflict_approval_plan.md
section 2 for why exactly these six and no phantom `rag_candidate`
table) -- it never introduces a seventh lifecycle or a competing
"approved" flag; it only adds a queue, grouped duplicate/conflict
tracking, and per-target-use approval on top.
"""

from __future__ import annotations

from typing import Any, TypedDict

GOVERNANCE_ENTITY_TYPES = (
    "document_page",
    "manual_data_record",
    "semantic_chunk",
    "structured_record_candidate",
    "document_candidate",
    "dataset_record",
)

REVIEW_STATUSES = (
    "open",
    "in_review",
    "waiting_for_correction",
    "waiting_for_source",
    "waiting_for_verification",
    "resolved",
    "rejected",
    "archived",
)

# A review item is genuinely "closed" (no longer needs a human decision)
# in exactly these statuses -- used by queue/summary counts so a
# resolved item never silently keeps counting as open work.
CLOSED_REVIEW_STATUSES = frozenset({"resolved", "rejected", "archived"})

REVIEW_PRIORITIES = ("low", "normal", "high", "urgent")

ISSUE_CATEGORIES = (
    "language_quality",
    "meaning_quality",
    "factual_accuracy",
    "source_traceability",
    "rights_restriction",
    "verification_missing",
    "exact_duplicate",
    "normalized_duplicate",
    "source_overlap",
    "dictionary_sense_conflict",
    "answer_conflict",
    "translation_conflict",
    "chunk_overlap",
    "chunk_gap",
    "revision_conflict",
    "ai_assisted_unreviewed",
    "high_risk_unverified",
    "time_sensitive_expired",
    "format_invalid",
    "export_duplicate",
)

SEVERITIES = ("info", "warning", "error", "critical")

DUPLICATE_TYPES = ("exact", "normalized", "source_locator", "export_duplicate")

CONFLICT_TYPES = (
    "dictionary_sense",
    "answer",
    "translation",
    "source_fact",
    "chunk_overlap",
    "chunk_gap",
    "revision",
    "classification",
)

GROUP_STATUSES = ("open", "resolved")

RESOLUTION_ACTIONS = (
    "keep_all",
    "choose_canonical",
    "mark_alternate",
    "merge_manually",
    "reject_selected",
    "archive_selected",
    "not_a_duplicate",
    "keep_both_with_context",
    "mark_alternate_sense",
    "mark_alternate_answer",
    "choose_preferred_translation",
    "request_domain_review",
    "request_source_verification",
    "resolve_with_new_revision",
)

# Distinct from `core_model.data_governance.TARGET_USES` (Phase 2's 6
# rights-registry target uses): this phase's target-use vocabulary adds
# `dataset_export`/`rag_handoff`, the two concrete handoff call sites
# Step 20's preflight guards (this phase adds no new target uses to the
# rights registry itself).
GOVERNANCE_TARGET_USES = (
    "rag",
    "training",
    "evaluation",
    "commercial",
    "public_export",
    "redistribution",
    "dataset_export",
    "rag_handoff",
)

APPROVAL_DECISIONS = ("allowed", "blocked", "needs_review", "not_requested")

# Conditions under which `GovernanceReviewService` creates (or reopens) a
# `governance_review_items` row for an entity (Step 13). Each is an
# idempotency key, not a free-text reason -- the service never opens two
# open review items for the same (entity_type, entity_public_id).
REVIEW_TRIGGER_REASONS = (
    "submitted_for_review",
    "blocking_quality_issue",
    "duplicate_group_opened",
    "conflict_group_opened",
    "rights_blocked",
    "verification_expired",
    "export_attempted_blocked",
)


class NormalizedIssue(TypedDict):
    issue_code: str
    issue_category: str
    severity: str
    is_blocking: bool
    blocking_targets: list[str]
    message: str


def compute_review_priority(issues: list[NormalizedIssue], *, is_high_risk: bool = False) -> str:
    """Deterministic priority from an entity's own normalized issues --
    never inferred from quality score alone (rule: high score must never
    hide a blocking issue, and priority must never either)."""

    blocking = [issue for issue in issues if issue.get("is_blocking")]
    if any(issue.get("severity") == "critical" for issue in blocking):
        return "urgent"
    if blocking and is_high_risk:
        return "urgent"
    if blocking:
        return "high"
    if any(issue.get("severity") == "error" for issue in issues):
        return "normal"
    if any(issue.get("severity") == "warning" for issue in issues):
        return "normal"
    return "low"


def blocking_issue_ids_for_target(
    issues: list[dict[str, Any]], target_use: str
) -> list[str]:
    """Issue public_ids that block *this specific* target use -- a
    blocking issue with `blocking_targets=['training']` never blocks
    `rag`, matching the task's "target-specific approval only" rule."""

    ids: list[str] = []
    for issue in issues:
        if not issue.get("is_blocking"):
            continue
        targets = issue.get("blocking_targets") or []
        if not targets or target_use in targets:
            ids.append(issue["public_id"])
    return ids


__all__ = [
    "GOVERNANCE_ENTITY_TYPES",
    "REVIEW_STATUSES",
    "CLOSED_REVIEW_STATUSES",
    "REVIEW_PRIORITIES",
    "ISSUE_CATEGORIES",
    "SEVERITIES",
    "DUPLICATE_TYPES",
    "CONFLICT_TYPES",
    "GROUP_STATUSES",
    "RESOLUTION_ACTIONS",
    "GOVERNANCE_TARGET_USES",
    "APPROVAL_DECISIONS",
    "REVIEW_TRIGGER_REASONS",
    "NormalizedIssue",
    "compute_review_priority",
    "blocking_issue_ids_for_target",
]
