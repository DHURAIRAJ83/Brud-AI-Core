import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChunkStudioPage from './ChunkStudioPage.jsx'

vi.mock('../services/api.js', () => ({
  approveChunk: vi.fn(), approveStructuredRecord: vi.fn(), archiveChunk: vi.fn(), assignChunkParent: vi.fn(),
  chunkClassificationSuggestions: vi.fn(), chunkCoverageReport: vi.fn(), chunkDetail: vi.fn(),
  chunkDuplicateCheck: vi.fn(), chunkHistory: vi.fn(), chunkQualityCheck: vi.fn(), chunkReviewHistory: vi.fn(),
  classifyChunk: vi.fn(), createManualChunk: vi.fn(), createStructuredRecordFromChunks: vi.fn(),
  createStructuredRecordRagCandidate: vi.fn(), documentChunks: vi.fn(), documents: vi.fn(), editChunkText: vi.fn(),
  excludeChunk: vi.fn(), exportStructuredRecordToDataset: vi.fn(), generateChunks: vi.fn(), mergeChunk: vi.fn(),
  moveChunkBoundary: vi.fn(), rejectChunk: vi.fn(), rejectStructuredRecord: vi.fn(), reopenChunk: vi.fn(),
  reorderChunks: vi.fn(), requestChunkBoundaryCorrection: vi.fn(), requestChunkClassificationCorrection: vi.fn(),
  reviseStructuredRecord: vi.fn(), restoreChunk: vi.fn(), splitChunk: vi.fn(), structuredRecordConflictCheck: vi.fn(),
  structuredRecordDetail: vi.fn(), structuredRecordHistory: vi.fn(), structuredRecords: vi.fn(),
  structuredRecordUsageCheck: vi.fn(), submitChunkForReview: vi.fn(), submitStructuredRecordForReview: vi.fn(),
}))

const api = await import('../services/api.js')

const DOCUMENT = { public_id: 'doc-1', original_filename: 'sample.pdf', page_count: 2, status: 'review_ready' }

const CHUNK_A = {
  public_id: 'chunk-1', chunk_code: 'CHK-00001', chunk_type: 'paragraph', status: 'draft', reading_order: 1,
  active_revision: { text: 'First paragraph here.', page_number: 1 },
}
const CHUNK_B = {
  public_id: 'chunk-2', chunk_code: 'CHK-00002', chunk_type: 'paragraph', status: 'draft', reading_order: 2,
  active_revision: { text: 'Second paragraph here.', page_number: 1 },
}

const RECORD = {
  public_id: 'record-1', candidate_code: 'SR-0001', record_type: 'dictionary_entry', status: 'draft',
  active_revision: { word: 'வணக்கம்' },
}

function mockBaseline() {
  api.documents.mockResolvedValue({ items: [DOCUMENT] })
  api.structuredRecords.mockResolvedValue({ items: [] })
  api.documentChunks.mockResolvedValue({ items: [CHUNK_A, CHUNK_B], total: 2 })
  api.chunkDetail.mockResolvedValue(CHUNK_A)
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('ChunkStudioPage: navigation', () => {
  it('renders all nine required tabs', async () => {
    mockBaseline()
    render(<ChunkStudioPage />)
    for (const tab of [
      'Overview', 'Documents', 'Chunk Editor', 'Structure', 'Record Builder',
      'Review Queue', 'Conflicts', 'Approved', 'History',
    ]) {
      expect(screen.getByRole('button', { name: tab })).toBeInTheDocument()
    }
  })

  it('overview shows real document and chunk-status counts, including zero states', async () => {
    mockBaseline()
    render(<ChunkStudioPage />)
    await waitFor(() => expect(screen.getByText('Total documents').nextSibling).toHaveTextContent('1'))
    expect(screen.getAllByText('draft')[0].nextSibling).toHaveTextContent('0')
  })
})

describe('ChunkStudioPage: document selection and generation', () => {
  it('selecting a document loads its chunks', async () => {
    mockBaseline()
    const user = userEvent.setup()
    render(<ChunkStudioPage />)
    await user.click(screen.getByRole('button', { name: 'Documents' }))
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => expect(api.documentChunks).toHaveBeenCalledWith('doc-1'))
  })

  it('clicking generate calls generateChunks for the selected document', async () => {
    mockBaseline()
    api.generateChunks.mockResolvedValue({ generated_chunk_count: 2, chunk_public_ids: ['chunk-1', 'chunk-2'] })
    const user = userEvent.setup()
    render(<ChunkStudioPage />)
    await user.click(screen.getByRole('button', { name: 'Documents' }))
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => screen.getByText(/Generate draft chunks/))
    await user.click(screen.getByText(/Generate draft chunks/))
    await waitFor(() => expect(api.generateChunks).toHaveBeenCalledWith('doc-1'))
  })
})

describe('ChunkStudioPage: chunk editor', () => {
  async function selectDocumentAndOpenEditor(user) {
    render(<ChunkStudioPage />)
    await user.click(screen.getByRole('button', { name: 'Documents' }))
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => expect(api.documentChunks).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: 'Chunk Editor' }))
  }

  it('opening a chunk shows its text for editing', async () => {
    mockBaseline()
    const user = userEvent.setup()
    await selectDocumentAndOpenEditor(user)
    await waitFor(() => screen.getAllByText(/First paragraph here/).length > 0)
    await user.click(screen.getAllByText('Open')[0])
    await waitFor(() => expect(screen.getByDisplayValue('First paragraph here.')).toBeInTheDocument())
  })

  it('approve calls approveChunk with the open chunk id', async () => {
    mockBaseline()
    api.approveChunk.mockResolvedValue({})
    const user = userEvent.setup()
    await selectDocumentAndOpenEditor(user)
    await user.click(screen.getAllByText('Open')[0])
    await waitFor(() => screen.getByText('Approve'))
    await user.click(screen.getByText('Approve'))
    await waitFor(() => expect(api.approveChunk).toHaveBeenCalledWith('chunk-1'))
  })

  it('classify calls classifyChunk with the selected type', async () => {
    mockBaseline()
    api.classifyChunk.mockResolvedValue({})
    const user = userEvent.setup()
    await selectDocumentAndOpenEditor(user)
    await user.click(screen.getAllByText('Open')[0])
    await waitFor(() => screen.getByText('Classification'))
    const select = screen.getAllByRole('combobox')[0]
    await user.selectOptions(select, 'heading')
    await waitFor(() => expect(api.classifyChunk).toHaveBeenCalledWith('chunk-1', 'heading'))
  })

  it('split calls splitChunk with the numeric offset', async () => {
    mockBaseline()
    api.splitChunk.mockResolvedValue({ chunks: [] })
    const user = userEvent.setup()
    await selectDocumentAndOpenEditor(user)
    await user.click(screen.getAllByText('Open')[0])
    await waitFor(() => screen.getByText('Split at offset'))
    await user.type(screen.getByLabelText('Split at offset'), '5')
    await user.click(screen.getByRole('button', { name: 'Split' }))
    await waitFor(() => expect(api.splitChunk).toHaveBeenCalledWith('chunk-1', 5))
  })
})

describe('ChunkStudioPage: review queue', () => {
  it('shows chunks needing review with approve/reject actions', async () => {
    mockBaseline()
    api.documentChunks.mockResolvedValue({
      items: [{ ...CHUNK_A, status: 'needs_review' }, CHUNK_B], total: 2,
    })
    api.approveChunk.mockResolvedValue({})
    const user = userEvent.setup()
    render(<ChunkStudioPage />)
    await user.click(screen.getByRole('button', { name: 'Documents' }))
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => expect(api.documentChunks).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: 'Review Queue' }))
    await waitFor(() => screen.getByText('First paragraph here.'))
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.approveChunk).toHaveBeenCalledWith('chunk-1'))
  })
})

describe('ChunkStudioPage: record builder', () => {
  it('creating a structured record calls createStructuredRecordFromChunks with selected chunks and fields', async () => {
    mockBaseline()
    api.createStructuredRecordFromChunks.mockResolvedValue(RECORD)
    const user = userEvent.setup()
    render(<ChunkStudioPage />)
    await user.click(screen.getByRole('button', { name: 'Documents' }))
    await waitFor(() => screen.getByText('sample.pdf'))
    await user.click(screen.getByText('sample.pdf'))
    await waitFor(() => expect(api.documentChunks).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: 'Record Builder' }))
    await waitFor(() => screen.getByText(/First paragraph here/))
    await user.click(screen.getByLabelText(/First paragraph here/))
    await user.click(screen.getByRole('button', { name: /Create structured record candidate/ }))
    await waitFor(() => expect(api.createStructuredRecordFromChunks).toHaveBeenCalled())
    const call = api.createStructuredRecordFromChunks.mock.calls[0][0]
    expect(call.chunk_public_ids).toContain('chunk-1')
    expect(call.record_type).toBe('plain_text')
  })
})

describe('ChunkStudioPage: approved and export', () => {
  it('export-dataset calls exportStructuredRecordToDataset for an approved record', async () => {
    mockBaseline()
    api.structuredRecords.mockResolvedValue({ items: [{ ...RECORD, status: 'approved' }] })
    api.exportStructuredRecordToDataset.mockResolvedValue({ ...RECORD, exported_dataset_record_public_id: 'ds-1' })
    const user = userEvent.setup()
    render(<ChunkStudioPage />)
    await user.click(screen.getByRole('button', { name: 'Approved' }))
    await waitFor(() => screen.getByText('SR-0001'))
    await user.click(screen.getByText('Export to Existing Dataset Record'))
    await waitFor(() => expect(api.exportStructuredRecordToDataset).toHaveBeenCalledWith('record-1'))
  })
})
