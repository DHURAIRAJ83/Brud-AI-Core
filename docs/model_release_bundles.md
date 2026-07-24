# Release Bundles (Phase 14)

`core_model/release/release_bundle.py` decides *what* goes into a safe
export bundle and validates it; `ModelReleaseService._write_bundle_archive()`
performs the actual (read-only, confined) file I/O to build the zip —
the same pure-decision/service-I/O split used throughout the project.

## Fixed layout

```
release/
├── model/
│   ├── checkpoint/       (every file from the checkpoint directory)
│   └── config.json
├── tokenizer/
│   ├── tokenizer.model
│   ├── tokenizer.vocab
│   └── tokenizer_manifest.json
├── manifests/
│   ├── release_manifest.json
│   ├── training_manifest.json
│   ├── instruction_manifest.json   (only if instruction-tuned)
│   └── evaluation_manifest.json
├── model_card.md
├── LICENCE
└── README.md
```

## Generation is rejected for a blocked or incomplete candidate

`build_bundle()` first requires the release itself to be `released` or
`deprecated` with a `deployment_eligibility` other than `not_deployable`
— a release that is `not_deployable` never reaches bundle generation.
`validate_bundle_source_artifacts()` then requires every artifact type
the candidate's lineage implies (including `model_card` and
`release_manifest`, which only exist once explicitly generated — see
`docs/model_cards.md`/`docs/model_release_manifests.md`) to be present
and `verified`; any gap raises `bundle_generation_failed` before any
archive is written.

(This exact gap was caught during automated testing: the first
implementation forgot to record `model_card`/`release_manifest` as
artifact rows at generation time, so `build_bundle()` correctly refused
to bundle an otherwise-eligible release. Fixed by recording both as
verified artifacts the moment their content is generated.)

## No sensitive content

`scan_bundle_paths_for_forbidden_content()` checks every planned bundle
path against a forbidden-fragment list (`.env`, `.db`, `.sqlite`,
`session`, `admin_accounts`, `.git/`, `__pycache__`) before writing
anything. Because the bundle's file list is built entirely from the
fixed `BUNDLE_REQUIRED_ENTRIES` mapping — never a directory walk over
arbitrary paths — there is no code path that could pull in the database
file, `.env`, session data, or a raw dataset even by accident.

## Checksum and size limit

`bundle_checksum_sha256` is the SHA-256 of the actual written archive
file (not just the content listing), so `verify_bundle()` provides real
tamper detection against the artifact itself. `is_bundle_size_within_limit()`
enforces `BRUD_RELEASE_MAX_BUNDLE_SIZE_BYTES`; an oversized archive is
deleted immediately and the request rejected. Only `zip` (and `tar_gz`,
reserved for future use) are accepted bundle formats
(`BRUD_RELEASE_ALLOWED_BUNDLE_FORMATS`).
