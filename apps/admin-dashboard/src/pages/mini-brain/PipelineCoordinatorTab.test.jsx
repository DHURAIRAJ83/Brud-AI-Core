import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PipelineCoordinatorTab from './PipelineCoordinatorTab.jsx'

function baseProps(overrides = {}) {
  return {
    pcSubTab: 'Overview',
    setPcSubTab: vi.fn(),
    pcDiag: null,
    pcSessionData: null,
    pcSessionsList: [],
    pcSelectedId: '',
    selectPcSession: vi.fn(),
    submitPcCreateSession: vi.fn((event) => event?.preventDefault?.()),
    pcNewTopic: '',
    setPcNewTopic: vi.fn(),
    pcBusy: false,
    submitPcLinkResearch: vi.fn((event) => event?.preventDefault?.()),
    pcMb09Id: '',
    setPcMb09Id: vi.fn(),
    submitPcLinkResearchCenter: vi.fn((event) => event?.preventDefault?.()),
    pcMb10Id: '',
    setPcMb10Id: vi.fn(),
    runPcRefreshResearchCenter: vi.fn(),
    submitPcLinkDatasetEvolution: vi.fn((event) => event?.preventDefault?.()),
    pcMb11Id: '',
    setPcMb11Id: vi.fn(),
    submitPcLinkTraining: vi.fn((event) => event?.preventDefault?.()),
    pcMb06Id: '',
    setPcMb06Id: vi.fn(),
    runPcRefreshTraining: vi.fn(),
    runPcRunRagFirstEnforcement: vi.fn(),
    runPcGenerateTrainingReadiness: vi.fn(),
    runPcGenerateTimeline: vi.fn(),
    runPcPredictImprovement: vi.fn(),
    runPcGenerateRecommendation: vi.fn(),
    runPcGenerateReport: vi.fn(),
    runPcAdminDecide: vi.fn(),
    pcEventsList: [],
    ...overrides,
  }
}

describe('PipelineCoordinatorTab', () => {
  it('renders all 8 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setPcSubTab = vi.fn()
    render(<PipelineCoordinatorTab {...baseProps({ setPcSubTab })} />)
    for (const label of ['Overview', 'Link Phases', 'RAG Gate', 'Readiness & Timeline', 'Prediction', 'Recommendation & Report', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'RAG Gate' }))
    expect(setPcSubTab).toHaveBeenCalledWith('RAG Gate')
  })

  it('Overview: starts a real new pipeline and shows real linked sessions', () => {
    render(<PipelineCoordinatorTab {...baseProps({
      pcSessionData: { topic: 't', stage: 'linking', status: 'active', mb09_session_public_id: 'rc-1', mb10_session_public_id: null, mb11_session_public_id: null, mb06_session_public_id: null },
    })} />)
    expect(screen.getByText(/MB-09 \(Research\): rc-1/)).toBeInTheDocument()
    expect(screen.getByText(/MB-10 \(Provider Consensus \/ Draft\): not linked/)).toBeInTheDocument()
  })

  it('Link Phases: submits a real MB-09 link', async () => {
    const user = userEvent.setup()
    const submitPcLinkResearch = vi.fn((event) => event?.preventDefault?.())
    render(<PipelineCoordinatorTab {...baseProps({
      pcSubTab: 'Link Phases',
      pcSessionData: { topic: 't', stage: 'linking', status: 'active' },
      pcMb09Id: 'rc-1',
      submitPcLinkResearch,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Link Research (MB-09)' }))
    expect(submitPcLinkResearch).toHaveBeenCalled()
  })

  it('Recommendation & Report: admin decision center calls the real handler with the right value', async () => {
    const user = userEvent.setup()
    const runPcAdminDecide = vi.fn()
    render(<PipelineCoordinatorTab {...baseProps({
      pcSubTab: 'Recommendation & Report',
      pcSessionData: { topic: 't', stage: 'recommendation', status: 'active' },
      runPcAdminDecide,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve Training' }))
    expect(runPcAdminDecide).toHaveBeenCalledWith('approve_training')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<PipelineCoordinatorTab {...baseProps({ pcSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
