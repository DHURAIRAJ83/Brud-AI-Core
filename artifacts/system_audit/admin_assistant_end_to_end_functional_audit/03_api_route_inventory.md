# 03 API ROUTE INVENTORY AUDIT

- Total Route Modules Registered: 94 route files under `backend/api/routes/`.
- Total Exposed Endpoints: ~140 endpoints across dataset, RAG, training, candidate, governance, and admin assistant domains.
- Endpoint Health & Connectivity:
  - `/api/admin/assistant/overview`: CONNECTED (Reads DB counts & pending work).
  - `/api/admin/assistant/governance-status`: CONNECTED (Reads `EnterpriseGovernanceDashboardContract`).
  - `/api/admin/assistant/proposals`: CONNECTED (Reads/writes `AdminApprovalRepository`).
  - `/api/admin/assistant/upload`: CONNECTED (Uploads PDFs/datasets via `DocumentService`/`ImportService`).
  - `/api/admin/mini-brain/llm-runtime/chat`: CONNECTED (LLM widget chat).
  - `/api/admin/mini-brain/llm-runtime/grounded-chat`: CONNECTED (RAG vector grounded chat).
