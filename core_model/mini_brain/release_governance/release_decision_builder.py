"""MB-20: Release Decision Builder -- pure. Produces one of three
recommendations -- approved_for_release, conditionally_approved,
not_approved -- from already-computed safety/compliance/benchmark gate
results. This is a recommendation only: the actual, binding decision
is always made by a human admin via admin_review(), never by this
module.
"""

from __future__ import annotations

from typing import Any

APPROVED_FOR_RELEASE = "approved_for_release"
CONDITIONALLY_APPROVED = "conditionally_approved"
NOT_APPROVED = "not_approved"


def build_release_decision(
    *, safety_gate_report: dict[str, Any], compliance_gate_report: dict[str, Any],
    benchmark_gate_report: dict[str, Any], release_risk_level: str,
) -> dict[str, Any]:
    blocking_issues: list[str] = []
    blocking_issues.extend(safety_gate_report.get("blocking_reasons", []))
    blocking_issues.extend(compliance_gate_report.get("blocking_reasons", []))

    benchmark_status = benchmark_gate_report.get("overall_benchmark_status")
    if benchmark_status == "fail":
        blocking_issues.append("one or more benchmark gate metrics failed")

    if blocking_issues:
        recommendation = NOT_APPROVED
    elif benchmark_status == "marginal" or release_risk_level == "medium":
        recommendation = CONDITIONALLY_APPROVED
    else:
        recommendation = APPROVED_FOR_RELEASE

    return {
        "recommendation": recommendation, "blocking_issues": blocking_issues,
        "safety_status": safety_gate_report.get("overall_status"),
        "compliance_status": compliance_gate_report.get("overall_status"),
        "benchmark_status": benchmark_status,
        "release_risk_level": release_risk_level,
        "binding": False,
        "disclosure": (
            "this is a recommendation only -- the binding decision is always made by a human admin "
            "via admin_review(), never automatically by this module"
        ),
    }
