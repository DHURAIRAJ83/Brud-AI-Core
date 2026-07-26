import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  assistantActions,
  assistantOverview,
  assistantProposal,
  assistantProposals,
  createAssistantProposal,
  executeAssistantProposal,
  reviewAssistantProposal,
} from '../services/api.js'

const GOVERNANCE_NOTICE = 'The Admin Assistant never mutates anything on its own. Every proposed action must be approved through Admin Review, and approved actions execute only through the existing secured dataset/admin services -- never a direct database write. It cannot start model training.'

function Pre({ value }) {
  if (value === undefined || value === null) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

const TABS = ['Guidance', 'Propose an Action', 'Proposals & Admin Review']

export default function AdminAssistantPage() {
  const [tab, setTab] = useState('Guidance')
  const [overview, setOverview] = useState(null)
  const [actions, setActions] = useState([])
  const [proposals, setProposals] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [comment, setComment] = useState('')

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
    assistantActions().then((data) => setActions(data.action_types)).catch(() => {})
  }

  function loadProposals(status = statusFilter) {
    assistantProposals(status).then(setProposals).catch((reason) => setError(reason.message))
  }

  useEffect(() => { loadOverview() }, [])
  useEffect(() => { if (tab === 'Proposals & Admin Review') loadProposals() }, [tab])

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
    <nav aria-label="Admin Assistant sections" style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
      {TABS.map((item) => (
        <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
      ))}
    </nav>

    {tab === 'Guidance' && <>
      <h3>What needs attention</h3>
      {!overview && <p>Loading dashboard summary…</p>}
      {overview && <>
        <ul>{overview.guidance.map((line) => <li key={line}>{line}</li>)}</ul>
        <h3>Dashboard snapshot</h3>
        <section className="card-grid">
          {Object.entries(overview.summary).map(([area, buckets]) => (
            <StatusCard key={area} label={area.replaceAll('_', ' ')} value={Object.values(buckets).reduce((a, b) => a + b, 0)} />
          ))}
        </section>
        <Pre value={overview.summary} />
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
