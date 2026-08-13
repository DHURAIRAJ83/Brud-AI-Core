# Release Candidate Checklist (RC1 Verification)

Produced by the Final Commit Audit & Release Candidate Verification pass
(2026-08-01). Read-only verification: **no file staged, committed, or
pushed; no feature, route, migration, API, page, service, or model
added.** Builds on `final_release_checklist.md`'s 11-group structure.

## Exclusive-session check

Clear — the only Claude CLI process on the host (PID 2378) is this
session's own host process. HEAD unchanged at `26611fcbca5d0a91e7dddd
1c0d3ddf5204c09444`. Nothing staged (`git diff --cached --name-only`
empty) throughout this pass.

## Step 1: Commit Group Audit

| Group | Feature completeness | Dependency correctness | Shared-file boundaries | Hunk-split required? | Migration dependency | Documentation dependency | Verdict |
|---|---|---|---|---|---|---|---|
| **G0 E2E infra** | Complete (13 files: fixtures, global setup/teardown, seed, config, specs 00–07) | None upstream; everything else's Playwright tests depend on it | N/A (no shared files) | N/A | None | None dedicated | **READY** |
| **G_AA Admin Assistant infra** | Complete (90/90, 103/103/103 parity re-verified) | Depends on G0 for spec 06 | `admin_assistant_service.py` (tracked-modified — safely splittable, see Step 2), `admin_assistant.py` route | Yes, for `admin_assistant_service.py`/route only | **029, 032** (corrected — schema.py is atomic, see Step 2) | `docs/admin_assistant/` present | **READY** |
| **G_PR Production Readiness** | Complete (10 test files, 4 docs, 15 services) | Depends on G0 for spec 02; depends on release-registry primitives already committed (Main Brud AI Phase 14) | `production_readiness.py` route (new file, not shared) | No (new file) | **038** | `docs/production/` present | **NEEDS_REVIEW** — governs model/RAG activation and rollback, highest-consequence subsystem after Trusted Web; recommend dedicated security pass before commit, consistent with the prior pass's finding |
| **G_DOCSFT Document SFT remaining** | Complete (extensive tests/docs) | Depends on G0 (specs 08/09, already committed) and **G1 for migration 025** (corrected this pass — the foundational `document_page_extractions` table was created by Data Studio Phase 4, not by Document SFT's own migrations) | `documents.py` route, `DocumentsPage.jsx` (both tracked-modified, splittable) | Yes | **025** (via G1) **+ 043, 044** (already committed) | `docs/data_studio/document_sft_*` present | **READY**, with the corrected note that it cannot land before G1 |
| **G1 Data Studio 1–7** | Complete | None upstream | Several route files (splittable) | Yes | **023, 024, 026** (corrected — migration 028 does NOT belong to G1 despite its doc title "dataset-RAG-training integration"; verified by reading the actual `CREATE TABLE` statement, which is `governed_build_requests`, a G2 table) | `docs/data_studio/phase1-3,5_*` | **READY** |
| **G2 RAG Sandbox + Governance + Governed Builds** | Complete | Depends on G1 (dataset primitives) | Route files (splittable) | Yes | **027, 028, 036** (corrected — 027/028 reassigned here from G1, verified by table content) | `docs/rag_sandbox/` | **READY** |
| **G3 External intake** | Complete | Depends on G1 | Route files (splittable) | Yes | **030, 031, 033, 034, 035** | Present | **NEEDS_REVIEW** — largest external-input surface (dataset discovery, sample import, licence verification); recommend dedicated security pass, unchanged from the prior pass's finding |
| **G4 Training governance + Pipeline Integration** | Complete | Depends on G1, G2 | Route files (splittable) | Yes | **037** | Present | **READY** |
| **G5 Knowledge Routing + Knowledge Gap** | Complete | None upstream beyond G0 | Route files (splittable) | Yes | **039, 041** | `docs/smart_routing/phase17,19_*` | **READY** |
| **G6 Public Chat Routing** | Complete | Depends on G5 | `chat.py` (tracked-modified, splittable; already reviewed — deliberately public, rate-limited) | Yes | **040** | `docs/smart_routing/phase18_*` | **READY** |
| **G7 Trusted Web + Tool Gateway + Deterministic Tools** | Complete | Depends on G6 | Route files (splittable) | Yes | **042** | `docs/smart_routing/phase20_*` | **NEEDS_REVIEW** — highest security sensitivity (first unauthenticated traffic reaching fetch/tool execution); confirmed real SSRF defenses this pass (see Step 3), but still recommend the most thorough pre-commit pass of all 11 groups |

**3 of 11 groups: NEEDS_REVIEW** (G_PR, G3, G7). **0 groups: BLOCKED.** **8 of 11: READY.**

## Step 2: Shared File Audit

This pass found a critical distinction the prior pass's "hunk-level
splitting recommended" guidance did not make: **not all shared files can
actually be split.**

| Shared file | Groups that modify it | `git add -p` viable? | Reason |
|---|---|---|---|
| `backend/database/schema.py` | G1, G2, G3, G4, G5, G6, G7, G_AA, G_PR, G_DOCSFT (foundation) | **NO — must be committed as one atomic unit** | Confirmed by reading `initialize_database()`: migrations 23–44 are invoked as an unconditional, flat sequential call chain (`_apply_v23(connection)` through `_apply_v44(connection)`, no loop, no early exit). Every `_apply_vN` function is individually idempotent, but the call chain itself has **zero gap tolerance** — if `_apply_v25`'s definition were committed without also committing the call site (or vice versa), every database initialization anywhere in the app would crash with `NameError` at that line, regardless of which feature triggered it. The 20 remaining migrations (23–42; 43–44 already committed) must land together, in strict ascending order, as their own dedicated commit (or bundled entirely into whichever group commits first) — never split by feature group. |
| `backend/database/migrations.py` | Same as above | **NO — same reason, same file pair** | The `_apply_vN` function *definitions* and their *call sites* are two different locations in the same file; both must move together |
| `backend/api/router.py` | G1, G2, G3, G4, G5, G6, G7, G_AA, G_PR | **YES** | Each addition is an independent `from backend.api.routes import x` + `api_router.include_router(x.router)` pair; FastAPI route registration order does not affect correctness for non-overlapping path prefixes — verified by reading the diff (alphabetically-sorted imports, no shared state between registrations) |
| `apps/admin-dashboard/src/App.jsx` | G_PR, G_DOCSFT, G1, G2, G3, G4, G5, G6, G7 | **YES** | 22 independent `if (active === 'X') page = <XPage/>` statements, no shared state, verified by reading the diff |
| `apps/admin-dashboard/src/components/Sidebar.jsx` | Same as App.jsx | **YES** | 42 independent nav-entry object literals, verified by reading the diff |
| `apps/admin-dashboard/src/services/api.js` | All frontend-touching groups | **YES** | 495 independent exported functions, one per API call, verified by reading the diff |
| `backend/core/config.py`, `backend/models/domain.py`, various repository files | Multiple groups each | **Likely yes, not individually re-verified this pass** | Same additive-only pattern observed everywhere else in this codebase; each group's settings/model additions were not individually confirmed order-independent in this time-boxed pass — recommend a quick same-style check (are additions independent declarations, or do they append to a sequential structure like schema.py's call chain?) before relying on this |

**Logical conflicts found: none.** No two groups were found modifying the
same line range of any shared file in a way that would produce a merge
conflict between them — all diffs observed were pure, non-overlapping
additions.

**Corrected recommendation**: commit `schema.py`/`migrations.py` as their
own dedicated "schema catch-up" commit (covering migrations 23–42 in one
shot) either first, before any of the 11 feature groups, or bundled
entirely into G1 (the first group in dependency order) — never attempt to
split it group-by-group. All other shared files remain safely
hunk-splittable as previously recommended.

## Step 3: Security Verification (evidence-backed only)

| System | Check | Evidence | Issue found? |
|---|---|---|---|
| Authentication | Admin-auth dependency on every route file | 39/43 route files (re-confirmed this pass); 4 exceptions all legitimate (login, health, public chat router, package init) | None |
| Authorization | Tool execution permission gating | `deterministic_tool_execution_service.py:84`: `if context.is_public_request and not descriptor.public_enabled:` — explicit allow-list check before any public-facing tool call | None |
| CSRF | Mutation-route coverage | 38/38 mutation route files (re-confirmed); `production_readiness.py` has 45 CSRF references (heaviest-covered route file found in this pass, consistent with its many mutation actions) | None |
| Secrets | Backend-wide TODO/FIXME/placeholder/bare-except scan | 0/0/1(historical, non-live)/0 (all re-confirmed from the prior Backend Completion pass; not re-run from scratch this pass, no code changed since) | None new |
| Trusted Web | SSRF defense in `safe_web_fetcher.py` | Explicit resolved-IP checking (`parsed.is_private`), not just hostname string matching; blocks localhost/private/link-local/multicast; raises `FetchBlockedError` on match — read directly this pass | None |
| Tool execution | Same as Authorization row | Public-enabled allow-list confirmed | None |
| Dataset workflow | Route-level auth/CSRF | Covered by the 39/43 and 38/38 figures above (dataset routes are among the 39/38) | None |
| Document SFT | Security-review/export-blocking | Already exhaustively verified across 4 prior passes (secret/PII redaction, checksum-gated idempotent handoff, `vision_required` blocking) — not re-verified from scratch this pass since no code changed | None new |
| Production Readiness | Route-level auth/CSRF | `production_readiness.py`: 2 admin-auth references, 45 CSRF references — confirmed present this pass | None |
| Smart Routing (Knowledge Routing/Gap, Public Chat) | Route-level auth/CSRF | Knowledge Routing/Gap routes are part of the 39/38 figures; Public Chat's `chat.py` deliberate public exemption already reviewed (rate limiting + Pydantic validation in place of auth) | None |

**No evidence-backed security issue found in this pass.** This is
consistent with every prior security-focused check in this multi-session
initiative — the codebase's auth/CSRF/input-validation discipline has been
uniformly clean every time it has been checked. This pass did not invent
or speculate about issues beyond what direct evidence supports.

## Step 4: Release Candidate Checklist summary

| Category | Status |
|---|---|
| Commit order | Established: `schema.py`/`migrations.py` (atomic, first or bundled with G1) → G1 → G_DOCSFT → G2 → G_AA → G3 → G4 → G_PR → G5 → G6 → G7. G0 (e2e infra) ships alongside whichever group first needs its own spec. |
| Security status | Clean across every check performed; 3 groups (G_PR, G3, G7) still recommended for a dedicated deeper pass before their own commit, not because an issue was found, but because of what they govern (model/RAG activation, external input intake, unauthenticated web/tool execution) |
| Regression status | 75/75 canonical regression batches, 3297/3297 assertions, 55/55 Playwright — all real, all passing, all against the current working tree (not yet reproducible from a clean `git checkout 26611fc` alone — see `final_release_checklist.md`'s correction) |
| Documentation status | Complete for all 11 groups (each has matching docs); 11 archive candidates and a 3-track phase-numbering ambiguity remain, both previously flagged, neither blocking |
| Test status | Backend/database: 263/264 canonical-manifest-registered (1 legitimate meta-test exclusion). Frontend: static review clean for all 40 pages; live coverage exists only in the uncommitted working tree today |
| Remaining limitations | (1) schema.py/migrations.py must land as one atomic 20-migration commit, not split; (2) 3 groups need a dedicated security pass before their own commit; (3) 5 `helpRegistry.js` entries and 9 pages' empty-state messaging remain deferred (unchanged from `final_release_checklist.md`); (4) phase-numbering ambiguity unresolved |
| Release blockers | None found that would prevent proceeding to RC1 preparation — every "NEEDS_REVIEW" item is a recommended deeper pass before that specific group's own commit, not a defect blocking the whole repository |

## Step 5: Release Decision

**RELEASE_CANDIDATE_READY_WITH_LIMITATIONS**

Evidence for every limitation:

1. **`schema.py`/`migrations.py` atomicity** — evidenced by reading
   `initialize_database()`'s flat, gap-intolerant `_apply_v23`...`_apply_v44`
   call chain directly (Step 2).
2. **G_PR, G3, G7 need a dedicated security pass** — not because a defect
   was found (Step 3 found none), but because their blast radius
   (model/RAG activation+rollback, external dataset intake, first
   unauthenticated fetch/tool execution) warrants more scrutiny than this
   time-boxed pass's spot-checks provide, consistent with the same
   recommendation made in the prior two passes.
3. **5 missing help entries, 9 pages' empty-state gap** — evidenced and
   precisely enumerated in `admin_assistant_completion_report.md` and
   `final_release_checklist.md`; deliberately not fixed to avoid rushing
   unverified Tamil content or unverified UI changes.
4. **Phase-numbering ambiguity** — evidenced in `documentation_index.md`
   (three tracks reusing the same integers).

None of these limitations are release blockers for RC1 preparation itself
— they are pre-commit and pre-tag action items, each with exact evidence
and exact scope, none requiring new code, new features, or redesign to
resolve.
