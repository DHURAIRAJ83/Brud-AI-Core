"""Learning-target recommendation engine (Step 10).

Independent from, but informed by, the execution-route recommendation
(`route_recommender.py`) -- these are always two separate fields, never
merged into one. No value this engine can return grants training
approval by itself; `future_training_candidate` only flags content for
a later, separately-approved training cycle (Phase 18+ decides that).

Precedence (8 steps, one per `LEARNING_TARGETS` value):
  1. `blocked`                    -- safety_value == likely_disallowed
  2. `do_not_learn`                -- domain == personal_context (personal/
                                      user-specific content never becomes a
                                      training signal)
  3. `tool_required`               -- execution_route == tool (deterministic
                                      results carry no learning signal)
  4. `web_preferred`               -- freshness in (real_time, time_sensitive)
                                      (volatile facts must never be baked
                                      into model weights)
  5. `rag_only`                    -- evidence_requirement ==
                                      internal_evidence_required (stable
                                      fact suitable for an approved
                                      knowledge space, not model weights)
  6. `evaluation_only`             -- execution_route in (clarify,
                                      insufficient) (session-specific /
                                      operational; useful for evaluation
                                      only)
  7. `future_training_candidate`   -- domain in the timeless-language set
                                      AND freshness == timeless AND
                                      confidence is not low/unknown (a
                                      timeless linguistic/reasoning skill
                                      worth generalizing)
  8. `core_model`                  -- fallback: everything else that
                                      reached `core_model` execution route
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.knowledge_routing import LEARNING_TARGETS, POLICY_VERSION
from core_model.knowledge_routing.reason_codes import TARGET_REASON_CODE_BY_VALUE

_TIMELESS_LANGUAGE_DOMAINS = frozenset({"tamil_language", "english_language", "tanglish_input"})


@dataclass(frozen=True)
class LearningTargetRecommendation:
    learning_target: str
    confidence_band: str
    reason_codes: tuple[str, ...]
    matched_rules: tuple[str, ...]
    policy_version: str
    grants_training_approval: bool = False
    requires_human_review: bool = False


def recommend_learning_target(
    *,
    execution_route: str,
    safety_value: str,
    domain: str,
    freshness: str,
    evidence_value: str,
    route_confidence_band: str,
) -> LearningTargetRecommendation:
    if safety_value == "likely_disallowed":
        target = "blocked"
        confidence = "high"
        matched = ("safety:likely_disallowed",)
        review = True
    elif domain == "personal_context":
        target = "do_not_learn"
        confidence = "high"
        matched = ("domain:personal_context",)
        review = False
    elif execution_route == "tool":
        target = "tool_required"
        confidence = "high"
        matched = ("execution_route:tool",)
        review = False
    elif freshness in ("real_time", "time_sensitive"):
        target = "web_preferred"
        confidence = "medium"
        matched = (f"freshness:{freshness}",)
        review = False
    elif evidence_value == "internal_evidence_required":
        target = "rag_only"
        confidence = "medium"
        matched = ("evidence:internal_evidence_required",)
        review = False
    elif execution_route in ("clarify", "insufficient", "refuse", "memory"):
        target = "evaluation_only"
        confidence = "low"
        matched = (f"execution_route:{execution_route}",)
        review = execution_route == "insufficient"
    elif (
        domain in _TIMELESS_LANGUAGE_DOMAINS
        and freshness == "timeless"
        and route_confidence_band in ("high", "medium")
    ):
        target = "future_training_candidate"
        confidence = "medium"
        matched = (f"domain:{domain}", "freshness:timeless")
        review = True
    else:
        target = "core_model"
        confidence = "low"
        matched = ("fallback:core_model",)
        review = False

    assert target in LEARNING_TARGETS
    return LearningTargetRecommendation(
        learning_target=target,
        confidence_band=confidence,
        reason_codes=(TARGET_REASON_CODE_BY_VALUE[target],),
        matched_rules=matched,
        policy_version=POLICY_VERSION,
        grants_training_approval=False,
        requires_human_review=review,
    )


__all__ = ["LearningTargetRecommendation", "recommend_learning_target"]
