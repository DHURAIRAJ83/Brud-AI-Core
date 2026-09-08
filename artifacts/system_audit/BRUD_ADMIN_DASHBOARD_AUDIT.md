# BRUD AI — ADMIN DASHBOARD AUDIT (WS01)
**Audit Date:** 2026-09-07

---

## OVERVIEW

The Admin Dashboard is a **Vite/React SPA** at `apps/admin-dashboard/`.
- Uses hash-based routing (`#PageName`)
- 52 lazy-loaded page components
- 77 total page files
- 19 shared components
- Authentication: cookie-based session via `/admin/login`
- **SINGLE authoritative frontend** — no duplicate admin UI detected

---

## NAVIGATION STRUCTURE (App.jsx)

| Page Name | Component | Backend Route | Status |
|-----------|-----------|---------------|--------|
| Overview | OverviewPage.jsx | /admin/overview | ACTIVE |
| System | SystemPage.jsx | /admin/system | ACTIVE |
| Pilot Operations | PilotOperationsPage.jsx | - | PARTIAL |
| Pilot Metrics | PilotMetricsPage.jsx | - | PARTIAL |
| Data Overview | DataOverviewPage.jsx | Multiple | ACTIVE |
| Data Help | DataHelpPage.jsx | Static | ACTIVE |
| Documents | DocumentsPage.jsx | /admin/documents | ACTIVE |
| Document Wizard | DocumentWizardPage.jsx | /admin/documents | ACTIVE |
| Datasets | DatasetsPage.jsx | /admin/datasets | ACTIVE |
| Dataset Discovery | DatasetDiscoveryPage.jsx | /admin/dataset-discovery | ACTIVE |
| Dataset Verification | DatasetVerificationPage.jsx | /admin/dataset-verification | ACTIVE |
| Sample Import & Quarantine | DatasetSampleImportPage.jsx | /admin/dataset-sample-import | ACTIVE |
| Sources & Rights | SourcesRightsPage.jsx | /admin/sources | ACTIVE |
| Manual Data | ManualDataPage.jsx | /admin/manual-data | ACTIVE |
| Data Workspace Wizard | DataWorkspaceWizardPage.jsx | /admin/data-workspace | ACTIVE |
| External Data Providers | ExternalDataProvidersPage.jsx | /admin/external-data-providers | ACTIVE |
| Gateway Dataset RAG Bridge | GatewayDatasetRagBridgePage.jsx | /admin/external-gateway-dataset-bridge | ACTIVE |
| Corpus | CorpusPage.jsx | /admin/corpus | ACTIVE |
| Chunk Studio | ChunkStudioPage.jsx | /admin/semantic-chunks | ACTIVE |
| RAG | RagPage.jsx | /admin/rag | ACTIVE |
| RAG Sandbox | RagSandboxPage.jsx | /admin/rag-sandbox | ACTIVE |
| Governance | GovernancePage.jsx | /admin/governance | ACTIVE |
| Builds & Pipelines | BuildsPipelinesPage.jsx | /admin/governed-builds | ACTIVE |
| Tokenizer | TokenizerPage.jsx | /admin/tokenizers | ACTIVE |
| Core Model | CoreModelPage.jsx | /admin/core-models | ACTIVE |
| Base Training | BaseTrainingPage.jsx | /admin/base-training | ACTIVE |
| Training | TrainingPage.jsx | /admin/pretraining | ACTIVE |
| Instruction Tuning | InstructionTuningPage.jsx | /admin/instruction-tuning | ACTIVE |
| Incremental Training | IncrementalTrainingPage.jsx | /admin/incremental-training | ACTIVE |
| Pretraining Readiness | PretrainingReadinessPage.jsx | /admin/pretraining-readiness | ACTIVE |
| Inference Runtime | InferenceRuntimePage.jsx | /admin/inference-runtime | ACTIVE |
| Model Evaluation | ModelEvaluationPage.jsx | /admin/model-evaluation | ACTIVE |
| Model Registry | ModelRegistryPage.jsx | /admin/model-release | ACTIVE |
| Production Readiness | ProductionReadinessPage.jsx | /admin/production-readiness | ACTIVE |
| Public Chat Routing | PublicChatRoutingPage.jsx | /admin/public-chat-routing | ACTIVE |
| Trusted Web | TrustedWebPage.jsx | /admin/trusted-web | ACTIVE |
| Deterministic Tools | DeterministicToolsPage.jsx | /admin/deterministic-tools | ACTIVE |
| Knowledge Gaps | KnowledgeGapsPage.jsx | /admin/knowledge-gap | ACTIVE |
| Knowledge Routing | KnowledgeRoutingPage.jsx | /admin/knowledge-routing | ACTIVE |
| Conversation & Memory | ConversationMemoryPage.jsx | /admin/conversation-memory | ACTIVE |
| Feedback | FeedbackPage.jsx | /admin/feedback | ACTIVE |
| Imports | ImportsPage.jsx | /admin/imports | ACTIVE |
| Prompt Optimization | PromptOptimizationPage.jsx | /mini-brain/prompt-optimization | ACTIVE |
| Brud Mini Brain | MiniBrainPage.jsx | /mini-brain/* | ACTIVE |
| Assistant Center | AssistantCenterPage.jsx | /admin/assistant | ACTIVE |
| Admin Assistant | AdminAssistantPage.jsx | /admin/assistant | ACTIVE |

---

## ADMIN ASSISTANT UI

- **AdminAssistantPage.jsx** (14 KB) — floating chat assistant UI
- **AssistantCenterPage.jsx** (2 KB) — center/landing page for assistant
- `src/components/admin-assistant/` — assistant-specific sub-components

### POSSIBLE DUPLICATE:
- `AssistantCenterPage.jsx` and `AdminAssistantPage.jsx` both exist.
- Investigation: AssistantCenterPage is a wrapper/overview; AdminAssistantPage is the full chat interface.
- **VERDICT:** NOT a duplicate — different responsibilities.

---

## MINI BRAIN PAGE

- **MiniBrainPage.jsx** is 182 KB — the largest single frontend file
- Contains all Mini Brain sub-tabs (tab-based navigation within one page)
- **MiniBrainPage.test.jsx** is 43 KB — comprehensive tests

---

## COMPONENTS AUDIT

| Component | Status | Notes |
|-----------|--------|-------|
| Sidebar.jsx | ACTIVE | Navigation sidebar |
| DashboardLayout.jsx | ACTIVE | Shell layout |
| Topbar.jsx | ACTIVE | Top bar |
| CommandPalette.jsx | ACTIVE | Quick command palette |
| Toast.jsx | ACTIVE | Notifications |
| ErrorBanner.jsx | ACTIVE | Error display |
| ThemeSwitcher.jsx | ACTIVE | Dark/light mode |
| Breadcrumbs.jsx | ACTIVE | Navigation breadcrumbs |
| Button.jsx | ACTIVE | Shared button |
| Skeleton.jsx | ACTIVE | Loading skeleton |
| StatusCard.jsx | ACTIVE | Status display |

---

## AUTHENTICATION

- Login: `LoginPage.jsx` → `services/api.js: login()` → `POST /admin/login`
- Session check: `getMe()` → `GET /admin/me`
- Logout: `logout()` → `POST /admin/logout`
- **Single implementation** — no duplicate auth detected

---

## DUPLICATE ANALYSIS

| Finding | Severity | Notes |
|---------|----------|-------|
| No duplicate admin dashboards | CLEAN | Single Vite SPA |
| No duplicate authentication flows | CLEAN | Single login path |
| MiniBrainPage is a monolith | LOW | 182KB, could be split |
| AssistantCenterPage vs AdminAssistantPage | RESOLVED | Different scopes |

---

## FINDINGS

1. **COMPLETE:** All major admin pages have corresponding backend API routes
2. **PARTIAL:** `PilotOperationsPage` and `PilotMetricsPage` — backend endpoints may be stub
3. **ACTIVE:** Authentication fully functional
4. **NO DUPLICATE DASHBOARDS DETECTED**

---
*WS01 Complete*
