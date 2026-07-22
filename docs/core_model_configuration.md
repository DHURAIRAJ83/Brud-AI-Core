# Core Model Configuration

## Presets

`Brud Core Micro`:

- hidden size 128
- intermediate size 384
- 4 layers
- 4 attention heads
- context length 256

`Brud Core Tiny`:

- hidden size 256
- intermediate size 768
- 6 layers
- 8 attention heads
- context length 512

Tests also use smaller bounded overrides for fast CPU verification.

## Validation

Validation checks vocabulary size, context length, hidden/head divisibility, even RoPE head dimension, dropout bounds, token IDs, parameter limits, memory limits, and tokenizer compatibility.

## Estimates

Parameter estimates are deterministic and compared with the actual PyTorch parameter count after safe model construction. Memory estimates include parameters, gradients, optimizer state, activations, inputs, and a safety margin; they are conservative planning estimates, not exact runtime measurements.
