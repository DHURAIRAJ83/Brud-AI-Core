# Phase 37 — Training Run Report

## 1. Real PyTorch Training Verification
- **Architecture**: `BrudForCausalLM`
- **Optimizer**: `AdamW` (lr=1e-2, weight_decay=0.01)
- **Loss Function**: `CrossEntropyLoss`
- **Parameter Mutation Evidence**:
  - Initial embedding tensor copied before forward pass.
  - Backpropagation and optimizer step executed.
  - `torch.equal(w_before, w_after) == False` empirically verified in `test_003_real_training_step_mutates_model_weights`.
- **Loss Trajectory**: Initial batch loss decreased on subsequent step pass.
- **Resource Limits**: Executed entirely on CPU with bounded context and zero GPU dependencies.
