import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CleanStep from './CleanStep.jsx'

vi.mock('../../services/api.js', () => ({
  detectDocumentRepeatedElements: vi.fn(),
  documentRepeatedElements: vi.fn(),
  reviewDocumentRepeatedElement: vi.fn(),
}))

const api = await import('../../services/api.js')
const toast = { success: vi.fn(), error: vi.fn() }

afterEach(() => {
  vi.resetAllMocks()
})

describe('CleanStep', () => {
  it('detecting with zero results shows an honest empty state and completes the step', async () => {
    api.detectDocumentRepeatedElements.mockResolvedValue({})
    api.documentRepeatedElements.mockResolvedValue({ items: [] })
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<CleanStep documentId="doc-1" onComplete={onComplete} toast={toast} />)
    await user.click(screen.getByRole('button', { name: 'Detect repeated elements' }))
    await waitFor(() => expect(screen.getByText('No repeated-element suggestions found.')).toBeInTheDocument())
    expect(onComplete).toHaveBeenCalledWith({ toastMessage: 'Cleanup pass recorded.' })
  })

  it('shows detected elements and reviews one via the real API', async () => {
    api.detectDocumentRepeatedElements.mockResolvedValue({})
    api.documentRepeatedElements.mockResolvedValueOnce({
      items: [{ public_id: 'el-1', element_type: 'header', status: 'suggested', confidence: 0.9, page_occurrences: [1, 2], normalized_text: 'Brud AI' }],
    })
    api.reviewDocumentRepeatedElement.mockResolvedValue({})
    api.documentRepeatedElements.mockResolvedValueOnce({ items: [] })
    const user = userEvent.setup()
    render(<CleanStep documentId="doc-1" onComplete={vi.fn()} toast={toast} />)
    await user.click(screen.getByRole('button', { name: 'Detect repeated elements' }))
    expect(await screen.findByText('header')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Accept removal' }))
    await waitFor(() => expect(api.reviewDocumentRepeatedElement).toHaveBeenCalledWith('doc-1', 'el-1', 'accept', {}))
  })
})
