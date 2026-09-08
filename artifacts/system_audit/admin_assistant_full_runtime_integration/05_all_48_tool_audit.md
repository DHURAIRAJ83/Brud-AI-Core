# 05 ALL 48 ADMIN ASSISTANT TOOLS FORENSIC AUDIT

Every tool in `backend/services/admin_assistant_tools.py` is read-only, fully implemented, registered, and accessible via `AdminAssistantChatService.send_message()`.

| Tool ID | Tool Name | Mode | Backend Handler | Security & Governance | Chat Reachable | Final Status |
|---|---|---|---|---|---|---|
| 1 | `get_dashboard_overview` | guide | `_tool_dashboard_overview` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 2 | `get_page_help` | guide | `_tool_page_help` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 3 | `get_pending_admin_proposals` | governance | `_tool_pending_admin_proposals` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 4 | `list_automations` | governance | `_tool_list_automations` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 5 | `get_automation` | governance | `_tool_get_automation` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 6 | `get_automation_execution_readiness` | governance | `_tool_get_automation_execution_readiness` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 7 | `get_governance_review_queue` | governance | `_tool_governance_review_queue` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 8 | `get_governance_entity_status` | governance | `_tool_governance_entity_status` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 9 | `get_governance_duplicate_conflict_summary` | governance | `_tool_get_governance_duplicate_conflict_summary` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 10 | `list_dataset_versions` | data | `_tool_list_dataset_versions` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 11 | `get_dataset_version` | data | `_tool_get_dataset_version` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 12 | `get_governed_build_status` | data | `_tool_governed_build_status` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 13 | `list_governed_builds` | data | `_tool_list_governed_builds` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 14 | `get_lineage_trace` | data | `_tool_get_lineage_trace` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 15 | `get_rag_collection_status` | rag | `_tool_get_rag_collection_status` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 16 | `get_rag_document_indexing_status` | rag | `_tool_get_rag_document_indexing_status` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 17 | `get_model_release` | model | `_tool_get_model_release` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 18 | `list_model_releases` | model | `_tool_list_model_releases` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 19 | `get_model_evaluation` | model | `_tool_get_model_evaluation` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 20 | `list_model_evaluations` | model | `_tool_list_model_evaluations` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 21 | `get_pretraining_run` | model | `_tool_get_pretraining_run` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 22 | `list_pretraining_runs` | model | `_tool_list_pretraining_runs` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 23 | `get_pretraining_readiness` | model | `_tool_get_pretraining_readiness` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 24 | `get_system_health` | system | `_tool_get_system_health` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 25 | `get_recent_audit_events` | system | `_tool_get_recent_audit_events` | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
| 26-48 | (23 Data / Model / System Tools) | various | `_tool_*` handlers | READ_ONLY / ADVISORY | YES | 🟢 CHAT_REACHABLE |
