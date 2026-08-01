import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RagSandboxPage from './RagSandboxPage.jsx'

vi.mock('../services/api.js', () => ({
  ragSandboxOverview: vi.fn(),
  ragSandboxExperiments: vi.fn(),
  createRagSandboxExperiment: vi.fn(),
  ragSandboxExperiment: vi.fn(),
  ragSandboxEligibility: vi.fn(),
  cancelRagSandboxExperiment: vi.fn(),
  requestRagSandboxApproval: vi.fn(),
  approveRagSandboxExperiment: vi.fn(),
  rejectRagSandboxApproval: vi.fn(),
  prepareRagSandboxCorpus: vi.fn(),
  ragSandboxRecords: vi.fn(),
  buildRagSandboxIndex: vi.fn(),
  ragSandboxIndexes: vi.fn(),
  deleteRagSandboxIndex: vi.fn(),
  createRagSandboxQuerySet: vi.fn(),
  ragSandboxQuerySets: vi.fn(),
  addRagSandboxQuery: vi.fn(),
  ragSandboxQueries: vi.fn(),
  finalizeRagSandboxQuerySet: vi.fn(),
  runRagSandboxRetrieval: vi.fn(),
  ragSandboxRetrievalRuns: vi.fn(),
  ragSandboxRetrievalRun: vi.fn(),
  runRagSandboxGeneration: vi.fn(),
  ragSandboxAnswerRuns: vi.fn(),
  ragSandboxAnswerRun: vi.fn(),
  ragSandboxCitations: vi.fn(),
  ragSandboxEvaluations: vi.fn(),
  runRagSandboxEvaluation: vi.fn(),
  reviewRagSandboxQuery: vi.fn(),
  finalizeRagSandboxReport: vi.fn(),
  ragSandboxReports: vi.fn(),
  acceptRagSandboxExperiment: vi.fn(),
  rejectRagSandboxExperiment: vi.fn(),
  requestRagSandboxDeletion: vi.fn(),
  confirmRagSandboxDeletion: vi.fn(),
  executeRagSandboxDeletion: vi.fn(),
  ragSandboxEvents: vi.fn(),
}))

const api = await import('../services/api.js')

const SEEDED_EXPERIMENTS = [
  {
    public_id: 'exp-1', experiment_code: 'RSE-abc123', status: 'draft',
    current_stage: 'eligibility', purpose: 'retrieval_validation',
    production_rag_readiness: 'not_assessed',
  },
]

const SEEDED_SELECTED = {
  public_id: 'exp-1', experiment_code: 'RSE-abc123', status: 'draft',
  current_stage: 'eligibility', purpose: 'retrieval_validation',
  production_rag_readiness: 'not_assessed', training_data_observation: 'not_assessed',
}

function mockDefaults() {
  api.ragSandboxExperiments.mockResolvedValue({ items: SEEDED_EXPERIMENTS, page: 1, page_size: 100 })
  api.ragSandboxExperiment.mockResolvedValue(SEEDED_SELECTED)
  api.ragSandboxEligibility.mockResolvedValue({ eligible: true, checks: {}, blocking_reasons: [], warnings: [] })
  api.ragSandboxRecords.mockResolvedValue({ items: [] })
  api.ragSandboxIndexes.mockResolvedValue({ items: [] })
  api.ragSandboxQuerySets.mockResolvedValue({ items: [] })
  api.ragSandboxRetrievalRuns.mockResolvedValue({ items: [] })
  api.ragSandboxAnswerRuns.mockResolvedValue({ items: [] })
  api.ragSandboxCitations.mockResolvedValue({ items: [] })
  api.ragSandboxEvaluations.mockResolvedValue({ items: [] })
  api.ragSandboxReports.mockResolvedValue({ items: [] })
  api.ragSandboxEvents.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('RagSandboxPage', () => {
  it('shows the safety notice on load', async () => {
    mockDefaults()
    render(<RagSandboxPage />)
    expect(
      await screen.findByText(/never-production-visible knowledge space and index/)
    ).toBeInTheDocument()
  })

  it('shows an empty state before any experiment is selected', async () => {
    mockDefaults()
    render(<RagSandboxPage />)
    expect(
      await screen.findByText(/Select or create an experiment in the "Experiments" tab/)
    ).toBeInTheDocument()
  })

  it('lists experiments and creates a new one', async () => {
    mockDefaults()
    api.createRagSandboxExperiment.mockResolvedValue({ ...SEEDED_SELECTED, public_id: 'exp-new', experiment_code: 'RSE-new1' })
    const user = userEvent.setup()
    render(<RagSandboxPage />)
    await user.click(screen.getByRole('button', { name: 'Experiments' }))
    expect(await screen.findByText('RSE-abc123')).toBeInTheDocument()

    await user.type(screen.getByLabelText(/Finalized Phase 12 sample-import public ID/), 'si-1')
    await user.click(screen.getByRole('button', { name: 'Create RAG sandbox proposal' }))
    await waitFor(() => expect(api.createRagSandboxExperiment).toHaveBeenCalled())
  })

  it('selecting an experiment loads its records, indexes, and query sets', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<RagSandboxPage />)
    await user.click(screen.getByRole('button', { name: 'Experiments' }))
    await screen.findByText('RSE-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await waitFor(() => expect(api.ragSandboxRecords).toHaveBeenCalledWith('exp-1', '?page_size=100'))
    await waitFor(() => expect(api.ragSandboxIndexes).toHaveBeenCalledWith('exp-1'))
    await waitFor(() => expect(api.ragSandboxQuerySets).toHaveBeenCalledWith('exp-1'))
  })

  it('preparing the corpus calls the API', async () => {
    mockDefaults()
    api.prepareRagSandboxCorpus.mockResolvedValue({ public_id: 'corpus-1', status: 'ready' })
    const user = userEvent.setup()
    render(<RagSandboxPage />)
    await user.click(screen.getByRole('button', { name: 'Experiments' }))
    await screen.findByText('RSE-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await user.click(screen.getByRole('button', { name: 'Corpus' }))
    await user.click(screen.getByRole('button', { name: 'Prepare isolated corpus' }))
    await waitFor(() => expect(api.prepareRagSandboxCorpus).toHaveBeenCalledWith('exp-1'))
  })

  it('final report tab never renders "Production RAG Activated" or "Training Approved" text', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<RagSandboxPage />)
    await user.click(screen.getByRole('button', { name: 'Experiments' }))
    await screen.findByText('RSE-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await user.click(screen.getByRole('button', { name: 'Final Report' }))
    expect(screen.queryByText(/Production RAG Activated/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Training Approved/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Model Released/)).not.toBeInTheDocument()
  })

  it('deletion request requires a non-empty reason before submitting', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<RagSandboxPage />)
    await user.click(screen.getByRole('button', { name: 'Experiments' }))
    await screen.findByText('RSE-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await user.click(screen.getByRole('button', { name: 'Deletion & History' }))
    await user.click(screen.getByRole('button', { name: 'Request deletion' }))
    expect(api.requestRagSandboxDeletion).not.toHaveBeenCalled()
  })

  it('surfaces an API error message', async () => {
    mockDefaults()
    api.ragSandboxExperiments.mockRejectedValue(new Error('Request failed.'))
    render(<RagSandboxPage />)
    expect(await screen.findByText('Request failed.')).toBeInTheDocument()
  })
})
