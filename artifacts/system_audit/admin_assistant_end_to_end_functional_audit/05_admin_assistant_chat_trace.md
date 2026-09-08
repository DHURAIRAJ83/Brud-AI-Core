# 05 ADMIN ASSISTANT CHAT TRACE AUDIT

- User Input Flow: `ChatPanel.jsx` -> `send()` -> `sendMiniBrainWidgetMessage()` -> `POST /api/admin/mini-brain/llm-runtime/chat`.
- RAG Knowledge Base Toggle Flow: Checking "Use Knowledge Base" calls `POST /api/admin/mini-brain/llm-runtime/grounded-chat` -> retrieves top vector chunks from `RagRepository` -> constructs RAG context prompt with citations -> returns grounded LLM answer.
- Tool Invocation Flow: `AdminAssistantChatService` with 48 backend tools exists in Python (`backend/services/admin_assistant_chat_service.py`), but the frontend floating widget invokes `/mini-brain/llm-runtime/chat` directly. Thus tool execution is `BACKEND_ONLY / UI_NOT_INVOKING`.
