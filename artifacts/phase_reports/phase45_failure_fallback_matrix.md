# PHASE 45 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 21 — Failure and Fallback Matrix  
**Scope:** 42 Comprehensive Failure Scenarios Across Pretraining, Evaluation, Admin API, Tenant Isolation, and System  

---

| ID | Category | Failure Condition | Detection Mechanism | Immediate Action | Fallback | Severity | Recovery | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | Training | RAM exhaustion (<500MB) | Resource Guard poll | Halt pretraining gracefully | Save last checkpoint | HIGH | Throttle micro-batches | `phase45_training_telemetry.jsonl` |
| **02** | Training | Disk exhaustion (<1000MB) | Resource Guard poll | Halt pretraining gracefully | Save last checkpoint | HIGH | Clean old tmp checkpoints | Telemetry record |
| **03** | Training | CPU thread oversubscription | `torch.get_num_threads()` | Cap threads at 2 | `num_threads=2` bound | MEDIUM | Automatic thread clamp | Pretrainer init log |
| **04** | Training | Loss divergence (val spikes >2.0)| Convergence check | Halt run; mark divergent | Revert to best checkpoint | HIGH | Adjust learning rate | Convergence report |
| **05** | Training | Loss plateau (slope < 0.001) | Slope analysis | Log plateau warning | Continue or lr-step | LOW | Cosine scheduler decay | Convergence report |
| **06** | Training | Sudden process kill / SIGINT | Signal trap | Load latest checkpoint | Previous checkpoint | MEDIUM | Checkpoint manager resume | `trainer_state.json` |
| **07** | Checkpoint | Checkpoint weight corruption | SHA-256 vs manifest | Reject corrupted checkpoint | Revert to prior step | BLOCK | Operator alert | `manifest.json` check |
| **08** | Checkpoint | Optimizer state corruption | SHA-256 vs manifest | Reject checkpoint load | Revert to prior step | BLOCK | Re-init moments if needed | Manifest check |
| **09** | Checkpoint | Scheduler state corruption | SHA-256 vs manifest | Reject checkpoint load | Revert to prior step | BLOCK | Re-init scheduler | Manifest check |
| **10** | Checkpoint | RNG tensor corruption | SHA-256 vs manifest | Reject checkpoint load | Re-seed deterministic RNG | HIGH | Seed fallback | Manifest check |
| **11** | Dataset | Validation data leakage | Split index overlap | Terminate evaluation | Re-split dataset | BLOCK | Re-index splits | Dataset split check |
| **12** | Tokenizer | Vocab size gap vs model | `config.py` validator | Refuse training start | Re-align vocab dimension | BLOCK | Rebuild config/model | Architecture check |
| **13** | Architecture| RoPE head dimension odd | `micro_preset` validator | Raise `ValueError` | Force even dimension | BLOCK | Reconfigure heads | Config validation |
| **14** | Artifact | Post-training weight mutation | Hash verification | Invalidate prior evaluations | Mark REVIEW_REQUIRED | BLOCK | Re-evaluate model | Evaluation record |
| **15** | Capability | Tamil syllabic accuracy drop | Capability evaluator | Flag regression in report | Retain in candidate state | WARN | Continuous pretraining | Capability report |
| **16** | Capability | English syntax compliance drop | Capability evaluator | Flag regression in report | Retain in candidate state | WARN | Continuous pretraining | Capability report |
| **17** | Capability | Tanglish output policy breach | Policy validator | Block response; force Tamil | Pure Tamil response | HIGH | Transliteration engine | Policy check |
| **18** | Capability | Structural reasoning regression| 8-dimension benchmark | Flag regression in report | Retain in candidate state | WARN | Review pretraining data | Reasoning report |
| **19** | Capability | Hallucination on ungrounded query| Grounding check | Return uncertainty refusal | "ஆதாரம் இல்லை" | MEDIUM | Model prompt clamp | Grounding report |
| **20** | Security | RAG prompt injection attack | `assess_context_item_injection` | Quarantine item; block exec | Safe context only | BLOCK | Payload quarantine | Security log |
| **21** | Security | Memory cross-session leak | UUID session query gate | Return empty history | Fresh session state | BLOCK | Scope memory strictly | Session test |
| **22** | Security | Static AST: `eval` detected | AST scanner | Terminate build pipeline | Reject code addition | BLOCK | Refactor code cleanly | AST scan report |
| **23** | Security | Static AST: `exec` detected | AST scanner | Terminate build pipeline | Reject code addition | BLOCK | Refactor code cleanly | AST scan report |
| **24** | Security | Static AST: `subprocess` detected | AST scanner | Terminate build pipeline | Reject code addition | BLOCK | Refactor code cleanly | AST scan report |
| **25** | Security | Static AST: `os.system` detected | AST scanner | Terminate build pipeline | Reject code addition | BLOCK | Refactor code cleanly | AST scan report |
| **26** | Tenant | Tenant A reads Tenant B model | Tenant manager check | Raise `TenantAccessDeniedError` | Fail closed (404/403) | BLOCK | Log violation to audit | `phase45_admin_audit.jsonl` |
| **27** | Tenant | Tenant A reads Tenant B eval | Tenant manager check | Raise `TenantAccessDeniedError` | Fail closed (404/403) | BLOCK | Log violation to audit | Audit log |
| **28** | Tenant | Tenant A reads Tenant B telem | Tenant manager check | Return filtered tenant view | Empty view | BLOCK | Log violation to audit | Audit log |
| **29** | Tenant | Tenant A modifies Tenant B gov | Tenant manager check | Raise `TenantAccessDeniedError` | Deny modification | BLOCK | Log violation to audit | Audit log |
| **30** | Tenant | Missing tenant identifier | Context validator | Raise `TenantAccessDeniedError` | Reject request | BLOCK | Reject anonymous call | Audit log |
| **31** | Tenant | Forged admin context signature | `verify_signature()` | Raise `PermissionError` | Reject request | BLOCK | Revoke caller token | Audit log |
| **32** | RBAC | Auditor attempts model creation | RBAC manager check | Raise `RolePermissionDeniedError` | Deny operation | HIGH | Audit violation | Audit log |
| **33** | RBAC | Admin attempts canary approval | RBAC manager check | Raise `RolePermissionDeniedError` | Deny operation | HIGH | Audit violation | Audit log |
| **34** | RBAC | Unknown role in token | RBAC manager check | Raise `RolePermissionDeniedError` | Deny operation | BLOCK | Audit violation | Audit log |
| **35** | Admin API | Public Chat scope requested | Scope validator | Raise `ScopeAccessDeniedError` | Block access | BLOCK | Prevent public exposure | Audit log |
| **36** | Admin API | Arbitrary path traversal attempt| Path confinement check | Abort request | Confined path only | BLOCK | Reject traversal | Audit log |
| **37** | Admin API | Secret logged in audit log | Audit sanitizer | Replace with `[REDACTED]` | Sanitized record | HIGH | Automatic scrub | Audit log |
| **38** | Canary | Traffic set > 1.0% | Canary traffic validator | Raise `ValueError` | Retain current traffic | BLOCK | Enforce 1.0% cap | Canary log |
| **39** | Canary | Error rate tripwire (>2%) | Health monitor check | Trigger atomic rollback | `0.1.0-synthetic-test` | BLOCK | Traffic cut to 0.0% | Telemetry log |
| **40** | Canary | Latency tripwire (P95 > 1,000ms)| Health monitor check | Trigger atomic rollback | `0.1.0-synthetic-test` | BLOCK | Traffic cut to 0.0% | Telemetry log |
| **41** | System | Production database altered | Pre/post SHA-256 check | Immediate hard halt (`BLOCKED`) | Preserve baseline | BLOCK | Stop execution | SHA-256 record |
| **42** | System | Git HEAD or stash mutated | Git status check | Revert to baseline commit | `stash@{0}` intact | BLOCK | Halt phase | Git log |
