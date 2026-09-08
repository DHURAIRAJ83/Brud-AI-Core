# 02 FRONTEND → BACKEND TRACE REPORT

1. **Dashboard Overview & Guidance**:
   - `AdminAssistantPage.jsx` -> `assistantOverview()` -> `GET /api/admin/assistant/overview` -> `AdminAssistantService.dashboard_overview()` -> executes SQLite counts on legacy tables (`dataset_sources`, `dataset_records`, `training_jobs`, `model_registry`, `user_feedback`, `admin_approvals`).
   - Does NOT query P1–P10G canonical governance contracts or activation blocker repositories.

2. **Chat Messages (Widget & Chat Panel)**:
   - `ChatPanel.jsx` -> `send()` -> `lrChat()` -> `POST /api/admin/mini-brain/llm-runtime/chat` -> LLM generation runtime.
   - Does NOT query P1–P10G governance contracts or token validation gates.

3. **Proposals & Action Allowlist**:
   - `AdminAssistantPage.jsx` -> `createAssistantProposal()` -> `POST /api/admin/assistant/proposals` -> `propose_with_governance()` -> `AdminApprovalRepository` -> SQLite `admin_approvals` table.
   - Only basic dataset/source review action types allowlisted. P1–P10G authorization tokens cannot be issued or approved via this UI.

4. **File Upload**:
   - `ChatPanel.jsx` -> `assistantUpload()` -> `POST /api/admin/assistant/upload` -> `DocumentService` / `ImportService`.
