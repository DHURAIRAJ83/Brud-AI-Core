# Phase 50 Scale Gap Analysis & Bottleneck Decomposition

**Analysis Date**: 2026-08-29T16:50:00+05:30  
**Objective**: Identify and quantify the physical, architectural, data, and statistical bottlenecks preventing meaningful sovereign pretraining scale, and define defensible campaign parameters.

---

## 1. Concrete System Metrics & Measurements

| Metric ID | Dimension | Exact Measured Value | Verification Source |
|:---|:---|:---|:---|
| M-01 | Available Approved Corpus Tokens | ~8,680 unique tokens (~34,720 chars) | `data/document_sft_exports` + `data/corpus_exports` |
| M-02 | Unique Corpus Tokens | ~8,680 tokens across 334 approved records | Ingestion crawler inventory |
| M-03 | Current Training Exposure Tokens | 9,056 verified tokens | `artifacts/phase49_token_ledger.json` |
| M-04 | Current Validation Tokens | 768 tokens (256 tokens / window) | Checkpoint evaluation logs |
| M-05 | Current Test Tokens | Held-out 10% split in manifest | `Phase47CorpusExpander` |
| M-06 | Current Tokenizer Vocabulary | 64 tokens (Micro architecture) | `artifacts/.../checkpoint_step_218/config.json` |
| M-07 | Current Sequence Length | 256 tokens (context length) | `config.context_length = 256` |
| M-08 | Model Parameter Count | 22,688 parameters (100% trainable) | PyTorch `sum(p.numel())` check |
| M-09 | Checkpoint Directory Size | ~324 KB uncompressed | `artifacts/.../checkpoint_step_218/` |
| M-10 | Checkpoint Compressed Archive Size | ~267 KB gzip `.tar.gz` | `artifacts/checkpoint_archive/` |
| M-11 | Actual Measured CPU Throughput | 842.7 - 1,238.1 tokens/sec (mean ~1,023.7 tps) | Phase 49 Windows 1, 2, 3 telemetry |
| M-12 | Disk Required per Checkpoint | ~324 KB local HOT / ~267 KB COLD | Exact disk stat |
| M-13 | Disk Required for Retained Lineage | ~2.6 MB (10 intermediate archives) | Measured archive folder size |
| M-14 | Available Host RAM Headroom | 4,401 MB free (~4.3 GB available) | `/proc/meminfo` via ResourceGuard |
| M-15 | Available Host Disk Headroom | 108,116 MB free (~105.5 GB available) | `os.statvfs` via ResourceGuard |
| M-16 | Maximum Safe Continuous Runtime | Bounded to 30.0s slices / unlimited daemon | FSM ResourceGuard & Lease timeout |

---

## 2. Campaign Time Estimates by Target Tier

*Based on actual measured CPU throughput of 1,023.7 tokens/second on Intel Pentium G2030 (2 physical cores, 2 threads, no AVX).*  
*Note: These are mathematical estimates based on real measured rate, NOT claimed achievements.*

| Tier ID | Target Ceiling Tokens | Optimizer Steps (@ 32 tok/step) | Estimated Pure Compute Time | Estimated Wall-Clock Time (incl. ckpt/ledger) | Feasibility on Host |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **Tier A** | 25,000 tokens | ~781 steps | ~24.4 seconds | ~45 seconds | **HIGHLY FEASIBLE** |
| **Tier B** | 100,000 tokens | ~3,125 steps | ~97.7 seconds (~1.6 min) | ~2.5 minutes | **HIGHLY FEASIBLE** |
| **Tier C** | 250,000 tokens | ~7,812 steps | ~244.2 seconds (~4.1 min) | ~6.5 minutes | **FEASIBLE** |
| **Tier D** | 500,000 tokens | ~15,625 steps | ~488.4 seconds (~8.1 min) | ~13.0 minutes | **FEASIBLE** |
| **Tier E** | 1,000,000 tokens | ~31,250 steps | ~976.8 seconds (~16.3 min) | ~26.0 minutes | **FEASIBLE (Long Run)** |

---

## 3. Scale Bottleneck Decomposition

### Bottleneck 1: Approved Corpus Volume vs Training Exposure (CRITICAL)
* **Reality**: The total approved sovereign text in `data/document_sft_exports` (316 records) and `data/corpus_exports` (18 records) contains ~34,720 characters, yielding ~8,680 unique tokens.
* **Impact**: Reaching 100,000 or 500,000 tokens of *training exposure* requires multiple epochs over the approved corpus.
* **Distinction**: We must strictly separate **Unique Corpus Size** (~8.6K tokens) from **Training Exposure Tokens** (tokens fed through forward/backward optimizer passes).
* **Mitigation**:
  1. Compile an immutable dataset manifest (`phase50_dataset_manifest_v001.json`) containing all 334 approved records with deterministic train/val/test splits.
  2. Implement an epoch-aware dataloader with deterministic pseudo-random shuffling per epoch to achieve continuous multi-epoch sovereign training exposure without memorization leakage.

### Bottleneck 2: Benchmark Saturation & Anti-Saturation Probes
* **Reality**: Discrete keyword-matching evaluation suites can saturate to 1.0000 on structured reasoning prompts (e.g. `15 + 27 = 42`).
* **Impact**: A high score does not provide definitive evidence of open-domain generative capability.
* **Mitigation**:
  1. Create a held-out, immutable evaluation manifest (`phase50_evaluation_manifest.json`) containing unseen multi-turn, adversarial, distractor-laden, and counterfactual prompts.
  2. Implement anti-saturation probes with nuanced lexical substitutions, false premises, and length variations.
  3. Distinguish descriptive capability scores from inferential statistical significance.

### Bottleneck 3: Hardware Envelope & Single-Worker Constraints
* **Reality**: Intel Pentium G2030 (2 physical cores, 2 threads, no AVX/AVX2, ~5 GB RAM).
* **Enforcement**: Concurrency clamp (`max_training_workers = 1`, `torch_threads = 2`) must never be exceeded.
* **Mitigation**: Bounded window execution (e.g. 50–100 steps per window) with immediate memory reclamation (`gc.collect()`, PyTorch thread management) and atomic checkpoint archiving.

---

## 4. Architecture Reuse Map (Zero Unnecessary Duplication)

| Subsystem Requirement | Reused Phase 49 Component | Extensions for Phase 50 |
|:---|:---|:---|
| Continuous Training Daemon | `Phase49TrainingDaemon` | Campaign lifecycle coordination & auto-pause on convergence |
| Exclusive Process Lease | `ExclusiveTrainingLease` | Reused as-is (`artifacts/training_lease.lock`) |
| Persistent Queue | `Phase48TrainingQueue` | Reused as-is (`artifacts/phase49_queue.json`) |
| Append-Only Token Ledger | `Phase49TokenLedger` | Extended multi-epoch & campaign accounting fields |
| Checkpoint Lineage & Archiving | `Phase49CheckpointManager` | Multi-window pruning & retention of gold checkpoints |
| Ingestion & Governance | `Phase47CorpusExpander` & `Phase49IngestionScheduler` | Multi-source batch ingestion & manifest versioning |
| Capability Evaluator | `Phase48CapabilityEvaluator` | Extended with held-out open-domain & anti-saturation probes |
| Admin API | `TenantAdminAPI` | Reused with campaign status endpoints (zero promotion authority) |

---

## 5. Risk Assessment & Safe Fallbacks

| Risk ID | Risk Description | Severity | Automated Guard / Mitigation |
|:---:|:---|:---:|:---|
| R-01 | Model Overfitting on 8.6K Unique Tokens | HIGH | Real-time validation loss monitoring; early stopping if val loss diverges by >0.25 |
| R-02 | Benchmark Contamination | HIGH | 5-way contamination screening (`is_benchmark_contaminated`) on every ingested record |
| R-03 | Token Fabrication | CRITICAL | Token counts computed strictly from actual batch tensor sizes passed to optimizer |
| R-04 | Database Mutation | CRITICAL | Continuous pre- and post-run SHA-256 validation of `data/database/brud_ai.db` |
| R-05 | Public Chat Leakage | CRITICAL | Candidate models hard-locked to `is_public_chat_eligible = False`; 0% traffic |

---

## 6. Recommended Target Tier for Phase 50 Campaign

**Recommendation: TIER B (100,000 Tokens) with optional expansion to TIER C (250,000 Tokens).**

* **Rationale**:
  1. 100,000 tokens represents an **11x scale increase** over current cumulative exposure (9,056 tokens).
  2. At ~1,023 tokens/second, 100,000 tokens requires only ~2.5 minutes of wall-clock execution time, providing ample headroom within the host CPU envelope.
  3. It allows rigorous multi-checkpoint capability comparison across early (25K), intermediate (50K), and final (100K) checkpoints to measure empirical loss vs capability divergence.
  4. It strictly satisfies all hardware safety bounds without risking thermal throttling or host instability.
