# Master Brud AI System Audit — 01: Repository Inventory

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect & Repository Auditor  
**Audit Mode:** Strict Read-Only Deep Inspection  
**Audit Directory:** `artifacts/system_audit/master/`  

---

## 1. High-Level Repository Structural Breakdown

The Brud AI repository is a monorepo containing backend services, core machine learning modules, web frontend interfaces, deployment tooling, datasets, model artifacts, and an extensive test harness.

| Component / Subsystem | Directory | Files | Lines of Code | Size (Disk) | Primary Tech Stack |
|---|---|---|---|---|---|
| **Backend Services & API** | `backend/` | 523 | 173,208 | 7.39 MB | Python 3.13, FastAPI, SQLite, Pydantic v2 |
| **Core ML & Tokenizer** | `core_model/` | 762 | 76,303 | 3.06 MB | PyTorch, NumPy, Custom BPE Tokenizer v2 |
| **Web Frontends** | `apps/` | 257 | 54,616 | 3.16 MB | React 19, Vite, Vitest, Playwright |
| **Test Suites** | `tests/` | 511 | 172,716 | 7.01 MB | Pytest, AnyIO |
| **Artifacts & Runs** | `artifacts/` | 1,355 | 27,494 | 256.41 MB | Markdown, JSON, PyTorch Checkpoints |
| **Deploy & Infrastructure** | `deploy/` | 715 | 47,601 | 158.35 MB | Shell scripts, system configs, verification logs |
| **Documentation** | `docs/` | 265 | 32,153 | 1.93 MB | Markdown specifications and audits |
| **Data & SQLite Storage** | `data/` | 3,000+ | — | 4.5 GB | SQLite DB (`brud_ai.db`), JSONL, backups |
| **Model Weights & GGUF** | `models/` | 10 | — | 1.5 GB | PyTorch `.pt`, GGUF (Qwen 0.5B/1.5B) |
| **Repository Root Files** | `./` | ~40 | ~15,000 | ~1.5 MB | Phase manifests, audit reports, configs |

---

## 2. Classification of Subsystems (Active vs Experimental vs Obsolete)

### A. Active Production / Runtime Files [HIGH CONFIDENCE]
- **API & App Entrypoint:** `backend/main.py`, `backend/core/config.py`, `backend/core/application.py`.
- **Database Layer:** `backend/database/connection.py`, `backend/database/schema.py`, `data/database/brud_ai.db` (139 SQLite tables).
- **Public Chat Runtime:** `backend/api/routes/public_chat_runtime.py`, `backend/services/public_chat_routing_service.py`.
- **Admin Assistant API & Runtime:** `backend/api/routes/admin_assistant.py`, `backend/services/admin_assistant_chat_service.py`, `backend/services/admin_assistant_tools.py` (108 active read-only tools).
- **Governance Gateways:** `core_model/release/phase44_runtime_governance.py`, `backend/services/admin_assistant_write_governance.py`.
- **Web Frontend Apps:** `apps/admin-dashboard` (Vite on port 5174), `apps/chatbot` (Vite on port 5173).

### B. Active Development / Remediation Files [HIGH CONFIDENCE]
- **Candidate Training Framework:** `artifacts/candidates/phase60/run_controlled_training_ws05.py`, `artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py`.
- **Admin Assistant Expansion Engine:** `core_model/admin_assistant/dataset_expansion_engine.py`, `core_model/admin_assistant/dataset_expansion_validator.py`, `backend/services/admin_assistant_dataset_expansion_service.py`.
- **Model Evaluation Probes:** `artifacts/candidates/phase60/run_capability_evaluation_ws06.py` (24 CAP probes).
- **Phase 60 Test Harness:** `tests/evaluation/test_phase60_*.py` (9 active test files, 1,894 passing tests).

### C. Experimental Files [MEDIUM CONFIDENCE]
- **Mini Brain Multimodal & Vision Modules:** `core_model/mini_brain/vision_*`, `core_model/mini_brain/voice_runtime`.
- **Mini Brain Continuous Learning Skeleton:** `core_model/mini_brain/continuous_learning/`, `core_model/mini_brain/continuous_learning_center/`.
- **External AI Gateways:** `core_model/mini_brain/external_ai_gateway/` (stubs for Ollama / external models).

### D. Deprecated / Obsolete Files [HIGH CONFIDENCE]
- **Old Phase Manifests in Repo Root:** Root-level manifests from Phase 21 through Phase 59 (e.g., `phase59_ws02_transformation_manifest.json`, `phase59_ws07_manifest.json`). Kept for audit provenance but no longer executed.
- **Data Core Models Legacy Checkpoints:** Over 1,200 tiny test adapter checkpoints (`data/core_models/checkpoints/adapter-it-*`, 37KB to 106KB) created during earlier phase integration drills.

### E. Duplicate Implementations [HIGH CONFIDENCE]
- **Tokenizers:** `core_model/tokenization/tokenizer.py` (v1) vs `core_model/tokenization/tokenizer_v2.py` (v2, 1024-vocab BPE, active).
- **Inference Runtimes:** `backend/services/inference_runtime_service.py` (Phase 15 runtime) vs `core_model/mini_brain/llm_runtime/` (Mini Brain MB-28 rule-based wrapper) vs `artifacts/candidates/phase60/run_controlled_training_ws05.py` (standalone PyTorch model class).
- **Canary & Governance:** `core_model/release/phase44_runtime_canary.py` vs `core_model/release/phase44_runtime_governance.py` vs `backend/services/admin_assistant_write_governance.py`.

### F. Dead Code / Unwired Modules [HIGH CONFIDENCE]
- **`core_model/inference/`:** Empty directory except for `__init__.py` (354 bytes). All inference actually runs via `core_model/inference_runtime/` or candidate runners.
- **`models/active/`:** Completely empty (only contains `.gitkeep`). No model is deployed to active production storage.
- **`models/checkpoints/` & `models/registry/`:** Only contain `.gitkeep`.
- **Electron Container:** No Electron application files exist. Only Playwright-internal dependency files inside `apps/admin-dashboard/node_modules/`.
- **Docker Tooling:** Zero `Dockerfile` or `docker-compose.yml` files found in repository.

### G. Placeholder / Mock Implementations [HIGH CONFIDENCE]
- **Placeholder Models in `models/`:**
  - `models/brud_v1.gguf` (18 bytes - plain text stub)
  - `models/candidate_model.gguf` (20 bytes - plain text stub)
  - `models/tiny_model.gguf` (21 bytes - plain text stub)
  - `models/trained_model.gguf` (9 bytes - plain text stub)
- **External Local LLM in `models/`:**
  - `models/qwen2.5-0.5b-instruct-q4_k_m.gguf` (469 MB, real external Qwen model)
  - `models/qwen2.5-1.5b-instruct-q4_k_m.gguf` (1.1 GB, real external Qwen model)
- **Mini Brain Vision Integration:** `core_model/mini_brain/vision_model_integration/` contains structural dataclasses and metadata validators, but no actual vision transformer or ViT inference weights exist.

### H. Real ML Implementations [HIGH CONFIDENCE]
- **`BrudSmallV2Model` / `BrudSmallV2`:**
  - Parameters: Exactly 528,128.
  - Vocab: 1024. $d_{\text{model}}=128, h=4, L=2, d_{\text{ff}}=256, T=128$.
  - Checkpoints:
    - Phase 59: `artifacts/candidates/phase59/checkpoints/checkpoint_best.pt` (6.08 MB)
    - WS05: `artifacts/candidates/phase60/checkpoints/checkpoint_best.pt` (6.14 MB)
    - E3-A to E3-E: `artifacts/candidates/phase60/ws07/e3/experiments/e3_{a,b,c,d,e}/checkpoint_best.pt` (2.02 MB each)
- **Tokenizer v2:**
  - File: `core_model/tokenization/tokenizer_v2.py`
  - Vocabulary: Exactly 1,024 tokens. Real BPE with Tamil syllable clusters and byte fallback.

---

## 3. Evidence Index

- **Backend Scan:** `backend/` (523 files, 173k lines, Python 3.13).
- **Core Model Scan:** `core_model/` (762 files, 76k lines, PyTorch).
- **Test Scan:** `tests/` (511 files, 172k lines, Pytest).
- **Database Inspection:** `data/database/brud_ai.db` (139 tables, 4.5 GB total data dir).
- **Models Inspection:** `models/` (1.5 GB total, 4 stub GGUF files, 2 real external Qwen GGUF files).
