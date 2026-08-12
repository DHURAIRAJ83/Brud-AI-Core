import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PilotOperationsPage from './PilotOperationsPage.jsx'

vi.mock('../services/api.js', () => ({
  getSystemStatus: vi.fn(),
  miniBrainDefaultRetrievalProfile: vi.fn(),
  miniBrainWidgetHealth: vi.fn(),
  ragRetrievalProfiles: vi.fn(),
  ragSpaces: vi.fn(),
  systemRecentAudit: vi.fn(),
}))

const api = await import('../services/api.js')

const HEALTH_RESPONSE = { loaded: true, backend_type: 'local', current_model: 'test-model.gguf', available: true, error_message: null }
const DEFAULT_PROFILE_RESPONSE = { retrieval_profile_public_id: 'profile-1', name: 'Default profile' }
const SPACES_RESPONSE = { items: [{ public_id: 'space-1' }, { public_id: 'space-2' }] }
const PROFILES_RESPONSE = { items: [{ public_id: 'profile-1', status: 'active' }, { public_id: 'profile-2', status: 'validated' }] }
const AUDIT_RESPONSE = { items: [{ public_id: 'evt-1', event_type: 'rag_retrieval_profile_activated', outcome: 'success', created_at: '2026-01-01T00:00:00Z' }] }
const SYSTEM_RESPONSE = { database: { schema_version: 70 }, configuration: {}, schema: {}, audit: { items: [] } }

function mockDefaults() {
  api.miniBrainWidgetHealth.mockResolvedValue(HEALTH_RESPONSE)
  api.miniBrainDefaultRetrievalProfile.mockResolvedValue(DEFAULT_PROFILE_RESPONSE)
  api.ragSpaces.mockResolvedValue(SPACES_RESPONSE)
  api.ragRetrievalProfiles.mockResolvedValue(PROFILES_RESPONSE)
  api.systemRecentAudit.mockResolvedValue(AUDIT_RESPONSE)
  api.getSystemStatus.mockResolvedValue(SYSTEM_RESPONSE)
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('PilotOperationsPage', () => {
  it('shows a loading state, then renders real runtime/grounded-chat/audit data', async () => {
    mockDefaults()
    render(<PilotOperationsPage />)
    expect(screen.getByText(/Loading pilot operations status/)).toBeInTheDocument()

    expect(await screen.findByText('local')).toBeInTheDocument()
    expect(screen.getByText('test-model.gguf')).toBeInTheDocument()
    expect(screen.getByText('available')).toBeInTheDocument()
    expect(screen.getByText('70')).toBeInTheDocument()
    expect(screen.getByText('Default profile')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument() // knowledge space count
    expect(screen.getByText('1')).toBeInTheDocument() // active profile count (only 1 of 2 is active)
    expect(screen.getByText(/rag retrieval profile activated/)).toBeInTheDocument()
  })

  it('counts only active profiles, ignoring draft/validated ones', async () => {
    mockDefaults()
    api.ragRetrievalProfiles.mockResolvedValue({
      items: [
        { public_id: 'p1', status: 'active' },
        { public_id: 'p2', status: 'active' },
        { public_id: 'p3', status: 'draft' },
      ],
    })
    render(<PilotOperationsPage />)
    const card = await screen.findByText('Active retrieval profiles')
    expect(card.closest('article')).toHaveTextContent('2')
  })

  it('shows an empty-state message when there are no audit events', async () => {
    mockDefaults()
    api.systemRecentAudit.mockResolvedValue({ items: [] })
    render(<PilotOperationsPage />)
    expect(await screen.findByText('No audit events have been recorded yet.')).toBeInTheDocument()
  })

  it('shows a retry button on failure and recovers on click', async () => {
    mockDefaults()
    api.miniBrainWidgetHealth.mockRejectedValueOnce(new Error('Network error.'))
    const user = userEvent.setup()
    render(<PilotOperationsPage />)
    expect(await screen.findByText('Network error.')).toBeInTheDocument()
    const retry = screen.getByRole('button', { name: 'Retry' })
    await user.click(retry)
    await waitFor(() => expect(screen.getByText('local')).toBeInTheDocument())
  })

  it('shows "none set" when there is no active default retrieval profile', async () => {
    mockDefaults()
    api.miniBrainDefaultRetrievalProfile.mockResolvedValue({ retrieval_profile_public_id: null, name: null })
    render(<PilotOperationsPage />)
    expect(await screen.findByText('none set')).toBeInTheDocument()
  })
})
