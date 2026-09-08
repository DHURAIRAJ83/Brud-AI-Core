# 04 TOKEN BINDING VALIDATION AUDIT

- Payload Binding Verification: Strict matching enforced for `dataset_manifest_hash`, `model_hash`, `tokenizer_hash`, `release_id`, `snapshot_hash`, and `tenant_id`. Any mismatch fails closed.
