"""MB-04C: Retry Strategy -- a pure DECISION function only. It never
executes a retry itself (that happens once, in the service layer,
structurally incapable of looping since it is a single `if` block, not
a loop). "Never retry unsafe requests": a blocked/training-boundary
Response Plan or a detected forbidden claim in the first response both
skip retry entirely and say why, rather than attempting to regenerate
around a safety block.
"""

from __future__ import annotations

from typing import Any


def should_retry(
    *, length_issues: list[str], echo_severity: str, blocked: bool, forbidden_claim_detected: bool,
) -> dict[str, Any]:
    if blocked:
        return {"retry": False, "reason": "blocked_response_never_retried"}
    if forbidden_claim_detected:
        return {"retry": False, "reason": "forbidden_claim_detected_never_retried"}
    if echo_severity == "dominant":
        return {"retry": True, "reason": "dominant_echo_detected", "bump_tokens": False}
    if "cut_off" in length_issues:
        return {"retry": True, "reason": "output_was_cut_off", "bump_tokens": True}
    if "too_short" in length_issues:
        return {"retry": True, "reason": "output_too_short", "bump_tokens": True}
    return {"retry": False, "reason": "no_retry_needed"}
