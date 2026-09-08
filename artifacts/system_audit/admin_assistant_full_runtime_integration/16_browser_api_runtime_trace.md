# 16 BROWSER / API RUNTIME TRACE

```text
BROWSER (ChatPanel.jsx)
       ↓
API CLIENT (api.js - sendAssistantChatMessage)
       ↓
FASTAPI ROUTE (POST /api/admin/assistant/chat)
       ↓
BACKEND SERVICE (AdminAssistantChatService.send_message)
       ↓
TOOL ROUTER (run_tool / classify_intent / pending_work_lines)
       ↓
CANONICAL ENGINE (EnterpriseGovernanceDashboardContract / DatasetAdminRepository)
       ↓
DATABASE / PERSISTENCE (SQLite brud_ai.db)
       ↓
RESPONSE payload ({ answer, intent, status })
       ↓
UI RENDERING (ChatPanel message list) [✓ LEVEL 5 E2E VERIFIED]
```
