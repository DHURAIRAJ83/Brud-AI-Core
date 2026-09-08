# Phase 22 Implementation Plan — Controlled RAG Ingestion & Dataset Export / Training Preparation

## 1. Objectives & Architectural Principles
Phase 22 implements a strictly human-governed, auditable, atomic, and rollback-aware production ingestion and export boundary for RAG knowledge sources and training dataset artifacts.

**Key Invariants**:
- **No Autonomous Learning**: Zero model training, fine-tuning, or automatic weight modifications.
- **Explicit Approval Required**: Status `READY_FOR_INGESTION` or `READY_FOR_EXPORT` **NEVER** triggers production mutation automatically. Explicit admin interaction is mandatory.
- **Security Boundary Protection**: `SECURITY_ADMIN_BOUNDARY` records and secret-bearing content are permanently blocked.
- **Atomic Operations & Rollback Awareness**: Immutable versioning for RAG sources and dataset artifacts with explicit rollback pointers.
- **Database & Test Isolation**: Automated tests execute against `:memory:` or temporary SQLite databases only. Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) remain 100% UNTOUCHED.

---

## 2. Target Component Specifications

### Component A: Pure Domain Controlled Ingestion Service
- Path: `core_model/capabilities/controlled_ingestion_service.py`
- Responsibilities:
  - Immutable plan dataclasses: `IngestionPlan`, `ExportPlan`, `ControlledOperationRecord`.
  - State Machines:
    - RAG: `READY_FOR_INGESTION` → `PREFLIGHT_VALIDATED` → `DRY_RUN_READY` → `PENDING_APPROVAL` → `APPROVED_FOR_INGESTION` → `INGESTING` → `INGESTED` → `VERIFIED`. (Failures: `PREFLIGHT_FAILED`, `INGESTION_FAILED`, `VERIFICATION_FAILED`, `ROLLED_BACK`).
    - Dataset: `READY_FOR_EXPORT` → `PREFLIGHT_VALIDATED` → `EXPORT_DRY_RUN_READY` → `PENDING_APPROVAL` → `APPROVED_FOR_EXPORT` → `EXPORTING` → `EXPORTED` → `VERIFIED`. (Failures: `PREFLIGHT_FAILED`, `EXPORT_FAILED`, `VERIFICATION_FAILED`, `ROLLED_BACK`).
  - Pre-flight validation rules, SHA-256 canonical hashing, secret sanitization, duplicate/conflict policy evaluation, and dry-run execution.

### Component B: SQLite Repository for Phase 22 Operations
- Path: `backend/database/repositories/controlled_ingestion_repository.py`
- Tables:
  - `phase22_artifact_versions`
  - `phase22_operation_logs`
  - `phase22_rag_ingestion_records`
  - `phase22_dataset_export_records`
- Complete DDL (`CREATE TABLE IF NOT EXISTS`), indexing, atomic insertion, state update, and metrics aggregation methods.

### Component C: High-Level RAG Ingestion Service
- Path: `backend/services/controlled_rag_ingestion_service.py`
- Pre-flight verification, dry-run plan generation, explicit approval gate, versioned RAG document insertion into knowledge sources, post-ingestion verification, audit logging, and version rollback pointer management.

### Component D: High-Level Dataset Export Service
- Path: `backend/services/controlled_dataset_export_service.py`
- Pre-flight verification, dry-run plan generation, explicit approval gate, versioned dataset artifact export to `data/dataset_exports/` (`manifest.json`, `records.jsonl`, `provenance.json`, `checksums.json`), post-export checksum verification, audit logging, and rollback management.

### Component E: Admin API Router & Registry
- Path: `backend/api/routes/controlled_ingestion_admin.py`
- Prefix: `/admin/phase22`
- Endpoints: Preflight, Dry-Run, Approve, Ingest, Export, Status, Rollback, Metrics for RAG and Dataset candidate records.
- Registered in `backend/api/route_registry.py`.

### Component F: Dedicated Test Suite
- Path: `tests/core_model/test_phase22_controlled_ingestion.py`
- **120+ dedicated test cases** verifying all domain schemas, validation rules, security boundaries, state transitions, repository operations, service executions, dry-runs, approvals, rollbacks, audit events, RBAC, AST security, and production DB SHA-256 integrity.

---

## 3. Verification Strategy & Commands
```bash
# 1. Dedicated test suite
venv/bin/python -m pytest tests/core_model/test_phase22_controlled_ingestion.py -v --tb=short

# 2. Combined full regression test suite (Phases 13–22 + RBAC)
venv/bin/python -m pytest tests/core_model/test_phase15_text_nlp_production_readiness.py tests/core_model/test_phase16_capability_matrix_and_routing.py tests/core_model/test_phase17_public_chat_capability_gate.py tests/core_model/test_phase18_public_chat_production_readiness.py tests/core_model/test_phase19_knowledge_gap_and_clarification.py tests/core_model/test_phase20_admin_knowledge_gap_governance.py tests/core_model/test_phase21_approved_candidate_curation.py tests/core_model/test_phase22_controlled_ingestion.py tests/database/test_admin_automation_phase13_evaluation_and_dryrun.py tests/database/test_admin_automation_phase14_manual_execution.py tests/database/test_admin_rbac.py -v --tb=short

# 3. Production DB SHA-256 & Size Check
sha256sum data/database/brud_ai.db && ls -l data/database/brud_ai.db

# 4. Git Branch & HEAD Check
git status --short && git branch --show-current && git rev-parse HEAD
```
