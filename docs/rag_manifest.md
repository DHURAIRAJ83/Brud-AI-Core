# RAG Manifest

`RagEvaluationService.generate_manifest()` builds one JSON manifest per
knowledge space containing: the space's public ID, every source
version's public ID + content checksum, the latest chunk-set manifest
checksum, the active vector/keyword index checksums, the injection
filter configuration, and an explicit `known_limitations` list (grounding
does not guarantee factual correctness; the FTS5 tokenizer does not
perform true Tamil morphological segmentation; the local custom
embedding is a bounded hashing-trick approximation, not a trained
semantic model). It never includes raw document/chunk text, absolute
filesystem paths, or secrets.

Re-exports `manifest_checksum`, `scan_for_sensitive_content`, and
`verify_manifest_checksum` unchanged from Phase 14's
`core_model.release.manifest` — no second checksum or secret-scanning
implementation. `generate_manifest()` runs `scan_for_sensitive_content()`
over the assembled manifest before persisting it and raises if any
concern (`absolute_path_detected`, `secret_like_content_detected`) is
found, rather than persisting a manifest that might leak something.

`verify_manifest()` recomputes the checksum of the latest stored
manifest's JSON and compares it against the stored
`manifest_checksum_sha256`, exactly mirroring
`ModelAssignmentService.generate_manifest()`/`verify_manifest()` from
Phase 15.

Manual verification: a manifest generated for the Path A knowledge space
verified `matches: true` on the first attempt, and its serialized JSON
contained no `/home/` path segments.
