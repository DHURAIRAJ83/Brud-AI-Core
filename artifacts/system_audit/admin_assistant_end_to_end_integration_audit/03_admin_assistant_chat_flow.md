# 03 ADMIN ASSISTANT CHAT FLOW FORENSIC AUDIT

- **User Message Dispatch**:
  `ChatPanel.jsx` -> `send()` -> calls `sendMiniBrainWidgetMessage(sessionId, message)` in `api.js` -> `POST /api/admin/mini-brain/llm-runtime/chat`.
- **Backend Route Execution**:
  `backend/api/routes/mini_brain_llm_runtime.py` receives request -> dispatches to LLM generation service or local model.
- **Tool Orchestrator Audit**:
  - The tool orchestrator (`AdminAssistantChatService` in `backend/services/admin_assistant_chat_service.py`) and tool registry (`READ_ONLY_TOOLS` in `admin_assistant_tools.py`) ARE FULLY IMPLEMENTED in Python.
  - HOWEVER, the Admin Assistant Chat UI widget was switched to `/api/admin/mini-brain/llm-runtime/chat` (comment in `api.js` line 784).
  - Therefore, free-form chat queries in the UI widget bypass tool execution and act as **Pure Generic LLM Chat / Grounded RAG Chat**.
- **Chat Classification**:
  - Without KB Toggle: **A. Pure Generic LLM Chat**.
  - With KB Toggle: **B. RAG Grounded Chat**.
  - Tool Invocation via Chat: **C. Tool-using agent is BACKEND_ONLY (UI_NOT_INVOKING)**.
