import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatPage from './ChatPage.jsx'
import {
  clearSession,
  clearStoredSession,
  getHealth,
  getSessionMessages,
  getStoredSession,
  initSession,
  sendChatFeedback,
  sendChatMessage,
} from '../services/api.js'

vi.mock('../services/api.js', () => ({
  getHealth: vi.fn(),
  getChatCapabilities: vi.fn(),
  sendChatMessage: vi.fn(),
  sendChatFeedback: vi.fn(),
  initSession: vi.fn(),
  getSessionMessages: vi.fn(),
  clearSession: vi.fn(),
  getStoredSession: vi.fn(),
  setStoredSession: vi.fn(),
  clearStoredSession: vi.fn(),
}))

async function sendMessage(text) {
  const textbox = screen.getByRole('textbox')
  await userEvent.type(textbox, text)
  await userEvent.click(screen.getByRole('button', { name: /send/i }))
}

describe('ChatPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    getHealth.mockResolvedValue({ status: 'healthy' })
    getStoredSession.mockReturnValue(null)
    initSession.mockResolvedValue({ conversation_id: 'conv-123', session_token: 'token-123' })
    getSessionMessages.mockResolvedValue({ messages: [] })
    clearSession.mockResolvedValue({ cleared: true })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders a real assistant reply with its route label after sending a message', async () => {
    sendChatMessage.mockResolvedValue({
      reply: 'இது ஒரு பதில்.',
      route_used: 'core_model',
      request_id: 'req-1',
      conversation_id: 'conv-1',
    })
    render(<ChatPage />)
    await sendMessage('வணக்கம்')
    expect(await screen.findByText('இது ஒரு பதில்.')).toBeInTheDocument()
    expect(screen.getByText('Model')).toBeInTheDocument()
  })

  it('shows a loading state while the request is in flight', async () => {
    let resolveRequest
    sendChatMessage.mockReturnValue(new Promise((resolve) => { resolveRequest = resolve }))
    render(<ChatPage />)
    await sendMessage('Hello')
    expect(screen.getByRole('button', { name: /sending/i })).toBeInTheDocument()
    resolveRequest({ reply: 'Hi', route_used: 'core_model', request_id: 'req-2' })
    await waitFor(() => expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument())
  })

  it('shows a timeout error and offers retry when the request takes too long', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    sendChatMessage.mockReturnValue(new Promise(() => {}))
    render(<ChatPage />)
    const textbox = screen.getByRole('textbox')
    await userEvent.setup({ delay: null }).type(textbox, 'Hello')
    await userEvent.setup({ delay: null }).click(screen.getByRole('button', { name: /send/i }))
    await vi.advanceTimersByTimeAsync(30000)
    expect(await screen.findByRole('alert')).toHaveTextContent(/took too long/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('displays a clarification response distinctly', async () => {
    sendChatMessage.mockResolvedValue({
      reply: 'எதை apply செய்ய வேண்டும் என்று குறிப்பிடுங்கள்?',
      route_used: 'clarify',
      request_id: 'req-3',
      clarification_required: true,
    })
    render(<ChatPage />)
    await sendMessage('அதை apply செய்')
    expect(await screen.findByText('Clarification')).toBeInTheDocument()
  })

  it('displays a refusal response distinctly', async () => {
    sendChatMessage.mockResolvedValue({
      reply: 'இந்த கோரிக்கைக்கு உதவ முடியாது.',
      route_used: 'refuse',
      request_id: 'req-4',
      safety_status: 'refused',
    })
    render(<ChatPage />)
    await sendMessage('unsafe request')
    expect(await screen.findByText('Refused')).toBeInTheDocument()
  })

  it('displays an insufficient-evidence response distinctly', async () => {
    sendChatMessage.mockResolvedValue({
      reply: 'இதற்கு தற்போது நம்பகமான தகவல் இல்லை.',
      route_used: 'insufficient',
      request_id: 'req-5',
      insufficient_evidence: true,
    })
    render(<ChatPage />)
    await sendMessage('Python latest stable version என்ன?')
    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
  })

  it('shows a rate-limit message and disables retry when the server rate limits', async () => {
    const rateLimitError = new Error('Too many requests')
    rateLimitError.code = 'CHAT_RATE_LIMITED'
    sendChatMessage.mockRejectedValue(rateLimitError)
    render(<ChatPage />)
    await sendMessage('Hello')
    expect(await screen.findByRole('alert')).toHaveTextContent(/too many messages/i)
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument()
  })

  it('retries the last failed message when Retry is clicked', async () => {
    sendChatMessage.mockRejectedValueOnce(new Error('boom'))
    sendChatMessage.mockResolvedValueOnce({ reply: 'Recovered', route_used: 'core_model', request_id: 'req-6' })
    render(<ChatPage />)
    await sendMessage('Hello')
    await screen.findByRole('alert')
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(await screen.findByText('Recovered')).toBeInTheDocument()
    expect(sendChatMessage).toHaveBeenCalledTimes(2)
  })

  it('submits feedback bound to the request id and route, using a client-computed answer hash', async () => {
    sendChatMessage.mockResolvedValue({ reply: 'Reply text', route_used: 'core_model', request_id: 'req-7' })
    sendChatFeedback.mockResolvedValue({})
    render(<ChatPage />)
    await sendMessage('Hello')
    await screen.findByText('Reply text')
    await userEvent.click(screen.getByRole('button', { name: /^helpful$/i }))
    await waitFor(() => expect(sendChatFeedback).toHaveBeenCalledTimes(1))
    const call = sendChatFeedback.mock.calls[0][0]
    expect(call.requestId).toBe('req-7')
    expect(call.routeUsed).toBe('core_model')
    expect(call.feedbackType).toBe('thumbs_up')
    expect(call.answerHash).toMatch(/^[0-9a-f]{64}$/)
    expect(await screen.findByText(/thanks for the feedback/i)).toBeInTheDocument()
  })

  it('never offers Tanglish as an answer-language option', () => {
    render(<ChatPage />)
    const options = screen.getAllByRole('option').map((option) => option.textContent)
    expect(options).not.toContain('Tanglish')
    expect(options).toEqual(['Auto', 'தமிழ்', 'English'])
  })

  // ---------------------------------------------------------------------------
  // P8-03: Anonymous Session Lifecycle, Hydration, and Actions Tests
  // ---------------------------------------------------------------------------

  it('hydrates historical turns when a valid stored session is found on mount', async () => {
    getStoredSession.mockReturnValue({ conversationId: 'stored-conv-1', sessionToken: 'stored-token-1' })
    getSessionMessages.mockResolvedValue({
      conversation_id: 'stored-conv-1',
      turn_count: 2,
      messages: [
        { id: 'turn-1', role: 'user', content: 'Previous Question' },
        { id: 'turn-2', role: 'assistant', content: 'Previous Answer' },
      ],
    })

    render(<ChatPage />)
    expect(await screen.findByText('Previous Question')).toBeInTheDocument()
    expect(screen.getByText('Previous Answer')).toBeInTheDocument()
    expect(getSessionMessages).toHaveBeenCalledWith('stored-conv-1', 'stored-token-1')
  })

  it('starts a new chat when New Chat button is clicked', async () => {
    render(<ChatPage />)
    const newChatBtn = screen.getByRole('button', { name: /new chat/i })
    expect(newChatBtn).toBeInTheDocument()

    await userEvent.click(newChatBtn)
    expect(clearStoredSession).toHaveBeenCalled()
    expect(initSession).toHaveBeenCalled()
  })

  it('clears chat history and closes session when Clear button is clicked', async () => {
    getStoredSession.mockReturnValue({ conversationId: 'conv-clear-1', sessionToken: 'token-clear-1' })
    getSessionMessages.mockResolvedValue({
      conversation_id: 'conv-clear-1',
      turn_count: 1,
      messages: [{ id: 'turn-1', role: 'user', content: 'Message to clear' }],
    })

    render(<ChatPage />)
    expect(await screen.findByText('Message to clear')).toBeInTheDocument()

    const clearBtn = await screen.findByRole('button', { name: /clear chat/i })
    expect(clearBtn).toBeInTheDocument()

    await userEvent.click(clearBtn)
    expect(clearSession).toHaveBeenCalledWith('conv-clear-1', 'token-clear-1')
    expect(screen.queryByText('Message to clear')).not.toBeInTheDocument()
  })

  it('handles expired session error gracefully and prompts for retry', async () => {
    const expiredError = new Error('Conversation session has expired.')
    expiredError.code = 'CHAT_SESSION_EXPIRED'
    expiredError.status = 401
    sendChatMessage.mockRejectedValue(expiredError)

    render(<ChatPage />)
    await sendMessage('Hello with expired session')

    expect(await screen.findByRole('alert')).toHaveTextContent(/session has expired/i)
    expect(clearStoredSession).toHaveBeenCalled()
  })
})
