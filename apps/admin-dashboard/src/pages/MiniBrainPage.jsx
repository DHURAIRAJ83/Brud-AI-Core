import { useEffect, useRef, useState } from 'react'
import Button from '../components/Button.jsx'
import ChatPanel from '../components/chat/ChatPanel.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusCard from '../components/StatusCard.jsx'
import { useToast } from '../components/Toast.jsx'
import DiagnosticsTab from './mini-brain/DiagnosticsTab.jsx'
import CapabilityTab from './mini-brain/CapabilityTab.jsx'
import DatasetIntelligenceTab from './mini-brain/DatasetIntelligenceTab.jsx'
import IntelligenceEngineTab from './mini-brain/IntelligenceEngineTab.jsx'
import KnowledgeCoreTab from './mini-brain/KnowledgeCoreTab.jsx'
import LearningSupervisorTab from './mini-brain/LearningSupervisorTab.jsx'
import LogsTab from './mini-brain/LogsTab.jsx'
import OverviewTab from './mini-brain/OverviewTab.jsx'
import ReleasePipelineTab from './mini-brain/ReleasePipelineTab.jsx'
import ResponseQualityTab from './mini-brain/ResponseQualityTab.jsx'
import RuntimeTab from './mini-brain/RuntimeTab.jsx'
import SettingsTab from './mini-brain/SettingsTab.jsx'
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
const rcSubTabs = [
  'Overview', 'Provider Registry', 'Research Requests', 'Consensus', 'Evidence', 'Dataset Draft',
  'RAG Status', 'Training Status', 'Reports', 'History', 'Diagnostics',
]
const deSubTabs = [
  'Overview', 'Knowledge Evolution', 'Dataset Evolution', 'Simulation', 'Recommendation & Report',
  'RAG Status', 'History', 'Diagnostics',
]
const pcSubTabs = [
  'Overview', 'Link Phases', 'RAG Gate', 'Readiness & Timeline', 'Prediction',
  'Recommendation & Report', 'History', 'Diagnostics',
]
const liSubTabs = [
  'Overview', 'Language Scan', 'Unicode & Character', 'Spell & Grammar', 'OCR', 'Tanglish',
  'Translation', 'Dataset Draft', 'Quality & Report', 'History', 'Diagnostics',
]
const viSubTabs = [
  'Overview', 'Image Extraction', 'Quality', 'Objects', 'OCR Compare', 'Caption', 'Annotation',
  'Knowledge Graph', 'QA', 'Vision Draft', 'Report', 'History', 'Diagnostics',
]
const vmSubTabs = [
  'Overview', 'Providers', 'Detection', 'Caption', 'Scene', 'Relationships', 'Corrections',
  'Learning Memory', 'Reports', 'History', 'Diagnostics',
]
const vmReviewActions = [
  'approve', 'reject', 'rename', 'split', 'merge', 'delete', 'add', 'move_box', 'resize_box', 'rotate_box',
]
const mdSubTabs = [
  'Overview', 'Sources', 'Images', 'Text', 'Conversation', 'Instructions', 'QA', 'Dataset Draft',
  'Quality', 'Reports', 'History', 'Diagnostics',
]
const vrSubTabs = [
  'Overview', 'Query', 'Results', 'Evidence', 'Images', 'OCR', 'Objects', 'Graph', 'Quality',
  'Hallucinations', 'History', 'Reports', 'Diagnostics',
]
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
        <>
          <p className="notice">
            MB-08 -- Continuous Learning &amp; Feedback Engine. Advisory only: observes real Public
            Chat routing/feedback evidence and the Knowledge Gap Registry, analyzes weaknesses, and
            prepares a report for admin approval. Never retrains, never edits a dataset, never
            modifies a checkpoint, never activates a model. Approving a report records the admin's
            judgment only -- nothing here automatically starts MB-06 or MB-07; an admin acts on the
            recommendations manually, through those phases' own UIs.
          </p>
          {clDiagnostics && (
            <div className="notice">
              <p><strong>Pipeline stages:</strong> {clDiagnostics.pipeline_stages.join(' -> ')}</p>
              <p><strong>Writes:</strong> {clDiagnostics.writes_scope}</p>
            </div>
          )}

          <div className="training-grid">
            <div>
              <h4>Learning cycles</h4>
              <ul className="notice">
                {clSessions.map((s) => (
                  <li key={s.public_id}>
                    <Button className={clSelectedId === s.public_id ? 'active' : ''} onClick={() => selectClSession(s.public_id)}>
                      {s.public_id.slice(0, 8)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!clSessions.length && <li>No learning cycles yet.</li>}
              </ul>

              <h4>New learning cycle</h4>
              <form className="inline-form training-form" onSubmit={submitClCreateSession}>
                <label>Cycle window (days, intent only -- see diagnostics)<input type="number" min="1" max="365" value={clCycleWindowDays} onChange={(e) => setClCycleWindowDays(Number(e.target.value))} /></label>
                <Button type="submit" disabled={clBusy}>{clBusy ? 'Working…' : 'Start learning cycle'}</Button>
              </form>
            </div>

            <div>
              {!clSession && <div className="notice">Select or start a learning cycle to see its workflow.</div>}

              {clSession && (
                <>
                  <section className="metric-grid">
                    <StatusCard label="Stage" value={clSession.stage} tone="neutral" />
                    <StatusCard label="Status" value={clSession.status} tone={clSession.status === 'admin_approved' ? 'good' : clSession.status === 'admin_rejected' ? 'waiting' : 'neutral'} />
                    <StatusCard label="Overall health" value={clSession.continuous_learning_report?.overall_health ?? 'not yet assessed'} tone={clSession.continuous_learning_report?.overall_health === 'Healthy' ? 'good' : clSession.continuous_learning_report?.overall_health === 'At Risk' ? 'waiting' : 'neutral'} />
                    <StatusCard label="Admin decision" value={clSession.admin_decision ?? 'pending'} tone={clSession.admin_decision === 'approve' ? 'good' : 'neutral'} />
                  </section>

                  {clSession.stage === 'feedback_collection' && (
                    <div className="notice">
                      <p>Stage 1: collect real Public Chat routing + feedback evidence (approved logs only -- no raw text is ever read).</p>
                      <Button onClick={runClCollectFeedback} disabled={clBusy}>Collect feedback</Button>
                    </div>
                  )}
                  {clSession.feedback_report?.total_conversations_observed !== undefined && (
                    <pre className="notice">{JSON.stringify(clSession.feedback_report, null, 2)}</pre>
                  )}

                  {clSession.stage === 'failure_analysis' && (
                    <div className="notice">
                      <p>Stage 2: classify failures -- no answer, blocked, timeout, low confidence, wrong answer.</p>
                      <Button onClick={runClAnalyzeFailures} disabled={clBusy}>Analyze failures</Button>
                    </div>
                  )}

                  {clSession.stage === 'hallucination_analysis' && (
                    <div className="notice">
                      <p>Stage 3: hallucination signal from the routing pipeline's own real evidence_status field.</p>
                      <Button onClick={runClAnalyzeHallucinations} disabled={clBusy}>Analyze hallucinations</Button>
                    </div>
                  )}

                  {clSession.stage === 'knowledge_gap_analysis' && (
                    <div className="notice">
                      <p>Stage 4: aggregate the existing Knowledge Gap Registry's own cases -- read-only, never writes back to it.</p>
                      <Button onClick={runClAnalyzeKnowledgeGaps} disabled={clBusy}>Analyze knowledge gaps</Button>
                    </div>
                  )}

                  {clSession.stage === 'weak_topic_detection' && (
                    <div className="notice">
                      <p>Stage 5: rank domains by a disclosed weakness index (no true per-domain accuracy % is measurable from real data today).</p>
                      <Button onClick={runClDetectWeakTopics} disabled={clBusy}>Detect weak topics</Button>
                    </div>
                  )}
                  {clSession.weak_topic_report?.topics && (
                    <pre className="notice">{JSON.stringify(clSession.weak_topic_report.topics, null, 2)}</pre>
                  )}

                  {clSession.stage === 'difficulty_analysis' && (
                    <div className="notice">
                      <p>Stage 6: Easy/Medium/Hard/Expert/Unknown, reusing MB-05.1's difficulty scoring unchanged.</p>
                      <Button onClick={runClAnalyzeDifficulty} disabled={clBusy}>Analyze difficulty</Button>
                    </div>
                  )}

                  {clSession.stage === 'dataset_recommendation' && (
                    <div className="notice">
                      <p>Stage 7: recommend dataset formats per weak domain, each with a WHY.</p>
                      <Button onClick={runClRecommendDatasets} disabled={clBusy}>Recommend datasets</Button>
                    </div>
                  )}

                  {clSession.stage === 'training_recommendation' && (
                    <div className="notice">
                      <p>Stage 8: No Training / Fine Tune / Continue Training / Full Retraining, with WHY.</p>
                      <Button onClick={runClRecommendTraining} disabled={clBusy}>Recommend training action</Button>
                    </div>
                  )}

                  {clSession.stage === 'priority_ranking' && !clSession.continuous_learning_report?.overall_health && (
                    <div className="notice">
                      <p>Stage 9: rank recommendations using the Knowledge Gap Registry's own real priority scores.</p>
                      <Button onClick={runClRankPriorities} disabled={clBusy}>Rank priorities</Button>
                    </div>
                  )}
                  {clSession.stage === 'priority_ranking' && clSession.priority_report?.training_recommendation && (
                    <div className="notice">
                      <p>Stage 10: assemble the final Continuous Learning Report.</p>
                      <Button onClick={runClGenerateReport} disabled={clBusy}>Generate report</Button>
                    </div>
                  )}

                  {clSession.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Admin reviews the full Continuous Learning Report and decides.</p>
                      <pre className="notice">{JSON.stringify(clSession.continuous_learning_report, null, 2)}</pre>
                      <Button onClick={() => runClAdminReview('reject')} disabled={clBusy}>Reject</Button>{' '}
                      <Button onClick={() => runClAdminReview('approve')} disabled={clBusy}>Approve</Button>
                    </div>
                  )}

                  {clSession.stage === 'closed' && (
                    <div className="notice">
                      <p>Cycle closed with status <strong>{clSession.status}</strong>. No automatic action was taken.</p>
                    </div>
                  )}

                  <h4>Cycle events</h4>
                  <ul className="notice">
                    {clEvents.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!clEvents.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {tab === 'Continuous Learning Center' && (
        <>
          <p className="notice">
            MB-09 -- Continuous Learning Center. A planning and recommendation layer only: it is not a
            Training Engine, Dataset Generator, or Model Runtime. It continuously analyzes completed
            MB-08 reports, discovers recurring knowledge gaps, prepares learning plans and draft
            outlines, plans multi-provider consensus requests, and recommends the next learning cycle.
            Nothing here automatically modifies a dataset, calls an external AI provider, triggers RAG,
            starts MB-06, launches MB-07, or trains a model -- every downstream action stays behind
            explicit admin approval.
          </p>
          {clcDiag && (
            <div className="notice">
              <p><strong>External providers called:</strong> {String(clcDiag.external_providers_called)} -- Brud AI has no Claude/OpenAI/Gemini/OpenRouter integration; provider outputs must be collected externally and supplied back.</p>
              <p><strong>Writes:</strong> {clcDiag.writes_scope}</p>
            </div>
          )}

          <h4>Learning Memory (permanent history)</h4>
          <div className="notice">
            <ul>
              {clcMemoryItems.map((m) => (
                <li key={m.public_id}>{m.created_at} -- weak: {m.weak_domains.join(', ') || 'none'} -- training decision: {m.training_decision ?? 'n/a'} -- {m.improvement_notes}</li>
              ))}
              {!clcMemoryItems.length && <li>No memory entries recorded yet.</li>}
            </ul>
            <form className="inline-form training-form" onSubmit={submitClcRecordMemory}>
              <label>MB-08 session public ID<input value={clcMemoryForm.continuous_learning_session_public_id} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, continuous_learning_session_public_id: e.target.value })} /></label>
              <label>Model version public ID (optional)<input value={clcMemoryForm.model_version_public_id} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, model_version_public_id: e.target.value })} /></label>
              <label>Dataset version public ID (optional)<input value={clcMemoryForm.dataset_version_public_id} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, dataset_version_public_id: e.target.value })} /></label>
              <label>Improvement notes<input value={clcMemoryForm.improvement_notes} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, improvement_notes: e.target.value })} /></label>
              <Button type="submit" disabled={clcBusy || !clcMemoryForm.continuous_learning_session_public_id}>Record memory</Button>
            </form>
          </div>

          <div className="training-grid">
            <div>
              <h4>Planning cycles</h4>
              <ul className="notice">
                {clcSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={clcSelectedId === s.public_id ? 'active' : ''} onClick={() => selectClcSession(s.public_id)}>
                      {s.public_id.slice(0, 8)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!clcSessionsList.length && <li>No planning cycles yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitClcCreateSession}>
                <Button type="submit" disabled={clcBusy}>{clcBusy ? 'Working…' : 'Start planning cycle'}</Button>
              </form>
            </div>

            <div>
              {!clcSessionData && <div className="notice">Select or start a planning cycle to see its workflow.</div>}

              {clcSessionData && (
                <>
                  <section className="metric-grid">
                    <StatusCard label="Stage" value={clcSessionData.stage} tone="neutral" />
                    <StatusCard label="Status" value={clcSessionData.status} tone={clcSessionData.status.includes('reject') ? 'waiting' : clcSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                    <StatusCard label="Admin decision" value={clcSessionData.admin_decision ?? 'pending'} tone={clcSessionData.admin_decision ? 'good' : 'neutral'} />
                  </section>

                  {clcSessionData.stage === 'knowledge_gap_evolution' && (
                    <div className="notice">
                      <p>Knowledge Gap Evolution: compares recent MB-08 reports for recurring weaknesses.</p>
                      <Button onClick={runClcEvolveKnowledgeGaps} disabled={clcBusy}>Evolve knowledge gaps</Button>
                    </div>
                  )}
                  {clcSessionData.knowledge_gap_evolution_report?.recurring_weak_domains && (
                    <pre className="notice">{JSON.stringify(clcSessionData.knowledge_gap_evolution_report.recurring_weak_domains, null, 2)}</pre>
                  )}

                  {clcSessionData.stage === 'learning_queue' && (
                    <div className="notice">
                      <p>Learning Queue: prioritized topics only -- never creates a dataset.</p>
                      <Button onClick={runClcBuildLearningQueue} disabled={clcBusy}>Build learning queue</Button>
                    </div>
                  )}
                  {clcSessionData.learning_queue_report?.queue && (
                    <pre className="notice">{JSON.stringify(clcSessionData.learning_queue_report.queue, null, 2)}</pre>
                  )}

                  {clcSessionData.stage === 'draft_planning' && (
                    <div className="notice">
                      <p>Local Draft Planner: structure only -- never invents facts, never claims verification.</p>
                      <form className="inline-form training-form" onSubmit={submitClcBuildDraft}>
                        <label>Topic (optional -- defaults to top queue item)<input value={clcDraftTopic} onChange={(e) => setClcDraftTopic(e.target.value)} /></label>
                        <Button type="submit" disabled={clcBusy}>Build draft outline</Button>
                      </form>
                    </div>
                  )}
                  {clcSessionData.draft_report?.topic && (
                    <pre className="notice">{JSON.stringify(clcSessionData.draft_report, null, 2)}</pre>
                  )}

                  {clcSessionData.stage === 'provider_request' && (
                    <div className="notice">
                      <p>Multi-Provider Consensus Planner: prepares a request only -- Brud AI never calls a provider automatically.</p>
                      <form className="inline-form training-form" onSubmit={submitClcPrepareProviderRequest}>
                        <label>Providers (comma separated: claude, openai, gemini, openrouter, local_only)<input value={clcProviders} onChange={(e) => setClcProviders(e.target.value)} /></label>
                        <Button type="submit" disabled={clcBusy}>Prepare provider request</Button>
                      </form>
                    </div>
                  )}

                  {clcSessionData.stage === 'provider_consensus' && (
                    <div className="notice">
                      <p>Once an admin has run the requested providers externally, supply their outputs here for comparison, conflict detection, and consensus.</p>
                      <form className="inline-form training-form" onSubmit={submitClcIngestProviderResults}>
                        {clcProviderOutputs.map((o, idx) => (
                          <label key={idx}>{o.provider} output
                            <input value={o.output_text} onChange={(e) => {
                              const next = [...clcProviderOutputs]; next[idx] = { ...next[idx], output_text: e.target.value }; setClcProviderOutputs(next)
                            }} />
                          </label>
                        ))}
                        <Button type="submit" disabled={clcBusy}>Ingest provider results</Button>
                      </form>
                    </div>
                  )}
                  {clcSessionData.provider_consensus_report?.confidence && (
                    <pre className="notice">{JSON.stringify(clcSessionData.provider_consensus_report, null, 2)}</pre>
                  )}

                  {clcSessionData.stage === 'dataset_evolution' && (
                    <div className="notice">
                      <p>Dataset Evolution Planner: recommends merge/extend/replace/split/ignore -- never performs the merge.</p>
                      <form className="inline-form training-form" onSubmit={submitClcPlanDatasetEvolution}>
                        <label>Existing dataset source public ID (optional)<input value={clcExistingDatasetId} onChange={(e) => setClcExistingDatasetId(e.target.value)} /></label>
                        <Button type="submit" disabled={clcBusy}>Plan dataset evolution</Button>
                      </form>
                    </div>
                  )}

                  {clcSessionData.stage === 'knowledge_roadmap' && (
                    <div className="notice">
                      <p>Knowledge Roadmap: strengths, weaknesses, missing knowledge, future priorities.</p>
                      <Button onClick={runClcBuildRoadmap} disabled={clcBusy}>Build roadmap</Button>
                    </div>
                  )}

                  {clcSessionData.stage === 'recommendation' && !clcSessionData.planning_report?.next_action && (
                    <div className="notice">
                      <p>Learning Recommendation Engine: one of No Action / Collect More Data / Local Draft / External Provider Consensus / RAG Evaluation / Training Candidate.</p>
                      <Button onClick={runClcGenerateRecommendation} disabled={clcBusy}>Generate recommendation</Button>
                    </div>
                  )}
                  {clcSessionData.stage === 'recommendation' && clcSessionData.recommendation_report?.action && !clcSessionData.planning_report?.next_action && (
                    <div className="notice">
                      <p>Recommended: <strong>{clcSessionData.recommendation_report.action}</strong> -- {clcSessionData.recommendation_report.why}</p>
                      <Button onClick={runClcGenerateReport} disabled={clcBusy}>Generate admin planning report</Button>
                    </div>
                  )}

                  {clcSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Admin Planning Report ready for review.</p>
                      <pre className="notice">{JSON.stringify(clcSessionData.planning_report, null, 2)}</pre>
                      <Button onClick={() => runClcAdminReview('reject')} disabled={clcBusy}>Reject</Button>{' '}
                      <Button onClick={() => runClcAdminReview('edit')} disabled={clcBusy}>Edit</Button>{' '}
                      <Button onClick={() => runClcAdminReview('approve_draft')} disabled={clcBusy}>Approve Draft</Button>{' '}
                      <Button onClick={() => runClcAdminReview('request_provider_consensus')} disabled={clcBusy}>Request Provider Consensus</Button>{' '}
                      <Button onClick={() => runClcAdminReview('send_to_rag')} disabled={clcBusy}>Send to RAG</Button>{' '}
                      <Button onClick={() => runClcAdminReview('archive')} disabled={clcBusy}>Archive</Button>
                    </div>
                  )}

                  {clcSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Planning cycle closed with status <strong>{clcSessionData.status}</strong>. No automatic action was taken.</p>
                    </div>
                  )}

                  <h4>Cycle events</h4>
                  <ul className="notice">
                    {clcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!clcEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {tab === 'Research Center' && (
        <>
          <p className="notice">
            MB-10 -- AI Research &amp; Knowledge Acquisition Center. Admin-only: prepares research
            requests, compares multiple AI providers (never contacting any of them automatically --
            an admin runs them externally and pastes results back), builds evidence-backed dataset
            drafts, and sends only admin-approved knowledge to the RAG Sandbox and later the Learning
            Supervisor (MB-06). Nothing here starts training, deploys a model, activates a runtime, or
            writes/approves a dataset -- every irreversible step requires an explicit prior admin
            decision recorded on the session.
          </p>

          <div className="dataset-tabs">
            {rcSubTabs.map((t) => (
              <Button key={t} className={rcSubTab === t ? 'active' : ''} onClick={() => setRcSubTab(t)}>{t}</Button>
            ))}
          </div>

          {rcSubTab === 'Overview' && (
            <>
              {rcDiag && (
                <div className="notice">
                  <p><strong>External providers called:</strong> {String(rcDiag.external_providers_called)} -- Brud AI has no Claude/OpenAI/Gemini/OpenRouter integration; provider outputs must be collected externally and supplied back.</p>
                  <p><strong>RAG first policy:</strong> {rcDiag.rag_first_policy}</p>
                </div>
              )}
              {rcSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Topic" value={rcSessionData.topic} tone="neutral" />
                  <StatusCard label="Mode" value={rcSessionData.mode ?? 'not selected'} tone="neutral" />
                  <StatusCard label="Stage" value={rcSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={rcSessionData.status} tone={rcSessionData.status.includes('reject') ? 'waiting' : rcSessionData.status.startsWith('admin_') || rcSessionData.status === 'training_eligible' ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Research sessions</h4>
                  <ul className="notice">
                    {rcSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={rcSelectedId === s.public_id ? 'active' : ''} onClick={() => selectRcSession(s.public_id)}>
                          {s.topic} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!rcSessionsList.length && <li>No research sessions yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitRcCreateSession}>
                    <label>Topic<input value={rcNewTopic} onChange={(e) => setRcNewTopic(e.target.value)} placeholder="e.g. Photosynthesis" /></label>
                    <Button type="submit" disabled={rcBusy || !rcNewTopic.trim()}>{rcBusy ? 'Working…' : 'Start research session'}</Button>
                  </form>
                </div>
                <div>
                  {!rcSessionData && <div className="notice">Select or start a research session to work through its workflow in the other sub-tabs.</div>}
                  {rcSessionData && (
                    <>
                      <h4>Session events</h4>
                      <ul className="notice">
                        {rcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!rcEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {rcSubTab === 'Provider Registry' && (
            <>
              <p className="notice">Real, admin-extensible registry -- never a hardcoded provider list. Future providers are added here, not in code.</p>
              <ul className="notice">
                {rcProviders.map((p) => (
                  <li key={p.provider_key}>
                    <strong>{p.display_name}</strong> ({p.provider_key}) -- {p.status} -- {p.requires_external_call ? 'external call' : 'no external call'} -- {p.description}{' '}
                    <Button onClick={() => toggleRcProviderStatus(p.provider_key, p.status)} disabled={rcBusy}>
                      {p.status === 'active' ? 'Deactivate' : 'Activate'}
                    </Button>
                  </li>
                ))}
                {!rcProviders.length && <li>No providers registered.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitRcAddProvider}>
                <label>Provider key<input value={rcNewProviderForm.provider_key} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, provider_key: e.target.value })} /></label>
                <label>Display name<input value={rcNewProviderForm.display_name} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, display_name: e.target.value })} /></label>
                <label>Description<input value={rcNewProviderForm.description} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, description: e.target.value })} /></label>
                <label>
                  <input type="checkbox" checked={rcNewProviderForm.requires_external_call} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, requires_external_call: e.target.checked })} />
                  {' '}Requires external call
                </label>
                <Button type="submit" disabled={rcBusy || !rcNewProviderForm.provider_key || !rcNewProviderForm.display_name}>Add provider</Button>
              </form>
            </>
          )}

          {rcSubTab === 'Research Requests' && (
            <>
              {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
              {rcSessionData && (
                <>
                  {rcSessionData.stage === 'research_request' && (
                    <div className="notice">
                      <p>Builds a set of research questions, folding in evidence from an already-completed MB-09 Planning Center cycle if one is supplied.</p>
                      <form className="inline-form training-form" onSubmit={submitRcResearchRequest}>
                        <label>MB-09 planning session public ID (optional)<input value={rcPlanningCenterId} onChange={(e) => setRcPlanningCenterId(e.target.value)} /></label>
                        <Button type="submit" disabled={rcBusy}>Prepare research request</Button>
                      </form>
                    </div>
                  )}
                  {rcSessionData.stage === 'mode_selection' && (
                    <div className="notice">
                      <p>Mode 1 (Local Draft): Mini Brain drafts from its own existing evidence, no provider contacted. Mode 2 (Multi-Provider Consensus): a package is prepared for the admin to run externally.</p>
                      <form className="inline-form training-form" onSubmit={submitRcSelectMode}>
                        <label>Mode
                          <select value={rcMode} onChange={(e) => setRcMode(e.target.value)}>
                            <option value="local_draft">Local Draft</option>
                            <option value="multi_provider">Multi-Provider Consensus</option>
                          </select>
                        </label>
                        {rcMode === 'multi_provider' && (
                          <label>Provider keys (comma separated)<input value={rcProviderKeys} onChange={(e) => setRcProviderKeys(e.target.value)} /></label>
                        )}
                        <Button type="submit" disabled={rcBusy}>Select mode</Button>
                      </form>
                    </div>
                  )}
                  {rcSessionData.research_request?.questions && (
                    <pre className="notice">{JSON.stringify(rcSessionData.research_request, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {rcSubTab === 'Consensus' && (
            <>
              {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
              {rcSessionData && (
                <>
                  {rcSessionData.stage === 'local_draft' && (
                    <div className="notice">
                      <p>Local Draft: uses Mini Brain's own existing evidence -- Knowledge Roadmap, Learning Queue, Dataset Intelligence, Continuous Learning History (read via MB-09, read-only).</p>
                      <form className="inline-form training-form" onSubmit={submitRcBuildLocalDraft}>
                        <label>Existing dataset source public ID (optional)<input value={rcExistingDatasetId} onChange={(e) => setRcExistingDatasetId(e.target.value)} /></label>
                        <Button type="submit" disabled={rcBusy}>Build local draft</Button>
                      </form>
                    </div>
                  )}
                  {rcSessionData.stage === 'provider_request' && (
                    <div className="notice">
                      <p>Prepares a Provider Request Package only -- Brud AI never calls a provider automatically. The admin runs these providers externally.</p>
                      <Button onClick={runRcPrepareProviderRequestPackage} disabled={rcBusy}>Prepare provider request package</Button>
                    </div>
                  )}
                  {rcSessionData.provider_request?.status && (
                    <pre className="notice">{JSON.stringify(rcSessionData.provider_request, null, 2)}</pre>
                  )}
                  {rcSessionData.stage === 'provider_consensus' && (
                    <div className="notice">
                      <p>Once an admin has run the requested providers externally, paste their outputs here for duplicate/conflict detection and consensus.</p>
                      <form className="inline-form training-form" onSubmit={submitRcIngestProviderResults}>
                        {rcProviderOutputs.map((o, idx) => (
                          <label key={idx}>{o.provider} output
                            <input value={o.output_text} onChange={(e) => {
                              const next = [...rcProviderOutputs]; next[idx] = { ...next[idx], output_text: e.target.value }; setRcProviderOutputs(next)
                            }} />
                          </label>
                        ))}
                        <Button type="submit" disabled={rcBusy}>Ingest provider results</Button>
                      </form>
                    </div>
                  )}
                  {rcSessionData.consensus_report?.verdict && (
                    <pre className="notice">{JSON.stringify(rcSessionData.consensus_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {rcSubTab === 'Evidence' && (
            <>
              {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
              {rcSessionData && (
                <>
                  <p className="notice">Citation Analyzer and Evidence Validator are rule-based heuristics only (URL/year/attribution markers, absolute-claim and hedging-word counts) -- never a fact-checker, never AI-generated judgment.</p>
                  {rcSessionData.evidence_report?.per_provider ? (
                    <pre className="notice">{JSON.stringify(rcSessionData.evidence_report, null, 2)}</pre>
                  ) : <div className="notice">No evidence signals yet -- only produced for Multi-Provider Consensus mode after ingesting provider results.</div>}
                  {rcSessionData.quality_report?.overall_quality !== undefined && (
                    <>
                      <h4>Research Quality Score</h4>
                      <pre className="notice">{JSON.stringify(rcSessionData.quality_report, null, 2)}</pre>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {rcSubTab === 'Dataset Draft' && (
            <>
              {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
              {rcSessionData && (
                <>
                  {rcSessionData.stage === 'dataset_draft' && (
                    <div className="notice">
                      <p>Assembles the draft only -- <code>verified: false</code>, needs admin review. MB-10 never creates a final dataset; Dataset Studio remains the only place that happens.</p>
                      <Button onClick={runRcBuildDatasetDraft} disabled={rcBusy}>Build dataset draft</Button>
                    </div>
                  )}
                  {rcSessionData.recommendation_report?.recommendation && (
                    <p className="notice">Recommended: <strong>{rcSessionData.recommendation_report.recommendation}</strong> -- {rcSessionData.recommendation_report.why}</p>
                  )}
                  {rcSessionData.dataset_draft?.status && (
                    <pre className="notice">{JSON.stringify(rcSessionData.dataset_draft, null, 2)}</pre>
                  )}
                  {rcSessionData.stage === 'awaiting_draft_review' && (
                    <div className="notice">
                      <p>Admin decision (accept, then send-to-RAG, is a two-step confirmation -- RAG FIRST POLICY):</p>
                      <Button onClick={() => runRcAdminReviewDraft('reject')} disabled={rcBusy}>Reject</Button>{' '}
                      <Button onClick={() => runRcAdminReviewDraft('edit')} disabled={rcBusy}>Edit</Button>{' '}
                      <Button onClick={() => runRcAdminReviewDraft('accept_draft')} disabled={rcBusy}>Accept Draft</Button>{' '}
                      <Button onClick={() => runRcAdminReviewDraft('request_more_research')} disabled={rcBusy}>Request More Research</Button>{' '}
                      <Button onClick={() => runRcAdminReviewDraft('request_different_providers')} disabled={rcBusy}>Request Different Providers</Button>{' '}
                      <Button onClick={() => runRcAdminReviewDraft('request_local_draft')} disabled={rcBusy}>Request Local Draft</Button>{' '}
                      <Button onClick={() => runRcAdminReviewDraft('send_to_rag')} disabled={rcBusy || rcSessionData.draft_admin_decision !== 'accept_draft'}>Send to RAG</Button>{' '}
                      <Button onClick={() => runRcAdminReviewDraft('archive')} disabled={rcBusy}>Archive</Button>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {rcSubTab === 'RAG Status' && (
            <>
              {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
              {rcSessionData && (
                <>
                  <p className="notice">RAG FIRST POLICY: every dataset draft passes through the existing RAG Sandbox (generation + evaluation + report, reusing MB-06's exact pattern) before a training gate can ever open. Corpus, index, and retrieval remain admin-driven through RAG Sandbox's own UI.</p>
                  {rcSessionData.stage === 'rag_evaluation' && (
                    <form className="inline-form training-form" onSubmit={submitRcRunRagEvaluation}>
                      <label>RAG Sandbox experiment public ID<input value={rcRagForm.rag_sandbox_experiment_public_id} onChange={(e) => setRcRagForm({ ...rcRagForm, rag_sandbox_experiment_public_id: e.target.value })} /></label>
                      <label>Retrieval run public ID<input value={rcRagForm.retrieval_run_public_id} onChange={(e) => setRcRagForm({ ...rcRagForm, retrieval_run_public_id: e.target.value })} /></label>
                      <label>Generation assignment public ID<input value={rcRagForm.generation_assignment_public_id} onChange={(e) => setRcRagForm({ ...rcRagForm, generation_assignment_public_id: e.target.value })} /></label>
                      <Button type="submit" disabled={rcBusy}>Run RAG generation + evaluation</Button>
                      <Button type="button" onClick={runRcFinalizeRagEvaluation} disabled={rcBusy}>Finalize report (retry after human review)</Button>
                    </form>
                  )}
                  {rcSessionData.rag_report && Object.keys(rcSessionData.rag_report).length > 0 && (
                    <pre className="notice">{JSON.stringify(rcSessionData.rag_report, null, 2)}</pre>
                  )}
                  {rcSessionData.stage === 'awaiting_rag_review' && (
                    <div className="notice">
                      <Button onClick={() => runRcAdminReviewRag('approve')} disabled={rcBusy}>Approve</Button>{' '}
                      <Button onClick={() => runRcAdminReviewRag('reject')} disabled={rcBusy}>Reject</Button>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {rcSubTab === 'Training Status' && (
            <>
              {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
              {rcSessionData && (
                <>
                  <p className="notice">Eligibility check only -- never a training trigger. Training Engine only accepts admin-approved + RAG-approved datasets, and only ever starts through MB-06's own UI.</p>
                  {rcSessionData.stage === 'training_gate' && (
                    <Button onClick={runRcCheckTrainingGate} disabled={rcBusy}>Check training gate</Button>
                  )}
                  {rcSessionData.training_gate_report && Object.keys(rcSessionData.training_gate_report).length > 0 && (
                    <pre className="notice">{JSON.stringify(rcSessionData.training_gate_report, null, 2)}</pre>
                  )}
                  {rcSessionData.training_gate_report?.eligible && (
                    <form className="inline-form training-form" onSubmit={submitRcAnalyzeTrainingReport}>
                      <label>MB-06 Learning Supervisor session public ID (once training has completed there)<input value={rcTrainingReportMb06Id} onChange={(e) => setRcTrainingReportMb06Id(e.target.value)} /></label>
                      <Button type="submit" disabled={rcBusy}>Analyze training report (read-only)</Button>
                    </form>
                  )}
                </>
              )}
            </>
          )}

          {rcSubTab === 'Reports' && (
            <>
              {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
              {rcSessionData && (
                <>
                  <p className="notice">Assembled on demand from fields already on the session -- pure merge, nothing recomputed, nothing stored separately.</p>
                  <Button onClick={runRcGenerateReport} disabled={rcBusy}>Generate research report</Button>
                  {rcReport && <pre className="notice">{JSON.stringify(rcReport, null, 2)}</pre>}
                </>
              )}
            </>
          )}

          {rcSubTab === 'History' && (
            <>
              <h4>Learning Memory (permanent, insert-only)</h4>
              <div className="notice">
                <ul>
                  {rcMemoryItems.map((m) => (
                    <li key={m.public_id}>{m.created_at} -- session {m.research_session_public_id.slice(0, 8)} -- decision: {m.admin_decision ?? 'n/a'} -- {m.notes}</li>
                  ))}
                  {!rcMemoryItems.length && <li>No memory entries recorded yet.</li>}
                </ul>
                {rcSessionData && (
                  <form className="inline-form training-form" onSubmit={submitRcRecordMemory}>
                    <label>Notes<input value={rcMemoryNotes} onChange={(e) => setRcMemoryNotes(e.target.value)} /></label>
                    <Button type="submit" disabled={rcBusy}>Record memory snapshot for selected session</Button>
                  </form>
                )}
              </div>
              {rcSessionData && (
                <>
                  <h4>Selected session events</h4>
                  <ul className="notice">
                    {rcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!rcEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {rcSubTab === 'Diagnostics' && (
            <>
              {rcDiag && <pre className="notice">{JSON.stringify(rcDiag, null, 2)}</pre>}
              {!rcDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Dataset Evolution' && (
        <>
          <p className="notice">
            MB-11 -- Autonomous Dataset Evolution &amp; Knowledge Factory. Not a Training Engine, a
            Dataset Editor, or a Runtime. It continuously analyzes what MB-05, MB-05.1, MB-08, MB-09,
            and MB-10 have already computed and plans how Brud AI's dataset should evolve --
            recommendation and planning only. It never writes a dataset record, never trains, never
            deploys, and never modifies RAG -- every action requires explicit admin approval.
          </p>

          <div className="dataset-tabs">
            {deSubTabs.map((t) => (
              <Button key={t} className={deSubTab === t ? 'active' : ''} onClick={() => setDeSubTab(t)}>{t}</Button>
            ))}
          </div>

          {deSubTab === 'Overview' && (
            <>
              {deDiag && (
                <div className="notice">
                  <p><strong>Dataset writes performed:</strong> {String(deDiag.dataset_writes_performed)} -- Dataset Studio remains the only place a dataset is actually written.</p>
                  <p><strong>Training started:</strong> {String(deDiag.training_started)} -- <strong>Models deployed:</strong> {String(deDiag.models_deployed)} -- <strong>RAG modified:</strong> {String(deDiag.rag_modified)}</p>
                </div>
              )}
              {deSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Dataset source" value={deSessionData.dataset_source_public_id.slice(0, 12)} tone="neutral" />
                  <StatusCard label="Stage" value={deSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={deSessionData.status} tone={deSessionData.status.includes('reject') ? 'waiting' : deSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Evolution cycles</h4>
                  <ul className="notice">
                    {deSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={deSelectedId === s.public_id ? 'active' : ''} onClick={() => selectDeSession(s.public_id)}>
                          {s.dataset_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!deSessionsList.length && <li>No evolution cycles yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitDeCreateSession}>
                    <label>Dataset source public ID<input value={deNewSourceId} onChange={(e) => setDeNewSourceId(e.target.value)} placeholder="source public_id from Dataset Studio" /></label>
                    <Button type="submit" disabled={deBusy || !deNewSourceId.trim()}>{deBusy ? 'Working…' : 'Start evolution cycle'}</Button>
                  </form>
                </div>
                <div>
                  {!deSessionData && <div className="notice">Select or start an evolution cycle to work through its workflow in the other sub-tabs.</div>}
                  {deSessionData && (
                    <>
                      <h4>Cycle events</h4>
                      <ul className="notice">
                        {deEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!deEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {deSubTab === 'Knowledge Evolution' && (
            <>
              {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
              {deSessionData && (
                <>
                  {deSessionData.stage === 'knowledge_evolution' && (
                    <div className="notice">
                      <p>Combines the current dataset's real MB-05/MB-05.1 analysis with recent closed MB-08/MB-09/MB-10 evidence into one evolution analysis, dependency graph, coverage classification, and knowledge-relationship report.</p>
                      <Button onClick={runDeKnowledgeEvolution} disabled={deBusy}>Run knowledge evolution analysis</Button>
                    </div>
                  )}
                  {deSessionData.evolution_analysis?.evolution_pressure !== undefined && (
                    <>
                      <h4>Evolution analysis</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.evolution_analysis, null, 2)}</pre>
                      <h4>Dependency graph</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.dependency_graph, null, 2)}</pre>
                      <h4>Coverage</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.coverage_report, null, 2)}</pre>
                      <h4>Knowledge relationships</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.relationship_report, null, 2)}</pre>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {deSubTab === 'Dataset Evolution' && (
            <>
              {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
              {deSessionData && (
                <>
                  {deSessionData.stage === 'dataset_evolution' && (
                    <div className="notice">
                      <p>Plans expansion action, version projection, knowledge-factory content recommendations, a synthetic-dataset design, and predicted quality evolution. Recommends only -- never performs any of it.</p>
                      <Button onClick={runDeDatasetEvolution} disabled={deBusy}>Plan dataset evolution</Button>
                    </div>
                  )}
                  {deSessionData.expansion_plan?.action && (
                    <>
                      <h4>Expansion plan</h4>
                      <p className="notice">Recommended action: <strong>{deSessionData.expansion_plan.action}</strong> -- {deSessionData.expansion_plan.why}</p>
                      <h4>Version plan</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.version_plan, null, 2)}</pre>
                      <h4>Knowledge factory plan</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.knowledge_factory_plan, null, 2)}</pre>
                      <h4>Synthetic dataset plan (design only, never generated)</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.synthetic_dataset_plan, null, 2)}</pre>
                      <h4>Quality evolution prediction</h4>
                      <pre className="notice">{JSON.stringify(deSessionData.quality_evolution, null, 2)}</pre>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {deSubTab === 'Simulation' && (
            <>
              {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
              {deSessionData && (
                <>
                  {deSessionData.stage === 'evolution_simulation' && (
                    <div className="notice">
                      <p>Simulation only -- no benchmark runs, no model is evaluated, no RAG query executes.</p>
                      <Button onClick={runDeSimulation} disabled={deBusy}>Run evolution simulation</Button>
                    </div>
                  )}
                  {deSessionData.simulation_report?.expected_improvement !== undefined && (
                    <pre className="notice">{JSON.stringify(deSessionData.simulation_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {deSubTab === 'Recommendation & Report' && (
            <>
              {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
              {deSessionData && (
                <>
                  {deSessionData.stage === 'recommendation' && !deSessionData.recommendation_report?.recommendation && (
                    <div className="notice">
                      <p>One of: Continue Current Dataset / Expand Dataset / Split Dataset / Replace Dataset / Research More / Collect More Data / Wait / Reject -- with WHY, evidence, confidence, and risk.</p>
                      <Button onClick={runDeGenerateRecommendation} disabled={deBusy}>Generate recommendation</Button>
                    </div>
                  )}
                  {deSessionData.recommendation_report?.recommendation && deSessionData.stage === 'recommendation' && !deSessionData.evolution_report?.ready_for_admin_review && (
                    <div className="notice">
                      <p>Recommended: <strong>{deSessionData.recommendation_report.recommendation}</strong> (confidence {deSessionData.recommendation_report.confidence}, risk {deSessionData.recommendation_report.risk}) -- {deSessionData.recommendation_report.why}</p>
                      <Button onClick={runDeGenerateReport} disabled={deBusy}>Generate evolution report</Button>
                    </div>
                  )}
                  {deSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Evolution Report ready for review.</p>
                      <pre className="notice">{JSON.stringify(deSessionData.evolution_report, null, 2)}</pre>
                      <Button onClick={() => runDeAdminReview('approve_evolution')} disabled={deBusy}>Approve Evolution</Button>{' '}
                      <Button onClick={() => runDeAdminReview('edit_plan')} disabled={deBusy}>Edit Plan</Button>{' '}
                      <Button onClick={() => runDeAdminReview('research_more')} disabled={deBusy}>Research More</Button>{' '}
                      <Button onClick={() => runDeAdminReview('request_provider_consensus')} disabled={deBusy}>Request Provider Consensus</Button>{' '}
                      <Button onClick={() => runDeAdminReview('expand_dataset')} disabled={deBusy}>Expand Dataset</Button>{' '}
                      <Button onClick={() => runDeAdminReview('split_dataset')} disabled={deBusy}>Split Dataset</Button>{' '}
                      <Button onClick={() => runDeAdminReview('merge_dataset')} disabled={deBusy}>Merge Dataset</Button>{' '}
                      <Button onClick={() => runDeAdminReview('archive_plan')} disabled={deBusy}>Archive Plan</Button>{' '}
                      <Button onClick={() => runDeAdminReview('reject')} disabled={deBusy}>Reject</Button>{' '}
                      <Button onClick={() => runDeAdminReview('send_to_rag')} disabled={deBusy || deSessionData.draft_admin_decision !== 'approve_evolution'}>Send to RAG</Button>
                    </div>
                  )}
                  {deSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Evolution cycle closed with status <strong>{deSessionData.status}</strong>. No automatic action was taken.</p>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {deSubTab === 'RAG Status' && (
            <>
              {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
              {deSessionData && (
                <>
                  <p className="notice">Reuses MB-06/MB-10's exact RAG Sandbox pattern: generation + evaluation + report finalization only. Corpus, index, and retrieval remain admin-driven through RAG Sandbox's own UI.</p>
                  {deSessionData.stage === 'rag_evaluation' && (
                    <form className="inline-form training-form" onSubmit={submitDeRunRagEvaluation}>
                      <label>RAG Sandbox experiment public ID<input value={deRagForm.rag_sandbox_experiment_public_id} onChange={(e) => setDeRagForm({ ...deRagForm, rag_sandbox_experiment_public_id: e.target.value })} /></label>
                      <label>Retrieval run public ID<input value={deRagForm.retrieval_run_public_id} onChange={(e) => setDeRagForm({ ...deRagForm, retrieval_run_public_id: e.target.value })} /></label>
                      <label>Generation assignment public ID<input value={deRagForm.generation_assignment_public_id} onChange={(e) => setDeRagForm({ ...deRagForm, generation_assignment_public_id: e.target.value })} /></label>
                      <Button type="submit" disabled={deBusy}>Run RAG generation + evaluation</Button>
                      <Button type="button" onClick={runDeFinalizeRagEvaluation} disabled={deBusy}>Finalize report (retry after human review)</Button>
                    </form>
                  )}
                  {deSessionData.rag_report && Object.keys(deSessionData.rag_report).length > 0 && (
                    <pre className="notice">{JSON.stringify(deSessionData.rag_report, null, 2)}</pre>
                  )}
                  {deSessionData.stage === 'awaiting_rag_review' && (
                    <div className="notice">
                      <Button onClick={() => runDeAdminReviewRag('approve')} disabled={deBusy}>Approve</Button>{' '}
                      <Button onClick={() => runDeAdminReviewRag('reject')} disabled={deBusy}>Reject</Button>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {deSubTab === 'History' && deSessionData && (
            <>
              <h4>Cycle events</h4>
              <ul className="notice">
                {deEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!deEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {deSubTab === 'History' && !deSessionData && (
            <div className="notice">Select an evolution cycle in Overview first.</div>
          )}

          {deSubTab === 'Diagnostics' && (
            <>
              {deDiag && <pre className="notice">{JSON.stringify(deDiag, null, 2)}</pre>}
              {!deDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Pipeline Coordinator' && (
        <>
          <p className="notice">
            MB-12 -- Autonomous AI Knowledge Pipeline Coordinator. Not a Training Engine, a Dataset
            Writer, or a Runtime. It links together, in order, the real sessions MB-09, MB-10, MB-11,
            and MB-06 already produced for one topic and reports on the result -- orchestration,
            validation, scheduling, and reporting only. It never contacts RAG Sandbox itself; it only
            ever reads a RAG report MB-11 or MB-06 already produced. Every stage transition is
            dependency-checked so a pipeline can never skip a stage.
          </p>

          <div className="dataset-tabs">
            {pcSubTabs.map((t) => (
              <Button key={t} className={pcSubTab === t ? 'active' : ''} onClick={() => setPcSubTab(t)}>{t}</Button>
            ))}
          </div>

          {pcSubTab === 'Overview' && (
            <>
              {pcDiag && (
                <div className="notice">
                  <p><strong>Training started:</strong> {String(pcDiag.training_started)} -- <strong>Models deployed:</strong> {String(pcDiag.models_deployed)} -- <strong>RAG Sandbox called directly:</strong> {String(pcDiag.rag_sandbox_called_directly)}</p>
                </div>
              )}
              {pcSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Topic" value={pcSessionData.topic} tone="neutral" />
                  <StatusCard label="Stage" value={pcSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={pcSessionData.status} tone={pcSessionData.status.includes('reject') ? 'waiting' : pcSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Pipelines</h4>
                  <ul className="notice">
                    {pcSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={pcSelectedId === s.public_id ? 'active' : ''} onClick={() => selectPcSession(s.public_id)}>
                          {s.topic} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!pcSessionsList.length && <li>No pipelines yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitPcCreateSession}>
                    <label>Topic<input value={pcNewTopic} onChange={(e) => setPcNewTopic(e.target.value)} placeholder="matches the topic used in MB-09/MB-10" /></label>
                    <Button type="submit" disabled={pcBusy || !pcNewTopic.trim()}>{pcBusy ? 'Working…' : 'Start pipeline'}</Button>
                  </form>
                </div>
                <div>
                  {!pcSessionData && <div className="notice">Select or start a pipeline to work through it in the other sub-tabs.</div>}
                  {pcSessionData && (
                    <>
                      <h4>Linked sessions</h4>
                      <ul className="notice">
                        <li>MB-09 (Research): {pcSessionData.mb09_session_public_id || 'not linked'}</li>
                        <li>MB-10 (Provider Consensus / Draft): {pcSessionData.mb10_session_public_id || 'not linked'}</li>
                        <li>MB-11 (Dataset Evolution): {pcSessionData.mb11_session_public_id || 'not linked'}</li>
                        <li>MB-06 (Training): {pcSessionData.mb06_session_public_id || 'not linked'}</li>
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {pcSubTab === 'Link Phases' && (
            <>
              {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
              {pcSessionData && (
                <div className="notice">
                  <p>Every link is dependency-checked -- linking out of order is rejected with the exact reason.</p>
                  <form className="inline-form training-form" onSubmit={submitPcLinkResearch}>
                    <label>MB-09 planning session public ID<input value={pcMb09Id} onChange={(e) => setPcMb09Id(e.target.value)} /></label>
                    <Button type="submit" disabled={pcBusy || !pcMb09Id.trim()}>Link Research (MB-09)</Button>
                  </form>
                  <form className="inline-form training-form" onSubmit={submitPcLinkResearchCenter}>
                    <label>MB-10 research session public ID<input value={pcMb10Id} onChange={(e) => setPcMb10Id(e.target.value)} /></label>
                    <Button type="submit" disabled={pcBusy || !pcMb10Id.trim()}>Link Provider Consensus / Draft (MB-10)</Button>
                  </form>
                  <Button onClick={runPcRefreshResearchCenter} disabled={pcBusy}>Refresh MB-10 link (check for draft readiness)</Button>
                  <form className="inline-form training-form" onSubmit={submitPcLinkDatasetEvolution}>
                    <label>MB-11 evolution session public ID<input value={pcMb11Id} onChange={(e) => setPcMb11Id(e.target.value)} /></label>
                    <Button type="submit" disabled={pcBusy || !pcMb11Id.trim()}>Link Dataset Evolution (MB-11)</Button>
                  </form>
                  <form className="inline-form training-form" onSubmit={submitPcLinkTraining}>
                    <label>MB-06 learning session public ID<input value={pcMb06Id} onChange={(e) => setPcMb06Id(e.target.value)} /></label>
                    <Button type="submit" disabled={pcBusy || !pcMb06Id.trim()}>Link Training (MB-06)</Button>
                  </form>
                  <Button onClick={runPcRefreshTraining} disabled={pcBusy}>Refresh MB-06 link (check for training/benchmark/release progress)</Button>
                </div>
              )}
            </>
          )}

          {pcSubTab === 'RAG Gate' && (
            <>
              {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
              {pcSessionData && (
                <>
                  <p className="notice">Reads whichever RAG report MB-11 or MB-06 already produced -- verifies citations, evidence, hallucination rate, and admin approval. Never calls RAG Sandbox itself. On failure, the pipeline returns to Dataset Planned.</p>
                  <Button onClick={runPcRunRagFirstEnforcement} disabled={pcBusy}>Run RAG First Enforcement</Button>
                  {pcSessionData.rag_first_report && Object.keys(pcSessionData.rag_first_report).length > 0 && (
                    <pre className="notice">{JSON.stringify(pcSessionData.rag_first_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {pcSubTab === 'Readiness & Timeline' && (
            <>
              {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
              {pcSessionData && (
                <>
                  <p className="notice">Unified readiness score combines already-computed signals from MB-05, MB-05.1, MB-06, MB-08, MB-09, MB-10, and MB-11 -- omitting any source not yet linked, never treating it as zero.</p>
                  <Button onClick={runPcGenerateTrainingReadiness} disabled={pcBusy}>Generate training readiness report</Button>{' '}
                  <Button onClick={runPcGenerateTimeline} disabled={pcBusy}>Generate lifecycle timeline</Button>
                  {pcSessionData.training_readiness_report?.unified_readiness_score !== undefined && (
                    <pre className="notice">{JSON.stringify(pcSessionData.training_readiness_report, null, 2)}</pre>
                  )}
                  {pcSessionData.lifecycle_timeline?.timeline && (
                    <pre className="notice">{JSON.stringify(pcSessionData.lifecycle_timeline, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {pcSubTab === 'Prediction' && (
            <>
              {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
              {pcSessionData && (
                <>
                  <p className="notice">Simulation only -- expected benchmark, reasoning, Tamil quality, English quality, memory, and hallucination-reduction gains, derived from MB-11's own projection and, once linked, MB-06's real benchmark comparison.</p>
                  <Button onClick={runPcPredictImprovement} disabled={pcBusy}>Predict improvement</Button>
                  {pcSessionData.improvement_prediction?.expected_benchmark_gain !== undefined && (
                    <pre className="notice">{JSON.stringify(pcSessionData.improvement_prediction, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {pcSubTab === 'Recommendation & Report' && (
            <>
              {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
              {pcSessionData && (
                <>
                  <div className="notice">
                    <Button onClick={runPcGenerateRecommendation} disabled={pcBusy}>Generate recommendation</Button>{' '}
                    <Button onClick={runPcGenerateReport} disabled={pcBusy}>Generate master pipeline report</Button>
                  </div>
                  {pcSessionData.recommendation_report?.action && (
                    <p className="notice">Recommended: <strong>{pcSessionData.recommendation_report.action}</strong> (confidence {pcSessionData.recommendation_report.confidence}, risk {pcSessionData.recommendation_report.risk}) -- {pcSessionData.recommendation_report.why}</p>
                  )}
                  {pcSessionData.master_report?.next_action && (
                    <pre className="notice">{JSON.stringify(pcSessionData.master_report, null, 2)}</pre>
                  )}
                  <div className="notice">
                    <p>Admin Decision Center -- always available, no decision executes anything:</p>
                    <Button onClick={() => runPcAdminDecide('continue')} disabled={pcBusy}>Continue</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('pause')} disabled={pcBusy}>Pause</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('research_more')} disabled={pcBusy}>Research More</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('request_providers')} disabled={pcBusy}>Request Providers</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('improve_dataset')} disabled={pcBusy}>Improve Dataset</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('retry_rag')} disabled={pcBusy}>Retry RAG</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('approve_training')} disabled={pcBusy}>Approve Training</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('reject')} disabled={pcBusy}>Reject</Button>{' '}
                    <Button onClick={() => runPcAdminDecide('archive')} disabled={pcBusy}>Archive</Button>
                  </div>
                </>
              )}
            </>
          )}

          {pcSubTab === 'History' && pcSessionData && (
            <>
              <h4>Pipeline events</h4>
              <ul className="notice">
                {pcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!pcEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {pcSubTab === 'History' && !pcSessionData && (
            <div className="notice">Select a pipeline in Overview first.</div>
          )}

          {pcSubTab === 'Diagnostics' && (
            <>
              {pcDiag && <pre className="notice">{JSON.stringify(pcDiag, null, 2)}</pre>}
              {!pcDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Language Intelligence' && (
        <>
          <p className="notice">
            MB-13 -- Language Intelligence &amp; Dataset Normalization Center. Not a spell checker,
            OCR engine, translator, dataset generator, or Training Engine. It validates, normalizes,
            scores, and certifies a dataset's language quality before RAG or Training. It never edits
            a dataset record, never starts training, and never deploys -- every action requires
            explicit admin approval, and every check reuses this codebase's own existing Tamil/
            Unicode/Tanglish utilities rather than a second implementation.
          </p>

          <div className="dataset-tabs">
            {liSubTabs.map((t) => (
              <Button key={t} className={liSubTab === t ? 'active' : ''} onClick={() => setLiSubTab(t)}>{t}</Button>
            ))}
          </div>

          {liSubTab === 'Overview' && (
            <>
              {liDiag && (
                <div className="notice">
                  <p><strong>Dataset writes performed:</strong> {String(liDiag.dataset_writes_performed)} -- Dataset Studio remains the only place a dataset is actually written.</p>
                  <p><strong>Training started:</strong> {String(liDiag.training_started)} -- <strong>RAG called:</strong> {String(liDiag.rag_called)} -- <strong>Automatic approval:</strong> {String(liDiag.automatic_approval)}</p>
                </div>
              )}
              {liSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Dataset source" value={liSessionData.dataset_source_public_id.slice(0, 12)} tone="neutral" />
                  <StatusCard label="Stage" value={liSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={liSessionData.status} tone={liSessionData.status.includes('reject') ? 'waiting' : liSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Language cycles</h4>
                  <ul className="notice">
                    {liSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={liSelectedId === s.public_id ? 'active' : ''} onClick={() => selectLiSession(s.public_id)}>
                          {s.dataset_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!liSessionsList.length && <li>No language cycles yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitLiCreateSession}>
                    <label>Dataset source public ID<input value={liNewSourceId} onChange={(e) => setLiNewSourceId(e.target.value)} placeholder="source public_id from Dataset Studio" /></label>
                    <Button type="submit" disabled={liBusy || !liNewSourceId.trim()}>{liBusy ? 'Working…' : 'Start language cycle'}</Button>
                  </form>
                </div>
                <div>
                  {!liSessionData && <div className="notice">Select or start a language cycle to work through it in the other sub-tabs.</div>}
                  {liSessionData && (
                    <>
                      <h4>Cycle events</h4>
                      <ul className="notice">
                        {liEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!liEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {liSubTab === 'Language Scan' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'language_scan' && (
                    <div className="notice">
                      <p>Reuses MB-05's real language distribution (Tamil/English/Tanglish/Mixed) for this dataset.</p>
                      <Button onClick={runLiLanguageScan} disabled={liBusy}>Run language scan</Button>
                    </div>
                  )}
                  {liSessionData.language_scan_report?.dominant_language && (
                    <pre className="notice">{JSON.stringify(liSessionData.language_scan_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'Unicode & Character' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'unicode_validation' && (
                    <div className="notice">
                      <p>Reuses core_model.corpus.unicode_normalization (replacement/mojibake/combining-mark checks) and the Tamil Fluency Validator's orphan vowel-sign detection.</p>
                      <Button onClick={runLiUnicodeValidation} disabled={liBusy}>Run Unicode &amp; Tamil character validation</Button>
                    </div>
                  )}
                  {liSessionData.unicode_report?.unicode_score !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.unicode_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'Spell & Grammar' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'spell_analysis' && (
                    <div className="notice">
                      <p>Matches text against the existing, admin-curated Document Tamil Correction Registry's active rules only -- never a fabricated dictionary.</p>
                      <Button onClick={runLiSpellAnalysis} disabled={liBusy}>Run spell analysis</Button>
                    </div>
                  )}
                  {liSessionData.spell_report?.spell_score !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.spell_report, null, 2)}</pre>
                  )}
                  {liSessionData.stage === 'grammar_analysis' && (
                    <div className="notice">
                      <p>Script-structural heuristics only -- real grammatical analysis (verb agreement, gender, number, case, tense) is honestly NOT implemented; see disclosure in the result.</p>
                      <Button onClick={runLiGrammarAnalysis} disabled={liBusy}>Run grammar &amp; sentence quality analysis</Button>
                    </div>
                  )}
                  {liSessionData.grammar_report?.grammar_confidence !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.grammar_report, null, 2)}</pre>
                  )}
                  {liSessionData.sentence_quality_report?.naturalness_score !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.sentence_quality_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'OCR' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'ocr_analysis' && (
                    <div className="notice">
                      <p>Never edits automatically -- only reports possible OCR mistakes with a confidence band and suggested correction. An admin must apply any accepted correction manually through Dataset Studio.</p>
                      <Button onClick={runLiOcrAnalysis} disabled={liBusy}>Run OCR correction planning</Button>
                    </div>
                  )}
                  {liSessionData.ocr_report?.ocr_score !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.ocr_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'Tanglish' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'tanglish_analysis' && (
                    <div className="notice">
                      <p>Tanglish -&gt; Tamil (existing MB-04A dictionary) and Tamil -&gt; Tanglish (existing Phase 10A phonetic transliterator) -- never overwrites the original text.</p>
                      <Button onClick={runLiTanglishAnalysis} disabled={liBusy}>Run Tanglish analysis</Button>
                    </div>
                  )}
                  {liSessionData.tanglish_report?.forward && (
                    <pre className="notice">{JSON.stringify(liSessionData.tanglish_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'Translation' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'translation_analysis' && (
                    <div className="notice">
                      <p>No Tamil&lt;-&gt;English translation engine exists in this codebase -- this only validates already-claimed pairs (none, for a monolingual dataset), never invents a translation.</p>
                      <Button onClick={runLiTranslationAnalysis} disabled={liBusy}>Run translation analysis</Button>
                    </div>
                  )}
                  {liSessionData.translation_report?.pairs_analyzed !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.translation_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'Dataset Draft' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'dataset_draft_generation' && (
                    <div className="notice">
                      <p>For a Tamil-dominant dataset: a real Tanglish draft (deterministic transliteration). No English draft is ever fabricated -- no translation engine exists. Always <code>verified: false</code>.</p>
                      <Button onClick={runLiDatasetDraft} disabled={liBusy}>Generate language dataset draft</Button>
                    </div>
                  )}
                  {liSessionData.dataset_draft_report?.applicable !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.dataset_draft_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'Quality & Report' && (
            <>
              {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
              {liSessionData && (
                <>
                  {liSessionData.stage === 'language_quality_score' && (
                    <div className="notice">
                      <Button onClick={runLiQualityScore} disabled={liBusy}>Compute language quality score</Button>
                    </div>
                  )}
                  {liSessionData.quality_score_report?.overall_language_quality !== undefined && (
                    <pre className="notice">{JSON.stringify(liSessionData.quality_score_report, null, 2)}</pre>
                  )}
                  {liSessionData.stage === 'language_report' && (
                    <div className="notice">
                      <Button onClick={runLiGenerateReport} disabled={liBusy}>Generate language report</Button>
                    </div>
                  )}
                  {liSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Language Report ready for review.</p>
                      <pre className="notice">{JSON.stringify(liSessionData.language_report, null, 2)}</pre>
                      <Button onClick={() => runLiAdminReview('approve')} disabled={liBusy}>Approve</Button>{' '}
                      <Button onClick={() => runLiAdminReview('reject')} disabled={liBusy}>Reject</Button>{' '}
                      <Button onClick={() => runLiAdminReview('request_fix')} disabled={liBusy}>Request Fix</Button>{' '}
                      <Button onClick={() => runLiAdminReview('archive')} disabled={liBusy}>Archive</Button>
                    </div>
                  )}
                  {liSessionData.stage === 'certified' && (
                    <div className="notice">
                      <p>Language Certified -- eligible for MB-11 Dataset Evolution, RAG Sandbox, and MB-06 Learning Supervisor. This service never submits it to any of them automatically.</p>
                    </div>
                  )}
                  {liSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Language cycle closed with status <strong>{liSessionData.status}</strong>. No automatic action was taken.</p>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {liSubTab === 'History' && liSessionData && (
            <>
              <h4>Cycle events</h4>
              <ul className="notice">
                {liEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!liEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {liSubTab === 'History' && !liSessionData && (
            <div className="notice">Select a language cycle in Overview first.</div>
          )}

          {liSubTab === 'Diagnostics' && (
            <>
              {liDiag && <pre className="notice">{JSON.stringify(liDiag, null, 2)}</pre>}
              {!liDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Vision Intelligence' && (
        <>
          <p className="notice">
            MB-14 -- Vision Intelligence &amp; Image Understanding Center. Not an image generator,
            dataset editor, OCR engine, training engine, or runtime. It extracts and analyzes images
            already inside a document, compares them with OCR/dataset text, and prepares structured
            visual knowledge for admin review. No vision model, object-detection model, or
            captioning model exists anywhere in this codebase (confirmed by audit) -- every
            automated detection is honestly reported as an <code>Unknown Object</code> with
            confidence 0.0 until an admin annotates it. It never edits the original document, never
            writes to Dataset Studio, never starts training, and never deploys.
          </p>

          <div className="dataset-tabs">
            {viSubTabs.map((t) => (
              <Button key={t} className={viSubTab === t ? 'active' : ''} onClick={() => setViSubTab(t)}>{t}</Button>
            ))}
          </div>

          {viSubTab === 'Overview' && (
            <>
              {viDiag && (
                <div className="notice">
                  <p><strong>Vision model available:</strong> {String(viDiag.vision_model_available)} -- <strong>Object detection available:</strong> {String(viDiag.object_detection_model_available)} -- <strong>Captioning available:</strong> {String(viDiag.captioning_model_available)}</p>
                  <p><strong>Dataset writes performed:</strong> {String(viDiag.dataset_writes_performed)} -- Dataset Studio remains the only place a dataset is actually written.</p>
                  <p><strong>Training started:</strong> {String(viDiag.training_started)} -- <strong>Runtime activated:</strong> {String(viDiag.runtime_activated)} -- <strong>RAG modified:</strong> {String(viDiag.rag_modified)} -- <strong>Automatic approval:</strong> {String(viDiag.automatic_approval)}</p>
                </div>
              )}
              {viSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Document source" value={viSessionData.document_source_public_id.slice(0, 12)} tone="neutral" />
                  <StatusCard label="Stage" value={viSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={viSessionData.status} tone={viSessionData.status.includes('reject') ? 'waiting' : viSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Vision cycles</h4>
                  <ul className="notice">
                    {viSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={viSelectedId === s.public_id ? 'active' : ''} onClick={() => selectViSession(s.public_id)}>
                          {s.document_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!viSessionsList.length && <li>No vision cycles yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitViCreateSession}>
                    <label>Document source public ID<input value={viNewDocumentSourceId} onChange={(e) => setViNewDocumentSourceId(e.target.value)} placeholder="document public_id from Document Workspace" /></label>
                    <label>Dataset source public ID (optional)<input value={viNewDatasetSourceId} onChange={(e) => setViNewDatasetSourceId(e.target.value)} placeholder="linked Dataset Studio source, optional" /></label>
                    <Button type="submit" disabled={viBusy || !viNewDocumentSourceId.trim()}>{viBusy ? 'Working…' : 'Start vision cycle'}</Button>
                  </form>
                </div>
                <div>
                  {!viSessionData && <div className="notice">Select or start a vision cycle to work through it in the other sub-tabs.</div>}
                  {viSessionData && (
                    <>
                      <h4>Cycle events</h4>
                      <ul className="notice">
                        {viEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!viEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {viSubTab === 'Image Extraction' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'image_extraction' && (
                    <div className="notice">
                      <p>Extracts every real embedded image from the already-stored PDF via PyMuPDF -- the original document is never modified.</p>
                      <Button onClick={runViImageExtraction} disabled={viBusy}>Run image extraction</Button>
                    </div>
                  )}
                  {viSessionData.image_extraction_report?.total_images !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.image_extraction_report, null, 2)}</pre>
                  )}
                  {!!viImagesList.length && (
                    <>
                      <h4>Extracted images</h4>
                      <ul className="notice">
                        {viImagesList.map((img) => (
                          <li key={img.public_id}>
                            page {img.page_number} #{img.image_index} -- {img.image_format} {img.width_pixels}x{img.height_pixels} -- {img.file_size_bytes} bytes -- {img.checksum_sha256.slice(0, 12)}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'Quality' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'image_quality' && (
                    <div className="notice">
                      <p>Real pixel statistics via Pillow: resolution, brightness/contrast (grayscale histogram), a blur proxy (edge-variance), and rotation (real EXIF orientation tag). Crop and noise detection are honestly NOT implemented.</p>
                      <Button onClick={runViImageQuality} disabled={viBusy}>Run image quality analysis</Button>
                    </div>
                  )}
                  {viSessionData.quality_report?.average_quality_score !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.quality_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'Objects' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'vision_understanding' && (
                    <div className="notice">
                      <p>No vision model exists anywhere in this codebase -- every extracted image is honestly reported as containing one <code>Unknown Object</code> placeholder with confidence 0.0, pending Stage 7 Admin Annotation. Nothing is ever invented.</p>
                      <Button onClick={runViVisionUnderstanding} disabled={viBusy}>Run vision understanding</Button>
                    </div>
                  )}
                  {viSessionData.vision_understanding_report?.vision_model_available !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.vision_understanding_report, null, 2)}</pre>
                  )}
                  <h4>Active objects</h4>
                  <ul className="notice">
                    {viObjectsList.map((o) => (
                      <li key={o.public_id}>
                        {o.label} -- confidence {o.confidence} -- source {o.source} -- {o.public_id.slice(0, 12)}
                        {o.bounding_box && Object.keys(o.bounding_box).length > 0 && ` -- box ${JSON.stringify(o.bounding_box)}`}
                      </li>
                    ))}
                    {!viObjectsList.length && <li>No objects recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {viSubTab === 'OCR Compare' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'ocr_cross_validation' && (
                    <div className="notice">
                      <p>Compares each page's real OCR text (already extracted by Document Workspace) against an optional linked dataset text. No vision model exists to describe image content for a true Image/OCR/Dataset three-way comparison -- this honestly compares only what is real and available. Never auto-corrects.</p>
                      <label>Dataset text to compare against (optional)<textarea rows={3} value={viDatasetTextInput} onChange={(e) => setViDatasetTextInput(e.target.value)} /></label>
                      <Button onClick={runViOcrCrossValidation} disabled={viBusy}>Run OCR cross validation</Button>
                    </div>
                  )}
                  {viSessionData.ocr_cross_validation_report?.pages_compared !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.ocr_cross_validation_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'Caption' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'caption_generation' && (
                    <div className="notice">
                      <p>No image-captioning model exists anywhere in this codebase -- a caption is only ever populated from an admin-supplied caption, never generated automatically. Always <code>verified: false</code>.</p>
                      <label>Admin-supplied caption (optional)<textarea rows={2} value={viAdminCaptionInput} onChange={(e) => setViAdminCaptionInput(e.target.value)} /></label>
                      <Button onClick={runViCaption} disabled={viBusy}>Set caption</Button>
                    </div>
                  )}
                  {viSessionData.caption_report?.source && (
                    <pre className="notice">{JSON.stringify(viSessionData.caption_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'Annotation' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'bounding_box_planning' && (
                    <div className="notice">
                      <p>No object-detection model exists anywhere in this codebase -- no box is ever planned automatically. This only classifies already admin-drawn boxes; nothing is auto-accepted.</p>
                      <Button onClick={runViBoundingBoxPlan} disabled={viBusy}>Run bounding box planning</Button>
                    </div>
                  )}
                  {viSessionData.bounding_box_report?.box_count !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.bounding_box_report, null, 2)}</pre>
                  )}
                  {viSessionData.stage === 'admin_annotation' && (
                    <div className="notice">
                      <p>Admin can rename, delete, add, correct a caption, correct a label, or redraw a box. Everything is recorded as an event, and delete is a soft status flip, never a row delete.</p>
                      <form className="inline-form training-form" onSubmit={submitViAnnotate}>
                        <label>Action
                          <select value={viAnnotateAction} onChange={(e) => setViAnnotateAction(e.target.value)}>
                            <option value="rename">rename</option>
                            <option value="delete">delete</option>
                            <option value="add">add</option>
                            <option value="correct_caption">correct_caption</option>
                            <option value="correct_label">correct_label</option>
                            <option value="redraw_box">redraw_box</option>
                          </select>
                        </label>
                        {viAnnotateAction !== 'add' && (
                          <label>Object
                            <select value={viAnnotateObjectId} onChange={(e) => setViAnnotateObjectId(e.target.value)}>
                              <option value="">select an object…</option>
                              {viObjectsList.map((o) => (
                                <option key={o.public_id} value={o.public_id}>{o.label} -- {o.public_id.slice(0, 12)}</option>
                              ))}
                            </select>
                          </label>
                        )}
                        {(viAnnotateAction === 'rename' || viAnnotateAction === 'correct_label' || viAnnotateAction === 'add') && (
                          <label>Label<input value={viAnnotateLabel} onChange={(e) => setViAnnotateLabel(e.target.value)} /></label>
                        )}
                        {viAnnotateAction === 'add' && (
                          <label>Image
                            <select value={viAnnotateImageId} onChange={(e) => setViAnnotateImageId(e.target.value)}>
                              <option value="">select an image…</option>
                              {viImagesList.map((img) => (
                                <option key={img.public_id} value={img.public_id}>page {img.page_number} #{img.image_index} -- {img.public_id.slice(0, 12)}</option>
                              ))}
                            </select>
                          </label>
                        )}
                        {viAnnotateAction === 'correct_caption' && (
                          <label>Caption<input value={viAnnotateCaption} onChange={(e) => setViAnnotateCaption(e.target.value)} /></label>
                        )}
                        {(viAnnotateAction === 'redraw_box' || viAnnotateAction === 'add') && (
                          <>
                            <label>Box x (0-1)<input value={viAnnotateBoxX} onChange={(e) => setViAnnotateBoxX(e.target.value)} /></label>
                            <label>Box y (0-1)<input value={viAnnotateBoxY} onChange={(e) => setViAnnotateBoxY(e.target.value)} /></label>
                            <label>Box width (0-1)<input value={viAnnotateBoxW} onChange={(e) => setViAnnotateBoxW(e.target.value)} /></label>
                            <label>Box height (0-1)<input value={viAnnotateBoxH} onChange={(e) => setViAnnotateBoxH(e.target.value)} /></label>
                          </>
                        )}
                        <Button type="submit" disabled={viBusy}>{viBusy ? 'Working…' : 'Apply annotation'}</Button>
                      </form>
                      <Button onClick={runViFinishAnnotation} disabled={viBusy}>Finish annotation stage</Button>
                    </div>
                  )}
                  {viSessionData.annotation_report?.total_annotations !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.annotation_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'Knowledge Graph' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'knowledge_graph' && (
                    <div className="notice">
                      <p>Relationships (contains/inside/overlaps/near) are derived purely from real bounding-box geometry -- never a semantic or causal claim about what the objects actually depict.</p>
                      <Button onClick={runViKnowledgeGraph} disabled={viBusy}>Build knowledge graph</Button>
                    </div>
                  )}
                  {viSessionData.knowledge_graph_report?.node_count !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.knowledge_graph_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'QA' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'qa_generation' && (
                    <div className="notice">
                      <p>Generates educational questions from admin-verified objects and caption -- always <code>verified: false</code>.</p>
                      <Button onClick={runViQaGeneration} disabled={viBusy}>Generate vision questions</Button>
                    </div>
                  )}
                  {viSessionData.qa_report?.question_count !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.qa_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'Vision Draft' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'vision_dataset_draft' && (
                    <div className="notice">
                      <p>Assembles image metadata, OCR, caption, bounding boxes, objects, QA, and the knowledge graph into one draft. Nothing is inserted into Dataset Studio -- always <code>verified: false</code>.</p>
                      <Button onClick={runViDatasetDraft} disabled={viBusy}>Build vision dataset draft</Button>
                    </div>
                  )}
                  {viSessionData.vision_dataset_draft_report?.status && (
                    <pre className="notice">{JSON.stringify(viSessionData.vision_dataset_draft_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'Report' && (
            <>
              {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
              {viSessionData && (
                <>
                  {viSessionData.stage === 'vision_quality_score' && (
                    <div className="notice">
                      <Button onClick={runViQualityScore} disabled={viBusy}>Compute vision quality score</Button>
                    </div>
                  )}
                  {viSessionData.vision_quality_score_report?.overall_vision_score !== undefined && (
                    <pre className="notice">{JSON.stringify(viSessionData.vision_quality_score_report, null, 2)}</pre>
                  )}
                  {viSessionData.stage === 'vision_report' && (
                    <div className="notice">
                      <Button onClick={runViGenerateReport} disabled={viBusy}>Generate vision report</Button>
                    </div>
                  )}
                  {viSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Vision Report ready for review.</p>
                      <pre className="notice">{JSON.stringify(viSessionData.vision_report, null, 2)}</pre>
                      <Button onClick={() => runViAdminReview('approve')} disabled={viBusy}>Approve</Button>{' '}
                      <Button onClick={() => runViAdminReview('reject')} disabled={viBusy}>Reject</Button>{' '}
                      <Button onClick={() => runViAdminReview('request_fix')} disabled={viBusy}>Request Fix</Button>{' '}
                      <Button onClick={() => runViAdminReview('archive')} disabled={viBusy}>Archive</Button>
                    </div>
                  )}
                  {viSessionData.stage === 'certified' && (
                    <div className="notice">
                      <p>Vision Certified -- eligible for MB-15 Multimodal Dataset Generator, MB-16 Vision RAG, and MB-17 Multimodal Training Pipeline. This service never submits it to any of them automatically.</p>
                    </div>
                  )}
                  {viSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Vision cycle closed with status <strong>{viSessionData.status}</strong>. No automatic action was taken.</p>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {viSubTab === 'History' && viSessionData && (
            <>
              <h4>Cycle events</h4>
              <ul className="notice">
                {viEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!viEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {viSubTab === 'History' && !viSessionData && (
            <div className="notice">Select a vision cycle in Overview first.</div>
          )}

          {viSubTab === 'Diagnostics' && (
            <>
              {viDiag && <pre className="notice">{JSON.stringify(viDiag, null, 2)}</pre>}
              {!viDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Vision Model Center' && (
        <>
          <p className="notice">
            MB-15 -- Vision Model Integration &amp; Human-in-the-Loop Annotation Center. Not another
            Vision Intelligence module -- that is MB-14, whose images and objects this phase only ever
            reads. MB-15 connects a real, pluggable vision inference backend to MB-14's already-extracted
            images and structures whatever it predicts into suggestions. No vision model file exists
            anywhere in this environment, so predictions are honestly empty until an admin configures a
            real model. Everything here requires explicit admin approval -- nothing is accepted
            automatically, and no dataset, document, MB-14 row, training run, runtime, GGUF export, or RAG
            index is ever touched by this service.
          </p>

          <div className="dataset-tabs">
            {vmSubTabs.map((t) => (
              <Button key={t} className={vmSubTab === t ? 'active' : ''} onClick={() => setVmSubTab(t)}>{t}</Button>
            ))}
          </div>

          {vmSubTab === 'Overview' && (
            <>
              {vmDiag && (
                <div className="notice">
                  <p><strong>Vision model file present:</strong> {String(vmDiag.vision_model_file_present)} -- <strong>LLaVA GGUF library available:</strong> {String(vmDiag.backend_library_available?.llava_gguf)}</p>
                  <p><strong>Dataset writes:</strong> {String(vmDiag.dataset_writes_performed)} -- <strong>MB-14 writes:</strong> {String(vmDiag.mb14_writes_performed)} -- <strong>Training started:</strong> {String(vmDiag.training_started)} -- <strong>Automatic approval:</strong> {String(vmDiag.automatic_approval)}</p>
                </div>
              )}
              {vmSessionData && (
                <section className="metric-grid">
                  <StatusCard label="MB-14 session" value={vmSessionData.vision_session_public_id.slice(0, 12)} tone="neutral" />
                  <StatusCard label="Provider" value={vmSessionData.provider_key} tone="neutral" />
                  <StatusCard label="Stage" value={vmSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={vmSessionData.status} tone={vmSessionData.status.includes('reject') ? 'waiting' : vmSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Vision model cycles</h4>
                  <ul className="notice">
                    {vmSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={vmSelectedId === s.public_id ? 'active' : ''} onClick={() => selectVmSession(s.public_id)}>
                          {s.provider_key} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!vmSessionsList.length && <li>No vision model cycles yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitVmCreateSession}>
                    <label>MB-14 vision session public ID<input value={vmNewVisionSessionId} onChange={(e) => setVmNewVisionSessionId(e.target.value)} placeholder="a certified or in-progress MB-14 session" /></label>
                    <label>Provider
                      <select value={vmNewProviderKey} onChange={(e) => setVmNewProviderKey(e.target.value)}>
                        {vmProvidersList.filter((p) => p.status === 'active').map((p) => (
                          <option key={p.provider_key} value={p.provider_key}>{p.display_name}</option>
                        ))}
                      </select>
                    </label>
                    <Button type="submit" disabled={vmBusy || !vmNewVisionSessionId.trim()}>{vmBusy ? 'Working…' : 'Start vision model cycle'}</Button>
                  </form>
                </div>
                <div>
                  {!vmSessionData && <div className="notice">Select or start a vision model cycle to work through it in the other sub-tabs.</div>}
                  {vmSessionData && (
                    <>
                      <h4>Cycle events</h4>
                      <ul className="notice">
                        {vmEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!vmEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {vmSubTab === 'Providers' && (
            <>
              <h4>Provider registry</h4>
              <ul className="notice">
                {vmProvidersList.map((p) => (
                  <li key={p.provider_key}>
                    <strong>{p.display_name}</strong> ({p.provider_key}, {p.backend_type}/{p.hardware_target}) --{' '}
                    <span className={`pill ${p.status === 'active' ? 'good' : 'neutral'}`}>{p.status}</span>{' '}
                    <Button onClick={() => toggleVmProviderStatus(p.provider_key, p.status)} disabled={vmBusy}>
                      {p.status === 'active' ? 'Deactivate' : 'Activate'}
                    </Button>
                    <div>{p.description}</div>
                  </li>
                ))}
              </ul>

              {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
              {vmSessionData && (
                <>
                  {vmSessionData.stage === 'image_load' && (
                    <div className="notice">
                      <p>Reads MB-14's own already-extracted image metadata read-only.</p>
                      <Button onClick={runVmImageLoad} disabled={vmBusy}>Load images from MB-14</Button>
                    </div>
                  )}
                  {vmSessionData.image_load_report?.image_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.image_load_report, null, 2)}</pre>
                  )}
                  {vmSessionData.stage === 'provider_selection' && (
                    <div className="notice">
                      <p>No vision model file exists anywhere in this environment by default -- supply real paths only if one has been placed on disk. Otherwise every prediction stage will honestly report the provider unavailable.</p>
                      <label>Model path (optional)<input value={vmModelPath} onChange={(e) => setVmModelPath(e.target.value)} placeholder="/path/to/vision-model.gguf" /></label>
                      <label>CLIP mmproj path (optional, LLaVA only)<input value={vmMmprojPath} onChange={(e) => setVmMmprojPath(e.target.value)} placeholder="/path/to/mmproj.gguf" /></label>
                      <Button onClick={runVmProviderSelection} disabled={vmBusy}>Select provider</Button>
                    </div>
                  )}
                  {vmSessionData.provider_report?.selected !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.provider_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vmSubTab === 'Detection' && (
            <>
              {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
              {vmSessionData && (
                <>
                  {vmSessionData.stage === 'object_detection' && (
                    <div className="notice">
                      <p>Real bounding boxes are never produced by any provider in this codebase -- no detection-capable model architecture exists for any of them.</p>
                      <Button onClick={runVmObjectDetection} disabled={vmBusy}>Run object detection</Button>
                    </div>
                  )}
                  {vmSessionData.detection_report?.object_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.detection_report, null, 2)}</pre>
                  )}

                  <h4>Predictions</h4>
                  <ul className="notice">
                    {vmPredictionsList.map((p) => (
                      <li key={p.public_id}>
                        {p.label} -- confidence {p.confidence} -- {p.source} -- <span className="pill neutral">{p.review_status}</span> -- {p.public_id.slice(0, 12)}
                      </li>
                    ))}
                    {!vmPredictionsList.length && <li>No predictions yet.</li>}
                  </ul>

                  {vmSessionData.stage === 'admin_review' && (
                    <div className="notice">
                      <p>Admin can approve, reject, rename, split, merge, delete, add, move box, resize box, or rotate box. Every correction becomes permanent Vision Correction Memory.</p>
                      <form className="inline-form training-form" onSubmit={submitVmReview}>
                        <label>Action
                          <select value={vmReviewAction} onChange={(e) => setVmReviewAction(e.target.value)}>
                            {vmReviewActions.map((a) => <option key={a} value={a}>{a}</option>)}
                          </select>
                        </label>
                        {vmReviewAction !== 'add' && vmReviewAction !== 'merge' && (
                          <label>Prediction
                            <select value={vmReviewPredictionId} onChange={(e) => setVmReviewPredictionId(e.target.value)}>
                              <option value="">select a prediction…</option>
                              {vmPredictionsList.map((p) => (
                                <option key={p.public_id} value={p.public_id}>{p.label} -- {p.public_id.slice(0, 12)}</option>
                              ))}
                            </select>
                          </label>
                        )}
                        {(vmReviewAction === 'rename' || vmReviewAction === 'add') && (
                          <label>Label<input value={vmReviewLabel} onChange={(e) => setVmReviewLabel(e.target.value)} /></label>
                        )}
                        {vmReviewAction === 'add' && (
                          <label>Image public ID<input value={vmReviewImageId} onChange={(e) => setVmReviewImageId(e.target.value)} /></label>
                        )}
                        {['move_box', 'resize_box', 'rotate_box', 'add'].includes(vmReviewAction) && (
                          <>
                            <label>Box x (0-1)<input value={vmReviewBoxX} onChange={(e) => setVmReviewBoxX(e.target.value)} /></label>
                            <label>Box y (0-1)<input value={vmReviewBoxY} onChange={(e) => setVmReviewBoxY(e.target.value)} /></label>
                            <label>Box width (0-1)<input value={vmReviewBoxW} onChange={(e) => setVmReviewBoxW(e.target.value)} /></label>
                            <label>Box height (0-1)<input value={vmReviewBoxH} onChange={(e) => setVmReviewBoxH(e.target.value)} /></label>
                          </>
                        )}
                        <Button type="submit" disabled={vmBusy}>{vmBusy ? 'Working…' : 'Apply review'}</Button>
                      </form>
                      <Button onClick={runVmFinishReview} disabled={vmBusy}>Finish admin review stage</Button>
                    </div>
                  )}
                  {vmSessionData.admin_review_report?.total_predictions !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.admin_review_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vmSubTab === 'Scene' && (
            <>
              {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
              {vmSessionData && (
                <>
                  {vmSessionData.stage === 'scene_detection' && (
                    <div className="notice">
                      <Button onClick={runVmSceneDetection} disabled={vmBusy}>Run scene detection</Button>
                    </div>
                  )}
                  {vmSessionData.scene_report?.provider_available !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.scene_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vmSubTab === 'Caption' && (
            <>
              {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
              {vmSessionData && (
                <>
                  {vmSessionData.stage === 'caption_generation' && (
                    <div className="notice">
                      <Button onClick={runVmCaption} disabled={vmBusy}>Run caption generation</Button>
                    </div>
                  )}
                  {vmSessionData.caption_report?.provider_available !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.caption_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vmSubTab === 'Relationships' && (
            <>
              {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
              {vmSessionData && (
                <>
                  {vmSessionData.stage === 'relationship_detection' && (
                    <div className="notice">
                      <p>Reuses MB-14's own real bounding-box geometry -- zero new relationship logic.</p>
                      <Button onClick={runVmRelationshipDetection} disabled={vmBusy}>Detect relationships (preview)</Button>
                    </div>
                  )}
                  {vmSessionData.relationship_report?.node_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.relationship_report, null, 2)}</pre>
                  )}
                  {vmSessionData.stage === 'ocr_cross_validation' && (
                    <div className="notice">
                      <label>Dataset text to compare against (optional)<textarea rows={3} value={vmDatasetTextInput} onChange={(e) => setVmDatasetTextInput(e.target.value)} /></label>
                      <Button onClick={runVmOcrCrossValidation} disabled={vmBusy}>Run OCR/vision/dataset cross validation</Button>
                    </div>
                  )}
                  {vmSessionData.ocr_cross_validation_report?.status && (
                    <pre className="notice">{JSON.stringify(vmSessionData.ocr_cross_validation_report, null, 2)}</pre>
                  )}
                  {vmSessionData.stage === 'knowledge_graph' && (
                    <div className="notice">
                      <p>Final knowledge graph, built from admin-approved predictions only.</p>
                      <Button onClick={runVmKnowledgeGraph} disabled={vmBusy}>Build final knowledge graph</Button>
                    </div>
                  )}
                  {vmSessionData.knowledge_graph_report?.node_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.knowledge_graph_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vmSubTab === 'Corrections' && (
            <>
              {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
              {vmSessionData && (
                <>
                  {vmSessionData.stage === 'correction_memory' && (
                    <div className="notice">
                      <Button onClick={runVmCorrectionMemory} disabled={vmBusy}>Summarize correction memory</Button>
                    </div>
                  )}
                  {vmSessionData.correction_memory_report?.total_corrections !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.correction_memory_report, null, 2)}</pre>
                  )}
                  <h4>Correction memory (permanent)</h4>
                  <ul className="notice">
                    {vmCorrectionsList.map((c) => (
                      <li key={c.public_id}>{c.created_at} -- {c.action} -- {c.wrong_label} -&gt; {c.correct_label || '(n/a)'} -- {c.reason}</li>
                    ))}
                    {!vmCorrectionsList.length && <li>No corrections recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {vmSubTab === 'Learning Memory' && (
            <>
              <p className="notice">Permanent, insert-only rollups -- MB-15 never retrains anything; a future training phase can reuse this history.</p>
              <ul className="notice">
                {vmLearningMemoryList.map((m) => (
                  <li key={m.public_id}>
                    {m.created_at} -- {m.provider_key} -- {m.total_predictions} prediction(s), {m.corrected_count} corrected, {m.rejected_count} rejected, rate {m.correction_rate}
                  </li>
                ))}
                {!vmLearningMemoryList.length && <li>No learning memory recorded yet.</li>}
              </ul>
            </>
          )}

          {vmSubTab === 'Reports' && (
            <>
              {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
              {vmSessionData && (
                <>
                  {vmSessionData.stage === 'quality_score' && (
                    <div className="notice">
                      <Button onClick={runVmQualityScore} disabled={vmBusy}>Compute AI-only quality score</Button>
                    </div>
                  )}
                  {vmSessionData.quality_report?.overall_vision_model_score !== undefined && (
                    <pre className="notice">{JSON.stringify(vmSessionData.quality_report, null, 2)}</pre>
                  )}
                  {vmSessionData.stage === 'dataset_draft' && (
                    <div className="notice">
                      <Button onClick={runVmDatasetDraft} disabled={vmBusy}>Build vision model dataset draft</Button>
                    </div>
                  )}
                  {vmSessionData.dataset_draft_report?.status && (
                    <pre className="notice">{JSON.stringify(vmSessionData.dataset_draft_report, null, 2)}</pre>
                  )}
                  {vmSessionData.stage === 'vision_report' && (
                    <div className="notice">
                      <Button onClick={runVmGenerateReport} disabled={vmBusy}>Generate vision model report</Button>
                    </div>
                  )}
                  {vmSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Vision Model Report ready for review.</p>
                      <pre className="notice">{JSON.stringify(vmSessionData.vision_report, null, 2)}</pre>
                      <Button onClick={() => runVmAdminReview('approve')} disabled={vmBusy}>Approve</Button>{' '}
                      <Button onClick={() => runVmAdminReview('reject')} disabled={vmBusy}>Reject</Button>{' '}
                      <Button onClick={() => runVmAdminReview('request_fix')} disabled={vmBusy}>Request Fix</Button>{' '}
                      <Button onClick={() => runVmAdminReview('archive')} disabled={vmBusy}>Archive</Button>
                    </div>
                  )}
                  {vmSessionData.stage === 'certified' && (
                    <div className="notice">
                      <p>Vision Model Certified -- eligible for MB-16 Multimodal Dataset Generator, MB-17 Vision RAG, and MB-18 Multimodal Training Pipeline. This service never submits it to any of them automatically.</p>
                    </div>
                  )}
                  {vmSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Vision model cycle closed with status <strong>{vmSessionData.status}</strong>. No automatic action was taken.</p>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {vmSubTab === 'History' && vmSessionData && (
            <>
              <h4>Cycle events</h4>
              <ul className="notice">
                {vmEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!vmEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {vmSubTab === 'History' && !vmSessionData && (
            <div className="notice">Select a vision model cycle in Overview first.</div>
          )}

          {vmSubTab === 'Diagnostics' && (
            <>
              {vmDiag && <pre className="notice">{JSON.stringify(vmDiag, null, 2)}</pre>}
              {!vmDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Multimodal Dataset Generator' && (
        <>
          <p className="notice">
            MB-16 -- Multimodal Dataset Generator Center. Not an OCR engine, vision model, language
            model, dataset writer, training engine, or runtime. It combines already-computed output from
            MB-13, MB-14, MB-15, Dataset Studio, and Document Workspace -- read through their own public
            methods only -- into one unified draft dataset spanning conversation, instruction, QA,
            caption, vision, grounding, reasoning, and training record flavors. Every record stays
            <code>verified: false</code> and every dataset stays Draft until an admin certifies it. Nothing
            here is ever written into Dataset Studio, Document Workspace, or any prior Mini Brain phase.
          </p>

          <div className="dataset-tabs">
            {mdSubTabs.map((t) => (
              <Button key={t} className={mdSubTab === t ? 'active' : ''} onClick={() => setMdSubTab(t)}>{t}</Button>
            ))}
          </div>

          {mdSubTab === 'Overview' && (
            <>
              {mdDiag && (
                <div className="notice">
                  <p><strong>Dataset Studio writes:</strong> {String(mdDiag.dataset_studio_writes_performed)} -- <strong>Document Workspace writes:</strong> {String(mdDiag.document_workspace_writes_performed)}</p>
                  <p><strong>Training started:</strong> {String(mdDiag.training_started)} -- <strong>Automatic export:</strong> {String(mdDiag.automatic_export)} -- <strong>Automatic approval:</strong> {String(mdDiag.automatic_approval)}</p>
                </div>
              )}
              {mdSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Document" value={mdSessionData.document_source_public_id.slice(0, 12)} tone="neutral" />
                  <StatusCard label="Stage" value={mdSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={mdSessionData.status} tone={mdSessionData.status.includes('reject') || mdSessionData.status === 'draft_deleted' ? 'waiting' : mdSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Multimodal dataset cycles</h4>
                  <ul className="notice">
                    {mdSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={mdSelectedId === s.public_id ? 'active' : ''} onClick={() => selectMdSession(s.public_id)}>
                          {s.document_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!mdSessionsList.length && <li>No multimodal dataset cycles yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitMdCreateSession}>
                    <label>Document source public ID<input value={mdNewDocumentId} onChange={(e) => setMdNewDocumentId(e.target.value)} placeholder="document public_id from Document Workspace" /></label>
                    <label>MB-14 vision session (optional)<input value={mdNewVisionSessionId} onChange={(e) => setMdNewVisionSessionId(e.target.value)} /></label>
                    <label>MB-13 language session (optional)<input value={mdNewLanguageSessionId} onChange={(e) => setMdNewLanguageSessionId(e.target.value)} /></label>
                    <label>MB-15 vision model session (optional)<input value={mdNewVisionModelSessionId} onChange={(e) => setMdNewVisionModelSessionId(e.target.value)} /></label>
                    <Button type="submit" disabled={mdBusy || !mdNewDocumentId.trim()}>{mdBusy ? 'Working…' : 'Start dataset cycle'}</Button>
                  </form>
                </div>
                <div>
                  {!mdSessionData && <div className="notice">Select or start a dataset cycle to work through it in the other sub-tabs.</div>}
                  {mdSessionData && (
                    <>
                      <h4>Cycle events</h4>
                      <ul className="notice">
                        {mdEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!mdEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {mdSubTab === 'Sources' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'collect_sources' && (
                    <div className="notice">
                      <Button onClick={runMdCollectSources} disabled={mdBusy}>Collect sources</Button>
                    </div>
                  )}
                  {mdSessionData.source_report?.available_source_count !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.source_report, null, 2)}</pre>
                  )}
                  {mdSessionData.stage === 'merge_metadata' && (
                    <div className="notice">
                      <p>Merges the text section, image section, and a reference (never regenerated) knowledge graph into one unified object.</p>
                      <Button onClick={runMdMergeMetadata} disabled={mdBusy}>Merge metadata</Button>
                    </div>
                  )}
                  {mdSessionData.metadata_report?.is_multimodal !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.metadata_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {mdSubTab === 'Text' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'collect_text' && (
                    <div className="notice">
                      <p>Reuses MB-13's own already-computed language/Unicode/OCR/Tanglish reports when a Language Intelligence session is linked; otherwise language-quality fields are honestly unavailable.</p>
                      <Button onClick={runMdCollectText} disabled={mdBusy}>Collect text</Button>
                    </div>
                  )}
                  {mdSessionData.text_section?.ocr_char_count !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.text_section, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {mdSubTab === 'Images' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'collect_images' && (
                    <div className="notice">
                      <p>Reuses MB-14's own image metadata/checksum/resolution/boxes/caption/objects/relationships/quality, plus MB-15's own vision-provider predictions and corrections when linked.</p>
                      <Button onClick={runMdCollectImages} disabled={mdBusy}>Collect images</Button>
                    </div>
                  )}
                  {mdSessionData.image_section?.image_count !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.image_section, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {mdSubTab === 'Conversation' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'conversation_builder' && (
                    <div className="notice">
                      <p>Builds User/Assistant turns only from real, already-computed data -- MB-14's own QA questions and real OCR text. Always <code>verified: false</code>.</p>
                      <Button onClick={runMdConversationBuilder} disabled={mdBusy}>Build conversations</Button>
                    </div>
                  )}
                  {mdSessionData.conversation_report?.conversation_count !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.conversation_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {mdSubTab === 'Instructions' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'instruction_builder' && (
                    <div className="notice">
                      <p>Builds instruction/input/output triples from real transcription, caption, and object-list data. No summarization model exists in this codebase.</p>
                      <Button onClick={runMdInstructionBuilder} disabled={mdBusy}>Build instructions</Button>
                    </div>
                  )}
                  {mdSessionData.instruction_report?.instruction_count !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.instruction_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {mdSubTab === 'QA' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  <p className="notice">QA-flavored records are a filtered view of the dataset draft -- reused from MB-14's own QA generation, never regenerated here.</p>
                  <ul className="notice">
                    {mdRecordsList.filter((r) => r.record_type === 'qa').map((r) => (
                      <li key={r.public_id}>{r.content.user} -- {r.content.assistant}</li>
                    ))}
                    {!mdRecordsList.filter((r) => r.record_type === 'qa').length && <li>No QA records yet -- build the dataset draft first.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {mdSubTab === 'Dataset Draft' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'dataset_draft' && (
                    <div className="notice">
                      <p>Assembles every record flavor (conversation, instruction, qa, caption, vision, grounding, reasoning, training) from already-built data. Nothing inserted into Dataset Studio.</p>
                      <Button onClick={runMdDatasetDraft} disabled={mdBusy}>Assemble dataset draft</Button>
                    </div>
                  )}
                  {mdSessionData.dataset_draft_report?.record_count !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.dataset_draft_report, null, 2)}</pre>
                  )}
                  <h4>Records ({mdRecordsList.length})</h4>
                  <ul className="notice">
                    {mdRecordsList.slice(0, 50).map((r) => (
                      <li key={r.public_id}>
                        <span className="pill neutral">{r.record_type}</span> {r.status !== 'active' && <span className="pill warn">{r.status}</span>} -- {r.public_id.slice(0, 12)}
                      </li>
                    ))}
                    {!mdRecordsList.length && <li>No records yet.</li>}
                  </ul>

                  {mdSessionData.stage === 'certified' && (
                    <>
                      <h4>Split into a new draft</h4>
                      <form className="inline-form training-form" onSubmit={submitMdSplit}>
                        <label>Record public IDs (comma-separated)<input value={mdSplitRecordIds} onChange={(e) => setMdSplitRecordIds(e.target.value)} /></label>
                        <Button type="submit" disabled={mdBusy}>Split dataset</Button>
                      </form>
                      <h4>Merge with other certified datasets</h4>
                      <form className="inline-form training-form" onSubmit={submitMdMerge}>
                        <label>Session public IDs incl. this one (comma-separated)<input value={mdMergeSessionIds} onChange={(e) => setMdMergeSessionIds(e.target.value)} /></label>
                        <Button type="submit" disabled={mdBusy}>Merge datasets</Button>
                      </form>
                    </>
                  )}

                  <h4>Export / Delete</h4>
                  <div className="notice">
                    <label>Format
                      <select value={mdExportFormat} onChange={(e) => setMdExportFormat(e.target.value)}>
                        <option value="json">json</option>
                        <option value="jsonl">jsonl</option>
                      </select>
                    </label>{' '}
                    <Button onClick={runMdExportDraft} disabled={mdBusy}>Export draft</Button>{' '}
                    {mdSessionData.stage !== 'certified' && (
                      <Button onClick={runMdDeleteDraft} disabled={mdBusy}>Delete draft</Button>
                    )}
                    {mdExportResult && (
                      <pre className="notice">{mdExportResult.content}</pre>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {mdSubTab === 'Quality' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'quality_analysis' && (
                    <div className="notice">
                      <Button onClick={runMdQualityAnalysis} disabled={mdBusy}>Run quality analysis</Button>
                    </div>
                  )}
                  {mdSessionData.quality_report?.overall_dataset_quality !== undefined && (
                    <pre className="notice">{JSON.stringify(mdSessionData.quality_report, null, 2)}</pre>
                  )}
                  {mdSessionData.stage === 'duplicate_detection' && (
                    <div className="notice">
                      <p>Reuses the existing ExternalDatasetDuplicateService (Phase 12) -- never a new duplicate-matching implementation.</p>
                      <Button onClick={runMdDuplicateDetection} disabled={mdBusy}>Run duplicate detection</Button>
                    </div>
                  )}
                  {mdSessionData.duplicate_report?.reused_service && (
                    <pre className="notice">{JSON.stringify(mdSessionData.duplicate_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {mdSubTab === 'Reports' && (
            <>
              {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
              {mdSessionData && (
                <>
                  {mdSessionData.stage === 'report' && (
                    <div className="notice">
                      <Button onClick={runMdGenerateReport} disabled={mdBusy}>Generate dataset report</Button>
                    </div>
                  )}
                  {mdSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>Dataset Report ready for review.</p>
                      <pre className="notice">{JSON.stringify(mdSessionData.dataset_report, null, 2)}</pre>
                      <Button onClick={() => runMdAdminReview('approve')} disabled={mdBusy}>Approve</Button>{' '}
                      <Button onClick={() => runMdAdminReview('reject')} disabled={mdBusy}>Reject</Button>{' '}
                      <Button onClick={() => runMdAdminReview('request_changes')} disabled={mdBusy}>Request Changes</Button>{' '}
                      <Button onClick={() => runMdAdminReview('archive')} disabled={mdBusy}>Archive</Button>
                    </div>
                  )}
                  {mdSessionData.stage === 'certified' && (
                    <div className="notice">
                      <p>Dataset Certified -- eligible for MB-17 Vision RAG, MB-18 Multimodal Training Pipeline, MB-19 Evaluation, and MB-20 Release Pipeline. This service never submits it to any of them automatically, and nothing has been written into Dataset Studio.</p>
                    </div>
                  )}
                  {mdSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Dataset cycle closed with status <strong>{mdSessionData.status}</strong>. No automatic action was taken.</p>
                    </div>
                  )}

                  <h4>Dataset Memory (permanent)</h4>
                  <ul className="notice">
                    {mdMemoryList.map((m) => (
                      <li key={m.public_id}>{m.created_at} -- v{m.dataset_version} -- {m.total_records} record(s) -- {m.admin_decision}</li>
                    ))}
                    {!mdMemoryList.length && <li>No dataset memory recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {mdSubTab === 'History' && mdSessionData && (
            <>
              <h4>Cycle events</h4>
              <ul className="notice">
                {mdEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!mdEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {mdSubTab === 'History' && !mdSessionData && (
            <div className="notice">Select a dataset cycle in Overview first.</div>
          )}

          {mdSubTab === 'Diagnostics' && (
            <>
              {mdDiag && <pre className="notice">{JSON.stringify(mdDiag, null, 2)}</pre>}
              {!mdDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
      )}

      {tab === 'Vision RAG' && (
        <>
          <p className="notice">
            MB-17 -- Vision RAG &amp; Multimodal Retrieval Center. Not an OCR engine, vision model,
            dataset generator, embedding trainer, training engine, runtime, or release pipeline. It
            answers questions using text, OCR, image, object, and knowledge-graph retrieval from an
            already-certified MB-16 dataset -- every answer stays evidence-linked, and if evidence is
            insufficient it says so honestly instead of guessing. It never edits Dataset Studio, Document
            Workspace, or any prior Mini Brain phase, and it runs no vision model inference of its own.
          </p>

          <div className="dataset-tabs">
            {vrSubTabs.map((t) => (
              <Button key={t} className={vrSubTab === t ? 'active' : ''} onClick={() => setVrSubTab(t)}>{t}</Button>
            ))}
          </div>

          {vrSubTab === 'Overview' && (
            <>
              {vrDiag && (
                <div className="notice">
                  <p><strong>Requires certified dataset:</strong> {String(vrDiag.requires_certified_dataset)} -- <strong>Vision model inference performed:</strong> {String(vrDiag.vision_model_inference_performed)}</p>
                  <p><strong>Dataset Studio writes:</strong> {String(vrDiag.dataset_studio_writes_performed)} -- <strong>Training started:</strong> {String(vrDiag.training_started)} -- <strong>Automatic approval:</strong> {String(vrDiag.automatic_approval)}</p>
                </div>
              )}
              {vrSessionData && (
                <section className="metric-grid">
                  <StatusCard label="Query" value={vrSessionData.query.slice(0, 24)} tone="neutral" />
                  <StatusCard label="Stage" value={vrSessionData.stage} tone="neutral" />
                  <StatusCard label="Status" value={vrSessionData.status} tone={vrSessionData.status.includes('reject') || vrSessionData.status.includes('hallucination') ? 'waiting' : vrSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                </section>
              )}
              <div className="training-grid">
                <div>
                  <h4>Vision RAG query sessions</h4>
                  <ul className="notice">
                    {vrSessionsList.map((s) => (
                      <li key={s.public_id}>
                        <Button className={vrSelectedId === s.public_id ? 'active' : ''} onClick={() => selectVrSession(s.public_id)}>
                          {s.query.slice(0, 30)} -- {s.stage} ({s.status})
                        </Button>
                      </li>
                    ))}
                    {!vrSessionsList.length && <li>No query sessions yet.</li>}
                  </ul>
                  <form className="inline-form training-form" onSubmit={submitVrCreateSession}>
                    <label>MB-16 certified dataset session public ID<input value={vrNewDatasetSessionId} onChange={(e) => setVrNewDatasetSessionId(e.target.value)} /></label>
                    <label>Query<input value={vrNewQuery} onChange={(e) => setVrNewQuery(e.target.value)} placeholder="Where is the river located?" /></label>
                    <Button type="submit" disabled={vrBusy || !vrNewDatasetSessionId.trim() || !vrNewQuery.trim()}>{vrBusy ? 'Working…' : 'Ask'}</Button>
                  </form>
                </div>
                <div>
                  {!vrSessionData && <div className="notice">Select or start a query session to work through it in the other sub-tabs.</div>}
                  {vrSessionData && (
                    <>
                      <h4>Session events</h4>
                      <ul className="notice">
                        {vrEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                        {!vrEventsList.length && <li>No events yet.</li>}
                      </ul>
                    </>
                  )}
                </div>
              </div>
            </>
          )}

          {vrSubTab === 'Query' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <div className="notice">
                  <p><strong>Query:</strong> {vrSessionData.query}</p>
                  <p><strong>Detected language:</strong> {vrSessionData.query_language}</p>
                  {vrSessionData.stage === 'query_session' && (
                    <Button onClick={runVrTextRetrieval} disabled={vrBusy}>Run text retrieval</Button>
                  )}
                </div>
              )}
            </>
          )}

          {vrSubTab === 'Results' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'grounded_answer' && (
                    <div className="notice">
                      <p>Never generates free text -- the answer is built only from real, already-retrieved evidence snippets with citation markers. If evidence is insufficient, it says so honestly.</p>
                      <Button onClick={runVrAnswer} disabled={vrBusy}>Generate grounded answer</Button>
                    </div>
                  )}
                  {vrSessionData.answer_report?.answer !== undefined && (
                    <div className="notice">
                      <p><strong>Answer:</strong> {vrSessionData.answer_report.answer}</p>
                      <p><strong>Confidence:</strong> {vrSessionData.answer_report.confidence} -- <strong>Status:</strong> {vrSessionData.answer_report.status}</p>
                      <pre className="notice">{JSON.stringify(vrSessionData.answer_report, null, 2)}</pre>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {vrSubTab === 'Evidence' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'evidence_fusion' && (
                    <div className="notice">
                      <Button onClick={runVrEvidenceFusion} disabled={vrBusy}>Fuse evidence</Button>
                    </div>
                  )}
                  {vrSessionData.evidence_fusion_report?.evidence_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vrSessionData.evidence_fusion_report, null, 2)}</pre>
                  )}
                  <h4>Evidence ({vrEvidenceList.length})</h4>
                  <ul className="notice">
                    {vrEvidenceList.map((e) => (
                      <li key={e.public_id}>
                        <span className="pill neutral">{e.evidence_type}</span> {e.used_in_answer && <span className="pill good">cited</span>} score={e.relevance_score} -- {e.content_snippet?.slice(0, 80)}
                      </li>
                    ))}
                    {!vrEvidenceList.length && <li>No evidence yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {vrSubTab === 'Images' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'image_retrieval' && (
                    <div className="notice">
                      <p>No semantic image embedding exists in this codebase -- images are matched by their real, already-computed caption text only.</p>
                      <Button onClick={runVrImageRetrieval} disabled={vrBusy}>Retrieve images</Button>
                    </div>
                  )}
                  {vrSessionData.image_retrieval_report?.image_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vrSessionData.image_retrieval_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vrSubTab === 'OCR' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'ocr_retrieval' && (
                    <div className="notice">
                      <Button onClick={runVrOcrRetrieval} disabled={vrBusy}>Retrieve OCR text</Button>
                    </div>
                  )}
                  {vrSessionData.ocr_retrieval_report?.ocr_record_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vrSessionData.ocr_retrieval_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vrSubTab === 'Objects' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'object_retrieval' && (
                    <div className="notice">
                      <p>Reuses MB-15's admin-approved predictions when linked, otherwise MB-14's admin-annotated objects -- never a new detection pass.</p>
                      <Button onClick={runVrObjectRetrieval} disabled={vrBusy}>Retrieve objects</Button>
                    </div>
                  )}
                  {vrSessionData.object_retrieval_report?.object_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vrSessionData.object_retrieval_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vrSubTab === 'Graph' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'knowledge_graph_retrieval' && (
                    <div className="notice">
                      <p>Never regenerates a graph -- only filters MB-14/MB-15's already-built graph down to query-relevant edges.</p>
                      <Button onClick={runVrKnowledgeGraphRetrieval} disabled={vrBusy}>Retrieve graph edges</Button>
                    </div>
                  )}
                  {vrSessionData.knowledge_graph_retrieval_report?.matched_edge_count !== undefined && (
                    <pre className="notice">{JSON.stringify(vrSessionData.knowledge_graph_retrieval_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vrSubTab === 'Quality' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'quality_evaluation' && (
                    <div className="notice">
                      <Button onClick={runVrQuality} disabled={vrBusy}>Evaluate RAG quality</Button>
                    </div>
                  )}
                  {vrSessionData.quality_report?.overall_rag_quality !== undefined && (
                    <pre className="notice">{JSON.stringify(vrSessionData.quality_report, null, 2)}</pre>
                  )}
                </>
              )}
            </>
          )}

          {vrSubTab === 'Hallucinations' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'hallucination_check' && (
                    <div className="notice">
                      <p>Every claim must trace to a real, cited evidence row -- reuses the production RAG system's own citation-validity and grounding-quality functions.</p>
                      <Button onClick={runVrHallucinationCheck} disabled={vrBusy}>Run hallucination check</Button>
                    </div>
                  )}
                  {vrSessionData.hallucination_report?.hallucination_risk !== undefined && (
                    <div className="notice">
                      <p><strong>Hallucination flag:</strong> <span className={`pill ${vrSessionData.hallucination_report.hallucination_flag ? 'block' : 'good'}`}>{String(vrSessionData.hallucination_report.hallucination_flag)}</span></p>
                      <pre className="notice">{JSON.stringify(vrSessionData.hallucination_report, null, 2)}</pre>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {vrSubTab === 'Reports' && (
            <>
              {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
              {vrSessionData && (
                <>
                  {vrSessionData.stage === 'report' && (
                    <div className="notice">
                      <Button onClick={runVrGenerateReport} disabled={vrBusy}>Generate RAG report</Button>
                    </div>
                  )}
                  {vrSessionData.stage === 'awaiting_admin_review' && (
                    <div className="notice">
                      <p>RAG Report ready for review.</p>
                      <pre className="notice">{JSON.stringify(vrSessionData.rag_report, null, 2)}</pre>

                      <h4>Correct before deciding (optional, repeatable)</h4>
                      <form className="inline-form training-form" onSubmit={submitVrCorrect}>
                        <label>Action
                          <select value={vrCorrectAction} onChange={(e) => setVrCorrectAction(e.target.value)}>
                            <option value="correct_answer">correct_answer</option>
                            <option value="correct_evidence">correct_evidence</option>
                            <option value="add_evidence">add_evidence</option>
                          </select>
                        </label>
                        {vrCorrectAction === 'correct_answer' && (
                          <label>Corrected answer<input value={vrCorrectAnswer} onChange={(e) => setVrCorrectAnswer(e.target.value)} /></label>
                        )}
                        {vrCorrectAction === 'correct_evidence' && (
                          <>
                            <label>Evidence public ID<input value={vrCorrectEvidenceId} onChange={(e) => setVrCorrectEvidenceId(e.target.value)} /></label>
                            <label>Corrected snippet<input value={vrCorrectSnippet} onChange={(e) => setVrCorrectSnippet(e.target.value)} /></label>
                          </>
                        )}
                        {vrCorrectAction === 'add_evidence' && (
                          <>
                            <label>Evidence type
                              <select value={vrAddEvidenceType} onChange={(e) => setVrAddEvidenceType(e.target.value)}>
                                <option value="text">text</option>
                                <option value="ocr">ocr</option>
                                <option value="image">image</option>
                                <option value="object">object</option>
                                <option value="graph_edge">graph_edge</option>
                              </select>
                            </label>
                            <label>Content snippet<input value={vrCorrectSnippet} onChange={(e) => setVrCorrectSnippet(e.target.value)} /></label>
                          </>
                        )}
                        <Button type="submit" disabled={vrBusy}>Apply correction</Button>
                      </form>

                      <h4>Final decision</h4>
                      <Button onClick={() => runVrAdminReview('approve')} disabled={vrBusy}>Approve</Button>{' '}
                      <Button onClick={() => runVrAdminReview('reject')} disabled={vrBusy}>Reject</Button>{' '}
                      <Button onClick={() => runVrAdminReview('flag_hallucination')} disabled={vrBusy}>Flag Hallucination</Button>{' '}
                      <Button onClick={() => runVrAdminReview('archive')} disabled={vrBusy}>Archive</Button>
                    </div>
                  )}
                  {vrSessionData.stage === 'closed' && (
                    <div className="notice">
                      <p>Query closed with status <strong>{vrSessionData.status}</strong>. RAG Memory recorded -- eligible for MB-18/19/20 to reuse, never submitted automatically.</p>
                    </div>
                  )}

                  <h4>RAG Memory (permanent)</h4>
                  <ul className="notice">
                    {vrMemoryList.map((m) => (
                      <li key={m.public_id}>{m.created_at} -- "{m.query.slice(0, 40)}" -- {m.admin_decision} -- confidence {m.confidence} -- hallucination {String(m.hallucination_flag)}</li>
                    ))}
                    {!vrMemoryList.length && <li>No RAG memory recorded yet.</li>}
                  </ul>
                </>
              )}
            </>
          )}

          {vrSubTab === 'History' && vrSessionData && (
            <>
              <h4>Session events</h4>
              <ul className="notice">
                {vrEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!vrEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
          {vrSubTab === 'History' && !vrSessionData && (
            <div className="notice">Select a query session in Overview first.</div>
          )}

          {vrSubTab === 'Diagnostics' && (
            <>
              {vrDiag && <pre className="notice">{JSON.stringify(vrDiag, null, 2)}</pre>}
              {!vrDiag && <Skeleton lines={2} />}
            </>
          )}
        </>
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
