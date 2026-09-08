# WS08 Duplicate Forensic Audit — 13: Canonical Architecture

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. CANONICAL MODEL IMPLEMENTATION

```
CANONICAL: artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py — BrudSmallV2Model (local, line 75)
HASH: 6aecf087c213d4506129
REASON:
  - Chronologically most recent (WS07 E3 — highest workstream number)
  - Has persistent=False on PE buffer (correct checkpoint hygiene)
  - Has full controlled generate() with θ=1.25 + no-repeat 3-gram
  - Has docstring confirming role
  - Used for E3-A through E3-E training runs (most current and validated)
EVIDENCE: run_e3_experiments.py verified as the runner for Phase 60 WS07 Stage B
NOTE: No shared Python module exists for BrudSmallV2Model. Each runner is self-contained.
```

> **IMPORTANT FINDING:** There is no canonical *module* — only a canonical *runner script*. Creating a shared `core_model/architecture/brud_small_v2.py` module is the P1 pre-E4/E5 architectural cleanup action.

---

## 2. CANONICAL INFERENCE IMPLEMENTATION

```
CANONICAL: core_model/inference_runtime/ (entire package)
  Primary class: core_model/inference_runtime/generation_engine.py — GenerationEngine
  Config: core_model/inference_runtime/generation_config.py — GenerationConfig
  Loader: core_model/inference_runtime/model_loader.py — ModelLoader
REASON:
  - 12 active modules vs. core_model/inference/__init__.py (1 stub)
  - Actively imported by backend/services/inference_runtime_service.py
  - Contains canary, assignment_policy, fallback — all production-ready
  - inference_runtime/ was built to supersede inference/
EVIDENCE: backend/services/inference_runtime_service.py imports from core_model.inference_runtime
DEAD: core_model/inference/__init__.py — Phase 1 stub, raises NotImplementedError
```

---

## 3. CANONICAL DATASET ENGINE

```
CANONICAL: core_model/mini_brain/dataset_expansion/dataset_expansion_engine.py
  Class: DatasetExpansionEngine
REASON:
  - Only dataset expansion engine in codebase (no duplicates)
  - 7 generation modes (phrase, sentence, conversation, instruction, translation pair, transliteration, mixed)
  - SHA-256 seal integration built in
  - Enforces 8:1 synthetic-to-human ratio
EVIDENCE: Imported by backend/services/admin_assistant_dataset_expansion_service.py
```

---

## 4. CANONICAL TRANSLATION ENGINE

```
CANONICAL: core_model/mini_brain/dataset_expansion/dataset_expansion_engine.py
  Method: _translate_to_english() and _generate_translation_pairs()
  Lexicon: TAMIL_ENGLISH_LEXICON (10 root concepts with polysemy)
REASON:
  - Only translation logic in codebase
  - Tanglish normalization in tanglish_normalizer.py (companion, no duplicates)
EVIDENCE: Same file as dataset engine — translation is an integrated mode
NOTE: 10-concept lexicon is a known limitation (P1 gap, not a duplicate issue)
```

---

## 5. CANONICAL ADMIN ASSISTANT SERVICE

```
CANONICAL: backend/services/admin_assistant_service.py
  Class: AdminAssistantService
REASON:
  - 4-layer hybrid routing (FAQ → page-help → tools → proposals)
  - 108 registered read-only inspection tools
  - Imported by backend/api/routes/admin_assistant.py
  - No duplicate AdminAssistantService exists
EVIDENCE: Sole importer of all Mini Brain tool modules
```

---

## 6. CANONICAL TRAINING ENGINE

```
CANONICAL: artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py
  Training loop: run_training_experiment() function
REASON:
  - Most recent training runner (WS07 E3)
  - Implements 15 hardware guards
  - SHA-256 locked baselines verification
  - AdamW + Cosine LR schedule
  - Response-only masking
  - E3-A through E3-E split logic
EVIDENCE: Executed for Phase 60 E3-A through E3-E training runs
NOTE: No shared training module exists — each runner is self-contained.
  Creating a shared training engine module is a P1 pre-E4/E5 recommendation.
```

---

## 7. CANONICAL RAG ENGINE

```
CANONICAL: backend/services/rag_service.py + core_model/rag/ package
  Primary classes: RagService, SemanticChunkService, RagRepository
REASON:
  - No duplicate RAG service exists
  - Actively integrated into PublicChatRoutingService Stage 7
  - Ingestion → chunking → hybrid BM25/n-gram search → retrieval pipeline implemented
EVIDENCE: Imported by public_chat_routing_service.py
NOTE: N-gram hashing approximation (not dense bi-encoder) — known P1 limitation
```

---

## 8. CANONICAL MEMORY ENGINE

```
CANONICAL: backend/services/conversation_memory_service.py
  Classes: ConversationMemoryService
REASON:
  - No duplicate memory service exists
  - Consent-gated declarative + episodic SQLite storage
  - Integrated into PublicChatRoutingService Stage 4
EVIDENCE: Imported by public_chat_routing_service.py
```

---

## 9. CANONICAL PROVIDER GATEWAY

```
CANONICAL: backend/services/mini_brain_external_ai_gateway_service.py
  Class: MiniBrainExternalAIGatewayService
REASON:
  - Only external AI provider gateway implementation
  - OpenRouter adapter with httpx dispatch
  - is_available() check enforces governance (returns False when API key absent)
EVIDENCE: Imported by PublicChatRoutingService for Stage 11 fallback
NOTE: is_available()=False in current env — feature built but not activated
```

---

## 10. CANONICAL PUBLIC CHAT ORCHESTRATOR

```
CANONICAL: backend/services/public_chat_routing_service.py
  Class: PublicChatRoutingService
REASON:
  - Only public chat orchestrator
  - 13-stage pipeline with safety filters, tools, RAG, memory, model routing
  - Safe degradation when no model is assigned
EVIDENCE: Imported by backend/api/routes/public_chat.py
```

---

## 11. Canonical Architecture Summary

| Subsystem | Canonical File | Class | Resolved? |
|---|---|---|---|
| Model Implementation | `run_e3_experiments.py` | `BrudSmallV2Model` (local) | ✅ Resolved (no shared module yet) |
| Inference Runtime | `core_model/inference_runtime/generation_engine.py` | `GenerationEngine` | ✅ Resolved |
| Dataset Engine | `core_model/mini_brain/dataset_expansion/dataset_expansion_engine.py` | `DatasetExpansionEngine` | ✅ Resolved |
| Translation Engine | Same as Dataset Engine | `_translate_to_english()` | ✅ Resolved |
| Admin Assistant | `backend/services/admin_assistant_service.py` | `AdminAssistantService` | ✅ Resolved |
| Training Engine | `run_e3_experiments.py` | `run_training_experiment()` | ✅ Resolved (no shared module yet) |
| RAG Engine | `backend/services/rag_service.py` | `RagService` | ✅ Resolved |
| Memory Engine | `backend/services/conversation_memory_service.py` | `ConversationMemoryService` | ✅ Resolved |
| Provider Gateway | `backend/services/mini_brain_external_ai_gateway_service.py` | `MiniBrainExternalAIGatewayService` | ✅ Resolved |
| Public Chat Orchestrator | `backend/services/public_chat_routing_service.py` | `PublicChatRoutingService` | ✅ Resolved |

**All 10 canonical implementations are RESOLVED.**  
The 2 marked "no shared module yet" (Model + Training Engine) are the primary P1 technical debt items before E4/E5.
