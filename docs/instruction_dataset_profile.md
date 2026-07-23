# Instruction Dataset Profile (Phase 12)

`core_model/instruction_tuning/batch_builder.py::build_instruction_examples`
computes a deterministic profile of an experiment's instruction dataset
before any SFT run starts. It never trains a model and never fabricates
records to reach a target count.

## Eligible record types

Only `instruction`, `chat`, `translation`, `tanglish_pair`, and `safety`
records ever enter a training batch. `preference` records are validated
structurally but always excluded, with the explicit reason
`preference_optimization_out_of_scope_phase12` — training on chosen+rejected
completions as equal supervised targets would itself be a crude, undocumented
form of preference optimization, which Phase 12 explicitly does not implement.
Arbitrary `pretrain` records are never treated as instruction data.

## Per-type validation (see `core_model/instruction_tuning/dataset_validator.py`)

| record_type | Required fields | Explicit rejection reasons |
|---|---|---|
| `instruction` | `instruction`, `output_text` | `missing_instruction`, `missing_output_text` |
| `chat` | `metadata.turns` (preferred) or `input_text`+`output_text` (flat fallback, logged as `synthesized_from_flat_fields`) | `invalid_turn_structure`, `empty_turn_content`, `missing_assistant_final_turn`, `no_user_turn` |
| `translation` | `input_text`, `output_text`, `metadata.source_language`, `metadata.target_language` | `missing_language_pair_metadata`, `missing_source_or_target_text` |
| `tanglish_pair` | `input_text` + (`normalized_input` or `output_text`) | `missing_tanglish_input`, `missing_normalized_or_output` |
| `safety` | `input_text`, `output_text` | `missing_safety_prompt`, `missing_safety_response` |

If `chat` metadata explicitly provides `turns` but the structure is invalid
(unknown role, empty content, no user turn, last turn not `assistant`), the
record is **rejected**, never silently coerced to the flat fallback — the
flat fallback only applies when `turns` is absent entirely.

## Profile contents

Every `POST /experiments/{id}/profile` call persists a new append-only
`instruction_dataset_profiles` row containing: total/eligible/invalid/excluded
records, train/validation/test counts, language/record-type/source/licence
distributions, system-prompt and input-field counts, the synthesized-flat-chat
count, average/maximum prompt and response token counts, empty-response
count, duplicate-prompt/response counts, exact prompt-response duplicate
count, response-language mismatch count, special-token collision count,
truncation-risk count, the maskable assistant-target-token count, the full
exclusion-reason breakdown, two separate stream checksums (see below), and
`data_sufficiency_status`. No raw prompt or response text is ever included.

## Two stream checksums, not one

`input_stream_checksum_sha256` is computed only from tokenized `input_ids`
(plus dataset/tokenizer checksums). `label_stream_checksum_sha256` is
computed only from the response-only `labels` (plus the template checksum
and truncation policy). This separation is deliberate and tested
(`same input IDs + different label mask → different label stream checksum`)
— an input checksum alone cannot prove the label masking actually changed.

## Data sufficiency

`data_sufficiency_status` is exactly one of:

- `sufficient` — eligible records ≥ `BRUD_INSTRUCTION_TUNING_MIN_RECORDS` (1,000 default).
- `limited_instruction_experiment` — some eligible records exist, below the minimum. The experiment may proceed, but every downstream artifact (candidate rationale, manifest, phase report) must carry this limitation explicitly.
- `insufficient` — no eligible records.

Recommended language distribution (Tamil 50–70%, English 10–25%, Tanglish
10–20%, Mixed 5–15%) is reported, never silently rebalanced.
