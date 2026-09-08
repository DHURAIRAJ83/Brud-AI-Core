# Master Brud AI End-to-End Audit — 07: External Provider Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal Cloud Architect & Security Auditor  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code in `external_ai_provider_client.py`, `mini_brain_external_ai_gateway_service.py`, and `external_gateway_dataset_bridge_service.py`)  

---

## 1. Provider Adapter & Client Reality

| Provider Key | Registry Listing | Dedicated Client Adapter | Network HTTP Dispatch | Environment Secret Variable | Current Environment Status |
|---|---|---|---|---|---|
| **`openrouter`** | ✅ `provider_registry.py` | ✅ `OpenRouterProviderClient` | ✅ Real `httpx.post()` to `https://openrouter.ai/api/v1/chat/completions` | `BRUD_EXTERNAL_AI_OPENROUTER_API_KEY` | ⚪ Not configured in env (`is_available()=False`) |
| **`openai`** | ✅ `provider_registry.py` | 🔴 None (Uses OpenRouter or Mock) | 🔴 No direct adapter | `OPENAI_API_KEY` | ⚪ Unwired (Routes via OpenRouter if configured) |
| **`anthropic`** | ✅ `provider_registry.py` | 🔴 None (Uses OpenRouter or Mock) | 🔴 No direct adapter | `ANTHROPIC_API_KEY` | ⚪ Unwired (Routes via OpenRouter if configured) |
| **`gemini`** | ✅ `provider_registry.py` | 🔴 None (Uses OpenRouter or Mock) | 🔴 No direct adapter | `GEMINI_API_KEY` | ⚪ Unwired (Routes via OpenRouter if configured) |
| **`mock`** | ✅ In tests | ✅ `MockProviderClient` | ❌ Deterministic in-memory canned responses | None required | ✅ Operational in tests |

---

## 2. External Provider -> Training Pipeline Governance Verification

The audit specifically inspected whether external provider outputs can silently contaminate training datasets:

```
[ External Provider Request ]
              │
              ▼ (Explicit Admin Session Authorization Required)
[ MiniBrainExternalAiGatewayService ]
              │
              ▼ (Dispatches HTTP via OpenRouter or Mock)
[ Raw Candidate Response ]
              │
              ▼ (SHA-256 Hashed; Raw Prompt Dropped from DB)
[ Safety & Failure Detectors ]
              │
              ▼ (Status: 'pending_admin_review')
[ Admin Review Gate (admin_review()) ]
              │
              ├─── Admin Decision: 'reject' ──► Terminated / Quarantined
              │
              └─── Admin Decision: 'admin_accepted'
                           │
                           ▼ (Explicit Action Required: No Auto-Export)
              [ ExternalGatewayDatasetBridgeService ]
                           │
                           ▼ (Creates 'draft' Dataset Records Only)
              [ Dataset Studio (Draft Status) ]
                           │
                           ▼ (Mandatory Dataset Sealing & Versioning)
              [ Immutable Sealed JSONL (SHA-256) ]
                           │
                           ▼ (Explicit Human Authorization Required)
              [ Controlled Training Sandbox ]
```

### Critical Findings:
1. **Zero Silent Injection:**
   - There is **no code path** in the repository that automatically writes an external provider response into active training data.
   - `ExternalGatewayDatasetBridgeService` will refuse to bridge any record unless `session.status == "admin_accepted"`.
2. **Air-Gap Benchmarks Protected:**
   - All proposed records are validated by `dataset_expansion_validator.py` against the Phase 53 benchmark hash; any match is immediately rejected.
3. **Secret Security:**
   - Provider API keys are read strictly from environment variables (`os.environ`) at construction time. They are never written to SQLite, never serialized in JSON manifests, and scrubbed via `redact_secrets()`.
4. **Privacy & Data Minimization:**
   - In `mini_brain_external_ai_gateway_service.py`, raw prompt text sent to external providers is not persisted to the database; only its SHA-256 digest is stored.
