# BRUD AI — MINI BRAIN AUDIT (WS03)
**Audit Date:** 2026-09-07

---

## OVERVIEW

The Brud Mini Brain (MB) system is organized across:
- `core_model/mini_brain/` — 34 sub-directories of domain logic
- `backend/services/mini_brain_*` — 39 service files
- `backend/api/routes/mini_brain_*` — 36 route files
- `backend/database/repositories/mini_brain_*` — 20+ repository files
- `backend/models/mini_brain_*` — 30 model files

The core intelligence lives in:
- `core_model/mini_brain/intelligence/` — 18 files

---

## PHASE 17 INTELLIGENCE MODULES AUDIT

### core_model/mini_brain/intelligence/ (18 files)

| Module | File | Size | Phase | Callers | Status |
|--------|------|------|-------|---------|--------|
| Context Intelligence | `context_intelligence.py` | 23 KB | 17.2 | `memory_service.py` | ACTIVE |
| Memory Intelligence | `memory_intelligence.py` | 16 KB | 17.3 | `memory_service.py` | ACTIVE |
| Duplicate Detector | `duplicate_detector.py` | 14 KB | 17.4 | `memory_service.py` | ACTIVE |
| Conflict Detector | `conflict_detector.py` | 21 KB | 17.5 | `memory_service.py` | ACTIVE |
| Memory Consolidator | `memory_consolidator.py` | 16 KB | 17.6 | `memory_service.py` | ACTIVE |
| Memory Lifecycle | `memory_lifecycle.py` | 12 KB | 17.7 | `memory_service.py` | ACTIVE |
| Memory Recall | `memory_recall.py` | 20 KB | 17.8 | `memory_service.py` | ACTIVE |
| Memory Reasoner | `memory_reasoner.py` | 25 KB | 17.9 | `memory_service.py` | ACTIVE |
| Confidence | `confidence.py` | 2.3 KB | 17.x | - | ACTIVE |
| Context Resolver | `context_resolver.py` | 2.2 KB | 17.x | - | ACTIVE |
| Feature Resolver | `feature_resolver.py` | 1.6 KB | 17.x | - | ACTIVE |
| Intent Engine | `intent_engine.py` | 3.7 KB | 17.x | - | ACTIVE |
| Knowledge Planner | `knowledge_planner.py` | 2.9 KB | 17.x | - | ACTIVE |
| Question Analyzer | `question_analyzer.py` | 2.7 KB | 17.x | - | ACTIVE |
| Response Plan | `response_plan.py` | 2.1 KB | 17.x | - | ACTIVE |
| Rule Engine | `rule_engine.py` | 2.3 KB | 17.x | - | ACTIVE |
| Workflow Graph | `workflow_graph.py` | 2 KB | 17.x | - | ACTIVE |

---

## PHASE 17.x VERIFICATION

### Phase 17.2 — Context Intelligence
- **File:** `core_model/mini_brain/intelligence/context_intelligence.py` (23 KB)
- **Callers:** `memory_service.py` (verified by import grep)
- **Runtime Connected:** YES — MemoryService imports ContextIntelligence modules
- **Status:** VERIFIED ACTIVE

### Phase 17.3 — Memory Intelligence
- **File:** `core_model/mini_brain/intelligence/memory_intelligence.py` (16 KB)
- **Callers:** `memory_service.py` line 68-73
- **Runtime Connected:** YES
- **Status:** VERIFIED ACTIVE

### Phase 17.4 — Duplicate Detection
- **File:** `core_model/mini_brain/intelligence/duplicate_detector.py` (14 KB)
- **Callers:** `memory_service.py` lines 59-62
- **Runtime Connected:** YES
- **Status:** VERIFIED ACTIVE

### Phase 17.5 — Conflict Detection
- **File:** `core_model/mini_brain/intelligence/conflict_detector.py` (21 KB)
- **Callers:** `memory_service.py` lines 50-58
- **Runtime Connected:** YES
- **Status:** VERIFIED ACTIVE

### Phase 17.6 — Memory Consolidation
- **File:** `core_model/mini_brain/intelligence/memory_consolidator.py` (16 KB)
- **Callers:** `memory_service.py` lines 63-67
- **Runtime Connected:** YES
- **Status:** VERIFIED ACTIVE

### Phase 17.7 — Memory Lifecycle
- **File:** `core_model/mini_brain/intelligence/memory_lifecycle.py` (12 KB)
- **Callers:** `memory_service.py` lines 74-77
- **Runtime Connected:** YES
- **Status:** VERIFIED ACTIVE

### Phase 17.8 — Memory Recall
- **File:** `core_model/mini_brain/intelligence/memory_recall.py` (20 KB)
- **Callers:** `memory_service.py` lines 78-82
- **Runtime Connected:** YES
- **Status:** VERIFIED ACTIVE

### Phase 17.9 — Memory Reasoning
- **File:** `core_model/mini_brain/intelligence/memory_reasoner.py` (25 KB)
- **Callers:** `memory_service.py` lines 83-89
- **Runtime Connected:** YES
- **Status:** VERIFIED ACTIVE

---

## MINI BRAIN SUB-SYSTEMS

| Sub-module | Core Model Dir | Service File | Route File | Status |
|-----------|----------------|--------------|------------|--------|
| Intelligence | intelligence/ | mini_brain_intelligence_service.py | mini_brain_intelligence.py | ACTIVE |
| LLM Runtime | llm_runtime/ | mini_brain_llm_runtime_service.py | mini_brain_llm_runtime.py | ACTIVE |
| Knowledge | knowledge/ | mini_brain_knowledge_service.py | mini_brain_knowledge.py | ACTIVE |
| Capability | capability/ | mini_brain_capability_service.py | mini_brain_capability.py | ACTIVE |
| Quality | quality/ | mini_brain_quality_service.py | mini_brain_quality.py | ACTIVE |
| Research Center | research_center/ | mini_brain_research_center_service.py | mini_brain_research_center.py | ACTIVE |
| Training Engine | training_engine/ | mini_brain_training_engine_service.py | mini_brain_training_engine.py | ACTIVE |
| Training Pipeline | training_pipeline/ | mini_brain_training_pipeline_service.py | mini_brain_training_pipeline.py | ACTIVE |
| Evaluation Center | evaluation_center/ | mini_brain_evaluation_center_service.py | mini_brain_evaluation_center.py | ACTIVE |
| Plugin Governance | plugin_governance/ | mini_brain_plugin_governance_service.py | mini_brain_plugin_governance.py | ACTIVE |
| Plugin Runtime | plugin_runtime/ | mini_brain_plugin_runtime_service.py | mini_brain_plugin_runtime.py | ACTIVE |
| Provider Settings | provider_settings/ | mini_brain_provider_settings_service.py | mini_brain_provider_settings.py | ACTIVE |
| Voice Runtime | voice_runtime/ | mini_brain_voice_runtime_service.py | mini_brain_voice_runtime.py | ACTIVE |
| Vision Intelligence | vision_intelligence/ | mini_brain_vision_intelligence_service.py | mini_brain_vision_intelligence.py | ACTIVE |
| Vision Model | vision_model_integration/ | mini_brain_vision_model_service.py | mini_brain_vision_model.py | ACTIVE |
| Vision RAG | vision_rag/ | mini_brain_vision_rag_service.py | mini_brain_vision_rag.py | ACTIVE |
| Language Intelligence | language_intelligence/ | mini_brain_language_intelligence_service.py | mini_brain_language_intelligence.py | ACTIVE |
| Public Chat Runtime | public_chat_runtime/ | mini_brain_public_chat_runtime_service.py | mini_brain_public_chat_runtime.py | ACTIVE |
| Release Pipeline | release_pipeline/ | mini_brain_release_pipeline_service.py | mini_brain_release_pipeline.py | ACTIVE |
| Release Governance | release_governance/ | mini_brain_release_governance_service.py | mini_brain_release_governance.py | ACTIVE |
| Continuous Learning | continuous_learning/ | mini_brain_continuous_learning_service.py | mini_brain_continuous_learning.py | ACTIVE |
| Learning Supervisor | learning_supervisor/ | mini_brain_learning_supervisor_service.py | mini_brain_learning_supervisor.py | ACTIVE |
| Dataset Evolution | dataset_evolution/ | mini_brain_dataset_evolution_service.py | mini_brain_dataset_evolution.py | ACTIVE |
| Dataset Intelligence | dataset_intelligence/ | mini_brain_dataset_intelligence_service.py | mini_brain_dataset_intelligence.py | ACTIVE |
| Pipeline Coordinator | pipeline_coordinator/ | mini_brain_pipeline_coordinator_service.py | mini_brain_pipeline_coordinator.py | ACTIVE |
| External AI Gateway | external_ai_gateway/ | mini_brain_external_ai_gateway_service.py | mini_brain_external_ai_gateway.py | ACTIVE |
| Multimodal Generator | multimodal_dataset_generator/ | mini_brain_multimodal_dataset_generator_service.py | mini_brain_multimodal_dataset_generator.py | ACTIVE |
| Runtime Manager | runtime_manager/ | mini_brain_runtime_manager_service.py | mini_brain_runtime_manager.py | ACTIVE |
| Local Setup | local_setup/ | (via admin_assistant_tools) | mini_brain_local_setup.py | ACTIVE |

---

## FOUNDATION SERVICE (MiniBrainService)

`backend/services/mini_brain_service.py` is the base service:
- Composes `MiniBrainRepository` + `MiniBrainRuntime`
- Placeholder methods: `placeholder_inference()`, `placeholder_knowledge()`, `placeholder_memory()`
- These are NOT actual inference — they return `"not_implemented_in_mb01"`
- **Status:** Foundation is ACTIVE but inference is still PLACEHOLDER

---

## CRITICAL FINDING: MINI BRAIN HAS PLACEHOLDER INFERENCE

The `MiniBrainService.placeholder_inference()` method explicitly returns:
```python
"reason": "not_implemented_in_mb01"
```

This means the base MiniBrainService does NOT have real inference.
Real inference happens via:
1. `InferenceRuntimeService` (Phase 15 — Brud core model)
2. `MiniBrainLlmRuntimeService` (MB-28 — adapter-based external/local LLM)

---

## ROUTE LOADING STATUS

Mini Brain routes are classified as DEFERRED:
```python
RoutePlugin("mini_brain", False, False, ...)  # enabled_by_default=False
```
They load only when `BRUD_DEFER_ADMIN_TOOL_ROUTES` is NOT set (dev mode) or in admin mode.

---

## FINDINGS SUMMARY

| Phase | Status | Evidence |
|-------|--------|---------|
| 17.2 Context Intelligence | VERIFIED ACTIVE | Imported by MemoryService |
| 17.3 Memory Intelligence | VERIFIED ACTIVE | Imported by MemoryService |
| 17.4 Duplicate Detection | VERIFIED ACTIVE | Imported by MemoryService |
| 17.5 Conflict Detection | VERIFIED ACTIVE | Imported by MemoryService |
| 17.6 Memory Consolidation | VERIFIED ACTIVE | Imported by MemoryService |
| 17.7 Memory Lifecycle | VERIFIED ACTIVE | Imported by MemoryService |
| 17.8 Memory Recall | VERIFIED ACTIVE | Imported by MemoryService |
| 17.9 Memory Reasoning | VERIFIED ACTIVE | Imported by MemoryService |

---
*WS03 Complete*
