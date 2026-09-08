# 19 CHANGES MADE REPORT

- Updated `apps/admin-dashboard/src/components/chat/ChatPanel.jsx`:
  - Imported `sendAssistantChatMessage` from `../../services/api.js`.
  - Updated standard chat message dispatch to route through `sendAssistantChatMessage({ message: trimmed, page_id: 'overview', mode: 'guide' })`.
  - Added clean fallback to `lrChat` if `sendAssistantChatMessage` encounters an exception.
  - Added automatic execution of `onNavigate` if response contains `navigation_target`.
