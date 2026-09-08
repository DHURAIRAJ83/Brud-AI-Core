# 11 MEMORY & FEEDBACK TRACE

- User Feedback: Ratings (`helpful`, `not_helpful`, `incorrect_guidance`, `action_failed`) and comments stored via `POST /api/admin/assistant/feedback` (`END_TO_END_CONNECTED`).
- Conversation Memory: Multi-turn session history stored in SQLite `conversation_memory` table and viewable via `ConversationMemoryPage.jsx` (`END_TO_END_CONNECTED`).
