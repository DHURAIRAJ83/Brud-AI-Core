# Phase 30 Implementation Plan — Production Reliability, Recovery Validation & Operational Governance

## Executive Summary
This document defines the proposed technical step-by-step implementation plan for **Phase 30 — Production Reliability, Recovery Validation & Operational Governance**.

> [!IMPORTANT]
> **READ-ONLY PROPOSED PLAN**:
> This document defines a future implementation design. **NO SOURCE CODE MODIFICATIONS ARE PERFORMED DURING THIS AUDIT PHASE**. Source implementation requires explicit human authorization (`APPROVED — START PHASE 30 IMPLEMENTATION`).

---

## 1. Safety & Production Database Protection Policy
- **Database Safety**: Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) MUST remain 100% byte-identical during all test executions.
- **Drill Isolation**: All recovery drills MUST execute against isolated in-memory (`:memory:`) or temporary SQLite databases generated in isolated scratch directories via `tempfile.mkdtemp()`.
- **Non-Autonomous Invariant**: Zero background workers, Celery, APScheduler, cron, automatic database restores, or automatic failovers.

---

## 2. Proposed Architecture & Technical Components

### Step A: Pure Domain Capability Layer
- **File**: `core_model/capabilities/recovery_validation_service.py` [PROPOSED NEW]
- **Dataclasses**:
  - `RecoveryDrillRecord`: `drill_id`, `backup_id`, `drill_type`, `started_at`, `completed_at`, `duration_seconds`, `target_rto_seconds`, `rto_status`, `backup_sha256`, `restored_db_sha256`, `integrity_status`, `schema_status`, `result`, `executed_by`, `audit_reference`, `idempotency_key`, `provenance`.
  - `OperationalReadinessReport`: `evaluation_id`, `readiness_status` (`READY`, `READY_WITH_WARNINGS`, `NOT_READY`), `latest_backup_freshness_seconds`, `rpo_status`, `rto_status`, `latest_drill_result`, `active_locks_count`, `evaluated_at`, `details`.
  - `RecoveryValidationProvenance`: Extended 16-step provenance chain tracking.
- **Functions**:
  - `compute_recovery_drill_idempotency_key(backup_id: str, executed_by: str) -> str`
  - `evaluate_rpo_status(latest_backup_freshness_seconds: float, rpo_target_seconds: float = 3600.0) -> str`
  - `evaluate_rto_status(drill_duration_seconds: float, rto_target_seconds: float = 900.0) -> str`

### Step B: Additive SQLite Database Layer
- **File**: `backend/database/repositories/recovery_validation_repository.py` [PROPOSED NEW]
- **Additive Table**:
  - `phase30_recovery_drills` (`drill_id PRIMARY KEY`, `backup_id`, `drill_type`, `started_at`, `completed_at`, `duration_seconds`, `target_rto_seconds`, `rto_status`, `backup_sha256`, `restored_db_sha256`, `integrity_status`, `schema_status`, `result`, `executed_by`, `audit_reference`, `idempotency_key UNIQUE`, `provenance_json`).

### Step C: Backend Service Layer
- **File**: `backend/services/recovery_validation_service.py` [PROPOSED NEW]
- **Methods**:
  - `execute_recovery_drill(backup_id: str, *, executed_by: str, drill_type: str = "SCHEDULED_DRILL") -> RecoveryDrillRecord`
  - `evaluate_operational_readiness() -> OperationalReadinessReport`
  - `get_rpo_compliance_status() -> dict[str, Any]`
  - `get_rto_compliance_status() -> dict[str, Any]`

### Step D: Admin API Router Layer
- **File**: `backend/api/routes/recovery_validation_admin.py` [PROPOSED NEW]
- **Prefix**: `/admin/phase30`
- **Dependencies**: `[Depends(require_admin)]`
- **Endpoints**:
  - `GET  /admin/phase30/health` — Subsystem health inspection.
  - `GET  /admin/phase30/readiness` — Deterministic operational readiness report.
  - `GET  /admin/phase30/rpo` — RPO status & backup freshness.
  - `GET  /admin/phase30/rto` — RTO status & latest recovery drill duration.
  - `GET  /admin/phase30/drills` — List recovery drill records.
  - `GET  /admin/phase30/drills/{drill_id}` — Get specific recovery drill details.
  - `POST /admin/phase30/drills/{backup_id}` — Execute isolated recovery drill from backup snapshot.
  - `GET  /admin/phase30/metrics` — Phase 30 operational governance metrics summary.

---

## 3. Verification Plan (When Authorized)
1. Run dedicated test suite: `pytest tests/core_model/test_phase30_recovery_validation.py` (120 tests).
2. Run full regression suite: Phases 13–30 + RBAC (1,488 tests).
3. Verify production database SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) are 100% UNTOUCHED.
4. Produce `phase30_final_verification_report.md` and update walkthrough artifact.
