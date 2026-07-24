# Admin Diagnostic Inference (Phase 15)

`POST /api/admin/inference-runtime/assignments/{public_id}/diagnostic-generate`

## Requirements

* The assignment's scope must be exactly `admin_diagnostic` and its
  status must be `active` (i.e. validated, approved, and activated).
* The prompt is bounded (1–4000 characters); the effective
  `maximum_new_tokens` is `min(requested, profile maximum)` — a caller
  can only tighten the bound, never loosen it.
* The runtime instance is loaded on demand
  (`_ensure_loaded()` → verify-then-load, per
  `docs/inference_model_loading.md`) if it is not already serving the
  assignment's exact release.

## Response always includes the disclaimer

```
"Admin-only diagnostic generation. This output is not from the public chatbot."
```

verbatim, alongside `generated_text`, `stop_reason`,
`input_token_count`, `output_token_count`, `runtime_milliseconds`,
`role_token_leakage`, `prompt_leakage`, and `unicode_valid` — every flag
Phase 12's post-hoc checks (`no_role_token_leakage`,
`no_system_prompt_leakage`, `valid_unicode`) can raise, reused
unchanged.

## No persistence beyond the evidence trail

The route never writes to `chat_sessions`/`chat_messages`, never
creates a session, and never triggers an automatic assignment. It does
record one `inference_requests` row (prompt checksum only, never the
raw prompt) and one `inference_results` row (output checksum plus the
structural flags above) — the same evidence discipline every other
Phase 15 generation path uses.

## Honest behavior on an undertrained model

During manual verification, the synthetic Micro-scale fixture model
(tens of thousands of parameters, never meaningfully trained) produced
`stop_reason: "role_token_leakage"` with empty `generated_text` on a
real diagnostic prompt — the mid-generation leakage guard correctly
stopped generation rather than returning a role-token-contaminated
string. This is reported honestly in `docs/phase_15_report.md`, not
hidden: the mechanism works exactly as designed, and the fixture's
actual output quality is not, and was never claimed to be, evidence of
a capable chatbot.
