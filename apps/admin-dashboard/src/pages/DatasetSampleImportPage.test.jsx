import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DatasetSampleImportPage from './DatasetSampleImportPage.jsx'

vi.mock('../services/api.js', () => ({
  sampleImports: vi.fn(),
  createSampleImport: vi.fn(),
  sampleImport: vi.fn(),
  cancelSampleImport: vi.fn(),
  requestSampleImportApproval: vi.fn(),
  approveSampleImport: vi.fn(),
  rejectSampleImportApproval: vi.fn(),
  downloadSampleFile: vi.fn(),
  sampleFiles: vi.fn(),
  sampleFile: vi.fn(),
  validateSampleFiles: vi.fn(),
  extractSampleArchives: vi.fn(),
  scanSample: vi.fn(),
  parseSample: vi.fn(),
  sampleRecords: vi.fn(),
  reviewSampleRecord: vi.fn(),
  createSampleRecordRevision: vi.fn(),
  sampleIssues: vi.fn(),
  reviewSampleIssue: vi.fn(),
  runSampleQualityChecks: vi.fn(),
  runSampleDuplicateChecks: vi.fn(),
  runSampleContaminationChecks: vi.fn(),
  finalizeSampleImport: vi.fn(),
  sampleImportReport: vi.fn(),
  requestSampleDeletion: vi.fn(),
  executeSampleDeletion: vi.fn(),
  sampleImportEvents: vi.fn(),
}))

const api = await import('../services/api.js')

const SEEDED_IMPORTS = [
  {
    public_id: 'si-1', sample_import_code: 'SI-abc123', status: 'draft',
    current_stage: 'eligibility_check', purpose: 'manual_review',
    rag_sandbox_eligible: null, locked_at: null,
  },
]

const SEEDED_SELECTED = {
  public_id: 'si-1', sample_import_code: 'SI-abc123', status: 'draft',
  current_stage: 'eligibility_check', purpose: 'manual_review',
  quarantine_bytes_used: 0, rag_sandbox_eligible: null,
  training_assessment_status: null, locked_at: null,
}

function mockDefaults() {
  api.sampleImports.mockResolvedValue({ items: SEEDED_IMPORTS, page: 1, page_size: 100 })
  api.sampleImport.mockResolvedValue(SEEDED_SELECTED)
  api.sampleFiles.mockResolvedValue({ items: [] })
  api.sampleRecords.mockResolvedValue({ items: [] })
  api.sampleIssues.mockResolvedValue({ items: [] })
  api.sampleImportReport.mockResolvedValue(null)
  api.sampleImportEvents.mockResolvedValue({ items: [] })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('DatasetSampleImportPage', () => {
  it('shows the safety notice on load', async () => {
    mockDefaults()
    render(<DatasetSampleImportPage />)
    expect(
      await screen.findByText(/never downloads a full dataset, clones a repository/)
    ).toBeInTheDocument()
  })

  it('shows an empty state before any sample import is selected', async () => {
    mockDefaults()
    render(<DatasetSampleImportPage />)
    expect(
      await screen.findByText(/Select or create a sample import in the "Sample Imports" tab/)
    ).toBeInTheDocument()
  })

  it('lists sample imports and creates a new one', async () => {
    mockDefaults()
    api.createSampleImport.mockResolvedValue({ ...SEEDED_SELECTED, public_id: 'si-new', sample_import_code: 'SI-new1' })
    const user = userEvent.setup()
    render(<DatasetSampleImportPage />)
    await user.click(screen.getByRole('button', { name: 'Sample Imports' }))
    expect(await screen.findByText('SI-abc123')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Verification case public ID'), 'case-1')
    await user.type(screen.getByLabelText('Candidate public ID'), 'cand-1')
    await user.click(screen.getByRole('button', { name: 'Create sample import proposal' }))
    await waitFor(() => expect(api.createSampleImport).toHaveBeenCalled())
  })

  it('selecting an import loads its files, records, and issues', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<DatasetSampleImportPage />)
    await user.click(screen.getByRole('button', { name: 'Sample Imports' }))
    await screen.findByText('SI-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await waitFor(() => expect(api.sampleFiles).toHaveBeenCalledWith('si-1'))
    await waitFor(() => expect(api.sampleRecords).toHaveBeenCalledWith('si-1', '?page_size=100'))
  })

  it('requesting approval calls the API with the entered limits', async () => {
    mockDefaults()
    api.requestSampleImportApproval.mockResolvedValue({ public_id: 'ap-1', status: 'pending' })
    const user = userEvent.setup()
    render(<DatasetSampleImportPage />)
    await user.click(screen.getByRole('button', { name: 'Sample Imports' }))
    await screen.findByText('SI-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await user.click(screen.getByRole('button', { name: 'Approval' }))
    await user.click(screen.getByRole('button', { name: 'Request approval' }))
    await waitFor(() => expect(api.requestSampleImportApproval).toHaveBeenCalled())
  })

  it('finalize is not offered to render "Training Approved" or "Production RAG Approved" text', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<DatasetSampleImportPage />)
    await user.click(screen.getByRole('button', { name: 'Sample Imports' }))
    await screen.findByText('SI-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await user.click(screen.getByRole('button', { name: 'Final Report' }))
    expect(screen.queryByText(/Training Approved/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Production RAG Approved/)).not.toBeInTheDocument()
  })

  it('deletion request requires a non-empty reason before submitting', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<DatasetSampleImportPage />)
    await user.click(screen.getByRole('button', { name: 'Sample Imports' }))
    await screen.findByText('SI-abc123')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await user.click(screen.getByRole('button', { name: 'Deletion & History' }))
    await user.click(screen.getByRole('button', { name: 'Request deletion' }))
    expect(api.requestSampleDeletion).not.toHaveBeenCalled()
  })

  it('surfaces an API error message', async () => {
    mockDefaults()
    api.sampleImports.mockRejectedValue(new Error('Request failed.'))
    render(<DatasetSampleImportPage />)
    expect(await screen.findByText('Request failed.')).toBeInTheDocument()
  })
})
