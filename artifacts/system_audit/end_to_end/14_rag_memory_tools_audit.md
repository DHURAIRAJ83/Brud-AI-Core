# Master Brud AI End-to-End Audit — 14: RAG, Memory, Tools & Orchestration Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect & Orchestration Engineer  
**Confidence Rating:** HIGH CONFIDENCE (Verified by end-to-end tracing of `backend/services/public_chat_routing_service.py`)  

---

## 1. Orchestration Pipeline: Connected vs Isolated Reality

The audit examined the 13-stage orchestration pipeline required for enterprise conversational AI:

| Pipeline Stage | Module Location | Connected into Public Chat? | Operational Reality |
|---|---|---|---|
| **1. Input Safety Filtering** | `backend/services/public_safety_service.py` | ✅ **YES** | Intercepts harmful inputs, jailbreak attempts, and profanity; returns refusal text. |
| **2. Language Detection** | `core_model/rag/language_routing.py` | ✅ **YES** | Accurately identifies `ta`, `en`, `tgl`, and `mixed` via Unicode script-point density. |
| **3. Intent & Route Classification**| `backend/services/classification_service.py`| ✅ **YES** | Resolves intent and execution route (`refuse`, `tool`, `clarify`, `approved_rag`, `memory`, `core_model`). |
| **4. Ambiguity Resolution** | `core_model/capabilities/supplemental_ambiguity.py` | ✅ **YES** | Matches unclear pronouns and asks clarifying questions before routing. |
| **5. Tool Selection & Execution**| `backend/services/deterministic_tool_registry.py` | ✅ **YES** | Math calculator, unit conversion, and date arithmetic execute deterministically. |
| **6. RAG Retrieval** | `backend/services/rag_service.py` | ✅ **YES** (When scope assigned) | Retrieves chunks, computes n-gram overlap, builds citation headers. |
| **7. Memory Retrieval** | `backend/services/memory_service.py` | ✅ **YES** (Consent-gated) | Loads participant declarative/episodic facts if `memory_consent == True`. |
| **8. Model Routing & Assignment** | `backend/services/public_model_assignment_resolver.py` | ✅ **YES** | Queries `public_chat` scope; safely returns `None` when zero models assigned. |
| **9. External Provider Fallback** | `backend/services/mini_brain_external_ai_gateway_service.py` | 🔴 **NOT CONNECTED** | Gateway exists for evaluation sessions, but is NOT wired as a live public chat fallback. |
| **10. Context Assembly** | `core_model/inference_runtime/context_builder.py` | ✅ **YES** | Binds system prompt, retrieved RAG chunks, memory facts, and recent conversation turns. |
| **11. Local Inference Execution** | `backend/services/inference_runtime_service.py` | ✅ **YES** (Conditional) | Dispatched if a model assignment is active; currently blocked in production. |
| **12. Output Safety Filtering** | `backend/services/public_safety_service.py` | ✅ **YES** | Sanitizes model completions, scrubs secrets, and intercepts harmful output tokens. |
| **13. Final Bounded Response** | `backend/services/public_chat_routing_service.py` | ✅ **YES** | Returns structured JSON with text, route used, citations, and latency metrics. |

---

## 2. Definitive Architectural Finding

The orchestration pipeline is **genuinely connected and functional in source code**:
- Deterministic tools, safety filters, language classification, and ambiguity handlers execute on live queries.
- For RAG, Memory, and Model generation, the architecture is **fully assembled**, but gracefully degrades to `"model_assignment_unavailable"` because the production assignment table is intentionally empty (`status='active'` models = 0).
- This design proves that Brud AI is **fail-safe**: an unvetted small model cannot be accidentally exposed to users.
