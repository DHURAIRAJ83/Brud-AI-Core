# Phase 1 — Existing Data System Audit

Scope: read-only inspection of the current Brud AI Admin Dashboard, backend APIs, database
schema, and tests, performed before any Data Studio navigation change. This document is the
baseline the Phase 1 navigation restructure is measured against.

## 1. Backend entry point and schema

- Application entry point: `backend/main.py::create_app()`, mounted by `backend/api/router.py`
  under prefix `/api`.
- Current schema version: **22** (`backend/database/schema.py::SCHEMA_VERSION`), applied via
  `backend/database/migrations.py` (`_apply_v1` .. `_apply_v22`, each additive and forward-only,
  tracked in `schema_migrations`).
- No schema change is required for Phase 1 (see §7 — the new Data Overview page is built by
  composing existing endpoints client-side, not a new aggregation endpoint).

## 2. Backend data-related API surface (existing, unchanged)

All routes below are already registered in `backend/api/router.py` and already require an
authenticated admin session (`Depends(require_admin)`), most also CSRF-protected on mutations.

| Area | Router file | Prefix | Notes |
|---|---|---|---|
| Datasets (sources/records/quality/duplicates/versions/builds/exports) | `datasets.py` | `/api/admin/datasets` | 40 endpoints; quality, versioning, duplicate-detection, and build/export all live in this one router |
| Dataset imports | `imports.py` | `/api/admin/datasets/imports` | 10 endpoints; upload/parse/mapping/confirm/cancel/report |
| Documents (PDF/OCR extraction, page review, candidates) | `documents.py` | `/api/admin/documents` | 24 endpoints; capabilities, upload, analyze/process, page-level OCR review, candidate segmentation/import |
| Tamil corpus builder | `corpus.py` | `/api/admin/corpus` | 783 lines, 90+ endpoints (Phase 19+20): policies, sources & licences, snapshots/extraction, normalization/segmentation, quality/safety, dedup/contamination, collections/balance, builds/partitions, versions/export/manifest, compare, ingestion jobs, protected-content, tokenizer analysis, readiness, releases |
| RAG ingestion/index | `rag.py` | `/api/admin/rag` | 537 lines, 60+ endpoints: knowledge spaces/sources/versions, chunking, embedding models/runs, vector/keyword indexes, retrieval profiles, grounded answer, chat lab, evaluation, manifest |
| Training readiness / export | `pretraining_readiness.py` | `/api/admin/pretraining-readiness` | tokenizer-corpus builds, tokenizer candidate comparisons, resource estimates, dataset snapshots, smoke runs, readiness evaluations (17-dimension gate) |
| Model evaluation | `model_evaluation.py` | `/api/admin/model-evaluation` | suites/fixture-sets/fixtures, runs, human review, readiness assessment, comparisons, manifest |
| Admin Assistant | `admin_assistant.py` | `/api/admin/assistant` | read-only `overview`, allowlisted `actions`, proposal create/list/get/review/execute |

Not moved under "Data" in Phase 1 (kept top-level, out of scope for this reorganization):
`tokenizers.py`, `core_models.py`, `pretraining.py`, `training_reliability.py`, `base_training.py`,
`instruction_tuning.py`, `model_release.py`, `inference_runtime.py`, `conversation_memory.py`,
`feedback.py`. These operate on datasets as *input* but are training/runtime/model-lifecycle
concerns, not data curation, and the task's own "Reuse existing" list does not name them.

## 3. Frontend: layout, "routing", and pages (as they actually exist today)

**There is no client-side router library** (`apps/admin-dashboard/package.json` has no
`react-router` or equivalent). What Step 3 of the task calls "routes" are, in this codebase,
plain string keys:

- `App.jsx` holds `active` state, initialized from `decodeURIComponent(window.location.hash.slice(1)) || 'Overview'`.
- Selecting a sidebar item calls `window.history.replaceState(null, '', '#${encodeURIComponent(page)}')`
  then `setActive(page)`.
- `App.jsx` is a flat chain of `if (active === 'X') page = <XPage/>` — the *only* thing that makes
  a URL like `#Documents` "work" is that the string `'Documents'` appears, unchanged, in three
  places: `Sidebar.jsx`'s `menuItems`, this `if` chain, and whatever the admin bookmarked.

**Compatibility constraint for Phase 1**: as long as these exact string keys are preserved
verbatim (not renamed, not restructured into objects with different props), every existing
bookmarked `#PageName` URL keeps working, refresh keeps working, and `Topbar`'s `title={active}`
keeps showing the right heading — regardless of how the *sidebar visually groups* those same
keys. This is the mechanism the Phase 1 change relies on.

- Layout: `DashboardLayout.jsx` (sidebar + topbar + main), `Sidebar.jsx` (flat `<nav>` of
  buttons from a `menuItems` string array, 21 entries today), `Topbar.jsx` (title + admin name +
  logout + mobile menu toggle).
- Mobile: `.sidebar` becomes an off-canvas panel below 800px width (`@media (max-width: 800px)`
  in `index.css`), toggled by `Topbar`'s ☰ button; an `.overlay` closes it. This already works
  and must not be broken.
- No role/permission system beyond "is there a valid admin session" (`require_admin` /
  `getMe()`/`auth.admin`). There is no per-role UI hiding anywhere in the frontend today, so
  "preserve permission checks" for Phase 1 reduces to: keep every moved page behind the same
  authenticated `DashboardLayout` shell it already renders inside (trivially true — the page
  components themselves are untouched).
- No Help registry exists anywhere in the repository today (frontend or backend) — Phase 1's
  Help & Guide is a new, additive registry, not an extension of a pre-existing competing system.

### 3.1 Current Sidebar menu (21 flat items) and what each really is

| Sidebar label | `active` key | Page component | Real internal structure |
|---|---|---|---|
| Overview | `Overview` | `OverviewPage.jsx` | single view, backed by `GET /api/admin/overview` |
| System | `System` | `SystemPage.jsx` | single view |
| **Datasets** | `Datasets` | `DatasetsPage.jsx` | **8 internal tabs**: Overview, Sources, Records, Review Queue, Quality, Duplicates, **Imports** (renders `ImportsPage` inline), Versions |
| **Documents** | `Documents` | `DocumentsPage.jsx` | **5 internal tabs**: Overview, Upload, Processing, Page Review (OCR correction lives here), Candidates |
| Tokenizer | `Tokenizer` | `TokenizerPage.jsx` | 6 tabs |
| Core Model | `Core Model` | `CoreModelPage.jsx` | 8 tabs |
| Training | `Training` | `TrainingPage.jsx` | — |
| Base Training | `Base Training` | `BaseTrainingPage.jsx` | — |
| Instruction Tuning | `Instruction Tuning` | `InstructionTuningPage.jsx` | — |
| **Evaluation** | `Evaluation` | `ModelEvaluationPage.jsx` | 576 lines, multi-tab |
| Model Registry | `Model Registry` | `ModelRegistryPage.jsx` | — |
| Inference Runtime | `Inference Runtime` | `InferenceRuntimePage.jsx` | — |
| **Knowledge & RAG** | `Knowledge & RAG` | `RagPage.jsx` | **17 internal tabs**: Overview, Knowledge Spaces, Sources, Source Versions, Chunking, Chunk Quality, Embedding Models, Embedding Runs, Vector Indexes, Keyword Indexes, Retrieval Profiles, Retrieval Lab, Grounded Generation, RAG Chat Lab, Evaluation, Index Comparison, Manifest |
| Conversation & Memory | `Conversation & Memory` | `ConversationMemoryPage.jsx` | — |
| Feedback & Improvement | `Feedback & Improvement` | `FeedbackPage.jsx` | — |
| **Corpus Builder** | `Corpus Builder` | `CorpusPage.jsx` | **18 internal tabs** (largest page, 1596 lines): Overview, Policies, Sources & Licences, Snapshots & Extraction, Normalization & Segmentation, Quality & Safety, Deduplication & Contamination, Collections & Balance, Builds & Partitions, Versions/Export/Manifest, Compare, Governance & Ingestion, Profiles, Label Correction, Protected Content, Balance/Partition Preview, Tokenizer & Readiness, Releases |
| **Pretraining Readiness** | `Pretraining Readiness` | `PretrainingReadinessPage.jsx` | 7 tabs: Overview, Tokenizer Corpus, Tokenizer Candidates, Model Profiles, Dataset Snapshot, Training Config & Smoke Runs, Readiness |
| Chat Testing | `Chat Testing` | *(none — falls through to `PlaceholderPage`)* | **not implemented yet**, pre-existing gap, not introduced by Phase 1 |
| Admin Assistant | `Admin Assistant` | `AdminAssistantPage.jsx` | governed proposal/review workflow (Phase 22) |
| Audit Logs | `Audit Logs` | *(none — `PlaceholderPage`)* | **not implemented yet**, pre-existing gap |
| Settings | `Settings` | *(none — `PlaceholderPage`)* | **not implemented yet**, pre-existing gap |

Bold rows are the ones moving under **Data** in Phase 1. `ImportsPage.jsx` is **not** an orphaned
page — it already renders reachably as the "Imports" tab inside `DatasetsPage`. There is no
separate top-level "Imports" sidebar entry today, and Phase 1 does not add one (see §8, deferred).

## 4. Reusable components

- `Sidebar.jsx` — extended (not replaced) to support one collapsible grouped entry alongside the
  existing flat entries; same DOM idiom (`<button>` per item), same CSS classes for buttons.
- `DashboardLayout.jsx`, `Topbar.jsx` — untouched; `active` and `onSelect` contracts unchanged.
- `StatusCard.jsx` — reused as-is for the new Data Overview page's metric tiles (same component
  `OverviewPage.jsx` already uses).
- CSS: `.dashboard-tabs`/`.status-card`/`.metric-grid`/`.data-list`/`.notice`/`.card-grid` classes
  in `index.css` are reused for the new Overview and Help pages rather than inventing new classes.
- `services/api.js` — every function the new Data Overview page needs already exists:
  `datasetStatistics`, `datasetVersions`, `datasetDuplicates`, `qualitySummary`, `documents`,
  `corpusReleases` / `corpusVersions` / `corpusBuilds`, `ragSpaces`, `baseModelReadinessEvaluations`.
  No new API client function beyond simple read calls is required, and no new backend route.

## 5. Missing items (real gaps, not to be built in Phase 1)

- No client-side router (hash-string convention only, see §3).
- No Help/guide registry of any kind.
- No frontend automated-test tooling at all: `apps/admin-dashboard/package.json` has an empty
  `devDependencies` and no `test` script; there is no `vitest.config`/`jest.config` anywhere in
  the repo. **Phase 1 must introduce minimal test tooling to satisfy the task's own "frontend
  tests pass" completion criterion** — see §9. This is infrastructure, not new product
  functionality, and is scoped as narrowly as possible (Vitest + Testing Library, no other
  frontend dependency changes).
- No standalone "Manual Entry", "Chunk Editor", "Tamil/English/Tanglish editor", "Translation
  review", "Dictionary", "Instruction Q&A", "Conflicts", "Approval Queue", "RAG Index" (as a
  distinct export target), "Training Export" (as a distinct target from Pretraining Readiness),
  or "Evaluation Export" (as a distinct target from Evaluation) page — these are all named in the
  task's *recommended* submenu tree but do not exist as separate pages; the closest real
  functionality already lives inside the tabs of `DatasetsPage`, `DocumentsPage`, `CorpusPage`,
  `RagPage`, `PretrainingReadinessPage`, or `ModelEvaluationPage` (§3.1). No permission or role
  hierarchy beyond single-tier admin auth.

## 6. Duplicate or overlapping pages

- None found among the pages being moved. `ImportsPage` is reused *by* `DatasetsPage` (composition,
  not duplication — same component, one mount point).
- Risk introduced if the "recommended" submenu tree were implemented literally: several of its
  leaf names (`Records`, `Quality`, `Duplicates`, `Dataset Versions`, `RAG Index`) would have to
  point at the *same* underlying page as sibling leaves (`Dataset Studio`, `Review`,
  `Versions & Export`), which would look like distinct features while being one page's internal
  tab — this is exactly the "duplicate/overlapping" failure mode the task warns against. Phase 1
  avoids it by collapsing the recommended tree to real page granularity (§7) rather than
  fabricating extra clickable entries that land on an identical screen under a different name.

## 7. Planned Phase 1 changes

1. `Sidebar.jsx`: introduce one collapsible **Data** group containing, in order: a new
   **Overview** entry (`Data Overview`, new page), the six existing real pages that are
   data-related (`Datasets`, `Documents`, `Corpus Builder`, `Knowledge & RAG`,
   `Pretraining Readiness`, `Evaluation` — **`active` keys unchanged**), and a new
   **Help & Guide** entry (`Data Help`, new page). All other existing top-level items are
   untouched, same order, same keys.
2. `App.jsx`: add two new `if (active === ...)` branches for `Data Overview` and `Data Help`.
   Every existing branch is left exactly as-is.
3. New `DataOverviewPage.jsx`: read-only aggregation built entirely from the existing API
   functions in §4 — no new backend endpoint, no new migration. Honest `"Not available in the
   current system"` when a subsystem's data can't be fetched, never a fabricated number.
4. New `helpRegistry.js` + `DataHelpPage.jsx`: bilingual (EN/TA) contextual help entries for
   the eight implemented Data submenu pages, in the shape the task specifies.
5. `index.css`: additive rules only, for the group toggle, indentation of child items, and a
   "Planned" (disabled) item style — no existing class renamed or removed.
6. Minimal Vitest + Testing Library setup (`package.json` devDependencies, `vite.config.js`
   `test` block) and a focused test file for navigation + Data Overview states.
7. No backend file changes, no new migration, no schema version bump.

## 8. Explicitly deferred (not built in Phase 1)

Per the task's own "explicitly out of scope" list, plus what §5/§6 above rule out for this phase:
a distinct source-rights database; a manual Data Studio; a new PDF/OCR engine; a visual chunk
editor; a dictionary parser; a Tanglish editor; a translation review studio; a new duplicate
semantic engine; a new dataset-approval engine; new RAG/training export logic; a floating Admin
Assistant chatbot; AI-assisted dataset generation; a real client-side router; deep-linkable
sub-tabs (e.g. `#Documents/PageReview`); a third menu level (Add Data → Manual Entry, etc.) beyond
what real distinct pages justify; a dedicated "Imports" top-level entry (it stays reachable via
Datasets → Imports, unchanged); a new backend Data Overview aggregation endpoint (client-side
composition is sufficient and lower-risk for Phase 1).

## 9. Risks and compatibility constraints

- **Highest-risk mistake**: renaming or restructuring any of the six moved pages' `active` string
  keys. This would silently break bookmarked hash URLs and the `Topbar` title. Mitigation: the
  Sidebar's grouped-item data structure carries the *same* string as both `label` and `key` for
  every moved item; App.jsx's existing `if` chain is not touched at all.
- **Test tooling gap**: adding Vitest is new project infrastructure, not just test files. Kept to
  the minimum (one dev-dependency group, one config block) and documented explicitly rather than
  silently expanded into a broader tooling change.
- **No existing accessibility baseline**: there were zero ARIA/a11y tests before Phase 1, so
  "preserve accessibility behaviour" has no prior regression bar; Phase 1's new ARIA attributes
  (`aria-expanded`, `aria-current`) are additions, verified by the new tests themselves.
- **Large pages, coarse granularity**: because six of the moved pages each contain 5-18 internal
  tabs, the visual "Data" menu will look shallower than the task's recommended tree. This is a
  deliberate, documented trade-off (§6), not an oversight.

## 10. Baseline verification (pre-change)

- `npm run build --prefix apps/admin-dashboard` — succeeds (see Phase 1 navigation doc for the
  exact output captured before and after this change).
- Targeted backend baseline (`test_dataset_api`, `test_dataset_phase6`, `test_document_pipeline`,
  `test_import_pipeline`, `test_corpus_api`, `test_phase20_corpus_api`, `test_rag_api`,
  `test_system_api`, `test_admin_assistant_api`) and the full `pytest`/`ruff` baseline are recorded
  in `phase1_unified_data_navigation.md` §"Test evidence" with exact pass counts, both before and
  after the Phase 1 change.
