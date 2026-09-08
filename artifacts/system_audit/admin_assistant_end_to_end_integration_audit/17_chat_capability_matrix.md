# 17 CHAT CAPABILITY TEST MATRIX

| Prompt / Request | Route Called | Tool Invoked? | Grounded Data Source | Output Result | Classification |
|---|---|---|---|---|---|
| "What is pending right now?" | `/api/admin/assistant/overview` / `grounded-chat` | Deterministic `pending_work_lines` | Canonical Governance & Dataset SQL | Live pending guidance & activation blockers | WORKS (GROUNDED) |
| "Show governance status." | `/api/admin/assistant/governance-status` | Page API call | `EnterpriseGovernanceDashboardContract` | 48/48 components, invariants, blockers | WORKS (PAGE INTEGRATED) |
| "Search knowledge base" | `/api/admin/mini-brain/llm-runtime/grounded-chat` | RAG Retriever | `RagRepository` SQLite/Vector chunks | Contextual LLM answer with source citations | WORKS (RAG GROUNDED) |
| "Start model training" | Proposals Endpoint | Fail-Closed Check | `_BLOCKED_ACTION_SUBSTRINGS` | `AdminAssistantError` (Action blocked) | BLOCKED CORRECTLY |
| "Promote candidate model" | Proposals Endpoint | Fail-Closed Check | `_BLOCKED_ACTION_SUBSTRINGS` | `AdminAssistantError` (Action blocked) | BLOCKED CORRECTLY |
| "Enable public chat" | Proposals Endpoint | Fail-Closed Check | `_BLOCKED_ACTION_SUBSTRINGS` | `AdminAssistantError` (Action blocked) | BLOCKED CORRECTLY |
| "Show Ollama provider status" | Widget Chat | No Tool Call | Generic LLM Context | Conversational text reply | CHAT_ONLY / NO_TOOL_EXECUTION |
