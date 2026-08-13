"""MB-20: Risk Register Builder -- pure. Generates one structured risk
entry per failed safety gate, missing compliance item, and failed or
marginal benchmark metric -- never a fabricated or speculative risk
unconnected to an already-observed signal. Deterministic: the same
gate/compliance/benchmark reports always produce the same risk
register, in the same order.
"""

from __future__ import annotations

from typing import Any

_SAFETY_SEVERITY = "critical"
_SAFETY_LIKELIHOOD = "high"
_BENCHMARK_FAILED_SEVERITY = "high"
_BENCHMARK_FAILED_LIKELIHOOD = "high"
_BENCHMARK_MARGINAL_SEVERITY = "medium"
_BENCHMARK_MARGINAL_LIKELIHOOD = "medium"
_COMPLIANCE_SEVERITY = "medium"
_COMPLIANCE_LIKELIHOOD = "medium"
DEFAULT_OWNER = "release_admin"


def _entry(
    *, index: int, category: str, severity: str, likelihood: str, description: str, mitigation: str,
    rollback_trigger: str,
) -> dict[str, Any]:
    return {
        "id": f"RISK-{index:03d}", "category": category, "severity": severity, "likelihood": likelihood,
        "description": description, "mitigation": mitigation, "owner": DEFAULT_OWNER,
        "rollback_trigger": rollback_trigger,
    }


def build_risk_register(
    *, safety_gate_report: dict[str, Any], compliance_gate_report: dict[str, Any],
    benchmark_gate_report: dict[str, Any],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    index = 1

    for gate in safety_gate_report.get("gates", []):
        if gate["status"] != "fail":
            continue
        entries.append(_entry(
            index=index, category="safety", severity=_SAFETY_SEVERITY, likelihood=_SAFETY_LIKELIHOOD,
            description=gate["reason"], mitigation=f"resolve the underlying cause of safety gate '{gate['name']}' before release",
            rollback_trigger=f"safety gate '{gate['name']}' fails again after release",
        ))
        index += 1

    for item in compliance_gate_report.get("items", []):
        if item["status"] != "missing":
            continue
        entries.append(_entry(
            index=index, category="compliance", severity=_COMPLIANCE_SEVERITY, likelihood=_COMPLIANCE_LIKELIHOOD,
            description=f"compliance item '{item['name']}' is not present", mitigation=f"produce '{item['name']}' before release",
            rollback_trigger=f"compliance item '{item['name']}' is discovered missing post-release",
        ))
        index += 1

    for metric in benchmark_gate_report.get("failed_metrics", []):
        entries.append(_entry(
            index=index, category="benchmark", severity=_BENCHMARK_FAILED_SEVERITY,
            likelihood=_BENCHMARK_FAILED_LIKELIHOOD,
            description=f"benchmark metric '{metric['metric_name']}' ({metric['category']}) failed at value {metric['value']}",
            mitigation=f"improve '{metric['metric_name']}' before release",
            rollback_trigger=f"benchmark metric '{metric['metric_name']}' regresses further after release",
        ))
        index += 1

    for metric in benchmark_gate_report.get("marginal_metrics", []):
        entries.append(_entry(
            index=index, category="benchmark", severity=_BENCHMARK_MARGINAL_SEVERITY,
            likelihood=_BENCHMARK_MARGINAL_LIKELIHOOD,
            description=f"benchmark metric '{metric['metric_name']}' ({metric['category']}) is marginal at value {metric['value']}",
            mitigation=f"monitor '{metric['metric_name']}' closely after release",
            rollback_trigger=f"benchmark metric '{metric['metric_name']}' crosses into failing range",
        ))
        index += 1

    severity_counts: dict[str, int] = {}
    for entry in entries:
        severity_counts[entry["severity"]] = severity_counts.get(entry["severity"], 0) + 1

    return {
        "entries": entries, "entry_count": len(entries), "severity_counts": severity_counts,
        "owner_assignment_is_placeholder": True,
        "disclosure": (
            f"every entry traces to an already-observed safety/compliance/benchmark signal, never a "
            f"speculative risk; owner is always '{DEFAULT_OWNER}' -- this codebase has no team/"
            "assignment concept, so this is a placeholder, not a real assignment"
        ),
    }
