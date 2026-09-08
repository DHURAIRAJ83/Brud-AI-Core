# Phase 17.9: Evidence Aggregation Specification

## 1. Objective
Define deterministic principles for aggregating multi-memory evidence sets without violating **G4 (Retrieval $\neq$ Evidence)**.

---

## 2. Invariant Boundary: Evidence Aggregation vs Retrieval
```
[User Observation / Insertion Time]
     ↓
Evidence Ingestion / Reinforcement
(Increments evidence_count, modifies confidence)
-------------------------------------------------------------
[Query / Recall Planning Time]
     ↓
MemoryReasoningEngine Evidence Aggregation
(READ-ONLY grouping, synthesis, confidence scoring of context)
(NEVER modifies database evidence_count or confidence_score)
```

---

## 3. Evidence Grouping Policy
1. **Corroborating Memory Cluster**:
   - Memories with pairwise similarity $S_{\text{vec}} \ge 0.75$ and non-conflicting values are grouped into an `EvidenceCluster`.
   - Aggregate cluster confidence is computed as:
     $$\text{Conf}_{\text{cluster}} = 100.0 \times \left(1.0 - \prod_{m \in \text{Cluster}} \left(1.0 - \frac{m.\text{confidence}}{100.0}\right)\right)$$
     (bounded strictly to $[0.0, 100.0]$).
2. **Conflicting Evidence Partition**:
   - If memories within a cluster share a contradictory predicate (as evaluated by `ConflictKnowledgeEngine`), the cluster is split into affirmative and contested branches.
   - The aggregated confidence of the contested branch is penalized by $0.5 \times \text{DisputeSeverity}$.
3. **Source Diversity Weighting**:
   - An evidence set corroborated by multiple distinct creation sources (e.g. `explicit_user_request` + `system_derived`) is assigned a diversity bonus in reasoning priority.
