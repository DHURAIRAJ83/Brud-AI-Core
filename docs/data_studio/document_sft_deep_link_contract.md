# Document SFT — Deep-Link Contract (Production Closure)

## URL shape

Extends the existing hash-only routing (`#PageName`, unchanged for every other
page) additively:

```
#Documents?document=<public_id>&tab=<tab_key>
#Document%20Wizard?document=<public_id>&step=<1-14>
```

Parsing/building lives in one place on each side, kept in parity by an
automated test:
- Python: `core_model/admin_assistant/dashboard_registry.py::DOCUMENT_NAVIGATION_TARGETS`,
  `resolve_document_navigation()`.
- JS: `apps/admin-dashboard/src/services/documentNavigation.js` (`parseHash`,
  `buildDocumentsHash`, `buildWizardHash`, `resolveDocumentNavigation`).
- Parity test: `tests/core_model/test_admin_assistant_registries.py::
  test_frontend_document_navigation_registry_matches_python_exactly` (regex-parses
  the JS file the same way the pre-existing `_real_nav_keys()` already parses
  `Sidebar.jsx` against `DASHBOARD_PAGES`).

## Supported `tab` keys (Documents)

`overview`, `pages`, `critical-pages` (also sets the page filter to "Critical
only"), `cleanup`, `tamil-quality`, `sft-generation`, `sft-candidates`,
`export`, `media-tables`, `security-review`. Each resolves to one of the 12
real tab labels `DocumentsPage.jsx` renders (`tabs` array) -- never a
fabricated tab.

## Supported `step` values (Document Wizard)

`11` (Dataset Handoff), `12` (Preview Split), `13` (Build Dataset Version),
`14` (Training Readiness) -- 1-indexed positions in the real 14-entry
`STEP_DEFINITIONS` array. Any other value (`< 1`, `> 14`, non-numeric)
selects the document but does not scroll/highlight anything, plus a
non-fatal notice.

## Two other real destinations

`chunks` (Chunk & Record Studio) and `assistant` (Admin Assistant) resolve
to a plain page-level navigation with no sub-state -- both are real pages,
but neither currently accepts a document-preselection parameter (Chunk &
Record Studio has no such prop; adding one was judged out of this pass's
"small and targeted" scope).

## Excluded: `history`

Considered and explicitly rejected: no History tab/section exists anywhere
in Documents or the Wizard. `resolve_document_navigation("history")` and
`DOCUMENT_NAV_TARGETS['history']` are both intentionally absent, and a test
(`test_no_fabricated_history_navigation_key_exists`) pins this down.

## Fallback behavior (implemented and tested)

| Input | Behavior |
|---|---|
| Valid document + valid tab | Opens that document on that tab |
| Valid document + invalid/unknown tab | Opens the document on `Overview`, shows "The requested tab is unavailable -- showing the default view instead." |
| Missing document param | Documents/Wizard load normally with their document list, no deep-link behavior |
| Unknown document public ID | Stable "The requested document was not found." notice, document list still shown -- never a blank screen |
| Invalid wizard step | Document opens, no scroll/highlight, "The requested wizard step is unavailable..." notice |

No internal numeric database ID is ever placed in the URL -- only public
IDs, exactly as every existing API response already exposes.

## State preservation

- **Tab change**: `DocumentsPage`'s `changeTab()` calls `onNavigationChange(documentPublicId, tab)`,
  which `App.jsx` turns into `history.pushState` + a hash update.
- **Refresh**: the initial-mount hash parse (`parseHash(window.location.hash.slice(1))`,
  computed once before the first `useState` call) re-derives the same state a
  full reload produces -- identical to the pre-existing pattern already used
  for `ProductionReadinessPage`'s `?tab=` deep link (see
  `e2e/tests/03-hash-deep-link.spec.js`).
- **Browser Back/Forward**: `App.jsx` registers a `popstate` listener that
  re-parses the hash and updates `active`/`documentNav` state. This only
  fires for real back/forward navigation across `pushState` entries (the
  browser's own behavior) -- consistent with the documented, pre-existing
  limitation that a same-document, hash-only `page.goto()` does not trigger
  a `hashchange`-driven re-render either (see the same spec file's own
  comment block); this was an accepted architectural limitation before this
  pass and remains one, not something this pass introduced or is
  responsible for closing.

## Dataset-version navigation

`DocumentWizardPage`'s "Open resulting dataset version" button now calls
`onOpenDatasetVersion(datasetVersionStatus.dataset_version_public_id)`
(a real public ID from `get_document_dataset_version_status`, unchanged
from the prior pass) instead of a bare page switch. `App.jsx` wires this to
`openDatasetVersion()`, which sets `datasetVersionId` state and navigates to
Datasets. `DatasetsPage` gained the smallest compatible prop,
`initialVersionPublicId`: defaults its own tab to "Versions" and adds an
`active` CSS class + a stable DOM id (`dataset-version-<public_id>`) to the
matching version article -- no redesign of the Datasets page.
