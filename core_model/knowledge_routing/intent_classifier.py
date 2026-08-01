"""Deterministic, rule-based primary + secondary intent classification
(Step 4). Same structural template as `core_model.admin_assistant.
intent.classify_intent`: bilingual keyword lexicons loaded from the
checksummed policy file, `_hits()`-style matching, no LLM.
"""

from __future__ import annotations

from core_model.knowledge_routing import INTENTS, POLICY_VERSION
from core_model.knowledge_routing.policy_loader import get_policy
from core_model.knowledge_routing.reason_codes import INTENT_REASON_CODE_BY_VALUE
from core_model.knowledge_routing.result_types import LayerResult


def _hits(text_lower: str, lexicon: list[str]) -> tuple[str, ...]:
    return tuple(word for word in lexicon if word and word.lower() in text_lower)


def classify_intent(text: str) -> LayerResult:
    policy = get_policy()
    text_lower = text.lower()
    intent_lexicons = policy.get("intents", {})

    scored: list[tuple[str, tuple[str, ...]]] = []
    for intent in INTENTS:
        entry = intent_lexicons.get(intent)
        if not entry:
            continue
        hits = _hits(text_lower, entry.get("keywords_en", [])) + _hits(
            text_lower, entry.get("keywords_ta", [])
        )
        if hits:
            scored.append((intent, hits))

    if not scored:
        return LayerResult(
            value="unknown",
            confidence_band="unknown",
            reason_codes=(INTENT_REASON_CODE_BY_VALUE["unknown"],),
            matched_rules=(),
            policy_version=POLICY_VERSION,
        )

    scored.sort(key=lambda pair: len(pair[1]), reverse=True)
    primary_intent, primary_hits = scored[0]
    secondary = tuple(intent for intent, _ in scored[1:] if intent != primary_intent)

    confidence_band = "high" if len(primary_hits) >= 2 else "medium"
    all_matched = tuple(dict.fromkeys(hit for _, hits in scored for hit in hits))

    return LayerResult(
        value=primary_intent,
        confidence_band=confidence_band,
        reason_codes=(INTENT_REASON_CODE_BY_VALUE[primary_intent],),
        matched_rules=all_matched,
        policy_version=POLICY_VERSION,
        secondary_values=secondary,
    )


__all__ = ["classify_intent"]
