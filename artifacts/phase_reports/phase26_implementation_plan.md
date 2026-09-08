# Phase 26 Implementation Plan — Production Observability, Runtime Health, Incident Detection & Human-Governed Recovery

## Executive Summary
This document defines the technical step-by-step implementation plan for **Phase 26 — Production Observability, Runtime Health, Incident Detection & Human-Governed Recovery**.

Implementation will begin **ONLY AFTER EXPLICIT HUMAN APPROVAL**.

---

## 1. Safety & Database Protection Policy
- **Database Safety**: Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) MUST remain 100% byte-identical.
- **Test Isolation**: All automated tests MUST execute against isolated in-memory (`:memory:`) or temporary SQLite databases.
- **Zero Autonomous Execution**: No background workers, Celery, APScheduler, cron, automatic deployments, automatic rollbacks, automatic restarts, or automatic incident remediation.

---

## 2. Technical Implementation Steps

### Step A: Pure Domain Capability Layer
- **File**: `core_model/capabilities/production_observability_service.py` [NEW]
- **Components**:
  - Immutable dataclasses: `HealthCheckItem`, `RuntimeHealthReport`, `HealthTrendComparison`, `IncidentRecord`, `IncidentReview`, `RecoveryRecommendation`, `RecoveryOperation`, `ObservabilityProvenance`.
  - Incident State Machine: `INCIDENT_DETECTED` → `ACKNOWLEDGED` → `INVESTIGATING` → `RECOVERY_RECOMMENDED` → `PENDING_HUMAN_ACTION` → `RECOVERY_APPROVED` → `RECOVERY_EXECUTING` → `RECOVERY_VERIFIED`.
  - Failures/Terminal States: `RECOVERY_REJECTED`, `RECOVERY_DEFERRED`, `RECOVERY_FAILED`, `VERIFICATION_FAILED`, `RESOLVED`, `CLOSED`.
  - Deterministic Health Check Engine (API, routes, database, RAG, datasets, active releases, models, config, resources, security).
  - Health Trend Engine (`HEALTH_IMPROVED`, `HEALTH_STABLE`, `HEALTH_DEGRADED`, `HEALTH_REGRESSED`, `INCONCLUSIVE`).
  - Recovery Recommendation Engine (Determines non-destructive recommendations without auto-executing).
  - Idempotency key computation for recovery operations.
  - Extended 16-step provenance chain tracking.
- **Export**: Export Phase 26 symbols in `core_model/capabilities/__init__.py` [MODIFY].

### Step B: Additive SQLite Database Layer
- **File**: `backend/database/repositories/observability_repository.py` [NEW]
- **Tables**:
  - `phase26_health_reports`
  - `phase26_health_checks`
  - `phase26_health_comparisons`
  - `phase26_incidents`
  - `phase26_incident_reviews`
  - `phase26_recovery_recommendations`
  - `phase26_recovery_operations`
  - `phase26_health_locks`
- **DDL & Indexing**: `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.

### Step C: Backend Service Layer
- **Files**:
  - `backend/services/runtime_health_service.py` [NEW]
  - `backend/services/incident_detection_service.py` [NEW]
  - `backend/services/human_recovery_service.py` [NEW]
- **Responsibilities**:
  - Health preflight execution and report persistence.
  - Incident detection from health failures & recovery recommendation computation.
  - Human review decision processing (`ACKNOWLEDGED`, `RECOVERY_APPROVED`, `RECOVERY_REJECTED`, `RECOVERY_DEFERRED`) and atomic recovery execution.

### Step D: Admin API Router Layer
- **File**: `backend/api/routes/observability_admin.py` [NEW]
- **Prefix**: `/admin/phase26`
- **Dependencies**: `[Depends(require_admin)]`
- **Endpoints**:
  - `GET  /admin/phase26/health`
  - `GET  /admin/phase26/health/{deployment_id}`
  - `GET  /admin/phase26/health/history`
  - `GET  /admin/phase26/health/compare/{report_a}/{report_b}`
  - `GET  /admin/phase26/incidents`
  - `GET  /admin/phase26/incidents/{incident_id}`
  - `POST /admin/phase26/incidents/{incident_id}/acknowledge`
  - `POST /admin/phase26/incidents/{incident_id}/review`
  - `POST /admin/phase26/incidents/{incident_id}/recommend`
  - `POST /admin/phase26/incidents/{incident_id}/approve-recovery`
  - `POST /admin/phase26/incidents/{incident_id}/reject-recovery`
  - `POST /admin/phase26/incidents/{incident_id}/defer-recovery`
  - `POST /admin/phase26/incidents/{incident_id}/execute-recovery`
  - `POST /admin/phase26/incidents/{incident_id}/verify-recovery`
  - `GET  /admin/phase26/metrics`
- **Registry**: Register `observability_admin` RoutePlugin in `backend/api/route_registry.py` [MODIFY].

### Step E: Dedicated Test Suite
- **File**: `tests/core_model/test_phase26_production_observability.py` [NEW]
- **Target**: **120+ dedicated tests** covering dataclasses, incident state machine, health checks, trend comparisons, incident detection, recovery recommendations, human recovery gate, idempotency, RBAC, AST security, and production DB SHA-256 integrity verification.

---

## 3. Verification Plan
1. Run dedicated test suite: `pytest tests/core_model/test_phase26_production_observability.py` (expect 120/120 PASSED).
2. Run combined regression suite: Phases 13–26 + RBAC (expect 1,006 + 120+ = 1,126+ PASSED).
3. Verify production database SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) are 100% UNTOUCHED.
4. Produce `phase26_final_verification_report.md` and update `walkthrough.md`.
