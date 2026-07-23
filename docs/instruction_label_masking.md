# Response-Only Label Masking (Phase 12)

This is the single most safety-critical piece of Phase 12: the guarantee
that loss trains **only** on assistant-response tokens, never on system,
user, or padding tokens.

## Mechanism

`core_model/instruction_tuning/label_masking.py::build_response_labeled_example()`
takes already-tokenized `prompt_token_ids` (everything up to and including
the assistant role marker) and `response_token_ids` (the actual response,
optionally including EOS), and builds:

```
input_ids  = prompt_ids + response_ids  (+ padding)
labels     = [-100]*len(prompt_ids) + response_ids  (+ [-100] padding)
attention_mask = [1]*(len(prompt_ids)+len(response_ids)) + [0] padding
```

`labels` and `input_ids` are always the same length and shape. No shift
happens here — the existing `core_model.training.loss.causal_lm_loss`
(unmodified, reused exactly as base pretraining uses it) does the
shift-by-one internally: `shift_logits = logits[:, :-1, :]`,
`shift_labels = labels[:, 1:]`, then
`F.cross_entropy(..., ignore_index=-100)`. Because that shift is applied
uniformly to the whole sequence, masking the *unshifted* prompt positions
with `-100` is exactly correct — no off-by-one error is introduced by
label masking itself.

## What this guarantees, and how it's tested

- System tokens → `-100` (never a training target).
- User tokens → `-100`.
- The assistant role marker itself → `-100` (it belongs to the prompt
  segment per the formatter's prompt/response split).
- The first actual response token → a real trainable target, and — because
  of the causal shift — the hidden state used to predict it comes from the
  **last prompt position** (the assistant marker), not from itself. This is
  the exact boundary tests in `tests/core_model/test_phase12_instruction_tuning.py`
  assert directly.
- Padding → `-100`.
- At least one assistant-response token must remain trainable; if zero
  target tokens survive (extreme truncation, or an empty response), the
  example is rejected with `reject_reason = "zero_target_tokens"` rather
  than silently trained on nothing.

## Truncation policies

Three policies, `LabelMaskingThresholds.truncation_policy`:

- **`reject`** — any example exceeding `sequence_length` is dropped outright.
- **`truncate_prompt_first`** (default) — the front of the prompt is cut
  first, always preserving the entire response (and therefore its EOS).
  If the response alone still doesn't fit, the prompt is dropped entirely
  and only the front of the response is kept — this is the one case where
  a response is truncated under this policy, and it is counted as
  `truncation_risk_count`, never silent.
- **`truncate_response_tail`** — the prompt is preserved in full; the
  response is cut from the end. If cutting would remove all response
  tokens, the example is rejected (`truncation_would_remove_all_targets`)
  rather than trained on zero targets. If the original response ended in
  EOS and at least 2 response-token slots remain after truncation, EOS is
  re-appended so the truncated response still terminates correctly.

Every truncation (successful or rejected) increments the dataset profile's
`truncation_risk_count` — nothing is truncated silently.

## Stream checksums

`assistant_target_tokens`, `prompt_tokens`, and `ignored_tokens` are counted
per training step (`core_model.training.trainer.run_instruction_tuning`) and
persisted per-run. The run's `label_stream_checksum_sha256` is computed from
the actual label values (plus template checksum and truncation policy) —
changing only the label mask, with identical `input_ids`, produces a
different label checksum, proven by test.
