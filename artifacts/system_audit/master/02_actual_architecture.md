# Master Brud AI System Audit — 02: Actual Runtime Architecture

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code inspection and tracing)  

---

## 1. Actual End-to-End Runtime Architecture Map: Public Chat

```
[ End User / Web Client (apps/chatbot, Vite :5173) ]
                       │
                       ▼ HTTP POST /public/chat/sessions/{session_id}/messages
      [ backend/api/routes/public_chat_runtime.py ]
                       │
                       ▼ rate-limiting & session validation
      [ backend/services/mini_brain_public_chat_runtime_service.py ]
                       │
                       ▼ handle_message()
      [ backend/services/public_chat_routing_service.py ]
         │               │                     │
         ▼               ▼                     ▼
 [ Input Safety ] [ Language Policy ] [ Route Classifier ]
 (input_safety.py)(language_routing.py)(query_classifier.py)
         │               │                     │
         └───────────────┼─────────────────────┘
                         │
                         ▼ resolve_route_availability()
               ┌─────────┴─────────┐
               ▼                   ▼
      [ Deterministic Route ]   [ Insufficient / Fallback ]
      - calculator              (fallback_text.py)
      - unit_conversion         "Reason: model disabled or RAG unavailable"
      - date_time_arithmetic
               │
               ▼ (if model assignment exists)
      [ backend/services/chat_orchestration_service.py ]
         │               │                     │
         ▼               ▼                     ▼
   [ Context Budget ] [ Memory Retrieval ] [ RAG Retrieval ]
   (context_budget.py)(memory_service.py)  (rag_retrieval_service.py)
         │               │                     │
         └───────────────┼─────────────────────┘
                         │
                         ▼ send_message()
      [ backend/services/inference_runtime_service.py ]
                         │
                         ▼ verify_manifest / verify_checkpoint
      [ core_model/inference_runtime/model_loader.py ]
                         │
                         ▼ CPU-only PyTorch inference
      [ BrudSmallV2Model / local model ]
                         │
                         ▼ output safety & citation adapter
      [ backend/services/public_citation_adapter.py ]
                         │
                         ▼
             [ JSON Response to User ]
```

### Critical Architecture Finding for Public Chat:
1. **Actual Execution State Today:**
   - Public chat does **NOT** route to any active neural model in production because `models/active/` is empty and `production_promotion` is **BLOCKED**.
   - If a user sends a query today, the route availability service (`core_model/public_chat/route_availability.py`) resolves `core_model` as unavailable or falls back to deterministic tools (`calculator`, `unit_conversion`, `date_time_arithmetic`) or returns a polite, governed fallback response (`fallback_text.py`).
   - This design prevents hallucinated, uncontrolled model outputs from reaching users when candidate models are not production-ready.

---

## 2. Actual Runtime Architecture Map: Admin System & Admin Assistant Mini Brain

```
[ System Administrator (apps/admin-dashboard, Vite :5174) ]
                       │
                       ▼ Authenticated HTTP Requests (Session Cookie + CSRF)
      [ backend/api/routes/admin_assistant.py ]
                       │
                       ├─── Mode 1: Chat / Help / Guide ───────────────────┐
                       │                                                   ▼
                       │                    [ backend/services/admin_assistant_chat_service.py ]
                       │                                                   │
                       │                    ┌──────────────────────────────┴──────────────────────────────┐
                       │                    ▼                                                             ▼
                       │         [ Deterministic Path ]                                       [ Open-Ended LLM Path ]
                       │         - FAQ match (FAQ dicts)                                      - Reuses admin_diagnostic scope
                       │         - Page help (dashboard_registry.py)                          - Falls back to "AI generation
                       │         - Read-Only Tool Execution (108 tools)                         unavailable" if model unassigned
                       │                    │                                                             │
                       │                    └──────────────────────────────┬──────────────────────────────┘
                       │                                                   ▼
                       │                                   [ Sanitized Admin Reply ]
                       │
                       └─── Mode 2: Governed Mutation Proposals ───────────┐
                                                                           ▼
                                            [ backend/services/admin_assistant_write_governance.py ]
                                                                           │
                                                                           ▼ propose_with_governance()
                                            [ backend/services/admin_assistant_service.py ]
                                                                           │
                                            ┌──────────────────────────────┴──────────────────────────────┐
                                            ▼                                                             ▼
                                 [ Action Allowlist Check ]                                   [ Blocked Substrings ]
                                 (action_registry.py)                                         ("train", "pretrain" BLOCKED)
                                            │                                                             │
                                            └──────────────────────────────┬──────────────────────────────┘
                                                                           ▼
                                                    [ Proposal Created: Status PENDING ]
                                                    (Written to Admin Review Queue)
                                                                           │
                                                                           ▼ Human Admin Review
                                                    [ Decision: APPROVE / REJECT / EDIT ]
                                                                           │
                                                                           ▼ execute_with_governance()
                                                    [ Two-Person Verification Enforced ]
                                                    (Admin 1 != Admin 2 for high-risk actions)
                                                                           │
                                                                           ▼
                                                    [ Allowlisted Backend Service Execution ]
                                                    (Document, Dataset, or Governance update)
                                                                           │
                                                                           ▼
                                                    [ Immutable Append-Only Audit Log ]
                                                    (AuditLogRepository in SQLite)
```

---

## 3. Detailed Component Map

| Component Layer | Source File | Class / Function | Inputs | Outputs | Dependencies | Implementation Status |
|---|---|---|---|---|---|---|
| **Public Chat Route** | `backend/api/routes/public_chat_runtime.py` | `start_session`, `send_message` | JSON payload, client IP | Session ID, Chat Response | FastAPI, RateLimiter | ✅ Operational |
| **Chat Routing Engine** | `backend/services/public_chat_routing_service.py` | `PublicChatRoutingService.handle_message` | User query, history, language | Structured response | Safety, Language policy, Tools | ✅ Operational |
| **Deterministic Tools** | `backend/services/deterministic_tool_registry.py` | `get_tool_descriptor`, `run_tool` | Math expression, unit values | Calculated scalar | Python stdlib, re | ✅ Operational |
| **Chat Context Builder** | `backend/services/chat_orchestration_service.py` | `ChatOrchestrationService.send_message` | Session, messages, RAG scope | Grounded text | MemoryService, RagService | ✅ Operational |
| **Inference Loader** | `backend/services/inference_runtime_service.py` | `InferenceRuntimeService.load_model` | Release ID, instance ID | In-process model handle | ModelLoader, Tokenizer | ✅ Operational |
| **Admin Assistant Chat**| `backend/services/admin_assistant_chat_service.py`| `AdminAssistantChatService.handle_message`| Admin prompt, page context | Guide message, proposal | Tool registry, FAQ match | ✅ Operational |
| **Admin Assistant Tools**| `backend/services/admin_assistant_tools.py` | `run_tool` (108 tools) | Tool name, parameters | Redacted JSON state | 15+ Repositories | ✅ Operational |
| **Admin Write Governance**| `backend/services/admin_assistant_write_governance.py`| `propose_with_governance`, `execute_with_governance` | Proposal payload, Admin ID | Approval token, execution | RBAC, AuditLogRepo | ✅ Operational |
| **Dataset Expansion Engine**| `core_model/admin_assistant/dataset_expansion_engine.py`| `generate_expansion_proposals` | Tamil concept, mode | Multilingual proposals | Lexicon, NFC normalizer | ✅ Operational |
| **Quality Validator** | `core_model/admin_assistant/dataset_expansion_validator.py`| `validate_proposal` | Proposal record | Validation score, flags | Script ratio, Virama | ✅ Operational |
| **Candidate Trainer** | `artifacts/candidates/phase60/run_controlled_training_ws05.py`| `train_candidate()` | Config JSON, Dataset JSONL | Checkpoint `.pt`, logs | PyTorch CPU, AdamW | ✅ Operational |
| **Capability Evaluator**| `artifacts/candidates/phase60/run_capability_evaluation_ws06.py`| `evaluate_checkpoint()` | Checkpoint `.pt`, Tokenizer v2 | Metrics, 24 CAP probe logs | PyTorch, NumPy | ✅ Operational |
| **Production Gate** | `core_model/release/phase44_runtime_governance.py` | `RuntimeGovernanceController` | Checkpoint, two admin tokens | Internal canary token | SHA-256 signatures | ✅ Enforced in code |
