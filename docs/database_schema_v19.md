# Database Schema v19 — Tamil Corpus Builder

Migration `019_phase19_tamil_corpus_builder`, schema version 18 → 19,
independent of migration 018 (verified directly:
`test_migration_018_is_unchanged_in_isolation`). Adds 34 tables: 14
mutable, 20 append-only.

## Tables

Mutable (14):

- `corpus_policies` — per-corpus requirement flags (verified origin,
  licence review, privacy/safety scan, quality assessment,
  deduplication, contamination check), size/segment bounds.
  `lifecycle_status` CHECK `draft|validated|active|deprecated|archived`.
- `corpus_source_registries` — one row per provenance-tracked source.
  `source_type` CHECK 17 values, `status` CHECK 9 values
  (`draft|origin_review|licence_review|approved|approved_with_restrictions|rejected|quarantined|disputed|archived`).
  Deliberately has **no** `licence_id` column — see "Circular-FK
  avoidance" below.
- `corpus_source_licences` — `licence_family` CHECK 12 values,
  `review_status` CHECK 8 values
  (`approved|approved_with_conditions|restricted|unknown|blocked|disputed|expired|not_applicable`).
  One-directional `source_id -> corpus_source_registries.id` only.
- `corpus_source_snapshots` — `status` CHECK
  `creating|ready|failed|superseded|archived`, `UNIQUE(source_id, version_number)`.
- `corpus_source_files` — registered file inventory per snapshot;
  `safe_relative_storage_key` is always a validated, approved-root-relative
  path, never an arbitrary filesystem path.
- `corpus_extraction_runs`, `corpus_normalization_runs`,
  `corpus_deduplication_runs`, `corpus_contamination_runs`,
  `corpus_exports` — the two-phase create-then-execute pattern already
  established by Phase 16/17/18's own analogous run tables; **this
  phase's own spec already pre-classifies these as mutable**, so no
  literal-reading deviation was needed here (see design comment in
  `schema.py`).
- `corpus_collections` — `lifecycle_status` CHECK
  `draft|validated|active|deprecated|archived`.
- `corpus_balance_policies` — per-category target shares plus
  `maximum_single_source_share`.
- `corpus_builds` — `status` CHECK 9 values
  (`draft|validating|ready|building|completed|completed_with_warnings|failed|cancelled|archived`).
- `corpus_versions` — `status` CHECK
  `draft|validating|ready|deprecated|retired|archived`, `UNIQUE(semantic_version)`.
  A correction is always a brand-new `semantic_version` row (matching
  the "immutable content, mutable lifecycle column" convention already
  used for `dataset_versions` since Phase 6); the row itself carries no
  append-only trigger since its lifecycle column must transition after
  creation.

Append-only (20): `corpus_extracted_documents`, `corpus_normalized_documents`,
`corpus_segments`, `corpus_segment_locations`, `corpus_language_assessments`,
`corpus_domain_assessments`, `corpus_style_assessments`,
`corpus_quality_assessments`, `corpus_quality_issues`,
`corpus_privacy_findings`, `corpus_safety_findings`,
`corpus_duplicate_clusters`, `corpus_duplicate_members`,
`corpus_contamination_findings`, `corpus_collection_members`,
`corpus_build_members`, `corpus_partitions`, `corpus_export_shards`,
`corpus_manifests`, `corpus_comparisons`.

## Circular-FK avoidance

`corpus_source_registries` and `corpus_source_licences` have a genuine
mutual-reference need: a source's "current licence" would naturally
want to point at its latest licence row, while every licence row must
always point back at the source it reviews. Rather than a nullable
`licence_id` column on the source row (updated after the fact, and
therefore not append-only-safe), `corpus_source_licences.source_id ->
corpus_source_registries.id` is the only stored direction. The
"current" licence for a source is always resolved by querying the
latest `corpus_source_licences` row for that source
(`CorpusRepository.latest_licence_for_source`) — the same
circular-FK-avoidance reasoning Phase 17 used for
`participant_scope_key`.

## Polymorphic quality/privacy/safety subjects

`corpus_quality_assessments` uses `subject_type` (`source|document|
segment|collection|build`) + `subject_reference_public_id` rather than
five sets of mostly-null FK columns — the same pattern Phase 18 used
for `feedback_subjects`. `corpus_privacy_findings` and
`corpus_safety_findings` use a nullable `segment_id` FK directly, since
in practice every finding recorded by this phase's services is
segment-scoped.

## Approved-root path enforcement

No API or CLI command ever accepts an arbitrary filesystem path.
`corpus_source_files.safe_relative_storage_key` is always resolved and
validated against `Settings.corpus_approved_roots` (the registered
upload directory plus any admin-configured additional roots) before
being read; `CorpusSourceService.resolve_approved_path` rejects `..`
segments, absolute paths, and anything outside every approved root —
verified directly in `test_corpus_api.py::test_snapshot_rejects_path_outside_approved_roots`
and manual verification Path C.

## Real dev DB upgrade

```
python -m backend.database.migrations upgrade
schema_version: 19
integrity_check: ok
```

Post-upgrade: `PRAGMA user_version` = 19, `PRAGMA integrity_check` =
`ok`, `PRAGMA foreign_key_check` = 0 rows, 34 `corpus_%` tables
present. A checksum-verified pre-migration backup was created
automatically (`brud_ai_before_v19_*.db`).
