import { useEffect, useState } from 'react'
import {
  addManualDiscoveryCandidate, cancelDiscoverySession, createDiscoveryComparison,
  createDiscoverySession, createVerificationCase, discoveryCandidate, discoveryCandidates,
  discoveryComparisons, discoveryEvents, discoveryProviderRuns, discoveryRequirements,
  discoverySession, discoverySessions, excludeDiscoveryCandidate, restoreDiscoveryCandidate,
  runDiscoverySearch, setDiscoveryRequirements, verificationCases,
} from '../services/api.js'

const TABS = ['Sessions', 'Requirement', 'Candidates', 'Comparison', 'History']

const MODALITIES = ['text', 'image', 'audio', 'video', 'multimodal']
const LANGUAGES = ['tamil', 'english', 'tanglish', 'mixed', 'other', 'unknown']
const TASKS = [
  'chat', 'language_modeling', 'instruction_tuning', 'question_answering', 'translation',
  'summarization', 'classification', 'ocr', 'asr', 'tts', 'vision', 'object_detection',
  'image_classification', 'video_understanding', 'multimodal_alignment', 'evaluation', 'other',
]
const INTENDED_USES = [
  'rag', 'training', 'evaluation', 'tokenizer', 'research', 'commercial_product', 'internal_testing',
]
const COMMERCIAL_REQUIREMENTS = ['required', 'preferred', 'not_required', 'unknown']

const SAFETY_NOTICE = 'Discovery only ever produces candidates for human review -- nothing here downloads a file, imports a dataset, or grants a licence, RAG, training, evaluation, or commercial-use approval. Provider search results and manually added candidates are treated identically: unknown licence stays unknown, a missing dataset card is shown as a warning, and every score is explainable.'

const emptyRequirement = {
  modality: 'text', languages: [], tasks: [], intended_uses: [], commercial_requirement: 'unknown',
  free_text_requirement: '', preferred_providers: '', excluded_providers: '',
}

const emptyManualCandidate = {
  canonical_name: '', organization: '', description: '', declared_licence: '',
  homepage_url: '', repository_url: '', dataset_card_url: '',
}

function toggleInList(list, value) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
}

function scoreLabel(score) {
  if (score === null || score === undefined) return 'not scored yet'
  return `${Math.round(score)}/100`
}

export default function DatasetDiscoveryPage({ onOpenVerification }) {
  const [tab, setTab] = useState('Sessions')
  const [sessions, setSessions] = useState([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [sessionTitle, setSessionTitle] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [selected, setSelected] = useState(null)
  const [requirement, setRequirement] = useState(emptyRequirement)
  const [candidates, setCandidates] = useState([])
  const [candidateDetail, setCandidateDetail] = useState(null)
  const [candidateVerificationCase, setCandidateVerificationCase] = useState(null)
  const [manualCandidate, setManualCandidate] = useState(emptyManualCandidate)
  const [compareIds, setCompareIds] = useState([])
  const [comparisons, setComparisons] = useState([])
  const [events, setEvents] = useState([])
  const [providerRuns, setProviderRuns] = useState([])

  function loadSessions() {
    discoverySessions('?page_size=100').then((data) => setSessions(data.items)).catch((reason) => setError(reason.message))
  }

  useEffect(() => { loadSessions() }, [])

  function selectSession(publicId) {
    setSelectedId(publicId)
    setSelected(null)
    setCandidates([])
    setCandidateDetail(null)
    setCompareIds([])
    setError(''); setNotice('')
    refreshSelected(publicId)
  }

  function refreshSelected(publicId = selectedId) {
    if (!publicId) return
    discoverySession(publicId).then(setSelected).catch((reason) => setError(reason.message))
    discoveryRequirements(publicId).then((data) => {
      if (data && data.public_id) {
        setRequirement({
          modality: data.modality, languages: data.languages, tasks: data.tasks,
          intended_uses: data.intended_uses, commercial_requirement: data.commercial_requirement,
          free_text_requirement: data.free_text_requirement,
          preferred_providers: (data.preferred_providers || []).join(', '),
          excluded_providers: (data.excluded_providers || []).join(', '),
        })
      }
    }).catch(() => {})
    discoveryCandidates(publicId).then((data) => setCandidates(data.items)).catch(() => {})
    discoveryComparisons(publicId).then((data) => setComparisons(data.items)).catch(() => {})
    discoveryEvents(publicId).then((data) => setEvents(data.items)).catch(() => {})
    discoveryProviderRuns(publicId).then((data) => setProviderRuns(data.items)).catch(() => {})
  }

  async function action(label, fn) {
    setBusy(label); setError(''); setNotice('')
    try {
      await fn()
      loadSessions()
      refreshSelected()
      setNotice(`${label}: done.`)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitSession(event) {
    event.preventDefault()
    setBusy('Create session'); setError('')
    try {
      const created = await createDiscoverySession({ title: sessionTitle })
      setSessionTitle('')
      loadSessions()
      selectSession(created.public_id)
      setNotice(`Session "${created.session_code}" created. Fill in the Requirement tab next.`)
      setTab('Requirement')
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  async function submitRequirement(event) {
    event.preventDefault()
    if (!selectedId) return
    const payload = {
      modality: requirement.modality, languages: requirement.languages, tasks: requirement.tasks,
      intended_uses: requirement.intended_uses, commercial_requirement: requirement.commercial_requirement,
      free_text_requirement: requirement.free_text_requirement,
      preferred_providers: requirement.preferred_providers.split(',').map((s) => s.trim()).filter(Boolean),
      excluded_providers: requirement.excluded_providers.split(',').map((s) => s.trim()).filter(Boolean),
    }
    action('Save requirement', () => setDiscoveryRequirements(selectedId, payload))
  }

  async function submitManualCandidate(event) {
    event.preventDefault()
    if (!selectedId) return
    action('Add manual candidate', async () => {
      await addManualDiscoveryCandidate(selectedId, manualCandidate)
      setManualCandidate(emptyManualCandidate)
    })
  }

  function openCandidateDetail(candidateId) {
    discoveryCandidate(candidateId).then(setCandidateDetail).catch((reason) => setError(reason.message))
    setCandidateVerificationCase(null)
    verificationCases(`?candidate_public_id=${candidateId}&page_size=1`)
      .then((data) => setCandidateVerificationCase(data.items[0] || null))
      .catch(() => {})
  }

  async function startLicenceVerification(candidateId) {
    setBusy('Start licence verification'); setError('')
    try {
      await createVerificationCase({ candidate_public_id: candidateId })
      onOpenVerification?.(candidateId)
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
  }

  function toggleCompare(candidateId) {
    setCompareIds((current) => toggleInList(current, candidateId))
  }

  const currentPage = <>
    <section className="intro">
      <div><span>Data research studio</span><h2>Live Dataset Discovery</h2></div>
      <div className="phase-number">P10</div>
    </section>
    <div className="notice">{SAFETY_NOTICE}</div>
    {error && <div className="notice error-notice">{error}</div>}
    {notice && <div className="success-note">{notice}</div>}
    <nav aria-label="Dataset Discovery sections" style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
      {TABS.map((item) => (
        <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
      ))}
    </nav>

    {tab === 'Sessions' && <>
      <h3>Research sessions</h3>
      <form onSubmit={submitSession} style={{ display: 'flex', gap: '.5rem', alignItems: 'flex-end', margin: '1rem 0' }}>
        <label>Title<input value={sessionTitle} onChange={(e) => setSessionTitle(e.target.value)} placeholder="e.g. Tamil ASR corpus search" /></label>
        <button type="submit" disabled={!!busy}>New session</button>
      </form>
      <table>
        <thead><tr>
          <th>Session</th><th>Status</th><th>Stage</th><th>Providers</th><th>Candidates</th><th></th>
        </tr></thead>
        <tbody>
          {sessions.map((item) => (
            <tr key={item.public_id}>
              <td>{item.title || item.session_code}<br /><small>{item.session_code}</small></td>
              <td>{item.status}</td>
              <td>{item.current_stage}</td>
              <td>{item.successful_provider_count}/{item.provider_count}</td>
              <td>{item.result_count}</td>
              <td><button onClick={() => selectSession(item.public_id)}>Select</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && <div className="notice" style={{ marginTop: '1rem' }}>
        <h4>{selected.title || selected.session_code}</h4>
        <p>status: <strong>{selected.status}</strong> · stage: <strong>{selected.current_stage}</strong></p>
        <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
          <button disabled={!!busy} onClick={() => action('Run search', () => runDiscoverySearch(selectedId))}>Run search</button>
          <button disabled={!!busy} onClick={() => action('Cancel session', () => cancelDiscoverySession(selectedId))}>Cancel session</button>
        </div>
      </div>}
    </>}

    {tab === 'Requirement' && <>
      <h3>Requirement{selected ? ` — ${selected.title || selected.session_code}` : ''}</h3>
      {!selected && <p>Select a session in the Sessions tab first.</p>}
      {selected && <form onSubmit={submitRequirement} style={{ display: 'grid', gap: '.5rem', maxWidth: '40rem' }}>
        <label>Modality
          <select value={requirement.modality} onChange={(e) => setRequirement({ ...requirement, modality: e.target.value })}>
            {MODALITIES.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <fieldset>
          <legend>Languages</legend>
          {LANGUAGES.map((lang) => (
            <label key={lang} style={{ display: 'inline-block', marginRight: '1rem' }}>
              <input type="checkbox" checked={requirement.languages.includes(lang)} onChange={() => setRequirement({ ...requirement, languages: toggleInList(requirement.languages, lang) })} /> {lang}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Tasks</legend>
          {TASKS.map((task) => (
            <label key={task} style={{ display: 'inline-block', marginRight: '1rem' }}>
              <input type="checkbox" checked={requirement.tasks.includes(task)} onChange={() => setRequirement({ ...requirement, tasks: toggleInList(requirement.tasks, task) })} /> {task}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Intended use</legend>
          {INTENDED_USES.map((use) => (
            <label key={use} style={{ display: 'inline-block', marginRight: '1rem' }}>
              <input type="checkbox" checked={requirement.intended_uses.includes(use)} onChange={() => setRequirement({ ...requirement, intended_uses: toggleInList(requirement.intended_uses, use) })} /> {use}
            </label>
          ))}
        </fieldset>
        <label>Commercial requirement
          <select value={requirement.commercial_requirement} onChange={(e) => setRequirement({ ...requirement, commercial_requirement: e.target.value })}>
            {COMMERCIAL_REQUIREMENTS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Free-text requirement (used as the search query if given)<textarea rows={3} value={requirement.free_text_requirement} onChange={(e) => setRequirement({ ...requirement, free_text_requirement: e.target.value })} /></label>
        <label>Preferred providers (comma-separated provider codes)<input value={requirement.preferred_providers} onChange={(e) => setRequirement({ ...requirement, preferred_providers: e.target.value })} /></label>
        <label>Excluded providers (comma-separated provider codes)<input value={requirement.excluded_providers} onChange={(e) => setRequirement({ ...requirement, excluded_providers: e.target.value })} /></label>
        <button type="submit" disabled={!!busy}>Save requirement</button>
      </form>}
    </>}

    {tab === 'Candidates' && <>
      <h3>Candidates{selected ? ` — ${selected.title || selected.session_code}` : ''}</h3>
      {!selected && <p>Select a session in the Sessions tab first.</p>}
      {selected && <>
        <table>
          <thead><tr>
            <th>Compare</th><th>Name</th><th>Organization</th><th>Licence</th><th>Score</th>
            <th>Recommendation</th><th>Providers</th><th>Excluded</th><th></th>
          </tr></thead>
          <tbody>
            {candidates.map((c) => (
              <tr key={c.public_id} style={c.excluded ? { opacity: 0.5 } : undefined}>
                <td><input type="checkbox" checked={compareIds.includes(c.public_id)} onChange={() => toggleCompare(c.public_id)} disabled={!compareIds.includes(c.public_id) && compareIds.length >= 5} /></td>
                <td>{c.canonical_name}</td>
                <td>{c.organization || '—'}</td>
                <td>{c.licence_status}{c.declared_licence ? ` (${c.declared_licence})` : ''}</td>
                <td>{scoreLabel(c.suitability_score)}</td>
                <td>{c.recommendation_status}</td>
                <td>{c.provider_count}</td>
                <td>{c.excluded ? 'yes' : 'no'}</td>
                <td>
                  <button onClick={() => openCandidateDetail(c.public_id)}>Details</button>
                  {c.excluded
                    ? <button disabled={!!busy} onClick={() => action('Restore candidate', () => restoreDiscoveryCandidate(c.public_id))}>Restore</button>
                    : <button disabled={!!busy} onClick={() => action('Exclude candidate', () => excludeDiscoveryCandidate(c.public_id))}>Exclude</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {candidateDetail && <div className="notice" style={{ marginTop: '1rem' }}>
          <h4>{candidateDetail.canonical_name}</h4>
          <p>{candidateDetail.description || 'No description recorded.'}</p>
          {candidateDetail.warnings?.length > 0 && <p>Warnings: {candidateDetail.warnings.join(', ')}</p>}
          {candidateDetail.blocking_reasons?.length > 0 && <p>Blocking reasons: {candidateDetail.blocking_reasons.join(', ')}</p>}
          <div style={{ display: 'flex', gap: '.5rem', margin: '.5rem 0' }}>
            {candidateVerificationCase
              ? <button onClick={() => onOpenVerification?.(candidateDetail.public_id)}>Open Verification Case ({candidateVerificationCase.verification_code})</button>
              : <button disabled={!!busy} onClick={() => startLicenceVerification(candidateDetail.public_id)}>Start Licence Verification</button>}
          </div>
          <h5>Sources</h5>
          <ul>
            {candidateDetail.sources.map((s) => (
              <li key={s.public_id}>{s.provider_dataset_id} — {s.source_url || 'no URL recorded'}</li>
            ))}
          </ul>
          <h5>Scores (explainable, per dimension)</h5>
          <table>
            <thead><tr><th>Dimension</th><th>Raw value</th><th>Weight</th><th>Score</th><th>Reason</th></tr></thead>
            <tbody>
              {candidateDetail.scores.map((s) => (
                <tr key={s.public_id}><td>{s.dimension}</td><td>{s.raw_value.toFixed(2)}</td><td>{s.weight}</td><td>{s.score.toFixed(2)}</td><td>{s.reason}</td></tr>
              ))}
            </tbody>
          </table>
        </div>}

        <h4 style={{ marginTop: '2rem' }}>Add a candidate you already know about</h4>
        <form onSubmit={submitManualCandidate} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
          <label>Name<input required value={manualCandidate.canonical_name} onChange={(e) => setManualCandidate({ ...manualCandidate, canonical_name: e.target.value })} /></label>
          <label>Organization<input value={manualCandidate.organization} onChange={(e) => setManualCandidate({ ...manualCandidate, organization: e.target.value })} /></label>
          <label>Declared licence<input value={manualCandidate.declared_licence} onChange={(e) => setManualCandidate({ ...manualCandidate, declared_licence: e.target.value })} /></label>
          <label>Homepage URL<input value={manualCandidate.homepage_url} onChange={(e) => setManualCandidate({ ...manualCandidate, homepage_url: e.target.value })} /></label>
          <label>Description<textarea rows={3} value={manualCandidate.description} onChange={(e) => setManualCandidate({ ...manualCandidate, description: e.target.value })} /></label>
          <button type="submit" disabled={!!busy}>Add manual candidate</button>
        </form>
      </>}
    </>}

    {tab === 'Comparison' && <>
      <h3>Comparison{selected ? ` — ${selected.title || selected.session_code}` : ''}</h3>
      {!selected && <p>Select a session in the Sessions tab first.</p>}
      {selected && <>
        <p>{compareIds.length} candidate(s) selected in the Candidates tab (2-5 required).</p>
        <button disabled={!!busy || compareIds.length < 2 || compareIds.length > 5} onClick={() => action('Create comparison', () => createDiscoveryComparison(selectedId, { candidate_ids: compareIds }))}>Create comparison</button>
        {comparisons.map((cmp) => (
          <div key={cmp.public_id} className="notice" style={{ marginTop: '1rem' }}>
            <p>Compared {cmp.candidate_ids.length} candidates at {cmp.created_at}.</p>
            <p>Best overall: <strong>{cmp.summary?.best_overall_candidate_public_id || 'not yet scored'}</strong></p>
            {cmp.summary?.warnings?.length > 0 && <p>Warnings: {cmp.summary.warnings.join('; ')}</p>}
          </div>
        ))}
      </>}
    </>}

    {tab === 'History' && <>
      <h3>History{selected ? ` — ${selected.title || selected.session_code}` : ''}</h3>
      {!selected && <p>Select a session in the Sessions tab first.</p>}
      {selected && <>
        <h4>Provider runs</h4>
        <table>
          <thead><tr><th>Provider</th><th>Status</th><th>Results</th><th>Latency (ms)</th><th>Error</th></tr></thead>
          <tbody>
            {providerRuns.map((run) => (
              <tr key={run.public_id}><td>{run.provider_code}</td><td>{run.status}</td><td>{run.result_count}</td><td>{run.latency_ms ?? '—'}</td><td>{run.error_code || '—'}</td></tr>
            ))}
          </tbody>
        </table>
        <h4>Events</h4>
        <div className="audit-list">
          {events.map((event) => (
            <article key={event.public_id}>
              <div><strong>{event.event_type.replaceAll('_', ' ')}</strong><span>{event.performed_by_admin_public_id}</span></div>
              <small>{event.summary} — {event.created_at}</small>
            </article>
          ))}
        </div>
      </>}
    </>}
  </>

  return currentPage
}
