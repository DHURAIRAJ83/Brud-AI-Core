# Stage C Pre-Flight Audit — 08: E4/E5 Dataset Strategy

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Dataset Candidate Analysis

We evaluated all candidate dataset splits (Phase 59, WS03/WS05 base dataset, and E3 expansion splits E3-A through E3-E) to determine the optimal training dataset for Stage C E4 and E5 experiments.

```text
RECOMMENDED_E4_DATASET = E3-E (Sealed Multilingual + Conversational + Instruction)
RECOMMENDED_E5_DATASET = E3-E (Sealed Multilingual + Conversational + Instruction)
REASON                  = Complete linguistic representation (Ta, En, Tanglish, Mixed) combined with verified 8:1 synthetic-to-human ratio and SHA-256 cryptographic sealing.
```

---

## 2. Comprehensive Candidate Dataset Comparison

| Dataset Candidate | Description | Total Records | Languages | Synthetic Ratio | Sealing SHA-256 | Lineage Verified? | Alignment Score |
|---|---|---|---|---|---|---|---|
| **Phase 59 Base** | Phase 59 pretraining data | 1,600 | Ta, En, Tanglish | N/A (Legacy) | Locked | Yes | 45% |
| **WS03/WS05 Base** | Phase 60 baseline dataset | 1,800 | Ta, En, Tanglish, Mixed | 0% | `WS03_DATASET_SHA` | Yes | 60% |
| **E3-A Split** | Tamil only extension | 1,825 | Ta only | 1.3% | `E3_DATA_SHA` | Yes | 65% |
| **E3-B Split** | Tamil + English extension | 1,850 | Ta, En | 2.7% | `E3_DATA_SHA` | Yes | 75% |
| **E3-C Split** | Ta + En + Tanglish extension | 1,861 | Ta, En, Tanglish | 3.2% | `E3_DATA_SHA` | Yes | 80% |
| **E3-D Split** | Ta + En + Tanglish + Mixed | 1,885 | Ta, En, Tanglish, Mixed | 4.5% | `E3_DATA_SHA` | Yes | 88% |
| **E3-E Split (RECOMMENDED)** | **Balanced Multilingual + Conversation + Instruction** | **1,885** | **Ta, En, Tanglish, Mixed, Pairs** | **4.5% (Cap: 11.1%)** | `E3_DATA_SHA` | **Yes** | **95%** |

---

## 3. Linguistic Balance & Governance Limits in E3-E

The E3-E split incorporates:
- **Base Training Set:** 1,600 records across all 4 language categories.
- **Admin Assistant Sealed Expansion:** 70 training records covering Tamil $\leftrightarrow$ English translation pairs, Tamil $\leftrightarrow$ Tanglish transliteration pairs, conversational dialogues, and instruction samples.
- **Validation Set:** 200 base records + 10 E3 expansion records.
- **Test Set:** 100 base records + 5 E3 expansion records.

### Synthetic Data Ratio Enforcement:
- Total synthetic additions: 85 records out of 1,885 total records ($4.5\%$).
- Well below the strict **8:1 synthetic-to-human ceiling** (max $11.1\%$).
- 100% of expansion records have passed `DatasetExpansionValidator` (NFC script normalization, virama integrity, air-gap domain filter).

---

## 4. Context Length Adaptation for E4 & E5

When feeding E3-E into E4 and E5 training loops:
1. **Dynamic Length Collator:** Pads sequences up to `max_seq=512`.
2. **Multi-Turn Assembly:** Conversations with multiple turns are concatenated into single `<user>...<assistant>...<user>...<assistant>` training examples up to 512 tokens without artificial slicing.
3. **Zero Data Retraining/Regeneration:** Data remains 100% frozen; only the sequence window truncation limit increases from 128 to 512.
