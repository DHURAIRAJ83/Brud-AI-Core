# Phase 16 Settings

All new settings are `BRUD_RAG_*` environment variables (see
`backend/core/config.py`), safe by default:

| Setting | Default | Purpose |
|---|---|---|
| `rag_enabled` | `True` | Master feature flag for the RAG subsystem. |
| `rag_max_source_characters` | 2,000,000 | Bound on inline source content size. |
| `rag_target_chunk_tokens` / `rag_max_chunk_tokens` | 350 / 500 | Default chunking targets. |
| `rag_chunk_overlap_tokens` | 50 | Sliding-window overlap for token-window chunking. |
| `rag_min_chunk_characters` | 40 | Minimum viable chunk size. |
| `rag_max_chunks_per_source` | 2000 | Hard cap; chunking fails closed above this. |
| `rag_embedding_batch_size` | 16 | Embedding-run batching (not currently parallelized). |
| `rag_max_active_embedding_runs` | 1 | Reserved for future concurrency limits. |
| `rag_max_vector_results` / `rag_max_keyword_results` | 20 / 20 | Per-index candidate pool size. |
| `rag_max_final_results` | 5 | Default `final_top_k`. |
| `rag_default_vector_weight` / `rag_default_keyword_weight` | 0.6 / 0.4 | Default hybrid weights (must sum to 1.0). |
| `rag_min_retrieval_score` | 0.15 | Default `minimum_score` floor. |
| `rag_context_token_budget` | 800 | Default retrieval-profile context budget. |
| `rag_max_citations` | 5 | Citation-count-exceeded threshold. |
| `rag_no_answer_threshold` | 0.2 | Default no-answer score threshold. |
| `rag_block_injection_risk` | `True` | Block (vs. quarantine) injection-flagged chunks. |
| `rag_allow_warning_chunks` | `False` | Whether `accepted_with_warning` chunks are index-eligible. |
| `rag_max_active_sessions` / `rag_max_session_turns` / `rag_session_ttl_seconds` | 5 / 10 / 3600 | RAG Chat Lab bounds. |
| `rag_require_approved_sources` | `True` | Hard-require source approval for retrieval eligibility. |
| `rag_allowed_index_roots` | `"rag_indexes"` | Reserved path-confinement root(s) for any future on-disk index artifact. |

No setting defaults to a value that would enable public RAG activation
or automatic ingestion of unapproved content — every default is the
conservative, fail-closed choice.
