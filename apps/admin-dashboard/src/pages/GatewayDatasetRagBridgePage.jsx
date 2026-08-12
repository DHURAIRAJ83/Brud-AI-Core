import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  egdbExportToDataset,
  gaProviderRuns,
  gaSessions,
  ragSpaces,
  systemRecentAudit,
} from '../services/api.js'

const NOTICE = 'MB-40/41: exports an admin_accepted External AI Gateway session into Dataset Studio, and, if requested, on into a RAG knowledge space and vector index -- in the same call. This page is admin-only and never changes what the public chatbot serves.'

function Pre({ value }) {
  if (!value) return null
  return <pre className="notice" style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{JSON.stringify(value, null, 2)}</pre>
}

export default function GatewayDatasetRagBridgePage() {
  const [state, setState] = useState({ loading: true, error: '', sessions: [], spaces: [] })
  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [providerRuns, setProviderRuns] = useState([])

  const [targetSourcePublicId, setTargetSourcePublicId] = useState('')
  const [ingestToRag, setIngestToRag] = useState(false)
  const [ragKnowledgeSpacePublicId, setRagKnowledgeSpacePublicId] = useState('')
  const [buildRagIndex, setBuildRagIndex] = useState(false)
  const [retrievalProfileName, setRetrievalProfileName] = useState('')

  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const [exportResult, setExportResult] = useState(null)

  const [auditEvents, setAuditEvents] = useState([])
  const [auditLoading, setAuditLoading] = useState(false)

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [sessions, spaces] = await Promise.all([gaSessions(), ragSpaces()])
      setState({
        loading: false, error: '',
        sessions: (sessions.items ?? []).filter((item) => item.status === 'admin_accepted'),
        spaces: spaces.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function selectSession(id) {
    setSelectedSessionId(id)
    setExportResult(null)
    setExportError('')
    setProviderRuns([])
    try { setProviderRuns((await gaProviderRuns(id)).items ?? []) }
    catch { setProviderRuns([]) }
    await loadAuditEvents(id)
  }

  async function loadAuditEvents(sessionId) {
    setAuditLoading(true)
    try {
      const recent = await systemRecentAudit(50)
      const items = (recent.items ?? []).filter(
        (event) => event.resource_type === 'external_gateway_dataset_bridge' && event.resource_public_id === sessionId
      )
      setAuditEvents(items)
    } catch {
      setAuditEvents([])
    } finally {
      setAuditLoading(false)
    }
  }

  async function runExport(event) {
    event.preventDefault()
    if (!selectedSessionId || exporting) return
    setExporting(true)
    setExportError('')
    try {
      const result = await egdbExportToDataset(selectedSessionId, {
        target_source_public_id: targetSourcePublicId || null,
        ingest_to_rag: ingestToRag,
        rag_knowledge_space_public_id: ingestToRag ? ragKnowledgeSpacePublicId || null : null,
        build_rag_index: ingestToRag && buildRagIndex,
        retrieval_profile_name: retrievalProfileName || null,
      })
      setExportResult(result)
      await loadAuditEvents(selectedSessionId)
    } catch (error) {
      setExportError(error.message)
    } finally {
      setExporting(false)
    }
  }

  if (state.loading) return <div className="notice">Loading gateway sessions…</div>

  return (
    <>
      <div className="system-heading">
        <span>MB-40 / MB-41</span>
        <h2>Gateway → Dataset/RAG</h2>
        <p>{NOTICE}</p>
      </div>
      {state.error && (
        <div className="notice error-notice">
          <strong>Unable to load gateway sessions</strong>
          <p>{state.error}</p>
          <button type="button" onClick={load}>Retry</button>
        </div>
      )}

      <div className="training-grid">
        <section className="data-list">
          <h3>Accepted gateway sessions</h3>
          {state.sessions.length === 0 && (
            <article>No sessions with an admin-accepted decision yet. Review a session on the External AI Gateway tab first.</article>
          )}
          {state.sessions.map((item) => (
            <button
              key={item.public_id}
              type="button"
              className="training-job-row"
              onClick={() => selectSession(item.public_id)}
            >
              <strong>{item.topic}</strong>
              <span>{item.status}</span>
              <small>{item.purpose} · {(item.requested_provider_keys ?? []).join(', ') || 'no providers recorded'}</small>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {!selectedSessionId && <p className="notice">Select an accepted session to export it.</p>}

          {selectedSessionId && (
            <>
              <p className="notice">Selected session: {selectedSessionId.slice(0, 8)} · {providerRuns.length} provider run(s) collected</p>

              <form className="inline-form training-form" onSubmit={runExport}>
                <h2>Run export</h2>
                <label>
                  Target dataset source ID (optional)
                  <input
                    value={targetSourcePublicId}
                    onChange={(event) => setTargetSourcePublicId(event.target.value)}
                    placeholder="leave blank to create a new source"
                  />
                </label>
                <label>
                  <input type="checkbox" checked={ingestToRag} onChange={(event) => setIngestToRag(event.target.checked)} />
                  {' '}Also ingest into RAG
                </label>
                {ingestToRag && (
                  <>
                    <label>
                      RAG knowledge space
                      <select value={ragKnowledgeSpacePublicId} onChange={(event) => setRagKnowledgeSpacePublicId(event.target.value)}>
                        <option value="">Select a space…</option>
                        {state.spaces.map((space) => (
                          <option key={space.public_id} value={space.public_id}>{space.name}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <input type="checkbox" checked={buildRagIndex} onChange={(event) => setBuildRagIndex(event.target.checked)} />
                      {' '}Also build a RAG vector index + retrieval profile
                    </label>
                  </>
                )}
                {ingestToRag && buildRagIndex && (
                  <label>
                    Retrieval profile name (optional)
                    <input
                      value={retrievalProfileName}
                      onChange={(event) => setRetrievalProfileName(event.target.value)}
                      placeholder="leave blank for a generated name"
                    />
                  </label>
                )}
                <p className="notice" style={{ gridColumn: '1 / -1' }}>
                  Check the RAG boxes before running the export. Running export again afterward re-detects the same
                  provider runs as duplicates and skips RAG ingestion for them -- ingesting to RAG only works in the
                  same call as the export, never as a separate follow-up step.
                </p>
                <button type="submit" disabled={exporting || (ingestToRag && !ragKnowledgeSpacePublicId)} style={{ gridColumn: '1 / -1' }}>
                  {exporting ? 'Running export…' : 'Run export'}
                </button>
              </form>

              {exportError && <div className="form-error">{exportError}</div>}

              {exportResult && (
                <>
                  <h3>Export status</h3>
                  <div className="metric-grid">
                    <StatusCard label="Records created" value={exportResult.created_record_public_ids.length} tone="good" />
                    <StatusCard label="Duplicates skipped" value={exportResult.duplicate_provider_run_public_ids.length} tone="neutral" />
                    <StatusCard label="Runs skipped" value={exportResult.skipped_provider_run_public_ids.length} tone="waiting" />
                    <StatusCard label="RAG sources created" value={exportResult.rag_source_public_ids.length} tone="good" />
                    <StatusCard label="Vector indexes built" value={exportResult.vector_index_public_ids.length} tone="good" />
                  </div>
                  {exportResult.retrieval_profile_public_id && (
                    <p className="notice">Retrieval profile created: {exportResult.retrieval_profile_public_id}</p>
                  )}
                  <Pre value={exportResult} />
                </>
              )}

              <h3>Audit events for this session</h3>
              {auditLoading && <p className="notice">Loading audit events…</p>}
              {!auditLoading && auditEvents.length === 0 && <p className="notice">No export/build audit events recorded for this session yet.</p>}
              {!auditLoading && auditEvents.length > 0 && (
                <div className="audit-list">
                  {auditEvents.map((event) => (
                    <article key={event.public_id}>
                      <div>
                        <span>{event.outcome}</span>
                        <strong>{event.event_type}</strong>
                      </div>
                      <small>{event.created_at}</small>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </>
  )
}
