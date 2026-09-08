# PHASE 43 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Scope:** 36 Comprehensive Failure, Edge-Case, and Fallback Scenarios  

---

| ID | Failure Condition | Detection Mechanism | Severity | System Response | Fallback Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Checkpoint weight corruption | Checksum mismatch in `manifest.json` | BLOCK | `verify_checkpoint_integrity` fails | Abort promotion; alert admin |
| **SC-02** | Optimizer state corruption | Checksum mismatch in `optimizer_state.pt` | BLOCK | Verification fails | Revert to previous good checkpoint |
| **SC-03** | Scheduler state corruption | Checksum mismatch in `scheduler_state.pt` | BLOCK | Verification fails | Revert to previous good checkpoint |
| **SC-04** | RNG state corruption | Checksum mismatch in `rng_state.pt` | BLOCK | Verification fails | Revert to previous good checkpoint |
| **SC-05** | Extraneous file in checkpoint | Extra `.bin` or `.tmp` file found | BLOCK | Unexpected file detected | Reject checkpoint integrity |
| **SC-06** | Missing checkpoint file | Required `config.json` absent | BLOCK | File existence check fails | Reject checkpoint integrity |
| **SC-07** | Model/Tokenizer vocab gap | Vocab size mismatch detected | BLOCK | `verify_model_tokenizer_compatibility` | Refuse promotion |
| **SC-08** | Missing special token | `<system>` token ID missing | BLOCK | Token map validation fails | Refuse promotion |
| **SC-09** | Token ID mismatch | `<eos>` assigned wrong integer ID | BLOCK | Token ID comparison fails | Refuse promotion |
| **SC-10** | Architecture misconfiguration| RoPE head dimension odd | BLOCK | `BrudModelConfig.validate` | Reject model config |
| **SC-11** | Dataset provenance gap | Dataset manifest hash mismatch | BLOCK | Lineage verification fails | Refuse promotion |
| **SC-12** | Validation data leakage | Record overlap in train/val splits | BLOCK | Split intersection test | Halt promotion immediately |
| **SC-13** | Tamil fluency regression | Benchmark QA score degrades | WARN | Capability evaluator flags drop | Retain model in candidate stage |
| **SC-14** | English syntax regression | Instruction following violates bounds| WARN | Evaluator flags format error | Retain model in candidate stage |
| **SC-15** | Tanglish policy violation | Output contains English/Latin script | BLOCK | Policy check fails | Force pure Tamil generation |
| **SC-16** | Reasoning regression | Score drops below baseline | WARN | Progression evaluator flags drop| Prevent candidate promotion |
| **SC-17** | Hallucination on missing fact| Unsupported answer generated | WARN | Confidence check flags fact | Return safe uncertainty message |
| **SC-18** | RAG prompt injection attack | Malicious payload in document | BLOCK | `assess_context_item_injection` | Quarantine item; refuse exec |
| **SC-19** | Memory cross-session leak | Cross-session token access attempt | BLOCK | UUID session query gate | Return empty history |
| **SC-20** | AST security violation | Forbidden `eval`/`exec` found | BLOCK | Static AST scan fails | Terminate release build |
| **SC-21** | Path traversal attempt | Checkpoint path traverses `/etc` | BLOCK | Path confinement check | Abort inventory scan |
| **SC-22** | Inference latency spike | P95 latency > 1,000 ms | BLOCK | Telemetry monitor tripwire | Trigger atomic rollback |
| **SC-23** | Model load failure | Weight loading throws exception | BLOCK | Try/except in loader | Fallback to known-good model |
| **SC-24** | Secret inclusion in bundle | `.key` or password file in bundle | BLOCK | Bundle security scan | Immediate packaging abort |
| **SC-25** | Database inclusion in bundle | `.db` or `.sqlite` file in bundle | BLOCK | Bundle security scan | Immediate packaging abort |
| **SC-26** | Shadow mode leak | User sees shadow model output | BLOCK | Router output isolation | Bar shadow responses |
| **SC-27** | Public chat scope violation | Public query targets unapproved model| BLOCK | Public resolver scope gate | Return 403 Forbidden / null |
| **SC-28** | Missing administrative sign-off| Promotion without approvals | BLOCK | Governance check fails | Retain in REVIEW_REQUIRED |
| **SC-29** | Duplicate admin approval | Admin 1 signs twice | BLOCK | Admin ID uniqueness check | Reject duplicate approval |
| **SC-30** | Artifact mutation post-approval| File hash modified after sign-off | BLOCK | Hash verification fails | Invalidate all approvals |
| **SC-31** | Rollout stage jumping | Jumping 0% to 10% directly | BLOCK | Stage index validator | Reject stage change |
| **SC-32** | Canary error rate spike (>2%)| Rolling error rate breach | BLOCK | Automated tripwire | Trigger atomic rollback |
| **SC-33** | Atomic rollback failure | Fallback model missing | BLOCK | Fallback integrity check | Alert operator; keep candidate |
| **SC-34** | Candidate artifact deletion | Artifacts deleted on rollback | BLOCK | Non-destructive rollback rule | Preserve all artifacts |
| **SC-35** | Production DB mutation | DB file hash or size changes | BLOCK | Pre/Post SHA-256 verification | Immediate hard halt |
| **SC-36** | Git working tree mutation | Stash or HEAD mutated | BLOCK | Git status check | Revert to original HEAD |
