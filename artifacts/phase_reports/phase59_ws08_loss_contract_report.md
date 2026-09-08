# Phase 59 WS08 — Loss Contract & Mathematics Report

**Workstream:** 08 — Final Pre-Training Scientific Validation & Release Readiness Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **LOSS CONTRACT & MATHEMATICS FULLY QUALIFIED**

---

## 1. Executive Summary

This report establishes the final pre-training validation of the causal language model loss contract, response-only masking invariants, and ignore-index defensive guards.

---

## 2. Causal Shift Alignment

```python
shift_logits = logits[:, :-1, :].contiguous()  # [B, 127, 1024]
shift_labels = labels[:, 1:].contiguous()       # [B, 127]
```

- **Alignment Proof:** Position $t$ predicts target token $t+1$.
- **Boundary Conditioning:** Hidden state at index $p_{\text{len}} - 1$ (the `<assistant>` role token) predicts the first assistant response token at index $p_{\text{len}}$ with zero off-by-one errors.
- **Zero Loss on Prompts:** Prompt labels are masked to `-100` $\to \frac{\partial \mathcal{L}}{\partial z_{\text{prompt}}} = 0$.
- **Zero Loss on Padding:** Padding tokens are masked to `-100` $\to \frac{\partial \mathcal{L}}{\partial z_{\text{pad}}} = 0$.
- **Terminal EOS Supervision:** Every response terminates with token ID 3 (`</s>`) and is supervised.

---

## 3. Defensive Guard Stability

In `core_model/training/loss.py`:
```python
if not torch.any(shift_labels != ignore_index):
    raise ValueError("causal LM loss requires at least one valid target token")
```
- **Defensive Protection:** Prevents standard PyTorch `F.cross_entropy` from returning silent `NaN` values on all-masked batches.
- **Dynamic Range Stability:** Validated under extreme positive ($+10^4$) and extreme negative ($-10^4$) logits without overflow or NaN poisoning.

---

## 4. Loss Contract Verdict

**STATUS: PASS.** Causal shifting, response-only supervision, and ignore-index defensive guards are mathematically sound and operational.
