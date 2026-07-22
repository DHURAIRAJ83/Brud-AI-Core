# Dataset Quality

Phase 6 quality scoring is deterministic. It does not call an AI model, rewrite text, infer answers, or approve records automatically.

## Dimensions

- Completeness: required fields are present and non-empty.
- Structure: record type, language, metadata, field lengths, and translation metadata are valid.
- Language: selected language matches script expectations for Tamil, English, Tanglish, mixed, and unknown.
- Text quality: replacement characters, punctuation ratio, repetition, control characters, short text, and low letter ratio.
- Duplication: canonical content hash conflicts with existing records.
- Safety: bounded checks for secret-like metadata and obvious personal-data patterns.
- Provenance: source, source type, licence status, and manual/import/document metadata.

## Readiness

- `ready`: score is at or above `BRUD_QUALITY_READY_THRESHOLD` and no blocking issues exist.
- `warning`: score is above warning threshold but below ready threshold, or warning issues exist.
- `blocked`: blocking issue exists or score is below warning threshold.
- `not_assessed`: no assessment has been recorded.

Assessments preserve history and do not mutate the dataset record. The latest assessment is used by review and build workflows.

## Review integration

Normal approval rejects blocked-quality records. Phase 6 records audit evidence for quality assessment and blocked approval behavior. Override workflows are intentionally limited and must require comments when expanded in a later phase.

## Limitations

Language validation is script-based, not ML detection. Safety checks are conservative deterministic checks, not semantic moderation.
