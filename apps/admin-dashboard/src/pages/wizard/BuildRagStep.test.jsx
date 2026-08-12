import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BuildRagStep from './BuildRagStep.jsx'

vi.mock('../../services/api.js', () => ({
  createRagChunkSet: vi.fn(),
  createRagSource: vi.fn(),
  createRagSourceVersion: vi.fn(),
  documentChunks: vi.fn(),
  documentDetail: vi.fn(),
  ragSpaces: vi.fn(),
  validateRagChunkSet: vi.fn(),
  validateRagSourceVersion: vi.fn(),
}))

const api = await import('../../services/api.js')
const toast = { success: vi.fn(), error: vi.fn() }

afterEach(() => {
  vi.resetAllMocks()
  vi.unstubAllGlobals()
})

function mockDefaults() {
  api.ragSpaces.mockResolvedValue({ items: [{ public_id: 'space-1', name: 'Brud Knowledge' }] })
  api.documentChunks.mockResolvedValue({
    items: [{ status: 'approved', active_revision: { text: 'Brud AI is Tamil-first.' } }],
  })
  api.documentDetail.mockResolvedValue({ original_filename: 'brud.pdf' })
}

describe('BuildRagStep', () => {
  it('lists real knowledge spaces and shows the approved-chunk preview', async () => {
    mockDefaults()
    render(<BuildRagStep documentId="doc-1" onComplete={vi.fn()} onNavigate={vi.fn()} toast={toast} />)
    expect(await screen.findByText('Brud Knowledge')).toBeInTheDocument()
    expect(screen.getByText(/Brud AI is Tamil-first\./)).toBeInTheDocument()
  })

  it('Build RAG runs the real create+validate sequence and shows the result IDs', async () => {
    mockDefaults()
    api.createRagSource.mockResolvedValue({ public_id: 'source-1' })
    api.createRagSourceVersion.mockResolvedValue({ public_id: 'version-1' })
    api.validateRagSourceVersion.mockResolvedValue({})
    api.createRagChunkSet.mockResolvedValue({ public_id: 'chunkset-1' })
    api.validateRagChunkSet.mockResolvedValue({})
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<BuildRagStep documentId="doc-1" onComplete={onComplete} onNavigate={vi.fn()} toast={toast} />)
    await screen.findByText('Brud Knowledge')
    await user.click(screen.getByRole('button', { name: 'Build RAG' }))

    await waitFor(() => expect(api.createRagSource).toHaveBeenCalledWith('space-1', expect.objectContaining({
      source_type: 'plain_text', content: expect.stringContaining('Brud AI is Tamil-first.'),
    })))
    expect(api.createRagSourceVersion).toHaveBeenCalledWith('source-1')
    expect(api.validateRagSourceVersion).toHaveBeenCalledWith('version-1')
    expect(api.createRagChunkSet).toHaveBeenCalledWith('version-1', { chunking_strategy: 'heading_aware' })
    expect(api.validateRagChunkSet).toHaveBeenCalledWith('chunkset-1')

    expect(await screen.findByText('source-1')).toBeInTheDocument()
    expect(screen.getByText('version-1')).toBeInTheDocument()
    expect(screen.getByText('chunkset-1')).toBeInTheDocument()
    expect(onComplete).toHaveBeenCalled()
  })

  it('"Continue" link navigates to the real Knowledge & RAG page, without claiming RAG is fully live', async () => {
    mockDefaults()
    api.createRagSource.mockResolvedValue({ public_id: 'source-1' })
    api.createRagSourceVersion.mockResolvedValue({ public_id: 'version-1' })
    api.validateRagSourceVersion.mockResolvedValue({})
    api.createRagChunkSet.mockResolvedValue({ public_id: 'chunkset-1' })
    api.validateRagChunkSet.mockResolvedValue({})
    const onNavigate = vi.fn()
    const user = userEvent.setup()
    render(<BuildRagStep documentId="doc-1" onComplete={vi.fn()} onNavigate={onNavigate} toast={toast} />)
    await screen.findByText('Brud Knowledge')
    await user.click(screen.getByRole('button', { name: 'Build RAG' }))
    await screen.findByText('source-1')
    await user.click(screen.getByRole('button', { name: /Continue building the embedding/ }))
    expect(onNavigate).toHaveBeenCalledWith('Knowledge & RAG')
  })

  // copyToClipboard itself (navigator.clipboard + textarea fallback) is
  // now shared via utils/clipboard.js and tested there directly --
  // utils/clipboard.test.js. This file only tests that the result panel
  // wires it up correctly.
  it('the Build RAG result panel wires real copy buttons for each ID', async () => {
    mockDefaults()
    api.createRagSource.mockResolvedValue({ public_id: 'source-1' })
    api.createRagSourceVersion.mockResolvedValue({ public_id: 'version-1' })
    api.validateRagSourceVersion.mockResolvedValue({})
    api.createRagChunkSet.mockResolvedValue({ public_id: 'chunkset-1' })
    api.validateRagChunkSet.mockResolvedValue({})
    const user = userEvent.setup()
    render(<BuildRagStep documentId="doc-1" onComplete={vi.fn()} onNavigate={vi.fn()} toast={toast} />)
    await screen.findByText('Brud Knowledge')
    await user.click(screen.getByRole('button', { name: 'Build RAG' }))
    await screen.findByText('source-1')
    expect(screen.getByRole('button', { name: 'Copy Source ID' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy Version ID' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy Chunk set ID' })).toBeInTheDocument()
  })

  it('warns and truncates the preview for a large document, without truncating the real payload', async () => {
    api.ragSpaces.mockResolvedValue({ items: [{ public_id: 'space-1', name: 'Brud Knowledge' }] })
    const largeText = 'x'.repeat(6_000_000)
    api.documentChunks.mockResolvedValue({ items: [{ status: 'approved', active_revision: { text: largeText } }] })
    api.documentDetail.mockResolvedValue({ original_filename: 'brud.pdf' })
    api.createRagSource.mockResolvedValue({ public_id: 'source-1' })
    api.createRagSourceVersion.mockResolvedValue({ public_id: 'version-1' })
    api.validateRagSourceVersion.mockResolvedValue({})
    api.createRagChunkSet.mockResolvedValue({ public_id: 'chunkset-1' })
    api.validateRagChunkSet.mockResolvedValue({})
    const user = userEvent.setup()
    render(<BuildRagStep documentId="doc-1" onComplete={vi.fn()} onNavigate={vi.fn()} toast={toast} />)
    expect(await screen.findByText(/Preview truncated/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Build RAG' }))
    await waitFor(() => expect(api.createRagSource).toHaveBeenCalledWith('space-1', expect.objectContaining({
      content: largeText,
    })))
  })
})
