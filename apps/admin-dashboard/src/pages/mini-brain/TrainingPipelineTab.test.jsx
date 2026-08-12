import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TrainingPipelineTab from './TrainingPipelineTab.jsx'

function baseProps(overrides = {}) {
  return {
    tpSubTab: 'Overview',
    setTpSubTab: vi.fn(),
    tpDiag: null,
    tpSessionData: null,
    tpSessionsList: [],
    tpSelectedId: '',
    selectTpSession: vi.fn(),
    submitTpCreateSession: vi.fn((event) => event?.preventDefault?.()),
    tpNewTopic: '',
    setTpNewTopic: vi.fn(),
    tpBusy: false,
    tpEventsList: [],
    submitTpCollectDatasets: vi.fn((event) => event?.preventDefault?.()),
    tpDatasetSessionIds: '',
    setTpDatasetSessionIds: vi.fn(),
    submitTpCollectRagMemory: vi.fn((event) => event?.preventDefault?.()),
    tpRagSessionIds: '',
    setTpRagSessionIds: vi.fn(),
    tpAvailableRagMemory: [],
    runTpAnalyzeLanguage: vi.fn(),
    runTpAnalyzeVision: vi.fn(),
    runTpAnalyzeTokenizer: vi.fn(),
    submitTpPlanSplits: vi.fn((event) => event?.preventDefault?.()),
    tpSplitSeed: '',
    setTpSplitSeed: vi.fn(),
    runTpPlanCurriculum: vi.fn(),
    runTpEstimateHardware: vi.fn(),
    runTpBuildPackage: vi.fn(),
    tpPackagesList: [],
    runTpGenerateReport: vi.fn(),
    runTpAdminReview: vi.fn(),
    tpMemoryList: [],
    ...overrides,
  }
}

describe('TrainingPipelineTab', () => {
  it('renders all 12 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setTpSubTab = vi.fn()
    render(<TrainingPipelineTab {...baseProps({ setTpSubTab })} />)
    for (const label of ['Overview', 'Sources', 'Language', 'Vision', 'Tokenizer', 'Splits', 'Curriculum', 'Hardware', 'Package', 'Report', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Curriculum' }))
    expect(setTpSubTab).toHaveBeenCalledWith('Curriculum')
  })

  it('Overview: creates a real new session', async () => {
    const user = userEvent.setup()
    const submitTpCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<TrainingPipelineTab {...baseProps({ tpNewTopic: 'topic-1', submitTpCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Create session' }))
    expect(submitTpCreateSession).toHaveBeenCalled()
  })

  it('Sources: submits real dataset collection', async () => {
    const user = userEvent.setup()
    const submitTpCollectDatasets = vi.fn((event) => event?.preventDefault?.())
    render(<TrainingPipelineTab {...baseProps({
      tpSubTab: 'Sources',
      tpSessionData: { topic: 't', stage: 'collect_datasets', status: 'active' },
      tpDatasetSessionIds: 'ds-1',
      submitTpCollectDatasets,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Collect certified datasets' }))
    expect(submitTpCollectDatasets).toHaveBeenCalled()
  })

  it('Report: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runTpAdminReview = vi.fn()
    render(<TrainingPipelineTab {...baseProps({
      tpSubTab: 'Report',
      tpSessionData: { topic: 't', stage: 'awaiting_admin_review', status: 'active', readiness_report: {} },
      runTpAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runTpAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<TrainingPipelineTab {...baseProps({ tpSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
