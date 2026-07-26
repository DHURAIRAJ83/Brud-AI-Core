# Admin Assistant and Admin Review

The Admin Assistant is a governed guide over the Admin Dashboard. It understands dashboard state, helps an admin inspect and prepare datasets, and drafts proposals for anything that would change data. It never mutates anything itself: every mutation requires an explicit Admin Review approval, and approved actions execute only through the same secured services the dashboard already uses by hand.

## Lifecycle

A proposal moves through four states, each written to the audit log via `AuditLogRepository`:

1. **Proposed** -- `POST /api/admin/assistant/proposals` creates a row in `admin_approvals` with `status=pending`, `execution_status=not_applicable`. No mutation happens here.
2. **Reviewed** -- `POST /api/admin/assistant/proposals/{id}/review` lets an authenticated admin set `status` to `approved` or `rejected`. A proposal can only be reviewed once; re-reviewing a decided proposal is rejected. Approval flips `execution_status` to `pending`; rejection leaves it `not_applicable`.
3. **Executed** -- `POST /api/admin/assistant/proposals/{id}/execute` is only accepted when `status=approved` and `execution_status=pending`. It dispatches to an allowlisted executor (see below), records the result, and sets `execution_status` to `succeeded` or `failed`. A proposal can only be executed once; re-executing a completed proposal is rejected.
4. **Guidance** -- `GET /api/admin/assistant/overview` is read-only: it summarizes counts across dataset sources, dataset records, training jobs, model registry, feedback, admin approvals, and (where present) corpus releases and model versions, and turns pending work into plain-language guidance ("N dataset records are pending_review").

Every step, plus failures, is audited: `admin_assistant_proposal_created`, `admin_review_approved`, `admin_review_rejected`, `admin_review_decision_failed`, `admin_assistant_proposal_executed`, `admin_assistant_proposal_execution_failed`.

## Execution is allowlisted, not generic

`ACTION_EXECUTORS` in `backend/services/admin_assistant_service.py` is a closed map from `action_type` to a function that calls an existing, already-secured admin service -- currently `DatasetService.review` (approve/reject/request_changes a dataset record) and `DatasetService.update_source` (patch a dataset source). Proposing or executing any `action_type` outside this map is rejected with 422 before anything runs. There is no generic "run this SQL" or "call this service" escape hatch.

As a second, independent guard, any `action_type` containing `train` or `pretrain` is refused even if it were somehow present in the map. **The Admin Assistant cannot start, resume, or otherwise trigger model training.** Extending it to cover a new dashboard area means adding a new entry to `ACTION_EXECUTORS` that wraps an existing service call -- never a direct database write, and never a training entry point.

## Schema

Migration 022 (`backend/database/schema.py::PHASE22_COLUMNS`) adds `summary`, `execution_status`, `executed_at`, `execution_result_json`, and `executor_public_id` to the Phase 2 `admin_approvals` table, which already modeled `action_type` / `target_type` / `target_public_id` / `request_payload_json` / `status` but had no caller until this feature. `AdminApprovalRepository` (`backend/database/repositories/phase2.py`) gained `list`, `update_review`, and `update_execution`, each enforcing the one-shot review/execute transitions at the database layer as well as the service layer.

## Frontend

`apps/admin-dashboard/src/pages/AdminAssistantPage.jsx` exposes three views: Guidance (the dashboard overview), Propose an Action (a form scoped to the allowlisted action types returned by `GET /api/admin/assistant/actions`), and Proposals & Admin Review (list, open, approve/reject, execute). The public chatbot (`apps/chatbot`) is untouched by this feature.

## Out of scope

The Admin Assistant does not start or manage training runs, does not write to the database directly, and does not bypass Admin Review. Those remain deliberate, human-triggered actions elsewhere in the dashboard.
