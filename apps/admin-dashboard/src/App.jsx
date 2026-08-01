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
import RagPage from './pages/RagPage.jsx'
import RagSandboxPage from './pages/RagSandboxPage.jsx'
import SourcesRightsPage from './pages/SourcesRightsPage.jsx'
import SystemPage from './pages/SystemPage.jsx'
import TokenizerPage from './pages/TokenizerPage.jsx'
import TrainingPage from './pages/TrainingPage.jsx'
import { getMe, login, logout } from './services/api.js'

export default function App() {
  const [auth, setAuth] = useState({ checking: true, admin: null })
  const initialPage = decodeURIComponent(window.location.hash.slice(1)) || 'Overview'
  const [active, setActive] = useState(initialPage)
  const [verificationCandidateId, setVerificationCandidateId] = useState(null)
  const [sampleImportCaseId, setSampleImportCaseId] = useState(null)
  const [ragSandboxSampleImportId, setRagSandboxSampleImportId] = useState(null)
  useEffect(() => { getMe().then((data) => setAuth({ checking: false, admin: data.admin })).catch(() => setAuth({ checking: false, admin: null })) }, [])
  async function signIn(username, password) { const data = await login(username, password); setAuth({ checking: false, admin: data.admin }); setActive('Overview') }
  async function signOut() { try { await logout() } finally { setAuth({ checking: false, admin: null }); window.history.replaceState(null, '', '#Login') } }
  if (auth.checking) return <main className="login-shell"><div className="notice">Checking admin session…</div></main>
  if (!auth.admin) return <LoginPage onLogin={signIn} />
  const selectPage = (page) => { window.history.replaceState(null, '', `#${encodeURIComponent(page)}`); setActive(page) }
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
  if (active === 'Datasets') page = <DatasetsPage />
  if (active === 'Documents') page = <DocumentsPage />
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
  if (active === 'Admin Assistant') page = <AdminAssistantPage />
  return <DashboardLayout active={active} onSelect={selectPage} admin={auth.admin} onLogout={signOut}>{page}</DashboardLayout>
}
