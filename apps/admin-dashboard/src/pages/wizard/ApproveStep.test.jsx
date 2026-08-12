import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ApproveStep from './ApproveStep.jsx'

vi.mock('../../services/api.js', () => ({
  bulkApproveDocumentSftCandidates: vi.fn(),
  documentSftCandidateSummary: vi.fn(),
  documentSftCandidates: vi.fn(),
}))

const api = await import('../../services/api.js')
const toast = { success: vi.fn(), error: vi.fn() }

afterEach(() => {
  vi.resetAllMocks()
})

describe('ApproveStep', () => {
  it('shows real counts derived from the fetched candidates', async () => {
    api.documentSftCandidates.mockResolvedValue({
      items: [
        { public_id: 'c1', task: 'qa', quality_status: 'approved', rights_status: 'verified', generation_method: 'template_heuristic_v1' },
        { public_id: 'c2', task: 'qa', quality_status: 'pending_review', rights_status: 'verified', generation_method: 'template_heuristic_v1' },
      ],
    })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 2, approved_count: 1 })
    render(<ApproveStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    const approvedCard = await screen.findByText('Approved')
    expect(approvedCard.closest('article')).toHaveTextContent('1')
  })

  it('bulk-approving selected low-risk candidates calls the real API', async () => {
    api.documentSftCandidates.mockResolvedValue({
      items: [{ public_id: 'c2', task: 'qa', quality_status: 'pending_review', rights_status: 'verified', generation_method: 'template_heuristic_v1' }],
    })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 1, approved_count: 0 })
    api.bulkApproveDocumentSftCandidates.mockResolvedValue({})
    const user = userEvent.setup()
    render(<ApproveStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await user.click(await screen.findByRole('checkbox', { name: 'Select candidate c2' }))
    await user.click(screen.getByRole('button', { name: /Bulk approve 1 selected/ }))
    await waitFor(() => expect(api.bulkApproveDocumentSftCandidates).toHaveBeenCalledWith('doc-1', ['c2']))
  })

  it('Confirm and continue completes the step', async () => {
    api.documentSftCandidates.mockResolvedValue({ items: [] })
    api.documentSftCandidateSummary.mockResolvedValue({ total_candidates: 0, approved_count: 0 })
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<ApproveStep documentId="doc-1" onComplete={onComplete} toast={toast} />)
    await user.click(await screen.findByRole('button', { name: 'Confirm and continue' }))
    expect(onComplete).toHaveBeenCalled()
  })
})
