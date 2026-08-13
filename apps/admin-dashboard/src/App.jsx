import { lazy, Suspense, useEffect, useState } from 'react'
import DashboardLayout from './components/DashboardLayout.jsx'
import Skeleton from './components/Skeleton.jsx'
import LoginPage from './pages/LoginPage.jsx'
import PlaceholderPage from './pages/PlaceholderPage.jsx'
import { getMe, login, logout } from './services/api.js'
import { buildDocumentsHash, buildWizardHash, parseHash } from './services/documentNavigation.js'

const AdminAssistantPage = lazy(() => import('./pages/AdminAssistantPage.jsx'))
const AssistantCenterPage = lazy(() => import('./pages/AssistantCenterPage.jsx'))
const BaseTrainingPage = lazy(() => import('./pages/BaseTrainingPage.jsx'))
const BuildsPipelinesPage = lazy(() => import('./pages/BuildsPipelinesPage.jsx'))
const DatasetDiscoveryPage = lazy(() => import('./pages/DatasetDiscoveryPage.jsx'))
const DatasetSampleImportPage = lazy(() => import('./pages/DatasetSampleImportPage.jsx'))
const DatasetVerificationPage = lazy(() => import('./pages/DatasetVerificationPage.jsx'))
const DatasetsPage = lazy(() => import('./pages/DatasetsPage.jsx'))
const DocumentsPage = lazy(() => import('./pages/DocumentsPage.jsx'))
const DocumentWizardPage = lazy(() => import('./pages/DocumentWizardPage.jsx'))
const DataWorkspaceWizardPage = lazy(() => import('./pages/DataWorkspaceWizardPage.jsx'))
const ConversationMemoryPage = lazy(() => import('./pages/ConversationMemoryPage.jsx'))
const CorpusPage = lazy(() => import('./pages/CorpusPage.jsx'))
const CoreModelPage = lazy(() => import('./pages/CoreModelPage.jsx'))
const ChunkStudioPage = lazy(() => import('./pages/ChunkStudioPage.jsx'))
const DataHelpPage = lazy(() => import('./pages/DataHelpPage.jsx'))
const DataOverviewPage = lazy(() => import('./pages/DataOverviewPage.jsx'))
const ExternalDataProvidersPage = lazy(() => import('./pages/ExternalDataProvidersPage.jsx'))
const GovernancePage = lazy(() => import('./pages/GovernancePage.jsx'))
const IncrementalTrainingPage = lazy(() => import('./pages/IncrementalTrainingPage.jsx'))
const FeedbackPage = lazy(() => import('./pages/FeedbackPage.jsx'))
const InferenceRuntimePage = lazy(() => import('./pages/InferenceRuntimePage.jsx'))
const InstructionTuningPage = lazy(() => import('./pages/InstructionTuningPage.jsx'))
const ManualDataPage = lazy(() => import('./pages/ManualDataPage.jsx'))
const MiniBrainPage = lazy(() => import('./pages/MiniBrainPage.jsx'))
const ModelEvaluationPage = lazy(() => import('./pages/ModelEvaluationPage.jsx'))
const ModelRegistryPage = lazy(() => import('./pages/ModelRegistryPage.jsx'))
const OverviewPage = lazy(() => import('./pages/OverviewPage.jsx'))
const PretrainingReadinessPage = lazy(() => import('./pages/PretrainingReadinessPage.jsx'))
const ProductionReadinessPage = lazy(() => import('./pages/ProductionReadinessPage.jsx'))
const KnowledgeGapsPage = lazy(() => import('./pages/KnowledgeGapsPage.jsx'))
const KnowledgeRoutingPage = lazy(() => import('./pages/KnowledgeRoutingPage.jsx'))
const PublicChatRoutingPage = lazy(() => import('./pages/PublicChatRoutingPage.jsx'))
const TrustedWebPage = lazy(() => import('./pages/TrustedWebPage.jsx'))
const DeterministicToolsPage = lazy(() => import('./pages/DeterministicToolsPage.jsx'))
const GatewayDatasetRagBridgePage = lazy(() => import('./pages/GatewayDatasetRagBridgePage.jsx'))
const PilotMetricsPage = lazy(() => import('./pages/PilotMetricsPage.jsx'))
const PilotOperationsPage = lazy(() => import('./pages/PilotOperationsPage.jsx'))
const PromptOptimizationPage = lazy(() => import('./pages/PromptOptimizationPage.jsx'))
const RagPage = lazy(() => import('./pages/RagPage.jsx'))
const RagSandboxPage = lazy(() => import('./pages/RagSandboxPage.jsx'))
const SourcesRightsPage = lazy(() => import('./pages/SourcesRightsPage.jsx'))
const SystemPage = lazy(() => import('./pages/SystemPage.jsx'))
const TokenizerPage = lazy(() => import('./pages/TokenizerPage.jsx'))
const TrainingPage = lazy(() => import('./pages/TrainingPage.jsx'))

export default function App() {
  const [auth, setAuth] = useState({ checking: true, admin: null })
  const initialHashState = parseHash(window.location.hash.slice(1))
  const [active, setActive] = useState(initialHashState.page)
  const [documentNav, setDocumentNav] = useState({
    documentPublicId: initialHashState.documentPublicId, tab: initialHashState.tab, step: initialHashState.step,
  })
  const [datasetVersionId, setDatasetVersionId] = useState(null)
  const [verificationCandidateId, setVerificationCandidateId] = useState(null)
  const [sampleImportCaseId, setSampleImportCaseId] = useState(null)
  const [ragSandboxSampleImportId, setRagSandboxSampleImportId] = useState(null)
  const [miniBrainInitialTab, setMiniBrainInitialTab] = useState(null)
  useEffect(() => { getMe().then((data) => setAuth({ checking: false, admin: data.admin })).catch(() => setAuth({ checking: false, admin: null })) }, [])
  useEffect(() => {
    function handlePopState() {
      const parsed = parseHash(window.location.hash.slice(1))
      setActive(parsed.page)
      setDocumentNav({ documentPublicId: parsed.documentPublicId, tab: parsed.tab, step: parsed.step })
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])
  async function signIn(username, password) { const data = await login(username, password); setAuth({ checking: false, admin: data.admin }); setActive('Overview') }
  async function signOut() { try { await logout() } finally { setAuth({ checking: false, admin: null }); window.history.replaceState(null, '', '#Login') } }
  if (auth.checking) return <main className="login-shell"><div className="notice">Checking admin session…</div></main>
  if (!auth.admin) return <LoginPage onLogin={signIn} />
  const selectPage = (page) => { window.history.replaceState(null, '', `#${encodeURIComponent(page)}`); setActive(page); setDocumentNav({ documentPublicId: null, tab: null, step: null }) }
  const openDocumentsTab = (documentPublicId, tab) => {
    window.history.pushState(null, '', buildDocumentsHash(documentPublicId, tab))
    setActive('Documents'); setDocumentNav({ documentPublicId, tab, step: null })
  }
  const openWizardStep = (documentPublicId, step) => {
    window.history.pushState(null, '', buildWizardHash(documentPublicId, step))
    setActive('Document Wizard'); setDocumentNav({ documentPublicId, tab: null, step })
  }
  const openDatasetVersion = (versionPublicId) => { setDatasetVersionId(versionPublicId); selectPage('Datasets') }
  const openVerificationForCandidate = (candidatePublicId) => { setVerificationCandidateId(candidatePublicId); selectPage('Dataset Verification') }
  const openSampleImportForCase = (casePublicId) => { setSampleImportCaseId(casePublicId); selectPage('Sample Import & Quarantine') }
  const openRagSandboxForSampleImport = (sampleImportPublicId) => { setRagSandboxSampleImportId(sampleImportPublicId); selectPage('RAG Sandbox') }
  const openMiniBrainAssistant = () => { setMiniBrainInitialTab('Assistant Intelligence'); selectPage('Brud Mini Brain') }
  let page = <PlaceholderPage name={active} />
  if (active === 'Overview') page = <OverviewPage onNavigate={selectPage} />
  if (active === 'System') page = <SystemPage />
  if (active === 'Pilot Operations') page = <PilotOperationsPage />
  if (active === 'Pilot Metrics') page = <PilotMetricsPage />
  if (active === 'Data Overview') page = <DataOverviewPage onNavigate={selectPage} />
  if (active === 'Data Help') page = <DataHelpPage onNavigate={selectPage} />
  if (active === 'Manual Data') page = <ManualDataPage />
  if (active === 'Sources & Rights') page = <SourcesRightsPage />
  if (active === 'External Data Providers') page = <ExternalDataProvidersPage />
  if (active === 'Dataset Discovery') page = <DatasetDiscoveryPage onOpenVerification={openVerificationForCandidate} />
  if (active === 'Dataset Verification') page = <DatasetVerificationPage initialCandidatePublicId={verificationCandidateId} onOpenSampleImport={openSampleImportForCase} />
  if (active === 'Sample Import & Quarantine') page = <DatasetSampleImportPage initialVerificationCasePublicId={sampleImportCaseId} onOpenRagSandbox={openRagSandboxForSampleImport} />
  if (active === 'RAG Sandbox') page = <RagSandboxPage initialSampleImportPublicId={ragSandboxSampleImportId} />
  if (active === 'Incremental Training') page = <IncrementalTrainingPage />
  if (active === 'Chunk & Record Studio') page = <ChunkStudioPage />
  if (active === 'Quality & Approval') page = <GovernancePage />
  if (active === 'Builds & Pipelines') page = <BuildsPipelinesPage />
  if (active === 'Datasets') page = <DatasetsPage initialVersionPublicId={datasetVersionId} />
  if (active === 'Documents') page = <DocumentsPage
      initialDocumentPublicId={documentNav.documentPublicId} initialTab={documentNav.tab}
      onNavigationChange={openDocumentsTab}
    />
  if (active === 'Document Wizard') page = <DocumentWizardPage
      onNavigate={selectPage} initialDocumentPublicId={documentNav.documentPublicId}
      initialStep={documentNav.step} onNavigationChange={openWizardStep}
      onOpenDatasetVersion={openDatasetVersion}
    />
  if (active === 'Data Workspace Wizard') page = <DataWorkspaceWizardPage onNavigate={selectPage} />
  if (active === 'Tokenizer') page = <TokenizerPage />
  if (active === 'Core Model') page = <CoreModelPage />
  if (active === 'Training') page = <TrainingPage />
  if (active === 'Base Training') page = <BaseTrainingPage />
  if (active === 'Instruction Tuning') page = <InstructionTuningPage />
  if (active === 'Evaluation') page = <ModelEvaluationPage />
  if (active === 'Model Registry') page = <ModelRegistryPage />
  if (active === 'Inference Runtime') page = <InferenceRuntimePage />
  if (active === 'Knowledge & RAG') page = <RagPage />
  if (active === 'Gateway → Dataset/RAG') page = <GatewayDatasetRagBridgePage />
  if (active === 'Prompt Optimization') page = <PromptOptimizationPage />
  if (active === 'Conversation & Memory') page = <ConversationMemoryPage />
  if (active === 'Feedback & Improvement') page = <FeedbackPage />
  if (active === 'Corpus Builder') page = <CorpusPage />
  if (active === 'Pretraining Readiness') page = <PretrainingReadinessPage />
  if (active === 'Production Readiness') page = <ProductionReadinessPage />
  if (active === 'Knowledge Routing') page = <KnowledgeRoutingPage />
  if (active === 'Public Chat Routing') page = <PublicChatRoutingPage />
  if (active === 'Knowledge Gaps') page = <KnowledgeGapsPage />
  if (active === 'Trusted Web') page = <TrustedWebPage />
  if (active === 'Deterministic Tools') page = <DeterministicToolsPage />
  if (active === 'Admin Assistant') page = <AdminAssistantPage />
  if (active === 'Assistant Center') page = <AssistantCenterPage admin={auth.admin} />
  if (active === 'Brud Mini Brain') page = <MiniBrainPage initialTab={miniBrainInitialTab} admin={auth.admin} />
  return <DashboardLayout active={active} onSelect={selectPage} onOpenMiniBrainAssistant={openMiniBrainAssistant} admin={auth.admin} onLogout={signOut}>
      <Suspense fallback={<PageSkeleton />}>{page}</Suspense>
    </DashboardLayout>
}

function PageSkeleton() {
  return (
    <div className="page-skeleton" style={{ padding: '1.5rem' }}>
      <Skeleton lines={1} height="1.75rem" width="240px" className="page-skeleton-title" />
      <div style={{ marginTop: '1rem' }}>
        <Skeleton lines={6} height="1rem" />
      </div>
    </div>
  )
}
