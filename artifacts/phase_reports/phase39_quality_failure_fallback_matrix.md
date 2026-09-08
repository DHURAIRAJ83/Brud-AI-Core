# Phase 39 — Quality Failure & Fallback Matrix

| Scenario # | Condition | Expected Behavior | Verification Status | Evidence File / Test |
|---|---|---|---|---|
| **1** | Missing sovereign dataset | Graceful error / manifest rejection | `PASS` | `test_001_sovereign_dataset_governance_and_provenance` |
| **2** | Invalid dataset schema | Validation error on load | `PASS` | `test_001_sovereign_dataset_governance_and_provenance` |
| **3** | Corrupted dataset bytes | SHA-256 hash mismatch rejection | `PASS` | `test_001_sovereign_dataset_governance_and_provenance` |
| **4** | Dataset hash mismatch | Rejection by manifest check | `PASS` | `test_001_sovereign_dataset_governance_and_provenance` |
| **5** | Unauthorized dataset | Blocked by license/governance check | `PASS` | `test_001_sovereign_dataset_governance_and_provenance` |
| **6** | Tokenizer training failure | Caught without corrupted artifact write | `PASS` | `test_004_sentencepiece_tokenizer_training_and_manifest` |
| **7** | Tokenizer mismatch | Vocabulary size incompatibility detected | `PASS` | `test_004_sentencepiece_tokenizer_training_and_manifest` |
| **8** | Architecture mismatch | MHA / KV head validation catches error | `PASS` | `test_005_production_model_configuration_validation` |
| **9** | Insufficient RAM | Resource Guard blocks allocation | `PASS` | `test_006_cpu_resource_planning_and_resource_guard` |
| **10** | Insufficient disk | Resource Guard blocks checkpoint write | `PASS` | `test_006_cpu_resource_planning_and_resource_guard` |
| **11** | Training interruption | State checkpoint allows resume | `PASS` | `test_008_checkpoint_creation_and_restoration` |
| **12** | Corrupted checkpoint | State load fails without system crash | `PASS` | `test_008_checkpoint_creation_and_restoration` |
| **13** | Checkpoint checksum mismatch | Validation rejection via manifest | `PASS` | `test_008_checkpoint_creation_and_restoration` |
| **14** | Validation failure | Flagged in training telemetry | `PASS` | `test_009_training_metrics_observability` |
| **15** | Quality gate failure | Status degrades to WARN/BLOCK | `PASS` | `test_010_model_evaluation_and_quality_gates` |
| **16** | Inference failure | Safe fallback reply generated | `PASS` | `test_012_public_chat_scope_isolation` |
| **17** | Public/admin scope violation | Admin models inaccessible to Public Chat | `PASS` | `test_012_public_chat_scope_isolation` |
| **18** | Invalid artifact path | Path confinement blocks traversal | `PASS` | `test_015_failure_and_fallback_matrix` |
| **19** | Rollback required | Reverts safely to previous state | `PASS` | `test_013_rollback_safety` |
| **20** | Release approval missing | Resolver returns unassigned state | `PASS` | `test_011_release_governance_and_approval_gating` |
