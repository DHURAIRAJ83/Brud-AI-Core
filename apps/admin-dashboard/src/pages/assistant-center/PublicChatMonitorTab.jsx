import { useCallback, useEffect, useState } from 'react'
import Button from '../../components/Button.jsx'
import ErrorBanner from '../../components/ErrorBanner.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import SessionList from '../../components/chat/SessionList.jsx'
import { useToast } from '../../components/Toast.jsx'
import {
  pcrCandidates,
  pcrMessages,
  pcrReviewCandidate,
  pcrSessions,
  pcrSignals,
} from '../../services/api.js'

// Matches the real privacy notice MiniBrainPage.jsx's own Public Chat
// Runtime tab already shows, verbatim -- the schema has no text column at
// all (append-only, immutable), so this tab shows real metadata only,
// never a fabricated message bubble with invented text.
const NO_RAW_TEXT_NOTICE = 'No raw message text is ever stored, only content hashes and already-sanitized signal text.'

export default function PublicChatMonitorTab() {
  const toast = useToast()
  const [sessions, setSessions] = useState([])
  const [sessionsLoaded, setSessionsLoaded] = useState(false)
  const [sessionsError, setSessionsError] = useState('')
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [signals, setSignals] = useState([])
  const [threadError, setThreadError] = useState('')
  const [candidates, setCandidates] = useState([])
  const [candidatesLoaded, setCandidatesLoaded] = useState(false)
  const [reviewBusy, setReviewBusy] = useState('')

  const loadSessions = useCallback(async () => {
    setSessionsLoaded(false)
    setSessionsError('')
    try {
      const result = await pcrSessions()
      setSessions(result.items ?? [])
    } catch (error) {
      setSessionsError(error.message)
    } finally {
      setSessionsLoaded(true)
    }
  }, [])

  const loadCandidates = useCallback(async () => {
    try {
      const result = await pcrCandidates('pending_admin_review')
      setCandidates(result.items ?? [])
    } catch {
      setCandidates([])
    } finally {
      setCandidatesLoaded(true)
    }
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])
  useEffect(() => { loadCandidates() }, [loadCandidates])

  async function selectSession(id) {
    setActiveSessionId(id)
    setThreadError('')
    try {
      const [messagesResult, signalsResult] = await Promise.all([
        pcrMessages(id),
        pcrSignals(id).catch(() => ({ items: [] })),
      ])
      setMessages(messagesResult.items ?? [])
      setSignals(signalsResult.items ?? [])
    } catch (error) {
      setThreadError(error.message)
    }
  }

  async function review(id, decision) {
    setReviewBusy(id)
    try {
      await pcrReviewCandidate(id, decision, '')
      toast.success(`Candidate ${decision === 'approve' ? 'approved' : 'rejected'}.`)
      await loadCandidates()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setReviewBusy('')
    }
  }

  const sessionItems = sessions.map((session) => ({
    id: session.public_id,
    title: session.public_id,
    subtitle: session.status,
    meta: `${session.message_count ?? 0} messages · ${session.unresolved_count ?? 0} unresolved`,
    status: session.status,
  }))

  return (
    <div className="wizard-shell">
      <aside className="wizard-progress" aria-label="Public chat sessions">
        <h3>Sessions</h3>
        {!sessionsLoaded ? (
          <Skeleton lines={4} />
        ) : sessionsError ? (
          <ErrorBanner message={sessionsError} onRetry={loadSessions} />
        ) : (
          <SessionList items={sessionItems} activeId={activeSessionId} onSelect={selectSession} emptyLabel="No public chat sessions yet." />
        )}
      </aside>

      <div className="wizard-content">
        <div className="notice">{NO_RAW_TEXT_NOTICE}</div>

        {threadError && <ErrorBanner message={threadError} onRetry={() => selectSession(activeSessionId)} />}

        {!activeSessionId ? (
          <div className="notice">Select a session to view its message metadata.</div>
        ) : (
          <>
            <h3>Message metadata</h3>
            {messages.length === 0 ? (
              <div className="notice">No messages recorded for this session yet.</div>
            ) : (
              <div className="data-list">
                {messages.map((message) => (
                  <article key={message.public_id}>
                    <div>
                      <strong>{message.role}</strong>
                      <span>hash {message.content_hash?.slice(0, 12)}</span>
                    </div>
                    <small>
                      {message.route_used && `route ${message.route_used} · `}
                      {message.used_rag && 'RAG · '}
                      {message.used_vision && 'vision · '}
                      {message.used_tool && 'tool · '}
                      {new Date(message.created_at).toLocaleString()}
                    </small>
                  </article>
                ))}
              </div>
            )}

            <h3>Feedback signals</h3>
            {signals.length === 0 ? (
              <div className="notice">No feedback signals for this session.</div>
            ) : (
              <div className="data-list">
                {signals.map((signal) => (
                  <article key={signal.public_id}>
                    <div><strong>{signal.signal_type || 'signal'}</strong></div>
                    <small>{signal.normalized_text}</small>
                  </article>
                ))}
              </div>
            )}
          </>
        )}

        <h3>Candidate review queue</h3>
        {!candidatesLoaded ? (
          <Skeleton lines={3} />
        ) : candidates.length === 0 ? (
          <div className="notice">No candidates pending admin review.</div>
        ) : (
          <div className="candidate-list">
            {candidates.map((candidate) => (
              <article key={candidate.public_id}>
                <header>
                  <strong>{candidate.public_id}</strong>
                  <span>{candidate.status}</span>
                </header>
                <div className="review-actions">
                  <Button size="sm" variant="success" loading={reviewBusy === candidate.public_id} onClick={() => review(candidate.public_id, 'approve')}>
                    Approve
                  </Button>
                  <Button size="sm" variant="danger" loading={reviewBusy === candidate.public_id} onClick={() => review(candidate.public_id, 'reject')}>
                    Reject
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
