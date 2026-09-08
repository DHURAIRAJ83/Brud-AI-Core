# Phase 28 Pre-Implementation Audit — Operations Hardening & Stale-Lock Governance

## 1. Executive Baseline Verification
The repository baseline has been verified prior to Phase 28 planning:
- **Repository Path**: `/home/dhurai/Projects/brud-ai`
- **Git Branch**: `phase-5-performance-polish`
- **Git HEAD**: `df054cb100b58d99acf42a72d18dcbcb7dcbd5f8`
- **Git Stash**: `stash@{0}` (untouched)
- **Production DB Path**: `data/database/brud_ai.db`
- **Production DB Baseline SHA-256**: `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729` (100% UNTOUCHED)
- **Production DB Baseline Size**: `11,096,064 bytes` (100% UNTOUCHED)
- **WAL / SHM Baseline**: WAL = `0 bytes`, SHM = `32,768 bytes` (Clean)
- **Regression Suite Baseline**: `1,128 / 1,128 tests PASSED` (Phases 13–26)
- **Phase 27 Status**: `A — VERIFIED`

---

## 2. Phase 27 Debt Items Audit & Strategy

### A. DEBT-27-01: Legacy Health Endpoint Coexistence
- **Current Situation**:
  - Legacy endpoints: `/api/v1/health` and `/admin/mini-brain/health` provide basic system uptime / connectivity pings.
  - Phase 26 endpoint: `/admin/phase26/health` provides structured operational health observations across 8 categories.
- **Audit Finding**: Existing clients and internal readiness checks consume legacy health endpoints for basic liveness probes.
- **Resolution Strategy**:
  - **Preserve legacy endpoints with zero breaking API changes**.
  - Document operational distinctions in route docstrings: `/api/v1/health` for Liveness/Readiness, `/admin/phase26/health` for Structured Operational Inspection & Governance.

### B. DEBT-27-02: Settings Dependency Import Standardization
- **Current Situation**: Modern admin route plugins use `from backend.api.dependencies import SettingsDependency`.
- **Audit Finding**: Older plugins imported directly from `backend.core.config`.
- **Resolution Strategy**: Standardize route plugins to import `SettingsDependency` from canonical `backend.api.dependencies` where safe, preserving full backward compatibility.

### C. DEBT-27-03: Stale Concurrency Lock Handling (PRIMARY TASK)
- **Lock Tables Audited**:
  1. `phase24_release_locks` (`lock_key`, `release_id`, `acquired_by`, `acquired_at`)
  2. `phase25_deployment_locks` (`lock_key`, `release_id`, `acquired_by`, `acquired_at`)
  3. `phase26_health_locks` (`lock_key`, `incident_id`, `acquired_by`, `acquired_at`)
- **Audit Finding**: All three lock tables store `acquired_at TEXT NOT NULL` ISO timestamps.
- **Critical Non-Autonomous Requirement**:
  - Stale lock detection MUST NOT trigger automatic lock deletion.
  - System MUST NEVER silently wipe locks or automatically execute deployment, rollback, recovery, or process restarts.
- **Resolution Strategy**:
  - Introduce `LockMaintenanceService` with pure domain inspection.
  - Compute age threshold (`age_seconds > lock_ttl_seconds`, default 3600s) to mark locks as `is_stale`.
  - Require explicit human admin action (`SUPER_ADMIN` / `ADMIN`) with audit reason to execute lock release.
  - Record lock cleanup in additive table `phase28_lock_cleanup_operations` with deterministic idempotency keys (`compute_lock_cleanup_idempotency_key`).

### D. DEBT-27-04: Test Suite Performance
- **Current Situation**: 1,128 tests execute in ~125s to 142s with full `:memory:` SQLite isolation.
- **Audit Finding**: `pytest-xdist` is not installed in local venv. Baseline execution is fast, deterministic, and isolated.
- **Resolution Strategy**: Maintain local deterministic `pytest` execution as default; document optional CI parallelization flags.

---

## 3. Proposed Phase 28 Architecture

### A. Pure Domain Layer (`core_model/capabilities/lock_maintenance_service.py` [NEW])
- Dataclasses: `StaleLockRecord`, `LockInspectionReport`, `LockCleanupOperation`, `LockMaintenanceProvenance`.
- Pure domain functions for stale calculation, lock report generation, and idempotency key computation (`compute_lock_cleanup_idempotency_key`).
- Export symbols in `core_model/capabilities/__init__.py` [MODIFY].

### B. Additive SQLite Repository Layer (`backend/database/repositories/lock_maintenance_repository.py` [NEW])
- Additive table: `phase28_lock_cleanup_operations` (`cleanup_id PRIMARY KEY`, `lock_table`, `lock_key`, `resource_id`, `released_by`, `released_at`, `reason`, `idempotency_key UNIQUE`, `audit_reference`).
- Methods to query active locks across Phase 24, 25, 26 lock tables and execute explicit human-authorized lock cleanup.

### C. Backend Service Layer (`backend/services/lock_maintenance_service.py` [NEW])
- Service class `LockMaintenanceService` coordinating lock inspection, stale status determination, RBAC verification, idempotency key lookups, and audit log persistence.

### D. Admin API Router (`backend/api/routes/lock_maintenance_admin.py` [NEW])
- Prefix: `/admin/phase28`
- Dependencies: `[Depends(require_admin)]`
- Endpoints:
  - `GET  /admin/phase28/locks`
  - `GET  /admin/phase28/locks/{lock_table}/{lock_key}`
  - `POST /admin/phase28/locks/{lock_table}/{lock_key}/release`
  - `GET  /admin/phase28/metrics`
- Registration in `backend/api/route_registry.py` [MODIFY].

### E. Dedicated Test Suite (`tests/core_model/test_phase28_operations_hardening.py` [NEW])
- **100+ dedicated tests** covering lock inspection, stale detection, fresh lock protection, human authorization gate, idempotency, RBAC, AST security, and production DB SHA-256 integrity protection.

---

## 4. Non-Autonomous Governance Invariants
- `STALE LOCK DETECTED != AUTOMATIC DELETION`
- `LOCK RELEASE != AUTOMATIC DEPLOYMENT / ROLLBACK / RECOVERY`
- Zero background workers, Celery, APScheduler, cron, or autonomous execution.
- Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) MUST remain 100% byte-identical.

---

## 5. Audit Verdict & Next Gate
**READY_FOR_HUMAN_REVIEW**.  
Phase 28 pre-implementation audit is complete.  
Source code implementation has **NOT** started.  
Explicit human authorization is required before beginning implementation.
