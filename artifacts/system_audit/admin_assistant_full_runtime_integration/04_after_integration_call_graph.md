# 04 AFTER INTEGRATION CALL GRAPH

```text
[BROWSER CHAT WIDGET / PANEL]
       │
       ├──> KB Toggle ON  ──[POST /mini-brain/llm-runtime/grounded-chat]──> mini_brain_llm_runtime.py ──> RagRepository Vector Search + Citations [✓ E2E CONNECTED]
       │
       └──> KB Toggle OFF ──[POST /api/admin/assistant/chat]──────────────> admin_assistant.py ──> AdminAssistantChatService ──> 48 Tools / Intent Router / Proposals [✓ E2E CONNECTED]
```
