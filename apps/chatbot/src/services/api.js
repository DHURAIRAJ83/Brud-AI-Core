const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

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

export const sendChatMessage = ({ message, conversationId, languageOverride, memoryConsent, clientRequestId }) =>
  request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? null,
      language_override: languageOverride ?? 'auto',
      memory_consent: Boolean(memoryConsent),
      client_request_id: clientRequestId ?? null,
    }),
  })

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
