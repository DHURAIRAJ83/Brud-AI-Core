# 19 MASTER END-TO-END CALL GRAPH DIAGRAM

```text
[ADMIN DASHBOARD USER]
       │
       ├──> AdminAssistantPage.jsx ──[GET /api/admin/assistant/governance-status]──> admin_assistant.py ──> EnterpriseGovernanceDashboardContract [🟢 LEVEL 5 VERIFIED]
       │
       ├──> ChatPanel.jsx (KB OFF) ──[POST /api/admin/assistant/chat]──────────────> admin_assistant.py ──> AdminAssistantChatService ──> 48 Tools [🟢 LEVEL 5 VERIFIED]
       │
       ├──> ChatPanel.jsx (KB ON)  ──[POST /mini-brain/llm-runtime/grounded-chat]──> mini_brain_llm_runtime.py ──> RagRepository Vector Search [🟢 LEVEL 5 VERIFIED]
       │
       ├──> Upload Button ─────────[POST /api/admin/assistant/upload]─────────────> admin_assistant.py ──> DocumentService / ImportService [🟢 LEVEL 5 VERIFIED]
       │
       └──> Proposal Action ───────[POST /api/admin/assistant/proposals]──────────> admin_assistant_write_governance.py ──> AdminApprovalRepository [🟢 LEVEL 5 FAIL-CLOSED]
```
