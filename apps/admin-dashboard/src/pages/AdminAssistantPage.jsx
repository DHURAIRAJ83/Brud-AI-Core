import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  assistantActions,
  assistantLanguagePreference,
  assistantOverview,
  assistantProposal,
  assistantProposals,
  createAssistantProposal,
  executeAssistantProposal,
  getGovernanceStatus,
  reviewAssistantProposal,
  setAssistantLanguagePreference,
} from '../services/api.js'

const GOVERNANCE_NOTICE = 'The Admin Assistant never mutates anything on its own. Every proposed action must be approved through Admin Review, and approved actions execute only through the existing secured dataset/admin services -- never a direct database write. It cannot start model training.'

const LANGUAGE_OPTIONS = [
  { key: 'tamil', label: 'தமிழ்' },
  { key: 'english', label: 'English' },
  { key: 'tanglish', label: 'Tanglish' },
  { key: 'auto', label: 'Auto' },
]

function Pre({ value }) {
  if (value === undefined || value === null) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

const TABS = ['Guidance', 'Governance & Activation Readiness', 'Propose an Action', 'Proposals & Admin Review']

export default function AdminAssistantPage() {
  const [tab, setTab] = useState('Guidance')
  const [overview, setOverview] = useState(null)
  const [govStatus, setGovStatus] = useState(null)
  const [actions, setActions] = useState([])
  const [proposals, setProposals] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [comment, setComment] = useState('')
  const [language, setLanguage] = useState('auto')
  const [languageLoaded, setLanguageLoaded] = useState(false)
  const [languageSaving, setLanguageSaving] = useState(false)
  const [languageError, setLanguageError] = useState('')

  const [form, setForm] = useState({
    action_type: 'dataset_record_review',
    target_type: 'dataset_record',
    target_public_id: '',
    summary: '',
    decision: 'approve',
    comments: '',
  })

  function loadOverview() {
    assistantOverview().then(setOverview).catch((reason) => setError(reason.message))
    getGovernanceStatus().then(setGovStatus).catch(() => {})
    assistantActions().then((data) => setActions(data.action_types)).catch(() => {})
  }

  function loadProposals(status = statusFilter) {
    assistantProposals(status).then(setProposals).catch((reason) => setError(reason.message))
  }

  useEffect(() => { loadOverview() }, [])
  useEffect(() => { if (tab === 'Proposals & Admin Review') loadProposals() }, [tab])
  useEffect(() => {
    assistantLanguagePreference()
      .then((data) => setLanguage(data.response_language))
      .catch(() => {})
      .finally(() => setLanguageLoaded(true))
  }, [])

  // Shares the one saved preference with the floating widget -- the two
  // surfaces never keep competing copies. Changing it here also changes
  // what the widget's next reply is written in, since both simply read
  // the same backend-stored value.
  async function changeLanguage(nextLanguage) {
    const previous = language
    setLanguage(nextLanguage)
    setLanguageSaving(true)
    setLanguageError('')
    try {
      await setAssistantLanguagePreference(nextLanguage)
      loadOverview()
    } catch (reason) {
      setLanguage(previous)
      setLanguageError(reason.message)
    } finally {
      setLanguageSaving(false)
    }
  }

  async function submitProposal(event) {
    event.preventDefault()
    setError('')
    try {
      const request_payload = form.action_type === 'dataset_record_review'
        ? { decision: form.decision, comments: form.comments || null }
        : JSON.parse(form.comments || '{}')
      await createAssistantProposal({
        action_type: form.action_type,
        target_type: form.target_type,
        target_public_id: form.target_public_id,
        summary: form.summary,
        request_payload,
      })
      setForm({ ...form, target_public_id: '', summary: '', comments: '' })
      setTab('Proposals & Admin Review')
      loadProposals()
      loadOverview()
    } catch (reason) { setError(reason.message) }
  }

  async function openProposal(publicId) {
    try { setSelected(await assistantProposal(publicId)); setComment('') }
    catch (reason) { setError(reason.message) }
  }

  async function decide(decision) {
    if (!selected) return
    try {
      const updated = await reviewAssistantProposal(selected.public_id, { decision, comment: comment || null })
      setSelected(updated)
      loadProposals()
      loadOverview()
    } catch (reason) { setError(reason.message) }
  }

  async function execute() {
    if (!selected) return
    try {
      const updated = await executeAssistantProposal(selected.public_id)
      setSelected(updated)
      loadProposals()
      loadOverview()
    } catch (reason) { setError(reason.message) }
  }

  return <>
    <section className="intro">
      <div><span>Governed automation</span><h2>Admin Assistant</h2></div>
      <div className="phase-number">AA</div>
    </section>
    <div className="notice">{GOVERNANCE_NOTICE}</div>
    {error && <div className="notice error-notice">{error}</div>}
    <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center', margin: '.75rem 0' }}>
      <label htmlFor="assistant-page-response-language">Reply language</label>
      <select
        id="assistant-page-response-language"
        value={language}
        disabled={!languageLoaded || languageSaving}
        onChange={(event) => changeLanguage(event.target.value)}
      >
        {LANGUAGE_OPTIONS.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
      </select>
    </div>
    {languageError && <div className="notice error-notice">{languageError}</div>}
    <nav aria-label="Admin Assistant sections" style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
      {TABS.map((item) => (
        <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
      ))}
    </nav>

    {tab === 'Guidance' && <>
      <h3>What needs attention</h3>
      {!overview && <p>Loading dashboard summary…</p>}
      {overview && <>
        <ul>{(overview.localized_guidance ?? overview.guidance).map((line) => <li key={line}>{line}</li>)}</ul>
        <h3>Dashboard snapshot</h3>
        <section className="card-grid">
          {Object.entries(overview.summary).map(([area, buckets]) => (
            <StatusCard key={area} label={area.replaceAll('_', ' ')} value={Object.values(buckets).reduce((a, b) => a + b, 0)} />
          ))}
        </section>
        <Pre value={overview.summary} />
      </>}
    </>}

    {tab === 'Governance & Activation Readiness' && <>
      <h3>Canonical Governance Status (P0–P10G)</h3>
      {!govStatus && <p>Loading canonical governance status…</p>}
      {govStatus && <>
        <div className="notice" style={{ background: '#0d2238', color: '#70baff', borderLeft: '4px solid #388bfd', marginBottom: '1rem' }}>
          <strong>Authority Lock:</strong> {govStatus.admin_assistant_authority} — The Admin Assistant displays status and provides advice only. It cannot authorize training, sign tokens, promote candidates, or activate production.
        </div>

        <section className="card-grid" style={{ marginBottom: '1.5rem' }}>
          <StatusCard label="Canonical Components" value={govStatus.activation_readiness.p0_p10g_canonical_components} />
          <StatusCard label="Production State" value={govStatus.activation_readiness.production_state} />
          <StatusCard label="Final Verdict" value={govStatus.activation_readiness.final_verdict} />
          <StatusCard label="Compliance Status" value={govStatus.governance.compliance.compliance_status} />
        </section>

        <h3>System Governance & Invariants</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          <div className="card" style={{ padding: '1rem', background: '#161b22', borderRadius: '6px', border: '1px solid #30363d' }}>
            <h4 style={{ margin: '0 0 .5rem 0', color: '#58a6ff' }}>Training & Mutation</h4>
            <p><strong>Training Execution Authorized:</strong> {String(govStatus.governance.invariants.training_execution_authorized)}</p>
            <p><strong>Optimizer Stepping:</strong> {String(govStatus.governance.invariants.optimizer_stepping)}</p>
            <p><strong>Tokenizer Mutation:</strong> {String(govStatus.governance.invariants.tokenizer_mutation)}</p>
          </div>

          <div className="card" style={{ padding: '1rem', background: '#161b22', borderRadius: '6px', border: '1px solid #30363d' }}>
            <h4 style={{ margin: '0 0 .5rem 0', color: '#58a6ff' }}>Candidate & Release</h4>
            <p><strong>Promotion:</strong> {govStatus.governance.invariants.production_promotion}</p>
            <p><strong>Public Chat Eligible:</strong> {String(govStatus.governance.invariants.public_chat_eligible)}</p>
            <p><strong>Candidate Traffic Share:</strong> {govStatus.governance.invariants.candidate_traffic_share}</p>
          </div>

          <div className="card" style={{ padding: '1rem', background: '#161b22', borderRadius: '6px', border: '1px solid #30363d' }}>
            <h4 style={{ margin: '0 0 .5rem 0', color: '#58a6ff' }}>Security & Compliance</h4>
            <p><strong>RBAC Integrity:</strong> {govStatus.governance.rbac.rbac_integrity_passed ? 'PASSED' : 'FAILED'}</p>
            <p><strong>Tenant Isolation:</strong> {govStatus.governance.rbac.tenant_isolation_passed ? 'PASSED' : 'FAILED'}</p>
            <p><strong>Policy Drift:</strong> {govStatus.governance.rbac.policy_drift_status}</p>
            <p><strong>Active Keys:</strong> {govStatus.governance.secrets.active_keys_count}</p>
          </div>
        </div>

        <h3>Final Activation Blockers</h3>
        <ul style={{ background: '#21262d', padding: '1rem 1.5rem', borderRadius: '6px', border: '1px solid #363b42' }}>
          {govStatus.activation_readiness.activation_blockers.map((blocker) => (
            <li key={blocker} style={{ color: '#f85149', marginBottom: '.25rem' }}>{blocker}</li>
          ))}
        </ul>
      </>}
    </>}

    {tab === 'Propose an Action' && <>
      <h3>Draft a reviewable proposal</h3>
      <p>Allowlisted action types: {actions.join(', ') || 'loading…'}. Nothing outside this list can be proposed or executed.</p>
      <form onSubmit={submitProposal} style={{ display: 'grid', gap: '.5rem', maxWidth: '32rem' }}>
        <label>Action type
          <select value={form.action_type} onChange={(event) => setForm({ ...form, action_type: event.target.value })}>
            {actions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>Target type
          <input value={form.target_type} onChange={(event) => setForm({ ...form, target_type: event.target.value })} />
        </label>
        <label>Target public ID (e.g. dataset record ID)
          <input value={form.target_public_id} onChange={(event) => setForm({ ...form, target_public_id: event.target.value })} required />
        </label>
        <label>Summary shown to the reviewing admin
          <input value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} required />
        </label>
        {form.action_type === 'dataset_record_review' && <>
          <label>Decision
            <select value={form.decision} onChange={(event) => setForm({ ...form, decision: event.target.value })}>
              <option value="approve">approve</option>
              <option value="reject">reject</option>
              <option value="request_changes">request_changes</option>
            </select>
          </label>
          <label>Comments
            <input value={form.comments} onChange={(event) => setForm({ ...form, comments: event.target.value })} />
          </label>
        </>}
        {form.action_type !== 'dataset_record_review' && <label>Request payload (JSON)
          <textarea rows={4} value={form.comments} onChange={(event) => setForm({ ...form, comments: event.target.value })} placeholder="{}" />
        </label>}
        <button type="submit">Create proposal</button>
      </form>
    </>}

    {tab === 'Proposals & Admin Review' && <>
      <h3>Proposals</h3>
      <label>Filter by status
        <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); loadProposals(event.target.value) }}>
          <option value="">all</option>
          <option value="pending">pending</option>
          <option value="approved">approved</option>
          <option value="rejected">rejected</option>
        </select>
      </label>
      <table>
        <thead><tr><th>Summary</th><th>Action</th><th>Status</th><th>Execution</th><th></th></tr></thead>
        <tbody>
          {proposals.map((item) => (
            <tr key={item.public_id}>
              <td>{item.summary || item.action_type}</td>
              <td>{item.action_type}</td>
              <td>{item.status}</td>
              <td>{item.execution_status}</td>
              <td><button onClick={() => openProposal(item.public_id)}>Review</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && <div className="notice" style={{ marginTop: '1rem' }}>
        <h4>{selected.summary || selected.action_type}</h4>
        <Pre value={selected} />
        {selected.status === 'pending' && <div style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
          <input placeholder="Review comment" value={comment} onChange={(event) => setComment(event.target.value)} />
          <button onClick={() => decide('approved')}>Approve</button>
          <button onClick={() => decide('rejected')}>Reject</button>
        </div>}
        {selected.status === 'approved' && selected.execution_status === 'pending' && (
          <button onClick={execute}>Execute through secured service</button>
        )}
      </div>}
    </>}
  </>
}
