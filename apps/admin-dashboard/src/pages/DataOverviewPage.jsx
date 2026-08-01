import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  datasetStatistics, datasetVersions, datasetDuplicates, qualitySummary,
  documents, corpusVersions, ragSpaces, baseModelReadinessEvaluations, governedBuildSummary,
  assistantOverview, verificationOverview, sampleImportOverview, ragSandboxOverview,
  incrementalTrainingOverview, knowledgeRoutingMetrics, publicChatRoutingOverview,
  knowledgeGapOverview, generateKnowledgeGapDailyReport,
  trustedWebOverview, toolsOverview,
} from '../services/api.js'

// Every number on this page comes directly from an existing API response.
// A group that could not be fetched renders the literal string below for
// each of its metrics, rather than a fabricated 0 -- see
// docs/data_studio/phase1_existing_data_system_audit.md.
const UNAVAILABLE = 'Not available in the current system'

// Grouped by underlying API call so a subsystem is only ever requested
// once, and a single failure honestly marks only the metrics that actually
// depended on it -- not the whole page.
const GROUPS = [
  {
    key: 'datasetStatistics',
    fetcher: datasetStatistics,
    metrics: [
      { key: 'sources', label: 'Total sources', pick: (data) => data.total_sources },
      { key: 'records', label: 'Dataset records', pick: (data) => data.total_records },
      { key: 'pendingReview', label: 'Records pending review', pick: (data) => data.pending_review_records },
      { key: 'approved', label: 'Approved records', pick: (data) => data.approved_records },
    ],
  },
  {
    key: 'documentsTotal',
    fetcher: () => documents('?page_size=1'),
    metrics: [{ key: 'documentsTotal', label: 'Total uploaded documents', pick: (data) => data.total }],
  },
  {
    key: 'documentsAwaiting',
    fetcher: () => documents('?status=review_ready&page_size=1'),
    metrics: [{ key: 'documentsAwaiting', label: 'Documents awaiting review', pick: (data) => data.total }],
  },
  {
    key: 'qualitySummary',
    fetcher: qualitySummary,
    metrics: [{ key: 'qualityIssues', label: 'Quality issues (blocked + warning)', pick: (data) => data.blocked + data.warning }],
  },
  {
    key: 'datasetDuplicates',
    fetcher: datasetDuplicates,
    metrics: [{ key: 'duplicates', label: 'Duplicate candidates', pick: (data) => data.items.length }],
  },
  {
    key: 'datasetVersions',
    fetcher: () => datasetVersions('?page_size=1'),
    metrics: [{ key: 'versions', label: 'Dataset versions', pick: (data) => data.total }],
  },
  {
    key: 'corpusVersions',
    fetcher: corpusVersions,
    metrics: [{ key: 'corpusVersions', label: 'Corpus builder versions', pick: (data) => data.items.length }],
  },
  {
    key: 'ragSpaces',
    fetcher: ragSpaces,
    metrics: [{ key: 'ragSpaces', label: 'RAG knowledge spaces', pick: (data) => data.items.length }],
  },
  {
    key: 'readiness',
    fetcher: baseModelReadinessEvaluations,
    metrics: [{
      key: 'readiness',
      label: 'Latest pretraining readiness result',
      pick: (data) => (data.items.length ? data.items[data.items.length - 1].overall_result : 'no_evaluation_yet'),
    }],
  },
  {
    key: 'governedBuilds',
    fetcher: governedBuildSummary,
    metrics: [
      { key: 'governedBuildsBlocked', label: 'Governed builds blocked', pick: (data) => data.counts_by_status.blocked || 0 },
      { key: 'governedBuildsReady', label: 'Governed builds preflight-ready', pick: (data) => data.counts_by_status.preflight_ready || 0 },
    ],
  },
  {
    key: 'adminAssistant',
    fetcher: assistantOverview,
    metrics: [
      { key: 'assistantPendingProposals', label: 'Admin Assistant proposals awaiting review', pick: (data) => data.summary.admin_approvals?.pending || 0 },
    ],
  },
  {
    key: 'datasetVerification',
    fetcher: verificationOverview,
    metrics: [
      { key: 'verificationAwaiting', label: 'Candidates awaiting verification', pick: (data) => data.candidates_awaiting_verification },
      { key: 'verificationInReview', label: 'Verification cases in review', pick: (data) => data.verification_cases_in_review },
      { key: 'verificationMissingLicence', label: 'Missing-licence cases', pick: (data) => data.missing_licence_cases },
      { key: 'verificationConflicting', label: 'Conflicting-evidence cases', pick: (data) => data.conflicting_evidence_cases },
      { key: 'verificationTrainingApproved', label: 'Training permission approved', pick: (data) => data.training_permission_approved },
      { key: 'verificationCommercialApproved', label: 'Commercial permission approved', pick: (data) => data.commercial_permission_approved },
      { key: 'verificationExpired', label: 'Verification expired', pick: (data) => data.verification_expired },
    ],
  },
  {
    key: 'datasetSampleImport',
    fetcher: sampleImportOverview,
    metrics: [
      { key: 'sampleImportsAwaitingApproval', label: 'Sample imports awaiting approval', pick: (data) => data.sample_imports_awaiting_approval },
      { key: 'samplesDownloading', label: 'Samples downloading', pick: (data) => data.samples_downloading },
      { key: 'samplesInQuarantine', label: 'Samples in quarantine', pick: (data) => data.samples_in_quarantine },
      { key: 'samplesNeedingReview', label: 'Samples needing review', pick: (data) => data.samples_needing_review },
      { key: 'samplesBlockedByPii', label: 'Samples blocked by PII', pick: (data) => data.samples_blocked_by_pii },
      { key: 'samplesBlockedBySecurity', label: 'Samples blocked by security', pick: (data) => data.samples_blocked_by_security },
      { key: 'samplesWithContamination', label: 'Samples with contamination', pick: (data) => data.samples_with_contamination },
      { key: 'samplesEligibleForRagSandbox', label: 'Samples eligible for RAG sandbox', pick: (data) => data.samples_eligible_for_rag_sandbox },
      { key: 'quarantineStorageUsed', label: 'Quarantine storage used (bytes)', pick: (data) => data.quarantine_storage_used_bytes },
    ],
  },
  {
    key: 'ragSandbox',
    fetcher: ragSandboxOverview,
    metrics: [
      { key: 'ragSandboxAwaitingApproval', label: 'RAG sandbox experiments awaiting approval', pick: (data) => data.rag_sandbox_experiments_awaiting_approval },
      { key: 'ragSandboxIndexesBuilding', label: 'RAG sandbox indexes building', pick: (data) => data.rag_sandbox_indexes_building },
      { key: 'ragSandboxReady', label: 'RAG sandbox experiments ready for testing', pick: (data) => data.rag_sandbox_experiments_ready_for_testing },
      { key: 'ragSandboxNeedingReview', label: 'RAG sandbox experiments needing human review', pick: (data) => data.rag_sandbox_experiments_needing_human_review },
      { key: 'ragSandboxAccepted', label: 'RAG sandbox experiments accepted', pick: (data) => data.rag_sandbox_experiments_accepted },
      { key: 'ragSandboxRejected', label: 'RAG sandbox experiments rejected', pick: (data) => data.rag_sandbox_experiments_rejected },
      { key: 'ragSandboxCitationFailures', label: 'RAG sandbox citation failures', pick: (data) => data.rag_sandbox_citation_failures },
      { key: 'ragSandboxUnsupportedClaimFailures', label: 'RAG sandbox unsupported-claim failures', pick: (data) => data.rag_sandbox_unsupported_claim_failures },
      { key: 'ragSandboxInjectionFailures', label: 'RAG sandbox injection-test failures', pick: (data) => data.rag_sandbox_injection_test_failures },
      { key: 'ragSandboxPotentiallyReady', label: 'RAG sandbox experiments potentially ready for production RAG', pick: (data) => data.rag_sandbox_experiments_potentially_ready_for_production_rag },
    ],
  },
  {
    key: 'incrementalTraining',
    fetcher: incrementalTrainingOverview,
    metrics: [
      { key: 'trainingAssessmentsAwaitingReview', label: 'Training assessments awaiting review', pick: (data) => data.training_assessments_awaiting_review },
      { key: 'trainingCandidatesNeedingTransformation', label: 'Training candidates needing transformation', pick: (data) => data.training_candidates_needing_transformation },
      { key: 'datasetPromotionsAwaitingApproval', label: 'Dataset promotions awaiting approval', pick: (data) => data.dataset_promotions_awaiting_approval },
      { key: 'trainingRunsAwaitingApproval', label: 'Training runs awaiting approval', pick: (data) => data.training_runs_awaiting_approval },
      { key: 'trainingRunsInProgress', label: 'Training runs in progress', pick: (data) => data.training_runs_in_progress },
      { key: 'trainingRunsFailed', label: 'Training runs failed', pick: (data) => data.training_runs_failed },
      { key: 'checkpointsAwaitingEvaluation', label: 'Checkpoints awaiting evaluation', pick: (data) => data.checkpoints_awaiting_evaluation },
      { key: 'checkpointsWithRegression', label: 'Checkpoints with regression', pick: (data) => data.checkpoints_with_regression },
      { key: 'checkpointsAwaitingAdminAcceptance', label: 'Checkpoints awaiting Admin acceptance', pick: (data) => data.checkpoints_awaiting_admin_acceptance },
      { key: 'acceptedModelCandidates', label: 'Accepted model candidates (staging)', pick: (data) => data.accepted_model_candidates },
    ],
  },
  {
    key: 'knowledgeRouting',
    fetcher: knowledgeRoutingMetrics,
    metrics: [
      { key: 'knowledgeRoutingTotal', label: 'Knowledge-routing classifications recorded', pick: (data) => data.total_classifications },
      { key: 'knowledgeRoutingNeedsReview', label: 'Knowledge-routing decisions needing human review', pick: (data) => data.requires_human_review_count },
    ],
  },
  {
    key: 'publicChatRouting',
    fetcher: publicChatRoutingOverview,
    metrics: [
      { key: 'publicChatRequests', label: 'Public chat requests', pick: (data) => data.total_requests },
      { key: 'publicChatCoreModelAnswers', label: 'Public chat core-model answers', pick: (data) => data.by_resolved_route.core_model || 0 },
      { key: 'publicChatRagAnswers', label: 'Public chat approved-RAG answers', pick: (data) => data.by_resolved_route.approved_rag || 0 },
      { key: 'publicChatMemoryAnswers', label: 'Public chat memory answers', pick: (data) => data.by_resolved_route.memory || 0 },
      { key: 'publicChatClarifications', label: 'Public chat clarification responses', pick: (data) => data.clarification_count },
      { key: 'publicChatRefusals', label: 'Public chat safety refusals', pick: (data) => data.refusal_count },
      { key: 'publicChatInsufficient', label: 'Public chat insufficient-evidence responses', pick: (data) => data.insufficient_count },
      { key: 'publicChatWebUnavailable', label: 'Public chat Trusted-Web recommended but unavailable', pick: (data) => data.trusted_web_unavailable_count },
      { key: 'publicChatToolUnavailable', label: 'Public chat Tool recommended but unavailable', pick: (data) => data.tool_unavailable_count },
      { key: 'publicChatLanguageViolations', label: 'Public chat Tanglish-output-compliance failures', pick: (data) => data.language_compliance.language_policy_violations },
    ],
  },
  {
    key: 'knowledgeGaps',
    fetcher: knowledgeGapOverview,
    metrics: [
      { key: 'knowledgeGapNewCases', label: 'New knowledge-gap cases', pick: (data) => data.by_status.new || 0 },
      { key: 'knowledgeGapHighPriority', label: 'High-priority unresolved cases', pick: (data) => (data.by_priority_band.critical || 0) + (data.by_priority_band.high || 0) },
      { key: 'knowledgeGapTamil', label: 'Tamil capability gaps', pick: (data) => data.tamil.tamil_capability_cases },
      { key: 'knowledgeGapRagInsufficiency', label: 'RAG insufficiency cases', pick: (data) => data.by_event_type.knowledge_gap || 0 },
      { key: 'knowledgeGapWebDemand', label: 'Web-unavailable demand', pick: (data) => data.web_demand.web_capability_gap_cases },
      { key: 'knowledgeGapToolDemand', label: 'Tool-unavailable demand', pick: (data) => data.tool_demand.tool_capability_gap_cases },
      { key: 'knowledgeGapWrongLanguage', label: 'Wrong-language failures', pick: (data) => data.language_failures.language_failure_cases },
      { key: 'knowledgeGapOperational', label: 'Operational failures', pick: (data) => data.by_event_type.operational_failure || 0 },
      { key: 'knowledgeGapAwaitingReview', label: 'Cases awaiting review', pick: (data) => data.cases_awaiting_review },
      { key: 'knowledgeGapRagEligible', label: 'Cases eligible for RAG research', pick: (data) => data.cases_eligible_for_rag_research },
      { key: 'knowledgeGapTrainingEligible', label: 'Cases eligible for training assessment', pick: (data) => data.cases_eligible_for_training_assessment },
    ],
  },
  {
    key: 'trustedWeb',
    fetcher: trustedWebOverview,
    metrics: [
      { key: 'trustedWebRequests', label: 'Trusted Web requests', pick: (data) => data.total_search_events },
      { key: 'trustedWebSuccessful', label: 'Successful Web answers', pick: (data) => data.by_status.success || 0 },
      { key: 'trustedWebInsufficient', label: 'Web insufficient-evidence responses', pick: (data) => data.by_status.evidence_insufficient || 0 },
      { key: 'trustedWebConflicts', label: 'Source conflicts', pick: (data) => Object.values(data.conflicts).reduce((sum, n) => sum + n, 0) },
      { key: 'trustedWebBlockedFetches', label: 'Blocked/stale-source fetch blocks', pick: (data) => data.blocked_fetches },
      { key: 'trustedWebInjectionBlocks', label: 'Injection-source blocks', pick: (data) => data.injection_blocked_sources },
      { key: 'trustedWebResolvedGaps', label: 'Resolved Web capability gaps', pick: (data) => data.resolved_web_capability_gaps },
    ],
  },
  {
    key: 'deterministicTools',
    fetcher: toolsOverview,
    metrics: [
      { key: 'toolCalculatorExecutions', label: 'Calculator executions', pick: (data) => data.by_tool.calculator || 0 },
      { key: 'toolUnitConversions', label: 'Unit conversions', pick: (data) => data.by_tool.unit_conversion || 0 },
      { key: 'toolDateCalculations', label: 'Date calculations', pick: (data) => data.by_tool.date_time_arithmetic || 0 },
      { key: 'toolFailures', label: 'Tool failures', pick: (data) => data.total_executions - (data.by_status.success || 0) },
      { key: 'toolExternalMcpEnabled', label: 'External MCP enabled', pick: (data) => String(data.external_mcp_enabled) },
      { key: 'toolResolvedGaps', label: 'Resolved Tool capability gaps', pick: (data) => data.resolved_tool_capability_gaps },
    ],
  },
]

const ACTIONS = [
  { label: 'Add / import data', activeKey: 'Datasets' },
  { label: 'Open documents', activeKey: 'Documents' },
  { label: 'Review quality', activeKey: 'Datasets' },
  { label: 'Open dataset versions', activeKey: 'Datasets' },
  { label: 'Open corpus builder', activeKey: 'Corpus Builder' },
  { label: 'Open RAG workspace', activeKey: 'Knowledge & RAG' },
  { label: 'Open pretraining readiness', activeKey: 'Pretraining Readiness' },
  { label: 'Open builds & pipelines', activeKey: 'Builds & Pipelines' },
  { label: 'Open Admin Assistant', activeKey: 'Admin Assistant' },
  { label: 'Open dataset verification', activeKey: 'Dataset Verification' },
  { label: 'Open Sample Import & Quarantine', activeKey: 'Sample Import & Quarantine' },
  { label: 'Open RAG Sandbox', activeKey: 'RAG Sandbox' },
  { label: 'Open Incremental Training', activeKey: 'Incremental Training' },
  { label: 'Open Knowledge Routing', activeKey: 'Knowledge Routing' },
  { label: 'Open Public Chat Routing', activeKey: 'Public Chat Routing' },
  { label: 'Open Knowledge Gaps', activeKey: 'Knowledge Gaps' },
  { label: 'Open Trusted Web', activeKey: 'Trusted Web' },
  { label: 'Open Deterministic Tools', activeKey: 'Deterministic Tools' },
  { label: 'Open Web Demand', activeKey: 'Knowledge Gaps' },
  { label: 'Open Tool Demand', activeKey: 'Knowledge Gaps' },
  { label: 'Ask Admin Assistant', activeKey: 'Admin Assistant' },
]

// The public chatbot is a separate app (`apps/chatbot`), not an Admin
// Dashboard page, so it needs an external link rather than an
// `activeKey` navigation entry. Matches the documented dev URL in
// README.md ("make chatbot # http://localhost:5173").
const PUBLIC_CHATBOT_URL = 'http://localhost:5173'

function initialResults() {
  const entries = GROUPS.flatMap((group) => group.metrics.map((metric) => [metric.key, { loading: true, value: null, error: false }]))
  return Object.fromEntries(entries)
}

export default function DataOverviewPage({ onNavigate }) {
  const [results, setResults] = useState(initialResults)
  const [reportStatus, setReportStatus] = useState('')

  async function generateDailyReport() {
    setReportStatus('generating')
    try {
      await generateKnowledgeGapDailyReport()
      setReportStatus('done')
    } catch {
      setReportStatus('error')
    }
  }

  useEffect(() => {
    let cancelled = false
    GROUPS.forEach(async (group) => {
      try {
        const data = await group.fetcher()
        if (cancelled) return
        setResults((current) => {
          const next = { ...current }
          for (const metric of group.metrics) next[metric.key] = { loading: false, value: metric.pick(data), error: false }
          return next
        })
      } catch {
        if (cancelled) return
        setResults((current) => {
          const next = { ...current }
          for (const metric of group.metrics) next[metric.key] = { loading: false, value: null, error: true }
          return next
        })
      }
    })
    return () => { cancelled = true }
  }, [])

  const metricList = GROUPS.flatMap((group) => group.metrics)
  const entries = metricList.map((metric) => ({ metric, entry: results[metric.key] }))
  const anyLoading = entries.some(({ entry }) => entry.loading)
  const anyError = entries.some(({ entry }) => entry.error)
  const allError = entries.every(({ entry }) => entry.error)

  return (
    <section className="data-overview-workspace">
      <header className="section-heading">
        <div>
          <h2>Data Overview</h2>
          <p>A read-only snapshot of every data-related area, built from existing dashboard data only.</p>
        </div>
      </header>
      {allError && (
        <div className="form-error" role="alert">
          None of the data services could be reached right now. Try again once the backend is available.
        </div>
      )}
      {!allError && anyError && (
        <div className="notice">Some sections could not be reached and show &quot;{UNAVAILABLE}&quot; below. The rest of this page remains usable.</div>
      )}
      {anyLoading && !allError && <div className="notice">Loading data overview…</div>}
      <section className="metric-grid" aria-busy={anyLoading}>
        {entries.map(({ metric, entry }) => {
          const value = entry.loading ? '…' : entry.error ? UNAVAILABLE : String(entry.value)
          return <StatusCard key={metric.key} label={metric.label} value={value} tone={entry.error ? 'waiting' : 'good'} />
        })}
      </section>
      <h3>Go to a workspace</h3>
      <div className="card-grid">
        {ACTIONS.map((action) => (
          <button key={action.label + action.activeKey} className="data-overview-action" onClick={() => onNavigate?.(action.activeKey)}>
            {action.label}
          </button>
        ))}
        <a className="data-overview-action" href={PUBLIC_CHATBOT_URL} target="_blank" rel="noopener noreferrer">
          Open Public Chatbot
        </a>
        <button className="data-overview-action" onClick={generateDailyReport}>
          {reportStatus === 'generating' ? 'Generating daily report…' : 'Generate Daily Report'}
        </button>
      </div>
      {reportStatus === 'done' && <p className="notice">Daily knowledge-gap report generated -- see the Knowledge Gaps page.</p>}
      {reportStatus === 'error' && <div className="form-error" role="alert">Could not generate the daily report right now.</div>}
    </section>
  )
}
