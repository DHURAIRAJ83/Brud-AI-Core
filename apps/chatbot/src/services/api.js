const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const SESSION_ID_KEY = 'brud_anon_conversation_id'
const SESSION_TOKEN_KEY = 'brud_anon_session_token'

export function getStoredSession() {
  try {
    const conversationId = sessionStorage.getItem(SESSION_ID_KEY)
    const sessionToken = sessionStorage.getItem(SESSION_TOKEN_KEY)
    if (conversationId && sessionToken) {
      return { conversationId, sessionToken }
    }
  } catch {
    // sessionStorage unavailable (e.g. strict sandbox or SSR)
  }
  return null
}

export function setStoredSession({ conversationId, sessionToken }) {
  try {
    if (conversationId && sessionToken) {
      sessionStorage.setItem(SESSION_ID_KEY, conversationId)
      sessionStorage.setItem(SESSION_TOKEN_KEY, sessionToken)
    }
  } catch {
    // ignore
  }
}

export function clearStoredSession() {
  try {
    sessionStorage.removeItem(SESSION_ID_KEY)
    sessionStorage.removeItem(SESSION_TOKEN_KEY)
  } catch {
    // ignore
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    let code = null
    try {
      const data = await response.json()
      code = data?.error?.code ?? null
      message = data?.error?.message ?? data?.detail?.[0]?.msg ?? message
    } catch {
      // Preserve the status-based message for non-JSON failures.
    }
    const error = new Error(message)
    error.status = response.status
    error.code = code
    throw error
  }
  return response.json()
}

export const getHealth = () => request('/api/health')

export const getChatCapabilities = () => request('/api/chat/capabilities')

export const initSession = async ({ languagePreference = 'auto' } = {}) => {
  const data = await request('/api/chat/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language_preference: languagePreference }),
  })
  if (data?.conversation_id && data?.session_token) {
    setStoredSession({
      conversationId: data.conversation_id,
      sessionToken: data.session_token,
    })
  }
  return data
}

export const getSessionMessages = (conversationId, sessionToken) => {
  const headers = {}
  const token = sessionToken ?? getStoredSession()?.sessionToken
  if (token) {
    headers['X-Session-Token'] = token
  }
  return request(`/api/chat/session/${conversationId}/messages`, {
    method: 'GET',
    headers,
  })
}

export const clearSession = async (conversationId, sessionToken) => {
  const headers = {}
  const token = sessionToken ?? getStoredSession()?.sessionToken
  if (token) {
    headers['X-Session-Token'] = token
  }
  const result = await request(`/api/chat/session/${conversationId}/clear`, {
    method: 'POST',
    headers,
  })
  clearStoredSession()
  return result
}

export const sendChatMessage = ({
  message,
  conversationId,
  sessionToken,
  languageOverride,
  memoryConsent,
  clientRequestId,
}) => {
  const headers = { 'Content-Type': 'application/json' }
  const token = sessionToken ?? getStoredSession()?.sessionToken
  if (token) {
    headers['X-Session-Token'] = token
  }
  return request('/api/chat', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? null,
      language_override: languageOverride ?? 'auto',
      memory_consent: Boolean(memoryConsent),
      client_request_id: clientRequestId ?? null,
    }),
  })
}

export const sendChatFeedback = ({ requestId, routeUsed, answerHash, feedbackType, comment }) =>
  request('/api/chat/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request_id: requestId,
      route_used: routeUsed,
      answer_hash: answerHash,
      feedback_type: feedbackType,
      comment: comment ?? null,
    }),
  })
