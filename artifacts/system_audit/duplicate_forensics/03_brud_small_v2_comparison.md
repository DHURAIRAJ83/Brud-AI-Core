# WS08 Duplicate Forensic Audit — 03: BrudSmallV2Model × 4 Production Runners Deep Comparison

**Audit Date:** 2026-09-01  
**Classification:** EVIDENCE-BASED, READ-ONLY  
**Files Compared:** 4 production runners + 5 test copies = 9 total

---

## 1. All Occurrences (Confirmed by AST Scan)

| # | File | Context | Line | Impl Hash | PE persistent=False |
|---|---|---|---|---|---|
| P1 | `artifacts/candidates/phase60/run_controlled_training_ws05.py` | WS05 training runner | 47 | `e8056a70bc11` | ❌ Missing `persistent=False` |
| P2 | `artifacts/candidates/phase60/run_capability_evaluation_ws06.py` | WS06 evaluation runner | 46 | `5f5834fb2070` | ✅ Has `persistent=False` |
| P3 | `artifacts/candidates/phase60/ws07/run_ws07_stage_a_diagnostics.py` | WS07 Stage A diagnostics | 49 | `518a7b39d5e8` | ✅ Has `persistent=False` |
| P4 | `artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py` | WS07 E3 experiments | 75 | `6aecf087c213` | ✅ Has `persistent=False` |
| T1 | `tests/evaluation/test_phase60_ws04_training_preparation.py` | Test fixture | 62 | `e8056a70bc11` | ❌ Missing |
| T2 | `tests/evaluation/test_phase60_ws05_controlled_training.py` | Test fixture | 63 | `71103863b113` | ❌ Missing |
| T3 | `tests/evaluation/test_phase60_ws06_capability_evaluation.py` | Test fixture | 63 | `518a7b39d5e8` | ✅ |
| T4 | `tests/evaluation/test_phase60_ws07_remediation.py` | Test fixture | 70 | `93c2d088bbb7` | ✅ |
| T5 | `tests/evaluation/test_phase59_ws05_training_safety.py` | Phase59 test fixture | 70 | Similar | ✅ |

---

## 2. Architecture Comparison Matrix

| Attribute | P1 (WS05) | P2 (WS06) | P3 (WS07-A) | P4 (E3) |
|---|---|---|---|---|
| **vocab_size** | 1024 | 1024 | 1024 | 1024 ✅ |
| **d_model** | 128 | 128 | 128 | 128 ✅ |
| **nhead** | 4 | 4 | 4 | 4 ✅ |
| **num_layers** | 2 | 2 | 2 | 2 ✅ |
| **dim_feedforward** | 256 | 256 | 256 | 256 ✅ |
| **Embedding** | `nn.Embedding(1024,128)` | Same | Same | Same ✅ |
| **Positional Enc** | Sinusoidal PE | Same | Same | Same ✅ |
| **pe register_buffer** | `persistent` not set → **defaults True** | `persistent=False` | `persistent=False` | `persistent=False` |
| **TransformerEncoderLayer** | batch_first, dropout=0.0, relu | Same | Same | Same ✅ |
| **num_layers** | 2 | 2 | 2 | 2 ✅ |
| **lm_head** | Linear(128→1024, bias=True) | Same | Same | Same ✅ |
| **forward()** | Same 3-line | Same | Same | Same ✅ |
| **generate()** | NOT defined | greedy/temp | controlled (θ+ngram) | controlled (θ+ngram) |
| **param count** | **528,128** | **528,128** | **528,128** | **528,128** ✅ |
| **Docstring** | "Authoritative…(528,128 parameters)" | Same | None | "Authoritative…(528,128 parameters)" |
| **state_dict compat** | ✅ Compatible | ✅ Compatible | ✅ Compatible | ✅ Compatible |

---

## 3. The One Critical Difference: `persistent=False` in PE Buffer

### WS05 (P1 — oldest runner):
```python
self.register_buffer("pe", self._build_sinusoidal_pe(128, d_model))
# persistent defaults to True → PE tensor saved into checkpoint state_dict
```

### WS06, WS07-A, E3 (P2, P3, P4 — all newer runners):
```python
self.register_buffer("pe", self._build_sinusoidal_pe(128, d_model), persistent=False)
# PE tensor is NOT saved in state_dict → checkpoint is clean
```

### Impact of This Difference
| Effect | P1 (WS05) | P2/P3/P4 (newer) |
|---|---|---|
| PE in checkpoint `.pt` file | ✅ Saved | ❌ Not saved (by design) |
| Load checkpoint with `strict=True` | ❌ Will FAIL if P1 ckpt loaded into P2/P3/P4 model | N/A |
| Load checkpoint with `strict=False` | ✅ Works | ✅ Works |
| Functional difference in inference | ❌ None — PE is rebuilt on demand | ❌ None |
| checkpoint_best.pt compatibility | ⚠️ MARGINAL RISK | ✅ Correct |

> **FINDING:** The WS05 training checkpoint may include `pe` in `state_dict`. The WS06/WS07 evaluators load it with `strict=False` in most runners, so no runtime failure occurs. However WS05's checkpoint is the upstream starting point for WS07 Stage B training. If E4/E5 use the new canonical form with `persistent=False` and try to load the WS05 checkpoint with `strict=True`, the extra `pe` key will cause a state dict mismatch error.

---

## 4. generate() Implementation Comparison

| Runner | generate() Method | Temperature | Repetition Penalty | No-Repeat N-Gram |
|---|---|---|---|---|
| P1 WS05 | ❌ Not present | N/A | N/A | N/A |
| P2 WS06 | Greedy/temp inline | ✅ configurable | ❌ None | ❌ None |
| P3 WS07-A | Controlled inline | ✅ temp=0.7 | ✅ θ=1.25 | ✅ 3-gram |
| P4 E3 | Same as P3 + docstring | ✅ temp=0.7 | ✅ θ=1.25 | ✅ 3-gram |

---

## 5. Canonical Implementation Determination

### Which is AUTHORITATIVE?

```
CANONICAL OWNER: P4 — artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py
```

**Evidence:**
1. Chronologically last — produced at WS07 E3 (most recent phase)
2. Has `persistent=False` (correct checkpoint hygiene)
3. Has docstring confirming role
4. Has best `generate()` with repetition controls (θ=1.25, 3-gram)
5. Was used for E3-A through E3-E training runs (the most current training iteration)
6. All other runners are a subset of its capabilities

### Why NOT P3 (WS07-A)?
P3 has no docstring and its `generate()` is identical to P4's. P4 is strictly a superset.

### Why NOT P1 (WS05)?
Missing `persistent=False` — checkpoint includes PE tensor unnecessarily.

### Is there a canonical MODEL FILE (not runner)?
**No.** `BrudSmallV2Model` exists only as a self-contained class inside standalone runner scripts. There is **no shared canonical model module** in the codebase. This is the P0 architecture gap.

---

## 6. Test Copies Classification

All 5 test file copies are **classification D — TEST FIXTURE**.

They are local inline copies needed to:
- Avoid importing production runner scripts into test environment
- Keep tests self-contained for CI
- Allow testing of checkpoint loading/state_dict without runner side effects

**Risk:** Test WS04 (T1) uses the P1 hash — no `persistent=False`. This means the test does not catch the PE checkpoint hygiene issue. Low operational risk since tests verify structural properties only.

---

## 7. Will E4/E5 Be Affected?

**Yes — potential P0 risk** if E4/E5 runners:
1. Start from a checkpoint produced by P1 (WS05 runner)
2. Define the new architecture with `persistent=False`
3. Load with `strict=True`

**Result:** `RuntimeError: Unexpected key(s) in state_dict: 'pe'`

**Mitigation required before E4/E5:**
- Confirm all E4/E5 runners use `persistent=False`
- Confirm WS05 checkpoint loading uses `strict=False` or `map_location` + key filtering
- Or re-save the WS05 checkpoint with the `pe` key removed

**DO NOT implement now — this is an audit finding only.**

---

## 8. Summary Verdict

```
BrudSmallV2Model × 9 occurrences:
  CLASSIFICATION: E (Experimental Candidate) × 4 production | D (Test Fixture) × 5 tests
  ARCHITECTURALLY IDENTICAL: YES (same 528,128 param layout)
  FUNCTIONALLY DIFFERENT: YES (different generate() implementations)
  STATE_DICT COMPATIBLE: YES for P2/P3/P4; MARGINAL for P1→P2/P3/P4 with strict=True
  CANONICAL OWNER: P4 — run_e3_experiments.py
  SAFE_TO_REMOVE: NO — each serves a distinct phase execution role
  E4/E5 IMPACT: ⚠️  MODERATE RISK if strict=True loading used with WS05 checkpoint
  ACTION BEFORE E4/E5: Verify checkpoint loading uses strict=False or strip pe key
```
