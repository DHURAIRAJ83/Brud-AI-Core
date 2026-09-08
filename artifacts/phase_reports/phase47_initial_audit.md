# PHASE 47 INITIAL READ-ONLY BASELINE AUDIT REPORT

**Date:** 2026-08-29  
**Audit Role:** Principal ML Systems Engineer, AI Safety Engineer, Security Engineer, & Production Architecture Engineer  
**Git Branch:** `phase-5-performance-polish`  
**Git HEAD:** `df054cb100b58d99acf42a72d18dcbcb7dcbd5f8`  
**Git Stash:** `stash@{0}: On phase-5-performance-polish: Phase 7C-1 pilot: async->def conversion (inconclusive, not adopted)`  
**Audit Purpose:** Workstream 1 read-only baseline capture for Phase 47.  

---

## 1. Safety & Production Database Invariants

| Property | Measured Value | Target / Invariant | Status |
| :--- | :--- | :--- | :--- |
| **Database Path** | `/home/dhurai/Projects/brud-ai/data/database/brud_ai.db` | `data/database/brud_ai.db` | Verified |
| **Database SHA-256** | `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729` | Exact Match | 100% Byte-Identical |
| **Database Size** | `11,096,064 bytes` | 11,096,064 bytes | 100% Byte-Identical |
| **WAL File** | None (`brud_ai.db-wal` does not exist) | Clean | Verified |
| **SHM File** | None (`brud_ai.db-shm` does not exist) | Clean | Verified |

---

## 2. Hardware Resource Constraints (Host Profile)

| Hardware Dimension | Measured Reality | Constraint Enforcement |
| :--- | :--- | :--- |
| **CPU Model** | Intel(R) Pentium(R) CPU G2030 @ 3.00GHz | 2 physical cores, 2 threads |
| **Vector Extensions**| SSE4.2 (NO AVX, NO AVX2) | CPU-only PyTorch execution |
| **Active Thread Bound**| Bounded via `torch.set_num_threads(2)` | Strictly 2 worker threads |
| **RAM (Total / Avail)**| 11 GiB total / ~4.9 GiB available | ResourceGuard threshold: 500 MB minimum |
| **Swap (Total / Free)**| 5.9 GiB total / 4.3 GiB free | Healthy swap headroom |
| **Disk Available (/)** | 106 GiB available on `/dev/sda1` | ResourceGuard threshold: 1,000 MB minimum |
| **GPU / Accelerator**| None (`torch.cuda.is_available() == False`)| CPU-only |

---

## 3. Software Environment

- **Python Version:** 3.13.5
- **PyTorch Version:** 2.13.0+cpu
- **SentencePiece Version:** 0.2.2
- **Pytest Version:** 8.4.2

---

## 4. Current Training & Checkpoint Baseline (Phase 46 Legacy)

- **Latest Manifest:** `phase46_dataset_manifest.json`
  - Manifest Hash: `f84a4fce2d438ad4c78940967f7bf0b9f5692bf047a71e5355fbc9c07f808241`
  - Accepted records: 11 (Tamil: 8, English: 3)
  - Estimated tokens: 281 tokens
- **Checkpoint Inventory:** `artifacts/phase46_checkpoints/`
  - Existing steps: `checkpoint_step_10` through `checkpoint_step_130`, plus `checkpoint_best`
  - Latest checkpoint: `checkpoint_step_130`
  - Best checkpoint: `checkpoint_best` (val loss: `4.17959`)
- **Cumulative Optimizer Steps:** 130 steps
- **Cumulative Training Tokens:** 4,160 tokens
- **Validation Tokens Processed:** 320 tokens
- **Measured Throughput:** 267.80 tokens/second on Intel Pentium G2030 (2 threads)
- **Latest Training Loss:** 3.7823
- **Latest Validation Loss:** 4.2117 (Best: 4.1796)

---

## 5. Measured Capability Baseline (Phase 46)

- **Tamil Score:** 1.00 (Structured Benchmark QA) / **WARN** (Open-Domain Fluency)
- **English Score:** 1.00 (Structured Benchmark QA) / **WARN** (Open-Domain Fluency)
- **Tanglish Score:** 1.00 (Normalized input, strict Tamil-first output policy)
- **Reasoning Score:** 1.00 (Tiers 1–4 deterministic benchmarks) / **WARN** (General Emergent Reasoning)
- **Grounding Score:** 1.00 (Factual answer with evidence, safe refusal on missing facts)
- **Hallucination Refusal Score:** 1.00 ("ஆதாரம் இல்லை" on unknown information)
- **Composite Benchmark Score:** 1.000 / 1.000
- **Regression Status:** 349 / 349 PASSED (100% green across all repository evaluation suites)

---

## 6. Audit Conclusion

The repository is intact. Database immutability, Git baseline, and test suites are 100% verified. Phase 47 can proceed to Workstream 2 (Architecture Gap Analysis) without modifying code.
