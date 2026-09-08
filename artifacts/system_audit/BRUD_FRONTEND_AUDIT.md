# BRUD AI — FRONTEND AUDIT (WS12)
**Audit Date:** 2026-09-07

---

## FRONTEND APPLICATIONS

### 1. Admin Dashboard (apps/admin-dashboard/)
- Framework: Vite + React (JSX)
- Routing: Hash-based (#PageName)
- Auth: Cookie-based session
- State: Local React state + props
- API: `src/services/api.js` (single API client)
- Tests: Vitest unit tests + Playwright E2E
- **Status: ACTIVE — PRIMARY ADMIN UI**

### 2. Public Chatbot (apps/chatbot/)
- Framework: Vite + React (JSX)
- App.jsx: 101 bytes (minimal)
- **Status: ACTIVE — PUBLIC CHAT UI**

---

## ADMIN DASHBOARD PAGES (77 files)

### Data Management Pages
| Page | File | Backend Route | Status |
|------|------|---------------|--------|
| Data Overview | DataOverviewPage.jsx (19 KB) | Multiple admin APIs | ACTIVE |
| Documents | DocumentsPage.jsx (51 KB) | /admin/documents | ACTIVE |
| Document Wizard | DocumentWizardPage.jsx (19 KB) | /admin/documents | ACTIVE |
| Datasets | DatasetsPage.jsx (16 KB) | /admin/datasets | ACTIVE |
| Dataset Discovery | DatasetDiscoveryPage.jsx (19 KB) | /admin/dataset-discovery | ACTIVE |
| Dataset Verification | DatasetVerificationPage.jsx (33 KB) | /admin/dataset-verification | ACTIVE |
| Sample Import | DatasetSampleImportPage.jsx (29 KB) | /admin/dataset-sample-import | ACTIVE |
| Sources & Rights | SourcesRightsPage.jsx (16 KB) | /admin/sources | ACTIVE |
| Manual Data | ManualDataPage.jsx (31 KB) | /admin/manual-data | ACTIVE |
| Corpus | CorpusPage.jsx (69 KB) | /admin/corpus | ACTIVE |
| Chunk Studio | ChunkStudioPage.jsx (30 KB) | /admin/semantic-chunks | ACTIVE |
| External Providers | ExternalDataProvidersPage.jsx (19 KB) | /admin/external-data-providers | ACTIVE |
| Gateway Bridge | GatewayDatasetRagBridgePage.jsx (9.9 KB) | /admin/external-gateway | ACTIVE |
| Imports | ImportsPage.jsx (10 KB) | /admin/imports | ACTIVE |

### Model & Training Pages
| Page | File | Status |
|------|------|--------|
| Core Model | CoreModelPage.jsx (22 KB) | ACTIVE |
| Base Training | BaseTrainingPage.jsx (17 KB) | ACTIVE |
| Training | TrainingPage.jsx (19 KB) | ACTIVE |
| Incremental Training | IncrementalTrainingPage.jsx (33 KB) | ACTIVE |
| Instruction Tuning | InstructionTuningPage.jsx (22 KB) | ACTIVE |
| Pretraining Readiness | PretrainingReadinessPage.jsx (20 KB) | ACTIVE |
| Inference Runtime | InferenceRuntimePage.jsx (27 KB) | ACTIVE |
| Model Evaluation | ModelEvaluationPage.jsx (26 KB) | ACTIVE |
| Model Registry | ModelRegistryPage.jsx (25 KB) | ACTIVE |
| Production Readiness | ProductionReadinessPage.jsx (38 KB) | ACTIVE |
| Tokenizer | TokenizerPage.jsx (9 KB) | ACTIVE |

### AI/Intelligence Pages
| Page | File | Status |
|------|------|--------|
| Mini Brain | MiniBrainPage.jsx (182 KB) | ACTIVE |
| RAG | RagPage.jsx (40 KB) | ACTIVE |
| RAG Sandbox | RagSandboxPage.jsx (35 KB) | ACTIVE |
| Conversation Memory | ConversationMemoryPage.jsx (37 KB) | ACTIVE |
| Public Chat Routing | PublicChatRoutingPage.jsx (8.5 KB) | ACTIVE |
| Knowledge Gaps | KnowledgeGapsPage.jsx (18 KB) | ACTIVE |
| Knowledge Routing | KnowledgeRoutingPage.jsx (11 KB) | ACTIVE |
| Trusted Web | TrustedWebPage.jsx (10 KB) | ACTIVE |
| Deterministic Tools | DeterministicToolsPage.jsx (7 KB) | ACTIVE |
| Prompt Optimization | PromptOptimizationPage.jsx (9.6 KB) | ACTIVE |
| Feedback | FeedbackPage.jsx (36 KB) | ACTIVE |

### Governance Pages
| Page | File | Status |
|------|------|--------|
| Governance | GovernancePage.jsx (23 KB) | ACTIVE |
| Builds & Pipelines | BuildsPipelinesPage.jsx (21 KB) | ACTIVE |

### System Pages
| Page | File | Status |
|------|------|--------|
| Overview | OverviewPage.jsx (4.4 KB) | ACTIVE |
| System | SystemPage.jsx (2.3 KB) | ACTIVE |
| Login | LoginPage.jsx (1.2 KB) | ACTIVE |
| Placeholder | PlaceholderPage.jsx (185 bytes) | ACTIVE (catch-all) |
| Pilot Metrics | PilotMetricsPage.jsx (2.5 KB) | PARTIAL |
| Pilot Operations | PilotOperationsPage.jsx (4 KB) | PARTIAL |

### Assistant Pages
| Page | File | Status |
|------|------|--------|
| Admin Assistant | AdminAssistantPage.jsx (14 KB) | ACTIVE |
| Assistant Center | AssistantCenterPage.jsx (1.9 KB) | ACTIVE |

---

## SHARED COMPONENTS (19 files)

| Component | Status | Notes |
|-----------|--------|-------|
| Sidebar.jsx (7.5 KB) | ACTIVE | Main navigation |
| DashboardLayout.jsx (1 KB) | ACTIVE | Shell layout |
| Topbar.jsx (505 B) | ACTIVE | Top bar |
| CommandPalette.jsx (3.7 KB) | ACTIVE | Quick navigation |
| Toast.jsx (1.8 KB) | ACTIVE | Notifications |
| ErrorBanner.jsx (373 B) | ACTIVE | Error display |
| ThemeSwitcher.jsx (2 KB) | ACTIVE | Dark/light mode |
| Breadcrumbs.jsx (939 B) | ACTIVE | Navigation breadcrumbs |
| Button.jsx (555 B) | ACTIVE | Shared button |
| Skeleton.jsx (445 B) | ACTIVE | Loading state |
| StatusCard.jsx (249 B) | ACTIVE | Status display |

### Sub-component directories
- `components/admin-assistant/` — Admin assistant chat UI components
- `components/chat/` — Chat UI components

---

## API CLIENT

`src/services/api.js` — SINGLE API CLIENT — no duplication
- All API calls go through this file
- Uses fetch() with credentials

---

## DUPLICATE ANALYSIS

| Finding | Severity | Notes |
|---------|----------|-------|
| No duplicate admin dashboards | CLEAN | Single Vite SPA |
| No duplicate API clients | CLEAN | Single api.js |
| MiniBrainPage at 182 KB | CONCERN | Monolithic, should be split |
| CorpusPage at 69 KB | CONCERN | Very large single component |
| DocumentsPage at 51 KB | CONCERN | Very large single component |
| Two assistant pages (Admin + Center) | RESOLVED | Different scopes |

---

## FRONTEND TEST COVERAGE

| File | Test File | Status |
|------|-----------|--------|
| AdminAssistantPage.jsx | AdminAssistantPage.test.jsx | ACTIVE |
| MiniBrainPage.jsx | MiniBrainPage.test.jsx (43 KB) | ACTIVE |
| DocumentsPage.jsx | DocumentsPage.test.jsx (26 KB) | ACTIVE |
| ProductionReadinessPage.jsx | ProductionReadinessPage.test.jsx (14 KB) | ACTIVE |
| ManualDataPage.jsx | ManualDataPage.test.jsx (14 KB) | ACTIVE |
| ~25 other pages | Corresponding .test.jsx files | ACTIVE |
| ~25 pages | NO test file | UNVERIFIED |

---

## FINDINGS

1. **COMPLETE:** Single admin dashboard SPA with comprehensive routing
2. **COMPLETE:** All major features have dedicated pages
3. **ACTIVE:** Frontend tests exist for ~60% of pages
4. **CONCERN:** MiniBrainPage.jsx at 182 KB — maintenance risk monolith
5. **CONCERN:** CorpusPage.jsx at 69 KB — large component
6. **NO DUPLICATE FRONTENDS** detected
7. **PARTIAL:** Pilot pages (Metrics/Operations) likely stub

---
*WS12 Complete*
