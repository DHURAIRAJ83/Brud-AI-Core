# Stage D Audit Report — 10: Pretraining vs Supervised Fine-Tuning Analysis

## Token Exposure Requirements
- **Micro Model (528k params):** Requires $\\approx 10\\text{M}$ pretraining tokens.
- **Scaled Model (3.16M params):** Requires $\\approx 50\\text{M}$ pretraining tokens.
- **Current Dataset Exposure:** 855k tokens (0.017x requirement).
- **Conclusion:** Foundation pretraining data pipeline must precede future architecture scaling.
