import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import KnowledgeGapsPage from './KnowledgeGapsPage.jsx'

vi.mock('../services/api.js', () => ({
  knowledgeGapOverview: vi.fn(),
  knowledgeGapCases: vi.fn(),
  knowledgeGapCase: vi.fn(),
  knowledgeGapOccurrences: vi.fn(),
  knowledgeGapReviews: vi.fn(),
  knowledgeGapNotes: vi.fn(),
  knowledgeGapEvents: vi.fn(),
  reviewKnowledgeGapCase: vi.fn(),
  addKnowledgeGapNote: vi.fn(),
  resolveKnowledgeGapCase: vi.fn(),
  archiveKnowledgeGapCase: vi.fn(),
  assessKnowledgeGapHandoff: vi.fn(),
  knowledgeGapClusters: vi.fn(),
  proposeKnowledgeGapMerge: vi.fn(),
  confirmKnowledgeGapMerge: vi.fn(),
  recalculateKnowledgeGapClusterPriority: vi.fn(),
  knowledgeGapDailyReports: vi.fn(),
  generateKnowledgeGapDailyReport: vi.fn(),
  requestKnowledgeGapDeletion: vi.fn(),
  knowledgeGapDeletionPreview: vi.fn(),
  confirmKnowledgeGapDeletion: vi.fn(),
  executeKnowledgeGapDeletion: vi.fn(),
}))

const api = await import('../services/api.js')

const OVERVIEW = {
  total_cases: 4,
  by_status: { new: 2, review_required: 1 },
  by_event_type: { knowledge_gap: 2, web_capability_gap: 1, operational_failure: 1 },
  by_priority_band: { high: 1, medium: 2 },
  cases_awaiting_review: 1,
  cases_eligible_for_rag_research: 1,
  cases_eligible_for_training_assessment: 0,
  tamil: { tamil_capability_cases: 1, tamil_first_priority_boosted: 1 },
  web_demand: { web_capability_gap_cases: 1, total_occurrences: 2 },
  tool_demand: { tool_capability_gap_cases: 0, total_occurrences: 0 },
  language_failures: { language_failure_cases: 0 },
}

const CASE = {
  public_id: 'case-1',
  canonical_question: 'what is the latest python version',
  event_type: 'web_capability_gap',
  language: 'en',
  frequency: 3,
  priority_band: 'high',
  status: 'new',
  stage: 'classification',
  reason_codes: ['web_search_unavailable'],
  eligible_for_rag_research: false,
  eligible_for_training_assessment: false,
  content_unavailable_for_review: false,
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('KnowledgeGapsPage', () => {
  it('renders real overview metrics -- never a fabricated number', async () => {
    api.knowledgeGapOverview.mockResolvedValue(OVERVIEW)
    render(<KnowledgeGapsPage />)
    await waitFor(() => expect(screen.getByText('Total cases').nextSibling).toHaveTextContent('4'))
    expect(screen.getByText('Awaiting review').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Tamil capability cases').nextSibling).toHaveTextContent('1')
  })

  it('loads and displays cases with no raw question text -- canonical only', async () => {
    api.knowledgeGapOverview.mockResolvedValue(OVERVIEW)
    api.knowledgeGapCases.mockResolvedValue({ cases: [CASE], count: 1 })
    render(<KnowledgeGapsPage />)
    await waitFor(() => expect(screen.getByText('Total cases').nextSibling).toHaveTextContent('4'))

    await userEvent.click(screen.getByRole('button', { name: 'New Cases' }))
    await waitFor(() => expect(api.knowledgeGapCases).toHaveBeenCalledWith('?status=new'))
    expect(await screen.findByText('what is the latest python version')).toBeInTheDocument()
    expect(screen.getAllByText(/redacted canonical questions only/i).length).toBeGreaterThan(0)
  })

  it('opens a case detail panel and submits a review decision', async () => {
    api.knowledgeGapOverview.mockResolvedValue(OVERVIEW)
    api.knowledgeGapCases.mockResolvedValue({ cases: [CASE], count: 1 })
    api.knowledgeGapCase.mockResolvedValue(CASE)
    api.knowledgeGapOccurrences.mockResolvedValue({ occurrences: [] })
    api.knowledgeGapReviews.mockResolvedValue({ reviews: [] })
    api.knowledgeGapNotes.mockResolvedValue({ notes: [] })
    api.knowledgeGapEvents.mockResolvedValue({ events: [] })
    api.reviewKnowledgeGapCase.mockResolvedValue({ ...CASE, status: 'review_required' })

    render(<KnowledgeGapsPage />)
    await waitFor(() => expect(screen.getByText('Total cases').nextSibling).toHaveTextContent('4'))
    await userEvent.click(screen.getByRole('button', { name: 'New Cases' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Details' }))

    expect(await screen.findByLabelText('Case detail')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Submit review' }))
    await waitFor(() => expect(api.reviewKnowledgeGapCase).toHaveBeenCalledWith('case-1', { decision: 'confirm_gap', comment: null }))
  })

  it('proposes and confirms a cluster merge with the stale-check fingerprint', async () => {
    api.knowledgeGapOverview.mockResolvedValue(OVERVIEW)
    api.knowledgeGapClusters.mockResolvedValue({ clusters: [] })
    api.proposeKnowledgeGapMerge.mockResolvedValue({
      case_public_ids: ['a', 'b'], decisions: [{ case_public_id: 'b', matched_case_public_id: 'a', decision: 'probable_duplicate' }],
      stale_check_fingerprint: 'fp-123',
    })
    api.confirmKnowledgeGapMerge.mockResolvedValue({ public_id: 'cluster-1' })

    render(<KnowledgeGapsPage />)
    await waitFor(() => expect(screen.getByText('Total cases').nextSibling).toHaveTextContent('4'))
    await userEvent.click(screen.getByRole('button', { name: 'Clusters' }))
    await userEvent.type(screen.getByPlaceholderText('case-id-1, case-id-2'), 'a, b')
    await userEvent.click(screen.getByRole('button', { name: 'Preview merge' }))
    expect(await screen.findByText(/probable_duplicate/i)).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText('Canonical question for merged cluster'), 'merged question')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm merge' }))
    await waitFor(() => expect(api.confirmKnowledgeGapMerge).toHaveBeenCalledWith(
      expect.objectContaining({ stale_check_fingerprint: 'fp-123', case_public_ids: ['a', 'b'] }),
    ))
  })

  it('generates a daily report', async () => {
    api.knowledgeGapOverview.mockResolvedValue(OVERVIEW)
    api.knowledgeGapDailyReports.mockResolvedValue({ reports: [] })
    api.generateKnowledgeGapDailyReport.mockResolvedValue({ public_id: 'r1', report_date: '2026-07-30', summary: {} })

    render(<KnowledgeGapsPage />)
    await waitFor(() => expect(screen.getByText('Total cases').nextSibling).toHaveTextContent('4'))
    await userEvent.click(screen.getByRole('button', { name: 'Daily Report' }))
    await userEvent.click(await screen.findByRole('button', { name: /generate today's report/i }))
    await waitFor(() => expect(api.generateKnowledgeGapDailyReport).toHaveBeenCalledTimes(1))
  })

  it('runs the request -> confirm -> execute deletion sequence', async () => {
    api.knowledgeGapOverview.mockResolvedValue(OVERVIEW)
    api.knowledgeGapDeletionPreview.mockResolvedValue({ case_public_id: 'case-1', will_remove: ['redacted_question'] })
    api.requestKnowledgeGapDeletion.mockResolvedValue({ state: 'requested' })
    api.confirmKnowledgeGapDeletion.mockResolvedValue({ state: 'confirmed' })
    api.executeKnowledgeGapDeletion.mockResolvedValue({ status: 'deleted_payload' })
    api.knowledgeGapCase.mockResolvedValue({ ...CASE, status: 'deleted_payload' })
    api.knowledgeGapOccurrences.mockResolvedValue({ occurrences: [] })
    api.knowledgeGapReviews.mockResolvedValue({ reviews: [] })
    api.knowledgeGapNotes.mockResolvedValue({ notes: [] })
    api.knowledgeGapEvents.mockResolvedValue({ events: [] })

    render(<KnowledgeGapsPage />)
    await waitFor(() => expect(screen.getByText('Total cases').nextSibling).toHaveTextContent('4'))
    await userEvent.click(screen.getByRole('button', { name: 'Deletion & History' }))
    await userEvent.type(screen.getByPlaceholderText('case public id'), 'case-1')
    await userEvent.click(screen.getByRole('button', { name: 'Load impact preview' }))
    await waitFor(() => expect(api.knowledgeGapDeletionPreview).toHaveBeenCalledWith('case-1'))

    await userEvent.click(screen.getByRole('button', { name: 'Request deletion' }))
    await waitFor(() => expect(api.requestKnowledgeGapDeletion).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('button', { name: 'Confirm deletion' }))
    await waitFor(() => expect(api.confirmKnowledgeGapDeletion).toHaveBeenCalledWith('case-1'))
    await userEvent.click(screen.getByRole('button', { name: 'Execute deletion' }))
    await waitFor(() => expect(api.executeKnowledgeGapDeletion).toHaveBeenCalledWith('case-1'))
  })
})
