# Phase 24 Implementation Plan — Knowledge Release Management, Promotion & Rollback Governance

## 1. Objectives & Architectural Principles
Phase 24 introduces a human-governed **release candidate, validation, promotion, active version management, and non-destructive rollback layer** for Phase 23 evaluated artifacts.

**Key Architectural Invariants**:
- **Evaluation APPROVED != Automatic Promotion**: An approved evaluation **NEVER** automatically creates a production release or promotes an artifact. Explicit human admin action is required.
- **Strict Human Approval Gate**: Release candidates transition through `PENDING_RELEASE_APPROVAL` to `RELEASE_APPROVED` before explicit promotion execution.
- **Atomic Promotion**: Active version pointer updates execute within atomic transaction boundaries. Failed promotion rolls back cleanly without leaving partial pointers.
- **Non-Destructive Rollback**: Rollback transitions active pointer back to a historical active release version without deleting version history or filesystem artifacts.
- **Zero Autonomous Learning**: Zero model training, zero fine-tuning, zero automatic weight modifications, zero background workers, zero Celery/APScheduler jobs.
- **Full Provenance Chain**:
  `source_request_id` → `source_gap_id` → `source_record_id` → `candidate_id` → `operation_id` → `artifact_id` → `evaluation_id` → `comparison_id` → `review_id` → `release_id` → `promotion_operation_id` → `rollback_operation_id`
- **Database & Test Isolation**: All tests execute against `:memory:` or temporary SQLite databases. Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) remain 100% UNTOUCHED.

---

## 2. Target Component Specifications

### Component A: Pure Domain Release Management Service
- Path: `core_model/capabilities/release_management_service.py`
- Responsibilities:
  - Immutable Dataclasses: `ReleaseCandidate`, `ReleaseApproval`, `PromotionOperation`, `RollbackOperation`, `ReleaseProvenance`.
  - Lifecycle State Machine:
    - `EVALUATION_APPROVED` → `RELEASE_CANDIDATE_CREATED` → `RELEASE_PREFLIGHT_VALIDATED` → `PENDING_RELEASE_APPROVAL` → `RELEASE_APPROVED` → `READY_FOR_PROMOTION` → `PROMOTING` → `PROMOTED` → `ACTIVE`.
    - Terminal/Failure states: `RELEASE_REJECTED`, `RELEASE_DEFERRED`, `PROMOTION_FAILED`, `VERIFICATION_FAILED`, `ROLLED_BACK`.
  - Secret & Security Boundary re-verification (`SECURITY_ADMIN_BOUNDARY` hard block).
  - Idempotency key computation for promotion and rollback operations.

### Component B: SQLite Repository for Phase 24 Operations
- Path: `backend/database/repositories/release_repository.py`
- Additive Tables:
  - `phase24_release_candidates`
  - `phase24_release_approvals`
  - `phase24_promotion_operations`
  - `phase24_rollback_operations`
  - `phase24_active_version_pointers`
- Complete DDL (`CREATE TABLE IF NOT EXISTS`), indexing, atomic insertion, active pointer updates, state transitions, and audit logging.

### Component C: Backend Release & Promotion Services
- Paths:
  - `backend/services/rag_release_service.py`
  - `backend/services/dataset_release_service.py`
  - `backend/services/promotion_rollback_service.py`
- High-level orchestration for fetching Phase 23 evaluation records, validating release preflight, storing release candidates, executing atomic promotion, updating active version pointers, executing non-destructive rollback, and generating audit logs.

### Component D: FastAPI Admin API Router & Registry
- Path: `backend/api/routes/release_admin.py`
- Prefix: `/admin/phase24`
- Dependencies: `[Depends(require_admin)]`
- Endpoints:
  - `GET  /admin/phase24/releases/{release_id}/preflight`
  - `POST /admin/phase24/releases/create`
  - `POST /admin/phase24/releases/{release_id}/review`
  - `POST /admin/phase24/releases/{release_id}/approve`
  - `POST /admin/phase24/releases/{release_id}/reject`
  - `POST /admin/phase24/releases/{release_id}/promote`
  - `POST /admin/phase24/releases/{release_id}/rollback`
  - `GET  /admin/phase24/releases`
  - `GET  /admin/phase24/active`
  - `GET  /admin/phase24/metrics`
- Register `release_admin` in `backend/api/route_registry.py`.

### Component E: Dedicated Test Suite
- Path: `tests/core_model/test_phase24_release_management.py`
- Target: **120+ dedicated unit and integration tests** verifying:
  - Dataclasses, state machine transitions, invalid transition error handling
  - Pre-release validation & secret re-verification
  - `SECURITY_ADMIN_BOUNDARY` hard block
  - RAG & Dataset release candidate creation
  - Human release approval gate (`Evaluation APPROVED != Automatic Promotion`)
  - Atomic promotion & active pointer management
  - Non-destructive rollback to historical active versions
  - Full provenance chain preservation across 12 tracking levels
  - Idempotency key calculation and duplicate promotion protection
  - Admin RBAC (Super Admin/Admin allowed, Auditor read-only, Public User denied)
  - AST Security (absence of `eval`, `exec`, `subprocess`, `celery`, `apscheduler`, network calls)
  - Isolated database execution (`:memory:`)
  - Production DB SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) 100% UNTOUCHED.

---

## 3. Proposed Verification Strategy & Commands
```bash
# 1. Run Phase 24 dedicated test suite (120+ tests)
venv/bin/python -m pytest tests/core_model/test_phase24_release_management.py -v --tb=short

# 2. Run full combined Phase 13–24 regression test suite (886+ tests)
venv/bin/python -m pytest tests/core_model/test_phase15_text_nlp_production_readiness.py tests/core_model/test_phase16_capability_matrix_and_routing.py tests/core_model/test_phase17_public_chat_capability_gate.py tests/core_model/test_phase18_public_chat_production_readiness.py tests/core_model/test_phase19_knowledge_gap_and_clarification.py tests/core_model/test_phase20_admin_knowledge_gap_governance.py tests/core_model/test_phase21_approved_candidate_curation.py tests/core_model/test_phase22_controlled_ingestion.py tests/core_model/test_phase23_quality_evaluation.py tests/core_model/test_phase24_release_management.py tests/database/test_admin_automation_phase13_evaluation_and_dryrun.py tests/database/test_admin_automation_phase14_manual_execution.py tests/database/test_admin_rbac.py -v --tb=short

# 3. Production DB SHA-256 & Size Check
sha256sum data/database/brud_ai.db
stat -c %s data/database/brud_ai.db

# 4. Git Branch, HEAD, and Stash Status Check
git status --short
git branch --show-current
git rev-parse HEAD
git stash list
```
