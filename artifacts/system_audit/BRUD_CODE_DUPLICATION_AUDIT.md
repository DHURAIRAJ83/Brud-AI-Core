# BRUD AI — CODE DUPLICATION AUDIT (WS14)
**Audit Date:** 2026-09-07

---

## DUPLICATION SEVERITY LEGEND

- D1 — EXACT DUPLICATE
- D2 — FUNCTIONAL DUPLICATE
- D3 — PARTIAL DUPLICATE
- D4 — LEGACY DUPLICATE
- D5 — CONFLICTING IMPLEMENTATION

---

## DUPLICATE GROUP 001 — Admin AI Systems (D5 — CRITICAL)

| ID | DUP-001 |
|----|---------|
| Responsibility | Admin AI assistant / LLM interface |
| Implementation A | Phase 8 AdminAssistantChatService (60 KB) + external_ai_provider_client.py |
| Implementation B | MB-28 MiniBrainLlmRuntimeService (81 KB) + MiniBrainLlmAdapterProtocol |
| Similarity | Both provide LLM-based admin intelligence |
| Callers A | `/admin/assistant/chat` route |
| Callers B | `/mini-brain/llm-runtime/` routes |
| Active? | BOTH ACTIVE |
| Authoritative? | CONFLICTING — by design, documented in MB-28 docstring |
| Status | D5 — CONFLICTING |

---

## DUPLICATE GROUP 002 — Public Chat Entry Points (D3 — MEDIUM)

| ID | DUP-002 |
|----|---------|
| Responsibility | Public chat entry point |
| Implementation A | `routes/chat.py` → `PublicChatRoutingService` |
| Implementation B | `routes/public_chat_runtime.py` → `MiniBrainPublicChatRuntimeService` |
| Similarity | Both handle public-facing chat |
| Callers A | `/chat` endpoint |
| Callers B | `/public/chat-runtime/*` endpoints |
| Active? | BOTH ACTIVE |
| Authoritative? | `/chat` is Phase 18 authoritative; `public_chat_runtime` is MB layer |
| Status | D3 — PARTIAL DUPLICATE |

---

## DUPLICATE GROUP 003 — Inference Paths (D3 — MEDIUM)

| ID | DUP-003 |
|----|---------|
| Responsibility | LLM inference execution |
| Implementation A | `InferenceRuntimeService` → Brud core model |
| Implementation B | `MiniBrainLlmRuntimeService` → LlamaCpp/external adapter |
| Implementation C | `ExternalProviderMiniBrainAdapter` → OpenRouter etc |
| Similarity | All produce LLM-generated text |
| Callers | A: PublicChat, AdminAssistant; B: MiniBrain routes; C: AdminAssistant fallback |
| Active? | ALL ACTIVE |
| Authoritative? | A is authoritative for Brud model; B/C for external |
| Status | D3 — PARTIAL DUPLICATE (intentional separation) |

---

## DUPLICATE GROUP 004 — Tool Systems (D3 — MEDIUM)

| ID | DUP-004 |
|----|---------|
| Responsibility | Tool execution for AI responses |
| Implementation A | `deterministic_tool_execution_service.py` (public tools: calculator, unit, datetime) |
| Implementation B | `admin_assistant_tools.py` (admin tools: dashboard queries) |
| Implementation C | `mini_brain_plugin_runtime_service.py` (Mini Brain plugins) |
| Similarity | All execute tools on behalf of AI systems |
| Active? | ALL ACTIVE |
| Authoritative? | Each serves a different scope |
| Status | D3 — PARTIAL DUPLICATE (different scopes) |

---

## DUPLICATE GROUP 005 — core_model/eval vs core_model/evaluation (D2 — HIGH)

| ID | DUP-005 |
|----|---------|
| Responsibility | Model/RAG evaluation logic |
| Implementation A | `core_model/eval/` |
| Implementation B | `core_model/evaluation/` |
| Similarity | Both contain evaluation-related code |
| Callers | Requires deeper investigation |
| Active? | REQUIRES VERIFICATION |
| Status | POSSIBLE D2 — POSSIBLE DUPLICATE — REQUIRES REVIEW |

---

## DUPLICATE GROUP 006 — Empty inference module (D4 — LOW)

| ID | DUP-006 |
|----|---------|
| Responsibility | Core inference |
| Implementation A | `core_model/inference/` — empty __init__.py only |
| Implementation B | `core_model/inference_runtime/` — full implementation |
| Status | D4 — LEGACY — `core_model/inference/` is vestigial |

---

## DUPLICATE GROUP 007 — Phase Report Root Pollution (D4 — LOW)

| ID | DUP-007 |
|----|---------|
| Responsibility | Phase documentation |
| Implementation A | Root-level phase*.md files (400+) |
| Implementation B | artifacts/system_audit/ directory (proper location) |
| Status | D4 — GOVERNANCE — phase reports at root are misplaced |

---

## DUPLICATE GROUP 008 — Memory-related Service Layer (D3 — MEDIUM)

| ID | DUP-008 |
|----|---------|
| Responsibility | Memory evaluation |
| Implementation A | `memory_service.py` (primary memory operations) |
| Implementation B | `memory_evaluation_service.py` (quality evaluation) |
| Callers | Different callers |
| Status | NOT DUPLICATE — different responsibilities. Memory operations vs quality evaluation. |

---

## STRUCTURAL DUPLICATION: Mini Brain Tripling

Every Mini Brain sub-system exists in THREE layers:
1. `core_model/mini_brain/<subsystem>/` — domain logic
2. `backend/services/mini_brain_<subsystem>_service.py` — service layer
3. `backend/api/routes/mini_brain_<subsystem>.py` — route layer

This is the **expected service architecture pattern** (separation of concerns), NOT duplication.
However, there are also corresponding:
4. `backend/database/repositories/mini_brain_<subsystem>.py` — repository
5. `backend/models/mini_brain_<subsystem>.py` — Pydantic models

For 34 Mini Brain sub-systems, this means ~170 files following the same pattern.
**VERDICT:** Structural pattern, not duplication. Each layer has distinct responsibility.

---

## SUMMARY TABLE

| Group | Type | Severity | Recommended Action |
|-------|------|----------|-------------------|
| DUP-001 Admin AI | D5 | CRITICAL | Document boundary; prevent third system |
| DUP-002 Public Chat Entry | D3 | MEDIUM | Clarify `/chat` as primary; document MB path |
| DUP-003 Inference Paths | D3 | MEDIUM | Document each path's purpose |
| DUP-004 Tool Systems | D3 | MEDIUM | Create unified tool registry (future) |
| DUP-005 eval vs evaluation | D2 | HIGH | Investigate and consolidate |
| DUP-006 Empty inference/ | D4 | LOW | Remove in next cleanup |
| DUP-007 Root phase reports | D4 | LOW | Move to docs/phases/ |
| DUP-008 Memory services | RESOLVED | NONE | Not a duplicate |

---
*WS14 Complete*
