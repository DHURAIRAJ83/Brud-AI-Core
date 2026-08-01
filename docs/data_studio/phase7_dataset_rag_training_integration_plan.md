# Phase 7 Plan — Dataset Version, RAG & Training Pipeline Integration

Written before implementation, per this phase's Step 1. Synthesizes four
parallel baseline-research passes over: (a) the existing dataset
build/versioning system, (b) the existing RAG ingestion/index system,
(c) the existing tokenizer/pretraining-readiness/instruction-tuning/
evaluation/model-release systems, and (d) the existing frontend pages
and help registry.

## 1. Existing systems (confirmed by direct inspection)

### 1.1 Dataset build/versioning (`backend/services/dataset_versioning.py`)

`DatasetVersioningService` (built on `DatasetQualityRepository`, the
same repo `dataset_quality.py` uses) already provides the full
build/version lifecycle: `create_version`/`create_build` ->
`validate_build` -> `run_build` -> `archive_version`, plus
`create_export`/`export_file`/`verify_export`. Tables: `dataset_versions`
(`draft -> building -> ready -> failed | archived`), `dataset_version_items`
(join table with `split` + `sequence_number`), `dataset_build_jobs`,
`dataset_build_events` (append-only), `dataset_exports`.

Split logic (`_select_records`/`_groups`/`_split_groups`/`_leakage`) is
**already deterministic and already groups** by
`metadata_json.document_public_id + source_page_start/end` when
present, falling back to `content_hash`/`public_id` — document-level
grouping already exists. Leakage checking is content-hash collision
only (`blocked`/`safe`), no semantic-family/translation grouping yet.

Manifest (`_manifest()`) is a plain dict with a `schema_version` field,
already versioned at 6; checksum is SHA-256 of a narrower
`_checksum_payload()` (identity + core per-record fields), **not** the
full manifest dict — so Phase 7 can add new manifest keys without ever
touching `_checksum_payload` or invalidating existing versions'
`verify_version()`/`verify_export()`.

**The critical existing gap**: `selectable_records()`
(`dataset_quality.py`) filters only on `dataset_records.status='approved'`
and the old Phase-1 `dataset_sources.licence_status != 'rejected'` —
it is completely oblivious to Phase 2 rights, Phase 3/5 provenance, and
Phase 6 governance (target approvals, blocking issues, duplicate/
conflict groups). This is exactly the gap Phase 7 closes, additively,
by wrapping this selection with a governance post-filter rather than
editing `selectable_records()` itself.

`dataset_records.source_id` FKs only to the old, simple `dataset_sources`
table (Phase 1) — a bridge row, not the real rights source. The real
rights linkage for a bridged record lives in Phase 2's
`source_record_links` (polymorphic `(entity_type, entity_public_id) ->
data_source_id`), already read by `GET /versions/{id}/rights-summary`
via `SourceUsagePolicyService.rights_summary_for_entities()`. Phase 7
reuses this exact call rather than re-deriving rights from
`dataset_sources.licence_status`.

Duplicate-export protection already exists per-candidate:
`structured_record_candidates.exported_dataset_record_public_id`/
`rag_handoff_at`, `manual_data_records.exported_dataset_record_public_id`
— both bridges are already Phase-6-preflight-gated
(`GovernanceExportReadinessService.require_allowed(..., "dataset_export"/
"rag_handoff")`, added in Phase 6).

### 1.2 RAG ingestion (`backend/services/rag_ingestion_service.py`)

`RagIngestionService.create_source(source_type=...)` already accepts
`source_type='dataset_version'` with `source_entity_public_id=<dataset
version public_id>` and resolves its content by joining
`dataset_version_items JOIN dataset_records WHERE split='train'` —
**a governed dataset_version is already a first-class, zero-code-change
RAG ingestion input.** `manual_admin_content` is a second existing
inline `source_type` (raw text + metadata) usable for chunk-level
content that isn't itself a `dataset_record`.

Every layer already has its own manual, explicit activation step
(`activate_vector_index`/`activate_keyword_index`/retrieval-profile
`.../activate`) — Phase 7's "no auto-activation" rule is satisfied
simply by never calling these from the new governed wrapper.

No RAG-native `internal_only` flag exists; internal-only-ness is Phase
2's `source_rights.internal_only`, already reachable via the existing
`GET /sources/{id}/rights-check` -> `SourceUsagePolicyService
.rights_summary_for_entities("rag_knowledge_source", ids, "rag")` call
— reused as-is, not reimplemented.

Duplicate-ingestion protection today is content-hash based per source
only (`UNIQUE(knowledge_source_id, content_checksum_sha256)` on
`rag_source_versions`) — no cross-source/cross-dataset-version check
exists; Phase 7 adds one via `lineage_edges`/`pipeline_artifact_links`
(never re-ingest a dataset_version that already has a linked RAG
source).

`StructuredRecordCandidateService.create_rag_candidate()` today only
sets `rag_handoff_at` and audits — it never actually calls
`RagIngestionService`. Phase 7 builds the real bridge.

RAG manifests (`POST/GET /spaces/{id}/manifest[/verify]`) already
exist — Phase 7's governance-aware manifest work extends the
*dataset-version* manifest, and references (not duplicates) the
existing RAG manifest for RAG-target builds.

### 1.3 Tokenizer / pretraining / instruction-tuning / evaluation / release

`TokenizerCorpusService.build_corpus()` is **specific to the Phase
19-21A Tamil corpus-release pipeline** — it consumes an approved,
finalized `corpus_release` (a completely separate content pipeline
from Data Studio's `dataset_records`) and materializes it into a
*new* `dataset_version` via `pretraining_bridge.materialize_corpus_release()`.
Data-Studio-approved content (Manual Data/Structured Records/PDF
chunks) was never part of a `corpus_release` and has **no existing
path into this specific service** — confirmed by direct inspection of
`tokenizer_corpus_service.py`'s docstring and implementation.

`core_model.pretraining_readiness.readiness.overall_readiness()` (17
independent dimensions, each `pass/warning/fail/not_evaluated`) already
defines the exact readiness vocabulary: `not_ready`,
`ready_for_experimental_pretraining`, `ready_for_bounded_pretraining`
— reused verbatim per Step 15's "do not invent readiness if current
system already defines it."

`PretrainingService`/`pretraining_jobs` and
`InstructionTuningService.create_experiment()` **already accept a
`dataset_version_id`/`dataset_version_public_id` directly** as their
real training/SFT input. Evaluation fixture sets are a separate,
already-immutable-and-versioned concept (`ModelEvaluationService`,
not `dataset_records`-based).

`model_release_candidates` already carries direct FKs
(`dataset_version_id, tokenizer_version_id, core_model_version_id,
checkpoint_id, instruction_tuning_candidate_id, model_evaluation_run_id`)
— **complete lineage from dataset_version through model release
already exists via plain foreign keys.** No generic lineage/graph table
exists anywhere in the schema (confirmed by a broad `lineage` grep —
only informal booleans like `lineage_complete` exist, never a
queryable edge list). This confirms `lineage_edges`/`lineage_events`
are genuinely new, but **only needed for the Data-Studio side of the
chain** (source -> PDF page -> chunk -> structured record -> dataset
record), which today only has opaque `metadata_json` references
(e.g. `dataset_records.metadata_json.manual_data_record_public_id`),
never a real queryable link. From `dataset_version` onward to
`model_release`, direct FKs already give complete lineage — Phase 7
must not duplicate those with edges, only bridge the gap before them.

`DATASET_RECORD_TYPE_MAP` (`core_model/manual_data/__init__.py`)
already converts every Manual-Data/Structured-Record `record_type`
(dictionary_entry, question_answer, instruction_response, ...) into
the 7 real `DatasetRecordType` values (`pretrain, instruction, chat,
translation, tanglish_pair, safety, preference`) *before* the record
ever reaches `dataset_records` — Phase 7's instruction-tuning/tokenizer
eligibility filtering operates on these 7 already-mapped types plus
governance state, never reinventing the mapping.

### 1.4 Frontend

Confirmed exact current `Sidebar.jsx` `dataGroup.children` order, the
current `App.jsx` Data-section if-chain, and the current
`helpRegistry.js` `dataHelpEntries` pageId order/`nextPageIds` (see
research transcript) — Phase 7 inserts "Builds & Pipelines" right after
"Quality & Approval" in all three places, matching Step 25's
recommended placement exactly.

No test files exist yet for `DatasetsPage`, `RagPage`, `CorpusPage`,
`PretrainingReadinessPage`, `ModelEvaluationPage`, or
`ModelRegistryPage` — Phase 7's additive changes to those pages should
stay minimal (a governance-context readout, not new interactive
surface) precisely because they have no regression-test safety net
today; the new "Builds & Pipelines" page gets full test coverage since
it is new.

## 2. Architecture decision

**One governed build engine, six thin target-specific handoffs, both
built entirely on existing services.**

`GovernedBuildService` wraps the *existing* `DatasetVersioningService`
(`create_build`/`validate_build`/`run_build`/`create_export`) to
produce exactly one immutable, governed `dataset_version` per
`governed_build_requests` row. It never reimplements version creation,
splitting, checksums, or JSONL export — it selects eligible
`dataset_record` entities (via a governance post-filter layered over
the existing `selectable_records()`), and drives the existing builder.

A `target_pipeline` (Step 2's 8 values) is a **different vocabulary
axis than Phase 6's existing `target_use`** (rights-eligibility, not
pipeline-selection) — `GOVERNANCE_TARGET_USES` is *not* extended, per
a fixed, explicit mapping table
(`core_model.pipeline_integration.PIPELINE_TARGET_USE_MAP`):

| `target_pipeline` | Phase 6 `target_use` checked |
|---|---|
| `dataset_version` | `dataset_export` |
| `rag` | `rag` |
| `tokenizer` | `training` |
| `pretraining` | `training` |
| `instruction_tuning` | `training` |
| `evaluation` | `evaluation` |
| `commercial_release` | `commercial` |
| `public_export` | `public_export` |

Every candidate `dataset_record` is evaluated via
`GovernanceApprovalService.evaluate("dataset_record", public_id,
mapped_target_use, ...)` (persisted) — reusing Phase 6 verbatim, never
reimplementing rights/quality/duplicate/conflict gating.

Once a governed `dataset_version` exists, each pipeline gets a thin,
**honest** handoff — honest meaning it only ever calls a real existing
integration point, never a fabricated one:

- **RAG**: calls the *existing*
  `RagIngestionService.create_source(source_type='dataset_version',
  source_entity_public_id=<version>)` for real — a genuine, already-
  supported integration point. Never auto-activates an index.
- **Tokenizer / Pretraining / Instruction-tuning**: since
  `TokenizerCorpusService.build_corpus()` is structurally scoped to
  `corpus_release`s and cannot accept Data-Studio content, and since
  `pretraining_jobs`/`InstructionTuningService.create_experiment()`
  already take a `dataset_version_id` as their real input, Phase 7's
  handoff for these three pipelines is: produce the eligible governed
  `dataset_version` (this *is* the artifact those systems already
  expect), run the *existing* readiness/eligibility check
  (`overall_readiness()` for pretraining), and record a
  `pipeline_artifact_link`. The actual `pretraining_jobs`/
  `instruction_tuning_experiments` row is still created through the
  existing, unmodified, manual admin action — satisfying "no automatic
  training start" structurally, not by a flag.
- **Evaluation**: produces a governed `dataset_version` with every
  item forced to `split='test'` (isolation is structural, not just
  policy) for admin reference; mapping into
  `model_evaluation_fixture_sets`/`fixtures` remains a separate,
  existing, manual step (documented as a limitation — no existing
  bridge from a plain dataset_version into a fixture set exists to
  reuse, and inventing one would be a second competing eval-data
  system).
- **Commercial release / public export**: pure preflight (Step 20) —
  evaluates every candidate's rights/attribution/redistribution/expiry
  state and returns a blocked-item report; may optionally also produce
  a governed dataset_version if the admin proceeds, but never
  publishes or releases anything itself.

## 3. Legacy compatibility policy

A `dataset_record` with no `governance_review_items`/
`governance_target_approvals` row at all (created before Phase 6, or
via the Phase 20/21A corpus-release bridge, which predates governance)
is classified `legacy_unclassified` by `PipelineEligibilityService` —
never silently treated as approved, never silently excluded either.
Existing dataset versions/builds remain fully readable and
re-verifiable (`verify_version`) regardless of governance status,
since Phase 7 changes nothing about how an *existing* version is read.
A **new** governed build excludes `legacy_unclassified` records by
default; an explicit, reasoned, audited legacy-inclusion override
(reusing Phase 6's override mechanics) is required to include one.

## 4. Migration decision

Additive only, schema 27 -> 28: `governed_build_requests`,
`governed_build_request_items`, `governed_build_preflight_results`,
`pipeline_artifact_links`, `lineage_edges`, `lineage_events`. No
existing table's columns, CHECK constraints, triggers, or the existing
`dataset_versions`/`dataset_version_items`/`dataset_build_jobs`/
`dataset_exports` shape change at all.

## 5. Compatibility risks

- **Risk**: a governed build's split-safety enhancement (Step 8) needs
  to know whether a record was already included in a *prior*
  evaluation-target build, to keep it out of a later training-target
  build's train/validation splits — this requires a cross-build query,
  not just within-build leakage checking. **Mitigation**: query prior
  `governed_build_request_items` where the parent request's
  `target_pipeline='evaluation'` and `included=1`; exclude those
  `entity_id`s from train/validation candidate pools for any other
  target. No new statistical algorithm — an additional exclusion
  filter over existing deterministic selection.
- **Risk**: `SCHEMA_VERSION` moving 27->28 triggers the same class of
  hardcoded-version-assertion regression hit in every prior phase.
  **Mitigation**: grep for hardcoded `SCHEMA_VERSION`/`applied_migrations`
  assertions before the final verification pass (same as every prior
  phase).
- **Risk**: adding governance eligibility filtering on top of
  `selectable_records()` could silently change which records an
  *existing*, non-governed build (created via the pre-existing
  `POST /builds` API, bypassing the new governed layer entirely)
  selects. **Mitigation**: `selectable_records()` itself is never
  edited; the governance filter only ever runs inside the *new*
  `GovernedBuildService` code path. The existing `/api/admin/datasets/
  builds` endpoints and `DatasetsPage`'s "Versions" tab keep behaving
  exactly as before Phase 7, confirmed by re-running their existing
  test suites unchanged after implementation.
- **Risk**: `RagIngestionService.create_source(source_type=
  'dataset_version', ...)` reads only `split='train'` items — a
  governed RAG-target build must ensure 100% of its eligible records
  land in the `train` split (RAG has no train/validation/test
  distinction), otherwise silently ingesting zero content.
  **Mitigation**: `GovernedBuildService` sets
  `split_configuration={train_percent:100,validation_percent:0,
  test_percent:0}` automatically for `rag`/`tokenizer`/`dataset_version`/
  `commercial_release`/`public_export` targets, and forces
  `test_percent:100` for `evaluation` — never left to the admin to
  misconfigure.

## 6. Frontend plan

New "Builds & Pipelines" page (`BuildsPipelinesPage.jsx`) inserted into
`Sidebar.jsx`/`App.jsx`/`helpRegistry.js` right after "Quality &
Approval", per Step 25's exact recommended ordering. 11 tabs per Step
26. Existing pages (`DatasetsPage`, `RagPage`, `CorpusPage`,
`PretrainingReadinessPage`, `ModelEvaluationPage`, `ModelRegistryPage`,
`DataOverviewPage`) get small, additive governance-context readouts
only — never restructured, never have their existing tabs removed or
renamed, matching Step 31's explicit instruction.

## 7. Explicitly deferred (this phase)

Automatic training/tokenizer-training/RAG-index-activation/model-release/
public-publishing, new training algorithms, semantic embedding
duplicate detection, AI-generated data, automatic translation/Tanglish
generation, Floating Admin Assistant, external legal review, web
crawling, automated permission acquisition — all per the task's
explicit out-of-scope list. Also deferred: an automatic bridge from a
governed evaluation-target dataset_version into
`model_evaluation_fixture_sets` (no existing bridge to reuse; inventing
one would be a second, competing evaluation-data system — flagged as
a real limitation, not silently worked around).
