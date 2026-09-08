# Phase 17.4 — Conflict Detection Boundary Report

## 1. Architectural Boundary
Phase 17.4 implements duplicate knowledge detection and semantic reinforcement.
It **DOES NOT** perform autonomous resolution of conflicting knowledge.

### Responsibilities Owned by Phase 17.4:
- Exact, normalized, and semantic similarity evaluation.
- Detection of numerical, interval, and parameter contradictions between semantically related claims.
- Classification of contradictory pairs as `POSSIBLE_CONFLICT`.
- Preservation of both existing and candidate memory records without destructive deletion or overwrite.
- Emission of structured conflict metadata (`review_required = True`).

### Responsibilities Owned by Phase 17.5 (Future):
- Deep semantic dispute resolution and arbitration.
- Human-in-the-loop conflict triage.
- Multi-source credibility weighting.
- Explicit retirement or superseding of outdated knowledge.

---

## 2. Parameter & Numerical Contradiction Guard

The engine extracts numerical tokens, intervals, and quantitative parameters (e.g., `24 hours` vs `12 hours`, `30 days` vs `7 days`):
```python
@staticmethod
def has_predicate_contradiction(text_a: str, text_b: str) -> bool:
    params_a = DuplicateKnowledgeEngine.extract_numbers_or_parameters(text_a)
    params_b = DuplicateKnowledgeEngine.extract_numbers_or_parameters(text_b)
    if params_a and params_b:
        if params_a != params_b:
            return True
    return False
```

When contradiction is detected:
- The candidate is classified as `POSSIBLE_CONFLICT`.
- Neither record is deleted or overwritten.
- `review_required` is set to `True`.

---

## 3. Verification Evidence
- `test_p17_4_dedup_006_possible_conflict_detection_not_merged`: **PASS**
- `test_p17_4_adversarial_002_high_similarity_contradictory_value`: **PASS**
