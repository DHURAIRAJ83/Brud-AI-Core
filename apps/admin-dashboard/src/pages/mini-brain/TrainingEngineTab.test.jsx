import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TrainingEngineTab from './TrainingEngineTab.jsx'

function baseProps(overrides = {}) {
  return {
    teSubTab: 'Overview',
    setTeSubTab: vi.fn(),
    teDiag: null,
    teJobData: null,
    runTeValidateRelease: vi.fn(),
    runTeValidatePackage: vi.fn(),
    teJobsList: [],
    teSelectedId: '',
    selectTeJob: vi.fn(),
    submitTeCreateJob: vi.fn((event) => event?.preventDefault?.()),
    teNewTopic: '',
    setTeNewTopic: vi.fn(),
    teNewPackageId: '',
    setTeNewPackageId: vi.fn(),
    teNewReleaseId: '',
    setTeNewReleaseId: vi.fn(),
    teNewExecutionMode: 'simulation',
    setTeNewExecutionMode: vi.fn(),
    teBusy: false,
    submitTeAuthorize: vi.fn((event) => event?.preventDefault?.()),
    teAuthorizationReason: '',
    setTeAuthorizationReason: vi.fn(),
    runTePlanResources: vi.fn(),
    runTeBuildManifest: vi.fn(),
    runTeReserveRuntime: vi.fn(),
    runTeStart: vi.fn(),
    runTePause: vi.fn(),
    runTeCancel: vi.fn(),
    runTeResume: vi.fn(),
    submitTeStreamMetric: vi.fn((event) => event?.preventDefault?.()),
    teMetricStep: '',
    setTeMetricStep: vi.fn(),
    teMetricEpoch: '',
    setTeMetricEpoch: vi.fn(),
    teMetricsList: [],
    submitTeSaveCheckpoint: vi.fn((event) => event?.preventDefault?.()),
    teCheckpointStep: '',
    setTeCheckpointStep: vi.fn(),
    teCheckpointEpoch: '',
    setTeCheckpointEpoch: vi.fn(),
    teCheckpointsList: [],
    teEventsList: [],
    runTeFinalize: vi.fn(),
    runTeGenerateReport: vi.fn(),
    runTeArchive: vi.fn(),
    teMemoryList: [],
    ...overrides,
  }
}

describe('TrainingEngineTab', () => {
  it('renders all 13 real sub-tabs and switches on click', async () => {
    const user = userEvent.setup()
    const setTeSubTab = vi.fn()
    render(<TrainingEngineTab {...baseProps({ setTeSubTab })} />)
    for (const label of ['Overview', 'Jobs', 'Authorization', 'Resources', 'Manifest', 'Runtime', 'Metrics', 'Checkpoints', 'Logs', 'Report', 'Archive', 'History', 'Diagnostics']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
    await user.click(screen.getByRole('button', { name: 'Runtime' }))
    expect(setTeSubTab).toHaveBeenCalledWith('Runtime')
  })

  it('Jobs: creates a real new job', async () => {
    const user = userEvent.setup()
    const submitTeCreateJob = vi.fn((event) => event?.preventDefault?.())
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Jobs',
      teNewTopic: 'topic-1',
      teNewPackageId: 'pkg-1',
      teNewReleaseId: 'rel-1',
      submitTeCreateJob,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Create job' }))
    expect(submitTeCreateJob).toHaveBeenCalled()
  })

  it('Runtime: calls the real reserve runtime action', async () => {
    const user = userEvent.setup()
    const runTeReserveRuntime = vi.fn()
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Runtime',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'pending' },
      runTeReserveRuntime,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Reserve runtime' }))
    expect(runTeReserveRuntime).toHaveBeenCalled()
  })

  it('Report: real finalize button calls the handler', async () => {
    const user = userEvent.setup()
    const runTeFinalize = vi.fn()
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Report',
      teJobData: { topic: 't', stage: 'streaming_metrics', status: 'running' },
      runTeFinalize,
    })} />)
    await user.click(screen.getByRole('button', { name: 'Finalize training' }))
    expect(runTeFinalize).toHaveBeenCalled()
  })

  it('Diagnostics: shows a skeleton before loaded', () => {
    render(<TrainingEngineTab {...baseProps({ teSubTab: 'Diagnostics' })} />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
  })
})
