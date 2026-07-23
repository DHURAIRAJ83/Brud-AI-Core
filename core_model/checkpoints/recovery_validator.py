"""Pre-recovery checkpoint validation.

A checkpoint is only ever recovered from once every check below passes. If the
latest checkpoint fails validation it is rejected and marked corrupt; this
module never silently falls back to an earlier checkpoint on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core_model.architecture.model import BrudForCausalLM
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager


@dataclass
class RecoveryValidation:
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    recovered_step: int | None = None
    recovered_tokens: int | None = None


def validate_checkpoint_for_recovery(
    *,
    checkpoint_row: dict[str, Any] | None,
    checkpoint_dir: Path,
    max_bytes: int,
    model_config,
    dataset_checksum_expected: str | None,
    dataset_checksum_actual: str | None,
    tokenizer_checksum_expected: str | None,
    tokenizer_checksum_actual: str | None,
    model_config_checksum_expected: str | None,
    model_config_checksum_actual: str | None,
    stream_checksum_expected: str | None,
    stream_checksum_actual: str | None,
    step_monotonic: bool,
    token_monotonic: bool,
) -> RecoveryValidation:
    checks: dict[str, bool] = {}
    failures: list[str] = []

    registered = checkpoint_row is not None
    checks["checkpoint_registered"] = registered
    if not registered:
        failures.append("checkpoint not registered")
        return RecoveryValidation(ok=False, checks=checks, failures=failures)

    status_ok = checkpoint_row.get("status") in {"completed", "verified"}
    checks["checkpoint_status_verified"] = status_ok
    if not status_ok:
        failures.append("checkpoint status is not verified")

    manager = TrainingCheckpointManager(checkpoint_dir.parent, max_bytes)
    try:
        manager.verify(checkpoint_dir)
        checksum_ok = True
    except (OSError, ValueError):
        checksum_ok = False
    for check_name in (
        "combined_checksum_valid",
        "model_checksum_valid",
        "optimizer_checksum_valid",
        "scheduler_checksum_valid",
        "trainer_state_checksum_valid",
    ):
        checks[check_name] = checksum_ok
    if not checksum_ok:
        failures.append("checkpoint file checksums failed verification")

    rng_ok = False
    tensors_ok = False
    if checksum_ok:
        try:
            states = manager.load_states(checkpoint_dir)
            rng_ok = states.get("rng") is not None
        except (OSError, ValueError, RuntimeError):
            states = {}
            rng_ok = False
        if rng_ok:
            try:
                reference_state = BrudForCausalLM(model_config).state_dict()
                loaded_state = states.get("model", {})
                tensors_ok = set(reference_state) == set(loaded_state) and all(
                    reference_state[name].shape == loaded_state[name].shape
                    for name in reference_state
                )
            except Exception:
                tensors_ok = False
    checks["rng_state_valid"] = rng_ok
    checks["tensor_names_and_shapes_valid"] = tensors_ok
    if not rng_ok:
        failures.append("RNG state failed to load")
    if not tensors_ok:
        failures.append("checkpoint tensors are incompatible with the current model architecture")

    dataset_ok = (
        dataset_checksum_expected is None
        or dataset_checksum_actual is None
        or dataset_checksum_expected == dataset_checksum_actual
    )
    tokenizer_ok = (
        tokenizer_checksum_expected is None
        or tokenizer_checksum_actual is None
        or tokenizer_checksum_expected == tokenizer_checksum_actual
    )
    model_config_ok = (
        model_config_checksum_expected is None
        or model_config_checksum_actual is None
        or model_config_checksum_expected == model_config_checksum_actual
    )
    checks["dataset_checksum_valid"] = dataset_ok
    checks["tokenizer_checksum_valid"] = tokenizer_ok
    checks["model_config_checksum_valid"] = model_config_ok
    if not dataset_ok:
        failures.append("dataset checksum does not match the checkpoint's recorded reference")
    if not tokenizer_ok:
        failures.append("tokenizer checksum does not match the checkpoint's recorded reference")
    if not model_config_ok:
        failures.append("model config checksum does not match the checkpoint's recorded reference")

    stream_ok = (
        stream_checksum_expected is None
        or stream_checksum_actual is None
        or stream_checksum_expected == stream_checksum_actual
    )
    checks["stream_checksum_valid"] = stream_ok
    if not stream_ok:
        failures.append("stream checksum does not match the checkpoint's recorded reference")

    checks["step_counters_monotonic"] = step_monotonic
    checks["token_counters_monotonic"] = token_monotonic
    if not step_monotonic:
        failures.append("step counters are not monotonic")
    if not token_monotonic:
        failures.append("token counters are not monotonic")

    ok = not failures
    return RecoveryValidation(
        ok=ok,
        checks=checks,
        failures=failures,
        recovered_step=checkpoint_row.get("step") if ok else None,
        recovered_tokens=checkpoint_row.get("processed_tokens") if ok else None,
    )
