# Phase 57 Safe Micro-Experiment Plan

**Workstream:** 15 — Safe Micro-Experiment Design  
**Timestamp:** 2026-08-30T17:15:00Z  
**Status:** ✅ EXPERIMENT SPECIFICATION APPROVED — ISOLATED DIAGNOSTIC TESTS

---

## 1. Experimental Objectives

To isolate specific components of the model, optimizer, tokenizer, and evaluation pipeline without running uncontrolled training campaigns, six targeted micro-experiments are designed.

---

## 2. Micro-Experiment Matrix

| Experiment | Name | Purpose | Configuration | Pass / Fail Criterion |
|---|---|---|---|---|
| **Exp A** | Overfit Tiny Known Batch | Test whether the 83K model architecture has the basic mathematical capacity to minimize cross-entropy loss to near-zero when exposure is sufficient | Single sequence (batch size 1), 100 optimizer steps, AdamW lr=1e-3 | Loss < 0.10 within 100 steps |
| **Exp B** | Single-Batch Gradient Update | Verify that backpropagation produces non-zero weight updates in PyTorch without silently failing | 1 step backward, measure $\max \vert \theta_{t+1} - \theta_t \vert$ | Parameter delta > 0 |
| **Exp C** | Evaluator Known-Learning Detection | Test whether the evaluation pipeline's keyword matching logic can detect a correctly produced keyword | Synthetically generate a response containing target keyword `'வணக்கம்'` | Evaluator returns `kw_hit=True` |
| **Exp D** | Tokenizer Reconstruction Test | Test whether the SentencePiece model can encode and decode critical target keywords without character destruction | Encode and decode 8 representative words across Tamil, English, and digits | Round-trip reconstruction matches input string exactly |
| **Exp E** | Label-Shift Alignment Test | Verify that causal next-token cross-entropy correctly pairs $x_t$ with $x_{t+1}$ | Construct tensor $[10, 20, 30, 40]$; verify target slice equals $[20, 30, 40]$ | Target tensor is correctly shifted by 1 |
| **Exp F** | Checkpoint Load Equivalence Test | Verify that loading weights from saved `.pt` checkpoints produces bit-exact deterministic model outputs | Load candidate checkpoint into two separate model instances; compare logits on test input | `torch.equal(logits1, logits2)` is True |

---

## 3. Containment & Boundary Guarantees

- No changes to production database.
- No model registration or promotion.
- Experiments run strictly in-memory within ephemeral diagnostic harnesses.
- Checkpoint files remain strictly read-only.
