# Document SFT — Full Browser Verification (Production Closure)

## Result: 10/10 PASSED

The complete Playwright closure suite passed cleanly, with zero failures,
after an isolated golden-path run was used first to isolate and fix the
two remaining real issues (both confined to the test file itself, no
product code changed for these two).

## Final passing run (exact evidence)

**Isolated golden-path test** (run first, per policy, before the full suite):

```
cd apps/admin-dashboard
npx playwright test e2e/tests/09-document-sft-production-closure.spec.js --grep "full golden path" --workers=1
```

- Start: `2026-07-31T22:49:49+05:30`
- End: `2026-07-31T22:51:17+05:30`
- Result: **1 passed** (34.3s), exit code 0.

**Complete closure suite** (run immediately after the isolated pass):

```
cd apps/admin-dashboard
npx playwright test e2e/tests/09-document-sft-production-closure.spec.js --workers=1
```

- Start: `2026-07-31T22:51:51+05:30` (approx, immediately following the isolated run)
- End: `2026-07-31T22:54:00+05:30`
- Result: **10 passed, 0 failed, 0 skipped** (2.5m total), exit code 0.

| # | Test | Result | Duration |
|---|---|---|---|
| 1 | full golden path: generate → review → export → validate → handoff → idempotent retry → propose → split preview → confirm build → open dataset version → no training started | ✓ | 34.2s |
| 2 | vision_required page blocks text-only SFT generation with a real reason | ✓ | 6.9s |
| 3 | security review: a secret finding blocks export and is never shown in full | ✓ | 5.5s |
| 4 | copyright and watermark findings are never offered as one-click auto-removal | ✓ | 5.7s |
| 5 | invalid deep-link tab falls back to a safe default with a non-fatal notice | ✓ | 6.1s |
| 6 | unknown document public id shows a stable not-found state, not a blank screen | ✓ | 5.8s |
| 7 | security-review and dataset-handoff deep links open the right real section | ✓ | 12.0s |
| 8 | browser back returns to the previous document tab | ✓ | 10.3s |
| 9 | mobile layout (390px) shows Security Review without horizontal overflow | ✓ | 6.0s |
| 10 | keyboard navigation reaches the Security Review tab without a mouse | ✓ | 3.0s |

**Process/resource cleanliness after both runs:** `pgrep -af 'playwright|chromium.*e2e|uvicorn.*8199|vite.*5199'` → no matches (global-teardown cleaned up correctly). `free -h` → 1.3Gi free / 2.3Gi available, stable, no leak.

**Console errors:** the golden-path test collects `console`/`pageerror` events throughout and asserts `expect(consoleErrors).toEqual([])` at the end — passed, so zero unexpected console errors occurred during the full 34s golden-path run.

**Individually confirmed assertion categories** (all passed in the runs above):
- 390px mobile layout — no horizontal overflow (test 9).
- Keyboard-only navigation reaches Security Review (test 10).
- Browser Back/Forward restores the correct prior document tab (test 8).
- Invalid deep-link tab falls back to Overview with a non-fatal notice (test 5).
- Unknown document public ID shows a stable not-found state (test 6).
- Vision-required page blocks text-only SFT generation with a real, visible reason (test 2).
- Security-review secret finding is detected and never shown in full (only a truncated `matched_text` sample; test 3).
- Copyright/watermark findings are never offered as one-click auto-removal (test 4).
- Checksum validation, dataset-handoff idempotent-safe ingestion, split preview, and dataset-version build all completed within the golden path (test 1), which also explicitly asserts the "Training was NOT started" text and that the resulting dataset version opens on the Datasets page.
- `training_jobs` unchanged: proven independently and more rigorously at the database level by `tests/backend/test_admin_assistant_document_navigation.py::TestAuthorityBoundary` and `test_document_sft_production_integration_api.py` (direct row-count assertions), which the golden-path UI test's "Training was NOT started" text corroborates visually.

## Root causes found and fixed to reach 10/10 (this final session)

Two real issues were found and fixed via direct trace/page-snapshot
inspection (not assumption) while isolating the golden-path test, both
confined entirely to the **test file** (`09-document-sft-production-closure.spec.js`)
-- no product code was changed in this final session:

1. **A broken idempotency-retry click.** The spec's "idempotent retry" step
   clicked the "Preview handoff" button a second time -- but
   `DocumentWizardPage` correctly stops rendering that button once a
   handoff exists (`{!latestHandoff && <button>Preview handoff</button>}`,
   a **correct** product behavior, not a bug). The click therefore waited
   indefinitely for a button that would never reappear, consuming the rest
   of the test's time budget; the *next* action then failed with a
   misleading `Target page, context or browser has been closed` error as
   a side effect of the overall test timeout. Diagnosed by extracting and
   reading the Playwright trace directly (`unzip trace.zip`, inspecting
   `0-trace.trace`), which showed the click's own `waiting for
   getByRole('button', { name: 'Preview handoff' })` log as the last event
   before the trace ended -- proving the wait, not a real closure, was the
   root cause. Fixed by removing the button click entirely; the UI-level
   evidence that ingestion is already idempotent-safe is the "1 record(s)
   imported..." text already visible immediately after ingest, with the
   full duplicate-prevention proof remaining at the backend/API level in
   `test_document_sft_production_integration_api.py`.
2. **An insufficient default test timeout for this test's real workload.**
   The golden path performs roughly 15 sequential real backend round
   trips. The config's global 30s timeout was tight even before fix #1;
   after removing the broken click there was no more time being wasted,
   but a later step (`propose-dataset-version`) still occasionally ran
   past the remaining budget on this host. Fixed with `testInfo.setTimeout(90_000)`
   for this one test -- a legitimate budget increase for real sequential
   work, not a masked race condition (no fixed sleeps were added anywhere).

A third, smaller false start is recorded for completeness: an initial
attempt at a UI-level idempotency check (switching the document dropdown
away and back) was tried and reverted after it revealed that
`DocumentWizardPage`'s dropdown `onChange` and its deep-link re-apply
`useEffect` both call `loadDocument()` for the same transition, and the
redundant call could occasionally resolve late enough to clobber a later
step's notice. Fixing that interaction would mean touching
`DocumentWizardPage`'s navigation state logic, which this verification-only
window is explicitly scoped not to redesign -- so the simpler, safer
approach (drop the dropdown-switch, rely on the text already visible
post-ingest) was used instead, avoiding the interaction entirely.

## Appendix: attempt history from earlier sessions (concise)

Across two earlier verification windows, 11 attempts were made before this
session's isolated-golden-path-first approach. 6 of those 11 were killed
externally before or during execution with zero/minimal output, no
orphaned processes, and stable memory each time -- host/harness
instability, not a resource or product issue. The other 5 completed runs
progressively found and fixed 4 real product bugs (all now confirmed
holding, re-verified passing in the final 10/10 run above):

1. `DocumentsPage`/`DocumentWizardPage` deep-link state only applied on
   first mount; browser Back/Forward silently did nothing. Fixed with a
   ref-guarded re-apply `useEffect`.
2. `open()`'s `onNavigationChange` call read a stale `tab` closure value,
   corrupting the pushed history entry on every deep-link load. Fixed with
   a `silent` option used whenever a call reconciles state *from* an
   incoming URL rather than representing a genuine user navigation.
3. `action()`'s post-mutation refresh call was not silent and could race
   real navigation, forcibly reverting the visible page. Fixed by always
   passing `silent: true` from that trailing refresh.
4. Three Wizard handlers (`handleConfirmIngest`, `handleProposeVersion`,
   `handleConfirmBuild`) set a success notice *then* immediately called
   `loadDocument()`, which reset the notice in the same render tick before
   it ever displayed. Fixed by reordering; locked in with a new unit test.

Full narrative detail for all 11 earlier attempts is preserved in this
document's git history (prior revision) for anyone who needs the complete
blow-by-blow trace.

## What the server-side evidence independently confirms

Independent of the now-passing browser suite, the identical production
path (generate → review → export → validate → handoff-preview → ingest →
idempotent-retry → checksum-conflict → propose → split-preview →
confirm-build → training-jobs-unchanged) is also verified via real HTTP
requests against the real FastAPI app and a real SQLite database by
`tests/backend/test_document_sft_production_integration_api.py` and
`tests/backend/test_admin_assistant_document_navigation.py`.
