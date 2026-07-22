# Core Model Attention

The Phase 8 attention module uses standard multi-head causal self-attention.

## Shape conventions

Inputs are `[batch, sequence, hidden]`. Query, key, and value tensors are reshaped to `[batch, heads, sequence, head_dim]`.

## RoPE

Rotary embeddings are applied to query and key tensors. Head dimension must be even. The RoPE cache is bounded by configured context length and is device/dtype aware.

## Masks

Causal masking prevents each position from reading future tokens. Padding masks prevent attention to padded keys. Tests verify future-token isolation.

## CPU behavior

The implementation uses standard PyTorch tensor operations and does not require CUDA or custom native extensions.
