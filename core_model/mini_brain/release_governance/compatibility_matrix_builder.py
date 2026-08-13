"""MB-20: Compatibility Matrix Builder -- pure. Re-surfaces MB-18's own
already-computed hardware estimate and MB-19's own already-computed
language/multimodal coverage into a single compatibility-shaped
document -- never invents a new compatibility claim MB-18/19 didn't
already compute.
"""

from __future__ import annotations

from typing import Any


def build_compatibility_matrix(
    *, hardware_estimate_report: dict[str, Any], language_benchmark_report: dict[str, Any],
    multimodal_benchmark_report: dict[str, Any],
) -> dict[str, Any]:
    language_distribution = language_benchmark_report.get("language_distribution") or {}
    return {
        "cpu_only_feasible": hardware_estimate_report.get("cpu_only_feasible"),
        "minimum_ram_tier": hardware_estimate_report.get("ram_tier"),
        "minimum_vram_tier": hardware_estimate_report.get("vram_tier"),
        "estimated_disk_bytes": hardware_estimate_report.get("estimated_disk_bytes"),
        "expected_training_duration_category": hardware_estimate_report.get("expected_training_duration_category"),
        "image_support": bool((multimodal_benchmark_report.get("image_coverage") or 0) > 0),
        "knowledge_graph_support": bool((multimodal_benchmark_report.get("knowledge_graph_coverage") or 0) > 0),
        "supported_languages": sorted(language_distribution),
        "dominant_language": language_benchmark_report.get("dominant_language"),
        "all_estimates_heuristic": True,
        "disclosure": (
            "every figure here is read directly from MB-18's own hardware estimate and MB-19's own "
            "language/multimodal benchmarks -- this module recomputes nothing and never claims a "
            "compatibility guarantee beyond what those phases already estimated"
        ),
    }
