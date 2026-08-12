import { useEffect, useRef, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  acceptConversationSummary,
  activateMemoryPolicy,
  activateMemoryRetrievalProfile,
  addMemoryEvaluationFixture,
  closeConversationSession,
  confirmMemoryItem,
  conversationSession,
  conversationSessionTurns,
  conversationSessions,
  conversationSummaries,
  correctMemoryItem,
  createConversationSession,
  createConversationSummary,
  createMemoryConsent,
  createMemoryEvaluationRun,
  createMemoryEvaluationSuite,
  createMemoryItem,
  createMemoryPolicy,
  createMemoryRetrievalProfile,
  deleteMemoryItem,
  executeMemoryEvaluationRun,
  expireConversationSession,
  expireMemoryConsent,
  expireMemoryItem,
  generateMemoryManifest,
  memoryConsents,
  memoryEvaluationMetrics,
  memoryEvaluationSuites,
  memoryItemEvents,
  memoryItems,
  memoryItemVersions,
  memoryPolicies,
  memoryRetrievalProfiles,
  orchestrationContext,
  orchestrationIssues,
  orchestrationResponse,
  orchestrationRun,
  pauseConversationSession,
  postConversationMessage,
  rejectMemoryItem,
  resumeConversationSession,
  retrieveMemory,
  revokeMemoryConsent,
  validateConversationSummary,
  validateMemoryPolicy,
  validateMemoryRetrievalProfile,
  verifyMemoryManifest,
} from '../services/api.js'

const PRIVACY_NOTICE = 'Conversation memory is consent-aware, purpose-bound, inspectable, and deletable. It must not be treated as hidden permanent profiling.'
const LAB_DISCLAIMER = 'Admin-only conversation diagnostic. This is not the public chatbot.'

const TABS = [
  'Overview', 'Memory Policies', 'Sessions', 'Session Turns', 'Summaries', 'Consent',
  'Memory Items', 'Memory Versions', 'Memory Retrieval', 'Context Orchestration',
  'Grounded Conversation Lab', 'Privacy & Deletion', 'Evaluation', 'Reproducibility',
]

function Pre({ value }) {
  if (!value) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

export default function ConversationMemoryPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', policies: [], sessions: [], consents: [], profiles: [], suites: [] })
  const [panelError, setPanelError] = useState('')

  const [policyForm, setPolicyForm] = useState({ name: '', default_session_mode: 'private_no_persist', allow_long_term_memory: false })
  const [selectedPolicyId, setSelectedPolicyId] = useState('')

  const [sessionForm, setSessionForm] = useState({ session_mode: 'private_no_persist', memory_policy_public_id: '', participant_scope_key: '', model_assignment_public_id: '', rag_retrieval_profile_public_id: '' })
  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [sessionDetail, setSessionDetail] = useState(null)
  const [turns, setTurns] = useState({ items: [] })

  const [chatMessage, setChatMessage] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [chatSending, setChatSending] = useState(false)
  const chatEndRef = useRef(null)
  const [lastOrchestrationRunId, setLastOrchestrationRunId] = useState('')
  const [orchestrationRunData, setOrchestrationRunData] = useState(null)
  const [orchestrationContextData, setOrchestrationContextData] = useState(null)
  const [orchestrationResponseData, setOrchestrationResponseData] = useState(null)
  const [orchestrationIssuesData, setOrchestrationIssuesData] = useState(null)

  const [summaries, setSummaries] = useState({ items: [] })

  const [consentForm, setConsentForm] = useState({ participant_scope_key: '', memory_policy_public_id: '', purpose: 'language_preference' })

  const [memoryForm, setMemoryForm] = useState({ participant_scope_key: '', category: 'language_preference', purpose: 'language_preference', creation_source: 'explicit_user_request', confidence_type: 'user_confirmed', display_value: '', consent_public_id: '' })
  const [participantFilter, setParticipantFilter] = useState('')
  const [items, setItems] = useState({ items: [] })
  const [selectedMemoryId, setSelectedMemoryId] = useState('')
  const [versions, setVersions] = useState({ items: [] })
  const [events, setEvents] = useState({ items: [] })
  const [correctionForm, setCorrectionForm] = useState({ display_value: '', change_reason: '' })

  const [retrieveForm, setRetrieveForm] = useState({ retrieval_profile_public_id: '', participant_scope_key: '', query: '' })
  const [retrieveResult, setRetrieveResult] = useState(null)

  const [suiteForm, setSuiteForm] = useState({ name: '', version: 'v1' })
  const [selectedSuiteId, setSelectedSuiteId] = useState('')
  const [fixtureForm, setFixtureForm] = useState({ participant_scope_key: '', query: '', expected_retrieved_memory_ids: '' })
  const [evaluationRunResult, setEvaluationRunResult] = useState(null)
  const [evaluationMetricsData, setEvaluationMetricsData] = useState({ items: [] })

  const [manifestResult, setManifestResult] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [policies, sessions, consents, profiles, suites] = await Promise.all([
        memoryPolicies(), conversationSessions(), memoryConsents(), memoryRetrievalProfiles(), memoryEvaluationSuites(),
      ])
      setState({
        loading: false, error: '',
        policies: policies.items ?? [], sessions: sessions.items ?? [],
        consents: consents.items ?? [], profiles: profiles.items ?? [], suites: suites.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => { chatEndRef.current?.scrollIntoView({ block: 'nearest' }) }, [chatHistory])

  async function submitPolicy(event) {
    event.preventDefault()
    try { await createMemoryPolicy(policyForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runValidatePolicy(id) {
    try { await validateMemoryPolicy(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runActivatePolicy(id) {
    try { await activateMemoryPolicy(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }

  async function submitSession(event) {
    event.preventDefault()
    try {
      const body = { ...sessionForm }
      if (!body.model_assignment_public_id) delete body.model_assignment_public_id
      if (!body.rag_retrieval_profile_public_id) delete body.rag_retrieval_profile_public_id
      const created = await createConversationSession(body)
      setPanelError('')
      await load()
      await openSession(created.public_id)
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function loadSessionDetail(id) {
    setSelectedSessionId(id)
    setSessionDetail(await conversationSession(id).catch(() => null))
    const loadedTurns = await conversationSessionTurns(id).catch(() => ({ items: [] }))
    setTurns(loadedTurns)
    setSummaries(await conversationSummaries(id).catch(() => ({ items: [] })))
    return loadedTurns
  }
  // Opening a (possibly different) session must restore its persisted
  // transcript into the chat view -- loadSessionDetail alone only
  // refreshes metadata/turns/summaries state, it never touches
  // chatHistory, so switching sessions previously left stale or empty
  // chat bubbles on screen. Historical turns carry no citation data
  // (chat_response_citations link to a grounded_response, not a turn),
  // so restored turns render without citations -- only the transcript
  // text/role, matching what's actually persisted.
  async function openSession(id) {
    const loadedTurns = await loadSessionDetail(id)
    setChatHistory(
      (loadedTurns.items ?? []).map((item) => ({
        role: item.role,
        text: item.stored_content ?? '(not persisted)',
      })),
    )
    setLastOrchestrationRunId('')
  }
  async function runPause() {
    try { await pauseConversationSession(selectedSessionId); setPanelError(''); await loadSessionDetail(selectedSessionId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runResume() {
    try { await resumeConversationSession(selectedSessionId); setPanelError(''); await loadSessionDetail(selectedSessionId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runClose() {
    try { await closeConversationSession(selectedSessionId); setPanelError(''); await loadSessionDetail(selectedSessionId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runExpire() {
    try { await expireConversationSession(selectedSessionId); setPanelError(''); await loadSessionDetail(selectedSessionId) }
    catch (error) { setPanelError(error.message) }
  }

  async function sendMessage(event) {
    event.preventDefault()
    const sentMessage = chatMessage
    setChatSending(true)
    try {
      const result = await postConversationMessage(selectedSessionId, { message: sentMessage })
      setChatHistory((old) => [
        ...old,
        { role: 'user', text: sentMessage },
        {
          role: 'assistant', text: result.answer_text, status: result.response?.answer_status,
          citations: result.citations ?? [],
        },
      ])
      setLastOrchestrationRunId(result.orchestration_run.public_id)
      setChatMessage('')
      setPanelError('')
      await loadSessionDetail(selectedSessionId)
    } catch (error) {
      setPanelError(error.message)
    } finally {
      setChatSending(false)
    }
  }
  async function loadOrchestrationTrace() {
    setOrchestrationRunData(await orchestrationRun(lastOrchestrationRunId).catch(() => null))
    setOrchestrationContextData(await orchestrationContext(lastOrchestrationRunId).catch(() => null))
    setOrchestrationResponseData(await orchestrationResponse(lastOrchestrationRunId).catch(() => null))
    setOrchestrationIssuesData(await orchestrationIssues(lastOrchestrationRunId).catch(() => null))
  }

  async function runCreateSummary() {
    try { await createConversationSummary(selectedSessionId); setPanelError(''); await loadSessionDetail(selectedSessionId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runValidateSummary(id) {
    try { await validateConversationSummary(id); setPanelError(''); await loadSessionDetail(selectedSessionId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runAcceptSummary(id) {
    try { await acceptConversationSummary(id); setPanelError(''); await loadSessionDetail(selectedSessionId) }
    catch (error) { setPanelError(error.message) }
  }

  async function submitConsent(event) {
    event.preventDefault()
    try { await createMemoryConsent(consentForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runRevokeConsent(id) {
    try { await revokeMemoryConsent(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function runExpireConsent(id) {
    try { await expireMemoryConsent(id); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }

  async function loadMemoryItems() {
    setItems(await memoryItems(participantFilter || undefined).catch(() => ({ items: [] })))
  }
  async function submitMemory(event) {
    event.preventDefault()
    try {
      const body = { ...memoryForm }
      if (!body.consent_public_id) delete body.consent_public_id
      await createMemoryItem(body)
      setPanelError('')
      await loadMemoryItems()
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function selectMemory(id) {
    setSelectedMemoryId(id)
    setVersions(await memoryItemVersions(id).catch(() => ({ items: [] })))
    setEvents(await memoryItemEvents(id).catch(() => ({ items: [] })))
  }
  async function runConfirmMemory(id) {
    try { await confirmMemoryItem(id); setPanelError(''); await loadMemoryItems() }
    catch (error) { setPanelError(error.message) }
  }
  async function runRejectMemory(id) {
    try { await rejectMemoryItem(id); setPanelError(''); await loadMemoryItems() }
    catch (error) { setPanelError(error.message) }
  }
  async function runCorrectMemory() {
    try {
      await correctMemoryItem(selectedMemoryId, correctionForm)
      setPanelError('')
      await selectMemory(selectedMemoryId)
      await loadMemoryItems()
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runExpireMemory(id) {
    try { await expireMemoryItem(id); setPanelError(''); await loadMemoryItems() }
    catch (error) { setPanelError(error.message) }
  }
  async function runDeleteMemory(id) {
    try { await deleteMemoryItem(id); setPanelError(''); await loadMemoryItems() }
    catch (error) { setPanelError(error.message) }
  }

  async function submitRetrievalProfile(event) {
    event.preventDefault()
    try {
      const created = await createMemoryRetrievalProfile({ name: `profile-${Date.now()}` })
      await validateMemoryRetrievalProfile(created.public_id)
      await activateMemoryRetrievalProfile(created.public_id)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runRetrieve(event) {
    event.preventDefault()
    try { setRetrieveResult(await retrieveMemory(retrieveForm)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  async function submitSuite(event) {
    event.preventDefault()
    try { await createMemoryEvaluationSuite(suiteForm); setPanelError(''); await load() }
    catch (error) { setPanelError(error.message) }
  }
  async function submitFixture(event) {
    event.preventDefault()
    try {
      const ids = fixtureForm.expected_retrieved_memory_ids.split(',').map((id) => id.trim()).filter(Boolean)
      await addMemoryEvaluationFixture(selectedSuiteId, { ...fixtureForm, expected_retrieved_memory_ids: ids })
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runEvaluation() {
    try {
      const run = await createMemoryEvaluationRun(selectedSuiteId, { retrieval_profile_public_id: retrieveForm.retrieval_profile_public_id })
      const executed = await executeMemoryEvaluationRun(run.public_id)
      setEvaluationRunResult(executed)
      setEvaluationMetricsData(await memoryEvaluationMetrics(run.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateManifest() {
    try { setManifestResult(await generateMemoryManifest(selectedPolicyId)); setManifestVerification(null); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runVerifyManifest() {
    try { setManifestVerification(await verifyMemoryManifest(selectedPolicyId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  if (state.loading) return <section className="notice">Loading conversation and memory workspace…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Conversation &amp; Memory</h2>
          <p className="notice">{PRIVACY_NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Conversation and memory sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Sessions</h3>
          {(state.sessions ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => openSession(item.public_id)}>
              <strong>{item.session_mode}</strong>
              <span>{item.status}</span>
            </button>
          ))}
          <h3>Memory Policies</h3>
          {(state.policies ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => setSelectedPolicyId(item.public_id)}>
              <strong>{item.name}</strong>
              <span>{item.lifecycle_status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="Memory policies" value={state.policies.length} tone="neutral" />
                <StatusCard label="Sessions" value={state.sessions.length} tone="neutral" />
                <StatusCard label="Consents" value={state.consents.length} tone="neutral" />
                <StatusCard label="Retrieval profiles" value={state.profiles.length} tone="neutral" />
                <StatusCard label="Public chat" value="placeholder" tone="good" />
              </div>
              {sessionDetail && (
                <div className="metric-grid">
                  <StatusCard label="Session mode" value={sessionDetail.session_mode} tone="neutral" />
                  <StatusCard label="Session status" value={sessionDetail.status} tone="neutral" />
                  <StatusCard label="Recent turns" value={turns.items?.length ?? 0} tone="neutral" />
                  <StatusCard label="Active memory items" value={items.items?.filter((i) => i.status === 'active').length ?? 0} tone="neutral" />
                </div>
              )}
            </>
          )}

          {tab === 'Memory Policies' && (
            <>
              <form className="inline-form training-form" onSubmit={submitPolicy}>
                <h3>Create memory policy</h3>
                <label>Name<input value={policyForm.name} onChange={(e) => setPolicyForm({ ...policyForm, name: e.target.value })} /></label>
                <label>Default session mode
                  <select value={policyForm.default_session_mode} onChange={(e) => setPolicyForm({ ...policyForm, default_session_mode: e.target.value })}>
                    <option value="private_no_persist">private_no_persist</option>
                    <option value="stateless">stateless</option>
                    <option value="session_memory">session_memory</option>
                    <option value="consented_memory">consented_memory</option>
                  </select>
                </label>
                <label><input type="checkbox" checked={policyForm.allow_long_term_memory} onChange={(e) => setPolicyForm({ ...policyForm, allow_long_term_memory: e.target.checked })} /> Allow long-term memory</label>
                <button type="submit">Create policy</button>
              </form>
              <div className="data-list">
                {(state.policies ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong> — {item.default_session_mode}, {item.lifecycle_status}
                    <div className="inline-form">
                      {item.lifecycle_status === 'draft' && <button onClick={() => runValidatePolicy(item.public_id)}>Validate</button>}
                      {item.lifecycle_status === 'validated' && <button onClick={() => runActivatePolicy(item.public_id)}>Activate</button>}
                      <button onClick={() => setSelectedPolicyId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Sessions' && (
            <>
              <form className="inline-form training-form" onSubmit={submitSession}>
                <h3>Create session</h3>
                <label>Mode
                  <select value={sessionForm.session_mode} onChange={(e) => setSessionForm((prev) => ({ ...prev, session_mode: e.target.value }))}>
                    <option value="private_no_persist">private_no_persist</option>
                    <option value="stateless">stateless</option>
                    <option value="session_memory">session_memory</option>
                    <option value="consented_memory">consented_memory</option>
                  </select>
                </label>
                <label>Memory policy public ID<input value={sessionForm.memory_policy_public_id} onChange={(e) => setSessionForm((prev) => ({ ...prev, memory_policy_public_id: e.target.value }))} /></label>
                <label>Participant scope key<input value={sessionForm.participant_scope_key} onChange={(e) => setSessionForm((prev) => ({ ...prev, participant_scope_key: e.target.value }))} /></label>
                <label>Inference assignment public ID (optional)<input value={sessionForm.model_assignment_public_id} onChange={(e) => setSessionForm((prev) => ({ ...prev, model_assignment_public_id: e.target.value }))} /></label>
                <label>RAG retrieval profile public ID (optional)<input value={sessionForm.rag_retrieval_profile_public_id} onChange={(e) => setSessionForm((prev) => ({ ...prev, rag_retrieval_profile_public_id: e.target.value }))} /></label>
                <button type="submit">Create session</button>
              </form>
              {sessionDetail && (
                <>
                  <h3>Selected session: {sessionDetail.session_mode} / {sessionDetail.status}</h3>
                  <div className="inline-form">
                    <button onClick={runPause}>Pause</button>
                    <button onClick={runResume}>Resume</button>
                    <button onClick={runClose}>Close</button>
                    <button onClick={runExpire}>Expire</button>
                  </div>
                  <Pre value={sessionDetail} />
                </>
              )}
            </>
          )}

          {tab === 'Session Turns' && (
            <>
              <p className="notice">Private sessions never persist raw turn content -- only checksums and token counts.</p>
              <div className="data-list">
                {(turns.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>#{item.sequence_number} {item.role}</strong> — {item.stored_content ?? '(not persisted)'}
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Summaries' && (
            <>
              <button onClick={runCreateSummary}>Create summary from current session</button>
              <div className="data-list">
                {(summaries.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.public_id.slice(0, 8)}</strong> — {item.status}
                    <div className="inline-form">
                      <button onClick={() => runValidateSummary(item.public_id)}>Validate</button>
                      <button onClick={() => runAcceptSummary(item.public_id)}>Accept</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Consent' && (
            <>
              <form className="inline-form training-form" onSubmit={submitConsent}>
                <h3>Grant consent</h3>
                <label>Participant scope key<input value={consentForm.participant_scope_key} onChange={(e) => setConsentForm({ ...consentForm, participant_scope_key: e.target.value })} /></label>
                <label>Memory policy public ID<input value={consentForm.memory_policy_public_id} onChange={(e) => setConsentForm({ ...consentForm, memory_policy_public_id: e.target.value })} /></label>
                <label>Purpose<input value={consentForm.purpose} onChange={(e) => setConsentForm({ ...consentForm, purpose: e.target.value })} /></label>
                <button type="submit">Grant consent</button>
              </form>
              <div className="data-list">
                {(state.consents ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.purpose}</strong> — {item.participant_scope_key}, {item.status}
                    <div className="inline-form">
                      <button onClick={() => runRevokeConsent(item.public_id)}>Revoke</button>
                      <button onClick={() => runExpireConsent(item.public_id)}>Expire</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Memory Items' && (
            <>
              <form className="inline-form training-form" onSubmit={submitMemory}>
                <h3>Propose memory item</h3>
                <label>Participant scope key<input value={memoryForm.participant_scope_key} onChange={(e) => setMemoryForm({ ...memoryForm, participant_scope_key: e.target.value })} /></label>
                <label>Category
                  <select value={memoryForm.category} onChange={(e) => setMemoryForm({ ...memoryForm, category: e.target.value })}>
                    <option value="language_preference">language_preference</option>
                    <option value="format_preference">format_preference</option>
                    <option value="confirmed_name_or_alias">confirmed_name_or_alias</option>
                    <option value="learning_goal">learning_goal</option>
                    <option value="course_progress">course_progress</option>
                    <option value="project_preference">project_preference</option>
                    <option value="user_confirmed_fact">user_confirmed_fact</option>
                    <option value="conversation_follow_up">conversation_follow_up</option>
                  </select>
                </label>
                <label>Purpose<input value={memoryForm.purpose} onChange={(e) => setMemoryForm({ ...memoryForm, purpose: e.target.value })} /></label>
                <label>Creation source
                  <select value={memoryForm.creation_source} onChange={(e) => setMemoryForm({ ...memoryForm, creation_source: e.target.value })}>
                    <option value="explicit_user_request">explicit_user_request</option>
                    <option value="admin_created_for_test">admin_created_for_test</option>
                    <option value="assistant_proposed">assistant_proposed</option>
                    <option value="system_derived">system_derived</option>
                  </select>
                </label>
                <label>Confidence type
                  <select value={memoryForm.confidence_type} onChange={(e) => setMemoryForm({ ...memoryForm, confidence_type: e.target.value })}>
                    <option value="user_confirmed">user_confirmed</option>
                    <option value="admin_test_fixture">admin_test_fixture</option>
                    <option value="deterministically_extracted">deterministically_extracted</option>
                    <option value="assistant_inferred">assistant_inferred</option>
                  </select>
                </label>
                <label>Value<input value={memoryForm.display_value} onChange={(e) => setMemoryForm({ ...memoryForm, display_value: e.target.value })} /></label>
                <label>Consent public ID (if required)<input value={memoryForm.consent_public_id} onChange={(e) => setMemoryForm({ ...memoryForm, consent_public_id: e.target.value })} /></label>
                <button type="submit">Propose memory</button>
              </form>
              <div className="inline-form">
                <label>Filter by participant<input value={participantFilter} onChange={(e) => setParticipantFilter(e.target.value)} /></label>
                <button onClick={loadMemoryItems}>Load memory items</button>
              </div>
              <div className="data-list">
                {(items.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.category}</strong> — {item.purpose}, {item.status} ({item.confidence_type})
                    <div className="inline-form">
                      <button onClick={() => selectMemory(item.public_id)}>Select</button>
                      {item.status === 'awaiting_confirmation' && <button onClick={() => runConfirmMemory(item.public_id)}>Confirm</button>}
                      {item.status === 'awaiting_confirmation' && <button onClick={() => runRejectMemory(item.public_id)}>Reject</button>}
                      <button onClick={() => runExpireMemory(item.public_id)}>Expire</button>
                      <button onClick={() => runDeleteMemory(item.public_id)}>Delete</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Memory Versions' && (
            <>
              {!selectedMemoryId && <p className="notice">Select a memory item from the Memory Items tab.</p>}
              {selectedMemoryId && (
                <>
                  <form className="inline-form training-form" onSubmit={(e) => { e.preventDefault(); runCorrectMemory() }}>
                    <h4>Correct memory (creates a new immutable version)</h4>
                    <label>New value<input value={correctionForm.display_value} onChange={(e) => setCorrectionForm({ ...correctionForm, display_value: e.target.value })} /></label>
                    <label>Reason<input value={correctionForm.change_reason} onChange={(e) => setCorrectionForm({ ...correctionForm, change_reason: e.target.value })} /></label>
                    <button type="submit">Correct</button>
                  </form>
                  <div className="data-list">
                    {(versions.items ?? []).map((item) => (
                      <article key={item.public_id}>v{item.version_number}: {item.display_value} — {item.change_reason}</article>
                    ))}
                  </div>
                  <h4>Events</h4>
                  <div className="data-list">
                    {(events.items ?? []).map((item) => <article key={item.public_id}>{item.event_type} — {item.created_at}</article>)}
                  </div>
                </>
              )}
            </>
          )}

          {tab === 'Memory Retrieval' && (
            <>
              <button onClick={submitRetrievalProfile}>Create + activate a retrieval profile</button>
              <form className="inline-form training-form" onSubmit={runRetrieve}>
                <label>Retrieval profile public ID<input value={retrieveForm.retrieval_profile_public_id} onChange={(e) => setRetrieveForm({ ...retrieveForm, retrieval_profile_public_id: e.target.value })} /></label>
                <label>Participant scope key<input value={retrieveForm.participant_scope_key} onChange={(e) => setRetrieveForm({ ...retrieveForm, participant_scope_key: e.target.value })} /></label>
                <label>Query<input value={retrieveForm.query} onChange={(e) => setRetrieveForm({ ...retrieveForm, query: e.target.value })} /></label>
                <button type="submit">Retrieve</button>
              </form>
              <Pre value={retrieveResult} />
            </>
          )}

          {tab === 'Context Orchestration' && (
            <>
              <p className="notice">Send a message in the Grounded Conversation Lab tab, then inspect its trace here.</p>
              <button onClick={loadOrchestrationTrace}>Load latest orchestration trace</button>
              <h4>Run (status, runtime)</h4>
              <Pre value={orchestrationRunData} />
              <h4>Context assembly</h4>
              <Pre value={orchestrationContextData} />
              <h4>Response</h4>
              <Pre value={orchestrationResponseData} />
              <h4>Issues</h4>
              <Pre value={orchestrationIssuesData} />
            </>
          )}

          {tab === 'Grounded Conversation Lab' && (
            <>
              <p className="notice">{LAB_DISCLAIMER}</p>
              {!selectedSessionId && <p className="notice">Select or create a session first.</p>}
              {selectedSessionId && (
                <>
                  <div className="data-list">
                    {chatHistory.map((turn, index) => (
                      <article key={index}>
                        <strong>{turn.role}:</strong> {turn.text} {turn.status && <em>({turn.status})</em>}
                        {turn.citations && turn.citations.length > 0 && (
                          <ul>
                            {turn.citations.map((citation) => (
                              <li key={citation.public_id}>
                                [{citation.rank}] {citation.citation_label} · {citation.evidence_type} · {citation.validation_status}
                              </li>
                            ))}
                          </ul>
                        )}
                      </article>
                    ))}
                    {chatSending && <div className="notice">Waiting for a response…</div>}
                    <div ref={chatEndRef} />
                  </div>
                  <form className="inline-form training-form" onSubmit={sendMessage}>
                    <label>Message<input value={chatMessage} onChange={(e) => setChatMessage(e.target.value)} disabled={chatSending} /></label>
                    <button type="submit" disabled={chatSending || !chatMessage}>{chatSending ? 'Sending…' : 'Send'}</button>
                  </form>
                </>
              )}
            </>
          )}

          {tab === 'Privacy & Deletion' && (
            <>
              <p className="notice">{PRIVACY_NOTICE}</p>
              <p className="notice">Deleted, expired, or revoked memory is immediately excluded from all future retrieval -- retrieval always re-reads live status, so there is no separate cache to invalidate.</p>
              <div className="data-list">
                {(items.items ?? []).filter((i) => i.status === 'active').map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.category}</strong> — {item.purpose}
                    <div className="inline-form">
                      <button onClick={() => runExpireMemory(item.public_id)}>Expire</button>
                      <button onClick={() => runDeleteMemory(item.public_id)}>Delete</button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Evaluation' && (
            <>
              <form className="inline-form training-form" onSubmit={submitSuite}>
                <h3>Create evaluation suite</h3>
                <label>Name<input value={suiteForm.name} onChange={(e) => setSuiteForm({ ...suiteForm, name: e.target.value })} /></label>
                <button type="submit">Create suite</button>
              </form>
              <div className="data-list">
                {(state.suites ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong>
                    <button onClick={() => setSelectedSuiteId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                  </article>
                ))}
              </div>
              {selectedSuiteId && (
                <>
                  <form className="inline-form training-form" onSubmit={submitFixture}>
                    <h4>Add fixture (known relevant memory IDs only)</h4>
                    <label>Participant scope key<input value={fixtureForm.participant_scope_key} onChange={(e) => setFixtureForm({ ...fixtureForm, participant_scope_key: e.target.value })} /></label>
                    <label>Query<input value={fixtureForm.query} onChange={(e) => setFixtureForm({ ...fixtureForm, query: e.target.value })} /></label>
                    <label>Expected relevant memory IDs (comma separated)<input value={fixtureForm.expected_retrieved_memory_ids} onChange={(e) => setFixtureForm({ ...fixtureForm, expected_retrieved_memory_ids: e.target.value })} /></label>
                    <button type="submit">Add fixture</button>
                  </form>
                  <button onClick={runEvaluation}>Run evaluation</button>
                  <Pre value={evaluationRunResult} />
                  {(evaluationMetricsData.items ?? []).map((item) => (
                    <article key={item.public_id}>{item.metric_scope}/{item.metric_name}: {item.metric_value}</article>
                  ))}
                </>
              )}
            </>
          )}

          {tab === 'Reproducibility' && (
            <>
              <p className="notice">The conversation-memory manifest never includes raw messages, raw memory values, secrets, or paths -- checksums and configuration only.</p>
              <div className="inline-form">
                <button onClick={runGenerateManifest}>Generate/view manifest</button>
                <button onClick={runVerifyManifest}>Verify checksum</button>
              </div>
              <Pre value={manifestResult} />
              <Pre value={manifestVerification} />
            </>
          )}
        </section>
      </div>
    </section>
  )
}
