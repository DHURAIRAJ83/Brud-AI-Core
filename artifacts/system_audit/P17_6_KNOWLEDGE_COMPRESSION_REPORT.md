# Phase 17.6 — Knowledge Compression Report
**Brud Mini Brain: Deterministic Structural Compression & Information Preservation**

## 1. Compression Paradigm
Knowledge compression in Brud Mini Brain is **deterministic structural compression**, NOT unconstrained generative LLM summarization.

### Why Generative "Summarize & Delete" is Forbidden:
1. Generative LLMs can hallucinate non-existent details or omit critical parameters (e.g. turning "24 hours" into "regularly").
2. Destructive deletion breaks provenance chains and prevents auditing.
3. Information loss becomes irreversible.

---

## 2. Information Preservation Boundaries

| Information Dimension | Preservation Strategy | Loss Risk | Mitigation Mechanism |
|:---|:---|:---:|:---|
| **Dates & Timestamps** | Retained in `valid_from`, `valid_until`, `created_at` | Zero | Explicit temporal range tracking |
| **Quantities & Units** | Extracted scalars (e.g., `24 hours`, `1024 MB`) preserved in canonical claim | Low | Numeric consistency check before merge |
| **Conditions & Exceptions** | Preserved in structural qualifiers | Low | Separate items if condition differs |
| **Provenance References** | Aggregated list of source public IDs stored in `compression_state` | Zero | Direct database foreign/reference keys |
| **Evidence Count** | $\text{total\_evidence} = \sum \text{evidence\_count}$ | Zero | Exact integer summation |
| **Confidence Score** | $\min(100.0, \max(\text{confidences}) + \Delta_{\text{evidence}})$ | Zero | Calibrated bounded score |
| **Conflict & Dispute State** | Preserved in event ledger; blocked from merging if disputed | Zero | Conflict gate check |
| **User/Admin Confirmation** | Retained in canonical metadata | Zero | Elevation if any constituent is confirmed |

---

## 3. Structural Compression Mathematics

1. **Evidence Aggregation**:
   $$\text{evidence\_count}_{\text{canonical}} = \sum_{i=1}^N \text{evidence\_count}(M_i)$$

2. **Confidence Computation**:
   $$\text{confidence\_score}_{\text{canonical}} = \min\left(100.0, \max_{i} (\text{confidence\_score}(M_i)) + \min(10.0, (N - 1) \times 2.0)\right)$$

3. **Importance Computation**:
   $$\text{importance\_score}_{\text{canonical}} = \max_{i} (\text{importance\_score}(M_i))$$

4. **Canonical Claim Selection**:
   Deterministic selection using multi-factor criteria:
   - Rank 1: Confirmed status (`status == 'active'` or `user_confirmed`)
   - Rank 2: Highest confidence score
   - Rank 3: Highest importance score
   - Rank 4: Highest evidence count
   - Rank 5: Earliest creation timestamp / ID tie-breaker
