# Master Brud AI End-to-End Audit — 05: Admin Assistant Deep Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code inspection and API route tests)  

---

## 1. Subsystem Architecture & UI Integration

The Admin Assistant is built as a floating, contextual assistant embedded in the React 19 Admin Dashboard (`apps/admin-dashboard`).

### Entrypoint & Protocol:
- **API Endpoint:** `POST /api/admin/assistant/chat`
- **Authentication:** Admin session cookie (`brud_admin_session`) + CSRF Token (`X-CSRF-Token`). Unauthenticated requests are rejected with HTTP 401/403.
- **Service Handler:** `AdminAssistantChatService` (`backend/services/admin_assistant_chat_service.py`).
- **Context Awareness:** Automatically receives `page_id`, `tab_id`, `entity_type`, and `entity_public_id` from the admin's active browser viewport.

---

## 2. The 4 Operational Modes

The assistant operates across 4 distinct modes defined in `core_model/admin_assistant/dashboard_registry.py`:

| Mode | Target Domain | Primary Capability | Active Tools Consulted |
|---|---|---|---|
| **`guide`** | Dashboard Navigation & UI Help | Explains pages, tables, buttons, and recommended workflows | `get_dashboard_overview`, `get_page_help`, `get_navigation_targets` |
| **`governance`** | Approvals & Reviews | Summarizes pending proposals, two-person reviews, and audit events | `get_pending_admin_proposals`, `get_governance_review_queue` |
| **`data`** | Datasets & Sources | Reports on dataset versions, sample imports, and quarantine records | `list_dataset_versions`, `get_dataset_quality_summary` |
| **`system`** | Health & Runtime Telemetry | Inspects CPU, RAM, database WAL mode, backups, and training status | `get_system_health`, `get_hardware_resource_metrics` |

---

## 3. Bilingual Intelligence & Intent Processing

1. **Persistent Language Preference (`AdminAssistantLanguageService`):**
   - Each admin's preferred response language (`ta`, `en`, `tgl`) is persisted in the database.
   - All deterministic replies and LLM prompts are localized into the chosen language (`catalog_message`, `localize`).
2. **Intent Classification (`core_model/admin_assistant/intent.py`):**
   - Classifies admin queries into: `page_help`, `pending_work`, `navigation`, `entity_status`, `system_health`, or `open_ended`.
   - Read-only queries execute deterministically via tool dispatch without requiring an LLM.
3. **Curated FAQ Knowledge Bases:**
   - Pre-indexed domain FAQs:
     - `DATASET_VERIFICATION_FAQ` (`dataset_verification_help.py`)
     - `KNOWLEDGE_GAP_FAQ` (`knowledge_gap_help.py`)
     - `RAG_SANDBOX_FAQ` (`rag_sandbox_help.py`)
     - `SAMPLE_IMPORT_FAQ` (`sample_import_help.py`)
     - `TRUSTED_WEB_FAQ` (`trusted_web_help.py`)

---

## 4. Governed Proposal Creation & Two-Person Verification

When an admin asks the assistant to perform an action (e.g. "Review this record" or "Update dataset source"):
1. The assistant matches the intent against `ACTION_DEFINITIONS` (`core_model/admin_assistant/action_registry.py`).
2. It verifies that the action does **NOT** contain blocked substrings (`"train"`, `"pretrain"` are strictly barred).
3. It drafts an `AdminApproval` record (`status='PENDING'`) via `propose_with_governance()`.
4. The proposal is surfaced on the Admin Dashboard's Review Queue.
5. High-risk proposals enforce the **Two-Person Rule**: the admin who created the proposal cannot be the one to approve it (`proposer_id != reviewer_id`).
6. Execution occurs only after an explicit `APPROVE` decision is logged.
