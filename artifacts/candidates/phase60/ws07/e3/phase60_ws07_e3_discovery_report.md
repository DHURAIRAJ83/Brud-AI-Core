# Phase 60 WS07 E3 — Repository Discovery & Implementation Report

**Phase:** Phase 60 — Post-Training Capability Expansion & Generalization Improvement  
**Workstream:** WS07 Stage B — Controlled Remediation Training (E3 Multilingual Data Experiments)  
**Date:** 2026-09-01  
**Status:** DISCOVERY COMPLETE — AWAITING HUMAN AUTHORIZATION FOR STAGE B TRAINING  

---

## 1. Existing Infrastructure Audit & Reuse Map

| Component | Existing Repository Source | Reuse Strategy for E3 Experiments |
|---|---|---|
| **Model Architecture** | `run_controlled_training_ws05.py` / `BrudSmallV2Model` | Reused exactly: $V=1024, d_{\text{model}}=128, h=4, L=2, d_{\text{ff}}=256, T=128$, Sinusoidal PE buffer, 528,128 parameters. |
| **Tokenizer** | `data/tokenizers/versions/tok/v2/tokenizer.model` | Frozen Tokenizer v2 (SHA-256: `65342625...`) used without any mutation or retraining. |
| **Checkpoints Lineage** | `artifacts/candidates/phase60/checkpoints/checkpoint_best.pt` | WS05 checkpoint (SHA-256: `30dbb892...`) is strictly READ-ONLY. Each E3 experiment outputs to an isolated directory. |
| **Dataset Schema** | `artifacts/candidates/phase60/phase60_dataset_v001.jsonl` | Canonical 19-field Phase 60 schema followed 100%. |
| **E3 Sealed Dataset** | `artifacts/candidates/phase60/ws07/e3/data/phase60_ws07_e3_dataset_v001.jsonl` | Sealed candidate dataset (SHA-256: `cb1387eb...`, 88 records) used as authoritative expansion source. |
| **Training Engine** | `run_controlled_training_ws05.py` | PyTorch AdamW training loop with response-only loss masking (`-100`), gradient clipping, and cosine LR scheduling. |
| **Stop Conditions** | `phase60_ws04_stop_conditions.md` & WS05 monitor | Enforcing all 15 stop conditions (NaN/Inf loss/grad, RSS > 2GB, swap > 0MB, loss spike > 3.0x, checkpoint verification). |
| **Capability Evaluator** | `run_capability_evaluation_ws06.py` | CAP-01 through CAP-24 probe suite, repetition ratio calculation, EOS emission rate, multi-turn context testing. |
| **Inference Controls** | WS07 Stage A decoding ablations | Repetition penalty $\theta=1.25$, top-k sampling, and no-repeat 3-gram controls evaluated alongside raw weights. |

---

## 2. Frozen Inputs & Cryptographic Baselines

All 8 authoritative baselines verified bit-for-bit:
- **Tokenizer v2:** `65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4`
- **Phase 53 Benchmark:** `554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088`
- **Phase 55 Corpus:** `3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1`
- **Production DB:** `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`
- **Phase 59 Baseline:** `a5218b5bdb94d3b218896f3021d7f7d5298023036d350bf8a2d5e3b70423371a`
- **WS05 Candidate Checkpoint:** `30dbb8927c0c61c786683c06eebf8a2718054a4cf1df25ece47f97ca7c605421`
- **Phase 60 WS03 Dataset v001:** `f682ddf82e750449792f8148be50ccb235506d16a0732fb8dc3fa2e9f4935920`
- **E3 Sealed Dataset v001:** `cb1387ebc92c6554fa0bd6a3b076728142b295c7e3b334670a2f5547da17c391`

---

## 3. Directory Isolation Structure

```
artifacts/candidates/phase60/ws07/e3/experiments/
├── e3_a/       # Tamil Only Baseline
├── e3_b/       # Tamil + English Translations
├── e3_c/       # Tamil + English + Tanglish
├── e3_d/       # Tamil + English + Tanglish + Mixed
└── e3_e/       # Balanced Multilingual + Conversation + Instruction
```

Each experiment sub-directory contains its own:
- Sealed experiment training dataset (`dataset.jsonl`)
- Manifest and training config
- Training log (`training_log.jsonl`)
- Checkpoints (`checkpoint_best.pt`, `checkpoint_step_*.pt`)
- 14 required analytical reports
