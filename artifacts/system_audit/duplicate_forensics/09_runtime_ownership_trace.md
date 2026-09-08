# WS08 Duplicate Forensic Audit — 09: Runtime Ownership Trace

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. Public Chat Runtime Ownership Trace

```
User HTTP Request
       ↓
POST /api/chat/message [port 5173]
       ↓
backend/api/routes/public_chat.py
       ↓
PublicChatRoutingService.handle_message()
[backend/services/public_chat_routing_service.py]
       ↓
13-Stage Orchestration Pipeline:
  Stage 1:  Safety Input Filter
  Stage 2:  Language Detection (langdetect)
  Stage 3:  Bilingual Normalization
  Stage 4:  Conversation Memory Retrieval
  Stage 5:  Intent Classification
  Stage 6:  Tool Routing (Calculator / Date / Unit)
  Stage 7:  RAG Retrieval
  Stage 8:  Context Assembly
  Stage 9:  Model Route Selection
  Stage 10: ← INFERENCE GATE (model assignment check)
  Stage 11: External Provider Fallback
  Stage 12: Safety Output Filter
  Stage 13: Response Formatting
       ↓
Stage 10: InferenceRuntimeService._execute_evidence_route()
[backend/services/inference_runtime_service.py]
       ↓
ModelAssignmentService.get_active_assignment()
[backend/services/model_assignment_service.py]
       ↓
core_model/inference_runtime/assignment_policy.py
       ↓
core_model/inference_runtime/model_loader.py
     ↓               ↓
 [GGUF path]    [torch.load path]
     ↓
REAL MODEL FILE (models/qwen2.5-*.gguf OR candidates/*.pt)
```

**Which duplicate class does this path use?**
```
BrudSmallV2Model: NOT USED — the inference path loads via file path, not Python class import
InferenceEngine (core_model/inference/): NOT USED — raises NotImplementedError
```

**Actual active model classes in inference path:**
```
core_model/inference_runtime/generation_engine.py — GenerationEngine (no duplicates)
core_model/inference_runtime/model_loader.py — ModelLoader (no duplicates)
```

---

## 2. Admin Dashboard → Mini Brain Runtime Ownership Trace

```
Admin HTTP Request
       ↓
React Admin Dashboard [port 5174]
       ↓
POST /api/admin/mini-brain/*/sessions [FastAPI]
       ↓
backend/api/routes/mini_brain_*.py
       ↓ (imports its own CreateSessionRequest)
backend/services/mini_brain_*_service.py
       ↓
core_model/mini_brain/{subsystem}/
       ↓
SQLite Session Table (specific to subsystem)
```

**Which duplicate class does this path use?**
```
CreateSessionRequest: Each route uses its own module-specific class — no cross-contamination
AdminReviewRequest: Each service uses its own module's definition
```

---

## 3. Admin Dataset → Training Pipeline Ownership Trace

```
Admin Dataset Upload
       ↓
POST /api/admin/dataset-sample-imports [FastAPI]
backend/api/routes/dataset_sample_import.py
       ↓
AdminAssistantDatasetExpansionService
[backend/services/admin_assistant_dataset_expansion_service.py]
       ↓
DatasetExpansionEngine
[core_model/mini_brain/dataset_expansion/dataset_expansion_engine.py]
       ↓
DatasetExpansionValidator
[core_model/mini_brain/dataset_expansion/dataset_expansion_validator.py]
       ↓
Admin Review Queue (status=PENDING)
       ↓ [HUMAN APPROVAL REQUIRED]
Dataset Sealing (SHA-256)
       ↓ [HUMAN TRAINING AUTHORIZATION REQUIRED]
Training Runner: run_e3_experiments.py (most recent)
       ↓
BrudSmallV2Model (locally defined in runner = E3 canonical version)
       ↓
AdamW + Cosine LR optimizer
       ↓
Candidate Checkpoint (artifacts/candidates/phase60/ws07/e3/outputs/)
       ↓
Evaluation Runner: run_capability_evaluation_ws06.py
[uses its own local BrudSmallV2Model definition — compatible]
```

**Which duplicate class does this path use?**
```
Training: E3 runner's local BrudSmallV2Model (P4 = most current)
Evaluation: WS06 runner's local BrudSmallV2Model (P2 — architecturally identical to P4, different hash due to docstring)
```

**Risk:** If checkpoint from E3 runner is loaded by WS06 evaluator, the PE key compatibility issue applies (see Report 03). However WS06 evaluator uses `strict=False` internally → no runtime failure.

---

## 4. Canonical Class Per Runtime Path Summary

| Runtime Path | Duplicate Class | Which Instance Is Used | Risk |
|---|---|---|---|
| Public Chat → Inference | `BrudSmallV2Model` | ❌ Not used (file-path loading) | None |
| Public Chat → Inference | `InferenceEngine` | ❌ Not used (NotImplementedError) | None |
| Admin → Mini Brain Sessions | `CreateSessionRequest` | Own module's definition | None |
| Admin → Dataset Pipeline | `AdminReviewRequest` | Own module's definition | None |
| Training | `BrudSmallV2Model` | P4 — run_e3_experiments.py | Low |
| Evaluation | `BrudSmallV2Model` | P2 — run_capability_ws06.py | Low (compatible) |
| Tests | `BrudSmallV2Model` | Test-local definition | None |
| Training → Memorization Guard | `GuardAction` | phase56 (most recent) | None |
| research_center pipeline | `ProviderOutput` / `IngestProviderResultsRequest` | research_center.py version | None |
| continuous_learning pipeline | `ProviderOutput` / `IngestProviderResultsRequest` | continuous_learning_center.py version | None |

---

## 5. Overall Ownership Verdict

```
No duplicate class confusion in any active production runtime path.
Each duplicated class is imported exclusively by its own module.
The only theoretical runtime risk is BrudSmallV2Model checkpoint compatibility (PE key)
between WS05 trainer (P1) and WS06/WS07/E3 evaluators (P2/P3/P4).
This is a checkpoint loading concern, not an import or class resolution concern.
```
