"""MB-48 P5: lightweight internal-pilot usage telemetry.

Layered directly on the existing append-only `audit_logs` table via
`AuditLogRepository` -- no new table, no external analytics service.
Most counters are new audit log rows whose `action` is the metric name
itself. `gateway_export_run_count` reuses an audit action the export
pipeline (`ExternalGatewayDatasetBridgeService._audit`) already writes
on every successful export -- no duplicate instrumentation needed
there.

`pilot_metric_counts()` aggregates these back out for the admin-facing
Pilot Metrics page.
"""

from __future__ import annotations

from backend.database.repositories import AuditLogRepository
from backend.models.domain import AuditEventCreate

# metric name -> the audit_logs `action` value(s) counted as that metric.
PILOT_METRIC_ACTIONS: dict[str, tuple[str, ...]] = {
    "widget_plain_chat_count": ("widget_plain_chat_count",),
    "widget_grounded_chat_count": ("widget_grounded_chat_count",),
    "grounded_chat_citation_render_count": ("grounded_chat_citation_render_count",),
    "retrieval_profile_switch_count": ("retrieval_profile_switch_count",),
    "prompt_optimization_run_count": ("prompt_optimization_run_count",),
    "gateway_export_run_count": ("external_gateway_dataset_export_completed",),
}

# Metrics this module itself is responsible for recording via
# record_pilot_metric(). gateway_export_run_count is deliberately
# excluded -- it is derived from an event the export service already
# writes, so nothing here should ever record it directly.
_RECORDABLE_METRICS = frozenset(PILOT_METRIC_ACTIONS) - {"gateway_export_run_count"}


def record_pilot_metric(settings, metric: str, *, resource_public_id: str | None = None) -> None:
    if metric not in _RECORDABLE_METRICS:
        raise ValueError(f"pilot metric {metric!r} is not directly recordable")
    if not settings.audit_enabled:
        return
    try:
        AuditLogRepository(settings.resolved_database_path).append(
            AuditEventCreate(
                event_type="pilot_metric",
                actor_type="admin",
                action=metric,
                resource_type="pilot_metric",
                resource_public_id=resource_public_id,
            )
        )
    except Exception:
        # Metrics collection must never break the real feature it measures.
        return


def pilot_metric_counts(settings) -> dict[str, int]:
    all_actions = tuple({action for actions in PILOT_METRIC_ACTIONS.values() for action in actions})
    counts_by_action = AuditLogRepository(settings.resolved_database_path).count_by_actions(all_actions)
    return {
        metric: sum(counts_by_action.get(action, 0) for action in actions)
        for metric, actions in PILOT_METRIC_ACTIONS.items()
    }
