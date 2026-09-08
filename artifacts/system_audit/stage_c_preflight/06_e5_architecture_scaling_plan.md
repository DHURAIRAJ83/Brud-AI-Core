# Stage C Pre-Flight Audit — 06: E5 Architecture Scaling Plan

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Mathematical Verification

Phase 60 WS07 Stage C E5 is designed to scale model capacity:
$$\text{Parameters: } 528\text{K} \longrightarrow \sim 3.16\text{M} \quad (6.0\times \text{ Capacity Expansion})$$

This capacity expansion addresses the **Severe Under-Parameterization Bottleneck** (FM-01 / RSK-E2E-03) where the 528k parameter model passed only 1 out of 24 functional capability probes (4.17% pass rate).

---

## 2. Mathematical Parameter Derivation

We verify the exact parameter breakdown for the proposed E5 architecture against PyTorch's `TransformerEncoderLayer` and `nn.Embedding` implementations:

### Hyperparameters:
- Vocabulary Size ($V$) = 1,024
- Hidden Dimension ($d_{model}$) = 256
- Attention Heads ($h$) = 8
- Number of Transformer Layers ($L$) = 4
- Feedforward Dimension ($d_{ff}$) = 768  ($3 \times d_{model}$)
- Max Context Length ($T$) = 512

### Parameter Calculations:

1. **Token Embedding Layer (`nn.Embedding(1024, 256)`):**
   $$P_{emb} = V \times d_{model} = 1024 \times 256 = \mathbf{262,144}$$

2. **Per-Layer Multi-Head Attention (`PyTorch MultiheadAttention`):**
   - $W_{in\_proj}$ (Q, K, V concatenated): $3 \times d_{model} \times d_{model} = 3 \times 256 \times 256 = 196,608$
   - $b_{in\_proj}$: $3 \times d_{model} = 3 \times 256 = 768$
   - $W_{out\_proj}$: $d_{model} \times d_{model} = 256 \times 256 = 65,536$
   - $b_{out\_proj}$: $d_{model} = 256$
   $$\text{Subtotal MHA per layer} = 196,608 + 768 + 65,536 + 256 = \mathbf{263,168}$$

3. **Per-Layer Feedforward Network (FFN with $d_{ff}=768$):**
   - $W_1$ (`Linear(256, 768)`): $256 \times 768 = 196,608$
   - $b_1$: $768$
   - $W_2$ (`Linear(768, 256)`): $768 \times 256 = 196,608$
   - $b_2$: $256$
   $$\text{Subtotal FFN per layer} = 196,608 + 768 + 196,608 + 256 = \mathbf{394,240}$$

4. **Per-Layer Layer Normalization (`norm1` + `norm2`):**
   - $2 \times (\text{weight} + \text{bias}) = 2 \times (256 + 256) = \mathbf{1,024}$

5. **Total Per-Layer Parameters ($P_{layer}$):**
   $$P_{layer} = 263,168 + 394,240 + 1,024 = \mathbf{658,432}$$
   $$\text{For } L=4 \text{ layers}: 4 \times 658,432 = \mathbf{2,633,728}$$

6. **Language Model Output Head (`nn.Linear(256, 1024)`):**
   $$P_{head} = d_{model} \times V + V = 256 \times 1024 + 1024 = \mathbf{263,168}$$

7. **Sinusoidal Positional Buffer (`pe`):**
   $$P_{pe} = 0 \quad (\text{registered non-trainable buffer})$$

### GRAND TOTAL TRAINABLE PARAMETERS ($P_{total}$):
$$P_{total} = P_{emb} + 4 \times P_{layer} + P_{head}$$
$$P_{total} = 262,144 + 2,633,728 + 263,168 = \mathbf{3,159,040 \text{ parameters}}$$

$$\mathbf{3,159,040} \approx \mathbf{3.16 \text{M parameters}}$$

---

## 3. Comparative Architecture Grid

| Architectural Metric | Baseline (WS05/E3) | E4 Scaled | E5 Scaled (Target) |
|---|---|---|---|
| **Parameters** | 528,128 (0.53M) | 528,128 (0.53M) | **3,159,040 (3.16M)** |
| **Context Length ($T$)** | 128 | 512 | **512** |
| **Layers ($L$)** | 2 | 2 | **4** |
| **Hidden Dim ($d_{model}$)** | 128 | 128 | **256** |
| **Heads ($h$)** | 4 | 4 | **8** |
| **Head Dim ($d_k$)** | 32 | 32 | **32** |
| **FFN Dim ($d_{ff}$)** | 256 | 256 | **768** |
| **Embedding Params** | 131,072 | 131,072 | **262,144** |
| **Per-Layer Params** | 132,480 | 132,480 | **658,432** |
| **LM Head Params** | 132,096 | 132,096 | **263,168** |

---

## 4. Expected Probe Pass Rate Improvements Post-E5

With a 6.0x capacity increase to 3.16M parameters, the model gains sufficient representational capacity for:
- Basic Tamil morphological inflection matching
- 2-step logical deduction
- Accurate entity extraction & formatting
- Grounded RAG answer synthesis (target CAP pass rate: > 35% across 24 capability probes).
