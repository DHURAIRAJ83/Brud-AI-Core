import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PublicChatRuntimeTab from './PublicChatRuntimeTab.jsx'

function baseProps(overrides = {}) {
  return {
    pcrSubTab: 'Overview',
    setPcrSubTab: vi.fn(),
    pcrAnalyticsData: null,
    pcrCandidatesList: [],
    pcrDiag: null,
    pcrSessionsList: [],
    pcrSelectedSessionId: '',
    selectPcrSession: vi.fn(),
    pcrSessionData: null,
    pcrMessagesList: [],
    pcrSignalsList: [],
    pcrClustersList: [],
    submitPcrGenerateCandidates: vi.fn((event) => event?.preventDefault?.()),
    pcrMinFrequency: '3',
    setPcrMinFrequency: vi.fn(),
    pcrBusy: false,
    pcrSelectedCandidateId: '',
    selectPcrCandidate: vi.fn(),
    pcrCandidateData: null,
    pcrReviewNotes: '',
    setPcrReviewNotes: vi.fn(),
    submitPcrReview: vi.fn(),
    pcrCandidateEventsList: [],
    pcrApprovedCandidatesList: [],
    runPcrExportAnalytics: vi.fn(),
    runPcrExportCandidates: vi.fn(),
    pcrExportResult: null,
    ...overrides,
  }
}

describe('PublicChatRuntimeTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setPcrSubTab = vi.fn()
    render(<PublicChatRuntimeTab {...baseProps({ setPcrSubTab })} />)
    for (const label of ['Overview', 'Live Sessions', 'Conversations', 'Analytics', 'Feedback Signals', 'Failure Clusters', 'Improvement Queue', 'Candidate Review', 'Admin Handoffs', 'Exports', 'Runtime Diagnostics', 'Safety Monitor', 'History']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Failure Clusters' }))
    expect(setPcrSubTab).toHaveBeenCalledWith('Failure Clusters')
  })

  it('Live Sessions: selects a real session', async () => {
    const user = userEvent.setup()
    const selectPcrSession = vi.fn()
    render(<PublicChatRuntimeTab {...baseProps({
      pcrSubTab: 'Live Sessions',
      pcrSessionsList: [{ public_id: 'sess-12345678', language: 'en', message_count: 3, unresolved_count: 1, started_at: '2026-08-01' }],
      selectPcrSession,
    })} />)
    await user.click(screen.getByRole('button', { name: /sess-123/ }))
    expect(selectPcrSession).toHaveBeenCalledWith('sess-12345678')
  })

  it('Improvement Queue: submits a real generate-candidates form', async () => {
    const user = userEvent.setup()
    const submitPcrGenerateCandidates = vi.fn((event) => event?.preventDefault?.())
    render(<PublicChatRuntimeTab {...baseProps({
      pcrSubTab: 'Improvement Queue',
      submitPcrGenerateCandidates,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Generate candidates from clusters' }))
    expect(submitPcrGenerateCandidates).toHaveBeenCalled()
  })

  it('Candidate Review: real approve button calls the handler', async () => {
    const user = userEvent.setup()
    const submitPcrReview = vi.fn()
    render(<PublicChatRuntimeTab {...baseProps({
      pcrSubTab: 'Candidate Review',
      pcrCandidateData: { topic: 't', status: 'pending_admin_review' },
      submitPcrReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(submitPcrReview).toHaveBeenCalledWith('approve')
  })

  it('Runtime Diagnostics: shows a skeleton before loaded', () => {
    render(<PublicChatRuntimeTab {...baseProps({ pcrSubTab: 'Runtime Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
