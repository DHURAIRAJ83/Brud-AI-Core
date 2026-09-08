# 10 ADMIN ASSISTANT CHAT TRACE

- Standard Assistant Chat: `ChatPanel.jsx` routes non-grounded assistant messages through `sendAssistantChatMessage` (`POST /api/admin/assistant/chat`) -> `AdminAssistantChatService` (intent classification, 48 read-only tools, pending-work guidance, proposal creation).
- Grounded RAG Chat: Routed through `sendMiniBrainGroundedMessage` when KB toggle is ON (`LEVEL 5 - PROVEN`).
