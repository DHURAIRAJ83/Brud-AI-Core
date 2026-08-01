import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AdminAssistantWidget from './AdminAssistantWidget.jsx'

vi.mock('../../services/api.js', () => ({
  assistantPages: vi.fn(),
  assistantHealth: vi.fn(),
  sendAssistantChatMessage: vi.fn(),
  submitAssistantFeedback: vi.fn(),
  assistantLanguagePreference: vi.fn(),
  setAssistantLanguagePreference: vi.fn(),
}))

const api = await import('../../services/api.js')

const PAGES_RESPONSE = {
  registry_version: 'v1',
  items: [
    { page_id: 'datasets', nav_key: 'Datasets', implemented: true, mode: 'data', title: { en: 'Datasets', ta: 'Datasets' }, purpose: { en: 'Manage datasets.', ta: '' }, tabs: [], related_page_ids: [], safety_note: {} },
    { page_id: 'overview', nav_key: 'Overview', implemented: true, mode: 'guide', title: { en: 'Overview', ta: '' }, purpose: { en: 'Landing page.', ta: '' }, tabs: [], related_page_ids: [], safety_note: {} },
  ],
}

function mockDefaults() {
  api.assistantPages.mockResolvedValue(PAGES_RESPONSE)
  api.assistantHealth.mockResolvedValue({ llm_available: false, scope_key: 'admin_diagnostic', assignment_public_id: null })
  api.sendAssistantChatMessage.mockResolvedValue({
    answer: 'Datasets: Manage datasets.',
    intent: 'help',
    language_category: 'en',
    resolved_language: 'english',
    language_source: 'default',
    status: 'completed',
    navigation_target: null,
    conversation_session_public_id: null,
    registry_version: 'v1',
  })
  api.submitAssistantFeedback.mockResolvedValue({ public_id: 'fb-1', rating: 'helpful' })
  api.assistantLanguagePreference.mockResolvedValue({ response_language: 'auto', updated_at: null })
  api.setAssistantLanguagePreference.mockResolvedValue({ response_language: 'tamil', updated_at: '2026-01-01' })
}

afterEach(() => {
  vi.resetAllMocks()
})

describe('AdminAssistantWidget', () => {
  it('renders only the launcher until opened', () => {
    mockDefaults()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={{ display_name: 'Test Admin' }} />)
    expect(screen.getByRole('button', { name: 'Open Admin Assistant' })).toBeInTheDocument()
    expect(screen.queryByText('Brud AI Assistant')).not.toBeInTheDocument()
  })

  it('opens the card, loads pages/health, and shows suggestions', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={{ display_name: 'Test Admin' }} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    expect(screen.getByText('Brud AI Assistant')).toBeInTheDocument()
    await waitFor(() => expect(api.assistantPages).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByRole('button', { name: 'How do I use this page?' })).toBeEnabled())
    expect(screen.getByText(/AI response generation is unavailable/)).toBeInTheDocument()
  })

  it('does not allow sending before the page registry has loaded', async () => {
    mockDefaults()
    let resolvePages
    api.assistantPages.mockReturnValue(new Promise((resolve) => { resolvePages = resolve }))
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    expect(screen.getByText('Loading dashboard context…')).toBeInTheDocument()
    expect(screen.getByLabelText('Message to the Admin Assistant')).toBeDisabled()
    resolvePages(PAGES_RESPONSE)
    await waitFor(() => expect(screen.getByLabelText('Message to the Admin Assistant')).toBeEnabled())
  })

  it('sends the resolved page_id for the current page, not a stale default', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'How do I use this page?' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'How do I use this page?' }))
    await waitFor(() => expect(api.sendAssistantChatMessage).toHaveBeenCalledWith(
      expect.objectContaining({ page_id: 'datasets', message: 'How do I use this page?' })
    ))
    expect(await screen.findByText('Datasets: Manage datasets.')).toBeInTheDocument()
  })

  it('renders a navigation button and calls onNavigate when clicked', async () => {
    mockDefaults()
    api.sendAssistantChatMessage.mockResolvedValue({
      answer: 'Use the button below to go to Builds & Pipelines.',
      intent: 'navigation',
      language_category: 'en',
      status: 'completed',
      navigation_target: { page_id: 'builds_pipelines', nav_key: 'Builds & Pipelines' },
      conversation_session_public_id: null,
      registry_version: 'v1',
    })
    const onNavigate = vi.fn()
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={onNavigate} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await waitFor(() => expect(screen.getByLabelText('Message to the Admin Assistant')).toBeEnabled())
    await user.type(screen.getByLabelText('Message to the Admin Assistant'), 'take me to Builds & Pipelines')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    const navButton = await screen.findByRole('button', { name: 'Go to Builds & Pipelines' })
    await user.click(navButton)
    expect(onNavigate).toHaveBeenCalledWith('Builds & Pipelines')
  })

  it('records feedback and shows a thank-you without blocking the chat', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'How do I use this page?' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'How do I use this page?' }))
    await screen.findByText('Datasets: Manage datasets.')
    await user.click(screen.getByRole('button', { name: 'Mark helpful' }))
    await waitFor(() => expect(api.submitAssistantFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ rating: 'helpful', page_id: 'datasets' })
    ))
    expect(await screen.findByText('Thanks for the feedback.')).toBeInTheDocument()
  })

  it('minimizes, restores, and closes back to the launcher', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await user.click(screen.getByRole('button', { name: 'Minimize Admin Assistant' }))
    expect(screen.queryByPlaceholderText('Type a question…')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Restore Admin Assistant' }))
    await waitFor(() => expect(screen.getByLabelText('Message to the Admin Assistant')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Close Admin Assistant' }))
    expect(screen.getByRole('button', { name: 'Open Admin Assistant' })).toBeInTheDocument()
    expect(screen.queryByText('Brud AI Assistant')).not.toBeInTheDocument()
  })

  it('closes on Escape and returns focus to the launcher', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    expect(screen.getByText('Brud AI Assistant')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByText('Brud AI Assistant')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Open Admin Assistant' })).toHaveFocus()
  })

  it('shows a generic error notice without a stack trace when the chat call fails', async () => {
    mockDefaults()
    api.sendAssistantChatMessage.mockRejectedValue(new Error('Request failed.'))
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'How do I use this page?' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'How do I use this page?' }))
    expect(await screen.findByText('Request failed.')).toBeInTheDocument()
  })

  it('loads the saved language preference and shows it in the selector', async () => {
    mockDefaults()
    api.assistantLanguagePreference.mockResolvedValue({ response_language: 'tanglish', updated_at: null })
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await waitFor(() => expect(api.assistantLanguagePreference).toHaveBeenCalled())
    expect(await screen.findByLabelText('Reply language')).toHaveValue('tanglish')
  })

  it('saves a new language preference when changed', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    const select = await screen.findByLabelText('Reply language')
    await waitFor(() => expect(select).toHaveValue('auto'))
    await user.selectOptions(select, 'tamil')
    await waitFor(() => expect(api.setAssistantLanguagePreference).toHaveBeenCalledWith('tamil'))
    expect(select).toHaveValue('tamil')
  })

  it('rolls back the selector and shows an error when saving the language fails', async () => {
    mockDefaults()
    api.setAssistantLanguagePreference.mockRejectedValue(new Error('Could not save.'))
    const user = userEvent.setup()
    render(<AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} admin={null} />)
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    const select = await screen.findByLabelText('Reply language')
    await waitFor(() => expect(select).toHaveValue('auto'))
    await user.selectOptions(select, 'english')
    expect(await screen.findByText('Could not save.')).toBeInTheDocument()
    await waitFor(() => expect(select).toHaveValue('auto'))
  })
})
