import { useEffect, useState } from 'react'
import {
  archiveDataSource, checkDataSourceUsage, createDataSource, dataSourceHistory,
  dataSourceRights, dataSourceUsageSummary, dataSourceVerificationEvents, dataSources,
  rejectDataSource, restoreDataSource, restrictDataSource, submitDataSourceForReview,
  upsertDataSourceRights, verifyDataSource,
} from '../services/api.js'

const TABS = ['Overview', 'Sources', 'Rights Review', 'Usage Eligibility', 'Verification History', 'Blocked Items']

const SOURCE_TYPES = [
  'human_created', 'admin_created', 'teacher_created', 'institution_created',
  'document_derived', 'government_source', 'public_domain', 'open_dataset',
  'licensed_dataset', 'permission_granted', 'user_contributed', 'ai_assisted',
  'ai_generated', 'web_source', 'unknown',
]

const TARGET_USES = ['rag', 'training', 'evaluation', 'commercial', 'public_export', 'redistribution']

const emptySourceForm = { source_code: '', title: '', source_type: 'human_created', description: '' }

const emptyRightsForm = {
  rights_status: 'unknown', license_name: '', license_identifier: '', copyright_owner: '',
  permission_reference: '', attribution_required: false, commercial_use_allowed: false,
  rag_use_allowed: false, training_use_allowed: false, evaluation_use_allowed: false,
  public_export_allowed: false, redistribution_allowed: false, internal_only: false,
  review_notes: '',
}

export default function SourcesRightsPage() {
  const [tab, setTab] = useState('Overview')
  const [sources, setSources] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [sourceForm, setSourceForm] = useState(emptySourceForm)
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [rightsForm, setRightsForm] = useState(emptyRightsForm)
  const [targetUse, setTargetUse] = useState('training')
  const [usageResult, setUsageResult] = useState(null)
  const [usageSummary, setUsageSummary] = useState(null)
  const [historyResult, setHistoryResult] = useState(null)
  const [verificationEvents, setVerificationEvents] = useState([])

  async function load() {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.set('status', statusFilter)
      if (typeFilter) params.set('source_type', typeFilter)
      if (search) params.set('search', search)
      params.set('page_size', '100')
      setSources(await dataSources(`?${params.toString()}`))
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [statusFilter, typeFilter, search])

  async function createSource(event) {
    event.preventDefault()
    try {
      await createDataSource(sourceForm)
      setNotice('Source created as a draft.')
      setSourceForm(emptySourceForm)
      await load()
    } catch (reason) {
      setError(reason.message)
    }
  }

  async function selectSource(publicId) {
    setSelectedId(publicId)
    setUsageResult(null)
    try {
      const rights = await dataSourceRights(publicId)
      setRightsForm(rights ? { ...emptyRightsForm, ...rights } : emptyRightsForm)
    } catch (reason) {
      setError(reason.message)
    }
  }

  async function saveRights(event) {
    event.preventDefault()
    if (!selectedId) return setError('Choose a source first.')
    try {
      await upsertDataSourceRights(selectedId, rightsForm)
      setNotice('Rights declaration saved.')
    } catch (reason) {
      setError(reason.message)
    }
  }

  async function submitForReview() {
    try {
      await submitDataSourceForReview(selectedId)
      setNotice('Submitted for review.')
      await load()
    } catch (reason) {
      setError(reason.message)
    }
  }

  async function reviewDecision(action, callback) {
    try {
      await callback(selectedId, { action, notes: '' })
      setNotice(`Recorded: ${action}.`)
      await load()
    } catch (reason) {
      setError(reason.message)
    }
  }

  async function runUsageCheck() {
    if (!selectedId) return setError('Choose a source first.')
    try {
      setUsageResult(await checkDataSourceUsage(selectedId, targetUse))
    } catch (reason) {
      setError(reason.message)
    }
  }

  async function runUsageSummary() {
    if (!selectedId) return setError('Choose a source first.')
    try {
      setUsageSummary(await dataSourceUsageSummary(selectedId))
    } catch (reason) {
      setError(reason.message)
    }
  }

  async function loadHistory() {
    if (!selectedId) return setError('Choose a source first.')
    try {
      setHistoryResult(await dataSourceHistory(selectedId))
      setVerificationEvents((await dataSourceVerificationEvents(selectedId)).items)
    } catch (reason) {
      setError(reason.message)
    }
  }

  const blockedItems = sources.items.filter((item) => ['rejected', 'restricted'].includes(item.status))

  return (
    <section className="sources-rights-workspace">
      <header className="section-heading">
        <div>
          <h2>Sources &amp; Rights</h2>
          <p>Where data came from, who owns it, what it may be used for -- and what is blocked until review completes.</p>
        </div>
      </header>
      <div className="dataset-tabs">
        {TABS.map((item) => <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>)}
      </div>
      {notice && <div className="success-note" role="status">{notice}</div>}
      {error && <div className="form-error" role="alert">{error}</div>}

      {tab === 'Overview' && (
        <section className="metric-grid">
          {['draft', 'needs_review', 'verified', 'restricted', 'rejected', 'archived'].map((status) => (
            <article className="status-card" key={status}>
              <span>{status.replaceAll('_', ' ')}</span>
              <strong>{sources.items.filter((item) => item.status === status).length}</strong>
            </article>
          ))}
          <article className="status-card"><span>Total sources</span><strong>{sources.total}</strong></article>
        </section>
      )}

      {tab === 'Sources' && (
        <>
          <form className="inline-form" onSubmit={createSource}>
            <h2>Register a new source</h2>
            <label>Source code<input value={sourceForm.source_code} onChange={(e) => setSourceForm({ ...sourceForm, source_code: e.target.value })} placeholder="SRC-HUMAN-DHURAI-0001" required /></label>
            <label>Title<input value={sourceForm.title} onChange={(e) => setSourceForm({ ...sourceForm, title: e.target.value })} required /></label>
            <label>Source type<select value={sourceForm.source_type} onChange={(e) => setSourceForm({ ...sourceForm, source_type: e.target.value })}>{SOURCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></label>
            <button>Create draft source</button>
          </form>
          <div className="dataset-tabs" role="group" aria-label="Source filters">
            <input placeholder="Search title, owner, code..." value={search} onChange={(e) => setSearch(e.target.value)} />
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {['draft', 'needs_review', 'verified', 'restricted', 'rejected', 'archived'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">All types</option>
              {SOURCE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          {loading ? <div className="notice">Loading sources…</div> : !sources.items.length ? <div className="notice">No sources match this filter.</div> : (
            <div className="data-list">
              {sources.items.map((item) => (
                <article key={item.public_id}>
                  <div>
                    <strong>{item.source_code}</strong>
                    <small>{item.title} · {item.source_type} · {item.status}</small>
                  </div>
                  <div>
                    <button onClick={() => selectSource(item.public_id)}>Open in Rights Review</button>
                    {item.status === 'archived'
                      ? <button onClick={async () => { await restoreDataSource(item.public_id); await load() }}>Restore</button>
                      : <button onClick={async () => { await archiveDataSource(item.public_id); await load() }}>Archive</button>}
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'Rights Review' && (
        <>
          <div className="panel-controls">
            <label>Source to review
              <select value={selectedId} onChange={(e) => selectSource(e.target.value)}>
                <option value="">Choose a source</option>
                {sources.items.map((item) => <option key={item.public_id} value={item.public_id}>{item.source_code} -- {item.title}</option>)}
              </select>
            </label>
          </div>
          {selectedId && (
            <form className="inline-form" onSubmit={saveRights}>
              <h2>Rights declaration</h2>
              <label>Rights status
                <select value={rightsForm.rights_status} onChange={(e) => setRightsForm({ ...rightsForm, rights_status: e.target.value })}>
                  {['unknown', 'pending_review', 'public_domain', 'open_license', 'licensed', 'permission_granted', 'internal_only', 'restricted', 'prohibited', 'expired'].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <label>License name<input value={rightsForm.license_name || ''} onChange={(e) => setRightsForm({ ...rightsForm, license_name: e.target.value })} /></label>
              <label>Copyright owner<input value={rightsForm.copyright_owner || ''} onChange={(e) => setRightsForm({ ...rightsForm, copyright_owner: e.target.value })} /></label>
              <label>Permission reference<input value={rightsForm.permission_reference || ''} onChange={(e) => setRightsForm({ ...rightsForm, permission_reference: e.target.value })} /></label>
              <div className="rights-checkbox-section">
                <h3>Explicit per-use decisions (never one ambiguous &quot;approved&quot;)</h3>
                <div className="rights-checkbox-grid">
                  {[
                    ['rag_use_allowed', 'RAG'], ['training_use_allowed', 'Training'], ['evaluation_use_allowed', 'Evaluation'],
                    ['commercial_use_allowed', 'Commercial use'], ['public_export_allowed', 'Public export'], ['redistribution_allowed', 'Redistribution'],
                    ['internal_only', 'Internal only'],
                  ].map(([field, label]) => (
                    <label className="rights-checkbox" key={field}>
                      <input type="checkbox" checked={!!rightsForm[field]} onChange={(e) => setRightsForm({ ...rightsForm, [field]: e.target.checked })} /> {label}
                    </label>
                  ))}
                </div>
              </div>
              <label className="rights-notes">Review notes<textarea value={rightsForm.review_notes || ''} onChange={(e) => setRightsForm({ ...rightsForm, review_notes: e.target.value })} /></label>
              <button className="rights-save-button">Save rights declaration</button>
            </form>
          )}
          {selectedId && (
            <div className="review-actions">
              <h3>Review decision</h3>
              <button type="button" onClick={submitForReview}>Submit for review</button>
              <button type="button" onClick={() => reviewDecision('document_verify', verifyDataSource)}>Verify (document)</button>
              <button type="button" onClick={() => reviewDecision('owner_confirm', verifyDataSource)}>Verify (owner confirmed)</button>
              <button type="button" onClick={() => reviewDecision('restrict', restrictDataSource)}>Restrict</button>
              <button type="button" onClick={() => reviewDecision('reject', rejectDataSource)}>Reject</button>
            </div>
          )}
        </>
      )}

      {tab === 'Usage Eligibility' && (
        <>
          <div className="panel-controls">
            <label>Source
              <select value={selectedId} onChange={(e) => selectSource(e.target.value)}>
                <option value="">Choose a source</option>
                {sources.items.map((item) => <option key={item.public_id} value={item.public_id}>{item.source_code} -- {item.title}</option>)}
              </select>
            </label>
            <label>Target use
              <select value={targetUse} onChange={(e) => setTargetUse(e.target.value)}>
                {TARGET_USES.map((use) => <option key={use} value={use}>{use}</option>)}
              </select>
            </label>
            <button onClick={runUsageCheck}>Check eligibility</button>
            <button onClick={runUsageSummary}>Check all uses at a glance</button>
          </div>
          {usageSummary && (
            <section className="metric-grid">
              {Object.entries(usageSummary).map(([use, decision]) => (
                <article className="status-card" key={use}>
                  <span>{use.replaceAll('_', ' ')}</span>
                  <strong>{decision.allowed ? 'Allowed' : 'Blocked'}</strong>
                </article>
              ))}
            </section>
          )}
          {usageResult && (
            <div className={usageResult.allowed ? 'success-note' : 'form-error'} role="status">
              <strong>{usageResult.allowed ? 'Allowed' : 'Blocked'}</strong> -- {usageResult.decision_code}
              {usageResult.blocking_reasons?.length > 0 && <ul>{usageResult.blocking_reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
              {usageResult.warnings?.length > 0 && <ul>{usageResult.warnings.map((w) => <li key={w} className="row-warning">{w}</li>)}</ul>}
              {usageResult.required_actions?.length > 0 && <ul>{usageResult.required_actions.map((a) => <li key={a}>{a}</li>)}</ul>}
            </div>
          )}
        </>
      )}

      {tab === 'Verification History' && (
        <>
          <div className="panel-controls">
            <label>Source
              <select value={selectedId} onChange={(e) => selectSource(e.target.value)}>
                <option value="">Choose a source</option>
                {sources.items.map((item) => <option key={item.public_id} value={item.public_id}>{item.source_code} -- {item.title}</option>)}
              </select>
            </label>
            <button onClick={loadHistory}>Load history</button>
          </div>
          {historyResult && (
            <div className="history-panel">
              <h3>Verification events (append-only)</h3>
              {!verificationEvents.length ? <div className="notice">No verification events yet.</div> : (
                <ol>{verificationEvents.map((event) => <li key={event.public_id}>{event.action} → {event.verification_status_after} ({event.performed_by_admin_public_id}) at {event.created_at}</li>)}</ol>
              )}
              <h3>Links</h3>
              {!historyResult.links.length ? <div className="notice">No linked records yet.</div> : (
                <ul>{historyResult.links.map((link) => <li key={link.public_id}>{link.entity_type}: {link.entity_public_id} ({link.relationship_type})</li>)}</ul>
              )}
            </div>
          )}
        </>
      )}

      {tab === 'Blocked Items' && (
        !blockedItems.length ? <div className="notice">No restricted or rejected sources right now.</div> : (
          <div className="data-list">
            {blockedItems.map((item) => (
              <article key={item.public_id}>
                <div><strong>{item.source_code}</strong><small>{item.title} · {item.status}</small></div>
                <button onClick={() => selectSource(item.public_id)}>Review</button>
              </article>
            ))}
          </div>
        )
      )}
    </section>
  )
}
