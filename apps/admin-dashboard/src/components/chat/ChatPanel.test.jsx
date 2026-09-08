import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatPanel from './ChatPanel.jsx'

vi.mock('../../services/api.js', () => ({
  lrChat: vi.fn(),
  lrDeleteSession: vi.fn(),
  lrMessages: vi.fn(),
  lrSessions: vi.fn(),
  miniBrainDefaultRetrievalProfile: vi.fn(),
  sendMiniBrainGroundedMessage: vi.fn(),
}))

const api = await import('../../services/api.js')
const toast = { success: vi.fn(), error: vi.fn() }

afterEach(() => {
  vi.resetAllMocks()
})

function mockDefaults() {
  api.lrSessions.mockResolvedValue({ items: [] })
}

describe('ChatPanel', () => {
  it('compact variant does not render a session list', async () => {
    mockDefaults()
    render(<ChatPanel variant="compact" toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    expect(document.querySelector('.chat-panel-sessions')).not.toBeInTheDocument()
  })

  it('full variant renders the real session list once loaded', async () => {
    api.lrSessions.mockResolvedValue({
      items: [{ public_id: 's1', title: 'Prior chat', status: 'active', total_messages: 3 }],
    })
    render(<ChatPanel variant="full" toast={toast} />)
    expect(await screen.findByText('Prior chat')).toBeInTheDocument()
  })

  it('shows the empty greeting and real suggestions before any message is sent', async () => {
    mockDefaults()
    render(<ChatPanel toast={toast} emptyGreeting="Hi there." suggestions={['What is pending?']} />)
    expect(await screen.findByText('Hi there.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'What is pending?' })).toBeInTheDocument()
  })

  it('sends a plain message via lrChat and renders the real reply', async () => {
    mockDefaults()
    api.lrChat.mockResolvedValue({
      session: { public_id: 'sess-1' }, reply: { sanitized_text: 'Here is the answer.' }, backend_type: 'local', error_message: null,
    })
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    await user.type(screen.getByLabelText('Message'), 'What is Brud AI?')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(api.lrChat).toHaveBeenCalledWith(null, 'What is Brud AI?', expect.anything()))
    expect(await screen.findByText('Here is the answer.')).toBeInTheDocument()
  })

  it('grounded mode calls sendMiniBrainGroundedMessage and renders a real citation card', async () => {
    mockDefaults()
    api.miniBrainDefaultRetrievalProfile.mockResolvedValue({ retrieval_profile_public_id: 'profile-1', name: 'Default' })
    api.sendMiniBrainGroundedMessage.mockResolvedValue({
      session: { public_id: 'sess-1' }, reply: { sanitized_text: 'Grounded answer.' }, backend_type: 'local', error_message: null,
      citations: [{ source_public_id: 'src-1', source_name: 'Source A', rank: 1, score: 0.9, text_preview: 'preview text' }],
    })
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    await user.click(screen.getByLabelText('Use knowledge base'))
    await user.type(screen.getByLabelText('Message'), 'Grounded question')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(api.sendMiniBrainGroundedMessage).toHaveBeenCalledWith(null, 'Grounded question', 'profile-1', expect.anything(), expect.anything()))
    expect(await screen.findByText('Source A')).toBeInTheDocument()
    expect(screen.getByText('preview text')).toBeInTheDocument()
  })

  it('warns honestly when grounded mode is on but no default profile is active', async () => {
    mockDefaults()
    api.miniBrainDefaultRetrievalProfile.mockResolvedValue({ retrieval_profile_public_id: null, name: null })
    api.lrChat.mockResolvedValue({ session: { public_id: 'sess-1' }, reply: { sanitized_text: 'Reply.' }, backend_type: 'local' })
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    await user.click(screen.getByLabelText('Use knowledge base'))
    await user.type(screen.getByLabelText('Message'), 'Question')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText(/No active knowledge base profile/)).toBeInTheDocument()
    // Falls back to the real, unmodified plain-chat path.
    await waitFor(() => expect(api.lrChat).toHaveBeenCalledWith(null, 'Question', expect.anything()))
  })

  it('Regenerate resends the last real user message', async () => {
    mockDefaults()
    api.lrChat.mockResolvedValue({ session: { public_id: 'sess-1' }, reply: { sanitized_text: 'First reply.' }, backend_type: 'local' })
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    await user.type(screen.getByLabelText('Message'), 'Original question')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await screen.findByText('First reply.')

    api.lrChat.mockResolvedValue({ session: { public_id: 'sess-1' }, reply: { sanitized_text: 'Second reply.' }, backend_type: 'local' })
    await user.click(screen.getByRole('button', { name: 'Regenerate' }))
    await waitFor(() => expect(api.lrChat).toHaveBeenCalledWith('sess-1', 'Original question', expect.anything()))
    expect(await screen.findByText('Second reply.')).toBeInTheDocument()
  })

  it('Regenerate is disabled until a message has been sent', async () => {
    mockDefaults()
    render(<ChatPanel toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: 'Regenerate' })).toBeDisabled()
  })

  it('Copy calls the shared clipboard util and shows a toast', async () => {
    mockDefaults()
    api.lrChat.mockResolvedValue({ session: { public_id: 'sess-1' }, reply: { sanitized_text: 'Copy me.' }, backend_type: 'local' })
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue() } })
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    await user.type(screen.getByLabelText('Message'), 'Question')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await screen.findByText('Copy me.')
    await user.click(screen.getByRole('button', { name: 'Copy' }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Copied to clipboard.'))
    vi.unstubAllGlobals()
  })

  it('feedback buttons only render when onFeedback is provided, and call it with the real message + rating', async () => {
    mockDefaults()
    api.lrChat.mockResolvedValue({ session: { public_id: 'sess-1' }, reply: { sanitized_text: 'Reply.' }, backend_type: 'local' })
    const onFeedback = vi.fn().mockResolvedValue()
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} onFeedback={onFeedback} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    await user.type(screen.getByLabelText('Message'), 'Question')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await screen.findByText('Reply.')
    await user.click(screen.getByRole('button', { name: 'Mark helpful' }))
    expect(onFeedback).toHaveBeenCalledWith(expect.objectContaining({ text: 'Reply.' }), 'helpful')
    expect(await screen.findByText('Thanks for the feedback.')).toBeInTheDocument()
  })

  it('selecting a real past session loads its real messages via lrMessages', async () => {
    api.lrSessions.mockResolvedValue({ items: [{ public_id: 's1', title: 'Old chat', status: 'active', total_messages: 2 }] })
    api.lrMessages.mockResolvedValue({
      items: [
        { public_id: 'm1', role: 'admin', sanitized_text: 'Old question' },
        { public_id: 'm2', role: 'assistant', sanitized_text: 'Old answer' },
      ],
    })
    const user = userEvent.setup()
    render(<ChatPanel variant="full" toast={toast} />)
    await user.click(await screen.findByText('Old chat'))
    await waitFor(() => expect(api.lrMessages).toHaveBeenCalledWith('s1'))
    expect(await screen.findByText('Old question')).toBeInTheDocument()
    expect(screen.getByText('Old answer')).toBeInTheDocument()
  })

  it('deleting a session calls lrDeleteSession and refreshes the list', async () => {
    api.lrSessions.mockResolvedValueOnce({ items: [{ public_id: 's1', title: 'Old chat', status: 'active', total_messages: 2 }] })
    api.lrDeleteSession.mockResolvedValue({})
    api.lrSessions.mockResolvedValueOnce({ items: [] })
    const user = userEvent.setup()
    render(<ChatPanel variant="full" toast={toast} />)
    await screen.findByText('Old chat')
    await user.click(screen.getByRole('button', { name: 'Delete Old chat' }))
    await waitFor(() => expect(api.lrDeleteSession).toHaveBeenCalledWith('s1'))
    expect(toast.success).toHaveBeenCalledWith('Conversation deleted.')
  })

  it('renders markdown in replies via the shared formatter', async () => {
    mockDefaults()
    api.lrChat.mockResolvedValue({ session: { public_id: 'sess-1' }, reply: { sanitized_text: 'This is **bold** text.' }, backend_type: 'local' })
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} />)
    await waitFor(() => expect(api.lrSessions).toHaveBeenCalled())
    await user.type(screen.getByLabelText('Message'), 'Question')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText('bold')).toBeInTheDocument()
    expect(document.querySelector('.chat-msg-assistant strong')).toHaveTextContent('bold')

  })

  it('switches between Chat, Assistant Settings, and Dataset Generate tabs', async () => {
    mockDefaults()
    const user = userEvent.setup()
    render(<ChatPanel toast={toast} />)

    // Chat tab is active by default
    expect(screen.getByPlaceholderText('Type a question or attach a PDF…')).toBeInTheDocument()

    // Switch to Settings tab
    await user.click(screen.getByRole('button', { name: 'Provider & AI Settings' }))
    expect(await screen.findByText('Assistant & Provider Settings')).toBeInTheDocument()

    // Switch to Generate tab
    await user.click(screen.getByRole('button', { name: 'Dataset Generator' }))
    expect(await screen.findByText('Provider Dataset Generator')).toBeInTheDocument()

    // Switch back to Chat tab
    await user.click(screen.getByRole('button', { name: 'Assistant Chat' }))
    expect(screen.getByPlaceholderText('Type a question or attach a PDF…')).toBeInTheDocument()
  })
})

