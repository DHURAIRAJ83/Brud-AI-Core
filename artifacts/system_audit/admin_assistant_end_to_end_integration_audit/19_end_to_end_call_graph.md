# 19 END-TO-END CALL GRAPH DIAGRAM

```text
[ADMIN DASHBOARD USER]
       │
       ├──> AdminAssistantPage.jsx ──[GET /api/admin/assistant/governance-status]──> admin_assistant.py ──> AdminAssistantService ──> EnterpriseGovernanceDashboardContract [✓ CONNECTED]
       │
       ├──> ChatPanel.jsx (KB OFF) ──[POST /api/admin/mini-brain/llm-runtime/chat]──> mini_brain_llm_runtime.py ──> LLM Generation Runtime [✓ CONNECTED - CHAT ONLY]
       │
       ├──> ChatPanel.jsx (KB ON)  ──[POST /api/admin/mini-brain/llm-runtime/grounded-chat]──> mini_brain_llm_runtime.py ──> RagRepository Vector Store [✓ CONNECTED - RAG GROUNDED]
       │
       ├──> ChatPanel.jsx (Upload) ──[POST /api/admin/assistant/upload]──> admin_assistant.py ──> DocumentService / ImportService [✓ CONNECTED]
       │
       └──> Proposal Form ──────────[POST /api/admin/assistant/proposals]──> admin_assistant_write_governance.py ──> AdminApprovalRepository [✓ CONNECTED - FAIL-CLOSED]
```
