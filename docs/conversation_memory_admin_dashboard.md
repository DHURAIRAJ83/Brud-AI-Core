# Conversation Memory Admin Dashboard

`apps/admin-dashboard/src/pages/ConversationMemoryPage.jsx`, wired
into `App.jsx` (`active === 'Conversation & Memory'`) and
`Sidebar.jsx` (nav item placed after "Knowledge & RAG"; footer phase
tag updated to "Phase 17 · Conversation memory").

## Tabs (14)

Overview, Memory Policies, Sessions, Session Turns, Summaries,
Consent, Memory Items, Memory Versions, Memory Retrieval, Context
Orchestration, Grounded Conversation Lab, Privacy & Deletion,
Evaluation, Reproducibility.

Structural pattern mirrors `RagPage.jsx` exactly: tab navigation,
`state`/`panelError` React state, a left-side data list plus a
right-side tabbed detail panel, and `StatusCard` components on the
Overview tab.

## Required disclaimers (always rendered, verbatim)

- Page-level, always visible: *"Conversation memory is consent-aware,
  purpose-bound, inspectable, and deletable. It must not be treated as
  hidden permanent profiling."*
- Grounded Conversation Lab tab specifically: *"Admin-only conversation
  diagnostic. This is not the public chatbot."*

## API integration

`apps/admin-dashboard/src/services/api.js` gained ~60 functions under
`const CM = '/api/admin/conversation-memory'`, covering every route in
`docs/conversation_memory_api_and_cli.md`.

## Build verification

`cd apps/admin-dashboard && npm run build` — succeeded. `cd
apps/chatbot && npm run build` — succeeded unchanged (placeholder chat
UI untouched by this phase).
