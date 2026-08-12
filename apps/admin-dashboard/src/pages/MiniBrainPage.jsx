import { useEffect, useRef, useState } from 'react'
import Button from '../components/Button.jsx'
import ChatPanel from '../components/chat/ChatPanel.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusCard from '../components/StatusCard.jsx'
import { useToast } from '../components/Toast.jsx'
import DiagnosticsTab from './mini-brain/DiagnosticsTab.jsx'
import AssistantIntelligenceTab from './mini-brain/AssistantIntelligenceTab.jsx'
import CapabilityTab from './mini-brain/CapabilityTab.jsx'
import ContinuousLearningCenterTab from './mini-brain/ContinuousLearningCenterTab.jsx'
import ContinuousLearningTab from './mini-brain/ContinuousLearningTab.jsx'
import DatasetEvolutionTab from './mini-brain/DatasetEvolutionTab.jsx'
import DatasetIntelligenceTab from './mini-brain/DatasetIntelligenceTab.jsx'
import EvaluationCenterTab from './mini-brain/EvaluationCenterTab.jsx'
import ExternalAIGatewayTab from './mini-brain/ExternalAIGatewayTab.jsx'
import FutureModelTab from './mini-brain/FutureModelTab.jsx'
import IntelligenceEngineTab from './mini-brain/IntelligenceEngineTab.jsx'
import KnowledgeCoreTab from './mini-brain/KnowledgeCoreTab.jsx'
import LanguageIntelligenceTab from './mini-brain/LanguageIntelligenceTab.jsx'
import LearningSupervisorTab from './mini-brain/LearningSupervisorTab.jsx'
import LocalSetupTab from './mini-brain/LocalSetupTab.jsx'
import LogsTab from './mini-brain/LogsTab.jsx'
import MultimodalDatasetGeneratorTab from './mini-brain/MultimodalDatasetGeneratorTab.jsx'
import OverviewTab from './mini-brain/OverviewTab.jsx'
import PipelineCoordinatorTab from './mini-brain/PipelineCoordinatorTab.jsx'
import PluginGovernanceTab from './mini-brain/PluginGovernanceTab.jsx'
import PluginRuntimeTab from './mini-brain/PluginRuntimeTab.jsx'
import ProviderSettingsTab from './mini-brain/ProviderSettingsTab.jsx'
import PublicChatRuntimeTab from './mini-brain/PublicChatRuntimeTab.jsx'
import ReleaseGovernanceTab from './mini-brain/ReleaseGovernanceTab.jsx'
import ReleasePipelineTab from './mini-brain/ReleasePipelineTab.jsx'
import ResearchCenterTab from './mini-brain/ResearchCenterTab.jsx'
import ResponseQualityTab from './mini-brain/ResponseQualityTab.jsx'
import RuntimeManagerTab from './mini-brain/RuntimeManagerTab.jsx'
import RuntimeTab from './mini-brain/RuntimeTab.jsx'
import SettingsTab from './mini-brain/SettingsTab.jsx'
import TrainingEngineTab from './mini-brain/TrainingEngineTab.jsx'
import TrainingPipelineTab from './mini-brain/TrainingPipelineTab.jsx'
import VisionIntelligenceTab from './mini-brain/VisionIntelligenceTab.jsx'
import VisionModelCenterTab from './mini-brain/VisionModelCenterTab.jsx'
import VisionRAGTab from './mini-brain/VisionRAGTab.jsx'
import VoiceRuntimeTab from './mini-brain/VoiceRuntimeTab.jsx'
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
const psProviderKeys = ['openrouter', 'openai', 'anthropic', 'gemini', 'faster_whisper', 'coqui_tts', 'local_llm']
const psRequiredSecrets = {
  openrouter: ['api_key'], openai: ['api_key'], anthropic: ['api_key'], gemini: ['api_key'],
  faster_whisper: [], coqui_tts: [], local_llm: [],
}
const lcExternalProviderKeys = ['openai', 'anthropic', 'gemini', 'openrouter']

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
        <TrainingPipelineTab
          tpSubTab={tpSubTab} setTpSubTab={setTpSubTab}
          tpDiag={tpDiag} tpSessionData={tpSessionData}
          tpSessionsList={tpSessionsList} tpSelectedId={tpSelectedId} selectTpSession={selectTpSession} submitTpCreateSession={submitTpCreateSession} tpNewTopic={tpNewTopic} setTpNewTopic={setTpNewTopic} tpBusy={tpBusy}
          tpEventsList={tpEventsList}
          submitTpCollectDatasets={submitTpCollectDatasets} tpDatasetSessionIds={tpDatasetSessionIds} setTpDatasetSessionIds={setTpDatasetSessionIds}
          submitTpCollectRagMemory={submitTpCollectRagMemory} tpRagSessionIds={tpRagSessionIds} setTpRagSessionIds={setTpRagSessionIds} tpAvailableRagMemory={tpAvailableRagMemory}
          runTpAnalyzeLanguage={runTpAnalyzeLanguage}
          runTpAnalyzeVision={runTpAnalyzeVision}
          runTpAnalyzeTokenizer={runTpAnalyzeTokenizer}
          submitTpPlanSplits={submitTpPlanSplits} tpSplitSeed={tpSplitSeed} setTpSplitSeed={setTpSplitSeed}
          runTpPlanCurriculum={runTpPlanCurriculum}
          runTpEstimateHardware={runTpEstimateHardware}
          runTpBuildPackage={runTpBuildPackage} tpPackagesList={tpPackagesList}
          runTpGenerateReport={runTpGenerateReport}
          runTpAdminReview={runTpAdminReview}
          tpMemoryList={tpMemoryList}
        />
      )}

      {tab === 'Evaluation Center' && (
        <EvaluationCenterTab
          ecSubTab={ecSubTab} setEcSubTab={setEcSubTab}
          ecDiag={ecDiag} ecSessionData={ecSessionData}
          ecSessionsList={ecSessionsList} ecSelectedId={ecSelectedId} selectEcSession={selectEcSession} submitEcCreateSession={submitEcCreateSession} ecNewTopic={ecNewTopic} setEcNewTopic={setEcNewTopic} ecBusy={ecBusy}
          ecEventsList={ecEventsList}
          submitEcCollectDatasets={submitEcCollectDatasets} ecDatasetSessionIds={ecDatasetSessionIds} setEcDatasetSessionIds={setEcDatasetSessionIds}
          submitEcCollectRagSessions={submitEcCollectRagSessions} ecRagSessionIds={ecRagSessionIds} setEcRagSessionIds={setEcRagSessionIds}
          submitEcCollectTrainingPackages={submitEcCollectTrainingPackages} ecPackageSessionIds={ecPackageSessionIds} setEcPackageSessionIds={setEcPackageSessionIds}
          runEcLanguageBenchmarks={runEcLanguageBenchmarks}
          runEcOcrBenchmarks={runEcOcrBenchmarks}
          runEcGroundingRetrievalBenchmarks={runEcGroundingRetrievalBenchmarks}
          runEcMultimodalBenchmarks={runEcMultimodalBenchmarks}
          runEcPackageBenchmarks={runEcPackageBenchmarks}
          submitEcRegression={submitEcRegression} ecBaselineSessionId={ecBaselineSessionId} setEcBaselineSessionId={setEcBaselineSessionId}
          runEcGenerateReport={runEcGenerateReport}
          runEcAdminReview={runEcAdminReview}
          ecMemoryList={ecMemoryList}
          ecExportsList={ecExportsList}
        />
      )}

      {tab === 'Release Governance' && (
        <ReleaseGovernanceTab
          rgSubTab={rgSubTab} setRgSubTab={setRgSubTab}
          rgDiag={rgDiag} rgSessionData={rgSessionData}
          rgSessionsList={rgSessionsList} rgSelectedId={rgSelectedId} selectRgSession={selectRgSession} submitRgCreateSession={submitRgCreateSession} rgNewTopic={rgNewTopic} setRgNewTopic={setRgNewTopic} rgBusy={rgBusy}
          rgEventsList={rgEventsList}
          submitRgCollectDatasets={submitRgCollectDatasets} rgDatasetSessionIds={rgDatasetSessionIds} setRgDatasetSessionIds={setRgDatasetSessionIds}
          submitRgCollectRag={submitRgCollectRag} rgRagSessionIds={rgRagSessionIds} setRgRagSessionIds={setRgRagSessionIds}
          submitRgCollectPackage={submitRgCollectPackage} rgPackageSessionId={rgPackageSessionId} setRgPackageSessionId={setRgPackageSessionId}
          submitRgCollectEvaluation={submitRgCollectEvaluation} rgEvaluationSessionId={rgEvaluationSessionId} setRgEvaluationSessionId={setRgEvaluationSessionId}
          runRgSafety={runRgSafety}
          runRgCompliance={runRgCompliance}
          runRgBenchmarks={runRgBenchmarks}
          runRgBuildRiskRollback={runRgBuildRiskRollback}
          runRgBuildPackage={runRgBuildPackage} rgArtifactsList={rgArtifactsList}
          runRgGenerateReport={runRgGenerateReport}
          runRgAdminReview={runRgAdminReview}
          rgMemoryList={rgMemoryList}
        />
      )}

      {tab === 'External AI Gateway' && (
        <ExternalAIGatewayTab
          gaSubTab={gaSubTab} setGaSubTab={setGaSubTab}
          gaDiag={gaDiag} gaSessionData={gaSessionData}
          gaSessionsList={gaSessionsList} gaSelectedId={gaSelectedId} selectGaSession={selectGaSession} submitGaCreateSession={submitGaCreateSession}
          gaNewTopic={gaNewTopic} setGaNewTopic={setGaNewTopic} gaNewPurpose={gaNewPurpose} setGaNewPurpose={setGaNewPurpose} gaNewDatasetIds={gaNewDatasetIds} setGaNewDatasetIds={setGaNewDatasetIds} gaNewRagId={gaNewRagId} setGaNewRagId={setGaNewRagId}
          gaBusy={gaBusy}
          gaEventsList={gaEventsList}
          submitGaAuthorize={submitGaAuthorize} gaAuthorizationNote={gaAuthorizationNote} setGaAuthorizationNote={setGaAuthorizationNote}
          submitGaSelectProviders={submitGaSelectProviders} gaProviderKeys={gaProviderKeys} setGaProviderKeys={setGaProviderKeys}
          runGaDispatch={runGaDispatch}
          submitGaSanitize={submitGaSanitize} gaAdminStatedNeed={gaAdminStatedNeed} setGaAdminStatedNeed={setGaAdminStatedNeed}
          runGaAction={runGaAction} gaSanitize={gaSanitize}
          runGaCollect={runGaCollect}
          runGaNormalize={runGaNormalize} gaProviderRunsList={gaProviderRunsList}
          runGaAnalyze={runGaAnalyze}
          runGaBuildEvidence={runGaBuildEvidence}
          runGaGenerateReport={runGaGenerateReport}
          runGaAdminReview={runGaAdminReview}
          runGaArchive={runGaArchive}
          gaMemoryList={gaMemoryList}
        />
      )}

      {tab === 'Training Engine' && (
        <TrainingEngineTab
          teSubTab={teSubTab} setTeSubTab={setTeSubTab}
          teDiag={teDiag} teJobData={teJobData}
          runTeValidateRelease={runTeValidateRelease} runTeValidatePackage={runTeValidatePackage}
          teJobsList={teJobsList} teSelectedId={teSelectedId} selectTeJob={selectTeJob} submitTeCreateJob={submitTeCreateJob}
          teNewTopic={teNewTopic} setTeNewTopic={setTeNewTopic} teNewPackageId={teNewPackageId} setTeNewPackageId={setTeNewPackageId} teNewReleaseId={teNewReleaseId} setTeNewReleaseId={setTeNewReleaseId}
          teNewExecutionMode={teNewExecutionMode} setTeNewExecutionMode={setTeNewExecutionMode} teBusy={teBusy}
          submitTeAuthorize={submitTeAuthorize} teAuthorizationReason={teAuthorizationReason} setTeAuthorizationReason={setTeAuthorizationReason}
          runTePlanResources={runTePlanResources}
          runTeBuildManifest={runTeBuildManifest}
          runTeReserveRuntime={runTeReserveRuntime}
          runTeStart={runTeStart}
          runTePause={runTePause} runTeCancel={runTeCancel} runTeResume={runTeResume}
          submitTeStreamMetric={submitTeStreamMetric} teMetricStep={teMetricStep} setTeMetricStep={setTeMetricStep} teMetricEpoch={teMetricEpoch} setTeMetricEpoch={setTeMetricEpoch} teMetricsList={teMetricsList}
          submitTeSaveCheckpoint={submitTeSaveCheckpoint} teCheckpointStep={teCheckpointStep} setTeCheckpointStep={setTeCheckpointStep} teCheckpointEpoch={teCheckpointEpoch} setTeCheckpointEpoch={setTeCheckpointEpoch} teCheckpointsList={teCheckpointsList}
          teEventsList={teEventsList}
          runTeFinalize={runTeFinalize}
          runTeGenerateReport={runTeGenerateReport}
          runTeArchive={runTeArchive}
          teMemoryList={teMemoryList}
        />
      )}

      {tab === 'Public Chat Runtime' && (
        <PublicChatRuntimeTab
          pcrSubTab={pcrSubTab} setPcrSubTab={setPcrSubTab}
          pcrAnalyticsData={pcrAnalyticsData} pcrCandidatesList={pcrCandidatesList} pcrDiag={pcrDiag}
          pcrSessionsList={pcrSessionsList} pcrSelectedSessionId={pcrSelectedSessionId} selectPcrSession={selectPcrSession} pcrSessionData={pcrSessionData}
          pcrMessagesList={pcrMessagesList}
          pcrSignalsList={pcrSignalsList}
          pcrClustersList={pcrClustersList}
          submitPcrGenerateCandidates={submitPcrGenerateCandidates} pcrMinFrequency={pcrMinFrequency} setPcrMinFrequency={setPcrMinFrequency} pcrBusy={pcrBusy}
          pcrSelectedCandidateId={pcrSelectedCandidateId} selectPcrCandidate={selectPcrCandidate}
          pcrCandidateData={pcrCandidateData} pcrReviewNotes={pcrReviewNotes} setPcrReviewNotes={setPcrReviewNotes} submitPcrReview={submitPcrReview} pcrCandidateEventsList={pcrCandidateEventsList}
          pcrApprovedCandidatesList={pcrApprovedCandidatesList}
          runPcrExportAnalytics={runPcrExportAnalytics} runPcrExportCandidates={runPcrExportCandidates} pcrExportResult={pcrExportResult}
        />
      )}

      {tab === 'Plugin Governance' && (
        <PluginGovernanceTab
          pgSubTab={pgSubTab} setPgSubTab={setPgSubTab}
          pgDiag={pgDiag} pgPluginsList={pgPluginsList} pgMemoryList={pgMemoryList} pgPluginData={pgPluginData} pgBusy={pgBusy}
          runPgValidate={runPgValidate} runPgClassify={runPgClassify} runPgRiskScore={runPgRiskScore} runPgSandbox={runPgSandbox} runPgFilesystemPolicy={runPgFilesystemPolicy} runPgNetworkPolicy={runPgNetworkPolicy} runPgEnable={runPgEnable}
          submitPgRegister={submitPgRegister} pgForm={pgForm} setPgForm={setPgForm}
          pgSelectedPluginId={pgSelectedPluginId} selectPgPlugin={selectPgPlugin}
          submitPgEvaluate={submitPgEvaluate} pgEvalScopeKey={pgEvalScopeKey} setPgEvalScopeKey={setPgEvalScopeKey} pgEvalIsPublicChat={pgEvalIsPublicChat} setPgEvalIsPublicChat={setPgEvalIsPublicChat} pgEvalUserIdHash={pgEvalUserIdHash} setPgEvalUserIdHash={setPgEvalUserIdHash}
          runPgPolicyCheck={runPgPolicyCheck} pgEvalResult={pgEvalResult} pgPolicyCheckResult={pgPolicyCheckResult} pgPermissionsList={pgPermissionsList} runPgGrant={runPgGrant} runPgRevoke={runPgRevoke}
          submitPgConsent={submitPgConsent} pgConsentScopeKey={pgConsentScopeKey} setPgConsentScopeKey={setPgConsentScopeKey} pgConsentUserIdentity={pgConsentUserIdentity} setPgConsentUserIdentity={setPgConsentUserIdentity}
          pgConsentGiven={pgConsentGiven} setPgConsentGiven={setPgConsentGiven} pgConsentTtl={pgConsentTtl} setPgConsentTtl={setPgConsentTtl} pgConsentsList={pgConsentsList}
          submitPgIssueToken={submitPgIssueToken} pgTokenScopeKeys={pgTokenScopeKeys} setPgTokenScopeKeys={setPgTokenScopeKeys} pgTokenUserIdentity={pgTokenUserIdentity} setPgTokenUserIdentity={setPgTokenUserIdentity}
          pgTokenSessionIdentity={pgTokenSessionIdentity} setPgTokenSessionIdentity={setPgTokenSessionIdentity} pgTokenTtl={pgTokenTtl} setPgTokenTtl={setPgTokenTtl} pgTokenResult={pgTokenResult}
          runPgReportExecution={runPgReportExecution} runPgGenerateReport={runPgGenerateReport} runPgDisable={runPgDisable} runPgArchive={runPgArchive} pgEventsList={pgEventsList}
        />
      )}

      {tab === 'Plugin Runtime' && (
        <PluginRuntimeTab
          prSubTab={prSubTab} setPrSubTab={setPrSubTab}
          prDiag={prDiag} prStats={prStats}
          submitPrExecute={submitPrExecute} prExecForm={prExecForm} setPrExecForm={setPrExecForm} prBusy={prBusy} prExecResult={prExecResult}
          prExecutionsList={prExecutionsList} prSelectedExecutionId={prSelectedExecutionId} selectPrExecution={selectPrExecution} runPrCancel={runPrCancel}
          prExecutionData={prExecutionData} prLogs={prLogs} runPrGenerateReport={runPrGenerateReport} runPrArchive={runPrArchive} prReportResult={prReportResult}
          submitPrPublicExecute={submitPrPublicExecute} prPublicForm={prPublicForm} setPrPublicForm={setPrPublicForm} prPublicResult={prPublicResult}
          runPrReportEvent={runPrReportEvent}
          prMemoryList={prMemoryList}
        />
      )}

      {tab === 'Voice Runtime' && (
        <VoiceRuntimeTab
          voSubTab={voSubTab} setVoSubTab={setVoSubTab}
          voDiag={voDiag} voStats={voStats}
          voConsent={voConsent} setVoConsent={setVoConsent} voBusy={voBusy} voRecording={voRecording} startVoRecording={startVoRecording} stopVoRecordingAndSend={stopVoRecordingAndSend} voSessionData={voSessionData}
          voSelectedSessionId={voSelectedSessionId} selectVoSession={selectVoSession} voSessionsList={voSessionsList}
          runVoTestStt={runVoTestStt} voTestSttText={voTestSttText}
          voTestTtsForm={voTestTtsForm} setVoTestTtsForm={setVoTestTtsForm} runVoTestTts={runVoTestTts} voTestTtsResult={voTestTtsResult}
          voMetrics={voMetrics}
          voEventsList={voEventsList}
          voMemoryList={voMemoryList}
        />
      )}

      {tab === 'Provider Settings' && (
        <ProviderSettingsTab
          psSubTab={psSubTab} setPsSubTab={setPsSubTab}
          psDiag={psDiag}
          renderPsProviderCard={renderPsProviderCard}
          psTestResults={psTestResults}
          psAuditList={psAuditList}
        />
      )}

      {tab === 'Assistant Intelligence' && (
        <AssistantIntelligenceTab
          admin={admin} toast={toast}
          lrDiag={lrDiag}
          lrSubTab={lrSubTab} setLrSubTab={setLrSubTab}
          submitLrExplainPage={submitLrExplainPage} lrExplainPageForm={lrExplainPageForm} setLrExplainPageForm={setLrExplainPageForm} lrBusy={lrBusy}
          submitLrSummarizeReport={submitLrSummarizeReport} lrReportForm={lrReportForm} setLrReportForm={setLrReportForm}
          submitLrSummarizeRegression={submitLrSummarizeRegression} lrRegressionForm={lrRegressionForm} setLrRegressionForm={setLrRegressionForm}
          submitLrExplainError={submitLrExplainError} lrErrorForm={lrErrorForm} setLrErrorForm={setLrErrorForm}
          submitLrNextActions={submitLrNextActions} lrStatusSnapshotForm={lrStatusSnapshotForm} setLrStatusSnapshotForm={setLrStatusSnapshotForm} lrNextActionsResult={lrNextActionsResult}
          lrLocalModelConfig={lrLocalModelConfig} setLrLocalModelConfig={setLrLocalModelConfig} saveLrLocalModelConfig={saveLrLocalModelConfig}
        />
      )}

      {tab === 'Local Setup' && (
        <LocalSetupTab
          lcSubTab={lcSubTab} setLcSubTab={setLcSubTab}
          lcHardwareData={lcHardwareData}
          lcSetupBusy={lcSetupBusy} runLcScan={runLcScan} lcScannedModels={lcScannedModels} selectLcScannedModel={selectLcScannedModel}
          loadLcRecommendations={loadLcRecommendations} lcRecommendationsData={lcRecommendationsData}
          lcLocalForm={lcLocalForm} setLcLocalForm={setLcLocalForm} saveLcLocalModel={saveLcLocalModel} testLcLocalModel={testLcLocalModel}
          lcCatalog={lcCatalog} lcProviderForm={lcProviderForm} updateLcProviderForm={updateLcProviderForm} saveLcProvider={saveLcProvider}
          lcDiag={lcDiag}
          loadLcGuide={loadLcGuide} lcGuide={lcGuide}
        />
      )}

      {tab === 'Runtime Manager' && (
        <RuntimeManagerTab
          rmStatusData={rmStatusData} rmHardwareData={rmHardwareData}
          rmSubTab={rmSubTab} setRmSubTab={setRmSubTab}
          rmBusy={rmBusy} installRecommendedModel={installRecommendedModel}
          rmCatalogData={rmCatalogData} setRmSelectedModelId={setRmSelectedModelId}
          rmInstalledList={rmInstalledList} runRmRemove={runRmRemove}
          rmSelectedModelId={rmSelectedModelId} runRmDownload={runRmDownload} runRmVerify={runRmVerify} runRmInstallSelected={runRmInstallSelected} rmLastActionResult={rmLastActionResult}
          rmLoadForm={rmLoadForm} setRmLoadForm={setRmLoadForm} runRmLoad={runRmLoad} runRmUnload={runRmUnload}
          rmBenchmarkPrompt={rmBenchmarkPrompt} setRmBenchmarkPrompt={setRmBenchmarkPrompt} runRmBenchmark={runRmBenchmark} rmLastBenchmarkResult={rmLastBenchmarkResult}
          loadRmEvents={loadRmEvents} rmEventsList={rmEventsList}
          loadRmHistory={loadRmHistory} rmMemoryList={rmMemoryList}
        />
      )}

      {tab === 'Future Model' && <FutureModelTab />}
    </section>
  )
}
