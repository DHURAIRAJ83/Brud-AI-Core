# 04 API ROUTE COVERAGE AUDIT

- Total Admin API Routes Registered: 94 route modules in `backend/api/routes/`.
- Frontend API Client (`api.js`): Exposes ~120 API wrapper functions.
- Connected Routes:
  - `/api/admin/assistant/overview` (CONNECTED)
  - `/api/admin/assistant/governance-status` (CONNECTED)
  - `/api/admin/assistant/proposals` (CONNECTED)
  - `/api/admin/assistant/upload` (CONNECTED)
  - `/api/admin/mini-brain/llm-runtime/chat` (CONNECTED)
  - `/api/admin/mini-brain/llm-runtime/grounded-chat` (CONNECTED)
  - `/api/admin/datasets` (CONNECTED to DatasetsPage)
  - `/api/admin/documents` (CONNECTED to DocumentsPage)
  - `/api/admin/rag` (CONNECTED to RagPage)
  - `/api/admin/base-training` (CONNECTED to BaseTrainingPage)
  - `/api/admin/candidates` (CONNECTED to ModelRegistryPage)
  - `/api/admin/governance` (CONNECTED to GovernancePage)
- Orphan / Backend-Only Routes:
  - `/api/admin/assistant/chat` (Tool-using chat endpoint - UI uses mini-brain chat instead).
