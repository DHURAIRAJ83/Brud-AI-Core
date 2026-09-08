# Stage D Audit Report — 09: Model Training Quality & E5 Capability Failure Analysis

## Root Cause Analysis for E5 (3.16M params, 0/24 raw CAP pass rate)
1. **Severe Undertraining & Token Exposure Deficit:** E5 has 3,159,040 parameters. It was trained on 1,670 records (855k tokens) for 2 epochs = **1.71M total token exposure**.
2. **Tokens-per-Parameter Ratio:** $\\frac{1.71\\text{M tokens}}{3.16\\text{M params}} = 0.54$ tokens/param. Standard LLM pretraining requires **$15 - 20$ tokens per parameter** ($50\\text{M}+$ tokens for a 3.16M model).
3. **Pretraining vs SFT Deficit:** E5 was initialized from random weights and trained via pure SFT on small instruction data without a foundation pretraining corpus.
