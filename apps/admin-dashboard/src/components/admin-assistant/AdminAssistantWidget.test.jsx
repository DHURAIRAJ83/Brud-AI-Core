import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ToastProvider } from '../Toast.jsx'
import AdminAssistantWidget from './AdminAssistantWidget.jsx'

const LAYOUT_STORAGE_KEY = 'brud-admin-assistant-widget-layout-v1'

// Phase 3: the widget's chat area is now the shared ChatPanel component, so
// it goes through the exact same lrChat/lrSessions/lrMessages/lrDeleteSession
// + sendMiniBrainGroundedMessage/miniBrainDefaultRetrievalProfile calls
// already proven by ChatPanel.test.jsx and MiniBrainChatTab.test.jsx --
// only page help, feedback, health, and language preference remain
// widget-specific (Phase-8 + MB-45 health).
vi.mock('../../services/api.js', () => ({
  assistantPages: vi.fn(),
  miniBrainWidgetHealth: vi.fn(),
  miniBrainDefaultRetrievalProfile: vi.fn(),
  lrChat: vi.fn(),
  lrSessions: vi.fn(),
  lrMessages: vi.fn(),
  lrDeleteSession: vi.fn(),
  sendMiniBrainGroundedMessage: vi.fn(),
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

function chatReply(text) {
  return {
    session: { public_id: 'sess-1', admin_public_id: 'admin-1', stage: 'reply_received', status: 'active', backend_type: 'local', total_messages: 2, created_at: '2026-01-01', updated_at: '2026-01-01' },
    reply: { public_id: 'msg-1', session_id: 'sess-1', role: 'assistant', capability: 'chat', sanitized_text: text, backend_type: 'local', truncated: false, created_at: '2026-01-01' },
    backend_type: 'local',
    error_message: null,
  }
}

function mockDefaults() {
  api.assistantPages.mockResolvedValue(PAGES_RESPONSE)
  api.miniBrainWidgetHealth.mockResolvedValue({ loaded: false, backend_type: 'unavailable', current_model: null, available: false, error_message: 'no local model configured and no external provider is enabled' })
  api.miniBrainDefaultRetrievalProfile.mockResolvedValue({ retrieval_profile_public_id: null, name: null })
  api.lrSessions.mockResolvedValue({ items: [] })
  api.lrChat.mockResolvedValue(chatReply('Datasets: Manage datasets.'))
  api.sendMiniBrainGroundedMessage.mockResolvedValue({ ...chatReply('Grounded answer.'), citations: [] })
  api.submitAssistantFeedback.mockResolvedValue({ public_id: 'fb-1', rating: 'helpful' })
  api.assistantLanguagePreference.mockResolvedValue({ response_language: 'auto', updated_at: null })
  api.setAssistantLanguagePreference.mockResolvedValue({ response_language: 'tamil', updated_at: '2026-01-01' })
}

function renderWidget(props) {
  return render(<ToastProvider><AdminAssistantWidget active="Datasets" onNavigate={vi.fn()} {...props} /></ToastProvider>)
}

beforeEach(() => {
  localStorage.removeItem(LAYOUT_STORAGE_KEY)
})

afterEach(() => {
  vi.resetAllMocks()
  localStorage.removeItem(LAYOUT_STORAGE_KEY)
})

describe('AdminAssistantWidget', () => {
  it('renders only the launcher until opened', () => {
    mockDefaults()
    renderWidget({ admin: { display_name: 'Test Admin' } })
    expect(screen.getByRole('button', { name: 'Open Admin Assistant' })).toBeInTheDocument()
    expect(screen.queryByText('Brud AI Assistant')).not.toBeInTheDocument()
  })

  it('opens the card, loads pages/health, and shows suggestions', async () => {
    mockDefaults()
    const user = userEvent.setup()
    renderWidget({ admin: { display_name: 'Test Admin' } })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    expect(screen.getByText('Brud AI Assistant')).toBeInTheDocument()
    await waitFor(() => expect(api.assistantPages).toHaveBeenCalled())
    await waitFor(() => expect(api.miniBrainWidgetHealth).toHaveBeenCalled())
    expect(await screen.findByRole('button', { name: 'How do I use this page?' })).toBeInTheDocument()
    expect(screen.getByText(/AI response generation is unavailable/)).toBeInTheDocument()
  })

  it('does not show the unavailable notice when the runtime reports an available backend', async () => {
    mockDefaults()
    api.miniBrainWidgetHealth.mockResolvedValue({ loaded: true, backend_type: 'local', current_model: 'test-model.gguf', available: true, error_message: null })
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await waitFor(() => expect(api.miniBrainWidgetHealth).toHaveBeenCalled())
    expect(await screen.findByRole('button', { name: 'How do I use this page?' })).toBeInTheDocument()
    expect(screen.queryByText(/AI response generation is unavailable/)).not.toBeInTheDocument()
  })

  it('sends the typed message through the shared chat panel and renders the reply', async () => {
    mockDefaults()
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await user.click(await screen.findByRole('button', { name: 'How do I use this page?' }))
    await waitFor(() => expect(api.lrChat).toHaveBeenCalledWith(null, 'How do I use this page?'))
    expect(await screen.findByText('Datasets: Manage datasets.')).toBeInTheDocument()
  })

  it('sends through the grounded endpoint when the knowledge-base toggle is on and a profile is active', async () => {
    mockDefaults()
    api.miniBrainDefaultRetrievalProfile.mockResolvedValue({ retrieval_profile_public_id: 'profile-1', name: 'Default profile' })
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await user.click(await screen.findByLabelText('Use knowledge base'))
    await user.click(screen.getByRole('button', { name: 'How do I use this page?' }))
    await waitFor(() => expect(api.miniBrainDefaultRetrievalProfile).toHaveBeenCalled())
    await waitFor(() => expect(api.sendMiniBrainGroundedMessage).toHaveBeenCalledWith(null, 'How do I use this page?', 'profile-1'))
    expect(await screen.findByText('Grounded answer.')).toBeInTheDocument()
  })

  it('records feedback and shows a thank-you without blocking the chat', async () => {
    mockDefaults()
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await user.click(await screen.findByRole('button', { name: 'How do I use this page?' }))
    await screen.findByText('Datasets: Manage datasets.')
    await user.click(screen.getByRole('button', { name: 'Mark helpful' }))
    await waitFor(() => expect(api.submitAssistantFeedback).toHaveBeenCalledWith(
      expect.objectContaining({ rating: 'helpful', page_id: 'datasets' })
    ))
    expect(await screen.findByText('Thanks for the feedback.')).toBeInTheDocument()
  })

  it('keeps the conversation intact across minimize/restore (ChatPanel never unmounts)', async () => {
    mockDefaults()
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await user.click(await screen.findByRole('button', { name: 'How do I use this page?' }))
    expect(await screen.findByText('Datasets: Manage datasets.')).toBeInTheDocument()
    const callsBeforeMinimize = api.lrSessions.mock.calls.length

    await user.click(screen.getByRole('button', { name: 'Minimize Admin Assistant' }))
    await user.click(screen.getByRole('button', { name: 'Restore Admin Assistant' }))
    expect(screen.getByText('Datasets: Manage datasets.')).toBeInTheDocument()
    // No fresh lrSessions() fetch on restore -- proves ChatPanel never
    // remounted (a remount would re-run its load-sessions effect).
    expect(api.lrSessions.mock.calls.length).toBe(callsBeforeMinimize)
  })

  it('minimizes, restores, and closes back to the launcher', async () => {
    mockDefaults()
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await user.click(screen.getByRole('button', { name: 'Minimize Admin Assistant' }))
    // ChatPanel stays mounted (never unmounted) across minimize so an
    // in-progress conversation survives -- only hidden via CSS.
    expect(screen.getByLabelText('Message')).not.toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Restore Admin Assistant' }))
    await waitFor(() => expect(screen.getByLabelText('Message')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Close Admin Assistant' }))
    expect(screen.getByRole('button', { name: 'Open Admin Assistant' })).toBeInTheDocument()
    expect(screen.queryByText('Brud AI Assistant')).not.toBeInTheDocument()
  })

  it('closes on Escape and returns focus to the launcher', async () => {
    mockDefaults()
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    expect(screen.getByText('Brud AI Assistant')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByText('Brud AI Assistant')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Open Admin Assistant' })).toHaveFocus()
  })

  it('shows a generic error notice without a stack trace when the chat call fails', async () => {
    mockDefaults()
    api.lrChat.mockRejectedValue(new Error('Request failed.'))
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await user.click(await screen.findByRole('button', { name: 'How do I use this page?' }))
    expect(await screen.findAllByText('Request failed.')).not.toHaveLength(0)
  })

  it('loads the saved language preference and shows it in the selector', async () => {
    mockDefaults()
    api.assistantLanguagePreference.mockResolvedValue({ response_language: 'tanglish', updated_at: null })
    const user = userEvent.setup()
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    await waitFor(() => expect(api.assistantLanguagePreference).toHaveBeenCalled())
    expect(await screen.findByLabelText('Reply language')).toHaveValue('tanglish')
  })

  it('saves a new language preference when changed', async () => {
    mockDefaults()
    const user = userEvent.setup()
    renderWidget({ admin: null })
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
    renderWidget({ admin: null })
    await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
    const select = await screen.findByLabelText('Reply language')
    await waitFor(() => expect(select).toHaveValue('auto'))
    await user.selectOptions(select, 'english')
    expect(await screen.findByText('Could not save.')).toBeInTheDocument()
    await waitFor(() => expect(select).toHaveValue('auto'))
  })

  describe('draggable/resizable/dockable workspace', () => {
    it('docks left, persists the layout, and restores it on remount', async () => {
      mockDefaults()
      const user = userEvent.setup()
      const { unmount } = renderWidget({ admin: null })
      await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
      await user.click(screen.getByRole('button', { name: 'Dock left' }))
      expect(screen.getByRole('button', { name: 'Dock left' })).toHaveAttribute('aria-pressed', 'true')
      expect(JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY)).mode).toBe('docked-left')
      unmount()

      renderWidget({ admin: null })
      await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
      expect(screen.getByRole('button', { name: 'Dock left' })).toHaveAttribute('aria-pressed', 'true')
    })

    it('docks right', async () => {
      mockDefaults()
      const user = userEvent.setup()
      renderWidget({ admin: null })
      await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
      await user.click(screen.getByRole('button', { name: 'Dock right' }))
      expect(screen.getByRole('button', { name: 'Dock right' })).toHaveAttribute('aria-pressed', 'true')
      expect(JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY)).mode).toBe('docked-right')
    })

    it('enters and exits large chat mode (maximize)', async () => {
      mockDefaults()
      const user = userEvent.setup()
      renderWidget({ admin: null })
      await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
      await user.click(screen.getByRole('button', { name: 'Enter large chat mode' }))
      expect(screen.getByRole('button', { name: 'Exit large chat mode' })).toHaveAttribute('aria-pressed', 'true')
      expect(JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY)).mode).toBe('fullscreen')
      await user.click(screen.getByRole('button', { name: 'Exit large chat mode' }))
      expect(screen.getByRole('button', { name: 'Enter large chat mode' })).toHaveAttribute('aria-pressed', 'false')
    })

    it('drags via the title bar into floating mode and persists position/size', async () => {
      mockDefaults()
      renderWidget({ admin: null })
      fireEvent.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
      await screen.findByText('Brud AI Assistant')
      const handle = document.querySelector('.assistant-drag-handle')
      fireEvent.pointerDown(handle, { pointerId: 1, clientX: 100, clientY: 100 })
      fireEvent.pointerMove(handle, { pointerId: 1, clientX: 160, clientY: 140 })
      fireEvent.pointerUp(handle, { pointerId: 1, clientX: 160, clientY: 140 })
      const stored = JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY))
      expect(stored.mode).toBe('floating')
      expect(typeof stored.x).toBe('number')
      expect(typeof stored.y).toBe('number')
      expect(document.querySelector('.assistant-resize-handle')).toBeInTheDocument()
    })

    it('resizes via the resize handle once floating', async () => {
      mockDefaults()
      renderWidget({ admin: null })
      fireEvent.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
      await screen.findByText('Brud AI Assistant')
      const dragHandle = document.querySelector('.assistant-drag-handle')
      fireEvent.pointerDown(dragHandle, { pointerId: 1, clientX: 100, clientY: 100 })
      fireEvent.pointerMove(dragHandle, { pointerId: 1, clientX: 120, clientY: 110 })
      fireEvent.pointerUp(dragHandle, { pointerId: 1, clientX: 120, clientY: 110 })

      const resizeHandle = document.querySelector('.assistant-resize-handle')
      const before = JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY))
      fireEvent.pointerDown(resizeHandle, { pointerId: 2, clientX: 300, clientY: 300 })
      fireEvent.pointerMove(resizeHandle, { pointerId: 2, clientX: 400, clientY: 380 })
      fireEvent.pointerUp(resizeHandle, { pointerId: 2, clientX: 400, clientY: 380 })
      const after = JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY))
      expect(after.width).toBeGreaterThan(before.width)
      expect(after.height).toBeGreaterThan(before.height)
    })

    it('ignores a corrupted stored layout and falls back to default', async () => {
      localStorage.setItem(LAYOUT_STORAGE_KEY, 'not json')
      mockDefaults()
      const user = userEvent.setup()
      renderWidget({ admin: null })
      await user.click(screen.getByRole('button', { name: 'Open Admin Assistant' }))
      expect(screen.getByText('Brud AI Assistant')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Dock left' })).toHaveAttribute('aria-pressed', 'false')
    })
  })
})
