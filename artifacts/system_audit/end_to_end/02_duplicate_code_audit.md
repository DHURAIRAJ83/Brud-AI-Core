# Master Brud AI End-to-End Audit — 02: Duplicate Code Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal Software Architect & Codebase Auditor  
**Confidence Rating:** HIGH CONFIDENCE (Verified by AST parsing and SHA-256 hash collision detection)  

---

## 1. Master Duplicate Registry

The codebase inspection identified 53 duplicate class names, multiple parallel directory implementations, and several duplicate model definitions.

### Duplicate Folders & Parallel Implementations

| Duplicate Folder ID | Folder Path A | Folder Path B | Nature of Duplication | Active Path | Inactive / Legacy Path | Risk & Recommendation |
|---|---|---|---|---|---|---|
| **DUP-DIR-01** | `core_model/mini_brain/research_center/` | `core_model/mini_brain/continuous_learning_center/` | Parallel provider consensus engines and memory recording logic | `research_center` | `continuous_learning_center` | Low risk; consolidate into a single research center module in future cleanup. |
| **DUP-DIR-02** | `core_model/mini_brain/llm_runtime/` | `backend/services/inference_runtime_service.py` | Dual inference runtime concepts (Rule wrapper vs PyTorch loader) | `inference_runtime_service.py` | `llm_runtime` (mostly advisory templates) | Medium risk; callers might confuse MB-28 prompt builder with real inference runtime. |
| **DUP-DIR-03** | `models/active/` | `artifacts/candidates/phase60/checkpoints/` | Target model directory vs Candidate storage directory | `artifacts/candidates/` | `models/active/` (empty `.gitkeep`) | Low risk; intentional governance isolation preventing unvetted deployment. |

---

### Duplicate Classes & Services Registry

| Duplicate ID | Class / Symbol | File Location A | File Location B | Similarity | Active Implementation | Unused / Legacy Implementation | Risk & Action |
|---|---|---|---|---|---|---|---|
| **DUP-001** | `BrudSmallV2Model` | `artifacts/candidates/phase60/run_controlled_training_ws05.py` | `artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py` (also in ws06, ws07) | 98% | `run_e3_experiments.py` & `run_controlled_training_ws05.py` | Multiple copies embedded in standalone experiment scripts | Low risk (self-contained runners); recommend factoring into `core_model/architecture/brud_small_v2.py`. |
| **DUP-002** | `FeedbackRepository` | `backend/database/repositories/feedback.py` | `backend/database/repositories/phase2.py` | 90% | `backend/database/repositories/feedback.py` | `phase2.py` (Phase 2 legacy snapshot) | Low risk; callers use `feedback.py`. Consolidate in future refactor. |
| **DUP-003** | `RoutingDecision` | `core_model/release/phase44_runtime_canary.py` | `core_model/capabilities/smart_router.py` | 85% | `phase44_runtime_canary.py` | `smart_router.py` | Low risk; both define routing dataclasses for different phases. |
| **DUP-004** | `RetrievalProfileCreate` | `backend/models/conversation_memory.py` | `backend/models/rag.py` | 95% | Both are active in their respective domains | Domain model duplication | Low risk; distinct Pydantic models for memory vs RAG profiles. |
| **DUP-005** | `CreateSessionRequest` | `backend/models/mini_brain_language_intelligence.py` | 11 other Mini Brain model files (e.g. `mini_brain_evaluation_center.py`) | 95% | Handled per Mini Brain sub-route | Duplicated request schema across 12 files | Medium code bloat; recommend unified session request schema. |
| **DUP-006** | `VoiceAudioDecodeError` | `backend/api/routes/public_voice_runtime.py` | `backend/api/routes/mini_brain_voice_runtime.py` | 100% | `public_voice_runtime.py` | `mini_brain_voice_runtime.py` | Low risk; identical exception defined in two route files. |
| **DUP-007** | `GuardAction` | `core_model/training/phase54_memorization_guard.py` | `core_model/training/phase56_memorization_guard.py` | 95% | `phase56_memorization_guard.py` | `phase54_memorization_guard.py` | Low risk; versioned phase progression. |
| **DUP-008** | `TamilNormalizationError`| `core_model/corpus/phase47_corpus_expander.py` | `core_model/corpus/phase46_corpus_scaler.py` | 100% | Versioned historical modules | Retained for phase audit history | Low risk; do not delete to preserve past phase test integrity. |

---

## 2. Duplicate Checkpoint Artifacts & Configs

- **Exact Duplicate Config JSONs (SHA-256 Match):**
  - Match across Phase 45, 46, 47, 48, 49, 50, 51 checkpoints (`config.json` files identically parameterized).
  - Match between `config.json` and `summary.json` within candidate folders (`e3_a`, `e3_b`, `e3_c`, `e3_d`, `e3_e`) where parameter dictionaries are mirrored.
- **Legacy Tiny Checkpoints:**
  - 1,200+ small adapter `.pt` files (37 KB to 106 KB) under `data/core_models/checkpoints/` generated during Phase 28-30 integration tests.
  - *Recommendation:* Keep preserved for historical audit; do not delete or overwrite.
