"""Phase 19 Step 3 -- deterministic gap-eligibility policy.

`determine_gap_eligibility()` is a **pure function**: Phase 18's own
already-computed `PublicChatResponse` fields (`resolved_route`,
`safety_status`, `evidence_status`, `confidence_band`,
`fallbacks_attempted`) plus a small set of capture-time signals in,
one `GapEligibilityResult` out. It never touches the database, never
calls the model/RAG/web/tool, and never mutates anything -- see
`KnowledgeGapCaptureService` for the (also conservative) integration
layer that calls this and decides whether to actually write a row.

Design notes (see plan doc section 4 for the full rationale):

- A route that resolved to `insufficient` because of
  `fallbacks_attempted=["model_assignment_unavailable"]` or
  `["classification_failed"]` is treated as `operational_failure`, not
  `knowledge_gap` -- Phase 18 uses that same generic reason both for a
  genuinely unconfigured model *and* for an unexpected exception
  caught by its broad `except Exception` handler, so there is no
  reliable signal to distinguish "the model doesn't know this" from
  "something broke." Erring toward `operational_failure` directly
  upholds the invariant *"Knowledge gap != Temporary provider
  failure"* -- never over-claiming a factual gap when the cause is
  genuinely unknown.
- `output_safety_blocked` / `input_safety_refused` / `safety_status in
  ("refused", "output_blocked")` are always `safety_event`, always
  `eligible_for_gap_registry=False` -- Step 14 explicitly excludes
  safety refusals from automatic capture, and the non-negotiable rules
  require them to be recorded as safety events, not knowledge gaps.
- A first-time `clarify` response is captured as `clarification_event`
  with `eligible_for_gap_registry=True` (so `KnowledgeGapCaptureService`
  can create the bounded tracking case Step 15 needs, at case status
  `needs_clarification`) but `review_required=False` -- it does not
  yet count as a reviewable gap. Only once the caller determines
  `unresolved_after_clarification=True` (bounded attempt count
  exceeded, still ambiguous) does this reclassify to
  `event_type="knowledge_gap"`, `reason_codes=("unresolved_after_clarification",)`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core_model.knowledge_gap import RETENTION_POLICIES

_SAFETY_FALLBACK_REASONS = frozenset({"output_safety_blocked", "input_safety_refused"})

_WEB_FALLBACK_REASONS = frozenset({"trusted_web_unavailable"})
_TOOL_FALLBACK_REASONS = frozenset({"tool_unavailable"})
# Phase 20: the Web/Tool route was actually *attempted* (a healthy
# provider/tool gateway was reached) and still couldn't answer -- a
# more specific capability-gap signal than the generic
# "never even attempted" fallbacks above, but still the same
# `web_capability_gap`/`tool_capability_gap` event_type (Non-negotiable
# rule: "Web unavailable != Core model should guess" applies equally
# whether the route was never attempted or attempted-and-insufficient).
_WEB_ATTEMPTED_FALLBACK_REASONS = frozenset(
    {
        "web_no_trusted_source",
        "web_evidence_insufficient",
        "web_quota_exceeded",
        "web_fetch_blocked",
    }
)
_TOOL_ATTEMPTED_FALLBACK_REASONS = frozenset({"tool_unsupported", "tool_input_invalid"})
_WEB_ATTEMPTED_REASON_CODE = {
    "web_no_trusted_source": "web_no_trusted_source",
    "web_evidence_insufficient": "web_evidence_insufficient",
    "web_quota_exceeded": "web_quota_exceeded",
    "web_fetch_blocked": "web_fetch_blocked",
}
_TOOL_ATTEMPTED_REASON_CODE = {
    "tool_unsupported": "tool_unsupported_operation",
    "tool_input_invalid": "tool_input_invalid",
}
_RAG_KNOWLEDGE_GAP_FALLBACK_REASONS = frozenset(
    {"rag_scope_unavailable", "rag_insufficient_evidence"}
)
_OPERATIONAL_FALLBACK_REASONS = frozenset({"model_assignment_unavailable", "classification_failed"})
_MEMORY_OPERATIONAL_REASONS = frozenset({"memory_unavailable"})
_MEMORY_NOT_APPLICABLE_REASONS = frozenset({"memory_consent_required"})

_LOW_EVIDENCE_STATUSES = frozenset({"insufficient", "conflicting"})
_LOW_CONFIDENCE_BANDS = frozenset({"low", "unknown"})

_NEGATIVE_FEEDBACK_REASONS = frozenset(
    {
        "stale_information",
        "source_conflict",
        "unknown_question",
        "wrong_answer",
        "missing_evidence",
        "wrong_language",
        "unsafe_answer",
        "unhelpful",
    }
)


@dataclass(frozen=True)
class GapEligibilityResult:
    eligible_for_gap_registry: bool
    event_type: str
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    retention_policy: str = "standard"
    review_required: bool = False

    def __post_init__(self) -> None:
        if self.retention_policy not in RETENTION_POLICIES:
            raise ValueError(f"unknown retention_policy: {self.retention_policy!r}")


def _first(reasons: frozenset[str], fallbacks: tuple[str, ...]) -> str | None:
    for fallback in fallbacks:
        if fallback in reasons:
            return fallback
    return None


def determine_gap_eligibility(
    *,
    resolved_route: str,
    safety_status: str,
    evidence_status: str,
    confidence_band: str = "unknown",
    fallbacks_attempted: tuple[str, ...] = (),
    clarification_required: bool = False,
    unresolved_after_clarification: bool = False,
    negative_feedback_reason: str | None = None,
) -> GapEligibilityResult:
    fallbacks_attempted = tuple(fallbacks_attempted)

    # -- 1. Safety always wins, and is never a knowledge gap
    if (
        safety_status in ("refused", "output_blocked")
        or _first(_SAFETY_FALLBACK_REASONS, fallbacks_attempted) is not None
    ):
        reason = "output_safety_block" if safety_status == "output_blocked" else "policy_refusal"
        return GapEligibilityResult(
            eligible_for_gap_registry=False,
            event_type="safety_event",
            reason_codes=(reason,),
            retention_policy="not_retained",
            review_required=False,
        )

    # -- 2. Clarification
    if resolved_route == "clarify" or clarification_required:
        if unresolved_after_clarification:
            return GapEligibilityResult(
                eligible_for_gap_registry=True,
                event_type="knowledge_gap",
                reason_codes=("unresolved_after_clarification",),
                retention_policy="standard",
                review_required=True,
            )
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="clarification_event",
            reason_codes=("clarification_pending_followup",),
            retention_policy="standard",
            review_required=False,
        )

    # -- 3. Capability gaps (Web/Tool recommended but unavailable, or
    # attempted and still insufficient -- both are the same
    # event_type, since "attempted and failed" is still evidence the
    # capability needs work, not a factual model-knowledge gap)
    if _first(_WEB_FALLBACK_REASONS, fallbacks_attempted):
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="web_capability_gap",
            reason_codes=("web_search_unavailable",),
            retention_policy="standard",
            review_required=False,
        )
    web_attempted_reason = _first(_WEB_ATTEMPTED_FALLBACK_REASONS, fallbacks_attempted)
    if web_attempted_reason:
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="web_capability_gap",
            reason_codes=(_WEB_ATTEMPTED_REASON_CODE[web_attempted_reason],),
            retention_policy="standard",
            review_required=False,
        )
    if _first(_TOOL_FALLBACK_REASONS, fallbacks_attempted):
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="tool_capability_gap",
            reason_codes=("tool_execution_unavailable",),
            retention_policy="standard",
            review_required=False,
        )
    tool_attempted_reason = _first(_TOOL_ATTEMPTED_FALLBACK_REASONS, fallbacks_attempted)
    if tool_attempted_reason:
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="tool_capability_gap",
            reason_codes=(_TOOL_ATTEMPTED_REASON_CODE[tool_attempted_reason],),
            retention_policy="standard",
            review_required=False,
        )

    # -- 4. RAG-evidence knowledge gaps
    rag_reason = _first(_RAG_KNOWLEDGE_GAP_FALLBACK_REASONS, fallbacks_attempted)
    if rag_reason:
        mapped = (
            "rag_content_missing"
            if rag_reason == "rag_scope_unavailable"
            else "rag_retrieval_insufficient"
        )
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="knowledge_gap",
            reason_codes=(mapped,),
            retention_policy="standard",
            review_required=True,
        )

    # -- 5. Memory-route special cases
    if _first(_MEMORY_NOT_APPLICABLE_REASONS, fallbacks_attempted):
        return GapEligibilityResult(
            eligible_for_gap_registry=False,
            event_type="not_applicable",
            reason_codes=("no_actionable_signal",),
            retention_policy="not_retained",
        )
    if _first(_MEMORY_OPERATIONAL_REASONS, fallbacks_attempted):
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="operational_failure",
            reason_codes=("memory_unavailable",),
            retention_policy="standard",
            review_required=False,
        )

    # -- 6. Generic operational fallbacks (uncertain cause -- never a knowledge gap)
    operational_reason = _first(_OPERATIONAL_FALLBACK_REASONS, fallbacks_attempted)
    if operational_reason:
        mapped = (
            "model_unavailable"
            if operational_reason == "model_assignment_unavailable"
            else "internal_error"
        )
        return GapEligibilityResult(
            eligible_for_gap_registry=True,
            event_type="operational_failure",
            reason_codes=(mapped,),
            retention_policy="standard",
            review_required=False,
        )

    # -- 7. A successfully executed route (core_model/approved_rag/memory,
    # plus Phase 20's trusted_web/tool once they actually resolve to
    # themselves rather than falling back to insufficient)
    if resolved_route in ("core_model", "approved_rag", "memory", "trusted_web", "tool"):
        if negative_feedback_reason in _NEGATIVE_FEEDBACK_REASONS:
            mapped = {
                "wrong_language": "language_failure",
                "unsafe_answer": "safety_event",
                "unhelpful": None,
            }.get(negative_feedback_reason)
            if mapped == "language_failure":
                return GapEligibilityResult(
                    eligible_for_gap_registry=True,
                    event_type="language_failure",
                    reason_codes=("wrong_output_language",),
                    retention_policy="standard",
                    review_required=True,
                )
            if mapped == "safety_event":
                return GapEligibilityResult(
                    eligible_for_gap_registry=False,
                    event_type="safety_event",
                    reason_codes=("policy_refusal",),
                    retention_policy="not_retained",
                )
            return GapEligibilityResult(
                eligible_for_gap_registry=True,
                event_type="feedback_issue",
                reason_codes=(negative_feedback_reason,),
                retention_policy="standard",
                review_required=True,
            )
        if evidence_status in _LOW_EVIDENCE_STATUSES or confidence_band in _LOW_CONFIDENCE_BANDS:
            # Low confidence/insufficient evidence alone (no negative
            # feedback) is not auto-captured -- Step 14 only lists "low
            # confidence *with not-helpful feedback*" as eligible.
            return GapEligibilityResult(
                eligible_for_gap_registry=False,
                event_type="not_applicable",
                reason_codes=("no_actionable_signal",),
                retention_policy="not_retained",
            )
        return GapEligibilityResult(
            eligible_for_gap_registry=False,
            event_type="not_applicable",
            reason_codes=("successful_but_disliked",)
            if negative_feedback_reason
            else ("no_actionable_signal",),
            retention_policy="not_retained",
        )

    # -- 8. Fallback: any other insufficient with no matched reason
    return GapEligibilityResult(
        eligible_for_gap_registry=True,
        event_type="knowledge_gap",
        reason_codes=("model_knowledge_missing",),
        retention_policy="standard",
        review_required=True,
    )


__all__ = ["GapEligibilityResult", "determine_gap_eligibility"]
