# Brud AI Database Schema v6

Schema v6 is additive on top of schema v5. It preserves manual records, file imports, document extraction provenance, authentication, audit logs, and all prior API behavior.

## New tables

- `dataset_quality_assessments`: immutable history of deterministic quality assessments per dataset record.
- `dataset_quality_issues`: explainable issue rows for each assessment.
- `dataset_build_jobs`: one bounded dataset-version build request and its counters.
- `dataset_build_events`: append-only lifecycle events for builds.
- `dataset_exports`: metadata for server-generated dataset exports.

## Extended tables

`dataset_versions` gains `quality_summary_json`, `source_distribution_json`, `record_type_distribution_json`, `build_configuration_json`, `parent_dataset_version_id`, and `export_status`.

Ready dataset versions remain immutable through existing triggers on version content and items.

## Relationships

- Quality assessments reference `dataset_records`.
- Quality issues reference quality assessments.
- Build jobs reference `dataset_versions`.
- Build events reference build jobs.
- Exports reference dataset versions.
- Version items continue to reference approved dataset records.

## Guarantees

- Numeric database IDs are internal only.
- Public APIs use `public_id`.
- Quality issues and build events are append-only.
- Only approved records may enter a ready dataset version.
- Export metadata stores safe names, checksums, and file manifests, not private paths.
