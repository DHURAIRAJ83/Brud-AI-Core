# PHASE 44 FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 15 — Failure and Fallback Matrix  
**Scope:** 42 Comprehensive Scenarios Across Governance, Runtime, Canary, Safety, and Rollback  

---

| ID | Scenario Category | Failure Condition | Detection Mechanism | Immediate Action | Fallback Model | Candidate State | Artifact Preservation | Database Effect |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | Governance | Single admin attempts approval | `submit_approval` count < 2 | State remains `ADMIN_APPROVAL_PENDING` | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **02** | Governance | Duplicate admin approval | Admin ID duplicate check | Reject second approval | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **03** | Governance | Model weight mutation post-approval | SHA-256 mismatch vs token | Invalidate all approvals | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **04** | Governance | Tokenizer mutation post-approval | SHA-256 mismatch vs token | Invalidate all approvals | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **05** | Governance | Config mutation post-approval | SHA-256 mismatch vs token | Invalidate all approvals | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **06** | Governance | Manifest mutation post-approval | SHA-256 mismatch vs token | Invalidate all approvals | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **07** | Governance | Admin signs stale build hash | Verification against live files | Reject approval token | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **08** | Governance | Unauthorized public transition attempt | Target state == `PUBLIC_PRODUCTION`| Raise `PermissionError` | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **09** | Canary | Traffic set > 1.0% | Traffic percentage check | Raise `ValueError` | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **10** | Canary | Traffic set negative | Traffic percentage check | Raise `ValueError` | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **11** | Canary | Canary routed when unapproved | Governance state check | Reject candidate routing | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **12** | Canary | Public chat requested candidate | Scope check in router | Raise `ScopeViolationError` | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **13** | Canary | Unknown scope requested | Scope validation check | Reject request (fail closed) | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **14** | Canary | Unauthorized scope backdoor | Scope whitelist check | Reject request (fail closed) | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **15** | Canary | Staged rollout jump (0% to 5%) | Allowed traffic stage check | Raise `ValueError` | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **16** | Telemetry | Missing telemetry record field | Dataclass validation | Refuse record; alert operator | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **17** | Telemetry | Telemetry file unwriteable | Disk / OS error trap | Log to stderr; fail closed | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **18** | Health | Error rate exceeds 2.0% | `calculate_metrics` check | Trigger atomic rollback | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **19** | Health | P95 latency exceeds 1,000ms | Rolling percentile check | Trigger atomic rollback | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **20** | Health | Model weight load failure | Exception in loader | Trigger atomic rollback | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **21** | Health | Checkpoint integrity check fails | Checksum mismatch | Trigger atomic rollback | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **22** | Health | Scope violation detected | Router scope exception | Trigger atomic rollback | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **23** | Rollback | Rollback traffic zeroing fails | Try/except in rollback | Hard assign traffic = 0.0% | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **24** | Rollback | Fallback model missing | Fallback existence check | Hard halt; alert admin | Fallback model | `ROLLED_BACK` | Preserved | None |
| **25** | Rollback | Reactivation attempt after rollback | State check (`ROLLED_BACK`) | Block reactivation | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **26** | Rollback | Candidate artifact deletion attempt | File system guard | Deny deletion; preserve files | `0.1.0-synthetic-test` | `ROLLED_BACK` | Preserved | None |
| **27** | Shadow | Shadow execution throws exception | Internal try/except | Record error in telemetry | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **28** | Shadow | Shadow output leak attempt | `user_exposed` flag check | Enforce `user_exposed: False` | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **29** | Capability | Tamil syllabic accuracy drops | Capability evaluation check | Retain candidate in review | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **30** | Capability | English syntax compliance drops | Capability evaluation check | Retain candidate in review | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **31** | Capability | Tanglish output violates Tamil policy | Language policy check | Force pure Tamil output | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **32** | Capability | Reasoning score degradation | Regression check vs baseline | Prevent candidate advance | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **33** | Capability | Hallucination on ungrounded fact | Grounding validation check | Return uncertainty refusal | `0.1.0-synthetic-test` | `REVIEW_REQUIRED` | Preserved | None |
| **34** | Security | RAG prompt injection attack | `assess_context_item_injection` | Quarantine item; block exec | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **35** | Security | Cross-session memory leak | UUID session query gate | Return empty history | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **36** | Security | Forbidden `eval` in source | Static AST scanner | Abort build; report violation | `0.1.0-synthetic-test` | Rejected | Preserved | None |
| **37** | Security | Forbidden `exec` in source | Static AST scanner | Abort build; report violation | `0.1.0-synthetic-test` | Rejected | Preserved | None |
| **38** | Security | Forbidden `subprocess` in source | Static AST scanner | Abort build; report violation | `0.1.0-synthetic-test` | Rejected | Preserved | None |
| **39** | Security | Path traversal outside root | Path confinement check | Abort inventory scan | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **40** | System | Production database file altered | SHA-256 pre/post check | Hard stop (`BLOCKED`) | `0.1.0-synthetic-test` | `BLOCKED` | Preserved | None |
| **41** | System | Root disk space exhaustion (<1GB) | Resource Guard pre-check | Halt runtime drill | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
| **42** | System | Available RAM exhaustion (<500MB) | Resource Guard pre-check | Throttle runtime drill | `0.1.0-synthetic-test` | Unchanged | Preserved | None |
