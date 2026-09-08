# Phase 37 — Training Failure & Fallback Matrix

| Scenario # | Condition | Expected Behavior | Verification Status | Evidence File / Test |
|---|---|---|---|---|
| **1** | Missing dataset | Registration rejected / error raised | `PASS` | `test_001_dataset_registration_and_provenance` |
| **2** | Invalid dataset syntax | Manifest creation fails safely | `PASS` | `test_001_dataset_registration_and_provenance` |
| **3** | Unapproved dataset | Release pipeline blocks promotion | `PASS` | `test_007_scoped_assignment_isolation_and_rollback` |
| **4** | Tokenizer mismatch | Model load rejected | `PASS` | `test_002_tokenizer_vocabulary_compatibility_check` |
| **5** | Corrupted dataset bytes | SHA-256 digest verification fails | `PASS` | `test_001_dataset_registration_and_provenance` |
| **6** | Insufficient memory | Resource Guard blocks execution | `PASS` | `test_009_cpu_and_resource_guard_behavior` |
| **7** | Training interruption | Checkpoint state preserved on disk | `PASS` | `test_004_checkpoint_creation_and_integrity_verification` |
| **8** | Checkpoint corruption | Checksum validation triggers error | `PASS` | `test_004_checkpoint_creation_and_integrity_verification` |
| **9** | Checksum mismatch | State restoration rejected | `PASS` | `test_004_checkpoint_creation_and_integrity_verification` |
| **10** | Architecture mismatch | Parameter shape mismatch rejected | `PASS` | `test_002_tokenizer_vocabulary_compatibility_check` |
| **11** | Incompatible tokenizer vocab | Rejection by loader compatibility | `PASS` | `test_002_tokenizer_vocabulary_compatibility_check` |
| **12** | Failed validation metrics | Quality gate issues blocking status | `PASS` | `test_006_pretraining_quality_gate_evaluation` |
| **13** | Failed quality gate | Pipeline transitions to `blocked` | `PASS` | `test_006_pretraining_quality_gate_evaluation` |
| **14** | Unapproved release activation | Assignment resolver returns None | `PASS` | `test_007_scoped_assignment_isolation_and_rollback` |
| **15** | Public chat admin scope request | Access denied / ignored | `PASS` | `test_007_scoped_assignment_isolation_and_rollback` |
| **16** | Invalid artifact path | Path confinement returns None | `PASS` | `test_008_path_confinement_and_traversal_rejection` |
| **17** | Missing artifact file | Controlled fallback reply | `PASS` | `test_007_scoped_assignment_isolation_and_rollback` |
| **18** | Corrupted release metadata | Rejected during load verification | `PASS` | `test_004_checkpoint_creation_and_integrity_verification` |
| **19** | Rollback between releases | Reverts cleanly to fallback reply | `PASS` | `test_007_scoped_assignment_isolation_and_rollback` |
| **20** | Resource exhaustion | Memory guard evaluation fails safely | `PASS` | `test_009_cpu_and_resource_guard_behavior` |
