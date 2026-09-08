# 06 MODEL HEALTH MONITOR AUDIT

- Class: `ModelHealthMonitor` in `core_model/ops/model_health_monitor.py`.
- Fail-Closed Requirement: Unknown or missing telemetry strictly defaults to `DEGRADED` or `CRITICAL`. Never classifies unverified state as `HEALTHY`.
