# Model Cards (Phase 14)

`core_model/release/model_card.py` generates and validates a versioned
model card from already-registered, already-verified data only — it
never invents a capability claim, and a card describing an
evaluation-blocked model as capable or production-ready must fail
validation.

## 24 required sections

```
model_name, version, release_family, summary, architecture,
parameter_count, context_length, tokenizer, training_datasets,
dataset_limitations, base_training, instruction_tuning, evaluation,
supported_languages, intended_uses, out_of_scope_uses,
known_limitations, safety_limitations, resource_requirements,
licence_and_provenance, artifact_checksums, release_status,
deployment_eligibility, public_chat_assignment_status
```

`render_model_card()` renders these in a fixed order, one `## Title`
header per section, always followed by the three required honesty
statements verbatim:

* *"This model has not been proven to provide production-grade factual
  accuracy."*
* *"Evaluation results are bounded by the size and quality of the
  available datasets and fixtures."*
* *"Release registration does not automatically make the model
  available to the public chatbot."*

## Validation reads the rendered markdown, not a separate dict

`validate_model_card()` takes only the rendered `markdown` string —
`parse_model_card_sections()` parses it back into a section dict using
the exact same fixed header format `render_model_card()` produces. This
is deliberate: an earlier draft of this module took a separate `fields`
dict as the source of truth for section-presence checks, which meant
validation could pass or fail based on data the caller forgot to
re-supply, disconnected from what the card actually says. Reading only
the markdown means validation always reflects the card's real content.

## What validation checks

* Every required section is present and non-empty (not the
  `_Not provided._` placeholder).
* No absolute filesystem path or secret-shaped string appears anywhere
  in the card.
* No unsupported capability phrase (`"production-ready"`,
  `"guaranteed safe"`, `"fully accurate"`, ...) appears unless
  `evaluation_status == "eligible"`.
* All three honesty statements are present verbatim.
* A card for an `evaluation_blocked` candidate must not contain
  `"capable"`, `"ready for users"`, or `"production"` — a hard
  misleading-claim check independent of the phrase list above.
* The card's stated parameter count and checkpoint checksum match the
  candidate's actually-registered values.
* The `public_chat_assignment_status` section, when the candidate is
  `not_public_chat_ready`, must actually say so (`"none"`, `"not
  assigned"`, or `"placeholder"`) — a card cannot claim public
  availability that does not exist.

A card failing any of the above is `validation_status = "invalid"`, with
every specific issue listed — never a bare pass/fail.
