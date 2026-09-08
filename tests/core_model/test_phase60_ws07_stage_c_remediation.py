"""
Automated Governance & Remediation Tests for Phase 60 WS07 Stage C Pre-Flight.
Verifies:
  - Canonical Model parameter counts (E4 528,128; E5 3,159,040)
  - Canonical Training Engine refusal path when training_execution_authorized == False
  - Checkpoint migration handling static 'pe' buffer
  - Fail-closed behavior on trainable parameter shape mismatches
  - Non-mutating E4 and E5 dry runs without optimizer.step() execution
"""

import pytest
import torch
from pathlib import Path
from core_model.architecture.brud_small_v2 import BrudSmallV2Model, BrudSmallScaledModel
from core_model.training.brud_training_engine import (
    BrudTrainingEngine,
    TrainingAuthorizationError,
    CheckpointMismatchError
)

WS05_CKPT_PATH = Path("artifacts/candidates/phase60/checkpoints/checkpoint_best.pt")


def test_canonical_model_parameter_counts():
    m2_128 = BrudSmallV2Model(max_seq=128)
    m2_512 = BrudSmallV2Model(max_seq=512)
    m_scaled = BrudSmallScaledModel(max_seq=512)

    assert m2_128.get_parameter_count()["total_trainable_parameters"] == 528128
    assert m2_512.get_parameter_count()["total_trainable_parameters"] == 528128
    assert m_scaled.get_parameter_count()["total_trainable_parameters"] == 3159040


def test_training_engine_refusal_when_unauthorized():
    engine = BrudTrainingEngine(training_execution_authorized=False)
    with pytest.raises(TrainingAuthorizationError) as exc_info:
        engine.verify_authorization()
    assert "HARD GOVERNANCE STOP" in str(exc_info.value)


def test_safe_checkpoint_loading_ws05_pe_handling():
    if not WS05_CKPT_PATH.exists():
        pytest.skip(f"WS05 Checkpoint file not found: {WS05_CKPT_PATH}")

    engine = BrudTrainingEngine(training_execution_authorized=False)
    model = BrudSmallV2Model(max_seq=128)
    report = engine.load_checkpoint_safely(model, WS05_CKPT_PATH)

    assert report["loaded_keys_count"] == 27
    assert "pe" in report["ignored_static_buffers"]
    assert report["shape_mismatches"] == []


def test_checkpoint_loading_fails_closed_on_shape_mismatch():
    if not WS05_CKPT_PATH.exists():
        pytest.skip(f"WS05 Checkpoint file not found: {WS05_CKPT_PATH}")

    engine = BrudTrainingEngine(training_execution_authorized=False)
    scaled_model = BrudSmallScaledModel(max_seq=512)

    with pytest.raises(CheckpointMismatchError) as exc_info:
        engine.load_checkpoint_safely(scaled_model, WS05_CKPT_PATH)
    assert "HARD CHECKPOINT ERROR" in str(exc_info.value)


def test_e4_dry_run_without_optimizer_step():
    engine = BrudTrainingEngine(training_execution_authorized=False)
    e4_model = BrudSmallV2Model(max_seq=512)
    dummy_batch = [{
        "input_ids": torch.randint(0, 1024, (1, 128)),
        "labels": torch.randint(0, 1024, (1, 128))
    }]

    result = engine.run_dry_run(e4_model, dummy_batch)

    assert result["dry_run_completed"] is True
    assert result["optimizer_step_called"] is False
    assert result["parameter_count"] == 528128
    assert result["sample_loss"] > 0.0


def test_e5_dry_run_without_optimizer_step():
    engine = BrudTrainingEngine(training_execution_authorized=False)
    e5_model = BrudSmallScaledModel(max_seq=512)
    dummy_batch = [{
        "input_ids": torch.randint(0, 1024, (1, 128)),
        "labels": torch.randint(0, 1024, (1, 128))
    }]

    result = engine.run_dry_run(e5_model, dummy_batch)

    assert result["dry_run_completed"] is True
    assert result["optimizer_step_called"] is False
    assert result["parameter_count"] == 3159040
    assert result["sample_loss"] > 0.0
