# 01 ADMIN ASSISTANT UI INVENTORY

- Baseline Commit: `df054cb100b58d99acf42a72d18dcbcb7dcbd5f8`
- Admin Assistant Window / Widget: [`apps/admin-dashboard/src/components/admin-assistant/AdminAssistantWidget.jsx`](file:///home/dhurai/Projects/brud-ai/apps/admin-dashboard/src/components/admin-assistant/AdminAssistantWidget.jsx)
- Admin Assistant Page: [`apps/admin-dashboard/src/pages/AdminAssistantPage.jsx`](file:///home/dhurai/Projects/brud-ai/apps/admin-dashboard/src/pages/AdminAssistantPage.jsx)
- Chat Panel Component: [`apps/admin-dashboard/src/components/chat/ChatPanel.jsx`](file:///home/dhurai/Projects/brud-ai/apps/admin-dashboard/src/components/chat/ChatPanel.jsx)
- Assistant Modes (Tabs): Defined in `MODES` array in `AdminAssistantWidget.jsx` lines 16–23 (`guide`, `data`, `governance`, `rag`, `model`, `system`).
- Reply Language Selector: Defined in `LANGUAGE_OPTIONS` array in `AdminAssistantWidget.jsx` lines 29–34 and `AdminAssistantPage.jsx` lines 19–24 (`tamil`, `english`, `tanglish`, `auto`).
- Use Knowledge Base Toggle: Checkbox in `ChatPanel.jsx` lines 223–230.
- Suggestions / Prompts: Defined in `SUGGESTIONS` array in `AdminAssistantWidget.jsx` line 36 (`"How do I use this page?"`, `"What is pending right now?"`).
- PDF / File Attachment Handler: `handleFileUpload` in `ChatPanel.jsx` lines 147–175 calling `assistantUpload` (`/api/admin/assistant/upload`).
- Chat Input & Send Action: `send()` function in `ChatPanel.jsx` lines 98–145 calling `lrChat` or `sendMiniBrainGroundedMessage`.
- Regenerate Action: `regenerate()` function in `ChatPanel.jsx` lines 180–183.
