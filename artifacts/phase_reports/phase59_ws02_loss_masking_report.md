# Phase 59 WS02 — Loss Masking & Causal Alignment Report

**Workstream:** 02 — Dataset Transformation Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **LOSS MASKING & CAUSAL ALIGNMENT FULLY QUALIFIED**

---

## 1. Executive Summary

This report establishes the empirical verification of response-only loss masking and causal sequence alignment for the Phase 59 dataset transformation pipeline. In supervised instruction fine-tuning, training loss must be calculated strictly on assistant response tokens. Computing loss over prompt, system, or user tokens destroys instruction-following dynamics and causes prompt memorization.

Using `core_model/instruction_tuning/label_masking.py` and `core_model/training/loss.py`:
- All prompt tokens (BOS, system, user, language indicator, instruction body, input context, and assistant role marker) are strictly masked with `ignore_index = -100`.
- All padding tokens are masked with `ignore_index = -100`.
- Only actual assistant response tokens and the terminal `</s>` (EOS) token are assigned active target IDs in `labels`.
- Causal language modeling shift (`shift_logits = logits[:, :-1, :]` vs `shift_labels = labels[:, 1:]`) is mathematically aligned: the `<assistant>` token position predicts the first response token, and each response token predicts its successor.

---

## 2. Loss Masking Quantitative Telemetry

Evaluated across all 396 transformed sequences at context length $T = 128$:

| Metric | Measured Value | Percentage of Total Tokens | Verification Finding |
|---|---|---|---|
| **Total Sequences Evaluated** | **396** | 100.0% | All Phase 55 records covered |
| **Total Sequence Length** | **128 tokens** | Constant | Matches Model v2 context window |
| **Total Token Positions ($396 \times 128$)** | **50,688** | 100.0% | Complete matrix capacity |
| **Total Prompt Tokens (Masked)** | **12,897** | **25.44%** | `labels[t] == -100` |
| **Total Response Tokens (Supervised)** | **18,719** | **36.93%** | `labels[t] == target_id` |
| **Total Padding Tokens (Masked)** | **19,072** | **37.63%** | `labels[t] == -100` |
| **Total Masked Positions (`-100`)** | **31,969** | **63.07%** | Exact match: $12,897 + 19,072$ |
| **Total Supervised Positions (`!= -100`)** | **18,719** | **36.93%** | Exact match with response tokens |
| **Prompt Loss Contribution** | **0.0000** | 0.00% | Zero gradient from prompt tokens |
| **Response Loss Contribution** | **100.0%** | 100.0% | Complete gradient focus on response |

---

## 3. Structural Sequence Anatomy & Token Boundaries

A representative example from the vocabulary domain demonstrates the exact boundary mechanics:

```text
Sequence Index: 0 (Domain: government)
Prompt Text:
  <s> <system> <user> <ta> government தொடர்பான பின்வரும் தகவலை விளக்குக: <assistant>
Response Text:
  பொது சுகாதார விழிப்புணர்வு நிகழ்ச்சிகள் ஒவ்வொரு மாதமும் நடத்தப்படும். </s>
```

### Token-by-Token Boundary Map

| Position ($t$) | Token ID | Piece Representation | Role | Label Value | Supervision State |
|---|---|---|---|---|---|
| `0` | `2` | `<s>` | BOS | `-100` | ❌ Masked (No loss) |
| `1` | `893` | `▁` | Whitespace prefix | `-100` | ❌ Masked |
| `2` | `4` | `<system>` | System delimiter | `-100` | ❌ Masked |
| `3` | `893` | `▁` | Whitespace prefix | `-100` | ❌ Masked |
| `4` | `5` | `<user>` | User delimiter | `-100` | ❌ Masked |
| `5` | `893` | `▁` | Whitespace prefix | `-100` | ❌ Masked |
| `6` | `7` | `<ta>` | Language indicator | `-100` | ❌ Masked |
| `...` | `...` | `[Prompt tokens]` | Instruction body | `-100` | ❌ Masked |
| `p_len - 1` | `6` | `<assistant>` | Assistant boundary | `-100` | ❌ Masked |
| `p_len` | `285` | `▁பொ` | First response token | `285` | ✅ Supervised Target |
| `p_len + 1` | `902` | `து` | Subword token | `902` | ✅ Supervised Target |
| `...` | `...` | `[Response tokens]` | Response body | `...` | ✅ Supervised Target |
| `p_len + r_len - 1` | `3` | `</s>` | EOS delimiter | `3` | ✅ Supervised Target |
| `p_len + r_len` | `0` | `<pad>` | Pad token | `-100` | ❌ Masked |
| `...` | `0` | `<pad>` | Pad tokens to 128 | `-100` | ❌ Masked |

---

## 4. Causal Shift Alignment Proof

In causal language modeling (`core_model/training/loss.py:causal_lm_loss`), the loss computation operates as:
```python
shift_logits = logits[:, :-1, :].contiguous()
shift_labels = labels[:, 1:].contiguous()
loss = F.cross_entropy(shift_logits.view(-1, V), shift_labels.view(-1), ignore_index=-100)
```

### Mathematical Proof of Correct Conditioning
1. **Prompt Boundary Conditioning**:
   - The token `<assistant>` is located at prompt position $t = p_{\text{len}} - 1$.
   - Its output logit is $\text{shift\_logits}[:, p_{\text{len}} - 1, :]$.
   - The target label evaluated against this logit is $\text{shift\_labels}[:, p_{\text{len}} - 1] = \text{labels}[:, p_{\text{len}}]$.
   - $\text{labels}[:, p_{\text{len}}]$ is the **exact first token ID of the assistant response**.
   - **Conclusion:** The model learns to emit the first response token directly conditioned on the prompt and the assistant role marker.

2. **Internal Prompt Isolation**:
   - For all prompt positions $t < p_{\text{len}} - 1$, the target label is $\text{shift\_labels}[:, t] = \text{labels}[:, t+1] = -100$.
   - **Conclusion:** No loss or gradient is computed across internal prompt tokens. Changing prompt phrasing does not produce loss targets.

3. **Terminal EOS Conditioning**:
   - The final response token precedes the terminal $\text{EOS}$ (`</s>` = ID 3).
   - Its logit predicts $\text{EOS}$ at label index $p_{\text{len}} + r_{\text{len}} - 1$.
   - **Conclusion:** The model is explicitly trained to terminate generation with `</s>`.

4. **Padding Invariance**:
   - For all positions $t \ge p_{\text{len}} + r_{\text{len}}$, $\text{labels}[:, t] = -100$.
   - Cross-entropy loss ignores all positions where target is `-100`.
   - **Conclusion:** Variable-length sequences padded to context length 128 produce zero gradient contribution from padding positions.

---

## 5. Truncation Policy Safety Analysis

The audit evaluated two candidate truncation policies for handling sequences exceeding context length 128:
1. `truncate_prompt_first`:
   - Left-truncates prompt context when length $> 128$.
   - **Critical Vulnerability Identified:** When response length alone equals 128, the entire prompt is truncated away (`prompt_token_count = 0`), leaving an unconditioned sequence where `labels[0]` becomes a target. This occurred in 56 records.
   - **Action:** Policy rejected as unsafe for instruction learning.
2. `truncate_response_tail`:
   - Preserves 100% of the prompt context and role markers (`<s> <system> ... <user> [<lang>] {instruction} <assistant>`).
   - Truncates long response tails to fit within context length, while strictly preserving terminal `</s>` (EOS).
   - **Audit Result:** `prompt_token_count > 0` across 100% of records; BOS and `<assistant>` boundaries preserved across 100% of records.
   - **Action:** Adopted as the authoritative qualification policy for Phase 59.

---

## 6. Loss Masking Verdict

**STATUS: PASS.** Response-only loss masking is formally verified, mathematically aligned with causal language modeling, and certified free of prompt exposure or padding contamination.
