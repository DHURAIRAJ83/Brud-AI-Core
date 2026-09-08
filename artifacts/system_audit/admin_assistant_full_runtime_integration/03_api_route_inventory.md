# 03 API ROUTE INVENTORY AUDIT

- Total Route Modules Registered: 94 route files under `backend/api/routes/`.
- Total Exposed Endpoints: ~140 endpoints across dataset, RAG, training, candidate, governance, and admin assistant domains.
- Endpoint Security:
  - `/api/admin/assistant/overview`: CONNECTED (Requires Admin Session/Auth).
  - `/api/admin/assistant/governance-status`: CONNECTED (Requires Admin Session/Auth).
  - `/api/admin/assistant/chat`: CONNECTED (Invokes `AdminAssistantChatService` with 48 tools & proposals).
  - `/api/admin/assistant/proposals`: CONNECTED (Reads/writes `AdminApprovalRepository`).
  - `/api/admin/assistant/upload`: CONNECTED (Uploads PDFs/datasets via `DocumentService`/`ImportService`).
  - `/api/admin/mini-brain/llm-runtime/chat`: CONNECTED (LLM widget chat).
  - `/api/admin/mini-brain/llm-runtime/grounded-chat`: CONNECTED (RAG vector grounded chat).
