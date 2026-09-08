# 17 BACKEND-ONLY FEATURES REGISTRY

- Tool Agent Orchestration: The 48 backend tool wrappers in `admin_assistant_tools.py` are callable via `AdminAssistantChatService.send_message()` (`POST /api/admin/assistant/chat`), while the floating widget chat calls `/api/admin/mini-brain/llm-runtime/chat` directly.
