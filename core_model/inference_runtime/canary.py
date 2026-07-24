"""Bounded, deterministic internal-canary mechanics: routing, metrics, and
automatic stopping rules. No public model activation ever happens here."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

MINIMUM_SAMPLE_SIZE_FOR_SIGNIFICANCE = 30


def stable_routing_key(routing_seed: str, percentage: int) -> bool:
    """Deterministic: the same seed always routes the same way, so a
    canary's routing decisions are reproducible, not re-randomized per call."""

    if percentage <= 0:
        return False
    if percentage >= 100:
        return True
    digest = hashlib.sha256(routing_seed.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < percentage


def compute_canary_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)

    def rate(count: int) -> float | None:
        return (count / total) if total else None

    model_requests = sum(1 for r in results if r.get("used_model"))
    successes = sum(1 for r in results if r.get("success"))
    failures = total - successes
    timeouts = sum(1 for r in results if r.get("timed_out"))
    latencies = sorted(int(r.get("latency_ms", 0)) for r in results)
    average_latency_ms = (sum(latencies) / total) if total else None
    p95_latency_ms = None
    if len(latencies) >= MINIMUM_SAMPLE_SIZE_FOR_SIGNIFICANCE:
        index = max(0, int(len(latencies) * 0.95) - 1)
        p95_latency_ms = latencies[index]
    role_leakage = sum(1 for r in results if r.get("role_leakage"))
    prompt_leakage = sum(1 for r in results if r.get("prompt_leakage"))
    duplicate = sum(1 for r in results if r.get("duplicate_output"))
    unicode_valid = sum(1 for r in results if r.get("unicode_valid"))
    stop_reason_distribution: dict[str, int] = {}
    for r in results:
        reason = r.get("stop_reason") or "unknown"
        stop_reason_distribution[reason] = stop_reason_distribution.get(reason, 0) + 1

    return {
        "total_requests": total,
        "model_requests": model_requests,
        "fallback_requests": total - model_requests,
        "successful_generations": successes,
        "failed_generations": failures,
        "timeouts": timeouts,
        "average_latency_ms": average_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "input_tokens": sum(r.get("input_tokens", 0) for r in results),
        "output_tokens": sum(r.get("output_tokens", 0) for r in results),
        "role_leakage_rate": rate(role_leakage),
        "prompt_leakage_rate": rate(prompt_leakage),
        "repetition_warning_rate": rate(duplicate),
        "unicode_valid_rate": rate(unicode_valid),
        "failure_rate": rate(failures),
        "timeout_rate": rate(timeouts),
        "stop_reason_distribution": stop_reason_distribution,
        "sample_size_small": total < MINIMUM_SAMPLE_SIZE_FOR_SIGNIFICANCE,
    }


@dataclass(frozen=True)
class CanaryThresholds:
    max_failure_rate: float = 0.2
    max_timeout_rate: float = 0.2
    max_role_leakage_rate: float = 0.0
    max_prompt_leakage_rate: float = 0.0
    max_duplicate_rate: float = 0.5


@dataclass(frozen=True)
class CanaryStopAssessment:
    should_stop: bool
    reasons: list[str] = field(default_factory=list)


def assess_canary_stop(
    metrics: dict[str, Any],
    thresholds: CanaryThresholds,
    *,
    checkpoint_mismatch: bool = False,
    runtime_unhealthy: bool = False,
    memory_guard_failed: bool = False,
    unsafe_output_issue: bool = False,
    admin_requested_stop: bool = False,
) -> CanaryStopAssessment:
    reasons: list[str] = []
    if checkpoint_mismatch:
        reasons.append("checkpoint_mismatch")
    if runtime_unhealthy:
        reasons.append("runtime_unhealthy")
    if memory_guard_failed:
        reasons.append("memory_guard_failed")
    if unsafe_output_issue:
        reasons.append("unsafe_output_issue")
    if admin_requested_stop:
        reasons.append("admin_stop")
    if metrics.get("total_requests"):
        if (metrics.get("failure_rate") or 0) > thresholds.max_failure_rate:
            reasons.append("failure_rate_exceeded")
        if (metrics.get("timeout_rate") or 0) > thresholds.max_timeout_rate:
            reasons.append("timeout_rate_exceeded")
        if (metrics.get("role_leakage_rate") or 0) > thresholds.max_role_leakage_rate:
            reasons.append("role_leakage_rate_exceeded")
        if (metrics.get("prompt_leakage_rate") or 0) > thresholds.max_prompt_leakage_rate:
            reasons.append("prompt_leakage_rate_exceeded")
        if (metrics.get("repetition_warning_rate") or 0) > thresholds.max_duplicate_rate:
            reasons.append("duplicate_rate_exceeded")
    return CanaryStopAssessment(should_stop=bool(reasons), reasons=reasons)
