# 03 TOKEN BINDING INTEGRITY AUDIT

- Binding Enforcement: Tokens bind `request_id`, `tenant_id`, `candidate_model_hash`, `dataset_manifest_hash`, `tokenizer_hash`, `release_id`, `snapshot_hash`, and `admin_public_id`.
- Mismatch Behavior: Mismatched hashes fail closed safely (`BLOCKED / DENIED`).
