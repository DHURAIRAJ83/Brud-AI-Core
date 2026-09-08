# BRUD AI — INCOMPLETE / STUB FEATURES AUDIT (WS22)
**Audit Date:** 2026-09-07

---

## STATUS CLASSIFICATION

- **STUB:** Service/route exists, returns placeholder or empty
- **PARTIAL:** Core flow works, edge cases missing
- **PLACEHOLDER_BY_DESIGN:** Explicitly marked as MB-01 not-yet-implemented
- **SUSPECTED:** Not verified by code tracing, but file size / docstring suggests stub

---

## CONFIRMED PLACEHOLDER (BY DESIGN)

### MiniBrainService Base Placeholders

| Method | Status | Evidence |
|--------|--------|---------|
| `placeholder_inference()` | PLACEHOLDER | Returns `{"reason": "not_implemented_in_mb01"}` |
| `placeholder_knowledge()` | PLACEHOLDER | Returns `{"reason": "not_implemented_in_mb01"}` |
| `placeholder_memory()` | PLACEHOLDER | Returns `{"reason": "not_implemented_in_mb01"}` |
| `placeholder_suggestion()` | PLACEHOLDER | Returns `{"reason": "not_implemented_in_mb01"}` |
| `placeholder_context()` | PLACEHOLDER | Explicitly marked as "MB-02's Brud Context Interface" |

**Note:** These placeholders exist in `MiniBrainService` (the foundation MB-01 service). MB-28 (`MiniBrainLlmRuntimeService`) is the fully-implemented intelligence layer.

---

## SUSPECTED STUBS (REQUIRE DEEPER VERIFICATION)

### Vision Pipeline
| Component | Status | Basis |
|-----------|--------|-------|
| `mini_brain_vision_intelligence_service.py` | SUSPECTED_STUB | Service exists; no GPU dependency |
| `mini_brain_vision_model_service.py` | SUSPECTED_STUB | Vision model integration |
| `mini_brain_vision_rag_service.py` | SUSPECTED_STUB | Vision RAG |
| `MiniBrainVisionIntelligencePage` tab | SUSPECTED_STUB | Frontend tab in MiniBrainPage |

### Voice Pipeline
| Component | Status | Basis |
|-----------|--------|-------|
| `mini_brain_voice_runtime_service.py` | SUSPECTED_STUB | Voice runtime |
| Voice runtime routes | SUSPECTED_STUB | Public voice route exists |

### Multimodal
| Component | Status | Basis |
|-----------|--------|-------|
| `mini_brain_multimodal_dataset_generator_service.py` | SUSPECTED_STUB | Multimodal generation |

---

## PARTIAL IMPLEMENTATIONS

| Feature | Complete | Incomplete |
|---------|----------|-----------|
| Streaming responses | UNKNOWN | Streaming not detected in PublicChatRoutingService |
| Connection pool adoption | 2 routes using pool | 90+ routes using direct connection |
| Mini Brain plugins | Governance framework active | No actual plugins ship |
| RBAC | No RBAC | All admins have equal permissions |
| Distributed rate limiting | In-memory only | No Redis / distributed limiter |
| Model quantization | Not detected | Referenced in some comments |
| GPU inference | CPU only detected | No CUDA dependency found |
| Pilot Operations page | UI exists | Backend data likely minimal |
| Pilot Metrics page | UI exists | Backend data likely minimal |

---

## DEAD CODE CONFIRMED

| File | Evidence | Action |
|------|---------|--------|
| `core_model/inference/__init__.py` | Empty file | Remove |
| Root-level phase*.md files (400+) | Documentation noise | Move to docs/phases/ |
| `.claude/` directory | Legacy tool config | Archive |
| `.codex/` directory | Legacy tool config | Archive |
| Root-level `node_modules/` | Empty/unused | Remove |

---

## FINDINGS

1. **CONFIRMED PLACEHOLDER:** MiniBrainService MB-01 base has 5 explicit placeholder methods
2. **SUSPECTED STUB:** Vision, Voice, Multimodal pipelines (services exist but likely non-functional)
3. **PARTIAL:** Connection pool only 2% adopted
4. **DEAD:** core_model/inference/ — empty module
5. **MISSING:** Real-time streaming (SSE)
6. **MISSING:** GPU acceleration
7. **MISSING:** RBAC beyond admin/non-admin

---
*WS22 Complete*
