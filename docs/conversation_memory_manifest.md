# Conversation Memory Reproducibility Manifest

`core_model/conversation/manifest.py` re-exports Phase 16's manifest
checksum/scan functions unchanged. `MemoryEvaluationService.generate_manifest()`/
`verify_manifest()` produce and check a `conversation_memory_manifests`
row (append-only) per memory policy: configuration checksums, applied
migration/schema version, evaluation-suite/run summary, and an
explicit `known_limitations` list — never raw memory content, raw
conversation text, secrets, or absolute filesystem paths.

`verify_manifest()` recomputes the checksum from current state and
compares against the stored value, reporting `matches: true/false` —
the same verify-not-trust pattern used by every manifest in this
project since Phase 10.
