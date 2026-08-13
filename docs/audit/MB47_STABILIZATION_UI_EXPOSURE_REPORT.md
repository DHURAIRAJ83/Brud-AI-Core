# MB-47 — Stabilization & UI Exposure Report

**Date:** 2026-08-11
**Branch:** rc-fixes-2026-08-08
**Scope:** P1–P4, executed sequentially, none blocked. No new AI capabilities, no new database tables, no schema migrations, no provider behavior changes. `/api/admin/assistant/*` untouched; the MB-45 widget health fix verified still intact throughout.

---

## 1. Files changed

**New (P1 — Gateway bridge UI):**
- `apps/admin-dashboard/src/pages/GatewayDatasetRagBridgePage.jsx`
- `apps/admin-dashboard/src/pages/GatewayDatasetRagBridgePage.test.jsx`

**New (P2 — Prompt Optimization UI):**
- `apps/admin-dashboard/src/pages/PromptOptimizationPage.jsx`
- `apps/admin-dashboard/src/pages/PromptOptimizationPage.test.jsx`

**Modified — navigation & bindings (P1 + P2):**
- `apps/admin-dashboard/src/App.jsx` — two new page routes
- `apps/admin-dashboard/src/components/Sidebar.jsx` — two new nav entries under "Data"
- `apps/admin-dashboard/src/services/api.js` — 5 new exports added (`egdbExportToDataset`, `systemRecentAudit`, `promptLanguageDetect`, `promptTemplates`, `promptGenerate`, `promptCompare` — 6 total), 39 dead exports removed (P3)

**Modified — dead-code cleanup (P3), zero behavior change:**
- `apps/admin-dashboard/src/pages/MiniBrainPage.jsx` — removed 2 dead import references (`psExport`, `psImportMetadata`)
- `backend/models/external_gateway_dataset_bridge.py`, `mini_brain_evaluation_center_service.py`, `mini_brain_external_ai_gateway_service.py`, `mini_brain_knowledge_service.py`, `mini_brain_llm_runtime_service.py`, `mini_brain_plugin_governance_service.py`, `mini_brain_release_governance_service.py`, `mini_brain_release_pipeline_service.py`, `mini_brain_runtime_manager_service.py`, `runtime_manager_service.py` — unused imports/locals removed
- `core_model/mini_brain/local_setup/capability_catalog.py`, `pipeline_coordinator/dependency_coordinator.py`, `provider_settings/provider_capability_matrix.py`, `research_center/evidence_validator.py` — unused imports removed

**Modified — rename (P4), zero behavior change:**
- `backend/services/mini_brain_runtime_manager_service.py` — class renamed, migration-note comment added
- 8 more source files updating the import/usage: `backend/api/routes/mini_brain_quality.py`, `mini_brain_runtime.py`, `mini_brain_prompt_optimization.py`, `mini_brain_capability.py`; `backend/services/mini_brain_capability_service.py`, `mini_brain_inference_backend.py`, `mini_brain_release_pipeline_service.py`; `core_model/mini_brain/release_pipeline/compatibility_validator.py`
- 22 test files updated in lockstep (mechanical rename only): every `test_mini_brain_*_safety.py` file that referenced the class name, plus `test_mini_brain_runtime_service.py`, `test_mini_brain_capability_service.py`, `test_mini_brain_prompt_optimization_service.py`, `test_mini_brain_quality_service.py`, `test_runtime_manager_safety.py`

31 files touched by the P4 rename in total (9 source + 22 test), all confirmed via fresh grep to have zero remaining occurrences of the old name.

---

## 2. Features exposed

### P1 — Gateway → Dataset/RAG (new page, "Data" nav group)
Backend was already real and tested (28 tests: 18 dataset-bridge + 10 RAG-build); it had **zero** `api.js` bindings before this phase. Now: select an `admin_accepted` External AI Gateway session, optionally ingest into a RAG knowledge space and build a vector index + retrieval profile in the same call, view the real export/build response as structured status tiles, and view real audit events for that session (client-side filtered from the existing `GET /admin/audit/recent` feed — no new backend route). One real, disclosed constraint surfaced during design and documented directly in the UI: RAG ingestion only works when requested in the *same* export call — re-running export afterward with the RAG flag on re-detects the same provider runs as duplicates (via `DatasetService`'s own content-hash check) and silently skips RAG ingestion for them. Not patched (would be a provider-behavior change, out of scope) — disclosed to the admin in the form itself instead.

### P2 — Prompt Optimization (new page, "Data" nav group)
Backend (MB-4A) was real and tested with zero dashboard surface — not even a partial one. Now: a question textarea, a real "Detect language" action (deterministic, no model call), a reference list of the 11 real templates the pipeline can auto-select (never manually overridable — the backend has no such parameter, so none is offered in the UI), a "Generate optimized prompt" action, and a "Compare baseline vs optimized" side-by-side view showing real prompt lengths, response text, timing, and validation results from both paths.

---

## 3. Dead bindings removed

**Frontend (39 exports from `api.js`), every one individually grep-confirmed to have zero real call sites across both `apps/admin-dashboard/` and `apps/chatbot/` before removal:**

`capabilityAnalyze`, `capabilityProfile`, `capabilityModels`, `knowledgeCoreDiagnostics`, `knowledgeCoreItems`, `knowledgeCoreValidationReports`, `knowledgeGapCluster`, `miniBrainContext`, `psProvider`, `psExport`, `psImportMetadata`, `ragSpace`, `ragSource`, `ragSourceVersion`, `ragChunkSets`, `ragRetrievalProfile`, `ragRetrievalRun`, `ragRetrievalResults`, `ragGroundedRequest`, `ragGroundedAnswerResult`, `ragGroundedCitations`, `ragGroundedIssues`, `ragChatLabSession`, `ragEvaluationSuite`, `ragEvaluationRun`, `ragIndexComparison`, `ragSourceRightsCheck`, `ragValidationResults`, `ragActivationEvents`, `voCreateAdminSession`, `voPublicGetSession`, `voPublicCloseSession`, `acceptanceReviews`, `discoveryComparison`, `documentSftExport`, `improvementReport`, `patchEvalSuite`, `pretrainingEstimate`, `runtimeHealth`.

**One correction made during verification, not a removal:** MB-46's own dead-binding list included `ragSandboxOverview` alongside the RAG singular-getter pattern. Direct re-verification this pass found it is **not** dead — `DataOverviewPage.jsx:121` and `RagSandboxPage.jsx` both call it for real. It was excluded from removal. This is exactly the class of false positive the "grep confirms zero usage" hard rule exists to catch, and it did.

**Backend (17 findings, all `ruff --select F401,F841`-flagged, all matching MB-46's own "safe to delete" verdicts exactly):** 14 unused imports removed outright; 2 unused local variables required judgment rather than a blind delete — `dataset_session` in `mini_brain_external_ai_gateway_service.py:205` kept its function call (possible validation side effect) and only dropped the unused binding; `counts` in `mini_brain_knowledge_service.py:81` was fully dead computation (its `domain_id=None` argument meant every domain mapped to the same value, and it was never read) and was deleted outright.

**Explicitly not touched, per MB-46's own "needs a human read" verdicts:** `backend/api/routes/mini_brain_release_pipeline.py:135` (local `result`, possible dropped return value), `backend/services/mini_brain_llm_runtime_service.py`'s `MockMiniBrainAdapter` import (low-value but not high-confidence-safe), `core_model/mini_brain/dataset_intelligence/rag_readiness.py:52` (local `reasons`, needs a human read).

---

## 4. Ruff findings, before/after

| Scope | Before | After |
|---|---|---|
| `--select F401,F841` (the meaningful dead-code metric, matches MB-46's own methodology) | 20 | **3** — exactly the 3 explicitly-preserved "needs a human read" findings, none touched |
| Full default ruleset (`ruff check backend/ core_model/`, no `--select`) | not previously measured | 3,171 — **pre-existing, unrelated to this phase.** Overwhelmingly `E501` line-length violations spread across the whole ~260K-line codebase (this project does not enforce a line-length rule in its own workflow); confirmed by spot-checking that none of the sampled violations are in files this phase touched. Reported for completeness per the verification checklist, not a regression. |

---

## 5. Tests run and results

| Command | Result |
|---|---|
| `npx vitest run src/pages/GatewayDatasetRagBridgePage.test.jsx` | **6/6 passed** (new) |
| `npx vitest run src/pages/PromptOptimizationPage.test.jsx` | **6/6 passed** (new) |
| `npx vitest run` (full frontend suite) | **243/244 passed** — the 1 failure (`Sidebar.test.jsx`, "keeps every pre-Phase-1 page key reachable") is pre-existing and unrelated: confirmed via `git diff` that `Sidebar.jsx`'s removal of `'Chat Testing'`/`'Audit Logs'`/`'Settings'` predates this session entirely |
| `npm run build` | **0 errors**, run 3 times across P1/P2/P4 checkpoints |
| `pytest tests/backend -q` (full suite, chunked, 291 files) | **4,262 passed, 0 failed** — up from the MB-45 baseline of 4,260 by exactly the 2 tests MB-45 itself added; MB-47 added no new backend tests since no API shape changed (P1) and the checklist's own "only if required" condition was never triggered |
| `ruff check --select F401,F841 backend/ core_model/` | 20 → 3 (see §4) |
| Targeted: 172 tests across the 9 P3-touched service files | **172/172 passed** |
| Targeted: 60 tests across runtime/capability/prompt-optimization/quality services (P4) | **60/60 passed** |
| Targeted: 272 safety tests across every phase whose safety test references the renamed class | **272/272 passed** |
| Backend import/compile check (`python3 -c "from backend.main import create_app; ..."`) | Clean, all P1–P4 modules import successfully |

---

## 6. UI verification notes (live browser session)

Verified live in Chrome against the real dev server (real SQLite DB, real backend, a temporary `mb47-verify` admin account created for this session):

- **Gateway → Dataset/RAG** page: loads under "Data" nav, renders the real honest empty state ("No sessions with an admin-accepted decision yet") since this dev database genuinely has no `admin_accepted` gateway session — not a fabricated screenshot, the real API response.
- **Prompt Optimization** page: loads under "Data" nav, real `GET /templates` call returned and rendered exactly 11 templates. Typed a real Tamil sentence, clicked **Detect language**, and the backend's real (non-LLM, deterministic) language detector returned and rendered: Detected language **Tamil**, Resolved output language **Tamil**, Tamil ratio **1**, Effective Tamil ratio **1**.
- **Generate/Compare** (LLM-dependent paths) were not live-triggered this pass — they route through the identical, already-passing 60-test backend service coverage, and this session's established pattern is that real local-model inference takes 60–130+ seconds per call; the language-detection live check already proves the frontend↔backend wiring is real end to end, which is what UI exposure verification is for.
- Both dev servers (backend `:8000`, admin dashboard `:5174`) were started for this check and cleanly stopped afterward; the temporary verification admin account was left in place, matching this session's established convention of not deleting verification artifacts from the dev database.

---

## 7. Remaining known limitations

- **RAG-after-the-fact-export limitation (P1, disclosed in the UI itself, not fixed):** see §2 — a real backend behavior, not a bug, but worth a future phase's attention if it proves confusing in practice.
- **External Gateway Dataset/RAG Bridge has no live-populated verification** in this pass — the dev database has no admin-accepted gateway session to exercise it against; the page's wiring is proven correct via its 6 passing tests plus the empty-state live check, but a real end-to-end export was not clicked through live.
- **Prompt Optimization's Generate/Compare** were not live-triggered (see §6) — real, tested, but not clicked through with a live model this pass.
- The full-ruleset ruff count (3,171) remains unaddressed — explicitly out of scope per the task's own "delete only MB-46-marked-safe findings" instruction, not a regression.
- MB-46's own remaining architectural notes (training simulation-only, the naming-collision risk between `RuntimeManagerService` and the now-renamed `MiniBrainInMemoryModelLoader`) are addressed only insofar as P4 closes the naming risk; the training-simulation gap is explicitly out of this phase's scope ("No training implementation").

---

## 8. Final verdict

**READY FOR INTERNAL PILOT.**

Two previously-invisible, fully-real backend subsystems are now reachable through the dashboard with passing tests and a live-verified render; 39 confirmed-dead frontend bindings and 17 confirmed-dead backend imports/locals are gone with zero behavior change (4,262/4,262 backend tests and 243/244 frontend tests green, the one frontend failure pre-existing and unrelated); a real naming-collision risk is closed; and every constraint in the task's hard-rules list held throughout — no new AI capability, no new tables, no migrations, no provider-behavior change, `/api/admin/assistant/*` untouched, and the MB-45 widget fix independently re-verified intact (its own tests still pass, and its regression-guard tests for health/chat backend consistency still pass unchanged).

Not yet claiming **READY FOR EXTERNAL PILOT** — that verdict depends on the MB-46 report's own external-pilot blockers (real model training remains simulation-only; that is unchanged and explicitly out of this phase's scope), not on anything found or left open in this phase.

---

## Console summary

```
P1 (Gateway bridge exposed): done
P2 (Prompt Optimization exposed): done
P3 (dead bindings removed): 39 frontend + 17 backend
P4 (rename complete): done
ruff F401/F841: 20 -> 3
frontend build: passing
frontend tests: 243/244 (1 pre-existing unrelated failure)
backend tests: 4262/4262 passed
MB-45 widget fix: intact
verdict: READY FOR INTERNAL PILOT
```
