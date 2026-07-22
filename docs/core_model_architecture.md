# Core Model Architecture

Phase 8 implements `BrudForCausalLM`, a CPU-first decoder-only Transformer.

## Components

- Token embeddings with padding index support.
- RMSNorm before attention and feed-forward blocks.
- Rotary positional embeddings for attention heads.
- Causal self-attention with padding-mask support.
- SwiGLU feed-forward blocks.
- Residual connections.
- Final RMSNorm.
- Language-model output head.
- Shifted causal language-model loss.

## Current limitations

The model is randomly initialized and only smoke-tested. It is not pretrained, instruction-tuned, chat-capable, quantized, or exported to deployment formats.
