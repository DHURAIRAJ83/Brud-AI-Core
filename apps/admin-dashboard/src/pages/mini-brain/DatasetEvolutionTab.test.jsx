import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DatasetEvolutionTab from './DatasetEvolutionTab.jsx'

function baseProps(overrides = {}) {
  return {
    deSubTab: 'Overview',
    setDeSubTab: vi.fn(),
    deDiag: null,
    deSessionData: null,
    deSessionsList: [],
    deSelectedId: '',
    selectDeSession: vi.fn(),
    submitDeCreateSession: vi.fn((event) => event?.preventDefault?.()),
    deNewSourceId: '',
    setDeNewSourceId: vi.fn(),
    deBusy: false,
    deEventsList: [],
    runDeKnowledgeEvolution: vi.fn(),
    runDeDatasetEvolution: vi.fn(),
    runDeSimulation: vi.fn(),
    runDeGenerateRecommendation: vi.fn(),
    runDeGenerateReport: vi.fn(),
    runDeAdminReview: vi.fn(),
    submitDeRunRagEvaluation: vi.fn((event) => event?.preventDefault?.()),
    deRagForm: { rag_sandbox_experiment_public_id: '', retrieval_run_public_id: '', generation_assignment_public_id: '' },
    setDeRagForm: vi.fn(),
    runDeFinalizeRagEvaluation: vi.fn(),
    runDeAdminReviewRag: vi.fn(),
    ...overrides,
  }
}

describe('DatasetEvolutionTab', () => {
  it('renders all 8 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setDeSubTab = vi.fn()
    render(<DatasetEvolutionTab {...baseProps({ setDeSubTab })} />)
    for (const label of ['Overview', 'Knowledge Evolution', 'Dataset Evolution', 'Simulation', 'Recommendation & Report', 'RAG Status', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Simulation' }))
    expect(setDeSubTab).toHaveBeenCalledWith('Simulation')
  })

  it('Overview: starts a real new evolution cycle', async () => {
    const user = userEvent.setup()
    const submitDeCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<DatasetEvolutionTab {...baseProps({ deNewSourceId: 'src-1', submitDeCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Start evolution cycle' }))
    expect(submitDeCreateSession).toHaveBeenCalled()
  })

  it('Knowledge Evolution: calls the real analysis action', async () => {
    const user = userEvent.setup()
    const runDeKnowledgeEvolution = vi.fn()
    render(<DatasetEvolutionTab {...baseProps({
      deSubTab: 'Knowledge Evolution',
      deSessionData: { dataset_source_public_id: 'src-12345678', stage: 'knowledge_evolution', status: 'active' },
      runDeKnowledgeEvolution,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Run knowledge evolution analysis' }))
    expect(runDeKnowledgeEvolution).toHaveBeenCalled()
  })

  it('Recommendation & Report: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runDeAdminReview = vi.fn()
    render(<DatasetEvolutionTab {...baseProps({
      deSubTab: 'Recommendation & Report',
      deSessionData: { dataset_source_public_id: 'src-12345678', stage: 'awaiting_admin_review', status: 'active', evolution_report: {}, draft_admin_decision: 'approve_evolution' },
      runDeAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Send to RAG' }))
    expect(runDeAdminReview).toHaveBeenCalledWith('send_to_rag')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<DatasetEvolutionTab {...baseProps({ deSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
