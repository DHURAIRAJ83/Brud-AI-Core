"""MB-22: Metric Smoother -- pure. A simple, disclosed exponential
moving average over already-recorded metric points, for dashboard
display only -- never a replacement for the real, unsmoothed values
the database stores permanently.
"""

from __future__ import annotations

from typing import Any

DEFAULT_SMOOTHING_FACTOR = 0.1


def smooth_series(*, values: list[float | None], smoothing_factor: float = DEFAULT_SMOOTHING_FACTOR) -> list[float | None]:
    if not (0.0 < smoothing_factor <= 1.0):
        raise ValueError("smoothing_factor must be in (0, 1]")
    smoothed: list[float | None] = []
    running: float | None = None
    for value in values:
        if value is None:
            smoothed.append(running)
            continue
        running = value if running is None else (smoothing_factor * value + (1 - smoothing_factor) * running)
        smoothed.append(round(running, 6))
    return smoothed


def smooth_metrics(*, metrics: list[dict[str, Any]], smoothing_factor: float = DEFAULT_SMOOTHING_FACTOR) -> dict[str, Any]:
    losses = [m.get("loss") for m in metrics]
    smoothed_losses = smooth_series(values=losses, smoothing_factor=smoothing_factor)
    return {
        "smoothing_factor": smoothing_factor, "point_count": len(metrics),
        "smoothed_loss": smoothed_losses,
        "disclosure": "an exponential moving average for dashboard display only -- the database's own recorded metric rows are never modified or replaced by this",
    }
