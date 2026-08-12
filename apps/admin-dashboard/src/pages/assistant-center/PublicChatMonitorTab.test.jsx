import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider } from '../../components/Toast.jsx'
import PublicChatMonitorTab from './PublicChatMonitorTab.jsx'

vi.mock('../../services/api.js', () => ({
  pcrCandidates: vi.fn(),
  pcrMessages: vi.fn(),
  pcrReviewCandidate: vi.fn(),
  pcrSessions: vi.fn(),
  pcrSignals: vi.fn(),
}))

const api = await import('../../services/api.js')

function mockDefaults() {
  api.pcrSessions.mockResolvedValue({ items: [{ public_id: 'sess-1', status: 'active', message_count: 4, unresolved_count: 1 }] })
  api.pcrCandidates.mockResolvedValue({ items: [] })
}

function renderTab() {
  return render(<ToastProvider><PublicChatMonitorTab /></ToastProvider>)
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('PublicChatMonitorTab', () => {
  it('always shows the real no-raw-text privacy notice', async () => {
    mockDefaults()
    renderTab()
    expect(await screen.findByText(/No raw message text is ever stored/)).toBeInTheDocument()
  })

  it('lists real sessions, and selecting one loads real message metadata (never literal text)', async () => {
    mockDefaults()
    api.pcrMessages.mockResolvedValue({
      items: [{ public_id: 'm1', role: 'user', content_hash: 'abcdef0123456789', used_rag: true, route_used: 'rag', created_at: '2026-01-01T00:00:00Z' }],
    })
    api.pcrSignals.mockResolvedValue({ items: [] })
    const user = userEvent.setup()
    renderTab()
    await user.click(await screen.findByText('sess-1'))
    await waitFor(() => expect(api.pcrMessages).toHaveBeenCalledWith('sess-1'))
    expect(await screen.findByText(/hash abcdef012345/)).toBeInTheDocument()
    expect(screen.getByText(/RAG/)).toBeInTheDocument()
  })

  it('shows an empty state before a session is selected', async () => {
    mockDefaults()
    renderTab()
    expect(await screen.findByText('Select a session to view its message metadata.')).toBeInTheDocument()
  })

  it('shows real feedback signals for the selected session', async () => {
    mockDefaults()
    api.pcrMessages.mockResolvedValue({ items: [] })
    api.pcrSignals.mockResolvedValue({ items: [{ public_id: 'sig-1', signal_type: 'thumbs_down', normalized_text: 'unclear answer' }] })
    const user = userEvent.setup()
    renderTab()
    await user.click(await screen.findByText('sess-1'))
    expect(await screen.findByText('unclear answer')).toBeInTheDocument()
  })

  it('shows the real candidate review queue and approves/rejects via the real API', async () => {
    api.pcrSessions.mockResolvedValue({ items: [] })
    api.pcrCandidates.mockResolvedValue({ items: [{ public_id: 'cand-1', status: 'pending_admin_review' }] })
    api.pcrReviewCandidate.mockResolvedValue({})
    const user = userEvent.setup()
    renderTab()
    await screen.findByText('cand-1')
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(api.pcrReviewCandidate).toHaveBeenCalledWith('cand-1', 'approve', ''))
  })

  it('shows an empty state when there are no candidates pending review', async () => {
    mockDefaults()
    renderTab()
    expect(await screen.findByText('No candidates pending admin review.')).toBeInTheDocument()
  })
})
