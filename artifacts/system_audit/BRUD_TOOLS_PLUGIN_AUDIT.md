# BRUD AI — TOOLS, PLUGINS & AGENTS AUDIT (WS09)
**Audit Date:** 2026-09-07

---

## DETERMINISTIC TOOLS (Phase 15+)

### Registry
- **File:** `backend/services/deterministic_tool_registry.py` (4.5 KB)
- **Function:** `get_tool_descriptor(name)` — returns tool metadata
- **Available tools:** calculator, unit_conversion, date_time_arithmetic
- **Status:** ACTIVE

### Execution
- **File:** `backend/services/deterministic_tool_execution_service.py` (10 KB)
- **Caller:** `PublicChatRoutingService`
- **Governance:** Tool permissions per scope
- **Status:** ACTIVE

### Tool Gateway (core_model)
| File | Status | Purpose |
|------|--------|---------|
| `core_model/tool_gateway/input_extraction.py` | ACTIVE | Extract tool inputs from text |
| `core_model/tool_gateway/tool_selection.py` | ACTIVE | Select appropriate tool |
| `core_model/tool_gateway/tool_result_text.py` | ACTIVE | Format tool results |
| `core_model/tool_gateway/mcp_contract.py` | ACTIVE | ToolInvocationRequest, PermissionContext |

---

## MINI BRAIN PLUGIN SYSTEM

### Plugin Governance
- **File:** `backend/services/mini_brain_plugin_governance_service.py` (36 KB)
- **Core:** `core_model/mini_brain/plugin_governance/`
- **Features:** Plugin registration, permissions, execution tokens
- **Status:** ACTIVE (framework ready, no plugins ship in current phase)

### Plugin Runtime
- **File:** `backend/services/mini_brain_plugin_runtime_service.py` (29 KB)
- **Core:** `core_model/mini_brain/plugin_runtime/`
- **Status:** ACTIVE (execute_for_admin_assistant() is the gated entrypoint)

---

## ADMIN ASSISTANT TOOLS

- **File:** `backend/services/admin_assistant_tools.py` (119 KB)
- This is the primary tool execution layer for Admin Assistant (Phase 8)
- Contains read-only tools for dashboard queries
- **Status:** ACTIVE
- **Note:** 119 KB is very large — high maintenance risk

---

## WEB SEARCH

- **File:** `backend/services/web_search_provider.py` (13 KB)
- Providers: `WikipediaSearchProvider`, `ConfigurableSearchApiProvider`
- Cached: `web_search_cache.py`
- Trusted Web: `trusted_web_answer_service.py` (22 KB)
- **Status:** ACTIVE

### Trusted Web Policy
- **File:** `backend/services/trusted_web_policy_service.py` (5.4 KB)
- Governs which web sources are trusted
- **Status:** ACTIVE

---

## TOOL EXECUTION GOVERNANCE

| Layer | File | Status |
|-------|------|--------|
| Public tools | `deterministic_tool_execution_service.py` | ACTIVE |
| Admin tools (Phase 8) | `admin_assistant_tools.py` | ACTIVE |
| Mini Brain plugins | `mini_brain_plugin_governance_service.py` | ACTIVE |
| Tool permissions | `mini_brain_plugin_governance_service.py` | ACTIVE |
| Execution tokens | `mini_brain_plugin_governance_service.py` | ACTIVE |

---

## POSSIBLE DUPLICATE: TWO TOOL SYSTEMS

| System | Files | Callers | Status |
|--------|-------|---------|--------|
| Deterministic Tools (Phase 15) | `deterministic_tool_registry.py`, `deterministic_tool_execution_service.py` | PublicChatRoutingService | ACTIVE |
| Mini Brain Plugin System | `mini_brain_plugin_governance_service.py`, `mini_brain_plugin_runtime_service.py` | MiniBrainLlmRuntimeService | ACTIVE |
| Admin Assistant Tools | `admin_assistant_tools.py` | AdminAssistantChatService | ACTIVE |

**VERDICT:** Three separate tool systems exist:
1. Public deterministic tools (calculator, unit conversion, datetime)
2. Admin assistant tools (dashboard read queries)
3. Mini Brain plugin system (extensible plugins for MB-28)

These are D3 (PARTIAL DUPLICATE) — overlapping in concept but different scopes. No single unified tool registry exists.

---

## FINDINGS

1. **COMPLETE:** Deterministic tools (calculator, unit_conversion, datetime) active for public chat
2. **COMPLETE:** Admin assistant tools (read-only dashboard queries) active
3. **COMPLETE:** Mini Brain plugin framework (governance + runtime) active
4. **MISSING:** Unified tool registry across all three systems
5. **RISK:** admin_assistant_tools.py at 119 KB is a maintenance monolith
6. **ACTIVE:** MCP contract defined in tool_gateway

---
*WS09 Complete*
