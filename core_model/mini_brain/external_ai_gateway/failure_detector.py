"""MB-21: Failure Detector -- pure. Aggregates each provider run's own
already-reported status/error into a summary -- never re-classifies or
second-guesses what the provider client itself already determined.
"""

from __future__ import annotations

from typing import Any

FAILURE_STATUSES = ("failed", "timeout", "rate_limited", "unavailable", "disabled")


def detect_failures(*, provider_runs: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [run for run in provider_runs if run["status"] in FAILURE_STATUSES]
    by_status: dict[str, int] = {}
    for run in failures:
        by_status[run["status"]] = by_status.get(run["status"], 0) + 1

    return {
        "failure_count": len(failures), "failures_by_status": by_status,
        "failed_providers": [
            {"provider_key": run["provider_key"], "status": run["status"], "error_message": run.get("error_message")}
            for run in failures
        ],
        "all_providers_failed": len(failures) == len(provider_runs) and len(provider_runs) > 0,
        "disclosure": "reports each provider run's own already-determined status and error -- never re-classifies or infers a failure reason beyond what the provider client itself reported",
    }
