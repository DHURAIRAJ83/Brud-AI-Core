# Master Brud AI End-to-End Audit — 01: Repository Structure Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect & Repository Auditor  
**Audit Location:** `artifacts/system_audit/end_to_end/`  
**Mode:** STRICT READ-ONLY, NON-MUTATING  

---

## 1. Full Repository Tree & Inventory

Brud AI is organized as a monorepo containing backend services, core machine learning modules, React frontends, test suites, datasets, model weights, and extensive governance audit artifacts.

### Repository High-Level Directory Metrics

| Top-Level Directory | Files | Lines of Code | Disk Size | Primary Purpose & Language |
|---|---|---|---|---|
| `backend/` | 523 | 173,208 | 7.39 MB | FastAPI application, database repositories, services, CLI tools (Python 3.13) |
| `core_model/` | 762 | 76,303 | 3.06 MB | PyTorch transformer architecture, tokenizer v2, RAG, memory, Mini Brain (Python) |
| `apps/` | 257 | 54,616 | 3.16 MB | React 19 web applications: `chatbot` (:5173) and `admin-dashboard` (:5174) (JS/JSX) |
| `tests/` | 511 | 172,716 | 7.01 MB | Pytest test suites across backend, database, core model, and evaluation (Python) |
| `artifacts/` | 1,355 | 27,494 | 256.41 MB | Phase evaluation logs, candidate checkpoints, experiment summaries (Markdown/JSON/.pt) |
| `deploy/` | 715 | 47,601 | 158.35 MB | Infrastructure verification scripts, model audit records, shell scripts |
| `docs/` | 265 | 32,153 | 1.93 MB | Architecture specifications, phase plans, and API/CLI guides (Markdown) |
| `data/` | 3,000+ | — | 4.5 GB | SQLite primary DB (`brud_ai.db`), backups, document workspaces, release artifacts |
| `models/` | 10 | — | 1.5 GB | Real external GGUF weights (Qwen 0.5B/1.5B) + 4 placeholder stub files |
| `./` (Root) | ~40 | ~15,000 | ~1.5 MB | Phase 59-60 manifests, root diagnostic markdown files, project configuration |

---

## 2. File Type Distribution (Across Non-Virtualenv Codebase)

- **Python (`.py`):** 1,634 files | ~420,000 lines of code
- **JavaScript / JSX (`.js`, `.jsx`):** 198 files | ~48,000 lines of code
- **Markdown (`.md`):** 842 files | ~110,000 lines of documentation and audit traces
- **JSON / JSONL (`.json`, `.jsonl`):** 960 files | Datasets, manifests, configurations, telemetry
- **SQLite Database (`.db`):** Primary database (`brud_ai.db`, 139 tables) + backup database snapshots
- **PyTorch Model Weights (`.pt`):** Checkpoints under `artifacts/candidates/` and `data/core_models/checkpoints/`
- **GGUF Model Weights (`.gguf`):** 2 real Qwen models (469 MB and 1.1 GB) + 4 text stub placeholders

---

## 3. Subsystem Breakdown: Core vs Experimental vs Legacy

1. **Active Core Backend (`backend/`):**
   - 94 API route modules under `backend/api/routes/` with 1,774 unique registered FastAPI endpoints.
   - 139 SQLite tables managed through repository abstractions under `backend/database/repositories/`.
   - 108 read-only inspection tools wired into `backend/services/admin_assistant_tools.py`.
2. **Core ML System (`core_model/`):**
   - Tokenizer v2 (`core_model/tokenization/tokenizer_v2.py`): 1,024-token BPE with byte fallback.
   - Brud-Small v2 Model (`BrudSmallV2Model`): 528,128 parameters, 2 layers, 128 hidden dim, 4 heads.
   - RAG Subsystem (`core_model/rag/`): 21 modules covering chunking, n-gram hashing, and hybrid search.
   - Conversation Memory (`core_model/conversation/`): 19 modules covering consent, budgets, and ranking.
   - Admin Assistant Mini Brain (`core_model/mini_brain/`): 34 subdirectories covering modular governance.
3. **Candidate & Remediation Zone (`artifacts/candidates/phase60/`):**
   - Phase 60 dataset (`phase60_dataset_v001.jsonl`, 2,000 records).
   - WS07 E3 sealed dataset (`phase60_ws07_e3_dataset_v001.jsonl`, 88 records).
   - E3 experiment candidates: `e3_a` through `e3_e` checkpoints and analytical evaluation logs.
