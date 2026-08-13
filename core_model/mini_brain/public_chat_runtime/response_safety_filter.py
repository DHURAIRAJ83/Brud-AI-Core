"""MB-23: Response Safety Filter -- pure. Decides whether a response's
already-computed `safety_status` (from `core_model.public_chat.
output_safety.evaluate_output_safety`, applied once, upstream, before
the reply ever reaches the user) should escalate the severity of any
feedback signal MB-23 records for this turn, and whether a dedicated
`safety_flag` signal should be raised. This module never re-filters
the reply text shown to the user -- that filtering has already
happened before this module ever runs.
"""

from __future__ import annotations

from typing import Any

_ESCALATING_STATUSES = frozenset({"refused", "output_blocked", "review_flagged"})


def evaluate_response_safety(*, safety_status: str) -> dict[str, Any]:
    escalate = safety_status in _ESCALATING_STATUSES
    return {
        "safety_status": safety_status, "escalate_severity": escalate,
        "raise_safety_flag_signal": escalate,
        "disclosure": "reads the already-computed safety_status from the public chat response -- this module never re-filters or modifies the reply shown to the user",
    }
