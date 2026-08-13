# Final Release Checklist

Produced by the Production Release Finalization pass (2026-08-01).
Read-only preparation: **no file was staged, committed, or pushed; no new
feature, route, migration, or architecture was introduced.** This document
supersedes nothing in `release_readiness_report.md` — it corrects and
extends it with evidence found while actually re-verifying its 7 proposed
commit groups, per this task's Steps 1–2.

## Exclusive-session check

Confirmed clear: the only Claude CLI process on the host (PID 2378) is
this session's own host process (verified via `pstree`/parent-chain
correlation in the prior task). HEAD unchanged at `26611fcbca5d0a91e7dddd
1c0d3ddf5204c09444` throughout this pass.

## Critical correction to the prior pass's "committed core" framing

While re-verifying the 7 proposed commit groups against real files (Step
1), this pass found that `release_readiness_report.md`'s "Production
Ready (committed scope)" characterizations conflated two different
things: **evidence gathered against the current working tree** (real,
valid — canonical regression and Playwright genuinely pass) and **what is
actually reachable from a clean `git checkout 26611fc`**. Specifically:

- **Every Playwright spec file (00–09) is untracked.** Even
  `00-smoke.spec.js` and `01-auth-session.spec.js` — the ones exercising
  core login/session/CSRF behavior — plus `fixtures.js`, `global-setup.js`,
  `global-teardown.js`, `seed.py`, and `playwright.config.js` itself. A
  clean checkout of `26611fc` has **zero** e2e test infrastructure.
- **Only 13 of 40 dashboard page files are fully committed with no
  pending changes** (`BaseTrainingPage`, `ConversationMemoryPage`,
  `CoreModelPage`, `FeedbackPage`, `ImportsPage`, `InferenceRuntimePage`,
  `InstructionTuningPage`, `LoginPage`, `OverviewPage`, `PlaceholderPage`,
  `SystemPage`, `TokenizerPage`, `TrainingPage`). None of these 13 have
  live Playwright coverage today (impossible — the specs that would cover
  them are themselves uncommitted).
- **`ProductionReadinessPage.jsx` and its entire backend
  (`backend/api/routes/production_readiness.py` + 15 `production_*`
  services) are 100% untracked** — despite `02-production-readiness-ui.
  spec.js` (also untracked) providing 10 passing tests for it. This
  subsystem was not mentioned anywhere in the original 7-group proposal.
- **The Document SFT closure commit (`26611fc`) itself committed 2
  Playwright specs (08, 09) that partially test uncommitted code**:
  `DocumentWizardPage.jsx` is 100% untracked; `DocumentsPage.jsx` is only
  partially committed (tracked-modified). This is not a defect in the
  closure commit — the specs correctly describe real, working behavior in
  the working tree — but it means "closure is committed and self-
  contained" was not quite accurate; it has an implicit dependency on
  still-uncommitted page code.

**This does not mean the code is broken** — canonical regression (75/75,
3297/3297 assertions) and Playwright (55/55) both genuinely pass against
the real, current working tree, and that remains true. It means labeling
specific subsystems "Production Ready (committed scope)" without checking
`git status` on every file cited as evidence was imprecise. This pass
corrects that by re-deriving Step 4's determinations from actual tracked
status, not from "a test passed" alone.

## Step 1–2: Commit group review (files, verification, readiness)

The original 7 groups omitted 4 real, substantial areas entirely: **E2E
test infrastructure** (needed by every other group's own tests),
**Production Readiness** (37 files, its own governance subsystem, not
mentioned at all), **Admin Assistant infrastructure** (31 files — the
90-tool read-only registry, chat service, context repository, and the
`core_model/admin_assistant` intent/action-registry/localization engine —
distinct from `admin_assistant_service.py`, which is tracked-modified and
was the only Admin-Assistant-related file the original proposal
implicitly covered), and **Document SFT remaining implementation** (57
files — never assigned to any group in this whole multi-session
initiative, since the earlier dedicated task for exactly this was blocked
by an active-session false alarm before it could run). These are
corrected below as 4 additional groups, listed first since several later
groups depend on them.

Also found: **the 61 tracked-modified "shared" files** (`router.py`,
`schema.py`, `migrations.py`, `App.jsx`, `Sidebar.jsx`, `config.py`,
various repositories/models, ~15 pre-existing test files with small
additions) **cannot be cleanly pre-assigned to exactly one group** — each
accumulated incremental hunks from multiple feature areas over many
sessions (e.g. `schema.py` adds tables for phases 23 through 44 in one
diff). The correct, honest guidance is that these require **hunk-level
staging (`git add -p`) at actual commit time**, guided by each group's own
new symbols, not a single up-front group assignment. This is itself a
"grouping recommendation" correction, not an implementation change — no
file's content was touched to produce this finding.

| Group | Files (untracked, approx.) | Scope | Tests | Docs | Migrations | APIs | Frontend | Backend | Security | Admin Assistant integration | Readiness |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **G0. E2E test infrastructure** (new) | 13 | Playwright fixtures, global setup/teardown, seed script, config, specs 00–07 | N/A (is the test infra) | None dedicated | N/A | N/A | N/A | N/A | Reviewed (isolated DB per run, admin-only fixtures) | N/A | **Needs Review** — must ship before/with the first group whose pages it tests |
| **G_AA. Admin Assistant infrastructure** (new) | 31 | 90-tool registry, chat service, context repo, intent/localization engine | `test_admin_assistant_api*`, `_lifecycle`, `_tools`, `_intent`, `_localization`, `_registries` — present | Present (`docs/admin_assistant/`) | None | `backend/api/routes/admin_assistant.py` (tracked-modified, needs hunk split) | Widget component, `AdminAssistantPage.test.jsx` | `admin_assistant_tools.py`, `admin_assistant_chat_service.py`, `admin_assistant_context_repository.py` | Read-only-by-construction, re-verified this session (90/90, 103/103/103 parity) | Is the subsystem itself | **Ready** |
| **G_PR. Production Readiness** (new) | 37 | Model/RAG release governance, rollback, secret scan, artifact security, backup/deployment readiness | 10 dedicated test files present | `docs/production/` (4 files) | None | `production_readiness.py` route | `ProductionReadinessPage.jsx` + test | 15 `production_*` services | Not independently re-audited this pass (time-boxed) | `test_production_readiness_admin_assistant.py` present | **Needs Review** — largest ungrouped area found, deserves its own dedicated security pass before commit given it governs model/RAG activation |
| **G_DOCSFT. Document SFT remaining** (new) | 57 | Everything from the workflow/production-integration/finalization passes not in the closure commit | Extensive (`test_document_sft_*`, `test_document_workspace_*`, `test_document_content_classification.py`, `test_document_security_review.py`, `test_document_tamil_correction_registry.py`) | `docs/data_studio/document_sft_*` (11 remaining docs) | 043/044 already committed via closure; no new migration here | `documents.py` (tracked-modified, needs hunk split) | `DocumentWizardPage.jsx` (+test), `documentNavigation.js` (+test) | 8 services | Re-verified indirectly (closure's own security-review/export-blocking tests) | `test_admin_assistant_document_navigation.py` present | **Ready** — this is the most mature, most-tested uncommitted area (it's the direct predecessor of the already-shipped closure) |
| **G1. Data Studio Phases 1–7** | 74 | Manual data, source rights, semantic chunk/structured record | Present | `docs/data_studio/phase1-7_*` | None | Several route files (tracked-modified, hunk split needed) | `ManualDataPage`, `ChunkStudioPage`, `SourcesRightsPage`, `DataOverviewPage`, `DataHelpPage` | Present | Not independently re-audited this pass | Present | **Ready** |
| **G2. RAG Sandbox + Governance + Governed Builds** | 65 | Trial-before-promotion RAG pipeline, human-gated build/review | Present | `docs/rag_sandbox/` | None | Route files (hunk split needed) | `RagSandboxPage`, `GovernancePage`, `BuildsPipelinesPage` | Present | Not independently re-audited this pass | Present | **Ready** |
| **G3. External intake** (Discovery + Providers + Sample Import + Verification) | 111 | External dataset discovery/comparison/scoring, quarantine/PII/poisoning checks, licence verification | Present | Present | None | Route files (hunk split needed) | 4 pages | Present | Not independently re-audited this pass — **recommend a dedicated security pass given this is the largest external-input-facing group (SSRF/PII/poisoning surface)** | Present | **Needs Review** |
| **G4. Training governance + Pipeline Integration** | 36 | Incremental training checkpoints/approval, contamination/suitability/replay gating | Present | Present | None | Route files (hunk split needed) | `IncrementalTrainingPage` | Present | Not independently re-audited this pass | Present | **Ready** |
| **G5. Knowledge Routing + Knowledge Gap** | 58 | Intent/domain/freshness classifiers, gap registry | Present | `docs/smart_routing/phase17,19_*` | None | Route files (hunk split needed) | `KnowledgeRoutingPage`, `KnowledgeGapsPage` | Present | Not independently re-audited this pass | Present | **Ready** |
| **G6. Public Chat Routing** | 32 | Unauthenticated public smart-answer router | Present | `docs/smart_routing/phase18_*` | None | `chat.py` (tracked-modified — already reviewed this session: rate-limited, validated, deliberately no admin-auth) | `PublicChatRoutingPage` | Present | Re-verified this session (Finding 2, `backend_completion_report.md`) | Present | **Ready** |
| **G7. Trusted Web + Tool Gateway + Deterministic Tools** | 41 | Web-sourced answers, SSRF-safe fetch, injection screening, tool execution | Present (573 lines) | `docs/smart_routing/phase20_*` | None | Route files (hunk split needed) | `TrustedWebPage`, `DeterministicToolsPage` | Present | **Highest sensitivity — first unauthenticated traffic reaching fetch/tool execution. Recommend the most thorough pre-commit security pass of all 11 groups, not independently re-audited in this time-boxed session.** | Present | **Needs Review** |

11 groups total (7 original + 4 corrections), covering all ~684
category-A files plus the 61 shared tracked-modified files (flagged for
hunk-level splitting, not pre-assigned). 321 generated/temporary files
remain excluded per `repository_cleanup_audit.md`. 36 documentation files
map 1:1 to their code group and travel with it.

## Step 3: Review-only issues — resolved or explicitly deferred

- **5 missing `helpRegistry.js` entries** (Dataset Verification, Document
  Wizard, Incremental Training, RAG Sandbox, Sample Import & Quarantine):
  still deferred, not fabricated. Unchanged from `admin_assistant_
  completion_report.md`.
- **9 pages flagged "empty-state unconfirmed"**: re-checked this pass by
  reading actual list-rendering code (not just regex). **Confirmed, not
  fabricated**: several (e.g. `ConversationMemoryPage.jsx`, 15+ `.map()`
  calls across its tabs) render list content with no explicit "no items
  yet" fallback — an empty list silently renders blank space rather than
  a message. This is a real, minor UX-completeness gap, not a functional
  break. **Not fixed in this pass**: consistently applying an empty-state
  message across 9 pages' JSX is a real UI change that deserves its own
  live-verification pass (a prior attempt at live browser spot-checking
  this session hit the project's documented host/harness memory
  instability after 4 of 29 pages) — rushing a UI text change without
  visual confirmation risks introducing exactly the kind of unverified
  change this task prohibits.
- **Registry/navigation mismatch**: none found (re-confirmed: 38/38 page
  registry, 90/90 tool registry, 103/103/103 executor/fingerprint/preview
  registry — all exhaustive, all clean).
- **Stale comments**: none found beyond the already-documented Phase-1
  placeholder interfaces (`backend_completion_report.md`, Finding 1),
  which are intentionally preserved historical artifacts, not stale
  cruft.

## Step 4: Subsystem release-quality verification (corrected)

| Subsystem | Determination | Evidence |
|---|---|---|
| Backend (core, Main Brud AI 1–22) | **Production Ready** | Committed, 0 TODO/FIXME/bare-except, clean auth/CSRF coverage |
| Backend (Document SFT closure) | **Production Ready** | Committed (`26611fc`), 75/75 canonical regression |
| Backend (all 11 uncommitted groups) | **Needs Review** (2 of 11: G_PR, G3, G7 explicitly flagged for a dedicated security pass; the other 8 are file/test/doc-complete but unexecuted-by-this-pass) | See table above |
| Frontend (13 fully-committed pages) | **Needs Review** — **corrected from the prior pass's "Production Ready"**: these have zero live test coverage today, since all Playwright infra is uncommitted | This pass's git-status re-check |
| Frontend (27 uncommitted/modified pages) | **Needs Review** | Static review clean; live coverage exists only in the uncommitted working tree, not in git |
| Admin Dashboard registry | **Production Ready** (as a file-level artifact) / **Needs Review** (as a committed artifact — `dashboard_registry.py` itself is untracked) | 38/38 parity confirmed against the working tree |
| Admin Assistant | **Ready to commit as G_AA** | 90/90, 103/103/103 parity; one deferred content gap (5 help entries) |
| Smart Routing (Knowledge Routing + Public Chat + Trusted Web, split as G5/G6/G7) | **Needs Review** (G7 specifically, for security) / **Ready** (G5, G6) | See table |
| Knowledge Gap | **Ready** (part of G5) | |
| Trusted Web | **Needs Review** | Highest security sensitivity, recommend dedicated pass before commit |
| Document SFT (closure) | **Production Ready** | Committed, verified |
| Document SFT (remaining, G_DOCSFT) | **Ready to commit** | Most mature of the uncommitted groups |
| Dataset workflow (G1, G3) | **Ready** (G1) / **Needs Review** (G3 — external-input security pass recommended) | |
| Security (committed scope) | **Production Ready** | Re-verified this pass and the prior one |
| Security (uncommitted scope) | **Needs Review** | Working-tree-wide secret/forbidden-write scans passed as part of the last canonical run, but no group received an independent, dedicated security review in this time-boxed session beyond G6 (chat.py) |
| Database | **Production Ready** | Schema 44, chain 1–44 verified additive and clean, both fresh-DB and real-DB integrity/FK clean |

## Step 5: Commit readiness summary

| Group | Ready to commit (pending its own pre-commit test run) | Blocking dependency |
|---|---|---|
| G0 E2E infra | Needs Review (ship first/alongside G_AA or G_DOCSFT) | None |
| G_AA Admin Assistant infra | Ready | G0 (for its own spec, 06) |
| G_DOCSFT Document SFT remaining | Ready | G0 (for specs 08/09, already committed — but see the correction above) |
| G_PR Production Readiness | Needs Review (security pass) | G0 (for spec 02) |
| G1 Data Studio 1–7 | Ready | None |
| G2 RAG Sandbox + Governance | Ready | G1 (dataset primitives) |
| G3 External intake | Needs Review (security pass) | G1 |
| G4 Training governance | Ready | G1, G2 |
| G5 Knowledge Routing + Gap | Ready | None |
| G6 Public Chat Routing | Ready | G5 |
| G7 Trusted Web + Tools | Needs Review (security pass, highest priority) | G6 |

No group was staged or committed in this pass.

## Known limitations

1. The 61 shared tracked-modified files require hunk-level (`git add -p`)
   splitting at actual commit time — not solved by this pass, correctly
   identified as a real constraint rather than force-fit into one group.
2. 4 groups (G_PR, G3, G7, and security broadly) need a dedicated
   security pass this time-boxed session could not complete for all 11
   groups.
3. 9 pages have a confirmed (not just suspected) minor empty-state UX gap,
   deferred pending a live-verification pass.
4. 5 `helpRegistry.js` entries remain unwritten, deferred to avoid
   fabricating Tamil content.
5. The three-track phase-numbering ambiguity (`documentation_index.md`)
   remains unresolved.

## Release blockers (for a full-repository v1.0 tag)

1. None of the 11 groups have been committed.
2. G_PR, G3, and G7 need a dedicated security review before commit.
3. The corrected "committed core" picture means **zero** frontend pages
   currently in git have live browser test coverage — before any v1.0
   claim, at minimum G0 (e2e infra) plus one feature group should land
   together so committed code has real, reproducible test evidence again.

## Final verdict

**RELEASE_PREPARATION_COMPLETE_WITH_LIMITATIONS**

Every proposed commit group was reviewed and corrected where the original
proposal was incomplete; every genuine review-only issue found was either
resolved (empty-state ambiguity converted from "unconfirmed" to
"confirmed, deferred with reason") or precisely documented for a future
pass; no new feature, route, migration, or architecture was introduced;
nothing was staged, committed, or pushed. The limitations above are real
and un-fixed by design (this task's own scope excludes rushing them), not
oversights.
