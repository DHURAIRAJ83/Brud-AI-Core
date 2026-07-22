# Core Model Checkpoints

## Layout

Registered checkpoints are stored under `BRUD_CORE_CHECKPOINT_DIR` using safe server-generated names. Each checkpoint directory contains:

- `config.json`
- `model_state.pt`
- `artifact_manifest.json`
- `checksums.txt`

## Safety

Only registered checkpoint directories are loaded. The loader verifies the manifest and checksums before loading a PyTorch state dictionary. `weights_only=True` is used when supported by the installed PyTorch version.

Unexpected or missing state keys are rejected through strict loading.

## Verification

Checkpoint round trip initializes a model, saves weights, reloads the state dictionary, and compares forward logits on the same bounded input.
