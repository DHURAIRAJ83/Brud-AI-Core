# Phase 28 Implementation Plan — Operations Hardening & Stale-Lock Governance

## Executive Summary
This document defines the technical step-by-step implementation plan for **Phase 28 — Operations Hardening & Stale-Lock Governance**.

Implementation will begin **ONLY AFTER EXPLICIT HUMAN AUTHORIZATION** (`APPROVED — START PHASE 28 IMPLEMENTATION`).

---

## 1. Safety & Production Database Protection Policy
- **Database Safety**: Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) MUST remain 100% byte-identical.
- **Test Isolation**: All automated unit and integration tests MUST execute against isolated in-memory (`:memory:`) or temporary SQLite databases.
- **Non-Autonomous Operations**: Zero background workers, Celery, APScheduler, cron, automatic deployments, automatic rollbacks, automatic restarts, or automatic lock deletion.

---

## 2. Technical Implementation Steps

### Step A: Pure Domain Capability Layer
- **File**: `core_model/capabilities/lock_maintenance_service.py` [NEW]
- **Dataclasses**:
  - `StaleLockRecord`
  - `LockInspectionReport`
  - `LockCleanupOperation`
  - `LockMaintenanceProvenance`
- **Functions**:
  - `compute_lock_cleanup_idempotency_key(lock_table: str, lock_key: str, released_by: str) -> str`
  - `inspect_lock_records(...)`
  - `process_stale_lock_release(...)`
- **Export**: Export Phase 28 symbols in `core_model/capabilities/__init__.py` [MODIFY].

### Step B: Additive SQLite Database Layer
- **File**: `backend/database/repositories/lock_maintenance_repository.py` [NEW]
- **Additive Table**: `phase28_lock_cleanup_operations` (`cleanup_id PRIMARY KEY`, `lock_table`, `lock_key`, `resource_id`, `released_by`, `released_at`, `reason`, `idempotency_key UNIQUE`, `audit_reference`).
- **Methods**:
  - `fetch_active_locks()`
  - `insert_lock_cleanup_operation()`
  - `get_lock_cleanup_operation_by_idempotency_key()`
  - `delete_lock_record(lock_table: str, lock_key: str)`

### Step C: Backend Service Layer
- **File**: `backend/services/lock_maintenance_service.py` [NEW]
- **Methods**:
  - `inspect_locks(stale_threshold_seconds: int = 3600) -> LockInspectionReport`
  - `release_stale_lock(lock_table: str, lock_key: str, *, released_by: str, reason: str) -> LockCleanupOperation`

### Step D: Admin API Router Layer
- **File**: `backend/api/routes/lock_maintenance_admin.py` [NEW]
- **Prefix**: `/admin/phase28`
- **Dependencies**: `[Depends(require_admin)]`
- **Endpoints**:
  - `GET  /admin/phase28/locks`
  - `GET  /admin/phase28/locks/{lock_table}/{lock_key}`
  - `POST /admin/phase28/locks/{lock_table}/{lock_key}/release`
  - `GET  /admin/phase28/metrics`
- **Registry**: Register `lock_maintenance_admin` RoutePlugin in `backend/api/route_registry.py` [MODIFY].

### Step E: Dedicated Test Suite
- **File**: `tests/core_model/test_phase28_operations_hardening.py` [NEW]
- **Target**: **100+ dedicated tests** covering dataclasses, lock inspection, stale detection, fresh lock protection, human authorization gate, idempotency, RBAC, AST security, and production DB SHA-256 integrity verification.

---

## 3. Verification Plan
1. Run dedicated test suite: `pytest tests/core_model/test_phase28_operations_hardening.py` (expect 100+ PASSED).
2. Run combined regression suite: Phases 13–28 + RBAC (expect 1,128 + 100+ = 1,228+ PASSED).
3. Verify production database SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) are 100% UNTOUCHED.
4. Produce `phase28_final_verification_report.md` and `phase28_walkthrough.md`.
