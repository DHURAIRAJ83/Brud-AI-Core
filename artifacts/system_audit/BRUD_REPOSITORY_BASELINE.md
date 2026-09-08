# BRUD AI — REPOSITORY BASELINE AUDIT (WS00)
**Audit Date:** 2026-09-07
**Auditor:** Antigravity Senior Architecture Audit Agent
**Scope:** Complete repository inventory — byte-level truth, not filename assumption

---

## REPOSITORY OVERVIEW

| Metric | Count |
|--------|-------|
| Root-level files | 506 |
| Root-level directories | 22 |
| Backend Python files | 527 |
| Core Model Python files | 818 |
| Frontend JSX/TSX files | 217 |
| Test Python files | 562 |
| Root-level phase report .md files | ~400+ |

> **CRITICAL FINDING:** 400+ phase report files (phase22_* through phase60_*) are stored at the repository **root level**. Documentation governance failure.

---

## TOP-LEVEL DIRECTORY STRUCTURE

| Directory | Purpose | Status |
|-----------|---------|--------|
| `backend/` | FastAPI backend, API routes, services, database | ACTIVE |
| `core_model/` | Domain logic, ML architecture, intelligence modules | ACTIVE |
| `apps/admin-dashboard/` | Vite/React admin UI | ACTIVE |
| `apps/chatbot/` | Vite/React public chat UI | ACTIVE |
| `tests/` | Pytest test suite | ACTIVE |
| `artifacts/` | Training checkpoints, ledgers, audit outputs | MIXED |
| `config/` | Configuration files | ACTIVE |
| `deploy/` | Deployment scripts | PARTIALLY_ACTIVE |
| `docs/` | Documentation | DOCUMENTATION_ONLY |
| `scripts/` | CLI and utility scripts | ACTIVE |
| `models/` | Model binary artifacts | ACTIVE |
| `data/` | Training/dataset data | ACTIVE |
| `scratch/` | Scratch space | LEGACY |
| `.agents/` | Antigravity agent rules | ACTIVE |
| `.claude/` | Claude config | LEGACY |
| `.codex/` | Codex config | LEGACY |
| `node_modules/` | Root-level node packages | DEAD |
| `.git/` | Git history | ACTIVE |
| `venv/` | Python virtual environment | ACTIVE |

---

## BACKEND STRUCTURE (527 Python files)

### backend/api/
- `main.py` — ACTIVE: FastAPI app factory, lifespan, middleware, CORS
- `api/route_registry.py` — ACTIVE: 156 registered route plugins
- `api/router.py` — ACTIVE: Combines eager + deferred loading
- `api/auth.py` — ACTIVE: AdminDependency, CsrfDependency
- `api/dependencies.py` — ACTIVE: SettingsDependency, PoolDependency
- `api/routes/` — ACTIVE: 94 route files

### backend/services/ (243 files)
- 39 mini_brain_* services — ACTIVE
- 11 dataset_sample_* services — ACTIVE
- 12 corpus_* services — ACTIVE
- 14 production_* services — ACTIVE
- 11 rag_* services — ACTIVE
- 8 admin_assistant_* services — ACTIVE
- 10 training-related services — ACTIVE
- ~138 other core services — ACTIVE

### backend/database/
- `schema.py` — ACTIVE: 766 KB master schema
- `migrations.py` — ACTIVE: Schema initialization
- `repositories/` — ACTIVE: 78 repository files
- `connection.py` / `connection_pool.py` — ACTIVE

### backend/models/ (64 files)
- 30 mini_brain_*.py — ACTIVE
- 34 domain model files — ACTIVE

### backend/core/ (9 files)
- config, exceptions, rate_limit, security, logging, json_utils — ACTIVE

---

## CORE_MODEL STRUCTURE (818 Python files, 41 directories)

| Module | Files | Status | Notes |
|--------|-------|--------|-------|
| admin/ | 5 | ACTIVE | Auth, RBAC, audit, tenant |
| admin_assistant/ | 16 | ACTIVE | Intent, actions, localization |
| architecture/ | 9 | ACTIVE | BrudSmallV2 transformer |
| capabilities/ | 14 | ACTIVE | Public gate, smart router |
| checkpoints/ | 7 | ACTIVE | Training checkpoints |
| conversation/ | 15 | ACTIVE | Memory, context, session |
| corpus/ | 25+ | ACTIVE | Corpus pipeline |
| eval/ | 5 | PARTIALLY_ACTIVE | POSSIBLE DUPLICATE of evaluation/ |
| evaluation/ | 5 | PARTIALLY_ACTIVE | POSSIBLE DUPLICATE of eval/ |
| inference/ | 1 | DEAD | Empty __init__.py only |
| inference_runtime/ | 12 | ACTIVE | Full generation engine |
| mini_brain/ | 34 dirs | ACTIVE | Intelligence, LLM, training |
| rag/ | 21 | ACTIVE | Full RAG pipeline |
| public_chat/ | 10 | ACTIVE | Chat routing policy |
| tool_gateway/ | 5 | ACTIVE | Tool invocation, MCP |
| Other modules | 100+ | ACTIVE | Various domain modules |

---

## APPS STRUCTURE

### apps/admin-dashboard/
- src/App.jsx — ACTIVE: 52 lazy-loaded pages, hash-based routing
- src/pages/ — ACTIVE: 77 pages + 3 subdirs
- src/components/ — ACTIVE: 19 shared components
- e2e/ — ACTIVE: Playwright E2E tests

### apps/chatbot/
- src/App.jsx — ACTIVE: Minimal (101 bytes)
- src/pages/, src/components/, src/services/ — ACTIVE

---

## TESTS STRUCTURE (562 files)

- tests/backend/ — ACTIVE: 200+ API/service tests
- tests/core_model/ — ACTIVE: Core model unit tests
- tests/database/ — ACTIVE: DB/schema tests
- tests/e2e/ — ACTIVE: Playwright tests
- tests/evaluation/ — PARTIALLY_ACTIVE

---

## POSSIBLE DUPLICATES FLAGGED

| Group | File A | File B | Investigation |
|-------|--------|--------|---------------|
| Eval | core_model/eval/ | core_model/evaluation/ | Different scopes? |
| Inference | core_model/inference/ (empty) | core_model/inference_runtime/ | inference/ is DEAD |

---

## FILE STATUS SUMMARY

| Classification | Estimated Count |
|---------------|-----------------|
| ACTIVE | ~1,200 |
| PARTIALLY_ACTIVE | ~50 |
| DOCUMENTATION_ONLY | ~400 (phase reports) |
| DUPLICATE | ~30 |
| LEGACY | ~10 |
| TEST_ONLY | ~562 |
| BUILD_ARTIFACT | ~5 |
| DEAD | ~5 |
| UNKNOWN | ~20 |

---
*WS00 Complete*
