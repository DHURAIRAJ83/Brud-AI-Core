# P12.3 — Dashboard Context Truth Matrix

**Subsystem**: Brud AI Mini Brain Unified Context Service (`MiniBrainDashboardContextService`)  
**Audit Date**: September 4, 2026  
**Auditor**: Antigravity Operational Verification Agent  
**Status**: 🟢 **VERIFIED — TRUTHFUL SOURCE-TO-ANSWER CHAIN**  

---

## 1. Context Truth Traceability Architecture

For every field in the 11 subsystems, truthfulness requires complete traceability from runtime source to the final LLM response:

```
[Database / Runtime Service]
              │
              ▼
[MiniBrainDashboardContextService.get_system_context()]
              │
              ▼
[PromptBuilder.format_dashboard_context()]
              │
              ▼
[System Prompt Context Block]
              │
              ▼
[Model Router & LLM Inference]
              │
              ▼
[Final Admin Assistant Answer]
```

**Anti-Hallucination Invariant**: If any metric or status is absent, the context returns `None` or `0`, and the assistant explicitly reports that the information is unavailable or unconfigured, rather than hallucinating numbers or names.

---

## 2. Comprehensive 11-Subsystem Truth Matrix

| Subsystem | Field Name | Runtime Source (Database / Service) | Context Service Transformation | System Prompt Representation | Response Usage | Test Evidence | Failure / Default Behavior |
|---|---|---|---|---|---|---|---|
| **1. System & Health** | `overall_status` | `MiniBrainHealthService.snapshot()` | `"healthy"` if backend != `"unavailable"`, else `"degraded"` | `- System Health: status=healthy, backend=...` | Explains overall system health to Admin | `test_smoke_04`, `test_e2e_001` | `"degraded"` if snapshot fails |
| | `backend_type` | `MiniBrainHealthService.snapshot()` | Local or external backend identifier | `backend=local` / `backend=external` | Discloses execution backend | `test_e2e_001`, `test_e2e_003` | `"unavailable"` |
| | `model_loaded` | `MiniBrainHealthService.snapshot()` | Boolean indicating active weight in RAM | `model_loaded=True/False` | Informs if warm inference is available | `test_smoke_05`, `test_e2e_013` | `False` |
| | `environment` | `Settings.environment` | Config string (`development`, `production`) | `env=development` | Identifies staging vs prod boundary | `test_e2e_010` | `"development"` |
| | `production_locked` | Constant / Security Policy | Strict boolean: `True` | Included in governance rules | Enforces read-only safety boundary | `test_e2e_017` | `True` (Fail-closed) |
| **2. Providers** | `total_configured` | `MiniBrainProviderSettingsService.list_settings()` | Count of provider rows with non-empty secrets | `- Providers: configured=[...], enabled=[...]` | Reports available cloud endpoints | `test_e2e_006`, `test_smoke_04` | `0` if none |
| | `enabled` | `provider_settings.enabled` | List of enabled provider keys (e.g. `["ollama"]`) | `enabled=['ollama']` | Used by router for fallback priority | `test_e2e_005`, `test_e2e_006` | `[]` |
| | `encryption_active` | `Settings.secret_encryption_key` | Boolean: `True` | Zero plaintext secrets exposed | Verifies vault integrity | `test_e2e_023` | `True` (AES-GCM) |
| **3. Models** | `active_model` | `MiniBrainLlmRuntimeService.widget_health()` | Currently loaded GGUF/provider model name | `- Models: active_model=qwen2.5-..., backend_type=...` | Accurately tells admin which model answers | `test_smoke_05`, `test_e2e_013` | `"Not Selected"` |
| | `local_available` | `MiniBrainLlmRuntimeService.diagnostics()` | Verifies GGUF file exists on disk | `local_available=True` | Explains whether offline inference works | `test_smoke_11`, `test_e2e_004` | `False` |
| | `external_fallback_enabled`| `MiniBrainLlmRuntimeService.diagnostics()` | Boolean check if cloud fallback is active | Truthful boolean | Explains auto-routing fallback | `test_e2e_005` | `False` |
| **4. Datasets** | `total_dataset_versions` | `CorpusRepository.list_dataset_versions()` | Count of dataset version records in SQLite | `- Datasets: total_versions=X, latest_version=...` | Answers admin queries about training data | `test_smoke_06`, `test_e2e_021` | `0` |
| | `latest_version` | `corpus_dataset_versions.dataset_version` | Version string of top record (e.g. `v1.0-tamil`) | `latest_version=v1.0-tamil` | Informs admin of latest dataset build | `test_smoke_06` | `None` |
| | `training_ready` | Computed boolean | `total_dataset_versions > 0` | `training_ready=True/False` | Indicates readiness for tuning | `test_smoke_06` | `False` |
| **5. Training** | `total_runs` | `PretrainingRepository.list_runs()` | Count of training run records | `- Training: total_runs=X, latest_status=...` | Answers training history queries | `test_smoke_07` | `0` |
| | `latest_run_status` | `pretraining_runs.status` | Status string (e.g. `completed`, `failed`, `none`) | `latest_status=completed` | Informs status of last training attempt | `test_smoke_07` | `"none"` |
| | `training_gate_locked` | Hardcoded Invariant | `SignedTrainingAuthorizationToken = ABSENT` -> `True` | `training_gate=LOCKED (Fail-closed)` | Rebuffs any direct "train" prompt | `test_e2e_017`, `test_smoke_07` | `True` (Fail-closed) |
| **6. Evaluation** | `total_evaluations` | `ModelEvaluationRepository.list_evaluation_runs()` | Total completed evaluation runs | `- Evaluation: total_evaluations=X, latest_score=...` | Informs benchmark progress | `test_e2e_020` | `0` |
| | `latest_score` | `model_evaluations.overall_score` | Float score (0.0 to 1.0) | `latest_score=0.88` | Answers benchmark score queries | `test_e2e_020` | `None` |
| | `evaluation_status` | `model_evaluations.status` | Status string | `status=completed` | Reflects evaluation pipeline state | `test_e2e_020` | `"no_evaluations"` |
| **7. RAG** | `knowledge_spaces_count`| `RagRepository.list_knowledge_spaces()` | Count of registered knowledge spaces | `- RAG: spaces_count=X, default_profile=...` | Reports document index coverage | `test_smoke_08`, `test_e2e_007` | `0` |
| | `default_profile` | `settings` table key | Public ID of default retrieval profile | `default_profile=prof-uuid` | Grounded chat routing target | `test_smoke_08` | `None` |
| | `grounded_chat_ready` | Computed boolean | `bool(default_profile_id)` | `grounded_ready=True/False` | Explains whether RAG is ready | `test_e2e_008` | `False` |
| **8. Memory** | `active_chat_sessions` | `mini_brain_llm_sessions` | Count of sessions where `status='active'` | `- Memory: active_sessions=X, total_messages=...` | Discloses active conversation volume | `test_smoke_09`, `test_e2e_011` | `0` |
| | `total_messages_recorded`| `mini_brain_llm_messages` | Count of all historical messages | `total_messages=X` | Discloses total memory footprint | `test_e2e_012` | `0` |
| **9. Governance** | `pending_proposals_count`| `AdminAssistantService.list_proposals(status='pending')` | Count of pending admin approvals in SQLite | `- Governance: authority_mode=ADVISORY_ONLY, pending=X` | Alerts admin to pending approvals | `test_e2e_018`, `test_e2e_019` | `0` |
| | `authority_mode` | Hardcoded Invariant | `"ADVISORY_ONLY"` | `authority_mode=ADVISORY_ONLY` | Invariant: No autonomous execution | `test_e2e_017`, `test_e2e_019` | `"ADVISORY_ONLY"` |
| | `production_state` | Hardcoded Invariant | `"LOCKED"` | `production_state=LOCKED` | Invariant: Read-only protection | `test_e2e_017` | `"LOCKED"` |
| **10. Recent Events** | `recent_events` | `AuditLogRepository.list_events(limit=5)` | Top 5 audit rows (action, target_type, time) | Formatted audit bullet list | Answers "what changed recently?" | `test_e2e_022` | `[]` |
| **11. Recommendations**| `recommendations` | Rule engine on provider, rag, and proposal state | Actionable admin hints with `nav_key` | Contextual recommendations block | Proactively guides administrator | `test_e2e_010` | `[]` |

---

## 3. Strict Truth Chain Verification Result

A complete end-to-end verification test asserts that for every sampled field (e.g. `active_model`, `latest_dataset_version`, `pending_proposals_count`):
1. The **database value** equals the **context service dictionary value**.
2. The **context service value** is formatted verbatim into the **system prompt string**.
3. When queried, the **LLM response contains this exact value**.
4. If a value does not exist, the LLM explicitly returns **"unavailable" / "not configured"** rather than hallucinating.

Status: 🟢 **VERIFIED — ZERO FABRICATION IN CONTEXT PATH**
