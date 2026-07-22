# Pretraining Checkpoints

Checkpoints are written under `BRUD_PRETRAINING_DIR` using server-generated safe names.

Layout:

```text
data/core_models/pretraining/<job-public-id>/step-00000020-<suffix>/
  model_state.pt
  optimizer_state.pt
  scheduler_state.pt
  rng_state.pt
  trainer_state.json
  config.json
  references.json
  manifest.json
  checksums.txt
```

The checkpoint manager writes to a temporary directory first, calculates SHA-256 checksums, then atomically promotes the directory. Loading is restricted to registered checkpoint metadata. `torch.load` uses CPU mapping and `weights_only=True` when supported.

Resume restores model, optimizer, scheduler, RNG, processed-token count, and block position from the latest checkpoint.
