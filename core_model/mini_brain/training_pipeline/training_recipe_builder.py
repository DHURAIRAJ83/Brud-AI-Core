"""MB-18: Training Recipe builder -- pure. Produces a suggested
hyperparameter configuration as metadata only -- this module never
trains anything and never calls any training API. Every value is a
disclosed, fixed heuristic default scaled only by real record counts;
none of it has ever been validated against an actual training run in
this codebase.
"""

from __future__ import annotations

from typing import Any

BASE_LEARNING_RATE = 2e-5
BASE_BATCH_SIZE = 8
BASE_EPOCHS = 3
SMALL_DATASET_THRESHOLD = 200
LARGE_DATASET_THRESHOLD = 20000


def build_training_recipe(*, total_record_count: int, curriculum_stage_count: int) -> dict[str, Any]:
    if total_record_count < SMALL_DATASET_THRESHOLD:
        epochs = BASE_EPOCHS + 2
        batch_size = max(2, BASE_BATCH_SIZE // 2)
    elif total_record_count > LARGE_DATASET_THRESHOLD:
        epochs = max(1, BASE_EPOCHS - 1)
        batch_size = BASE_BATCH_SIZE * 2
    else:
        epochs = BASE_EPOCHS
        batch_size = BASE_BATCH_SIZE

    return {
        "optimizer": "adamw", "learning_rate": BASE_LEARNING_RATE, "batch_size": batch_size,
        "epochs": epochs, "warmup_ratio": 0.03, "weight_decay": 0.01,
        "curriculum_stage_count": curriculum_stage_count, "gradient_checkpointing": total_record_count > LARGE_DATASET_THRESHOLD,
        "status": "suggested_only", "executed": False,
        "disclosure": (
            "fixed heuristic defaults scaled only by real record counts -- never validated against an "
            "actual training run in this codebase, and this module never calls any training API"
        ),
    }
