# 02 FRONTEND INTEGRATION AUDIT

- **Admin Assistant Dedicated Page** (`AdminAssistantPage.jsx`):
  - Calls `assistantOverview()` -> `GET /api/admin/assistant/overview`.
  - Calls `getGovernanceStatus()` -> `GET /api/admin/assistant/governance-status`.
  - Calls `assistantActions()` -> `GET /api/admin/assistant/actions`.
  - Calls `assistantProposals()` -> `GET /api/admin/assistant/proposals`.
  - **Verdict**: `END_TO_END_CONNECTED` for Guidance, Governance Status, and Proposals.

- **Admin Assistant Floating/Docked Widget** (`AdminAssistantWidget.jsx`):
  - Calls `assistantPages()` -> `GET /api/admin/assistant/pages`.
  - Calls `sendMiniBrainWidgetMessage()` -> `POST /api/admin/mini-brain/llm-runtime/chat`.
  - Calls `assistantUpload()` -> `POST /api/admin/assistant/upload`.
  - **Verdict**: `CHAT_ONLY / NO_TOOL_EXECUTION` for chat prompts; `END_TO_END_CONNECTED` for PDF/dataset upload.
