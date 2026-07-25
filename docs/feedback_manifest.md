# Feedback Manifest

`core_model/feedback/manifest.py` re-exports Phase 14's checksum/scan
implementation unchanged (via Phase 16/17's own re-export) — no fourth
implementation of the same tamper-detection and secret/path-scanning
logic in this project.

`RegressionEvaluationService.generate_manifest()`/`verify_manifest()`
produce and check a `feedback_manifests` row (append-only) per
feedback policy: feedback-policy checksum, feedback counts by
type/classification, privacy/safety finding summaries, review rubric
version, dataset-candidate checksums, deduplication/contamination
configuration, the active regression-suite checksum, model-comparison
results, an improvement-report checksum, an explicit
`known_limitations` list, and software versions — never raw feedback
comments, raw private conversation text, raw corrected responses,
secrets, absolute paths, or numeric database IDs.

`verify_manifest()` recomputes the checksum from the stored manifest
JSON and compares against the stored value, reporting `matches:
true/false` — the same verify-not-trust pattern used by every manifest
in this project since Phase 10.
