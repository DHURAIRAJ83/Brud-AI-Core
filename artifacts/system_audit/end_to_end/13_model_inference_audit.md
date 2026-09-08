# Master Brud AI End-to-End Audit — 13: Model Inference & Decoding Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal Inference Runtime Engineer  
**Confidence Rating:** HIGH CONFIDENCE (Verified by running evaluation harnesses and inspecting `backend/services/inference_runtime_service.py`)  

---

## 1. Inference Engine Architecture & Model Loader

The inference runtime executes locally on CPU with hardware safety guards:
- **Service:** `InferenceRuntimeService` (`backend/services/inference_runtime_service.py`).
- **Loader:** `model_loader.py` validates model file existence and verifies SHA-256 digests against the database registration record before loading weights.
- **Hardware Isolation:** Enforces a 2 GB RAM ceiling and 30-second execution timeout per inference request.
- **Scope Isolation:** Models can only be assigned to specific scopes (`admin_diagnostic`, `eval_benchmark`, or `public_chat`). Assigning a model to `public_chat` requires passing the strict canary gate.

---

## 2. Raw Greedy Decoding vs Repetition-Controlled Decoding

The Phase 60 WS06 and WS07 evaluations uncovered a fundamental scientific insight regarding Brud-Small v2's inference behavior:

### A. Raw Greedy Decoding Pathologies
Under default greedy decoding ($\text{argmax}_{w} P(w \mid w_{<t})$):
- **3-Gram Repetition Ratio:** **0.51 to 0.90** across all evaluated checkpoints. The model rapidly enters infinite repetition loops (e.g. repeating `நன்றி நன்றி நன்றி...` or `is a is a is a...`).
- **EOS Emission Rate:** Only **0% to 25%** for earlier runs (WS05, E3-A..E3-D). The model fails to emit `<eos>` (token ID 3) and exhausts the max token budget ($T=128$).

### B. Controlled Decoding Remediation
In WS07 E3, an inference-assisted decoding engine was implemented and benchmarked:
- **Parameters:** Temperature $\theta = 1.25$, Top-$k = 50$, Top-$p = 0.90$, Repetition Penalty $= 1.20$, and `no_repeat_ngram_size = 3`.
- **Results:**
  - **3-Gram Repetition Ratio:** Drops to **0.0000** across all 5 candidate models!
  - **EOS Emission Rate:** Reaches **100.0%** in candidate `E3-E`.
  - **Safety Refusals:** Retained cleanly without loop degradation.

### Scientific Caveat:
Controlled decoding **cures generation degeneration (looping)**, but it **cannot synthesize knowledge or reasoning** that does not exist in the 528k parameter weights.
