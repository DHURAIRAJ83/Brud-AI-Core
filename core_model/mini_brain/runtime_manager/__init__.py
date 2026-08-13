"""MB-30: Production Runtime Manager & One-Click Local Model Lifecycle
-- pure policy/planning/catalog helpers only.

Every module in this package is strictly pure -- no I/O at all, not
even the disclosed real-I/O exceptions MB-29's own package allowed
itself (`hardware_probe.py`/`model_scanner.py`). This phase's spec is
explicit: "Only model_catalog.py may contain static download
metadata. All other modules must remain pure." `checksum_verifier.
compute_sha256()` hashes bytes already read by the caller (the same
"hashing in-memory bytes is not I/O" precedent MB-26's `voice_result_
sanitizer.hash_audio()` already established) -- it never opens a file
itself.

Real streamed HTTP downloads, real file writes, real checksum-bytes
reads, and real model loading live entirely in
`backend/services/runtime_manager_service.py` -- the one designated
impure module for this phase, the same pattern MB-25's `timeout_
runner.py`, MB-27's `secret_encryptor.py`, and MB-28's `mini_brain_
llm_adapter.py` already established.
"""
