import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  activateAssignment,
  approveAssignment,
  assessRuntimeCompatibility,
  assignment as fetchAssignment,
  assignmentEvents,
  assignmentScopes,
  assignments,
  assignmentVersions,
  canaryResults,
  closeChatLabSession,
  createAssignment,
  createChatLabSession,
  createRuntimeInstance,
  createRuntimeProfile,
  runtimeDiagnosticGenerate,
  executeCanary,
  loadRuntimeInstance,
  pauseAssignment,
  postChatLabMessage,
  resumeAssignment,
  rollbackExecute,
  rollbackPreview,
  runtimeCompatibility,
  runtimeInstance,
  runtimeInstanceHealthCheck,
  runtimeInstances,
  runtimeManifest,
  runtimeProfiles,
  startCanary,
  startRuntimeInstance,
  stopCanary,
  stopRuntimeInstance,
  unloadRuntimeInstance,
  validateAssignment,
  verifyRuntimeManifest,
} from '../services/api.js'

const RUNTIME_NOTICE = 'Loading a model into the inference runtime does not automatically make it available to the public chatbot.'
const DIAGNOSTIC_NOTICE = 'Admin-only bounded diagnostic generation. This is not the public chatbot.'
const PUBLIC_ACTIVATION_NOTICE = 'Public-chat activation requires an eligible release, passing evaluation evidence, runtime health, canary success, approvals, and rollback readiness.'

const TABS = [
  'Overview', 'Runtime Profiles', 'Runtime Instances', 'Compatibility', 'Assignments',
  'Assignment Versions', 'Admin Diagnostic', 'Admin Chat Lab', 'Canary', 'Health',
  'Usage and Failures', 'Rollback', 'Runtime Manifest',
]

function Pre({ value }) {
  if (!value) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

export default function InferenceRuntimePage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', profiles: [], instances: [], assignments: [], scopes: [] })
  const [panelError, setPanelError] = useState('')

  const [profileForm, setProfileForm] = useState({ name: '', maximum_context_length: 512, maximum_new_tokens: 64, minimum_available_memory_bytes: 0, minimum_available_disk_bytes: 0 })
  const [selectedProfileId, setSelectedProfileId] = useState('')

  const [selectedInstanceId, setSelectedInstanceId] = useState('')
  const [instanceDetail, setInstanceDetail] = useState(null)
  const [loadReleaseId, setLoadReleaseId] = useState('')
  const [healthResult, setHealthResult] = useState(null)

  const [compatReleaseId, setCompatReleaseId] = useState('')
  const [compatResult, setCompatResult] = useState(null)

  const [assignmentForm, setAssignmentForm] = useState({ scope: 'admin_diagnostic', release_public_id: '', runtime_profile_public_id: '' })
  const [selectedAssignmentId, setSelectedAssignmentId] = useState('')
  const [assignmentDetail, setAssignmentDetail] = useState(null)
  const [versions, setVersions] = useState({ items: [] })
  const [events, setEvents] = useState({ items: [] })
  const [approvalForm, setApprovalForm] = useState({ role: 'release', decision: 'approve', comment: '' })
  const [validationResult, setValidationResult] = useState(null)
  const [activationResult, setActivationResult] = useState(null)

  const [diagnosticPrompt, setDiagnosticPrompt] = useState('')
  const [diagnosticResult, setDiagnosticResult] = useState(null)

  const [chatSessionId, setChatSessionId] = useState('')
  const [chatMessage, setChatMessage] = useState('')
  const [chatHistory, setChatHistory] = useState([])

  const [canaryPrompts, setCanaryPrompts] = useState('hello\nhow are you\nwhat can you do')
  const [canaryResult, setCanaryResult] = useState(null)
  const [canaryRuns, setCanaryRuns] = useState({ items: [] })

  const [rollbackTargetVersion, setRollbackTargetVersion] = useState('')
  const [rollbackResult, setRollbackResult] = useState(null)

  const [manifestResult, setManifestResult] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [profiles, instances, assignmentList, scopes] = await Promise.all([
        runtimeProfiles(), runtimeInstances(), assignments(), assignmentScopes(),
      ])
      setState({
        loading: false, error: '',
        profiles: profiles.items ?? [], instances: instances.items ?? [],
        assignments: assignmentList.items ?? [], scopes: scopes.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function submitProfile(event) {
    event.preventDefault()
    try {
      await createRuntimeProfile({
        ...profileForm,
        maximum_context_length: Number(profileForm.maximum_context_length),
        maximum_new_tokens: Number(profileForm.maximum_new_tokens),
        minimum_available_memory_bytes: Number(profileForm.minimum_available_memory_bytes),
        minimum_available_disk_bytes: Number(profileForm.minimum_available_disk_bytes),
      })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function createInstanceForProfile() {
    try {
      await createRuntimeInstance(selectedProfileId)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadInstanceDetail(id) {
    setSelectedInstanceId(id)
    setHealthResult(null)
    setInstanceDetail(await runtimeInstance(id).catch(() => null))
  }

  async function runStart() {
    try { await startRuntimeInstance(selectedInstanceId); setPanelError(''); await loadInstanceDetail(selectedInstanceId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runStop() {
    try { await stopRuntimeInstance(selectedInstanceId); setPanelError(''); await loadInstanceDetail(selectedInstanceId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runLoad() {
    try { await loadRuntimeInstance(selectedInstanceId, loadReleaseId); setPanelError(''); await loadInstanceDetail(selectedInstanceId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runUnload() {
    try { await unloadRuntimeInstance(selectedInstanceId); setPanelError(''); await loadInstanceDetail(selectedInstanceId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runHealthCheck() {
    try { setHealthResult(await runtimeInstanceHealthCheck(selectedInstanceId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  async function runAssessCompatibility() {
    try { setCompatResult(await assessRuntimeCompatibility(compatReleaseId, selectedProfileId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runGetCompatibility() {
    setCompatResult(await runtimeCompatibility(compatReleaseId).catch(() => null))
  }

  async function submitAssignment(event) {
    event.preventDefault()
    try {
      await createAssignment(assignmentForm)
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function loadAssignmentDetail(id) {
    setSelectedAssignmentId(id)
    setAssignmentDetail(await fetchAssignment(id).catch(() => null))
    setVersions(await assignmentVersions(id).catch(() => ({ items: [] })))
    setEvents(await assignmentEvents(id).catch(() => ({ items: [] })))
  }

  async function runValidate() {
    try { setValidationResult(await validateAssignment(selectedAssignmentId)); setPanelError(''); await loadAssignmentDetail(selectedAssignmentId) }
    catch (error) { setPanelError(error.message) }
  }
  async function submitApproval(event) {
    event.preventDefault()
    try { await approveAssignment(selectedAssignmentId, approvalForm); setPanelError(''); await loadAssignmentDetail(selectedAssignmentId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runActivate(confirmed) {
    try {
      const result = await activateAssignment(selectedAssignmentId, confirmed)
      setActivationResult(result)
      setPanelError('')
      await loadAssignmentDetail(selectedAssignmentId)
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runPause() {
    try { await pauseAssignment(selectedAssignmentId); setPanelError(''); await loadAssignmentDetail(selectedAssignmentId) }
    catch (error) { setPanelError(error.message) }
  }
  async function runResume() {
    try { await resumeAssignment(selectedAssignmentId); setPanelError(''); await loadAssignmentDetail(selectedAssignmentId) }
    catch (error) { setPanelError(error.message) }
  }

  async function runDiagnostic(event) {
    event.preventDefault()
    try { setDiagnosticResult(await runtimeDiagnosticGenerate(selectedAssignmentId, { prompt: diagnosticPrompt })); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  async function openChatSession() {
    try {
      const session = await createChatLabSession(selectedAssignmentId, { max_turns: 10 })
      setChatSessionId(session.public_id)
      setChatHistory([])
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function sendChatMessage(event) {
    event.preventDefault()
    try {
      const result = await postChatLabMessage(chatSessionId, chatMessage)
      setChatHistory((old) => [...old, { role: 'user', text: chatMessage }, { role: 'assistant', text: result.generated_text }])
      setChatMessage('')
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function closeChat() {
    try { await closeChatLabSession(chatSessionId); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  async function runStartCanary() {
    try { await startCanary(selectedAssignmentId, { percentage: 100, max_request_count: 20 }); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runExecuteCanary() {
    try {
      const prompts = canaryPrompts.split('\n').map((line) => line.trim()).filter(Boolean)
      setCanaryResult(await executeCanary(selectedAssignmentId, prompts))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }
  async function runStopCanary() {
    try { await stopCanary(selectedAssignmentId); setPanelError(''); setCanaryRuns(await canaryResults(selectedAssignmentId)) }
    catch (error) { setPanelError(error.message) }
  }
  async function loadCanaryResults() {
    setCanaryRuns(await canaryResults(selectedAssignmentId).catch(() => ({ items: [] })))
  }

  async function runRollbackPreview() {
    try { setRollbackResult(await rollbackPreview(selectedAssignmentId, rollbackTargetVersion)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runRollbackExecute() {
    try { setRollbackResult(await rollbackExecute(selectedAssignmentId, rollbackTargetVersion)); setPanelError(''); await loadAssignmentDetail(selectedAssignmentId) }
    catch (error) { setPanelError(error.message) }
  }

  async function runGenerateManifest() {
    try { setManifestResult(await runtimeManifest(selectedAssignmentId)); setManifestVerification(null); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }
  async function runVerifyManifest() {
    try { setManifestVerification(await verifyRuntimeManifest(selectedAssignmentId)); setPanelError('') }
    catch (error) { setPanelError(error.message) }
  }

  if (state.loading) return <section className="notice">Loading inference runtime…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Controlled Inference Runtime</h2>
          <p className="notice">{RUNTIME_NOTICE}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Inference runtime sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Assignments</h3>
          {(state.assignments ?? []).length === 0 && <article>No assignments yet.</article>}
          {(state.assignments ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadAssignmentDetail(item.public_id)}>
              <strong>{item.scope_key}</strong>
              <span>{item.status}</span>
            </button>
          ))}
          <h3>Runtime Instances</h3>
          {(state.instances ?? []).map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadInstanceDetail(item.public_id)}>
              <strong>{item.public_id.slice(0, 8)}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <h3>Overview</h3>
              <div className="metric-grid">
                <StatusCard label="Runtime profiles" value={state.profiles.length} tone="neutral" />
                <StatusCard label="Runtime instances" value={state.instances.length} tone="neutral" />
                <StatusCard label="Assignments" value={state.assignments.length} tone="neutral" />
                <StatusCard label="Public chat" value="placeholder" tone="good" />
              </div>
              <p className="notice">{PUBLIC_ACTIVATION_NOTICE}</p>
              {assignmentDetail && (
                <div className="metric-grid">
                  <StatusCard label="Assignment scope" value={assignmentDetail.scope_key} tone="neutral" />
                  <StatusCard label="Assignment status" value={assignmentDetail.status} tone="neutral" />
                  <StatusCard label="Release" value={assignmentDetail.release_public_id?.slice(0, 8)} tone="neutral" />
                  <StatusCard label="Fallback policy" value={JSON.stringify(assignmentDetail.fallback_policy ?? {})} tone="neutral" />
                </div>
              )}
            </>
          )}

          {tab === 'Runtime Profiles' && (
            <>
              <form className="inline-form training-form" onSubmit={submitProfile}>
                <h3>Create runtime profile (local CPU, float32)</h3>
                <label>Name<input value={profileForm.name} onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })} /></label>
                <label>Max context length<input type="number" value={profileForm.maximum_context_length} onChange={(e) => setProfileForm({ ...profileForm, maximum_context_length: e.target.value })} /></label>
                <label>Max new tokens<input type="number" value={profileForm.maximum_new_tokens} onChange={(e) => setProfileForm({ ...profileForm, maximum_new_tokens: e.target.value })} /></label>
                <label>Min available memory bytes<input type="number" value={profileForm.minimum_available_memory_bytes} onChange={(e) => setProfileForm({ ...profileForm, minimum_available_memory_bytes: e.target.value })} /></label>
                <label>Min available disk bytes<input type="number" value={profileForm.minimum_available_disk_bytes} onChange={(e) => setProfileForm({ ...profileForm, minimum_available_disk_bytes: e.target.value })} /></label>
                <button type="submit">Create profile</button>
              </form>
              <div className="data-list">
                {(state.profiles ?? []).map((item) => (
                  <article key={item.public_id}>
                    <strong>{item.name}</strong> — {item.runtime_type}/{item.dtype}, context {item.maximum_context_length}, new tokens {item.maximum_new_tokens}
                    <div className="inline-form">
                      <button onClick={() => setSelectedProfileId(item.public_id)}>Select ({item.public_id.slice(0, 8)})</button>
                    </div>
                  </article>
                ))}
              </div>
              {selectedProfileId && (
                <div className="inline-form">
                  <span>Selected profile: {selectedProfileId.slice(0, 8)}</span>
                  <button onClick={createInstanceForProfile}>Create instance for this profile</button>
                </div>
              )}
            </>
          )}

          {tab === 'Runtime Instances' && (
            <>
              <h3>Runtime instance detail</h3>
              {!instanceDetail && <p className="notice">Select an instance from the list on the left.</p>}
              {instanceDetail && (
                <>
                  <div className="metric-grid">
                    <StatusCard label="Status" value={instanceDetail.status} tone={instanceDetail.status === 'ready' ? 'good' : 'neutral'} />
                    <StatusCard label="Loaded release" value={instanceDetail.loaded_release_public_id?.slice(0, 8) ?? 'none'} tone="neutral" />
                  </div>
                  <div className="inline-form">
                    <button onClick={runStart}>Start</button>
                    <button onClick={runStop}>Stop</button>
                    <button onClick={runUnload}>Unload</button>
                    <button onClick={runHealthCheck}>Run health check</button>
                  </div>
                  <div className="inline-form">
                    <label>Release public ID to load<input value={loadReleaseId} onChange={(e) => setLoadReleaseId(e.target.value)} /></label>
                    <button onClick={runLoad}>Load model</button>
                  </div>
                  <Pre value={healthResult} />
                </>
              )}
            </>
          )}

          {tab === 'Compatibility' && (
            <>
              <h3>Release/runtime compatibility</h3>
              <div className="inline-form">
                <label>Release public ID<input value={compatReleaseId} onChange={(e) => setCompatReleaseId(e.target.value)} /></label>
                <label>Runtime profile public ID<input value={selectedProfileId} onChange={(e) => setSelectedProfileId(e.target.value)} /></label>
                <button onClick={runAssessCompatibility}>Assess compatibility</button>
                <button onClick={runGetCompatibility}>View latest</button>
              </div>
              <Pre value={compatResult} />
            </>
          )}

          {tab === 'Assignments' && (
            <>
              <form className="inline-form training-form" onSubmit={submitAssignment}>
                <h3>Create assignment</h3>
                <label>Scope
                  <select value={assignmentForm.scope} onChange={(e) => setAssignmentForm({ ...assignmentForm, scope: e.target.value })}>
                    <option value="admin_diagnostic">admin_diagnostic</option>
                    <option value="admin_chat_lab">admin_chat_lab</option>
                    <option value="internal_canary">internal_canary</option>
                    <option value="public_chat">public_chat (disabled by default)</option>
                  </select>
                </label>
                <label>Release public ID<input value={assignmentForm.release_public_id} onChange={(e) => setAssignmentForm({ ...assignmentForm, release_public_id: e.target.value })} /></label>
                <label>Runtime profile public ID<input value={assignmentForm.runtime_profile_public_id} onChange={(e) => setAssignmentForm({ ...assignmentForm, runtime_profile_public_id: e.target.value })} /></label>
                <button type="submit">Create assignment</button>
              </form>

              {assignmentDetail && (
                <>
                  <h3>Selected assignment: {assignmentDetail.scope_key} / {assignmentDetail.status}</h3>
                  <div className="inline-form">
                    <button onClick={runValidate}>Validate</button>
                    <button onClick={() => runActivate(false)}>Activate</button>
                    <button onClick={runPause}>Pause</button>
                    <button onClick={runResume}>Resume</button>
                  </div>
                  <Pre value={validationResult} />
                  <Pre value={activationResult} />
                  <form className="inline-form training-form" onSubmit={submitApproval}>
                    <h4>Record approval</h4>
                    <label>Role
                      <select value={approvalForm.role} onChange={(e) => setApprovalForm({ ...approvalForm, role: e.target.value })}>
                        <option value="technical">technical</option>
                        <option value="evaluation">evaluation</option>
                        <option value="security">security</option>
                        <option value="release">release</option>
                      </select>
                    </label>
                    <label>Decision
                      <select value={approvalForm.decision} onChange={(e) => setApprovalForm({ ...approvalForm, decision: e.target.value })}>
                        <option value="approve">approve</option>
                        <option value="approve_with_warning">approve_with_warning</option>
                        <option value="reject">reject</option>
                        <option value="request_changes">request_changes</option>
                      </select>
                    </label>
                    <label>Comment<input value={approvalForm.comment} onChange={(e) => setApprovalForm({ ...approvalForm, comment: e.target.value })} /></label>
                    <button type="submit">Submit approval</button>
                  </form>
                  {assignmentDetail.scope_key === 'public_chat' && (
                    <>
                      <div className="notice error-notice">{PUBLIC_ACTIVATION_NOTICE}</div>
                      <button onClick={() => runActivate(true)}>Activate with explicit confirmation</button>
                    </>
                  )}
                </>
              )}
            </>
          )}

          {tab === 'Assignment Versions' && (
            <>
              <h3>Assignment versions</h3>
              {(versions.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <strong>v{item.version_number}</strong> — release {item.release_public_id?.slice(0, 8) ?? item.public_id.slice(0, 8)}
                </article>
              ))}
              <h3>Assignment events</h3>
              {(events.items ?? []).map((item) => (
                <article key={item.public_id}>{item.event_type} — {item.created_at}</article>
              ))}
            </>
          )}

          {tab === 'Admin Diagnostic' && (
            <>
              <p className="notice">{DIAGNOSTIC_NOTICE}</p>
              <form className="inline-form training-form" onSubmit={runDiagnostic}>
                <label>Prompt<input value={diagnosticPrompt} onChange={(e) => setDiagnosticPrompt(e.target.value)} /></label>
                <button type="submit">Generate</button>
              </form>
              <Pre value={diagnosticResult} />
            </>
          )}

          {tab === 'Admin Chat Lab' && (
            <>
              <div className="inline-form">
                <button onClick={openChatSession}>Open chat-lab session</button>
                <button onClick={closeChat}>Close session</button>
              </div>
              {chatSessionId && (
                <>
                  <div className="data-list">
                    {chatHistory.map((turn, index) => <article key={index}><strong>{turn.role}:</strong> {turn.text}</article>)}
                  </div>
                  <form className="inline-form training-form" onSubmit={sendChatMessage}>
                    <label>Message<input value={chatMessage} onChange={(e) => setChatMessage(e.target.value)} /></label>
                    <button type="submit">Send</button>
                  </form>
                </>
              )}
            </>
          )}

          {tab === 'Canary' && (
            <>
              <h3>Internal canary (explicit fixture prompts, no public traffic)</h3>
              <div className="inline-form">
                <button onClick={runStartCanary}>Start canary</button>
                <button onClick={runStopCanary}>Stop canary</button>
                <button onClick={loadCanaryResults}>Load run history</button>
              </div>
              <label>Fixture prompts (one per line)
                <textarea value={canaryPrompts} onChange={(e) => setCanaryPrompts(e.target.value)} rows={4} />
              </label>
              <button onClick={runExecuteCanary}>Execute canary batch</button>
              <Pre value={canaryResult} />
              {(canaryRuns.items ?? []).map((run) => (
                <article key={run.public_id}>{run.run_status} — {run.requests_executed}/{run.max_request_count} requests</article>
              ))}
            </>
          )}

          {tab === 'Health' && instanceDetail && (
            <>
              <h3>Runtime health</h3>
              <Pre value={healthResult} />
              <button onClick={runHealthCheck}>Run health check</button>
            </>
          )}

          {tab === 'Usage and Failures' && (
            <>
              <h3>Usage and failures</h3>
              <p className="notice">Per-request usage and failure evidence is recorded append-only; use the Health and Canary tabs for aggregated rates.</p>
            </>
          )}

          {tab === 'Rollback' && (
            <>
              <h3>Assignment rollback</h3>
              <label>Target assignment version public ID<input value={rollbackTargetVersion} onChange={(e) => setRollbackTargetVersion(e.target.value)} /></label>
              <div className="inline-form">
                <button onClick={runRollbackPreview}>Preview rollback</button>
                <button onClick={runRollbackExecute}>Execute rollback</button>
              </div>
              <Pre value={rollbackResult} />
            </>
          )}

          {tab === 'Runtime Manifest' && (
            <>
              <h3>Runtime manifest</h3>
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
