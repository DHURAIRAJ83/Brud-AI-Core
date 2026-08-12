import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LearningSupervisorTab from './LearningSupervisorTab.jsx'

function baseProps(overrides = {}) {
  return {
    lsSessions: [],
    lsSelectedId: '',
    selectLsSession: vi.fn(),
    submitLsCreateSession: vi.fn((event) => event?.preventDefault?.()),
    lsCreateForm: { dataset_source_public_id: '', hyperparameter_profile: 'default' },
    setLsCreateForm: vi.fn(),
    lsProfiles: [],
    lsBusy: false,
    lsSession: null,
    runLsValidateDataset: vi.fn(),
    runLsDecideDataset: vi.fn(),
    submitLsRagEvaluation: vi.fn((event) => event?.preventDefault?.()),
    lsRagForm: { rag_sandbox_experiment_public_id: '', retrieval_run_public_id: '', generation_assignment_public_id: '' },
    setLsRagForm: vi.fn(),
    runLsFinalizeRag: vi.fn(),
    runLsDecideRag: vi.fn(),
    submitLsTrainingRequest: vi.fn((event) => event?.preventDefault?.()),
    lsTrainingForm: { name: '', dataset_version_public_id: '', tokenizer_version_public_id: '', core_model_version_public_id: '', hyperparameter_profile: '' },
    setLsTrainingForm: vi.fn(),
    runLsMonitorTraining: vi.fn(),
    lsMonitor: null,
    runLsAnalyzeTraining: vi.fn(),
    submitLsBenchmark: vi.fn((event) => event?.preventDefault?.()),
    lsBenchmarkForm: { model_evaluation_fixture_set_public_id: '', candidate_core_model_version_public_id: '' },
    setLsBenchmarkForm: vi.fn(),
    submitLsCompareModels: vi.fn((event) => event?.preventDefault?.()),
    lsCompareForm: { previous_benchmark_run_public_id: '' },
    setLsCompareForm: vi.fn(),
    runLsRecommendations: vi.fn(),
    runLsAdminReview: vi.fn(),
    submitLsReleaseCandidate: vi.fn((event) => event?.preventDefault?.()),
    lsReleaseForm: { checkpoint_public_id: '', override_comment: '' },
    setLsReleaseForm: vi.fn(),
    lsEvents: [],
    ...overrides,
  }
}

describe('LearningSupervisorTab', () => {
  it('shows an honest empty state before any session is selected, and lists real sessions', async () => {
    const user = userEvent.setup()
    const selectLsSession = vi.fn()
    render(<LearningSupervisorTab {...baseProps({
      lsSessions: [{ public_id: 'sess-12345678', stage: 'dataset_validation', status: 'active' }],
      selectLsSession,
    })} />)
    expect(screen.getByText('Select or create a session to see its workflow.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sess-123/ }))
    expect(selectLsSession).toHaveBeenCalledWith('sess-12345678')
  })

  it('submits a real new-session form', async () => {
    const user = userEvent.setup()
    const submitLsCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<LearningSupervisorTab {...baseProps({
      lsCreateForm: { dataset_source_public_id: 'src-1', hyperparameter_profile: 'default' },
      submitLsCreateSession,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Create session' }))
    expect(submitLsCreateSession).toHaveBeenCalled()
  })

  it('dataset_validation stage: shows a real Validate dataset action', async () => {
    const user = userEvent.setup()
    const runLsValidateDataset = vi.fn()
    render(<LearningSupervisorTab {...baseProps({
      lsSession: { stage: 'dataset_validation', status: 'active', dataset_decision: null, rag_decision: null, admin_final_decision: null },
      runLsValidateDataset,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Validate dataset' }))
    expect(runLsValidateDataset).toHaveBeenCalled()
  })

  it('awaiting_dataset_decision stage: approve/reject call the real decision handler', async () => {
    const user = userEvent.setup()
    const runLsDecideDataset = vi.fn()
    render(<LearningSupervisorTab {...baseProps({
      lsSession: { stage: 'awaiting_dataset_decision', status: 'active', dataset_decision: null, rag_decision: null, admin_final_decision: null, dataset_readiness_report: {} },
      runLsDecideDataset,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runLsDecideDataset).toHaveBeenCalledWith('approve')
  })

  it('closed stage: shows the real final status and release candidate id', () => {
    render(<LearningSupervisorTab {...baseProps({
      lsSession: {
        stage: 'closed', status: 'accepted', dataset_decision: 'approve', rag_decision: 'approve', admin_final_decision: 'accept',
        release_candidate_core_model_version_public_id: 'cmv-1',
      },
    })} />)
    expect(screen.getByText('Release candidate:')).toBeInTheDocument()
    expect(screen.getByText('cmv-1')).toBeInTheDocument()
  })

  it('shows real session events', () => {
    render(<LearningSupervisorTab {...baseProps({
      lsSession: { stage: 'closed', status: 'accepted', dataset_decision: null, rag_decision: null, admin_final_decision: null },
      lsEvents: [{ public_id: 'e1', created_at: '2026-01-01', event_type: 'created', message: 'Session created.' }],
    })} />)
    expect(screen.getByText(/Session created\./)).toBeInTheDocument()
  })
})
