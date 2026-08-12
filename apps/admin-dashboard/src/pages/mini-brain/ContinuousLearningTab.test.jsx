import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ContinuousLearningTab from './ContinuousLearningTab.jsx'

function baseProps(overrides = {}) {
  return {
    clDiagnostics: null,
    clSessions: [],
    clSelectedId: '',
    selectClSession: vi.fn(),
    submitClCreateSession: vi.fn((event) => event?.preventDefault?.()),
    clCycleWindowDays: 30,
    setClCycleWindowDays: vi.fn(),
    clBusy: false,
    clSession: null,
    runClCollectFeedback: vi.fn(),
    runClAnalyzeFailures: vi.fn(),
    runClAnalyzeHallucinations: vi.fn(),
    runClAnalyzeKnowledgeGaps: vi.fn(),
    runClDetectWeakTopics: vi.fn(),
    runClAnalyzeDifficulty: vi.fn(),
    runClRecommendDatasets: vi.fn(),
    runClRecommendTraining: vi.fn(),
    runClRankPriorities: vi.fn(),
    runClGenerateReport: vi.fn(),
    runClAdminReview: vi.fn(),
    clEvents: [],
    ...overrides,
  }
}

describe('ContinuousLearningTab', () => {
  it('shows the real pipeline stages and writes scope from diagnostics', () => {
    render(<ContinuousLearningTab {...baseProps({ clDiagnostics: { pipeline_stages: ['collect', 'analyze'], writes_scope: 'none' } })} />)
    expect(screen.getByText(/collect -> analyze/)).toBeInTheDocument()
  })

  it('starts a real new learning cycle', async () => {
    const user = userEvent.setup()
    const submitClCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<ContinuousLearningTab {...baseProps({ submitClCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start learning cycle' }))
    expect(submitClCreateSession).toHaveBeenCalled()
  })

  it('feedback_collection stage: calls the real collect action', async () => {
    const user = userEvent.setup()
    const runClCollectFeedback = vi.fn()
    render(<ContinuousLearningTab {...baseProps({
      clSession: { stage: 'feedback_collection', status: 'active', admin_decision: null },
      runClCollectFeedback,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Collect feedback' }))
    expect(runClCollectFeedback).toHaveBeenCalled()
  })

  it('awaiting_admin_review stage: approve calls the real handler', async () => {
    const user = userEvent.setup()
    const runClAdminReview = vi.fn()
    render(<ContinuousLearningTab {...baseProps({
      clSession: { stage: 'awaiting_admin_review', status: 'active', admin_decision: null, continuous_learning_report: {} },
      runClAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runClAdminReview).toHaveBeenCalledWith('approve')
  })

  it('closed stage: shows the real final status honestly, with no automatic action taken', () => {
    render(<ContinuousLearningTab {...baseProps({
      clSession: { stage: 'closed', status: 'admin_rejected', admin_decision: 'reject' },
    })} />)
    expect(screen.getByText(/No automatic action was taken\./)).toBeInTheDocument()
  })
})
