# Phase 31 — Architecture Debt Registry

## 1. Executive Summary
This document records all identified technical, architectural, and operational governance debt across Phases 13 through 30 in the Brud AI repository.

Severity Classifications:
- **CRITICAL**: 0
- **HIGH**: 0
- **MEDIUM**: 0
- **LOW**: 1
- **INFORMATIONAL**: 1

---

## 2. Identified Architecture Debt Items

### Item DEBT-1: Restore Endpoint Role Context Extraction (Low Severity)
- **ID**: `DEBT-1`
- **Severity**: Low
- **File**: [`backend/api/routes/disaster_recovery_admin.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/disaster_recovery_admin.py#L130-L144)
- **Problem**: `execute_restore_endpoint` verifies string parameter `admin_id` containing `"super"` or `"admin"` rather than extracting `AdminContext.admin.role` directly from `AdminDependency`.
- **Impact**: Low risk. Route is protected by `[Depends(require_admin)]`, but extracting authenticated role directly from session token context aligns with best practices.
- **Recommendation**: Refactor parameter to use `context: AdminDependency` and assert `context.admin.role == Role.SUPER_ADMIN`.
- **Implementation Required**: Yes (Low priority / optional hardening).

### Item DEBT-2: Non-Autonomous Retention Observation Model (Informational)
- **ID**: `DEBT-2`
- **Severity**: Informational
- **File**: [`core_model/capabilities/recovery_validation_service.py`](file:///home/dhurai/Projects/brud-ai/core_model/capabilities/recovery_validation_service.py#L150-L180)
- **Problem**: Backups older than 7 days are evaluated as `RETENTION_ELIGIBLE` by `evaluate_backup_lifecycle_state`, but no automated deletion mechanism exists.
- **Impact**: Zero risk. Enforces non-autonomous governance invariant (`STALE BACKUP != AUTOMATIC DELETION`).
- **Recommendation**: Maintain manual admin observation via `/admin/phase29/backups`.
- **Implementation Required**: No (By design).

---

## 3. Recommended Remediation Order
1. **DEBT-1**: Refactor `execute_restore_endpoint` in Phase 32 (or future maintenance phase) to validate `context.admin.role`.
2. **DEBT-2**: Retain non-autonomous retention observation model.
