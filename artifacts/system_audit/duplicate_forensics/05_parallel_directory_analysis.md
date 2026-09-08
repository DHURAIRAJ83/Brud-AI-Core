# WS08 Duplicate Forensic Audit — 05: Parallel Directory Analysis

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. research_center/ vs continuous_learning_center/

### Directory Paths
```
backend/api/routes/mini_brain_research_center.py
backend/api/routes/mini_brain_continuous_learning_center.py

backend/models/mini_brain_research_center.py
backend/models/mini_brain_continuous_learning_center.py

backend/services/mini_brain_research_center_service.py
backend/services/mini_brain_continuous_learning_center_service.py

backend/database/repositories/mini_brain_research_center.py (if exists)
backend/database/repositories/mini_brain_continuous_learning_center.py (if exists)

core_model/mini_brain/research_center/ (if exists)
core_model/mini_brain/continuous_learning_center/
```

### Purpose of Each

| Subsystem | Purpose | Key Responsibility |
|---|---|---|
| **research_center** (MB-10) | Knowledge Gap Research | Identifies what Brud AI doesn't know; proposes RAG/dataset research topics; outputs a knowledge gap report |
| **continuous_learning_center** (MB-11) | Learning Plan Execution | Converts research findings into structured learning queue, draft outlines, and dataset evolution proposals |

### Do They Supersede Each Other?
**No.** They are **sequential stages in the same pipeline**, not duplicates:
```
research_center (MB-10)
       ↓
   Gap Report
       ↓
continuous_learning_center (MB-11)
       ↓
   Learning Queue → Dataset Evolution → Admin Review
```

The pipeline_coordinator explicitly chains them:
- `link_research_center_stage()` → executes MB-10
- Passes result to MB-11 continuous_learning_center

### API Exposure
- `POST /api/mini-brain/research-center/sessions` — active
- `POST /api/mini-brain/continuous-learning-center/sessions` — active

### Database Usage
- Both have separate session tables in SQLite (distinct schemas)
- No shared tables

### Verdict
```
DUPLICATE? NO
STATUS: COMPLEMENTARY PIPELINE STAGES
SAFE TO REMOVE: NO — both required for E3/E4 learning loop
RECOMMENDATION: KEEP + DOCUMENT dependency order
```

---

## 2. core_model/inference/ vs core_model/inference_runtime/

### Directory Contents

| Directory | Files | Status |
|---|---|---|
| `core_model/inference/` | `__init__.py` only (354 bytes) | **STUB / DEAD** |
| `core_model/inference_runtime/` | 12 active Python modules (~35KB) | **ACTIVE** |

### core_model/inference/__init__.py Content
```python
"""Model inference interface."""

class InferenceEngine:
    """Will load a registered model and generate validated multilingual responses."""

    def generate(self, prompt: str) -> str:
        """Generate model output in a future phase; no fake output is returned."""
        raise NotImplementedError("Model inference is not available in Phase 1")
```

This is a **Phase 1 placeholder** (docstring confirms: "Phase 1") created before the actual inference runtime was built.

### Who Imports core_model/inference?
```
core_model/__init__.py:6:from core_model.inference import InferenceEngine
```

Only `core_model/__init__.py` imports `InferenceEngine`. It is **not called anywhere in production**, but the import at package level means:
- `InferenceEngine` is accessible as `core_model.InferenceEngine`
- Used in zero runtime paths — tested in old Phase 34–40 tests via `from core_model.inference import InferenceEngine`

### core_model/inference_runtime/ Active Modules
```
__init__.py          — public API exports
assignment_policy.py — model assignment decision logic
canary.py            — traffic splitting + canary rollout
comparison.py        — A/B comparison
context_builder.py   — prompt context assembly
fallback.py          — graceful degradation
generation_config.py — decoding hyperparameters
generation_engine.py — actual token generation
model_loader.py      — checkpoint loading + safety
resource_guard.py    — CPU/RAM guards
runtime_config.py    — runtime settings schema
runtime_health.py    — health check probe
```

### Verdict
```
core_model/inference/         — DEAD STUB (Phase 1 placeholder, never evolved)
core_model/inference_runtime/ — ACTIVE (sole canonical inference subsystem)

DUPLICATE? TECHNICALLY NO (different responsibilities, different scope)
RELATIONSHIP: inference/ was SUPERSEDED by inference_runtime/
SAFE TO ARCHIVE: YES (inference/__init__.py is safe to archive AFTER E6)
ACTION NOW: NONE — read-only audit only
RISK: LOW — inference/ is imported at package level but never executed in runtime
E4/E5 IMPACT: NONE — new runners will use inference_runtime/ directly
```

---

## 3. Phase 45–51 Checkpoint config.json Identical Files

### Evidence
From audit scan: `data/core_models/checkpoints/adapter-it-at-*` — 6,017 directories, 3.8GB

Sample config.json from `adapter-it-at-envelope_v0.1_initialization_03e79c7f/config.json`:
```json
{
  "attention_dropout":0.0,
  "bos_token_id":2,
  "context_length":32,
  "embedding_dropout":0.0,
  "eos_token_id":3,
  "hidden_size":16,
  "ignore_index":-100,
  "initializer_range":0.02,
  "intermediate_size":32,
  "num_attention_heads":2,
  "num_hidden_layers":2,
  "num_key_value_heads":2,
  "pad_token_id":0,
  "residual_dropout":0.0,
  "rms_norm_epsilon":1e-06,
  "rope_theta":10000.0,
  "tie_word_embeddings":true,
  "unk_token_id":1,
  "use_bias":false,
  "vocabulary_size":400
}
```

This describes **a completely different architecture** from BrudSmallV2:
- `hidden_size=16` vs BrudSmallV2's `d_model=128`
- `vocabulary_size=400` vs BrudSmallV2's `1024`
- `context_length=32` vs BrudSmallV2's `128`
- Uses RoPE (`rope_theta=10000.0`) vs BrudSmallV2's sinusoidal PE
- Has `num_key_value_heads=2` → GQA-style architecture

These are **Phase 1–2 experimental adapter initialization checkpoints** from before the BrudSmallV2 architecture was defined. The 6,017 directories all share this same config because they were generated by a grid-search initialization experiment.

### Active Runtime Reference
Only `backend/core/config.py:359` references `data/core_models/checkpoints` as a default directory path — it does NOT load individual adapter-it-at checkpoints. **No production code loads these files.**

### Classification
```
CLASSIFICATION: HISTORICAL — Phase 1-2 architecture exploration artifacts
REFERENCED BY: Zero production code (only config default path)
REQUIRED FOR REPRODUCIBILITY: YES — these represent historical training runs
SAFE TO ARCHIVE: YES (after E6, zip and move to cold storage)
SAFE TO DELETE NOW: NO — may be needed to audit architecture decision history
```

---

## 4. Other Parallel Directories Investigated

### core_model/training/phase4X_memorization_guard.py files

| File | Phase | GuardAction Hash |
|---|---|---|
| `phase53_memorization_guard.py` | 53 | `0c3bfd021f84` — old version |
| `phase54_memorization_guard.py` | 54 | `3fa6cc41e238` — current |
| `phase56_memorization_guard.py` | 56 | `3fa6cc41e238` — same as 54 |

Phase56 is a copy of phase54 guard with additional `RecordExposureTelemetry` class extended.  
Classification: **F — VERSIONED IMPLEMENTATION** (phase progression artifacts)

### core_model/evaluation/phase50 vs phase51 evaluator

Both define `OpenDomainStatus` and `CausalityVerdict` with different implementations — representing two phases of the capability evaluation framework. Phase51 supersedes Phase50 but Phase50 is retained for historical regression testing.  
Classification: **F — VERSIONED IMPLEMENTATION**

### Verdict Summary

| Parallel Pair | Duplicate? | Status | Recommendation |
|---|---|---|---|
| `research_center` / `continuous_learning_center` | NO | Complementary pipeline stages | KEEP BOTH |
| `core_model/inference` / `core_model/inference_runtime` | Partial | inference/ is dead stub | ARCHIVE inference/ AFTER E6 |
| `phase53/54/56_memorization_guard` | Partial | F-versioned | KEEP for audit, archive after E6 |
| `phase50/51_evaluator` | Partial | F-versioned | KEEP — phase51 is canonical |
| `adapter-it-at-*` checkpoints × 6017 | NO | Historical training artifacts | ARCHIVE to cold storage after E6 |
