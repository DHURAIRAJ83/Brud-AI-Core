# Phase 57 Training Target Alignment Report

**Workstream:** 5 — Tokenizer & Label Alignment Audit  
**Timestamp:** 2026-08-30T16:45:00Z  
**Status:** ⚠️ CRITICAL REPRESENTATION DEFECT IDENTIFIED (HIGH UNK FREQUENCY)

---

## 1. Causal LM Objective & Label Shifting

The mathematical formulation of causal next-token prediction in the Phase 56 training loop was audited:

$$\mathcal{L} = \text{CrossEntropy}\Big(\mathbf{Z}_{0:T-1}, \mathbf{X}_{1:T}, \text{ignore\_index}=0\Big)$$

- **Input tokens:** $\mathbf{X}_{0:T-1}$
- **Target tokens:** $\mathbf{X}_{1:T}$
- **Alignment:** At time $t$, input $x_t$ correctly predicts $x_{t+1}$.
- **Label leakage:** None. The causal mask strictly prevents future token visibility.
- **Padding tokens:** PAD ID = 0 is correctly ignored in loss computation.

---

## 2. Tokenizer Representation Defect: The 29.17% UNK Crisis

While the loss calculation mechanics are correct, the **tokens themselves suffer from severe representational collapse**:

| Corpus Scope | Total Tokens Encoded | `<unk>` Tokens (ID 1) | `<unk>` Token Percentage |
|---|---|---|---|
| Entire Phase 55 Corpus | 50,037 | 14,594 | **29.17%** |
| Train Split (316 records) | 40,490 | 11,811 | **29.17%** |
| Val Split (40 records) | 4,772 | 1,391 | **29.15%** |
| Test Split (40 records) | 4,775 | 1,392 | **29.15%** |
| Evaluation Probe Prompts | 1,867 | 418 | **22.39%** |

### Why Did This Happen?
The SentencePiece model (`data/tokenizers/versions/tok/v1/tokenizer.model`) has an artificial vocabulary ceiling of **only 64 tokens**. It was initialized on a toy synthetic dataset containing limited phrases ("வணக்கம்", "hello", "English").

As a consequence, **standard Tamil characters and common English letters are completely missing from the vocabulary**:
- Tamil vowels/consonants mapped to `<unk>`: `அ`, `ர`, `ப`, `சு`, `பொ`, `ரா`, `பு`, `ா`, `ு`, `ள`
- English letters mapped to `<unk>`: `w`, `b`, `c`, `f`, `j`, `p`, `q`, `u`, `z`, and capital letters `P`, `A`, `B`, `C`, `T`
- All numerical digits mapped to `<unk>`: `0`, `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`

---

## 3. Impact on Training and Loss

1. When nearly 1 in every 3 tokens in the training set is token `1` (`<unk>`), the training objective strongly rewards the model for predicting `<unk>`.
2. As the model learns character frequency statistics on the training split, its output distribution heavily biases toward `<unk>` (token 1) and whitespace (token 37).
3. **Loss decreased from 4.98 to 4.13 primarily because the model learned the high frequency of `<unk>` and common bigrams**, not because it learned Tamil grammar, reasoning, or domain knowledge!

**Key Finding:** The causal language modeling objective was correctly implemented, but the tokenizer represents a lossy, unlearnable signal where semantic information is wiped out by `<unk>` replacement.
