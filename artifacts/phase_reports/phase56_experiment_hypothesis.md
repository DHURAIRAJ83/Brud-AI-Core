# Phase 56 Experiment Hypothesis

**Workstream:** 5 — Experimental Hypothesis  
**Timestamp:** 2026-08-30T15:55:00Z

---

## 1. Scientific Context

Phase 55 produced a qualified 10K+ sovereign corpus (15,162 unique approved tokens, 396 records). Training was deliberately NOT executed in Phase 55. Phase 56 is the first controlled training experiment using this corpus.

The baseline model (Phase 53 checkpoint) demonstrates **0.0% capability** on the frozen 32-probe evaluation manifest. The central scientific question is: **does training on the Phase 55 sovereign corpus produce measurable, reproducible, generalizable capability improvement?**

---

## 2. Formal Hypotheses

### Null Hypothesis (H0)
> **H0:** Training on the Phase 55 sovereign corpus produces no statistically meaningful improvement in keyword-hit capability across the frozen 32-probe evaluation set compared to the pre-training baseline.

**H0 is accepted (not rejected) unless the evidence meets all primary endpoint criteria.**

### Alternative Hypothesis (H1)
> **H1:** Training on the Phase 55 sovereign corpus produces a statistically meaningful, reproducible improvement in keyword-hit capability across the frozen 32-probe evaluation set, without unacceptable memorization, generalization degradation, or OOD performance collapse.

**H0 and H1 are evaluated neutrally. Scientific honesty takes precedence over a positive result.**

---

## 3. Endpoints

### 3.1 Primary Endpoint

**Primary endpoint:** Change in keyword-hit score on the frozen 32-probe evaluation manifest.

$$\Delta_{\text{primary}} = \text{Score}(B) - \text{Score}(A)$$

Where:
- `A` = Frozen baseline (Phase 53 checkpoint, step 3154) = **0/32 = 0.0%**
- `B` = Phase 56 trained candidate (post-training checkpoint)

---

### 3.2 Secondary Endpoints

| ID | Endpoint | Measurement |
|----|----------|-------------|
| SE-01 | Tamil-specific capability | Δ in Tamil cluster keyword hits (5 probes) |
| SE-02 | English-specific capability | Δ in English cluster keyword hits (4 probes) |
| SE-03 | Tanglish capability | Δ in Tanglish cluster keyword hits (3 probes) |
| SE-04 | Reasoning/Mathematics | Δ in reasoning cluster keyword hits (6 probes) |
| SE-05 | Grounding | Δ in grounding cluster keyword hits (4 probes) |
| SE-06 | Adversarial robustness | Δ in adversarial cluster keyword hits (5 probes) |
| SE-07 | Generative coherence | Δ in generative cluster keyword hits (5 probes) |
| SE-08 | Seen/held-out/OOD preservation | Δ per probe type |
| SE-09 | Train loss trajectory | Does loss decrease monotonically? |
| SE-10 | Validation loss trajectory | Does val loss remain coupled to train loss? |
| SE-11 | Gain per 1,000 exposure tokens | Efficiency of capability gain |
| SE-12 | Repetition rate | Does post-training repetition decrease? |
| SE-13 | Generation latency | Δ latency in ms/probe |

---

## 4. Success Criteria and Thresholds

### 4.1 Minimum Meaningful Capability Delta

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Minimum Δ(primary) to reject H0 | **≥ 3/32 probes (9.4%)** | At least 3 additional probes must pass keywords |
| Minimum Δ per cluster | ≥ 1 probe | Each cluster must show non-zero improvement |
| Minimum OOD improvement | ≥ 1/18 | At least 1 OOD probe must pass |

### 4.2 Statistical Significance Criterion

Due to the small evaluation set (32 probes) and deterministic greedy decoding:
- Evaluation is repeated 3 times with identical conditions to confirm determinism
- A result is considered stable if all 3 repetitions produce the same score
- Bootstrap significance is not computed (deterministic evaluation)
- A single post-training gain ≥ 3/32 is treated as evidence (not proof) of capability gain

### 4.3 Acceptable Regression Limits

| Metric | Maximum Acceptable Regression |
|--------|-------------------------------|
| OOD score degradation | ≤ 0% (no OOD regression permitted if baseline > 0%) |
| Seen score degradation | ≤ 0% (no regression on seen probes permitted) |
| Validation loss divergence from train loss | < 0.25 |
| Output repetition rate increase | < 0.10 |

*Since baseline is 0.0% across all metrics, degradation below 0% is structurally impossible. All positive Δ is measured as gain.*

---

## 5. Memorization Failure Criterion

A result is classified as **MEMORIZATION_DOMINATED** if:

| Condition | Threshold |
|-----------|-----------|
| Dominant record concentration (top 10% records) | ≥ 40% of total exposures |
| Domain concentration (single domain) | ≥ 50% of total exposures |
| N-gram repetition ratio | ≥ 50% |
| Effective epochs | ≥ 25 (BLOCK threshold) |
| Seen/OOD performance gap | > 50% (seen >> OOD) |

---

## 6. OOD Degradation Criterion

A result is classified as **REGRESSION** or flagged for OOD concern if:

| Condition | Threshold |
|-----------|-----------|
| OOD score decreases while seen score increases | Any negative OOD Δ |
| Generalization gap (seen - OOD) | > 30% |

*Since baseline OOD = 0.0%, any OOD improvement is positive. OOD degradation below 0% is impossible.*

---

## 7. Loss vs. Capability Decoupling Criterion

The experiment explicitly tests:

> **LOSS REDUCTION ≠ CAPABILITY IMPROVEMENT**

Classification rules:
- If loss decreases AND capability increases: **CORRELATED** (but not causal proof)
- If loss decreases AND capability stays at 0%: **UNCORRELATED** → verdict = NO_MEASURABLE_GAIN
- If loss decreases AND capability decreases: **ADVERSE** → verdict = REGRESSION
- If insufficient data: **INCONCLUSIVE**

---

## 8. Control Group

| Arm | Description |
|-----|-------------|
| A | Frozen baseline model (Phase 53 checkpoint, untouched) |
| B | Phase 56 trained candidate |
| C | Frozen evaluation repeat control (same model as A, re-evaluated) |

Arm C verifies evaluation determinism (score should be identical to A).

---

## 9. Milestone Evaluation Points

| Milestone | Description |
|-----------|-------------|
| M0 | Pre-training baseline (locked above: 0/32) |
| M1 | Early training (≈25% of planned steps) |
| M2 | Mid training (≈50% of planned steps) |
| M3 | Final training (100% of planned steps or guard HALT) |

---

## 10. Authoritative Verdict Categories

Upon completion, exactly one verdict will be issued:

| Code | Verdict |
|------|---------|
| A | VERIFIED CAPABILITY IMPROVEMENT |
| B | VERIFIED TRAINING WITH NO MEASURABLE CAPABILITY GAIN |
| C | INCONCLUSIVE |
| D | REGRESSION DETECTED |
| E | MEMORIZATION / OVERFITTING DOMINATED |
| F | TRAINING HALTED BY SAFETY GUARD |

**Verdict A requires:** Δ(primary) ≥ 3/32, no memorization failure, no OOD collapse, causal attribution confirmed.

---

## 11. Scientific Integrity Declaration

This experiment does NOT assume H1 is true.

A verdict of **B, C, D, E, or F** is equally acceptable as **A** from a scientific perspective. The objective is to determine the truth about whether training on a 15K-token sovereign corpus produces capability improvement in a 83K-parameter character-level model — not to manufacture a positive result.
