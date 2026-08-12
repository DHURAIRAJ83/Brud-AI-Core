import { useEffect, useRef, useState } from 'react'
import Button from '../components/Button.jsx'
import ChatPanel from '../components/chat/ChatPanel.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusCard from '../components/StatusCard.jsx'
import { useToast } from '../components/Toast.jsx'
import DiagnosticsTab from './mini-brain/DiagnosticsTab.jsx'
import CapabilityTab from './mini-brain/CapabilityTab.jsx'
import ContinuousLearningCenterTab from './mini-brain/ContinuousLearningCenterTab.jsx'
import ContinuousLearningTab from './mini-brain/ContinuousLearningTab.jsx'
import DatasetEvolutionTab from './mini-brain/DatasetEvolutionTab.jsx'
import DatasetIntelligenceTab from './mini-brain/DatasetIntelligenceTab.jsx'
import IntelligenceEngineTab from './mini-brain/IntelligenceEngineTab.jsx'
import KnowledgeCoreTab from './mini-brain/KnowledgeCoreTab.jsx'
import LanguageIntelligenceTab from './mini-brain/LanguageIntelligenceTab.jsx'
import LearningSupervisorTab from './mini-brain/LearningSupervisorTab.jsx'
import LogsTab from './mini-brain/LogsTab.jsx'
import MultimodalDatasetGeneratorTab from './mini-brain/MultimodalDatasetGeneratorTab.jsx'
import OverviewTab from './mini-brain/OverviewTab.jsx'
import PipelineCoordinatorTab from './mini-brain/PipelineCoordinatorTab.jsx'
import ReleasePipelineTab from './mini-brain/ReleasePipelineTab.jsx'
import ResearchCenterTab from './mini-brain/ResearchCenterTab.jsx'
import ResponseQualityTab from './mini-brain/ResponseQualityTab.jsx'
import RuntimeTab from './mini-brain/RuntimeTab.jsx'
import SettingsTab from './mini-brain/SettingsTab.jsx'
import VisionIntelligenceTab from './mini-brain/VisionIntelligenceTab.jsx'
import VisionModelCenterTab from './mini-brain/VisionModelCenterTab.jsx'
import VisionRAGTab from './mini-brain/VisionRAGTab.jsx'
import {
  analyzeQuestion, capabilityDiagnostics, capabilityGenerate, continuousLearningAdminReview,
  continuousLearningAnalyzeDifficulty, continuousLearningAnalyzeFailures,
  continuousLearningAnalyzeHallucinations, continuousLearningAnalyzeKnowledgeGaps,
  continuousLearningCollectFeedback, continuousLearningCreateSession, continuousLearningDetectWeakTopics,
  continuousLearningDiagnostics, continuousLearningEvents, continuousLearningGenerateReport,
  continuousLearningRankPriorities, continuousLearningRecommendDatasets,
  continuousLearningRecommendTraining, continuousLearningSession, continuousLearningSessions,
  clcAdminReview, clcBuildDraft, clcBuildLearningQueue, clcBuildRoadmap, clcCreateSession,
  clcDiagnostics, clcEvents, clcEvolveKnowledgeGaps, clcGenerateRecommendation, clcGenerateReport,
  clcIngestProviderResults, clcListMemory, clcPlanDatasetEvolution, clcPrepareProviderRequest,
  clcRecordMemory, clcSession, clcSessions,
  datasetAdvancedDiagnostics,
  datasetAdvancedReport, datasetIntelligenceDiagnostics, datasetIntelligenceReport, disableMiniBrain,
  enableMiniBrain, knowledgeCoreCoverage, knowledgeCoreDomains, knowledgeCoreItem,
  learningSupervisorAdminReview, learningSupervisorAnalyzeTraining, learningSupervisorCompareModels,
  learningSupervisorCreateSession, learningSupervisorDecideDataset, learningSupervisorDecideRag,
  learningSupervisorEvents, learningSupervisorFinalizeRag, learningSupervisorMonitorTraining,
  learningSupervisorProfiles, learningSupervisorRecommendations, learningSupervisorReleaseCandidate,
  learningSupervisorRunBenchmark, learningSupervisorRunRag, learningSupervisorSession,
  learningSupervisorSessions, learningSupervisorSubmitTraining, learningSupervisorValidateDataset,
  listRuntimeModels, loadRuntimeModel, miniBrainDiagnostics, miniBrainHealth, miniBrainLogs,
  miniBrainRuntimeHealth,
  miniBrainSettings, miniBrainStatus, miniBrainVersion, qualityDiagnostics, qualityGenerate,
  registerRuntimeModel, releasePipelineActivate, releasePipelineAdminReview, releasePipelineConvert,
  releasePipelineCreateSession, releasePipelineCreateVersion, releasePipelineDiagnostics,
  releasePipelineEvaluateRollback,
  releasePipelineEvents, releasePipelineExecuteRollback, releasePipelinePerformance,
  releasePipelineQuantize, releasePipelineRegistry, releasePipelineReport, releasePipelineSession,
  releasePipelineSessions, releasePipelineValidateCheckpoint, releasePipelineVerify,
  rcAddProvider, rcAdminReviewDraft, rcAdminReviewRag, rcAnalyzeTrainingReport, rcBuildDatasetDraft,
  rcBuildLocalDraft, rcCheckTrainingGate, rcCreateSession, rcDiagnostics, rcEvents,
  rcFinalizeRagEvaluation, rcGenerateReport, rcIngestProviderResults, rcListMemory, rcListProviders,
  rcPrepareProviderRequestPackage, rcPrepareResearchRequest, rcRecordMemory, rcRunRagEvaluation,
  rcSelectMode, rcSession, rcSessions, rcSetProviderStatus,
  deAdminReview, deAdminReviewRag, deCreateSession, deDiagnostics, deEvents,
  deFinalizeRagEvaluation, deGenerateReport, deGenerateRecommendation, deRunDatasetEvolution,
  deRunKnowledgeEvolution, deRunRagEvaluation, deRunSimulation, deSession, deSessions,
  pcAdminDecide, pcCreateSession, pcDiagnostics, pcEvents, pcGenerateRecommendation,
  pcGenerateReport, pcGenerateTimeline, pcGenerateTrainingReadiness, pcLinkDatasetEvolution,
  pcLinkResearch, pcLinkResearchCenter, pcLinkTraining, pcPredictImprovement,
  pcRefreshResearchCenter, pcRefreshTraining, pcRunRagFirstEnforcement, pcSession, pcSessions,
  liAdminReview, liCreateSession, liDiagnostics, liEvents, liGenerateReport, liRunDatasetDraft,
  liRunGrammarAnalysis, liRunLanguageScan, liRunOcrAnalysis, liRunQualityScore,
  liRunSpellAnalysis, liRunTanglishAnalysis, liRunTranslationAnalysis, liRunUnicodeValidation,
  liSession, liSessions,
  viAdminReview, viAnnotate, viCreateSession, viDiagnostics, viEvents, viFinishAnnotation,
  viGenerateReport, viImages, viObjects, viRunBoundingBoxPlan, viRunCaption, viRunDatasetDraft,
  viRunImageExtraction, viRunImageQuality, viRunKnowledgeGraph, viRunOcrCrossValidation,
  viRunQaGeneration, viRunQualityScore, viRunVisionUnderstanding, viSession, viSessions,
  vmAdminReview, vmCorrections, vmCreateSession, vmDiagnostics, vmEvents, vmFinishReview,
  vmGenerateReport, vmLearningMemory, vmPredictions, vmProviders, vmReviewPrediction,
  vmRunCaption, vmRunCorrectionMemory, vmRunDatasetDraft, vmRunImageLoad, vmRunKnowledgeGraph,
  vmRunObjectDetection, vmRunOcrCrossValidation, vmRunProviderSelection, vmRunQualityScore,
  vmRunRelationshipDetection, vmRunSceneDetection, vmSession, vmSessions, vmSetProviderStatus,
  mdAdminReview, mdCreateSession, mdDatasetMemory, mdDeleteDraft, mdDiagnostics, mdEvents,
  mdExportDraft, mdGenerateReport, mdMergeDatasets, mdRecords, mdRunCollectImages,
  mdRunCollectSources, mdRunCollectText, mdRunConversationBuilder, mdRunDatasetDraft,
  mdRunDuplicateDetection, mdRunInstructionBuilder, mdRunMergeMetadata, mdRunQualityAnalysis,
  mdSession, mdSessions, mdSplitDataset,
  vrAdminReview, vrCorrect, vrCreateSession, vrDiagnostics, vrEvents, vrEvidence, vrGenerateReport,
  vrRagMemory, vrRunAnswer, vrRunEvidenceFusion, vrRunHallucinationCheck, vrRunImageRetrieval,
  vrRunKnowledgeGraphRetrieval, vrRunObjectRetrieval, vrRunOcrRetrieval, vrRunQuality,
  vrRunTextRetrieval, vrSession, vrSessions,
  tpAdminReview, tpCreateSession, tpDiagnostics, tpEvents, tpGenerateReport, tpMemory, tpPackages,
  tpRagMemory, tpRunAnalyzeLanguage, tpRunAnalyzeTokenizer, tpRunAnalyzeVision, tpRunBuildPackage,
  tpRunCollectDatasets, tpRunCollectRagMemory, tpRunEstimateHardware, tpRunPlanCurriculum,
  tpRunPlanSplits, tpSession, tpSessions,
  ecAdminReview, ecCreateSession, ecDiagnostics, ecEvents, ecExports, ecGenerateReport, ecMemory,
  ecResults, ecRunCollectDatasets, ecRunCollectRagSessions, ecRunCollectTrainingPackages,
  ecRunGroundingRetrievalBenchmarks, ecRunLanguageBenchmarks, ecRunMultimodalBenchmarks,
  ecRunOcrBenchmarks, ecRunPackageBenchmarks, ecRunRegression, ecSession, ecSessions,
  rgAdminReview, rgArtifacts, rgBuildPackage, rgBuildRiskRollback, rgCreateSession, rgDiagnostics,
  rgEvents, rgGenerateReport, rgMemory, rgRunBenchmarks, rgRunCollectDatasets, rgRunCollectEvaluation,
  rgRunCollectPackage, rgRunCollectRag, rgRunCompliance, rgRunSafety, rgSession, rgSessions,
  gaAdminReview, gaAnalyze, gaArchive, gaAuthorize, gaBuildEvidence, gaCollect, gaCreateSession,
  gaDiagnostics, gaDispatch, gaEvents, gaGenerateReport, gaMemory, gaNormalize, gaProviderRuns,
  gaSanitize, gaSelectProviders, gaSession, gaSessions,
  teArchive, teAudit, teAuthorize, teBuildManifest, teCancel, teCheckpoints, teCreateJob,
  teDiagnostics, teEvents, teFinalize, teGenerateReport, teJob, teJobs, teMemory, teMetrics,
  tePause, tePlanResources, teReserveRuntime, teResume, teSaveCheckpoint, teStart, teStreamMetric,
  teValidatePackage, teValidateRelease,
  pcrAnalytics, pcrCandidate, pcrCandidateEvents, pcrCandidates, pcrClusters, pcrDiagnostics,
  pcrExportAnalytics, pcrExportCandidates, pcrGenerateCandidates, pcrMessages, pcrReviewCandidate,
  pcrSession, pcrSessionEvents, pcrSessions, pcrSignals,
  pgArchivePlugin, pgBuildFilesystemPolicy, pgBuildNetworkPolicy, pgBuildSandboxProfile,
  pgCheckPolicy, pgClassifyCapabilities, pgComputeRiskScore, pgConsents, pgDiagnostics,
  pgDisablePlugin, pgEnablePlugin, pgEvaluatePermission, pgEvents, pgGenerateReport,
  pgGrantPermission, pgIssueToken, pgMemory, pgPermissions, pgPlugin, pgPlugins,
  pgRegisterPlugin, pgRequestConsent, pgRevokePermission, pgRuntimeEvent, pgValidateManifest,
  prArchiveExecution, prCancelExecution, prDiagnostics, prExecute, prExecution, prExecutionLogs,
  prExecutions, prGenerateReport, prMemory, prPublicExecute, prRuntimeEvent, prStatistics,
  reloadRuntimeModel, runKnowledgeCoreValidation, runtimeDiagnostics,
  runtimeStatistics, runtimeStatus, searchKnowledgeCore, seedKnowledgeCore, unloadRuntimeModel,
  updateMiniBrainSettings,
  voDiagnostics, voEvents, voMemory, voSession, voSessions, voStatistics, voTestStt, voTestTts,
  voPublicCreateSession, voPublicFinishSession, voPublicSendChunk,
  psDiagnostics, psProviders, psCreateProvider, psUpdateProvider, psEnableProvider, psDisableProvider,
  psSetSecret, psDeleteSecret, psTestConnection, psProviderAudit,
  psArchiveProvider, psMemory,
  lrDiagnostics, lrChat, lrExplainPage,
  lrSummarizeReport, lrSummarizeRegression, lrExplainError, lrNextActions,
  lcHardware, lcScanModels, lcRecommendations, lcSaveLocalModel, lcSaveProvider,
  lcProvidersCatalog, lcSetupGuide, lcDiagnostics,
  rmHardware, rmCatalog, rmInstalled, rmStatus, rmRecommendation, rmDownload, rmVerify,
  rmInstall, rmLoad, rmUnload, rmBenchmark, rmRemove, rmEvents, rmMemory,
} from '../services/api.js'

const tabs = [
  'Overview', 'Settings', 'Logs', 'Diagnostics', 'Knowledge Core', 'Intelligence Engine', 'Runtime',
  'Response Quality', 'Capability', 'Dataset Intelligence', 'Learning Supervisor', 'Release Pipeline',
  'Continuous Learning', 'Continuous Learning Center', 'Research Center', 'Dataset Evolution',
  'Pipeline Coordinator', 'Language Intelligence', 'Vision Intelligence', 'Vision Model Center',
  'Multimodal Dataset Generator', 'Vision RAG', 'Training Pipeline', 'Evaluation Center',
  'Release Governance', 'External AI Gateway', 'Training Engine', 'Public Chat Runtime',
  'Plugin Governance', 'Plugin Runtime', 'Voice Runtime', 'Provider Settings', 'Assistant Intelligence', 'Local Setup', 'Runtime Manager', 'Future Model',
]

// Mirrors ProductionReadinessPage.jsx's tabFromHash() verbatim -- the
// top-level tab is encoded into the URL hash so a hard refresh returns to
// the same tab instead of always resetting to Overview.
function tabFromHash() {
  const queryIndex = window.location.hash.indexOf('?')
  if (queryIndex === -1) return 'Overview'
  const requested = new URLSearchParams(window.location.hash.slice(queryIndex + 1)).get('tab')
  return requested && tabs.includes(requested) ? requested : 'Overview'
}
const MAX_QUALITY_HISTORY = 10
const tpSubTabs = [
  'Overview', 'Sources', 'Language', 'Vision', 'Tokenizer', 'Splits', 'Curriculum', 'Hardware',
  'Package', 'Report', 'History', 'Diagnostics',
]
const ecSubTabs = [
  'Overview', 'Sources', 'Language', 'OCR', 'Grounding', 'Retrieval', 'Multimodal', 'Package',
  'Regression', 'Report', 'Exports', 'History', 'Diagnostics',
]
const rgSubTabs = [
  'Overview', 'Sources', 'Safety', 'Compliance', 'Benchmarks', 'Risks', 'Rollback', 'Compatibility',
  'Prerequisites', 'Package', 'Report', 'History', 'Diagnostics',
]
const gaSubTabs = [
  'Overview', 'Authorization', 'Providers', 'Sanitization', 'Public Evaluation', 'Data Acquisition',
  'Provider Responses', 'Agreement', 'Evidence', 'Report', 'History', 'Diagnostics',
]
const teSubTabs = [
  'Overview', 'Jobs', 'Authorization', 'Resources', 'Manifest', 'Runtime', 'Metrics', 'Checkpoints',
  'Logs', 'Report', 'Archive', 'History', 'Diagnostics',
]
const pcrSubTabs = [
  'Overview', 'Live Sessions', 'Conversations', 'Analytics', 'Feedback Signals', 'Failure Clusters',
  'Improvement Queue', 'Candidate Review', 'Admin Handoffs', 'Exports', 'Runtime Diagnostics',
  'Safety Monitor', 'History',
]
const pgSubTabs = [
  'Overview', 'Plugin Registry', 'Validation', 'Capabilities', 'Risk Analysis', 'Sandbox',
  'Filesystem', 'Network', 'Permissions', 'Consents', 'Runtime Events', 'Reports', 'Diagnostics',
]
const prSubTabs = [
  'Overview', 'Execute', 'Active Executions', 'Results', 'Filesystem', 'Network', 'Permissions',
  'Consents', 'Public Chat', 'Admin Assistant', 'Audit', 'History', 'Diagnostics',
]
const voSubTabs = [
  'Overview', 'Public Voice Chat', 'Admin Voice Assistant', 'Sessions', 'STT', 'TTS',
  'Permissions', 'Diagnostics', 'Metrics', 'Events', 'Memory', 'Settings', 'History',
]
const psSubTabs = [
  'Overview', 'External AI', 'OpenAI', 'Anthropic', 'Gemini', 'OpenRouter', 'Speech',
  'STT', 'TTS', 'Local Models', 'Connection Tests', 'Audit', 'Diagnostics',
]
const psProviderKeys = ['openrouter', 'openai', 'anthropic', 'gemini', 'faster_whisper', 'coqui_tts', 'local_llm']
const psRequiredSecrets = {
  openrouter: ['api_key'], openai: ['api_key'], anthropic: ['api_key'], gemini: ['api_key'],
  faster_whisper: [], coqui_tts: [], local_llm: [],
}
// "Conversations" was folded into "Chat" -- ChatPanel's variant="full"
// already includes its own session list (9 sub-tabs -> 8).
const lrSubTabs = [
  'Chat', 'Explain Page', 'Summarize Report', 'Summarize Regression',
  'Explain Error', 'Next Actions', 'Local Model Config', 'Diagnostics',
]
const lcSubTabs = [
  'Hardware', 'Local Models', 'Recommendations', 'Local Configuration', 'External Providers',
  'Diagnostics', 'Setup Guide', 'Help',
]
const lcExternalProviderKeys = ['openai', 'anthropic', 'gemini', 'openrouter']
const rmSubTabs = [
  'Overview', 'Catalog', 'Installed', 'Download', 'Load / Unload', 'Benchmark',
  'Performance', 'Diagnostics', 'Events', 'History',
]

function mbBenchmarkTone(rating) {
  if (rating === 'excellent' || rating === 'good') return 'good'
  if (rating === 'fair' || rating === 'poor') return 'waiting'
  return 'neutral'
}

function mbQualityTone(status) {
  if (status === 'good' || status === 'excellent') return 'good'
  if (status === 'fair' || status === 'limited') return 'waiting'
  return 'neutral'
}

export default function MiniBrainPage({ initialTab, admin } = {}) {
  const toast = useToast()
  // An explicit initialTab (the Admin Assistant widget's "Open Mini Brain
  // Assistant" deep-link) wins on first mount; otherwise the URL hash
  // controls the tab, same precedence order as the plan requires.
  const [tab, setTab] = useState(() => (initialTab && tabs.includes(initialTab) ? initialTab : tabFromHash()))
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [status, setStatus] = useState(null)
  const [settings, setSettings] = useState(null)
  const [logLevel, setLogLevel] = useState('info')
  const [logs, setLogs] = useState({ items: [], total: 0 })
  const [diagnostics, setDiagnostics] = useState(null)
  const [version, setVersion] = useState(null)
  const [busy, setBusy] = useState(false)
  const [runtimeHealth, setRuntimeHealth] = useState(null)

  const [knowledgeSubTab, setKnowledgeSubTab] = useState('Domains')
  const [kcDomains, setKcDomains] = useState([])
  const [kcQuery, setKcQuery] = useState('')
  const [kcResults, setKcResults] = useState([])
  const [kcSelectedItem, setKcSelectedItem] = useState(null)
  const [kcValidation, setKcValidation] = useState(null)
  const [kcCoverage, setKcCoverage] = useState(null)

  const [ieQuestion, setIeQuestion] = useState('')
  const [ieResult, setIeResult] = useState(null)
  const [ieBusy, setIeBusy] = useState(false)

  const [rtStatus, setRtStatus] = useState(null)
  const [rtStats, setRtStats] = useState(null)
  const [rtDiagnostics, setRtDiagnostics] = useState(null)
  const [rtModels, setRtModels] = useState([])
  const [rtBusy, setRtBusy] = useState(false)
  const [rtRegisterForm, setRtRegisterForm] = useState({ name: '', path: '', quantization: 'Q4_K_M', context_length: 2048 })

  const [qDiagnostics, setQDiagnostics] = useState(null)
  const [qQuestion, setQQuestion] = useState('')
  const [qResult, setQResult] = useState(null)
  const [qBusy, setQBusy] = useState(false)
  // Diagnostic history is session-local (React state) only -- MB-04B
  // deliberately adds no database table, so nothing here persists
  // across a page reload or a new session.
  const [qHistory, setQHistory] = useState([])

  const [capDiagnostics, setCapDiagnostics] = useState(null)
  const [capQuestion, setCapQuestion] = useState('')
  const [capResult, setCapResult] = useState(null)
  const [capBusy, setCapBusy] = useState(false)

  const [diSubTab, setDiSubTab] = useState('Overview')
  const [diSourceId, setDiSourceId] = useState('')
  const [diReport, setDiReport] = useState(null)
  const [diDiagnostics, setDiDiagnostics] = useState(null)
  const [diBusy, setDiBusy] = useState(false)

  const [showAdvanced, setShowAdvanced] = useState(false)
  const [advSubTab, setAdvSubTab] = useState('Overview')
  const [advReport, setAdvReport] = useState(null)
  const [advDiagnostics, setAdvDiagnostics] = useState(null)
  const [advBusy, setAdvBusy] = useState(false)

  const [lsSessions, setLsSessions] = useState([])
  const [lsProfiles, setLsProfiles] = useState([])
  const [lsSelectedId, setLsSelectedId] = useState('')
  const [lsSession, setLsSession] = useState(null)
  const [lsEvents, setLsEvents] = useState([])
  const [lsMonitor, setLsMonitor] = useState(null)
  const [lsBusy, setLsBusy] = useState(false)
  const [lsCreateForm, setLsCreateForm] = useState({ dataset_source_public_id: '', hyperparameter_profile: 'default' })
  const [lsRagForm, setLsRagForm] = useState({ rag_sandbox_experiment_public_id: '', retrieval_run_public_id: '', generation_assignment_public_id: '' })
  const [lsTrainingForm, setLsTrainingForm] = useState({ name: '', dataset_version_public_id: '', tokenizer_version_public_id: '', core_model_version_public_id: '', hyperparameter_profile: '' })
  const [lsBenchmarkForm, setLsBenchmarkForm] = useState({ model_evaluation_fixture_set_public_id: '', candidate_core_model_version_public_id: '' })
  const [lsCompareForm, setLsCompareForm] = useState({ previous_benchmark_run_public_id: '' })
  const [lsReleaseForm, setLsReleaseForm] = useState({ checkpoint_public_id: '', override_comment: '' })

  const [rpDiagnostics, setRpDiagnostics] = useState(null)
  const [rpSessions, setRpSessions] = useState([])
  const [rpSelectedId, setRpSelectedId] = useState('')
  const [rpSession, setRpSession] = useState(null)
  const [rpEvents, setRpEvents] = useState([])
  const [rpBusy, setRpBusy] = useState(false)
  const [rpCreateForm, setRpCreateForm] = useState({
    core_model_version_public_id: '', pretraining_checkpoint_public_id: '',
    model_release_family_public_id: '', target_quantizations: 'f16,q8_0',
    dataset_version_public_id: '', model_evaluation_run_public_id: '',
  })
  const [rpVersionForm, setRpVersionForm] = useState({ version: '', prerelease_label: '' })
  const [rpActivateLevel, setRpActivateLevel] = useState('')
  const [rpRollbackEvalForm, setRpRollbackEvalForm] = useState({ target_version: '' })
  const [rpRollbackExecuteForm, setRpRollbackExecuteForm] = useState({ target_release_public_id: '', reason: '' })
  const [rpRollbackEval, setRpRollbackEval] = useState(null)

  const [clDiagnostics, setClDiagnostics] = useState(null)
  const [clSessions, setClSessions] = useState([])
  const [clSelectedId, setClSelectedId] = useState('')
  const [clSession, setClSession] = useState(null)
  const [clEvents, setClEvents] = useState([])
  const [clBusy, setClBusy] = useState(false)
  const [clCycleWindowDays, setClCycleWindowDays] = useState(30)

  const [clcDiag, setClcDiag] = useState(null)
  const [clcMemoryItems, setClcMemoryItems] = useState([])
  const [clcSessionsList, setClcSessionsList] = useState([])
  const [clcSelectedId, setClcSelectedId] = useState('')
  const [clcSessionData, setClcSessionData] = useState(null)
  const [clcEventsList, setClcEventsList] = useState([])
  const [clcBusy, setClcBusy] = useState(false)
  const [clcDraftTopic, setClcDraftTopic] = useState('')
  const [clcProviders, setClcProviders] = useState('claude,openai')
  const [clcProviderOutputs, setClcProviderOutputs] = useState([{ provider: 'claude', output_text: '' }, { provider: 'openai', output_text: '' }])
  const [clcExistingDatasetId, setClcExistingDatasetId] = useState('')
  const [clcMemoryForm, setClcMemoryForm] = useState({
    continuous_learning_session_public_id: '', model_version_public_id: '', dataset_version_public_id: '',
    improvement_notes: '',
  })

  const [rcSubTab, setRcSubTab] = useState('Overview')
  const [rcDiag, setRcDiag] = useState(null)
  const [rcProviders, setRcProviders] = useState([])
  const [rcMemoryItems, setRcMemoryItems] = useState([])
  const [rcSessionsList, setRcSessionsList] = useState([])
  const [rcSelectedId, setRcSelectedId] = useState('')
  const [rcSessionData, setRcSessionData] = useState(null)
  const [rcEventsList, setRcEventsList] = useState([])
  const [rcReport, setRcReport] = useState(null)
  const [rcBusy, setRcBusy] = useState(false)
  const [rcNewTopic, setRcNewTopic] = useState('')
  const [rcPlanningCenterId, setRcPlanningCenterId] = useState('')
  const [rcMode, setRcMode] = useState('local_draft')
  const [rcProviderKeys, setRcProviderKeys] = useState('claude,openai')
  const [rcExistingDatasetId, setRcExistingDatasetId] = useState('')
  const [rcProviderOutputs, setRcProviderOutputs] = useState([
    { provider: 'claude', output_text: '' }, { provider: 'openai', output_text: '' },
  ])
  const [rcNewProviderForm, setRcNewProviderForm] = useState({ provider_key: '', display_name: '', requires_external_call: true, description: '' })
  const [rcRagForm, setRcRagForm] = useState({ rag_sandbox_experiment_public_id: '', retrieval_run_public_id: '', generation_assignment_public_id: '' })
  const [rcTrainingReportMb06Id, setRcTrainingReportMb06Id] = useState('')
  const [rcMemoryNotes, setRcMemoryNotes] = useState('')

  const [deSubTab, setDeSubTab] = useState('Overview')
  const [deDiag, setDeDiag] = useState(null)
  const [deSessionsList, setDeSessionsList] = useState([])
  const [deSelectedId, setDeSelectedId] = useState('')
  const [deSessionData, setDeSessionData] = useState(null)
  const [deEventsList, setDeEventsList] = useState([])
  const [deBusy, setDeBusy] = useState(false)
  const [deNewSourceId, setDeNewSourceId] = useState('')
  const [deRagForm, setDeRagForm] = useState({ rag_sandbox_experiment_public_id: '', retrieval_run_public_id: '', generation_assignment_public_id: '' })

  const [pcSubTab, setPcSubTab] = useState('Overview')
  const [pcDiag, setPcDiag] = useState(null)
  const [pcSessionsList, setPcSessionsList] = useState([])
  const [pcSelectedId, setPcSelectedId] = useState('')
  const [pcSessionData, setPcSessionData] = useState(null)
  const [pcEventsList, setPcEventsList] = useState([])
  const [pcBusy, setPcBusy] = useState(false)
  const [pcNewTopic, setPcNewTopic] = useState('')
  const [pcMb09Id, setPcMb09Id] = useState('')
  const [pcMb10Id, setPcMb10Id] = useState('')
  const [pcMb11Id, setPcMb11Id] = useState('')
  const [pcMb06Id, setPcMb06Id] = useState('')

  const [liSubTab, setLiSubTab] = useState('Overview')
  const [liDiag, setLiDiag] = useState(null)
  const [liSessionsList, setLiSessionsList] = useState([])
  const [liSelectedId, setLiSelectedId] = useState('')
  const [liSessionData, setLiSessionData] = useState(null)
  const [liEventsList, setLiEventsList] = useState([])
  const [liBusy, setLiBusy] = useState(false)
  const [liNewSourceId, setLiNewSourceId] = useState('')

  const [viSubTab, setViSubTab] = useState('Overview')
  const [viDiag, setViDiag] = useState(null)
  const [viSessionsList, setViSessionsList] = useState([])
  const [viSelectedId, setViSelectedId] = useState('')
  const [viSessionData, setViSessionData] = useState(null)
  const [viEventsList, setViEventsList] = useState([])
  const [viImagesList, setViImagesList] = useState([])
  const [viObjectsList, setViObjectsList] = useState([])
  const [viBusy, setViBusy] = useState(false)
  const [viNewDocumentSourceId, setViNewDocumentSourceId] = useState('')
  const [viNewDatasetSourceId, setViNewDatasetSourceId] = useState('')
  const [viDatasetTextInput, setViDatasetTextInput] = useState('')
  const [viAdminCaptionInput, setViAdminCaptionInput] = useState('')
  const [viAnnotateAction, setViAnnotateAction] = useState('rename')
  const [viAnnotateObjectId, setViAnnotateObjectId] = useState('')
  const [viAnnotateLabel, setViAnnotateLabel] = useState('')
  const [viAnnotateImageId, setViAnnotateImageId] = useState('')
  const [viAnnotateCaption, setViAnnotateCaption] = useState('')
  const [viAnnotateBoxX, setViAnnotateBoxX] = useState('0.1')
  const [viAnnotateBoxY, setViAnnotateBoxY] = useState('0.1')
  const [viAnnotateBoxW, setViAnnotateBoxW] = useState('0.2')
  const [viAnnotateBoxH, setViAnnotateBoxH] = useState('0.2')

  const [vmSubTab, setVmSubTab] = useState('Overview')
  const [vmDiag, setVmDiag] = useState(null)
  const [vmProvidersList, setVmProvidersList] = useState([])
  const [vmSessionsList, setVmSessionsList] = useState([])
  const [vmSelectedId, setVmSelectedId] = useState('')
  const [vmSessionData, setVmSessionData] = useState(null)
  const [vmEventsList, setVmEventsList] = useState([])
  const [vmPredictionsList, setVmPredictionsList] = useState([])
  const [vmCorrectionsList, setVmCorrectionsList] = useState([])
  const [vmLearningMemoryList, setVmLearningMemoryList] = useState([])
  const [vmBusy, setVmBusy] = useState(false)
  const [vmNewVisionSessionId, setVmNewVisionSessionId] = useState('')
  const [vmNewProviderKey, setVmNewProviderKey] = useState('llava_gguf_cpu')
  const [vmModelPath, setVmModelPath] = useState('')
  const [vmMmprojPath, setVmMmprojPath] = useState('')
  const [vmDatasetTextInput, setVmDatasetTextInput] = useState('')
  const [vmReviewAction, setVmReviewAction] = useState('approve')
  const [vmReviewPredictionId, setVmReviewPredictionId] = useState('')
  const [vmReviewLabel, setVmReviewLabel] = useState('')
  const [vmReviewImageId, setVmReviewImageId] = useState('')
  const [vmReviewBoxX, setVmReviewBoxX] = useState('0.1')
  const [vmReviewBoxY, setVmReviewBoxY] = useState('0.1')
  const [vmReviewBoxW, setVmReviewBoxW] = useState('0.2')
  const [vmReviewBoxH, setVmReviewBoxH] = useState('0.2')

  const [mdSubTab, setMdSubTab] = useState('Overview')
  const [mdDiag, setMdDiag] = useState(null)
  const [mdSessionsList, setMdSessionsList] = useState([])
  const [mdSelectedId, setMdSelectedId] = useState('')
  const [mdSessionData, setMdSessionData] = useState(null)
  const [mdEventsList, setMdEventsList] = useState([])
  const [mdRecordsList, setMdRecordsList] = useState([])
  const [mdMemoryList, setMdMemoryList] = useState([])
  const [mdBusy, setMdBusy] = useState(false)
  const [mdNewDocumentId, setMdNewDocumentId] = useState('')
  const [mdNewVisionSessionId, setMdNewVisionSessionId] = useState('')
  const [mdNewLanguageSessionId, setMdNewLanguageSessionId] = useState('')
  const [mdNewVisionModelSessionId, setMdNewVisionModelSessionId] = useState('')
  const [mdExportFormat, setMdExportFormat] = useState('json')
  const [mdExportResult, setMdExportResult] = useState(null)
  const [mdSplitRecordIds, setMdSplitRecordIds] = useState('')
  const [mdMergeSessionIds, setMdMergeSessionIds] = useState('')

  const [vrSubTab, setVrSubTab] = useState('Overview')
  const [vrDiag, setVrDiag] = useState(null)
  const [vrSessionsList, setVrSessionsList] = useState([])
  const [vrSelectedId, setVrSelectedId] = useState('')
  const [vrSessionData, setVrSessionData] = useState(null)
  const [vrEventsList, setVrEventsList] = useState([])
  const [vrEvidenceList, setVrEvidenceList] = useState([])
  const [vrMemoryList, setVrMemoryList] = useState([])
  const [vrBusy, setVrBusy] = useState(false)
  const [vrNewDatasetSessionId, setVrNewDatasetSessionId] = useState('')
  const [vrNewQuery, setVrNewQuery] = useState('')
  const [vrCorrectAction, setVrCorrectAction] = useState('correct_answer')
  const [vrCorrectAnswer, setVrCorrectAnswer] = useState('')
  const [vrCorrectEvidenceId, setVrCorrectEvidenceId] = useState('')
  const [vrCorrectSnippet, setVrCorrectSnippet] = useState('')
  const [vrAddEvidenceType, setVrAddEvidenceType] = useState('text')

  const [tpSubTab, setTpSubTab] = useState('Overview')
  const [tpDiag, setTpDiag] = useState(null)
  const [tpSessionsList, setTpSessionsList] = useState([])
  const [tpSelectedId, setTpSelectedId] = useState('')
  const [tpSessionData, setTpSessionData] = useState(null)
  const [tpEventsList, setTpEventsList] = useState([])
  const [tpPackagesList, setTpPackagesList] = useState([])
  const [tpMemoryList, setTpMemoryList] = useState([])
  const [tpAvailableRagMemory, setTpAvailableRagMemory] = useState([])
  const [tpBusy, setTpBusy] = useState(false)
  const [tpNewTopic, setTpNewTopic] = useState('')
  const [tpDatasetSessionIds, setTpDatasetSessionIds] = useState('')
  const [tpRagSessionIds, setTpRagSessionIds] = useState('')
  const [tpSplitSeed, setTpSplitSeed] = useState('')

  const [ecSubTab, setEcSubTab] = useState('Overview')
  const [ecDiag, setEcDiag] = useState(null)
  const [ecSessionsList, setEcSessionsList] = useState([])
  const [ecSelectedId, setEcSelectedId] = useState('')
  const [ecSessionData, setEcSessionData] = useState(null)
  const [ecEventsList, setEcEventsList] = useState([])
  const [ecExportsList, setEcExportsList] = useState([])
  const [ecMemoryList, setEcMemoryList] = useState([])
  const [ecBusy, setEcBusy] = useState(false)
  const [ecNewTopic, setEcNewTopic] = useState('')
  const [ecDatasetSessionIds, setEcDatasetSessionIds] = useState('')
  const [ecRagSessionIds, setEcRagSessionIds] = useState('')
  const [ecPackageSessionIds, setEcPackageSessionIds] = useState('')
  const [ecBaselineSessionId, setEcBaselineSessionId] = useState('')

  const [rgSubTab, setRgSubTab] = useState('Overview')
  const [rgDiag, setRgDiag] = useState(null)
  const [rgSessionsList, setRgSessionsList] = useState([])
  const [rgSelectedId, setRgSelectedId] = useState('')
  const [rgSessionData, setRgSessionData] = useState(null)
  const [rgEventsList, setRgEventsList] = useState([])
  const [rgArtifactsList, setRgArtifactsList] = useState([])
  const [rgMemoryList, setRgMemoryList] = useState([])
  const [rgBusy, setRgBusy] = useState(false)
  const [rgNewTopic, setRgNewTopic] = useState('')
  const [rgDatasetSessionIds, setRgDatasetSessionIds] = useState('')
  const [rgRagSessionIds, setRgRagSessionIds] = useState('')
  const [rgPackageSessionId, setRgPackageSessionId] = useState('')
  const [rgEvaluationSessionId, setRgEvaluationSessionId] = useState('')

  const [gaSubTab, setGaSubTab] = useState('Overview')
  const [gaDiag, setGaDiag] = useState(null)
  const [gaSessionsList, setGaSessionsList] = useState([])
  const [gaSelectedId, setGaSelectedId] = useState('')
  const [gaSessionData, setGaSessionData] = useState(null)
  const [gaEventsList, setGaEventsList] = useState([])
  const [gaProviderRunsList, setGaProviderRunsList] = useState([])
  const [gaMemoryList, setGaMemoryList] = useState([])
  const [gaBusy, setGaBusy] = useState(false)
  const [gaNewTopic, setGaNewTopic] = useState('')
  const [gaNewPurpose, setGaNewPurpose] = useState('public_style_stress_test')
  const [gaNewDatasetIds, setGaNewDatasetIds] = useState('')
  const [gaNewRagId, setGaNewRagId] = useState('')
  const [gaAuthorizationNote, setGaAuthorizationNote] = useState('')
  const [gaAdminStatedNeed, setGaAdminStatedNeed] = useState('')
  const [gaProviderKeys, setGaProviderKeys] = useState('openrouter')

  const [teSubTab, setTeSubTab] = useState('Overview')
  const [teDiag, setTeDiag] = useState(null)
  const [teJobsList, setTeJobsList] = useState([])
  const [teSelectedId, setTeSelectedId] = useState('')
  const [teJobData, setTeJobData] = useState(null)
  const [teEventsList, setTeEventsList] = useState([])
  const [teCheckpointsList, setTeCheckpointsList] = useState([])
  const [teMetricsList, setTeMetricsList] = useState([])
  const [teMemoryList, setTeMemoryList] = useState([])
  const [teBusy, setTeBusy] = useState(false)
  const [teNewTopic, setTeNewTopic] = useState('')
  const [teNewPackageId, setTeNewPackageId] = useState('')
  const [teNewReleaseId, setTeNewReleaseId] = useState('')
  const [teNewExecutionMode, setTeNewExecutionMode] = useState('simulation')
  const [teAuthorizationReason, setTeAuthorizationReason] = useState('')
  const [teMetricStep, setTeMetricStep] = useState('0')
  const [teMetricEpoch, setTeMetricEpoch] = useState('0')
  const [teCheckpointStep, setTeCheckpointStep] = useState('0')
  const [teCheckpointEpoch, setTeCheckpointEpoch] = useState('0')
  const [pcrSubTab, setPcrSubTab] = useState('Overview')
  const [pcrDiag, setPcrDiag] = useState(null)
  const [pcrAnalyticsData, setPcrAnalyticsData] = useState(null)
  const [pcrSessionsList, setPcrSessionsList] = useState([])
  const [pcrSelectedSessionId, setPcrSelectedSessionId] = useState('')
  const [pcrSessionData, setPcrSessionData] = useState(null)
  const [pcrMessagesList, setPcrMessagesList] = useState([])
  const [pcrSignalsList, setPcrSignalsList] = useState([])
  const [pcrSessionEventsList, setPcrSessionEventsList] = useState([])
  const [pcrClustersList, setPcrClustersList] = useState([])
  const [pcrCandidatesList, setPcrCandidatesList] = useState([])
  const [pcrApprovedCandidatesList, setPcrApprovedCandidatesList] = useState([])
  const [pcrSelectedCandidateId, setPcrSelectedCandidateId] = useState('')
  const [pcrCandidateData, setPcrCandidateData] = useState(null)
  const [pcrCandidateEventsList, setPcrCandidateEventsList] = useState([])
  const [pcrReviewNotes, setPcrReviewNotes] = useState('')
  const [pcrMinFrequency, setPcrMinFrequency] = useState('2')
  const [pcrExportResult, setPcrExportResult] = useState(null)
  const [pcrBusy, setPcrBusy] = useState(false)

  const [pgSubTab, setPgSubTab] = useState('Overview')
  const [pgDiag, setPgDiag] = useState(null)
  const [pgPluginsList, setPgPluginsList] = useState([])
  const [pgSelectedPluginId, setPgSelectedPluginId] = useState('')
  const [pgPluginData, setPgPluginData] = useState(null)
  const [pgPermissionsList, setPgPermissionsList] = useState([])
  const [pgConsentsList, setPgConsentsList] = useState([])
  const [pgEventsList, setPgEventsList] = useState([])
  const [pgMemoryList, setPgMemoryList] = useState([])
  const [pgBusy, setPgBusy] = useState(false)
  const [pgForm, setPgForm] = useState({
    plugin_id: '', name: '', version: '1.0.0', author: '', description: '', entrypoint: 'main.js',
    requested_scopes: '', allowed_domains: '', filesystem_roots: '', ui_components: '',
    local_storage_usage: false, cloud_storage_usage: false, minimum_brud_version: '1.0.0',
    signature_placeholder: 'unsigned', homepage: '', support_url: '', source: 'manual_upload',
  })
  const [pgEvalScopeKey, setPgEvalScopeKey] = useState('')
  const [pgEvalIsPublicChat, setPgEvalIsPublicChat] = useState(false)
  const [pgEvalUserIdHash, setPgEvalUserIdHash] = useState('')
  const [pgEvalResult, setPgEvalResult] = useState(null)
  const [pgPolicyCheckResult, setPgPolicyCheckResult] = useState(null)
  const [pgConsentScopeKey, setPgConsentScopeKey] = useState('')
  const [pgConsentUserIdentity, setPgConsentUserIdentity] = useState('')
  const [pgConsentGiven, setPgConsentGiven] = useState(true)
  const [pgConsentTtl, setPgConsentTtl] = useState('3600')
  const [pgTokenScopeKeys, setPgTokenScopeKeys] = useState('')
  const [pgTokenUserIdentity, setPgTokenUserIdentity] = useState('')
  const [pgTokenSessionIdentity, setPgTokenSessionIdentity] = useState('')
  const [pgTokenTtl, setPgTokenTtl] = useState('300')
  const [pgTokenResult, setPgTokenResult] = useState(null)
  const [prSubTab, setPrSubTab] = useState('Overview')
  const [prDiag, setPrDiag] = useState(null)
  const [prStats, setPrStats] = useState(null)
  const [prExecutionsList, setPrExecutionsList] = useState([])
  const [prMemoryList, setPrMemoryList] = useState([])
  const [prSelectedExecutionId, setPrSelectedExecutionId] = useState('')
  const [prExecutionData, setPrExecutionData] = useState(null)
  const [prLogs, setPrLogs] = useState(null)
  const [prReportResult, setPrReportResult] = useState(null)
  const [prBusy, setPrBusy] = useState(false)
  const [prExecForm, setPrExecForm] = useState({
    plugin_public_id: '', scope_key: '', arguments: '{}', execution_token: '', timeout_seconds: '5',
  })
  const [prExecResult, setPrExecResult] = useState(null)
  const [prPublicForm, setPrPublicForm] = useState({
    plugin_public_id: '', scope_key: '', arguments: '{}', raw_user_identity: '', execution_token: '',
  })
  const [prPublicResult, setPrPublicResult] = useState(null)

  const [voSubTab, setVoSubTab] = useState('Overview')
  const [voDiag, setVoDiag] = useState(null)
  const [voStats, setVoStats] = useState(null)
  const [voSessionsList, setVoSessionsList] = useState([])
  const [voMemoryList, setVoMemoryList] = useState([])
  const [voMetrics, setVoMetrics] = useState(null)
  const [voEventsList, setVoEventsList] = useState([])
  const [voSelectedSessionId, setVoSelectedSessionId] = useState('')
  const [voSessionData, setVoSessionData] = useState(null)
  const [voBusy, setVoBusy] = useState(false)
  const [voRecording, setVoRecording] = useState(false)
  const [voChunkSeq, setVoChunkSeq] = useState(0)
  const [voConsent, setVoConsent] = useState(false)
  const [voTestSttText, setVoTestSttText] = useState(null)
  const [voTestTtsForm, setVoTestTtsForm] = useState({ text: '' })
  const [voTestTtsResult, setVoTestTtsResult] = useState(null)

  const [psSubTab, setPsSubTab] = useState('Overview')
  const [psDiag, setPsDiag] = useState(null)
  const [psProvidersList, setPsProvidersList] = useState([])
  const [psAuditList, setPsAuditList] = useState([])
  const [psMemoryList, setPsMemoryList] = useState([])
  const [psSelectedProviderId, setPsSelectedProviderId] = useState('')
  const [psSecretInputs, setPsSecretInputs] = useState({})
  const [psBusy, setPsBusy] = useState(false)
  const [psTestResults, setPsTestResults] = useState({})

  const [lrSubTab, setLrSubTab] = useState('Chat')
  const [lrDiag, setLrDiag] = useState(null)
  // lrActiveSessionId is still real, used context: the non-Chat sub-tabs
  // (Explain Page, Summarize Report/Regression, Explain Error, Next
  // Actions) each continue the same conversation thread across actions.
  const [lrActiveSessionId, setLrActiveSessionId] = useState('')
  const [lrBusy, setLrBusy] = useState(false)
  const [lrExplainPageForm, setLrExplainPageForm] = useState({ page_id: '', nav_key: '' })
  const [lrReportForm, setLrReportForm] = useState('{}')
  const [lrRegressionForm, setLrRegressionForm] = useState('{}')
  const [lrErrorForm, setLrErrorForm] = useState('')
  const [lrStatusSnapshotForm, setLrStatusSnapshotForm] = useState('{}')
  const [lrNextActionsResult, setLrNextActionsResult] = useState(null)
  const [lrLocalModelConfig, setLrLocalModelConfig] = useState({
    model_path: '', context_length: 2048, max_tokens: 512, temperature: 0.3, threads: 4,
  })
  const [lrLocalProviderId, setLrLocalProviderId] = useState('')

  const [lcSubTab, setLcSubTab] = useState('Hardware')
  const [lcHardwareData, setLcHardwareData] = useState(null)
  const [lcScannedModels, setLcScannedModels] = useState([])
  const [lcRecommendationsData, setLcRecommendationsData] = useState(null)
  const [lcDiag, setLcDiag] = useState(null)
  const [lcGuide, setLcGuide] = useState(null)
  const [lcCatalog, setLcCatalog] = useState([])
  const [lcSetupBusy, setLcSetupBusy] = useState(false)
  const [lcLocalForm, setLcLocalForm] = useState({
    model_path: '', context_length: 2048, max_tokens: 512, temperature: 0.3, threads: 4, additional_model_dirs: '',
  })
  const [lcProviderForms, setLcProviderForms] = useState({})

  const [rmSubTab, setRmSubTab] = useState('Overview')
  const [rmHardwareData, setRmHardwareData] = useState(null)
  const [rmCatalogData, setRmCatalogData] = useState([])
  const [rmInstalledList, setRmInstalledList] = useState([])
  const [rmStatusData, setRmStatusData] = useState(null)
  const [rmRecommendationData, setRmRecommendationData] = useState(null)
  const [rmEventsList, setRmEventsList] = useState([])
  const [rmMemoryList, setRmMemoryList] = useState([])
  const [rmBusy, setRmBusy] = useState(false)
  const [rmSelectedModelId, setRmSelectedModelId] = useState('')
  const [rmLoadForm, setRmLoadForm] = useState({ context_length: 2048, max_tokens: 512, temperature: 0.3, threads: 4 })
  const [rmBenchmarkPrompt, setRmBenchmarkPrompt] = useState('Say hello in one short sentence.')
  const [rmLastBenchmarkResult, setRmLastBenchmarkResult] = useState(null)
  const [rmLastActionResult, setRmLastActionResult] = useState(null)

  useEffect(() => { load() }, [])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (initialTab && initialTab !== tab) selectTab(initialTab) }, [initialTab])

  // Mirrors ProductionReadinessPage.jsx's write-back effect verbatim.
  useEffect(() => {
    const pageName = window.location.hash.slice(1).split('?')[0]
    const params = new URLSearchParams()
    params.set('tab', tab)
    window.history.replaceState(null, '', `#${pageName}?${params.toString()}`)
  }, [tab])

  async function load() {
    try {
      const [statusData, versionData, runtimeHealthData] = await Promise.all([miniBrainStatus(), miniBrainVersion(), miniBrainRuntimeHealth()])
      setStatus(statusData)
      setVersion(versionData)
      setRuntimeHealth(runtimeHealthData)
    } catch (reason) { setError(reason.message) }
  }

  async function selectTab(value) {
    setTab(value)
    setError('')
    try {
      if (value === 'Settings') {
        const data = await miniBrainSettings()
        setSettings(data)
        setLogLevel(data.config?.log_level ?? 'info')
      }
      if (value === 'Logs') setLogs(await miniBrainLogs())
      if (value === 'Diagnostics') setDiagnostics(await miniBrainDiagnostics())
      if (value === 'Knowledge Core') await loadKnowledgeCore()
      if (value === 'Runtime') await loadRuntimeTab()
      if (value === 'Response Quality') setQDiagnostics(await qualityDiagnostics())
      if (value === 'Capability') setCapDiagnostics(await capabilityDiagnostics())
      if (value === 'Dataset Intelligence') setDiDiagnostics(await datasetIntelligenceDiagnostics())
      if (value === 'Learning Supervisor') await loadLearningSupervisor()
      if (value === 'Release Pipeline') await loadReleasePipeline()
      if (value === 'Continuous Learning') await loadContinuousLearning()
      if (value === 'Continuous Learning Center') await loadClc()
      if (value === 'Research Center') await loadRc()
      if (value === 'Dataset Evolution') await loadDe()
      if (value === 'Pipeline Coordinator') await loadPc()
      if (value === 'Language Intelligence') await loadLi()
      if (value === 'Vision Intelligence') await loadVi()
      if (value === 'Vision Model Center') await loadVm()
      if (value === 'Multimodal Dataset Generator') await loadMd()
      if (value === 'Vision RAG') await loadVr()
      if (value === 'Training Pipeline') await loadTp()
      if (value === 'Evaluation Center') await loadEc()
      if (value === 'Release Governance') await loadRg()
      if (value === 'External AI Gateway') await loadGa()
      if (value === 'Training Engine') await loadTe()
      if (value === 'Public Chat Runtime') await loadPcr()
      if (value === 'Plugin Governance') await loadPg()
      if (value === 'Plugin Runtime') await loadPr()
      if (value === 'Voice Runtime') await loadVo()
      if (value === 'Provider Settings') await loadPs()
      if (value === 'Assistant Intelligence') await loadLr()
      if (value === 'Local Setup') await loadLc()
      if (value === 'Runtime Manager') await loadRm()
    } catch (reason) { setError(reason.message) }
  }

  async function loadLearningSupervisor() {
    const [sessions, profiles] = await Promise.all([learningSupervisorSessions(), learningSupervisorProfiles()])
    setLsSessions(sessions.items)
    setLsProfiles(profiles.items)
  }

  async function selectLsSession(publicId) {
    setLsSelectedId(publicId)
    setLsMonitor(null)
    setError('')
    if (!publicId) { setLsSession(null); setLsEvents([]); return }
    try {
      const [session, events] = await Promise.all([learningSupervisorSession(publicId), learningSupervisorEvents(publicId)])
      setLsSession(session)
      setLsEvents(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshLsSession() {
    if (!lsSelectedId) return
    await selectLsSession(lsSelectedId)
    setLsSessions((await learningSupervisorSessions()).items)
  }

  async function runLsAction(action) {
    setLsBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshLsSession()
      setNotice('Learning Supervisor session updated.')
    } catch (reason) { setError(reason.message) } finally { setLsBusy(false) }
  }

  async function submitLsCreateSession(event) {
    event.preventDefault()
    await runLsAction(async () => {
      const session = await learningSupervisorCreateSession(lsCreateForm)
      setLsSessions((await learningSupervisorSessions()).items)
      await selectLsSession(session.public_id)
    })
  }

  const runLsValidateDataset = () => runLsAction(() => learningSupervisorValidateDataset(lsSelectedId))
  const runLsDecideDataset = (decision) => runLsAction(() => learningSupervisorDecideDataset(lsSelectedId, decision))
  const runLsFinalizeRag = () => runLsAction(() => learningSupervisorFinalizeRag(lsSelectedId))
  const runLsDecideRag = (decision) => runLsAction(() => learningSupervisorDecideRag(lsSelectedId, decision))
  const runLsAnalyzeTraining = () => runLsAction(() => learningSupervisorAnalyzeTraining(lsSelectedId))
  const runLsRecommendations = () => runLsAction(() => learningSupervisorRecommendations(lsSelectedId))
  const runLsAdminReview = (decision) => runLsAction(() => learningSupervisorAdminReview(lsSelectedId, decision))

  function submitLsRagEvaluation(event) {
    event.preventDefault()
    return runLsAction(() => learningSupervisorRunRag(lsSelectedId, lsRagForm))
  }

  function submitLsTrainingRequest(event) {
    event.preventDefault()
    const body = { ...lsTrainingForm }
    if (!body.hyperparameter_profile) delete body.hyperparameter_profile
    return runLsAction(() => learningSupervisorSubmitTraining(lsSelectedId, body))
  }

  async function runLsMonitorTraining() {
    setLsBusy(true); setError('')
    try { setLsMonitor(await learningSupervisorMonitorTraining(lsSelectedId)) }
    catch (reason) { setError(reason.message) } finally { setLsBusy(false) }
  }

  function submitLsBenchmark(event) {
    event.preventDefault()
    return runLsAction(() => learningSupervisorRunBenchmark(lsSelectedId, lsBenchmarkForm))
  }

  function submitLsCompareModels(event) {
    event.preventDefault()
    return runLsAction(() => learningSupervisorCompareModels(lsSelectedId, lsCompareForm))
  }

  function submitLsReleaseCandidate(event) {
    event.preventDefault()
    const body = { ...lsReleaseForm }
    if (!body.override_comment) delete body.override_comment
    return runLsAction(() => learningSupervisorReleaseCandidate(lsSelectedId, body))
  }

  async function loadReleasePipeline() {
    const [sessions, diag] = await Promise.all([releasePipelineSessions(), releasePipelineDiagnostics()])
    setRpSessions(sessions.items)
    setRpDiagnostics(diag)
  }

  async function selectRpSession(publicId) {
    setRpSelectedId(publicId)
    setRpRollbackEval(null)
    setError('')
    if (!publicId) { setRpSession(null); setRpEvents([]); return }
    try {
      const [session, events] = await Promise.all([releasePipelineSession(publicId), releasePipelineEvents(publicId)])
      setRpSession(session)
      setRpEvents(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshRpSession() {
    if (!rpSelectedId) return
    await selectRpSession(rpSelectedId)
    setRpSessions((await releasePipelineSessions()).items)
  }

  async function runRpAction(action) {
    setRpBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshRpSession()
      setNotice('Release Pipeline session updated.')
    } catch (reason) { setError(reason.message) } finally { setRpBusy(false) }
  }

  async function submitRpCreateSession(event) {
    event.preventDefault()
    await runRpAction(async () => {
      const body = {
        ...rpCreateForm,
        target_quantizations: rpCreateForm.target_quantizations.split(',').map((s) => s.trim()).filter(Boolean),
      }
      if (!body.dataset_version_public_id) delete body.dataset_version_public_id
      if (!body.model_evaluation_run_public_id) delete body.model_evaluation_run_public_id
      const session = await releasePipelineCreateSession(body)
      setRpSessions((await releasePipelineSessions()).items)
      await selectRpSession(session.public_id)
    })
  }

  const runRpValidateCheckpoint = () => runRpAction(() => releasePipelineValidateCheckpoint(rpSelectedId))
  const runRpConvert = () => runRpAction(() => releasePipelineConvert(rpSelectedId))
  const runRpQuantize = () => runRpAction(() => releasePipelineQuantize(rpSelectedId))
  const runRpVerify = () => runRpAction(() => releasePipelineVerify(rpSelectedId))
  const runRpPerformance = () => runRpAction(() => releasePipelinePerformance(rpSelectedId))
  const runRpAdminReview = (decision) => runRpAction(() => releasePipelineAdminReview(rpSelectedId, decision))

  function submitRpCreateVersion(event) {
    event.preventDefault()
    const body = { ...rpVersionForm }
    if (!body.prerelease_label) delete body.prerelease_label
    return runRpAction(() => releasePipelineCreateVersion(rpSelectedId, body))
  }

  function submitRpActivate(event) {
    event.preventDefault()
    return runRpAction(() => releasePipelineActivate(rpSelectedId, rpActivateLevel))
  }

  async function submitRpEvaluateRollback(event) {
    event.preventDefault()
    setRpBusy(true); setError('')
    try { setRpRollbackEval(await releasePipelineEvaluateRollback(rpSelectedId, rpRollbackEvalForm.target_version)) }
    catch (reason) { setError(reason.message) } finally { setRpBusy(false) }
  }

  function submitRpExecuteRollback(event) {
    event.preventDefault()
    return runRpAction(() => releasePipelineExecuteRollback(rpSelectedId, rpRollbackExecuteForm))
  }

  async function loadContinuousLearning() {
    const [sessions, diag] = await Promise.all([continuousLearningSessions(), continuousLearningDiagnostics()])
    setClSessions(sessions.items)
    setClDiagnostics(diag)
  }

  async function selectClSession(publicId) {
    setClSelectedId(publicId)
    setError('')
    if (!publicId) { setClSession(null); setClEvents([]); return }
    try {
      const [session, events] = await Promise.all([continuousLearningSession(publicId), continuousLearningEvents(publicId)])
      setClSession(session)
      setClEvents(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshClSession() {
    if (!clSelectedId) return
    await selectClSession(clSelectedId)
    setClSessions((await continuousLearningSessions()).items)
  }

  async function runClAction(action) {
    setClBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshClSession()
      setNotice('Continuous Learning session updated.')
    } catch (reason) { setError(reason.message) } finally { setClBusy(false) }
  }

  async function submitClCreateSession(event) {
    event.preventDefault()
    await runClAction(async () => {
      const session = await continuousLearningCreateSession(clCycleWindowDays)
      setClSessions((await continuousLearningSessions()).items)
      await selectClSession(session.public_id)
    })
  }

  const runClCollectFeedback = () => runClAction(() => continuousLearningCollectFeedback(clSelectedId))
  const runClAnalyzeFailures = () => runClAction(() => continuousLearningAnalyzeFailures(clSelectedId))
  const runClAnalyzeHallucinations = () => runClAction(() => continuousLearningAnalyzeHallucinations(clSelectedId))
  const runClAnalyzeKnowledgeGaps = () => runClAction(() => continuousLearningAnalyzeKnowledgeGaps(clSelectedId))
  const runClDetectWeakTopics = () => runClAction(() => continuousLearningDetectWeakTopics(clSelectedId))
  const runClAnalyzeDifficulty = () => runClAction(() => continuousLearningAnalyzeDifficulty(clSelectedId))
  const runClRecommendDatasets = () => runClAction(() => continuousLearningRecommendDatasets(clSelectedId))
  const runClRecommendTraining = () => runClAction(() => continuousLearningRecommendTraining(clSelectedId))
  const runClRankPriorities = () => runClAction(() => continuousLearningRankPriorities(clSelectedId))
  const runClGenerateReport = () => runClAction(() => continuousLearningGenerateReport(clSelectedId))
  const runClAdminReview = (decision) => runClAction(() => continuousLearningAdminReview(clSelectedId, decision))

  async function loadClc() {
    const [sessions, diag, memory] = await Promise.all([clcSessions(), clcDiagnostics(), clcListMemory()])
    setClcSessionsList(sessions.items)
    setClcDiag(diag)
    setClcMemoryItems(memory.items)
  }

  async function selectClcSession(publicId) {
    setClcSelectedId(publicId)
    setError('')
    if (!publicId) { setClcSessionData(null); setClcEventsList([]); return }
    try {
      const [session, events] = await Promise.all([clcSession(publicId), clcEvents(publicId)])
      setClcSessionData(session)
      setClcEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshClcSession() {
    if (!clcSelectedId) return
    await selectClcSession(clcSelectedId)
    setClcSessionsList((await clcSessions()).items)
  }

  async function runClcAction(action) {
    setClcBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshClcSession()
      setNotice('Continuous Learning Center session updated.')
    } catch (reason) { setError(reason.message) } finally { setClcBusy(false) }
  }

  async function submitClcCreateSession(event) {
    event.preventDefault()
    await runClcAction(async () => {
      const session = await clcCreateSession()
      setClcSessionsList((await clcSessions()).items)
      await selectClcSession(session.public_id)
    })
  }

  const runClcEvolveKnowledgeGaps = () => runClcAction(() => clcEvolveKnowledgeGaps(clcSelectedId))
  const runClcBuildLearningQueue = () => runClcAction(() => clcBuildLearningQueue(clcSelectedId))
  const runClcBuildRoadmap = () => runClcAction(() => clcBuildRoadmap(clcSelectedId))
  const runClcGenerateRecommendation = () => runClcAction(() => clcGenerateRecommendation(clcSelectedId))
  const runClcGenerateReport = () => runClcAction(() => clcGenerateReport(clcSelectedId))
  const runClcAdminReview = (decision) => runClcAction(() => clcAdminReview(clcSelectedId, decision))

  function submitClcBuildDraft(event) {
    event.preventDefault()
    return runClcAction(() => clcBuildDraft(clcSelectedId, clcDraftTopic || null))
  }

  function submitClcPrepareProviderRequest(event) {
    event.preventDefault()
    const providers = clcProviders.split(',').map((p) => p.trim()).filter(Boolean)
    return runClcAction(() => clcPrepareProviderRequest(clcSelectedId, providers))
  }

  function submitClcIngestProviderResults(event) {
    event.preventDefault()
    const outputs = clcProviderOutputs.filter((o) => o.output_text.trim())
    return runClcAction(() => clcIngestProviderResults(clcSelectedId, outputs))
  }

  function submitClcPlanDatasetEvolution(event) {
    event.preventDefault()
    return runClcAction(() => clcPlanDatasetEvolution(clcSelectedId, clcExistingDatasetId || null))
  }

  async function submitClcRecordMemory(event) {
    event.preventDefault()
    setClcBusy(true); setError(''); setNotice('')
    try {
      const body = { ...clcMemoryForm }
      if (!body.model_version_public_id) delete body.model_version_public_id
      if (!body.dataset_version_public_id) delete body.dataset_version_public_id
      await clcRecordMemory(body)
      setClcMemoryItems((await clcListMemory()).items)
      setNotice('Learning memory recorded.')
    } catch (reason) { setError(reason.message) } finally { setClcBusy(false) }
  }

  async function loadRc() {
    const [sessions, diag, memory, providers] = await Promise.all([
      rcSessions(), rcDiagnostics(), rcListMemory(), rcListProviders(),
    ])
    setRcSessionsList(sessions.items)
    setRcDiag(diag)
    setRcMemoryItems(memory.items)
    setRcProviders(providers.items)
  }

  async function selectRcSession(publicId) {
    setRcSelectedId(publicId)
    setRcReport(null)
    setError('')
    if (!publicId) { setRcSessionData(null); setRcEventsList([]); return }
    try {
      const [session, events] = await Promise.all([rcSession(publicId), rcEvents(publicId)])
      setRcSessionData(session)
      setRcEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshRcSession() {
    if (!rcSelectedId) return
    await selectRcSession(rcSelectedId)
    setRcSessionsList((await rcSessions()).items)
  }

  async function runRcAction(action) {
    setRcBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshRcSession()
      setNotice('Research Center session updated.')
    } catch (reason) { setError(reason.message) } finally { setRcBusy(false) }
  }

  async function submitRcCreateSession(event) {
    event.preventDefault()
    if (!rcNewTopic.trim()) return
    await runRcAction(async () => {
      const session = await rcCreateSession(rcNewTopic.trim())
      setRcNewTopic('')
      setRcSessionsList((await rcSessions()).items)
      await selectRcSession(session.public_id)
    })
  }

  function submitRcResearchRequest(event) {
    event.preventDefault()
    return runRcAction(() => rcPrepareResearchRequest(rcSelectedId, rcPlanningCenterId || null, null))
  }

  function submitRcSelectMode(event) {
    event.preventDefault()
    const keys = rcMode === 'multi_provider' ? rcProviderKeys.split(',').map((p) => p.trim()).filter(Boolean) : []
    return runRcAction(() => rcSelectMode(rcSelectedId, rcMode, keys))
  }

  function submitRcBuildLocalDraft(event) {
    event.preventDefault()
    return runRcAction(() => rcBuildLocalDraft(rcSelectedId, rcExistingDatasetId || null))
  }

  const runRcPrepareProviderRequestPackage = () => runRcAction(() => rcPrepareProviderRequestPackage(rcSelectedId))

  function submitRcIngestProviderResults(event) {
    event.preventDefault()
    const outputs = rcProviderOutputs.filter((o) => o.output_text.trim())
    return runRcAction(() => rcIngestProviderResults(rcSelectedId, outputs))
  }

  const runRcBuildDatasetDraft = () => runRcAction(() => rcBuildDatasetDraft(rcSelectedId))
  const runRcAdminReviewDraft = (decision) => runRcAction(() => rcAdminReviewDraft(rcSelectedId, decision))

  function submitRcRunRagEvaluation(event) {
    event.preventDefault()
    return runRcAction(() => rcRunRagEvaluation(rcSelectedId, rcRagForm))
  }

  const runRcFinalizeRagEvaluation = () => runRcAction(() => rcFinalizeRagEvaluation(rcSelectedId))
  const runRcAdminReviewRag = (decision) => runRcAction(() => rcAdminReviewRag(rcSelectedId, decision))
  const runRcCheckTrainingGate = () => runRcAction(() => rcCheckTrainingGate(rcSelectedId))

  function submitRcAnalyzeTrainingReport(event) {
    event.preventDefault()
    if (!rcTrainingReportMb06Id.trim()) return
    return runRcAction(() => rcAnalyzeTrainingReport(rcSelectedId, rcTrainingReportMb06Id.trim()))
  }

  async function runRcGenerateReport() {
    setRcBusy(true); setError('')
    try {
      setRcReport(await rcGenerateReport(rcSelectedId))
    } catch (reason) { setError(reason.message) } finally { setRcBusy(false) }
  }

  async function submitRcRecordMemory(event) {
    event.preventDefault()
    setRcBusy(true); setError(''); setNotice('')
    try {
      await rcRecordMemory(rcSelectedId, rcMemoryNotes)
      setRcMemoryNotes('')
      setRcMemoryItems((await rcListMemory()).items)
      setNotice('Research memory recorded.')
    } catch (reason) { setError(reason.message) } finally { setRcBusy(false) }
  }

  async function submitRcAddProvider(event) {
    event.preventDefault()
    setRcBusy(true); setError(''); setNotice('')
    try {
      await rcAddProvider(rcNewProviderForm)
      setRcNewProviderForm({ provider_key: '', display_name: '', requires_external_call: true, description: '' })
      setRcProviders((await rcListProviders()).items)
      setNotice('Provider registered.')
    } catch (reason) { setError(reason.message) } finally { setRcBusy(false) }
  }

  async function toggleRcProviderStatus(providerKey, currentStatus) {
    setRcBusy(true); setError('')
    try {
      await rcSetProviderStatus(providerKey, currentStatus === 'active' ? 'inactive' : 'active')
      setRcProviders((await rcListProviders()).items)
    } catch (reason) { setError(reason.message) } finally { setRcBusy(false) }
  }

  async function loadDe() {
    const [sessions, diag] = await Promise.all([deSessions(), deDiagnostics()])
    setDeSessionsList(sessions.items)
    setDeDiag(diag)
  }

  async function selectDeSession(publicId) {
    setDeSelectedId(publicId)
    setError('')
    if (!publicId) { setDeSessionData(null); setDeEventsList([]); return }
    try {
      const [session, events] = await Promise.all([deSession(publicId), deEvents(publicId)])
      setDeSessionData(session)
      setDeEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshDeSession() {
    if (!deSelectedId) return
    await selectDeSession(deSelectedId)
    setDeSessionsList((await deSessions()).items)
  }

  async function runDeAction(action) {
    setDeBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshDeSession()
      setNotice('Dataset Evolution session updated.')
    } catch (reason) { setError(reason.message) } finally { setDeBusy(false) }
  }

  async function submitDeCreateSession(event) {
    event.preventDefault()
    if (!deNewSourceId.trim()) return
    await runDeAction(async () => {
      const session = await deCreateSession(deNewSourceId.trim())
      setDeNewSourceId('')
      setDeSessionsList((await deSessions()).items)
      await selectDeSession(session.public_id)
    })
  }

  const runDeKnowledgeEvolution = () => runDeAction(() => deRunKnowledgeEvolution(deSelectedId))
  const runDeDatasetEvolution = () => runDeAction(() => deRunDatasetEvolution(deSelectedId))
  const runDeSimulation = () => runDeAction(() => deRunSimulation(deSelectedId))
  const runDeGenerateRecommendation = () => runDeAction(() => deGenerateRecommendation(deSelectedId))
  const runDeGenerateReport = () => runDeAction(() => deGenerateReport(deSelectedId))
  const runDeAdminReview = (decision) => runDeAction(() => deAdminReview(deSelectedId, decision))
  const runDeAdminReviewRag = (decision) => runDeAction(() => deAdminReviewRag(deSelectedId, decision))
  const runDeFinalizeRagEvaluation = () => runDeAction(() => deFinalizeRagEvaluation(deSelectedId))

  function submitDeRunRagEvaluation(event) {
    event.preventDefault()
    return runDeAction(() => deRunRagEvaluation(deSelectedId, deRagForm))
  }

  async function loadPc() {
    const [sessions, diag] = await Promise.all([pcSessions(), pcDiagnostics()])
    setPcSessionsList(sessions.items)
    setPcDiag(diag)
  }

  async function selectPcSession(publicId) {
    setPcSelectedId(publicId)
    setError('')
    if (!publicId) { setPcSessionData(null); setPcEventsList([]); return }
    try {
      const [session, events] = await Promise.all([pcSession(publicId), pcEvents(publicId)])
      setPcSessionData(session)
      setPcEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshPcSession() {
    if (!pcSelectedId) return
    await selectPcSession(pcSelectedId)
    setPcSessionsList((await pcSessions()).items)
  }

  async function runPcAction(action) {
    setPcBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshPcSession()
      setNotice('Pipeline Coordinator session updated.')
    } catch (reason) { setError(reason.message) } finally { setPcBusy(false) }
  }

  async function submitPcCreateSession(event) {
    event.preventDefault()
    if (!pcNewTopic.trim()) return
    await runPcAction(async () => {
      const session = await pcCreateSession(pcNewTopic.trim())
      setPcNewTopic('')
      setPcSessionsList((await pcSessions()).items)
      await selectPcSession(session.public_id)
    })
  }

  function submitPcLinkResearch(event) {
    event.preventDefault()
    return runPcAction(() => pcLinkResearch(pcSelectedId, pcMb09Id))
  }
  function submitPcLinkResearchCenter(event) {
    event.preventDefault()
    return runPcAction(() => pcLinkResearchCenter(pcSelectedId, pcMb10Id))
  }
  function submitPcLinkDatasetEvolution(event) {
    event.preventDefault()
    return runPcAction(() => pcLinkDatasetEvolution(pcSelectedId, pcMb11Id))
  }
  function submitPcLinkTraining(event) {
    event.preventDefault()
    return runPcAction(() => pcLinkTraining(pcSelectedId, pcMb06Id))
  }
  const runPcRefreshResearchCenter = () => runPcAction(() => pcRefreshResearchCenter(pcSelectedId))
  const runPcRefreshTraining = () => runPcAction(() => pcRefreshTraining(pcSelectedId))
  const runPcRunRagFirstEnforcement = () => runPcAction(() => pcRunRagFirstEnforcement(pcSelectedId))
  const runPcGenerateTrainingReadiness = () => runPcAction(() => pcGenerateTrainingReadiness(pcSelectedId))
  const runPcGenerateTimeline = () => runPcAction(() => pcGenerateTimeline(pcSelectedId))
  const runPcPredictImprovement = () => runPcAction(() => pcPredictImprovement(pcSelectedId))
  const runPcGenerateRecommendation = () => runPcAction(() => pcGenerateRecommendation(pcSelectedId))
  const runPcGenerateReport = () => runPcAction(() => pcGenerateReport(pcSelectedId))
  const runPcAdminDecide = (decision) => runPcAction(() => pcAdminDecide(pcSelectedId, decision))

  async function loadLi() {
    const [sessions, diag] = await Promise.all([liSessions(), liDiagnostics()])
    setLiSessionsList(sessions.items)
    setLiDiag(diag)
  }

  async function selectLiSession(publicId) {
    setLiSelectedId(publicId)
    setError('')
    if (!publicId) { setLiSessionData(null); setLiEventsList([]); return }
    try {
      const [session, events] = await Promise.all([liSession(publicId), liEvents(publicId)])
      setLiSessionData(session)
      setLiEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshLiSession() {
    if (!liSelectedId) return
    await selectLiSession(liSelectedId)
    setLiSessionsList((await liSessions()).items)
  }

  async function runLiAction(action) {
    setLiBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshLiSession()
      setNotice('Language Intelligence session updated.')
    } catch (reason) { setError(reason.message) } finally { setLiBusy(false) }
  }

  async function submitLiCreateSession(event) {
    event.preventDefault()
    if (!liNewSourceId.trim()) return
    await runLiAction(async () => {
      const session = await liCreateSession(liNewSourceId.trim())
      setLiNewSourceId('')
      setLiSessionsList((await liSessions()).items)
      await selectLiSession(session.public_id)
    })
  }

  const runLiLanguageScan = () => runLiAction(() => liRunLanguageScan(liSelectedId))
  const runLiUnicodeValidation = () => runLiAction(() => liRunUnicodeValidation(liSelectedId))
  const runLiSpellAnalysis = () => runLiAction(() => liRunSpellAnalysis(liSelectedId))
  const runLiGrammarAnalysis = () => runLiAction(() => liRunGrammarAnalysis(liSelectedId))
  const runLiOcrAnalysis = () => runLiAction(() => liRunOcrAnalysis(liSelectedId))
  const runLiTanglishAnalysis = () => runLiAction(() => liRunTanglishAnalysis(liSelectedId))
  const runLiTranslationAnalysis = () => runLiAction(() => liRunTranslationAnalysis(liSelectedId, []))
  const runLiDatasetDraft = () => runLiAction(() => liRunDatasetDraft(liSelectedId))
  const runLiQualityScore = () => runLiAction(() => liRunQualityScore(liSelectedId))
  const runLiGenerateReport = () => runLiAction(() => liGenerateReport(liSelectedId))
  const runLiAdminReview = (decision) => runLiAction(() => liAdminReview(liSelectedId, decision))

  async function loadVi() {
    const [sessions, diag] = await Promise.all([viSessions(), viDiagnostics()])
    setViSessionsList(sessions.items)
    setViDiag(diag)
  }

  async function selectViSession(publicId) {
    setViSelectedId(publicId)
    setError('')
    if (!publicId) { setViSessionData(null); setViEventsList([]); setViImagesList([]); setViObjectsList([]); return }
    try {
      const [session, events, images, objects] = await Promise.all([
        viSession(publicId), viEvents(publicId), viImages(publicId), viObjects(publicId, 'active'),
      ])
      setViSessionData(session)
      setViEventsList(events.items)
      setViImagesList(images.items)
      setViObjectsList(objects.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshViSession() {
    if (!viSelectedId) return
    await selectViSession(viSelectedId)
    setViSessionsList((await viSessions()).items)
  }

  async function runViAction(action) {
    setViBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshViSession()
      setNotice('Vision Intelligence session updated.')
    } catch (reason) { setError(reason.message) } finally { setViBusy(false) }
  }

  async function submitViCreateSession(event) {
    event.preventDefault()
    if (!viNewDocumentSourceId.trim()) return
    await runViAction(async () => {
      const session = await viCreateSession(viNewDocumentSourceId.trim(), viNewDatasetSourceId.trim() || null)
      setViNewDocumentSourceId('')
      setViNewDatasetSourceId('')
      setViSessionsList((await viSessions()).items)
      await selectViSession(session.public_id)
    })
  }

  const runViImageExtraction = () => runViAction(() => viRunImageExtraction(viSelectedId))
  const runViImageQuality = () => runViAction(() => viRunImageQuality(viSelectedId))
  const runViVisionUnderstanding = () => runViAction(() => viRunVisionUnderstanding(viSelectedId))
  const runViOcrCrossValidation = () => runViAction(() => viRunOcrCrossValidation(viSelectedId, viDatasetTextInput || null, null))
  const runViCaption = () => runViAction(() => viRunCaption(viSelectedId, viAdminCaptionInput || null))
  const runViBoundingBoxPlan = () => runViAction(() => viRunBoundingBoxPlan(viSelectedId))
  const runViKnowledgeGraph = () => runViAction(() => viRunKnowledgeGraph(viSelectedId))
  const runViQaGeneration = () => runViAction(() => viRunQaGeneration(viSelectedId))
  const runViDatasetDraft = () => runViAction(() => viRunDatasetDraft(viSelectedId))
  const runViQualityScore = () => runViAction(() => viRunQualityScore(viSelectedId))
  const runViGenerateReport = () => runViAction(() => viGenerateReport(viSelectedId))
  const runViAdminReview = (decision) => runViAction(() => viAdminReview(viSelectedId, decision))
  const runViFinishAnnotation = () => runViAction(() => viFinishAnnotation(viSelectedId))

  function submitViAnnotate(event) {
    event.preventDefault()
    const payload = {}
    if (viAnnotateAction === 'rename' || viAnnotateAction === 'correct_label' || viAnnotateAction === 'add') {
      payload.label = viAnnotateLabel
    }
    if (viAnnotateAction === 'add') {
      payload.image_public_id = viAnnotateImageId
    }
    if (viAnnotateAction === 'correct_caption') {
      payload.caption = viAnnotateCaption
    }
    if (viAnnotateAction === 'redraw_box' || viAnnotateAction === 'add') {
      payload.bounding_box = {
        x: Number(viAnnotateBoxX), y: Number(viAnnotateBoxY),
        width: Number(viAnnotateBoxW), height: Number(viAnnotateBoxH),
      }
    }
    const objectId = viAnnotateAction === 'add' ? null : viAnnotateObjectId
    runViAction(() => viAnnotate(viSelectedId, viAnnotateAction, objectId, payload))
  }

  async function loadVm() {
    const [sessions, diag, providers, memory] = await Promise.all([
      vmSessions(), vmDiagnostics(), vmProviders(), vmLearningMemory(),
    ])
    setVmSessionsList(sessions.items)
    setVmDiag(diag)
    setVmProvidersList(providers.items)
    setVmLearningMemoryList(memory.items)
  }

  async function selectVmSession(publicId) {
    setVmSelectedId(publicId)
    setError('')
    if (!publicId) {
      setVmSessionData(null); setVmEventsList([]); setVmPredictionsList([]); setVmCorrectionsList([])
      return
    }
    try {
      const [session, events, predictions, corrections] = await Promise.all([
        vmSession(publicId), vmEvents(publicId), vmPredictions(publicId), vmCorrections(publicId),
      ])
      setVmSessionData(session)
      setVmEventsList(events.items)
      setVmPredictionsList(predictions.items)
      setVmCorrectionsList(corrections.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshVmSession() {
    if (!vmSelectedId) return
    await selectVmSession(vmSelectedId)
    setVmSessionsList((await vmSessions()).items)
  }

  async function runVmAction(action) {
    setVmBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshVmSession()
      setNotice('Vision Model Center session updated.')
    } catch (reason) { setError(reason.message) } finally { setVmBusy(false) }
  }

  async function submitVmCreateSession(event) {
    event.preventDefault()
    if (!vmNewVisionSessionId.trim()) return
    await runVmAction(async () => {
      const session = await vmCreateSession(vmNewVisionSessionId.trim(), vmNewProviderKey)
      setVmNewVisionSessionId('')
      setVmSessionsList((await vmSessions()).items)
      await selectVmSession(session.public_id)
    })
  }

  async function toggleVmProviderStatus(providerKey, currentStatus) {
    setVmBusy(true); setError('')
    try {
      await vmSetProviderStatus(providerKey, currentStatus === 'active' ? 'inactive' : 'active')
      setVmProvidersList((await vmProviders()).items)
    } catch (reason) { setError(reason.message) } finally { setVmBusy(false) }
  }

  const runVmImageLoad = () => runVmAction(() => vmRunImageLoad(vmSelectedId))
  const runVmProviderSelection = () => runVmAction(() => vmRunProviderSelection(vmSelectedId, vmModelPath, vmMmprojPath))
  const runVmObjectDetection = () => runVmAction(() => vmRunObjectDetection(vmSelectedId))
  const runVmSceneDetection = () => runVmAction(() => vmRunSceneDetection(vmSelectedId))
  const runVmCaption = () => runVmAction(() => vmRunCaption(vmSelectedId))
  const runVmRelationshipDetection = () => runVmAction(() => vmRunRelationshipDetection(vmSelectedId))
  const runVmOcrCrossValidation = () => runVmAction(() => vmRunOcrCrossValidation(vmSelectedId, vmDatasetTextInput))
  const runVmQualityScore = () => runVmAction(() => vmRunQualityScore(vmSelectedId))
  const runVmFinishReview = () => runVmAction(() => vmFinishReview(vmSelectedId))
  const runVmCorrectionMemory = () => runVmAction(() => vmRunCorrectionMemory(vmSelectedId))
  const runVmKnowledgeGraph = () => runVmAction(() => vmRunKnowledgeGraph(vmSelectedId))
  const runVmDatasetDraft = () => runVmAction(() => vmRunDatasetDraft(vmSelectedId))
  const runVmGenerateReport = () => runVmAction(() => vmGenerateReport(vmSelectedId))
  const runVmAdminReview = (decision) => runVmAction(() => vmAdminReview(vmSelectedId, decision))

  function submitVmReview(event) {
    event.preventDefault()
    const payload = {}
    if (vmReviewAction === 'rename' || vmReviewAction === 'add') payload.label = vmReviewLabel
    if (vmReviewAction === 'add') payload.image_public_id = vmReviewImageId
    if (['move_box', 'resize_box', 'rotate_box', 'add'].includes(vmReviewAction)) {
      payload.bounding_box = {
        x: Number(vmReviewBoxX), y: Number(vmReviewBoxY), width: Number(vmReviewBoxW), height: Number(vmReviewBoxH),
      }
    }
    const predictionId = vmReviewAction === 'add' ? null : vmReviewPredictionId
    runVmAction(() => vmReviewPrediction(vmSelectedId, vmReviewAction, predictionId, payload))
  }

  async function loadMd() {
    const [sessions, diag, memory] = await Promise.all([mdSessions(), mdDiagnostics(), mdDatasetMemory()])
    setMdSessionsList(sessions.items)
    setMdDiag(diag)
    setMdMemoryList(memory.items)
  }

  async function selectMdSession(publicId) {
    setMdSelectedId(publicId)
    setError('')
    setMdExportResult(null)
    if (!publicId) { setMdSessionData(null); setMdEventsList([]); setMdRecordsList([]); return }
    try {
      const [session, events, records] = await Promise.all([mdSession(publicId), mdEvents(publicId), mdRecords(publicId)])
      setMdSessionData(session)
      setMdEventsList(events.items)
      setMdRecordsList(records.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshMdSession() {
    if (!mdSelectedId) return
    await selectMdSession(mdSelectedId)
    setMdSessionsList((await mdSessions()).items)
  }

  async function runMdAction(action) {
    setMdBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshMdSession()
      setNotice('Multimodal Dataset Generator session updated.')
    } catch (reason) { setError(reason.message) } finally { setMdBusy(false) }
  }

  async function submitMdCreateSession(event) {
    event.preventDefault()
    if (!mdNewDocumentId.trim()) return
    await runMdAction(async () => {
      const session = await mdCreateSession(mdNewDocumentId.trim(), {
        visionSessionPublicId: mdNewVisionSessionId.trim() || null,
        languageSessionPublicId: mdNewLanguageSessionId.trim() || null,
        visionModelSessionPublicId: mdNewVisionModelSessionId.trim() || null,
      })
      setMdNewDocumentId(''); setMdNewVisionSessionId(''); setMdNewLanguageSessionId(''); setMdNewVisionModelSessionId('')
      setMdSessionsList((await mdSessions()).items)
      await selectMdSession(session.public_id)
    })
  }

  const runMdCollectSources = () => runMdAction(() => mdRunCollectSources(mdSelectedId))
  const runMdCollectText = () => runMdAction(() => mdRunCollectText(mdSelectedId))
  const runMdCollectImages = () => runMdAction(() => mdRunCollectImages(mdSelectedId))
  const runMdMergeMetadata = () => runMdAction(() => mdRunMergeMetadata(mdSelectedId))
  const runMdConversationBuilder = () => runMdAction(() => mdRunConversationBuilder(mdSelectedId))
  const runMdInstructionBuilder = () => runMdAction(() => mdRunInstructionBuilder(mdSelectedId))
  const runMdDatasetDraft = () => runMdAction(() => mdRunDatasetDraft(mdSelectedId))
  const runMdQualityAnalysis = () => runMdAction(() => mdRunQualityAnalysis(mdSelectedId))
  const runMdDuplicateDetection = () => runMdAction(() => mdRunDuplicateDetection(mdSelectedId))
  const runMdGenerateReport = () => runMdAction(() => mdGenerateReport(mdSelectedId))
  const runMdAdminReview = (decision) => runMdAction(() => mdAdminReview(mdSelectedId, decision))
  const runMdDeleteDraft = () => runMdAction(() => mdDeleteDraft(mdSelectedId))

  async function runMdExportDraft() {
    setMdBusy(true); setError('')
    try {
      const result = await mdExportDraft(mdSelectedId, mdExportFormat)
      setMdExportResult(result)
    } catch (reason) { setError(reason.message) } finally { setMdBusy(false) }
  }

  function submitMdSplit(event) {
    event.preventDefault()
    const ids = mdSplitRecordIds.split(',').map((s) => s.trim()).filter(Boolean)
    if (!ids.length) return
    runMdAction(() => mdSplitDataset(mdSelectedId, ids))
  }

  async function submitMdMerge(event) {
    event.preventDefault()
    const ids = mdMergeSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    if (ids.length < 2) return
    setMdBusy(true); setError('')
    try {
      const merged = await mdMergeDatasets(ids)
      setMdMergeSessionIds('')
      setMdSessionsList((await mdSessions()).items)
      await selectMdSession(merged.public_id)
      setNotice('Datasets merged into a new session.')
    } catch (reason) { setError(reason.message) } finally { setMdBusy(false) }
  }

  async function loadVr() {
    const [sessions, diag, memory] = await Promise.all([vrSessions(), vrDiagnostics(), vrRagMemory()])
    setVrSessionsList(sessions.items)
    setVrDiag(diag)
    setVrMemoryList(memory.items)
  }

  async function selectVrSession(publicId) {
    setVrSelectedId(publicId)
    setError('')
    if (!publicId) { setVrSessionData(null); setVrEventsList([]); setVrEvidenceList([]); return }
    try {
      const [session, events, evidence] = await Promise.all([vrSession(publicId), vrEvents(publicId), vrEvidence(publicId)])
      setVrSessionData(session)
      setVrEventsList(events.items)
      setVrEvidenceList(evidence.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshVrSession() {
    if (!vrSelectedId) return
    await selectVrSession(vrSelectedId)
    setVrSessionsList((await vrSessions()).items)
  }

  async function runVrAction(action) {
    setVrBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshVrSession()
      setNotice('Vision RAG session updated.')
    } catch (reason) { setError(reason.message) } finally { setVrBusy(false) }
  }

  async function submitVrCreateSession(event) {
    event.preventDefault()
    if (!vrNewDatasetSessionId.trim() || !vrNewQuery.trim()) return
    await runVrAction(async () => {
      const session = await vrCreateSession(vrNewDatasetSessionId.trim(), vrNewQuery.trim())
      setVrNewDatasetSessionId(''); setVrNewQuery('')
      setVrSessionsList((await vrSessions()).items)
      await selectVrSession(session.public_id)
    })
  }

  const runVrTextRetrieval = () => runVrAction(() => vrRunTextRetrieval(vrSelectedId))
  const runVrOcrRetrieval = () => runVrAction(() => vrRunOcrRetrieval(vrSelectedId))
  const runVrImageRetrieval = () => runVrAction(() => vrRunImageRetrieval(vrSelectedId))
  const runVrObjectRetrieval = () => runVrAction(() => vrRunObjectRetrieval(vrSelectedId))
  const runVrKnowledgeGraphRetrieval = () => runVrAction(() => vrRunKnowledgeGraphRetrieval(vrSelectedId))
  const runVrEvidenceFusion = () => runVrAction(() => vrRunEvidenceFusion(vrSelectedId))
  const runVrAnswer = () => runVrAction(() => vrRunAnswer(vrSelectedId))
  const runVrQuality = () => runVrAction(() => vrRunQuality(vrSelectedId))
  const runVrHallucinationCheck = () => runVrAction(() => vrRunHallucinationCheck(vrSelectedId))
  const runVrGenerateReport = () => runVrAction(() => vrGenerateReport(vrSelectedId))
  const runVrAdminReview = (decision) => runVrAction(() => vrAdminReview(vrSelectedId, decision))

  function submitVrCorrect(event) {
    event.preventDefault()
    const payload = {}
    if (vrCorrectAction === 'correct_answer') payload.answer = vrCorrectAnswer
    if (vrCorrectAction === 'correct_evidence') { payload.evidence_public_id = vrCorrectEvidenceId; payload.content_snippet = vrCorrectSnippet }
    if (vrCorrectAction === 'add_evidence') { payload.content_snippet = vrCorrectSnippet; payload.evidence_type = vrAddEvidenceType }
    runVrAction(() => vrCorrect(vrSelectedId, vrCorrectAction, payload))
  }

  async function loadTp() {
    const [sessions, diag, memory, ragMemory] = await Promise.all([tpSessions(), tpDiagnostics(), tpMemory(), tpRagMemory()])
    setTpSessionsList(sessions.items)
    setTpDiag(diag)
    setTpMemoryList(memory.items)
    setTpAvailableRagMemory(ragMemory.items)
  }

  async function selectTpSession(publicId) {
    setTpSelectedId(publicId)
    setError('')
    if (!publicId) { setTpSessionData(null); setTpEventsList([]); setTpPackagesList([]); return }
    try {
      const [session, events, packages] = await Promise.all([tpSession(publicId), tpEvents(publicId), tpPackages(publicId)])
      setTpSessionData(session)
      setTpEventsList(events.items)
      setTpPackagesList(packages.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshTpSession() {
    if (!tpSelectedId) return
    await selectTpSession(tpSelectedId)
    setTpSessionsList((await tpSessions()).items)
  }

  async function runTpAction(action) {
    setTpBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshTpSession()
      setNotice('Training pipeline session updated.')
    } catch (reason) { setError(reason.message) } finally { setTpBusy(false) }
  }

  async function submitTpCreateSession(event) {
    event.preventDefault()
    if (!tpNewTopic.trim()) return
    await runTpAction(async () => {
      const session = await tpCreateSession(tpNewTopic.trim())
      setTpNewTopic('')
      setTpSessionsList((await tpSessions()).items)
      await selectTpSession(session.public_id)
    })
  }

  function submitTpCollectDatasets(event) {
    event.preventDefault()
    const ids = tpDatasetSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    if (!ids.length) return
    runTpAction(() => tpRunCollectDatasets(tpSelectedId, ids))
  }

  function submitTpCollectRagMemory(event) {
    event.preventDefault()
    const ids = tpRagSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    runTpAction(() => tpRunCollectRagMemory(tpSelectedId, ids))
  }

  const runTpAnalyzeLanguage = () => runTpAction(() => tpRunAnalyzeLanguage(tpSelectedId))
  const runTpAnalyzeVision = () => runTpAction(() => tpRunAnalyzeVision(tpSelectedId))
  const runTpAnalyzeTokenizer = () => runTpAction(() => tpRunAnalyzeTokenizer(tpSelectedId))

  function submitTpPlanSplits(event) {
    event.preventDefault()
    const seed = tpSplitSeed.trim() ? Number(tpSplitSeed.trim()) : undefined
    runTpAction(() => tpRunPlanSplits(tpSelectedId, seed))
  }

  const runTpPlanCurriculum = () => runTpAction(() => tpRunPlanCurriculum(tpSelectedId))
  const runTpEstimateHardware = () => runTpAction(() => tpRunEstimateHardware(tpSelectedId))
  const runTpBuildPackage = () => runTpAction(() => tpRunBuildPackage(tpSelectedId))
  const runTpGenerateReport = () => runTpAction(() => tpGenerateReport(tpSelectedId))
  const runTpAdminReview = (decision) => runTpAction(() => tpAdminReview(tpSelectedId, decision))

  async function loadEc() {
    const [sessions, diag, memory] = await Promise.all([ecSessions(), ecDiagnostics(), ecMemory()])
    setEcSessionsList(sessions.items)
    setEcDiag(diag)
    setEcMemoryList(memory.items)
  }

  async function selectEcSession(publicId) {
    setEcSelectedId(publicId)
    setError('')
    if (!publicId) { setEcSessionData(null); setEcEventsList([]); setEcExportsList([]); return }
    try {
      const [session, events, exportsResult] = await Promise.all([ecSession(publicId), ecEvents(publicId), ecExports(publicId)])
      setEcSessionData(session)
      setEcEventsList(events.items)
      setEcExportsList(exportsResult.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshEcSession() {
    if (!ecSelectedId) return
    await selectEcSession(ecSelectedId)
    setEcSessionsList((await ecSessions()).items)
  }

  async function runEcAction(action) {
    setEcBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshEcSession()
      setNotice('Evaluation session updated.')
    } catch (reason) { setError(reason.message) } finally { setEcBusy(false) }
  }

  async function submitEcCreateSession(event) {
    event.preventDefault()
    if (!ecNewTopic.trim()) return
    await runEcAction(async () => {
      const session = await ecCreateSession(ecNewTopic.trim())
      setEcNewTopic('')
      setEcSessionsList((await ecSessions()).items)
      await selectEcSession(session.public_id)
    })
  }

  function submitEcCollectDatasets(event) {
    event.preventDefault()
    const ids = ecDatasetSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    if (!ids.length) return
    runEcAction(() => ecRunCollectDatasets(ecSelectedId, ids))
  }

  function submitEcCollectRagSessions(event) {
    event.preventDefault()
    const ids = ecRagSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    runEcAction(() => ecRunCollectRagSessions(ecSelectedId, ids))
  }

  function submitEcCollectTrainingPackages(event) {
    event.preventDefault()
    const ids = ecPackageSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    runEcAction(() => ecRunCollectTrainingPackages(ecSelectedId, ids))
  }

  const runEcLanguageBenchmarks = () => runEcAction(() => ecRunLanguageBenchmarks(ecSelectedId))
  const runEcOcrBenchmarks = () => runEcAction(() => ecRunOcrBenchmarks(ecSelectedId))
  const runEcGroundingRetrievalBenchmarks = () => runEcAction(() => ecRunGroundingRetrievalBenchmarks(ecSelectedId))
  const runEcMultimodalBenchmarks = () => runEcAction(() => ecRunMultimodalBenchmarks(ecSelectedId))
  const runEcPackageBenchmarks = () => runEcAction(() => ecRunPackageBenchmarks(ecSelectedId))

  function submitEcRegression(event) {
    event.preventDefault()
    runEcAction(() => ecRunRegression(ecSelectedId, ecBaselineSessionId.trim() || undefined))
  }

  const runEcGenerateReport = () => runEcAction(() => ecGenerateReport(ecSelectedId))
  const runEcAdminReview = (decision) => runEcAction(() => ecAdminReview(ecSelectedId, decision))

  async function loadRg() {
    const [sessions, diag, memory] = await Promise.all([rgSessions(), rgDiagnostics(), rgMemory()])
    setRgSessionsList(sessions.items)
    setRgDiag(diag)
    setRgMemoryList(memory.items)
  }

  async function selectRgSession(publicId) {
    setRgSelectedId(publicId)
    setError('')
    if (!publicId) { setRgSessionData(null); setRgEventsList([]); setRgArtifactsList([]); return }
    try {
      const [session, events, artifacts] = await Promise.all([rgSession(publicId), rgEvents(publicId), rgArtifacts(publicId)])
      setRgSessionData(session)
      setRgEventsList(events.items)
      setRgArtifactsList(artifacts.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshRgSession() {
    if (!rgSelectedId) return
    await selectRgSession(rgSelectedId)
    setRgSessionsList((await rgSessions()).items)
  }

  async function runRgAction(action) {
    setRgBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshRgSession()
      setNotice('Release governance session updated.')
    } catch (reason) { setError(reason.message) } finally { setRgBusy(false) }
  }

  async function submitRgCreateSession(event) {
    event.preventDefault()
    if (!rgNewTopic.trim()) return
    await runRgAction(async () => {
      const session = await rgCreateSession(rgNewTopic.trim())
      setRgNewTopic('')
      setRgSessionsList((await rgSessions()).items)
      await selectRgSession(session.public_id)
    })
  }

  function submitRgCollectDatasets(event) {
    event.preventDefault()
    const ids = rgDatasetSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    if (!ids.length) return
    runRgAction(() => rgRunCollectDatasets(rgSelectedId, ids))
  }

  function submitRgCollectRag(event) {
    event.preventDefault()
    const ids = rgRagSessionIds.split(',').map((s) => s.trim()).filter(Boolean)
    runRgAction(() => rgRunCollectRag(rgSelectedId, ids))
  }

  function submitRgCollectPackage(event) {
    event.preventDefault()
    if (!rgPackageSessionId.trim()) return
    runRgAction(() => rgRunCollectPackage(rgSelectedId, rgPackageSessionId.trim()))
  }

  function submitRgCollectEvaluation(event) {
    event.preventDefault()
    if (!rgEvaluationSessionId.trim()) return
    runRgAction(() => rgRunCollectEvaluation(rgSelectedId, rgEvaluationSessionId.trim()))
  }

  const runRgSafety = () => runRgAction(() => rgRunSafety(rgSelectedId))
  const runRgCompliance = () => runRgAction(() => rgRunCompliance(rgSelectedId))
  const runRgBenchmarks = () => runRgAction(() => rgRunBenchmarks(rgSelectedId))
  const runRgBuildRiskRollback = () => runRgAction(() => rgBuildRiskRollback(rgSelectedId))
  const runRgBuildPackage = () => runRgAction(() => rgBuildPackage(rgSelectedId))
  const runRgGenerateReport = () => runRgAction(() => rgGenerateReport(rgSelectedId))
  const runRgAdminReview = (decision) => runRgAction(() => rgAdminReview(rgSelectedId, decision))

  async function loadGa() {
    const [sessions, diag, memory] = await Promise.all([gaSessions(), gaDiagnostics(), gaMemory()])
    setGaSessionsList(sessions.items)
    setGaDiag(diag)
    setGaMemoryList(memory.items)
  }

  async function selectGaSession(publicId) {
    setGaSelectedId(publicId)
    setError('')
    if (!publicId) { setGaSessionData(null); setGaEventsList([]); setGaProviderRunsList([]); return }
    try {
      const [session, events, runs] = await Promise.all([gaSession(publicId), gaEvents(publicId), gaProviderRuns(publicId)])
      setGaSessionData(session)
      setGaEventsList(events.items)
      setGaProviderRunsList(runs.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshGaSession() {
    if (!gaSelectedId) return
    await selectGaSession(gaSelectedId)
    setGaSessionsList((await gaSessions()).items)
  }

  async function runGaAction(action) {
    setGaBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshGaSession()
      setNotice('External AI gateway session updated.')
    } catch (reason) { setError(reason.message) } finally { setGaBusy(false) }
  }

  async function submitGaCreateSession(event) {
    event.preventDefault()
    if (!gaNewTopic.trim()) return
    await runGaAction(async () => {
      const datasetIds = gaNewDatasetIds.split(',').map((s) => s.trim()).filter(Boolean)
      const session = await gaCreateSession(gaNewTopic.trim(), gaNewPurpose, datasetIds, gaNewRagId.trim() || null)
      setGaNewTopic(''); setGaNewDatasetIds(''); setGaNewRagId('')
      setGaSessionsList((await gaSessions()).items)
      await selectGaSession(session.public_id)
    })
  }

  function submitGaAuthorize(event) {
    event.preventDefault()
    if (!gaAuthorizationNote.trim()) return
    runGaAction(() => gaAuthorize(gaSelectedId, gaAuthorizationNote.trim()))
  }

  function submitGaSanitize(event) {
    event.preventDefault()
    runGaAction(() => gaSanitize(gaSelectedId, gaAdminStatedNeed.trim()))
  }

  function submitGaSelectProviders(event) {
    event.preventDefault()
    const keys = gaProviderKeys.split(',').map((s) => s.trim()).filter(Boolean)
    if (!keys.length) return
    runGaAction(() => gaSelectProviders(gaSelectedId, keys))
  }

  const runGaDispatch = () => runGaAction(() => gaDispatch(gaSelectedId, 30.0, false))
  const runGaCollect = () => runGaAction(() => gaCollect(gaSelectedId))
  const runGaNormalize = () => runGaAction(() => gaNormalize(gaSelectedId))
  const runGaAnalyze = () => runGaAction(() => gaAnalyze(gaSelectedId))
  const runGaBuildEvidence = () => runGaAction(() => gaBuildEvidence(gaSelectedId))
  const runGaGenerateReport = () => runGaAction(() => gaGenerateReport(gaSelectedId))
  const runGaAdminReview = (decision) => runGaAction(() => gaAdminReview(gaSelectedId, decision))
  const runGaArchive = () => runGaAction(() => gaArchive(gaSelectedId))

  async function loadTe() {
    const [jobs, diag, memory] = await Promise.all([teJobs(), teDiagnostics(), teMemory()])
    setTeJobsList(jobs.items)
    setTeDiag(diag)
    setTeMemoryList(memory.items)
  }

  async function selectTeJob(publicId) {
    setTeSelectedId(publicId)
    setError('')
    if (!publicId) { setTeJobData(null); setTeEventsList([]); setTeCheckpointsList([]); setTeMetricsList([]); return }
    try {
      const [job, events, checkpoints, metrics] = await Promise.all([
        teJob(publicId), teEvents(publicId), teCheckpoints(publicId), teMetrics(publicId),
      ])
      setTeJobData(job)
      setTeEventsList(events.items)
      setTeCheckpointsList(checkpoints.items)
      setTeMetricsList(metrics.items)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshTeJob() {
    if (!teSelectedId) return
    await selectTeJob(teSelectedId)
    setTeJobsList((await teJobs()).items)
  }

  async function runTeAction(action) {
    setTeBusy(true); setError(''); setNotice('')
    try {
      await action()
      await refreshTeJob()
      setNotice('Training engine job updated.')
    } catch (reason) { setError(reason.message) } finally { setTeBusy(false) }
  }

  async function submitTeCreateJob(event) {
    event.preventDefault()
    if (!teNewTopic.trim() || !teNewPackageId.trim() || !teNewReleaseId.trim()) return
    await runTeAction(async () => {
      const job = await teCreateJob(teNewTopic.trim(), teNewPackageId.trim(), teNewReleaseId.trim(), teNewExecutionMode)
      setTeNewTopic(''); setTeNewPackageId(''); setTeNewReleaseId('')
      setTeJobsList((await teJobs()).items)
      await selectTeJob(job.public_id)
    })
  }

  function submitTeAuthorize(event) {
    event.preventDefault()
    if (!teAuthorizationReason.trim()) return
    runTeAction(() => teAuthorize(teSelectedId, teAuthorizationReason.trim()))
  }

  function submitTeStreamMetric(event) {
    event.preventDefault()
    runTeAction(() => teStreamMetric(teSelectedId, Number(teMetricStep), Number(teMetricEpoch)))
  }

  function submitTeSaveCheckpoint(event) {
    event.preventDefault()
    runTeAction(() => teSaveCheckpoint(teSelectedId, Number(teCheckpointStep), Number(teCheckpointEpoch)))
  }

  const runTeValidateRelease = () => runTeAction(() => teValidateRelease(teSelectedId))
  const runTeValidatePackage = () => runTeAction(() => teValidatePackage(teSelectedId))
  const runTePlanResources = () => runTeAction(() => tePlanResources(teSelectedId))
  const runTeBuildManifest = () => runTeAction(() => teBuildManifest(teSelectedId))
  const runTeReserveRuntime = () => runTeAction(() => teReserveRuntime(teSelectedId))
  const runTeStart = () => runTeAction(() => teStart(teSelectedId))
  const runTePause = () => runTeAction(() => tePause(teSelectedId))
  const runTeResume = () => runTeAction(() => teResume(teSelectedId))
  const runTeCancel = () => runTeAction(() => teCancel(teSelectedId))
  const runTeFinalize = () => runTeAction(() => teFinalize(teSelectedId))
  const runTeGenerateReport = () => runTeAction(() => teGenerateReport(teSelectedId))
  const runTeArchive = () => runTeAction(() => teArchive(teSelectedId))

  async function loadPcr() {
    const [diag, analyticsData, sessions, clusters, pending, approved] = await Promise.all([
      pcrDiagnostics(), pcrAnalytics(), pcrSessions('active'), pcrClusters(),
      pcrCandidates('pending_admin_review'), pcrCandidates('approved'),
    ])
    setPcrDiag(diag)
    setPcrAnalyticsData(analyticsData)
    setPcrSessionsList(sessions.items)
    setPcrClustersList(clusters.items)
    setPcrCandidatesList(pending.items)
    setPcrApprovedCandidatesList(approved.items)
  }

  async function selectPcrSession(publicId) {
    setPcrSelectedSessionId(publicId)
    setError('')
    if (!publicId) {
      setPcrSessionData(null); setPcrMessagesList([]); setPcrSignalsList([]); setPcrSessionEventsList([])
      return
    }
    try {
      const [session, messages, signals, events] = await Promise.all([
        pcrSession(publicId), pcrMessages(publicId), pcrSignals(publicId), pcrSessionEvents(publicId),
      ])
      setPcrSessionData(session)
      setPcrMessagesList(messages.items)
      setPcrSignalsList(signals.items)
      setPcrSessionEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function selectPcrCandidate(publicId) {
    setPcrSelectedCandidateId(publicId)
    setPcrReviewNotes('')
    setError('')
    if (!publicId) { setPcrCandidateData(null); setPcrCandidateEventsList([]); return }
    try {
      const [candidate, events] = await Promise.all([pcrCandidate(publicId), pcrCandidateEvents(publicId)])
      setPcrCandidateData(candidate)
      setPcrCandidateEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function runPcrAction(action) {
    setPcrBusy(true); setError(''); setNotice('')
    try {
      await action()
      await loadPcr()
      setNotice('Public chat runtime updated.')
    } catch (reason) { setError(reason.message) } finally { setPcrBusy(false) }
  }

  async function submitPcrGenerateCandidates(event) {
    event.preventDefault()
    await runPcrAction(() => pcrGenerateCandidates(Number(pcrMinFrequency) || 2))
  }

  async function submitPcrReview(decision) {
    if (!pcrSelectedCandidateId) return
    await runPcrAction(async () => {
      await pcrReviewCandidate(pcrSelectedCandidateId, decision, pcrReviewNotes.trim() || null)
      await selectPcrCandidate(pcrSelectedCandidateId)
    })
  }

  async function runPcrExportAnalytics() {
    setPcrBusy(true); setError('')
    try { setPcrExportResult(await pcrExportAnalytics()) } catch (reason) { setError(reason.message) } finally { setPcrBusy(false) }
  }

  async function runPcrExportCandidates() {
    setPcrBusy(true); setError('')
    try { setPcrExportResult(await pcrExportCandidates()) } catch (reason) { setError(reason.message) } finally { setPcrBusy(false) }
  }

  async function loadPg() {
    const [diag, plugins, memory] = await Promise.all([pgDiagnostics(), pgPlugins(), pgMemory()])
    setPgDiag(diag)
    setPgPluginsList(plugins.items)
    setPgMemoryList(memory.items)
  }

  async function selectPgPlugin(publicId) {
    setPgSelectedPluginId(publicId)
    setPgEvalResult(null); setPgPolicyCheckResult(null); setPgTokenResult(null)
    setError('')
    if (!publicId) {
      setPgPluginData(null); setPgPermissionsList([]); setPgConsentsList([]); setPgEventsList([])
      return
    }
    try {
      const [plugin, permissions, consents, events] = await Promise.all([
        pgPlugin(publicId), pgPermissions(publicId), pgConsents(publicId), pgEvents(publicId),
      ])
      setPgPluginData(plugin)
      setPgPermissionsList(permissions.items)
      setPgConsentsList(consents.items)
      setPgEventsList(events.items)
    } catch (reason) { setError(reason.message) }
  }

  async function runPgAction(action) {
    setPgBusy(true); setError(''); setNotice('')
    try {
      await action()
      await loadPg()
      if (pgSelectedPluginId) await selectPgPlugin(pgSelectedPluginId)
      setNotice('Plugin governance updated.')
    } catch (reason) { setError(reason.message) } finally { setPgBusy(false) }
  }

  function pgListField(value) {
    return value.split(',').map((v) => v.trim()).filter(Boolean)
  }

  async function submitPgRegister(event) {
    event.preventDefault()
    await runPgAction(() => pgRegisterPlugin({
      plugin_id: pgForm.plugin_id, name: pgForm.name, version: pgForm.version, author: pgForm.author,
      description: pgForm.description, entrypoint: pgForm.entrypoint,
      requested_scopes: pgListField(pgForm.requested_scopes), allowed_domains: pgListField(pgForm.allowed_domains),
      filesystem_roots: pgListField(pgForm.filesystem_roots), ui_components: pgListField(pgForm.ui_components),
      local_storage_usage: pgForm.local_storage_usage, cloud_storage_usage: pgForm.cloud_storage_usage,
      minimum_brud_version: pgForm.minimum_brud_version, signature_placeholder: pgForm.signature_placeholder,
      homepage: pgForm.homepage, support_url: pgForm.support_url,
    }, pgForm.source))
  }

  async function runPgValidate() { await runPgAction(() => pgValidateManifest(pgSelectedPluginId)) }
  async function runPgClassify() { await runPgAction(() => pgClassifyCapabilities(pgSelectedPluginId)) }
  async function runPgRiskScore() { await runPgAction(() => pgComputeRiskScore(pgSelectedPluginId)) }
  async function runPgSandbox() { await runPgAction(() => pgBuildSandboxProfile(pgSelectedPluginId)) }
  async function runPgFilesystemPolicy() { await runPgAction(() => pgBuildFilesystemPolicy(pgSelectedPluginId)) }
  async function runPgNetworkPolicy() { await runPgAction(() => pgBuildNetworkPolicy(pgSelectedPluginId)) }
  async function runPgEnable() { await runPgAction(() => pgEnablePlugin(pgSelectedPluginId)) }
  async function runPgGenerateReport() { await runPgAction(() => pgGenerateReport(pgSelectedPluginId)) }
  async function runPgDisable() { await runPgAction(() => pgDisablePlugin(pgSelectedPluginId)) }
  async function runPgArchive() { await runPgAction(() => pgArchivePlugin(pgSelectedPluginId)) }

  async function submitPgEvaluate(event) {
    event.preventDefault()
    if (!pgSelectedPluginId) return
    setPgBusy(true); setError('')
    try {
      setPgEvalResult(await pgEvaluatePermission(pgSelectedPluginId, pgEvalScopeKey, pgEvalIsPublicChat, pgEvalUserIdHash || null))
      await selectPgPlugin(pgSelectedPluginId)
    } catch (reason) { setError(reason.message) } finally { setPgBusy(false) }
  }

  async function runPgPolicyCheck() {
    if (!pgSelectedPluginId || !pgEvalScopeKey) return
    setPgBusy(true); setError('')
    try { setPgPolicyCheckResult(await pgCheckPolicy(pgSelectedPluginId, pgEvalScopeKey)) }
    catch (reason) { setError(reason.message) } finally { setPgBusy(false) }
  }

  async function submitPgConsent(event) {
    event.preventDefault()
    if (!pgSelectedPluginId) return
    await runPgAction(() => pgRequestConsent(
      pgSelectedPluginId, pgConsentScopeKey, pgConsentUserIdentity, pgConsentGiven,
      pgConsentTtl ? Number(pgConsentTtl) : null,
    ))
  }

  async function runPgGrant(scopeKey, userIdHash) {
    await runPgAction(() => pgGrantPermission(pgSelectedPluginId, scopeKey, userIdHash || null))
  }

  async function runPgRevoke(scopeKey) {
    await runPgAction(() => pgRevokePermission(pgSelectedPluginId, scopeKey))
  }

  async function submitPgIssueToken(event) {
    event.preventDefault()
    if (!pgSelectedPluginId) return
    setPgBusy(true); setError('')
    try {
      setPgTokenResult(await pgIssueToken(
        pgSelectedPluginId, pgListField(pgTokenScopeKeys), pgTokenUserIdentity, pgTokenSessionIdentity,
        pgTokenTtl ? Number(pgTokenTtl) : 300,
      ))
      await selectPgPlugin(pgSelectedPluginId)
    } catch (reason) { setError(reason.message) } finally { setPgBusy(false) }
  }

  async function runPgReportExecution() {
    await runPgAction(() => pgRuntimeEvent(pgSelectedPluginId, 'plugin_execution_reported', 'reported from dashboard', {}))
  }

  const voMediaRecorderRef = useRef(null)
  const voRecordedChunksRef = useRef([])

  async function loadVo() {
    const [diag, stats, sessions, memory, events] = await Promise.all([
      voDiagnostics(), voStatistics(), voSessions(), voMemory(), voEvents(),
    ])
    setVoDiag(diag)
    setVoStats(stats)
    setVoSessionsList(sessions.items)
    setVoMemoryList(memory.items)
    setVoMetrics(memory.metrics)
    setVoEventsList(events.items)
  }

  async function selectVoSession(publicId) {
    setVoSelectedSessionId(publicId)
    setError('')
    if (!publicId) { setVoSessionData(null); return }
    try {
      const data = await voSession(publicId)
      setVoSessionData(data)
    } catch (reason) { setError(reason.message) }
  }

  async function blobToBase64(blob) {
    const arrayBuffer = await blob.arrayBuffer()
    const bytes = new Uint8Array(arrayBuffer)
    let binary = ''
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    return btoa(binary)
  }

  // Mic capture only ever starts on an explicit user action (push-to-talk
  // press) and only ever stops on the matching release -- never a
  // background timer/interval, matching MB-26's "mic only while pressed"
  // security requirement.
  async function startVoRecording() {
    setError(''); setNotice('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      voRecordedChunksRef.current = []
      const recorder = new MediaRecorder(stream)
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) voRecordedChunksRef.current.push(event.data)
      }
      recorder.start()
      voMediaRecorderRef.current = recorder
      setVoRecording(true)
    } catch (reason) {
      setError('Microphone access denied or unavailable: ' + reason.message)
    }
  }

  async function stopVoRecordingAndSend() {
    const recorder = voMediaRecorderRef.current
    if (!recorder) { setVoRecording(false); return }
    setVoBusy(true); setError(''); setNotice('')
    try {
      const stopped = new Promise((resolve) => { recorder.onstop = resolve })
      recorder.stop()
      recorder.stream.getTracks().forEach((track) => track.stop())
      await stopped
      setVoRecording(false)

      const blob = new Blob(voRecordedChunksRef.current, { type: 'audio/webm' })
      const audioBase64 = await blobToBase64(blob)

      const session = await voPublicCreateSession(voConsent, 'auto')
      if (session.status !== 'active') {
        setError('Voice session denied: ' + (session.denial_reason || 'unknown reason'))
        return
      }
      await voPublicSendChunk(session.public_id, 0, audioBase64)
      const result = await voPublicFinishSession(session.public_id)
      setVoSessionData(result)
      setVoChunkSeq(0)
      setNotice('Voice reply ready.')
      await loadVo()
    } catch (reason) {
      setError(reason.message)
    } finally {
      setVoBusy(false)
    }
  }

  async function runVoTestStt() {
    setVoBusy(true); setError(''); setNotice('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks = []
      const recorder = new MediaRecorder(stream)
      recorder.ondataavailable = (event) => { if (event.data && event.data.size > 0) chunks.push(event.data) }
      const stopped = new Promise((resolve) => { recorder.onstop = resolve })
      recorder.start()
      await new Promise((resolve) => setTimeout(resolve, 2000))
      recorder.stop()
      stream.getTracks().forEach((track) => track.stop())
      await stopped
      const blob = new Blob(chunks, { type: 'audio/webm' })
      const audioBase64 = await blobToBase64(blob)
      const result = await voTestStt(audioBase64)
      setVoTestSttText(result)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setVoBusy(false)
    }
  }

  async function runVoTestTts() {
    setVoBusy(true); setError(''); setNotice('')
    try {
      const result = await voTestTts(voTestTtsForm.text)
      setVoTestTtsResult(result)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setVoBusy(false)
    }
  }

  async function loadPs() {
    const [diag, providers, memory] = await Promise.all([psDiagnostics(), psProviders(), psMemory()])
    setPsDiag(diag)
    setPsProvidersList(providers.items)
    setPsMemoryList(memory.items)
    const auditLists = await Promise.all(providers.items.map((p) => psProviderAudit(p.public_id)))
    setPsAuditList(auditLists.flatMap((a) => a.items))
  }

  async function selectPsProvider(publicId) {
    setPsSelectedProviderId(publicId)
  }

  async function createPsProvider(providerKey) {
    setPsBusy(true); setError(''); setNotice('')
    try {
      await psCreateProvider(providerKey, false, {})
      setNotice(`${providerKey} provider created.`)
      await loadPs()
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPsBusy(false)
    }
  }

  async function togglePsProvider(providerId, currentlyEnabled) {
    setPsBusy(true); setError(''); setNotice('')
    try {
      if (currentlyEnabled) await psDisableProvider(providerId)
      else await psEnableProvider(providerId)
      await loadPs()
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPsBusy(false)
    }
  }

  async function savePsSecret(providerId, secretName) {
    const inputKey = `${providerId}:${secretName}`
    const value = psSecretInputs[inputKey]
    if (!value) return
    setPsBusy(true); setError(''); setNotice('')
    try {
      await psSetSecret(providerId, secretName, value)
      setPsSecretInputs((prev) => ({ ...prev, [inputKey]: '' }))
      setNotice('Secret saved.')
      await loadPs()
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPsBusy(false)
    }
  }

  async function deletePsSecret(providerId, secretName) {
    setPsBusy(true); setError(''); setNotice('')
    try {
      await psDeleteSecret(providerId, secretName)
      await loadPs()
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPsBusy(false)
    }
  }

  async function runPsTestConnection(providerId) {
    setPsBusy(true); setError(''); setNotice('')
    try {
      const result = await psTestConnection(providerId)
      setPsTestResults((prev) => ({ ...prev, [providerId]: result }))
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPsBusy(false)
    }
  }

  async function archivePsProvider(providerId) {
    setPsBusy(true); setError(''); setNotice('')
    try {
      await psArchiveProvider(providerId)
      setNotice('Provider archived.')
      await loadPs()
    } catch (reason) {
      setError(reason.message)
    } finally {
      setPsBusy(false)
    }
  }

  function psProviderByKey(providerKey) {
    return psProvidersList.find((p) => p.provider_key === providerKey)
  }

  function renderPsProviderCard(providerKey) {
    const provider = psProviderByKey(providerKey)
    if (!provider) {
      return (
        <div className="notice" key={providerKey}>
          <p>{providerKey} is not yet configured / இன்னும் அமைக்கப்படவில்லை.</p>
          <Button disabled={psBusy} onClick={() => createPsProvider(providerKey)}>Create {providerKey} setting</Button>
        </div>
      )
    }
    const testResult = psTestResults[provider.public_id]
    const requiredSecrets = psRequiredSecrets[providerKey] || []
    return (
      <div className="card" key={providerKey}>
        <h4>{providerKey} — <span className={provider.health === 'healthy' ? 'badge good' : 'badge warn'}>{provider.health}</span></h4>
        <label>
          <input type="checkbox" checked={provider.enabled} disabled={psBusy} onChange={() => togglePsProvider(provider.public_id, provider.enabled)} />
          {' '}Enabled / இயக்கப்பட்டது
        </label>
        {requiredSecrets.length === 0 && (
          <p className="notice">No API key required for this local backend / இதற்கு API key தேவையில்லை.</p>
        )}
        {requiredSecrets.map((secretName) => {
          const existing = provider.secrets.find((s) => s.secret_name === secretName)
          const inputKey = `${provider.public_id}:${secretName}`
          return (
            <div key={secretName} className="notice">
              <label>{secretName}</label>
              <input
                type="password"
                placeholder="API Key / API விசையை உள்ளிடவும்"
                value={psSecretInputs[inputKey] || ''}
                onChange={(e) => setPsSecretInputs((prev) => ({ ...prev, [inputKey]: e.target.value }))}
              />
              <Button disabled={psBusy || !psSecretInputs[inputKey]} onClick={() => savePsSecret(provider.public_id, secretName)}>Save</Button>
              {existing && existing.is_set && (
                <>
                  <span> {existing.masked_indicator} saved {existing.updated_at}</span>
                  <Button disabled={psBusy} onClick={() => deletePsSecret(provider.public_id, secretName)}>Remove</Button>
                </>
              )}
            </div>
          )
        })}
        <Button disabled={psBusy} onClick={() => runPsTestConnection(provider.public_id)}>Test Connection / இணைப்பை சோதிக்க</Button>
        {testResult && <pre className="notice">{JSON.stringify(testResult, null, 2)}</pre>}
        <Button disabled={psBusy} onClick={() => archivePsProvider(provider.public_id)}>Archive</Button>
      </div>
    )
  }

  async function loadLr() {
    const [diag, localProviders] = await Promise.all([lrDiagnostics(), psProviders('local_model')])
    setLrDiag(diag)
    const localProvider = localProviders.items.find((p) => p.provider_key === 'local_llm')
    if (localProvider) {
      const cfg = localProvider.config || {}
      setLrLocalProviderId(localProvider.public_id)
      setLrLocalModelConfig({
        model_path: cfg.model_path || '',
        context_length: cfg.context_length ?? 2048,
        max_tokens: cfg.max_tokens ?? 512,
        temperature: cfg.temperature ?? 0.3,
        threads: cfg.threads ?? 4,
      })
    }
  }

  // The non-Chat sub-tabs (Explain Page, Summarize Report/Regression,
  // Explain Error, Next Actions) each continue the same conversation
  // thread across actions -- this just tracks which session that is.
  function selectLrSession(sessionId) {
    setLrActiveSessionId(sessionId)
    setLrNextActionsResult(null)
  }

  function startNewLrConversation() {
    setLrActiveSessionId('')
    setLrNextActionsResult(null)
  }

  function lrParseJson(text, label) {
    try { return JSON.parse(text || '{}') }
    catch { throw new Error(`${label} must be valid JSON`) }
  }

  async function submitLrExplainPage(event) {
    event.preventDefault()
    setLrBusy(true); setError(''); setNotice('')
    try {
      const result = await lrExplainPage(lrActiveSessionId || null, lrExplainPageForm.page_id || null, lrExplainPageForm.nav_key || null)
      setLrActiveSessionId(result.session.public_id)
      setLrLastBackendType(result.backend_type)
      await selectLrSession(result.session.public_id)
      await loadLr()
    } catch (reason) { setError(reason.message) } finally { setLrBusy(false) }
  }

  async function submitLrSummarizeReport(event) {
    event.preventDefault()
    setLrBusy(true); setError(''); setNotice('')
    try {
      const report = lrParseJson(lrReportForm, 'Report')
      const result = await lrSummarizeReport(lrActiveSessionId || null, report)
      setLrActiveSessionId(result.session.public_id)
      setLrLastBackendType(result.backend_type)
      await selectLrSession(result.session.public_id)
      await loadLr()
    } catch (reason) { setError(reason.message) } finally { setLrBusy(false) }
  }

  async function submitLrSummarizeRegression(event) {
    event.preventDefault()
    setLrBusy(true); setError(''); setNotice('')
    try {
      const regressionResult = lrParseJson(lrRegressionForm, 'Regression result')
      const result = await lrSummarizeRegression(lrActiveSessionId || null, regressionResult)
      setLrActiveSessionId(result.session.public_id)
      setLrLastBackendType(result.backend_type)
      await selectLrSession(result.session.public_id)
      await loadLr()
    } catch (reason) { setError(reason.message) } finally { setLrBusy(false) }
  }

  async function submitLrExplainError(event) {
    event.preventDefault()
    if (!lrErrorForm.trim()) return
    setLrBusy(true); setError(''); setNotice('')
    try {
      const result = await lrExplainError(lrActiveSessionId || null, lrErrorForm)
      setLrActiveSessionId(result.session.public_id)
      setLrLastBackendType(result.backend_type)
      await selectLrSession(result.session.public_id)
      await loadLr()
    } catch (reason) { setError(reason.message) } finally { setLrBusy(false) }
  }

  async function submitLrNextActions(event) {
    event.preventDefault()
    setLrBusy(true); setError(''); setNotice('')
    try {
      const statusSnapshot = lrParseJson(lrStatusSnapshotForm, 'Status snapshot')
      const result = await lrNextActions(lrActiveSessionId || null, statusSnapshot)
      setLrActiveSessionId(result.session.public_id)
      setLrLastBackendType(result.backend_type)
      setLrNextActionsResult(result.actions)
      await selectLrSession(result.session.public_id)
      await loadLr()
    } catch (reason) { setError(reason.message) } finally { setLrBusy(false) }
  }

  async function saveLrLocalModelConfig() {
    setLrBusy(true); setError(''); setNotice('')
    try {
      let providerId = lrLocalProviderId
      if (!providerId) {
        const created = await psCreateProvider('local_llm', false, {})
        providerId = created.public_id
        setLrLocalProviderId(providerId)
      }
      await psUpdateProvider(providerId, {
        model_path: lrLocalModelConfig.model_path || null,
        context_length: Number(lrLocalModelConfig.context_length) || 2048,
        max_tokens: Number(lrLocalModelConfig.max_tokens) || 512,
        temperature: Number(lrLocalModelConfig.temperature),
        threads: Number(lrLocalModelConfig.threads) || 4,
      })
      setNotice('Local model configuration saved / உள்ளூர் மாடல் அமைப்பு சேமிக்கப்பட்டது.')
      await loadLr()
    } catch (reason) { setError(reason.message) } finally { setLrBusy(false) }
  }

  async function loadLc() {
    const [hardwareData, diag, catalog] = await Promise.all([lcHardware(), lcDiagnostics(), lcProvidersCatalog()])
    setLcHardwareData(hardwareData)
    setLcDiag(diag)
    setLcCatalog(catalog.providers)
  }

  async function runLcScan() {
    setLcSetupBusy(true); setError(''); setNotice('')
    try {
      const result = await lcScanModels()
      setLcScannedModels(result.items)
      setNotice(`Found ${result.items.length} local model(s) / ${result.items.length} உள்ளூர் மாடல்(கள்) கிடைத்தன.`)
    } catch (reason) { setError(reason.message) } finally { setLcSetupBusy(false) }
  }

  async function loadLcRecommendations() {
    setLcSetupBusy(true); setError(''); setNotice('')
    try {
      setLcRecommendationsData(await lcRecommendations())
    } catch (reason) { setError(reason.message) } finally { setLcSetupBusy(false) }
  }

  function selectLcScannedModel(absolutePath) {
    setLcLocalForm((prev) => ({ ...prev, model_path: absolutePath }))
    setLcSubTab('Local Configuration')
  }

  async function saveLcLocalModel() {
    setLcSetupBusy(true); setError(''); setNotice('')
    try {
      const dirs = lcLocalForm.additional_model_dirs
        ? lcLocalForm.additional_model_dirs.split('\n').map((s) => s.trim()).filter(Boolean)
        : null
      await lcSaveLocalModel(
        lcLocalForm.model_path, lcLocalForm.context_length, lcLocalForm.max_tokens,
        lcLocalForm.temperature, lcLocalForm.threads, dirs,
      )
      setNotice('Local model configuration saved / உள்ளூர் மாடல் அமைப்பு சேமிக்கப்பட்டது.')
      await loadLc()
    } catch (reason) { setError(reason.message) } finally { setLcSetupBusy(false) }
  }

  function lcProviderForm(providerKey) {
    return lcProviderForms[providerKey] || { api_key: '', model: '', enabled: false }
  }

  function updateLcProviderForm(providerKey, patch) {
    setLcProviderForms((prev) => ({ ...prev, [providerKey]: { ...lcProviderForm(providerKey), ...patch } }))
  }

  async function saveLcProvider(providerKey) {
    setLcSetupBusy(true); setError(''); setNotice('')
    try {
      const form = lcProviderForm(providerKey)
      await lcSaveProvider(providerKey, form.api_key, form.model, form.enabled)
      updateLcProviderForm(providerKey, { api_key: '' })
      setNotice(`${providerKey} saved / சேமிக்கப்பட்டது.`)
    } catch (reason) { setError(reason.message) } finally { setLcSetupBusy(false) }
  }

  async function testLcLocalModel() {
    setLcSetupBusy(true); setError(''); setNotice('')
    try {
      const result = await lrChat(null, `Say hello -- this is a connectivity test of the locally configured model at ${lcLocalForm.model_path}.`)
      setNotice(`Test reply (${result.backend_type}): ${result.reply.sanitized_text}`)
    } catch (reason) { setError(reason.message) } finally { setLcSetupBusy(false) }
  }

  async function loadLcGuide() {
    setLcSetupBusy(true); setError(''); setNotice('')
    try {
      setLcGuide(await lcSetupGuide())
    } catch (reason) { setError(reason.message) } finally { setLcSetupBusy(false) }
  }

  async function loadRm() {
    const [hardwareData, catalogData, installedList, statusData] = await Promise.all([
      rmHardware(), rmCatalog(), rmInstalled(), rmStatus(),
    ])
    setRmHardwareData(hardwareData)
    setRmCatalogData(catalogData.models)
    setRmInstalledList(installedList.items)
    setRmStatusData(statusData)
  }

  async function loadRmRecommendation() {
    setRmBusy(true); setError(''); setNotice('')
    try {
      const rec = await rmRecommendation()
      setRmRecommendationData(rec)
      setRmSelectedModelId(rec.model_id)
    } catch (reason) { setError(reason.message) } finally { setRmBusy(false) }
  }

  async function runRmAction(action, successMessage) {
    setRmBusy(true); setError(''); setNotice('')
    try {
      const result = await action()
      setRmLastActionResult(result)
      await loadRm()
      setNotice(successMessage)
      return result
    } catch (reason) { setError(reason.message); return null } finally { setRmBusy(false) }
  }

  async function installRecommendedModel() {
    setRmBusy(true); setError(''); setNotice('')
    try {
      const rec = rmRecommendationData || (await rmRecommendation())
      setRmRecommendationData(rec)
      setRmSelectedModelId(rec.model_id)
      await rmDownload(rec.model_id)
      await loadRm()
      setNotice(`${rec.display_name} installed / நிறுவப்பட்டது.`)
    } catch (reason) { setError(reason.message) } finally { setRmBusy(false) }
  }

  const runRmDownload = () => runRmAction(() => rmDownload(rmSelectedModelId), 'Download complete / பதிவிறக்கம் முடிந்தது.')
  const runRmVerify = () => runRmAction(() => rmVerify(rmSelectedModelId), 'Checksum verified / செக்சம் சரிபார்க்கப்பட்டது.')
  const runRmInstallSelected = () => runRmAction(() => rmInstall(rmSelectedModelId), 'Installed / நிறுவப்பட்டது.')
  const runRmLoad = () => runRmAction(
    () => rmLoad(rmSelectedModelId, rmLoadForm.context_length, rmLoadForm.max_tokens, rmLoadForm.temperature, rmLoadForm.threads),
    'Model loaded / மாடல் ஏற்றப்பட்டது.',
  )
  const runRmUnload = () => runRmAction(() => rmUnload(), 'Model unloaded / மாடல் இறக்கப்பட்டது.')
  const runRmRemove = (modelId) => runRmAction(() => rmRemove(modelId), 'Installation removed / நிறுவல் அகற்றப்பட்டது.')

  async function runRmBenchmark() {
    setRmBusy(true); setError(''); setNotice('')
    try {
      const result = await rmBenchmark(rmSelectedModelId, rmBenchmarkPrompt)
      setRmLastBenchmarkResult(result)
      await loadRm()
      setNotice(`Benchmark: ${result.rating}`)
    } catch (reason) { setError(reason.message) } finally { setRmBusy(false) }
  }

  async function loadRmEvents() {
    setRmBusy(true); setError(''); setNotice('')
    try {
      setRmEventsList((await rmEvents()).items)
    } catch (reason) { setError(reason.message) } finally { setRmBusy(false) }
  }

  async function loadRmHistory() {
    setRmBusy(true); setError(''); setNotice('')
    try {
      setRmMemoryList((await rmMemory()).items)
    } catch (reason) { setError(reason.message) } finally { setRmBusy(false) }
  }

  async function loadPr() {
    const [diag, stats, executions, memory] = await Promise.all([prDiagnostics(), prStatistics(), prExecutions(), prMemory()])
    setPrDiag(diag)
    setPrStats(stats)
    setPrExecutionsList(executions.items)
    setPrMemoryList(memory.items)
  }

  async function selectPrExecution(publicId) {
    setPrSelectedExecutionId(publicId)
    setPrReportResult(null)
    setError('')
    if (!publicId) {
      setPrExecutionData(null); setPrLogs(null)
      return
    }
    try {
      const [execution, logs] = await Promise.all([prExecution(publicId), prExecutionLogs(publicId)])
      setPrExecutionData(execution)
      setPrLogs(logs)
    } catch (reason) { setError(reason.message) }
  }

  async function runPrAction(action) {
    setPrBusy(true); setError(''); setNotice('')
    try {
      await action()
      await loadPr()
      if (prSelectedExecutionId) await selectPrExecution(prSelectedExecutionId)
      setNotice('Plugin runtime updated.')
    } catch (reason) { setError(reason.message) } finally { setPrBusy(false) }
  }

  function prParseJson(text, label) {
    try { return JSON.parse(text || '{}') }
    catch { throw new Error(`${label} must be valid JSON`) }
  }

  async function submitPrExecute(event) {
    event.preventDefault()
    setPrBusy(true); setError(''); setNotice('')
    try {
      const args = prParseJson(prExecForm.arguments, 'Arguments')
      const token = prParseJson(prExecForm.execution_token, 'Execution token')
      const result = await prExecute(prExecForm.plugin_public_id, prExecForm.scope_key, args, token, Number(prExecForm.timeout_seconds) || 5.0)
      setPrExecResult(result)
      await loadPr()
      await selectPrExecution(result.public_id)
      setNotice('Execution finished.')
    } catch (reason) { setError(reason.message) } finally { setPrBusy(false) }
  }

  async function submitPrPublicExecute(event) {
    event.preventDefault()
    setPrBusy(true); setError(''); setNotice('')
    try {
      const args = prParseJson(prPublicForm.arguments, 'Arguments')
      const token = prParseJson(prPublicForm.execution_token, 'Execution token')
      const result = await prPublicExecute(prPublicForm.plugin_public_id, prPublicForm.scope_key, args, prPublicForm.raw_user_identity, token)
      setPrPublicResult(result)
      await loadPr()
      setNotice('Public chat execution finished.')
    } catch (reason) { setError(reason.message) } finally { setPrBusy(false) }
  }

  async function runPrCancel() { await runPrAction(() => prCancelExecution(prSelectedExecutionId)) }
  async function runPrArchive() { await runPrAction(() => prArchiveExecution(prSelectedExecutionId)) }

  async function runPrGenerateReport() {
    setPrBusy(true); setError('')
    try { setPrReportResult(await prGenerateReport(prSelectedExecutionId)) }
    catch (reason) { setError(reason.message) } finally { setPrBusy(false) }
  }

  async function runPrReportEvent() {
    await runPrAction(() => prRuntimeEvent(prSelectedExecutionId, 'admin_note', 'reviewed from dashboard', {}))
  }

  async function runCapabilityGenerate(event) {
    event.preventDefault()
    setCapBusy(true); setError('')
    try {
      setCapResult(await capabilityGenerate(capQuestion))
    } catch (reason) { setError(reason.message) } finally { setCapBusy(false) }
  }

  async function runDatasetIntelligenceReport(event) {
    event.preventDefault()
    setDiBusy(true); setError('')
    try {
      setDiReport(await datasetIntelligenceReport(diSourceId))
    } catch (reason) { setError(reason.message) } finally { setDiBusy(false) }
  }

  async function toggleAdvanced() {
    const next = !showAdvanced
    setShowAdvanced(next)
    if (next && !advDiagnostics) {
      try { setAdvDiagnostics(await datasetAdvancedDiagnostics()) } catch (reason) { setError(reason.message) }
    }
  }

  async function runAdvancedReport(event) {
    event.preventDefault()
    setAdvBusy(true); setError('')
    try {
      setAdvReport(await datasetAdvancedReport(diSourceId))
    } catch (reason) { setError(reason.message) } finally { setAdvBusy(false) }
  }

  async function runQualityGenerate(event) {
    event.preventDefault()
    setQBusy(true); setError('')
    try {
      const result = await qualityGenerate({ question: qQuestion })
      setQResult(result)
      setQHistory((prev) => [
        { question: qQuestion, at: new Date().toLocaleTimeString(), overall: result.quality.quality_score.overall_quality },
        ...prev,
      ].slice(0, MAX_QUALITY_HISTORY))
    } catch (reason) { setError(reason.message) } finally { setQBusy(false) }
  }

  async function loadKnowledgeCore() {
    setKcDomains((await knowledgeCoreDomains()).items)
  }

  async function seedKnowledge() {
    setError(''); setNotice('')
    try {
      const result = await seedKnowledgeCore()
      setNotice(result.seeded
        ? `Seeded ${result.domains} domains, ${result.items} items, ${result.relationships} relationships.`
        : 'Knowledge Core is already seeded.')
      await loadKnowledgeCore()
    } catch (reason) { setError(reason.message) }
  }

  async function runKnowledgeSearch(event) {
    event?.preventDefault()
    setError('')
    try {
      const result = await searchKnowledgeCore(`?q=${encodeURIComponent(kcQuery)}`)
      setKcResults(result.items)
      setKcSelectedItem(null)
    } catch (reason) { setError(reason.message) }
  }

  async function openKnowledgeItem(publicId) {
    setError('')
    try { setKcSelectedItem(await knowledgeCoreItem(publicId)) } catch (reason) { setError(reason.message) }
  }

  async function runValidation() {
    setError(''); setNotice('')
    try {
      const result = await runKnowledgeCoreValidation()
      setKcValidation(result)
      setNotice(`Validation complete: ${result.issue_count} issue(s) found.`)
    } catch (reason) { setError(reason.message) }
  }

  async function loadCoverage() {
    setError('')
    try { setKcCoverage(await knowledgeCoreCoverage()) } catch (reason) { setError(reason.message) }
  }

  async function selectKnowledgeSubTab(value) {
    setKnowledgeSubTab(value)
    setError('')
    if (value === 'Coverage') await loadCoverage()
  }

  async function runIntelligenceAnalysis(event) {
    event.preventDefault()
    setIeBusy(true); setError('')
    try {
      setIeResult(await analyzeQuestion(ieQuestion))
    } catch (reason) { setError(reason.message) } finally { setIeBusy(false) }
  }

  async function loadRuntimeTab() {
    setError('')
    try {
      const [statusData, statsData, diagData, modelsData] = await Promise.all([
        runtimeStatus(), runtimeStatistics(), runtimeDiagnostics(), listRuntimeModels(),
      ])
      setRtStatus(statusData); setRtStats(statsData); setRtDiagnostics(diagData); setRtModels(modelsData.items)
    } catch (reason) { setError(reason.message) }
  }

  async function submitRegisterModel(event) {
    event.preventDefault()
    setError(''); setNotice('')
    try {
      await registerRuntimeModel(rtRegisterForm)
      setNotice('Model registered.')
      await loadRuntimeTab()
    } catch (reason) { setError(reason.message) }
  }

  async function runRuntimeAction(action) {
    setRtBusy(true); setError(''); setNotice('')
    try {
      if (action === 'unload') await unloadRuntimeModel()
      if (action === 'reload') await reloadRuntimeModel()
      if (action === 'load' && rtModels[0]) await loadRuntimeModel(rtModels[0].public_id)
      setNotice(`Runtime ${action} complete.`)
      await loadRuntimeTab()
    } catch (reason) { setError(reason.message) } finally { setRtBusy(false) }
  }

  async function toggle() {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = status?.enabled ? await disableMiniBrain() : await enableMiniBrain()
      setNotice(result.enabled ? 'Brud Mini Brain enabled.' : 'Brud Mini Brain disabled.')
      await load()
    } catch (reason) { setError(reason.message) } finally { setBusy(false) }
  }

  async function runHealthCheck() {
    setError(''); setNotice('')
    try {
      const result = await miniBrainHealth()
      setNotice(`Health check: ${result.status} (${result.reason})`)
      await load()
    } catch (reason) { setError(reason.message) }
  }

  async function saveSettings(event) {
    event.preventDefault()
    setError(''); setNotice('')
    try {
      const updated = await updateMiniBrainSettings({ config: { ...settings.config, log_level: logLevel } })
      setSettings(updated)
      setNotice('Configuration saved.')
      await load()
    } catch (reason) { setError(reason.message) }
  }

  return (
    <section className="documents-workspace">
      <header className="section-heading">
        <div>
          <h2>Brud Mini Brain</h2>
          <p>
            MB-01 -- Foundation &amp; Architecture. An independent admin-only framework, separate
            from the existing Admin Assistant. This phase ships no AI model: every inference,
            knowledge, memory, and suggestion interface below is a documented placeholder.
          </p>
        </div>
        <Button onClick={load}>Refresh</Button>
      </header>

      {runtimeHealth && (
        <section className="card">
          <h3 style={{ margin: '0 0 12px' }}>Mini Brain Runtime Health / Mini Brain இயக்க நிலை</h3>
          <div className="metric-grid">
            <StatusCard label="Active backend" value={runtimeHealth.backend_type} tone={runtimeHealth.backend_type.startsWith('local') ? 'good' : (runtimeHealth.backend_type === 'external' ? 'good' : 'neutral')} />
            <StatusCard label="Local model loaded" value={String(runtimeHealth.model_loaded)} tone={runtimeHealth.model_loaded ? 'good' : 'waiting'} />
            <StatusCard label="Current model" value={runtimeHealth.model_id ?? 'none'} tone="neutral" />
            <StatusCard label="Benchmark rating" value={runtimeHealth.benchmark_rating ?? 'no data'} tone={mbBenchmarkTone(runtimeHealth.benchmark_rating)} />
            <StatusCard label="Tokens/sec" value={runtimeHealth.tokens_per_second ?? 'no data'} tone="neutral" />
            <StatusCard label="Available RAM (GB)" value={runtimeHealth.available_ram_gb} tone="neutral" />
            <StatusCard label="External provider" value={runtimeHealth.external_provider_enabled ? (runtimeHealth.external_provider_name ?? 'enabled') : 'not configured'} tone={runtimeHealth.external_provider_enabled ? 'good' : 'neutral'} />
            <StatusCard label="Tamil reliability" value={runtimeHealth.tamil_quality_status ?? 'unknown'} tone={mbQualityTone(runtimeHealth.tamil_quality_status)} />
            <StatusCard label="English reliability" value={runtimeHealth.english_quality_status ?? 'unknown'} tone={mbQualityTone(runtimeHealth.english_quality_status)} />
          </div>
          {runtimeHealth.benchmark_rating && (
            <p className="notice" style={{ marginTop: '10px' }}>
              Benchmark scale: Excellent &ge; 15 tok/s, Good &ge; 8 tok/s, Fair &ge; 3 tok/s, Poor &lt; 3 tok/s.
            </p>
          )}
          <div className="notice" style={{ marginTop: '10px' }}>
            <strong>Next action:</strong> {runtimeHealth.next_action.en} / {runtimeHealth.next_action.ta}
          </div>
          {runtimeHealth.tamil_quality_status && runtimeHealth.tamil_quality_status !== 'good' && (
            <div className="assistant-llm-notice" style={{ marginTop: '10px' }}>
              Tamil answers may be inaccurate on the current local model. / தற்போதைய local model-இல் தமிழ் பதில்கள் துல்லியமாக இருக்காமல் இருக்கலாம்.
            </div>
          )}
        </section>
      )}

      <section className="card">
        <h3 style={{ margin: '0 0 6px' }}>Grounded Chat Test (MB-37)</h3>
        <p className="notice" style={{ marginTop: 0 }}>
          Temporary admin-only test panel for the grounded chat endpoint. Not the floating Admin
          Assistant widget -- retrieval evidence is injected directly into the local Mini Brain
          runtime's prompt. Now backed by the same shared chat component used elsewhere, with real
          markdown, citations, copy, and regenerate.
        </p>
        <ChatPanel variant="compact" toast={toast} suggestions={[]} />
      </section>

      <div className="dataset-tabs">
        {tabs.map((value) => (
          <Button key={value} className={tab === value ? 'active' : ''} onClick={() => selectTab(value)}>{value}</Button>
        ))}
      </div>
      {error && <ErrorBanner message={error} onRetry={() => selectTab(tab)} />}
      {notice && <div className="success-note" role="status">{notice}</div>}

      {tab === 'Overview' && (
        <OverviewTab status={status} version={version} busy={busy} toggle={toggle} runHealthCheck={runHealthCheck} />
      )}

      {tab === 'Settings' && (
        <SettingsTab settings={settings} logLevel={logLevel} setLogLevel={setLogLevel} saveSettings={saveSettings} />
      )}

      {tab === 'Logs' && <LogsTab logs={logs} />}

      {tab === 'Diagnostics' && <DiagnosticsTab diagnostics={diagnostics} />}

      {tab === 'Knowledge Core' && (
        <KnowledgeCoreTab
          knowledgeSubTab={knowledgeSubTab} selectKnowledgeSubTab={selectKnowledgeSubTab}
          kcDomains={kcDomains} seedKnowledge={seedKnowledge}
          kcQuery={kcQuery} setKcQuery={setKcQuery} runKnowledgeSearch={runKnowledgeSearch}
          kcResults={kcResults} openKnowledgeItem={openKnowledgeItem} kcSelectedItem={kcSelectedItem}
          runValidation={runValidation} kcValidation={kcValidation}
          kcCoverage={kcCoverage}
        />
      )}

      {tab === 'Intelligence Engine' && (
        <IntelligenceEngineTab
          runIntelligenceAnalysis={runIntelligenceAnalysis} ieQuestion={ieQuestion} setIeQuestion={setIeQuestion}
          ieBusy={ieBusy} ieResult={ieResult}
        />
      )}

      {tab === 'Runtime' && (
        <RuntimeTab
          rtStatus={rtStatus} rtStats={rtStats} rtBusy={rtBusy} rtModels={rtModels} runRuntimeAction={runRuntimeAction}
          rtRegisterForm={rtRegisterForm} setRtRegisterForm={setRtRegisterForm} submitRegisterModel={submitRegisterModel}
          rtDiagnostics={rtDiagnostics}
        />
      )}

      {tab === 'Response Quality' && (
        <ResponseQualityTab
          qDiagnostics={qDiagnostics} runQualityGenerate={runQualityGenerate} qQuestion={qQuestion}
          setQQuestion={setQQuestion} qBusy={qBusy} qResult={qResult} qHistory={qHistory}
        />
      )}

      {tab === 'Capability' && (
        <CapabilityTab
          capDiagnostics={capDiagnostics} runCapabilityGenerate={runCapabilityGenerate} capQuestion={capQuestion}
          setCapQuestion={setCapQuestion} capBusy={capBusy} capResult={capResult}
        />
      )}

      {tab === 'Dataset Intelligence' && (
        <DatasetIntelligenceTab
          runDatasetIntelligenceReport={runDatasetIntelligenceReport} diSourceId={diSourceId} setDiSourceId={setDiSourceId} diBusy={diBusy}
          diSubTab={diSubTab} setDiSubTab={setDiSubTab} diReport={diReport} diDiagnostics={diDiagnostics}
          toggleAdvanced={toggleAdvanced} showAdvanced={showAdvanced} advBusy={advBusy} runAdvancedReport={runAdvancedReport}
          advSubTab={advSubTab} setAdvSubTab={setAdvSubTab} advReport={advReport} advDiagnostics={advDiagnostics}
        />
      )}

      {tab === 'Learning Supervisor' && (
        <LearningSupervisorTab
          lsSessions={lsSessions} lsSelectedId={lsSelectedId} selectLsSession={selectLsSession}
          submitLsCreateSession={submitLsCreateSession} lsCreateForm={lsCreateForm} setLsCreateForm={setLsCreateForm} lsProfiles={lsProfiles} lsBusy={lsBusy}
          lsSession={lsSession}
          runLsValidateDataset={runLsValidateDataset}
          runLsDecideDataset={runLsDecideDataset}
          submitLsRagEvaluation={submitLsRagEvaluation} lsRagForm={lsRagForm} setLsRagForm={setLsRagForm} runLsFinalizeRag={runLsFinalizeRag}
          runLsDecideRag={runLsDecideRag}
          submitLsTrainingRequest={submitLsTrainingRequest} lsTrainingForm={lsTrainingForm} setLsTrainingForm={setLsTrainingForm}
          runLsMonitorTraining={runLsMonitorTraining} lsMonitor={lsMonitor} runLsAnalyzeTraining={runLsAnalyzeTraining}
          submitLsBenchmark={submitLsBenchmark} lsBenchmarkForm={lsBenchmarkForm} setLsBenchmarkForm={setLsBenchmarkForm}
          submitLsCompareModels={submitLsCompareModels} lsCompareForm={lsCompareForm} setLsCompareForm={setLsCompareForm}
          runLsRecommendations={runLsRecommendations}
          runLsAdminReview={runLsAdminReview}
          submitLsReleaseCandidate={submitLsReleaseCandidate} lsReleaseForm={lsReleaseForm} setLsReleaseForm={setLsReleaseForm}
          lsEvents={lsEvents}
        />
      )}

      {tab === 'Release Pipeline' && (
        <ReleasePipelineTab
          rpDiagnostics={rpDiagnostics}
          rpSessions={rpSessions} rpSelectedId={rpSelectedId} selectRpSession={selectRpSession}
          submitRpCreateSession={submitRpCreateSession} rpCreateForm={rpCreateForm} setRpCreateForm={setRpCreateForm} rpBusy={rpBusy}
          rpSession={rpSession}
          runRpValidateCheckpoint={runRpValidateCheckpoint}
          runRpConvert={runRpConvert}
          runRpQuantize={runRpQuantize}
          runRpVerify={runRpVerify}
          runRpPerformance={runRpPerformance}
          submitRpCreateVersion={submitRpCreateVersion} rpVersionForm={rpVersionForm} setRpVersionForm={setRpVersionForm}
          runRpAdminReview={runRpAdminReview}
          submitRpActivate={submitRpActivate} rpActivateLevel={rpActivateLevel} setRpActivateLevel={setRpActivateLevel}
          submitRpEvaluateRollback={submitRpEvaluateRollback} rpRollbackEvalForm={rpRollbackEvalForm} setRpRollbackEvalForm={setRpRollbackEvalForm} rpRollbackEval={rpRollbackEval}
          submitRpExecuteRollback={submitRpExecuteRollback} rpRollbackExecuteForm={rpRollbackExecuteForm} setRpRollbackExecuteForm={setRpRollbackExecuteForm}
          rpEvents={rpEvents}
        />
      )}

      {tab === 'Continuous Learning' && (
        <ContinuousLearningTab
          clDiagnostics={clDiagnostics}
          clSessions={clSessions} clSelectedId={clSelectedId} selectClSession={selectClSession}
          submitClCreateSession={submitClCreateSession} clCycleWindowDays={clCycleWindowDays} setClCycleWindowDays={setClCycleWindowDays} clBusy={clBusy}
          clSession={clSession}
          runClCollectFeedback={runClCollectFeedback}
          runClAnalyzeFailures={runClAnalyzeFailures}
          runClAnalyzeHallucinations={runClAnalyzeHallucinations}
          runClAnalyzeKnowledgeGaps={runClAnalyzeKnowledgeGaps}
          runClDetectWeakTopics={runClDetectWeakTopics}
          runClAnalyzeDifficulty={runClAnalyzeDifficulty}
          runClRecommendDatasets={runClRecommendDatasets}
          runClRecommendTraining={runClRecommendTraining}
          runClRankPriorities={runClRankPriorities}
          runClGenerateReport={runClGenerateReport}
          runClAdminReview={runClAdminReview}
          clEvents={clEvents}
        />
      )}

      {tab === 'Continuous Learning Center' && (
        <ContinuousLearningCenterTab
          clcDiag={clcDiag}
          clcMemoryItems={clcMemoryItems} submitClcRecordMemory={submitClcRecordMemory} clcMemoryForm={clcMemoryForm} setClcMemoryForm={setClcMemoryForm} clcBusy={clcBusy}
          clcSessionsList={clcSessionsList} clcSelectedId={clcSelectedId} selectClcSession={selectClcSession} submitClcCreateSession={submitClcCreateSession}
          clcSessionData={clcSessionData}
          runClcEvolveKnowledgeGaps={runClcEvolveKnowledgeGaps}
          runClcBuildLearningQueue={runClcBuildLearningQueue}
          submitClcBuildDraft={submitClcBuildDraft} clcDraftTopic={clcDraftTopic} setClcDraftTopic={setClcDraftTopic}
          submitClcPrepareProviderRequest={submitClcPrepareProviderRequest} clcProviders={clcProviders} setClcProviders={setClcProviders}
          submitClcIngestProviderResults={submitClcIngestProviderResults} clcProviderOutputs={clcProviderOutputs} setClcProviderOutputs={setClcProviderOutputs}
          submitClcPlanDatasetEvolution={submitClcPlanDatasetEvolution} clcExistingDatasetId={clcExistingDatasetId} setClcExistingDatasetId={setClcExistingDatasetId}
          runClcBuildRoadmap={runClcBuildRoadmap}
          runClcGenerateRecommendation={runClcGenerateRecommendation}
          runClcGenerateReport={runClcGenerateReport}
          runClcAdminReview={runClcAdminReview}
          clcEventsList={clcEventsList}
        />
      )}

      {tab === 'Research Center' && (
        <ResearchCenterTab
          rcSubTab={rcSubTab} setRcSubTab={setRcSubTab}
          rcDiag={rcDiag} rcSessionData={rcSessionData}
          rcSessionsList={rcSessionsList} rcSelectedId={rcSelectedId} selectRcSession={selectRcSession} submitRcCreateSession={submitRcCreateSession} rcNewTopic={rcNewTopic} setRcNewTopic={setRcNewTopic} rcBusy={rcBusy}
          rcEventsList={rcEventsList}
          rcProviders={rcProviders} toggleRcProviderStatus={toggleRcProviderStatus} submitRcAddProvider={submitRcAddProvider} rcNewProviderForm={rcNewProviderForm} setRcNewProviderForm={setRcNewProviderForm}
          submitRcResearchRequest={submitRcResearchRequest} rcPlanningCenterId={rcPlanningCenterId} setRcPlanningCenterId={setRcPlanningCenterId}
          submitRcSelectMode={submitRcSelectMode} rcMode={rcMode} setRcMode={setRcMode} rcProviderKeys={rcProviderKeys} setRcProviderKeys={setRcProviderKeys}
          submitRcBuildLocalDraft={submitRcBuildLocalDraft} rcExistingDatasetId={rcExistingDatasetId} setRcExistingDatasetId={setRcExistingDatasetId}
          runRcPrepareProviderRequestPackage={runRcPrepareProviderRequestPackage}
          submitRcIngestProviderResults={submitRcIngestProviderResults} rcProviderOutputs={rcProviderOutputs} setRcProviderOutputs={setRcProviderOutputs}
          runRcBuildDatasetDraft={runRcBuildDatasetDraft}
          runRcAdminReviewDraft={runRcAdminReviewDraft}
          submitRcRunRagEvaluation={submitRcRunRagEvaluation} rcRagForm={rcRagForm} setRcRagForm={setRcRagForm} runRcFinalizeRagEvaluation={runRcFinalizeRagEvaluation}
          runRcAdminReviewRag={runRcAdminReviewRag}
          runRcCheckTrainingGate={runRcCheckTrainingGate} rcTrainingReportMb06Id={rcTrainingReportMb06Id} setRcTrainingReportMb06Id={setRcTrainingReportMb06Id} submitRcAnalyzeTrainingReport={submitRcAnalyzeTrainingReport}
          runRcGenerateReport={runRcGenerateReport} rcReport={rcReport}
          rcMemoryItems={rcMemoryItems} submitRcRecordMemory={submitRcRecordMemory} rcMemoryNotes={rcMemoryNotes} setRcMemoryNotes={setRcMemoryNotes}
        />
      )}

      {tab === 'Dataset Evolution' && (
        <DatasetEvolutionTab
          deSubTab={deSubTab} setDeSubTab={setDeSubTab}
          deDiag={deDiag} deSessionData={deSessionData}
          deSessionsList={deSessionsList} deSelectedId={deSelectedId} selectDeSession={selectDeSession} submitDeCreateSession={submitDeCreateSession} deNewSourceId={deNewSourceId} setDeNewSourceId={setDeNewSourceId} deBusy={deBusy}
          deEventsList={deEventsList}
          runDeKnowledgeEvolution={runDeKnowledgeEvolution}
          runDeDatasetEvolution={runDeDatasetEvolution}
          runDeSimulation={runDeSimulation}
          runDeGenerateRecommendation={runDeGenerateRecommendation}
          runDeGenerateReport={runDeGenerateReport}
          runDeAdminReview={runDeAdminReview}
          submitDeRunRagEvaluation={submitDeRunRagEvaluation} deRagForm={deRagForm} setDeRagForm={setDeRagForm} runDeFinalizeRagEvaluation={runDeFinalizeRagEvaluation}
          runDeAdminReviewRag={runDeAdminReviewRag}
        />
      )}

      {tab === 'Pipeline Coordinator' && (
        <PipelineCoordinatorTab
          pcSubTab={pcSubTab} setPcSubTab={setPcSubTab}
          pcDiag={pcDiag} pcSessionData={pcSessionData}
          pcSessionsList={pcSessionsList} pcSelectedId={pcSelectedId} selectPcSession={selectPcSession} submitPcCreateSession={submitPcCreateSession} pcNewTopic={pcNewTopic} setPcNewTopic={setPcNewTopic} pcBusy={pcBusy}
          submitPcLinkResearch={submitPcLinkResearch} pcMb09Id={pcMb09Id} setPcMb09Id={setPcMb09Id}
          submitPcLinkResearchCenter={submitPcLinkResearchCenter} pcMb10Id={pcMb10Id} setPcMb10Id={setPcMb10Id}
          runPcRefreshResearchCenter={runPcRefreshResearchCenter}
          submitPcLinkDatasetEvolution={submitPcLinkDatasetEvolution} pcMb11Id={pcMb11Id} setPcMb11Id={setPcMb11Id}
          submitPcLinkTraining={submitPcLinkTraining} pcMb06Id={pcMb06Id} setPcMb06Id={setPcMb06Id}
          runPcRefreshTraining={runPcRefreshTraining}
          runPcRunRagFirstEnforcement={runPcRunRagFirstEnforcement}
          runPcGenerateTrainingReadiness={runPcGenerateTrainingReadiness}
          runPcGenerateTimeline={runPcGenerateTimeline}
          runPcPredictImprovement={runPcPredictImprovement}
          runPcGenerateRecommendation={runPcGenerateRecommendation}
          runPcGenerateReport={runPcGenerateReport}
          runPcAdminDecide={runPcAdminDecide}
          pcEventsList={pcEventsList}
        />
      )}

      {tab === 'Language Intelligence' && (
        <LanguageIntelligenceTab
          liSubTab={liSubTab} setLiSubTab={setLiSubTab}
          liDiag={liDiag} liSessionData={liSessionData}
          liSessionsList={liSessionsList} liSelectedId={liSelectedId} selectLiSession={selectLiSession} submitLiCreateSession={submitLiCreateSession} liNewSourceId={liNewSourceId} setLiNewSourceId={setLiNewSourceId} liBusy={liBusy}
          liEventsList={liEventsList}
          runLiLanguageScan={runLiLanguageScan}
          runLiUnicodeValidation={runLiUnicodeValidation}
          runLiSpellAnalysis={runLiSpellAnalysis}
          runLiGrammarAnalysis={runLiGrammarAnalysis}
          runLiOcrAnalysis={runLiOcrAnalysis}
          runLiTanglishAnalysis={runLiTanglishAnalysis}
          runLiTranslationAnalysis={runLiTranslationAnalysis}
          runLiDatasetDraft={runLiDatasetDraft}
          runLiQualityScore={runLiQualityScore}
          runLiGenerateReport={runLiGenerateReport}
          runLiAdminReview={runLiAdminReview}
        />
      )}

      {tab === 'Vision Intelligence' && (
        <VisionIntelligenceTab
          viSubTab={viSubTab} setViSubTab={setViSubTab}
          viDiag={viDiag} viSessionData={viSessionData}
          viSessionsList={viSessionsList} viSelectedId={viSelectedId} selectViSession={selectViSession} submitViCreateSession={submitViCreateSession} viNewDocumentSourceId={viNewDocumentSourceId} setViNewDocumentSourceId={setViNewDocumentSourceId} viNewDatasetSourceId={viNewDatasetSourceId} setViNewDatasetSourceId={setViNewDatasetSourceId} viBusy={viBusy}
          viEventsList={viEventsList}
          runViImageExtraction={runViImageExtraction} viImagesList={viImagesList}
          runViImageQuality={runViImageQuality}
          runViVisionUnderstanding={runViVisionUnderstanding} viObjectsList={viObjectsList}
          viDatasetTextInput={viDatasetTextInput} setViDatasetTextInput={setViDatasetTextInput} runViOcrCrossValidation={runViOcrCrossValidation}
          viAdminCaptionInput={viAdminCaptionInput} setViAdminCaptionInput={setViAdminCaptionInput} runViCaption={runViCaption}
          runViBoundingBoxPlan={runViBoundingBoxPlan}
          submitViAnnotate={submitViAnnotate} viAnnotateAction={viAnnotateAction} setViAnnotateAction={setViAnnotateAction} viAnnotateObjectId={viAnnotateObjectId} setViAnnotateObjectId={setViAnnotateObjectId}
          viAnnotateLabel={viAnnotateLabel} setViAnnotateLabel={setViAnnotateLabel} viAnnotateImageId={viAnnotateImageId} setViAnnotateImageId={setViAnnotateImageId}
          viAnnotateCaption={viAnnotateCaption} setViAnnotateCaption={setViAnnotateCaption}
          viAnnotateBoxX={viAnnotateBoxX} setViAnnotateBoxX={setViAnnotateBoxX} viAnnotateBoxY={viAnnotateBoxY} setViAnnotateBoxY={setViAnnotateBoxY} viAnnotateBoxW={viAnnotateBoxW} setViAnnotateBoxW={setViAnnotateBoxW} viAnnotateBoxH={viAnnotateBoxH} setViAnnotateBoxH={setViAnnotateBoxH}
          runViFinishAnnotation={runViFinishAnnotation}
          runViKnowledgeGraph={runViKnowledgeGraph}
          runViQaGeneration={runViQaGeneration}
          runViDatasetDraft={runViDatasetDraft}
          runViQualityScore={runViQualityScore}
          runViGenerateReport={runViGenerateReport}
          runViAdminReview={runViAdminReview}
        />
      )}

      {tab === 'Vision Model Center' && (
        <VisionModelCenterTab
          vmSubTab={vmSubTab} setVmSubTab={setVmSubTab}
          vmDiag={vmDiag} vmSessionData={vmSessionData}
          vmSessionsList={vmSessionsList} vmSelectedId={vmSelectedId} selectVmSession={selectVmSession} submitVmCreateSession={submitVmCreateSession}
          vmNewVisionSessionId={vmNewVisionSessionId} setVmNewVisionSessionId={setVmNewVisionSessionId} vmNewProviderKey={vmNewProviderKey} setVmNewProviderKey={setVmNewProviderKey} vmProvidersList={vmProvidersList} vmBusy={vmBusy}
          vmEventsList={vmEventsList}
          toggleVmProviderStatus={toggleVmProviderStatus}
          runVmImageLoad={runVmImageLoad}
          vmModelPath={vmModelPath} setVmModelPath={setVmModelPath} vmMmprojPath={vmMmprojPath} setVmMmprojPath={setVmMmprojPath} runVmProviderSelection={runVmProviderSelection}
          runVmObjectDetection={runVmObjectDetection} vmPredictionsList={vmPredictionsList}
          submitVmReview={submitVmReview} vmReviewAction={vmReviewAction} setVmReviewAction={setVmReviewAction} vmReviewPredictionId={vmReviewPredictionId} setVmReviewPredictionId={setVmReviewPredictionId}
          vmReviewLabel={vmReviewLabel} setVmReviewLabel={setVmReviewLabel} vmReviewImageId={vmReviewImageId} setVmReviewImageId={setVmReviewImageId}
          vmReviewBoxX={vmReviewBoxX} setVmReviewBoxX={setVmReviewBoxX} vmReviewBoxY={vmReviewBoxY} setVmReviewBoxY={setVmReviewBoxY} vmReviewBoxW={vmReviewBoxW} setVmReviewBoxW={setVmReviewBoxW} vmReviewBoxH={vmReviewBoxH} setVmReviewBoxH={setVmReviewBoxH}
          runVmFinishReview={runVmFinishReview}
          runVmSceneDetection={runVmSceneDetection}
          runVmCaption={runVmCaption}
          runVmRelationshipDetection={runVmRelationshipDetection}
          vmDatasetTextInput={vmDatasetTextInput} setVmDatasetTextInput={setVmDatasetTextInput} runVmOcrCrossValidation={runVmOcrCrossValidation}
          runVmKnowledgeGraph={runVmKnowledgeGraph}
          runVmCorrectionMemory={runVmCorrectionMemory} vmCorrectionsList={vmCorrectionsList}
          vmLearningMemoryList={vmLearningMemoryList}
          runVmQualityScore={runVmQualityScore}
          runVmDatasetDraft={runVmDatasetDraft}
          runVmGenerateReport={runVmGenerateReport}
          runVmAdminReview={runVmAdminReview}
        />
      )}

      {tab === 'Multimodal Dataset Generator' && (
        <MultimodalDatasetGeneratorTab
          mdSubTab={mdSubTab} setMdSubTab={setMdSubTab}
          mdDiag={mdDiag} mdSessionData={mdSessionData}
          mdSessionsList={mdSessionsList} mdSelectedId={mdSelectedId} selectMdSession={selectMdSession} submitMdCreateSession={submitMdCreateSession}
          mdNewDocumentId={mdNewDocumentId} setMdNewDocumentId={setMdNewDocumentId} mdNewVisionSessionId={mdNewVisionSessionId} setMdNewVisionSessionId={setMdNewVisionSessionId}
          mdNewLanguageSessionId={mdNewLanguageSessionId} setMdNewLanguageSessionId={setMdNewLanguageSessionId} mdNewVisionModelSessionId={mdNewVisionModelSessionId} setMdNewVisionModelSessionId={setMdNewVisionModelSessionId}
          mdBusy={mdBusy}
          mdEventsList={mdEventsList}
          runMdCollectSources={runMdCollectSources}
          runMdMergeMetadata={runMdMergeMetadata}
          runMdCollectText={runMdCollectText}
          runMdCollectImages={runMdCollectImages}
          runMdConversationBuilder={runMdConversationBuilder}
          runMdInstructionBuilder={runMdInstructionBuilder}
          mdRecordsList={mdRecordsList}
          runMdDatasetDraft={runMdDatasetDraft}
          submitMdSplit={submitMdSplit} mdSplitRecordIds={mdSplitRecordIds} setMdSplitRecordIds={setMdSplitRecordIds}
          submitMdMerge={submitMdMerge} mdMergeSessionIds={mdMergeSessionIds} setMdMergeSessionIds={setMdMergeSessionIds}
          mdExportFormat={mdExportFormat} setMdExportFormat={setMdExportFormat} runMdExportDraft={runMdExportDraft} runMdDeleteDraft={runMdDeleteDraft} mdExportResult={mdExportResult}
          runMdQualityAnalysis={runMdQualityAnalysis}
          runMdDuplicateDetection={runMdDuplicateDetection}
          runMdGenerateReport={runMdGenerateReport}
          runMdAdminReview={runMdAdminReview}
          mdMemoryList={mdMemoryList}
        />
      )}

      {tab === 'Vision RAG' && (
        <VisionRAGTab
          vrSubTab={vrSubTab} setVrSubTab={setVrSubTab}
          vrDiag={vrDiag} vrSessionData={vrSessionData}
          vrSessionsList={vrSessionsList} vrSelectedId={vrSelectedId} selectVrSession={selectVrSession} submitVrCreateSession={submitVrCreateSession}
          vrNewDatasetSessionId={vrNewDatasetSessionId} setVrNewDatasetSessionId={setVrNewDatasetSessionId} vrNewQuery={vrNewQuery} setVrNewQuery={setVrNewQuery} vrBusy={vrBusy}
          vrEventsList={vrEventsList}
          runVrTextRetrieval={runVrTextRetrieval}
          runVrAnswer={runVrAnswer}
          runVrEvidenceFusion={runVrEvidenceFusion} vrEvidenceList={vrEvidenceList}
          runVrImageRetrieval={runVrImageRetrieval}
          runVrOcrRetrieval={runVrOcrRetrieval}
          runVrObjectRetrieval={runVrObjectRetrieval}
          runVrKnowledgeGraphRetrieval={runVrKnowledgeGraphRetrieval}
          runVrQuality={runVrQuality}
          runVrHallucinationCheck={runVrHallucinationCheck}
          runVrGenerateReport={runVrGenerateReport}
          submitVrCorrect={submitVrCorrect} vrCorrectAction={vrCorrectAction} setVrCorrectAction={setVrCorrectAction} vrCorrectAnswer={vrCorrectAnswer} setVrCorrectAnswer={setVrCorrectAnswer}
          vrCorrectEvidenceId={vrCorrectEvidenceId} setVrCorrectEvidenceId={setVrCorrectEvidenceId} vrCorrectSnippet={vrCorrectSnippet} setVrCorrectSnippet={setVrCorrectSnippet}
          vrAddEvidenceType={vrAddEvidenceType} setVrAddEvidenceType={setVrAddEvidenceType}
          runVrAdminReview={runVrAdminReview}
          vrMemoryList={vrMemoryList}
        />
      )}

      {tab === 'Training Pipeline' && (
        <>
          <p className="notice">
            MB-18 -- Multimodal Training Pipeline Center. A planning, validation, packaging, and
            reporting system only: it never starts a training job, never calls a training or
            quantization API, never creates a GGUF file, and never deploys or activates a runtime.
            It prepares a deterministic, checksummed package of JSON metadata files from
            already-certified MB-16 datasets and already-approved MB-17 grounded RAG memory. Package
            approval never implies model quality.
          </p>

          <div className="dataset-tabs">
            {tpSubTabs.map((t) => (
              <Button key={t} className={tpSubTab === t ? 'active' : ''} onClick={() => setTpSubTab(t)}>{t}</Button>
            ))}
          </div>

          {tpSubTab === 'Overview' && (
            <>
              {tpDiag && (
                <div className="notice">
                  <p><strong>Training started:</strong> {String(tpDiag.training_started)} -- <strong>Runtime activated:</strong> {String(tpDiag.runtime_activated)} -- <strong>Model weights produced:</strong> {String(tpDiag.model_weights_produced)}</p>
                  <p><strong>Requires certified datasets:</strong> {String(tpDiag.requires_certified_datasets)} -- <strong>Automatic approval:</strong> {String(tpDiag.automatic_approval)}</p>
                </div>
              )}
              {tpSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Topic" value={tpSessionData.topic.slice(0, 24)} tone="neutral" />
                  <StatusCard label="Stage" value={tpSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={tpSessionData.status} tone={tpSessionData.status.includes('reject') ? 'waiting' : tpSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Training pipeline sessions</h4>
                  <ul className="notice">
                    {tpSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={tpSelectedId === s.public_id ? 'active' : ''} onClick={() => selectTpSession(s.public_id)}>
                          {s.topic.slice(0, 30)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!tpSessionsList.length && <li>No training pipeline sessions yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitTpCreateSession}>
                    <label>Topic<input value={tpNewTopic} onChange={(e) => setTpNewTopic(e.target.value)} placeholder="Mountain scene multimodal package" /></label>
                    <Button type="submit" disabled={tpBusy || !tpNewTopic.trim()}>{tpBusy ? 'Working…' : 'Create session'}</Button>
                  </form>
                </div>
                <div>
                  {!tpSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
                  {tpSessionData && (
                    <>
                      <h4>Session events</h4>
                      <ul className="notice">
                        {tpEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!tpEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {tpSubTab === 'Sources' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'collect_datasets' && (
                    <form className="inline-form training-form" onSubmit={submitTpCollectDatasets}>
                      <label>MB-16 certified dataset session public ID(s), comma-separated
                        <input value={tpDatasetSessionIds} onChange={(e) => setTpDatasetSessionIds(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={tpBusy || !tpDatasetSessionIds.trim()}>Collect certified datasets</Button>
                    </form>
                  )}
                  {tpSessionData.dataset_collection_report?.ready !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.dataset_collection_report, null, 2)}</pre>
                  )}

                  {tpSessionData.stage === 'collect_rag_memory' && (
                    <form className="inline-form training-form" onSubmit={submitTpCollectRagMemory}>
                      <label>MB-17 approved RAG session public ID(s), comma-separated, optional
                        <input value={tpRagSessionIds} onChange={(e) => setTpRagSessionIds(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={tpBusy}>Collect grounded RAG memory</Button>
                    </form>
                  )}
                  {tpSessionData.rag_memory_collection_report?.accepted_count !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.rag_memory_collection_report, null, 2)}</pre>
                  )}

                  <h4>Available approved MB-17 RAG memory</h4>
                  <ul className="notice">
                    {tpAvailableRagMemory.map((m) => (
                      <li key={m.public_id}>{m.created_at} -- "{m.query?.slice(0, 40)}" -- {m.admin_decision} -- confidence {m.confidence}</li>
                    ))}
                    {!tpAvailableRagMemory.length && <li>No approved RAG memory recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {tpSubTab === 'Language' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'analyze_language' && (
                    <div className="notice">
                      <Button onClick={runTpAnalyzeLanguage} disabled={tpBusy}>Analyze language distribution</Button>
                    </div>
                  )}
                  {tpSessionData.language_distribution_report?.session_count !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.language_distribution_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {tpSubTab === 'Vision' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'analyze_vision' && (
                    <div className="notice">
                      <p>Aggregates MB-14's own real image metadata and MB-17's own confidence/hallucination fields -- no new detection or retrieval pass.</p>
                      <Button onClick={runTpAnalyzeVision} disabled={tpBusy}>Analyze vision &amp; grounding coverage</Button>
                    </div>
                  )}
                  {tpSessionData.image_statistics_report?.image_count !== undefined && (
                    <>
                      <h4>Image statistics</h4>
                      <pre className="notice">{JSON.stringify(tpSessionData.image_statistics_report, null, 2)}</pre>
                    </>
                  )}
                  {tpSessionData.grounding_quality_report?.query_count !== undefined && (
                    <>
                      <h4>Grounding quality</h4>
                      <pre className="notice">{JSON.stringify(tpSessionData.grounding_quality_report, null, 2)}</pre>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {tpSubTab === 'Tokenizer' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'analyze_tokenizer' && (
                    <div className="notice">
                      <p>No tokenizer model is loaded -- character-level and Unicode-category analysis only.</p>
                      <Button onClick={runTpAnalyzeTokenizer} disabled={tpBusy}>Analyze tokenizer coverage</Button>
                    </div>
                  )}
                  {tpSessionData.tokenizer_coverage_report?.total_character_count !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.tokenizer_coverage_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {tpSubTab === 'Splits' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'plan_splits' && (
                    <form className="inline-form training-form" onSubmit={submitTpPlanSplits}>
                      <label>Seed (optional, deterministic if repeated)<input value={tpSplitSeed} onChange={(e) => setTpSplitSeed(e.target.value)} placeholder="20260101" /></label>
                      <Button type="submit" disabled={tpBusy}>Plan dataset splits</Button>
                    </form>
                  )}
                  {tpSessionData.splits_report?.seed !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.splits_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {tpSubTab === 'Curriculum' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'plan_curriculum' && (
                    <div className="notice">
                      <Button onClick={runTpPlanCurriculum} disabled={tpBusy}>Plan curriculum &amp; training recipe</Button>
                    </div>
                  )}
                  {tpSessionData.curriculum_report?.stage_count !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.curriculum_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {tpSubTab === 'Hardware' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'estimate_hardware' && (
                    <div className="notice">
                      <p>All estimates are explicitly marked heuristic -- no benchmark is executed.</p>
                      <Button onClick={runTpEstimateHardware} disabled={tpBusy}>Estimate hardware &amp; storage</Button>
                    </div>
                  )}
                  {tpSessionData.hardware_estimate_report?.estimated_token_count !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.hardware_estimate_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {tpSubTab === 'Package' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'build_package' && (
                    <div className="notice">
                      <p>Writes deterministic JSON metadata files only -- never model weights -- to this session's own artifact directory, with a SHA-256 checksum recorded for every file.</p>
                      <Button onClick={runTpBuildPackage} disabled={tpBusy}>Build training package</Button>
                    </div>
                  )}
                  {tpSessionData.package_manifest?.artifact_count !== undefined && (
                    <pre className="notice">{JSON.stringify(tpSessionData.package_manifest, null, 2)}</pre>
                  )}
                  <h4>Package artifacts ({tpPackagesList.length})</h4>
                  <ul className="notice">
                    {tpPackagesList.map((p) => (
                      <li key={p.public_id}>{p.artifact_name} -- {p.file_size_bytes} bytes -- sha256={p.sha256.slice(0, 16)}…</li>
                    ))}
                    {!tpPackagesList.length && <li>No artifacts written yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {tpSubTab === 'Report' && (
            <>
              {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
              {tpSessionData && (
                <>
                  {tpSessionData.stage === 'generate_report' && (
                    <div className="notice">
                      <Button onClick={runTpGenerateReport} disabled={tpBusy}>Generate training readiness report</Button>
                    </div>
                  )}
                  {tpSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Training Readiness Report ready for review. No training has been executed by this
                      service -- package approval does not imply model quality.</p>
                      <pre className="notice">{JSON.stringify(tpSessionData.readiness_report, null, 2)}</pre>

                      <h4>Final decision</h4>
                      <Button onClick={() => runTpAdminReview('approve')} disabled={tpBusy}>Approve</Button>{' '}
                      <Button onClick={() => runTpAdminReview('reject')} disabled={tpBusy}>Reject</Button>{' '}
                      <Button onClick={() => runTpAdminReview('archive')} disabled={tpBusy}>Archive</Button>
                    </div>
                  )}
                  {tpSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Session closed with status <strong>{tpSessionData.status}</strong>. Permanent pipeline memory recorded.</p>
                    </div>
                  )}

                  <h4>Training pipeline memory (permanent)</h4>
                  <ul className="notice">
                    {tpMemoryList.map((m) => (
                      <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- readiness {m.readiness_score}</li>
                    ))}
                    {!tpMemoryList.length && <li>No pipeline memory recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {tpSubTab === 'History' && tpSessionData && (
            <>
              <h4>Session events</h4>
              <ul className="notice">
                {tpEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!tpEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {tpSubTab === 'History' && !tpSessionData && (
            <div className="notice">Select a session in Overview first.</div>
          )}

          {tpSubTab === 'Diagnostics' && (
            <>
              {tpDiag && <pre className="notice">{JSON.stringify(tpDiag, null, 2)}</pre>}
              {!tpDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Evaluation Center' && (
        <>
          <p className="notice">
            MB-19 -- Evaluation &amp; Benchmark Center. An evaluation-only system: it never trains,
            fine-tunes, exports GGUF, quantizes, deploys, or activates a runtime. It measures the
            quality of already-certified MB-16 datasets, already-approved MB-17 grounded RAG
            sessions, and already-built MB-18 training packages. Evaluation approval never
            guarantees production model quality.
          </p>

          <div className="dataset-tabs">
            {ecSubTabs.map((t) => (
              <Button key={t} className={ecSubTab === t ? 'active' : ''} onClick={() => setEcSubTab(t)}>{t}</Button>
            ))}
          </div>

          {ecSubTab === 'Overview' && (
            <>
              {ecDiag && (
                <div className="notice">
                  <p><strong>Training started:</strong> {String(ecDiag.training_started)} -- <strong>Runtime activated:</strong> {String(ecDiag.runtime_activated)} -- <strong>Model inference performed:</strong> {String(ecDiag.model_inference_performed)}</p>
                  <p><strong>Requires certified dataset:</strong> {String(ecDiag.requires_certified_dataset)} -- <strong>Automatic approval:</strong> {String(ecDiag.automatic_approval)}</p>
                </div>
              )}
              {ecSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Topic" value={ecSessionData.topic.slice(0, 24)} tone="neutral" />
                  <StatusCard label="Stage" value={ecSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={ecSessionData.status} tone={ecSessionData.status.includes('reject') ? 'waiting' : ecSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Evaluation sessions</h4>
                  <ul className="notice">
                    {ecSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={ecSelectedId === s.public_id ? 'active' : ''} onClick={() => selectEcSession(s.public_id)}>
                          {s.topic.slice(0, 30)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!ecSessionsList.length && <li>No evaluation sessions yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitEcCreateSession}>
                    <label>Topic<input value={ecNewTopic} onChange={(e) => setEcNewTopic(e.target.value)} placeholder="Mountain scene evaluation" /></label>
                    <Button type="submit" disabled={ecBusy || !ecNewTopic.trim()}>{ecBusy ? 'Working…' : 'Create session'}</Button>
                  </form>
                </div>
                <div>
                  {!ecSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
                  {ecSessionData && (
                    <>
                      <h4>Session events</h4>
                      <ul className="notice">
                        {ecEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!ecEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {ecSubTab === 'Sources' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'collect_datasets' && (
                    <form className="inline-form training-form" onSubmit={submitEcCollectDatasets}>
                      <label>MB-16 certified dataset session public ID(s), comma-separated
                        <input value={ecDatasetSessionIds} onChange={(e) => setEcDatasetSessionIds(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={ecBusy || !ecDatasetSessionIds.trim()}>Collect certified datasets</Button>
                    </form>
                  )}
                  {ecSessionData.dataset_collection_report?.accepted_count !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.dataset_collection_report, null, 2)}</pre>
                  )}

                  {ecSessionData.stage === 'collect_rag_sessions' && (
                    <form className="inline-form training-form" onSubmit={submitEcCollectRagSessions}>
                      <label>MB-17 approved RAG session public ID(s), comma-separated, optional
                        <input value={ecRagSessionIds} onChange={(e) => setEcRagSessionIds(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={ecBusy}>Collect approved RAG sessions</Button>
                    </form>
                  )}
                  {ecSessionData.rag_collection_report?.accepted_count !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.rag_collection_report, null, 2)}</pre>
                  )}

                  {ecSessionData.stage === 'collect_training_packages' && (
                    <form className="inline-form training-form" onSubmit={submitEcCollectTrainingPackages}>
                      <label>MB-18 approved training package session public ID(s), comma-separated, optional
                        <input value={ecPackageSessionIds} onChange={(e) => setEcPackageSessionIds(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={ecBusy}>Collect training packages</Button>
                    </form>
                  )}
                  {ecSessionData.package_collection_report?.accepted_count !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.package_collection_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {ecSubTab === 'Language' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'run_language_benchmarks' && (
                    <div className="notice">
                      <Button onClick={runEcLanguageBenchmarks} disabled={ecBusy}>Run language benchmarks</Button>
                    </div>
                  )}
                  {ecSessionData.language_benchmark_report?.records_analyzed !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.language_benchmark_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {ecSubTab === 'OCR' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'run_ocr_benchmarks' && (
                    <div className="notice">
                      <p>Reuses MB-14's own OCR cross-validator applied to MB-17's own already-retrieved evidence -- never a new OCR pass.</p>
                      <Button onClick={runEcOcrBenchmarks} disabled={ecBusy}>Run OCR benchmarks</Button>
                    </div>
                  )}
                  {ecSessionData.ocr_benchmark_report?.session_count !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.ocr_benchmark_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {ecSubTab === 'Grounding' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'run_grounding_retrieval_benchmarks' && (
                    <div className="notice">
                      <p>Grounding and retrieval benchmarks run together as one combined stage.</p>
                      <Button onClick={runEcGroundingRetrievalBenchmarks} disabled={ecBusy}>Run grounding &amp; retrieval benchmarks</Button>
                    </div>
                  )}
                  {ecSessionData.grounding_benchmark_report?.session_count !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.grounding_benchmark_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {ecSubTab === 'Retrieval' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && ecSessionData.retrieval_benchmark_report?.session_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.retrieval_benchmark_report, null, 2)}</pre>
              )}
              {ecSessionData && ecSessionData.retrieval_benchmark_report?.session_count === undefined && (
                <div className="notice">Run grounding &amp; retrieval benchmarks in the Grounding tab first.</div>
              )}
            </>
          )}

          {ecSubTab === 'Multimodal' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'run_multimodal_benchmarks' && (
                    <div className="notice">
                      <Button onClick={runEcMultimodalBenchmarks} disabled={ecBusy}>Run multimodal coverage benchmarks</Button>
                    </div>
                  )}
                  {ecSessionData.multimodal_benchmark_report?.total_record_count !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.multimodal_benchmark_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {ecSubTab === 'Package' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'run_package_benchmarks' && (
                    <div className="notice">
                      <p>Every checksum and file-existence check reads real files on disk -- this never modifies an MB-18 package.</p>
                      <Button onClick={runEcPackageBenchmarks} disabled={ecBusy}>Run package integrity benchmarks</Button>
                    </div>
                  )}
                  {ecSessionData.package_benchmark_report?.package_count !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.package_benchmark_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {ecSubTab === 'Regression' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'run_regression_comparison' && (
                    <form className="inline-form training-form" onSubmit={submitEcRegression}>
                      <label>Baseline evaluation session public ID (optional -- defaults to the most recent approved session)
                        <input value={ecBaselineSessionId} onChange={(e) => setEcBaselineSessionId(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={ecBusy}>Run regression comparison</Button>
                    </form>
                  )}
                  {ecSessionData.regression_report?.has_baseline !== undefined && (
                    <pre className="notice">{JSON.stringify(ecSessionData.regression_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {ecSubTab === 'Report' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  {ecSessionData.stage === 'generate_report' && (
                    <div className="notice">
                      <Button onClick={runEcGenerateReport} disabled={ecBusy}>Generate evaluation &amp; release readiness report</Button>
                    </div>
                  )}
                  {ecSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Evaluation Report ready for review. No model inference was ever performed by this
                      service -- evaluation approval does not guarantee production model quality.</p>
                      <p><strong>Release readiness:</strong> <span className={`pill ${ecSessionData.release_readiness.status === 'Ready' ? 'good' : ecSessionData.release_readiness.status === 'Blocked' ? 'block' : 'neutral'}`}>{ecSessionData.release_readiness.status}</span></p>
                      <pre className="notice">{JSON.stringify(ecSessionData.evaluation_report, null, 2)}</pre>

                      <h4>Final decision</h4>
                      <Button onClick={() => runEcAdminReview('approve')} disabled={ecBusy}>Approve</Button>{' '}
                      <Button onClick={() => runEcAdminReview('reject')} disabled={ecBusy}>Reject</Button>{' '}
                      <Button onClick={() => runEcAdminReview('archive')} disabled={ecBusy}>Archive</Button>
                    </div>
                  )}
                  {ecSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Session closed with status <strong>{ecSessionData.status}</strong>. Permanent evaluation memory recorded.</p>
                    </div>
                  )}

                  <h4>Evaluation memory (permanent)</h4>
                  <ul className="notice">
                    {ecMemoryList.map((m) => (
                      <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- score {m.overall_score} -- {m.release_readiness_status}</li>
                    ))}
                    {!ecMemoryList.length && <li>No evaluation memory recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {ecSubTab === 'Exports' && (
            <>
              {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
              {ecSessionData && (
                <>
                  <h4>Export artifacts ({ecExportsList.length})</h4>
                  <ul className="notice">
                    {ecExportsList.map((a) => (
                      <li key={a.artifact_name}>{a.artifact_name} -- {a.file_size_bytes} bytes -- sha256={a.sha256.slice(0, 16)}…</li>
                    ))}
                    {!ecExportsList.length && <li>No export artifacts written yet -- generate the report first.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {ecSubTab === 'History' && ecSessionData && (
            <>
              <h4>Session events</h4>
              <ul className="notice">
                {ecEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!ecEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {ecSubTab === 'History' && !ecSessionData && (
            <div className="notice">Select a session in Overview first.</div>
          )}

          {ecSubTab === 'Diagnostics' && (
            <>
              {ecDiag && <pre className="notice">{JSON.stringify(ecDiag, null, 2)}</pre>}
              {!ecDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Release Governance' && (
        <>
          <p className="notice">
            MB-20 -- Release Readiness &amp; Deployment Governance Center. A decision-and-governance
            layer only: it never deploys a model, starts an inference server or public chat, calls a
            runtime-manager start API, calls a Docker/Kubernetes deployment API, uploads weights
            anywhere, exports GGUF, or quantizes. It performs the final governance review of an
            already-certified MB-16 dataset, an already-approved MB-17 RAG session, an
            already-approved MB-18 training package, and an already-approved MB-19 evaluation.
            Approval never implies production safety.
          </p>

          <div className="dataset-tabs">
            {rgSubTabs.map((t) => (
              <Button key={t} className={rgSubTab === t ? 'active' : ''} onClick={() => setRgSubTab(t)}>{t}</Button>
            ))}
          </div>

          {rgSubTab === 'Overview' && (
            <>
              {rgDiag && (
                <div className="notice">
                  <p><strong>Model deployed:</strong> {String(rgDiag.model_deployed)} -- <strong>Runtime manager start called:</strong> {String(rgDiag.runtime_manager_start_called)} -- <strong>Production traffic enabled:</strong> {String(rgDiag.production_traffic_enabled)}</p>
                  <p><strong>Requires certified sources:</strong> {String(rgDiag.requires_certified_sources)} -- <strong>Automatic approval:</strong> {String(rgDiag.automatic_approval)}</p>
                </div>
              )}
              {rgSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Topic" value={rgSessionData.topic.slice(0, 24)} tone="neutral" />
                  <StatusCard label="Stage" value={rgSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={rgSessionData.status} tone={rgSessionData.status.includes('reject') ? 'waiting' : rgSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Release governance sessions</h4>
                  <ul className="notice">
                    {rgSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={rgSelectedId === s.public_id ? 'active' : ''} onClick={() => selectRgSession(s.public_id)}>
                          {s.topic.slice(0, 30)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!rgSessionsList.length && <li>No release governance sessions yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitRgCreateSession}>
                    <label>Topic<input value={rgNewTopic} onChange={(e) => setRgNewTopic(e.target.value)} placeholder="Mountain scene release" /></label>
                    <Button type="submit" disabled={rgBusy || !rgNewTopic.trim()}>{rgBusy ? 'Working…' : 'Create session'}</Button>
                  </form>
                </div>
                <div>
                  {!rgSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
                  {rgSessionData && (
                    <>
                      <h4>Session events</h4>
                      <ul className="notice">
                        {rgEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!rgEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {rgSubTab === 'Sources' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && (
                <>
                  {rgSessionData.stage === 'collect_datasets' && (
                    <form className="inline-form training-form" onSubmit={submitRgCollectDatasets}>
                      <label>MB-16 certified dataset session public ID(s), comma-separated
                        <input value={rgDatasetSessionIds} onChange={(e) => setRgDatasetSessionIds(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={rgBusy || !rgDatasetSessionIds.trim()}>Collect dataset evidence</Button>
                    </form>
                  )}
                  {rgSessionData.dataset_collection_report?.accepted_count !== undefined && (
                    <pre className="notice">{JSON.stringify(rgSessionData.dataset_collection_report, null, 2)}</pre>
                  )}

                  {rgSessionData.stage === 'collect_rag' && (
                    <form className="inline-form training-form" onSubmit={submitRgCollectRag}>
                      <label>MB-17 approved RAG session public ID(s), comma-separated, optional
                        <input value={rgRagSessionIds} onChange={(e) => setRgRagSessionIds(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={rgBusy}>Collect RAG evidence</Button>
                    </form>
                  )}
                  {rgSessionData.rag_collection_report?.accepted_count !== undefined && (
                    <pre className="notice">{JSON.stringify(rgSessionData.rag_collection_report, null, 2)}</pre>
                  )}

                  {rgSessionData.stage === 'collect_training_package' && (
                    <form className="inline-form training-form" onSubmit={submitRgCollectPackage}>
                      <label>MB-18 approved training package session public ID
                        <input value={rgPackageSessionId} onChange={(e) => setRgPackageSessionId(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={rgBusy || !rgPackageSessionId.trim()}>Collect training package</Button>
                    </form>
                  )}
                  {rgSessionData.training_package_collection_report?.accepted !== undefined && (
                    <pre className="notice">{JSON.stringify(rgSessionData.training_package_collection_report, null, 2)}</pre>
                  )}

                  {rgSessionData.stage === 'collect_evaluation' && (
                    <form className="inline-form training-form" onSubmit={submitRgCollectEvaluation}>
                      <label>MB-19 approved evaluation session public ID
                        <input value={rgEvaluationSessionId} onChange={(e) => setRgEvaluationSessionId(e.target.value)} />
                      </label>
                      <Button type="submit" disabled={rgBusy || !rgEvaluationSessionId.trim()}>Collect evaluation report</Button>
                    </form>
                  )}
                  {rgSessionData.evaluation_collection_report?.accepted !== undefined && (
                    <pre className="notice">{JSON.stringify(rgSessionData.evaluation_collection_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {rgSubTab === 'Safety' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && (
                <>
                  {rgSessionData.stage === 'run_safety_gates' && (
                    <div className="notice">
                      <p>Ten deterministic checks against already-computed MB-17/MB-18/MB-19 signals -- any failed gate affects the final recommendation, never silently overridden.</p>
                      <Button onClick={runRgSafety} disabled={rgBusy}>Run safety gates</Button>
                    </div>
                  )}
                  {rgSessionData.safety_gate_report?.overall_status !== undefined && (
                    <>
                      <p><strong>Overall status:</strong> <span className={`pill ${rgSessionData.safety_gate_report.overall_status === 'pass' ? 'good' : 'block'}`}>{rgSessionData.safety_gate_report.overall_status}</span></p>
                      <pre className="notice">{JSON.stringify(rgSessionData.safety_gate_report, null, 2)}</pre>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {rgSubTab === 'Compliance' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && (
                <>
                  {rgSessionData.stage === 'run_compliance_gates' && (
                    <div className="notice">
                      <p>A checklist only -- never a legal certification. Items not yet built at this stage (rollback plan, operator instructions, deployment prerequisites) are marked pending, not failing.</p>
                      <Button onClick={runRgCompliance} disabled={rgBusy}>Run compliance gates</Button>
                    </div>
                  )}
                  {rgSessionData.compliance_gate_report?.overall_status !== undefined && (
                    <pre className="notice">{JSON.stringify(rgSessionData.compliance_gate_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {rgSubTab === 'Benchmarks' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && (
                <>
                  {rgSessionData.stage === 'run_benchmark_gates' && (
                    <div className="notice">
                      <p>Consumes MB-19's own already-computed benchmark result rows -- never re-benchmarks anything.</p>
                      <Button onClick={runRgBenchmarks} disabled={rgBusy}>Run benchmark gates</Button>
                    </div>
                  )}
                  {rgSessionData.benchmark_gate_report?.overall_benchmark_status !== undefined && (
                    <pre className="notice">{JSON.stringify(rgSessionData.benchmark_gate_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {rgSubTab === 'Risks' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && (
                <>
                  {rgSessionData.stage === 'build_risk_rollback' && (
                    <div className="notice">
                      <p>One risk entry per failed safety gate, missing compliance item, and failed/marginal benchmark metric -- never a speculative risk.</p>
                      <Button onClick={runRgBuildRiskRollback} disabled={rgBusy}>Build risk register &amp; rollback plan</Button>
                    </div>
                  )}
                  {rgSessionData.risk_rollback_report?.risk_register && (
                    <>
                      <h4>Risk register ({rgSessionData.risk_rollback_report.risk_register.entry_count})</h4>
                      <pre className="notice">{JSON.stringify(rgSessionData.risk_rollback_report.risk_register, null, 2)}</pre>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {rgSubTab === 'Rollback' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && rgSessionData.risk_rollback_report?.rollback_plan && (
                <pre className="notice">{JSON.stringify(rgSessionData.risk_rollback_report.rollback_plan, null, 2)}</pre>
              )}
              {rgSessionData && !rgSessionData.risk_rollback_report?.rollback_plan && (
                <div className="notice">Build the risk register &amp; rollback plan in the Risks tab first.</div>
              )}
            </>
          )}

          {rgSubTab === 'Compatibility' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && rgSessionData.release_manifest?.compatibility_matrix && (
                <pre className="notice">{JSON.stringify(rgSessionData.release_manifest.compatibility_matrix, null, 2)}</pre>
              )}
              {rgSessionData && !rgSessionData.release_manifest?.compatibility_matrix && (
                <div className="notice">Build the release package in the Package tab first.</div>
              )}
            </>
          )}

          {rgSubTab === 'Prerequisites' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && rgSessionData.release_manifest?.deployment_prerequisites && (
                <pre className="notice">{JSON.stringify(rgSessionData.release_manifest.deployment_prerequisites, null, 2)}</pre>
              )}
              {rgSessionData && !rgSessionData.release_manifest?.deployment_prerequisites && (
                <div className="notice">Build the release package in the Package tab first.</div>
              )}
            </>
          )}

          {rgSubTab === 'Package' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && (
                <>
                  {rgSessionData.stage === 'build_release_package' && (
                    <div className="notice">
                      <p>Writes 12 deterministic JSON governance files to this session's own release directory, with a SHA-256 checksum recorded for every file. No model weights, no deployment.</p>
                      <Button onClick={runRgBuildPackage} disabled={rgBusy}>Build release decision package</Button>
                    </div>
                  )}
                  {rgSessionData.release_manifest?.artifact_count !== undefined && (
                    <pre className="notice">{JSON.stringify(rgSessionData.release_manifest, null, 2)}</pre>
                  )}
                  <h4>Release artifacts ({rgArtifactsList.length})</h4>
                  <ul className="notice">
                    {rgArtifactsList.map((a) => (
                      <li key={a.public_id}>{a.artifact_name} -- {a.file_size_bytes} bytes -- sha256={a.sha256.slice(0, 16)}…</li>
                    ))}
                    {!rgArtifactsList.length && <li>No artifacts written yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {rgSubTab === 'Report' && (
            <>
              {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
              {rgSessionData && (
                <>
                  {rgSessionData.stage === 'generate_report' && (
                    <div className="notice">
                      <Button onClick={runRgGenerateReport} disabled={rgBusy}>Generate release readiness report</Button>
                    </div>
                  )}
                  {rgSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Release Readiness Report ready for review. No deployment, runtime start, or
                      public traffic was ever performed by this service -- approval does not imply
                      production safety.</p>
                      <p><strong>Recommendation:</strong> <span className={`pill ${rgSessionData.readiness_report.final_recommendation === 'approved_for_release' ? 'good' : rgSessionData.readiness_report.final_recommendation === 'not_approved' ? 'block' : 'neutral'}`}>{rgSessionData.readiness_report.final_recommendation}</span> -- <strong>Score:</strong> {rgSessionData.readiness_report.overall_readiness_score}</p>
                      <pre className="notice">{JSON.stringify(rgSessionData.readiness_report, null, 2)}</pre>

                      <h4>Final decision</h4>
                      <Button onClick={() => runRgAdminReview('approve')} disabled={rgBusy}>Approve</Button>{' '}
                      <Button onClick={() => runRgAdminReview('reject')} disabled={rgBusy}>Reject</Button>{' '}
                      <Button onClick={() => runRgAdminReview('archive')} disabled={rgBusy}>Archive</Button>
                    </div>
                  )}
                  {rgSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Session closed with status <strong>{rgSessionData.status}</strong>. Permanent release memory recorded.</p>
                    </div>
                  )}

                  <h4>Release memory (permanent)</h4>
                  <ul className="notice">
                    {rgMemoryList.map((m) => (
                      <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- score {m.overall_readiness_score} -- {m.release_decision_status}</li>
                    ))}
                    {!rgMemoryList.length && <li>No release memory recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {rgSubTab === 'History' && rgSessionData && (
            <>
              <h4>Session events</h4>
              <ul className="notice">
                {rgEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!rgEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {rgSubTab === 'History' && !rgSessionData && (
            <div className="notice">Select a session in Overview first.</div>
          )}

          {rgSubTab === 'Diagnostics' && (
            <>
              {rgDiag && <pre className="notice">{JSON.stringify(rgDiag, null, 2)}</pre>}
              {!rgDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'External AI Gateway' && (
        <>
          <p className="notice">
            MB-21 -- External AI Evaluation Gateway. External AI providers are used strictly as
            evaluation assistants, never as autonomous decision-makers. This phase never trains a
            model, modifies weights, starts a runtime, deploys, approves a dataset, approves a
            release, or writes into Dataset Studio or Document Workspace. Every provider output
            remains untrusted candidate evidence until a human admin reviews it.
          </p>

          <div className="dataset-tabs">
            {gaSubTabs.map((t) => (
              <Button key={t} className={gaSubTab === t ? 'active' : ''} onClick={() => setGaSubTab(t)}>{t}</Button>
            ))}
          </div>

          {gaSubTab === 'Overview' && (
            <>
              {gaDiag && (
                <div className="notice">
                  <p><strong>Model deployed:</strong> {String(gaDiag.model_deployed)} -- <strong>Shell commands executed:</strong> {String(gaDiag.shell_commands_executed)} -- <strong>Provider calls require authorization:</strong> {String(gaDiag.provider_calls_require_authorization)}</p>
                  <p><strong>External AI output treated as:</strong> {gaDiag.external_ai_output_treated_as} -- <strong>Automatic approval:</strong> {String(gaDiag.automatic_approval)}</p>
                </div>
              )}
              {gaSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Topic" value={gaSessionData.topic.slice(0, 24)} tone="neutral" />
                  <StatusCard label="Purpose" value={gaSessionData.purpose} tone="neutral" />
                  <StatusCard label="Stage" value={gaSessionData.stage} tone="neutral" />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>External AI gateway sessions</h4>
                  <ul className="notice">
                    {gaSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={gaSelectedId === s.public_id ? 'active' : ''} onClick={() => selectGaSession(s.public_id)}>
                          {s.topic.slice(0, 26)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!gaSessionsList.length && <li>No external AI gateway sessions yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitGaCreateSession}>
                    <label>Topic<input value={gaNewTopic} onChange={(e) => setGaNewTopic(e.target.value)} placeholder="Mountain scene public evaluation" /></label>
                    <label>Purpose
                      <select value={gaNewPurpose} onChange={(e) => setGaNewPurpose(e.target.value)}>
                        <option value="public_style_stress_test">public_style_stress_test</option>
                        <option value="data_acquisition_assistance">data_acquisition_assistance</option>
                      </select>
                    </label>
                    <label>MB-16 dataset session public ID(s), comma-separated, optional<input value={gaNewDatasetIds} onChange={(e) => setGaNewDatasetIds(e.target.value)} /></label>
                    <label>MB-17 RAG session public ID, optional<input value={gaNewRagId} onChange={(e) => setGaNewRagId(e.target.value)} /></label>
                    <Button type="submit" disabled={gaBusy || !gaNewTopic.trim()}>{gaBusy ? 'Working…' : 'Create session'}</Button>
                  </form>
                </div>
                <div>
                  {!gaSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
                  {gaSessionData && (
                    <>
                      <h4>Session events</h4>
                      <ul className="notice">
                        {gaEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!gaEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {gaSubTab === 'Authorization' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && (
                <>
                  {gaSessionData.stage === 'validate_authorization' && (
                    <form className="inline-form training-form" onSubmit={submitGaAuthorize}>
                      <label>Explicit authorization reason (required before any provider is ever called)
                        <input value={gaAuthorizationNote} onChange={(e) => setGaAuthorizationNote(e.target.value)} placeholder="testing public-style stress evaluation for release readiness" />
                      </label>
                      <Button type="submit" disabled={gaBusy || !gaAuthorizationNote.trim()}>Authorize</Button>
                    </form>
                  )}
                  {gaSessionData.authorization_report?.authorized !== undefined && (
                    <pre className="notice">{JSON.stringify(gaSessionData.authorization_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {gaSubTab === 'Providers' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && (
                <>
                  {gaSessionData.stage === 'select_providers' && (
                    <form className="inline-form training-form" onSubmit={submitGaSelectProviders}>
                      <label>Requested provider key(s), comma-separated<input value={gaProviderKeys} onChange={(e) => setGaProviderKeys(e.target.value)} /></label>
                      <Button type="submit" disabled={gaBusy || !gaProviderKeys.trim()}>Select providers</Button>
                    </form>
                  )}
                  {gaSessionData.provider_selection_report?.selected_count !== undefined && (
                    <pre className="notice">{JSON.stringify(gaSessionData.provider_selection_report, null, 2)}</pre>
                  )}
                  {gaSessionData.stage === 'dispatch_requests' && (
                    <div className="notice">
                      <p>Dispatches the sanitized prompt to every selected provider. The full raw prompt is never persisted -- only its SHA-256 hash.</p>
                      <Button onClick={runGaDispatch} disabled={gaBusy}>Dispatch provider requests</Button>
                    </div>
                  )}
                  {gaSessionData.dispatch_report?.dispatched_count !== undefined && (
                    <pre className="notice">{JSON.stringify(gaSessionData.dispatch_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {gaSubTab === 'Sanitization' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && (
                <>
                  {gaSessionData.stage === 'sanitize_inputs' && gaSessionData.purpose === 'data_acquisition_assistance' && (
                    <form className="inline-form training-form" onSubmit={submitGaSanitize}>
                      <label>What data is missing? (admin-stated need)<input value={gaAdminStatedNeed} onChange={(e) => setGaAdminStatedNeed(e.target.value)} /></label>
                      <Button type="submit" disabled={gaBusy || !gaAdminStatedNeed.trim()}>Sanitize &amp; continue</Button>
                    </form>
                  )}
                  {gaSessionData.stage === 'sanitize_inputs' && gaSessionData.purpose === 'public_style_stress_test' && (
                    <div className="notice">
                      <p>Builds sanitized context from the session's own topic plus any linked MB-16/MB-17 sessions.</p>
                      <Button onClick={() => runGaAction(() => gaSanitize(gaSelectedId, ''))} disabled={gaBusy}>Sanitize inputs</Button>
                    </div>
                  )}
                  {gaSessionData.sanitization_report?.privacy_audit && (
                    <pre className="notice">{JSON.stringify(gaSessionData.sanitization_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {gaSubTab === 'Public Evaluation' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && gaSessionData.purpose !== 'public_style_stress_test' && (
                <div className="notice">This session's purpose is {gaSessionData.purpose}, not public_style_stress_test.</div>
              )}
              {gaSessionData && gaSessionData.purpose === 'public_style_stress_test' && gaSessionData.evidence_bundle?.recommendations && (
                <pre className="notice">{JSON.stringify(gaSessionData.evidence_bundle.recommendations, null, 2)}</pre>
              )}
              {gaSessionData && gaSessionData.purpose === 'public_style_stress_test' && !gaSessionData.evidence_bundle?.recommendations && (
                <div className="notice">Build the evidence bundle in the Evidence tab first.</div>
              )}
            </>
          )}

          {gaSubTab === 'Data Acquisition' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && gaSessionData.purpose !== 'data_acquisition_assistance' && (
                <div className="notice">This session's purpose is {gaSessionData.purpose}, not data_acquisition_assistance.</div>
              )}
              {gaSessionData && gaSessionData.purpose === 'data_acquisition_assistance' && gaSessionData.evidence_bundle?.recommendations && (
                <>
                  <p className="notice">Unverified candidate data only -- never inserted into Dataset Studio automatically.</p>
                  <pre className="notice">{JSON.stringify(gaSessionData.evidence_bundle.recommendations, null, 2)}</pre>
                </>
              )}
              {gaSessionData && gaSessionData.purpose === 'data_acquisition_assistance' && !gaSessionData.evidence_bundle?.recommendations && (
                <div className="notice">Build the evidence bundle in the Evidence tab first.</div>
              )}
            </>
          )}

          {gaSubTab === 'Provider Responses' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && (
                <>
                  {gaSessionData.stage === 'collect_responses' && (
                    <div className="notice">
                      <Button onClick={runGaCollect} disabled={gaBusy}>Collect provider responses</Button>
                    </div>
                  )}
                  {gaSessionData.stage === 'normalize_responses' && (
                    <div className="notice">
                      <Button onClick={runGaNormalize} disabled={gaBusy}>Normalize responses</Button>
                    </div>
                  )}
                  <h4>Provider runs ({gaProviderRunsList.length})</h4>
                  <ul className="notice">
                    {gaProviderRunsList.map((r) => (
                      <li key={r.public_id}><span className={`pill ${r.status === 'success' ? 'good' : 'block'}`}>{r.status}</span> {r.provider_key} -- {r.latency_ms}ms{r.error_message ? ` -- ${r.error_message}` : ''}</li>
                    ))}
                    {!gaProviderRunsList.length && <li>No provider runs yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {gaSubTab === 'Agreement' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && (
                <>
                  {gaSessionData.stage === 'analyze_agreement' && (
                    <div className="notice">
                      <p>No majority voting here ever produces an automatic truth decision.</p>
                      <Button onClick={runGaAnalyze} disabled={gaBusy}>Analyze agreement &amp; failures</Button>
                    </div>
                  )}
                  {gaSessionData.agreement_report?.agreement && (
                    <pre className="notice">{JSON.stringify(gaSessionData.agreement_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {gaSubTab === 'Evidence' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && (
                <>
                  {gaSessionData.stage === 'build_evidence' && (
                    <div className="notice">
                      <p>Only hashes of raw provider text are included by default.</p>
                      <Button onClick={runGaBuildEvidence} disabled={gaBusy}>Build evidence bundle</Button>
                    </div>
                  )}
                  {gaSessionData.evidence_bundle?.provider_metadata && (
                    <pre className="notice">{JSON.stringify(gaSessionData.evidence_bundle, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {gaSubTab === 'Report' && (
            <>
              {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
              {gaSessionData && (
                <>
                  {gaSessionData.stage === 'generate_report' && (
                    <div className="notice">
                      <Button onClick={runGaGenerateReport} disabled={gaBusy}>Generate evaluation report</Button>
                    </div>
                  )}
                  {gaSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Every provider output above is unverified candidate evidence. No dataset, release,
                      or training decision is made by this review.</p>
                      <p><strong>Confidence:</strong> <span className="pill neutral">{gaSessionData.gateway_report.confidence_level}</span></p>
                      <pre className="notice">{JSON.stringify(gaSessionData.gateway_report, null, 2)}</pre>

                      <h4>Final decision (marks this evaluation session's own findings only)</h4>
                      <Button onClick={() => runGaAdminReview('accept')} disabled={gaBusy}>Accept</Button>{' '}
                      <Button onClick={() => runGaAdminReview('reject')} disabled={gaBusy}>Reject</Button>{' '}
                      <Button onClick={() => runGaAdminReview('needs_followup')} disabled={gaBusy}>Needs Follow-up</Button>
                    </div>
                  )}
                  {gaSessionData.stage === 'reviewed' && (
                    <div className="notice">
                      <p>Reviewed with status <strong>{gaSessionData.status}</strong>.</p>
                      <Button onClick={runGaArchive} disabled={gaBusy}>Archive session</Button>
                    </div>
                  )}
                  {gaSessionData.stage === 'archived' && (
                    <div className="notice">Session archived.</div>
                  )}

                  <h4>External AI memory (permanent)</h4>
                  <ul className="notice">
                    {gaMemoryList.map((m) => (
                      <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- agreement {m.agreement_score}</li>
                    ))}
                    {!gaMemoryList.length && <li>No external AI memory recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {gaSubTab === 'History' && gaSessionData && (
            <>
              <h4>Session events</h4>
              <ul className="notice">
                {gaEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!gaEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {gaSubTab === 'History' && !gaSessionData && (
            <div className="notice">Select a session in Overview first.</div>
          )}

          {gaSubTab === 'Diagnostics' && (
            <>
              {gaDiag && <pre className="notice">{JSON.stringify(gaDiag, null, 2)}</pre>}
              {!gaDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Training Engine' && (
        <>
          <p className="notice">
            MB-22 -- Real Training Execution Engine. The first Mini Brain phase allowed to run a
            training workflow -- but only ever behind a fresh, per-job admin authorization token,
            never auto-started, never auto-deployed, never auto-promoted to production. Simulation
            mode is the only runtime that actually executes here; the real CPU/GPU adapters are
            honestly disclosed stubs. An existing checkpoint is never overwritten.
          </p>

          <div className="dataset-tabs">
            {teSubTabs.map((t) => (
              <Button key={t} className={teSubTab === t ? 'active' : ''} onClick={() => setTeSubTab(t)}>{t}</Button>
            ))}
          </div>

          {teSubTab === 'Overview' && (
            <>
              {teDiag && (
                <div className="notice">
                  <p><strong>Simulation mode available:</strong> {String(teDiag.simulation_mode_available)} -- <strong>Real CPU training available:</strong> {String(teDiag.real_cpu_training_available)} -- <strong>Real GPU training available:</strong> {String(teDiag.real_gpu_training_available)}</p>
                  <p><strong>Auto-start after package approval:</strong> {String(teDiag.auto_start_after_package_approval)} -- <strong>Checkpoints ever overwritten:</strong> {String(teDiag.existing_checkpoints_ever_overwritten)}</p>
                </div>
              )}
              {teJobData && (
                <section className="metric-grid">
                  <StatusCard label="Topic" value={teJobData.topic.slice(0, 24)} tone="neutral" />
                  <StatusCard label="Stage" value={teJobData.stage} tone="neutral" />
                  <StatusCard label="Status" value={teJobData.status} tone="neutral" />
                </section>
              )}
              {!teJobData && <div className="notice">Select or create a job in the Jobs sub-tab first.</div>}
              {teJobData && (
                <div className="notice">
                  <h4>Advance workflow</h4>
                  {teJobData.stage === 'validate_release' && <Button onClick={runTeValidateRelease} disabled={teBusy}>Validate release approval</Button>}
                  {teJobData.stage === 'validate_package' && <Button onClick={runTeValidatePackage} disabled={teBusy}>Validate training package</Button>}
                  {teJobData.stage === 'validate_authorization' && <p>Authorize this job in the Authorization sub-tab.</p>}
                  {teJobData.stage === 'plan_resources' && <p>Plan resources in the Resources sub-tab.</p>}
                  {teJobData.stage === 'build_manifest' && <p>Build the training manifest in the Manifest sub-tab.</p>}
                  {teJobData.stage === 'reserve_runtime' && <p>Reserve the runtime and start training in the Runtime sub-tab.</p>}
                  {teJobData.stage === 'start_training' && <p>Start training in the Runtime sub-tab.</p>}
                  {teJobData.stage === 'streaming_metrics' && <p>Stream metrics and save checkpoints, then finalize in the Report sub-tab.</p>}
                  {teJobData.stage === 'generate_report' && <p>Generate the final report in the Report sub-tab.</p>}
                  {teJobData.stage === 'awaiting_archive' && <p>Archive this job in the Archive sub-tab.</p>}
                  {teJobData.stage === 'cancelled' && <p>This job was cancelled. Archive it in the Archive sub-tab.</p>}
                  {teJobData.stage === 'archived' && <p>This job is archived.</p>}
                </div>
              )}
            </>
          )}

          {teSubTab === 'Jobs' && (
            <div className="training-grid">
              <div>
                <h4>Training jobs</h4>
                <ul className="notice">
                  {teJobsList.map((j) => (
                    <li key={j.public_id}>
                      <Button className={teSelectedId === j.public_id ? 'active' : ''} onClick={() => selectTeJob(j.public_id)}>
                        {j.topic.slice(0, 26)} -- {j.stage} ({j.status})
                      </Button>
                    </li>
                  ))}
                  {!teJobsList.length && <li>No training jobs yet.</li>}
                </ul>
                <form className="inline-form training-form" onSubmit={submitTeCreateJob}>
                  <label>Topic<input value={teNewTopic} onChange={(e) => setTeNewTopic(e.target.value)} placeholder="mountain river fine-tune" /></label>
                  <label>MB-18 training package session public ID<input value={teNewPackageId} onChange={(e) => setTeNewPackageId(e.target.value)} /></label>
                  <label>MB-20 release governance session public ID<input value={teNewReleaseId} onChange={(e) => setTeNewReleaseId(e.target.value)} /></label>
                  <label>Execution mode
                    <select value={teNewExecutionMode} onChange={(e) => setTeNewExecutionMode(e.target.value)}>
                      <option value="simulation">simulation</option>
                      <option value="cpu">cpu</option>
                      <option value="gpu">gpu</option>
                    </select>
                  </label>
                  <Button type="submit" disabled={teBusy || !teNewTopic.trim() || !teNewPackageId.trim() || !teNewReleaseId.trim()}>{teBusy ? 'Working…' : 'Create job'}</Button>
                </form>
              </div>
              <div>
                {!teJobData && <div className="notice">Select or create a job to work through it in the other sub-tabs.</div>}
                {teJobData && <pre className="notice">{JSON.stringify(teJobData, null, 2)}</pre>}
              </div>
            </div>
          )}

          {teSubTab === 'Authorization' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (
                <>
                  {teJobData.stage === 'validate_authorization' && (
                    <form className="inline-form training-form" onSubmit={submitTeAuthorize}>
                      <label>Explicit authorization reason (required before this job may ever start)
                        <input value={teAuthorizationReason} onChange={(e) => setTeAuthorizationReason(e.target.value)} placeholder="approved for CPU-first simulation training run" />
                      </label>
                      <Button type="submit" disabled={teBusy || !teAuthorizationReason.trim()}>Authorize</Button>
                    </form>
                  )}
                  {teJobData.authorization_report?.authorized !== undefined && (
                    <pre className="notice">{JSON.stringify(teJobData.authorization_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {teSubTab === 'Resources' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (
                <>
                  {teJobData.stage === 'plan_resources' && (
                    <div className="notice">
                      <p>Every figure here is heuristic -- never a real hardware benchmark.</p>
                      <Button onClick={runTePlanResources} disabled={teBusy}>Plan resources</Button>
                    </div>
                  )}
                  {teJobData.resource_plan_report?.execution_mode && (
                    <pre className="notice">{JSON.stringify(teJobData.resource_plan_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {teSubTab === 'Manifest' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (
                <>
                  {teJobData.stage === 'build_manifest' && (
                    <div className="notice">
                      <Button onClick={runTeBuildManifest} disabled={teBusy}>Build training manifest</Button>
                    </div>
                  )}
                  {teJobData.training_manifest?.fingerprint && (
                    <pre className="notice">{JSON.stringify(teJobData.training_manifest, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {teSubTab === 'Runtime' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (
                <>
                  {teJobData.stage === 'reserve_runtime' && (
                    <div className="notice">
                      <Button onClick={runTeReserveRuntime} disabled={teBusy}>Reserve runtime</Button>
                    </div>
                  )}
                  {teJobData.runtime_reservation_report?.reserved !== undefined && (
                    <pre className="notice">{JSON.stringify(teJobData.runtime_reservation_report, null, 2)}</pre>
                  )}
                  {teJobData.stage === 'start_training' && (
                    <div className="notice">
                      <Button onClick={runTeStart} disabled={teBusy}>Start training</Button>
                    </div>
                  )}
                  {teJobData.status === 'running' && (
                    <div className="notice">
                      <Button onClick={runTePause} disabled={teBusy}>Pause</Button>{' '}
                      <Button onClick={runTeCancel} disabled={teBusy}>Cancel</Button>
                    </div>
                  )}
                  {teJobData.status === 'paused' && (
                    <div className="notice">
                      <Button onClick={runTeResume} disabled={teBusy}>Resume</Button>{' '}
                      <Button onClick={runTeCancel} disabled={teBusy}>Cancel</Button>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {teSubTab === 'Metrics' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (
                <>
                  {teJobData.status === 'running' && (
                    <form className="inline-form training-form" onSubmit={submitTeStreamMetric}>
                      <label>Step<input type="number" min="0" value={teMetricStep} onChange={(e) => setTeMetricStep(e.target.value)} /></label>
                      <label>Epoch<input type="number" min="0" value={teMetricEpoch} onChange={(e) => setTeMetricEpoch(e.target.value)} /></label>
                      <Button type="submit" disabled={teBusy}>Stream metric</Button>
                    </form>
                  )}
                  <table>
                    <thead><tr><th>Step</th><th>Epoch</th><th>Loss</th><th>Learning rate</th><th>Tokens/sec</th></tr></thead>
                    <tbody>
                      {teMetricsList.map((m) => (
                        <tr key={m.public_id}><td>{m.step}</td><td>{m.epoch}</td><td>{m.loss}</td><td>{m.learning_rate}</td><td>{m.tokens_per_second}</td></tr>
                      ))}
                      {!teMetricsList.length && <tr><td colSpan="5">No metrics recorded yet.</td></tr>}
                    </tbody>
                  </table>
                </>
              )}
            </>
          )}

          {teSubTab === 'Checkpoints' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (
                <>
                  {(teJobData.status === 'running' || teJobData.status === 'paused') && (
                    <form className="inline-form training-form" onSubmit={submitTeSaveCheckpoint}>
                      <label>Step<input type="number" min="0" value={teCheckpointStep} onChange={(e) => setTeCheckpointStep(e.target.value)} /></label>
                      <label>Epoch<input type="number" min="0" value={teCheckpointEpoch} onChange={(e) => setTeCheckpointEpoch(e.target.value)} /></label>
                      <Button type="submit" disabled={teBusy}>Save checkpoint</Button>
                    </form>
                  )}
                  <ul className="notice">
                    {teCheckpointsList.map((c) => (
                      <li key={c.public_id}>{c.checkpoint_name} -- sha256 {c.sha256.slice(0, 16)}… -- {c.is_metadata_only ? 'metadata-only' : 'real file'}</li>
                    ))}
                    {!teCheckpointsList.length && <li>No checkpoints saved yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {teSubTab === 'Logs' && teJobData && (
            <>
              <h4>Job events</h4>
              <ul className="notice">
                {teEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!teEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {teSubTab === 'Logs' && !teJobData && (
            <div className="notice">Select a job in Jobs first.</div>
          )}

          {teSubTab === 'Report' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (
                <>
                  {(teJobData.status === 'running' || teJobData.status === 'paused') && (
                    <div className="notice">
                      <p>Only finalize may set this job's status to completed.</p>
                      <Button onClick={runTeFinalize} disabled={teBusy}>Finalize training</Button>
                    </div>
                  )}
                  {teJobData.stage === 'generate_report' && (
                    <div className="notice">
                      <Button onClick={runTeGenerateReport} disabled={teBusy}>Generate final report</Button>
                    </div>
                  )}
                  {teJobData.final_report?.disclaimer && (
                    <>
                      <p className="notice">{teJobData.final_report.disclaimer}</p>
                      <pre className="notice">{JSON.stringify(teJobData.final_report, null, 2)}</pre>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {teSubTab === 'Archive' && (
            <>
              {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
              {teJobData && (teJobData.status === 'completed' || teJobData.status === 'cancelled') && (
                <div className="notice">
                  <Button onClick={runTeArchive} disabled={teBusy}>Archive job</Button>
                </div>
              )}
              {teJobData && teJobData.status === 'archived' && <div className="notice">Job archived.</div>}
              {teJobData && !['completed', 'cancelled', 'archived'].includes(teJobData.status) && (
                <div className="notice">Archiving requires status completed or cancelled (currently {teJobData.status}).</div>
              )}
            </>
          )}

          {teSubTab === 'History' && (
            <>
              <h4>Training engine memory (permanent)</h4>
              <ul className="notice">
                {teMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.final_status} -- final loss {m.final_loss} -- {m.checkpoint_count} checkpoint(s)</li>
                ))}
                {!teMemoryList.length && <li>No training engine memory recorded yet.</li>}
              </ul>
            </>
          )}

          {teSubTab === 'Diagnostics' && (
            <>
              {teDiag && <pre className="notice">{JSON.stringify(teDiag, null, 2)}</pre>}
              {!teDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Public Chat Runtime' && (
        <>
          <p className="notice">
            MB-23 -- Public Chat Runtime &amp; Self-Improvement Feedback Loop. Every real answer is
            produced by the existing public chat router -- this phase only observes its already-
            computed signals to detect knowledge gaps, cluster repeated failures, and queue advisory
            improvement candidates. No raw message text is ever stored, only content hashes and
            already-sanitized signal text. Every candidate is born pending admin review and can only
            leave that status through an explicit review here -- nothing here starts MB-22 training,
            approves an MB-16/17/18/19/20 record, or dispatches an MB-21 provider.
          </p>

          <div className="dataset-tabs">
            {pcrSubTabs.map((t) => (
              <Button key={t} className={pcrSubTab === t ? 'active' : ''} onClick={() => setPcrSubTab(t)}>{t}</Button>
            ))}
          </div>

          {pcrSubTab === 'Overview' && (
            <>
              {pcrAnalyticsData && (
                <section className="metric-grid">
                  <StatusCard label="Total sessions" value={pcrAnalyticsData.total_sessions} tone="neutral" />
                  <StatusCard label="Total messages" value={pcrAnalyticsData.total_messages} tone="neutral" />
                  <StatusCard label="Pending candidates" value={pcrCandidatesList.length} tone="neutral" />
                </section>
              )}
              {pcrDiag && (
                <div className="notice">
                  <p><strong>Candidates require admin review:</strong> {String(pcrDiag.candidates_require_admin_review)} -- <strong>Automatic learning performed:</strong> {String(pcrDiag.automatic_learning_performed)} -- <strong>Automatic training performed:</strong> {String(pcrDiag.automatic_training_performed)}</p>
                  <p><strong>Raw message content stored:</strong> {String(pcrDiag.raw_message_content_stored)} -- <strong>Raw personal data stored:</strong> {String(pcrDiag.raw_personal_data_stored)}</p>
                </div>
              )}
            </>
          )}

          {pcrSubTab === 'Live Sessions' && (
            <div className="training-grid">
              <div>
                <h4>Active sessions</h4>
                <ul className="notice">
                  {pcrSessionsList.map((s) => (
                    <li key={s.public_id}>
                      <Button className={pcrSelectedSessionId === s.public_id ? 'active' : ''} onClick={() => selectPcrSession(s.public_id)}>
                        {s.public_id.slice(0, 8)}… -- {s.language} -- {s.message_count} msg(s) -- {s.unresolved_count} unresolved -- {s.started_at}
                      </Button>
                    </li>
                  ))}
                  {!pcrSessionsList.length && <li>No active sessions.</li>}
                </ul>
              </div>
              <div>
                {!pcrSessionData && <div className="notice">Select a session to inspect it.</div>}
                {pcrSessionData && <pre className="notice">{JSON.stringify(pcrSessionData, null, 2)}</pre>}
              </div>
            </div>
          )}

          {pcrSubTab === 'Conversations' && (
            <>
              {!pcrSessionData && <div className="notice">Select a session in Live Sessions first.</div>}
              {pcrSessionData && (
                <>
                  <p className="notice">No raw message text is stored -- only a content hash and derived flags per turn.</p>
                  <ul className="notice">
                    {pcrMessagesList.map((m) => (
                      <li key={m.public_id}>
                        {m.role} -- hash {m.content_hash.slice(0, 12)}… -- rag={String(m.used_rag)} vision={String(m.used_vision)} tool={String(m.used_tool)} -- route={m.route_used || 'n/a'} -- {m.created_at}
                      </li>
                    ))}
                    {!pcrMessagesList.length && <li>No messages yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {pcrSubTab === 'Analytics' && (
            <>
              {pcrAnalyticsData && <pre className="notice">{JSON.stringify(pcrAnalyticsData, null, 2)}</pre>}
              {!pcrAnalyticsData && <Skeleton lines={2} />}
            </>
          )}

          {pcrSubTab === 'Feedback Signals' && (
            <>
              {!pcrSessionData && <div className="notice">Select a session in Live Sessions first.</div>}
              {pcrSessionData && (
                <ul className="notice">
                  {pcrSignalsList.map((s) => (
                    <li key={s.public_id}>{s.signal_type} -- {s.severity} -- "{s.normalized_text.slice(0, 60)}" -- topic: {s.topic_key} -- {s.created_at}</li>
                  ))}
                  {!pcrSignalsList.length && <li>No feedback signals recorded for this session.</li>}
                </ul>
              )}
            </>
          )}

          {pcrSubTab === 'Failure Clusters' && (
            <ul className="notice">
              {pcrClustersList.map((c) => (
                <li key={c.topic_key}>
                  <strong>{c.topic_key}</strong> -- frequency {c.frequency} -- {c.distinct_session_count} session(s) --
                  severity {JSON.stringify(c.severity_counts)} -- types {JSON.stringify(c.signal_type_counts)} -- most recent {c.most_recent_at}
                </li>
              ))}
              {!pcrClustersList.length && <li>No repeated failure clusters yet.</li>}
            </ul>
          )}

          {pcrSubTab === 'Improvement Queue' && (
            <>
              <form className="inline-form training-form" onSubmit={submitPcrGenerateCandidates}>
                <label>Minimum cluster frequency
                  <input type="number" min="1" value={pcrMinFrequency} onChange={(e) => setPcrMinFrequency(e.target.value)} />
                </label>
                <Button type="submit" disabled={pcrBusy}>{pcrBusy ? 'Working…' : 'Generate candidates from clusters'}</Button>
              </form>
              <ul className="notice">
                {pcrCandidatesList.map((c) => (
                  <li key={c.public_id}>
                    <Button className={pcrSelectedCandidateId === c.public_id ? 'active' : ''} onClick={() => selectPcrCandidate(c.public_id)}>
                      {c.topic.slice(0, 30)} -- frequency {c.frequency} -- priority {c.priority_score} -- {c.recommended_action} -- {c.status}
                    </Button>
                  </li>
                ))}
                {!pcrCandidatesList.length && <li>No candidates pending review.</li>}
              </ul>
            </>
          )}

          {pcrSubTab === 'Candidate Review' && (
            <>
              {!pcrCandidateData && <div className="notice">Select a candidate in Improvement Queue first.</div>}
              {pcrCandidateData && (
                <>
                  <pre className="notice">{JSON.stringify(pcrCandidateData, null, 2)}</pre>
                  {pcrCandidateData.status === 'pending_admin_review' && (
                    <div className="notice">
                      <label>Review notes<input value={pcrReviewNotes} onChange={(e) => setPcrReviewNotes(e.target.value)} placeholder="optional notes" /></label>
                      <Button onClick={() => submitPcrReview('approve')} disabled={pcrBusy}>Approve</Button>
                      <Button onClick={() => submitPcrReview('reject')} disabled={pcrBusy}>Reject</Button>
                    </div>
                  )}
                  {pcrCandidateData.status !== 'pending_admin_review' && (
                    <div className="notice">This candidate was already reviewed: {pcrCandidateData.status}.</div>
                  )}
                  <h4>Candidate events</h4>
                  <ul className="notice">
                    {pcrCandidateEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!pcrCandidateEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {pcrSubTab === 'Admin Handoffs' && (
            <>
              <p className="notice">Advisory only -- approving a candidate here never creates, starts, or approves anything in MB-13/16/18/21/22; an admin must act on it manually through those phases' own workflows.</p>
              <ul className="notice">
                {pcrApprovedCandidatesList.map((c) => (
                  <li key={c.public_id}>
                    <strong>{c.topic}</strong> -- {c.handoff_report?.recommended_next_phase || 'n/a'}
                    <br />{c.handoff_report?.candidate_summary}
                    {c.handoff_report?.example_anonymized_questions?.length > 0 && (
                      <ul>
                        {c.handoff_report.example_anonymized_questions.map((q, i) => <li key={i}>{q}</li>)}
                      </ul>
                    )}
                  </li>
                ))}
                {!pcrApprovedCandidatesList.length && <li>No approved candidates yet.</li>}
              </ul>
            </>
          )}

          {pcrSubTab === 'Exports' && (
            <>
              <div className="notice">
                <Button onClick={runPcrExportAnalytics} disabled={pcrBusy}>Export analytics</Button>
                <Button onClick={runPcrExportCandidates} disabled={pcrBusy}>Export candidates</Button>
              </div>
              {pcrExportResult && <pre className="notice">{JSON.stringify(pcrExportResult, null, 2)}</pre>}
            </>
          )}

          {pcrSubTab === 'Runtime Diagnostics' && (
            <>
              {pcrDiag && <pre className="notice">{JSON.stringify(pcrDiag, null, 2)}</pre>}
              {!pcrDiag && <Skeleton lines={2} />}
            </>
          )}

          {pcrSubTab === 'Safety Monitor' && (
            <>
              {pcrDiag && (
                <ul className="notice">
                  <li>MB-22 training started or finalized: {String(pcrDiag.mb22_training_started_or_finalized)}</li>
                  <li>MB-16 dataset approvals performed: {String(pcrDiag.mb16_dataset_approvals_performed)}</li>
                  <li>MB-17 grounded answer approvals performed: {String(pcrDiag.mb17_grounded_answer_approvals_performed)}</li>
                  <li>MB-18 package approvals performed: {String(pcrDiag.mb18_package_approvals_performed)}</li>
                  <li>MB-19 evaluation approvals performed: {String(pcrDiag.mb19_evaluation_approvals_performed)}</li>
                  <li>MB-20 release approvals performed: {String(pcrDiag.mb20_release_approvals_performed)}</li>
                  <li>MB-21 provider dispatch performed: {String(pcrDiag.mb21_provider_dispatch_performed)}</li>
                  <li>Models deployed: {String(pcrDiag.models_deployed)}</li>
                  <li>Production models changed: {String(pcrDiag.production_models_changed)}</li>
                  <li>Shell commands executed: {String(pcrDiag.shell_commands_executed)}</li>
                </ul>
              )}
              <h4>Safety-flagged signals in current session</h4>
              <ul className="notice">
                {pcrSignalsList.filter((s) => s.signal_type === 'safety_flag').map((s) => (
                  <li key={s.public_id}>{s.created_at} -- {s.severity} -- {s.normalized_text.slice(0, 60)}</li>
                ))}
                {!pcrSignalsList.some((s) => s.signal_type === 'safety_flag') && <li>No safety-flag signals in the selected session.</li>}
              </ul>
            </>
          )}

          {pcrSubTab === 'History' && (
            <>
              <h4>Recently reviewed candidates</h4>
              <ul className="notice">
                {pcrApprovedCandidatesList.map((c) => (
                  <li key={c.public_id}>{c.reviewed_at} -- {c.topic.slice(0, 30)} -- {c.status} -- reviewed by {c.reviewed_by_admin_public_id}</li>
                ))}
                {!pcrApprovedCandidatesList.length && <li>No reviewed candidates yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {tab === 'Plugin Governance' && (
        <>
          <p className="notice">
            MB-24 -- Plugin &amp; Tool Runtime Governance Center. This is the policy, permission,
            consent, sandbox, audit, and execution-governance layer -- not a marketplace, not a
            deployment engine, not a real sandbox. No plugin binary is ever executed. Every plugin is
            born disabled and every permission is born ungranted; only an explicit admin action here
            can change either.
          </p>

          <div className="dataset-tabs">
            {pgSubTabs.map((t) => (
              <Button key={t} className={pgSubTab === t ? 'active' : ''} onClick={() => setPgSubTab(t)}>{t}</Button>
            ))}
          </div>

          {pgSubTab === 'Overview' && (
            <>
              {pgDiag && (
                <div className="notice">
                  <p><strong>Plugins start disabled:</strong> {String(pgDiag.plugins_start_disabled)} -- <strong>Auto-enable performed:</strong> {String(pgDiag.auto_enable_after_upload_performed)} -- <strong>Auto permission grant performed:</strong> {String(pgDiag.auto_permission_grant_performed)}</p>
                  <p><strong>Plugin binaries ever executed:</strong> {String(pgDiag.plugin_binaries_ever_executed)} -- <strong>Real sandbox/OS isolation exists:</strong> {String(pgDiag.real_sandbox_or_os_isolation_exists)}</p>
                </div>
              )}
              <section className="metric-grid">
                <StatusCard label="Registered plugins" value={pgPluginsList.length} tone="neutral" />
                <StatusCard label="Archived (permanent record)" value={pgMemoryList.length} tone="neutral" />
              </section>
              {!pgPluginData && <div className="notice">Select or register a plugin in the Plugin Registry sub-tab first.</div>}
              {pgPluginData && (
                <div className="notice">
                  <section className="metric-grid">
                    <StatusCard label="Name" value={pgPluginData.name.slice(0, 24)} tone="neutral" />
                    <StatusCard label="Stage" value={pgPluginData.stage} tone="neutral" />
                    <StatusCard label="Status" value={pgPluginData.status} tone="neutral" />
                    <StatusCard label="Risk level" value={pgPluginData.risk_level || 'n/a'} tone="neutral" />
                  </section>
                  <h4>Advance workflow</h4>
                  {pgPluginData.stage === 'register' && <Button onClick={runPgValidate} disabled={pgBusy}>Validate manifest</Button>}
                  {pgPluginData.stage === 'validate_manifest' && <Button onClick={runPgClassify} disabled={pgBusy}>Classify capabilities</Button>}
                  {pgPluginData.stage === 'classify_capabilities' && <Button onClick={runPgRiskScore} disabled={pgBusy}>Compute risk score</Button>}
                  {pgPluginData.stage === 'compute_risk' && <Button onClick={runPgSandbox} disabled={pgBusy}>Build sandbox profile</Button>}
                  {pgPluginData.stage === 'build_sandbox' && <Button onClick={runPgFilesystemPolicy} disabled={pgBusy}>Build filesystem policy</Button>}
                  {pgPluginData.stage === 'build_filesystem_policy' && <Button onClick={runPgNetworkPolicy} disabled={pgBusy}>Build network policy</Button>}
                  {pgPluginData.stage === 'build_network_policy' && pgPluginData.status === 'disabled' && (
                    <Button onClick={runPgEnable} disabled={pgBusy}>Enable plugin (admin review)</Button>
                  )}
                  {pgPluginData.stage === 'evaluate_permission' && <p>Evaluate and grant permissions in the Permissions sub-tab.</p>}
                  {pgPluginData.stage === 'grant_permission' && <p>Issue an execution token in the Runtime Events sub-tab.</p>}
                  {pgPluginData.stage === 'issue_token' && <p>Generate the governance report in the Reports sub-tab.</p>}
                  {pgPluginData.stage === 'governance_report' && <p>Disable and archive in the Runtime Events sub-tab.</p>}
                  {pgPluginData.stage === 'archived' && <p>This plugin is archived. See Reports for its permanent record.</p>}
                </div>
              )}
            </>
          )}

          {pgSubTab === 'Plugin Registry' && (
            <>
              <form className="inline-form training-form" onSubmit={submitPgRegister}>
                <label>Plugin ID<input value={pgForm.plugin_id} onChange={(e) => setPgForm({ ...pgForm, plugin_id: e.target.value })} required /></label>
                <label>Name<input value={pgForm.name} onChange={(e) => setPgForm({ ...pgForm, name: e.target.value })} required /></label>
                <label>Version<input value={pgForm.version} onChange={(e) => setPgForm({ ...pgForm, version: e.target.value })} required /></label>
                <label>Author<input value={pgForm.author} onChange={(e) => setPgForm({ ...pgForm, author: e.target.value })} /></label>
                <label>Description<input value={pgForm.description} onChange={(e) => setPgForm({ ...pgForm, description: e.target.value })} /></label>
                <label>Entrypoint<input value={pgForm.entrypoint} onChange={(e) => setPgForm({ ...pgForm, entrypoint: e.target.value })} required /></label>
                <label>Requested scopes (comma-separated)<input value={pgForm.requested_scopes} onChange={(e) => setPgForm({ ...pgForm, requested_scopes: e.target.value })} placeholder="filesystem.read.user_selected, network.http.allowed_domains" /></label>
                <label>Allowed domains (comma-separated)<input value={pgForm.allowed_domains} onChange={(e) => setPgForm({ ...pgForm, allowed_domains: e.target.value })} /></label>
                <label>Filesystem roots (comma-separated)<input value={pgForm.filesystem_roots} onChange={(e) => setPgForm({ ...pgForm, filesystem_roots: e.target.value })} /></label>
                <label>UI components (comma-separated)<input value={pgForm.ui_components} onChange={(e) => setPgForm({ ...pgForm, ui_components: e.target.value })} /></label>
                <label><input type="checkbox" checked={pgForm.local_storage_usage} onChange={(e) => setPgForm({ ...pgForm, local_storage_usage: e.target.checked })} /> Local storage usage</label>
                <label><input type="checkbox" checked={pgForm.cloud_storage_usage} onChange={(e) => setPgForm({ ...pgForm, cloud_storage_usage: e.target.checked })} /> Cloud storage usage</label>
                <label>Minimum Brud version<input value={pgForm.minimum_brud_version} onChange={(e) => setPgForm({ ...pgForm, minimum_brud_version: e.target.value })} /></label>
                <label>Signature placeholder<input value={pgForm.signature_placeholder} onChange={(e) => setPgForm({ ...pgForm, signature_placeholder: e.target.value })} /></label>
                <label>Homepage<input value={pgForm.homepage} onChange={(e) => setPgForm({ ...pgForm, homepage: e.target.value })} /></label>
                <label>Support URL<input value={pgForm.support_url} onChange={(e) => setPgForm({ ...pgForm, support_url: e.target.value })} /></label>
                <label>Source
                  <select value={pgForm.source} onChange={(e) => setPgForm({ ...pgForm, source: e.target.value })}>
                    <option value="manual_upload">manual_upload</option>
                    <option value="local_development">local_development</option>
                    <option value="marketplace_reference">marketplace_reference</option>
                  </select>
                </label>
                <Button type="submit" disabled={pgBusy}>{pgBusy ? 'Working…' : 'Register plugin'}</Button>
              </form>
              <ul className="notice">
                {pgPluginsList.map((p) => (
                  <li key={p.public_id}>
                    <Button className={pgSelectedPluginId === p.public_id ? 'active' : ''} onClick={() => selectPgPlugin(p.public_id)}>
                      {p.name} v{p.version} -- {p.stage} -- {p.status} -- risk: {p.risk_level || 'n/a'}
                    </Button>
                  </li>
                ))}
                {!pgPluginsList.length && <li>No plugins registered yet.</li>}
              </ul>
            </>
          )}

          {pgSubTab === 'Validation' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.validation_report, null, 2)}</pre>}
            </>
          )}

          {pgSubTab === 'Capabilities' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.capability_classification, null, 2)}</pre>}
            </>
          )}

          {pgSubTab === 'Risk Analysis' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && (
                <section className="metric-grid">
                  <StatusCard label="Risk score" value={pgPluginData.risk_score ?? 'n/a'} tone="neutral" />
                  <StatusCard label="Risk level" value={pgPluginData.risk_level || 'n/a'} tone="neutral" />
                </section>
              )}
            </>
          )}

          {pgSubTab === 'Sandbox' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.sandbox_profile, null, 2)}</pre>}
            </>
          )}

          {pgSubTab === 'Filesystem' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.filesystem_policy, null, 2)}</pre>}
            </>
          )}

          {pgSubTab === 'Network' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.network_policy, null, 2)}</pre>}
            </>
          )}

          {pgSubTab === 'Permissions' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && (
                <>
                  <form className="inline-form training-form" onSubmit={submitPgEvaluate}>
                    <label>Scope key<input value={pgEvalScopeKey} onChange={(e) => setPgEvalScopeKey(e.target.value)} placeholder="filesystem.read.user_selected" required /></label>
                    <label><input type="checkbox" checked={pgEvalIsPublicChat} onChange={(e) => setPgEvalIsPublicChat(e.target.checked)} /> Is public chat</label>
                    <label>User ID hash (optional)<input value={pgEvalUserIdHash} onChange={(e) => setPgEvalUserIdHash(e.target.value)} /></label>
                    <Button type="submit" disabled={pgBusy}>Evaluate permission</Button>
                    <Button type="button" onClick={runPgPolicyCheck} disabled={pgBusy || !pgEvalScopeKey}>Preview public policy check</Button>
                  </form>
                  {pgEvalResult && <pre className="notice">{JSON.stringify(pgEvalResult, null, 2)}</pre>}
                  {pgPolicyCheckResult && <pre className="notice">{JSON.stringify(pgPolicyCheckResult, null, 2)}</pre>}
                  <ul className="notice">
                    {pgPermissionsList.map((p) => (
                      <li key={p.public_id}>
                        {p.scope_key} -- decision: {p.decision} -- status: {p.status}
                        {p.status !== 'granted' && (
                          <Button onClick={() => runPgGrant(p.scope_key, pgEvalUserIdHash)} disabled={pgBusy}>Grant</Button>
                        )}
                        {p.status === 'granted' && (
                          <Button onClick={() => runPgRevoke(p.scope_key)} disabled={pgBusy}>Revoke</Button>
                        )}
                      </li>
                    ))}
                    {!pgPermissionsList.length && <li>No permission evaluations recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {pgSubTab === 'Consents' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && (
                <>
                  <form className="inline-form training-form" onSubmit={submitPgConsent}>
                    <label>Scope key<input value={pgConsentScopeKey} onChange={(e) => setPgConsentScopeKey(e.target.value)} required /></label>
                    <label>Raw user identity<input value={pgConsentUserIdentity} onChange={(e) => setPgConsentUserIdentity(e.target.value)} placeholder="never stored raw -- hashed immediately" required /></label>
                    <label><input type="checkbox" checked={pgConsentGiven} onChange={(e) => setPgConsentGiven(e.target.checked)} /> Consent given</label>
                    <label>TTL seconds (optional)<input value={pgConsentTtl} onChange={(e) => setPgConsentTtl(e.target.value)} /></label>
                    <Button type="submit" disabled={pgBusy}>Record consent</Button>
                  </form>
                  <ul className="notice">
                    {pgConsentsList.map((c) => (
                      <li key={c.public_id}>{c.scope_key} -- given: {String(c.consent_given)} -- user {c.user_id_hash.slice(0, 12)}… -- expires: {c.expires_at || 'never'}</li>
                    ))}
                    {!pgConsentsList.length && <li>No consent records yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {pgSubTab === 'Runtime Events' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && (
                <>
                  <form className="inline-form training-form" onSubmit={submitPgIssueToken}>
                    <label>Scope keys (comma-separated, must already be granted)<input value={pgTokenScopeKeys} onChange={(e) => setPgTokenScopeKeys(e.target.value)} required /></label>
                    <label>Raw user identity<input value={pgTokenUserIdentity} onChange={(e) => setPgTokenUserIdentity(e.target.value)} required /></label>
                    <label>Raw session identity<input value={pgTokenSessionIdentity} onChange={(e) => setPgTokenSessionIdentity(e.target.value)} required /></label>
                    <label>TTL seconds<input value={pgTokenTtl} onChange={(e) => setPgTokenTtl(e.target.value)} /></label>
                    <Button type="submit" disabled={pgBusy}>Issue execution token</Button>
                  </form>
                  {pgTokenResult && (
                    <div className="notice">
                      <p>Only the token hash is ever persisted -- shown once, here, and never stored raw.</p>
                      <pre>{JSON.stringify(pgTokenResult, null, 2)}</pre>
                    </div>
                  )}
                  <div className="notice">
                    <Button onClick={runPgReportExecution} disabled={pgBusy}>Record an external execution report</Button>
                    <Button onClick={runPgGenerateReport} disabled={pgBusy}>Generate governance report</Button>
                    {pgPluginData.status === 'enabled' && <Button onClick={runPgDisable} disabled={pgBusy}>Disable plugin</Button>}
                    {(pgPluginData.status === 'disabled' || pgPluginData.status === 'enabled') && (
                      <Button onClick={runPgArchive} disabled={pgBusy}>Archive plugin</Button>
                    )}
                  </div>
                  <h4>Event log</h4>
                  <ul className="notice">
                    {pgEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.stage || 'n/a'} -- {e.message}</li>)}
                    {!pgEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {pgSubTab === 'Reports' && (
            <>
              {!pgPluginData && <div className="notice">Select a plugin in the Plugin Registry first.</div>}
              {pgPluginData && <pre className="notice">{JSON.stringify(pgPluginData.governance_report, null, 2)}</pre>}
              <h4>Permanent archive record</h4>
              <ul className="notice">
                {pgMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- final_status: {m.final_status} -- granted: {m.total_permissions_granted} -- consents: {m.total_consents_recorded} -- events: {m.total_runtime_events} -- risk: {m.risk_level || 'n/a'}</li>
                ))}
                {!pgMemoryList.length && <li>No archived plugins yet.</li>}
              </ul>
            </>
          )}

          {pgSubTab === 'Diagnostics' && (
            <>
              {pgDiag && <pre className="notice">{JSON.stringify(pgDiag, null, 2)}</pre>}
              {!pgDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Plugin Runtime' && (
        <>
          <p className="notice">
            MB-25 -- Secure Plugin Execution Runtime. The first phase that actually runs plugin
            code -- but only an admin-approved, on-disk file loaded via <code>importlib</code>
            (never <code>eval</code>/<code>exec</code>, never a shell, never code from a chat
            message), and only after MB-24's own permission and consent decisions are re-derived
            fresh, from MB-24's own database records, on every single execution. No container or
            process isolation exists in this phase -- guards are cooperative, not adversarially
            enforced.
          </p>

          <div className="dataset-tabs">
            {prSubTabs.map((t) => (
              <Button key={t} className={prSubTab === t ? 'active' : ''} onClick={() => setPrSubTab(t)}>{t}</Button>
            ))}
          </div>

          {prSubTab === 'Overview' && (
            <>
              {prDiag && (
                <div className="notice">
                  <p><strong>Container isolation exists:</strong> {String(prDiag.container_isolation_exists)} -- <strong>Process isolation exists:</strong> {String(prDiag.process_isolation_exists)} -- <strong>Shell commands executed:</strong> {String(prDiag.shell_commands_executed)}</p>
                  <p><strong>Consent bypassed:</strong> {String(prDiag.consent_bypassed)} -- <strong>Admin review bypassed:</strong> {String(prDiag.admin_review_bypassed)} -- <strong>Admin-only scopes reachable from public chat:</strong> {String(prDiag.admin_only_scopes_accessible_from_public_chat)}</p>
                </div>
              )}
              {prStats && (
                <section className="metric-grid">
                  <StatusCard label="Total executions" value={prStats.total_executions} tone="neutral" />
                  <StatusCard label="Completed" value={prStats.executions_by_status?.completed || 0} tone="good" />
                  <StatusCard label="Denied" value={prStats.executions_by_status?.denied || 0} tone="warn" />
                  <StatusCard label="Avg duration (ms)" value={prStats.average_duration_ms ? prStats.average_duration_ms.toFixed(2) : 'n/a'} tone="neutral" />
                </section>
              )}
            </>
          )}

          {prSubTab === 'Execute' && (
            <>
              <p className="notice">
                Requires a real execution token issued from the Plugin Governance tab's Runtime
                Events sub-tab (<code>pgIssueToken</code>). Paste the full returned token JSON
                below -- only its hash is ever persisted, never the raw token.
              </p>
              <form className="inline-form training-form" onSubmit={submitPrExecute}>
                <label>Plugin public ID<input value={prExecForm.plugin_public_id} onChange={(e) => setPrExecForm({ ...prExecForm, plugin_public_id: e.target.value })} required /></label>
                <label>Scope key<input value={prExecForm.scope_key} onChange={(e) => setPrExecForm({ ...prExecForm, scope_key: e.target.value })} placeholder="network.http.allowed_domains" required /></label>
                <label>Arguments (JSON)<textarea rows={3} value={prExecForm.arguments} onChange={(e) => setPrExecForm({ ...prExecForm, arguments: e.target.value })} /></label>
                <label>Execution token (JSON)<textarea rows={4} value={prExecForm.execution_token} onChange={(e) => setPrExecForm({ ...prExecForm, execution_token: e.target.value })} required /></label>
                <label>Timeout seconds<input value={prExecForm.timeout_seconds} onChange={(e) => setPrExecForm({ ...prExecForm, timeout_seconds: e.target.value })} /></label>
                <Button type="submit" disabled={prBusy}>{prBusy ? 'Executing…' : 'Execute'}</Button>
              </form>
              {prExecResult && <pre className="notice">{JSON.stringify(prExecResult, null, 2)}</pre>}
            </>
          )}

          {prSubTab === 'Active Executions' && (
            <>
              <ul className="notice">
                {prExecutionsList.map((e) => (
                  <li key={e.public_id}>
                    <Button className={prSelectedExecutionId === e.public_id ? 'active' : ''} onClick={() => selectPrExecution(e.public_id)}>
                      {e.plugin_public_id.slice(0, 8)}… -- {e.execution_mode} -- {e.status} -- {e.scope_key}
                    </Button>
                    {e.status === 'pending' && prSelectedExecutionId === e.public_id && (
                      <Button onClick={runPrCancel} disabled={prBusy}>Cancel</Button>
                    )}
                  </li>
                ))}
                {!prExecutionsList.length && <li>No executions recorded yet.</li>}
              </ul>
            </>
          )}

          {prSubTab === 'Results' && (
            <>
              {!prExecutionData && <div className="notice">Select an execution in Active Executions first.</div>}
              {prExecutionData && (
                <>
                  <section className="metric-grid">
                    <StatusCard label="Status" value={prExecutionData.status} tone="neutral" />
                    <StatusCard label="Duration (ms)" value={prExecutionData.duration_ms ?? 'n/a'} tone="neutral" />
                  </section>
                  {prExecutionData.denial_reason && <div className="notice">Denial reason: {prExecutionData.denial_reason}</div>}
                  <h4>Sanitized input/output</h4>
                  <ul className="notice">
                    {(prLogs?.io || []).map((io) => (
                      <li key={io.public_id}>{io.io_type} -- truncated: {String(io.truncated)} -- redactions: {(io.redaction_categories || []).join(', ') || 'none'}<pre>{io.sanitized_payload?.text}</pre></li>
                    ))}
                    {!(prLogs?.io || []).length && <li>No sanitized input/output recorded yet.</li>}
                  </ul>
                  <div className="notice">
                    <Button onClick={runPrGenerateReport} disabled={prBusy}>Generate report</Button>
                    {['completed', 'failed', 'timeout', 'denied', 'cancelled'].includes(prExecutionData.status) && (
                      <Button onClick={runPrArchive} disabled={prBusy}>Archive execution</Button>
                    )}
                  </div>
                  {prReportResult && <pre className="notice">{JSON.stringify(prReportResult, null, 2)}</pre>}
                </>
              )}
            </>
          )}

          {prSubTab === 'Filesystem' && (
            <div className="notice">
              Filesystem access is governed entirely by MB-24's own <code>filesystem_policy</code>
              for the plugin being executed -- see the Plugin Governance tab's Filesystem sub-tab
              for the actual approved roots. Any path a plugin declares outside those roots is
              blocked before execution and shows up here as a <code>denied</code> execution whose
              <code>denial_reason</code> mentions &quot;outside every filesystem root&quot;.
            </div>
          )}

          {prSubTab === 'Network' && (
            <div className="notice">
              Network access is governed entirely by MB-24's own <code>network_policy</code>
              allowed-domains list for the plugin being executed -- see the Plugin Governance
              tab's Network sub-tab for the actual approved domains. Any domain a plugin declares
              outside that list is blocked before execution and shows up here as a
              <code>denied</code> execution whose <code>denial_reason</code> mentions &quot;not in
              the approved allowed_domains list&quot;.
            </div>
          )}

          {prSubTab === 'Permissions' && (
            <>
              <p className="notice">
                MB-25 never trusts a cached decision -- the scope's grant status is re-queried
                from MB-24's own permission records on every execution. A <code>denied</code>
                execution whose <code>denial_reason</code> mentions &quot;not currently
                granted&quot; means the permission gate failed.
              </p>
              {prExecutionData && (
                <div className="notice">Selected execution scope: <strong>{prExecutionData.scope_key}</strong> -- granted scopes at execution time: {(prExecutionData.granted_scopes || []).join(', ') || 'none'}</div>
              )}
            </>
          )}

          {prSubTab === 'Consents' && (
            <>
              <p className="notice">
                Consent validity (including expiry) is re-checked fresh from MB-24's own consent
                records on every execution. A <code>denied</code> execution whose
                <code>denial_reason</code> mentions &quot;requires valid&quot; means the consent
                gate failed.
              </p>
              {prExecutionData && (
                <div className="notice">Selected execution requester: {prExecutionData.requester_user_id_hash ? `${prExecutionData.requester_user_id_hash.slice(0, 12)}…` : 'n/a (admin-initiated)'}</div>
              )}
            </>
          )}

          {prSubTab === 'Public Chat' && (
            <>
              <p className="notice">
                Demonstrates the fully public <code>/api/public/plugin-runtime/execute</code>
                route (no admin auth, rate-limited) -- <code>execution_mode</code> is always
                forced to <code>public_chat</code> server-side.
              </p>
              <form className="inline-form training-form" onSubmit={submitPrPublicExecute}>
                <label>Plugin public ID<input value={prPublicForm.plugin_public_id} onChange={(e) => setPrPublicForm({ ...prPublicForm, plugin_public_id: e.target.value })} required /></label>
                <label>Scope key<input value={prPublicForm.scope_key} onChange={(e) => setPrPublicForm({ ...prPublicForm, scope_key: e.target.value })} required /></label>
                <label>Arguments (JSON)<textarea rows={3} value={prPublicForm.arguments} onChange={(e) => setPrPublicForm({ ...prPublicForm, arguments: e.target.value })} /></label>
                <label>Raw user identity<input value={prPublicForm.raw_user_identity} onChange={(e) => setPrPublicForm({ ...prPublicForm, raw_user_identity: e.target.value })} required /></label>
                <label>Execution token (JSON)<textarea rows={4} value={prPublicForm.execution_token} onChange={(e) => setPrPublicForm({ ...prPublicForm, execution_token: e.target.value })} required /></label>
                <Button type="submit" disabled={prBusy}>{prBusy ? 'Executing…' : 'Execute as public chat'}</Button>
              </form>
              {prPublicResult && <pre className="notice">{JSON.stringify(prPublicResult, null, 2)}</pre>}
            </>
          )}

          {prSubTab === 'Admin Assistant' && (
            <>
              <p className="notice">
                Admin Assistant executions pass through the exact same policy re-verification as
                any other caller -- Admin Assistant is not a bypass.
              </p>
              <ul className="notice">
                {prExecutionsList.filter((e) => e.execution_mode === 'admin_assistant').map((e) => (
                  <li key={e.public_id}>{e.public_id.slice(0, 8)}… -- {e.status} -- {e.scope_key} -- {e.created_at}</li>
                ))}
                {!prExecutionsList.filter((e) => e.execution_mode === 'admin_assistant').length && <li>No Admin Assistant executions yet.</li>}
              </ul>
            </>
          )}

          {prSubTab === 'Audit' && (
            <>
              {!prExecutionData && <div className="notice">Select an execution in Active Executions first.</div>}
              {prExecutionData && (
                <>
                  <Button onClick={runPrReportEvent} disabled={prBusy}>Record an admin note</Button>
                  <ul className="notice">
                    {(prLogs?.events || []).map((ev) => <li key={ev.public_id}>{ev.created_at} -- {ev.event_type} -- {ev.stage || 'n/a'} -- {ev.message}</li>)}
                    {!(prLogs?.events || []).length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {prSubTab === 'History' && (
            <ul className="notice">
              {prMemoryList.map((m) => (
                <li key={m.public_id}>{m.created_at} -- plugin {m.plugin_public_id.slice(0, 8)}… -- final_status: {m.final_status} -- duration: {m.duration_ms ?? 'n/a'}ms -- guard violations: {m.guard_violation_count} -- recorded by: {m.recorded_by}</li>
              ))}
              {!prMemoryList.length && <li>No archived executions yet.</li>}
            </ul>
          )}

          {prSubTab === 'Diagnostics' && (
            <>
              {prDiag && <pre className="notice">{JSON.stringify(prDiag, null, 2)}</pre>}
              {!prDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Voice Runtime' && (
        <>
          <p className="notice">
            MB-26 -- Voice &amp; Speech Runtime. Local-first speech-to-text and text-to-speech for
            Public Chat and the Admin Assistant, CPU-only, no GPU requirement. Microphone capture
            only ever runs while push-to-talk is actively held -- there is no wake-word listening,
            no background recording, and no cloud speech API by default. Public chat voice access
            requires explicit per-session consent; the Admin Assistant path requires real admin
            authorization. Every voice reply is generated by the same PublicChatRoutingService the
            text chat uses, and has already passed the existing text safety layer before it is
            ever spoken.
          </p>

          <div className="dataset-tabs">
            {voSubTabs.map((t) => (
              <Button key={t} className={voSubTab === t ? 'active' : ''} onClick={() => setVoSubTab(t)}>{t}</Button>
            ))}
          </div>

          {voSubTab === 'Overview' && (
            <>
              {voDiag && (
                <div className="notice">
                  <p><strong>STT backend:</strong> {voDiag.stt_backend} ({voDiag.stt_available ? 'available' : 'unavailable, using mock'}) -- <strong>TTS backend:</strong> {voDiag.tts_backend} ({voDiag.tts_available ? 'available' : 'unavailable, using mock'})</p>
                  <p><strong>Local only:</strong> {String(voDiag.local_only)} -- <strong>GPU required:</strong> {String(voDiag.gpu_required)} -- <strong>Wake-word enabled:</strong> {String(voDiag.wakeword_enabled)}</p>
                  <p><strong>Max record seconds:</strong> {voDiag.max_record_seconds} -- <strong>Max audio MB:</strong> {voDiag.max_audio_mb}</p>
                </div>
              )}
              {voStats && (
                <section className="metric-grid">
                  <StatusCard label="Total sessions" value={voStats.total_sessions} tone="neutral" />
                  <StatusCard label="Completed" value={voStats.sessions_by_status?.completed || 0} tone="good" />
                  <StatusCard label="Denied" value={voStats.sessions_by_status?.denied || 0} tone="warn" />
                  <StatusCard label="Active" value={voStats.sessions_by_status?.active || 0} tone="neutral" />
                </section>
              )}
            </>
          )}

          {voSubTab === 'Public Voice Chat' && (
            <>
              <label>
                <input type="checkbox" checked={voConsent} onChange={(e) => setVoConsent(e.target.checked)} />
                {' '}I consent to microphone capture for this voice session
              </label>
              <div className="notice">
                <Button
                  disabled={!voConsent || voBusy}
                  className={voRecording ? 'active' : ''}
                  onMouseDown={startVoRecording}
                  onMouseUp={stopVoRecordingAndSend}
                  onTouchStart={startVoRecording}
                  onTouchEnd={stopVoRecordingAndSend}
                >
                  {voRecording ? '● Recording -- release to send' : '🎤 Hold to talk'}
                </Button>
                {voRecording && <span className="notice"> Recording…</span>}
              </div>
              {voSessionData && (
                <div className="notice">
                  <p><strong>Transcript:</strong> {voSessionData.transcript || '(none yet)'}</p>
                  <p><strong>Reply:</strong> {voSessionData.reply || '(none yet)'}</p>
                  {voSessionData.tts_audio_relative_path && (
                    <p><strong>TTS output path:</strong> {voSessionData.tts_audio_relative_path}</p>
                  )}
                  {voSessionData.denial_reason && <p className="notice">Denied: {voSessionData.denial_reason}</p>}
                </div>
              )}
            </>
          )}

          {voSubTab === 'Admin Voice Assistant' && (
            <div className="notice">
              Admin Assistant voice access requires real admin authorization (the same session the
              dashboard is already logged into) -- there is no separate consent checkbox for this
              path, matching MB-26's admin-authorization-substitutes-for-consent design.
            </div>
          )}

          {voSubTab === 'Sessions' && (
            <>
              <select value={voSelectedSessionId} onChange={(e) => selectVoSession(e.target.value)}>
                <option value="">Select a session…</option>
                {voSessionsList.map((s) => (
                  <option key={s.public_id} value={s.public_id}>{s.created_at} -- {s.session_mode} -- {s.status}</option>
                ))}
              </select>
              {voSessionData && <pre className="notice">{JSON.stringify(voSessionData, null, 2)}</pre>}
            </>
          )}

          {voSubTab === 'STT' && (
            <>
              <Button disabled={voBusy} onClick={runVoTestStt}>Record 2s and run STT test</Button>
              {voTestSttText && <pre className="notice">{JSON.stringify(voTestSttText, null, 2)}</pre>}
            </>
          )}

          {voSubTab === 'TTS' && (
            <>
              <textarea
                value={voTestTtsForm.text}
                onChange={(e) => setVoTestTtsForm({ text: e.target.value })}
                placeholder="Text to synthesize"
              />
              <Button disabled={voBusy || !voTestTtsForm.text} onClick={runVoTestTts}>Run TTS test</Button>
              {voTestTtsResult && <pre className="notice">{JSON.stringify(voTestTtsResult, null, 2)}</pre>}
            </>
          )}

          {voSubTab === 'Permissions' && (
            <div className="notice">
              microphone.capture: high sensitivity, explicit per-session consent required for public
              chat, real admin authorization required for the Admin Assistant. plugin.storage.local
              and chat.read.current are allow-by-default for voice sessions.
            </div>
          )}

          {voSubTab === 'Diagnostics' && (
            <>
              {voDiag && <pre className="notice">{JSON.stringify(voDiag, null, 2)}</pre>}
              {!voDiag && <Skeleton lines={2} />}
            </>
          )}

          {voSubTab === 'Metrics' && (
            <>
              {voMetrics && <pre className="notice">{JSON.stringify(voMetrics, null, 2)}</pre>}
              {!voMetrics && <div className="notice">No metrics yet.</div>}
            </>
          )}

          {voSubTab === 'Events' && (
            <ul className="notice">
              {voEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.stage || 'n/a'} -- {e.message}</li>)}
              {!voEventsList.length && <li>No events yet.</li>}
            </ul>
          )}

          {voSubTab === 'Memory' && (
            <ul className="notice">
              {voMemoryList.map((m) => (
                <li key={m.public_id}>{m.created_at} -- {m.session_mode} -- final_status: {m.final_status} -- stt: {m.stt_backend_used || 'n/a'} -- tts: {m.tts_backend_used || 'n/a'} -- duration: {m.duration_ms ?? 'n/a'}ms</li>
              ))}
              {!voMemoryList.length && <li>No archived sessions yet.</li>}
            </ul>
          )}

          {voSubTab === 'Settings' && (
            <div className="notice">
              Max record seconds, max audio MB, and STT model size are configured via
              BRUD_VOICE_MAX_RECORD_SECONDS / BRUD_VOICE_MAX_AUDIO_MB / BRUD_VOICE_STT_MODEL_SIZE --
              see the Diagnostics sub-tab for the current effective values.
            </div>
          )}

          {voSubTab === 'History' && (
            <ul className="notice">
              {voMemoryList.map((m) => (
                <li key={m.public_id}>{m.created_at} -- session {m.session_id} -- {m.final_status}</li>
              ))}
              {!voMemoryList.length && <li>No history yet.</li>}
            </ul>
          )}
        </>
      )}

      {tab === 'Provider Settings' && (
        <>
          <p className="notice">
            MB-27 -- Secrets &amp; Provider Settings. Configuration only -- no inference, training,
            or deployment starts from this tab, and no outbound network call happens anywhere here
            except an explicit Test Connection press. API keys are encrypted with a local Fernet key
            (<code>BRUD_SECRET_ENCRYPTION_KEY</code>) before they are ever written to disk, and a
            stored key is never displayed again once saved -- only a masked indicator.
          </p>

          <div className="dataset-tabs">
            {psSubTabs.map((t) => (
              <Button key={t} className={psSubTab === t ? 'active' : ''} onClick={() => setPsSubTab(t)}>{t}</Button>
            ))}
          </div>

          {psSubTab === 'Overview' && (
            <>
              {psDiag && (
                <section className="metric-grid">
                  <StatusCard label="Encryption available" value={String(psDiag.encryption_available)} tone={psDiag.encryption_available ? 'good' : 'warn'} />
                  <StatusCard label="Configured providers" value={psDiag.configured_provider_count} tone="neutral" />
                  <StatusCard label="Enabled providers" value={psDiag.enabled_provider_count} tone="good" />
                  <StatusCard label="Unavailable providers" value={psDiag.unavailable_providers.length} tone="warn" />
                </section>
              )}
              {psDiag && psDiag.missing_encryption_key && (
                <div className="notice">
                  BRUD_SECRET_ENCRYPTION_KEY is not configured in this environment -- secrets cannot
                  be saved until an admin sets it. This is reported honestly, never silently worked
                  around by generating a key.
                </div>
              )}
            </>
          )}

          {psSubTab === 'External AI' && (
            <>
              {renderPsProviderCard('openrouter')}
              {renderPsProviderCard('openai')}
              {renderPsProviderCard('anthropic')}
              {renderPsProviderCard('gemini')}
            </>
          )}

          {psSubTab === 'OpenAI' && renderPsProviderCard('openai')}
          {psSubTab === 'Anthropic' && renderPsProviderCard('anthropic')}
          {psSubTab === 'Gemini' && renderPsProviderCard('gemini')}
          {psSubTab === 'OpenRouter' && renderPsProviderCard('openrouter')}

          {psSubTab === 'Speech' && (
            <>
              {renderPsProviderCard('faster_whisper')}
              {renderPsProviderCard('coqui_tts')}
            </>
          )}
          {psSubTab === 'STT' && renderPsProviderCard('faster_whisper')}
          {psSubTab === 'TTS' && renderPsProviderCard('coqui_tts')}

          {psSubTab === 'Local Models' && renderPsProviderCard('local_llm')}

          {psSubTab === 'Connection Tests' && (
            <ul className="notice">
              {Object.entries(psTestResults).map(([providerId, result]) => (
                <li key={providerId}>{result.provider_key} -- {result.status} -- {result.latency_ms}ms{result.error_message ? ` -- ${result.error_message}` : ''}</li>
              ))}
              {!Object.keys(psTestResults).length && <li>No connection tests run yet this session.</li>}
            </ul>
          )}

          {psSubTab === 'Audit' && (
            <ul className="notice">
              {psAuditList.map((e) => (
                <li key={e.public_id}>{e.created_at} -- {e.provider_key} -- {e.action} -- admin: {e.admin_id} -- fields: {e.changed_fields.join(', ') || 'n/a'}</li>
              ))}
              {!psAuditList.length && <li>No audit events yet.</li>}
            </ul>
          )}

          {psSubTab === 'Diagnostics' && (
            <>
              {psDiag && <pre className="notice">{JSON.stringify(psDiag, null, 2)}</pre>}
              {!psDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Assistant Intelligence' && (
        <>
          <p className="notice">
            MB-28 -- Real Mini Brain LLM Runtime &amp; Admin Assistant Intelligence Layer. Local-first,
            CPU-first reasoning for admins only -- prefers a local model, falls back to an external
            provider only when explicitly enabled in Provider Settings. Never used by Public Chat.
            / உள்ளூர் மாடல் இயக்கம் -- நிர்வாகிகளுக்கு மட்டும்.
          </p>

          {lrDiag && (
            <section className="metric-grid">
              <StatusCard
                label="Backend"
                value={lrDiag.local_available ? 'Local' : (lrDiag.external_fallback_enabled ? 'External' : 'Unavailable')}
                tone={lrDiag.local_available ? 'good' : (lrDiag.external_fallback_enabled ? 'neutral' : 'warn')}
              />
              <StatusCard label="llama-cpp-python installed" value={String(lrDiag.llama_cpp_installed)} tone={lrDiag.llama_cpp_installed ? 'good' : 'warn'} />
              <StatusCard label="Active sessions" value={lrDiag.active_session_count} tone="neutral" />
              <StatusCard label="Total messages" value={lrDiag.total_messages} tone="neutral" />
            </section>
          )}
          {lrDiag && !lrDiag.local_available && !lrDiag.external_fallback_enabled && (
            <div className="notice">
              No local model is configured and no external fallback is enabled -- the assistant will
              honestly report itself unavailable rather than fail silently. Configure a model under
              "Local Model Config" below, or enable an external provider in Provider Settings.
            </div>
          )}

          <div className="dataset-tabs">
            {lrSubTabs.map((t) => (
              <Button key={t} className={lrSubTab === t ? 'active' : ''} onClick={() => setLrSubTab(t)}>{t}</Button>
            ))}
          </div>

          {lrSubTab === 'Chat' && (
            <ChatPanel variant="full" admin={admin} toast={toast} />
          )}

          {lrSubTab === 'Explain Page' && (
            <form onSubmit={submitLrExplainPage} className="card">
              <label>Page ID</label>
              <input value={lrExplainPageForm.page_id} onChange={(e) => setLrExplainPageForm((prev) => ({ ...prev, page_id: e.target.value }))} placeholder="e.g. mini_brain" />
              <label>Nav Key</label>
              <input value={lrExplainPageForm.nav_key} onChange={(e) => setLrExplainPageForm((prev) => ({ ...prev, nav_key: e.target.value }))} placeholder="e.g. Brud Mini Brain" />
              <Button type="submit" disabled={lrBusy}>Explain this page</Button>
            </form>
          )}

          {lrSubTab === 'Summarize Report' && (
            <form onSubmit={submitLrSummarizeReport} className="card">
              <label>Report JSON</label>
              <textarea rows={6} value={lrReportForm} onChange={(e) => setLrReportForm(e.target.value)} />
              <Button type="submit" disabled={lrBusy}>Summarize current report</Button>
            </form>
          )}

          {lrSubTab === 'Summarize Regression' && (
            <form onSubmit={submitLrSummarizeRegression} className="card">
              <label>Regression Result JSON</label>
              <textarea rows={6} value={lrRegressionForm} onChange={(e) => setLrRegressionForm(e.target.value)} />
              <Button type="submit" disabled={lrBusy}>Summarize regression</Button>
            </form>
          )}

          {lrSubTab === 'Explain Error' && (
            <form onSubmit={submitLrExplainError} className="card">
              <label>Error message</label>
              <textarea rows={4} value={lrErrorForm} onChange={(e) => setLrErrorForm(e.target.value)} />
              <Button type="submit" disabled={lrBusy || !lrErrorForm.trim()}>Explain error</Button>
            </form>
          )}

          {lrSubTab === 'Next Actions' && (
            <>
              <form onSubmit={submitLrNextActions} className="card">
                <label>Status Snapshot JSON</label>
                <textarea rows={5} value={lrStatusSnapshotForm} onChange={(e) => setLrStatusSnapshotForm(e.target.value)} />
                <Button type="submit" disabled={lrBusy}>Next actions</Button>
              </form>
              {lrNextActionsResult && (
                <ul className="notice">
                  {lrNextActionsResult.map((a, i) => (
                    <li key={i}>[{a.severity}] {a.title} -- {a.reason}</li>
                  ))}
                </ul>
              )}
            </>
          )}

          {lrSubTab === 'Local Model Config' && (
            <div className="card">
              <p className="notice">
                Saved via Provider Settings' generic <code>config</code> field (no new backend route --
                this reuses MB-27's existing <code>PATCH /providers/{'{id}'}</code>).
              </p>
              <label>Model path (must resolve inside the allowed model directory)</label>
              <input
                value={lrLocalModelConfig.model_path}
                onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, model_path: e.target.value }))}
                placeholder="e.g. qwen2.5-0.5b-instruct-q4_k_m.gguf"
              />
              <label>Context length</label>
              <input type="number" value={lrLocalModelConfig.context_length} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, context_length: e.target.value }))} />
              <label>Max tokens</label>
              <input type="number" value={lrLocalModelConfig.max_tokens} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, max_tokens: e.target.value }))} />
              <label>Temperature</label>
              <input type="number" step="0.05" value={lrLocalModelConfig.temperature} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, temperature: e.target.value }))} />
              <label>Threads</label>
              <input type="number" value={lrLocalModelConfig.threads} onChange={(e) => setLrLocalModelConfig((prev) => ({ ...prev, threads: e.target.value }))} />
              <Button disabled={lrBusy} onClick={saveLrLocalModelConfig}>Save</Button>
            </div>
          )}

          {lrSubTab === 'Diagnostics' && (
            <>
              {lrDiag && <pre className="notice">{JSON.stringify(lrDiag, null, 2)}</pre>}
              {!lrDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Local Setup' && (
        <>
          <p className="notice">
            MB-29 -- Local Model Auto-Setup &amp; Provider Configuration Center. Detects hardware, scans
            admin-approved directories for GGUF files, and recommends a model -- nothing is ever
            downloaded automatically. / வன்பொருளைக் கண்டறிந்து, GGUF கோப்புகளை ஸ்கேன் செய்து, மாடலைப்
            பரிந்துரைக்கிறது -- எதுவும் தானாக பதிவிறக்கப்படாது.
          </p>

          <div className="dataset-tabs">
            {lcSubTabs.map((t) => (
              <Button key={t} className={lcSubTab === t ? 'active' : ''} onClick={() => setLcSubTab(t)}>{t}</Button>
            ))}
          </div>

          {lcSubTab === 'Hardware' && (
            <>
              {lcHardwareData && (
                <section className="metric-grid">
                  <StatusCard label="Total RAM" value={`${lcHardwareData.total_ram_gb} GB`} tone="neutral" />
                  <StatusCard label="Available RAM" value={`${lcHardwareData.available_ram_gb} GB`} tone="neutral" />
                  <StatusCard label="CPU cores / threads" value={`${lcHardwareData.cpu_cores} / ${lcHardwareData.cpu_threads}`} tone="neutral" />
                  <StatusCard label="Disk free" value={`${lcHardwareData.disk_free_gb} GB`} tone="neutral" />
                  <StatusCard label="RAM tier" value={lcHardwareData.recommended_ram_tier} tone="neutral" />
                  <StatusCard label="Health" value={lcHardwareData.health?.health} tone={lcHardwareData.health?.health === 'healthy' ? 'good' : (lcHardwareData.health?.health === 'unconfigured' ? 'neutral' : 'waiting')} />
                </section>
              )}
              {lcHardwareData && !lcHardwareData.psutil_available && (
                <p className="notice">psutil is not installed -- using the standard-library fallback for hardware figures.</p>
              )}
              {!lcHardwareData && <Skeleton lines={2} />}
            </>
          )}

          {lcSubTab === 'Local Models' && (
            <div className="card">
              <Button disabled={lcSetupBusy} onClick={runLcScan}>Scan for local models</Button>
              <table>
                <thead><tr><th>Filename</th><th>Family</th><th>Quant</th><th>Size (GB)</th><th /></tr></thead>
                <tbody>
                  {lcScannedModels.map((m) => (
                    <tr key={m.absolute_path}>
                      <td>{m.filename}</td><td>{m.inferred_family || '—'}</td><td>{m.inferred_quantization || '—'}</td>
                      <td>{m.size_gb}</td>
                      <td><Button onClick={() => selectLcScannedModel(m.absolute_path)}>Select</Button></td>
                    </tr>
                  ))}
                  {!lcScannedModels.length && <tr><td colSpan={5}>No scan run yet, or no GGUF files found.</td></tr>}
                </tbody>
              </table>
            </div>
          )}

          {lcSubTab === 'Recommendations' && (
            <div className="card">
              <Button disabled={lcSetupBusy} onClick={loadLcRecommendations}>Get recommendations</Button>
              {lcRecommendationsData && lcRecommendationsData.top_recommendation && (
                <div className="notice">
                  <strong>Best for this machine / இந்த கணினிக்கு சிறந்தது:</strong>{' '}
                  {lcRecommendationsData.top_recommendation.model_name} ({lcRecommendationsData.top_recommendation.quantization})
                  — ~{lcRecommendationsData.top_recommendation.expected_ram_usage_gb}GB RAM,
                  {' '}{lcRecommendationsData.top_recommendation.expected_speed.en} / {lcRecommendationsData.top_recommendation.expected_speed.ta}
                </div>
              )}
              <table>
                <thead><tr><th>Model</th><th>RAM (GB)</th><th>Speed</th><th>Tamil</th><th>Coding</th><th>Brud Admin</th></tr></thead>
                <tbody>
                  {(lcRecommendationsData?.models || []).map((m) => (
                    <tr key={m.model_name}>
                      <td>{m.model_name} ({m.quantization})</td><td>{m.expected_ram_usage_gb}</td>
                      <td>{m.expected_speed.en} / {m.expected_speed.ta}</td>
                      <td>{m.tamil_support.en} / {m.tamil_support.ta}</td>
                      <td>{m.coding_support.en} / {m.coding_support.ta}</td>
                      <td>{m.recommended_for_brud_admin.en} / {m.recommended_for_brud_admin.ta}</td>
                    </tr>
                  ))}
                  {!(lcRecommendationsData?.models || []).length && <tr><td colSpan={6}>Press "Get recommendations" above.</td></tr>}
                </tbody>
              </table>
            </div>
          )}

          {lcSubTab === 'Local Configuration' && (
            <div className="card">
              <label>Model path</label>
              <input value={lcLocalForm.model_path} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, model_path: e.target.value }))} placeholder="e.g. qwen2.5-1.5b-instruct-q4_k_m.gguf" />
              <label>Context length</label>
              <input type="number" value={lcLocalForm.context_length} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, context_length: e.target.value }))} />
              <label>Max tokens</label>
              <input type="number" value={lcLocalForm.max_tokens} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, max_tokens: e.target.value }))} />
              <label>Temperature</label>
              <input type="number" step="0.05" value={lcLocalForm.temperature} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, temperature: e.target.value }))} />
              <label>Threads</label>
              <input type="number" value={lcLocalForm.threads} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, threads: e.target.value }))} />
              <label>Additional model directories (one per line, optional)</label>
              <textarea rows={3} value={lcLocalForm.additional_model_dirs} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, additional_model_dirs: e.target.value }))} />
              <div>
                <Button disabled={lcSetupBusy} onClick={saveLcLocalModel}>Save</Button>
                <Button disabled={lcSetupBusy || !lcLocalForm.model_path} onClick={testLcLocalModel}>Test local model</Button>
              </div>
            </div>
          )}

          {lcSubTab === 'External Providers' && (
            <>
              {lcCatalog.map((p) => {
                const form = lcProviderForm(p.provider_key)
                return (
                  <div className="card" key={p.provider_key}>
                    <h4>{p.provider_key}</h4>
                    <p className="notice">Context window: {p.context_window} -- Reasoning: {p.reasoning_level.en} / {p.reasoning_level.ta} -- Cost: {p.cost_hint.en} / {p.cost_hint.ta}</p>
                    <label>API Key</label>
                    <input type="password" value={form.api_key} onChange={(e) => updateLcProviderForm(p.provider_key, { api_key: e.target.value })} placeholder="API Key / API விசையை உள்ளிடவும்" />
                    <label>Model</label>
                    <select value={form.model} onChange={(e) => updateLcProviderForm(p.provider_key, { model: e.target.value })}>
                      <option value="">-- select --</option>
                      {p.recommended_models.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                    <label>
                      <input type="checkbox" checked={form.enabled} onChange={(e) => updateLcProviderForm(p.provider_key, { enabled: e.target.checked })} />
                      {' '}Enabled / இயக்கப்பட்டது
                    </label>
                    <div>
                      <Button disabled={lcSetupBusy} onClick={() => saveLcProvider(p.provider_key)}>Save</Button>
                    </div>
                  </div>
                )
              })}
              {!lcCatalog.length && <Skeleton lines={2} />}
            </>
          )}

          {lcSubTab === 'Diagnostics' && (
            <>
              {lcDiag && <pre className="notice">{JSON.stringify(lcDiag, null, 2)}</pre>}
              {!lcDiag && <Skeleton lines={2} />}
            </>
          )}

          {lcSubTab === 'Setup Guide' && (
            <div className="card">
              <Button disabled={lcSetupBusy} onClick={loadLcGuide}>Build setup guide</Button>
              <ol>
                {(lcGuide?.steps || []).map((s) => (
                  <li key={s.step}>
                    <strong>{s.title_en} / {s.title_ta}</strong>
                    <p>{s.body_en}</p>
                    <p>{s.body_ta}</p>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {lcSubTab === 'Help' && (
            <ul className="clean-list">
              <li><strong>Hardware / வன்பொருள்:</strong> Shows RAM, CPU, disk, and a health badge. / RAM, CPU, வட்டு மற்றும் ஆரோக்கிய பதக்கத்தைக் காட்டுகிறது.</li>
              <li><strong>Local Models / உள்ளூர் மாடல்கள்:</strong> Scans admin-approved directories for .gguf files. / அனுமதிக்கப்பட்ட அடைவுகளில் .gguf கோப்புகளை ஸ்கேன் செய்கிறது.</li>
              <li><strong>Recommendations / பரிந்துரைகள்:</strong> Suggests the best model for your machine -- nothing downloads automatically. / உங்கள் கணினிக்கு சிறந்த மாடலைப் பரிந்துரைக்கிறது -- எதுவும் தானாக பதிவிறக்கப்படாது.</li>
              <li><strong>Local Configuration / உள்ளூர் அமைப்பு:</strong> Set the model path and runtime parameters. / மாடல் பாதை மற்றும் இயக்க அளவுருக்களை அமைக்கவும்.</li>
              <li><strong>External Providers / வெளிப்புற வழங்குநர்கள்:</strong> Optional cloud fallback providers. / விருப்பமான cloud மாற்று வழங்குநர்கள்.</li>
            </ul>
          )}
        </>
      )}

      {tab === 'Runtime Manager' && (
        <>
          <p className="notice">
            MB-30 -- Production Runtime Manager &amp; One-Click Local Model Lifecycle. Install, load,
            benchmark, and manage local GGUF models -- CPU-only, no GPU dependency, nothing downloads
            without an explicit click. / உள்ளூர் GGUF மாடல்களை நிறுவவும், ஏற்றவும், சோதிக்கவும் --
            வெளிப்படையான கிளிக் இல்லாமல் எதுவும் பதிவிறக்கப்படாது.
          </p>

          {rmStatusData && (
            <section className="metric-grid">
              <StatusCard label="Runtime" value={rmStatusData.loaded ? 'Loaded' : 'Not loaded'} tone={rmStatusData.loaded ? 'good' : 'neutral'} />
              <StatusCard label="Installed models" value={rmStatusData.installed_count} tone="neutral" />
              <StatusCard label="RAM tier" value={rmHardwareData?.recommended_ram_tier} tone="neutral" />
              <StatusCard label="Disk free" value={rmHardwareData ? `${rmHardwareData.disk_free_gb} GB` : '—'} tone="neutral" />
            </section>
          )}

          <div className="dataset-tabs">
            {rmSubTabs.map((t) => (
              <Button key={t} className={rmSubTab === t ? 'active' : ''} onClick={() => setRmSubTab(t)}>{t}</Button>
            ))}
          </div>

          {rmSubTab === 'Overview' && (
            <div className="card">
              <Button disabled={rmBusy} onClick={installRecommendedModel}>Install Recommended Model / பரிந்துரைக்கப்பட்ட மாடலை நிறுவவும்</Button>
              {rmStatusData?.current_model && (
                <pre className="notice">{JSON.stringify(rmStatusData.current_model, null, 2)}</pre>
              )}
            </div>
          )}

          {rmSubTab === 'Catalog' && (
            <table>
              <thead><tr><th>Model</th><th>Tier</th><th>RAM (GB)</th><th>Tamil</th><th /></tr></thead>
              <tbody>
                {rmCatalogData.map((m) => (
                  <tr key={m.model_id}>
                    <td>{m.display_name}</td><td>{m.tier}</td><td>{m.recommended_ram_gb}</td><td>{m.tamil_support}</td>
                    <td><Button onClick={() => setRmSelectedModelId(m.model_id)}>Select</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {rmSubTab === 'Installed' && (
            <table>
              <thead><tr><th>Model</th><th>Status</th><th>Size</th><th /></tr></thead>
              <tbody>
                {rmInstalledList.map((m) => (
                  <tr key={m.public_id}>
                    <td>{m.model_name}</td><td>{m.status}</td><td>{m.file_size_bytes ? Math.round(m.file_size_bytes / (1024*1024)) + ' MB' : '—'}</td>
                    <td><Button disabled={rmBusy} onClick={() => runRmRemove(m.model_name)}>Remove</Button></td>
                  </tr>
                ))}
                {!rmInstalledList.length && <tr><td colSpan={4}>No models installed yet.</td></tr>}
              </tbody>
            </table>
          )}

          {rmSubTab === 'Download' && (
            <div className="card">
              <label>Model ID</label>
              <input value={rmSelectedModelId} onChange={(e) => setRmSelectedModelId(e.target.value)} placeholder="e.g. qwen2.5-1.5b-instruct-q4_k_m" />
              <div>
                <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmDownload}>Download</Button>
                <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmVerify}>Verify</Button>
                <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmInstallSelected}>Install</Button>
              </div>
              {rmLastActionResult && <pre className="notice">{JSON.stringify(rmLastActionResult, null, 2)}</pre>}
            </div>
          )}

          {rmSubTab === 'Load / Unload' && (
            <div className="card">
              <label>Context length</label>
              <input type="number" value={rmLoadForm.context_length} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, context_length: e.target.value }))} />
              <label>Max tokens</label>
              <input type="number" value={rmLoadForm.max_tokens} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, max_tokens: e.target.value }))} />
              <label>Temperature</label>
              <input type="number" step="0.05" value={rmLoadForm.temperature} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, temperature: e.target.value }))} />
              <label>Threads</label>
              <input type="number" value={rmLoadForm.threads} onChange={(e) => setRmLoadForm((prev) => ({ ...prev, threads: e.target.value }))} />
              <div>
                <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmLoad}>Load</Button>
                <Button disabled={rmBusy} onClick={runRmUnload}>Unload</Button>
              </div>
            </div>
          )}

          {rmSubTab === 'Benchmark' && (
            <div className="card">
              <label>Prompt</label>
              <textarea rows={2} value={rmBenchmarkPrompt} onChange={(e) => setRmBenchmarkPrompt(e.target.value)} />
              <Button disabled={rmBusy || !rmSelectedModelId} onClick={runRmBenchmark}>Run Benchmark</Button>
              {rmLastBenchmarkResult && (
                <div className="notice">
                  Rating: {rmLastBenchmarkResult.rating_label?.en} / {rmLastBenchmarkResult.rating_label?.ta} --
                  {' '}{rmLastBenchmarkResult.tokens_per_second} tok/s -- {rmLastBenchmarkResult.peak_ram_mb} MB peak RAM
                </div>
              )}
            </div>
          )}

          {rmSubTab === 'Performance' && (
            <>
              {rmLastBenchmarkResult && <pre className="notice">{JSON.stringify(rmLastBenchmarkResult, null, 2)}</pre>}
              {!rmLastBenchmarkResult && <p className="notice">Run a benchmark to see performance data.</p>}
            </>
          )}

          {rmSubTab === 'Diagnostics' && (
            <>
              {rmHardwareData && <pre className="notice">{JSON.stringify(rmHardwareData, null, 2)}</pre>}
              {!rmHardwareData && <Skeleton lines={2} />}
            </>
          )}

          {rmSubTab === 'Events' && (
            <>
              <Button disabled={rmBusy} onClick={loadRmEvents}>Load events</Button>
              <ul className="notice">
                {rmEventsList.map((e) => (
                  <li key={e.public_id}>{e.created_at} -- {e.model_name || 'n/a'} -- {e.event_type}</li>
                ))}
                {!rmEventsList.length && <li>No events loaded yet.</li>}
              </ul>
            </>
          )}

          {rmSubTab === 'History' && (
            <>
              <Button disabled={rmBusy} onClick={loadRmHistory}>Load history</Button>
              <ul className="notice">
                {rmMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- {m.model_name || 'n/a'} -- {m.event_type}</li>
                ))}
                {!rmMemoryList.length && <li>No history loaded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {tab === 'Future Model' && (
        <div className="notice">
          <p>Brud AI now has a real local LLM runtime, added after this tab was first written in MB-01 --
          it lives across three other tabs, not here:</p>
          <ul>
            <li><b>Local Setup</b> -- detects your hardware and recommends a CPU-friendly GGUF model for it.</li>
            <li><b>Runtime Manager</b> -- installs, loads, unloads, and benchmarks that model with real RAM
            and disk guards before anything loads.</li>
            <li><b>Assistant Intelligence</b> -- where admin conversations actually run once a model is loaded,
            with a governed external-provider fallback configured separately in <b>Provider Settings</b>.</li>
          </ul>
          <p>The runtime is CPU-first -- no GPU is required -- and once a GGUF model is installed, it can
          answer entirely offline with no external network call.</p>
          <p>This tab's own five endpoints below are unrelated MB-01-era extension points, kept as
          documented placeholders and unchanged in shape -- they are not part of the real runtime above:</p>
          <ul>
            <li><code>POST /api/admin/mini-brain/inference</code> -- currently returns <code>available: false</code></li>
            <li><code>GET /api/admin/mini-brain/knowledge</code> -- currently returns <code>available: false</code></li>
            <li><code>GET /api/admin/mini-brain/memory</code> -- currently returns <code>available: false</code></li>
            <li><code>POST /api/admin/mini-brain/suggestions</code> -- currently returns <code>available: false</code></li>
            <li><code>GET /api/admin/mini-brain/context</code> -- Brud Context Interface, currently returns <code>available: false</code>; reserved for MB-02's Admin Dashboard / dataset / training / RAG workflow context provider</li>
          </ul>
        </div>
      )}
    </section>
  )
}
