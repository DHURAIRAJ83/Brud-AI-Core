# Tokenizer Evaluation

Tokenizer evaluation is deterministic and local.

## Metrics

Stored metrics include:

- `total_characters`
- `total_tokens`
- `characters_per_token`
- `tokens_per_word`
- `unknown_token_rate`
- `byte_fallback_rate`
- `round_trip_success_rate`
- `special_token_collision_count`
- `tamil_grapheme_split_warning_rate`
- `long_sequence_rate`
- `compression_ratio`

Metrics are stored by `ta`, `en`, `tgl`, `mixed`, and `overall` where samples are available.

## Scope

Evaluation checks round-trip behavior, token counts, unknown-token usage, long sequences, and simple Tamil/English/Tanglish/mixed fixtures. It does not claim linguistic morpheme quality or semantic correctness.

Activation is blocked when artifact verification fails or the configured readiness threshold is not met.
