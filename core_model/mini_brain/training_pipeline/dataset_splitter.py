"""MB-18: Dataset Splitter -- pure. Reproducible train/validation/test
splits: input record ids are sorted first (removing any dependence on
upstream iteration order), then shuffled with a locally-scoped
`random.Random(seed)` instance -- the global `random` module state is
never touched, so this function's output depends only on its own
arguments, never on call order or other code's random usage.
"""

from __future__ import annotations

import random
from typing import Any

DEFAULT_SEED = 20260101
DEFAULT_TRAIN_RATIO = 0.8
DEFAULT_VALIDATION_RATIO = 0.1


def split_dataset(
    *, record_public_ids: list[str], seed: int = DEFAULT_SEED, train_ratio: float = DEFAULT_TRAIN_RATIO,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> dict[str, Any]:
    if not (0 < train_ratio < 1) or not (0 <= validation_ratio < 1) or train_ratio + validation_ratio > 1:
        raise ValueError("train_ratio and validation_ratio must describe a valid, non-overlapping split")

    ordered = sorted(set(record_public_ids))
    rng = random.Random(seed)
    shuffled = ordered.copy()
    rng.shuffle(shuffled)

    total = len(shuffled)
    train_count = round(total * train_ratio)
    validation_count = round(total * validation_ratio)

    train = shuffled[:train_count]
    validation = shuffled[train_count : train_count + validation_count]
    test = shuffled[train_count + validation_count :]

    return {
        "train": train, "validation": validation, "test": test,
        "counts": {"train": len(train), "validation": len(validation), "test": len(test), "total": total},
        "seed": seed, "train_ratio": train_ratio, "validation_ratio": validation_ratio,
        "test_ratio": round(1 - train_ratio - validation_ratio, 6),
        "disclosure": "deterministic given the same record id set and seed -- uses a locally-scoped random.Random instance, never global random state",
    }
