# Master Brud AI System Audit — 08: Tools & Agent Architecture Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code in `deterministic_tool_registry.py` and `admin_assistant_tools.py`)  

---

## 1. System Tool Inventory

Brud AI has two distinct tool execution environments:
1. **Public Chat Tools (Deterministic):** Built for the public chatbot.
2. **Admin Assistant Tools (Read-Only & Governed):** Built for the system admin console.

### A. Public Chat Deterministic Tools

| Tool Name | Purpose | Caller | Permissions | Input Validation | Execution Capability | Human Approval Required? |
|---|---|---|---|---|---|---|
| **`calculator`** | Deterministic arithmetic (+, -, *, /, %, powers, decimals) | `PublicChatRoutingService` | `public_safe_deterministic` | Max 100 chars, regex | Fully Automated (In-process Python) | ❌ No (Safe, deterministic) |
| **`unit_conversion`** | Metric/imperial conversions across 8 physical categories | `PublicChatRoutingService` | `public_safe_deterministic` | Strict unit allowlist | Fully Automated (In-process Python) | ❌ No (Safe, deterministic) |
| **`date_time_arithmetic`** | ISO-8601 calendar arithmetic (add days/weeks, diff) | `PublicChatRoutingService` | `public_safe_deterministic` | ISO date regex | Fully Automated (In-process Python) | ❌ No (Safe, deterministic) |

### B. Admin Assistant Read-Only Tools (108 Tools)

All 108 read-only tools are defined in `backend/services/admin_assistant_tools.py` under `ToolCapability.READ_ONLY`. They wrap existing backend services and database repositories:

| Category / Domain | Tool Count | Sample Tools | Data Returned | Security / Permissions |
|---|---|---|---|---|
| **Dashboard & UI Guidance** | 8 | `get_dashboard_overview`, `get_page_help`, `get_navigation_targets` | Page descriptions, nav URLs | Authenticated Admin (`tool.read`) |
| **Governance & Approvals** | 18 | `get_pending_admin_proposals`, `get_governance_review_queue`, `get_governance_entity_status` | Proposal rows, approval logs | Authenticated Admin (`tool.read`) |
| **Data & Dataset Registry** | 22 | `list_dataset_versions`, `get_dataset_quality_summary`, `get_dataset_split_statistics` | Record counts, hashes, schema | Authenticated Admin (`tool.read`) |
| **RAG & Search Diagnostic** | 16 | `get_rag_space_status`, `list_indexed_documents`, `get_chunk_quality_metrics` | Chunk counts, index health | Authenticated Admin (`tool.read`) |
| **Model Registry & Training**| 24 | `list_model_releases`, `get_training_job_status`, `get_evaluation_benchmark_summary` | Loss metrics, SHA-256 hashes | Authenticated Admin (`tool.read`) |
| **System & Infrastructure** | 20 | `get_system_health`, `get_database_backup_status`, `get_hardware_resource_metrics` | CPU, RAM, disk, WAL state | Authenticated Admin (`tool.read`) |

---

## 2. Governed Mutating Actions (Admin Assistant Write Governance)

The Admin Assistant **cannot execute mutations directly through tools**. All mutations must follow the two-step governance pipeline:
1. `POST /admin/assistant/proposals` (Creates proposal in `PENDING` state).
2. Human admin reviews on Dashboard and executes `POST /admin/assistant/proposals/{id}/review` (`APPROVE` or `REJECT`).
3. Only upon approval can `POST /admin/assistant/proposals/{id}/execute` run.

### Registered Mutating Action Types:
- `dataset_record_review` (Low risk)
- `dataset_source_update` (Moderate risk)
- `governance_target_approval_override` (High risk — requires two distinct admins)
- **BLOCKED ACTIONS:** Any action containing `"train"` or `"pretrain"` is **strictly barred in code** (`BLOCKED_ACTION_SUBSTRINGS = ("train", "pretrain")`).

---

## 3. Agentic Classification: What is Brud AI?

Is Brud AI an LLM-only system, Tool-assisted, Agentic, or Hybrid?

### Verdict: **HYBRID / TOOL-ASSISTED WITH GOVERNED WORKFLOWS**
- **Public Chat:** **Tool-assisted deterministic pipeline**. Queries needing calculation or unit conversion are routed to Python tools without calling the LLM. Open-ended queries attempt RAG + local LLM, but fall back safely when models are unassigned.
- **Admin Assistant:** **Governed tool-using assistant**. It possesses 108 read-only inspection tools that it invokes deterministically. It does **NOT** operate as an autonomous, self-directing agent that writes files, starts shell commands, or mutates code.
- **Why it is NOT fully Agentic:**
  - It does not run multi-step planning loops with self-correction in production.
  - It cannot execute write actions autonomously without explicit human approval.
  - It is barred at the code level from starting model training.
