# Training Dataset Coverage

## Overview

`training_dataset_coverage` provides comprehensive, deterministic reporting of the dataset records actually encoded and packed for training. Coverage is generated at job creation time and at completion time.

## Coverage Dimensions

### Record Counts

* **total_records** - All records in the dataset version (train + valid)
* **eligible_records** - Records that passed basic format validation
* **encoded_records** - Records successfully tokenized
* **excluded_records** - Records excluded by policy
* **zero_token_records** - Records that encoded to empty sequences
* **split_records** - Records assigned to train or validation split
* **truncated_records** - Records exceeding sequence length limits

### Token Counts

* **total_tokens** - All tokens in eligible records
* **usable_tokens** - Tokens used in final packed blocks
* **padding_tokens** - Padding tokens added to complete blocks

### Distribution Data

**Language token distribution** reports proportions of Tamil, English, Tanglish, and mixed-language tokens within usable tokens.

**Record-type distribution** reports counts by logical record category (pretrain, instruction, chat, translation, safety, preference, etc.).

**Source-type distribution** reports counts by source/document ID or classification.

### Exclusion Reporting

Each excluded record is counted with a reason:
* `oversized` - record longer than configured sequence length
* `invalid_format` - unable to extract content
* `encoder_error` - tokenizer raised an error
* `empty` - all content was whitespace

## Consumption in Phase 9

In Phase 9:

1. **Job creation** generates a coverage snapshot after tokenization and packing
2. **On loading** a job, the coverage records are read and used to verify training split correctness
3. **Metrics** include `dataset_coverage_public_id` to reference this record
4. **Validation** can reject jobs when coverage is empty or contains only excluded records

## Determinism Guarantees

The coverage generation process is deterministic when:

* Same dataset version ID
* Same tokenizer version ID
* Same sequence length
* Same EOS policy
* Same overlength policy
* Same bootstrap random seed

Identical inputs produce identical checksums and distribution reports.

## Interaction with Phase 10

Phase 10 builds on this record by:

1. **Generating coverage at worker startup** with registered tokenizer validation
2. **Reporting coverage lapses** when new waves of data are added
3. **Idempotent regeneration** when job status is `paused` or `queued`
4. **Enforcing validation** that coverage includes train data before training starts
5. **Blocking promotion** when coverage passes below configured thresholds

## Querying Coverage

```sql
-- Get coverage of a job
SELECT * FROM training_dataset_coverage
WHERE pretraining_job_public_id = ?
ORDER BY created_at DESC LIMIT 1;

-- Get coverage of all jobs for a dataset version
SELECT pretraining_job_id,
       total_records,
       encoded_records,
       usable_tokens,
       EXCLUDED_TOKENS / NULLIF(TOTAL_RECORDS, 0) AS EXCLUSION_RATIO
FROM training_dataset_coverage
WHERE dataset_version_public_id = ?;
```

## No Privacy Risks

Coverage records do not contain:

* Record content
* Full token streams
* Database record text
* Individual record IDs (except FK)
**Padding tokens are masked** in distribution summaries.