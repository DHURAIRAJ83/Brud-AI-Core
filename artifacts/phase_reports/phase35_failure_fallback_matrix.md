# Phase 35 — Failure & Fallback Matrix

| Scenario # | Condition | Expected Behavior | Verification Status | Evidence File / Test |
|---|---|---|---|---|
| **1** | Valid model checkpoint & assignment | Successful token generation | `PASS` | `test_005_real_autoregressive_inference_execution` |
| **2** | Missing model file | Controlled refusal fallback | `PASS` | `test_009_provider_availability_and_fallback` |
| **3** | Corrupted model bytes | Load rejection & error handling | `PASS` | `test_002_artifact_manifest_and_checksum_verification` |
| **4** | Checksum manifest mismatch | Activation rejected | `PASS` | `test_002_artifact_manifest_and_checksum_verification` |
| **5** | Unassigned model state | Safe fallback reply (`insufficient_text`) | `PASS` | `test_004_unassigned_model_produces_safe_fallback` |
| **6** | Insufficient memory | Load blocked by Resource Guard | `PASS` | `test_008_dynamic_resource_guard_evaluation` |
| **7** | Local provider unavailable | Graceful fallback to search/refusal | `PASS` | `test_009_provider_availability_and_fallback` |
| **8** | Invalid external API key | Safe error without leaking secret | `PASS` | `test_010_external_provider_invalid_key_fails_safely` |
| **9** | Prompt exceeds context length | Stop reason `prompt_too_long` | `PASS` | `test_006_excessive_token_request_is_bounded` |
| **10** | Path traversal attempt | Path resolution returns `None` | `PASS` | `test_001_artifact_path_confinement_and_traversal_rejection` |
| **11** | Public requests admin scope | Access denied & unassigned return | `PASS` | `test_003_scoped_assignment_public_vs_admin_isolation` |
| **12** | Prompt injection in context | Quarantine by Injection Guard | `PASS` | `test_011_context_injection_guard_quarantines_malicious_rag_item` |
| **13** | Repeated inference request | Stable instance reuse in cache | `PASS` | `test_007_runtime_instance_reuse_and_cache_management` |
| **14** | Model reload / eviction | Clean cache deletion & refresh | `PASS` | `test_007_runtime_instance_reuse_and_cache_management` |
| **15** | AST Security & Prohibited Code | Zero eval, exec, subprocess | `PASS` | `test_015_ast_security_no_eval_exec_in_deployment_test` |
