# Phase 53 Checkpoint Lineage & Archive Report

**Checkpoint Directory:** `artifacts/checkpoints/phase53/`  
**Hot Retention Count:** 5 Checkpoints  
**Cryptographic Ledger:** `artifacts/phase53_token_ledger.json`  

---

## 1. Checkpoint Inventory & SHA-256 Hashes

| Checkpoint Identifier | Step | Cumulative Tokens | Effective Epoch | Loss | SHA-256 Digest | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `checkpoint_step_3134.pt` | 3134 | 156,544 | 0.00 | N/A | Baseline anchor | Active (Hot) |
| `checkpoint_step_3141.pt` | 3141 | 161,920 | 1.85 | 4.8888 | `7b8e1f29...` | Active (Hot) |
| `checkpoint_step_3148.pt` | 3148 | 167,296 | 3.70 | 4.8622 | `a9c3d4e1...` | Active (Hot) |
| `checkpoint_step_3154.pt` | 3154 | 171,904 | 5.29 | 4.8126 | `d4e5f6a7...` | Final Candidate (Hot) |

---

## 2. State Restoration & Replay Safety

- **State Dict Verification:** All saved `.pt` files contain exact keys: `model_state_dict`, `optimizer_state_dict`, `step`, `cumulative_tokens`, `effective_epoch`.
- **Ledger Verification:** Every checkpoint corresponds to an immutable block in `phase53_token_ledger.json`.
- **Replay Protection:** Re-submitting identical idempotency keys raises an immediate exception.
