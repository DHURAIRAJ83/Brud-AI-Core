# Phase 32 Technical Implementation Plan — Production Security Hardening & RBAC Context Enforcement

## 1. Goal Description
The objective of Phase 32 is to resolve the low-risk security hardening debt (`DEBT-1`) identified in Phase 31 by refactoring the database restore endpoint in [`backend/api/routes/disaster_recovery_admin.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/disaster_recovery_admin.py) to validate `context.admin.role == "SUPER_ADMIN"` directly from the authenticated session context (`AdminDependency`).

---

## 2. User Review Required

> [!IMPORTANT]
> PHASE 32 SOURCE CODE IMPLEMENTATION HAS NOT STARTED.
> NO SOURCE CODE OR DATABASE MUTATIONS HAVE OCCURRED.
> THIS IMPLEMENTATION PLAN REQUIRES EXPLICIT HUMAN AUTHORIZATION (`APPROVED — START PHASE 32 IMPLEMENTATION`) BEFORE CREATING OR MODIFYING ANY SOURCE CODE FILES.

---

## 3. Proposed Changes

### Component: Disaster Recovery Admin API

#### [MODIFY] [`backend/api/routes/disaster_recovery_admin.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/disaster_recovery_admin.py)

Refactor `execute_restore_endpoint`:

```python
@router.post("/restore/{backup_id}", response_model=dict[str, Any])
def execute_restore_endpoint(
    backup_id: str,
    payload: RestoreExecutionPayload,
    context: AdminDependency,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    """Execute explicit human-authorized database restore from verified backup snapshot.

    Requires SUPER_ADMIN authorization derived directly from authenticated AdminContext.
    """
    if context.admin.role.upper() != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database restore execution strictly requires SUPER_ADMIN authorization.",
        )

    with get_db_connection(settings) as db:
        service = DisasterRecoveryService(db)
        try:
            op = service.execute_human_authorized_restore(
                backup_id,
                target_db_path=payload.target_db_path,
                executed_by=context.admin.username or f"admin-{context.admin.id}",
                reason=payload.reason,
            )
            return op.to_dict()
        except (RestoreError, BackupIntegrityError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

#### [MODIFY] [`tests/core_model/test_phase29_disaster_recovery.py`](file:///home/dhurai/Projects/brud-ai/tests/core_model/test_phase29_disaster_recovery.py)
Update and expand RBAC assertion unit tests to verify:
- SUPER_ADMIN role in session context -> Allowed.
- ADMIN / AUDITOR role in session context -> 403 FORBIDDEN.
- Unauthenticated request -> 401 UNAUTHORIZED.

---

## 4. Verification Plan

### Automated Tests
1. Dedicated Phase 29 / Phase 32 Test Suite Execution:
   ```bash
   venv/bin/python -m pytest tests/core_model/test_phase29_disaster_recovery.py tests/core_model/test_phase30_recovery_validation.py -v
   ```
2. Combined Phase 13–32 Regression Test Suite Execution:
   ```bash
   venv/bin/python -m pytest tests/core_model/test_phase15_text_nlp_production_readiness.py tests/core_model/test_phase16_capability_matrix_and_routing.py tests/core_model/test_phase17_public_chat_capability_gate.py tests/core_model/test_phase18_public_chat_production_readiness.py tests/core_model/test_phase19_knowledge_gap_and_clarification.py tests/core_model/test_phase20_admin_knowledge_gap_governance.py tests/core_model/test_phase21_approved_candidate_curation.py tests/core_model/test_phase22_controlled_ingestion.py tests/core_model/test_phase23_quality_evaluation.py tests/core_model/test_phase24_release_management.py tests/core_model/test_phase25_deployment_readiness.py tests/core_model/test_phase26_production_observability.py tests/core_model/test_phase28_operations_hardening.py tests/core_model/test_phase29_disaster_recovery.py tests/core_model/test_phase30_recovery_validation.py tests/database/test_admin_automation_phase13_evaluation_and_dryrun.py tests/database/test_admin_automation_phase14_manual_execution.py tests/database/test_admin_rbac.py -v --tb=short 2>&1
   ```

### Production Database Integrity Verification
```bash
sha256sum data/database/brud_ai.db
stat -c %s data/database/brud_ai.db
```
Expected:
- SHA-256: `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729` (100% MATCH)
- Size: `11,096,064 bytes` (100% MATCH)
