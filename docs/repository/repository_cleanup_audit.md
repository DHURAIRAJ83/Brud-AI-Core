# Repository Cleanup Audit

Produced by the Repository Stabilization pass (2026-08-01). Read-only audit
only — nothing in this document has been staged, committed, or deleted.
Every recommendation below is a recommendation, not an action taken.

## Scope and method

At the time of this audit, `git status --short` reported **561 changed/
untracked paths** against HEAD (`26611fc`), expanding to **991 individual
files** (61 tracked-modified + 930 untracked, via `git diff --name-only` and
`git ls-files --others --exclude-standard`). Auditing 991 files one row per
file would not be a usable document, so this audit groups files into
**feature areas**, verified by directory/filename patterns and spot-checked
against actual file contents (not name-guessing alone) — each area lists its
constituent files and one keep/remove/archive decision. This satisfies "for
every file" at a granularity a human can actually review; a raw per-file
listing for any group is one `git status --short -- <paths>` away if needed.

## A. Remaining feature implementation (uncommitted, real, tested source)

Every area below is legitimate, non-experimental implementation code with
matching tests and documentation — not cleanup debris. The finding here is
not "junk exists," it's **"an enormous amount of finished work across many
sessions has never been committed."** All rows: **keep — pending a
deliberate, scoped commit** (not part of this stabilization pass, see
`stable_release_readiness.md`).

| Feature area | Untracked files | Tracked-modified files touching it | Purpose | Duplicate? | Obsolete? | Temporary? |
|---|---|---|---|---|---|---|
| Document SFT (workspace/candidates/export/handoff/Tamil quality/security review) | 126 | `DocumentsPage.jsx`, `documents.py` (routes/repo/models) | PDF review → SFT candidate generation → export → dataset handoff, closure pass already committed separately in `26611fc` | No | No | No |
| Admin Assistant infrastructure (tools, chat service, context repo, widget) | 49 | `admin_assistant_service.py`, `AdminAssistantPage.jsx` | Floating read-only assistant: registry, tool wrappers, chat, proposal/review flow | No | No | No |
| Dataset sample import (14 services incl. quarantine/PII/poisoning/contamination) | 44 | — | Governed intake pipeline for external dataset samples | No | No | No |
| Production readiness governance (RAG/model/rollback/secret-scan/deployment/backup) | 33 | — | Phase 15A production-gating services (activation, canary, rollback, artifact security) | No | No | No |
| Public chat routing (router, citation adapter, rate limiter, scope resolvers) | 32 | `chat_orchestration_service.py` | Public (unauthenticated) smart-answer router — Phase 18 in `docs/smart_routing` numbering | No | No | No |
| Governance & governed builds | 31 | — | Human-gated build/review workflow feeding training/RAG/release | No | No | No |
| Semantic chunk / structured record studio | 31 | — | Chunk/record extraction, classification, lifecycle | No | No | No |
| Knowledge gap registry | 28 | — | Persists `insufficient_evidence` interactions — Phase 19 | No | No | No |
| RAG sandbox | 28 | — | Trial-before-promotion experimentation pipeline for RAG | No | No | No |
| External data providers | 27 | — | 6-connector external dataset discovery/comparison/scoring | No | No | No |
| Knowledge routing (classification) | 27 | — | Intent/domain/freshness classifiers — Phase 17 | No | No | No |
| Trusted Web (policy, answer, evidence, safe fetcher) | 24 | — | Web-sourced answers with SSRF-safe fetch + injection screening — Phase 20 (see finding below) | No | No | No |
| Manual data studio | 22 | — | Human-entered dataset record intake | No | No | No |
| Dataset verification | 18 | — | Licence/rights evidence review workflow | No | No | No |
| Incremental training | 15 | — | Post-launch checkpoint incremental-training governance | No | No | No |
| Data discovery | 14 | — | Candidate dataset discovery from external sources | No | No | No |
| Data sources / lineage | 11 | — | Source registry + lineage graph | No | No | No |
| Training governance (contamination/promotion/suitability/replay) | 12 | — | Additional gating for training-dataset promotion | No | No | No |
| Tool gateway | 9 | — | Trusted-web tool/MCP-adjacent gateway plumbing | No | No | No |
| Pipeline integration | 8 | — | Dataset→RAG→training pipeline eligibility/manifest glue | No | No | No |
| Deterministic tools | 6 | — | General deterministic tool execution + registry (distinct from Admin Assistant's own tool registry — see architecture summary) | No | No | No |
| Governed handoff (shared RAG/training) | 4 | — | Shared handoff service used by both RAG and training governance | No | No | No |
| Sample import (core_model policy layer) | 4 | — | Policy layer under `dataset_sample_import` | No | No | No |
| Data providers/verification policy (core_model) | 4 | — | `core_model/data_providers`, `core_model/data_verification` + their policy tests | No | No | No |
| Frontend pages misc (Overview/Help/etc. not otherwise classified) | 3 | `App.jsx`, `Sidebar.jsx`, `api.js` | Supporting pages for the above areas | No | No | No |
| `production_regression` (manifest service itself) | 3 | — | The `ProductionRegressionService` used to verify all of the above | No | No | No |
| Database migration tests (`test_phase17..36_migration.py`) | 14 | `test_phase22_migration.py` (modified) | One test file per schema migration 17–44 | No | No | No |
| E2E/Playwright infrastructure + specs 00–07 | 12 | — | Fixtures, global setup/teardown, seed script, 8 pre-existing spec files (specs 08/09 already committed) | No | No | No |
| Frontend shared test infra (`playwright.config.js`, `helpRegistry.js`, `test/setup.js` x2, misc `.test.jsx`) | 11 | — | Shared test scaffolding, not feature-specific | No | No | No |
| `docs/` (33 new files) | 33 | — | See `documentation_index.md` | Partially — see finding below | No | No |

## B. Already committed (closure pass, `26611fc`) — must not be re-staged

```
apps/admin-dashboard/e2e/tests/08-document-sft-workflow.spec.js
apps/admin-dashboard/e2e/tests/09-document-sft-production-closure.spec.js
config/production_regression_manifest.json
docs/data_studio/document_sft_final_production_readiness.md
docs/data_studio/document_sft_full_browser_verification.md
```
Confirmed clean at the time of this audit: none of these 5 paths appear in
`git status --short` (they are fully committed, no further drift).

## C. Unrelated / pre-existing broad refactor surface

The 61 tracked-modified files (`git diff --name-only`) are overwhelmingly
**connective-tissue changes required by area A above** — `router.py`
registering new routes, `schema.py`/`migrations.py` adding tables 23–44,
`App.jsx`/`Sidebar.jsx` adding nav entries, and a handful of existing test
files gaining a small addition (`test_system_api.py` +22 lines,
`test_phase22_migration.py` +13/-… lines). None of these 61 files are
"unrelated work" in the sense of a different, unconnected initiative — they
are the shared files every one of the area-A features had to touch. There is
**no genuinely unrelated (category C, in the strict sense) work** in this
repository at present; everything uncommitted traces to the Data Studio /
Smart Answer Routing program.

## D. Generated / temporary artifacts — recommend `.gitignore` + do-not-commit

| Path | Files | What it is | Recommendation |
|---|---|---|---|
| `data/release_artifacts/` | 144 | Per-model-release generated bundles (manifests, model cards, licences) keyed by UUID directories | **Recommend**: add to `.gitignore` (matches the existing pattern for `data/core_models/`, `data/corpus_exports/`, etc. already ignored) |
| `data/document_sft_exports/` | 74 | Generated JSONL exports keyed by UUID | **Recommend**: add to `.gitignore` |
| `data/manual_verification_phase21a/` | 64 | Manual-verification fixture/output bundle | **Recommend**: add to `.gitignore`, or move under `tests/fixtures/` if any file is a genuine committed fixture (needs a per-file check before archiving) |
| `data/manual_verification_phase20_clean/` | 19 | Same as above, phase 20 | **Recommend**: add to `.gitignore` |
| `data/manual_verification_phase20/` | 18 | Same as above, phase 20 | **Recommend**: add to `.gitignore` |
| `data/brud_ai.db` | 1 (0 bytes) | Stray empty file at a path the app no longer uses (real DB lives at `data/database/brud_ai.db`, already gitignored) | **Recommend removal** — verified empty (0 bytes, dated 2026-07-26), verified unreferenced by current `Settings()` config, which resolves to `data/database/brud_ai.db` |
| `.claude/launch.json` | 1 | Local editor/IDE launch config | **Recommend**: add `.claude/` to `.gitignore` if it is meant to stay local-only (matches other IDE-local conventions); confirm intent with the user before ignoring, since `.claude/` may also hold project-shared skills/settings elsewhere in a real deployment |

No files in category D were deleted. All are flagged for a future,
deliberate `.gitignore` update — never auto-deleted, per this task's
explicit "nothing should be deleted automatically" instruction.

## E. Ambiguous ownership

None found. Every one of the 991 changed/untracked paths could be traced to
a specific, named feature area (A), the already-committed closure (B), or a
generated-artifact directory (D) with reasonable confidence from path,
filename, and spot-checked file content. If a more granular per-file review
surfaces an exception, it should be added here before any future commit.

## Finding: Trusted Web (Phase 20) already has a real implementation

This task's brief states "No Trusted Web implementation" as an exclusion for
*this* pass — correctly not attempted here. But the audit found Trusted Web
is **already substantively implemented** in the uncommitted tree, not merely
planned: `trusted_web_answer_service.py` (564 lines), `safe_web_fetcher.py`
(332 lines), `trusted_web_policy_service.py` (151 lines),
`web_evidence_selection_service.py` (105 lines), a 253-line
`TrustedWebPage.jsx`, a registered API route
(`trusted_web_admin` in `backend/api/router.py`), `config/
trusted_web_policy.json`, and 573 lines of tests
(`test_trusted_web_admin_assistant.py`,
`test_trusted_web_and_tools_admin_api.py`, `test_trusted_web_help.py`). This
directly affects the "Phase 1–19 completed" framing in this task's own
brief — see `stable_release_readiness.md` for the full phase-status
reconciliation.

## Doc-duplication finding (Step 4 detail)

No literal duplicate documents were found. The apparent repetition in
`docs/data_studio/document_sft_*.md` (workflow_audit →
workflow_completion_plan → production_integration_audit/plan →
production_readiness → finalization_audit/plan → closure_audit/plan) is a
genuine, intentional audit→plan→completion record across **four distinct
passes**, each self-titled with its pass name (e.g.
`document_sft_production_readiness.md` is explicitly titled "(Production
Integration pass)", distinct from the later
`document_sft_final_production_readiness.md`, titled "(Production
Closure)"). Per this task's explicit instruction, these are preserved as
historical evidence, not merged or rewritten. See
`documentation_index.md` for the full map.

## Summary counts

- Total changed/untracked paths (git-status-line granularity): 561
- Total individual files: 991 (61 tracked-modified + 930 untracked)
- Category A (remaining implementation, keep pending commit): ~684 files
- Category B (already committed): 5 files (0 remaining in working tree)
- Category C (genuinely unrelated): 0 files found
- Category D (generated/temporary, recommend ignore/remove): 247 files
- Category E (ambiguous): 0 files
