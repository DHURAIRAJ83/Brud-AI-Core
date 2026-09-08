# BRUD AI — GOVERNANCE AUDIT (WS20)
**Audit Date:** 2026-09-07

---

## GOVERNANCE DIMENSIONS

### 1. Data Governance
- Dataset governance manifest (`dataset_governance_manifest_service.py`)
- Source rights verification (`dataset_verification_source_rights_service.py`)
- License policy (`core_model/corpus/licence_policy.py`)
- Contamination checking (`dataset_sample_contamination_service.py`)
- PII protection (`dataset_sample_pii_safety_service.py`)

### 2. Model Governance
- Governed builds pipeline (`governed_builds` routes + services)
- Model release governance (`core_model/release/`)
- Mini Brain release governance (`mini_brain_release_governance_service.py`)
- Production readiness gate (multiple checks)

### 3. Admin Action Governance
- Admin assistant action allowlist (`action_registry.py`)
- `BLOCKED_ACTION_SUBSTRINGS` guard
- Proposal → Review → Execute flow
- Fingerprint staleness check (prevent stale mutation)
- Full audit trail (AuditLogRepository)

### 4. Memory Governance
- Consent-based memory (`memory_policy.py`)
- Purpose-bounded storage
- Category allowlist
- Safety scan before activation

### 5. Tool Governance
- Tool permission system (`mini_brain_plugin_governance_service.py`)
- Execution tokens (single-use)
- Admin-initiated tool execution only
- `ToolAuthorizationError` gate

### 6. RAG Governance
- RAG Sandbox (test before production)
- Acceptance workflow for promoting sandbox content
- Access control per scope

### 7. Training Governance
- Pre-training readiness checklist
- Qualification guard (`database/qualification_guard.py`)
- Training reliability service
- Incremental training governance

---

## AUDIT TRAIL COVERAGE

| Domain | Audit Mechanism | Status |
|--------|----------------|--------|
| Auth events | AuditLogRepository | ACTIVE |
| Admin actions | AuditLogRepository | ACTIVE |
| Proposal lifecycle | AuditLogRepository | ACTIVE |
| Chat orchestration | chat_orchestration_runs table | ACTIVE |
| Memory events | memory item events | ACTIVE |
| Tool calls | deterministic_tool_execution_events | ACTIVE |
| Mini Brain events | mini_brain_llm_runtime_events | ACTIVE |
| Training events | training_runs + training events | ACTIVE |

---

## GOVERNANCE GAPS

| Gap | Risk |
|-----|------|
| No RBAC — all admins equal | MEDIUM |
| Provider API keys not encrypted | MEDIUM |
| No time-limited admin sessions (configurable?) | LOW |
| Mini Brain plugin system ships 0 real plugins | LOW (expected) |

---

## FINDINGS

1. **EXTENSIVE:** Governance spans data, model, action, memory, tool, RAG, training
2. **COMPLETE:** Admin action governance via proposal/review/execute flow
3. **COMPLETE:** Data governance with contamination, PII, license checks
4. **COMPLETE:** Audit trail across all critical domains
5. **ACTIVE:** Memory consent and safety governance
6. **GAP:** No RBAC — single permission tier for all admins
7. **GAP:** No automated rollback triggers on governance failure

---
*WS20 Complete*
