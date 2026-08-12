import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UploadStep from './UploadStep.jsx'

vi.mock('../../services/api.js', () => ({
  dataSources: vi.fn(),
  documentWorkspace: vi.fn(),
  documents: vi.fn(),
  linkDocumentSource: vi.fn(),
  uploadDocument: vi.fn(),
}))

const api = await import('../../services/api.js')

const toast = { success: vi.fn(), error: vi.fn() }

afterEach(() => {
  vi.resetAllMocks()
})

describe('UploadStep', () => {
  it('shows a resume list built from real documents()', async () => {
    api.documents.mockResolvedValue({ items: [{ public_id: 'doc-1', original_filename: 'brud.pdf', page_count: 3, status: 'ready' }] })
    render(<UploadStep documentId={null} onDocumentReady={vi.fn()} onComplete={vi.fn()} toast={toast} />)
    expect(await screen.findByText('brud.pdf')).toBeInTheDocument()
  })

  it('resuming a document whose source is already linked completes immediately', async () => {
    api.documents.mockResolvedValue({ items: [{ public_id: 'doc-1', original_filename: 'brud.pdf', page_count: 3, status: 'ready' }] })
    api.documentWorkspace.mockResolvedValue({ source_status: 'linked' })
    const onDocumentReady = vi.fn()
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<UploadStep documentId={null} onDocumentReady={onDocumentReady} onComplete={onComplete} toast={toast} />)
    await user.click(await screen.findByText('brud.pdf'))
    await waitFor(() => expect(onDocumentReady).toHaveBeenCalledWith('doc-1', 'brud.pdf'))
    expect(onComplete).toHaveBeenCalledWith({ toastMessage: '"brud.pdf" is ready (source already linked).' })
    expect(api.dataSources).not.toHaveBeenCalled()
  })

  it('resuming an unlinked document shows the real source picker, and linking completes the step', async () => {
    api.documents.mockResolvedValue({ items: [{ public_id: 'doc-1', original_filename: 'brud.pdf', page_count: 3, status: 'ready' }] })
    api.documentWorkspace.mockResolvedValue({ source_status: 'unlinked' })
    api.dataSources.mockResolvedValue({ items: [{ public_id: 'src-1', source_code: 'SRC-001', title: 'Sample source' }] })
    api.linkDocumentSource.mockResolvedValue({})
    const onDocumentReady = vi.fn()
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<UploadStep documentId={null} onDocumentReady={onDocumentReady} onComplete={onComplete} toast={toast} />)
    await user.click(await screen.findByText('brud.pdf'))
    expect(await screen.findByText(/has no linked data source yet/)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Data source'), 'src-1')
    await user.click(screen.getByRole('button', { name: 'Link source' }))
    await waitFor(() => expect(api.linkDocumentSource).toHaveBeenCalledWith('doc-1', 'src-1'))
    expect(onDocumentReady).toHaveBeenCalledWith('doc-1', 'brud.pdf')
    expect(onComplete).toHaveBeenCalledWith({ toastMessage: 'Data source linked to "brud.pdf".' })
  })

  it('shows an empty state when there are no documents yet', async () => {
    api.documents.mockResolvedValue({ items: [] })
    render(<UploadStep documentId={null} onDocumentReady={vi.fn()} onComplete={vi.fn()} toast={toast} />)
    expect(await screen.findByText('No documents uploaded yet.')).toBeInTheDocument()
  })

  it('uploading a new file checks the real link status before completing', async () => {
    api.documents.mockResolvedValue({ items: [] })
    api.uploadDocument.mockResolvedValue({ public_id: 'doc-2', original_filename: 'new.pdf' })
    api.documentWorkspace.mockResolvedValue({ source_status: 'linked' })
    const onDocumentReady = vi.fn()
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<UploadStep documentId={null} onDocumentReady={onDocumentReady} onComplete={onComplete} toast={toast} />)
    await screen.findByText('No documents uploaded yet.')

    const file = new File(['%PDF-1.4'], 'new.pdf', { type: 'application/pdf' })
    const input = screen.getByLabelText('PDF document')
    await user.upload(input, file)
    await user.click(screen.getByRole('button', { name: 'Upload securely' }))

    await waitFor(() => expect(api.uploadDocument).toHaveBeenCalled())
    await waitFor(() => expect(api.documentWorkspace).toHaveBeenCalledWith('doc-2'))
    expect(onDocumentReady).toHaveBeenCalledWith('doc-2', 'new.pdf')
    expect(onComplete).toHaveBeenCalled()
  })

  it('shows a summary instead of the picker once a document is already selected', () => {
    api.documents.mockResolvedValue({ items: [] })
    render(<UploadStep documentId="doc-1" documentTitle="brud.pdf" onDocumentReady={vi.fn()} onComplete={vi.fn()} toast={toast} />)
    expect(screen.getByText('Document selected')).toBeInTheDocument()
    expect(screen.getByText('brud.pdf')).toBeInTheDocument()
  })
})
