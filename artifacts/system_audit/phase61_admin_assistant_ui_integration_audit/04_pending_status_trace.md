# 04 "WHAT IS PENDING RIGHT NOW?" TRACE REPORT

- **Chat Widget Behavior**: Clicking `"What is pending right now?"` dispatches `send("What is pending right now?")` to `POST /api/admin/mini-brain/llm-runtime/chat`. The LLM generates a general conversational text response.
- **Dedicated Page Behavior**: The 'Guidance' tab on `AdminAssistantPage.jsx` calls `assistantOverview()` -> `GET /api/admin/assistant/overview` -> `AdminAssistantService.dashboard_overview()`.
- **Backend Source of Truth**: Queries SQLite counts on `dataset_records` (where `status='pending_review'`) and `admin_approvals` (where `status='pending'`).
- **Verdict**: Neither the chat widget nor the Admin Assistant page queries the P1–P10G canonical governance state, token inventory, or final activation blockers.
