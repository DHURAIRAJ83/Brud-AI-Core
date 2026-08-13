"""MB-25: Execution Report Builder -- pure assembly only. Merges every
earlier stage's already-computed output into the single execution
report. Never recomputes anything; always discloses, explicitly,
every Step 20 honest limitation.
"""

from __future__ import annotations

from typing import Any


def generate_execution_report(
    *, execution_public_id: str, plugin_public_id: str, execution_mode: str, status: str,
    duration_ms: float | None, scope_key: str, guard_violations: list[str], sanitized_output_summary: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "execution_public_id": execution_public_id, "plugin_public_id": plugin_public_id,
        "execution_mode": execution_mode, "status": status, "duration_ms": duration_ms, "scope_key": scope_key,
        "guard_violations": guard_violations, "sanitized_output_summary": sanitized_output_summary,
        "generated_at": generated_at,
        "no_container_isolation": True, "no_process_isolation": True, "no_cpu_quota_enforcement": True,
        "no_memory_quota_enforcement": True, "no_signed_plugin_verification": True, "no_package_marketplace": True,
        "no_automatic_updates": True, "no_remote_plugin_execution": True,
        "disclaimer": (
            "this report describes a real, real-time execution attempt against an admin-approved plugin -- "
            "but no container or process isolation exists in this phase, so a well-behaved plugin's own "
            "cooperation with the provided guards is what keeps it inside its approved boundaries, not "
            "OS-level enforcement"
        ),
    }
