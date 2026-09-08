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
    teNewCoreModelVersionId: '',
    setTeNewCoreModelVersionId: vi.fn(),
    teCoreModelVersion: null,
    teNewDatasetVersionId: '',
    setTeNewDatasetVersionId: vi.fn(),
    teDatasetReadinessData: null,
    teDatasetReadinessContractData: null,
    teTrainingReadinessData: null,
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

  it('Jobs: gpu mode requires a real Core Model Version and dataset identity before Create job is enabled', async () => {
    const user = userEvent.setup()
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Jobs', teNewTopic: 'topic-1', teNewPackageId: 'pkg-1', teNewReleaseId: 'rel-1',
      teNewExecutionMode: 'gpu', teNewCoreModelVersionId: '', teNewDatasetVersionId: '',
    })} />)
    expect(screen.getByPlaceholderText('architecture-verified version public id')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('ready dataset version public id')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create job' })).toBeDisabled()

    // Core Model Version alone is not enough -- dataset is also required.
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Jobs', teNewTopic: 'topic-1', teNewPackageId: 'pkg-1', teNewReleaseId: 'rel-1',
      teNewExecutionMode: 'gpu', teNewCoreModelVersionId: 'cmv-1', teNewDatasetVersionId: '',
    })} />)
    expect(screen.getAllByRole('button', { name: 'Create job' })[1]).toBeDisabled()

    const setTeNewCoreModelVersionId = vi.fn()
    const setTeNewDatasetVersionId = vi.fn()
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Jobs', teNewTopic: 'topic-1', teNewPackageId: 'pkg-1', teNewReleaseId: 'rel-1',
      teNewExecutionMode: 'gpu', teNewCoreModelVersionId: 'cmv-1', setTeNewCoreModelVersionId,
      teNewDatasetVersionId: 'ds-1', setTeNewDatasetVersionId,
    })} />)
    expect(screen.getAllByRole('button', { name: 'Create job' })[2]).toBeEnabled()
    await user.type(screen.getAllByPlaceholderText('architecture-verified version public id')[2], 'x')
    expect(setTeNewCoreModelVersionId).toHaveBeenCalled()
    await user.type(screen.getAllByPlaceholderText('ready dataset version public id')[2], 'x')
    expect(setTeNewDatasetVersionId).toHaveBeenCalled()
  })

  it('Overview: shows the resolved real Core Model Version identity for a gpu job', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: 'cmv-1' },
      teCoreModelVersion: {
        family_name: 'brud-tamil', config_public_id: '12345678-aaaa', version: '0.1.0', lifecycle_status: 'architecture_verified',
      },
    })} />)
    expect(screen.getByText(/brud-tamil/)).toBeInTheDocument()
    expect(screen.getByText(/architecture_verified/)).toBeInTheDocument()
    expect(screen.getAllByText(/never releases, activates, or assigns/).length).toBeGreaterThan(0)
  })

  it('Overview: honestly reports a gpu job with no Core Model Version identity yet', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'validate_release', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: null },
    })} />)
    expect(screen.getByText(/no Core Model Version identity/)).toBeInTheDocument()
  })

  it('Overview: shows real Phase 2.7G training readiness for a ready dataset', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: 'cmv-1', dataset_version_public_id: 'dsv-1' },
      teDatasetReadinessData: {
        ready: true, reason: null,
        report: { context_length: 32, train_report: { packed: { block_count: 3 } }, validation_report: { packed: { block_count: 1 } } },
      },
    })} />)
    expect(screen.getByText('TRAINING_READY')).toBeInTheDocument()
    expect(screen.getByText(/train blocks/)).toBeInTheDocument()
  })

  it('Overview: shows the real NOT_READY reason when the dataset pipeline rejects it', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: 'cmv-1', dataset_version_public_id: 'dsv-1' },
      teDatasetReadinessData: { ready: false, reason: "dataset version not found: dsv-1", report: null },
    })} />)
    expect(screen.getByText('NOT_READY')).toBeInTheDocument()
    expect(screen.getByText(/dataset version not found/)).toBeInTheDocument()
  })

  it('Overview: shows the real Phase 2.7H READY readiness contract with dataset/token statistics', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: 'cmv-1', dataset_version_public_id: 'dsv-1' },
      teDatasetReadinessContractData: {
        status: 'READY', reason: null,
        dataset: { record_count: 40 },
        blocks: { train_token_length_stats: { average_tokens: 12.5 } },
        quality: { train_vocabulary_coverage: { vocabulary_utilization_ratio: 0.42 } },
        resource_estimate: { pipeline_wall_clock_seconds: 0.123 },
      },
    })} />)
    expect(screen.getByText('READY')).toBeInTheDocument()
    expect(screen.getByText(/40 dataset records/)).toBeInTheDocument()
    expect(screen.getByText(/42\.0%/)).toBeInTheDocument()
  })

  it('Overview: distinguishes BLOCKED from NOT_READY in the real Phase 2.7H readiness contract', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: 'cmv-1', dataset_version_public_id: 'dsv-1' },
      teDatasetReadinessContractData: {
        status: 'BLOCKED', reason: "dataset version must be ready or archived (currently 'draft')",
        checks: {},
      },
    })} />)
    expect(screen.getByText('BLOCKED')).toBeInTheDocument()
    expect(screen.getByText(/must be ready or archived/)).toBeInTheDocument()
  })

  it('Overview: shows the real Phase 2.8A training readiness gate as READY TO TRAIN, not a release verdict', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: 'cmv-1', dataset_version_public_id: 'dsv-1' },
      teTrainingReadinessData: {
        status: 'READY', reason: null,
        core_model: { context_length: 32 },
        resource_estimate: { parameter_count: 11600, envelope_classification: 'fits_observed_safe_envelope' },
      },
    })} />)
    expect(screen.getByText('READY')).toBeInTheDocument()
    expect(screen.getByText(/fits_observed_safe_envelope/)).toBeInTheDocument()
    expect(screen.getByText(/qualified to start a controlled training run/)).toBeInTheDocument()
  })

  it('Overview: shows a BLOCKED training readiness reason distinctly from the dataset contract', () => {
    render(<TrainingEngineTab {...baseProps({
      teSubTab: 'Overview',
      teJobData: { topic: 't', stage: 'reserve_runtime', status: 'in_progress', execution_mode: 'gpu', core_model_version_public_id: 'cmv-1', dataset_version_public_id: 'dsv-1' },
      teTrainingReadinessData: {
        status: 'BLOCKED', reason: 'training configuration is invalid: batch size and gradient accumulation must be positive',
      },
    })} />)
    expect(screen.getByText(/batch size and gradient accumulation must be positive/)).toBeInTheDocument()
  })
})
