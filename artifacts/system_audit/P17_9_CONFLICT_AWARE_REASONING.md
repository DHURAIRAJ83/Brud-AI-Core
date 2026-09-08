# Phase 17.9: Contradiction-Aware Reasoning Specification

## 1. Objective
Ensure memory reasoning safely handles active disputes and contradictory observations without collapsing contested facts into false certainty or inventing ground truth.

---

## 2. Epistemic Partitioning Framework
When assembling memories for reasoning, the engine classifies facts into 5 mutually exclusive epistemic categories:

1. **`FACT_CURRENT`**: Uncontested, active memory reflecting current reality.
2. **`FACT_HISTORICAL`**: Uncontested historical observation preserving past reality.
3. **`FACT_CONTESTED`**: Observation associated with an open dispute (`DETECTED`, `PENDING_REVIEW`, `UNDER_REVIEW`).
4. **`FACT_SUPERSEDED`**: Observation replaced by an explicitly confirmed newer fact.
5. **`FACT_UNKNOWN / GAPPED`**: Missing required knowledge where evidence is inconclusive.

---

## 3. Dispute Policy Alignment
- **`exclude_conflicting`**: Contested facts (`FACT_CONTESTED`) are excluded from the main reasoning packet to guarantee zero disputed claims enter context.
- **`prefer_recent`**: Contested facts are included but segregated into an explicit `[Disputed / Contested Claims]` block with advisory warnings and dispute IDs.
- **Governance Gate**: Active disputes block automatic promotion or autonomous truth selection.
