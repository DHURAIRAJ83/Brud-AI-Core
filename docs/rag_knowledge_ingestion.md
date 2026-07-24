# RAG Knowledge Ingestion

## Source types

`dataset_version`, `pdf_document`, `plain_text`, `markdown`,
`html_snapshot`, `manual_admin_content`, `course_material`, `faq`.

`dataset_version` and `pdf_document` are registry-backed: creating one
requires an existing `source_entity_public_id` (a real
`dataset_versions.public_id` or `document_sources.public_id`), verified
to exist before the source is created. The other six are inline-content
types: their text is supplied directly at creation time, staged
temporarily in `metadata_json["_staged_content"]` (bounded by
`BRUD_RAG_MAX_SOURCE_CHARACTERS`), and consumed into a real
`rag_source_versions.raw_content` row the first time a version is
created.

## Content resolution

- `dataset_version` sources read real `dataset_records.content` via
  `dataset_version_items` joined on `split='train'` only — validation
  and test splits are deliberately excluded from RAG knowledge content,
  documented as an interpretation choice (no train/test mixing).
- `pdf_document` sources read real `document_pages.cleaned_text`
  (falling back to `raw_text`), ordered by `page_number`, with a
  `## Page {N}` markdown header inserted between pages so the
  heading-aware chunker creates one natural boundary per PDF page.

## Approval workflow

`approval_status` starts `draft` and moves through
`review_required → approved / rejected / quarantined → archived`. Only
`approved` sources' chunks are eligible for embedding and keyword
indexing (see `docs/rag_chunking.md`) — unapproved, rejected, or
quarantined sources structurally can never enter an active index; their
chunks are marked `quality_status='rejected'` with issue
`source_not_approved` at chunk-creation time, and an embedding run over
them always reports zero eligible chunks. Attempting to build a vector
index from zero embeddings fails closed with an explicit error rather
than producing an empty active index.

## Source versions are immutable

A new content checksum always creates a new `rag_source_versions` row;
`create_source_version` rejects the call outright if the computed
checksum matches the latest existing version's checksum ("content is
unchanged since the latest source version"). The previous `ready`
version is marked `superseded`, never deleted or overwritten — historical
answer lineage always resolves to a real, immutable version row.

## Licence and language

`licence_status` (`unknown`/`open`/`restricted`/`blocked`) is checked
independently of approval — a `blocked` licence always excludes a
source from retrieval regardless of any other filter. Language is
classified via `core_model.rag.language_routing.classify_language()` on
the first 5000 normalized characters at version-creation time (reusing
`core_model.instruction_tuning.language_checks.script_ratios`, not a
new script-ratio implementation).
