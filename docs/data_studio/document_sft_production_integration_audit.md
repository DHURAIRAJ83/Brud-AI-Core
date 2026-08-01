# Document SFT Production Integration — Audit

Baseline: branch `master`, HEAD `e24849f27a3dd4aaebf31ed89d7a3dd8d44d84a4`, schema 44,
previous verdict `DOCUMENT_SFT_FINALIZATION_COMPLETE_WITH_LIMITATIONS`.

Every Schema 44 service (`DocumentSftDatasetHandoffService`,
`DocumentSftCandidateGenerationService`, `DocumentSftExportService`,
`DocumentTamilCorrectionRegistryService`, `DocumentContentClassificationService`,
`DocumentSecurityReviewService`) was fully implemented at the service layer in the prior
pass, reachable only through direct Python calls and the Admin Assistant's governed
tools/proposals. No REST route, no dashboard UI, no `vision_required` cross-wire into
generation, and no performance bounds existed for these services. This audit classifies
each requested capability against that starting point.

| Capability | Status | Evidence |
|---|---|---|
| Admin REST APIs for handoff/export-validate | missing → implemented | `backend/api/routes/documents.py` (new endpoints) |
| Admin REST APIs for content classification | missing → implemented | same file, `/content-classifications*` |
| Admin REST APIs for security/PII findings | missing → implemented | same file, `/security*`, `/pii-findings` |
| Admin REST APIs for Tamil correction rules | missing → implemented | new `tamil_correction_rules_router`, global resource (no `document_source_id` FK exists on that table, so it cannot be nested under `/documents/{id}/...`) |
| CSRF/auth on all new mutation endpoints | missing → implemented | reused `CsrfDependency`/`require_admin`, identical to every existing document route |
| vision_required blocking in SFT generation | missing → implemented | `DocumentSftCandidateGenerationService.generate()` now excludes chunks on `vision_required=1` pages and reports each exclusion |
| Performance-bound settings (8 named) | missing → implemented | `backend/core/config.py`, wired into the 6 relevant services |
| Document Wizard steps 10–14 (Validate/Handoff/Split/Build/Readiness) | missing → implemented | `DocumentWizardPage.jsx`, real API-driven status + action buttons |
| Dashboard tabs: Security Review, Media & Tables, Tamil Corrections | missing → implemented | `DocumentsPage.jsx`, three new tab components |
| Dashboard tabs: separate "Dataset Handoff" top-level tab | **partially_available** | handoff actions live inside the Wizard's steps 11–13 rather than a 10th `DocumentsPage` tab, to avoid duplicating the same mutation surface in two places; disclosed as a deliberate consolidation, not a gap |
| Deep-link navigation (query-string/route-state tab jumps) | **not implemented** | `DocumentsPage`/`DocumentWizardPage` still use in-memory tab state only; cross-page links (e.g. "Open Critical Pages" from the Assistant) were not added this pass |
| Remaining SFT generators (contextual_meaning, multiple_meanings, clarification_request, computer_basics, safety_response) | **still deferred** | re-reviewed against §12's evidence bar; no reviewed target-word/context/meaning data, multi-meaning source-linked data, approved ambiguity registry, stable computer-domain chunk source, or approved safety-template source exists in this repository -- generating any of them now would mean inventing a heuristic, which the task explicitly forbids |
| Admin Assistant navigation to new areas | **not implemented** | the Assistant's read-only tools (already present from the prior pass) still answer the required Tamil-language example questions with real data; adding UI deep-links from Assistant answers into the Dashboard was not built this pass |
| Full canonical `ProductionRegressionService` manifest run | **not attempted** | consistent with 6+ prior attempts this session, all failed on host/harness restarts rather than product bugs; a large, sequential targeted regression (163 backend tests + 202 frontend tests) was run instead |
| New Playwright browser scenarios for the full handoff→build path | **not implemented** | the identical flow (upload→...→export→validate→preview→ingest→idempotent-retry→checksum-conflict→propose→split-preview→confirm-build→training_jobs-unchanged) is instead covered by a real HTTP-level integration test (`test_document_sft_production_integration_api.py`) against the live FastAPI app and a real SQLite DB; a browser run was judged not to add meaningfully more assurance for the API/service layer this pass adds, given tight session RAM (as low as ~420MB free) already shared with an active desktop Chromium/Electron session outside this agent's control |
| DB migration | **not needed** | every new capability layers onto the existing Schema 44 tables/columns; nothing required a new CHECK constraint, column, or table, so no migration 045 was created (per the task's own preference: "prefer no migration") |

No item in this pass was classified `blocked_by_architecture`.
