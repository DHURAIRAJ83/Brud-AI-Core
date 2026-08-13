"""MB-06: Training Request Builder -- pure payload construction only.
Builds the exact dict shape the existing Training Engine's own
`PretrainingJobCreate` model and `PretrainingConfig` dataclass expect
(field names read directly from `core_model/training/pretraining_config.py`,
never guessed) -- this module never calls the Training Engine itself;
the service layer does that with the payload this function returns.

Hyperparameter profiles are fixed, disclosed presets -- not tuned
against any real training outcome in this project, matching the same
"disclosed, not empirically validated" honesty already used for MB-05's
readiness thresholds and MB-04C's model profiles.
"""

from __future__ import annotations

from typing import Any

HYPERPARAMETER_PROFILES: dict[str, dict[str, Any]] = {
    "default": {
        "sequence_length": 512, "total_steps": 200, "learning_rate": 3e-4,
        "warmup_steps": 20, "weight_decay": 0.01, "gradient_accumulation_steps": 4,
        "gradient_clip_norm": 1.0, "scheduler": "linear_warmup_decay",
        "checkpoint_interval_steps": 25, "metric_interval_steps": 5,
    },
    "conservative": {
        "sequence_length": 256, "total_steps": 100, "learning_rate": 1e-4,
        "warmup_steps": 10, "weight_decay": 0.01, "gradient_accumulation_steps": 4,
        "gradient_clip_norm": 0.5, "scheduler": "constant",
        "checkpoint_interval_steps": 20, "metric_interval_steps": 5,
    },
    "aggressive": {
        "sequence_length": 512, "total_steps": 400, "learning_rate": 6e-4,
        "warmup_steps": 40, "weight_decay": 0.02, "gradient_accumulation_steps": 2,
        "gradient_clip_norm": 1.0, "scheduler": "cosine",
        "checkpoint_interval_steps": 50, "metric_interval_steps": 10,
    },
}

DEFAULT_JOB_MODE = "smoke_pretraining"


def available_profiles() -> list[str]:
    return sorted(HYPERPARAMETER_PROFILES)


def build_training_request(
    *,
    name: str,
    dataset_version_public_id: str,
    tokenizer_version_public_id: str,
    core_model_version_public_id: str,
    hyperparameter_profile: str = "default",
    job_mode: str = DEFAULT_JOB_MODE,
) -> dict[str, Any]:
    if hyperparameter_profile not in HYPERPARAMETER_PROFILES:
        raise ValueError(
            f"unknown hyperparameter_profile {hyperparameter_profile!r}, "
            f"available: {available_profiles()}"
        )
    return {
        "name": name,
        "dataset_version_public_id": dataset_version_public_id,
        "tokenizer_version_public_id": tokenizer_version_public_id,
        "core_model_version_public_id": core_model_version_public_id,
        "job_mode": job_mode,
        "configuration": dict(HYPERPARAMETER_PROFILES[hyperparameter_profile]),
    }
