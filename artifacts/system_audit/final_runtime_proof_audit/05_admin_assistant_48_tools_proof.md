# 05 ADMIN ASSISTANT 48-TOOL ROUTER PROOF

- API Route: `POST /api/admin/assistant/chat` routes to `AdminAssistantChatService.send_message()`.
- Deterministic Tool Router: `run_tool` executes read-only query handlers (`get_dashboard_overview`, `get_page_help`, `list_dataset_versions`, `get_governance_entity_status`, etc.).
- Proposal Creation Safety: Creating actionable proposals calls `propose_chat_action()`. Safe proposal types (`dataset_record_review`) create pending proposals for Admin review; privileged proposal types (`execute_model_training`) return fail-closed blocked error (`CONNECTED & FAIL-CLOSED`).
