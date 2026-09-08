# Phase 17.4 — Canonical Memory Selection Report

## 1. Objective & Design
When a memory candidate is classified as `EXACT_DUPLICATE`, `NORMALIZED_DUPLICATE`, or `SEMANTIC_DUPLICATE`, rather than creating redundant database rows or overwriting valid historical records, the engine deterministically elects the single authoritative canonical record.

---

## 2. Deterministic Ranking Algorithm

The selection algorithm evaluates items in strict deterministic priority:
1. **Confidence Score** (higher is preferred; range `0.0 - 100.0`, with user-confirmed facts ranking highest).
2. **Importance Score** (higher is preferred; range `0.0 - 100.0`).
3. **Evidence Count** (higher is preferred; accumulated support from previous observations).
4. **Record Stability / Age** (existing persisted record preferred over candidate to prevent churn).
5. **Deterministic ID Tie-Break** (lexicographic tie-breaker on `public_id`).

```python
score_existing = (
    float(existing_item.get("confidence_score", 50.0)),
    float(existing_item.get("importance_score", 50.0)),
    int(existing_item.get("evidence_count", 1)),
    1,  # Existing record preferred for stability
    str(existing_item.get("public_id", "")),
)
```

---

## 3. Evidence Accumulation & Reinforcement
Upon semantic duplicate detection:
- **No new memory row is created.**
- The canonical memory's `evidence_count` increases by the candidate's `evidence_count`:
  $$\text{evidence\_count}_{\text{new}} = \text{evidence\_count}_{\text{canonical}} + \text{evidence\_count}_{\text{candidate}}$$
- An immutable `SEMANTIC_REINFORCED` event is recorded with sanitized provenance details (`similarity_score`, `total_evidence_count`, `canonical_public_id`).

---

## 4. Verification
- Deterministic canonical selection: **VERIFIED** (`test_p17_4_canon_001_deterministic_canonical_selection`)
- Deterministic tie-break: **VERIFIED** (`test_p17_4_canon_002_deterministic_tie_break_with_identical_scores`)
- Evidence accumulation: **VERIFIED** (`test_p17_4_adversarial_005_repeated_semantic_duplicate_accumulates_evidence`)
