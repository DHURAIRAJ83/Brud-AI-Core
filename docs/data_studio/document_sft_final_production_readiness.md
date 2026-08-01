# Document SFT — Final Production Readiness (Production Closure)

## Summary

This pass closed the deep-link, Admin Assistant navigation, and browser/
regression-verification gaps disclosed at the end of the Production
Integration pass. No Schema-44 service, API contract, or dashboard tab from
the prior two passes was redesigned. Two genuine pre-existing registry bugs
were found and fixed early on (a stale `documents` tab list and a
`document_wizard` safety note that had gone false). Across several
verification sessions, the Playwright suite was executed repeatedly against
a real isolated backend/frontend/database, and that real browser execution
surfaced 4 genuine product bugs in the new navigation code -- none of which
any unit test or API-level test had caught, since they only manifest under
the timing and history-stack conditions a real browser produces. All 4 were
fixed and are confirmed holding. The final verification session isolated
and fixed two remaining test-file-only issues (not product bugs), reaching
**a clean 10/10 pass of the complete closure suite**. See "Bugs found and
fixed" below and the full evidence in `document_sft_full_browser_verification.md`.

## What changed

- **Deep-link navigation**: real, tested, additive query-string state on
  the existing hash router (`#Documents?document=...&tab=...`,
  `#Document Wizard?document=...&step=...`). See
  `document_sft_deep_link_contract.md`.
- **Admin Assistant navigation**: 10 new cases reusing the pre-existing
  `navigation_target` response contract and the pre-existing
  `entity_type`/`entity_public_id` context parameters. See
  `document_sft_admin_assistant_navigation.md`.
- **Navigation registry parity**: a new `DOCUMENT_NAVIGATION_TARGETS`
  registry (Python) mirrored exactly by `documentNavigation.js`, enforced
  by 11 new automated parity tests, plus a fix to the two stale
  `dashboard_registry.py` entries found during the audit.
- **Playwright**: a real spec (`09-document-sft-production-closure.spec.js`)
  authored, executed across multiple verification sessions, and finally
  reaching a clean **10/10 passed** run (isolated golden-path test run
  first, then the complete 10-test suite, both green). Full evidence in
  `document_sft_full_browser_verification.md`.
- **Regression**: no new migration; DB integrity/FK verified fresh; 231
  admin-dashboard frontend tests (231, up from 230, +1 new regression test
  locking in bug #4 below) + 34 chatbot frontend tests, all passing; both
  frontend production builds succeed; `ruff check .` and `git diff --check`
  both clean.

## Bugs found and fixed this pass

**Registry bugs (found via audit, before any browser execution):**

1. `dashboard_registry.py`'s `documents` `PageEntry.tabs` was missing 4 of
   12 real tabs (Overview, Security Review, Media & Tables, Tamil
   Corrections) added in the two prior passes but never synced here.
2. `document_wizard`'s `safety_note` claimed "This page never mutates
   anything" -- false since the Production Integration pass added real
   preview-then-confirm mutations (handoff ingest, dataset-version build
   confirm) directly to the Wizard. Both `purpose` and `safety_note` were
   corrected to describe the real, current 14-step, partially-mutating
   page.

**Product bugs (found only via actual Playwright execution, Attempts 1-6):**

3. `DocumentsPage`/`DocumentWizardPage`'s deep-link props were only applied
   inside a mount-only `useEffect` (`[]` deps) -- browser Back/Forward,
   which changes props on an already-mounted component (never a remount),
   was silently ignored. Fixed with a ref-guarded effect keyed on the
   deep-link props themselves.
4. `open()`'s `onNavigationChange` call read a stale `tab` value from
   closure, pushing a *wrong* browser-history entry immediately after every
   deep-link resolution and corrupting the history stack from the first
   load onward. Fixed by adding a `silent` option, used whenever a call is
   reconciling state *from* an incoming URL rather than a genuine user
   navigation.
5. `action()`'s post-mutation refresh call (fired after every approve/
   export/generate) was not silent -- if the admin navigated away before it
   resolved, it forcibly reverted the visible page back to Documents.
   Fixed by making that refresh call always silent.
6. Three Wizard handlers (`handleConfirmIngest`, `handleProposeVersion`,
   `handleConfirmBuild`) set a success `notice` then immediately called
   `loadDocument()`, which resets `notice` at its own start in the same
   synchronous tick -- the success message never actually reached the
   screen. Fixed by reordering; locked in with a new unit test.

## Authority boundary (re-verified this pass)

Every new Admin Assistant navigation code path is read-only by
construction (`_run_tool_logged()` → `run_tool()` → `READ_ONLY_TOOLS`
only). Directly verified: a real fixture document, 4 distinct navigation
messages sent, `training_jobs`/`admin_approvals`/
`document_sft_dataset_handoffs` row counts all `0` afterward.

## Known limitations

- `chunks`/`assistant` navigation targets are page-level only (no document
  preselection) -- disclosed, not fabricated as full deep links.
- No general React Router migration; only document/tab navigation actions
  push history entries, matching the existing pre-Closure precedent
  (`ProductionReadinessPage`'s `?tab=` deep link) exactly.
- `DocumentWizardPage`'s dropdown `onChange` and its deep-link re-apply
  `useEffect` both call `loadDocument()` for the same document-switch
  transition, which is redundant (though not observed to cause incorrect
  final state in the passing golden-path run). Not fixed this pass --
  doing so would mean touching `DocumentWizardPage`'s navigation state
  logic, out of scope for a verification-only window. Documented in
  `document_sft_full_browser_verification.md`'s root-cause section for a
  future pass to address if it ever becomes user-visible.

## Commit readiness

See the final report's "Commit-ready closure file list" /
"Pre-existing files excluded" sections. Nothing was staged or committed
this pass -- commit was not requested.
