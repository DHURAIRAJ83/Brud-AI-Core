import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DocumentWizardPage from './DocumentWizardPage.jsx'

vi.mock('../services/api.js', () => ({
  chunkCoverageReport: vi.fn(), documentDetail: vi.fn(), documentPages: vi.fn(),
  documentRepeatedElements: vi.fn(), documentSftCandidateSummary: vi.fn(), documentSftExports: vi.fn(),
  documentTamilQualitySummary: vi.fn(), documentWorkspace: vi.fn(), documents: vi.fn(),
  documentHandoffs: vi.fn(), documentDatasetVersionStatus: vi.fn(), validateDocumentSftExport: vi.fn(),
  previewDocumentSftHandoff: vi.fn(), ingestDocumentSftHandoff: vi.fn(), proposeDatasetVersion: vi.fn(),
  documentHandoffSplitPreview: vi.fn(), confirmDatasetVersionBuild: vi.fn(),
}))

const api = await import('../services/api.js')

const DOCUMENT = { public_id: 'doc-1', original_filename: 'sample.pdf', page_count: 2, status: 'review_ready' }
const PAGES = [
  { public_id: 'p1', page_number: 1, extraction_status: 'success', review_status: 'approved' },
  { public_id: 'p2', page_number: 2, extraction_status: 'success', review_status: 'approved' },
]
const WORKSPACE = { review_status_counts: { pending: 0, approved: 2, rejected: 0, excluded: 0 }, low_confidence_page_count: 0, readiness: 'ready' }

function mockBaseline() {
  api.documents.mockResolvedValue({ items: [DOCUMENT] })
  api.documentDetail.mockResolvedValue(DOCUMENT)
  api.documentPages.mockResolvedValue({ items: PAGES })
  api.documentWorkspace.mockResolvedValue(WORKSPACE)
  api.documentRepeatedElements.mockResolvedValue({ items: [] })
  api.documentTamilQualitySummary.mockResolvedValue({ total_issues: 0, pending_count: 0 })
  api.chunkCoverageReport.mockResolvedValue({})
  api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 0, approved_count: 0 })
  api.documentSftExports.mockResolvedValue({ items: [] })
  api.documentHandoffs.mockResolvedValue({ items: [] })
  api.documentDatasetVersionStatus.mockResolvedValue({ status: 'no_dataset_version_proposed', dataset_version_public_id: null })
}

afterEach(() => { vi.resetAllMocks() })

describe('DocumentWizardPage', () => {
  it('lists documents and shows a not-started prompt before one is selected', async () => {
    mockBaseline()
    render(<DocumentWizardPage />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    expect(screen.getByText('Select a document to see its guided status.')).toBeInTheDocument()
  })

  it('renders all fourteen steps with real computed status for a fully-processed document', async () => {
    mockBaseline()
    const user = userEvent.setup()
    render(<DocumentWizardPage />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Document'), 'doc-1')
    await waitFor(() => expect(screen.getByText('1. Upload')).toBeInTheDocument())
    for (const label of [
      '1. Upload', '2. Extract', '3. Review Pages', '4. Cleanup', '5. Tamil Quality',
      '6. Create Chunks', '7. Generate SFT', '8. Review Candidates', '9. Export JSONL',
      '10. Validate Export', '11. Dataset Handoff', '12. Preview Split', '13. Build Dataset Version',
      '14. Training Readiness',
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.getAllByText('completed').length).toBeGreaterThan(0)
  })

  it('flags review_pages as blocked with a blocking reason when no pages exist yet', async () => {
    mockBaseline()
    api.documentPages.mockResolvedValue({ items: [] })
    const user = userEvent.setup()
    render(<DocumentWizardPage />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Document'), 'doc-1')
    await waitFor(() => expect(screen.getByText('Blocked: no pages extracted yet')).toBeInTheDocument())
  })

  it('states plainly that training does not start automatically once a version is built', async () => {
    mockBaseline()
    api.documentSftExports.mockResolvedValue({ items: [{ public_id: 'exp-1', record_count: 3, checksum_sha256: 'abc123checksum' }] })
    api.documentHandoffs.mockResolvedValue({ items: [{ public_id: 'ho-1', imported_count: 3, dataset_source_public_id: 'src-12345678', dataset_build_public_id: 'build-1' }] })
    api.documentDatasetVersionStatus.mockResolvedValue({ status: 'version_built', dataset_version_public_id: 'ver-12345678' })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 3, approved_count: 3 })
    const user = userEvent.setup()
    render(<DocumentWizardPage />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Document'), 'doc-1')
    await waitFor(() => expect(screen.getByText(/Training requires a separate Admin approval/)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Open resulting dataset version' })).toBeInTheDocument()
  })

  it('previews then requires explicit confirmation before ingesting a handoff', async () => {
    mockBaseline()
    api.documentSftExports.mockResolvedValue({ items: [{ public_id: 'exp-1', record_count: 2, checksum_sha256: 'abc123checksum' }] })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 2, approved_count: 2 })
    api.previewDocumentSftHandoff.mockResolvedValue({ record_count: 2, eligible_count: 2, duplicate_count: 0, lineage_missing_count: 0 })
    const user = userEvent.setup()
    render(<DocumentWizardPage />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Document'), 'doc-1')
    await waitFor(() => expect(screen.getByText('11. Dataset Handoff')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Preview handoff' }))
    await waitFor(() => expect(api.previewDocumentSftHandoff).toHaveBeenCalledWith('doc-1', 'exp-1'))
    await waitFor(() => expect(screen.getByRole('button', { name: /Confirm ingestion/ })).toBeInTheDocument())
    expect(api.ingestDocumentSftHandoff).not.toHaveBeenCalled()
  })

  it('shows the ingestion success notice after confirming (not clobbered by the post-ingest reload)', async () => {
    mockBaseline()
    api.documentSftExports.mockResolvedValue({ items: [{ public_id: 'exp-1', record_count: 2, checksum_sha256: 'abc123checksum' }] })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 2, approved_count: 2 })
    api.previewDocumentSftHandoff.mockResolvedValue({ record_count: 2, eligible_count: 2, duplicate_count: 0, lineage_missing_count: 0 })
    api.ingestDocumentSftHandoff.mockResolvedValue({})
    const user = userEvent.setup()
    render(<DocumentWizardPage />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Document'), 'doc-1')
    await waitFor(() => expect(screen.getByText('11. Dataset Handoff')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Preview handoff' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Confirm ingestion/ })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /Confirm ingestion/ }))
    await waitFor(() => expect(screen.getByText('Records ingested into the dataset-record system.')).toBeInTheDocument())
  })

  it('calls onNavigate when Open Documents page is clicked', async () => {
    mockBaseline()
    const onNavigate = vi.fn()
    const user = userEvent.setup()
    render(<DocumentWizardPage onNavigate={onNavigate} />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Open Documents page' }))
    expect(onNavigate).toHaveBeenCalledWith('Documents')
  })
})

describe('DocumentWizardPage: deep-link navigation', () => {
  it('selects the requested document on mount when initialDocumentPublicId is given', async () => {
    mockBaseline()
    render(<DocumentWizardPage initialDocumentPublicId="doc-1" initialStep={11} />)
    await waitFor(() => expect(api.documentDetail).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(screen.getByText('11. Dataset Handoff')).toBeInTheDocument())
  })

  it('shows a non-fatal notice for a step number outside the valid range', async () => {
    mockBaseline()
    render(<DocumentWizardPage initialDocumentPublicId="doc-1" initialStep={99} />)
    await waitFor(() => expect(screen.getByText(/requested wizard step is unavailable/)).toBeInTheDocument())
    expect(screen.getByText('1. Upload')).toBeInTheDocument()
  })

  it('shows a stable not-found state for an unknown document public ID', async () => {
    mockBaseline()
    render(<DocumentWizardPage initialDocumentPublicId="doc-does-not-exist" />)
    await waitFor(() => expect(screen.getByText(/requested document was not found/)).toBeInTheDocument())
  })

  it('calls onNavigationChange with the selected document when the dropdown changes', async () => {
    mockBaseline()
    const onNavigationChange = vi.fn()
    const user = userEvent.setup()
    render(<DocumentWizardPage onNavigationChange={onNavigationChange} />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Document'), 'doc-1')
    await waitFor(() => expect(onNavigationChange).toHaveBeenCalledWith('doc-1', null))
  })

  it('uses onOpenDatasetVersion with the real version public id instead of a bare page switch', async () => {
    mockBaseline()
    api.documentSftExports.mockResolvedValue({ items: [{ public_id: 'exp-1', record_count: 2, checksum_sha256: 'abc' }] })
    api.documentHandoffs.mockResolvedValue({ items: [{ public_id: 'ho-1', imported_count: 2, dataset_source_public_id: 'src-1', dataset_build_public_id: 'build-1' }] })
    api.documentDatasetVersionStatus.mockResolvedValue({ status: 'version_built', dataset_version_public_id: 'ver-9' })
    const onOpenDatasetVersion = vi.fn()
    const onNavigate = vi.fn()
    const user = userEvent.setup()
    render(<DocumentWizardPage onNavigate={onNavigate} onOpenDatasetVersion={onOpenDatasetVersion} />)
    await waitFor(() => expect(screen.getByText(/sample.pdf/)).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Document'), 'doc-1')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Open resulting dataset version' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Open resulting dataset version' }))
    expect(onOpenDatasetVersion).toHaveBeenCalledWith('ver-9')
    expect(onNavigate).not.toHaveBeenCalled()
  })
})
