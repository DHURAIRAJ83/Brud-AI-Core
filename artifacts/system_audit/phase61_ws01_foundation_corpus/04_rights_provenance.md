# Phase 61 WS01 Report — 04: Rights & Provenance Verification

## Provenance Enforcement
- Every ingested record MUST reference a valid `source_id` in the Source Registry.
- Records missing explicit license metadata are automatically flagged as `QUARANTINED`.
