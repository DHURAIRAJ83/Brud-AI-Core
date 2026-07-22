# Database schema v5

Migration `005_phase5_document_processing` is additive and preserves schemas 1–4. It adds `document_sources`, `document_pages`, `document_processing_jobs`, `document_processing_events`, and `document_candidates`. Numeric IDs remain internal; public UUIDs are used by APIs. Page and candidate provenance is retained through document public IDs and page ranges. Events are append-only and records are created only after explicit candidate confirmation.
