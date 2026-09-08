# Stage C Pre-Flight Audit — 02: Canonical Training Engine Audit

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Canonical Identification

We performed an end-to-end trace of the training execution pipeline:
`Dataset → Dataset Loader → Tokenizer → Batch Builder → Loss Masking → Optimizer → Scheduler → Checkpoint Writer → Evaluation Engine`.

```text
CANONICAL_TRAINING_ENGINE     = artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py (run_training_experiment)
CANONICAL_CHECKPOINT_WRITER   = artifacts/candidates/phase60/ws07/e3/run_e3_experiments.py (atomic_save_checkpoint)
CANONICAL_EVALUATION_ENGINE   = artifacts/candidates/phase60/run_capability_evaluation_ws06.py (run_capability_probes)
```

---

## 2. Pipeline Trace & Overlap Analysis

### A. Dataset Loading & Slicing
- **Canonical Location:** `run_e3_experiments.py` (`load_data_and_slice`)
- **Behavior:** Loads frozen Phase 60 base dataset (`WS03_DATASET_PATH`) and sealed E3 expansion dataset (`E3_DATA_PATH`). Builds split variations E3-A, E3-B, E3-C, E3-D, and E3-E.
- **Verification:** Bit-for-bit SHA-256 baseline check before any batch construction.

### B. Batch Construction & Response-Only Loss Masking
- **Canonical Location:** `run_e3_experiments.py` (`build_dataloader` and `collate_fn`)
- **Prompt Format:** `<user>{instruction}{optional_context}<assistant>`
- **Masking Rule:** Prompt token labels are set to `-100` (ignored in CrossEntropyLoss). Response tokens emit standard token targets ending with `EOS` (`3`).

### C. Optimizer & Scheduler Configuration
- **Optimizer:** `torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=0.01, betas=(0.9, 0.999))`
- **Scheduler:** Cosine annealing with linear warmup (`get_cosine_schedule_with_warmup`). Warmup steps = 10% of total steps, min_lr = `1e-5`.
- **Resource Guards:** Enforces `torch.set_num_threads(2)` and active peak RSS monitoring (< 2.0 GB).

### D. Checkpoint Writing (Atomic & Provenance Sealed)
- **Canonical Writer:** Atomic two-phase write (`checkpoint_best.pt.tmp` -> `checkpoint_best.pt`).
- **Metadata Payload:** Includes `epoch`, `step`, `val_loss`, `model_state_dict`, `optimizer_state_dict`, `scheduler_state_dict`, `training_config`, `dataset_sha256`, `tokenizer_sha256`.

---

## 3. Training Engine Comparison Table

| Feature | WS05 Trainer (`run_controlled_training_ws05.py`) | E3 Experiments Trainer (`run_e3_experiments.py`) — CANONICAL |
|---|---|---|
| **Dataset Source** | Phase 60 Base Dataset (1,800 records) | Base Dataset + E3 Sealed Multilingual Dataset (1,885 records) |
| **Splits Supported** | Single Train/Val/Test | E3-A (Tamil), E3-B (Ta+En), E3-C (+Tanglish), E3-D (+Mixed), E3-E (Balanced Multilingual) |
| **PE State Dict** | Saved (`persistent=True` default) | Omitted (`persistent=False`, rebuilt dynamically) |
| **Integrated Eval** | Basic loss metric | Dual-mode (Raw + Repetition-Controlled θ=1.25 + 3-gram) |
| **Hardware Guards** | CPU thread ceiling (2), RSS ceiling (2GB) | CPU thread ceiling (2), RSS ceiling (2GB), Swap target (0MB) |

---

## 4. Stage C Pre-Flight Consolidation Plan

Before initiating E4/E5 Stage C execution, we recommend modularizing the training loop into a standalone, reusable core module:
```text
PROPOSED CANONICAL TRAINING MODULE = core_model/training/brud_training_engine.py
```
This module will encapsulate `train_one_epoch`, `evaluate_loss`, and `atomic_save_checkpoint`, preventing any training loop divergence between E4 (Context Scaling) and E5 (Architecture Scaling).
