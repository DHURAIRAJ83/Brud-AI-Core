import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider } from '../components/Toast.jsx'
import AssistantCenterPage from './AssistantCenterPage.jsx'

vi.mock('../services/api.js', () => ({
  lrChat: vi.fn(),
  lrDeleteSession: vi.fn(),
  lrDiagnostics: vi.fn().mockResolvedValue({ local_available: true, external_fallback_enabled: false, active_session_count: 0, total_messages: 0 }),
  lrMessages: vi.fn(),
  lrSessions: vi.fn().mockResolvedValue({ items: [] }),
  miniBrainDefaultRetrievalProfile: vi.fn().mockResolvedValue({ retrieval_profile_public_id: null, name: null }),
  sendMiniBrainGroundedMessage: vi.fn(),
  pcrCandidates: vi.fn().mockResolvedValue({ items: [] }),
  pcrMessages: vi.fn(),
  pcrReviewCandidate: vi.fn(),
  pcrSessions: vi.fn().mockResolvedValue({ items: [] }),
  pcrSignals: vi.fn(),
  assistantActions: vi.fn().mockResolvedValue({ items: [] }),
  assistantLanguagePreference: vi.fn().mockResolvedValue({ language: 'english' }),
  assistantOverview: vi.fn().mockResolvedValue({ guidance: [], summary: {} }),
  assistantProposal: vi.fn(),
  assistantProposals: vi.fn().mockResolvedValue({ items: [] }),
  createAssistantProposal: vi.fn(),
  executeAssistantProposal: vi.fn(),
  reviewAssistantProposal: vi.fn(),
  setAssistantLanguagePreference: vi.fn(),
}))

function renderPage() {
  return render(<ToastProvider><AssistantCenterPage admin={{ display_name: 'Admin' }} /></ToastProvider>)
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('AssistantCenterPage', () => {
  it('defaults to the Admin Tasks tab', async () => {
    renderPage()
    expect(screen.getByRole('button', { name: 'Admin Tasks' })).toHaveAttribute('aria-current', 'page')
  })

  it('switches to Mini Brain Chat and renders the real ChatPanel', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: 'Mini Brain Chat' }))
    expect(await screen.findByLabelText('Message')).toBeInTheDocument()
  })

  it('switches to Public Chat Monitor and shows the real privacy notice', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(screen.getByRole('button', { name: 'Public Chat Monitor' }))
    expect(await screen.findByText(/No raw message text is ever stored/)).toBeInTheDocument()
  })
})
