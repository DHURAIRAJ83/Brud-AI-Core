const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const data = await response.json()
      message = data?.error?.message ?? data?.detail?.[0]?.msg ?? message
    } catch {
      // Preserve the status-based message for non-JSON failures.
    }
    throw new Error(message)
  }
  return response.json()
}

export const getHealth = () => request('/api/health')

export const sendChatMessage = (message, language) => request('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message, language }),
})
