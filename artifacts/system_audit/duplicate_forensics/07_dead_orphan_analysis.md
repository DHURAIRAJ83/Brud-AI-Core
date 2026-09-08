# WS08 Duplicate Forensic Audit — 07: Dead / Orphan Code Analysis

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## 1. core_model/inference/ Directory

| Property | Value |
|---|---|
| **Path** | `core_model/inference/__init__.py` |
| **Size** | 354 bytes |
| **Last relevance** | Phase 1 (legacy placeholder) |
| **Imported by** | `core_model/__init__.py:6` — `from core_model.inference import InferenceEngine` |
| **Referenced by production** | ❌ Never called in any service, route, or runtime |
| **Referenced by tests** | ✅ Phase 34–40 test files check `InferenceEngine` exists |
| **Executed in production** | ❌ `generate()` always raises `NotImplementedError` |
| **Executed in tests** | ❌ Tests only check importability, never call `.generate()` |
| **Required?** | 🟡 The import in `core_model/__init__.py` means removing it would break the package-level symbol |
| **Historical evidence** | Docstring says "Phase 1" — it's the original inference stub |
| **Safe to archive?** | ✅ After E4/E5 when inference_runtime becomes the only path; requires removing the import from `core_model/__init__.py` |
| **Classification** | **G — DEAD / ORPHAN (Phase 1 stub superseded by inference_runtime/)** |

**Action Required Before E4/E5:** None (safe for now). Note for E6 cleanup.

---

## 2. models/*.gguf Stub Files

| File | Size | Content | Classification |
|---|---|---|---|
| `models/brud_v1.gguf` | 18 bytes | Plain text: `MOCK_MODEL_WEIGHTS` | **STUB PLACEHOLDER** |
| `models/candidate_model.gguf` | 20 bytes | Plain text: `GGUF_VALID_MOCK_DATA` | **STUB PLACEHOLDER** |
| `models/tiny_model.gguf` | 21 bytes | Plain text: `GGUF_HEADER_MOCK_DATA` | **STUB PLACEHOLDER** |
| `models/trained_model.gguf` | 9 bytes | Plain text: `GGUF_DATA` | **STUB PLACEHOLDER** |
| `models/qwen2.5-0.5b-instruct-q4_k_m.gguf` | **491 MB** | Real GGUF binary (header: `GGUF`) | **REAL MODEL ARTIFACT** |
| `models/qwen2.5-1.5b-instruct-q4_k_m.gguf` | **1.04 GB** | Real GGUF binary (header: `GGUF`) | **REAL MODEL ARTIFACT** |

### GGUF Stub Analysis

The 4 tiny files (18–21 bytes) contain **plain ASCII text** — they are NOT valid GGUF binary files. A valid GGUF file must start with the magic bytes `GGUF` (4 bytes). These stubs start with text strings.

They exist as:
- Path placeholders for early Phase test fixtures
- The tests that reference them (`test_phase37_training_release_readiness.py`, `test_phase34_real_model_activation.py`, etc.) only test **path resolution security** — they verify the `resolve_confined_model_path()` function rejects paths outside the allowed directory

### Are GGUF Stubs Referenced?
```
tests/evaluation/test_phase37_training_release_readiness.py → brud_v1.gguf (path resolution test)
tests/evaluation/test_phase56_controlled_training.py → brud_v1.gguf (existence check)
tests/evaluation/test_phase59_ws06_model_initialization.py → candidate_model.gguf, trained_model.gguf
tests/core_model/test_phase35_production_model_deployment.py → candidate_model.gguf
tests/core_model/test_phase34_real_model_activation.py → tiny_model.gguf
tests/core_model/test_phase37_real_model_training.py → trained_model.gguf
```

**None of these tests load or parse the GGUF files** — they only check file existence and path containment.

| GGUF File | Required? | Safe to Remove? | Note |
|---|---|---|---|
| `brud_v1.gguf` | ✅ For 2 tests | ❌ Do not remove | Path fixture for security test |
| `candidate_model.gguf` | ✅ For 2 tests | ❌ Do not remove | Path fixture |
| `tiny_model.gguf` | ✅ For 1 test | ❌ Do not remove | Path fixture |
| `trained_model.gguf` | ✅ For 1 test | ❌ Do not remove | Path fixture |
| `qwen2.5-0.5b-instruct-q4_k_m.gguf` | ✅ Active model | ❌ Critical — real model | External LLM provider model |
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | ✅ Active model | ❌ Critical — real model | External LLM provider model |

---

## 3. data/core_models/checkpoints/adapter-it-at-* (6,017 directories, 3.8GB)

| Property | Value |
|---|---|
| **Count** | 6,017 directories |
| **Total size** | 3.8 GB |
| **Per directory** | `config.json`, `checksums.txt`, `artifact_manifest.json`, `model_state.pt` (~55KB) |
| **Architecture** | Phase 1–2 tiny LM: hidden_size=16, vocab=400, context=32 |
| **Imported?** | ❌ No Python file imports these directly |
| **Referenced?** | Config root path referenced by `backend/core/config.py:359` as default |
| **Executed?** | ❌ Never loaded by model_loader.py in production |
| **Tested?** | ❌ No test references these adapter-it-at-* paths directly |
| **Required?** | 🟡 For historical reproducibility auditing only |
| **Historical evidence?** | ✅ Phase 1–2 grid-search initialization experiment |
| **Safe to archive?** | ✅ YES — zip entire directory, store in cold storage |
| **Classification** | **HISTORICAL — Phase 1-2 legacy artifacts** |

---

## 4. Root-Level phase59_ws*.md Reports (~40 files)

| Property | Value |
|---|---|
| **Files** | phase59_ws02_*.md through phase59_ws07_*.md (~40 files) |
| **Purpose** | Engineering audit reports from Phase 59 workstream evaluations |
| **Referenced by Python code?** | ✅ Some tests reference `phase59_ws{03/04/05/07/08}_manifest.json` (JSON, not MD) |
| **Imported?** | ❌ Markdown files are never imported |
| **Executed?** | ❌ |
| **Required for tests?** | ❌ MD files not required; only JSON manifests are |
| **Historical evidence?** | ✅ Engineering decision trail for Phase 59 architecture |
| **Safe to archive?** | ✅ YES — move to `docs/historical/phase59/` after E6 |
| **Classification** | **HISTORICAL — Phase 59 completed workstream reports** |

---

## 5. Dead / Orphan Summary Table

| Item | Size | Imported | Executed | Required | Safe to Archive | When |
|---|---|---|---|---|---|---|
| `core_model/inference/__init__.py` | 354B | ✅ (symbol only) | ❌ | 🟡 Symbol only | ✅ | After E6 |
| `models/brud_v1.gguf` | 18B | ❌ | ❌ | ✅ (path fixture) | ❌ | — |
| `models/candidate_model.gguf` | 20B | ❌ | ❌ | ✅ (path fixture) | ❌ | — |
| `models/tiny_model.gguf` | 21B | ❌ | ❌ | ✅ (path fixture) | ❌ | — |
| `models/trained_model.gguf` | 9B | ❌ | ❌ | ✅ (path fixture) | ❌ | — |
| `adapter-it-at-*` (6017 dirs) | 3.8GB | ❌ | ❌ | 🟡 Historical | ✅ | After E6 |
| `phase59_ws*.md` (~40 files) | ~500KB | ❌ | ❌ | 🟡 Historical | ✅ | After E6 |
| `deploy/phase-2.7B/` | Unknown | ❌ | ❌ | 🟡 Historical | ✅ | After E6 |
