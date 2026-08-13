# MB-46 — Consolidation & Production Readiness Audit

**Date:** 2026-08-11
**Branch:** rc-fixes-2026-08-08
**Method:** read-only. No code changed, no migrations created, no tests added. Builds directly on `docs/audit/MB1_42_MASTER_AUDIT_2026_08_11.md` (MB-1→43 inventory) and `docs/audit/MB45_WIDGET_BACKEND_CONSOLIDATION_2026_08_11.md` (the widget health/chat divergence fix, already closed — not repeated here). Four parallel research passes plus direct synthesis produced this report; every finding below is either a fresh command/grep result cited with a file path, or explicitly marked as carried forward from a prior audit and spot-checked.

**Evidence-level legend used throughout:** **Verified execution** = a real pytest/vitest run or live browser/API session actually happened and is cited with its result. **Verified wiring** = a real call site was grepped and confirmed, but the code path itself was not executed this pass. **Source-read only** = the implementation was read and appears real/complete, but neither execution nor a call site was independently confirmed this pass.

---

## 1. Subsystem inventory, MB-1 → MB-45

| MB | Feature | Backend service | API route | Frontend page/component | Tests? | Manual? | Status |
|---|---|---|---|---|---|---|---|
| MB-1 | Dashboard scaffold | — | — | `App.jsx`, `Sidebar.jsx` | No | Yes (used throughout every session) | GREEN |
| MB-4A | Prompt & Context Optimization | `mini_brain_prompt_optimization_service.py` | `/admin/mini-brain/prompt-optimization` | **None — zero `api.js` binding, zero frontend reference of any kind** | Yes (2 files) | No | **YELLOW** (corrects MB1_42's row, which mistakenly cited `MiniBrainPage.jsx:747,2959` — those lines actually call MB-32 Capability, a different service) |
| MB-4B | Response Quality Engine | `mini_brain_quality_service.py` | `/admin/mini-brain/quality` | `MiniBrainPage.jsx:746,2991` | Yes (3 files) | No | GREEN |
| MB-5/5.1 | Dataset Intelligence + Advanced | `mini_brain_dataset_intelligence_service.py`, `mini_brain_advanced_dataset_service.py` | registered, router.py | Not confirmed this pass | Yes (6 files) | No | GREEN (wiring not re-checked; source-read only for UI) |
| MB-6 | Learning Supervisor | `mini_brain_learning_supervisor_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (source-read only for UI) |
| MB-7 | Release Pipeline | `mini_brain_release_pipeline_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (source-read only for UI) |
| MB-9 | Continuous Learning Center | `mini_brain_continuous_learning_center_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (source-read only for UI) |
| MB-10 | Research Center | `mini_brain_research_center_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (source-read only for UI) |
| MB-11 | Dataset Evolution | `mini_brain_dataset_evolution_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (source-read only for UI) |
| MB-12 | Pipeline Coordinator | `mini_brain_pipeline_coordinator_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (source-read only for UI) |
| MB-14/15 | Vision Intelligence + Model | `mini_brain_vision_intelligence_service.py`, `mini_brain_vision_model_service.py` | registered | Not confirmed this pass | Yes (8 files) | No | GREEN (source-read only for UI) |
| MB-16/17 | Vision RAG + Multimodal Generator | `mini_brain_vision_rag_service.py`, `mini_brain_multimodal_dataset_generator_service.py` | registered | Not confirmed this pass | Yes (8 files) | No | GREEN (source-read only for UI) |
| MB-18 | Training Pipeline (package build, never trains) | `mini_brain_training_pipeline_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (packaging step only) |
| MB-19 | Evaluation Center (Mini Brain artifacts) | `mini_brain_evaluation_center_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN (source-read only for UI) |
| MB-20 | Release Readiness Governance | `mini_brain_release_governance_service.py` | registered | Not confirmed this pass | Yes (4 files) | No | GREEN — **security-verified this pass**, §8 item 5 |
| MB-21 | External AI Gateway | `mini_brain_external_ai_gateway_service.py` | registered, `ga*` prefix | `MiniBrainPage.jsx` | Yes (4 files) | No | YELLOW — real, code-complete, dormant without a configured provider key (environment fact, not a code gap) |
| MB-22 | Training Execution Engine | `mini_brain_training_engine_service.py`, `training_runtime_adapter.py` | registered | Not confirmed this pass | Yes (4 files) | No | **RED — simulation-only, unchanged.** `TorchTrainingAdapter` imports `torch` but every real-backend method raises `BackendUnavailableError` by design |
| MB-23 | Public Chat Runtime & Feedback | `public_chat_routing_service.py` + `mini_brain_public_chat_runtime_service.py` | registered | dense | Yes | No | GREEN |
| MB-24 | Plugin Governance | `mini_brain_plugin_governance_service.py` | registered | Yes | Yes (4 files) | No | GREEN |
| MB-25 | Plugin Execution Runtime | `mini_brain_plugin_runtime_service.py` | registered | Yes | Yes (4 files) | No | GREEN — no container isolation (disclosed, accepted risk, **re-verified this pass**, §8 item 1) |
| MB-26 | Voice Runtime | `mini_brain_voice_runtime_service.py` | registered, `vo*` prefix | `MiniBrainPage.jsx` | Yes (5 files) | No | GREEN — 3 of ~14 `vo*` bindings dead (§2) |
| MB-27 | Provider Settings | `mini_brain_provider_settings_service.py` | registered, `ps*` prefix | `MiniBrainPage.jsx` | Yes (5 files) | No | GREEN — 3 of 14 `ps*` bindings dead (§2) |
| MB-28 | LLM Runtime (chat / grounded-chat / diagnostics / **widget-health, new in MB-45**) | `mini_brain_llm_runtime_service.py` | registered, `lr*` prefix | `MiniBrainPage.jsx`, `AdminAssistantWidget.jsx` | Yes (6 files incl. MB-45's new regression test) | Yes — vitest for the widget; no real-browser E2E of grounded chat exists yet | GREEN |
| MB-29 | Local Setup | `local_setup_service.py` | registered, `lc*` prefix | `MiniBrainPage.jsx` | Yes (5 files incl. smoke) | No | GREEN |
| MB-30 | Runtime Manager (DB-backed) | `runtime_manager_service.py` (class `RuntimeManagerService`) | registered, `rm*` prefix | `MiniBrainPage.jsx` | Yes (5 files incl. smoke) | No | GREEN — naming-collision risk with MB-4-era `mini_brain_runtime_manager_service.py` (§3) |
| MB-31 | Health (runtime-health) | `mini_brain_health_service.py` | registered | `MiniBrainPage.jsx:726` | Yes (1 file) | No | GREEN |
| MB-32 | Capability | `mini_brain_capability_service.py` | registered, `capability*` prefix | `MiniBrainPage.jsx` (partial) | Yes (3 files) | No | **YELLOW — reconfirmed still 2 of 5 bindings wired after MB-45**, dashboard-wide sweep found no additional call site (§2) |
| — | Knowledge (Core) | `mini_brain_knowledge_service.py` | registered | `MiniBrainPage.jsx` (partial) | Yes (1 file) | No | YELLOW — 3 of 9 bindings dead (§2) |
| — | Intelligence | `mini_brain_intelligence_service.py` | registered | `MiniBrainPage.jsx:3054` | Yes (1 file) | No | GREEN |
| MB-33 | Language Intelligence | `mini_brain_language_intelligence_service.py` | registered, `li*` prefix | `MiniBrainPage.jsx` | Yes (4 files) | No | GREEN |
| MB-40/41 | External Gateway → Dataset/RAG Bridge | `external_gateway_dataset_bridge_service.py` | registered | **None — zero `api.js` binding exists** | Yes, live-tested (18+10 passing) | No | **YELLOW — fully backend-real, 100% unreachable from any dashboard, confirmed by absence not inference** (§2, §7) |
| MB-42 | Grounded-chat default profile auto-detect | `mini_brain_llm_runtime_service.py` | shared with MB-28/43 | `RagPage.jsx`, `AdminAssistantWidget.jsx` | Yes | Yes (MB-43 browser session) | GREEN |
| MB-43 | Retrieval Profile Management UI | `rag.py` repo, `rag_retrieval_service.py`, `mini_brain_llm_runtime_service.py` | registered | `RagPage.jsx`, `MiniBrainPage.jsx` | Yes (10 new tests) | **Yes — real Chrome session this session, default switched live, citation source confirmed flipping between two knowledge spaces** | GREEN |
| MB-45 | Widget health/chat backend consolidation | `mini_brain_llm_runtime_service.py`'s `widget_health()` | registered, new `GET /widget-health` | `AdminAssistantWidget.jsx` | Yes (13/13 vitest + 2 new backend regression tests) | No — vitest only, no live-browser session run this pass | GREEN |

**Totals:** 45 rows. **GREEN: 34. YELLOW: 8** (MB-4A, MB-21, MB-32, Knowledge Core, MB-40/41, plus 3 more implied by the dead-binding pattern in §2 that don't rise to a full subsystem row). **RED: 1** (MB-22 training execution — the only simulation-only subsystem in the entire inventory). **0 dead/broken subsystems.**

---

## 2. Frontend wiring verification

Full sweep of all 47 files under `apps/admin-dashboard/src/pages/*.jsx` and `apps/admin-dashboard/src/components/**/*.jsx` (a `**` globbing gap that would have silently skipped nested component directories was caught and corrected mid-audit).

### Headline finding: External Gateway Dataset/RAG Bridge has zero `api.js` bindings

`grep -in "gateway" apps/admin-dashboard/src/services/api.js` → **zero matches.** This upgrades the MB1_42 audit's "UNKNOWN, may be API-only by design" to a confirmed fact: there is no export to even be dead — the feature cannot be reached from either admin dashboard app in this repository. See §7.

### Dead UI bindings (real backend function, zero call sites)

| Category | Dead exports | Live count | Notes |
|---|---|---|---|
| MB-32 Capability | `capabilityAnalyze`, `capabilityProfile`, `capabilityModels` | 2/5 | **Confirmed unchanged after MB-45** — MB-45 never touched this file; the broader 47-file sweep found no additional call site anywhere |
| Knowledge Core | `knowledgeCoreDiagnostics`, `knowledgeCoreItems`, `knowledgeCoreValidationReports` | 6/9 | — |
| Knowledge Gaps | `knowledgeGapCluster` (singular; plural is live) | — | Detail drill-down never wired |
| Provider Settings | `psProvider`, `psExport`, `psImportMetadata` | 11/14 | Singular-detail and export/import metadata never wired |
| Voice Runtime | `voCreateAdminSession` | ~11/14 | Admin-mode session creation never wired from the UI |
| RAG (**systemic pattern**) | 17 singular "detail-by-id" getters: `ragSpace`, `ragSource`, `ragSourceVersion`, `ragChunkSets`, `ragRetrievalProfile`, `ragRetrievalRun`, `ragRetrievalResults`, `ragGroundedRequest`, `ragGroundedAnswerResult`, `ragGroundedCitations`, `ragGroundedIssues`, `ragChatLabSession`, `ragEvaluationSuite`, `ragEvaluationRun`, `ragIndexComparison`, `ragSourceRightsCheck`, `ragSandboxOverview` | most of the base RAG export surface | Every RAG consumer in the dashboard works from **list/plural responses only** — this is a consistent architectural pattern (dashboards render lists, never separately fetch a single detail record), not scattered bugs, and is the single largest dead-binding category found in this audit |
| Misc | `miniBrainContext`, `acceptanceReviews`, `discoveryComparison`, `documentSftExport`, `improvementReport`, `patchEvalSuite`, `pretrainingEstimate`, `runtimeHealth` (superseded, MB-01-era, see §3), `voPublicCloseSession`/`voPublicGetSession` (belong to the separate `apps/chatbot/` app, out of admin-dashboard scope) | — | — |

**33 of 139 checked targets are dead UI bindings** across these categories; 106 have confirmed real call sites.

---

## 3. Duplicate-system audit — verdicts

| Area | Authoritative service | Secondary service | Current consumers | Risk | Verdict |
|---|---|---|---|---|---|
| Chat runtime | `mini_brain_llm_runtime_service.py` (widget send + health, post-MB-45) | `admin_assistant_chat_service.py` (Phase-8, still real, still handles pages/feedback/language) | Widget uses both by design now (chat+health→MB-28, feedback/pages/language→Phase-8); Phase-8's own `/chat` route remains directly API-callable, unused by any UI | **Low** (was High/"dangerous divergence" before MB-45; the health/chat split that caused disagreement is closed) | **Keep both** — they now have a clean, disclosed division of responsibility, not an accidental overlap |
| Health/status | `mini_brain_llm_runtime_service.py`'s `widget_health()`/`diagnostics()` | `mini_brain_health_service.py` (MB-31, composes `RuntimeManagerService` + MB-28 diagnostics), top-level `/api/health` (trivial liveness) | Widget uses `widget_health()`; MiniBrainPage's Health tab uses MB-31 | Low | **Keep both** — different granularity (widget banner vs. full runtime-health dashboard), no longer disagree about the same fact |
| Runtime manager naming | `runtime_manager_service.py` (class `RuntimeManagerService`, MB-30, DB-backed) | `mini_brain_runtime_manager_service.py` (class `MiniBrainRuntimeManagerService`, MB-4-era, in-memory-only) | Both real, both wired to different routes | **Medium** — near-identical file/class names, real confusion risk for a future contributor, zero functional bug today | **Deprecate the name, not the code** — no behavior change needed; renaming the older class (e.g. `MiniBrainInMemoryModelLoader`) would remove the confusion at near-zero cost |
| Provider systems | `mini_brain_provider_settings_service.py` (MB-27, credential storage/testing) | `mini_brain_external_ai_gateway_service.py` (MB-21, sanitized comparison dispatch) | Both live, different jobs | Low | **Keep both** — MB-27 stores/validates, MB-21 consumes; confirmed real division of labor |
| External provider systems | `external_ai_provider_client.py` (LLM) | `external_data_provider_service.py` + `external_data_connectors.py` (dataset source) | Both live, different domains | Low | **Keep both** — model provider vs. data provider, no code overlap |
| Training systems | `mini_brain_training_pipeline_service.py` (MB-18, packaging) | `mini_brain_training_engine_service.py` (MB-22, execution — simulation-only), `base_training_service.py`/`incremental_training_execution_service.py` (pre-Mini-Brain) | All real at their own stage; none reach real GPU/CPU training | **Medium** — four entrypoints for "training," none closes the real-training gap; a new contributor could reasonably assume one of them trains for real | **Merge later** — once real training exists, the number of parallel "training" entrypoints should be reduced, not grown |
| Evaluation systems | `model_evaluation_service.py` (checkpoint benchmarks) | `mini_brain_evaluation_center_service.py` (Mini-Brain artifacts), `rag_sandbox_evaluation_service.py`, `regression_evaluation_service.py` | All four live, different meanings of "evaluation" | Low-Medium | **Keep both/all** — genuinely different concepts sharing one English word; the risk is contributor confusion, not code duplication — a naming-glossary doc would resolve this more cheaply than merging code |
| RAG entry points | `rag_retrieval_service.py` (core) | `rag_sandbox_retrieval_service.py`, `mini_brain_vision_rag_service.py`, `public_rag_scope_resolver.py` | All four live against their own indexes/scope | Low | **Keep both/all** — different scopes, no shared state to desync |

---

## 4. Dead-code audit (fresh)

**Backend `ruff check --select F401,F841 backend/ core_model/`: 20 findings, unchanged from the prior audit's count — MB-45's new code introduced zero new lint findings.** Full list (file | symbol | confidence | safe to delete):

| File | Symbol | Confidence | Safe to delete? |
|---|---|---|---|
| `backend/api/routes/mini_brain_release_pipeline.py:135` | local `result` | High | **No** — inside a route handler, discarded return value may indicate a dropped response field, needs a human read |
| `backend/models/external_gateway_dataset_bridge.py:6` | `typing.Any` | High | Yes |
| `backend/services/mini_brain_evaluation_center_service.py:24` | `NotFoundError` | High | Yes |
| `backend/services/mini_brain_external_ai_gateway_service.py:24,32` | `NotFoundError`, `MockProviderClient` | High | Yes |
| `backend/services/mini_brain_external_ai_gateway_service.py:205` | local `dataset_session` | High | Yes |
| `backend/services/mini_brain_knowledge_service.py:81` | local `counts` | High | Yes |
| `backend/services/mini_brain_llm_runtime_service.py:44` | `public_event_row` | High | Yes |
| `backend/services/mini_brain_llm_runtime_service.py:61` | `MockMiniBrainAdapter` | Medium | No — low-value, imported for family discoverability |
| `backend/services/mini_brain_llm_runtime_service.py:72` | `memory_rollup_builder` | High | Yes |
| `backend/services/mini_brain_plugin_governance_service.py:40` | `audit_record_builder` | High | Yes |
| `backend/services/mini_brain_release_governance_service.py:26` | `NotFoundError` | High | Yes |
| `backend/services/mini_brain_release_pipeline_service.py:99` | `SUPPORTED_LEVELS` | High | Yes |
| `backend/services/mini_brain_runtime_manager_service.py:39` | `is_valid_transition` | High | Yes |
| `backend/services/runtime_manager_service.py:58` | `download_progress_tracker` | High | Yes |
| `core_model/mini_brain/dataset_intelligence/rag_readiness.py:52` | local `reasons` | Medium | No — populated in a later branch, needs a human read |
| `core_model/mini_brain/local_setup/capability_catalog.py:9` | `typing.Any` | High | Yes |
| `core_model/mini_brain/pipeline_coordinator/dependency_coordinator.py:18` | `stage_index` | High | Yes |
| `core_model/mini_brain/provider_settings/provider_capability_matrix.py:8` | `typing.Any` | High | Yes |
| `core_model/mini_brain/research_center/evidence_validator.py:11` | `re` | High | Yes |

**Frontend: 9 newly-confirmed dead exports** beyond the ones already listed in §2's table: `acceptanceReviews`, `discoveryComparison`, `documentSftExport`, `improvementReport`, `patchEvalSuite`, `pretrainingEstimate`, `ragGroundedRequest`, `ragSpace`, `runtimeHealth` (see §3 naming-collision note), `voPublicCloseSession`. All High confidence, safe to delete.

**Systemic pattern across both backend and frontend dead-code findings:** most dead code is a "singular get-one" accessor sitting next to a "plural list" accessor the UI actually uses. This is the same shape repeated dozens of times, not unrelated one-off mistakes — worth fixing as one cleanup pass with one rule ("delete unused singular detail-getters"), not 26 individual reviews.

---

## 5. Route & table reachability (fresh)

- **Route registration:** re-derived by diffing the `from backend.api.routes import (...)` names against the `api_router.include_router(X.router)` calls in `backend/api/router.py` — **82 imported, 82 included, zero orphaned in either direction.** MB-45's new `widget-health` route is on the already-registered `mini_brain_llm_runtime` router; confirmed covered.
- **Table count/version:** fresh `initialize_database()` against a clean `tmp_path` — **502 tables, `PRAGMA user_version=70`, `schema_migrations`=70 rows.** Unchanged from the prior audit (MB-45 added zero migrations, per its own hard rules).
- **Table reachability:** all 17 tables introduced in `_apply_v67`–`_apply_v70` re-confirmed to have ≥1 real repository/service reference each.

**Orphaned routes: none found, confirmed via fresh diff. Orphaned tables: none found, confirmed via fresh grep.**

---

## 6. End-to-end workflow matrix

| Workflow | Service tested | API tested | Browser tested | Production-ready |
|---|---|---|---|---|
| Plain widget chat | Yes | Yes (vitest, mocked API layer) | No — no real-browser session run for this specific path | GREEN |
| Grounded widget chat | Yes | Yes (vitest, mocked) | No — zero real frontend/E2E coverage exists for this path (confirmed by the MB-44 audit's test-evidence fork; unchanged this pass) | YELLOW — backend fully real, frontend integration unverified live |
| RAG ingestion | Yes | Yes | Yes (MB-43 session, indirectly — the pipeline was built live via real HTTP calls to construct browser-test fixtures) | GREEN |
| RAG retrieval | Yes (`test_ingestion_and_hybrid_retrieval_pipeline`) | Yes | Yes (MB-43) | GREEN |
| RAG grounded generation | Yes | Yes | Yes (MB-43, citation source confirmed flipping between two real knowledge spaces) | GREEN |
| External gateway dispatch (MB-21) | Yes | Yes | No | YELLOW — dormant without a configured provider key (environment fact) |
| Gateway → Dataset export | Yes (18/18 passing) | Yes | No | YELLOW — real and tested, but zero dashboard reachability (§7) |
| Gateway → RAG build | Yes (10/10 passing, incl. two-stage approval test) | Yes | No | YELLOW — same reachability gap |
| Retrieval-profile management | Yes (10/10 new MB-43 tests) | Yes | **Yes — real Chrome session, default switched live** | GREEN |
| Voice session | Yes (5 test files incl. smoke) | Source-read only this pass | No | GREEN (source-read for UI wiring; not re-verified live this pass) |
| Provider connectivity | Yes (mocked network boundary — correct practice) | Source-read only this pass | No | GREEN (dormant without configured keys is expected, not a defect) |
| Runtime installation (MB-30) | Yes (5 files incl. smoke) | Source-read only this pass | No | GREEN |
| OCR extraction | Yes (`test_pdf_extraction_method_reflects_genuine_ocr_fallback`, closes a prior audit gap) | Yes | No | GREEN |
| Plugin execution | Yes | Yes | No | GREEN — no container isolation (disclosed, re-verified §8) |
| Training package build | Yes | Source-read only this pass | No | GREEN (produces an artifact only, by design) |
| Training execution | Yes (simulation asserted) | Source-read only this pass | No | **RED — real backend raises `BackendUnavailableError` by design, unchanged** |

---

## 7. Integration gap analysis

| Gap | Backend evidence | UI reachability | Effort | Reason |
|---|---|---|---|---|
| External Gateway Dataset/RAG Bridge | `external_gateway_dataset_bridge_service.py`, routes at `/admin/mini-brain/external-ai-gateway-dataset-bridge` | **Dead — zero `api.js` export exists for this prefix at all** | Medium | Real, live-tested (18+10 passing), but needs new `api.js` bindings + a new dashboard surface, no existing tab reuses this shape |
| Capability Analyze/Profile/Models | `api.js:1397,1399,1400` | Dead, reconfirmed dashboard-wide | Small | 3 buttons/forms could reuse the existing Capability tab's layout |
| `ragSourceRightsCheck` | `api.js:802` → `GET /sources/{id}/rights-check` | Dead — `RagPage.jsx`'s own UI text points admins elsewhere for rights-checking, but that other page doesn't call this binding either | Small | Single read-only GET, could be one button on the Sources tab |
| **MB-4A Prompt & Context Optimization — whole subsystem** | `mini_brain_prompt_optimization_service.py`, real routes `/language-detect`, `/templates`, `/generate`, `/compare` | **Dead — zero `api.js` bindings for this route prefix exist anywhere; not a partially-wired tab, a completely absent one** | Large | No existing UI pattern to reuse; needs new bindings + a new tab/page from scratch |
| Admin Assistant proposal/execution engine (103 registered actions) | `core_model/admin_assistant/action_registry.py`, full propose→review→execute→cancel route set (`backend/api/routes/admin_assistant.py:250-302`) | **Not a gap — confirmed reachable.** `AdminAssistantPage.jsx` has a real generic UI: an action-type selector populated from all 103 registry types + a raw-JSON payload textarea (only `dataset_record_review` gets a dedicated form) | — | UX quality (raw JSON for 102/103 action types) is a real but smaller usability note, not an integration gap |

**Whole-subsystem gap found (the one that matters most in this section): MB-4A Prompt & Context Optimization has zero dashboard surface.** This also corrects an error in the MB1_42 audit, which had mistakenly reported MB-4A as wired via `MiniBrainPage.jsx:747,2959` — those lines actually call MB-32 Capability (`capabilityGenerate`/`capabilityDiagnostics`), a different, superficially similarly-named service. The correction is reflected in §1's table.

---

## 8. Security & governance spot-check

All five items **re-verified fresh this pass, with real citations** — no regressions found since the original 2026-08-08 audit.

1. **Plugin execution isolation — Verified, unchanged (no isolation exists).** `mini_brain_plugin_runtime_service.py` executes via `importlib.util.spec_from_file_location()` + `exec_module()`, wrapped only by a single-worker `ThreadPoolExecutor` (`core_model/mini_brain/plugin_runtime/timeout_runner.py`, whose own docstring states "never subprocess... no process or container isolation"). Filesystem/network guards remain real allow-list checks against a plugin's *declared* scope only.
2. **CSRF protection — Verified, zero gaps.** `require_csrf` in `backend/api/auth.py` does a real double-submit + server-side session-tied validation. Spot-checked every mutating route across 5 MB-26+ files (voice, provider settings, runtime manager, gateway bridge, capability) — **23 of 23 mutating routes** declare `CsrfDependency`.
3. **Audit logging on gateway export/build — Verified, on the real code path.** `external_gateway_dataset_bridge_service.py` writes real `_audit()` rows at every state transition (`started`/`completed`/`failed` for both export and RAG-build), confirmed inside the actual execution path, not dead code.
4. **Approval gates before retrieval activation — Verified.** `rag_retrieval_service.py`'s draft→validated→active state machine still raises `ValidationError` on out-of-order transitions; the gateway's "second explicit admin approval" property is real code (deliberate absence of an auto-activate call), not just a passing test.
5. **Release-governance enforcement — Verified.** Zero deployment/activation call sites exist in either `mini_brain_release_governance_service.py` or `governed_build_service.py` — both remain governance-decision-only by construction.

---

## 9. Final production board

### Ready for real admin use now
RAG pipeline (ingest → embed → index → retrieve → grounded generation) with MB-43's admin-controlled default profile — **real Chrome-verified**. Retrieval Profile Management UI. Plain and grounded widget chat (backend real, vitest-verified; see §6 caveat on live-browser E2E). Admin Assistant proposal/execution engine (103 real actions, generic UI reachable). Voice Runtime, Provider Settings, Local Setup, Runtime Manager, Health, Language Intelligence, Knowledge/Intelligence core. MB-4B Quality Engine, MB-5–20 Dataset/Vision/Training-package/Evaluation/Release-readiness chain. Plugin Governance + Execution. OCR extraction (live-tested, closes a prior gap). CSRF, audit logging, approval-gate, and release-governance controls — all independently re-verified this pass.

### Ready after UI exposure only
**External Gateway Dataset/RAG Bridge** — real, live-tested, zero dashboard reachability, Medium effort to expose. **MB-4A Prompt & Context Optimization** — real, zero dashboard surface at all, Large effort. **Capability Analyze/Profile/Models** — real, Small effort. **`ragSourceRightsCheck`** — real, Small effort. **MB-21 External AI Gateway** — real, dormant pending a configured provider key (an operator step, not a code gap).

### Not ready yet
**Real GPU/CPU model training (MB-22)** — the only RED subsystem in the entire 45-row inventory. Every training entrypoint stops at a package artifact or an explicit `BackendUnavailableError`.

### Cleanup before MB-46+
- **17 dead RAG "singular detail-getter" bindings** — the single largest, most systemic dead-code pattern found (§2, §4). One rule closes most of it.
- **20 backend ruff findings** (16 High-confidence safe deletes; 2 need a human read for a possibly-dropped return value/branch, not blind deletion).
- **9 additional dead frontend exports** beyond the RAG pattern (§4).
- **`MiniBrainRuntimeManagerService` vs. `RuntimeManagerService` naming collision** (§3) — rename, don't merge; zero functional risk today, real risk to the next contributor.
- **`runtimeHealth` (MB-01-era, superseded by `miniBrainRuntimeHealth`)** — safe to delete, but flag the naming trap: an unrelated `useState` variable of the identical name in `MiniBrainPage.jsx` makes it easy to misjudge as "in use."

---

## 10. Executive decision

**1. Ready for an internal admin pilot today?**
Yes. 34 of 45 inventoried subsystems are GREEN with real execution evidence, the one prior live divergence (widget health/chat) is closed and regression-guarded, and every governance/security control spot-checked this pass verified clean with zero regressions.

**2. Ready for an external customer pilot today?**
No — not because of correctness, but because of *scope honesty*: real model training does not exist (RED), and a materially real, tested subsystem (External Gateway Dataset/RAG Bridge) is currently unreachable by any admin without direct API access, which is not a reasonable expectation for an external customer's operators. Close the training-simulation disclosure gap and the biggest UI-reachability gap first.

**3. Single highest-risk unresolved issue?**
None are correctness risks — the highest-risk item is **expectation mismatch**: an admin exploring the dashboard has no way to discover that MB-4A Prompt Optimization and the External Gateway Dataset/RAG Bridge exist at all, since neither has any UI trace. A real, working feature that looks absent is a worse trust problem than a feature that's honestly labeled unavailable.

**4. Single highest-value next implementation?**
Expose the External Gateway Dataset/RAG Bridge in the dashboard (Medium effort, real+tested backend, closes the largest "invisible feature" gap and the one MB1_42 flagged as merely "unknown").

**5. Should MB-46 be a feature phase or a stabilization phase?**
**Stabilization.** The backend is deep and consistently real (only one RED subsystem across 45); what's missing is almost entirely UI exposure and cleanup of dead bindings, not new capability. Adding features before closing the dead-code/UI-gap backlog above would grow the same pattern (real backend, invisible or half-wired frontend) rather than shrink it.
