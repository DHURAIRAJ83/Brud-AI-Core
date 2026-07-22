# Dataset management

Phase 3 implements manual data curation. Phase 4 adds preview-first JSON, JSONL, CSV, and TXT imports. Phase 5 adds PDF document extraction. Phase 6 adds deterministic quality assessment, immutable dataset version building, and JSONL export. Remote URL imports, tokenizer training, model training, and inference remain unavailable.

## Sources

The admin UI and API create `manual` sources only. Names are normalized and length-bounded; language, licence state, metadata size, and source state are validated. Sources are addressed by UUID public IDs and may be searched, filtered, paginated, and updated. There is no physical-delete endpoint.

## Record types and required fields

- `pretrain`: one main content value in `input_text` or `output_text`; Phase 3 recommends `output_text`.
- `instruction`: `instruction` and `output_text`; `input_text` is optional.
- `chat`, `safety`, and `preference`: `input_text` and `output_text`.
- `translation`: `input_text`, `output_text`, and source/target language metadata.
- `tanglish_pair`: `input_text`, `normalized_input`, and `output_text`.

Preference records currently support only one stored response, not chosen/rejected pairs. All text and metadata fields have request limits.

## Lifecycle and reviews

Allowed transitions are draft to pending review/archive; pending review to approved/rejected/draft/archive; approved to archived; rejected to draft/archive; and archived to draft. Approved records cannot be edited. Change them by archiving and creating a replacement draft.

Submitting records and reviewer actions are transactional. Reject and request-changes actions require comments. The authenticated admin public ID is recorded as reviewer. Review rows are append-only through repository behavior and database triggers. Archive is always a soft delete; restore returns a record to draft.

## Duplicate handling

A deterministic SHA-256 hash covers record type, language, instruction, input, output, and normalized input. Text is Unicode NFC-normalized and whitespace-normalized; English and Tanglish are safely case-folded while Tamil is not lower-cased. A conflicting create/update returns 409 with the existing record's public ID. Conflicts are audited and shown in the Duplicates tab; records are never merged or deleted automatically.

## Audit guarantees

Source and record creation/update, submit, review decisions, archive/restore, duplicates, and meaningful validation failures create bounded audit summaries. Audits identify public IDs and actions but omit full payloads, text bodies, passwords, tokens, hashes, and paths.

Imported records pass the same `validate_record` and deterministic `content_hash` logic as manual records and always begin as drafts. Invalid rows remain preview/report evidence; duplicates remain visible and are either confirmation blockers (`create_only`) or explicit skips (`skip_duplicates`). See [dataset_imports.md](dataset_imports.md).

## Quality and versions

Phase 6 quality assessments create separate immutable evidence and issue rows; they do not edit records. Blocked-quality records cannot be approved through the normal review action. Dataset builds select approved records, generate deterministic grouped splits, create immutable ready versions, and export UTF-8 JSONL files. See [dataset_quality.md](dataset_quality.md), [dataset_versioning.md](dataset_versioning.md), [dataset_splitting.md](dataset_splitting.md), and [dataset_export.md](dataset_export.md).
