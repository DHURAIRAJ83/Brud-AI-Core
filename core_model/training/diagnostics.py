"""Safe numerical diagnostics for training loss and perplexity."""

from __future__ import annotations

import math

PERPLEXITY_SAFE_LOSS_CEILING = 20.0


def safe_perplexity(loss: float | None) -> float | None:
    """Return exp(loss), or None when the result would be unsafe or meaningless."""

    if loss is None or not math.isfinite(loss) or loss < 0 or loss > PERPLEXITY_SAFE_LOSS_CEILING:
        return None
    try:
        return math.exp(loss)
    except OverflowError:
        return None


def loss_improvement_ratio(initial_loss: float | None, final_loss: float | None) -> float | None:
    if initial_loss is None or final_loss is None:
        return None
    if not math.isfinite(initial_loss) or not math.isfinite(final_loss) or initial_loss <= 0:
        return None
    return (initial_loss - final_loss) / initial_loss


def is_diverging(losses: list[float], *, window: int = 5) -> bool:
    finite = [loss for loss in losses if math.isfinite(loss)]
    if len(finite) < window * 2:
        return False
    early = sum(finite[:window]) / window
    late = sum(finite[-window:]) / window
    return early > 0 and late > early * 1.5


def train_validation_gap(
    training_loss: float | None, validation_loss: float | None
) -> float | None:
    if training_loss is None or validation_loss is None:
        return None
    if not math.isfinite(training_loss) or not math.isfinite(validation_loss):
        return None
    return validation_loss - training_loss
