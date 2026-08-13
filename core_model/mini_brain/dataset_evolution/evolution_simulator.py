"""MB-11: Evolution Simulator -- pure. Projects what the already-
computed quality-evolution prediction would mean for benchmark,
reasoning, language, memory, and RAG quality if the expansion actually
happened. Simulation only -- no benchmark is run, no model is
evaluated, no RAG query executes. Every figure here is derived from
`quality_evolution`'s own already-computed gains, never invented fresh.
"""

from __future__ import annotations

from typing import Any


def simulate_evolution(*, quality_evolution: dict[str, Any], expansion_action: str) -> dict[str, Any]:
    training_gain = quality_evolution["training_gain"]
    coverage_gain = quality_evolution["coverage_gain"]
    reasoning_gain = quality_evolution["reasoning_gain"]
    confidence = quality_evolution["confidence"]

    expected_benchmark_delta = round(training_gain * 0.4, 1)
    expected_reasoning_delta = round(reasoning_gain * 0.8, 1)
    expected_language_delta = round(coverage_gain * 0.2, 1)
    expected_memory_delta_mb = round(training_gain * 2.0, 1)
    expected_rag_quality_delta = round((coverage_gain + reasoning_gain) / 2 * 0.5, 1)

    return {
        "expansion_action": expansion_action,
        "expected_improvement": quality_evolution["quality_gain"],
        "expected_benchmark_delta": expected_benchmark_delta,
        "expected_reasoning_delta": expected_reasoning_delta,
        "expected_language_delta": expected_language_delta,
        "expected_memory_delta_mb": expected_memory_delta_mb,
        "expected_rag_quality_delta": expected_rag_quality_delta,
        "confidence": confidence,
        "disclosure": (
            "a simulation derived from disclosed heuristic gain figures, not a real benchmark, "
            "reasoning-eval, or RAG Sandbox run -- an admin who wants a measured number must run "
            "MB-06's real benchmark or RAG Sandbox's real evaluation after acting on this plan"
        ),
    }
