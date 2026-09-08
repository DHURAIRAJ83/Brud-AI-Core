# BRUD AI — PROVIDER / MODEL ROUTING AUDIT (WS08)
**Audit Date:** 2026-09-07

---

## PROVIDER LANDSCAPE

Two distinct provider layers exist:

### Layer 1: Brud Core Model Inference (Phase 15)
- **File:** `backend/services/inference_runtime_service.py`
- **Provider:** Local Brud transformer checkpoint
- **Config:** Via `InferenceRuntimeRepository` → runtime profiles
- **Model Assignment:** `ModelAssignmentService` (62 KB)
- **Scope Resolution:** `PublicModelAssignmentResolver` (public chat)
- **No external AI providers** — Brud-only inference
- **Status:** ACTIVE

### Layer 2: Mini Brain LLM Adapter (MB-28)
- **File:** `backend/services/mini_brain_llm_adapter.py` (25 KB)
- **Providers:**
  - `LlamaCppMiniBrainAdapter` — local llama.cpp
  - `ExternalProviderMiniBrainAdapter` — external APIs
  - `MockMiniBrainAdapter` — testing
- **Provider Settings:** `MiniBrainProviderSettingsService`
- **Status:** ACTIVE

### Layer 3: External AI Provider Client
- **File:** `backend/services/external_ai_provider_client.py` (7.4 KB)
- **Providers:**
  - `OpenRouterProviderClient` — OpenRouter API
  - `MockProviderClient` — testing
- **Purpose:** Used for Admin Assistant LLM calls
- **Status:** ACTIVE

### Layer 4: Provider Connection Adapters
- **File:** `backend/services/provider_settings_connection_adapters.py` (15 KB)
- **Adapters:** OpenAI, Anthropic, Gemini, OpenRouter, LocalLLM, LocalBackend, Mock
- **Purpose:** Connection testing and validation
- **Status:** ACTIVE

---

## PROVIDER REGISTRIES / ROUTING

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Inference Runtime (Brud) | `inference_runtime_service.py` | ACTIVE | Local checkpoint |
| Model Assignment | `model_assignment_service.py` | ACTIVE | Assigns model to scope |
| Mini Brain Provider Settings | `mini_brain_provider_settings_service.py` | ACTIVE | External provider config |
| Provider Settings Connection | `provider_settings_connection_adapters.py` | ACTIVE | Connection validation |
| External AI Provider | `external_ai_provider_client.py` | ACTIVE | OpenRouter client |
| Web Search Provider | `web_search_provider.py` | ACTIVE | Wikipedia + SearchAPI |
| Training Adapter Registry | `training_adapter_registry.py` | ACTIVE | Training runtime selection |
| Training Runtime Adapter | `training_runtime_adapter.py` | ACTIVE | LlamaCpp/Torch/Simulation |

---

## ARCHITECTURE CONFLICT: THREE INFERENCE PATHS

**Path A (Authoritative — Brud Core Model):**
```
InferenceRuntimeService → BrudModel checkpoint → generation_engine.py
```
Called by: PublicChatRoutingService, ChatOrchestrationService, RagGenerationService, AdminAssistantChatService

**Path B (Mini Brain LLM — External/Local):**
```
MiniBrainLlmRuntimeService → MiniBrainLlmAdapterProtocol → LlamaCpp or ExternalAPI
```
Called by: Mini Brain LLM Runtime routes only

**Path C (External AI Provider — for Admin Assistant):**
```
AdminAssistantChatService → ExternalProviderMiniBrainAdapter → OpenRouter/etc
```
Called by: Admin Assistant fallback when no Brud model assigned

---

## FALLBACK STRATEGY

| Scenario | Fallback |
|----------|---------|
| No Brud model assigned | Text: "AI response unavailable" |
| Mini Brain no local model | Fall back to external provider |
| External provider fails | Fall back to deterministic response |
| All providers fail | Graceful degradation message |

---

## DUPLICATE ANALYSIS

| Finding | Severity | Notes |
|---------|----------|-------|
| Three separate inference paths | D5 (CRITICAL) | By design but architecturally complex |
| ExternalProviderClient vs ExternalProviderMiniBrainAdapter | D3 (MEDIUM) | Similar but different integration points |
| Web search provider vs trusted_web_answer_service | RESOLVED | Different layers |

---

## FINDINGS

1. **ACTIVE:** Three separate inference paths exist by design
2. **CONFLICT:** No single unified provider router — each system has its own
3. **ACTIVE:** All providers have fallback handling
4. **MISSING:** Unified provider registry / cost tracking / quota management
5. **RISK:** Provider API keys managed in multiple places (settings DB + env vars)

---
*WS08 Complete*
