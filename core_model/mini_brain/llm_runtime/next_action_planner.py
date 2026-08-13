"""MB-28: Next Action Planner -- pure. Builds a rule-based ranked
action list from a status snapshot -- this always runs, with or
without an LLM available, so `next_actions`/`propose_next_phase` never
depend entirely on the model. `parse_llm_output()` reconciles free-text
LLM output back into the same structured shape when the LLM is
available, without ever trusting it to invent an action out of nothing.
"""

from __future__ import annotations

from typing import Any

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def plan_next_actions(*, status_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    failing_tests = status_snapshot.get("failing_tests", 0)
    if failing_tests:
        actions.append(
            {
                "title": f"Fix {failing_tests} failing test(s)",
                "severity": "critical",
                "reason": "Regression is not green.",
            }
        )

    pending_proposals = status_snapshot.get("pending_proposals", 0)
    if pending_proposals:
        actions.append(
            {
                "title": f"Review {pending_proposals} pending admin proposal(s)",
                "severity": "high",
                "reason": "Governed actions are awaiting admin review.",
            }
        )

    unconfigured_providers = status_snapshot.get("unconfigured_providers", [])
    for provider_key in unconfigured_providers:
        actions.append(
            {
                "title": f"Configure provider '{provider_key}'",
                "severity": "medium",
                "reason": "Provider is enabled but missing required configuration.",
            }
        )

    if not actions:
        actions.append(
            {
                "title": "No outstanding issues detected",
                "severity": "low",
                "reason": "All known signals are healthy.",
            }
        )

    actions.sort(key=lambda item: _SEVERITY_ORDER.get(item["severity"], 99))
    return actions


def parse_llm_output(*, llm_text: str, fallback_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines = [line.strip("-* \t") for line in llm_text.splitlines() if line.strip()]
    if not lines:
        return fallback_actions

    rephrased: list[dict[str, Any]] = []
    for index, action in enumerate(fallback_actions):
        title = lines[index] if index < len(lines) else action["title"]
        rephrased.append({**action, "title": title})
    return rephrased
