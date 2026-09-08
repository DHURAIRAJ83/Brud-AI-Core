# Stage C Pre-Flight Audit — 07: Hardware Feasibility Analysis

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Host Hardware Ceiling Constraints

All training experiments in Stage C (E4 and E5) MUST strictly respect the host execution boundaries:

```text
CPU CORES / THREADS  = 2 threads (torch.set_num_threads(2))
RAM CEILING          = 2.0 GB (2,048 MB)
SWAP CEILING         = 0 MB (zero swap usage allowed)
DEVICE               = CPU (PyTorch CPU execution)
```

---

## 2. Quantitative Static Memory & Runtime Model

### A. Parameter & Optimizer Footprint (fp32)
- **Parameters ($P = 3.16\text{M}$):** $3,159,040 \times 4 \text{ bytes} = \mathbf{12.64 \text{ MB}}$
- **Gradients:** $3,159,040 \times 4 \text{ bytes} = \mathbf{12.64 \text{ MB}}$
- **AdamW Optimizer States ($m$ and $v$):** $2 \times 3,159,040 \times 4 \text{ bytes} = \mathbf{25.28 \text{ MB}}$
- **Subtotal Model State:** $\mathbf{50.56 \text{ MB}}$

### B. Activation Memory Footprint per Batch ($T=512, d_{model}=256, h=8, d_{ff}=768$)
For a batch size $B = 4$:
- Input Tensor ($B \times T \times d_{model}$): $4 \times 512 \times 256 \times 4 \text{ bytes} = 2.10 \text{ MB}$
- QKV Projections: $3 \times 2.10 \text{ MB} = 6.29 \text{ MB}$
- Attention Matrix ($B \times h \times T \times T$): $4 \times 8 \times 512 \times 512 \times 4 \text{ bytes} = 33.55 \text{ MB}$
- Softmax & Attention Output: $33.55 + 2.10 = 35.65 \text{ MB}$
- FFN Activations ($B \times T \times d_{ff}$): $4 \times 512 \times 768 \times 4 \text{ bytes} = 6.29 \text{ MB}$
- Layer Norms & Residuals: ~$2.0 \text{ MB}$
- **Per-Layer Activation Total:** ~$83.8 \text{ MB}$
- **For $L=4$ Layers (B=4):** $\mathbf{335.2 \text{ MB}}$

### C. Total Peak Memory & Overhead Estimation

$$\text{Peak RSS} = \text{Model State} + \text{Activations} + \text{PyTorch Runtime Overhead} + \text{DataLoader Buffer}$$

| Experiment | Batch Size ($B$) | Seq Length ($T$) | Model State | Activations | PyTorch RSS Overhead | Estimated Peak RSS | RAM Ceiling Limit | Safety Margin | Swap Pressure |
|---|---|---|---|---|---|---|---|---|---|
| **Baseline (WS05)** | 16 | 128 | 8.4 MB | ~160 MB | ~200 MB | **~368 MB** | 2,048 MB | 1,680 MB (82%) | 0 MB |
| **E4 Context Scaled** | 8 | 512 | 8.4 MB | ~160 MB | ~210 MB | **~378 MB** | 2,048 MB | 1,670 MB (82%) | 0 MB |
| **E5 Arch Scaled (B=8)** | 8 | 512 | 50.6 MB | ~670 MB | ~250 MB | **~970 MB** | 2,048 MB | 1,078 MB (53%) | 0 MB |
| **E5 Arch Scaled (B=4)** | **4** | **512** | **50.6 MB** | **~335 MB** | **~240 MB** | **~625 MB** | **2,048 MB** | **1,423 MB (69%)** | **0 MB** |

---

## 3. Resource Risk Determination

```text
E5_RESOURCE_RISK = FALSE  (When executing with Batch Size B=4)
```

### Risk Assessment Verdict:
1. **RAM Ceiling:** Peak RSS of ~625 MB for B=4 is **less than 31% of the 2,048 MB RAM ceiling**.
2. **Swap Usage:** 0 MB swap required. Memory stays entirely within physical RAM.
3. **CPU Execution:** 2 CPU threads with `torch.set_num_threads(2)` can process ~1,885 dataset records in 470 steps (B=4) in approximately 45–60 seconds per epoch.

---

## 4. Mandatory Hardware Execution Protocol for Stage C

When Stage C training is eventually authorized by a human operator:
- Enforce `batch_size = 4` for E5.
- Enforce `torch.set_num_threads(2)`.
- Enable active memory polling via `resource_guard.py` with hard exit at 1,800 MB RSS.
