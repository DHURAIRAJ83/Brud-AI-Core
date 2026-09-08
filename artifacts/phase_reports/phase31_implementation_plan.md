# Phase 31 — Proposed Architecture Hardening & Remediation Plan (Read-Only Proposal)

## 1. Context & Overview
The Phase 31 Audit verified that the Brud AI repository (Phases 13–30) is architecturally stable, non-autonomous, resilient, and 100% regression-verified (**1,488 / 1,488 tests PASSED**).

Only **1 Low-Severity item (`DEBT-1`)** and **1 Informational item (`DEBT-2`)** were identified.

This document outlines the proposed technical implementation plan if human authorization is granted for future hardening (e.g., Phase 32).

> [!IMPORTANT]
> PHASE 31 IS A READ-ONLY AUDIT. THIS IMPLEMENTATION PLAN IS PROPOSED ONLY AND MUST NOT BE EXECUTED WITHOUT EXPLICIT HUMAN APPROVAL (`APPROVED — BEGIN SOURCE CODE IMPLEMENTATION`).

---

## 2. Proposed Remediation Scope

### Component 1: Admin RBAC Session Context Hardening (`DEBT-1`)

#### [MODIFY] [`backend/api/routes/disaster_recovery_admin.py`](file:///home/dhurai/Projects/brud-ai/backend/api/routes/disaster_recovery_admin.py)
Refactor `execute_restore_endpoint` to extract authenticated role directly from session token context:

```python
@router.post("/restore/{backup_id}", response_model=dict[str, Any])
def execute_restore_endpoint(
    backup_id: str,
    payload: RestoreExecutionPayload,
    context: AdminDependency,
    settings: SettingsDependency = None,
) -> dict[str, Any]:
    # Assert authenticated SUPER_ADMIN role directly from session context
    if context.admin.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Database restore execution strictly requires SUPER_ADMIN authorization.",
        )
    ...
```

---

## 3. Verification Plan

### Automated Tests
```bash
venv/bin/python -m pytest tests/core_model/test_phase29_disaster_recovery.py -v
```

### Full Regression Suite
```bash
venv/bin/python -m pytest tests/core_model/test_phase15_text_nlp_production_readiness.py tests/core_model/test_phase16_capability_matrix_and_routing.py tests/core_model/test_phase17_public_chat_capability_gate.py tests/core_model/test_phase18_public_chat_production_readiness.py tests/core_model/test_phase19_knowledge_gap_and_clarification.py tests/core_model/test_phase20_admin_knowledge_gap_governance.py tests/core_model/test_phase21_approved_candidate_curation.py tests/core_model/test_phase22_controlled_ingestion.py tests/core_model/test_phase23_quality_evaluation.py tests/core_model/test_phase24_release_management.py tests/core_model/test_phase25_deployment_readiness.py tests/core_model/test_phase26_production_observability.py tests/core_model/test_phase28_operations_hardening.py tests/core_model/test_phase29_disaster_recovery.py tests/core_model/test_phase30_recovery_validation.py tests/database/test_admin_automation_phase13_evaluation_and_dryrun.py tests/database/test_admin_automation_phase14_manual_execution.py tests/database/test_admin_rbac.py -v --tb=short 2>&1
```

---

## 4. Proposed Verdict Criteria
- Dedicated Tests: All PASS
- Combined Regression: 1,488 / 1,488 PASSED
- Production DB SHA-256: `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729` (UNTOUCHED)
- Production DB Size: `11,096,064 bytes` (UNTOUCHED)
