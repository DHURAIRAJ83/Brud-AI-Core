# Phase 7 — Dataset Version, RAG & Training Pipeline Integration

Status: complete. Schema version 27 -> 28 (migration
`028_data_studio_phase7_dataset_rag_training_integration`).

A governed build/preflight/lineage layer sitting *above* the existing
dataset build/versioning system, the existing RAG ingestion system, and
the existing tokenizer/pretraining-readiness/instruction-tuning/
evaluation/model-release systems — integrating them, never replacing
any of them. See
[phase7_dataset_rag_training_integration_plan.md](phase7_dataset_rag_training_integration_plan.md)
for the full pre-implementation baseline audit and architecture
rationale.

## 1. Architecture

**One governed build engine, six thin target-specific handoffs, both
built entirely on existing services.** `GovernedBuildService` wraps
the *existing* `DatasetVersioningService` (`create_build`/
`validate_build`/`run_build`/`create_export`) to produce exactly one
immutable, governed `dataset_version` per `governed_build_requests`
row — it never reimplements version creation, splitting, checksums, or
JSONL export.

A `target_pipeline` (8 values: `dataset_version, rag, tokenizer,
pretraining, instruction_tuning, evaluation, commercial_release,
public_export`) is a **different vocabulary axis** than Phase 6's
existing `target_use` (rights-eligibility, not pipeline-selection) —
`GOVERNANCE_TARGET_USES` is never extended; instead a fixed, explicit
mapping (`core_model.pipeline_integration.PIPELINE_TARGET_USE_MAP`)
bridges the two:

| `target_pipeline` | Phase 6 `target_use` checked |
|---|---|
| `dataset_version` | `dataset_export` |
| `rag` | `rag` |
| `tokenizer` / `pretraining` / `instruction_tuning` | `training` |
| `evaluation` | `evaluation` |
| `commercial_release` | `commercial` |
| `public_export` | `public_export` |

Once a governed `dataset_version` exists, each pipeline gets a thin,
**honest** handoff — one that only ever calls a real existing
integration point:

- **RAG**: calls the *existing* `RagIngestionService.create_source
  (source_type='dataset_version', ...)`, confirmed by direct baseline
  inspection to already accept a dataset_version verbatim.
- **Tokenizer / Pretraining / Instruction-tuning**: since
  `TokenizerCorpusService.build_corpus()` is structurally scoped to a
  Phase 19-21A `corpus_release` and cannot accept Data-Studio content,
  and since `pretraining_jobs`/`InstructionTuningService
  .create_experiment()` already accept a `dataset_version_id`
  directly, the handoff marks a completed dataset version ready and
  records a lineage event — it never creates a `pretraining_jobs`/
  `instruction_tuning_experiments` row itself. The existing, separate,
  manual admin action of pointing a new job at this dataset_version_id
  remains exactly as it is today.
- **Evaluation**: produces a governed dataset_version with every item
  forced to `split='test'` (isolation is structural, not just policy).
- **Commercial release / public export**: pure preflight — evaluates
  every candidate's current, expiry-aware rights/attribution state and
  returns a blocked-item report.

## 2. Schema (migration 028)

All additive; no existing table's columns, CHECK constraints, or
triggers changed; the existing `dataset_versions`/`dataset_version_items`/
`dataset_build_jobs`/`dataset_exports` are untouched.

| Table | Purpose |
|---|---|
| `governed_build_requests` | The build lifecycle root: `target_pipeline`, `status` (9 values), `configuration_json`, result artifact, and (additive) `manifest_extension_json`. |
| `governed_build_preflight_results` | Append-only snapshot of every preflight run (eligible/blocked/warning/excluded counts + full summaries) — a build can be re-previewed many times before confirmation, and every run is preserved. |
| `governed_build_request_items` | Per-entity decision tied to a specific preflight run; `included` is mutable (the one deliberate exception — Step 7's "allow admin to revise selection"), everything else about a row is fixed at creation. |
| `pipeline_artifact_links` | Links a build request to the real artifact it produced (`dataset_version`, `rag_source`, ...) — `UNIQUE(build_request_id, artifact_type, artifact_public_id)` prevents a duplicate link. |
| `lineage_edges` | The genuinely new capability: polymorphic `(entity_type, entity_id)` edges for the Data-Studio side of the chain that had no queryable link before (opaque `metadata_json` references only). `UNIQUE` on the full edge tuple makes creation idempotent. Append-only. |
| `lineage_events` | Append-only domain event log backing a build request's own History tab. |

`governed_build_requests.status`/`governed_build_request_items.included`
are the only two columns anywhere in this migration left deliberately
mutable, mirroring the codebase's established "queue item status can
change, facts cannot" convention.

## 3. Target pipeline types and governed build lifecycle

`draft -> preflight_running -> preflight_ready | blocked ->
approved_to_build -> building -> completed | failed -> cancelled`.
`create` -> `preview` (ephemeral, no persistence) -> `preflight`
(persists a snapshot + items, the real decision record) ->
`update_selection` (admin revises which eligible/warning items are
included) -> `confirm` -> `execute` (the *only* step that calls the
real `DatasetVersioningService`) -> target-specific handoff.

## 4. Selection and preflight logic

`PipelineEligibilityService.evaluate_entity()` combines, per candidate
`dataset_record`: legacy classification (Step 5), prior duplicate
export for this exact target, cross-build evaluation isolation, and —
only when none of those already decide the outcome — a real Phase 6
`GovernanceApprovalService.evaluate()` call. Every reason is explicit
(`decision`, `decision_code`, `blocking_reasons`, `warnings`) — never
one aggregate boolean.

**Critical fix made during this phase's own testing**: the first
implementation called (and persisted) a real Phase 6 governance
decision for *every* candidate unconditionally, including
legacy-and-not-overridden ones — meaning a preflight run that
correctly *blocked* a legacy record as `LEGACY_UNCLASSIFIED` was
simultaneously, silently curing that same record's legacy status as a
side effect (by writing a fresh `governance_target_approvals` row for
it). A second preflight run on the same record would then see it as
non-legacy. Fixed by short-circuiting before any Phase 6 call for
legacy-and-unoverridden entities — they now never touch
`governance_target_approvals` at all until an explicit governance scan
or a documented legacy override is given.

## 5. Legacy compatibility policy

A `dataset_record` with zero governance activity (no review item, no
target approval, ever) is `legacy_unclassified` from Phase 7's own
perspective, regardless of what a live Phase 6 rights check would say
— confirmed by both an automated test and manual browser verification
(Flow C). It is excluded from every new governed build by default;
inclusion requires either an explicit prior governance scan (Quality &
Approval) or a documented `legacy_overrides` reason in the build's own
configuration, which surfaces as a warning, never a silent inclusion.
Existing dataset versions/builds/exports remain fully readable and
re-verifiable regardless of governance status — nothing about reading
an *existing* version changed.

## 6. Dataset version integration, split/leakage safety

`GovernedBuildService` drives the real `DatasetVersioningService`
end-to-end (`create_build` -> `validate_build` -> `run_build`),
pinning the exact governance-eligible record set via a new, additive
`selectable_records()` filter key (`include_public_ids`) — the
*existing* `selectable_records()` contract is otherwise completely
unchanged, so the pre-existing, non-governed `/api/admin/datasets/builds`
path behaves exactly as before (confirmed by its own existing test
suite passing unchanged). Split configuration is fixed by pipeline
shape, never left to be misconfigured: `rag`/`tokenizer`/
`dataset_version`/`commercial_release`/`public_export` force 100%
`train`; `evaluation` forces 100% `test`; `pretraining`/
`instruction_tuning` use the admin-requested (or default 90/5/5) split.
Cross-build evaluation isolation excludes any record already included
in a completed evaluation-target build from a training-target build's
candidate pool — the existing document-level grouping and content-hash
leakage check inside `DatasetVersioningService` are reused verbatim,
never reimplemented.

## 7. Governance-aware manifest

`DatasetGovernanceManifestService` assembles an additive extension
(record/language/source/rights counts, quality/duplicate/conflict
summaries, legacy count, override count, real Phase-2 attribution
entries, two separate SHA-256 checksums) and stores it in
`governed_build_requests.manifest_extension_json` — generated once
from already-persisted data and never recomputed afterward. The
existing `dataset_versions.manifest_json`/`checksum_sha256` and their
own `_checksum_payload()` are never touched, so no pre-Phase-7
version's `verify_version()` is ever affected.

## 8. RAG handoff integration

`GovernedRagHandoffService.ingest()` calls the real
`RagIngestionService.create_source(source_type='dataset_version', ...)`,
guards against duplicate ingestion via both a `lineage_edges` check and
`pipeline_artifact_links`' own unique constraint, and never calls
`activate_vector_index`/`activate_keyword_index`/retrieval-profile
`activate` — confirmed structurally (the service never references
those methods) and by manual verification (Flow D-equivalent coverage
via the RAG Handoffs tab). A retrieval "smoke test" is a thin
pass-through to the existing `/retrieve` call, honest that it only
works once the admin has separately built and activated the rest of
the RAG pipeline through the existing, unmodified workflow.

## 9. Tokenizer/pretraining/instruction-tuning/evaluation integration

`GovernedTrainingHandoffService` marks a completed, governed dataset
version as ready for its matching pipeline via a lineage event — it
never creates a `pretraining_jobs`/`instruction_tuning_experiments`
row, and never recomputes
`core_model.pretraining_readiness.readiness.overall_readiness()` (a
17-dimension check spanning the tokenizer/model/training-loop systems
this phase does not own). Mapping a governed evaluation-target dataset
version into `model_evaluation_fixture_sets` remains a separate,
existing, manual step — documented as an explicit limitation (no
existing bridge to reuse; inventing one would be a second, competing
evaluation-data system).

## 10. Public/commercial preflight

`PublicCommercialPreflightService.check()` combines the build's own
preflight decisions with each entity's *current*, expiry-aware
approval status (`GovernanceApprovalService.status()`, since a
previously granted override may since have expired) into a complete
blocked-item report with exact decision codes — never a legal opinion,
never a publishing action.

## 11. Lineage implementation

`LineageGraphService` never duplicates the lineage that already exists
via plain foreign keys from `dataset_version` onward
(`model_release_candidates.dataset_version_id/tokenizer_version_id/
checkpoint_id/instruction_tuning_candidate_id/model_evaluation_run_id`,
confirmed complete by direct inspection) — it only bridges the
previously-missing Data-Studio-side gap via `lineage_edges`, created
idempotently at build-execute time (`dataset_record -[included_in]->
dataset_version`) and at RAG-ingest time (`dataset_version
-[indexed_into]-> rag_source`). `trace()` walks both directions and
reports `complete: false` rather than fabricating a missing link;
`for_model_release()` reads the existing direct FKs and appends any
upstream Data-Studio edges.

## 12. Backend modules created

`core_model/pipeline_integration/{__init__,eligibility,split_policy,manifest}.py`;
`backend/database/repositories/governed_builds.py`;
`backend/services/{pipeline_eligibility_service,governed_build_service,
dataset_governance_manifest_service,governed_rag_handoff_service,
governed_training_handoff_service,lineage_graph_service,
public_commercial_preflight_service}.py`;
`backend/models/governed_builds.py`;
`backend/api/routes/{governed_builds,data_lineage}.py`.

## 13. Backend modules modified (additive only)

`backend/database/schema.py` (`SCHEMA_VERSION` 27->28, `PHASE28_SCHEMA`,
plus one new optional filter key and one new column documented above);
`backend/database/migrations.py` (`_apply_v28`); `backend/database/
repositories/dataset_quality.py` (`selectable_records()` gained the
optional, backward-compatible `include_public_ids` filter key);
`backend/api/router.py`; `tests/backend/test_system_api.py` (expected
migrations set).

## 14. APIs added

`/api/admin/governed-builds` (summary, list, create, get, update,
preview, preflight, confirm, execute, cancel, selection, items,
blocked-items, manifest [GET+POST], history, dataset-version,
rag-handoff, tokenizer-handoff, pretraining-handoff, sft-handoff,
evaluation-handoff, public-export-preflight, commercial-preflight) and
`/api/admin/data-lineage` (edges, entity trace, entity upstream/
downstream, source, model-release) — 27 endpoints total, all behind
`require_admin` + CSRF for mutations.

## 15. Frontend

`BuildsPipelinesPage.jsx` ("Builds & Pipelines" in the Data submenu,
placed right after Quality & Approval): 11 tabs (Overview, Create
Build, Build Preview, Blocked Records, Dataset Versions, RAG Handoffs,
Tokenizer & Training, Evaluation Builds, Manifests, Lineage, History).
Existing pages (`DatasetsPage`, `RagPage`, `CorpusPage`,
`PretrainingReadinessPage`, `ModelEvaluationPage`, `ModelRegistryPage`,
`DataOverviewPage`) received small, additive governance-context notes
(and, for `DatasetsPage`, a real "View lineage" button per version) —
none were restructured or had existing tabs removed/renamed.

## 16. Navigation and Help registry

`Sidebar.jsx`/`App.jsx`/`helpRegistry.js` all updated in the exact
recommended position (right after Quality & Approval); every existing
route/hash key preserved. A full bilingual (Tamil/English)
`builds_pipelines` help entry was added, chained from
`quality_approval` and chaining onward to `datasets`/`knowledge_rag`/
`pretraining_readiness`.

## 17. Tests

96 new automated tests: 21 core_model (`pipeline_integration`
eligibility/split_policy/manifest), 8 migration
(`test_phase28_migration.py`), 10 repository
(`test_governed_build_repository.py`), 12 `GovernedBuildService`, 4
`DatasetGovernanceManifestService`, 4 `GovernedRagHandoffService`, 6
`GovernedTrainingHandoffService`, 5 `LineageGraphService`, 3
`PublicCommercialPreflightService`, 7 API
(`test_governed_builds_api.py`), 8 frontend
(`BuildsPipelinesPage.test.jsx`), plus updates to `DataOverviewPage`'s
existing test suite for its new metric group. All 1042 backend tests
and 82 frontend tests pass; both frontend builds (`admin-dashboard`,
`chatbot`) succeed; `ruff check` is clean across `backend/`,
`core_model/`, `tests/`.

## 18. Manual browser verification (Flows A, C, I, J + cross-cutting checks)

Verified live against the real `uvicorn --reload` backend, the real
Vite admin-dashboard dev server, and the persistent dev database
(already at schema 28), via Playwright driving an actual Chromium
browser through a real authenticated admin session and real API
setup calls in the same session:

- **Flow A**: created and approved a real dataset record, ran an
  explicit governance scan, created a `dataset_version`-target build,
  ran Preview then Preflight (reported `preflight_ready`), Confirmed,
  Executed — a real, immutable `dataset_version` was created — then
  generated and verified its governance manifest (`record_count: 1`).
- **Flow C**: an approved-but-never-governance-scanned record was
  correctly blocked as `LEGACY_UNCLASSIFIED` on its very first
  preflight, and the Blocked Records tab reported the exact reason.
- **Flow I**: ran the public-export preflight against a mixed
  candidate set and got a complete blocked-item report with exact
  decision codes.
- **Flow J**: traced the Flow A dataset record's lineage and confirmed
  a complete `dataset_record -[included_in]-> dataset_version` edge —
  never fabricated, never marked incomplete when real data existed.
- **Cross-cutting**: build history showed a complete, audited event
  trail; the Execute button was correctly disabled after a build
  already completed (duplicate-execution prevention); the bookmarked
  `#Builds%20%26%20Pipelines` route loaded directly; a hard refresh on
  that route reloaded correctly; the page rendered at a 390px mobile
  width; the bilingual Data Help page (English/Tamil toggle) was
  reachable and lists "Builds & Pipelines."

18/18 browser-level checks passed after fixes; screenshot captured of
the final Data Help page state confirming the new navigation entry.

## 19. Bugs discovered and fixed

1. **`PipelineEligibilityService.evaluate_entity()` silently cured a
   record's legacy status as a side effect of blocking it.** It called
   (and persisted) a real Phase 6 governance decision for *every*
   candidate unconditionally — including legacy-and-unoverridden ones
   — meaning the very preflight run that correctly blocked a legacy
   record also wrote a fresh `governance_target_approvals` row for it,
   making a *second* preflight run see it as non-legacy. Caught by a
   dedicated `PublicCommercialPreflightService` test before manual
   verification. Fixed by short-circuiting before any Phase 6 call for
   legacy-and-unoverridden entities.
2. **`BuildsPipelinesPage.jsx`'s `action()` helper showed a
   "completed" notice before the refreshed build detail had actually
   been fetched**, creating a real window where the UI displayed a
   stale status (e.g. still `draft` immediately after a successful
   preflight). Caught live during manual browser verification (the
   automated frontend test suite used synchronous mocked promises and
   never exposed the ordering issue). Fixed by fetching the refreshed
   detail and re-running list/summary refreshes *before* setting the
   success notice.
3. **Two instances of live-database schema drift**, both caused by
   this development session's `uvicorn --reload` process re-running
   `initialize_database()` against the real, persistent dev database
   at an intermediate point *during* this phase's own iterative
   schema.py editing — before the file reached its final, correct
   form. Since forward-only migrations are idempotent (`if applied:
   return`) and `CREATE TABLE IF NOT EXISTS` never retroactively
   alters an already-created table, the live database ended up
   physically stale relative to the (fully correct) final `schema.py`
   source of truth, even though `schema_migrations` recorded the
   migration as applied:
   - `governance_review_items` still had Phase 6's original,
     already-fixed-in-source-code 3-column table-wide `UNIQUE
     (entity_type, entity_public_id, status)` constraint instead of
     the corrected partial unique index — causing a real 409 on a
     second preflight run for the same entity. Confirmed by inspecting
     the live table's `sqlite_master` SQL directly.
   - `governed_build_requests` was missing the `manifest_extension_json`
     column entirely (added to `schema.py` after this phase's own
     migration had already been applied once to the live database) —
     causing a real 500 on manifest generation.
   Both were repaired surgically and non-destructively (a full
   recreate-and-copy for the table-constraint fix; a plain `ALTER
   TABLE ADD COLUMN` for the missing column) — no migration was
   rewritten, no `schema_migrations` history was altered, and no data
   was lost; `PRAGMA integrity_check`/`foreign_key_check` were clean
   before and after. This is a caveat specific to live-reloading a
   long-running dev server against a persistent database while
   iteratively editing schema code within one long session — the
   `schema.py` source of truth itself was correct throughout;
   diffing a live table's actual `sqlite_master` SQL against the
   final schema module before declaring migration work "done" is now
   a recommended check for any future phase using the same workflow.

## 20. Limitations / explicitly deferred

- No automatic training/tokenizer-training/RAG-index-activation/
  model-release/public-publishing, no new training algorithms, no
  semantic embedding duplicate detection, no AI-generated data, no
  automatic translation/Tanglish generation — all per the task's
  explicit out-of-scope list.
- No bridge from a governed evaluation-target dataset version into
  `model_evaluation_fixture_sets` — no existing integration point to
  reuse; building one would be a second, competing evaluation-data
  system, and inventing one was explicitly out of scope for this
  phase.
- A rights-usage evaluator is consulted for the `rag`/`training`/
  `evaluation`/`commercial`/`public_export` target uses only (the ones
  Phase 6 already wires for `manual_data_record`/
  `structured_record_candidate`) — `dataset_export` target-use checks
  rest on Phase 6's own dataset_record-level governance state, per
  Phase 6's own documented scope boundary, carried forward unchanged.
- No existing dataset version, build, export, RAG source/index,
  training run, or model release was backfilled or destructively
  modified — this phase only adds new tables, one new optional
  repository filter key, one new manifest column, and new admin-facing
  workflows on top of the unmodified existing six systems.

**Do not proceed to Phase 8.**
