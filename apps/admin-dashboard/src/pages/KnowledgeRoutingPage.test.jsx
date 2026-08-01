import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import KnowledgeRoutingPage from './KnowledgeRoutingPage.jsx'

vi.mock('../services/api.js', () => ({
  classifyKnowledgeRoutingRecord: vi.fn(),
  classifyKnowledgeRoutingText: vi.fn(),
  knowledgeRoutingContextTypes: vi.fn(),
  knowledgeRoutingDecision: vi.fn(),
  knowledgeRoutingDecisions: vi.fn(),
  knowledgeRoutingMetrics: vi.fn(),
  knowledgeRoutingPolicy: vi.fn(),
  knowledgeRoutingReasonCodes: vi.fn(),
}))

const api = await import('../services/api.js')

function mockBaseline() {
  api.knowledgeRoutingMetrics.mockResolvedValue({
    total_classifications: 3,
    requires_human_review_count: 1,
    by_execution_route: { core_model: 2, trusted_web: 1 },
    by_domain: { tamil_language: 2, computer_and_coding: 1 },
    by_learning_target: { core_model: 2, web_preferred: 1 },
  })
  api.knowledgeRoutingPolicy.mockResolvedValue({
    valid: true, policy_version: 'v1', taxonomy_version: 'v1',
    policy_checksum_sha256: 'abc123', domain_count: 16, intent_count: 16,
  })
  api.knowledgeRoutingContextTypes.mockResolvedValue({
    context_types: ['public_chat_question', 'rag_record'],
  })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('KnowledgeRoutingPage: navigation', () => {
  it('renders all six required tabs', async () => {
    mockBaseline()
    render(<KnowledgeRoutingPage />)
    for (const tab of ['Overview', 'Try Classifier', 'Structured Record', 'Recent Decisions', 'Reason Codes', 'Policy']) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview shows real metrics, including totals and per-route counts', async () => {
    mockBaseline()
    render(<KnowledgeRoutingPage />)
    await waitFor(() => expect(screen.getByText('Total classifications').nextSibling).toHaveTextContent('3'))
    expect(screen.getByText('Requires human review').nextSibling).toHaveTextContent('1')
  })

  it('shows the recommendation-only banner', async () => {
    mockBaseline()
    render(<KnowledgeRoutingPage />)
    await waitFor(() => expect(screen.getAllByText(/Recommendation only/).length).toBeGreaterThan(0))
  })
})

describe('KnowledgeRoutingPage: Try Classifier', () => {
  it('classifies free text and displays the result', async () => {
    mockBaseline()
    api.classifyKnowledgeRoutingText.mockResolvedValue({
      execution_route: 'trusted_web', learning_target: 'web_preferred',
      language_category: 'en', intent: 'ask_current_status', intent_confidence_band: 'high',
      domain: 'computer_and_coding', subdomain: null, domain_confidence_band: 'medium',
      freshness: 'time_sensitive', freshness_confidence_band: 'medium', ambiguity: 'not_ambiguous',
      safety_risk: 'safe', safety_matched_category: null, safety_confidence_band: 'low',
      evidence_requirement: 'external_verified_evidence_required', evidence_confidence_band: 'medium',
      execution_route_confidence_band: 'medium', learning_target_confidence_band: 'medium',
      requires_human_review: false, tamil_first_policy_violation: false,
      all_reason_codes: ['LANG_ENGLISH_DETECTED', 'ROUTE_WEB_CURRENT_INFORMATION'],
      public_id: 'dec-1',
    })
    const user = userEvent.setup()
    render(<KnowledgeRoutingPage />)
    await user.click(screen.getByRole('button', { name: 'Try Classifier' }))
    await user.type(screen.getByPlaceholderText(/Type a question/), 'Python latest stable version?')
    await user.click(screen.getByRole('button', { name: 'Classify' }))
    await waitFor(() => expect(screen.getByText(/Execution route recommendation: trusted_web/)).toBeInTheDocument())
    expect(api.classifyKnowledgeRoutingText).toHaveBeenCalledWith({
      text: 'Python latest stable version?', context_type: 'public_chat_question',
    })
  })
})

describe('KnowledgeRoutingPage: Reason Codes', () => {
  it('loads and lists the reason-code registry', async () => {
    mockBaseline()
    api.knowledgeRoutingReasonCodes.mockResolvedValue({
      reason_codes: { LANG_TAMIL_DETECTED: 'Tamil script present.' }, count: 1,
    })
    const user = userEvent.setup()
    render(<KnowledgeRoutingPage />)
    await user.click(screen.getByRole('button', { name: 'Reason Codes' }))
    await waitFor(() => expect(screen.getByText('LANG_TAMIL_DETECTED')).toBeInTheDocument())
  })
})
