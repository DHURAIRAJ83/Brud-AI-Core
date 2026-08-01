# Phase 16 — Existing-System Audit, Capability Mapping & Implementation Gap Report: Plan

Written before any audit findings, per the task's own requirement that
the plan document precede the audit work. This is an inspection,
evidence, mapping, and planning phase only -- no Smart Answer Router,
web connector, translation provider, new production action, new
database table, Vision/Audio/Video/Multimodal, or billing code is
written in this phase. Small test/audit tooling fixes are permitted only
when required to complete the audit itself, and must be documented as
such.

## 0. Baseline confirmed by direct inspection before this plan was written

- `backend/database/schema.py`: `SCHEMA_VERSION = 38` (confirmed by
  direct grep, not assumed from the prior phase's closing summary).
- Top-level layout: `apps/{chatbot,admin-dashboard}`, `backend/{api,core,
  database,models,runtime,services}`, `core_model/` (32 subpackages),
  `tests/`, `docs/` (200+ existing docs, including per-phase reports
  `phase_1_report.md` .. `phase_19_report.md` -- note these are an
  **earlier, unrelated numbering scheme** from before the Phase 15/15A
  production-readiness arc; this audit must not confuse them with the
  Smart Answer Routing Phase 16-26 numbering used in this task),
  `config/production_regression_manifest.json`, `scripts/run_chatbot.sh`
  / `run_admin.sh` / `run_backend.sh`.
- `backend/api/routes/chat.py` exists -- the presumed public-chatbot
  route, to be traced in Step 2, not assumed to be wired correctly.
- `backend/services/` contains 141 files, including `chat_orchestration_
  service.py`, `rag_retrieval_service.py`, `rag_generation_service.py`,
  `memory_service.py`, `external_data_provider_service.py`,
  `external_data_connectors/` (a subpackage), and the full Phase 15/15A
  `production_*.py` set already audited in the prior phase.

## 1. Method

Given the size of this audit (29 steps across chatbot execution,
core model, RAG, memory, safety, language, providers/MCP, source rights,
feedback, dataset/training chain, Admin Assistant, source UI, database,
API, frontend, tests, and manual verification), the investigation is
split into parallel, independent research passes (this session's
"fork" mechanism -- each inherits full conversation context, runs
independently, and reports back without polluting the main thread with
raw grep/read output). Each pass is scoped to a natural cluster of the
task's own steps so findings can be cross-checked against each other
during synthesis:

- **Pass A** (Steps 2-3): Public chatbot execution-path trace (frontend
  → API → orchestration → model/RAG/memory/safety → response →
  rendering) + core model / confidence / freshness audit.
- **Pass B** (Steps 4-5): RAG system audit (knowledge spaces through
  production RAG) + conversation memory audit.
- **Pass C** (Steps 6-7): Safety audit (input/output/refusal/PII/
  injection/tool permissions) + language/Tanglish audit (detection,
  normalization, Admin Assistant localization vs. public-chat policy).
- **Pass D** (Steps 8-11): External providers/connectors/tools/MCP audit
  + source-rights/evidence-governance audit + feedback/human-review
  audit + unknown-question capability audit.
- **Pass E** (Steps 12-13): Full governed dataset/RAG-sandbox/training
  chain audit + complete Admin Assistant action-table audit (every
  action's read-only/mutation/proposal/execution/approval/activation/
  rollback/human-gate/audit-coverage status).
- **Pass F** (Steps 14-17): Source-display UI audit (chatbot response
  schema + frontend components) + database/migration audit + API route
  inventory + frontend audit (both `apps/chatbot` and
  `apps/admin-dashboard`).

Each pass is instructed to cite concrete file paths, class/function
names, route paths, table names, and test files for every claim, and to
explicitly mark anything it could not verify rather than assume it.

Test/build verification (Step 18) and manual runtime verification
(Step 19) are run directly in this session (not via fork), since they
involve long-running, stateful processes (the canonical regression
manifest, a live backend+frontend) that need to be watched and their
real output captured verbatim -- consistent with how Phase 15A's own
regression runs were conducted.

## 2. Deliverables (Step 28) and their relationship

1. `phase16_existing_system_audit_plan.md` -- this document.
2. `phase16_existing_system_audit_and_gap_report.md` -- the main
   narrative report: Steps 1-19 findings, Step 20 status vocabulary
   applied throughout, Step 22 gap severities, Step 23-24 architecture,
   manual/test verification evidence.
3. `phase16_capability_matrix.md` -- Step 21's full matrix, one row per
   required feature group, every column populated with concrete
   evidence or `MISSING`.
4. `phase16_phase17_to_phase26_implementation_map.md` -- Step 25's
   phase-by-phase map with entry/exit gates.
5. `phase16_duplication_prevention_map.md` -- Step 26's "Do Not Rebuild"
   map, one exact existing component per item.
6. `phase16_risk_register.md` -- Step 27's risk register.

## 3. Non-negotiable constraints carried into every pass

- No existing feature/route/table/migration/test/CLI/frontend page/
  workflow is removed, renamed, rewritten, or broken.
- No Smart Answer Router, web connector, translation provider, new
  production action, new DB table (beyond a small, clearly-justified
  audit record if the repository's own convention already supports it
  trivially -- expected to be "none needed" given Phase 15's generic
  `production_readiness_events`-style tables, to be confirmed not
  assumed), or Vision/Audio/Video/Multimodal/billing code.
- A capability is only called `WORKING` if it is implemented, wired end
  to end (API + DB + frontend where applicable), and exercised by a real
  test or real manual verification recorded in this pass -- matching the
  task's own `implemented`/`wired`/`tested`/`production-used` distinction
  and the Step 20 status vocabulary.
- Every "existing capability ≠ X" invariant in the task prompt is
  treated as a hypothesis to actively falsify or confirm with evidence,
  not an assumed conclusion.

## 4. Pass/fail criteria for this plan

This plan is complete once committed to disk (matching the Phase 15A
plan-doc pattern); the audit passes begin immediately after.
