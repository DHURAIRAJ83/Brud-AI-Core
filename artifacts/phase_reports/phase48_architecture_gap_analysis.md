# PHASE 48 ARCHITECTURE GAP ANALYSIS

**Date:** 2026-08-29  
**Status:** GAP ANALYSIS COMPLETE  
**Workstream:** Workstream 1 — Architecture Audit & Gap Analysis  

---

## 1. Architectural Gap Analysis: Phase 47 vs Phase 48 Requirements

| System Requirement | Phase 47 Status | Phase 48 Gap / Required Implementation | Design Strategy |
| :--- | :--- | :--- | :--- |
| **Worker Execution Model** | Synchronous single-run pretrainer bounded by 15s execution | Needs background asynchronous worker engine with formal state machine (`QUEUED`, `INITIALIZING`, `TRAINING`, `CHECKPOINTING`, `PAUSED`, `RESOURCE_WAIT`, `RECOVERING`, `COMPLETED`, `FAILED`, `STOPPED`) | Create `core_model/training/phase48_training_worker.py` |
| **Worker Pool** | N/A | Needs hardware-aware pool managing execution without host contention (max 1 training worker on 2-core CPU) | Create `core_model/training/phase48_worker_pool.py` |
| **Training Queue** | In-memory batch list | Needs persistent disk-backed durable queue surviving process restarts with resumable partial jobs | Create `core_model/training/phase48_training_queue.py` |
| **Token Ledger** | Telemetry logs only | Needs append-only cryptographically verifiable global cumulative token ledger tracking cross-run accumulation | Create `core_model/training/phase48_token_ledger.py` |
| **Multi-Run Resume** | Single checkpoint reload | Needs cross-run worker-to-worker seamless resume (Worker A $\rightarrow$ Checkpoint $\rightarrow$ Terminate $\rightarrow$ Worker B resumes) | Verify step/token/loss/RNG continuity across independent workers |
| **Telemetry** | Single training telemetry log | Needs dual telemetry: worker lifecycle/queue (`phase48_worker_telemetry.jsonl`) & training (`phase48_training_telemetry.jsonl`), distinguishing RUN, JOB, and GLOBAL | Multi-tier structured JSONL logging |
| **Reasoning Evaluation** | 4-tier reasoning | Needs 5 levels (introducing Level 5: Abstract / Counterfactual Inference) | Extend benchmark battery with Level 5 reasoning |
| **Generalization Evaluation**| In-distribution benchmark | Needs unseen out-of-distribution evaluation data and classification (GAIN, FAILURE, NO_CHANGE, INCONCLUSIVE) | Add unseen generalization suite in evaluator |
| **Stochastic Evaluation** | Single deterministic probe pass | Needs repeated independent stochastic trials (mean, median, stddev, confidence intervals) with explicit `DETERMINISTIC` labels | Add stochastic evaluation harness |
| **Fine-Grained Capability Gain**| Overall gain only | Needs dimension-specific gain (Tamil, English, Tanglish, Reasoning, Grounding, Instruction, Overall) | Dimension-level breakdown in evaluator |
| **Loss vs Capability** | Uncorrelated observation | Needs formal classification (`CORRELATED`, `WEAKLY_CORRELATED`, `UNCORRELATED`, `INCONCLUSIVE`) | Add formal classification module |
| **Admin API Operations** | Model registry read/list | Needs training job control: `CREATE_JOB`, `START_JOB`, `PAUSE_JOB`, `RESUME_JOB`, `STOP_JOB`, `VIEW_STATUS`, `VIEW_TELEMETRY` | Extend `TenantAdminAPI` endpoints with full 7-step auth chain |
| **Crash & Corruption Recovery** | Baseline file check | Needs worker crash recovery and corrupt checkpoint fail-closed fallback | Comprehensive recovery simulation in dedicated tests |
