import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DatasetDiscoveryPage from './DatasetDiscoveryPage.jsx'

vi.mock('../services/api.js', () => ({
  discoverySessions: vi.fn(),
  createDiscoverySession: vi.fn(),
  discoverySession: vi.fn(),
  cancelDiscoverySession: vi.fn(),
  discoveryRequirements: vi.fn(),
  setDiscoveryRequirements: vi.fn(),
  runDiscoverySearch: vi.fn(),
  discoveryCandidates: vi.fn(),
  addManualDiscoveryCandidate: vi.fn(),
  discoveryCandidate: vi.fn(),
  excludeDiscoveryCandidate: vi.fn(),
  restoreDiscoveryCandidate: vi.fn(),
  discoveryProviderRuns: vi.fn(),
  discoveryEvents: vi.fn(),
  discoveryComparisons: vi.fn(),
  createDiscoveryComparison: vi.fn(),
  discoveryComparison: vi.fn(),
}))

const api = await import('../services/api.js')

const SEEDED_SESSIONS = [
  {
    public_id: 's-1', session_code: 'discovery-abc123', title: 'Tamil ASR search',
    status: 'draft', current_stage: 'requirement', provider_count: 0,
    successful_provider_count: 0, result_count: 0,
  },
]

const SEEDED_CANDIDATES = [
  {
    public_id: 'c-1', canonical_name: 'IndicVoices Tamil', organization: 'ai4bharat',
    licence_status: 'declared', declared_licence: 'cc-by-4.0', suitability_score: 82,
    recommendation_status: 'recommended_for_review', provider_count: 1, excluded: false,
  },
]

function mockDefaults() {
  api.discoverySessions.mockResolvedValue({ items: SEEDED_SESSIONS, page: 1, page_size: 100 })
  api.discoverySession.mockResolvedValue(SEEDED_SESSIONS[0])
  api.discoveryRequirements.mockResolvedValue({})
  api.discoveryCandidates.mockResolvedValue({ items: SEEDED_CANDIDATES })
  api.discoveryComparisons.mockResolvedValue({ items: [] })
  api.discoveryEvents.mockResolvedValue({ items: [] })
  api.discoveryProviderRuns.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('DatasetDiscoveryPage', () => {
  it('shows the safety notice on load', async () => {
    mockDefaults()
    render(<DatasetDiscoveryPage />)
    expect(await screen.findByText(/nothing here downloads a file, imports a dataset/)).toBeInTheDocument()
  })

  it('lists sessions and creates a new one', async () => {
    mockDefaults()
    api.createDiscoverySession.mockResolvedValue({
      public_id: 's-new', session_code: 'discovery-new1', title: 'New search',
      status: 'draft', current_stage: 'requirement',
    })
    const user = userEvent.setup()
    render(<DatasetDiscoveryPage />)
    expect(await screen.findByText('Tamil ASR search')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Title'), 'New search')
    await user.click(screen.getByRole('button', { name: 'New session' }))
    await waitFor(() => expect(api.createDiscoverySession).toHaveBeenCalledWith({ title: 'New search' }))
  })

  it('selecting a session loads its requirement, candidates, and history', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<DatasetDiscoveryPage />)
    await screen.findByText('Tamil ASR search')
    await user.click(screen.getByRole('button', { name: 'Select' }))
    await waitFor(() => expect(api.discoveryCandidates).toHaveBeenCalledWith('s-1'))
    await waitFor(() => expect(api.discoveryRequirements).toHaveBeenCalledWith('s-1'))
  })

  it('run search calls the API for the selected session', async () => {
    mockDefaults()
    api.runDiscoverySearch.mockResolvedValue({ ...SEEDED_SESSIONS[0], status: 'completed' })
    const user = userEvent.setup()
    render(<DatasetDiscoveryPage />)
    await screen.findByText('Tamil ASR search')
    await user.click(screen.getByRole('button', { name: 'Select' }))
    await screen.findByRole('button', { name: 'Run search' })
    await user.click(screen.getByRole('button', { name: 'Run search' }))
    await waitFor(() => expect(api.runDiscoverySearch).toHaveBeenCalledWith('s-1'))
  })

  it('saving the requirement submits the selected languages and tasks', async () => {
    mockDefaults()
    api.setDiscoveryRequirements.mockResolvedValue({ languages: ['tamil'], tasks: ['asr'] })
    const user = userEvent.setup()
    render(<DatasetDiscoveryPage />)
    await screen.findByText('Tamil ASR search')
    await user.click(screen.getByRole('button', { name: 'Select' }))
    await user.click(screen.getByRole('button', { name: 'Requirement' }))
    await user.click(screen.getByLabelText('tamil'))
    await user.click(screen.getByLabelText('asr'))
    await user.click(screen.getByRole('button', { name: 'Save requirement' }))
    await waitFor(() => expect(api.setDiscoveryRequirements).toHaveBeenCalledWith(
      's-1', expect.objectContaining({ languages: ['tamil'], tasks: ['asr'] })
    ))
  })

  it('lists candidates with score and recommendation, and excludes one', async () => {
    mockDefaults()
    api.excludeDiscoveryCandidate.mockResolvedValue({ ...SEEDED_CANDIDATES[0], excluded: true })
    const user = userEvent.setup()
    render(<DatasetDiscoveryPage />)
    await screen.findByText('Tamil ASR search')
    await user.click(screen.getByRole('button', { name: 'Select' }))
    await user.click(screen.getByRole('button', { name: 'Candidates' }))
    expect(await screen.findByText('IndicVoices Tamil')).toBeInTheDocument()
    expect(screen.getByText('82/100')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Exclude' }))
    await waitFor(() => expect(api.excludeDiscoveryCandidate).toHaveBeenCalledWith('c-1'))
  })

  it('adds a manual candidate not surfaced by any provider', async () => {
    mockDefaults()
    api.addManualDiscoveryCandidate.mockResolvedValue({
      public_id: 'c-manual', canonical_name: 'Manually Found Corpus',
      candidate_entry_method: 'manual',
    })
    const user = userEvent.setup()
    render(<DatasetDiscoveryPage />)
    await screen.findByText('Tamil ASR search')
    await user.click(screen.getByRole('button', { name: 'Select' }))
    await user.click(screen.getByRole('button', { name: 'Candidates' }))
    await user.type(screen.getByLabelText('Name'), 'Manually Found Corpus')
    await user.click(screen.getByRole('button', { name: 'Add manual candidate' }))
    await waitFor(() => expect(api.addManualDiscoveryCandidate).toHaveBeenCalledWith(
      's-1', expect.objectContaining({ canonical_name: 'Manually Found Corpus' })
    ))
  })

  it('creates a comparison from two selected candidates', async () => {
    mockDefaults()
    api.discoveryCandidates.mockResolvedValue({
      items: [
        SEEDED_CANDIDATES[0],
        { ...SEEDED_CANDIDATES[0], public_id: 'c-2', canonical_name: 'Second Candidate' },
      ],
    })
    api.createDiscoveryComparison.mockResolvedValue({
      public_id: 'cmp-1', candidate_ids: ['c-1', 'c-2'], created_at: '2026-01-01',
      summary: { best_overall_candidate_public_id: 'c-1', warnings: [] },
    })
    const user = userEvent.setup()
    render(<DatasetDiscoveryPage />)
    await screen.findByText('Tamil ASR search')
    await user.click(screen.getByRole('button', { name: 'Select' }))
    await user.click(screen.getByRole('button', { name: 'Candidates' }))
    await screen.findByText('IndicVoices Tamil')
    const checkboxes = screen.getAllByRole('checkbox')
    await user.click(checkboxes[0])
    await user.click(checkboxes[1])

    await user.click(screen.getByRole('button', { name: 'Comparison' }))
    await user.click(screen.getByRole('button', { name: 'Create comparison' }))
    await waitFor(() => expect(api.createDiscoveryComparison).toHaveBeenCalledWith(
      's-1', { candidate_ids: ['c-1', 'c-2'] }
    ))
  })

  it('shows an error notice without a stack trace on API failure', async () => {
    api.discoverySessions.mockRejectedValue(new Error('Request failed.'))
    render(<DatasetDiscoveryPage />)
    expect(await screen.findByText('Request failed.')).toBeInTheDocument()
  })
})
