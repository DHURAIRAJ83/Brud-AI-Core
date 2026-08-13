"""MB-22: Early Stop Monitor -- pure. Flags a possible early-stopping
signal from already-recorded loss history -- this module never stops
training itself; it only produces a recommendation for a human admin
or the service's own explicit `finalize()` call to act on.
"""

from __future__ import annotations

from typing import Any

DEFAULT_PATIENCE_STEPS = 5
DEFAULT_MIN_DELTA = 0.001


def monitor_early_stop(
    *, loss_history: list[float], patience_steps: int = DEFAULT_PATIENCE_STEPS, min_delta: float = DEFAULT_MIN_DELTA,
) -> dict[str, Any]:
    if len(loss_history) < 2:
        return {
            "should_consider_stopping": False, "best_loss": loss_history[0] if loss_history else None,
            "steps_since_improvement": 0, "disclosure": "not enough recorded loss points to evaluate",
        }

    best_loss = min(loss_history)
    best_index = loss_history.index(best_loss)
    steps_since_improvement = len(loss_history) - 1 - best_index
    should_consider_stopping = steps_since_improvement >= patience_steps

    recent_delta = loss_history[-1] - loss_history[-2]
    plateaued = abs(recent_delta) < min_delta

    return {
        "should_consider_stopping": should_consider_stopping, "best_loss": best_loss,
        "best_loss_index": best_index, "steps_since_improvement": steps_since_improvement,
        "plateaued": plateaued, "patience_steps": patience_steps, "min_delta": min_delta,
        "disclosure": (
            "a recommendation only -- this module never stops training itself; a human admin or the "
            "service's own explicit finalize() call decides whether to act on it"
        ),
    }
