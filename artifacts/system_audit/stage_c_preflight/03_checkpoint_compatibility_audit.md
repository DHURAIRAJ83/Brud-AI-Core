# Stage C Pre-Flight Audit — 03: Checkpoint Compatibility Audit

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & SHA Inventory

We performed a bit-for-bit forensic analysis of all key frozen baseline checkpoints across Phase 59, WS05, and WS07.

```text
PHASE 59 CHECKPOINT SHA   = a5218b5bdb94d3b218896f3021d7f7d5298023036d350bf8a2d5e3b70423371a
WS05 CHECKPOINT SHA       = 30dbb8927c0c61c786683c06eebf8a2718054a4cf1df25ece47f97ca7c605421
TOKENIZER V2 MODEL SHA    = 65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4
```

---

## 2. Deep Checkpoint Inspection Table

| Checkpoint Name | Disk Location | SHA-256 (First 16 chars) | Size (Bytes) | Params | State Dict Keys | `pe` Key Present? | Key Action for Loading |
|---|---|---|---|---|---|---|---|
| **Phase 59 Baseline** | `artifacts/candidates/phase59/checkpoints/checkpoint_best.pt` | `a5218b5bdb94d3b2` | 6,376,854 | 528,128 | 27 | ❌ No | Direct load compatible |
| **WS05 Baseline** | `artifacts/candidates/phase60/checkpoints/checkpoint_best.pt` | `30dbb8927c0c61c7` | 6,442,143 | 528,128 | 28 | ✅ Yes (`[1, 128, 128]`) | Requires key filtering or `strict=False` |
| **WS07 Stage A** | `artifacts/candidates/phase60/ws07/outputs/ws07_stage_a_checkpoint.pt` | Evaluated | N/A (Diagnostic) | 528,128 | 27 | ❌ No | Uses WS05 as input |
| **E3-A..E3-E** | `artifacts/candidates/phase60/ws07/e3/outputs/` | Sealed Candidates | ~6.4 MB | 528,128 | 27 | ❌ No | Uses WS05 as initialization base |

---

## 3. Investigation of the `pe` Key Anomaly

### Root Cause
In `run_controlled_training_ws05.py`, the positional encoding buffer was registered as:
```python
self.register_buffer("pe", self._build_sinusoidal_pe(128, d_model)) # persistent defaults to True
```
This caused PyTorch to save the static sinusoidal tensor (`pe`, shape `[1, 128, 128]`) into `checkpoint_best.pt`.

In all subsequent models (WS06, WS07 Stage A, E3), the buffer registration was updated to:
```python
self.register_buffer("pe", self._build_sinusoidal_pe(128, d_model), persistent=False)
```
When a model with `persistent=False` loads the WS05 checkpoint using `model.load_state_dict(ckpt, strict=True)`, PyTorch raises:
`RuntimeError: Unexpected key(s) in state_dict: "pe"`.

---

## 4. Checkpoint Migration Strategy for Stage C (E4 & E5)

### Rule: NO Blind Exception Suppression
We MUST NOT simply wrap checkpoint loading in a silent `try...except` or rely blindly on `strict=False` without reporting key reconciliation telemetry.

### Mandatory Controlled Migration Adapter Specification:
For Stage C E4 and E5 model loaders, we specify the explicit `load_checkpoint_safely` routine:

```python
def load_checkpoint_safely(model: torch.nn.Module, checkpoint_path: Path) -> dict:
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    state_dict = ckpt.get("model_state_dict", ckpt)
    
    # Filter non-persistent buffer keys if target model does not expect them
    model_state = model.state_dict()
    filtered_state = {}
    unexpected_keys = []
    missing_keys = []
    shape_mismatches = []
    
    for k, v in state_dict.items():
        if k in model_state:
            if model_state[k].shape == v.shape:
                filtered_state[k] = v
            else:
                shape_mismatches.append((k, v.shape, model_state[k].shape))
        else:
            unexpected_keys.append(k)
            
    for k in model_state.keys():
        if k not in state_dict and k not in filtered_state:
            missing_keys.append(k)
            
    # Explicitly load matching parameters
    missing, unexpected = model.load_state_dict(filtered_state, strict=False)
    
    report = {
        "loaded_keys_count": len(filtered_state),
        "unexpected_keys": unexpected_keys, # e.g. ['pe'] from WS05
        "missing_keys": missing_keys,
        "shape_mismatches": shape_mismatches # Expected when scaling to E5 (d_model 128 -> 256)
    }
    return report
```

### Behavior for E4 vs E5:
- **E4 Context Scaling (528k params, T=128 -> 512):** All 27 core weight shapes match bit-for-bit (`d_model=128`). `unexpected_keys=['pe']` is filtered cleanly. Zero shape mismatches.
- **E5 Architecture Scaling (3.16M params, L=4, d=256, T=512):** E5 is a structural capacity scaling phase. Layer count and embedding dimensions increase (`d_model=256`). Therefore, E5 starts with initialized weights or warm-started embeddings, and `shape_mismatches` telemetry will explicitly record layer expansion.
