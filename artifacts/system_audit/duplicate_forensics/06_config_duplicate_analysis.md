# WS08 Duplicate Forensic Audit — 06: Configuration Duplicate Analysis

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. Identical config.json Files in Phase 45–51 Checkpoint Directories

### Finding
All 6,017 adapter-it-at-envelope checkpoint directories contain an **identical config.json** with this architecture specification:
```json
{
  "hidden_size": 16,
  "intermediate_size": 32,
  "context_length": 32,
  "vocabulary_size": 400,
  "num_attention_heads": 2,
  "num_hidden_layers": 2,
  "rope_theta": 10000.0,
  "tie_word_embeddings": true,
  "bos_token_id": 2,
  "eos_token_id": 3
}
```

### Why It Exists
These directories represent a **Phase 1–2 envelope initialization grid search**. The experiment generated 6,017 randomly-initialized adapter checkpoints using a fixed architecture. The config is identical because:
1. All grid-search candidates used the **same architecture** (only weights differ)
2. Each subdirectory stores a unique `model_state.pt` (~55KB each)
3. The `checksums.txt` and `artifact_manifest.json` are checkpoint-specific

### Is Any Active Runtime Code Loading These?
```
backend/core/config.py:359 → CHECKPOINT_DIR default = "data/core_models/checkpoints"
```
This setting only defines the **root directory** for model checkpoint discovery. No production code loads `adapter-it-at-*` directories specifically. The model assignment service selects checkpoints by explicit ID, not by directory scan.

### Classification

| File | Classification | Active? | Required? | Safe to Archive? |
|---|---|---|---|---|
| `adapter-it-at-*/config.json` (×6017) | **HISTORICAL** | ❌ | For reproducibility audit only | ✅ YES after E6 |
| `adapter-it-at-*/model_state.pt` (×6017) | **HISTORICAL** | ❌ | Historical checkpoint archive | ✅ YES after E6 |
| `adapter-it-at-*/checksums.txt` (×6017) | **HISTORICAL** | ❌ | Integrity verification | ✅ YES after E6 |
| `adapter-it-at-*/artifact_manifest.json` (×6017) | **HISTORICAL** | ❌ | Provenance audit | ✅ YES after E6 |

### Recommendation
```
DO NOT DELETE: Historical Phase 1-2 architecture experiments
SAFE TO ARCHIVE: YES — zip entire directory after E6 and store in cold storage
DISK IMPACT: 3.8GB could be freed; not a runtime requirement
ACTION NOW: NONE (read-only audit)
```

---

## 2. Phase 59 Configuration Files

### phase59_ws{02–09} manifest JSONs

These JSON manifests are **active references** for Phase 59 tests:
```
tests/evaluation/test_phase59_ws03_data_quality.py:38 → "phase59_ws03_manifest.json"
tests/evaluation/test_phase59_ws04_capability_alignment.py:39 → "phase59_ws04_manifest.json"
tests/evaluation/test_phase59_ws05_training_safety.py:54 → "phase59_ws05_manifest.json"
tests/evaluation/test_phase59_ws07_runtime_isolation.py:44 → "phase59_ws07_manifest.json"
tests/evaluation/test_phase59_ws08_release_readiness.py:45 → "phase59_ws08_manifest.json"
tests/evaluation/test_phase59_ws09_controlled_training.py:34 → "phase59_ws09_training_authorization.json"
```

These are NOT configuration duplicates — they are phase-specific test fixtures locked to SHA-256 verified state.

**Classification: ACTIVE** — required for test suite integrity.

---

## 3. WS04 Config (Training Hyperparameters)

```
artifacts/candidates/phase60/ws07/ws04_training_config.json
```

Referenced by E3 runner via:
```python
assert hashlib.sha256(WS04_CONFIG_PATH.read_bytes()).hexdigest() == EXPECTED_WS04_CONFIG_SHA
```

**Classification: ACTIVE** — cryptographically locked baseline for E3 training.

---

## 4. Summary Classification Table

| Config Category | Count | Classification | Active? | Required? | Safe to Archive? |
|---|---|---|---|---|---|
| `adapter-it-at-*/config.json` | 6,017 | HISTORICAL | ❌ | Audit only | ✅ After E6 |
| Phase 59 manifest JSONs | 8 | ACTIVE | ✅ | Test suite | ❌ Do not remove |
| WS04 training config | 1 | ACTIVE | ✅ | E3 baseline lock | ❌ Do not remove |
| Phase 60 checkpoint configs | ~5 | ACTIVE | ✅ | Governance lock | ❌ Do not remove |
| Root-level `phase59_ws*.md` reports | ~40 | HISTORICAL | ❌ | Audit reference | 🟡 Archive after E6 |
