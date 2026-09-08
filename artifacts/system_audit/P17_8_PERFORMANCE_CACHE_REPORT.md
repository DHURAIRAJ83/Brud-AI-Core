# PHASE 17.8 — PERFORMANCE & CACHING ARCHITECTURE REPORT
# CPU-FIRST PERFORMANCE, BOUNDED COMPLEXITY & CACHING STRATEGY

**Document ID**: `P17_8_PERFORMANCE_CACHE_REPORT`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. CPU-First Performance Architecture

Brud Mini Brain memory recall is designed for ultra-low latency on standard commodity CPUs without requiring GPU acceleration or external vector databases.

### Computational Bounds:
1. **Candidate Set Upper Bound**: $N \le 100$ candidate memory items per participant scope in typical interactive sessions.
2. **Embedding Computation**: 64-dimensional character 3-gram hashing trick (`core_model.rag.embedding.compute_embedding()`) takes $< 0.05\text{ ms}$ on single-core CPU.
3. **Cosine Similarity Scoring**: Dot product over 64-dim float32 vectors takes $< 0.001\text{ ms}$ per candidate ($< 0.1\text{ ms}$ for 100 candidates).
4. **Keyword Scoring**: Set intersection over token sets takes $< 0.005\text{ ms}$.
5. **Combined Ranking & Sorting**: Python `list.sort()` over $\le 100$ elements takes $< 0.02\text{ ms}$.
6. **Total In-Memory Recall Latency Budget**: $< 2.0\text{ ms}$ on standard CPU.

---

## 2. Repeated Queries & Scope-Aware Caching Strategy

### Potential Risks of Uncontrolled Caching:
- Cross-tenant data leakage if cache keys omit `participant_scope_key`.
- Stale memory recall if cache fails to invalidate on memory updates, confirmations, or expirations.
- Memory leak if cache size is unbounded.

### Stage A Cache Design Specification (For Future Controlled Extension):
1. **Scope-Aware Cache Key**:
   $$\text{Key} = \text{SHA256}\left(\text{participant\_scope\_key} \parallel \text{retrieval\_mode} \parallel \text{sanitized\_query} \parallel \text{profile\_public\_id}\right)$$
2. **Bounded LRU**: Maximum 256 entries per tenant, total process memory bound $< 5\text{ MB}$.
3. **Cache TTL**: 30 seconds (short-lived for burst repeated queries).
4. **Invalidation Trigger**: Any mutation (`propose_memory`, `confirm_memory`, `expire_memory`, `consolidate_memories`, `unconsolidate_memory`) purges the participant's cache segment.
5. **Stage A Decision**: Caching is **specified as optional and isolated**. The core recall engine remains pure, stateless, and ultra-fast without mandatory caching dependencies.
