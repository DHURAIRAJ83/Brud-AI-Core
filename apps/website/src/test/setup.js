import '@testing-library/jest-dom'
import { vi } from 'vitest'

vi.mock('@chatbot/services/api.js', () => ({
  getHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
  getChatCapabilities: vi.fn().mockResolvedValue({}),
  initSession: vi.fn().mockResolvedValue({ conversation_id: 'mock-conv-id', session_token: 'mock-session-token' }),
  getStoredSession: vi.fn().mockReturnValue(null),
  setStoredSession: vi.fn(),
  clearStoredSession: vi.fn(),
  getSessionMessages: vi.fn().mockResolvedValue({ messages: [] }),
  clearSession: vi.fn().mockResolvedValue({ cleared: true }),
  sendChatMessage: vi.fn().mockResolvedValue({ reply: 'வணக்கம்! நான் புரூட் AI.' }),
  sendChatFeedback: vi.fn().mockResolvedValue({ public_id: 'feedback-123', accepted: true }),
}))
