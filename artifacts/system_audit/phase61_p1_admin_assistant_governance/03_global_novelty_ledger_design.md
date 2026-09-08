# 03 GLOBAL NOVELTY LEDGER DESIGN

## Complete Lineage Architecture
`Source -> Book -> Page -> Record -> Canonical Content -> Lineage -> Token Accounting -> Dataset Version -> Approval`

- Database Table: `global_novelty_ledger` (Migration 077).
- Persistent fields: `record_public_id`, `source_id`, `book_id`, `page_id`, `record_id`, `content_sha256`, `normalized_content_sha256`, `lineage_id`, `parent_lineage_id`, `rights_status`, `domain`, `native_or_synthetic`, `token_count`, `native_token_count`, `synthetic_token_count`, `translated_token_count`, `derived_token_count`, `novelty_status`.
