# Phase 57 Training Objective Report

**Workstream:** 11 — Training Objective Audit  
**Timestamp:** 2026-08-30T17:02:00Z  
**Status:** ✅ AUDIT COMPLETE — OBJECTIVE ALIGNMENT GAP DOCUMENTED

---

## 1. What Phase 56 Optimized

The training objective executed in Phase 56 was standard **unmasked causal language modeling (next-token prediction)** across complete document blocks:

$$\min_\theta \sum_{t=1}^{T-1} -\log P_\theta(x_{t+1} \mid x_1, \ldots, x_t)$$

- **Sequence length:** 64 tokens
- **Masking:** Square subsequent causal mask only (lower triangular)
- **Token loss weights:** Uniform across all non-pad tokens (including prompts, prefixes, and `<unk>`)
- **Prompt masking:** None (pretraining style, not instruction-finetuning style)

---

## 2. Objective Mismatch with Evaluation Requirements

| Dimension | Phase 56 Training Objective | Phase 53/56 Evaluation Requirement | Alignment Status |
|---|---|---|---|
| Task Type | Sequence continuation / document modeling | Prompt-response question answering & instruction following | ❌ Mismatch |
| Prompt Handling | Model learns to predict prompt tokens and punctuation | Model prompt is fixed; model must condition on prompt and generate response | ❌ Mismatch |
| Loss Attribution | 100% of loss computed over full record tokens | Model evaluated solely on generation following the prompt | ❌ Mismatch |
| Special Tokens | Document-level EOS appending | Conversational turn delimiters (`<user>`, `<assistant>`) | ❌ Mismatch |

---

## 3. Why This Caused Capability Decoupling

1. In pretraining mode, minimizing cross-entropy over a dictionary entry like `"அகராதி : ஒரு சொல்லின் பொருள் தரும் நூல்"` trains the model that `"அகராதி"` is followed by `":"`, `"ஒரு"`, etc.
2. But when evaluated with `"தமிழில் 'அகராதி' என்பதன் பொருள் என்ன?"`, the model has never been conditioned to treat `"என்பதன் பொருள் என்ன?"` as an inquiry cue that triggers extraction of `"நூல்"`.
3. Because prompt tokens are not masked during training, the model does not learn asymmetric conditional generation (instruction → response).

**Conclusion:** The objective optimized general token likelihood on unstructured text rather than instruction-conditioned response generation.
