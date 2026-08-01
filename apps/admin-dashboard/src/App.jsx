import { useEffect, useState } from 'react'
import DashboardLayout from './components/DashboardLayout.jsx'
import AdminAssistantPage from './pages/AdminAssistantPage.jsx'
import BaseTrainingPage from './pages/BaseTrainingPage.jsx'
import BuildsPipelinesPage from './pages/BuildsPipelinesPage.jsx'
import DatasetDiscoveryPage from './pages/DatasetDiscoveryPage.jsx'
import DatasetSampleImportPage from './pages/DatasetSampleImportPage.jsx'
import DatasetVerificationPage from './pages/DatasetVerificationPage.jsx'
import DatasetsPage from './pages/DatasetsPage.jsx'
import DocumentsPage from './pages/DocumentsPage.jsx'
import DocumentWizardPage from './pages/DocumentWizardPage.jsx'
import ConversationMemoryPage from './pages/ConversationMemoryPage.jsx'
import CorpusPage from './pages/CorpusPage.jsx'
import CoreModelPage from './pages/CoreModelPage.jsx'
import ChunkStudioPage from './pages/ChunkStudioPage.jsx'
import DataHelpPage from './pages/DataHelpPage.jsx'
import DataOverviewPage from './pages/DataOverviewPage.jsx'
import ExternalDataProvidersPage from './pages/ExternalDataProvidersPage.jsx'
import GovernancePage from './pages/GovernancePage.jsx'
import IncrementalTrainingPage from './pages/IncrementalTrainingPage.jsx'
import FeedbackPage from './pages/FeedbackPage.jsx'
import InferenceRuntimePage from './pages/InferenceRuntimePage.jsx'
import InstructionTuningPage from './pages/InstructionTuningPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ManualDataPage from './pages/ManualDataPage.jsx'
import ModelEvaluationPage from './pages/ModelEvaluationPage.jsx'
import ModelRegistryPage from './pages/ModelRegistryPage.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import PlaceholderPage from './pages/PlaceholderPage.jsx'
import PretrainingReadinessPage from './pages/PretrainingReadinessPage.jsx'
import ProductionReadinessPage from './pages/ProductionReadinessPage.jsx'
import KnowledgeGapsPage from './pages/KnowledgeGapsPage.jsx'
import KnowledgeRoutingPage from './pages/KnowledgeRoutingPage.jsx'
import PublicChatRoutingPage from './pages/PublicChatRoutingPage.jsx'
import TrustedWebPage from './pages/TrustedWebPage.jsx'
import DeterministicToolsPage from './pages/DeterministicToolsPage.jsx'
import RagPage from './pages/RagPage.jsx'
import RagSandboxPage from './pages/RagSandboxPage.jsx'
import SourcesRightsPage from './pages/SourcesRightsPage.jsx'
import SystemPage from './pages/SystemPage.jsx'
import TokenizerPage from './pages/TokenizerPage.jsx'
import TrainingPage from './pages/TrainingPage.jsx'
import { getMe, login, logout } from './services/api.js'
import { buildDocumentsHash, buildWizardHash, parseHash } from './services/documentNavigation.js'

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
  let page = <PlaceholderPage name={active} />
  if (active === 'Overview') page = <OverviewPage />
  if (active === 'System') page = <SystemPage />
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
  if (active === 'Tokenizer') page = <TokenizerPage />
  if (active === 'Core Model') page = <CoreModelPage />
  if (active === 'Training') page = <TrainingPage />
  if (active === 'Base Training') page = <BaseTrainingPage />
  if (active === 'Instruction Tuning') page = <InstructionTuningPage />
  if (active === 'Evaluation') page = <ModelEvaluationPage />
  if (active === 'Model Registry') page = <ModelRegistryPage />
  if (active === 'Inference Runtime') page = <InferenceRuntimePage />
  if (active === 'Knowledge & RAG') page = <RagPage />
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
  return <DashboardLayout active={active} onSelect={selectPage} admin={auth.admin} onLogout={signOut}>{page}</DashboardLayout>
}
