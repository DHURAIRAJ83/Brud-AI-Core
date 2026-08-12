import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OcrStep from './OcrStep.jsx'

vi.mock('../../services/api.js', () => ({
  analyzeDocument: vi.fn(),
  approveDocumentPage: vi.fn(),
  documentDetail: vi.fn(),
  documentPages: vi.fn(),
  processDocument: vi.fn(),
}))

const api = await import('../../services/api.js')
const toast = { success: vi.fn(), error: vi.fn() }

afterEach(() => {
  vi.resetAllMocks()
})

function mockDefaults() {
  api.documentDetail.mockResolvedValue({ public_id: 'doc-1', extraction_strategy: 'auto' })
  api.documentPages.mockResolvedValue({ items: [] })
}

describe('OcrStep', () => {
  it('shows an empty state before pages exist', async () => {
    mockDefaults()
    render(<OcrStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    expect(await screen.findByText(/No pages yet/)).toBeInTheDocument()
  })

  it('Analyze pages calls analyzeDocument and reloads', async () => {
    mockDefaults()
    api.analyzeDocument.mockResolvedValue({})
    const user = userEvent.setup()
    render(<OcrStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await screen.findByText(/No pages yet/)
    await user.click(screen.getByRole('button', { name: 'Analyze pages' }))
    await waitFor(() => expect(api.analyzeDocument).toHaveBeenCalledWith('doc-1'))
  })

  it('Process calls processDocument with the real extraction strategy', async () => {
    mockDefaults()
    api.processDocument.mockResolvedValue({})
    const user = userEvent.setup()
    render(<OcrStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await screen.findByRole('button', { name: 'Process auto' })
    await user.click(screen.getByRole('button', { name: 'Process auto' }))
    await waitFor(() => expect(api.processDocument).toHaveBeenCalledWith('doc-1', { strategy: 'auto' }))
  })

  it('approving a page calls approveDocumentPage and completes the step', async () => {
    api.documentDetail.mockResolvedValue({ public_id: 'doc-1', extraction_strategy: 'auto' })
    api.documentPages.mockResolvedValue({ items: [{ page_number: 1, review_status: 'pending' }] })
    api.approveDocumentPage.mockResolvedValue({})
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<OcrStep documentId="doc-1" onComplete={onComplete} toast={toast} />)
    await user.click(await screen.findByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.approveDocumentPage).toHaveBeenCalledWith('doc-1', 1))
    expect(onComplete).toHaveBeenCalledWith({ toastMessage: 'Page 1 approved.' })
  })
})
