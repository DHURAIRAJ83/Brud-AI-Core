# Core Model Smoke Testing

The smoke test is a bounded trainability check, not language-model training.

## Fixture

The test uses a tiny deterministic token sequence, batch size 1, CPU, AdamW, and a small bounded step count.

## Success criteria

- Initial loss is finite.
- Final loss is lower than initial loss.
- Gradients are finite.
- Step count is within configuration limits.

This does not prove language understanding and must not be presented as chatbot capability.
