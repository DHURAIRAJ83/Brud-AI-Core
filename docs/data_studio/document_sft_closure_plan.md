# Document SFT Production Closure — Plan

## Deep-link design

Extend the existing hash-only routing (`#PageName`) to `#PageName?document=<public_id>&tab=<key>`
(Documents) and `#Document Wizard?document=<public_id>&step=<key>` (Wizard). This is
additive to the existing pattern, not a redesign: `App.jsx` already special-cases a
handful of pages with extra "initial ID" props threaded from state
(`initialCandidatePublicId` etc.) -- Documents/Wizard get the same treatment, just with
a URL-visible representation instead of an in-memory-only one.

## Tab-state contract

A single source of truth, `DOCUMENT_NAVIGATION_TARGETS`, defined once in Python
(`core_model/admin_assistant/dashboard_registry.py`) and mirrored once in JS
(`apps/admin-dashboard/src/services/documentNavigation.js`), with a parity test that
regex-parses the JS file from Python (the same technique `test_admin_assistant_registries
.py` already uses to check `Sidebar.jsx` against `DASHBOARD_PAGES`). Only keys that map
to a real, already-existing UI section are included (`overview`, `pages`,
`critical-pages`, `cleanup`, `tamil-quality`, `sft-generation`, `sft-candidates`,
`export`, `media-tables`, `security-review`, `dataset-handoff`, `split-preview`,
`dataset-version`, `training-readiness`, `chunks`, `assistant`). `history` is excluded:
no History tab/section exists anywhere in Documents or the Wizard, and inventing a
route for it would violate "do not fabricate routes."

## Admin Assistant navigation contract

Reuses the *existing* `navigation_target` response field on
`AdminAssistantChatService.send_message()` (already present, already tested, already
consumed the same way for `dataset_discovery`/`rag_sandbox`/etc.) rather than inventing
a parallel `navigation` object. Adds `tab_key`, `document_public_id` (nullable), and a
bilingual `label`. `document_public_id` is populated only from a new optional
`document_public_id` parameter threaded through `send_message()` -- never inferred, never
guessed from message text.

## Browser-test data setup / isolated server plan / resource-safe strategy

Reuses the prior pass's committed Playwright fixtures/conventions exactly (isolated
temp DB, isolated backend/frontend ports, synthetic local PDF via the same `fitz`-based
generator pattern already used in the backend test suite). A `free -h` check
immediately before launch decides whether the suite runs at all this pass -- see the
final report for the actual reading and decision.

## Canonical regression strategy

Same disclosed policy as all three prior passes: a large, sequential, resource-bounded
targeted regression sweep with real pass/fail counts stands in for the full 70-batch
manifest, which is not attempted given this session's unbroken record of host/harness
restarts on that specific run.

## Failure-recovery rules

Any regression failure gets root-caused (product bug vs. stale test vs. environment)
before any fix is applied; a fix is followed by a focused rerun of the directly affected
file(s), not assumed to also validate the rest of the sweep.

## Exact files expected to change

`core_model/admin_assistant/dashboard_registry.py` (registry fixes + new navigation
target registry), `backend/services/admin_assistant_chat_service.py` (10 new navigation
cases), `backend/services/admin_assistant_tools.py` (navigation metadata on the relevant
read-only tools), `apps/admin-dashboard/src/services/documentNavigation.js` (new),
`apps/admin-dashboard/src/App.jsx`, `apps/admin-dashboard/src/pages/DocumentsPage.jsx`,
`apps/admin-dashboard/src/pages/DocumentWizardPage.jsx`,
`apps/admin-dashboard/src/pages/DatasetsPage.jsx` (smallest compatible version-select
prop only), new backend/frontend test files, a new Playwright spec (if resources allow).

## Explicit out-of-scope

Full React Router migration; deep-linking into any page outside Documents/Wizard/the
one Datasets version-select addition; a general-purpose Back/Forward history stack for
every dashboard page (only document/tab navigation actions push history entries);
anything listed in the task's own §26.
