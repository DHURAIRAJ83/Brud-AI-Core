"""MB-10: Research Recommendation Engine -- pure. Suggests which of
the admin's own real decision options (reject / edit / accept_draft /
request_more_research / request_different_providers /
request_local_draft) best fits the already-computed research quality
report. This is advisory only -- the admin decides regardless of what
is suggested here, and nothing here executes anything.
"""

from __future__ import annotations

from typing import Any

LOW_QUALITY_THRESHOLD = 40.0
GOOD_QUALITY_THRESHOLD = 70.0


def recommend_next_step(
    *, overall_quality: float, has_unresolved_conflicts: bool, provider_count: int,
) -> dict[str, Any]:
    evidence = {
        "overall_quality": overall_quality, "has_unresolved_conflicts": has_unresolved_conflicts,
        "provider_count": provider_count,
    }

    if provider_count == 0:
        return {
            "recommendation": "request_local_draft",
            "why": "no provider outputs were supplied -- a local draft can still be prepared from existing evidence",
            "evidence": evidence,
        }
    if has_unresolved_conflicts and overall_quality < LOW_QUALITY_THRESHOLD:
        return {
            "recommendation": "request_different_providers",
            "why": f"unresolved conflicts and overall_quality {overall_quality} below {LOW_QUALITY_THRESHOLD} -- the current provider mix disagrees too much to trust",
            "evidence": evidence,
        }
    if overall_quality < LOW_QUALITY_THRESHOLD:
        return {
            "recommendation": "request_more_research",
            "why": f"overall_quality {overall_quality} below {LOW_QUALITY_THRESHOLD} -- evidence is too thin to draft from yet",
            "evidence": evidence,
        }
    if overall_quality >= GOOD_QUALITY_THRESHOLD:
        return {
            "recommendation": "accept_draft",
            "why": f"overall_quality {overall_quality} meets or exceeds {GOOD_QUALITY_THRESHOLD}",
            "evidence": evidence,
        }
    return {
        "recommendation": "edit",
        "why": f"overall_quality {overall_quality} is moderate -- admin review and edits are recommended before proceeding",
        "evidence": evidence,
    }
