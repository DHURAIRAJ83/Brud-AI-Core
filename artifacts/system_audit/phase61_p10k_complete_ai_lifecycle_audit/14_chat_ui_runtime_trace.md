# 14 CHAT UI RUNTIME TRACE

- Chat Component: `ChatPanel.jsx` / `AdminAssistantWidget.jsx`.
- Standard Assistant Messages: Routed through `sendAssistantChatMessage({ message, page_id: 'overview', mode: 'guide' })` (`POST /api/admin/assistant/chat`).
- Grounded RAG Messages: Routed through `sendMiniBrainGroundedMessage(sessionId, message, profileId)` (`POST /api/admin/mini-brain/llm-runtime/grounded-chat`).
- File Uploads: Routed through `assistantUpload(file)` (`POST /api/admin/assistant/upload`).
