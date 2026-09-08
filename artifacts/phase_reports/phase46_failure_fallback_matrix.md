# PHASE 46 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 23 — Failure and Fallback Matrix  
**Scope:** 42 Comprehensive Failure Scenarios Across Corpus Scaling, Pretraining, Evaluation, Security, and Release  

---

| ID | Category | Failure Condition | Detection Mechanism | Immediate Action | Fallback State | Severity | Recovery | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | Corpus | Orphan Tamil combining mark | `normalize_tamil_safe` | Raise `TamilNormalizationError` | Reject record | HIGH | Skip corrupt text | `phase46_corpus_scaler.py` |
| **02** | Corpus | Combining mark count shift | Before/after mark audit | Raise `TamilNormalizationError` | Reject record | HIGH | Skip corrupt text | Scaler audit log |
| **03** | Corpus | Benchmark prompt in corpus | `is_benchmark_contaminated` | Drop record | Quarantine record | BLOCK | Strip from training split | Dataset manifest |
| **04** | Corpus | Normalized benchmark leak | Normalized string match | Drop record | Quarantine record | BLOCK | Strip from training split | Dataset manifest |
| **05** | Corpus | Cryptographic benchmark leak | SHA-256 hash match | Drop record | Quarantine record | BLOCK | Strip from training split | Dataset manifest |
| **06** | Corpus | Near-duplicate benchmark | 3-gram Jaccard >= 0.70 | Drop record | Quarantine record | BLOCK | Strip from training split | Dataset manifest |
| **07** | Corpus | PII (Phone/Email) in record | `detect_pii` | `redact_pii` | Redacted text | MEDIUM | Log redacted count | Manifest telemetry |
| **08** | Corpus | Secret in training record | `detect_secrets` | Drop record entirely | Exclude record | BLOCK | Log secret finding | Manifest telemetry |
| **09** | Corpus | Prompt injection in record | `assess_context_item_injection` | Quarantine item | Exclude record | BLOCK | Log quarantined count| Manifest telemetry |
| **10** | Corpus | Exact duplicate document | SHA-256 exact hash set | Drop duplicate record | First occurrence only | LOW | Increment duplicate count | Manifest telemetry |
| **11** | Corpus | Near-duplicate document | 5-gram Jaccard >= 0.85 | Drop near-duplicate | Primary record only | LOW | Increment near-dup count | Manifest telemetry |
| **12** | Training | RAM below 500 MB threshold | ResourceGuard memory poll | Terminate pretraining loop | Save last checkpoint | HIGH | Micro-batch throttle | `phase46_training_telemetry.jsonl` |
| **13** | Training | Disk below 1,000 MB threshold | ResourceGuard disk poll | Terminate pretraining loop | Save last checkpoint | HIGH | Clean old tmp shards | Telemetry record |
| **14** | Training | CPU threads > 2 | `torch.get_num_threads()` | Enforce clamp | `num_threads=2` bound | MEDIUM | Clamp worker threads | Pretrainer init log |
| **15** | Training | Time bound reached (15.0s) | Wall-clock timer check | Gracefully complete step | Persist state | LOW | Transparently report bound | Training run report |
| **16** | Training | Target tokens / steps unmet | Accounting loop condition | Report actual progress | Transparent reporting | LOW | State IN_PROGRESS | Token accounting report |
| **17** | Training | Sudden process kill (SIGKILL)| OS signal trap | Reload from last checkpoint | Resumed state | HIGH | Checkpoint manager resume | `trainer_state.json` |
| **18** | Training | Loss divergence (val spikes >2.0)| Convergence check | Halt run; flag divergence | Revert to `checkpoint_best`| HIGH | Lower learning rate | Convergence report |
| **19** | Checkpoint | Model state weight corruption | SHA-256 vs manifest | Reject checkpoint resume | Prior valid step | BLOCK | Alert administrator | `manifest.json` check |
| **20** | Checkpoint | Optimizer moments corrupted | SHA-256 vs manifest | Reject checkpoint resume | Prior valid step | BLOCK | Re-init optimizer if needed | Manifest check |
| **21** | Checkpoint | Scheduler state corrupted | SHA-256 vs manifest | Reject checkpoint resume | Prior valid step | BLOCK | Reset schedule | Manifest check |
| **22** | Checkpoint | RNG state corrupted | SHA-256 vs manifest | Reject checkpoint resume | Deterministic seed | HIGH | Re-seed deterministic RNG| Manifest check |
| **23** | Checkpoint | Missing `manifest.json` | File existence check | Reject directory load | Fail closed | BLOCK | Require valid manifest | Checkpoint verify |
| **24** | Evaluation | Zero delta tokens in gain calc | Denominator protection | Report `INCONCLUSIVE` | No division performed | LOW | Await token accumulation| Capability telemetry |
| **25** | Evaluation | Negative delta tokens in gain | Denominator protection | Report `INCONCLUSIVE` | No division performed | LOW | Checkpoint sequence fix | Capability telemetry |
| **26** | Evaluation | Sub-100 delta tokens in gain | Denominator protection | Report `INCONCLUSIVE` | No division performed | LOW | Await token accumulation| Capability telemetry |
| **27** | Evaluation | Spurious gain claim without tokens| Statistical threshold check| Flag `statistically_meaningful = False` | Transparent report | MEDIUM | Require >=1000 tokens | Gain metric record |
| **28** | Capability | Tamil factual QA regression | Benchmark evaluator | Flag regression in report | Retain candidate state | WARN | Additional pretraining | Capability report |
| **29** | Capability | English syntax regression | Benchmark evaluator | Flag regression in report | Retain candidate state | WARN | Additional pretraining | Capability report |
| **30** | Capability | Tanglish response in English | Output policy check | Fail policy test (score 0.0)| Force pure Tamil | HIGH | Output filter clamp | Policy check |
| **31** | Capability | Hallucination on missing facts | Epistemic Tier 4 check | Output "ஆதாரம் இல்லை" | Safe uncertainty refusal| MEDIUM | Model prompt clamp | Grounding report |
| **32** | Capability | Acceptance of false premise | Epistemic Tier 4 check | Output "தவறான அனுமானம்"| Premise correction | MEDIUM | Model prompt clamp | Grounding report |
| **33** | Security | RAG prompt injection attempt | Injection screening | Quarantine item | Clean context only | BLOCK | Security quarantine | Security log |
| **34** | Security | UUID session cross-talk | Session lookup isolation | Return empty context | Fresh session | BLOCK | Session boundary check | Session test |
| **35** | Security | AST scan: `eval` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **36** | Security | AST scan: `exec` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **37** | Security | AST scan: `subprocess` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **38** | Security | AST scan: `os.system` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **39** | Admin API | Cross-tenant access attempt | Tenant manager check | Raise `TenantAccessDeniedError` | Fail closed | BLOCK | Audit log event | `phase46_admin_audit.jsonl` |
| **40** | Admin API | Public Chat scope requested | Scope validator check | Raise `ScopeAccessDeniedError` | Reject request | BLOCK | Audit log event | Audit log |
| **41** | Persistence| Production database modified | SHA-256 mismatch | Immediate execution halt | Restore from backup | BLOCK | Halt Phase 46 | Database check |
| **42** | Git | Baseline commit or stash lost | Git status check | Immediate execution halt | Checkout baseline | BLOCK | Halt Phase 46 | Git status check |
