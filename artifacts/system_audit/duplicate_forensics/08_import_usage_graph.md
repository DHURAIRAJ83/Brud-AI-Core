# WS08 Duplicate Forensic Audit — 08: Import / Usage Graph Analysis

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. Methodology

All import analysis was performed by:
1. AST-level `from X import Y` and `import X` scanning
2. String-based registry and factory inspection
3. Dynamic import pattern detection (`importlib`, `__import__`)
4. Dependency injection inspection
5. FastAPI router prefix mapping

---

## 2. BrudSmallV2Model Import Graph

```
ZERO cross-file imports of BrudSmallV2Model
```

Each runner defines its own local copy. There is NO shared module. The complete import map:

```
run_controlled_training_ws05.py     → BrudSmallV2Model (defined locally, line 47)
run_capability_evaluation_ws06.py   → BrudSmallV2Model (defined locally, line 46)
run_ws07_stage_a_diagnostics.py     → BrudSmallV2Model (defined locally, line 49)
run_e3_experiments.py               → BrudSmallV2Model (defined locally, line 75)

test_phase60_ws04_*.py              → BrudSmallV2Model (defined locally, line 62)
test_phase60_ws05_*.py              → BrudSmallV2Model (defined locally, line 63)
test_phase60_ws06_*.py              → BrudSmallV2Model (defined locally, line 63)
test_phase60_ws07_*.py              → BrudSmallV2Model (defined locally, line 70)
test_phase59_ws05_*.py              → BrudSmallV2Model (defined locally, line 70)

backend/services/inference_runtime_service.py → NO BrudSmallV2Model import
core_model/inference_runtime/model_loader.py  → NO BrudSmallV2Model import
```

**Finding:** `BrudSmallV2Model` is **completely absent from the production inference path**. The `inference_runtime_service.py` and `inference_runtime/model_loader.py` load models via file path (GGUF loader or `torch.load`), not by importing the Python class.

---

## 3. CreateSessionRequest Import Graph

| File | Imported By |
|---|---|
| `mini_brain_dataset_evolution.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_dataset_evolution.py` |
| `mini_brain_evaluation_center.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_evaluation_center.py` |
| `mini_brain_external_ai_gateway.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_external_ai_gateway.py` |
| `mini_brain_language_intelligence.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_language_intelligence.py` |
| `mini_brain_multimodal_dataset_generator.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_multimodal_dataset_generator.py` |
| `mini_brain_pipeline_coordinator.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_pipeline_coordinator.py` |
| `mini_brain_release_governance.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_release_governance.py` |
| `mini_brain_research_center.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_research_center.py` |
| `mini_brain_training_pipeline.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_training_pipeline.py` |
| `mini_brain_vision_intelligence.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_vision_intelligence.py` |
| `mini_brain_vision_model.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_vision_model.py` |
| `mini_brain_vision_rag.py::CreateSessionRequest` | ONLY `backend/api/routes/mini_brain_vision_rag.py` |

**Finding:** Every `CreateSessionRequest` is perfectly isolated — each only imported by its own domain route file. No cross-module confusion is possible.

---

## 4. AdminReviewRequest Import Graph

```
IMPL_HASH 446c38f42e00f781 (11 files — same implementation):
  → mini_brain_continuous_learning_center_service.py imports from mini_brain_continuous_learning_center.py
  → mini_brain_language_intelligence_service.py imports from mini_brain_language_intelligence.py
  → mini_brain_evaluation_center_service.py imports from mini_brain_evaluation_center.py
  → mini_brain_training_pipeline_service.py imports from mini_brain_training_pipeline.py
  → mini_brain_external_ai_gateway_service.py imports from mini_brain_external_ai_gateway.py
  → mini_brain_dataset_evolution_service.py imports from mini_brain_dataset_evolution.py
  → mini_brain_multimodal_dataset_generator_service.py imports from mini_brain_multimodal_dataset_generator.py
  → mini_brain_vision_rag_service.py imports from mini_brain_vision_rag.py
  → mini_brain_vision_intelligence_service.py imports from mini_brain_vision_intelligence.py
  → mini_brain_release_governance_service.py imports from mini_brain_release_governance.py
  → mini_brain_vision_model_service.py imports from mini_brain_vision_model.py

IMPL_HASH c59e92d40d9b2d1b (3 files — different implementation):
  → mini_brain_release_pipeline_service.py imports from mini_brain_release_pipeline.py
  → mini_brain_continuous_learning_service.py imports from mini_brain_continuous_learning.py
  → mini_brain_learning_supervisor_service.py imports from mini_brain_learning_supervisor.py
```

The 11-file group has identical `AdminReviewRequest` schemas — these could be centralized to `backend/models/shared.py`. The 3-file group has a slightly different schema (different field for release pipeline).

---

## 5. HardwareProbeResponse / IngestProviderResultsRequest / ProviderOutput / RagAdminReviewRequest

These 4 classes are **identical implementations** (same impl_hash) across two sibling files each:

| Class | File 1 | File 2 | Impact |
|---|---|---|---|
| `HardwareProbeResponse` | `local_setup.py` | `mini_brain_runtime_manager.py` | Both imported by separate routes — no confusion |
| `IngestProviderResultsRequest` | `continuous_learning_center.py` | `research_center.py` | Both imported by separate routes — no confusion |
| `ProviderOutput` | `continuous_learning_center.py` | `research_center.py` | Both imported by separate routes — no confusion |
| `RagAdminReviewRequest` | `mini_brain_dataset_evolution.py` | `mini_brain_research_center.py` | Both imported by separate routes — no confusion |

All 4 are **true name+implementation duplicates** — same code, different modules. Safe for future consolidation but no runtime risk.

---

## 6. FeedbackRepository Import Graph

| Version | File | Imported By | Status |
|---|---|---|---|
| Legacy | `backend/database/repositories/phase2.py` | None in production | **DEAD** |
| Active | `backend/database/repositories/feedback.py` | Multiple backend services | **ACTIVE** |

`phase2.py` is a phase snapshot file. `FeedbackRepository` in it is a **legacy copy** that was superseded by `feedback.py`. No service imports from `phase2.py`.

---

## 7. Registry / Factory / Dynamic Loading Analysis

| Mechanism | File | Uses Duplicate Classes? |
|---|---|---|
| Provider Registry | `core_model/mini_brain/provider_settings/provider_registry.py` | No — uses ProviderKey enum |
| Model Loader | `core_model/inference_runtime/model_loader.py` | No — uses file path loading |
| Admin Assistant Tool Registry | `core_model/mini_brain/admin_assistant/*.py` | No — uses function registration |
| Dependency Injection (FastAPI) | Via `Depends()` | No — each service injected by its own module |
| String-based class loading | ❌ None found | N/A |

**No registry or factory pattern uses duplicate class names.** Dynamic loading is not used in this codebase.

---

## 8. Summary

```
Import isolation: EXCELLENT — all duplicates are imported exclusively within their own module
Cross-import confusion: ZERO — no cross-module imports of duplicate classes found
Registry conflict: ZERO — no registry or factory can accidentally load a wrong implementation
Dynamic import risk: ZERO — no string-based class loading detected
Production model path: BrudSmallV2Model ABSENT from production inference (safe)
```
