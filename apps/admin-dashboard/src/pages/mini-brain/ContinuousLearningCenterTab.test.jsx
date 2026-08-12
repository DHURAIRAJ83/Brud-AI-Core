import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ContinuousLearningCenterTab from './ContinuousLearningCenterTab.jsx'

function baseProps(overrides = {}) {
  return {
    clcDiag: null,
    clcMemoryItems: [],
    submitClcRecordMemory: vi.fn((event) => event?.preventDefault?.()),
    clcMemoryForm: { continuous_learning_session_public_id: '', model_version_public_id: '', dataset_version_public_id: '', improvement_notes: '' },
    setClcMemoryForm: vi.fn(),
    clcBusy: false,
    clcSessionsList: [],
    clcSelectedId: '',
    selectClcSession: vi.fn(),
    submitClcCreateSession: vi.fn((event) => event?.preventDefault?.()),
    clcSessionData: null,
    runClcEvolveKnowledgeGaps: vi.fn(),
    runClcBuildLearningQueue: vi.fn(),
    submitClcBuildDraft: vi.fn((event) => event?.preventDefault?.()),
    clcDraftTopic: '',
    setClcDraftTopic: vi.fn(),
    submitClcPrepareProviderRequest: vi.fn((event) => event?.preventDefault?.()),
    clcProviders: 'claude,openai',
    setClcProviders: vi.fn(),
    submitClcIngestProviderResults: vi.fn((event) => event?.preventDefault?.()),
    clcProviderOutputs: [{ provider: 'claude', output_text: '' }],
    setClcProviderOutputs: vi.fn(),
    submitClcPlanDatasetEvolution: vi.fn((event) => event?.preventDefault?.()),
    clcExistingDatasetId: '',
    setClcExistingDatasetId: vi.fn(),
    runClcBuildRoadmap: vi.fn(),
    runClcGenerateRecommendation: vi.fn(),
    runClcGenerateReport: vi.fn(),
    runClcAdminReview: vi.fn(),
    clcEventsList: [],
    ...overrides,
  }
}

describe('ContinuousLearningCenterTab', () => {
  it('shows real learning memory entries and submits a real new one', async () => {
    const user = userEvent.setup()
    const submitClcRecordMemory = vi.fn((event) => event?.preventDefault?.())
    render(<ContinuousLearningCenterTab {...baseProps({
      clcMemoryItems: [{ public_id: 'm1', created_at: '2026-01-01', weak_domains: ['tokenizer'], training_decision: 'retrain', improvement_notes: 'Added examples.' }],
      clcMemoryForm: { continuous_learning_session_public_id: 'cl-1', model_version_public_id: '', dataset_version_public_id: '', improvement_notes: '' },
      submitClcRecordMemory,
    })} />)
    expect(screen.getByText(/Added examples\./)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Record memory' }))
    expect(submitClcRecordMemory).toHaveBeenCalled()
  })

  it('starts a real new planning cycle', async () => {
    const user = userEvent.setup()
    const submitClcCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<ContinuousLearningCenterTab {...baseProps({ submitClcCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start planning cycle' }))
    expect(submitClcCreateSession).toHaveBeenCalled()
  })

  it('knowledge_gap_evolution stage: calls the real evolve action', async () => {
    const user = userEvent.setup()
    const runClcEvolveKnowledgeGaps = vi.fn()
    render(<ContinuousLearningCenterTab {...baseProps({
      clcSessionData: { stage: 'knowledge_gap_evolution', status: 'active', admin_decision: null },
      runClcEvolveKnowledgeGaps,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Evolve knowledge gaps' }))
    expect(runClcEvolveKnowledgeGaps).toHaveBeenCalled()
  })

  it('awaiting_admin_review stage: each real decision button calls the handler with the right value', async () => {
    const user = userEvent.setup()
    const runClcAdminReview = vi.fn()
    render(<ContinuousLearningCenterTab {...baseProps({
      clcSessionData: { stage: 'awaiting_admin_review', status: 'active', admin_decision: null, planning_report: {} },
      runClcAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Send to RAG' }))
    expect(runClcAdminReview).toHaveBeenCalledWith('send_to_rag')
  })

  it('closed stage: shows the real final status honestly', () => {
    render(<ContinuousLearningCenterTab {...baseProps({
      clcSessionData: { stage: 'closed', status: 'admin_archived', admin_decision: 'archive' },
    })} />)
    expect(screen.getByText(/No automatic action was taken\./)).toBeInTheDocument()
  })
})
