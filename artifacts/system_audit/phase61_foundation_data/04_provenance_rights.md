# Phase 61 Report — 04: Data Provenance & Rights Governance

## Provenance Manifest Schema (`dataset_manifest.json`)
Every dataset in the foundation corpus must record:
```json
{
  "dataset_id": "DS-FOUNDATION-TA-001",
  "version": "v001",
  "source_name": "Public Domain Tamil Literature & Reference",
  "source_url": "https://brud.ai/datasets/ta_reference_v1",
  "collection_date": "2026-09-01",
  "license": "CC-BY-4.0 / Public Domain",
  "language": "ta",
  "domain": "reference_prose",
  "synthetic_flag": false,
  "record_count": 125000,
  "estimated_tokens": 17500000,
  "sha256_seal": "a1b2c3d4e5f67890..."
}
```
