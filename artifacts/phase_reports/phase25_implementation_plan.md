# Phase 25 Implementation Plan — Production Readiness, Deployment Gate & Operational Safety

## Executive Summary
This document defines the technical step-by-step implementation plan for **Phase 25 — Production Readiness, Deployment Gate & Operational Safety**.

Implementation will begin **ONLY AFTER EXPLICIT HUMAN APPROVAL**.

---

## 1. Safety & Database Protection Policy
- **Database Safety**: Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) MUST remain 100% byte-identical.
- **Test Isolation**: All automated tests MUST execute against isolated in-memory (`:memory:`) or temporary SQLite databases.
- **Zero Autonomous Execution**: No background workers, Celery, APScheduler, cron, automatic deployments, service restarts, or model training.

---

## 2. Technical Implementation Steps

### Step A: Pure Domain Capability Layer
- **File**: `core_model/capabilities/deployment_readiness_service.py` [NEW]
- **Components**:
  - Immutable dataclasses: `DeploymentReadinessReport`, `ReadinessCheck`, `DeploymentApproval`, `DeploymentOperation`, `DeploymentRollback`, `DeploymentProvenance`.
  - State Machine: `ACTIVE_RELEASE` → `READINESS_PREFLIGHT` → `READINESS_VALIDATED` → `PENDING_DEPLOYMENT_APPROVAL` → `DEPLOYMENT_APPROVED` → `READY_FOR_DEPLOYMENT` → `DEPLOYING` → `POST_DEPLOYMENT_VERIFYING` → `DEPLOYMENT_VERIFIED`.
  - Failures/Rollbacks: `READINESS_FAILED`, `DEPLOYMENT_REJECTED`, `DEPLOYMENT_DEFERRED`, `DEPLOYMENT_FAILED`, `VERIFICATION_FAILED`, `ROLLBACK_PENDING`, `ROLLED_BACK`.
  - Deterministic Readiness Check Engine (8 categories: Release Integrity, Security & Secret Scan, Database Safety, Configuration, App Health, Resources, Regression, Operational Safety).
  - Idempotency key computation for deployment and rollback operations.
  - Extended 16-step provenance chain tracking.
- **Export**: Export Phase 25 symbols in `core_model/capabilities/__init__.py` [MODIFY].

### Step B: Additive SQLite Database Layer
- **File**: `backend/database/repositories/deployment_repository.py` [NEW]
- **Tables**:
  - `phase25_readiness_reports`
  - `phase25_readiness_checks`
  - `phase25_deployment_approvals`
  - `phase25_deployment_operations`
  - `phase25_deployment_rollbacks`
  - `phase25_deployment_locks`
- **DDL & Indexing**: `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.

### Step C: Backend Service Layer
- **Files**:
  - `backend/services/deployment_readiness_service.py` [NEW]
  - `backend/services/deployment_gate_service.py` [NEW]
  - `backend/services/deployment_rollback_service.py` [NEW]
- **Responsibilities**:
  - Readiness preflight execution and report generation.
  - Human deployment approval gate & atomic deployment status updates.
  - Non-destructive deployment rollback to historical active release versions.

### Step D: Admin API Router Layer
- **File**: `backend/api/routes/deployment_admin.py` [NEW]
- **Prefix**: `/admin/phase25`
- **Dependencies**: `[Depends(require_admin)]`
- **Endpoints**:
  - `GET  /admin/phase25/releases/{release_id}/readiness`
  - `POST /admin/phase25/releases/{release_id}/readiness`
  - `GET  /admin/phase25/readiness/{readiness_id}`
  - `GET  /admin/phase25/readiness/{readiness_id}/checks`
  - `POST /admin/phase25/readiness/{readiness_id}/review`
  - `POST /admin/phase25/readiness/{readiness_id}/approve`
  - `POST /admin/phase25/readiness/{readiness_id}/reject`
  - `POST /admin/phase25/readiness/{readiness_id}/defer`
  - `POST /admin/phase25/deployments/create`
  - `POST /admin/phase25/deployments/{deployment_id}/execute`
  - `GET  /admin/phase25/deployments/{deployment_id}`
  - `GET  /admin/phase25/deployments`
  - `POST /admin/phase25/deployments/{deployment_id}/verify`
  - `POST /admin/phase25/deployments/{deployment_id}/rollback`
  - `GET  /admin/phase25/metrics`
- **Registry**: Register `deployment_admin` RoutePlugin in `backend/api/route_registry.py` [MODIFY].

### Step E: Dedicated Test Suite
- **File**: `tests/core_model/test_phase25_deployment_readiness.py` [NEW]
- **Target**: **120+ dedicated tests** covering dataclasses, state machine transitions, readiness checks, security boundary hard blocks, secret scans, human deployment approval gate, atomic deployment status updates, non-destructive rollbacks, RBAC, AST security, and production DB SHA-256 integrity verification.

---

## 3. Verification Plan
1. Run dedicated test suite: `pytest tests/core_model/test_phase25_deployment_readiness.py` (expect 120/120 PASSED).
2. Run combined regression suite: Phases 13–25 + RBAC (expect 886 + 120+ = 1,006+ PASSED).
3. Verify production database SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) are 100% UNTOUCHED.
4. Produce `phase25_final_verification_report.md` and update `walkthrough.md`.
