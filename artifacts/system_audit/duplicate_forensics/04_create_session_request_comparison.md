# WS08 Duplicate Forensic Audit — 04: CreateSessionRequest × 12 Comparison

**Audit Date:** 2026-09-01  
**Finding:** 12 occurrences of `class CreateSessionRequest(DomainModel)` across 12 Mini Brain model files

---

## 1. All 12 Occurrences

| # | File | Line | Hash | Fields |
|---|---|---|---|---|
| 1 | `mini_brain_dataset_evolution.py` | 8 | `43c966445410` | `dataset_source_public_id` |
| 2 | `mini_brain_evaluation_center.py` | 28 | `f58526dbf7f7` | `topic` |
| 3 | `mini_brain_external_ai_gateway.py` | 8 | `f072d49fd16f` | `topic`, `purpose`, `dataset_session_public_ids`, `rag_session_public_id` |
| 4 | `mini_brain_language_intelligence.py` | 22 | `43c966445410` | `dataset_source_public_id` |
| 5 | `mini_brain_multimodal_dataset_generator.py` | 8 | `9bd9b17f8d0f` | `document_source_public_id`, `dataset_source_public_id`, `language_session_public_id`, `vision_session_public_id`, `vision_model_session_public_id` |
| 6 | `mini_brain_pipeline_coordinator.py` | 8 | `c518aa62f155` | `topic` |
| 7 | `mini_brain_release_governance.py` | 28 | `f58526dbf7f7` | `topic` |
| 8 | `mini_brain_research_center.py` | 8 | `c518aa62f155` | `topic` |
| 9 | `mini_brain_training_pipeline.py` | 8 | `f58526dbf7f7` | `topic` |
| 10 | `mini_brain_vision_intelligence.py` | 11 | `fabdf17a9390` | `document_source_public_id`, `dataset_source_public_id` |
| 11 | `mini_brain_vision_model.py` | 11 | `01f4a7ec2d91` | `vision_session_public_id`, `language_session_public_id`, `provider_key` |
| 12 | `mini_brain_vision_rag.py` | 10 | `67bc340b334f` | `multimodal_dataset_session_public_id`, `query` |

---

## 2. Implementation Hash Groupings

| Hash Group | Files | Field Set |
|---|---|---|
| `43c966445410` | dataset_evolution, language_intelligence | `dataset_source_public_id` — 1 field |
| `f58526dbf7f7` | evaluation_center, release_governance, training_pipeline | `topic` — 1 field |
| `c518aa62f155` | pipeline_coordinator, research_center | `topic` — 1 field (but different context) |
| `f072d49fd16f` | external_ai_gateway | `topic`, `purpose`, `dataset_session_public_ids`, `rag_session_public_id` — 4 fields |
| `9bd9b17f8d0f` | multimodal_dataset_generator | 5 cross-modal fields — most complex |
| `fabdf17a9390` | vision_intelligence | 2 document/dataset fields |
| `01f4a7ec2d91` | vision_model | 3 vision-specific fields |
| `67bc340b334f` | vision_rag | `multimodal_dataset_session_public_id`, `query` — 2 fields |

---

## 3. Structural Field Comparison Matrix

| Field | evo | eval | ext-gw | lang | multi | coord | rel-gov | res | train | vis-int | vis-mod | vis-rag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `topic` | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `purpose` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `dataset_source_public_id` | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `dataset_session_public_ids` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `rag_session_public_id` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `document_source_public_id` | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `language_session_public_id` | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `vision_session_public_id` | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `vision_model_session_public_id` | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `provider_key` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `multimodal_dataset_session_public_id` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `query` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

**CONCLUSION: These are NOT the same class. Each carries domain-specific foreign key fields for its respective Mini Brain subsystem.**

---

## 4. Why Each Has Its Own Definition

The Mini Brain is a **module-per-subsystem architecture**. Each `backend/models/mini_brain_*.py` file provides the Pydantic request/response contracts for its specific API domain:
- `mini_brain_research_center` → Research sessions keyed by `topic`
- `mini_brain_dataset_evolution` → Dataset sessions keyed by `dataset_source_public_id`
- `mini_brain_vision_rag` → Vision-RAG sessions keyed by `multimodal_dataset_session_public_id` + `query`

The **name** `CreateSessionRequest` is shared because every Mini Brain subsystem exposes a "create session" concept — but the **schema** is domain-specific.

---

## 5. Are They True API Contract Duplicates?

**No.** Each routes to a different FastAPI endpoint under a different prefix:
```
POST /api/mini-brain/research-center/sessions          → mini_brain_research_center.CreateSessionRequest
POST /api/mini-brain/dataset-evolution/sessions        → mini_brain_dataset_evolution.CreateSessionRequest
POST /api/mini-brain/vision-rag/sessions               → mini_brain_vision_rag.CreateSessionRequest
...
```

They are imported exclusively by their own module's route file. There are no cross-module imports of these classes.

---

## 6. Recommendation

| Option | Assessment |
|---|---|
| **Centralize as single class** | ❌ NOT POSSIBLE — schemas are incompatible; would require Union types or field explosion |
| **Aliases to a base class** | ❌ DISCOURAGED — base class would be near-empty (only session-level metadata, no domain fields) |
| **Shared schema in domain.py** | ❌ IMPRACTICAL — domain.py would need 12 CreateSessionRequest variants |
| **Keep separately (status quo)** | ✅ CORRECT — each module owns its contract; follows FastAPI modular design pattern |
| **Convert to typed namespace aliases** | 🟡 POSSIBLE IMPROVEMENT — `mini_brain_research_center.CreateSessionRequest` aliased to `ResearchCenterCreateSessionRequest` to prevent accidental cross-import |

### Audit Recommendation: **KEEP SEPARATELY + DOCUMENT**
> The 12 separate definitions are an **intentional specialization** (classification B). The shared class name is purely nominal. No centralization is warranted. A namespace alias rename is a P3 cosmetic improvement for future consideration.

---

## 7. Security Assessment

- No cross-module import found → no accidental field confusion between modules
- Each endpoint validates only its own `CreateSessionRequest` schema
- No security bypass risk from this duplication
- **SEVERITY: INFO**

---

## 8. Admin Assistant Mini Brain Impact

The Admin Assistant reads session data through service methods, not by directly constructing CreateSessionRequest objects. No impact on Admin Assistant behavior. The AI Mini Brain governance system correctly isolates each session domain.
