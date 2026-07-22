# Database schema v4

Migration `004_phase4_dataset_import` is additive. It preserves every Phase 1–3 table and adds three import-control tables.

- `dataset_import_jobs` registers sanitized upload metadata, server-only artifact identity, checksum, mapping/options, lifecycle state, counts, creator public ID, and timestamps.
- `dataset_import_rows` stores bounded raw/normalized preview JSON, canonical record fields, structured issues, duplicate public references, and imported record public references. Row number is unique within a job.
- `dataset_import_events` is append-only lifecycle history linked to its job by an enforced foreign key.

Indexes cover job status/creation time and row status/number/content hash/duplicate references. Numeric IDs are internal only. API relationships use UUID public IDs. Import events are protected from update and delete by database triggers.

Import statuses are uploaded, parsing, preview-ready, confirmed/importing, terminal completion, failed, cancelled, or expired. Completed/cancelled jobs cannot be reconfirmed; imported rows cannot be reinserted. Dataset records created by imports remain ordinary Phase 3 draft records and follow the same review lifecycle.
