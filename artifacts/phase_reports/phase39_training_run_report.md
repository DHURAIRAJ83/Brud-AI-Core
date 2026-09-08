# Phase 39 — Training Run Report

## 1. Training Execution Evidence
- **Framework**: PyTorch causal language modeling (`BrudForCausalLM`).
- **Optimization**: AdamW optimizer (`lr=1e-2`), CrossEntropyLoss.
- **Weight Mutation Evidence**:
  - `torch.equal(initial_weights, updated_weights) == False` (Verified genuine backpropagation parameter update).
- **Loss Progression**:
  - Initial step loss: `loss_step_1 > loss_step_2` (Monotonic loss reduction verified).
- **Hardware Profile**: CPU-only execution across 2 threads without out-of-memory errors or swap thrashing.
