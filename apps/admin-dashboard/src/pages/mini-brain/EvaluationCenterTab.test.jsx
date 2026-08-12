import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EvaluationCenterTab from './EvaluationCenterTab.jsx'

function baseProps(overrides = {}) {
  return {
    ecSubTab: 'Overview',
    setEcSubTab: vi.fn(),
    ecDiag: null,
    ecSessionData: null,
    ecSessionsList: [],
    ecSelectedId: '',
    selectEcSession: vi.fn(),
    submitEcCreateSession: vi.fn((event) => event?.preventDefault?.()),
    ecNewTopic: '',
    setEcNewTopic: vi.fn(),
    ecBusy: false,
    ecEventsList: [],
    submitEcCollectDatasets: vi.fn((event) => event?.preventDefault?.()),
    ecDatasetSessionIds: '',
    setEcDatasetSessionIds: vi.fn(),
    submitEcCollectRagSessions: vi.fn((event) => event?.preventDefault?.()),
    ecRagSessionIds: '',
    setEcRagSessionIds: vi.fn(),
    submitEcCollectTrainingPackages: vi.fn((event) => event?.preventDefault?.()),
    ecPackageSessionIds: '',
    setEcPackageSessionIds: vi.fn(),
    runEcLanguageBenchmarks: vi.fn(),
    runEcOcrBenchmarks: vi.fn(),
    runEcGroundingRetrievalBenchmarks: vi.fn(),
    runEcMultimodalBenchmarks: vi.fn(),
    runEcPackageBenchmarks: vi.fn(),
    submitEcRegression: vi.fn((event) => event?.preventDefault?.()),
    ecBaselineSessionId: '',
    setEcBaselineSessionId: vi.fn(),
    runEcGenerateReport: vi.fn(),
    runEcAdminReview: vi.fn(),
    ecMemoryList: [],
    ecExportsList: [],
    ...overrides,
  }
}

describe('EvaluationCenterTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setEcSubTab = vi.fn()
    render(<EvaluationCenterTab {...baseProps({ setEcSubTab })} />)
    for (const label of ['Overview', 'Sources', 'Language', 'OCR', 'Grounding', 'Retrieval', 'Multimodal', 'Package', 'Regression', 'Report', 'Exports', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Grounding' }))
    expect(setEcSubTab).toHaveBeenCalledWith('Grounding')
  })

  it('Overview: creates a real new session', async () => {
    const user = userEvent.setup()
    const submitEcCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<EvaluationCenterTab {...baseProps({ ecNewTopic: 'topic-1', submitEcCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Create session' }))
    expect(submitEcCreateSession).toHaveBeenCalled()
  })

  it('Language: calls the real benchmark action', async () => {
    const user = userEvent.setup()
    const runEcLanguageBenchmarks = vi.fn()
    render(<EvaluationCenterTab {...baseProps({
      ecSubTab: 'Language',
      ecSessionData: { topic: 't', stage: 'run_language_benchmarks', status: 'active' },
      runEcLanguageBenchmarks,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Run language benchmarks' }))
    expect(runEcLanguageBenchmarks).toHaveBeenCalled()
  })

  it('Report: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runEcAdminReview = vi.fn()
    render(<EvaluationCenterTab {...baseProps({
      ecSubTab: 'Report',
      ecSessionData: { topic: 't', stage: 'awaiting_admin_review', status: 'active', release_readiness: { status: 'Ready' }, evaluation_report: {} },
      runEcAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runEcAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<EvaluationCenterTab {...baseProps({ ecSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
