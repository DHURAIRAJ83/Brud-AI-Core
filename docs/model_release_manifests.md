# Release Manifests (Phase 14)

`ModelReleaseService.generate_manifest()` assembles a deterministic
release manifest from already-registered evidence — the family, candidate,
core model version, checkpoint, tokenizer, dataset lineage, base-training/
instruction-tuning/evaluation manifest checksums, evaluation readiness
status, model-card checksum, licence notices, eligibility assessment,
approvals, resource requirements, supported languages, and known
limitations — then computes its SHA-256 checksum
(`core_model.release.manifest.manifest_checksum()`).

## Never includes

Absolute paths, secrets, raw training text, raw evaluation prompts,
tensor contents, or numeric database IDs — only public IDs and
checksums. Before persisting, every manifest is passed through
`scan_for_sensitive_content()`, which searches the serialized manifest
for absolute-path patterns (`/home/`, `/etc/`, a Windows drive letter,
...) and secret-shaped key/value pairs (`api_key=...`,
`password=...`, ...). If either is found, `generate_manifest()` raises
rather than persisting a manifest that could leak either — this is a
hard stop, not a warning.

(An earlier version of this scanner anchored its absolute-path regex to
the start of a line, which meant a path embedded mid-string in the
serialized single-line JSON was never caught. Fixed to match after
whitespace or a quote character anywhere in the text, and verified
directly against both a Unix path and a Windows path embedded mid-value.)

## Immutability

`model_release_manifests` is append-only — a new `generate_manifest()`
call after evidence changes creates a new row rather than editing the
old one, and `model_release_candidates.latest_manifest_public_id` always
points at the newest. `verify_manifest()` recomputes the checksum of the
current row and compares; tamper detection is proven directly by test
(appending a manifest row with a deliberately mismatched checksum — the
table is append-only, so tampering is simulated as a new row, not an
`UPDATE` — and confirming `verify_manifest()` reports `matches: false`).

## Also recorded as an artifact

The moment a manifest is generated, its JSON is also written to a
controlled file and recorded as a `release_manifest`-type row in
`model_release_artifacts` (verification status `verified` immediately,
since it was just computed server-side) — this is what allows a release
bundle to include the manifest without a separate collection step.

## Release manifests vs. candidate manifests

A `model_release_manifests` row belongs to a **candidate**, not yet a
release — `create_release()` requires the candidate's latest manifest to
recompute-verify cleanly before a release can be created, and stores
that manifest's public ID on the resulting `model_releases` row
(`release_manifest_public_id`) so a release always has a fixed,
traceable manifest even though the manifest table itself is keyed by
candidate.
