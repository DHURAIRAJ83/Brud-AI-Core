import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IncrementalTrainingPage from './IncrementalTrainingPage.jsx'

vi.mock('../services/api.js', () => ({
  acceptTrainingCheckpoint: vi.fn(), acknowledgeNoTrainingExecution: vi.fn(),
  acknowledgeTrainingAssessment: vi.fn(), addTrainingCheckpointHumanReview: vi.fn(),
  approvePromotionRequest: vi.fn(), approveTrainingRunApproval: vi.fn(),
  compareTrainingCheckpoint: vi.fn(), contaminationRecheck: vi.fn(),
  createPromotionRequest: vi.fn(), createReplayPlan: vi.fn(), createTrainingAssessment: vi.fn(),
  createTrainingRunRequest: vi.fn(), evaluateTrainingCheckpoint: vi.fn(),
  finalizeTrainingReport: vi.fn(), incrementalTrainingOverview: vi.fn(),
  materializePromotionRequest: vi.fn(), promotionRequest: vi.fn(),
  requestTrainingRunApproval: vi.fn(), reviewTrainingCandidate: vi.fn(),
  runTrainingAssessment: vi.fn(), startTrainingRun: vi.fn(), submitPromotionRequest: vi.fn(),
  submitTrainingRunRequest: vi.fn(), trainingAssessmentCandidates: vi.fn(),
  trainingAssessmentItems: vi.fn(), trainingAssessments: vi.fn(), trainingCheckpoint: vi.fn(),
  trainingCheckpointAcceptances: vi.fn(), trainingCheckpointComparisons: vi.fn(),
  trainingCheckpointEvaluations: vi.fn(), trainingCheckpointHumanReviews: vi.fn(),
  trainingReports: vi.fn(), trainingRun: vi.fn(), trainingRunCheckpoints: vi.fn(),
  trainingRunEvents: vi.fn(), trainingRuns: vi.fn(), transformTrainingItem: vi.fn(),
  verifyTrainingCheckpoint: vi.fn(),
}))

const api = await import('../services/api.js')

const ASSESSMENT = { public_id: 'tda-1', assessment_code: 'TDA-0001', status: 'assessed' }

function mockBaseline() {
  api.incrementalTrainingOverview.mockResolvedValue({
    training_assessments_awaiting_review: 2, checkpoints_with_regression: 1,
    accepted_model_candidates: 3,
  })
  api.trainingAssessments.mockResolvedValue({ items: [ASSESSMENT] })
  api.trainingRuns.mockResolvedValue({ items: [] })
  api.trainingAssessmentItems.mockResolvedValue({ items: [] })
  api.trainingAssessmentCandidates.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('IncrementalTrainingPage: navigation', () => {
  it('renders all seven required tabs', async () => {
    mockBaseline()
    render(<IncrementalTrainingPage />)
    await waitFor(() => expect(api.incrementalTrainingOverview).toHaveBeenCalled())
    for (const tab of [
      'Overview', 'Assessments', 'Candidates', 'Dataset Promotion', 'Training Runs',
      'Checkpoints', 'Reports & Acceptance',
    ]) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview shows real governance metrics, including a regression warning', async () => {
    mockBaseline()
    render(<IncrementalTrainingPage />)
    await waitFor(() => expect(screen.getByText('Assessments awaiting review').nextSibling)
      .toHaveTextContent('2'))
    expect(screen.getByText('Checkpoints with regression').nextSibling).toHaveTextContent('1')
    expect(screen.getByText('Accepted model candidates (staging)').nextSibling)
      .toHaveTextContent('3')
  })

  it('never shows a production-activation or release label anywhere on the page', async () => {
    mockBaseline()
    render(<IncrementalTrainingPage />)
    await waitFor(() => expect(api.incrementalTrainingOverview).toHaveBeenCalled())
    expect(screen.queryByText(/Production Model Activated/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Model Released/i)).not.toBeInTheDocument()
  })
})

describe('IncrementalTrainingPage: create assessment', () => {
  it('creating an assessment calls createTrainingAssessment with the experiment id', async () => {
    mockBaseline()
    api.createTrainingAssessment.mockResolvedValue(ASSESSMENT)
    const user = userEvent.setup()
    render(<IncrementalTrainingPage />)
    await user.click(await screen.findByRole('button', { name: 'Assessments' }))
    await user.type(
      screen.getByPlaceholderText('Accepted RAG sandbox experiment public ID'), 'rse-1',
    )
    await user.click(screen.getByRole('button', { name: 'Create assessment' }))
    await waitFor(() => expect(api.createTrainingAssessment).toHaveBeenCalledWith({
      rag_sandbox_experiment_public_id: 'rse-1',
    }))
  })

  it('selecting an assessment loads its items and candidates', async () => {
    mockBaseline()
    const user = userEvent.setup()
    render(<IncrementalTrainingPage />)
    await waitFor(() => expect(api.trainingAssessments).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: /TDA-0001/ }))
    await waitFor(() => expect(api.trainingAssessmentItems).toHaveBeenCalledWith('tda-1'))
    expect(api.trainingAssessmentCandidates).toHaveBeenCalledWith('tda-1')
  })
})

describe('IncrementalTrainingPage: checkpoint acceptance', () => {
  it('accepting a checkpoint shows the registered staging model candidate', async () => {
    mockBaseline()
    api.acceptTrainingCheckpoint.mockResolvedValue({
      public_id: 'acc-1', decision: 'accepted_candidate', model_candidate_public_id: 'cmv-1',
    })
    const user = userEvent.setup()
    render(<IncrementalTrainingPage />)
    await user.click(await screen.findByRole('button', { name: 'Reports & Acceptance' }))
    await user.type(screen.getByPlaceholderText('Checkpoint public ID to accept'), 'ckpt-1')
    await user.type(screen.getByPlaceholderText('Report public ID'), 'rep-1')
    await user.type(screen.getByPlaceholderText('Reason'), 'good enough')
    await user.click(screen.getByRole('button', { name: 'Record decision' }))
    await waitFor(() => expect(api.acceptTrainingCheckpoint).toHaveBeenCalledWith('ckpt-1', {
      report_public_id: 'rep-1', decision: 'accepted_candidate', reason: 'good enough',
    }))
    expect(await screen.findByText(/Registered as staging model candidate: cmv-1/)).toBeInTheDocument()
  })
})
