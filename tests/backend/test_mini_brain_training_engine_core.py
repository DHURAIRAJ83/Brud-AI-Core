"""MB-22: pure-module unit tests for core_model/mini_brain/training_engine/.

Covers deterministic manifests, checkpoint naming/no-overwrite/latest
lookup, metric smoothing, throughput estimation, early-stop
recommendation, resume-state construction, reproducibility
fingerprinting, resource estimation, CPU feasibility, GPU capability
classification, failure classification, job report generation, and
training-audit summarization -- exactly the coverage the task spec's
own testing section (Step 17) names for MB-22's pure layer.
"""

from core_model.mini_brain.training_engine.checkpoint_namer import (
    build_checkpoint_name,
    check_no_overwrite,
    find_latest_checkpoint,
)
from core_model.mini_brain.training_engine.cpu_feasibility_estimator import (
    LARGE_TOKEN_COUNT_THRESHOLD,
    estimate_cpu_feasibility,
)
from core_model.mini_brain.training_engine.early_stop_monitor import monitor_early_stop
from core_model.mini_brain.training_engine.experiment_fingerprint import build_experiment_fingerprint
from core_model.mini_brain.training_engine.failure_classifier import classify_failure
from core_model.mini_brain.training_engine.gpu_capability_detector import detect_gpu_capability
from core_model.mini_brain.training_engine.job_report_generator import generate_job_report
from core_model.mini_brain.training_engine.job_validator import (
    validate_release_approval,
    validate_training_package,
)
from core_model.mini_brain.training_engine.metric_smoother import smooth_metrics, smooth_series
from core_model.mini_brain.training_engine.resource_planner import plan_resources
from core_model.mini_brain.training_engine.resume_state_builder import build_resume_state
from core_model.mini_brain.training_engine.throughput_estimator import estimate_throughput
from core_model.mini_brain.training_engine.training_audit_builder import build_training_audit
from core_model.mini_brain.training_engine.training_manifest_builder import build_training_manifest

# -- job_validator -------------------------------------------------------------------------


def test_validate_release_approval_requires_admin_approved_status() -> None:
    result = validate_release_approval(release_session={"public_id": "r1", "status": "awaiting_admin_review"})
    assert result["valid"] is False
    assert "admin_approved" in result["reason"]


def test_validate_release_approval_accepts_approved_session() -> None:
    result = validate_release_approval(release_session={"public_id": "r1", "status": "admin_approved"})
    assert result["valid"] is True
    assert result["session_public_id"] == "r1"


def test_validate_release_approval_handles_missing_session() -> None:
    result = validate_release_approval(release_session=None)
    assert result["valid"] is False


def test_validate_training_package_requires_built_package() -> None:
    result = validate_training_package(package_session={
        "public_id": "p1", "status": "admin_approved", "package_directory": None, "package_manifest": {"artifact_count": 0},
    })
    assert result["valid"] is False


def test_validate_training_package_accepts_real_built_package() -> None:
    result = validate_training_package(package_session={
        "public_id": "p1", "status": "admin_approved", "package_directory": "/tmp/pkg", "package_manifest": {"artifact_count": 3},
    })
    assert result["valid"] is True
    assert result["session_public_id"] == "p1"


# -- resource_planner -------------------------------------------------------------------------


def test_plan_resources_simulation_mode_is_trivial() -> None:
    plan = plan_resources(
        execution_mode="simulation", estimated_token_count=999_999_999, ram_tier="32GB+", vram_tier="24GB+",
        cpu_only_feasible=False, estimated_disk_bytes=999_999_999_999, expected_training_duration_category="many_hours_to_days",
    )
    assert plan["cpu_thread_count"] == 1
    assert plan["gpu_required"] is False
    assert plan["required_disk_bytes"] == 1_000_000


def test_plan_resources_gpu_mode_marks_gpu_required() -> None:
    plan = plan_resources(
        execution_mode="gpu", estimated_token_count=100_000, ram_tier="16GB+", vram_tier="8GB+",
        cpu_only_feasible=False, estimated_disk_bytes=5_000_000, expected_training_duration_category="hours",
    )
    assert plan["gpu_required"] is True
    assert plan["recommended_vram_tier"] == "8GB+"


def test_plan_resources_cpu_mode_never_requires_gpu() -> None:
    plan = plan_resources(
        execution_mode="cpu", estimated_token_count=1_000, ram_tier="8GB+", vram_tier="none",
        cpu_only_feasible=True, estimated_disk_bytes=1_000, expected_training_duration_category="minutes",
    )
    assert plan["gpu_required"] is False
    assert plan["recommended_vram_tier"] == "none"


def test_plan_resources_invalid_duration_category_falls_back_to_hours() -> None:
    plan = plan_resources(
        execution_mode="cpu", estimated_token_count=1_000, ram_tier="8GB+", vram_tier="none",
        cpu_only_feasible=True, estimated_disk_bytes=1_000, expected_training_duration_category="bogus",
    )
    assert plan["expected_duration_category"] == "hours"


# -- checkpoint_namer -------------------------------------------------------------------------


def test_build_checkpoint_name_is_deterministic() -> None:
    assert build_checkpoint_name(step=100, epoch=1) == "checkpoint-epoch001-step00000100"
    assert build_checkpoint_name(step=100, epoch=1) == build_checkpoint_name(step=100, epoch=1)


def test_check_no_overwrite_flags_existing_name() -> None:
    result = check_no_overwrite(checkpoint_name="checkpoint-epoch000-step00000100", existing_checkpoint_names=["checkpoint-epoch000-step00000100"])
    assert result["safe_to_write"] is False
    assert result["already_exists"] is True


def test_check_no_overwrite_allows_fresh_name() -> None:
    result = check_no_overwrite(checkpoint_name="checkpoint-epoch000-step00000200", existing_checkpoint_names=["checkpoint-epoch000-step00000100"])
    assert result["safe_to_write"] is True


def test_find_latest_checkpoint_picks_highest_step() -> None:
    checkpoints = [
        {"step": 100, "epoch": 0, "checkpoint_name": "a"}, {"step": 300, "epoch": 0, "checkpoint_name": "b"},
        {"step": 200, "epoch": 0, "checkpoint_name": "c"},
    ]
    latest = find_latest_checkpoint(checkpoints=checkpoints)
    assert latest["checkpoint_name"] == "b"


def test_find_latest_checkpoint_handles_empty_list() -> None:
    assert find_latest_checkpoint(checkpoints=[]) is None


# -- metric_smoother -------------------------------------------------------------------------


def test_smooth_series_converges_toward_recent_values() -> None:
    smoothed = smooth_series(values=[3.0, 3.0, 3.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], smoothing_factor=0.5)
    assert smoothed[0] == 3.0
    assert smoothed[-1] < 1.5
    assert smoothed[-1] > 1.0


def test_smooth_series_passes_through_none_values() -> None:
    smoothed = smooth_series(values=[2.0, None, None], smoothing_factor=0.5)
    assert smoothed == [2.0, 2.0, 2.0]


def test_smooth_series_rejects_invalid_smoothing_factor() -> None:
    import pytest

    with pytest.raises(ValueError):
        smooth_series(values=[1.0], smoothing_factor=0.0)


def test_smooth_metrics_wraps_loss_series() -> None:
    result = smooth_metrics(metrics=[{"loss": 3.0}, {"loss": 2.0}], smoothing_factor=0.5)
    assert result["point_count"] == 2
    assert len(result["smoothed_loss"]) == 2


# -- throughput_estimator -------------------------------------------------------------------------


def test_estimate_throughput_computes_real_rate() -> None:
    result = estimate_throughput(
        previous_step=0, previous_recorded_at_epoch_seconds=1000.0, current_step=100,
        current_recorded_at_epoch_seconds=1010.0, examples_per_step=8,
    )
    assert result["examples_per_second"] == 80.0
    assert result["steps_per_second"] == 10.0


def test_estimate_throughput_honestly_reports_none_for_non_positive_elapsed_time() -> None:
    result = estimate_throughput(
        previous_step=0, previous_recorded_at_epoch_seconds=1000.0, current_step=100,
        current_recorded_at_epoch_seconds=1000.0, examples_per_step=8,
    )
    assert result["examples_per_second"] is None


def test_estimate_throughput_honestly_reports_none_for_non_positive_step_delta() -> None:
    result = estimate_throughput(
        previous_step=100, previous_recorded_at_epoch_seconds=1000.0, current_step=100,
        current_recorded_at_epoch_seconds=1010.0, examples_per_step=8,
    )
    assert result["examples_per_second"] is None


# -- early_stop_monitor -------------------------------------------------------------------------


def test_monitor_early_stop_recommends_stopping_after_patience_exceeded() -> None:
    result = monitor_early_stop(loss_history=[3.0, 2.0, 1.0, 1.01, 1.02, 1.03, 1.04, 1.05], patience_steps=5, min_delta=0.001)
    assert result["should_consider_stopping"] is True
    assert result["best_loss"] == 1.0


def test_monitor_early_stop_does_not_recommend_stopping_within_patience() -> None:
    result = monitor_early_stop(loss_history=[3.0, 2.0, 1.0, 0.9], patience_steps=5, min_delta=0.001)
    assert result["should_consider_stopping"] is False


def test_monitor_early_stop_handles_short_history() -> None:
    result = monitor_early_stop(loss_history=[3.0])
    assert result["should_consider_stopping"] is False


# -- resume_state_builder -------------------------------------------------------------------------


def test_build_resume_state_with_no_checkpoint_cannot_resume() -> None:
    result = build_resume_state(latest_checkpoint=None, last_metric=None)
    assert result["can_resume"] is False


def test_build_resume_state_references_real_checkpoint() -> None:
    checkpoint = {"step": 200, "epoch": 1, "public_id": "ckpt-1", "checkpoint_name": "checkpoint-epoch001-step00000200"}
    result = build_resume_state(latest_checkpoint=checkpoint, last_metric={"loss": 1.5})
    assert result["can_resume"] is True
    assert result["resume_step"] == 200
    assert result["checkpoint_public_id"] == "ckpt-1"
    assert result["last_recorded_loss"] == 1.5


# -- experiment_fingerprint -------------------------------------------------------------------------


def test_build_experiment_fingerprint_is_deterministic() -> None:
    kwargs = {
        "training_package_session_public_id": "p1", "release_governance_session_public_id": "r1",
        "execution_mode": "simulation", "resource_plan": {"cpu_thread_count": 1, "gpu_required": False},
    }
    first = build_experiment_fingerprint(**kwargs)
    second = build_experiment_fingerprint(**kwargs)
    assert first["fingerprint_sha256"] == second["fingerprint_sha256"]
    assert len(first["fingerprint_sha256"]) == 64


def test_build_experiment_fingerprint_differs_on_input_change() -> None:
    base = {
        "training_package_session_public_id": "p1", "release_governance_session_public_id": "r1",
        "execution_mode": "simulation", "resource_plan": {"cpu_thread_count": 1, "gpu_required": False},
    }
    other = dict(base, execution_mode="gpu")
    assert build_experiment_fingerprint(**base)["fingerprint_sha256"] != build_experiment_fingerprint(**other)["fingerprint_sha256"]


# -- training_manifest_builder -------------------------------------------------------------------------


def test_build_training_manifest_never_claims_training_executed() -> None:
    manifest = build_training_manifest(
        job_public_id="j1", topic="t", training_package_session_public_id="p1",
        release_governance_session_public_id="r1", execution_mode="simulation",
        resource_plan={"cpu_thread_count": 1}, fingerprint={"fingerprint_sha256": "abc"}, created_at="now",
    )
    assert manifest["training_executed"] is False
    assert manifest["model_weights_included"] is False


# -- failure_classifier -------------------------------------------------------------------------


def test_classify_failure_recognizes_out_of_memory() -> None:
    result = classify_failure(error_message="CUDA out of memory error occurred")
    assert result["category"] == "out_of_memory"


def test_classify_failure_falls_back_to_unclassified() -> None:
    result = classify_failure(error_message="something bizarre happened")
    assert result["category"] == "unclassified"


def test_classify_failure_handles_empty_message() -> None:
    result = classify_failure(error_message=None)
    assert result["category"] == "unknown"


# -- gpu_capability_detector -------------------------------------------------------------------------


def test_detect_gpu_capability_no_cuda() -> None:
    result = detect_gpu_capability(cuda_available=False)
    assert result["gpu_available"] is False
    assert result["recommended_execution_mode"] == "cpu"


def test_detect_gpu_capability_with_real_device() -> None:
    result = detect_gpu_capability(cuda_available=True, device_count=1, device_name="Fake GPU")
    assert result["gpu_available"] is True
    assert result["recommended_execution_mode"] == "gpu"


# -- cpu_feasibility_estimator -------------------------------------------------------------------------


def test_estimate_cpu_feasibility_always_true_for_simulation() -> None:
    result = estimate_cpu_feasibility(resource_plan={"execution_mode": "simulation"})
    assert result["cpu_feasible"] is True


def test_estimate_cpu_feasibility_false_when_gpu_required() -> None:
    result = estimate_cpu_feasibility(resource_plan={"execution_mode": "gpu", "gpu_required": True, "estimated_token_count": 100})
    assert result["cpu_feasible"] is False


def test_estimate_cpu_feasibility_false_above_threshold() -> None:
    result = estimate_cpu_feasibility(resource_plan={
        "execution_mode": "cpu", "gpu_required": False, "estimated_token_count": LARGE_TOKEN_COUNT_THRESHOLD + 1,
    })
    assert result["cpu_feasible"] is False


def test_estimate_cpu_feasibility_true_below_threshold() -> None:
    result = estimate_cpu_feasibility(resource_plan={"execution_mode": "cpu", "gpu_required": False, "estimated_token_count": 100})
    assert result["cpu_feasible"] is True


# -- training_audit_builder -------------------------------------------------------------------------


def test_build_training_audit_counts_event_types() -> None:
    events = [
        {"created_at": "t1", "event_type": "job_created", "stage": "validate_release"},
        {"created_at": "t2", "event_type": "metric_streamed", "stage": "streaming_metrics"},
        {"created_at": "t3", "event_type": "metric_streamed", "stage": "streaming_metrics"},
    ]
    audit = build_training_audit(events=events, admin_authorized_by="admin1")
    assert audit["event_count"] == 3
    assert audit["event_type_counts"]["metric_streamed"] == 2
    assert audit["admin_authorized_by"] == "admin1"
    assert len(audit["timeline"]) == 3


# -- job_report_generator -------------------------------------------------------------------------


def test_generate_job_report_computes_real_final_and_best_loss() -> None:
    metrics = [{"loss": 3.0, "tokens_per_second": 500.0}, {"loss": 1.0, "tokens_per_second": 500.0}, {"loss": 2.0, "tokens_per_second": 500.0}]
    checkpoints = [{"checkpoint_name": "c1", "step": 100, "epoch": 0, "is_metadata_only": True}]
    report = generate_job_report(
        job_public_id="j1", topic="t", execution_mode="simulation", training_package_session_public_id="p1",
        release_governance_session_public_id="r1", status="completed", started_at="s", completed_at="c",
        metrics=metrics, checkpoints=checkpoints, resource_plan={"cpu_thread_count": 1}, fingerprint={"fingerprint_sha256": "abc"},
        failure_summary=None,
    )
    assert report["final_loss"] == 2.0
    assert report["best_loss"] == 1.0
    assert report["checkpoint_count"] == 1
    assert report["simulation_mode_is_not_real_training"] is True
    assert report["no_deployment_performed"] is True
    assert "disclaimer" in report


def test_generate_job_report_handles_no_metrics_honestly() -> None:
    report = generate_job_report(
        job_public_id="j1", topic="t", execution_mode="cpu", training_package_session_public_id="p1",
        release_governance_session_public_id="r1", status="failed", started_at=None, completed_at=None,
        metrics=[], checkpoints=[], resource_plan={"cpu_thread_count": 4}, fingerprint={"fingerprint_sha256": "abc"},
        failure_summary={"category": "out_of_memory"},
    )
    assert report["final_loss"] is None
    assert report["best_loss"] is None
    assert report["failure_summary"]["category"] == "out_of_memory"
