# Admin Assistant and Admin Review

The Admin Assistant is a governed guide over the Admin Dashboard. It understands dashboard state, helps an admin inspect and prepare datasets, and drafts proposals for anything that would change data. It never mutates anything itself: every mutation requires an explicit Admin Review approval, and approved actions execute only through the same secured services the dashboard already uses by hand.

## Lifecycle

A proposal moves through four states, each written to the audit log via `AuditLogRepository`:

1. **Proposed** -- `POST /api/admin/assistant/proposals` creates a row in `admin_approvals` with `status=pending`, `execution_status=not_applicable`. No mutation happens here.
2. **Reviewed** -- `POST /api/admin/assistant/proposals/{id}/review` lets an authenticated admin set `status` to `approved` or `rejected`. A proposal can only be reviewed once; re-reviewing a decided proposal is rejected. Approval flips `execution_status` to `pending`; rejection leaves it `not_applicable`. For `risk_level="high"` actions (see below), the reviewer must be a different admin than the one who proposed it -- this is unconditional and not configurable; approving your own high-risk proposal is rejected with 422. Moderate- and low-risk actions have no such requirement: the same admin may propose and review them.
3. **Executed** -- `POST /api/admin/assistant/proposals/{id}/execute` is only accepted when `status=approved` and `execution_status=pending`. It dispatches to an allowlisted executor (see below), records the result, and sets `execution_status` to `succeeded` or `failed`. A proposal can only be executed once; re-executing a completed proposal is rejected.
4. **Guidance** -- `GET /api/admin/assistant/overview` is read-only: it summarizes counts across dataset sources, dataset records, training jobs, model registry, feedback, admin approvals, and (where present) corpus releases and model versions, and turns pending work into plain-language guidance ("N dataset records are pending_review").

Every step, plus failures, is audited: `admin_assistant_proposal_created`, `admin_review_approved`, `admin_review_rejected`, `admin_review_decision_failed`, `admin_assistant_proposal_executed`, `admin_assistant_proposal_execution_failed`.

## Execution is allowlisted, not generic

`ACTION_EXECUTORS` in `backend/services/admin_assistant_service.py` is a closed map from `action_type` to a function that calls an existing, already-secured admin service -- currently `DatasetService.review` (approve/reject/request_changes a dataset record) and `DatasetService.update_source` (patch a dataset source). Proposing or executing any `action_type` outside this map is rejected with 422 before anything runs. There is no generic "run this SQL" or "call this service" escape hatch.

As a second, independent guard, any `action_type` containing `train` or `pretrain` is refused even if it were somehow present in the map. **The Admin Assistant cannot start, resume, or otherwise trigger model training.** Extending it to cover a new dashboard area means adding a new entry to `ACTION_EXECUTORS` that wraps an existing service call -- never a direct database write, and never a training entry point.

## High-risk actions require a distinct reviewer

Eight `risk_level="high"` action types -- `governance_target_approval_override`, `configure_provider_credential_reference`, `review_dataset_permission`, `finalize_dataset_verification_report`, `record_dataset_withdrawal_notice`, `link_dataset_verification_rights`, `execute_sample_deletion`, `execute_rag_sandbox_deletion` -- cannot be approved by the same admin who proposed them. `AdminAssistantService.review()` rejects `reviewed_by == requested_by` for these action types unconditionally, before the existing stale-check runs. This is a policy of this engine only, deliberately scoped to `risk_level="high"`:

- **Moderate- and low-risk actions** (the other 95 action types, including `create_production_model_release_request`/`submit_production_model_release_request`) have no distinct-reviewer requirement -- the same admin may propose and review them, unchanged.
- **GOV-33** (`core_model/release/approval_policy.py`, used by `ModelReleaseService`/`ModelAssignmentService`) is a separate, unrelated self-approval/distinct-approver-count mechanism for model release and inference-assignment approval. It is not reused or imported here, and this policy does not change it. In particular, `create_production_model_release_request`/`submit_production_model_release_request` only ever create or submit a request -- the actual release approval remains gated exclusively by GOV-33, downstream of anything the Admin Assistant does.

## Schema

Migration 022 (`backend/database/schema.py::PHASE22_COLUMNS`) adds `summary`, `execution_status`, `executed_at`, `execution_result_json`, and `executor_public_id` to the Phase 2 `admin_approvals` table, which already modeled `action_type` / `target_type` / `target_public_id` / `request_payload_json` / `status` but had no caller until this feature. `AdminApprovalRepository` (`backend/database/repositories/phase2.py`) gained `list`, `update_review`, and `update_execution`, each enforcing the one-shot review/execute transitions at the database layer as well as the service layer.

## Frontend

`apps/admin-dashboard/src/pages/AdminAssistantPage.jsx` exposes three views: Guidance (the dashboard overview), Propose an Action (a form scoped to the allowlisted action types returned by `GET /api/admin/assistant/actions`), and Proposals & Admin Review (list, open, approve/reject, execute). The public chatbot (`apps/chatbot`) is untouched by this feature.

## Out of scope

The Admin Assistant does not start or manage training runs, does not write to the database directly, and does not bypass Admin Review. Those remain deliberate, human-triggered actions elsewhere in the dashboard.

## Chat ownership: this service vs. Mini Brain (MB-28)

This document covers the Admin Assistant's proposal/governance service (`backend/services/admin_assistant_service.py`, `admin_assistant_chat_service.py`) and its `/api/admin/assistant/*` routes, including `POST /api/admin/assistant/chat`. A separate subsystem, Mini Brain (`MiniBrainLlmRuntimeService`, `/api/admin/mini-brain/llm-runtime/*`, sometimes referred to by its internal milestone name "MB-28"), also accepts chat-shaped input. The two are intentionally separate subsystems and must not be merged just because both process chat-like messages -- their capabilities, governance boundaries, and intended callers differ (see the table below). This section formalizes which one owns what, so neither is mistaken for the other's replacement.

**MB-28 is the canonical live chat runtime for the dashboard UI.** Every current chat surface -- the floating Admin Assistant widget, the Mini Brain page, the Mini Brain Chat and Assistant Intelligence tabs -- sends messages exclusively through `ChatPanel.jsx`, which calls only `POST /api/admin/mini-brain/llm-runtime/chat` and `.../grounded-chat`. `ChatPanel.jsx` does not call `POST /api/admin/assistant/chat`, and `sendAssistantChatMessage()` (the frontend binding for that endpoint, in `apps/admin-dashboard/src/services/api.js`) has no production caller as of this writing.

**`POST /api/admin/assistant/chat` remains a real, supported, admin-only API surface -- it is not dead, deprecated, or a replacement for MB-28.** Removing zero UI callers of the *chat* endpoint specifically does not mean removing the endpoint: this service also owns the proposal/review/execute governance flow, `/feedback`, `/pages`, and `/preferences` (language), all of which the floating widget and `AdminAssistantPage.jsx` still call directly, and which have no Mini Brain equivalent. Within this service, `/chat` specifically is best understood as a **direct admin API / diagnostic-and-fallback surface**: a deterministic (intent-classified, tool-dispatching) responder with an `admin_diagnostic`-scoped LLM fallback, independently tested (see `tests/backend/test_admin_assistant_api_phase8.py`, `test_admin_assistant_chat_service.py`), not the widget's live send path.

### Capability ownership

| Capability | Canonical owner | UI reachable | Direct API | Notes |
|---|---|---|---|---|
| Live chat (widget, Mini Brain page/tabs) | MB-28 | Yes, via `ChatPanel.jsx` | `POST /api/admin/mini-brain/llm-runtime/chat` | Sole live send path for every current chat surface |
| Greeting | Both | MB-28 only | Either | Phase-8's is deterministic; MB-28's is LLM-generated |
| Help / page guidance | This service | Via widget/`AdminAssistantPage.jsx` (non-chat calls) | `POST /api/admin/assistant/chat` | Deterministic, dashboard-registry-aware; MB-28 has no equivalent |
| Dataset discovery / verification / FAQ dispatch | This service | Via widget/`AdminAssistantPage.jsx` | `POST /api/admin/assistant/chat` | Deterministic tool dispatch, no MB-28 equivalent |
| Proposal governance (review/execute) | This service, exclusively | Yes, `AdminAssistantPage.jsx` | `/api/admin/assistant/proposals*` | See Lifecycle above; MB-28 can trigger *creation* of a proposal (see below) but never reviews or executes one |
| Training readiness (read-only) | This service | Via chat tool dispatch | `POST /api/admin/assistant/chat` | Read-only lookup only |
| Training execution | Neither | No | No | Blocked by `ACTION_EXECUTORS` allowlist and the `train`/`pretrain` substring guard -- see above |
| RAG / grounded chat | MB-28 | Yes | `POST /api/admin/mini-brain/llm-runtime/grounded-chat` | This service has no RAG retrieval |
| Memory / context | Both, disjoint | Yes | Both | Separate session/context stores per subsystem |
| Language preference | This service | Yes, widget's language selector | `/api/admin/assistant/preferences` | MB-28 has no persisted per-admin language preference |
| LLM fallback | Both, disjoint scopes | Chat: MB-28 only | Both | This service's fallback is `admin_diagnostic`-scoped; MB-28 has its own adapter chain |
| Feedback | This service | Yes, widget's feedback buttons | `/api/admin/assistant/feedback` | No MB-28 equivalent |
| Public chat | Neither | N/A | N/A | Fully separate, unauthenticated subsystem (`/api/chat`, `PublicChatRoutingService`) |
| Model assignment / release | Neither | N/A | N/A | Owned by governed release/assignment services, not chat |

### Governance boundary

Nothing above changes the governance model already described earlier in this document: `PROPOSE` (create a pending proposal) is never the same as `APPROVE` (a separate human review step -- for `risk_level="high"` actions this must be a distinct admin from the proposer, enforced; for moderate/low-risk actions the same admin may review their own proposal) or `EXECUTE` (dispatch through an allowlisted, already-secured service call). This applies whether the proposal originated from the Propose-an-Action form or from the chat endpoint's proposal-bridge. Training execution, dataset approval/promotion, model release, model activation, and public assignment remain unreachable through the Admin Assistant in every path (chat or form) -- those stay governed exclusively by their own existing APIs and human-approval gates, elsewhere in the dashboard.

### MB-28 -> proposal bridge -> Phase-8 governance (Phase 16.5)

MB-28's `chat()` recognizes a small, already-registered set of four governance-sensitive intents ("MB-39" scopes: `register_external_data_provider`, `run_sample_quality_checks`, `build_rag_sandbox_index`, `run_rag_sandbox_evaluation`) via the same shared matcher Phase-8's chat uses -- but *recognizing* a scope and being able to turn it into a proposal are not the same guarantee, and the four scopes split unevenly:

- `register_external_data_provider` is unconditionally proposal-capable from either chat surface once matched -- it needs no pre-existing target, so MB-28 can always propose it.
- `run_sample_quality_checks` requires a real `entity_type`/`entity_public_id` the bridge was actually given. Phase-8's chat can supply this from the dashboard's own entity context, so it is proposal-capable there; MB-28's current chat call path always passes `entity_type=None, entity_public_id=None`, so this scope is recognized by MB-28 but never proposal-capable from it today.
- `build_rag_sandbox_index` and `run_rag_sandbox_evaluation` are recognized by both chat surfaces but never converted into a proposal by either -- the bridge deliberately declines both, because the configuration they need (index/chunking/embedding settings, or an answer-run id) cannot come from a free-text chat message. This is a deliberate bridge-level decline, not a broken executor, a missing registry entry, or a governance failure -- both action types are fully registered and remain reachable through the existing Propose-an-Action form.

Whichever scope does produce a proposal, it does so by calling the same, unmodified `AdminAssistantService.propose()` that Phase-8's own chat already used, through a shared adapter (`core_model/admin_assistant/chat_action_bridge.py::propose_chat_action()`). This is strictly additive: MB-28 does not gain a second proposal engine, a second executor, or any new governance rule -- it gains exactly one narrow, read-then-propose call into the existing one.

**`PROPOSE != APPROVE != EXECUTE` holds across both chat surfaces.** A message MB-28 recognizes as actionable creates a `status="pending"` proposal and stops -- MB-28 never calls `review()` or `execute()`. Everything after that point (human review on `AdminAssistantPage.jsx`, approval, allowlisted execution) is the same, unmodified Phase-8 flow described in Lifecycle above, regardless of which chat surface created the proposal. Messages naming governance-sensitive actions outside this narrow scope (approve/freeze/promote a dataset, start training, release or activate a model, assign a model) do not match any MB-39 scope and are never proposed through this bridge -- they fall through to ordinary chat, exactly as they did before this bridge existed.

### Human review and execution (Phase 16.6)

A proposal created through the MB-28 bridge is stored as an ordinary `admin_approvals` row -- the same repository, the same fields, indistinguishable from one created by the Propose-an-Action form or Phase-8's own chat. No MB-28-specific handoff, second review surface, or second execution path exists or is needed: `GET /api/admin/assistant/proposals` (and `AdminAssistantPage.jsx`'s "Proposals & Admin Review" tab, which calls it) lists it, a human opens it, and the same `review()`/`execute()` calls described in Lifecycle above apply unchanged.

`PROPOSE != REVIEW != APPROVE != EXECUTE` holds through the full chain: `propose_chat_action()` calls `AdminAssistantService.propose()` and returns immediately -- it cannot reach `review()` or `execute()`, and nothing calls them automatically. A proposal stays `status="pending"` until a human explicitly reviews it on `AdminAssistantPage.jsx`; only after `status="approved"` can a human explicitly execute it, through the same allowlisted `ACTION_EXECUTORS` entry any other proposal of that `action_type` would use. Re-execution of an already-succeeded proposal is refused by the existing execution-status guard, not a new rule.

### Future routing rule

All current and future user-facing Admin Assistant chat UI should send through MB-28 unless a future architecture phase explicitly changes this canonical chat ownership decision. The continued existence of `POST /api/admin/assistant/chat` must not cause a new UI surface to be wired to it by accident (e.g. by copying an old `sendAssistantChatMessage()` call site) -- connecting a UI to this service's chat endpoint instead of MB-28 must be a deliberate, disclosed architecture decision, not an incidental import.
