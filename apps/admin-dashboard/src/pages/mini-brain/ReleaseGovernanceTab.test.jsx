import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ReleaseGovernanceTab from './ReleaseGovernanceTab.jsx'

function baseProps(overrides = {}) {
  return {
    rgSubTab: 'Overview',
    setRgSubTab: vi.fn(),
    rgDiag: null,
    rgSessionData: null,
    rgSessionsList: [],
    rgSelectedId: '',
    selectRgSession: vi.fn(),
    submitRgCreateSession: vi.fn((event) => event?.preventDefault?.()),
    rgNewTopic: '',
    setRgNewTopic: vi.fn(),
    rgBusy: false,
    rgEventsList: [],
    submitRgCollectDatasets: vi.fn((event) => event?.preventDefault?.()),
    rgDatasetSessionIds: '',
    setRgDatasetSessionIds: vi.fn(),
    submitRgCollectRag: vi.fn((event) => event?.preventDefault?.()),
    rgRagSessionIds: '',
    setRgRagSessionIds: vi.fn(),
    submitRgCollectPackage: vi.fn((event) => event?.preventDefault?.()),
    rgPackageSessionId: '',
    setRgPackageSessionId: vi.fn(),
    submitRgCollectEvaluation: vi.fn((event) => event?.preventDefault?.()),
    rgEvaluationSessionId: '',
    setRgEvaluationSessionId: vi.fn(),
    runRgSafety: vi.fn(),
    runRgCompliance: vi.fn(),
    runRgBenchmarks: vi.fn(),
    runRgBuildRiskRollback: vi.fn(),
    runRgBuildPackage: vi.fn(),
    rgArtifactsList: [],
    runRgGenerateReport: vi.fn(),
    runRgAdminReview: vi.fn(),
    rgMemoryList: [],
    ...overrides,
  }
}

describe('ReleaseGovernanceTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setRgSubTab = vi.fn()
    render(<ReleaseGovernanceTab {...baseProps({ setRgSubTab })} />)
    for (const label of ['Overview', 'Sources', 'Safety', 'Compliance', 'Benchmarks', 'Risks', 'Rollback', 'Compatibility', 'Prerequisites', 'Package', 'Report', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Safety' }))
    expect(setRgSubTab).toHaveBeenCalledWith('Safety')
  })

  it('Overview: creates a real new session', async () => {
    const user = userEvent.setup()
    const submitRgCreateSession = vi.fn((event) => event?.preventDefault?.())
    render(<ReleaseGovernanceTab {...baseProps({ rgNewTopic: 'topic-1', submitRgCreateSession })} />)
    await user.click(screen.getByRole('button', { name: 'Create session' }))
    expect(submitRgCreateSession).toHaveBeenCalled()
  })

  it('Safety: calls the real safety gate action', async () => {
    const user = userEvent.setup()
    const runRgSafety = vi.fn()
    render(<ReleaseGovernanceTab {...baseProps({
      rgSubTab: 'Safety',
      rgSessionData: { topic: 't', stage: 'run_safety_gates', status: 'active' },
      runRgSafety,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Run safety gates' }))
    expect(runRgSafety).toHaveBeenCalled()
  })

  it('Report: awaiting_admin_review real decision buttons call the handler correctly', async () => {
    const user = userEvent.setup()
    const runRgAdminReview = vi.fn()
    render(<ReleaseGovernanceTab {...baseProps({
      rgSubTab: 'Report',
      rgSessionData: { topic: 't', stage: 'awaiting_admin_review', status: 'active', readiness_report: { final_recommendation: 'approved_for_release', overall_readiness_score: 90 } },
      runRgAdminReview,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(runRgAdminReview).toHaveBeenCalledWith('approve')
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<ReleaseGovernanceTab {...baseProps({ rgSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
