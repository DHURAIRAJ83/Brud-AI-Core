import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AiReviewStudioStep from './AiReviewStudioStep.jsx'

vi.mock('../../services/api.js', () => ({
  documentSftCandidateSummary: vi.fn(),
  documentSftCandidates: vi.fn(),
  generateDocumentSftCandidates: vi.fn(),
  reviewDocumentSftCandidate: vi.fn(),
}))

const api = await import('../../services/api.js')
const toast = { success: vi.fn(), error: vi.fn() }

const CANDIDATE = {
  public_id: 'cand-1', task: 'question_answering', instruction: 'What is Brud AI?',
  context: '', response: 'Brud AI is a Tamil-first assistant.',
  source_page_start: 1, source_page_end: 1,
  quality_status: 'pending_review', rights_status: 'verified', generation_method: 'template_heuristic_v1',
}

afterEach(() => {
  vi.resetAllMocks()
})

function mockDefaults(items = []) {
  api.documentSftCandidates.mockResolvedValue({ items })
  api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: items.length, approved_count: 0 })
}

describe('AiReviewStudioStep', () => {
  it('shows an honest empty state before candidates exist', async () => {
    mockDefaults([])
    render(<AiReviewStudioStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    expect(await screen.findByText(/No SFT candidates yet/)).toBeInTheDocument()
  })

  it('generating candidates calls the real API and reloads', async () => {
    mockDefaults([])
    api.generateDocumentSftCandidates.mockResolvedValue({})
    const user = userEvent.setup()
    render(<AiReviewStudioStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await screen.findByText(/No SFT candidates yet/)
    await user.click(screen.getByRole('button', { name: 'Generate SFT candidates' }))
    await waitFor(() => expect(api.generateDocumentSftCandidates).toHaveBeenCalledWith('doc-1', {}))
  })

  it('selecting a candidate shows the raw output and seeds the editable form', async () => {
    mockDefaults([CANDIDATE])
    const user = userEvent.setup()
    render(<AiReviewStudioStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await user.click(await screen.findByRole('button', { name: 'Review' }))
    expect(screen.getByDisplayValue('What is Brud AI?')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Brud AI is a Tamil-first assistant.')).toBeInTheDocument()
  })

  it('editing a field shows the unsaved-edits note and highlights a real diff', async () => {
    mockDefaults([CANDIDATE])
    const user = userEvent.setup()
    render(<AiReviewStudioStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await user.click(await screen.findByRole('button', { name: 'Review' }))
    const responseField = screen.getByDisplayValue('Brud AI is a Tamil-first assistant.')
    await user.clear(responseField)
    await user.type(responseField, 'Brud AI is a Tamil-and-English assistant.')
    expect(screen.getByText('Unsaved edits')).toBeInTheDocument()
    expect(document.querySelector('.wizard-diff-added')).toBeTruthy()
  })

  it('approve is disabled until rights are verified', async () => {
    mockDefaults([{ ...CANDIDATE, rights_status: 'unverified' }])
    const user = userEvent.setup()
    render(<AiReviewStudioStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await user.click(await screen.findByRole('button', { name: 'Review' }))
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled()
    expect(screen.getByText(/Rights not verified/)).toBeInTheDocument()
  })

  it('approving a candidate calls reviewDocumentSftCandidate and completes the step', async () => {
    mockDefaults([CANDIDATE])
    api.reviewDocumentSftCandidate.mockResolvedValue({})
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<AiReviewStudioStep documentId="doc-1" onComplete={onComplete} toast={toast} />)
    await user.click(await screen.findByRole('button', { name: 'Review' }))
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.reviewDocumentSftCandidate).toHaveBeenCalledWith(
      'doc-1', 'cand-1', expect.objectContaining({ action: 'approve' }),
    ))
    expect(onComplete).toHaveBeenCalledWith({ toastMessage: 'Candidate approved.' })
  })

  it('Save Edits sends the edited fields via action "edit" without completing the step', async () => {
    mockDefaults([CANDIDATE])
    api.reviewDocumentSftCandidate.mockResolvedValue({})
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<AiReviewStudioStep documentId="doc-1" onComplete={onComplete} toast={toast} />)
    await user.click(await screen.findByRole('button', { name: 'Review' }))
    const responseField = screen.getByDisplayValue('Brud AI is a Tamil-first assistant.')
    await user.clear(responseField)
    await user.type(responseField, 'Edited response.')
    await user.click(screen.getByRole('button', { name: 'Save Edits' }))
    await waitFor(() => expect(api.reviewDocumentSftCandidate).toHaveBeenCalledWith(
      'doc-1', 'cand-1', expect.objectContaining({ action: 'edit', edited_response: 'Edited response.' }),
    ))
    expect(onComplete).not.toHaveBeenCalled()
  })
})
