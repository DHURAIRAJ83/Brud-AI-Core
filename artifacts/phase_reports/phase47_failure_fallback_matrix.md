# PHASE 47 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 23 — Failure and Fallback Matrix  
**Scope:** 52 Comprehensive Failure Scenarios Across Corpus Expansion, Training Orchestration, Lineage, Evaluation, Security, and Governance  

---

| ID | Category | Failure Condition | Detection Mechanism | Immediate Action | Fallback State | Severity | Recovery | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | Corpus | Orphan Tamil combining mark | `normalize_tamil_safe` | Raise `TamilNormalizationError` | Reject record | HIGH | Exclude corrupt string | `phase47_corpus_expander.py` |
| **02** | Corpus | Unicode combining count shift| Normalization auditor | Raise `TamilNormalizationError` | Reject record | HIGH | Exclude corrupt string | Expander unit test |
| **03** | Corpus | Unapproved source file | Approval gate | Reject record | Omit from splits | HIGH | Require explicit approval | Expander telemetry |
| **04** | Corpus | Unauthorized rights status | `is_approved_for_training` | Reject record | Omit from splits | HIGH | Require verified rights | Expander telemetry |
| **05** | Corpus | Benchmark prompt exact leak | 5-way screen layer 1 | Drop record | Exclude record | BLOCK | Strip from training split| Manifest telemetry |
| **06** | Corpus | Benchmark prompt norm leak | 5-way screen layer 2 | Drop record | Exclude record | BLOCK | Strip from training split| Manifest telemetry |
| **07** | Corpus | Benchmark prompt hash leak | 5-way screen layer 3 | Drop record | Exclude record | BLOCK | Strip from training split| Manifest telemetry |
| **08** | Corpus | Benchmark near-duplicate | 3-gram Jaccard >= 0.70 | Drop record | Exclude record | BLOCK | Strip from training split| Manifest telemetry |
| **09** | Corpus | PII (Phone/Email) in record | `detect_pii` | `redact_pii` | Redacted text | MEDIUM | Log redacted count | Manifest telemetry |
| **10** | Corpus | Secret in training record | `detect_secrets` | Drop record entirely | Exclude record | BLOCK | Log secret finding | Manifest telemetry |
| **11** | Corpus | Context prompt injection | `assess_context_item_injection` | Quarantine record | Exclude record | BLOCK | Log quarantined count | Manifest telemetry |
| **12** | Corpus | Exact duplicate document | SHA-256 hash set | Drop duplicate record | Primary record only | LOW | Increment duplicate count| Manifest telemetry |
| **13** | Corpus | Near-duplicate document | 5-gram Jaccard >= 0.85 | Drop near-duplicate | Primary record only | LOW | Increment near-dup count | Manifest telemetry |
| **14** | Corpus | Corrupted JSONL line | `json.JSONDecodeError` | Drop line | Skip line | LOW | Continue stream | Expander loop |
| **15** | Training | RAM below 500 MB threshold | ResourceGuard memory poll | Halt pretraining loop | Transition RESOURCE_LIMIT| HIGH | Emergency checkpoint save| `phase47_training_telemetry.jsonl` |
| **16** | Training | Disk below 1,000 MB threshold| ResourceGuard disk poll | Halt pretraining loop | Transition RESOURCE_LIMIT| HIGH | Emergency checkpoint save| Telemetry record |
| **17** | Training | CPU threads > 2 | `torch.get_num_threads()` | Enforce clamp | `num_threads=2` bound | MEDIUM | Clamp worker threads | Orchestrator init |
| **18** | Training | Time bound reached (15.0s) | Wall-clock timer check | Gracefully finish step | Transition TIME_LIMIT | LOW | Report TIME_LIMIT bound | Training run report |
| **19** | Training | Target steps unmet in bound | Step counter check | Report actual progress | Transparent reporting | LOW | State TIME_LIMIT | Token accounting report |
| **20** | Training | Sudden process kill (SIGKILL)| OS signal trap | Resume from last checkpoint | Resumed state | HIGH | Checkpoint manager resume | `trainer_state.json` |
| **21** | Training | Loss divergence (val spikes >2.0)| Convergence check | Halt run; flag divergence | Revert to `checkpoint_best`| HIGH | Lower learning rate | Convergence report |
| **22** | Checkpoint | Model weights corrupted | SHA-256 vs manifest | Reject checkpoint resume | Prior valid step | BLOCK | Alert administrator | `manifest.json` check |
| **23** | Checkpoint | Optimizer moments corrupted | SHA-256 vs manifest | Reject checkpoint resume | Prior valid step | BLOCK | Re-init optimizer if needed| Manifest check |
| **24** | Checkpoint | Scheduler state corrupted | SHA-256 vs manifest | Reject checkpoint resume | Prior valid step | BLOCK | Reset schedule | Manifest check |
| **25** | Checkpoint | RNG state corrupted | SHA-256 vs manifest | Reject checkpoint resume | Deterministic seed | HIGH | Re-seed deterministic RNG | Manifest check |
| **26** | Checkpoint | Missing `manifest.json` | File existence check | Reject directory load | Fail closed | BLOCK | Require valid manifest | Checkpoint verify |
| **27** | Checkpoint | Broken parent hash link | Lineage chain verification | Reject lineage chain | Fail closed | BLOCK | Repair lineage pointer | `phase47_checkpoint_lineage.py` |
| **28** | Checkpoint | Checkpoint deletion attempt | Invalidation policy | Refuse deletion of ancestors| Preserve immutable DAG | BLOCK | Lock checkpoint dir | Lineage report |
| **29** | Evaluation | Zero delta tokens in gain calc | Denominator protection | Report `INCONCLUSIVE` | No division performed | LOW | Await token accumulation | Capability telemetry |
| **30** | Evaluation | Negative delta tokens in gain | Denominator protection | Report `INCONCLUSIVE` | No division performed | LOW | Fix checkpoint order | Capability telemetry |
| **31** | Evaluation | Sub-100 delta tokens in gain | Denominator protection | Report `INCONCLUSIVE` | No division performed | LOW | Await token accumulation | Capability telemetry |
| **32** | Evaluation | Spurious gain claim without tokens| Statistical threshold check| Flag `statistically_meaningful = False` | Transparent report | MEDIUM | Require >=1000 tokens | Gain metric record |
| **33** | Capability | Tamil factual QA regression | Benchmark evaluator | Flag regression in report | Retain candidate state | WARN | Additional pretraining | Capability report |
| **34** | Capability | English syntax regression | Benchmark evaluator | Flag regression in report | Retain candidate state | WARN | Additional pretraining | Capability report |
| **35** | Capability | Tanglish response in English | Output policy check | Fail policy test (score 0.0)| Force pure Tamil | HIGH | Output filter clamp | Policy check |
| **36** | Capability | Hallucination on missing facts | Epistemic Tier 4 check | Output "ஆதாரம் இல்லை" | Safe uncertainty refusal | MEDIUM | Model prompt clamp | Grounding report |
| **37** | Capability | Acceptance of false premise | Epistemic Tier 4 check | Output "தவறான அனுமானம்"| Premise correction | MEDIUM | Model prompt clamp | Grounding report |
| **38** | Capability | Long-context memory loss | Long-context probe | Score 0.0 on dimension | Flag context limit | MEDIUM | Retain context window | Benchmark report |
| **39** | Security | RAG prompt injection attempt | Injection screening | Quarantine item | Clean context only | BLOCK | Security quarantine | Security log |
| **40** | Security | UUID session cross-talk | Session lookup isolation | Return empty context | Fresh session | BLOCK | Session boundary check | Session test |
| **41** | Security | AST scan: `eval` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **42** | Security | AST scan: `exec` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **43** | Security | AST scan: `subprocess` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **44** | Security | AST scan: `os.system` detected | Static AST parser | Build pipeline abort | Zero tolerance | BLOCK | Code refactor | AST scan report |
| **45** | Admin API | Cross-tenant access attempt | Tenant manager check | Raise `TenantAccessDeniedError` | Fail closed | BLOCK | Audit log event | `phase47_admin_audit.jsonl` |
| **46** | Admin API | Public Chat scope requested | Scope validator check | Raise `ScopeAccessDeniedError` | Reject request | BLOCK | Audit log event | Audit log |
| **47** | Admin API | Password leaked in audit log | Log sanitizer check | Redact credential string | `[REDACTED]` string | HIGH | Redaction filter | Audit test |
| **48** | Canary | Canary traffic exceeds 1.0% | Traffic router clamp | Clamp to 1.0% maximum | Fail-safe ceiling | BLOCK | Rate limiter clamp | Canary test |
| **49** | Release | Experimental candidate in Public| Scope router check | Reject candidate routing | Production baseline | BLOCK | Scope check | Public Chat test |
| **50** | Persistence| Production database modified | SHA-256 mismatch | Immediate execution halt | Restore from backup | BLOCK | Halt Phase 47 | Database check |
| **51** | Git | Baseline commit or stash lost | Git status check | Immediate execution halt | Checkout baseline | BLOCK | Halt Phase 47 | Git status check |
| **52** | Governance | Candidate auto-promoted | Release manager check | Default `REVIEW_REQUIRED` | No autonomous release | BLOCK | Manual review gate | Quality gate report |
