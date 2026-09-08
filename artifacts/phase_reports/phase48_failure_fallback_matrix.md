# PHASE 48 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 28 — Failure & Fallback Safety Matrix  
**Scope:** 55 Comprehensive Failure Scenarios Across Queue, Worker Pool, Token Ledger, Checkpoint Lineage, Capability Evaluation, Security, and Multi-Tenant Admin API  

---

| ID | Category | Failure Condition | Detection Mechanism | Immediate Action | Fallback State | Severity | Recovery Mechanism | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | Queue | Production DB write attempt | Path validator check | Block operation | Fail closed | BLOCK | Restrict to independent JSON queue | `phase48_training_queue.py` |
| **02** | Queue | Corrupted `queue.json` | `json.JSONDecodeError` | Return empty or last valid | Refuse corrupted jobs | HIGH | Recover from `.tmp` backup | Queue reader try/except |
| **03** | Queue | Duplicate job submission | Job ID collision check | Raise `ValueError` | Reject submission | MEDIUM | Keep original job intact | Queue unit test |
| **04** | Queue | Job cancelled while running | Status poll | Signal worker shutdown | Transition `CANCELLED` | LOW | Clean worker exit | Worker shutdown flag |
| **05** | Queue | Job paused while running | Status poll | Save checkpoint | Transition `PAUSED` | LOW | State preserved for resume | Queue update progress |
| **06** | Worker | Illegal state: QUEUED -> TRAINING| FSM transition check | Raise `WorkerTransitionError` | Remain in QUEUED | BLOCK | Enforce FSM path | Worker transition test |
| **07** | Worker | Illegal state: COMPLETED -> TRAIN| FSM transition check | Raise `WorkerTransitionError` | Remain in COMPLETED | BLOCK | Enforce terminal state | Worker transition test |
| **08** | Worker | RAM < 500 MB threshold | ResourceGuard check | Halt training loop | Transition `RESOURCE_WAIT` | HIGH | Emergency checkpoint flush | Telemetry emission |
| **09** | Worker | Disk < 1,000 MB threshold | ResourceGuard check | Halt training loop | Transition `RESOURCE_WAIT` | HIGH | Emergency checkpoint flush | Telemetry emission |
| **10** | Worker | Host CPU contention (>2 threads) | `torch.get_num_threads()` | Enforce clamp to 2 threads | Bound to 2 threads | MEDIUM | Worker initialization clamp | Worker init |
| **11** | Worker | Bounded time limit reached | Wall-clock timer check | Finish step, save checkpoint | Transition `STOPPED` | LOW | Normal slice completion | Training slice loop |
| **12** | Worker | Process SIGINT / SIGTERM | Signal handler trap | Save checkpoint atomically | Clean shutdown | HIGH | Exit without data loss | Worker signal trap |
| **13** | Worker | Optimizer loss NaN / Inf | Loss validity check | Halt training step | Revert to previous checkpoint | BLOCK | Lower learning rate | Trainer check |
| **14** | Worker | Weight gradient explosion | `clip_grad_norm_` | Clamp norm to 1.0 | Stable gradients | MEDIUM | Gradient clipping active | Training step |
| **15** | Worker | Validation loss divergence | Rolling loss monitor | Flag divergence in telemetry | Revert to `checkpoint_best` | HIGH | Fallback to best model | Telemetry record |
| **16** | Pool | Attempt to run >1 training worker| Hardware-aware clamp | Clamp `max_workers = 1` | 1 active worker only | BLOCK | Pool initialization clamp | `phase48_worker_pool.py` |
| **17** | Pool | Dispatch request when busy | Active worker check | Return None | Queue remains untouched | LOW | Await worker release | Pool dispatch method |
| **18** | Pool | Dispatch request on empty queue | Fetch next job check | Return None | No-op | LOW | Idle until job submitted | Pool dispatch method |
| **19** | Pool | Worker crash during execution | Process monitor check | Clear active worker pointer | Mark job PAUSED/RECOVERING | HIGH | Restart fresh worker | Pool error handling |
| **20** | Ledger | Replayed `run_id` submission | Run ID index check | Raise `TokenLedgerError` | Fail closed | BLOCK | Prevent duplicate tokens | Ledger append method |
| **21** | Ledger | Tampered token count in ledger | Chain audit check | Verify returns False | Fail closed | BLOCK | Alert administrator | Ledger verify method |
| **22** | Ledger | Broken SHA-256 hash link | Block hash check | Verify returns False | Fail closed | BLOCK | Alert administrator | Ledger verify method |
| **23** | Ledger | Missing genesis block | File empty check | Re-initialize genesis | Valid genesis block | HIGH | Genesis initialization | Ledger init |
| **24** | Ledger | Negative run tokens submitted | Invariant assertion | Reject block addition | Fail closed | BLOCK | Enforce positive delta | Ledger append check |
| **25** | Ledger | Mathematical token jump | Cumulative sum check | Verify returns False | Fail closed | BLOCK | Enforce sum continuity | Ledger verify method |
| **26** | Checkpoint | Missing `model_state.pt` | File existence check | Raise `CheckpointLineageError` | Fail closed | BLOCK | Revert to prior checkpoint | Lineage verify check |
| **27** | Checkpoint | Corrupted `optimizer_state.pt` | SHA-256 hash mismatch | Raise `CheckpointLineageError` | Fail closed | BLOCK | Revert to prior checkpoint | Lineage verify check |
| **28** | Checkpoint | Corrupted `scheduler_state.pt` | SHA-256 hash mismatch | Raise `CheckpointLineageError` | Fail closed | BLOCK | Revert to prior checkpoint | Lineage verify check |
| **29** | Checkpoint | Corrupted `rng_state.pt` | SHA-256 hash mismatch | Raise `CheckpointLineageError` | Fail closed | BLOCK | Revert to prior checkpoint | Lineage verify check |
| **30** | Checkpoint | Missing `manifest.json` | File existence check | Raise `CheckpointLineageError` | Fail closed | BLOCK | Revert to prior checkpoint | Lineage verify check |
| **31** | Checkpoint | Broken parent checkpoint hash | Ancestry link check | Raise `CheckpointLineageError` | Fail closed | BLOCK | Revert to prior checkpoint | Lineage verify check |
| **32** | Checkpoint | Attempt to delete old checkpoint| Policy invariant check | Refuse deletion | Preserve immutable DAG | BLOCK | Lock directory permissions | Lineage policy |
| **33** | Checkpoint | Partial write during crash | Manifest verification | Reject incomplete folder | Revert to prior valid | BLOCK | Load previous manifest | Lineage verify check |
| **34** | Resume | Step counter reset to 0 | `trainer_state.json` check | Enforce step from state | Exact step continuity | BLOCK | Load step from JSON | Worker resume check |
| **35** | Resume | Optimizer moments zeroed | State dict reload | Load PyTorch opt dict | Exact momentum recovery | BLOCK | Load optimizer state | Worker resume check |
| **36** | Resume | Scheduler cycle reset | State dict reload | Load PyTorch sched dict | Exact LR recovery | BLOCK | Load scheduler state | Worker resume check |
| **37** | Capability | Benchmark ceiling detected | Baseline score >= 0.95 | Flag `status = CEILING` | Report 0 gain | LOW | Use harder benchmarks | Evaluator gain check |
| **38** | Capability | Insufficient token delta (<1000)| Denominator check | Flag `INCONCLUSIVE` | No division performed | LOW | Await token accumulation | Evaluator gain check |
| **39** | Capability | High variance across trials | StdDev calculation | Report confidence interval | Transparent variance | MEDIUM | Increase trial count | Stochastic evaluator |
| **40** | Capability | Tamil factual QA regression | Benchmark evaluation | Flag regression in report | Retain candidate | WARN | Further training slices | Capability snapshot |
| **41** | Capability | English syntax regression | Benchmark evaluation | Flag regression in report | Retain candidate | WARN | Further training slices | Capability snapshot |
| **42** | Capability | Tanglish response with Latin | Regex `[a-zA-Z]` check | Penalize score to 0.5/0.0 | Enforce pure Tamil | HIGH | Output filter clamp | Policy check |
| **43** | Capability | Level 4 missing-fact hallucination| Keyword check | Demand "ஆதாரம் இல்லை" | Refusal pass | MEDIUM | Prompt grounding clamp | Evaluator Level 4 |
| **44** | Capability | Level 4 false premise acceptance| Keyword check | Demand "தவறான அனுமானம்" | Correction pass | MEDIUM | Prompt grounding clamp | Evaluator Level 4 |
| **45** | Capability | Level 5 counterfactual failure | Keyword check | Score 0.0 on Level 5 | Flag reasoning limit | MEDIUM | Advanced curriculum | Evaluator Level 5 |
| **46** | Security | RAG prompt injection in training| Context screening | Quarantine item | Clean context only | BLOCK | Exclude from split | Expander quarantine |
| **47** | Security | AST scan: `eval` detected | AST parser scan | Build failure | Zero tolerance | BLOCK | Code refactor | AST scan test |
| **48** | Security | AST scan: `exec` detected | AST parser scan | Build failure | Zero tolerance | BLOCK | Code refactor | AST scan test |
| **49** | Security | AST scan: `os.system` detected | AST parser scan | Build failure | Zero tolerance | BLOCK | Code refactor | AST scan test |
| **50** | Security | AST scan: `subprocess` in model | AST parser scan | Build failure | Zero tolerance | BLOCK | Code refactor | AST scan test |
| **51** | Admin API | Cross-tenant training job access| Tenant manager check | Raise `TenantAccessDeniedError` | Fail closed | BLOCK | Redacted audit event | Admin API check |
| **52** | Admin API | Public Chat scope requested | Scope validator check | Raise `ScopeAccessDeniedError` | Reject request | BLOCK | Redacted audit event | Admin API check |
| **53** | Admin API | `PROMOTE_CANDIDATE` requested | Endpoint existence check | Endpoint does not exist | Reject request | BLOCK | Multi-person governance | Mandatory Correction 6 |
| **54** | Governance | Candidate auto-promoted | Scope router check | `is_public_chat_eligible = False` | Public Chat isolated | BLOCK | Hard isolation gate | Quality gate 41 |
| **55** | Persistence| Production database modified | SHA-256 check | Immediate test failure | Abort Phase 48 | BLOCK | Restore from backup | Baseline check |
