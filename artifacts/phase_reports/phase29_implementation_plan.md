# Phase 29 Implementation Plan — Disaster Recovery, Backup Integrity & Business Continuity

## Executive Summary
This document defines the proposed technical step-by-step implementation plan for **Phase 29 / Phase 30 — Disaster Recovery, Backup Integrity & Business Continuity**.

> [!IMPORTANT]
> **READ-ONLY PROPOSED PLAN**:
> This document defines a future implementation design. **NO SOURCE CODE MODIFICATIONS ARE PERFORMED DURING PHASE 29**. Source implementation requires explicit human authorization (`APPROVED — START PHASE 29 IMPLEMENTATION`).

---

## 1. Safety & Production Database Protection Policy
- **Database Safety**: Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) MUST remain 100% byte-identical during all test executions.
- **Test Isolation**: All automated tests MUST execute against isolated in-memory (`:memory:`) or temporary SQLite databases.
- **Non-Autonomous Invariant**: Zero background workers, Celery, APScheduler, cron, automatic database restores, or automatic failovers.

---

## 2. Proposed Architecture & Technical Components

### Step A: Pure Domain Capability Layer
- **File**: `core_model/capabilities/disaster_recovery_service.py` [PROPOSED NEW]
- **Dataclasses**:
  - `BackupMetadataRecord`: `backup_id`, `backup_type`, `source_db_sha256`, `backup_sha256`, `backup_size_bytes`, `created_at`, `rpo_freshness_seconds`, `is_verified`.
  - `RestorePreflightReport`: `preflight_id`, `backup_id`, `checksum_match`, `integrity_check_passed`, `can_restore`.
  - `RestoreOperationRecord`: `restore_id`, `backup_id`, `target_db_path`, `executed_by`, `executed_at`, `reason`, `idempotency_key`, `audit_reference`.
  - `DisasterRecoveryProvenance`: Extended 16-step provenance chain tracking.
- **Functions**:
  - `compute_disaster_recovery_idempotency_key(backup_id: str, executed_by: str) -> str`
  - `calculate_rpo_freshness(backup_timestamp_iso: str, current_time_iso: str | None = None) -> float`

### Step B: Additive SQLite Database Layer
- **File**: `backend/database/repositories/disaster_recovery_repository.py` [PROPOSED NEW]
- **Additive Tables**:
  1. `phase29_database_backups` (`backup_id PRIMARY KEY`, `backup_type`, `source_db_sha256`, `backup_sha256`, `backup_size_bytes`, `created_at`, `storage_path`, `rpo_freshness_seconds`, `is_verified`, `provenance_json`).
  2. `phase29_restore_operations` (`restore_id PRIMARY KEY`, `backup_id`, `target_db_path`, `executed_by`, `executed_at`, `reason`, `idempotency_key UNIQUE`, `audit_reference`, `provenance_json`).
  3. `phase29_recovery_locks` (`lock_key PRIMARY KEY`, `backup_id`, `acquired_by`, `acquired_at`).

### Step C: Backend Service Layer
- **File**: `backend/services/disaster_recovery_service.py` [PROPOSED NEW]
- **Methods**:
  - `create_database_snapshot(*, created_by: str) -> BackupMetadataRecord`
  - `verify_backup_integrity(backup_id: str) -> bool`
  - `preflight_restore_check(backup_id: str) -> RestorePreflightReport`
  - `execute_human_authorized_restore(backup_id: str, *, executed_by: str, reason: str) -> RestoreOperationRecord`

### Step D: Admin API Router Layer
- **File**: `backend/api/routes/disaster_recovery_admin.py` [PROPOSED NEW]
- **Prefix**: `/admin/phase29`
- **Dependencies**: `[Depends(require_admin)]` (Strict SUPER_ADMIN requirement for restore execution)
- **Endpoints**:
  - `GET  /admin/phase29/backups` — List database backup snapshots and RPO freshness metrics.
  - `GET  /admin/phase29/backups/{backup_id}` — Get backup snapshot details.
  - `POST /admin/phase29/backups/{backup_id}/verify` — Verify backup SHA-256 checksum and integrity.
  - `POST /admin/phase29/backups/{backup_id}/restore-preflight` — Preflight restore check.
  - `POST /admin/phase29/backups/{backup_id}/restore` — Human-authorized database restore execution.
  - `GET  /admin/phase29/metrics` — Disaster recovery & RPO/RTO metrics.

---

## 3. Proposed Recovery State Machine

`RECOVERY_DETECTED`  
→ `BACKUP_IDENTIFIED`  
→ `BACKUP_VERIFICATION_PENDING`  
→ `BACKUP_VERIFIED`  
→ `PENDING_HUMAN_APPROVAL`  
→ `RESTORE_APPROVED`  
→ `RESTORE_EXECUTING`  
→ `RESTORE_VERIFICATION`  
→ `RECOVERY_VERIFIED`  
→ `RESOLVED`  
→ `CLOSED`

> **NON-AUTONOMOUS INVARIANT**: State transitions require explicit human approval at `PENDING_HUMAN_APPROVAL` → `RESTORE_APPROVED`.

---

## 4. Verification Plan (When Authorized)
1. Run dedicated test suite: `pytest tests/core_model/test_phase29_disaster_recovery.py` (100+ tests).
2. Run full regression suite: Phases 13–29 + RBAC (1,348+ tests).
3. Verify production database SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) are 100% UNTOUCHED.
4. Produce `phase29_final_verification_report.md` and walkthrough artifact.
