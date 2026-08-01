# Document SFT — Admin Dashboard (Production Integration pass)

## Documents page (`DocumentsPage.jsx`)

Three new tabs, each following the file's existing per-tab-component convention
(scan/load on mount, action buttons wired to real API calls, no hardcoded state):

- **Security Review** — scans and lists prompt-injection/PII/secret/path findings;
  shows an explicit "Export blocked" banner when any `block_export` finding is
  unresolved; per-finding actions are `Mark reviewed` / `Mark false positive`
  (see the Admin API doc for why the finding's own blocking `action` is not
  admin-overridable here).
- **Media & Tables** — scans and lists per-page content classification
  (`text_only`/`image_with_caption`/.../`table`/`image_without_usable_text`), shows
  caption/nearby text, and flags `vision_required` pages with a banner explaining
  they are excluded from text-only SFT generation. No Vision model behavior.
- **Tamil Corrections** — the global correction-rule registry: a create-draft form
  and a governed lifecycle list (`draft → needs_review → approve → activate`, or
  `reject` from any state). The UI only ever offers the single next legal transition
  per rule (derived from `status`), so it is structurally impossible to skip from
  `draft` straight to `active` through this screen.

## Document Wizard (`DocumentWizardPage.jsx`)

Extended from 10 to the full 14 steps: `Validate Export`, `Dataset Handoff`,
`Preview Split`, `Build Dataset Version` were added between `Export JSONL` and
`Training Readiness`. Every step still derives its `status`/`blocking_issues`/
`warnings`/`recommended_next_action` from real API responses (`documentHandoffs`,
`documentDatasetVersionStatus`, `documentHandoffSplitPreview`), never hardcoded.

The three irreversible actions in this range each use a **preview-then-confirm**
pattern matching the existing `KnowledgeGapsPage.jsx` convention (a separate, explicit
second action after a preview response is shown) rather than a browser `confirm()`
dialog, which is not used anywhere else in this codebase:
- Dataset Handoff: `Preview handoff` shows eligible/duplicate/lineage-missing counts;
  only then does `Confirm ingestion (irreversible -- creates dataset records)` appear.
- Preview Split → Build: `Preview split` must be run (and its result held in state)
  before `Confirm dataset-version build` is enabled.

Once a version is built, the step explicitly states *"Training was NOT started -- it
requires a separate Admin approval"* and offers `Open resulting dataset version`
(navigates to the Datasets page) rather than any training control.

## Deliberately not built this pass

- A separate 10th "Dataset Handoff" tab on `DocumentsPage` — the same actions already
  live in Wizard steps 11–13; adding a second UI surface for the identical mutations
  would duplicate state and confirmation logic for no functional gain.
- Deep-link query-string/route-state navigation between tabs (e.g. an Assistant
  answer linking straight into "Security Review" for a specific document).
- Mobile-390px and keyboard-only workflow audits of the *new* screens specifically
  (the existing screens' general responsive/keyboard behavior is unchanged and was
  not re-audited this pass).
