# BRUD AI — DATABASE & PERSISTENCE AUDIT (WS10)
**Audit Date:** 2026-09-07

---

## DATABASE TECHNOLOGY

**Primary Database:** SQLite
- Single file, path configured via `Settings.resolved_database_path`
- WAL mode supported (`database_wal` setting)
- Connection pooling: Phase 7C-33 `ConnectionPool`
- No PostgreSQL, no Supabase, no Firebase in production path
- No Redis

---

## SCHEMA OVERVIEW

`backend/database/schema.py` — 766 KB — Single master schema file

This file defines ALL tables for the entire application. Key schema sections:
- PHASE1_SCHEMA → admin users, sessions, audit
- PHASE2_SCHEMA → datasets, feedback, governance
- PHASE3_SCHEMA → documents
- PHASE4_SCHEMA → corpus
- PHASE5_SCHEMA → data sources
- PHASE6_SCHEMA → data versioning
- PHASE7_SCHEMA → imports
- PHASE8_SCHEMA → admin assistant, proposals
- PHASE9_SCHEMA → inference runtime
- PHASE10_SCHEMA → manual data
- PHASE11_SCHEMA → instruction tuning
- PHASE12_SCHEMA → tokenizers
- PHASE13_SCHEMA → model release
- PHASE14_SCHEMA → model evaluation
- PHASE15_SCHEMA → pretraining
- PHASE16_SCHEMA → RAG
- PHASE17_SCHEMA → memory (conversation, sessions, memory items)
- PHASE18_SCHEMA → public chat
- PHASE19_SCHEMA → knowledge gaps
- PHASE20_SCHEMA → knowledge routing
- PHASE21_SCHEMA → mini brain
- PHASE22_SCHEMA and beyond → extended features

---

## REPOSITORY INVENTORY (78 files)

| Category | Files | Status |
|----------|-------|--------|
| mini_brain_*.py | 20+ | ACTIVE |
| dataset_*.py | 8 | ACTIVE |
| corpus.py | 1 | ACTIVE (77 KB) |
| conversation_memory.py | 1 | ACTIVE (41 KB) |
| production_readiness.py | 1 | ACTIVE (79 KB) |
| rag.py | 1 | ACTIVE (43 KB) |
| rag_sandbox.py | 1 | ACTIVE (88 KB) |
| training_incremental.py | 1 | ACTIVE (79 KB) |
| external_data_providers.py | 1 | ACTIVE (35 KB) |
| knowledge_gap.py | 1 | ACTIVE (38 KB) |
| feedback.py | 1 | ACTIVE (37 KB) |
| governance.py | 1 | ACTIVE (20 KB) |
| dataset_sample_import.py | 1 | ACTIVE (66 KB) |
| dataset_verification.py | 1 | ACTIVE (54 KB) |
| model_release.py | 1 | ACTIVE (22 KB) |
| admin.py | 1 | ACTIVE (14 KB) |
| phase2.py | 1 | ACTIVE (44 KB — includes AuditLogRepository) |

---

## POTENTIAL ISSUE: phase2.py Repository

`backend/database/repositories/phase2.py` (44 KB) contains:
- `AuditLogRepository`
- `AdminApprovalRepository`
- `SettingsRepository`
- Multiple other repositories

**This is a multi-responsibility file named after a phase** — naming is misleading.
**Risk:** Developers may duplicate these repositories not knowing they exist in phase2.py.

---

## MIGRATIONS

`backend/database/migrations.py` — ACTIVE
- `initialize_database()` — called at app startup
- Applies all schema sections in order
- Uses `PRAGMA journal_mode=WAL` when enabled
- Idempotent — safe to call on startup

---

## CONNECTION MANAGEMENT

| Component | Status | Notes |
|-----------|--------|-------|
| `connection.py` | ACTIVE | Simple `database_connection()` context manager |
| `connection_pool.py` | ACTIVE | Phase 7C-33 pool, scoped to app instance |
| Connection pool usage | PARTIAL | Only 2 routes opted into pool (base_training.py) |

**Finding:** Most routes still use direct `database_connection()` not the pool. Pool adoption is incomplete.

---

## DUPLICATE TABLE RISK

The schema has been built phase-by-phase. No table duplication detected in schema.py (single source of truth). However:
- `repositories/phase2.py` contains multiple unrelated repositories
- `AuditLogRepository` appears in both `phase2.py` and is imported from `repositories` package `__init__.py`

---

## FINDINGS

1. **COMPLETE:** Single SQLite database — no competing datastores
2. **COMPLETE:** Schema centralized in schema.py (766 KB)
3. **COMPLETE:** 78 repositories with clear domain ownership
4. **PARTIAL:** Connection pool only adopted by 2 routes — most use unpooled connection
5. **RISK:** `phase2.py` is a multi-responsibility file with misleading name
6. **RISK:** 766 KB schema file — hard to navigate, risk of duplicate table creation in future
7. **NO DUPLICATE DATABASES** detected

---
*WS10 Complete*
