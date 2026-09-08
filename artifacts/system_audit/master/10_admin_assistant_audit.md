# Master Brud AI System Audit — 10: Admin Assistant Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code in `backend/api/routes/admin_assistant.py` and `backend/services/admin_assistant_*.py`)  

---

## 1. Admin Assistant Operational Architecture

The Admin Assistant is implemented as a floating, context-aware companion on the React Admin Dashboard (`apps/admin-dashboard`). It allows authenticated administrators to navigate the console, query system metrics, view documentation, and initiate governed mutation proposals.

```
[ Admin Dashboard Floating UI ]
               │
               ▼ POST /admin/assistant/chat (authenticated session + CSRF)
[ backend/api/routes/admin_assistant.py ]
               │
               ▼
[ backend/services/admin_assistant_chat_service.py ]
         │               │                     │
         ▼               ▼                     ▼
 [ Intent Parser ] [ Language Resolver ] [ Tool Router ]
 (classify_intent) (AdminAssistantLang)  (run_tool - 108 tools)
         │               │                     │
         └───────────────┼─────────────────────┘
                         │
                         ▼
        [ Deterministic Answer / Guide / Status ]
        (Falls back gracefully if LLM unassigned)
```

---

## 2. Implemented Capabilities vs Missing Capabilities

| Feature / Capability | Code Implementation | Verification | Operational Status |
|---|---|---|---|
| **Context-Aware Page Help** | Reads current `page_id`, `tab_id`, and `entity_type` to supply relevant help | `core_model/admin_assistant/dashboard_registry.py` | ✅ **OPERATIONAL** |
| **Bilingual Support (Tamil / English / Tanglish)** | Per-admin persistent language preference; returns replies in requested language | `backend/services/admin_assistant_language_service.py` | ✅ **OPERATIONAL** |
| **FAQ Question Matching** | Matches questions against curated FAQs (RAG Sandbox, Knowledge Gap, Dataset Verification) | `core_model/admin_assistant/*_help.py` | ✅ **OPERATIONAL** |
| **Read-Only System Inspection** | 108 read-only tools querying database, RAG, models, and training logs | `backend/services/admin_assistant_tools.py` | ✅ **OPERATIONAL** |
| **Proposal Creation (Propose)** | Generates structured proposals for dataset reviews, source edits, and overrides | `backend/services/admin_assistant_write_governance.py` | ✅ **OPERATIONAL** |
| **Admin Review Queue** | Dedicated UI queue for admins to approve, reject, or edit proposals | `backend/services/admin_assistant_service.py` | ✅ **OPERATIONAL** |
| **Two-Person Rule Enforcement** | High-risk proposals require approval by a different admin (`proposer != reviewer`) | `backend/services/admin_assistant_service.py` | ✅ **OPERATIONAL** |
| **Training Execution Block** | Code-level refusal of any proposal containing `"train"` or `"pretrain"` | `core_model/admin_assistant/action_registry.py` | ✅ **OPERATIONAL** |
| **Autonomous Model Retraining**| Assistant autonomously re-training models without human review | N/A | 🔒 **BLOCKED BY DESIGN** |
| **Direct Production Promotion**| Assistant promoting candidate to production without human drill | N/A | 🔒 **BLOCKED BY DESIGN** |

---

## 3. Tool Invocation & Audit Trail

- Every tool invocation is recorded in SQLite:
  - Table: `admin_assistant_tool_invocations`
  - Fields: `admin_public_id`, `tool_name`, `parameters_hash`, `outcome` (success/denied/error), `execution_duration_ms`, `timestamp`.
- Secrets, API keys, and sensitive tokens are automatically scrubbed via `redact_secrets()`.
- Unhandled exceptions are caught and returned as sanitized `ReadOnlyToolError` messages without leaking stack traces.
