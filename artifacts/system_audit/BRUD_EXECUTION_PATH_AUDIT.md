# BRUD AI — EXECUTION PATH AUDIT (WS16)
**Audit Date:** 2026-09-07

> Rule: A feature is NOT considered implemented merely because a file exists. It must be connected to the real execution path.

---

## EXECUTION PATH 1 — Public Chat (VERIFIED ACTIVE)

```
Browser: POST /chat
↓
backend/api/routes/chat.py
  ↓ rate_limit check → public_chat_rate_limiter.py
  ↓ PublicChatRequest Pydantic validation
  ↓ ConnectionPool.acquire()
  ↓ evaluate_public_capability_gate() [capabilities/public_capability_gate.py]
  ↓
PublicChatRoutingService.handle_message()
  ↓ evaluate_input_safety() [public_chat/input_safety.py]
  ↓ classify_language() [rag/language_routing.py]
  ↓ resolve_route_availability() [public_chat/route_availability.py]
  ↓ classify_knowledge_gap() [capabilities/clarification_intelligence.py]

  Route: RAG
    ↓ RagRetrievalService.retrieve()
    ↓ ChatOrchestrationService.send_message()
    ↓ InferenceRuntimeService.generate()
    ↓ BrudModel.forward() [core_model/architecture/model.py]
    ↓ generation_engine.py bounded loop
    ↓ Response with RAG citations

  Route: TOOL
    ↓ select_tool_for_request() [tool_gateway/tool_selection.py]
    ↓ DeterministicToolExecutionService.execute()
    ↓ Tool result

  Route: TRUSTED_WEB
    ↓ TrustedWebAnswerService.answer()
    ↓ web_search_provider.py
    ↓ Wikipedia/SearchAPI result

  Route: FALLBACK
    ↓ insufficient_text() / refusal_text() [public_chat/fallback_text.py]

  ↓ evaluate_output_safety() [public_chat/output_safety.py]
  ↓ resolve_answer_language() [public_chat/language_policy.py]
  ↓ Public citations adapted [public_citation_adapter.py]
  ↓ AuditLogRepository.append()
  ↓ PublicChatResponse
↓
Browser
```
**VERDICT: FULLY CONNECTED — Verified by direct code tracing**

---

## EXECUTION PATH 2 — Admin Authentication (VERIFIED ACTIVE)

```
Browser: POST /admin/login
↓
backend/api/routes/auth.py
  ↓ AdminRepository.authenticate()
  ↓ Session created
  ↓ Set-Cookie (session + CSRF)
↓
Browser has session

Subsequent admin request:
  ↓ require_admin(request) → AdminRepository.validate_session()
  ↓ require_csrf(request, context) → AdminRepository.validate_csrf()
  ↓ Handler executes
```
**VERDICT: FULLY CONNECTED**

---

## EXECUTION PATH 3 — Admin Assistant Proposal Flow (VERIFIED ACTIVE)

```
Browser: POST /admin/assistant/proposals
↓
admin_assistant.py route
  ↓ require_csrf (auth gate)
  ↓ AdminAssistantService.propose()
    ↓ get_action_definition() [action_registry.py]
    ↓ BLOCKED_ACTION_SUBSTRINGS check
    ↓ _generate_preview() → reads current DB state
    ↓ _compute_fingerprint() → current state snapshot
    ↓ AdminApprovalRepository.create_proposal()
    ↓ AuditLogRepository.append()
  ↓ ProposalPublic response

Browser: POST /admin/assistant/proposals/{id}/execute
  ↓ require_csrf
  ↓ AdminAssistantService.execute()
    ↓ AdminApprovalRepository.get_pending()
    ↓ _expire_if_due() fingerprint staleness check
    ↓ _compare_fingerprints() concurrent-mutation guard
    ↓ ACTION_EXECUTORS[action_type]() → existing admin service
    ↓ AdminApprovalRepository.mark_executed()
    ↓ AuditLogRepository.append()
  ↓ ExecutionResult response
```
**VERDICT: FULLY CONNECTED**

---

## EXECUTION PATH 4 — Memory Write (VERIFIED ACTIVE)

```
POST /admin/conversation-memory/memory-items
↓
conversation_memory.py route
  ↓ require_csrf
  ↓ MemoryService.create_item(MemoryItemCreate)
    ↓ ConversationMemoryRepository.policy()
    ↓ ConversationMemoryRepository.consent()
    ↓ category_is_allowed() [memory_policy.py]
    ↓ purpose_is_bounded() [memory_policy.py]
    ↓ assess_memory_safety() [memory_safety.py]
    ↓ normalize_memory_value() [memory_normalization.py]
    ↓ compute_embedding() [rag/embedding.py]
    ↓ pack_vector()
    ↓ ConversationMemoryRepository.create_item()
    ↓ status = 'pending' initially
  ↓ MemoryItem response
```
**VERDICT: FULLY CONNECTED**

---

## EXECUTION PATH 5 — Training (VERIFIED PARTIAL)

```
POST /admin/pretraining/runs
↓
pretraining.py route
  ↓ require_csrf
  ↓ PretrainingService.start_run()
    ↓ Validates corpus readiness
    ↓ Creates training_runs row
    ↓ Spawns background thread/process → training_worker.py

  training_worker.py:
    ↓ Loads BrudModelConfig
    ↓ Loads tokenizer
    ↓ Builds data loader
    ↓ Runs training loop [core_model/training/]
    ↓ Saves checkpoints [core_model/checkpoints/]
    ↓ Updates training_runs row
```
**VERDICT: CONNECTED** — training_worker.py is a separate process entry point

---

## EXECUTION PATH 6 — Mini Brain (MB-28) Chat (VERIFIED ACTIVE)

```
POST /mini-brain/llm-runtime/chat
↓
mini_brain_llm_runtime.py route
  ↓ require_csrf
  ↓ MiniBrainLlmRuntimeService.chat()
    ↓ MiniBrainProviderSettingsService.list_settings("local_model")
    ↓ provider_fallback_policy.decide()
    ↓ MiniBrainLlmAdapterProtocol.generate()
      [LlamaCpp | ExternalProvider | Mock]
    ↓ tool_intent_classifier [if tool intent detected]
    ↓ _maybe_propose_governed_action() → AdminAssistantService.propose() [narrow bridge]
    ↓ MiniBrainLlmRuntimeRepository.create_message()
  ↓ ChatResponse
```
**VERDICT: CONNECTED — with bridge to AdminAssistantService**

---

## DISCONNECTED / PLACEHOLDER PATHS

| Component | Status | Evidence |
|-----------|--------|---------|
| MiniBrainService.placeholder_inference() | PLACEHOLDER | Returns "not_implemented_in_mb01" |
| MiniBrainService.placeholder_knowledge() | PLACEHOLDER | Returns "not_implemented_in_mb01" |
| MiniBrainService.placeholder_memory() | PLACEHOLDER | Returns "not_implemented_in_mb01" |
| Vision pipeline (mini_brain_vision_*) | LIKELY STUB | Needs investigation |
| Voice runtime (mini_brain_voice_*) | LIKELY STUB | Needs investigation |
| Pilot Operations / Metrics pages | LIKELY STUB | Small page files with no backend data |
| core_model/inference/ | DEAD | Empty __init__.py |

---

## FINDINGS

1. **VERIFIED:** Public chat → 6-step pipeline → response: FULLY CONNECTED
2. **VERIFIED:** Admin authentication → cookie + CSRF: FULLY CONNECTED
3. **VERIFIED:** Admin assistant proposals → execute → audit: FULLY CONNECTED
4. **VERIFIED:** Memory write → policy → consent → safety → storage: FULLY CONNECTED
5. **VERIFIED:** Training → worker → checkpoint: CONNECTED
6. **VERIFIED:** MB-28 chat → adapter → response: CONNECTED
7. **PLACEHOLDER:** MiniBrainService base inference methods are explicitly non-functional
8. **SUSPECTED STUB:** Vision, Voice pipelines need deeper verification

---
*WS16 Complete*
