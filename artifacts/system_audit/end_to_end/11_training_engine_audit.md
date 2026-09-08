# Master Brud AI End-to-End Audit — 11: Training Engine Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal ML Training Systems Engineer  
**Confidence Rating:** HIGH CONFIDENCE (Verified by executing test suites and inspecting training runners)  

---

## 1. Training Engine Architecture & Hardware Bounds

The active training engine (`run_controlled_training_ws05.py` and `run_e3_experiments.py`) runs directly on PyTorch CPU with strict resource limits:

```
[ Input: Sealed JSONL Dataset ]
               │
               ▼ Stratified Seed Split (80% Train, 10% Val, 10% Test)
[ PyTorch Causal Dataloader ]
  - Batch Size: 32 (Gradient Accumulation: 4 steps x 8 micro-batch)
  - Sequence Length: T=128 (Pad token = 0, Loss masked on pad tokens)
               │
               ▼ Forward Pass
[ BrudSmallV2 Transformer ]
  - Parameters: 528,128 (V=1024, d=128, L=2, h=4, d_ff=256)
  - Non-trainable Sinusoidal Position Buffer
               │
               ▼ Cross-Entropy Loss (Shifted logits vs targets)
[ Backward Pass & Optimization ]
  - Optimizer: AdamW (lr=3e-4, weight_decay=0.01)
  - Scheduler: Linear warmup (50 steps) + Cosine decay
  - Gradient Clipping: max_norm = 1.0
               │
               ▼ Continuous Hardware & Loss Safety Guard
[ 15 Enforced Stop Conditions ]
  - Loss NaN / Inf
  - Gradient explosion (> 10.0)
  - Loss divergence (> 15.0)
  - RAM ceiling (> 2.0 GB)
  - Swap space usage (> 0.0 MB)
               │
               ▼ Periodic Evaluation
[ Checkpoint Serialization & Integrity Hashing ]
  - Saves: checkpoint_best.pt, config.json, summary.json, training_log.jsonl
  - Calculates: SHA-256 digest over state_dict
```

---

## 2. Can an Approved Dataset Actually Train a Model?

### The Question:
> *Can this actually happen: Admin approved dataset $\to$ Training sandbox $\to$ Brud model training $\to$ Checkpoint creation $\to$ Validation $\to$ Independent evaluation?*

### The Verdict: **YES, FULLY OPERATIONAL AND EMPIRICALLY VERIFIED.**
- **Evidence:** This exact chain ran 5 consecutive times in Phase 60 WS07 Stage B (`E3-A`, `E3-B`, `E3-C`, `E3-D`, `E3-E`):
  1. The sealed dataset (`phase60_ws07_e3_dataset_v001.jsonl`) was ingested.
  2. Training executed 100/100 steps on CPU (2 threads, RAM < 513 MB, 0 swap).
  3. `checkpoint_best.pt` was generated with exact SHA-256 hashes.
  4. Dual-mode capability evaluation (`CAP-01` through `CAP-24`) evaluated both raw weights and controlled decoding.
  5. 10 analytical markdown reports were output per experiment.
- **The Only Constraint:** It requires an operator command or automated test trigger; it does not self-execute without human authorization.
