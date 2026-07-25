# Memory Versioning and Correction

Every memory item's actual value lives in append-only
`memory_item_versions` (`UNIQUE(memory_item_id, version_number)`), not
on `memory_items` itself. `memory_items.current_version_id` is the
only mutable pointer.

## Correction

`MemoryService.correct_memory()` never edits an existing version row —
it calls `_record_version()` to insert a new
`memory_item_versions` row with an incremented `version_number`, a
required `change_reason`, re-normalizes and re-embeds the new value,
and only then repoints `current_version_id`. The original version
remains exactly as first recorded, forever inspectable via `GET
.../memory-items/{id}/versions`.

Verified directly in manual verification Path F: after a correction,
the versions list grows by exactly one row, and the first version's
`display_value` is byte-for-byte unchanged from before the correction.

## Embeddings follow versions, not items

`_record_version()` also computes and stores an embedding for every
new version in append-only `memory_embeddings` (see
`docs/memory_retrieval_and_embeddings.md`) — so a correction produces
a new embedding alongside the new text, and retrieval against an old
query phrasing still resolves through the current version's vector,
never a stale one.

## Events

Every proposal, confirmation, rejection, correction, expiry, and
deletion also appends a row to append-only `memory_item_events`
(`event_type` + `details_json`, never raw content) — a full,
tamper-evident audit trail per memory item, inspectable via `GET
.../memory-items/{id}/events`.
