# Dataset Export

Phase 6 exports ready or archived dataset versions as UTF-8 JSONL plus a manifest.

## Layout

```text
data/dataset_exports/
└── <safe_dataset_name>/
    ├── manifest.json
    ├── train.jsonl
    ├── validation.jsonl
    └── test.jsonl
```

Each line is one JSON object. Tamil Unicode is preserved.

## Safety

- Exports are written under `BRUD_DATASET_EXPORT_DIR`.
- The directory must remain inside approved project data storage.
- Existing export directories are not overwritten.
- APIs expose safe names and checksums, not local filesystem paths.
- Draft versions cannot be exported.

## Verification

Export verification recalculates SHA-256 over the generated manifest and split files listed in the export file manifest.

## Limitations

Phase 6 does not produce tokenizer-specific binary formats or training-framework-specific datasets.
