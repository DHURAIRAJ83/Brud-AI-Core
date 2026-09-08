# WS08 Duplicate Forensic Audit — 11: Training Pipeline Duplicate Impact

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. Training Pipeline Duplicate Impact Overview

The training pipeline for WS07 E3 and future E4/E5 operates through:
```
Dataset Seal → Training Runner → Checkpoint → Evaluation Runner
```

This report determines whether any duplicated class can cause wrong model architecture, wrong checkpoint, or wrong evaluation target.

---

## 2. BrudSmallV2Model — Training Impact

### The 4 production runners define their own local model class:

| Runner | BrudSmallV2Model Hash | Uses `persistent=False` | generate() |
|---|---|---|---|
| WS05 (training) | `e8056a70bc11` | ❌ NO | Not present |
| WS06 (evaluation) | `5f5834fb2070` | ✅ YES | Greedy/temp |
| WS07-A (diagnostics) | `518a7b39d5e8` | ✅ YES | Controlled (θ+ngram) |
| E3 (training + eval) | `6aecf087c213` | ✅ YES | Controlled (θ+ngram) |

### Checkpoint Compatibility Analysis

**Question: Can the WS05 checkpoint be loaded by WS06/E3 evaluators?**

WS05 runner saves PE buffer `persistent=True` (default):
```python
# WS05 model state_dict keys:
embedding.weight, encoder.layers.*.*, lm_head.weight, lm_head.bias, pe
```

WS06/WS07/E3 runners use `persistent=False`:
```python
# WS06/E3 model state_dict keys (expected):
embedding.weight, encoder.layers.*.*, lm_head.weight, lm_head.bias
# (pe NOT in state_dict — it's rebuilt at runtime)
```

**If WS05 checkpoint loaded into WS06 model with strict=True:**
```
RuntimeError: Unexpected key(s) in state_dict: 'pe'
```

**Actual behavior:**
The evaluation scripts use `model.load_state_dict(checkpoint["model_state_dict"], strict=False)` in most runners. Verified in WS06 runner — it uses `strict=False`. Therefore no runtime error occurs.

However: Any future E4/E5 runner that naively uses `strict=True` when loading the WS05 checkpoint **will fail**. This is a **forward-looking risk for E4/E5**.

### Will E4/E5 Be Affected?

**YES — POTENTIAL P0 IMPACT if not handled.**

E4/E5 will define a new, larger BrudSmallV2Model (e.g., L=4, d=256). If E4/E5 starts from the WS05 checkpoint with `strict=True`, it will encounter the unexpected `pe` key. The correct approach for E4/E5 is:
1. Use `strict=False` explicitly
2. OR re-save the WS05 checkpoint with the `pe` key stripped before starting E4/E5

**This is a documentation-and-verification item — no code change required now.**

---

## 3. GuardAction (Memorization Guard Versions)

| Version | File | Hash | Active in Training? |
|---|---|---|---|
| Phase53 | `phase53_memorization_guard.py` | `0c3bfd021f84` | ❌ Superseded |
| Phase54 | `phase54_memorization_guard.py` | `3fa6cc41e238` | ❌ Superseded |
| Phase56 | `phase56_memorization_guard.py` | `3fa6cc41e238` | 🟡 May be imported |

The Phase56 guard has the same `GuardAction` hash as Phase54. The additional `RecordExposureTelemetry` class in Phase56 is the only functional extension.

**Is Phase56 guard imported by E3?**
The E3 runner (`run_e3_experiments.py`) does NOT import any memorization guard module. Memorization guard is used in the training engine abstractions (Phase53/54/56 are historical evolution). The E3 runner implements its own dataset exposure tracking inline.

**Finding: Memorization guard duplicates have NO impact on E3/E4/E5 training.**

---

## 4. Dataset Pipeline Duplicates

| Class | Files | Training Impact |
|---|---|---|
| `AdminReviewRequest` (14 copies) | All Mini Brain models | No impact — training auth uses `phase44_runtime_governance.py` |
| `QualityAssessRequest` (2 copies) | corpus.py vs dataset_quality.py | No impact — separate validation paths |
| `GovernedRecord` (2 copies) | phase52 vs phase53 corpus | No impact — versioned, neither imported by E3 |

---

## 5. Wrong Model Architecture Risk

**Question: Could E4/E5 accidentally import an obsolete BrudSmallV2Model?**

**Answer: NO — because:**
1. There is no shared `BrudSmallV2Model` module to accidentally import
2. Each runner defines its own local class
3. E4/E5 will define a new class (likely `BrudSmallV4Model` or with different params)
4. The new class will not conflict with old definitions in separate files

**Finding: E4/E5 architecture scaling WILL NOT accidentally import an obsolete model class.**

---

## 6. Training Pipeline Impact Summary

| Risk Area | Risk Level | Finding |
|---|---|---|
| Wrong model class imported | **NONE** | No shared module — each runner defines locally |
| Wrong tokenizer | **NONE** | Tokenizer v2 is SHA-256 locked in all runners |
| Wrong checkpoint | **NONE** | Checkpoint paths are explicit in each runner |
| Wrong hyperparameters | **NONE** | Configs are SHA-256 verified before training |
| Wrong candidate directory | **NONE** | Output paths are hardcoded per phase |
| Wrong evaluation target | **NONE** | Evaluation runner explicitly loads specific checkpoint |
| PE key checkpoint mismatch | **LOW** | WS05→WS06 loading uses strict=False; future E4/E5 must verify |
| Memorization guard conflict | **NONE** | E3 runner doesn't use memorization guard |

---

## 7. Final Verdict

```
TRAINING PIPELINE DUPLICATE IMPACT: MINIMAL

One forward-looking risk for E4/E5:
  WS05 checkpoint includes 'pe' in state_dict (persistent=True default)
  E4/E5 must use strict=False OR strip 'pe' key before loading

No other duplicate class creates a training pipeline risk.
```
