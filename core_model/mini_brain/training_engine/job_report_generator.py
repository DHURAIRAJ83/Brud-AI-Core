"""MB-22: Job Report Generator -- pure assembly only. Merges every
earlier stage's already-computed output into the single final report
document. Never recomputes anything; every field is a direct pass-
through of an earlier stage's own real output. Always discloses,
explicitly, every honest limitation the task spec requires.
"""

from __future__ import annotations

from typing import Any


def generate_job_report(
    *, job_public_id: str, topic: str, execution_mode: str, training_package_session_public_id: str,
    release_governance_session_public_id: str, status: str, started_at: str | None, completed_at: str | None,
    metrics: list[dict[str, Any]], checkpoints: list[dict[str, Any]], resource_plan: dict[str, Any],
    fingerprint: dict[str, Any], failure_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    losses = [m["loss"] for m in metrics if m.get("loss") is not None]
    final_loss = losses[-1] if losses else None
    best_loss = min(losses) if losses else None

    throughputs = [m["tokens_per_second"] for m in metrics if m.get("tokens_per_second") is not None]
    avg_tokens_per_second = round(sum(throughputs) / len(throughputs), 3) if throughputs else None

    next_actions = [
        "an admin must review this report before any downstream action is taken",
        "no deployment, promotion, or public exposure has occurred as a result of this job",
    ]
    if execution_mode == "simulation":
        next_actions.append("re-run with execution_mode='cpu' or 'gpu' before treating any result as real")

    return {
        "job_public_id": job_public_id, "topic": topic, "execution_mode": execution_mode,
        "package_references": {
            "training_package_session_public_id": training_package_session_public_id,
            "release_governance_session_public_id": release_governance_session_public_id,
        },
        "status": status, "started_at": started_at, "completed_at": completed_at,
        "final_loss": final_loss, "best_loss": best_loss,
        "checkpoint_list": [
            {"checkpoint_name": c["checkpoint_name"], "step": c["step"], "epoch": c["epoch"], "is_metadata_only": c.get("is_metadata_only")}
            for c in checkpoints
        ],
        "checkpoint_count": len(checkpoints),
        "throughput_summary": {"average_tokens_per_second": avg_tokens_per_second, "recorded_metric_count": len(metrics)},
        "resource_usage_summary": resource_plan,
        "failure_summary": failure_summary,
        "reproducibility_fingerprint": fingerprint,
        "next_recommended_actions": next_actions,
        "simulation_mode_is_not_real_training": execution_mode == "simulation",
        "no_benchmark_executed_unless_explicitly_run": True,
        "no_deployment_performed": True,
        "no_inference_quality_guarantee": True,
        "resource_estimates_are_heuristic": True,
        "checkpoints_may_be_metadata_only_in_simulation_mode": execution_mode == "simulation",
        "disclaimer": (
            "job completion does not imply production deployment -- no model has been deployed, "
            "promoted, or exposed to public users as a result of this job; simulation mode never "
            "performs real training; resource estimates are heuristic; checkpoint files may be "
            "metadata-only when execution_mode is 'simulation'"
        ),
        "ready_for_admin_review": True,
    }
