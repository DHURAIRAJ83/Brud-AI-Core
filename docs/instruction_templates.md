# Instruction Templates (Phase 12)

`core_model/instruction_tuning/templates.py` defines a versioned, fixed
single-exchange Brud instruction format:

```
<bos> <system> {system text} <user> [<lang>] {instruction} [{input}] <assistant>
{response} <eos>
```

## Why exactly this shape

- **BOS appears exactly once**, at the very start of the prompt segment.
- **EOS appears exactly once**, at the very end of the response segment.
- The template is deliberately a fixed single system/user/assistant
  exchange, not a repeating multi-turn structure — this keeps role-token
  usage bounded and predictable, which is what makes exact label-mask
  alignment possible (see [instruction_label_masking.md](instruction_label_masking.md)).
  Multi-turn `chat` records are handled by the dataset validator, not the
  template: earlier turns are flattened into plain history text inside the
  single `<user>` section, and only the final `assistant` turn becomes the
  trainable response.
- A language marker (`<ta>`, `<en>`, `<tgl>`, `<mixed>`) may be inserted
  after `<user>` according to `insert_language_marker` — an explicit
  template option, not an automatic behavior.

## Formatter contract

`core_model/instruction_tuning/formatter.py::render_example()` returns a
`(prompt_text, response_text)` pair split exactly at the assistant boundary
— the assistant role marker is the last token of `prompt_text`, and the
actual response is the entirety of `response_text`. This split is what lets
label masking work correctly without re-parsing rendered text: the prompt
segment is tokenized and masked, the response segment is tokenized and kept
trainable.

`detect_special_token_collisions()` reports (never silently strips) any
literal special-token string that appears inside raw user/response text —
counted in the dataset profile's `special_token_collision_count`.

## Tokenizer compatibility

`validate_template_against_tokenizer(template, special_tokens)` checks the
template's required tokens against the tokenizer's **actual persisted**
`tokenizer_versions.special_tokens_json` — never the `SPECIAL_TOKENS` Python
constant, since a trained tokenizer's real token set may differ from the
default used at training time. A template with any missing required token
is `is_valid = false` and cannot be assigned to an experiment
(`patch_experiment` rejects it).

## Determinism and checksum

`template_checksum()` is a SHA-256 hash of the template's full JSON
representation (`template_to_dict`, which converts dataclass tuples/dicts to
JSON-safe lists/dicts first). Two templates created with identical fields
always produce the identical checksum — verified by test. The raw dataset
record is never mutated by templating; rendering is a pure, read-only
transformation.
