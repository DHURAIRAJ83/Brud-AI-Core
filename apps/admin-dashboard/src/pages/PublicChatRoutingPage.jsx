import { useEffect, useState } from 'react'
import { publicChatRoutingEvent, publicChatRoutingEvents, publicChatRoutingOverview } from '../services/api.js'

const tabs = [
  'Overview', 'Route Events', 'Model Route', 'RAG Route', 'Memory Route',
  'Clarifications', 'Safety', 'Unavailable Routes', 'Language Compliance', 'Errors',
]

const NO_RAW_TEXT_NOTE = 'Operational metadata only -- no raw question or answer text is ever stored or shown here.'

export default function PublicChatRoutingPage() {
  const [tab, setTab] = useState('Overview')
  const [error, setError] = useState('')
  const [overview, setOverview] = useState(null)
  const [events, setEvents] = useState([])
  const [routeFilter, setRouteFilter] = useState('')
  const [detail, setDetail] = useState(null)

  useEffect(() => { refreshOverview() }, [])

  async function refreshOverview() {
    try { setOverview(await publicChatRoutingOverview()) } catch (reason) { setError(reason.message) }
  }

  async function refreshEvents(route = '') {
    try {
      const query = route ? `?resolved_route=${route}` : ''
      setEvents((await publicChatRoutingEvents(query)).events)
    } catch (reason) { setError(reason.message) }
  }

  async function loadEventDetail(publicId) {
    try { setDetail(await publicChatRoutingEvent(publicId)) } catch (reason) { setError(reason.message) }
  }

  function selectTab(value) {
    setTab(value)
    setDetail(null)
    if (value === 'Route Events') { setRouteFilter(''); refreshEvents() }
    if (value === 'Model Route') { setRouteFilter('core_model'); refreshEvents('core_model') }
    if (value === 'RAG Route') { setRouteFilter('approved_rag'); refreshEvents('approved_rag') }
    if (value === 'Memory Route') { setRouteFilter('memory'); refreshEvents('memory') }
    if (value === 'Clarifications') { setRouteFilter('clarify'); refreshEvents('clarify') }
    if (value === 'Unavailable Routes') { setRouteFilter('insufficient'); refreshEvents('insufficient') }
  }

  return (
    <section className="documents-workspace">
      <header className="section-heading">
        <div>
          <h2>Public Chat Routing</h2>
          <p>
            Phase 18 public Smart Answer Router -- diagnostics for the real chatbot at{' '}
            <code>POST /api/chat</code>. Every request resolves to exactly one of core model,
            approved RAG, memory, clarification, refusal, or insufficient-evidence. {NO_RAW_TEXT_NOTE}
          </p>
        </div>
        <button onClick={refreshOverview}>Refresh</button>
      </header>
      <div className="dataset-tabs">
        {tabs.map((value) => (
          <button key={value} className={tab === value ? 'active' : ''} onClick={() => selectTab(value)}>
            {value}
          </button>
        ))}
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}

      {tab === 'Overview' && <OverviewTab overview={overview} />}
      {tab === 'Safety' && <SafetyTab overview={overview} />}
      {tab === 'Language Compliance' && <LanguageComplianceTab overview={overview} />}
      {tab === 'Errors' && <ErrorsTab overview={overview} />}
      {['Route Events', 'Model Route', 'RAG Route', 'Memory Route', 'Clarifications', 'Unavailable Routes'].includes(tab) && (
        <EventsTab
          tab={tab}
          events={events}
          routeFilter={routeFilter}
          setRouteFilter={setRouteFilter}
          refresh={refreshEvents}
          loadDetail={loadEventDetail}
          detail={detail}
        />
      )}
    </section>
  )
}

function OverviewTab({ overview }) {
  if (!overview) return <div className="notice">Loading...</div>
  return (
    <>
      <div className="notice">{NO_RAW_TEXT_NOTE}</div>
      <h3>Request volume</h3>
      <section className="metric-grid">
        <article className="status-card"><span>Total requests</span><strong>{overview.total_requests}</strong></article>
        <article className="status-card"><span>Clarifications</span><strong>{overview.clarification_count}</strong></article>
        <article className="status-card"><span>Refusals</span><strong>{overview.refusal_count}</strong></article>
        <article className="status-card"><span>Insufficient evidence</span><strong>{overview.insufficient_count}</strong></article>
        <article className="status-card"><span>Average latency (ms)</span><strong>{overview.average_latency_ms ?? '--'}</strong></article>
        <article className="status-card"><span>Errors</span><strong>{overview.error_count}</strong></article>
      </section>
      <h3>By resolved route</h3>
      <section className="metric-grid">
        {Object.entries(overview.by_resolved_route || {}).map(([route, count]) => (
          <article className="status-card" key={route}><span>{route}</span><strong>{count}</strong></article>
        ))}
      </section>
      <h3>Trusted Web / Tool honesty</h3>
      <p>Web Search and deterministic Tools are not part of this phase -- when Phase 17 recommends either, the public router honestly reports it as unavailable rather than substituting a stale model answer or an approximated calculation.</p>
      <section className="metric-grid">
        <article className="status-card"><span>Trusted Web recommended but unavailable</span><strong>{overview.trusted_web_unavailable_count}</strong></article>
        <article className="status-card"><span>Tool recommended but unavailable</span><strong>{overview.tool_unavailable_count}</strong></article>
      </section>
    </>
  )
}

function SafetyTab({ overview }) {
  if (!overview) return <div className="notice">Loading...</div>
  return (
    <>
      <h3>Input/output safety status</h3>
      <section className="metric-grid">
        {Object.entries(overview.by_safety_status || {}).map(([status, count]) => (
          <article className="status-card" key={status}><span>{status}</span><strong>{count}</strong></article>
        ))}
      </section>
      <p>A refusal is a deliberate safety decision, never a knowledge gap.</p>
    </>
  )
}

function LanguageComplianceTab({ overview }) {
  const compliance = overview?.language_compliance
  if (!compliance) return <div className="notice">Loading...</div>
  return (
    <>
      <h3>Tanglish-output-compliance</h3>
      <p>Public answers are always Tamil or English script -- Tanglish is never a valid output language.</p>
      <section className="metric-grid">
        <article className="status-card"><span>Total answered</span><strong>{compliance.total_answered}</strong></article>
        <article className="status-card"><span>Language policy violations</span><strong>{compliance.language_policy_violations}</strong></article>
      </section>
    </>
  )
}

function ErrorsTab({ overview }) {
  if (!overview) return <div className="notice">Loading...</div>
  return (
    <>
      <h3>Error volume</h3>
      <section className="metric-grid">
        <article className="status-card"><span>Total errors</span><strong>{overview.error_count}</strong></article>
      </section>
      <p>Use the Route Events tab to inspect individual events, including their stable <code>error_code</code>.</p>
    </>
  )
}

function EventsTab({ tab, events, routeFilter, setRouteFilter, refresh, loadDetail, detail }) {
  return (
    <>
      <h3>{tab}</h3>
      <p>Only the SHA-256 input hash and structured route/safety/language outputs are shown -- see the note above.</p>
      <div className="panel-controls">
        <input placeholder="Filter by resolved route" value={routeFilter} onChange={(e) => setRouteFilter(e.target.value)} />
        <button type="button" onClick={() => refresh(routeFilter)}>Filter</button>
        <button type="button" onClick={() => refresh('')}>Clear filter</button>
      </div>
      <table>
        <thead><tr><th>Route</th><th>Evidence</th><th>Language</th><th>Safety</th><th>Latency (ms)</th><th>Created</th><th></th></tr></thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.public_id}>
              <td>{event.resolved_route}</td>
              <td>{event.evidence_status}</td>
              <td>{event.answer_language ?? event.detected_language}</td>
              <td>{event.safety_status}</td>
              <td>{event.latency_ms ?? '--'}</td>
              <td>{event.created_at}</td>
              <td><button type="button" onClick={() => loadDetail(event.public_id)}>Details</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {detail && <div className="history-panel"><pre>{JSON.stringify(detail, null, 2)}</pre></div>}
    </>
  )
}
