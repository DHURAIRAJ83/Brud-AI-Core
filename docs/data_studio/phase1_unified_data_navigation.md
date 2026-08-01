# Phase 1 — Unified Data Navigation

## Goal

Reorganize every data-related Admin Dashboard page under one collapsible **Data** parent menu
item, without removing, rewriting, disabling, renaming incompatibly, or duplicating any existing
working feature. See [phase1_existing_data_system_audit.md](phase1_existing_data_system_audit.md)
for the full baseline this change is measured against.

## Baseline findings (summary)

- The Admin Dashboard has no client-side router; "routes" are plain `#PageName` hash strings read
  once on mount (`App.jsx`) and written via `window.history.replaceState` on selection. Preserving
  compatibility means preserving these exact strings, not URLs in the conventional sense.
- Six existing pages are genuinely data-related and were flat top-level Sidebar items: `Datasets`,
  `Documents`, `Corpus Builder`, `Knowledge & RAG`, `Pretraining Readiness`, `Evaluation`. Each
  already contains 5-18 internal tabs of its own (e.g. `ImportsPage` already renders inside
  `DatasetsPage`'s "Imports" tab; OCR review already lives inside `DocumentsPage`'s "Page Review"
  tab) — see the audit's §3.1 table.
- No Help registry, no frontend test tooling (`vitest`/`@testing-library`) existed before this
  phase.

## Navigation: before → after

**Before** (flat, 21 items):
`Overview, System, Datasets, Documents, Tokenizer, Core Model, Training, Base Training,
Instruction Tuning, Evaluation, Model Registry, Inference Runtime, Knowledge & RAG,
Conversation & Memory, Feedback & Improvement, Corpus Builder, Pretraining Readiness,
Chat Testing, Admin Assistant, Audit Logs, Settings`

**After** (21 pre-existing items unchanged in identity, 6 of them regrouped, 2 new pages added):

```text
Overview
System
Data  (collapsible, new)
├── Overview        (new: Data Overview)
├── Datasets        (existing, unchanged)
├── Documents       (existing, unchanged)
├── Corpus Builder  (existing, unchanged)
├── Knowledge & RAG (existing, unchanged)
├── Pretraining Readiness (existing, unchanged)
├── Evaluation      (existing, unchanged)
└── Help & Guide    (new: Data Help)
Tokenizer
Core Model
Training
Base Training
Instruction Tuning
Model Registry
Inference Runtime
Conversation & Memory
Feedback & Improvement
Chat Testing
Admin Assistant
Audit Logs
Settings
```

Every `active` string that existed before this change (`menuItems` in
`apps/admin-dashboard/src/components/Sidebar.jsx`) is still present, unrenamed, in the new
`menuItems` flat export — verified by `Sidebar.test.jsx`'s "keeps every pre-Phase-1 page key
reachable" test, which lists all 21 original keys literally and asserts membership.

### Deviation from the task's "recommended" submenu tree, and why

The task's example tree goes three levels deep (e.g. `Data → Add Data → Manual Entry`) and names
several leaves (`Chunk Editor`, `Tamil`/`English`/`Tanglish`, `Translation`, `Dictionary`,
`Instruction Q&A`, `Duplicates`, `Conflicts`, `Approval Queue`, `RAG Index`, `Training Export`,
`Evaluation Export`) that are not separate pages today — they are tabs inside the six pages above,
or do not exist at all (audit §5/§6). Fabricating extra top-level links that all resolve to the
same underlying page under different names would itself be the "duplicate/overlapping pages"
failure mode the task warns against, and the task explicitly permits omitting not-yet-implemented
items rather than inventing "Planned" placeholders for every one of them. Phase 1 therefore
implements a two-level menu (`Data → page`) matching the six pages that actually exist, plus the
two genuinely new pages (`Overview`, `Help & Guide`). This is recorded as a deliberate decision in
the audit doc, not an oversight.

## Existing pages reused (verbatim, unmodified)

`DatasetsPage.jsx`, `DocumentsPage.jsx`, `CorpusPage.jsx`, `RagPage.jsx`,
`PretrainingReadinessPage.jsx`, `ModelEvaluationPage.jsx` — none of these files were edited.
`DataOverviewPage.jsx` composes eight already-existing `services/api.js` functions
(`datasetStatistics`, `documents`, `qualitySummary`, `datasetDuplicates`, `datasetVersions`,
`corpusVersions`, `ragSpaces`, `baseModelReadinessEvaluations`); no new backend endpoint was added.

## Routes preserved

Verified directly (not just asserted) with a real browser session (Playwright + the existing
Chromium binary, driving the actual dev server and backend, screenshots retained in the session
scratch directory):

- Clicking a Data child updates the hash exactly as before (e.g. `#Documents`) and renders the
  same `DocumentsPage` component.
- **Hard refresh** while on `#Documents` (`page.reload()`, the true "F5" case) restores the exact
  same page, with the `Data` group auto-expanded and `Documents` marked `aria-current="page"`.
- **Bookmarked URL opened in a brand-new tab** (`#Corpus%20Builder`, first navigation of that tab,
  not an in-page hash edit) restores `Corpus Builder` with `Data` auto-expanded — the genuine
  "open a saved link" case, distinct from an in-page hash assignment (which, matching real
  browsers, does not reload the SPA document at all).
- Mobile off-canvas sidebar (`≤800px`) opens, shows the expanded `Data` group with no horizontal
  overflow (`scrollWidth === clientWidth` measured directly), and the existing overlay/close
  behaviour is untouched.

## Components changed

- `apps/admin-dashboard/src/components/Sidebar.jsx` — restructured from a flat string array into
  a `navTree` of flat items plus one `group` entry; added expand/collapse state, auto-expand when
  the active page is a Data child, `aria-expanded`/`aria-current`/`aria-label` attributes. Still
  exports a flat `menuItems` array for backward compatibility with anything that only cared about
  the full key list.
- `apps/admin-dashboard/src/App.jsx` — two new `if (active === ...)` branches added
  (`Data Overview`, `Data Help`); every existing branch is untouched.
- `apps/admin-dashboard/src/index.css` — additive rules only (`.nav-group*`, `.nav-children`,
  `.nav-item-planned` (reserved for future use, unused for now), `.data-overview-action`,
  `.help-entries`/`.help-entry*`). No existing selector was removed or renamed.
- New: `apps/admin-dashboard/src/pages/DataOverviewPage.jsx`,
  `apps/admin-dashboard/src/pages/DataHelpPage.jsx`,
  `apps/admin-dashboard/src/data/helpRegistry.js`.

## API changes

None. No backend file, migration, or schema version changed (schema remains v22). The Data
Overview page is a pure client-side composition of existing read-only endpoints.

## Accessibility behaviour

- `aria-expanded` on the Data group toggle, reflecting collapsed/expanded state.
- `aria-current="page"` on exactly one button at a time (the active page) — verified directly by a
  test that counts elements with `aria-current="page"` across the whole rendered sidebar.
- The Data group's children are wrapped in a `role="group"` region with `aria-label="Data pages"`.
- **Real bug found and fixed during verification**: the top-level `Overview` item and the new
  nested `Data → Overview` item both rendered with the identical accessible name `"Overview"` —
  indistinguishable to a screen-reader user navigating by name, even though sighted users can use
  the visual nesting/indentation as a cue. Fixed with a disambiguating `aria-label="Data Overview"`
  on the nested item, keeping the shorter visible label. Caught by
  `Sidebar.test.jsx`'s "expands on click" test (`getByRole` failed with "multiple elements found"),
  not assumed — this is exactly the kind of gap a pre-Phase-1 audit noted as having "no existing
  accessibility baseline" to regress against.
- Keyboard: the group toggle is a native `<button>`, reachable by Tab and activatable by
  `Enter`/`Space` — verified directly, not assumed from "buttons are naturally keyboard-accessible".
- No new horizontal overflow on mobile (measured directly).

## Test evidence

### Backend (unchanged, re-verified as a regression check — no backend files were touched)

- Baseline, before this Phase 1 UI work started: `test_dataset_api.py`, `test_dataset_phase6.py`,
  `test_document_pipeline.py`, `test_import_pipeline.py`, `test_corpus_api.py`,
  `test_phase20_corpus_api.py`, `test_rag_api.py`, `test_system_api.py`,
  `test_admin_assistant_api.py` — **70 passed**.
- Final: full `pytest` across `tests/backend`, `tests/database`, `tests/core_model` —
  **see exact count in the final report** (recorded there rather than duplicated here, since it
  was run once as the closing verification step).
- `ruff check .` — all checks passed, both before and after (no Python file was touched).

### Frontend

- `npm run build --prefix apps/admin-dashboard` — succeeds before and after every change,
  including after the Vitest devDependency addition.
- `npm run build --prefix apps/chatbot` — succeeds (this app was never touched).
- New Vitest + Testing Library suite (`npm test --prefix apps/admin-dashboard`, i.e.
  `vitest run`): **18 passed, 0 failed** across `Sidebar.test.jsx` (13 tests: key preservation, no
  duplicate keys, group render/expand/collapse, auto-expand on direct navigation, every Data child
  reachable and reporting its unchanged existing key, every non-Data item still present and
  clickable, single active-state invariant, ARIA/keyboard behaviour) and
  `DataOverviewPage.test.jsx` (5 tests: real-data success rendering, honest empty-state zeros,
  partial-failure isolation, total-failure honest error, navigation actions).
- Manual, real-browser verification (Playwright driving the actual Vite dev server against the
  actual running backend, a throwaway admin account created via `backend.admin_cli create-admin`
  for this purpose): screenshots and console/network logs captured for the initial render, expand/
  collapse, Data Overview's real loaded numbers, Data Help's bilingual toggle, hard refresh, and
  fresh-tab bookmark scenarios. This is where the layout bug below and the accessibility bug above
  were actually found — neither was caught by the automated tests alone.
- **Real layout bug found and fixed during manual verification**: `DataHelpPage` initially reused
  the existing `.data-list article` CSS class, which is a `display: flex; justify-content:
  space-between` rule designed for simple one-line list rows elsewhere in the app. Help entries
  have much richer content (paragraphs, lists, buttons), so this rule spread everything into a
  wide horizontal row instead of stacking it. Fixed by giving help entries their own
  `.help-entries`/`.help-entry` classes with `display: grid`/`display: block` instead of reusing
  an unrelated existing class that happened to have the same generic look.

## Deferred items

Everything listed in the audit's §8 ("Explicitly deferred") plus, specifically for this
implementation: a third menu level under `Data`; "Planned" (non-clickable) placeholder entries
(omitted per the task's own alternative, since the audit found no genuinely-missing-but-named
page that would need one); a dedicated backend Data Overview aggregation endpoint (the client-side
composition is sufficient for Phase 1's read-only needs); deep-linkable sub-tabs.

## Known limitations

- The six regrouped pages are visually "flatter" under Data than the task's recommended tree
  because each already contains many internal tabs — see the audit's §6/§9 for the reasoning.
- Vitest + Testing Library is new project infrastructure (not present before this phase); kept to
  the minimum needed to satisfy the task's own testing requirement.
- `datasetStatistics()` is called once by `DataOverviewPage` and separately by `DatasetsPage`'s own
  Overview tab — this is pre-existing duplication of a cheap read endpoint across pages, not
  something Phase 1 introduced or was asked to consolidate.
