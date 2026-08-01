import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DataOverviewPage from './DataOverviewPage.jsx'

vi.mock('../services/api.js', () => ({
  datasetStatistics: vi.fn(),
  documents: vi.fn(),
  qualitySummary: vi.fn(),
  datasetDuplicates: vi.fn(),
  datasetVersions: vi.fn(),
  corpusVersions: vi.fn(),
  ragSpaces: vi.fn(),
  baseModelReadinessEvaluations: vi.fn(),
  governedBuildSummary: vi.fn(),
  assistantOverview: vi.fn(),
  verificationOverview: vi.fn(),
  sampleImportOverview: vi.fn(),
  ragSandboxOverview: vi.fn(),
  incrementalTrainingOverview: vi.fn(),
  knowledgeRoutingMetrics: vi.fn(),
  publicChatRoutingOverview: vi.fn(),
  knowledgeGapOverview: vi.fn(),
  generateKnowledgeGapDailyReport: vi.fn(),
  trustedWebOverview: vi.fn(),
  toolsOverview: vi.fn(),
}))

const api = await import('../services/api.js')

const SUCCESSFUL_RESPONSES = {
  datasetStatistics: { total_sources: 4, total_records: 10, pending_review_records: 1, approved_records: 5 },
  documentsTotal: { total: 2 },
  documentsAwaiting: { total: 0 },
  qualitySummary: { blocked: 0, warning: 0 },
  datasetDuplicates: { items: [{}] },
  datasetVersions: { total: 1 },
  corpusVersions: { items: [{}, {}, {}] },
  ragSpaces: { items: [] },
  readiness: { items: [] },
  governedBuilds: { counts_by_status: { blocked: 0, preflight_ready: 0 } },
  assistantOverview: { summary: { admin_approvals: { pending: 2 } }, guidance: [] },
  verificationOverview: {
    candidates_awaiting_verification: 3, verification_cases_in_review: 1,
    missing_licence_cases: 2, conflicting_evidence_cases: 0,
    training_permission_approved: 1, commercial_permission_approved: 0,
    verification_expired: 0,
  },
  sampleImportOverview: {
    sample_imports_awaiting_approval: 2, samples_downloading: 0, samples_in_quarantine: 1,
    samples_needing_review: 1, samples_blocked_by_pii: 0, samples_blocked_by_security: 0,
    samples_with_contamination: 0, samples_eligible_for_rag_sandbox: 1,
    quarantine_storage_used_bytes: 4096,
  },
  ragSandboxOverview: {
    rag_sandbox_experiments_awaiting_approval: 1, rag_sandbox_indexes_building: 0,
    rag_sandbox_experiments_ready_for_testing: 1, rag_sandbox_experiments_needing_human_review: 0,
    rag_sandbox_experiments_accepted: 0, rag_sandbox_experiments_rejected: 0,
    rag_sandbox_citation_failures: 0, rag_sandbox_unsupported_claim_failures: 0,
    rag_sandbox_injection_test_failures: 0,
    rag_sandbox_experiments_potentially_ready_for_production_rag: 0,
  },
  incrementalTrainingOverview: {
    training_assessments_awaiting_review: 1, training_candidates_needing_transformation: 0,
    dataset_promotions_awaiting_approval: 0, training_runs_awaiting_approval: 0,
    training_runs_in_progress: 0, training_runs_failed: 0,
    checkpoints_awaiting_evaluation: 0, checkpoints_with_regression: 0,
    checkpoints_awaiting_admin_acceptance: 0, accepted_model_candidates: 0,
  },
  knowledgeRoutingMetrics: { total_classifications: 5, requires_human_review_count: 1 },
  publicChatRoutingOverview: {
    total_requests: 8, by_resolved_route: { core_model: 3, approved_rag: 2, memory: 1 },
    clarification_count: 1, refusal_count: 0, insufficient_count: 1,
    trusted_web_unavailable_count: 1, tool_unavailable_count: 0,
    language_compliance: { total_answered: 8, language_policy_violations: 0 },
  },
  knowledgeGapOverview: {
    total_cases: 5, by_status: { new: 2 }, by_event_type: { knowledge_gap: 2, operational_failure: 1 },
    by_priority_band: { critical: 1, high: 1 },
    cases_awaiting_review: 1, cases_eligible_for_rag_research: 1, cases_eligible_for_training_assessment: 0,
    tamil: { tamil_capability_cases: 1, tamil_first_priority_boosted: 1 },
    web_demand: { web_capability_gap_cases: 1, total_occurrences: 3 },
    tool_demand: { tool_capability_gap_cases: 0, total_occurrences: 0 },
    language_failures: { language_failure_cases: 1 },
  },
  trustedWebOverview: {
    total_search_events: 4, by_status: { success: 3, evidence_insufficient: 1 },
    by_category: { current_general_information: 4 }, conflicts: { material_conflict: 1 },
    blocked_fetches: 0, injection_blocked_sources: 0, resolved_web_capability_gaps: 1,
  },
  toolsOverview: {
    total_executions: 6, by_tool: { calculator: 4, unit_conversion: 1, date_time_arithmetic: 1 },
    by_status: { success: 5, input_invalid: 1 }, external_mcp_enabled: false,
    resolved_tool_capability_gaps: 2,
  },
}

function mockAllSuccess(overrides = {}) {
  const responses = { ...SUCCESSFUL_RESPONSES, ...overrides }
  api.datasetStatistics.mockResolvedValue(responses.datasetStatistics)
  api.documents.mockImplementation(async (query) =>
    query?.includes('status=review_ready') ? responses.documentsAwaiting : responses.documentsTotal
  )
  api.qualitySummary.mockResolvedValue(responses.qualitySummary)
  api.datasetDuplicates.mockResolvedValue(responses.datasetDuplicates)
  api.datasetVersions.mockResolvedValue(responses.datasetVersions)
  api.corpusVersions.mockResolvedValue(responses.corpusVersions)
  api.ragSpaces.mockResolvedValue(responses.ragSpaces)
  api.baseModelReadinessEvaluations.mockResolvedValue(responses.readiness)
  api.governedBuildSummary.mockResolvedValue(responses.governedBuilds)
  api.assistantOverview.mockResolvedValue(responses.assistantOverview)
  api.verificationOverview.mockResolvedValue(responses.verificationOverview)
  api.sampleImportOverview.mockResolvedValue(responses.sampleImportOverview)
  api.ragSandboxOverview.mockResolvedValue(responses.ragSandboxOverview)
  api.incrementalTrainingOverview.mockResolvedValue(responses.incrementalTrainingOverview)
  api.knowledgeRoutingMetrics.mockResolvedValue(responses.knowledgeRoutingMetrics)
  api.publicChatRoutingOverview.mockResolvedValue(responses.publicChatRoutingOverview)
  api.knowledgeGapOverview.mockResolvedValue(responses.knowledgeGapOverview)
  api.generateKnowledgeGapDailyReport.mockResolvedValue({})
  api.trustedWebOverview.mockResolvedValue(responses.trustedWebOverview)
  api.toolsOverview.mockResolvedValue(responses.toolsOverview)
}

function mockAllFail() {
  const error = new Error('down')
  for (const fn of [
    api.datasetStatistics, api.documents, api.qualitySummary, api.datasetDuplicates,
    api.datasetVersions, api.corpusVersions, api.ragSpaces, api.baseModelReadinessEvaluations,
    api.governedBuildSummary, api.assistantOverview, api.verificationOverview,
    api.sampleImportOverview, api.ragSandboxOverview, api.incrementalTrainingOverview,
    api.knowledgeRoutingMetrics, api.publicChatRoutingOverview, api.knowledgeGapOverview,
    api.trustedWebOverview, api.toolsOverview,
  ]) {
    fn.mockRejectedValue(error)
  }
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('DataOverviewPage: success state', () => {
  it('renders every metric from real API responses, never a fabricated number', async () => {
    mockAllSuccess()
    render(<DataOverviewPage onNavigate={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('4'))
    expect(screen.getByText('Dataset records').nextSibling).toHaveTextContent('10')
    expect(screen.getByText('Approved records').nextSibling).toHaveTextContent('5')
    expect(screen.getByText('Total uploaded documents').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Corpus builder versions').nextSibling).toHaveTextContent('3')
    expect(screen.getByText('Admin Assistant proposals awaiting review').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Candidates awaiting verification').nextSibling).toHaveTextContent('3')
    expect(screen.getByText('Missing-licence cases').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Training permission approved').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Sample imports awaiting approval').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Samples eligible for RAG sandbox').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('RAG sandbox experiments ready for testing').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Training assessments awaiting review').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Public chat requests').nextSibling).toHaveTextContent('8')
    expect(screen.getByText('Public chat core-model answers').nextSibling).toHaveTextContent('3')
    expect(screen.getByText('Public chat approved-RAG answers').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Public chat clarification responses').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Public chat Trusted-Web recommended but unavailable').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Public chat Tanglish-output-compliance failures').nextSibling).toHaveTextContent('0')
    expect(screen.queryByText('Not available in the current system')).not.toBeInTheDocument()
  })

  it('renders honest zeros for an empty system, not a hidden/omitted card', async () => {
    mockAllSuccess({
      datasetStatistics: { total_sources: 0, total_records: 0, pending_review_records: 0, approved_records: 0 },
      documentsTotal: { total: 0 },
      corpusVersions: { items: [] },
    })
    render(<DataOverviewPage onNavigate={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('0'))
    expect(screen.getByText('Corpus builder versions').nextSibling).toHaveTextContent('0')
  })
})

describe('DataOverviewPage: partial failure', () => {
  it('marks only the failed subsystem as unavailable and keeps the rest of the page usable', async () => {
    mockAllSuccess()
    api.ragSpaces.mockRejectedValue(new Error('network error'))
    render(<DataOverviewPage onNavigate={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('RAG knowledge spaces').nextSibling).toHaveTextContent('Not available in the current system'))
    // Unrelated metrics still render real values.
    expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('4')
    expect(screen.getByText(/Some sections could not be reached/)).toBeInTheDocument()
    expect(screen.queryByText(/None of the data services could be reached/)).not.toBeInTheDocument()
  })
})

describe('DataOverviewPage: total failure', () => {
  it('shows one honest error rather than a page full of unavailable cards with no context', async () => {
    mockAllFail()
    render(<DataOverviewPage onNavigate={vi.fn()} />)
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/None of the data services could be reached/))
  })
})

describe('DataOverviewPage: navigation actions', () => {
  it('routes each action button to an existing page key via onNavigate', async () => {
    mockAllSuccess()
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(<DataOverviewPage onNavigate={onNavigate} />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('4'))
    await user.click(screen.getByRole('button', { name: 'Open documents' }))
    expect(onNavigate).toHaveBeenCalledWith('Documents')
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    expect(onNavigate).toHaveBeenCalledWith('Admin Assistant')
    await user.click(screen.getByRole('button', { name: 'Open dataset verification' }))
    expect(onNavigate).toHaveBeenCalledWith('Dataset Verification')
    await user.click(screen.getByRole('button', { name: 'Open Sample Import & Quarantine' }))
    expect(onNavigate).toHaveBeenCalledWith('Sample Import & Quarantine')
    await user.click(screen.getByRole('button', { name: 'Open RAG Sandbox' }))
    expect(onNavigate).toHaveBeenCalledWith('RAG Sandbox')
    await user.click(screen.getByRole('button', { name: 'Open Public Chat Routing' }))
    expect(onNavigate).toHaveBeenCalledWith('Public Chat Routing')
    await user.click(screen.getByRole('button', { name: 'Open Knowledge Gaps' }))
    expect(onNavigate).toHaveBeenCalledWith('Knowledge Gaps')
  })

  it('links Open Public Chatbot to the external chatbot app, not an internal page key', async () => {
    mockAllSuccess()
    render(<DataOverviewPage onNavigate={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('4'))
    const link = screen.getByRole('link', { name: 'Open Public Chatbot' })
    expect(link).toHaveAttribute('href', 'http://localhost:5173')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('shows real knowledge-gap metrics, never fabricated values', async () => {
    mockAllSuccess()
    render(<DataOverviewPage onNavigate={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('4'))
    expect(screen.getByText('New knowledge-gap cases').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('High-priority unresolved cases').nextSibling).toHaveTextContent('2')
    expect(screen.getByText('Tamil capability gaps').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Web-unavailable demand').nextSibling).toHaveTextContent('1')
  })

  it('generates a daily knowledge-gap report on demand', async () => {
    mockAllSuccess()
    const user = userEvent.setup()
    render(<DataOverviewPage onNavigate={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('Total sources').nextSibling).toHaveTextContent('4'))
    await user.click(screen.getByRole('button', { name: /generate daily report/i }))
    await waitFor(() => expect(api.generateKnowledgeGapDailyReport).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/daily knowledge-gap report generated/i)).toBeInTheDocument()
  })
})
