# Phase 17.6 — Performance & Resource Planning Report
**Brud Mini Brain: Storage Growth, Candidate Bounds & CPU Efficiency**

## 1. Storage & Growth Dynamics
Because the Brud Mini Brain architecture preserves immutable observation lineage, consolidation does NOT discard historical rows. Instead, it:
1. Promotes the canonical record to `status = 'active'`.
2. Demotes redundant constituent items to `status = 'consolidated'`.
3. Reduces active retrieval candidate set size from $O(N_{\text{observations}})$ to $O(N_{\text{canonical}})$.

### Retrieval Latency Impact:
- Without consolidation: Retrieval scans all historical observations ($N = 1000 \implies \approx 25\text{ ms}$).
- With consolidation: Retrieval scans only active canonical concepts ($N_{\text{canonical}} \approx 50 \implies \le 1.5\text{ ms}$).

---

## 2. Computational Bounds (CPU-First)
- **Clustering Scope**: Bound candidate pool per pass to `MAX_CONSOLIDATION_CANDIDATES = 20`.
- **Embedding Compute**: $20 \times 64$-dimensional vectors $\approx 0.8\text{ ms}$.
- **Clustering Latency Target**: $\le 5.0\text{ ms}$ per consolidation pass on local CPU.
- **Zero Heavy ML / GPU**: 0 MB extra model overhead (pure NumPy / Python).
