# BRUD AI — ADMIN ASSISTANT PROVIDER DATASET GENERATION
# PRE-IMPLEMENTATION FORENSIC AUDIT & ARCHITECTURE DESIGN

============================================================
PHASE 0 — SAFETY / GOVERNANCE DECLARATION
============================================================
- **STATUS:** Read-Only Audit Completed.
- **TRAINING EXECUTED:** FALSE
- **TRAINING AUTHORIZATION:** FALSE
- **PRODUCTION PROMOTION:** BLOCKED
- **PUBLIC CHAT ELIGIBLE:** FALSE
- **MODEL WEIGHT MUTATION:** FALSE
- **TOKENIZER MUTATION:** FALSE
- **PRODUCTION STATE:** LOCKED
- **ADMIN_ASSISTANT_AUTHORITY:** ADVISORY_ONLY

===========================================================
1. EXECUTIVE SUMMARY
===========================================================
The existing architecture natively supports batch provider dataset generation via **MB-16 (MiniBrainMultimodalDatasetGeneratorService)**. This existing engine already handles provider routing, generation, batching, validation, quality analysis, duplicate detection, draft state isolation, and human review certification. 

Currently, MB-16 is accessible *only* via the Admin Dashboard's `MultimodalDatasetGeneratorTab.jsx`. The core gap is that the **Admin Assistant Chat UI** lacks the frontend components (Left Menu, Provider Settings pane) and the chat intent routing to trigger this existing MB-16 pipeline autonomously. 

**Recommendation:** Do NOT build a new generation service. The new implementation (P10-L) will strictly focus on adding the required frontend UI to `ChatPanel.jsx` (Left Menu, Settings) and connecting the `AdminAssistantChatService` intent router directly to the existing MB-16 service and `ProviderSettingsService`.

===========================================================
2. EXISTING ARCHITECTURE
===========================================================
- **Admin Assistant**: `AdminAssistantChatService` routes chat via 48 read-only tools and proposal generators (`POST /api/admin/assistant/chat`).
- **Provider System**: `ProviderSettingsService` (`POST /api/admin/mini-brain/provider-settings`) manages keys for Ollama, Groq, OpenRouter, etc.
- **Dataset Generation (MB-16)**: `MiniBrainMultimodalDatasetGeneratorService` orchestrates `collect_sources -> dataset_draft -> quality_analysis -> duplicate_detection -> awaiting_admin_review -> certified`.
- **RAG & Training Pipelines**: Certified datasets are automatically exported to `RagRepository` (for vector search) and `DatasetAdminRepository` (for training split manifests).

===========================================================
3. ADMIN ASSISTANT CURRENT CAPABILITIES
===========================================================
- **Working**: 48 read-only tools (dashboard status, dataset versions, governance status, etc.), grounded RAG chat, user feedback, file uploads, Tamil language localization.
- **Gap**: Cannot configure provider settings directly inside the Chat widget. Cannot autonomous trigger synthetic dataset generation from a raw chat prompt.

===========================================================
4. PROVIDER SYSTEM CURRENT CAPABILITIES
===========================================================
- **Working**: Secure HMAC encrypted API key storage via `ProviderSettingsService`. Adapters exist for Ollama, Groq, Claude, Gemini, OpenRouter. Fallbacks and timeouts are handled.
- **Gap**: Provider configuration UI is isolated in the `ProviderSettingsTab.jsx` on the Dashboard, rather than accessible inside the Admin Assistant Chat interface.

===========================================================
5. DATASET PIPELINE CURRENT CAPABILITIES
===========================================================
- **Working**: File uploads extract, clean (Tamil/Tanglish normalization), deduplicate, and store records. Proposals (`dataset_record_review`) are routed to `AdminApprovalRepository`.
- **Gap**: Seamless UX for generating 10,000 synthetic records directly via Assistant interaction requires wiring MB-16 into the chat proposal system.

===========================================================
6. EXISTING MULTIMODAL GENERATOR (MB-16) CAPABILITIES
===========================================================
- **Working**: Batched dataset generation, quality scoring, duplicate detection, draft session isolation, and human review state machine (`awaiting_admin_review`).
- **Reuse Assessment**: **100% Reusable**. We will route the Admin Assistant Chat's generation proposal directly into MB-16's `create_session` and `execute_pipeline` methods. No duplicate engine is needed.

===========================================================
7. RAG INTEGRATION
===========================================================
- **Working**: `RagRepository` ingests certified dataset chunks and provides `grounded-chat` retrieval. 
- Provider-generated datasets (MB-16) follow the exact same canonical path into RAG *after* Admin certification.

===========================================================
8. CONTINUOUS LEARNING INTEGRATION
===========================================================
- **Working**: Chat feedback enters `AdminAssistantContextRepository` and requires human approval before being merged into the canonical dataset manifest. No automatic training exists.

===========================================================
9. FRONTEND INTEGRATION (CURRENT STATE)
===========================================================
- **Working**: `ChatPanel.jsx` and `AdminAssistantWidget.jsx`.
- **Gap**: The floating chat UI does not have a "Left-Side Menu" for "Assistant Settings", "Dataset Generation", or "Jobs". 

===========================================================
10. BACKEND INTEGRATION (CURRENT STATE)
===========================================================
- **Working**: All APIs are functional, completely decoupled, and fail-closed governed.
- **Gap**: `admin_assistant_tools.py` requires a new `propose_synthetic_dataset_generation` tool to bridge chat intent to MB-16.

===========================================================
11. EXACT REUSABLE COMPONENTS
===========================================================
- `MiniBrainMultimodalDatasetGeneratorService` (100% reuse for data generation pipeline).
- `ProviderSettingsService` (100% reuse for API key storage).
- `AdminApprovalRepository` (100% reuse for human review).
- `RagRepository` (100% reuse for RAG indexing).
- `DatasetAdminRepository` (100% reuse for training export).

===========================================================
12. EXACT MISSING COMPONENTS
===========================================================
- Chat Intent: `propose_synthetic_dataset_generation` in `admin_assistant_tools.py`.
- Frontend: Left-Side Navigation Menu inside `ChatPanel.jsx`.
- Frontend: `AssistantProviderSettings.jsx` (embeddable in ChatPanel).
- Frontend: Job Progress UI inside `ChatPanel.jsx`.

===========================================================
13. EXACT UI GAPS
===========================================================
- Assistant Chat Widget currently lacks nested settings panes or progress bars for 10,000-record generation jobs.

===========================================================
14. SECURITY ASSESSMENT
===========================================================
- **Working**: API keys are securely encrypted at rest. Keys are never returned in plaintext (`masked_status` used).
- **Risk Mitigation**: The new Assistant Settings UI must strictly adhere to the existing pattern: `GET /api/admin/mini-brain/provider-settings` only returns `{ provider: "openrouter", configured: true, masked_key: "sk-...8d9f" }`.

===========================================================
15. PERFORMANCE ASSESSMENT
===========================================================
- **Working**: MB-16 already processes large jobs via batch chunks. 
- **Risk Mitigation**: A 10,000-record job will require the Chat UI to poll job status (`GET /admin/mini-brain/multimodal-dataset-generator/sessions/{id}`) rather than waiting synchronously on a single HTTP request.

===========================================================
16. GOVERNANCE ASSESSMENT
===========================================================
- **Working**: All dataset records remain in `Draft` until `AdminApprovalRepository` certification. Training requires `SignedTrainingAuthorizationToken`.
- **Risk Mitigation**: The Chat Assistant will only *propose* generation. MB-16 enforces the review queue. No governance bypass required.

===========================================================
17. ARCHITECTURE RECOMMENDATION
===========================================================
```text
Admin Assistant Chat (ChatPanel.jsx with New Left Menu)
        │
        ├── Chat View
        ├── Assistant Settings View (Provider Config) ──> ProviderSettingsService
        └── Dataset Generation View (Job Progress)
                 │
                 ↓
          AdminAssistantChatService
                 │
                 ↓ (Intent: Propose Dataset Generation)
          admin_assistant_tools.py
                 │
                 ↓
      MiniBrainMultimodalDatasetGeneratorService (MB-16)
                 │
                 ↓
        Provider Registry (Ollama, OpenRouter, Groq)
                 │
                 ↓
       Draft Dataset Session
                 │
                 ↓
       Quality / Duplicate Analysis
                 │
                 ↓
          HUMAN APPROVAL (Dashboard/Chat Notification)
                 │
          ┌──────┴──────┐
          ↓             ↓
     RagRepository    DatasetAdminRepository (Training Eligible)
```

===========================================================
18. IMPLEMENTATION PLAN (P10-L)
===========================================================
**P10-L-1 Provider Settings Integration**: Embed provider config UI into `ChatPanel.jsx`.
**P10-L-2 Assistant Chat Left Menu**: Refactor `ChatPanel.jsx` to support view switching.
**P10-L-3 Provider Dataset Generation Chat Intent**: Add tool router intent for generation.
**P10-L-4 Generation Job / Batch System**: Wire MB-16 polling to Chat UI progress bars.
**P10-L-5 Validation / Quality / Duplicate Pipeline**: Handled natively by MB-16 (no code needed).
**P10-L-6 Preview / Human Approval**: Add chat message proposal action for "Review Generated Dataset".
**P10-L-7 Dataset Version Export**: Handled natively (no code needed).
**P10-L-8 RAG Integration**: Handled natively (no code needed).
**P10-L-9 Training Eligibility Integration**: Handled natively (no code needed).
**P10-L-10 End-to-End Runtime Verification**: Master test suite + manual MOCK provider test.

===========================================================
19. TEST PLAN
===========================================================
1. Provider configuration save inside Chat UI.
2. API key encryption and non-disclosure validation.
3. Chat intent detection for "Generate 100 records".
4. MB-16 session creation from Chat proposal.
5. Job progress polling UI.
6. 10,000-record MOCK PROVIDER test execution (No external paid APIs).
7. Duplicate detection execution.
8. Dataset preview rendering in Chat.
9. Human approval proposal state transition.
10. RAG ingestion validation post-approval.

===========================================================
20. RISK REGISTER
===========================================================
- **UX Complexity**: Embedding a complex left-menu into the floating widget mode may crowd the UI.
- **Provider Timeouts**: External LLM providers will inevitably fail during 10,000-record generations. MB-16's retry logic must be robust.

===========================================================
21. BEFORE/AFTER CALL GRAPH
===========================================================
**Before**:
Chat -> `AdminAssistantChatService` -> (Can only answer questions about datasets)

**After**:
Chat -> `AdminAssistantChatService` -> `propose_synthetic_dataset_generation()` -> `MiniBrainMultimodalDatasetGeneratorService.create_session()` -> `execute_pipeline()` -> Progress polling -> Human Review Proposal.

===========================================================
22. FINAL READINESS SCORE
===========================================================
- Existing Backend Readiness: 100% (MB-16 and Provider System fully support this natively).
- Existing Frontend Readiness: 10% (Requires major Chat UI additions).
- Overall Integration Readiness: READY FOR P10-L CONTROLLED IMPLEMENTATION.

============================================================
PROVIDER DATASET LIFECYCLE — PRE-IMPLEMENTATION FORENSIC VERDICT
============================================================

ADMIN UPLOAD → DATASET       = EXISTING & WORKING (100%)
PROVIDER → DATASET            = EXISTING BUT UI NOT CONNECTED TO CHAT (MB-16 works via Dashboard)
DATASET → VALIDATION          = EXISTING & WORKING (100%)
VALIDATION → HUMAN REVIEW     = EXISTING & WORKING (100%)
APPROVAL → DATASET VERSION    = EXISTING & WORKING (100%)
DATASET → RAG                 = EXISTING & WORKING (100%)
FEEDBACK → LEARNING           = EXISTING & WORKING (100%)
DATASET → TRAINING            = EXISTING & WORKING (Gate Locked)
TRAINING → CANDIDATE          = EXISTING & WORKING (Gate Locked)
CANDIDATE → EVALUATION        = EXISTING & WORKING
EVALUATION → PROMOTION        = EXISTING & WORKING (Gate Locked)

ADMIN ASSISTANT CHAT          = PARTIAL (Missing Generation Intent)
48 TOOL ROUTER                = PARTIAL (Requires New Tool)
PROVIDER ROUTING              = EXISTING & WORKING (100%)
FRONTEND ↔ BACKEND            = MISSING (Requires Chat Settings UI)

CRITICAL GAPS                 = 0 (Safe to proceed)
HIGH GAPS                     = 0
MEDIUM GAPS                   = 1 (Chat UI Left Menu Required)
LOW GAPS                      = 0

FINAL CLASSIFICATION          = BACKEND IMPLEMENTED — FRONTEND CHAT NOT INTEGRATED

PRODUCTION STATE              = UNTOUCHED & LOCKED
TRAINING EXECUTED             = FALSE
MODEL WEIGHTS MUTATED         = FALSE
PRODUCTION ACTIVATION         = FALSE

DO NOT MODIFY SOURCE CODE.
DO NOT TRAIN.
DO NOT DEPLOY.
DO NOT PROMOTE.
AUDIT ONLY.
