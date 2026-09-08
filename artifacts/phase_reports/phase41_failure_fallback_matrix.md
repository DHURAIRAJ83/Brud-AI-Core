# PHASE 41 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Scope:** 27 Verified Failure, Edge-Case, and Fallback Scenarios  

---

| ID | Failure Condition | System Trigger | Severity | Expected Behavior | Fallback Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Missing checkpoint directory | `load_states` on non-existent path | BLOCK | Raises `ValueError` | Abort resume; alert operator |
| **SC-02** | Corrupted model weights | Checksum mismatch in `manifest.json`| BLOCK | Raises `ValueError` | Revert to previous good checkpoint |
| **SC-03** | Corrupted optimizer state | Non-loadable optimizer state dict | BLOCK | Raises `ValueError` | Revert to previous good checkpoint |
| **SC-04** | RAM exhaustion (<50MB) | Resource Guard poll fails | BLOCK | Safe pause / clean stop | Flush buffers; do not crash host |
| **SC-05** | Disk exhaustion (<200MB) | Resource Guard poll fails | BLOCK | Refuse checkpoint write | Abort checkpoint; preserve disk |
| **SC-06** | Validation divergence | $ValLoss > 2.5 \times RollingLoss$ | WARN | Flag `DIVERGING` status | Save best checkpoint; warn |
| **SC-07** | Step counter mismatch | Checkpoint trainer state corrupted | WARN | Fallback to latest valid step | Recalculate step from manifest |
| **SC-08** | Dataset corruption | Corrupt line in streaming JSONL | WARN | Skip corrupted record | Log line number; continue stream |
| **SC-09** | Benchmark data leakage | Fixture detected in training stream | BLOCK | `is_benchmark_fixture` blocks | Exclude item; update telemetry |
| **SC-10** | Prompt injection payload | Injected attack inside document | BLOCK | `assess_context_item_injection` | Quarantine item; refuse exec |
| **SC-11** | Secret in corpus | API key/token pattern detected | BLOCK | `detect_secrets` blocks | Quarantine item; update telemetry |
| **SC-12** | PII in corpus | Email/phone/Aadhaar detected | WARN | `redact_pii` masks text | Mask with typed placeholder |
| **SC-13** | Tanglish non-compliance | Output contains Latin script | BLOCK | Policy check fails | Force Tamil-first generation |
| **SC-14** | Hallucination on missing fact| Unsupported question submitted | WARN | Citation confidence low | Safe uncertainty refusal |
| **SC-15** | Cross-session memory leak | Target session differs from origin | BLOCK | UUID session query gate | Return empty history |
| **SC-16** | Canary traffic >10% | Traffic allocation out of bounds | BLOCK | Value validation error | Reject configuration change |
| **SC-17** | Canary error spike (>2%) | Rolling error rate tripwire | BLOCK | `emergency_rollback` triggers | Zero traffic; restore production |
| **SC-18** | Canary latency spike (>1s)| P95 latency tripwire | BLOCK | `emergency_rollback` triggers | Zero traffic; restore production |
| **SC-19** | Unapproved canary access | Public chat targets canary model | BLOCK | Resolver scope gate | Return 403 Forbidden / null |
| **SC-20** | Diagnostic scope leak | Public request targets admin scope | BLOCK | Resolver scope gate | Return 403 Forbidden / null |
| **SC-21** | AST security violation | Forbidden `eval`/`exec` introduced | BLOCK | Safety AST scanner fails | Terminate release build |
| **SC-22** | Path traversal attempt | Model path points to `/etc/passwd` | BLOCK | `resolve_confined_model_path` | Return `None` |
| **SC-23** | Corrupted tokenizer file | SPM model file missing/damaged | BLOCK | Import / Processor error | Abort tokenizer loading |
| **SC-24** | Model vocab mismatch | Tokenizer size != Model vocab | BLOCK | `verify_vocabulary_compatibility` | Refuse model initialization |
| **SC-25** | Database mutation attempt | DB file hash or size changes | BLOCK | Hash verification fails | Immediate hard halt |
| **SC-26** | Non-divisible attention | Head dimension not even | BLOCK | `BrudModelConfig.validate` | Reject architecture config |
| **SC-27** | Unhandled process kill | SIGTERM / SIGINT received | WARN | Checkpoint state intact on disk| Resume from latest checkpoint |
