# Pretraining Validation

Validation uses the validation split only and runs under `torch.no_grad()`.

Persisted evaluation evidence includes:

- validation loss;
- finite-status details;
- evaluated step;
- checkpoint reference when available.

Perplexity may be added when finite and safe. Validation loss is not a semantic language-quality claim.

Preflight checks verify dataset status, tokenizer status, architecture status, CPU device, config bounds, NumPy availability, and resource settings.
