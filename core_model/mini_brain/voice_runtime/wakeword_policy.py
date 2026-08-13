"""MB-26: Wake-word Policy -- pure, and deliberately trivial: this
module exists solely to make the "no always-on wake-word listening"
non-goal structurally provable rather than merely documented.
`evaluate_wakeword()` always returns an inactive decision regardless
of its inputs. No code anywhere in this package starts a thread,
loop, or background task -- this module's own AST safety test
verifies that directly against this file's source, and the service's
diagnostics reports this function's actual (always-False) result
rather than echoing the raw `voice_wakeword_enabled` settings flag,
which currently has no functional effect anywhere in the codebase.
"""

from __future__ import annotations

from typing import Any


def evaluate_wakeword(*, wakeword_enabled: bool, session_mode: str) -> dict[str, Any]:
    return {
        "active": False,
        "reason": "wake-word always-on listening is an explicit MB-26 non-goal and is never implemented",
    }
