# Phase 56 Control Group Design Report

**Workstream:** 8 — Control Group Design  
**Timestamp:** 2026-08-30T16:02:00Z  
**Status:** ✅ CONTROL DESIGN FINALIZED

---

## 1. Experimental Arms

| Arm | Label | Description |
|-----|-------|-------------|
| **A** | Frozen Baseline | Phase 53 checkpoint (step 3154) — evaluated WITHOUT any Phase 56 training |
| **B** | Phase 56 Candidate | Same checkpoint fine-tuned on Phase 55 train split (316 records, 12,277 tokens) |
| **C** | Frozen Evaluation Repeat | Arm A re-evaluated independently to confirm evaluation determinism |
| **D** | N/A | No independent random control arm (statistically inappropriate for deterministic greedy evaluation with only 32 probes) |

---

## 2. Arm Definitions

### Arm A — Frozen Baseline
- **Checkpoint:** `artifacts/checkpoints/phase53/checkpoint_step_3154.pt`
- **State:** Untouched, frozen after Phase 53
- **Evaluated at:** Pre-training (M0) — **already locked: 0/32 = 0.0%**
- **Purpose:** Ground truth baseline for capability comparison

### Arm B — Phase 56 Trained Candidate
- **Starting checkpoint:** `artifacts/checkpoints/phase53/checkpoint_step_3154.pt`
- **Training data:** Phase 55 train split only (316 records, 12,277 tokens)
- **Training:** 120 steps with config `artifacts/phase56_training_config.json`
- **Evaluated at:** M1 (step 30), M2 (step 60), M3 (step 120)
- **Saved to:** `artifacts/phase56_checkpoints/`
- **Purpose:** The experimental candidate

### Arm C — Evaluation Determinism Control
- **Checkpoint:** `artifacts/checkpoints/phase53/checkpoint_step_3154.pt` (identical to Arm A)
- **Training:** None
- **Evaluated at:** After training completes (post-M3)
- **Purpose:** Verify evaluation is deterministic and scores are stable

---

## 3. Evaluation Protocol

| Property | Specification |
|----------|---------------|
| Evaluation manifest | `artifacts/phase53_evaluation_manifest.json` (frozen, unchanged) |
| Total probes | 32 |
| Scoring | Keyword-hit (case-insensitive substring match) |
| Decoding policy | Greedy argmax (deterministic) |
| Max generation tokens | 25 |
| Prompt truncation | 40 tokens max |
| Evaluation seed | 42 (model deterministic under greedy) |
| Environment | CPU-only, identical torch version, identical tokenizer |

**All arms use the exact same:**
- Evaluation probes (frozen manifest)
- Scoring function
- Decoding policy
- Evaluation environment

**No arm receives privileged information.**

---

## 4. Comparison Metrics

| Comparison | Formula | Purpose |
|------------|---------|---------|
| Primary gain | Δ(B−A) = Score(B) − Score(A) | Main capability gain |
| Evaluation stability | Δ(C−A) = Score(C) − Score(A) | Must equal 0 (same model) |
| Cluster gains | Δ(B−A) per cluster | Per-domain capability change |
| Probe-type gains | Δ(B−A) per seen/held_out/OOD | Generalization profile |
| Gain efficiency | Δ(B−A) / (exposure_tokens / 1000) | Capability per 1K tokens |
| Repetition delta | repetition(B) − repetition(A) | Output quality |

---

## 5. Evaluation Timeline

| Milestone | Model Evaluated | Step | Purpose |
|-----------|----------------|------|---------|
| M0 | Arm A (baseline) | 0 | Baseline lock (completed: 0/32) |
| M1 | Arm B (candidate) | 30 | Early training capability |
| M2 | Arm B (candidate) | 60 | Mid-training capability |
| M3 | Arm B (candidate) | 120 | Final training capability |
| C | Arm C (control repeat) | Post-M3 | Determinism verification |

---

## 6. Split Isolation Guarantee

| Invariant | Enforcement |
|-----------|-------------|
| Train split used for gradient updates only | Enforced in training loop |
| Val split used for loss monitoring only | Enforced — no gradient updates |
| Test split never touched during training | Reserved for post-training analysis |
| Frozen eval probes never used in training | Verified by contamination screen (Phase 55) |

---

## 7. Evaluation Environment Consistency

All arms are evaluated in the same environment:
- Same machine (Intel G2030, 2 cores, CPU-only)
- Same Python 3.13.5 + torch 2.13.0+cpu
- Same tokenizer (`data/tokenizers/versions/tok/v1/tokenizer.model`)
- Same model loading code
- Same scoring function
- Same random seed (42)

---

## 8. Arm C Validity Check

Arm C evaluates the **identical model** as Arm A. Expected result:
```
Score(C) == Score(A) == 0/32
Δ(C−A) == 0
```

If `Δ(C−A) ≠ 0`, this indicates:
- Non-determinism in evaluation (bug)
- Environment change between evaluations
- Model file corruption

If Arm C fails determinism, all Arm B results are invalidated.

---

## 9. Control Design Verdict

> **✅ CONTROL DESIGN FINALIZED**
>
> Arms A (baseline), B (candidate), C (control repeat) defined.  
> Arm D omitted (not statistically appropriate for this evaluation protocol).  
> All arms use identical evaluation probes, scoring, and environment.  
> Evaluation timeline: M0 (done) → M1 → M2 → M3 → C.  
>
> Proceed to Workstream 9 — Controlled Training Campaign.
