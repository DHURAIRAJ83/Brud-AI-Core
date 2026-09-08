# PHASE 17.8 — RETRIEVAL PIPELINE & DATA FLOW
# END-TO-END RECALL ARCHITECTURE

**Document ID**: `P17_8_RETRIEVAL_PIPELINE`  
**Phase**: Phase 17.8 (Brud Mini Brain — Memory Recall & Retrieval Intelligence)  
**Status**: SPECIFICATION COMPLETE (STAGE A)  

---

## 1. End-to-End Retrieval Pipeline

The Phase 17.8 memory recall process follows a deterministic 12-stage cognitive pipeline:

```
[ Incoming Query + Context State ]
                 │
                 ▼
1. QUERY NORMALIZATION & SANITIZATION (G8)
   - Trim, lowercase, strip control chars
   - Redact detected secrets / tokens
   - Generate query embedding (64-dim n-gram hash)
                 │
                 ▼
2. PARTICIPANT SCOPE ISOLATION (G5)
   - Filter strictly by participant_scope_key
   - Cross-scope candidate injection rejected
                 │
                 ▼
3. RETRIEVAL MODE & STATUS FILTERING
   - CURRENT: status == 'active'
   - HISTORICAL: status in ('active', 'superseded', 'expired', 'archived')
   - Exclude 'deleted', 'revoked', 'quarantined', 'rejected'
                 │
                 ▼
4. CATEGORY & PURPOSE PROFILE CONFINEMENT
   - Filter against allowed_categories whitelist
   - Filter against allowed_purposes whitelist
   - Enforce G1 elevation check for SYSTEM / ADMIN
                 │
                 ▼
5. LEXICAL (KEYWORD) RELEVANCE COMPUTATION
   - Token overlap: len(Q_tokens ∩ M_tokens) / max(1, len(Q_tokens))
   - Substring exact-phrase boost (+0.1)
                 │
                 ▼
6. SEMANTIC (VECTOR) RELEVANCE COMPUTATION
   - Cosine similarity between query_vector and candidate_vector
   - Score bounded strictly to [0.0, 1.0]
                 │
                 ▼
7. TEMPORAL FRESHNESS & DECAY EVALUATION
   - Calculate memory age = max(0.0, now - created_epoch)
   - Map against category TTL: FRESH (0), AGING (5), STALE (15), EXPIRED (40)
   - Apply freshness penalty based on retrieval mode
                 │
                 ▼
8. CONTEXTUAL INTELLIGENCE BOOST (PHASE 17.2)
   - Topic match boost (+15.0 to +20.0) if active_topic matches content
   - Task match boost (+20.0 to +25.0) if active_task matches content
                 │
                 ▼
9. CONFLICT & DISPUTE SAFETY GATE (PHASE 17.5)
   - Check active dispute status (DETECTED, PENDING_REVIEW, UNDER_REVIEW)
   - If 'exclude_conflicting': exclude from accepted candidates
   - If 'prefer_recent' / 'prefer_user_confirmed': attach mandatory warning annotation
                 │
                 ▼
10. CONSOLIDATION DEDUPLICATION & DIVERSITY (PHASE 17.6)
    - If canonical memory accepted: suppress its constituent source IDs
    - If constituent memory accepted without canonical: retain individual record
                 │
                 ▼
11. DETERMINISTIC MULTI-SIGNAL RANKING & TIE-BREAKING
    - Compute unified bounded rank score (0.0 – 100.0)
    - Tie-break: (-score, -confidence, -importance, public_id ASC)
                 │
                 ▼
12. BUDGET BOUNDING, CITATION & AUDIT LOGGING
    - Enforce maximum_results (default 10)
    - Enforce maximum_memory_tokens (default 600 tokens)
    - Assemble provenance citations (public_ids, versions, timestamps)
    - Record immutable audit run in memory_retrieval_runs / memory_retrieval_results
```

---

## 2. Stage Breakdown & Boundaries

### Stage 1: Query Normalization & Sanitization (G8)
- Input: `raw_query: str`
- Operation: Call `sanitize_message(raw_query)`. Remove leading/trailing whitespace. Compute 64-dimensional character 3-gram embedding vector using `core_model.rag.embedding.compute_embedding()`.
- Output: `sanitized_query: str`, `query_tokens: set[str]`, `query_vector: np.ndarray`.

### Stage 2: Scope Isolation (G5)
- Input: `participant_scope_key: str`, `candidates: list[dict]`
- Operation: Strict check `candidate["participant_scope_key"] == participant_scope_key`.
- Invariant: Zero cross-tenant candidate passing.

### Stage 3: Retrieval Mode & Status Eligibility
- Policy:
  - `CURRENT`: Must be `active`.
  - `HISTORICAL`: Can be `active`, `superseded`, `expired`, `archived`.
  - Disallowed: `deleted`, `revoked`, `quarantined`, `rejected`, `proposed`, `awaiting_confirmation` (unless explicitly confirmed).

### Stage 4: Governance & Whitelist Confinement (G1)
- Whitelists: `allowed_categories`, `allowed_purposes`.
- SYSTEM / ADMIN: Must have `status == 'active'` and explicit authorization before being returned.

### Stage 5 & 6: Lexical & Semantic Relevance
- Keyword Score: $S_{\text{keyword}} = \min\left(1.0, \frac{|T_Q \cap T_M|}{|T_Q|}\right) \in [0.0, 1.0]$.
- Vector Score: $S_{\text{vector}} = \max\left(0.0, \frac{\mathbf{v}_Q \cdot \mathbf{v}_M}{\|\mathbf{v}_Q\| \|\mathbf{v}_M\|}\right) \in [0.0, 1.0]$.

### Stage 7: Freshness Decay Evaluation (Phase 17.7)
- Age calculated via `MemoryLifecycleEngine.compute_memory_age()`.
- Freshness state mapped to penalty $P_{\text{freshness}} \in \{0.0, 5.0, 15.0, 40.0\}$.

### Stage 8: Context Intelligence Boost (Phase 17.2)
- Topic boost: $\Delta_{\text{topic}} = +20.0$ if active topic tokens present.
- Task boost: $\Delta_{\text{task}} = +25.0$ if active task tokens present.

### Stage 9: Dispute Gate (Phase 17.5)
- If memory has active dispute:
  - Policy `exclude_conflicting`: Move candidate to `excluded` with reason `disputed_memory_pending_resolution`.
  - Policy `prefer_recent` / `prefer_user_confirmed`: Apply conflict penalty $P_{\text{conflict}} = 20.0$ and attach `dispute_warning`.

### Stage 10: Consolidation Lineage & Deduplication (Phase 17.6)
- Maintain set of constituent source IDs: `suppressed_source_ids = set()`.
- For each accepted canonical memory, add all its `source_references` to `suppressed_source_ids`.
- Filter out candidates whose `public_id` is in `suppressed_source_ids`.

### Stage 11: Unified Score Ranking
- Formula:
  $$\text{effective\_recall\_score} = \text{clamp}\Big(0.0, 100.0, (w_v \cdot S_{\text{vector}} \times 40) + (w_k \cdot S_{\text{keyword}} \times 30) + (0.2 \times \text{importance}) + (0.1 \times \text{confidence}) + \Delta_{\text{topic}} + \Delta_{\text{task}} - P_{\text{freshness}} - P_{\text{conflict}}\Big)$$
- Deterministic sort key: `(-effective_recall_score, -confidence_score, -importance_score, public_id)`

### Stage 12: Token & Result Budget Assembly
- Max Results: $\le \min(\text{maximum\_results}, 10)$
- Max Tokens: $\le \min(\text{maximum\_memory\_tokens}, 600)$
- Emits structured results with provenance links, checksums, and exclusion audit logs.
