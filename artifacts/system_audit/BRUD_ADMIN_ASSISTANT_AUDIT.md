# BRUD AI — ADMIN ASSISTANT AUDIT (WS02)
**Audit Date:** 2026-09-07

---

## EXECUTION GRAPH

```
Admin User (Browser)
    ↓ hash navigation #Admin-Assistant
AdminAssistantPage.jsx (14 KB)
    ↓ POST /admin/assistant/chat
backend/api/routes/admin_assistant.py
    ↓
AdminAssistantChatService (60 KB)
    ↓ deterministic intent → classify_intent()
    ↓ LLM route → InferenceRuntimeService
    ↓ tool route → run_tool()
core_model/admin_assistant/ (intent, action_registry, localization)
core_model/mini_brain/llm_runtime/ (prompt_builder, token_budget)
    ↓
AdminAssistantService (153 KB) — proposal/review/execute
    ↓
AdminApprovalRepository → SQLite
    ↓
AuditLogRepository → SQLite
    ↓
Response (bilingual: Tamil/English/Tanglish)
```

---

## IMPLEMENTATION INVENTORY

### Phase 8 Admin Assistant System (Original)

| Component | File | Size | Status |
|-----------|------|------|--------|
| Route | `backend/api/routes/admin_assistant.py` | 16 KB | ACTIVE |
| Chat Service | `backend/services/admin_assistant_chat_service.py` | 60 KB | ACTIVE |
| Proposal/Execute Service | `backend/services/admin_assistant_service.py` | 153 KB | ACTIVE |
| Tools | `backend/services/admin_assistant_tools.py` | 119 KB | ACTIVE |
| Tool Governance | `backend/services/admin_assistant_tool_governance.py` | 9.7 KB | ACTIVE |
| Write Governance | `backend/services/admin_assistant_write_governance.py` | 5 KB | ACTIVE |
| Language Service | `backend/services/admin_assistant_language_service.py` | 2.3 KB | ACTIVE |
| Dataset Expansion | `backend/services/admin_assistant_dataset_expansion_service.py` | 8.3 KB | ACTIVE |
| Context Repository | `backend/database/repositories/admin_assistant_context.py` | 11 KB | ACTIVE |

### Mini Brain LLM Runtime System (MB-28 — newer parallel system)

| Component | File | Size | Status |
|-----------|------|------|--------|
| Route | `backend/api/routes/mini_brain_llm_runtime.py` | 10 KB | ACTIVE |
| Service | `backend/services/mini_brain_llm_runtime_service.py` | 81 KB | ACTIVE |
| Adapter | `backend/services/mini_brain_llm_adapter.py` | 25 KB | ACTIVE |
| Core Modules | `core_model/mini_brain/llm_runtime/` | 15+ files | ACTIVE |

---

## ARCHITECTURE CONFLICT DETECTED (D5 — CRITICAL)

Two parallel admin AI systems exist:

**System A:** Phase 8 Admin Assistant
- Entry: `/admin/assistant/chat`
- Service: `AdminAssistantChatService`
- LLM: via `InferenceRuntimeService` (core model runtime)
- Scope: dashboard help, proposals, governance

**System B:** Mini Brain LLM Runtime (MB-28)
- Entry: `/mini-brain/llm-runtime/` routes
- Service: `MiniBrainLlmRuntimeService`
- LLM: via `MiniBrainLlmAdapterProtocol` (LlamaCpp or external)
- Scope: general admin intelligence, tool dispatch

### Key Finding from Code:
The MB-28 docstring explicitly states:
> "This is a new, additive, parallel capability — it does NOT touch the separate, pre-existing Phase 8 Admin Assistant system...with exactly one narrow, deliberate exception (Phase 16.5): `chat()` calls the existing, unmodified `AdminAssistantService.propose()` via the shared `core_model.admin_assistant.chat_action_bridge.propose_chat_action()` bridge"

**VERDICT: ARCHITECTURAL CONFLICT (D5)**
- Two separate AI chat systems for admins
- They share one narrow bridge (`chat_action_bridge.propose_chat_action()`)
- Both are ACTIVE
- This is by design in MB-28 but represents architectural duplication

---

## CORE MODEL MODULES FOR ADMIN ASSISTANT

| Module | File | Status | Responsibility |
|--------|------|--------|----------------|
| Intent Classification | `core_model/admin_assistant/intent.py` | ACTIVE | classify_intent() |
| Action Registry | `core_model/admin_assistant/action_registry.py` | ACTIVE | Allowlisted mutation types |
| Dashboard Registry | `core_model/admin_assistant/dashboard_registry.py` | ACTIVE | Page registry for navigation help |
| Localization | `core_model/admin_assistant/localization/` | ACTIVE | Tamil/English/Tanglish messages |
| Chat Action Bridge | `core_model/admin_assistant/chat_action_bridge.py` | ACTIVE | Bridge between Phase8 + MB-28 |
| Language Preference | `core_model/admin_assistant/language_preference.py` | ACTIVE | Per-admin language preference |
| Lifecycle | `core_model/admin_assistant/lifecycle.py` | ACTIVE | Session lifecycle |
| Dataset Reasoning | `core_model/admin_assistant/admin_dataset_reasoning.py` | ACTIVE | Dataset-specific reasoning |

---

## OWNERSHIP ANALYSIS

| Responsibility | Owner | Duplicate? |
|----------------|-------|-----------|
| Admin Intent Classification | `core_model/admin_assistant/intent.py` | NO |
| Admin LLM Prompt Building | `core_model/mini_brain/llm_runtime/prompt_builder.py` | NO |
| Admin Tool Execution (Ph8) | `admin_assistant_tools.py` | OVERLAP with MB-28 tool dispatch |
| Admin Tool Governance | `admin_assistant_tool_governance.py` | OVERLAP with `mini_brain_plugin_governance_service.py` |
| Admin Language Preference | `AdminAssistantLanguageService` | NO |
| Admin Proposal/Review/Execute | `AdminAssistantService` | NO — single owner |

---

## SECURITY AUDIT

| Gate | Implementation | Status |
|------|----------------|--------|
| Admin authentication | `require_admin` dependency on all `/admin/assistant/*` routes | ACTIVE |
| CSRF protection | `CsrfDependency` on mutating endpoints | ACTIVE |
| Action allowlist | `ACTION_DEFINITIONS` in action_registry | ACTIVE |
| Write governance | `execute_with_governance()` | ACTIVE |
| Audit logging | `AuditLogRepository.append()` on all steps | ACTIVE |
| Tool governance | `ToolAuthorizationError` guard | ACTIVE |

---

## FINDINGS

1. **COMPLETE:** Phase 8 Admin Assistant fully implemented and active
2. **COMPLETE:** Mini Brain LLM Runtime (MB-28) implemented as parallel system
3. **CONFLICT:** Two admin AI systems exist simultaneously — not clean separation
4. **RISK:** `admin_assistant_tools.py` (119 KB) is extremely large — maintenance risk
5. **ACTIVE:** All authentication and governance gates functional

---
*WS02 Complete*
