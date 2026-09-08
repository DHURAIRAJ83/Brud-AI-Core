# PHASE 47 ARCHITECTURE GAP ANALYSIS

**Date:** 2026-08-29  
**Role:** Principal ML Systems Engineer, AI Safety Engineer, & Production Reliability Engineer  
**Scope:** Determining what prevents Brud AI from reaching genuine large-scale sovereign capability qualification without inventing fake metrics or ungrounded infrastructure.  

---

## 1. Executive Summary

Phase 46 successfully proved that the continuous pretraining loop, CPU thread bounding, AdamW optimization, token accounting, checkpoint integrity, and benchmark evaluation mechanisms function correctly.

However, three primary architectural and operational bottlenecks currently prevent the model candidate from advancing beyond `Capability = WARN` to genuine sovereign capability qualification:

1. **Corpus Accumulation Bottleneck:** The active dataset manifest in Phase 46 was constrained to 11 accepted records (281 tokens) from 4 shards. The repository contains extensive approved datasets (`data/document_sft_exports/`, `data/dataset_exports/`) that have not yet been unified, validated, normalized, and bound into an expanded multi-source dataset manifest.
2. **Pretraining Orchestration & Lineage Bottleneck:** Checkpoints were previously indexed purely by local directories without an explicit state machine or cryptographically linked ancestor graph (`parent_checkpoint_hash` $\rightarrow$ `child_checkpoint_hash`). When long-duration training is resumed, it must verify the unbroken chain of custody across optimizer, scheduler, RNG, configuration, and dataset manifests.
3. **Capability Conflation Bottleneck:** High scores on deterministic 4-tier reasoning benchmarks and fixed-vocabulary questions were conflated with general artificial capability. Phase 47 must strictly disentangle `structured_benchmark_score` from `open_domain_capability_score` across 16 formal dimensions, protecting the gain-per-token metric with denominator guards.

---

## 2. Detailed Technical Gap Breakdown

### Gap 1: Corpus Scale & Multi-Source Provenance
- **Current State:** `Phase46CorpusScaler` processes raw shards independently without persistent multi-source discovery, cross-shard deduplication, or split accounting (train/validation/test).
- **Required Architecture:** `Phase47CorpusExpander` (`core_model/corpus/phase47_corpus_expander.py`):
  - Systematic crawler discovering all sovereign sources in `data/corpus_exports/`, `data/document_sft_exports/`, `data/approved/`.
  - Provenance tracking per source: `source_id`, `source_path`, `source_hash`.
  - Strict Tamil-safe Unicode normalization (retaining combining marks, rejecting orphan modifiers).
  - Multi-tier deduplication (exact SHA-256 and near-duplicate character n-gram Jaccard).
  - 5-layer contamination defense preventing any evaluation fixtures from entering training or validation splits.
  - Deterministic train/validation/test split generation (e.g. 80/10/10).
  - Immutable manifest generation (`phase47_dataset_manifest.json`) binding metadata to a root hash.

### Gap 2: Long-Run Orchestration & State Machine
- **Current State:** Pretraining runs were invoked synchronously with static bounds. Interruptions required manual script invocation.
- **Required Architecture:** `Phase47LongRunOrchestrator` (`core_model/training/phase47_long_run_orchestrator.py`):
  - Explicit finite-state machine:
    `READY` $\rightarrow$ `TRAINING` $\rightarrow$ `CHECKPOINTING` $\rightarrow$ `PAUSED` $\rightarrow$ `RESUMING` $\rightarrow$ `TRAINING` $\rightarrow$ `COMPLETED`.
  - Explicit failure states: `RESOURCE_LIMIT`, `TIME_LIMIT`, `CHECKPOINT_FAILURE`, `INTEGRITY_FAILURE`, `DATA_FAILURE`, `RECOVERY_FAILURE`.
  - Checkpoint discovery, latest-checkpoint resumption, and best-validation checkpoint isolation.
  - Total cumulative step, cumulative token, and duration tracking.
  - Safe interruption handling with immediate state flushing to disk.

### Gap 3: Immutable Checkpoint Lineage
- **Current State:** Checkpoints in `artifacts/phase46_checkpoints/` have local manifest checksums but lack parent-child pointer bindings.
- **Required Architecture:** `Phase47CheckpointLineage` (`core_model/training/phase47_checkpoint_lineage.py`):
  - Directed acyclic graph (DAG) structure where every checkpoint records `parent_checkpoint_hash`.
  - Verification that no ancestor checkpoint is modified, deleted, or orphaned.
  - Full state encapsulation: model weights, optimizer moments, scheduler state, RNG tensor, trainer state, config, tokenizer hash, dataset manifest hash.

### Gap 4: Multi-Dimensional Capability Benchmarking
- **Current State:** Evaluator tested 8 dimensions with basic string matching.
- **Required Architecture:** `Phase47CapabilityBenchmark` (`core_model/evaluation/phase47_capability_benchmark.py`):
  - 16 required evaluation dimensions:
    1. Tamil language capability
    2. English language capability
    3. Tanglish input normalization
    4. Tamil-first response policy
    5. Arithmetic
    6. Ordering
    7. Classification
    8. Contradiction detection
    9. Premise tracking
    10. Deductive reasoning
    11. Sequential planning
    12. Multi-step reasoning
    13. Grounding
    14. Hallucination refusal
    15. False-premise correction
    16. Long-context consistency
  - Explicit separation: `structured_benchmark_score` vs `open_domain_capability_score`.
  - Denominator-protected Capability Gain Per Token ($\Delta \text{tokens} > 0$ and $\Delta \text{tokens} \ge 100$).

---

## 3. Preservation of Verified Infrastructure

The following established components will be preserved and leveraged without regression:
- `ResourceGuard` (`core_model/training/phase45_capability_scaler.py`): CPU/RAM/Disk bounds.
- `ProductionIngestionPipeline` / `detect_language`: Proven language classifier.
- `detect_pii`, `redact_pii`, `detect_secrets`: Security filtering primitives.
- `assess_context_item_injection`: RAG and context quarantine.
- `TenantAdminAPI`: 7-step verification chain and strict fail-closed boundary.
- Database immutability and Public Chat isolation (`is_public_chat_eligible = False`).
