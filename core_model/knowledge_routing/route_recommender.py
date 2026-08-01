"""Execution-route recommendation engine (Step 9).

A literal, ordered if/elif precedence chain -- never a weighted score,
never every route tried sequentially at request time. Gate conditions
(unsafe, ambiguous) are checked first so an unsafe request is never
reclassified as merely needing clarification, and an ambiguous request
is never allowed to reach a route decision it cannot safely support.

Precedence (8 steps, one per `EXECUTION_ROUTES` value):
  1. `refuse`      -- safety_value == likely_disallowed
  2. `clarify`      -- ambiguity_value == ambiguous
  3. `memory`        -- domain == personal_context (the user's own prior
                        context/preference; never routed through
                        model/RAG/web)
  4. `tool`          -- evidence_requirement == deterministic_tool_required
  5. `trusted_web`   -- evidence_requirement == external_verified_evidence_required
  6. `approved_rag`  -- evidence_requirement == internal_evidence_required
  7. `core_model`    -- evidence_requirement == model_knowledge_ok
  8. `insufficient`  -- fallback: no viable evidence path was determined

This function only *recommends* -- it never calls Model, RAG, Web, Tool,
or Memory itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core_model.knowledge_routing import EXECUTION_ROUTES, POLICY_VERSION

_ROUTE_REASON_CODE = {
    "refuse": "ROUTE_REFUSE_UNSAFE",
    "clarify": "ROUTE_CLARIFY_AMBIGUOUS",
    "memory": "ROUTE_MEMORY_PERSONAL_CONTEXT",
    "tool": "ROUTE_TOOL_DETERMINISTIC",
    "trusted_web": "ROUTE_WEB_CURRENT_INFORMATION",
    "approved_rag": "ROUTE_RAG_APPROVED_INTERNAL",
    "core_model": "ROUTE_CORE_STABLE_LANGUAGE",
    "insufficient": "ROUTE_INSUFFICIENT_NO_EVIDENCE_PATH",
}

# Advisory only in this phase -- no execution code consumes this ordering
# yet (plan doc §6). It documents what a future orchestration layer could
# try next if the primary route is unavailable at request time.
_FALLBACK_ORDER: dict[str, tuple[str, ...]] = {
    "refuse": (),
    "clarify": (),
    "memory": ("core_model", "insufficient"),
    "tool": ("insufficient",),
    "trusted_web": ("approved_rag", "core_model", "insufficient"),
    "approved_rag": ("trusted_web", "core_model", "insufficient"),
    "core_model": ("approved_rag", "insufficient"),
    "insufficient": (),
}


@dataclass(frozen=True)
class RouteRecommendation:
    execution_route: str
    confidence_band: str
    reason_codes: tuple[str, ...]
    matched_rules: tuple[str, ...]
    policy_version: str
    route_blockers: tuple[str, ...] = field(default_factory=tuple)
    training_risk: str = "none"
    requires_human_review: bool = False
    fallback_route_order: tuple[str, ...] = field(default_factory=tuple)


def recommend_execution_route(
    *,
    safety_value: str,
    ambiguity_value: str,
    domain: str,
    evidence_value: str,
) -> RouteRecommendation:
    if safety_value == "likely_disallowed":
        route = "refuse"
        confidence = "high"
        matched = ("safety:likely_disallowed",)
        blockers = ("safety_risk",)
        review = True
    elif ambiguity_value == "ambiguous":
        route = "clarify"
        confidence = "medium"
        matched = ("ambiguity:ambiguous",)
        blockers = ("ambiguous_request",)
        review = False
    elif domain == "personal_context":
        route = "memory"
        confidence = "medium"
        matched = ("domain:personal_context",)
        blockers = ()
        review = False
    elif evidence_value == "deterministic_tool_required":
        route = "tool"
        confidence = "high"
        matched = ("evidence:deterministic_tool_required",)
        blockers = ()
        review = False
    elif evidence_value == "external_verified_evidence_required":
        route = "trusted_web"
        confidence = "medium"
        matched = ("evidence:external_verified_evidence_required",)
        blockers = ()
        review = False
    elif evidence_value == "internal_evidence_required":
        route = "approved_rag"
        confidence = "medium"
        matched = ("evidence:internal_evidence_required",)
        blockers = ()
        review = False
    elif evidence_value == "model_knowledge_ok":
        route = "core_model"
        confidence = "medium"
        matched = ("evidence:model_knowledge_ok",)
        blockers = ()
        review = False
    else:
        route = "insufficient"
        confidence = "unknown"
        matched = (f"evidence:{evidence_value}",)
        blockers = ("no_evidence_path",)
        review = evidence_value == "blocked"

    assert route in EXECUTION_ROUTES
    training_risk = "high" if route in ("refuse", "insufficient") else "none"

    return RouteRecommendation(
        execution_route=route,
        confidence_band=confidence,
        reason_codes=(_ROUTE_REASON_CODE[route],),
        matched_rules=matched,
        policy_version=POLICY_VERSION,
        route_blockers=blockers,
        training_risk=training_risk,
        requires_human_review=review,
        fallback_route_order=_FALLBACK_ORDER[route],
    )


__all__ = ["RouteRecommendation", "recommend_execution_route"]
