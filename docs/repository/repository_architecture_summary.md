# Repository Architecture Summary

Produced by the Repository Stabilization pass (2026-08-01). Read-only
architecture audit — no code was changed.

## Migration chain / schema (Step 6)

- `SCHEMA_VERSION = 44` (`backend/database/schema.py`).
- Migration 043 = `043_document_sft_workflow`, migration 044 =
  `044_document_sft_finalization` — both confirmed to genuinely belong to
  Document SFT by name and by the schema blocks they install.
- `git diff` against the committed HEAD baseline shows **zero lines removed**
  in `migrations.py` (pure addition of `_apply_v23()` through `_apply_v44()`
  and their import list) and **exactly one line changed** in `schema.py`
  (`SCHEMA_VERSION = 22` → `44`, the expected version bump) — migrations
  1–22 are byte-for-byte unchanged from the last commit. No historical
  migration was rewritten.
- Fresh temporary database (`initialize_database()`, the same call path
  `backend/main.py`'s startup uses): reaches version 44,
  `schema_migrations` contains exactly versions 1–44 contiguous with no
  gaps or duplicates, `PRAGMA integrity_check` = `ok`, `PRAGMA
  foreign_key_check` = 0 violations. Scratch DB removed after the check,
  nothing left behind.
- Real development database (`data/database/brud_ai.db`, gitignored):
  independently re-checked, also at version 44, `integrity_check: ok`, 0 FK
  violations.
- No migration file was edited during this pass.

## Duplicate-implementation check (Step 7)

Checked each named system for more than one implementation of the same
responsibility. **No true duplicates found.** What looks like repetition on
a `find`/`grep` pass is, in every case checked, a deliberate **layered
architecture** repeated consistently across every major subsystem:

```
base engine/registry  ->  workflow/sandbox layer  ->  production-governance layer
```

| System | Base | Workflow/sandbox layer | Production-governance layer | Verdict |
|---|---|---|---|---|
| RAG | `rag_retrieval_service.py`, `rag_generation_service.py`, `rag_ingestion_service.py`, `rag_evaluation_service.py` | `rag_sandbox_*` (9 files — eligibility, corpus, index, retrieval, answer, evaluation, review, report, acceptance, deletion) | `production_rag_*` (5 files — eligibility, candidate, validation, activation, promotion) | Single implementation per responsibility, no overlap |
| Training | `pretraining_*` (bootstrap pipeline), `base_training_service.py` | `training_evaluation_service.py`, `training_suitability_service.py`, `training_contamination_service.py`, `training_replay_plan_service.py`, `training_example_transformation_service.py`, `training_resource_preview_service.py`, `training_dataset_promotion_service.py` | `governed_training_handoff_service.py` | No duplicate; `pretraining_*` (tokenizer/corpus bootstrap) and `base_training_service.py` (actual training run) are genuinely different pipelines, not competing implementations of the same thing |
| Model/corpus release | `model_release_service.py` (base CRUD, used by `backend/api/routes/model_release.py`), `corpus_release_service.py` (unrelated — corpus, not model) | — | `production_model_release_request_service.py` + `_approval_service.py` + `_validation_service.py` (used by `backend/api/routes/production_readiness.py`) | Base registry + a separate, later production-gating layer built on top — confirmed by checking which route file imports which service; no route imports both for the same purpose |
| Document SFT | `document_workspace_service.py` (lifecycle) | `document_sft_candidate_service.py` (generation) | `document_sft_export_service.py`, `document_sft_dataset_handoff_service.py` (export/handoff gating) | Four distinct, non-overlapping responsibilities |
| Chat routing | `chat_orchestration_service.py` (admin-authenticated diagnostic chat) | — | `public_chat_routing_service.py` (unauthenticated public router, Phase 18/Smart Routing) | Two intentionally separate systems by design — the Smart Routing implementation map (`docs/smart_routing/phase16_phase17_to_phase26_implementation_map.md`) explicitly designs public routing as calling into the admin engine, not duplicating it; confirmed distinct auth boundaries, not overlapping code paths |
| Admin Assistant tool registry | `admin_assistant_tools.py` (read-only inspection tools for the floating Admin Assistant chat widget, imports from `dashboard_registry.py`) | — | `deterministic_tool_registry.py` (a separate, general-purpose deterministic-tool execution capability, backing `DeterministicToolsPage.jsx` and the Smart Routing `tool` execution route) | Confirmed by reading both files: different purpose, different consumers, no shared code duplicated between them |
| Navigation registry | `core_model/admin_assistant/dashboard_registry.py` (single canonical page/tab registry, 41 `PageEntry` records) | `apps/admin-dashboard/src/services/documentNavigation.js` (Document-SFT-specific navigation helper, consumes the Python registry's contract, does not duplicate it) | — | Single source of truth on the Python side; the JS file is a typed client helper, not a second registry |
| Dataset versioning | `backend/services/dataset_versioning.py` | `backend/database/repositories/phase2.py` (data-access layer) | — | Single business-logic implementation; the repository is the expected data-access split, not a duplicate |

## Admin Dashboard page/registry parity (Step 8)

- `App.jsx` registers **38 real page routes** (`if (active === '<Nav Key>')
  page = <SomePage .../>`), all falling back to `<PlaceholderPage
  name={active} />` for anything unregistered.
- `dashboard_registry.py` declares **41 `PageEntry` records**.
- `comm` diff of the two `nav_key`/route-string sets: **all 38 App.jsx
  routes have a matching registry entry** (0 missing). The registry has 3
  extra entries beyond App.jsx's real routes: `Chat Testing`, `Audit Logs`,
  `Settings` — all three are explicitly marked `implemented=False` in the
  registry itself.
- **Verdict: no orphan pages, no accidental gaps.** The 3 sidebar buttons
  with no dedicated page are a known, self-documented, intentional state
  (they render `PlaceholderPage`), not a bug. This is good registry
  discipline: the registry accurately reflects "planned but not yet built,"
  rather than silently omitting them or claiming false completeness.

## Admin Assistant tool/registry parity (Step 9)

- `admin_assistant_tools.py`'s docstring states its own invariant directly:
  "Every tool here is a thin, uniform wrapper around one method of an
  existing, already-secured Phase 2-7 service or repository -- never a new
  data-access layer, never raw SQL, and never a mutation." Confirmed by
  reading the tool function bodies (`_tool_dashboard_overview`,
  `_tool_page_help`, `_tool_pending_admin_proposals`, `_tool_governance_
  review_queue`, `_tool_governance_entity_status`, `_tool_governed_build_
  status`, `_tool_list_governed_builds`, `_tool_lineage_trace`, `_tool_
  source_status`, `_tool_list_rag_knowledge_spaces`, `_tool_model_
  evaluation_run`, `_tool_model_release_candidate`, `_tool_pretraining_
  readiness_evaluations`, `_tool_recent_audit_events`, `_tool_list_
  external_data_providers`, `_tool_get_external_data_provider`, and more) —
  each one calls into an existing service/repository method and returns its
  result, matching the stated invariant.
- `ReadOnlyToolError` is confirmed as the single exception type these tools
  raise, converted at the chat-orchestration boundary into a bounded,
  redacted message and logged as an `admin_assistant_tool_invocations` row
  (per the module's own docstring).
- Imports `dashboard_registry.py` directly (`from core_model.admin_
  assistant.dashboard_registry import (...)`) rather than maintaining a
  second, parallel page list — single source of truth confirmed.
- **No parity gap found** between registered tools and their underlying
  services during this pass; a full per-fingerprint/per-executor audit
  against every proposal type was not re-run in this pass since it would
  require executing the full Admin Assistant test suite, which this task's
  Step 9 does not request re-running (inventory/parity check only — see
  `documentation_index.md`/`repository_cleanup_audit.md` for what *was*
  executed vs. what was inspected statically).

## Phase implementation status reconciliation

Cross-referencing the three phase-numbering tracks (see `documentation_
index.md`) against actual code presence:

| Track / Phase | Claimed state (per various docs/task briefs) | Actual code state found |
|---|---|---|
| Main Brud AI 1–22 | Complete, committed | Confirmed — all committed through `196c2a4`/`7f050b6`/`e24849f` |
| Data Studio 1–7 | Complete (per this task's "Phase 1–19 completed" framing, if that framing refers to this track) | Confirmed implemented, **uncommitted** |
| Document SFT (workflow → closure) | Complete, closure committed | Confirmed — closure committed in `26611fc`; earlier 3 passes implemented and tested but uncommitted |
| Smart Routing 16–19 (router foundations, public router, knowledge gap) | Not mentioned in this task's brief | Confirmed implemented (real services, real tests, real docs), **uncommitted** |
| Smart Routing 20 (Trusted Web & Tool Gateway) | This task's brief explicitly says "No Trusted Web implementation" (as an instruction not to build it now) | **Already implemented** — 1,405 lines of backend services + 253-line frontend page + 573 lines of tests + a registered API route, all **uncommitted**. Not built in this pass; found already present. |

This reconciliation is the single most important input to `stable_release_
readiness.md`'s blocker list: the "Phase 1–19 completed" framing this task
was given does not match the actual working-tree state, which includes
substantial Smart Routing work (through at least Phase 20) already built.
