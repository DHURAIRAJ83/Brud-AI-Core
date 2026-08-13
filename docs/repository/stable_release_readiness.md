# Stable Release Readiness — Brud AI Text/NLP Baseline v1.0 Alpha

Produced by the Repository Stabilization pass (2026-08-01). Assessment
only — no code, tests, or commits were changed to produce this verdict.

## Method

Evaluated against: backend, frontend, tests, documentation, migrations,
governance, security, Admin Assistant, dataset workflow, document workflow
— per this task's Step 11. Evidence used: this pass's own architecture/
migration/registry checks (`repository_architecture_summary.md`), the
existing canonical regression evidence from the Document SFT closure
(`26611fc`, 75/75 batches, 3297/3297 assertions, Playwright 55/55 — real,
but scoped to Document SFT + the pre-existing committed suite, not the
uncommitted Data Studio/Smart Routing backlog), and the file-level inventory
in `repository_cleanup_audit.md`. **This pass did not re-run any test
suite** beyond the single fresh-DB migration/integrity check — per Step 5's
"inventory, do not delete/re-run" scope and this task's explicit "no new
commits, no new test execution beyond what's specified" framing. Where a
claim below depends on evidence this pass did not generate, it is marked
**unverified in this pass**.

## Per-area assessment

| Area | State | Evidence |
|---|---|---|
| Backend (committed: Main Brud AI 1–22 + Document SFT closure) | Ready | Canonical regression 75/75, fresh-DB schema 44 verified this pass |
| Backend (uncommitted: Data Studio, Smart Routing, ~90 new services) | **Unverified in this pass** | Real, substantive code confirmed present and wired (routes registered, line counts, imports checked); no test execution performed this pass |
| Frontend (committed) | Ready | Page/registry parity confirmed clean this pass (38/38, 3 honestly-flagged placeholders) |
| Frontend (uncommitted: ~20 new pages) | **Unverified in this pass** | Present and imported into `App.jsx`; not test-executed this pass |
| Tests | Inventoried, not gap-free by design | 157 backend + 51 core_model + 56 database + 24 admin-dashboard + 3 chatbot + 10 Playwright specs = 301 test files; only 1 legitimate exclusion from the canonical manifest (`test_production_regression_manifest.py`, a meta-test of the manifest itself) |
| Migrations | Ready | Schema 44, chain 1–44 contiguous, migrations 1–22 byte-identical to committed HEAD, fresh-DB integrity/FK checks clean, real dev DB independently confirmed healthy |
| Governance (Admin Assistant read-only boundary) | Ready (for committed scope) | `admin_assistant_tools.py` confirmed read-only-by-construction this pass; prior sessions' direct DB-level verification (0 mutation rows after real tool invocations) still stands for the committed Document SFT navigation actions |
| Security | **Partially unverified in this pass** | `git diff --check`/`ruff check .` were run for the committed closure only; the ~900 uncommitted files were not re-scanned for secrets/security issues in this pass (the existing `secret_scan_01`/`forbidden_write_scan_01` canonical batches only run against what's currently on disk when executed, and were last executed as part of the closure's own canonical run — which did include these files on disk, since the manifest's file-content/path-based scans read the working tree regardless of git status; **this is a meaningful distinction**: the *scan* did cover this content, but *targeted service-level tests* for the newer areas did not run in this specific stabilization pass) |
| Admin Assistant registry parity | Ready | Confirmed clean this pass — see `repository_architecture_summary.md` |
| Dataset workflow | Ready | Committed, part of Main Brud AI track |
| Document workflow (Document SFT) | Ready | Closure committed, canonical regression clean, Playwright 55/55 |

## Correction to this task's own premise

This task's brief stated "Phase 1–19 completed... No Trusted Web
implementation" as the current-state framing. This audit found that
framing does not match the working tree: Smart Routing phases 16–20
(including a substantive Trusted Web implementation — 1,405 backend lines,
a frontend page, 573 lines of tests, a registered route) already exist,
uncommitted. This does not mean Trusted Web was built in this pass (it was
not — this pass made no code changes), only that the premise "Trusted Web
doesn't exist yet" is inaccurate for the actual repository state. See
`repository_architecture_summary.md`'s "Phase implementation status
reconciliation" table for the full picture.

## Verdict: NOT READY for a v1.0 Alpha tag, with a narrower path that is

**The committed subset** (Main Brud AI phases 1–22 + Document SFT
Production Closure, `26611fc`) **is genuinely release-quality** on its own
merits — clean canonical regression, clean Playwright, clean migrations,
clean registry parity, no uncommitted drift. If "Text/NLP Baseline v1.0
Alpha" is scoped narrowly to exactly what's committed today, that scope
could be tagged as-is.

**The repository as a whole is not ready**, for these exact, specific
blockers:

1. **~900 uncommitted files spanning ~20 additional feature areas** (RAG
   Sandbox, Trusted Web, Knowledge Routing/Gap, Public Chat Routing,
   Governance, Semantic Chunk/Structured Record, Manual Data, Dataset
   Sample Import/Verification, External Data Providers, Incremental
   Training, Pipeline Integration, Tool Gateway, Deterministic Tools) sit
   in the working tree with no commit history, no version tag, and no
   audit trail. A "stable baseline" by definition should be a coherent,
   versioned state; right now the true state of the project is split
   between git history and one uncommitted working tree.
2. **That uncommitted backlog was not test-executed in this pass.** Its
   presence and wiring were confirmed (imports, route registration, line
   counts), but no pytest/vitest/Playwright run was performed against it
   here. It cannot be certified passing from this pass's evidence alone.
3. **Phase-numbering ambiguity** across three overlapping tracks (Main
   Brud AI, Data Studio, Smart Routing) that reuse the same integers for
   different phases — a real documentation/communication risk once this
   work is committed and referenced externally.
4. **247 generated/temporary files** (`data/release_artifacts/`,
   `data/document_sft_exports/`, `data/manual_verification_phase20*/21a/`,
   a stray empty `data/brud_ai.db`) are not covered by `.gitignore`,
   meaning a careless `git add -A` at any point could accidentally commit
   generated data as if it were source.
5. **3 sidebar navigation entries with no page** (`Chat Testing`, `Audit
   Logs`, `Settings`) — low severity, honestly self-documented in the
   registry, but still an incomplete surface for a v1.0 tag.

## What would need to happen before a full-repository v1.0 Alpha tag

(Recommendations only — none of this was performed in this pass, and this
task explicitly excludes starting Phase 20 work, new features, or
commits.)

1. A deliberate, scoped commit (or several) landing the uncommitted feature
   areas, each preceded by its own real test run — not one giant
   `git add -A`.
2. A full canonical-regression-manifest extension covering the newly
   committed areas (the manifest today only has batches for what's already
   committed plus Document SFT).
3. Resolve or clearly document the phase-numbering collision before wider
   circulation of these docs.
4. Add the recommended `.gitignore` entries for generated artifacts (Section
   D of `repository_cleanup_audit.md`).
5. Decide and either build or formally defer `Chat Testing`/`Audit Logs`/
   `Settings`.

## Final scoped verdict

- **Committed Text/NLP core (Main Brud AI 1–22 + Document SFT closure): READY.**
- **Full repository as a v1.0 Alpha baseline: NOT READY** — 5 blockers listed above, none of them touched by this pass per its explicit no-new-commits/no-new-features/no-Phase-20 instructions.
