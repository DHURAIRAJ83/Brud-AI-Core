# Keyword Index (FTS5)

`rag_keyword_indexes.index_type` is `fts5`. Each build creates a
dynamically-named virtual table
(`rag_fts_{public_id with dashes replaced by underscores}`) containing
`(chunk_public_id UNINDEXED, body)`, populated only with eligible chunks
(accepted + clean — see `docs/rag_chunking.md`).

## Known limitation (documented, not hidden)

FTS5's built-in `unicode61` tokenizer segments on Unicode word-boundary
heuristics; it does not perform true Tamil morphological segmentation,
so compound Tamil words are indexed as single whitespace-delimited
tokens rather than meaningful sub-parts. `core_model.rag.keyword_index.
KNOWN_LIMITATIONS` states this explicitly, and it is surfaced in the
admin dashboard's Keyword Indexes tab.

## Two real bugs found and fixed during implementation

1. **Tamil combining-mark shredding.** Python's `\w` regex excludes
   Unicode combining marks (categories Mn/Mc), which silently shredded
   every Tamil word at its vowel signs and virama — `"தமிழ்"` tokenized
   under naive `r"\w+"` as `["தம", "ி", "ழ", "்"]`. Fixed by widening
   `_WORD_PATTERN` to `r"[\w஀-௿]+"`, explicitly including the Tamil
   Unicode block (U+0B80-U+0BFF). Verified directly: `"தமிழ் new year
   2026 புத்தாண்டு"` now tokenizes to
   `['தமிழ்', 'new', 'year', '2026', 'புத்தாண்டு']`.
2. **Inverted `bm25()` sign convention.** SQLite's `bm25()` returns a
   *negative*, unbounded value where more negative means a stronger
   match — verified directly against a live FTS5 table, not assumed.
   `keyword_match_score()` originally assumed a positive
   "lower is better" convention
   (`1.0 / (1.0 + max(0.0, bm25_score))`), which clamps every real
   (negative) score to the same output regardless of match quality.
   Fixed to `magnitude = abs(bm25_score); return magnitude / (1.0 +
   magnitude)`; re-verified monotonic and correctly ordered.

## Query construction

`escape_fts5_query()` builds a safe, deterministic OR-of-quoted-tokens
query from tokenized input rather than passing raw user text to `MATCH`
unescaped. A malformed or empty query fails closed (empty keyword
candidate list), never crashes retrieval.
