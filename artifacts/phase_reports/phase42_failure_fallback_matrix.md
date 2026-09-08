# PHASE 42 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Scope:** 32 Comprehensive Failure, Edge-Case, and Fallback Scenarios  

---

| ID | Failure Condition | System Trigger | Severity | Expected Behavior | Fallback Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Checkpoint corruption | Checksum mismatch in `manifest.json` | BLOCK | Raises `ValueError` | Abort resume; alert operator |
| **SC-02** | Optimizer state corruption | Corrupted `optimizer_state.pt` | BLOCK | Raises `ValueError` | Revert to previous good checkpoint |
| **SC-03** | Scheduler state corruption | Corrupted `scheduler_state.pt` | BLOCK | Raises `ValueError` | Revert to previous good checkpoint |
| **SC-04** | RNG state corruption | Missing/damaged `rng_state.pt` | BLOCK | Raises `ValueError` | Revert to previous good checkpoint |
| **SC-05** | Dataset stream corruption | Corrupt record in streaming JSONL | WARN | Line parser intercepts error | Skip corrupted line; continue |
| **SC-06** | Tokenizer size mismatch | Vocab size != Model embedding dim | BLOCK | `verify_vocabulary_compatibility` | Reject model initialization |
| **SC-07** | Model architecture error | Head dimension not even (RoPE) | BLOCK | `BrudModelConfig.validate` | Reject architecture configuration |
| **SC-08** | Insufficient RAM (<50MB) | Resource Guard poll fails | BLOCK | Safe pause / clean stop | Flush buffers; do not crash host |
| **SC-09** | Insufficient disk (<200MB) | Resource Guard poll fails | BLOCK | Refuse checkpoint write | Abort checkpoint; preserve disk |
| **SC-10** | Training process interrupt | SIGTERM / SIGINT received | WARN | Checkpoint state intact on disk | Resume from latest valid step |
| **SC-11** | Validation loss divergence | $ValLoss > 2.5 \times RollingLoss$ | WARN | Flag `DIVERGING` status | Save best checkpoint; warn |
| **SC-12** | Loss explosion / NaN loss | `torch.isnan(loss) == True` | BLOCK | Terminate step update | Discard gradients; step back |
| **SC-13** | Checkpoint write failure | Disk write permission / full | BLOCK | Atomic temp-rename fails | Keep previous checkpoint intact |
| **SC-14** | Telemetry write failure | Telemetry file I/O error | WARN | Exception logged | Continue pretraining cycle |
| **SC-15** | Inference generation error | Forward pass exception | WARN | Causal loop caught | Return safe error message |
| **SC-16** | Malformed generation | Token sequence non-terminating | WARN | Max new tokens boundary | Force stop token append |
| **SC-17** | Hallucination regression | Fabricated facts on unknown queries | WARN | Evaluator flags score drop | Retain model in candidate stage |
| **SC-18** | Reasoning score drop | Regression below baseline score | WARN | Evaluator flags `REGRESSING` | Prevent candidate promotion |
| **SC-19** | Tamil fluency regression | Vowel marker / script distortion | WARN | Subword tokenizer check | Retain model in candidate stage |
| **SC-20** | English syntax regression | Format instruction violation | WARN | Instruction parser check | Retain model in candidate stage |
| **SC-21** | Tanglish policy violation | Output contains Latin script | BLOCK | Policy check fails | Force pure Tamil generation |
| **SC-22** | RAG prompt injection attack| Document contains hidden attack | BLOCK | `assess_context_item_injection` | Quarantine item; refuse exec |
| **SC-23** | Missing evidence in RAG | Context lacks supporting chunk | WARN | Citation confidence check | Return safe uncertainty message |
| **SC-24** | Memory cross-session leak | User A targets User B session | BLOCK | UUID session query gate | Return empty history |
| **SC-25** | Canary traffic > 1.0% | Requested traffic exceeds bound | BLOCK | `InternalCanaryController` error| Reject configuration change |
| **SC-26** | Canary error spike (> 2%) | Rolling error rate tripwire | BLOCK | `emergency_rollback` triggers | Zero traffic; restore production |
| **SC-27** | Canary latency spike (> 1s) | P95 latency tripwire | BLOCK | `emergency_rollback` triggers | Zero traffic; restore production |
| **SC-28** | Resource exhaustion in run | Process memory threshold breach | BLOCK | Resource Guard pause | Graceful process termination |
| **SC-29** | Missing admin approval | Canary ramp without sign-off | BLOCK | Controller gate blocks | Traffic remains strictly 0.0% |
| **SC-30** | Rollback failure attempt | Fallback model missing | BLOCK | Fallback integrity check | Abort rollback; alert admin |
| **SC-31** | Database mutation attempt | DB file hash or size changes | BLOCK | Hash verification fails | Immediate hard halt |
| **SC-32** | Public chat scope violation | Public query targets canary | BLOCK | Public resolver scope gate | Return 403 Forbidden / null |
