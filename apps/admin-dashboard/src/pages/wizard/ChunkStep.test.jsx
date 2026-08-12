import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChunkStep from './ChunkStep.jsx'

vi.mock('../../services/api.js', () => ({
  approveChunk: vi.fn(),
  classifyChunk: vi.fn(),
  documentChunks: vi.fn(),
  generateChunks: vi.fn(),
  submitChunkForReview: vi.fn(),
}))

const api = await import('../../services/api.js')
const toast = { success: vi.fn(), error: vi.fn() }

afterEach(() => {
  vi.resetAllMocks()
})

describe('ChunkStep', () => {
  it('shows an empty state before any chunks exist', async () => {
    api.documentChunks.mockResolvedValue({ items: [] })
    render(<ChunkStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    expect(await screen.findByText('No chunks yet.')).toBeInTheDocument()
  })

  it('generating chunks calls generateChunks and lists the real results without completing the step yet', async () => {
    api.documentChunks.mockResolvedValueOnce({ items: [] })
    api.generateChunks.mockResolvedValue({})
    api.documentChunks.mockResolvedValue({
      items: [{ public_id: 'chunk-1', reading_order: 1, chunk_type: 'paragraph', status: 'draft', active_revision: { text: 'Brud AI is real.' } }],
    })
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<ChunkStep documentId="doc-1" onComplete={onComplete} toast={toast} />)
    await screen.findByText('No chunks yet.')
    await user.click(screen.getByRole('button', { name: 'Generate draft chunks from approved pages' }))
    await waitFor(() => expect(api.generateChunks).toHaveBeenCalledWith('doc-1'))
    expect(await screen.findByText('draft')).toBeInTheDocument()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it('warns honestly when generation produces zero chunks', async () => {
    api.documentChunks.mockResolvedValue({ items: [] })
    api.generateChunks.mockResolvedValue({})
    const user = userEvent.setup()
    render(<ChunkStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await screen.findByText('No chunks yet.')
    await user.click(screen.getByRole('button', { name: 'Generate draft chunks from approved pages' }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('No chunks were generated')))
  })

  it('classifying and approving a chunk runs the real 3-call sequence and completes the step', async () => {
    api.documentChunks.mockResolvedValue({
      items: [{ public_id: 'chunk-1', reading_order: 1, chunk_type: 'unknown', status: 'draft', active_revision: { text: 'Brud AI is real.' } }],
    })
    api.classifyChunk.mockResolvedValue({})
    api.submitChunkForReview.mockResolvedValue({})
    api.approveChunk.mockResolvedValue({})
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<ChunkStep documentId="doc-1" onComplete={onComplete} toast={toast} />)
    await user.selectOptions(await screen.findByLabelText('Chunk type (applied when approving)'), 'definition')
    await user.click(screen.getByRole('button', { name: 'Classify & approve' }))
    await waitFor(() => expect(api.classifyChunk).toHaveBeenCalledWith('chunk-1', 'definition'))
    expect(api.submitChunkForReview).toHaveBeenCalledWith('chunk-1')
    expect(api.approveChunk).toHaveBeenCalledWith('chunk-1')
    expect(onComplete).toHaveBeenCalledWith({ toastMessage: 'Chunk classified and approved.' })
  })
})
