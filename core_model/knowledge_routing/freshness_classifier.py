"""Deterministic freshness/volatility classification (Step 5).

Keyword-signal detection first (loaded from the checksummed policy
file), then a conservative domain-based fallback for the two directions
that have no dedicated keyword lexicon:

- Typically-timeless domains (language grammar/meaning, mathematics,
  translation, creative writing) fall back to `timeless` only when no
  freshness keyword fired.
- Typically-volatile domains (`current_affairs`, `government_services`)
  fall back to `time_sensitive` even with no explicit keyword hit, so a
  volatile-domain question never silently defaults to `unknown` and
  then `core_model` merely for lack of a keyword match (plan doc §4).

Unmatched text with no domain-based signal stays `unknown` -- never
guessed as `timeless` (a stale-answer risk) or `real_time` (an
over-triggering risk).
"""

from __future__ import annotations

import re

from core_model.knowledge_routing import POLICY_VERSION
from core_model.knowledge_routing.policy_loader import get_policy
from core_model.knowledge_routing.reason_codes import FRESHNESS_REASON_CODE_BY_VALUE
from core_model.knowledge_routing.result_types import LayerResult

REFERENCE_YEAR = 2026
_HISTORICAL_YEAR_GAP = 2
_YEAR_TOKEN_RE = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")

_TIMELESS_DOMAINS = frozenset(
    {
        "tamil_language", "english_language", "tanglish_input", "mathematics",
        "translation", "creative_writing",
    }
)
_SLOW_CHANGING_DOMAINS = frozenset(
    {"science", "social_science", "industry_knowledge", "general_knowledge"}
)
_VOLATILE_DOMAINS = frozenset({"current_affairs", "government_services"})


def _hits(text_lower: str, lexicon: list[str]) -> tuple[str, ...]:
    return tuple(word for word in lexicon if word and word.lower() in text_lower)


def classify_freshness(text: str, *, domain: str | None = None) -> LayerResult:
    policy = get_policy()
    text_lower = text.lower()
    signals = policy.get("freshness_signals", {})

    real_time_hits = _hits(text_lower, signals.get("real_time", {}).get("keywords_en", [])) + _hits(
        text_lower, signals.get("real_time", {}).get("keywords_ta", [])
    )
    if real_time_hits:
        return LayerResult(
            value="real_time",
            confidence_band="high" if len(real_time_hits) >= 2 else "medium",
            reason_codes=(FRESHNESS_REASON_CODE_BY_VALUE["real_time"],),
            matched_rules=real_time_hits,
            policy_version=POLICY_VERSION,
        )

    time_sensitive_hits = _hits(
        text_lower, signals.get("time_sensitive", {}).get("keywords_en", [])
    ) + _hits(text_lower, signals.get("time_sensitive", {}).get("keywords_ta", []))
    if time_sensitive_hits:
        return LayerResult(
            value="time_sensitive",
            confidence_band="high" if len(time_sensitive_hits) >= 2 else "medium",
            reason_codes=(FRESHNESS_REASON_CODE_BY_VALUE["time_sensitive"],),
            matched_rules=time_sensitive_hits,
            policy_version=POLICY_VERSION,
        )

    historical_hits = _hits(
        text_lower, signals.get("historical", {}).get("keywords_en", [])
    ) + _hits(text_lower, signals.get("historical", {}).get("keywords_ta", []))
    year_tokens = tuple(
        year for year in _YEAR_TOKEN_RE.findall(text)
        if REFERENCE_YEAR - int(year) >= _HISTORICAL_YEAR_GAP
    )
    if historical_hits or year_tokens:
        matched = tuple(dict.fromkeys((*historical_hits, *year_tokens)))
        return LayerResult(
            value="historical",
            confidence_band="high" if len(matched) >= 2 else "medium",
            reason_codes=(FRESHNESS_REASON_CODE_BY_VALUE["historical"],),
            matched_rules=matched,
            policy_version=POLICY_VERSION,
        )

    if domain in _VOLATILE_DOMAINS:
        return LayerResult(
            value="time_sensitive",
            confidence_band="low",
            reason_codes=(FRESHNESS_REASON_CODE_BY_VALUE["time_sensitive"],),
            matched_rules=(f"domain:{domain}",),
            policy_version=POLICY_VERSION,
        )

    if domain in _TIMELESS_DOMAINS:
        return LayerResult(
            value="timeless",
            confidence_band="low",
            reason_codes=(FRESHNESS_REASON_CODE_BY_VALUE["timeless"],),
            matched_rules=(f"domain:{domain}",),
            policy_version=POLICY_VERSION,
        )

    if domain in _SLOW_CHANGING_DOMAINS:
        return LayerResult(
            value="slow_changing",
            confidence_band="low",
            reason_codes=(FRESHNESS_REASON_CODE_BY_VALUE["slow_changing"],),
            matched_rules=(f"domain:{domain}",),
            policy_version=POLICY_VERSION,
        )

    return LayerResult(
        value="unknown",
        confidence_band="unknown",
        reason_codes=(FRESHNESS_REASON_CODE_BY_VALUE["unknown"],),
        matched_rules=(),
        policy_version=POLICY_VERSION,
    )


__all__ = ["REFERENCE_YEAR", "classify_freshness"]
