# 08 INCIDENT RESPONSE ENGINE AUDIT

- Class: `IncidentResponseEngine` in `core_model/ops/incident_response_engine.py`.
- Lifecycle: `INCIDENT_DETECTED -> INCIDENT_TRIAGED -> MITIGATION_REQUIRED -> TRAFFIC_FROZEN -> ROLLBACK_REQUIRED -> ROLLBACK_EXECUTED -> RECOVERY_VERIFIED -> INCIDENT_CLOSED`.
- Human Authority: Critical incidents require explicit human Admin closure.
