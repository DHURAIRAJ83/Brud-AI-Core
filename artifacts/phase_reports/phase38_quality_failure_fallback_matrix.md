# Phase 38 — Quality Failure & Fallback Matrix

| Scenario # | Condition | Expected Behavior | Verification Status | Evidence File / Test |
|---|---|---|---|---|
| **1** | Missing benchmark dataset | Graceful error / manifest rejection | `PASS` | `test_001_benchmark_dataset_registration_and_manifest` |
| **2** | Invalid benchmark dataset | Syntax error caught safely | `PASS` | `test_001_benchmark_dataset_registration_and_manifest` |
| **3** | Dataset hash mismatch | Rejection by manifest check | `PASS` | `test_001_benchmark_dataset_registration_and_manifest` |
| **4** | Tokenizer mismatch | Vocabulary incompatibility detected | `PASS` | `test_002_tamil_language_evaluation` |
| **5** | Missing checkpoint | Resolver returns unassigned state | `PASS` | `test_014_safe_model_rollback` |
| **6** | Corrupted checkpoint | State load fails without crash | `PASS` | `test_013_quality_failure_and_fallback_scenarios` |
| **7** | Model load failure | Graceful fallback response | `PASS` | `test_013_quality_failure_and_fallback_scenarios` |
| **8** | Invalid model output | Bounded stop reason triggered | `PASS` | `test_005_instruction_following_format_compliance` |
| **9** | Context overflow | Bounded generation stops safely | `PASS` | `test_005_instruction_following_format_compliance` |
| **10** | Resource exhaustion | Dynamic memory guard blocks load | `PASS` | `test_011_cpu_performance_and_latency_measurement` |
| **11** | RAG context injection | Malicious item flagged/quarantined | `PASS` | `test_007_rag_grounding_and_context_injection_guard` |
| **12** | Missing RAG evidence | Controlled refusal response | `PASS` | `test_009_hallucination_and_uncertainty_control` |
| **13** | Memory isolation failure | Blocked; separate UUIDs isolated | `PASS` | `test_008_memory_session_continuity_and_isolation` |
| **14** | Unknown question | Safe refusal / uncertainty reply | `PASS` | `test_009_hallucination_and_uncertainty_control` |
| **15** | Hallucinated answer | Refusal when evidence insufficient | `PASS` | `test_009_hallucination_and_uncertainty_control` |
| **16** | Invalid generation request | Parameter bounds enforced | `PASS` | `test_005_instruction_following_format_compliance` |
| **17** | Public/admin scope violation | Admin models inaccessible to Public Chat | `PASS` | `test_013_quality_failure_and_fallback_scenarios` |
| **18** | Benchmark runner failure | Isolated exception handling | `PASS` | `test_002_tamil_language_evaluation` |
| **19** | Quality gate failure | Status degrades to WARN/BLOCK | `PASS` | `test_012_quality_gates_evaluation_all_18_gates` |
| **20** | Rollback requirement | Reverts safely to fallback response | `PASS` | `test_014_safe_model_rollback` |
