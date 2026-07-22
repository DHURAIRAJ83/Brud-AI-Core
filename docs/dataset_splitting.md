# Dataset Splitting

Phase 6 creates deterministic train, validation, and test splits.

## Defaults

- Train: 90%
- Validation: 5%
- Test: 5%
- Seed: `42`

The configured percentages must total 100.

## Small datasets

- 1-2 records: train only.
- 3-19 records: train and validation; test may be empty.
- 20+ records: configured percentages are applied.

Records are never duplicated to fill empty splits.

## Grouping and leakage

Splitting operates on groups. Group priority is:

- document public ID and page range when document provenance exists;
- canonical content hash;
- record public ID fallback.

The builder blocks exact hash leakage across splits. Duplicate groups stay together or are excluded before finalization.

## Reproducibility

The same approved record set, filters, grouping rules, and seed produce the same split assignments and checksum.
