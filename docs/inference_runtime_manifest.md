# Runtime Manifest (Phase 15)

`ModelAssignmentService.generate_manifest()` builds one deterministic
JSON manifest per assignment, containing: the assignment's public ID
and scope, the release's public ID and its Phase 14 release-manifest
checksum, checkpoint/tokenizer/model-config checksums, the latest
runtime-compatibility status, the generation configuration, the current
assignment-version public ID, the canary configuration (percentage,
max request count), the fallback policy, the recorded activation
approvals (role + decision only), fixed `known_limitations` strings
("runtime existence does not imply model quality", "public chat
activation requires a separate explicit gate"), and a software-version
tag.

## Reused, not duplicated

Checksum computation, verification, and sensitive-content scanning
(`manifest_checksum()`, `verify_manifest_checksum()`,
`scan_for_sensitive_content()`) are imported unchanged from
`core_model.release.manifest` — the same functions Phase 14's release
manifest uses. The manifest is scanned for absolute paths and
secret-shaped content **before** it is persisted; a positive scan
raises rather than silently stripping the offending content.

## Never included

Absolute paths, raw prompts, raw generated outputs, secrets, numeric
database IDs, or tensor contents. Every reference is a public ID or a
SHA-256 checksum.

## Verification

`GET /assignments/{public_id}/manifest` returns the latest manifest;
`POST /assignments/{public_id}/manifest/verify` recomputes the SHA-256
of the stored `manifest_json` and reports `matches: true/false` against
the stored checksum — the same tamper-detection pattern every prior
phase's manifest verification uses.
