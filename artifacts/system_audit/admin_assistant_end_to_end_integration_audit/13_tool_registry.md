# 13 TOOL REGISTRY AUDIT

- Registered Tools in `admin_assistant_tools.py`: 48 read-only tools (`get_dashboard_overview`, `get_page_help`, `get_pending_admin_proposals`, `list_dataset_versions`, `get_dataset_version`, `get_governance_entity_status`, etc.).
- Invocation Path: Executed via `AdminAssistantChatService.send_message()`.
- Widget Switch Impact: Because the widget calls `/api/admin/mini-brain/llm-runtime/chat` directly, these 48 backend tools are `BACKEND_ONLY / UI_NOT_INVOKING` from the floating chat widget, though fully functional via API.
