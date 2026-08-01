"""Phase 20 Step 11 -- `WebSourceVerificationService`.

A pure, monotonic escalation ladder: each verification level requires
every check the level below it required, plus one more. Never jumps
straight to a high level just because one check passed -- the public
answer metadata (Step 11's own requirement) must accurately report
only the level actually achieved.
"""

from __future__ import annotations

from core_model.web_search import VERIFICATION_LEVELS

_LEVEL_RANK = {level: rank for rank, level in enumerate(VERIFICATION_LEVELS)}


def evaluate_verification_level(
    *,
    trust_level: str,
    url_valid: bool,
    fetch_attempted: bool,
    fetch_succeeded: bool,
    content_relevant: bool,
    freshness_status: str,
    injection_status: str,
    cross_source_confirmed: bool,
) -> str:
    if trust_level == "blocked" or not url_valid:
        return "search_result_only"

    level = "search_result_only"
    if trust_level != "unknown":
        level = "domain_verified"
    else:
        return level

    if not (fetch_attempted and fetch_succeeded):
        return level
    level = "page_fetched"

    content_safe = injection_status in ("clean", "warning")
    if not (content_relevant and content_safe and freshness_status != "undated"):
        return level
    level = "content_verified"

    if not cross_source_confirmed:
        return level
    level = "cross_source_verified"

    if trust_level == "official":
        level = "official_source_verified"
    return level


def meets_required_level(achieved: str, required: str) -> bool:
    return _LEVEL_RANK[achieved] >= _LEVEL_RANK[required]


__all__ = ["evaluate_verification_level", "meets_required_level"]
