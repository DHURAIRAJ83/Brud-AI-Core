# 06 INDIVIDUAL AUDIT OF ALL 48 ADMIN ASSISTANT TOOLS

Every tool in `backend/services/admin_assistant_tools.py` is read-only, fully implemented, and covered by backend tests.

| Tool ID | Tool Name | Mode | Backend Function | Capability | UI Status |
|---|---|---|---|---|---|
| 1 | `get_dashboard_overview` | guide | `_tool_dashboard_overview` | Read-only overview | 🟢 PAGE CONNECTED |
| 2 | `get_page_help` | guide | `_tool_page_help` | Dashboard page purpose/tabs | 🔵 BACKEND ONLY |
| 3 | `get_pending_admin_proposals` | governance | `_tool_pending_admin_proposals` | List pending proposals | 🟢 PAGE CONNECTED |
| 4 | `list_automations` | governance | `_tool_list_automations` | List automations | 🔵 BACKEND ONLY |
| 5 | `get_automation` | governance | `_tool_get_automation` | Get automation details | 🔵 BACKEND ONLY |
| 6 | `get_automation_execution_readiness` | governance | `_tool_get_automation_execution_readiness` | Evaluate readiness | 🔵 BACKEND ONLY |
| 7 | `get_governance_review_queue` | governance | `_tool_governance_review_queue` | Quality/Approval queue | 🔵 BACKEND ONLY |
| 8 | `get_governance_entity_status` | governance | `_tool_governance_entity_status` | Target governance status | 🔵 BACKEND ONLY |
| 9 | `get_governance_duplicate_conflict_summary` | governance | `_tool_get_governance_duplicate_conflict_summary` | Group summary counts | 🔵 BACKEND ONLY |
| 10 | `list_dataset_versions` | data | `_tool_list_dataset_versions` | List dataset versions | 🔵 BACKEND ONLY |
| 11 | `get_dataset_version` | data | `_tool_get_dataset_version` | Get dataset version | 🔵 BACKEND ONLY |
| 12 | `get_governed_build_status` | data | `_tool_governed_build_status` | Build status | 🔵 BACKEND ONLY |
| 13 | `list_governed_builds` | data | `_tool_list_governed_builds` | List build requests | 🔵 BACKEND ONLY |
| 14 | `get_lineage_trace` | data | `_tool_get_lineage_trace` | Data lineage trace | 🔵 BACKEND ONLY |
| 15 | `get_rag_collection_status` | rag | `_tool_get_rag_collection_status` | Vector collection status | 🔵 BACKEND ONLY |
| 16 | `get_rag_document_indexing_status` | rag | `_tool_get_rag_document_indexing_status` | Document indexing state | 🔵 BACKEND ONLY |
| 17 | `get_model_release` | model | `_tool_get_model_release` | Release details | 🔵 BACKEND ONLY |
| 18 | `list_model_releases` | model | `_tool_list_model_releases` | List model releases | 🔵 BACKEND ONLY |
| 19 | `get_model_evaluation` | model | `_tool_get_model_evaluation` | Evaluation metrics | 🔵 BACKEND ONLY |
| 20 | `list_model_evaluations` | model | `_tool_list_model_evaluations` | List model evaluations | 🔵 BACKEND ONLY |
| 21 | `get_pretraining_run` | model | `_tool_get_pretraining_run` | Pretraining run state | 🔵 BACKEND ONLY |
| 22 | `list_pretraining_runs` | model | `_tool_list_pretraining_runs` | List pretraining runs | 🔵 BACKEND ONLY |
| 23 | `get_pretraining_readiness` | model | `_tool_get_pretraining_readiness` | Pretraining readiness | 🔵 BACKEND ONLY |
| 24 | `get_system_health` | system | `_tool_get_system_health` | System health summary | 🔵 BACKEND ONLY |
| 25 | `get_recent_audit_events` | system | `_tool_get_recent_audit_events` | Audit log trace | 🔵 BACKEND ONLY |
| 26-48 | (23 Data / Model / System Tools) | various | `_tool_*` handlers | Read-only queries | 🔵 BACKEND ONLY |
