import { useEffect, useState } from 'react'
import ChatHeader from '../components/ChatHeader.jsx'
import ChatInput from '../components/ChatInput.jsx'
import ChatMessages from '../components/ChatMessages.jsx'
import { getHealth, sendChatMessage } from '../services/api.js'

export default function ChatPage() {
  const [health, setHealth] = useState('checking')
  const [messages, setMessages] = useState([])
  const [message, setMessage] = useState('')
  const [language, setLanguage] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { getHealth().then((data) => setHealth(data.status)).catch(() => setHealth('offline')) }, [])

  async function submit(event) {
    event.preventDefault()
    const text = message.trim()
    if (!text || loading) return
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', text }])
    setMessage(''); setLoading(true); setError('')
    try {
      const data = await sendChatMessage(text, language)
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: data.reply }])
    } catch (requestError) {
      setError(requestError.message)
    } finally { setLoading(false) }
  }

  return (
    <main className="chat-shell">
      <ChatHeader health={health} />
      <ChatMessages messages={messages} />
      {error && <div className="error" role="alert">{error}</div>}
      <ChatInput value={message} language={language} loading={loading} onChange={setMessage}
        onLanguage={setLanguage} onSubmit={submit} />
    </main>
  )
}
