# Phase 10 — Live Dataset Discovery, Normalization & Comparison

Status: complete. Schema version 30 -> 31 (migration
`031_live_dataset_discovery_normalization_comparison`). See
[phase10_live_dataset_discovery_plan.md](phase10_live_dataset_discovery_plan.md)
for the full pre-implementation baseline audit and architecture
rationale.

A governed Live Dataset Discovery & Comparison Workspace: describe a
dataset requirement, search enabled external providers (Phase 9's
registry), normalize/deduplicate/score the results into candidates,
compare 2-5 of them, and save a reusable research session. This phase
never downloads a file, imports a dataset, clones a repository, or
grants a licence/RAG/training/evaluation/commercial-use approval --
every candidate stays a research artifact for the Source & Rights
Registry to formally approve later, and discovery is structurally
incapable of reaching an "approved" use status (enforced by SQLite
CHECK constraints, not just application logic).

## 1. Architecture

- **Pure policy** (`core_model/data_discovery/`): modalities, languages
  (a deliberately different full-word vocabulary from Phase 16's short
  detection codes, bridged by one explicit function), tasks, intended
  uses, commercial requirements, session/provider-run/licence/
  recommendation/freshness statuses, the `USE_APPROVAL_STATUSES`
  invariant (`("not_approved", "unknown")` -- structurally can never
  contain `"approved"`), bounded-execution constants, and
  `is_provider_searchable()` (Phase 9's `is_usable_for_discovery()` AND
  a `search_datasets`/manual-discovery capability check).
- **Candidate model** (`core_model/data_discovery/candidate_model.py`):
  `DatasetSearchRequest`/`NormalizedDatasetMetadata`/
  `DatasetSearchResult` -- frozen dataclasses every connector's search
  must honor. A field a connector cannot determine stays `None`/empty,
  never invented.
- **Scoring engine** (`core_model/data_discovery/scoring.py`): 13
  positive + 4 penalty dimensions, each a pure `score_*` function
  returning `{dimension, raw_value, weight, score, reason}`; a
  structural test (`inspect.signature()`) asserts no dimension ever
  gains a `downloads`/`popularity`/`stars` parameter.
- **Deduplication engine** (`core_model/data_discovery/deduplication.py`):
  conservative, signal-based, never title-similarity-based. Auto-merge
  only on an exact re-seen `provider_dataset_id`, a normalized
  `(organization, name)` pair, an identical declared URL, or a
  cross-reference between one candidate's URL and another's own URL.
  Anything weaker becomes a `possible_duplicate_group` flag for human
  review -- never an automatic merge.
- **Repository** (`backend/database/repositories/external_dataset_discovery.py`):
  one `ExternalDatasetDiscoveryRepository` over all 8 tables.
- **Connector extension** (`backend/services/external_data_connectors/`):
  two new, additive `search_datasets`/`get_dataset_metadata` methods on
  the existing Phase 9 `ExternalDataProviderConnector` protocol.
  `BaseHttpConnector`'s default honestly raises
  `ConnectorSearchError(status="unsupported")` (mirroring
  `ManualProviderConnector`'s existing pattern) so all 7 existing Phase
  9 connectors keep working unchanged. Real search implementations:
  Hugging Face, GitHub, Wikimedia (each a stable, publicly documented,
  unauthenticated-capable search endpoint). AI4Bharat/Bhashini keep the
  inherited `"unsupported"` default honestly -- neither has a confirmed
  stable public search API.
- **Services** (`backend/services/`): `ExternalDatasetNormalizationService`
  (bounds/redacts/checksums raw evidence, derives `freshness_status`),
  `ExternalDatasetDeduplicationService` (DB-backed resolution:
  merge-exact-source / merge-strong-signal / possible-duplicate / new),
  `ExternalDatasetScoringService` (wires the pure scoring dimensions to
  persisted rows, derives warnings/blocking-reasons and
  `recommendation_status`), `ExternalDatasetComparisonService` (2-5
  candidate side-by-side snapshots), `ExternalDatasetSearchSessionService`
  (session/requirement lifecycle), `ExternalDatasetSearchExecutionService`
  (the bounded, best-effort, per-provider-isolated search loop),
  `ExternalDatasetCandidateService` (list/detail/exclude/restore/manual
  entry).

## 2. Schema (migration 031)

8 new, all-additive tables: `external_dataset_search_sessions`,
`external_dataset_search_requirements` (1:1), `external_dataset_search_provider_runs`,
`external_dataset_candidates`, `external_dataset_candidate_sources`
(raw per-provider evidence), `external_dataset_candidate_scores`
(one row per scoring dimension), `external_dataset_candidate_comparisons`,
and an append-only `external_dataset_search_events` log. Every
`*_use_status` column's CHECK constraint literally excludes
`'approved'` -- proven by a migration test that asserts inserting
`'approved'` raises `sqlite3.IntegrityError`.

## 3. Bounded execution (Step 11)

| Constant | Value | Enforced in |
|---|---|---|
| `MAX_PROVIDERS_PER_SEARCH` | 8 | `_searchable_providers()` slice |
| `MAX_RESULTS_PER_PROVIDER` | 20 | connector `limit` + execution-loop slice |
| `MAX_CANDIDATES_PER_SESSION` | 100 | execution-loop running count, recorded as a `session_candidate_cap_reached` warning |
| `PER_PROVIDER_TIMEOUT_SECONDS` | 5.0 | `ConnectorConfig.timeout_seconds` |
| `OVERALL_SEARCH_DEADLINE_SECONDS` | 30.0 | wall-clock deadline check between providers |
| `MAX_RAW_METADATA_BYTES` | 32,768 | `bound_and_redact_raw_metadata()` |
| `MAX_QUERY_LENGTH` | 300 | `build_query()` |

All 4 numeric bounds are directly asserted by dedicated tests
(`test_dataset_discovery_security.py`), not just documented.

## 4. Security & resilience (Step 21)

- **No fetch of an attacker-controlled URL**: every connector builds
  its request URL only from the provider's own already-registered
  domain (`config.domains`), never from a field inside a provider's
  parsed response -- proven at runtime (a malicious `homepage` field
  containing `http://attacker.example/...` is never fetched) and
  statically (an AST scan asserts no `url = ...` assignment in the
  connector module references an `entry`/`payload`/`item` variable).
- **Raw evidence bounded + redacted before persistence**: secret-shaped
  keys (`auth_token`, `api_key`, etc.) are redacted; an oversized or
  non-JSON-safe payload (e.g. a literal `NaN`) degrades to a small,
  auditable truncation placeholder instead of raising or leaking.
- **One provider's failure never discards another's results**: every
  `ConnectorSearchError` and every truly unexpected exception is caught
  per-provider inside the execution loop; proven by a test where one
  provider's transport call raises `RuntimeError` mid-search and the
  other provider's candidate is still created.
- **No dynamic execution of provider content**: a structural regex scan
  across every module that parses a provider response asserts no
  `eval(`/`exec(`/`os.system(`/`subprocess.*(`/`pickle.load*(` call
  exists anywhere in that surface.
- **Every search is auditable**: recorded both in the session's own
  append-only `external_dataset_search_events` (mirroring Phase 9's
  `external_data_provider_events` pattern) and in the global
  `audit_logs` table.
- **Credentials**: reused Phase 9's reference-only model unchanged
  (`resolve_active_credential()`, extracted as a small shared helper so
  connection tests and dataset search resolve credentials identically)
  -- no secret value is ever read into a response.

## 5. Backend APIs

All under `/api/admin/dataset-discovery`, admin-only, CSRF-protected:
session CRUD + cancel, requirement get/set, run search, candidate
list/detail/exclude/restore/manual-add, provider-run list, event list,
comparison create/list/get.

## 6. Frontend

`apps/admin-dashboard/src/pages/DatasetDiscoveryPage.jsx`, added to
the Data nav group right after External Data Providers. 5 tabs
(Sessions, Requirement, Candidates, Comparison, History). Every
candidate row shows licence status, explainable score, recommendation,
provider count, and excluded state; a details panel shows raw sources
and the full per-dimension score breakdown with its `reason` text.

## 7. Admin Assistant integration

4 new read-only tools (`list_dataset_search_sessions`,
`get_dataset_search_session`, `list_dataset_candidates`,
`get_dataset_candidate`) and 2 new controlled actions
(`run_dataset_search` moderate, `exclude_dataset_candidate` low), both
wired through Phase 8's existing propose -> preview ->
confirm-with-stale-check -> execute -> verify -> audit pipeline --
proven by an end-to-end test including a genuine concurrent-mutation
race (`run_dataset_search` correctly refused at confirm time when
another admin cancelled the session in between). A new deterministic
chat path (`_match_dataset_discovery_intent()`) answers "find me a
dataset..."-style messages with real, live session-count guidance and
a navigation target -- never by inventing a dataset or a search result
the assistant never actually looked up.

## 8. Help registry

A new bilingual (EN/TA) entry added to
`apps/admin-dashboard/src/data/helpRegistry.js`, following the exact
structure every other Data Help entry uses, explicitly distinguishing
this page from External Data Providers ("where you might look") and
Sources & Rights ("what you actually brought in and what you may do
with it").

## 9. Tests

- `tests/core_model/`: policy (19), scoring (18), deduplication (9).
- `tests/database/`: migration 031 (10), repository (15).
- `tests/backend/`: connector search (20), normalization (9),
  deduplication service (8), scoring service (6), comparison service
  (5), search session/execution service (13), API (12), security (10),
  Admin Assistant integration (5), chat service (+2 dataset-discovery
  tests within the existing 14-test file).
- `apps/admin-dashboard/src/pages/DatasetDiscoveryPage.test.jsx` (9).
- Combined Phase-10-specific total: **159 backend/core_model/database
  tests + 9 frontend tests = 168**, all passing. Full targeted
  regression (every Phase 9 + Phase 10 file together, run repeatedly
  through this phase's build-out): 756 passed. Full core_model suite:
  532 passed. Full frontend suite: 109 passed.

## 10. Manual browser verification (Flows A-E)

Run against the real dev server (`vite` on :5174, proxying to the real
`uvicorn --reload` backend on :8000) with a dedicated `phase10-verifier`
admin account, via Playwright:

- **Flow A**: login, navigate to Dataset Discovery, safety notice
  visible.
- **Flow B**: create a session, set a requirement (Tamil + ASR), it
  moves to `ready`.
- **Flow C**: run search (no providers enabled in this sandbox -> a
  deterministic, honest `failed` outcome with `provider_count: 0` --
  the page never crashes).
- **Flow D**: add a manual candidate, exclude it, restore it.
- **Flow E**: select 2 candidates, create a comparison, see the
  dimension-by-dimension summary (honestly reporting "not yet scored"
  for unscored manual candidates rather than fabricating a score).

Also verified: the floating Admin Assistant answers "Can you find a
dataset for Tamil speech recognition?" with the real, live session
count and a "Go to Dataset Discovery" navigation button.

## 11. Bug found and fixed during manual verification

**Manual candidate addition was wrongly blocked after any finished
search, including a legitimate zero-provider `failed` outcome.**
`ExternalDatasetCandidateService.add_manual_candidate()` originally
refused whenever `session.status in TERMINAL_SESSION_STATUSES`
(`completed`/`failed`/`cancelled`/`expired`) -- but a session that
finished searching is still an open research workspace; only an
admin-cancelled or expired session should truly refuse further
curation. Caught live in Flow D (the "Add manual candidate" button
silently failed with "cannot add a candidate to a 'failed' session"
after Flow C's zero-provider search). Fixed by narrowing the guard to
`_ABANDONED_SESSION_STATUSES = ("cancelled", "expired")`; two
regression tests added
(`test_manual_candidate_can_still_be_added_after_a_search_finishes`,
`test_manual_candidate_is_refused_on_a_cancelled_session`).

## 12. Limitations / explicitly deferred (per the task's own rules)

No licence verification (declared licence is recorded, never
verified); no dataset download, sample import, quarantine, or RAG
sandbox; no automatic provider discovery or web crawler; no
browser-automation authentication; image/audio/video/multimodal
modalities are discoverable-metadata-only (no connector actually
filters or validates by modality yet); only 3 of 8 built-in providers
(Hugging Face, GitHub, Wikimedia) have a real search implementation --
AI4Bharat and Bhashini honestly report `"unsupported"` rather than a
fabricated result.

## 13. Phase 11 handoff

A future licence-verification phase should: (a) implement real
per-dataset licence-file/dataset-card fetching behind the existing
`get_dataset_metadata` connector method; (b) only then allow
`licence_status` to transition out of `unknown`/`declared` toward a
verified state; (c) only then allow a *separate*, explicit Source &
Rights Registry decision to move a candidate's `commercial_use_status`/
`training_use_status`/`rag_use_status`/`evaluation_use_status` off
`not_approved`/`unknown` -- this phase's schema cannot represent
`"approved"` in those columns at all, so Phase 11 will need its own
migration to add that capability, never a retrofit of this one.

**Do not proceed to Phase 11 in this session.**
