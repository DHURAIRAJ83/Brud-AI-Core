# 05 ADMIN ASSISTANT CHAT INTEGRATION TRACE

- Assistant Chat Endpoint: `/api/admin/assistant/chat` (POST) routes directly to `AdminAssistantChatService.send_message()`.
- Intent Classifier: `classify_intent` handles greeting, help, pending_work, navigation, provider lookup, dataset search, sample import, RAG sandbox help, and chat proposals (`_maybe_propose_chat_action`).
- Tool Orchestration: Calls `run_tool` deterministically for `get_page_help`, `get_dashboard_overview`, `get_provider_connection_status`, `list_dataset_search_sessions`, etc.
- Grounded RAG Chat: Checked via "Use Knowledge Base" toggle calling `/api/admin/mini-brain/llm-runtime/grounded-chat` -> retrieves `RagRepository` vector chunks and appends citations (`LEVEL 5 - E2E VERIFIED`).
