# Dataset Versioning

Dataset versions package approved records into immutable, reproducible training datasets for future tokenizer and model phases.

## Lifecycle

Allowed lifecycle:

```text
draft -> building
building -> ready
building -> failed
failed -> draft
ready -> archived
```

Only draft versions can be edited. Ready versions are immutable and remain readable/exportable after archive. Phase 7 tokenizer training and Phase 9 bounded pretraining consume only ready or archived versions and never edit version contents.

## Build workflow

1. Create a build with dataset name, version, filters, split configuration, and quality settings.
2. Validate selected records and proposed splits.
3. Run the build explicitly.
4. Store version items, manifest, distributions, and checksum.
5. Record build events and audit metadata.

Only approved records are selected. Archived, rejected, and rejected-licence records are excluded.

## Manifest and checksum

The manifest contains public IDs, distributions, selection filters, split configuration, and stable record references. The content checksum is SHA-256 over canonical logical dataset content, excluding internal IDs, paths, sessions, secrets, and mutable audit timestamps.

## Recovery

Failed builds do not produce a ready version. A draft or failed build can be retried after correcting the data or filters.
