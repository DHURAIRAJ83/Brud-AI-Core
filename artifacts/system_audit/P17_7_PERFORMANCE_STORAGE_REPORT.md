# Phase 17.7 — Performance & Storage Growth Report
**Brud Mini Brain: Computational Bounds & Non-Destructive Storage Planning**

## 1. Computational Strategy (CPU-First)
Phase 17.7 employs a **Hybrid Execution Model**:
1. **On-Read Dynamic Evaluation**:
   - Freshness penalty and decay are computed dynamically during retrieval ranking in $\le 0.05\text{ ms}$ per candidate.
   - Zero database write overhead on pure reads.
2. **On-Write Reinforcement**:
   - Deduplicated observations trigger immediate timestamp and evidence count updates within the proposal transaction ($\le 1.0\text{ ms}$).
3. **Scheduled Maintenance Sweep**:
   - Periodic background sweep (e.g. hourly or daily) queries `status = 'active'` items past TTL and transitions them to `expired` or `archived` in batches of 50.

### Performance Targets (CPU-First):
- **Candidate Freshness Evaluation**: $\le 0.1\text{ ms}$ per candidate (Target).
- **Batch Expiration Sweep (50 items)**: $\le 5.0\text{ ms}$ total execution (Target).
- **Zero Heavy ML**: 0 MB extra RAM / 0% GPU load.

---

## 2. Storage Growth Dynamics
Because Brud Mini Brain enforces non-destructive storage:
- **Active Records**: Kept compact via Phase 17.6 Consolidation ($O(N_{\text{canonical}})$ active rows).
- **Expired & Archived Records**: Remain stored in SQLite WAL, indexed by `status`, `participant_scope_key`, and `created_at`.
- **Database Index Optimization**: Existing index on `(participant_scope_key, status)` ensures retrieval queries (`WHERE status='active'`) scan only active records, completely ignoring expired/archived rows with $O(1)$ index lookup.
- **Estimated Row Size**: Each lifecycle transition adds one lightweight JSON row to `memory_item_events` ($\approx 250\text{ bytes}$), providing complete auditability at negligible disk footprint.
