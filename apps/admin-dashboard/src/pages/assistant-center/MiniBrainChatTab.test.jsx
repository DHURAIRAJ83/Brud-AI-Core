import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider } from '../../components/Toast.jsx'
import MiniBrainChatTab from './MiniBrainChatTab.jsx'

vi.mock('../../services/api.js', () => ({
  lrChat: vi.fn(),
  lrDeleteSession: vi.fn(),
  lrDiagnostics: vi.fn(),
  lrMessages: vi.fn(),
  lrSessions: vi.fn(),
  miniBrainDefaultRetrievalProfile: vi.fn(),
  sendMiniBrainGroundedMessage: vi.fn(),
}))

const api = await import('../../services/api.js')

const DIAGNOSTICS_RESPONSE = { local_available: true, external_fallback_enabled: false, active_session_count: 2, total_messages: 10 }
const DEFAULT_PROFILE_RESPONSE = { retrieval_profile_public_id: 'profile-1', name: 'Default profile' }

function mockDefaults() {
  api.lrSessions.mockResolvedValue({ items: [] })
  api.lrDiagnostics.mockResolvedValue(DIAGNOSTICS_RESPONSE)
  api.miniBrainDefaultRetrievalProfile.mockResolvedValue(DEFAULT_PROFILE_RESPONSE)
}

function renderTab(admin) {
  return render(<ToastProvider><MiniBrainChatTab admin={admin} /></ToastProvider>)
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('MiniBrainChatTab', () => {
  it('renders the real ChatPanel and real runtime diagnostics', async () => {
    mockDefaults()
    renderTab()
    expect(await screen.findByLabelText('Message')).toBeInTheDocument()
    expect(await screen.findByText('available')).toBeInTheDocument()
    expect(screen.getByText('Local runtime').closest('article')).toHaveTextContent('available')
    expect(screen.getByText('Active sessions').closest('article')).toHaveTextContent('2')
  })

  it('shows the real active retrieval profile name', async () => {
    mockDefaults()
    renderTab()
    expect(await screen.findByText('Default profile')).toBeInTheDocument()
  })

  it('shows an honest "none set" message when there is no default profile', async () => {
    mockDefaults()
    api.miniBrainDefaultRetrievalProfile.mockResolvedValue({ retrieval_profile_public_id: null, name: null })
    renderTab()
    expect(await screen.findByText(/None set/)).toBeInTheDocument()
  })

  it('shows a retry banner on failure and recovers', async () => {
    mockDefaults()
    api.lrDiagnostics.mockRejectedValueOnce(new Error('Network error.'))
    const user = userEvent.setup()
    renderTab()
    expect(await screen.findByText('Network error.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('available')).toBeInTheDocument()
  })
})
