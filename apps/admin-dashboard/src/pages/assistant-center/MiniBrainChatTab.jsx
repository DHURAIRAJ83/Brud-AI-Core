import { useCallback, useEffect, useState } from 'react'
import ChatPanel from '../../components/chat/ChatPanel.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'
import { useToast } from '../../components/Toast.jsx'
import { lrDiagnostics, miniBrainDefaultRetrievalProfile } from '../../services/api.js'

const SUGGESTIONS = ['How do I use this dashboard?', 'What needs my attention right now?']

export default function MiniBrainChatTab({ admin }) {
  const toast = useToast()
  const [state, setState] = useState({ loading: true, error: '' })

  const load = useCallback(async () => {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [diagnostics, defaultProfile] = await Promise.all([
        lrDiagnostics(),
        miniBrainDefaultRetrievalProfile(),
      ])
      setState({ loading: false, error: '', diagnostics, defaultProfile })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="assistant-center-chat-grid">
      <div className="training-detail assistant-center-chat-pane">
        <ChatPanel variant="full" admin={admin} toast={toast} suggestions={SUGGESTIONS} />
      </div>

      <div className="training-detail">
        <h3>Runtime</h3>
        {state.loading ? (
          <Skeleton lines={4} />
        ) : state.error ? (
          <ErrorBanner message={state.error} onRetry={load} />
        ) : (
          <>
            <section className="metric-grid">
              <StatusCard label="Local runtime" value={state.diagnostics.local_available ? 'available' : 'unavailable'} tone={state.diagnostics.local_available ? 'good' : 'waiting'} />
              <StatusCard label="External fallback" value={state.diagnostics.external_fallback_enabled ? 'enabled' : 'disabled'} />
              <StatusCard label="Active sessions" value={state.diagnostics.active_session_count} />
              <StatusCard label="Total messages" value={state.diagnostics.total_messages} />
            </section>
            <h3>Active retrieval profile</h3>
            <p className="notice">
              {state.defaultProfile.retrieval_profile_public_id ? state.defaultProfile.name : 'None set -- grounded replies fall back to plain chat.'}
            </p>
          </>
        )}
      </div>
    </div>
  )
}
