# Phase 61 WS03 Report — 02: 17-Step Governed Acquisition Architecture

## 17-Step Pipeline
1. Source Registry $\\rightarrow$ 2. Rights Check $\\rightarrow$ 3. Raw Acquisition $\\rightarrow$ 4. Raw SHA-256 Hashing $\\rightarrow$ 5. Provenance Record $\\rightarrow$ 6. Text Extraction $\\rightarrow$ 7. Unicode NFC Normalization $\\rightarrow$ 8. Control Char Removal $\\rightarrow$ 9. Language ID $\\rightarrow$ 10. Quality Engine (19 Rules) $\\rightarrow$ 11. Exact SHA-256 Dedup $\\rightarrow$ 12. Tokenizer v2 Token Accounting $\\rightarrow$ 13. Domain Classify $\\rightarrow$ 14. Synthetic Classify $\\rightarrow$ 15. Admin Review $\\rightarrow$ 16. Approval $\\rightarrow$ 17. SHA-256 Dataset Seal.
