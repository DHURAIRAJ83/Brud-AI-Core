# Phase 23 Implementation Plan — RAG & Dataset Quality Evaluation, Version Validation & Human-Approved Improvement Loop

## 1. Objectives & Architectural Principles
Phase 23 introduces an **evaluation, version validation, metric comparison, and human review layer** for Phase 22 production artifacts (RAG source versions and Dataset export bundles).

**Key Architectural Invariants**:
- **Evaluation PASS != Automatic Promotion**: A higher evaluation score **NEVER** automatically overwrites production RAG knowledge, updates capability routing, or promotes dataset releases.
- **Strict Human Review Gate**: Evaluation results advance to `PENDING_HUMAN_REVIEW`. Only explicit human admin review can transition an evaluation to `APPROVED_IMPROVEMENT`.
- **Zero Autonomous Learning**: Zero model training, zero fine-tuning, zero automatic weight modifications, zero background workers, zero Celery/APScheduler schedulers.
- **Security Boundary Protection**: `SECURITY_ADMIN_BOUNDARY` records and secret-bearing content are permanently prohibited from evaluation, comparison, or approval.
- **Full Provenance Chain**:
  `source_request_id` → `source_gap_id` → `source_record_id` → `candidate_id` → `operation_id` → `artifact_id` → `evaluation_id` → `comparison_id` → `review_id` → `decision`
- **Database & Test Isolation**: All tests execute against `:memory:` or temporary SQLite databases. Production database `data/database/brud_ai.db` SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) remain 100% UNTOUCHED.

---

## 2. Target Component Specifications

### Component A: Pure Domain Evaluation Service
- Path: `core_model/capabilities/evaluation_service.py`
- Responsibilities:
  - Immutable Dataclasses: `EvaluationMetric`, `EvaluationRecord`, `VersionComparison`, `RegressionResult`, `EvaluationReview`, `EvaluationProvenance`.
  - State Machines:
    - Evaluation Lifecycle: `EVALUATION_CREATED` → `PREFLIGHT_VALIDATED` → `EVALUATED` → `PENDING_HUMAN_REVIEW` → `APPROVED` (or `REJECTED` / `DEFERRED`).
    - Comparison Classification: `BETTER`, `SAME`, `REGRESSED`, `INCONCLUSIVE`.
  - Quality Validation & Metric Calculation:
    - RAG: retrieval relevance, grounding score, citation coverage, chunk quality, duplicate content, secret/PII audit.
    - Dataset: JSONL validity, schema compliance, checksum integrity, record completeness, secret/PII audit.
  - Deterministic version comparison engine (Version N vs Version N+1) and regression detection.

### Component B: SQLite Repository for Phase 23 Operations
- Path: `backend/database/repositories/evaluation_repository.py`
- Additive Tables:
  - `phase23_evaluation_records`
  - `phase23_metric_results`
  - `phase23_version_comparisons`
  - `phase23_review_decisions`
- Complete DDL (`CREATE TABLE IF NOT EXISTS`), indexing, atomic insertion, state update, and aggregate metrics methods.

### Component C: Backend RAG & Dataset Evaluation Services
- Paths:
  - `backend/services/rag_evaluation_service.py`
  - `backend/services/dataset_evaluation_service.py`
  - `backend/services/version_comparison_service.py`
- High-level orchestration for fetching Phase 22 artifacts, running pre-evaluation validation, computing metrics, storing evaluation records, comparing versions, and logging audit events.

### Component D: FastAPI Admin API Router & Registry
- Path: `backend/api/routes/evaluation_admin.py`
- Prefix: `/admin/phase23`
- Dependencies: `[Depends(require_admin)]`
- Endpoints:
  - `GET  /admin/phase23/rag/{artifact_id}/preflight`
  - `POST /admin/phase23/rag/{artifact_id}/evaluate`
  - `GET  /admin/phase23/rag/{artifact_id}/metrics`
  - `GET  /admin/phase23/rag/compare/{version_a}/{version_b}`
  - `POST /admin/phase23/rag/{evaluation_id}/review`
  - `POST /admin/phase23/rag/{evaluation_id}/approve`
  - `POST /admin/phase23/rag/{evaluation_id}/reject`
  - `POST /admin/phase23/rag/{evaluation_id}/defer`
  - `GET  /admin/phase23/datasets/{artifact_id}/preflight`
  - `POST /admin/phase23/datasets/{artifact_id}/evaluate`
  - `GET  /admin/phase23/datasets/{artifact_id}/metrics`
  - `GET  /admin/phase23/datasets/compare/{version_a}/{version_b}`
  - `POST /admin/phase23/datasets/{evaluation_id}/review`
  - `POST /admin/phase23/datasets/{evaluation_id}/approve`
  - `POST /admin/phase23/datasets/{evaluation_id}/reject`
  - `POST /admin/phase23/datasets/{evaluation_id}/defer`
  - `GET  /admin/phase23/metrics`
  - `GET  /admin/phase23/evaluations/{evaluation_id}`
- Register `evaluation_admin` in `backend/api/route_registry.py`.

### Component E: Dedicated Test Suite
- Path: `tests/core_model/test_phase23_quality_evaluation.py`
- **120+ dedicated unit and integration tests** verifying:
  - Dataclasses, metric schemas, state machine transitions
  - RAG metric calculations (relevance, grounding, citation coverage)
  - Dataset metric calculations (JSONL validity, checksums, schema compliance)
  - Version comparison engine & regression detection (`BETTER`, `SAME`, `REGRESSED`, `INCONCLUSIVE`)
  - Security boundary prohibition (`SECURITY_ADMIN_BOUNDARY` hard block)
  - Secret sanitization & PII protection
  - Human review gate enforcement (`Evaluation PASS != Approval`)
  - Full provenance chain preservation across evaluation, comparison, and decision
  - Admin RBAC (Super Admin/Admin allowed, Auditor read-only, Public User denied)
  - AST Security (absence of `eval`, `exec`, `subprocess`, `celery`, `apscheduler`, network calls)
  - Isolated database execution (`:memory:`)
  - Production DB SHA-256 (`34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`) and size (`11,096,064 bytes`) 100% UNTOUCHED.

---

## 3. Verification Strategy & Commands
```bash
# 1. Run Phase 23 dedicated test suite (120+ tests)
venv/bin/python -m pytest tests/core_model/test_phase23_quality_evaluation.py -v --tb=short

# 2. Run full combined Phase 13–23 regression test suite (766+ tests)
venv/bin/python -m pytest tests/core_model/test_phase15_text_nlp_production_readiness.py tests/core_model/test_phase16_capability_matrix_and_routing.py tests/core_model/test_phase17_public_chat_capability_gate.py tests/core_model/test_phase18_public_chat_production_readiness.py tests/core_model/test_phase19_knowledge_gap_and_clarification.py tests/core_model/test_phase20_admin_knowledge_gap_governance.py tests/core_model/test_phase21_approved_candidate_curation.py tests/core_model/test_phase22_controlled_ingestion.py tests/core_model/test_phase23_quality_evaluation.py tests/database/test_admin_automation_phase13_evaluation_and_dryrun.py tests/database/test_admin_automation_phase14_manual_execution.py tests/database/test_admin_rbac.py -v --tb=short

# 3. Production DB SHA-256 & Size Check
sha256sum data/database/brud_ai.db
stat -c %s data/database/brud_ai.db

# 4. Git Branch, HEAD, and Stash Status Check
git status --short
git branch --show-current
git rev-parse HEAD
git stash list
```
