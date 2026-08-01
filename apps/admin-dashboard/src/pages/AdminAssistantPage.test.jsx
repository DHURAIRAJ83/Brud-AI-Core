import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AdminAssistantPage from './AdminAssistantPage.jsx'

vi.mock('../services/api.js', () => ({
  assistantActions: vi.fn(),
  assistantOverview: vi.fn(),
  assistantProposal: vi.fn(),
  assistantProposals: vi.fn(),
  createAssistantProposal: vi.fn(),
  executeAssistantProposal: vi.fn(),
  reviewAssistantProposal: vi.fn(),
  assistantLanguagePreference: vi.fn(),
  setAssistantLanguagePreference: vi.fn(),
}))

const api = await import('../services/api.js')

const OVERVIEW_RESPONSE = {
  summary: { dataset_records: { pending_review: 2 }, admin_approvals: { pending: 1 } },
  guidance: ['2 dataset record(s) are pending_review.', '1 Admin Assistant proposal(s) pending.'],
  localized_guidance: ['2 dataset record(s) pending_review நிலையில் உள்ளன.'],
  resolved_language: 'tamil',
}

function mockDefaults() {
  api.assistantOverview.mockResolvedValue(OVERVIEW_RESPONSE)
  api.assistantActions.mockResolvedValue({ action_types: ['dataset_record_review'] })
  api.assistantLanguagePreference.mockResolvedValue({ response_language: 'auto', updated_at: null })
  api.setAssistantLanguagePreference.mockResolvedValue({ response_language: 'tamil', updated_at: '2026-01-01' })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('AdminAssistantPage', () => {
  it('shows the governance notice and loads the saved language preference', async () => {
    mockDefaults()
    render(<AdminAssistantPage />)
    expect(await screen.findByText(/never mutates anything on its own/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('Reply language')).toHaveValue('auto'))
  })

  it('renders localized guidance when available, not the raw English list', async () => {
    mockDefaults()
    render(<AdminAssistantPage />)
    expect(await screen.findByText('2 dataset record(s) pending_review நிலையில் உள்ளன.')).toBeInTheDocument()
    expect(screen.queryByText('2 dataset record(s) are pending_review.')).not.toBeInTheDocument()
  })

  it('falls back to the raw guidance list when localized_guidance is absent', async () => {
    mockDefaults()
    api.assistantOverview.mockResolvedValue({
      summary: {}, guidance: ['Nothing is pending right now.'],
    })
    render(<AdminAssistantPage />)
    expect(await screen.findByText('Nothing is pending right now.')).toBeInTheDocument()
  })

  it('saves a new language preference and reloads the overview', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<AdminAssistantPage />)
    const select = await screen.findByLabelText('Reply language')
    await waitFor(() => expect(select).toHaveValue('auto'))
    await user.selectOptions(select, 'tanglish')
    await waitFor(() => expect(api.setAssistantLanguagePreference).toHaveBeenCalledWith('tanglish'))
    expect(select).toHaveValue('tanglish')
    await waitFor(() => expect(api.assistantOverview).toHaveBeenCalledTimes(2))
  })

  it('rolls back the selector and shows an error when saving fails', async () => {
    mockDefaults()
    api.setAssistantLanguagePreference.mockRejectedValue(new Error('Save failed.'))
    const user = userEvent.setup()
    render(<AdminAssistantPage />)
    const select = await screen.findByLabelText('Reply language')
    await waitFor(() => expect(select).toHaveValue('auto'))
    await user.selectOptions(select, 'english')
    expect(await screen.findByText('Save failed.')).toBeInTheDocument()
    await waitFor(() => expect(select).toHaveValue('auto'))
  })
})
