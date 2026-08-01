import { useEffect, useState } from 'react'
import {
  trustedWebOverview, trustedWebProviders, trustedWebPolicy, trustedWebSearchEvents,
  trustedWebEvidence, trustedWebHealth, trustedWebTestSearch,
} from '../services/api.js'

const tabs = [
  'Overview', 'Demand', 'Providers', 'Policy', 'Search Events', 'Sources',
  'Freshness', 'Conflicts', 'Injection Blocks', 'Health',
]

export default function TrustedWebPage() {
  const [tab, setTab] = useState('Overview')
  const [error, setError] = useState('')
  const [overview, setOverview] = useState(null)
  const [providers, setProviders] = useState(null)
  const [policy, setPolicy] = useState(null)
  const [events, setEvents] = useState([])
  const [evidence, setEvidence] = useState([])
  const [health, setHealth] = useState(null)

  useEffect(() => { refreshOverview() }, [])

  async function refreshOverview() {
    try { setOverview(await trustedWebOverview()) } catch (reason) { setError(reason.message) }
  }

  async function selectTab(value) {
    setTab(value)
    setError('')
    try {
      if (value === 'Providers') setProviders(await trustedWebProviders())
      if (value === 'Policy') setPolicy(await trustedWebPolicy())
      if (value === 'Search Events' || value === 'Sources' || value === 'Freshness' || value === 'Conflicts') {
        setEvents((await trustedWebSearchEvents()).items)
      }
      if (value === 'Sources' || value === 'Injection Blocks') {
        setEvidence((await trustedWebEvidence()).items)
      }
      if (value === 'Health') setHealth(await trustedWebHealth())
    } catch (reason) { setError(reason.message) }
  }

  return (
    <section className="documents-workspace">
      <header className="section-heading">
        <div>
          <h2>Trusted Web</h2>
          <p>
            Phase 20 live, source-verified Web search gateway for public chat. Search results are
            never trusted evidence by themselves -- every answer here went through domain trust
            evaluation, optional safe fetch, injection filtering, freshness evaluation, and source
            conflict detection before being used.
          </p>
        </div>
        <button onClick={refreshOverview}>Refresh</button>
      </header>
      <div className="dataset-tabs">
        {tabs.map((value) => (
          <button key={value} className={tab === value ? 'active' : ''} onClick={() => selectTab(value)}>{value}</button>
        ))}
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}

      {tab === 'Overview' && <OverviewTab overview={overview} />}
      {tab === 'Demand' && <DemandTab overview={overview} />}
      {tab === 'Providers' && <ProvidersTab providers={providers} onTest={setError} />}
      {tab === 'Policy' && <PolicyTab policy={policy} />}
      {tab === 'Search Events' && <EventsTab events={events} />}
      {tab === 'Sources' && <SourcesTab evidence={evidence} />}
      {tab === 'Freshness' && <FreshnessTab events={events} />}
      {tab === 'Conflicts' && <ConflictsTab events={events} />}
      {tab === 'Injection Blocks' && <InjectionBlocksTab evidence={evidence} />}
      {tab === 'Health' && <HealthTab health={health} />}
    </section>
  )
}

function OverviewTab({ overview }) {
  if (!overview) return <div className="notice">Loading...</div>
  return (
    <section className="metric-grid">
      <article className="status-card"><span>Total search events</span><strong>{overview.total_search_events}</strong></article>
      <article className="status-card"><span>Blocked fetches</span><strong>{overview.blocked_fetches}</strong></article>
      <article className="status-card"><span>Injection-blocked sources</span><strong>{overview.injection_blocked_sources}</strong></article>
      {Object.entries(overview.by_status || {}).map(([status, n]) => (
        <article className="status-card" key={status}><span>{status}</span><strong>{n}</strong></article>
      ))}
    </section>
  )
}

function DemandTab({ overview }) {
  if (!overview) return <div className="notice">Loading...</div>
  const demand = overview.web_demand || {}
  return (
    <>
      <div className="notice">
        Real, evidence-backed demand from Phase 19's knowledge-gap registry -- used to prioritize
        which Web categories/providers to expand next.
      </div>
      <section className="metric-grid">
        {Object.entries(demand).map(([key, value]) => (
          <article className="status-card" key={key}><span>{key}</span><strong>{String(value)}</strong></article>
        ))}
      </section>
      <h3>By category</h3>
      <section className="metric-grid">
        {Object.entries(overview.by_category || {}).map(([category, n]) => (
          <article className="status-card" key={category}><span>{category}</span><strong>{n}</strong></article>
        ))}
      </section>
    </>
  )
}

function ProvidersTab({ providers, onTest }) {
  const [query, setQuery] = useState('latest software version')
  const [result, setResult] = useState(null)
  async function runTest() {
    try { setResult(await trustedWebTestSearch({ query })) } catch (reason) { onTest(reason.message) }
  }
  return (
    <>
      {!providers && <div className="notice">Loading...</div>}
      {providers && (
        <section className="metric-grid">
          <article className="status-card"><span>Configured provider</span><strong>{providers.configured_provider_name}</strong></article>
          <article className="status-card"><span>Healthy</span><strong>{String(providers.healthy)}</strong></article>
          <article className="status-card"><span>Reason</span><strong>{providers.reason || '--'}</strong></article>
        </section>
      )}
      <h3>Test search (Admin-only, real, bounded, audited)</h3>
      <div className="form-row">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="test query" />
        <button onClick={runTest}>Run test search</button>
      </div>
      {result && (
        <pre className="notice">{JSON.stringify(result, null, 2)}</pre>
      )}
    </>
  )
}

function PolicyTab({ policy }) {
  if (!policy) return <div className="notice">Loading...</div>
  if (!policy.available) return <div className="form-error" role="alert">{policy.error}</div>
  const p = policy.policy
  return (
    <>
      <section className="metric-grid">
        <article className="status-card"><span>Policy version</span><strong>{p.policy_version}</strong></article>
        <article className="status-card"><span>Checksum</span><strong>{p.policy_checksum_sha256?.slice(0, 12)}...</strong></article>
        <article className="status-card"><span>Allowed domains</span><strong>{Object.keys(p.allowed_domains || {}).length}</strong></article>
        <article className="status-card"><span>Blocked domains</span><strong>{(p.blocked_domains || []).length}</strong></article>
        <article className="status-card"><span>Maximum results</span><strong>{p.maximum_results}</strong></article>
        <article className="status-card"><span>Maximum fetches</span><strong>{p.maximum_fetches}</strong></article>
      </section>
      <h3>Allowed domains and trust levels</h3>
      <table>
        <thead><tr><th>Domain</th><th>Trust level</th></tr></thead>
        <tbody>
          {Object.entries(p.allowed_domains || {}).map(([domain, level]) => (
            <tr key={domain}><td>{domain}</td><td>{level}</td></tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

function EventsTab({ events }) {
  return (
    <table>
      <thead><tr><th>Category</th><th>Provider</th><th>Status</th><th>Results</th><th>Conflict</th><th>Freshness</th><th>Created</th></tr></thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.public_id}>
            <td>{e.web_category}</td><td>{e.provider_name}</td><td>{e.status}</td>
            <td>{e.result_count}</td><td>{e.conflict_status}</td><td>{e.overall_freshness_status || '--'}</td>
            <td>{e.created_at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function SourcesTab({ evidence }) {
  return (
    <table>
      <thead><tr><th>Domain</th><th>Trust level</th><th>Verification</th><th>Freshness</th></tr></thead>
      <tbody>
        {evidence.map((e) => (
          <tr key={e.public_id}>
            <td>{e.source_domain}</td><td>{e.trust_level}</td><td>{e.verification_level}</td><td>{e.freshness_status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function FreshnessTab({ events }) {
  const byFreshness = {}
  for (const e of events) {
    const key = e.overall_freshness_status || 'undated'
    byFreshness[key] = (byFreshness[key] || 0) + 1
  }
  return (
    <section className="metric-grid">
      {Object.entries(byFreshness).map(([key, n]) => (
        <article className="status-card" key={key}><span>{key}</span><strong>{n}</strong></article>
      ))}
    </section>
  )
}

function ConflictsTab({ events }) {
  const conflicting = events.filter((e) => e.conflict_status !== 'no_conflict')
  return (
    <table>
      <thead><tr><th>Category</th><th>Conflict status</th><th>Created</th></tr></thead>
      <tbody>
        {conflicting.map((e) => (
          <tr key={e.public_id}><td>{e.web_category}</td><td>{e.conflict_status}</td><td>{e.created_at}</td></tr>
        ))}
      </tbody>
    </table>
  )
}

function InjectionBlocksTab({ evidence }) {
  return (
    <div className="notice">
      Injection-blocked fetch attempts are recorded in the fetch-events audit trail
      (`injection_status = 'blocked'`) -- never included in the evidence used for an answer.
      Source-level view: {evidence.length} evidence rows currently visible.
    </div>
  )
}

function HealthTab({ health }) {
  if (!health) return <div className="notice">Loading...</div>
  return (
    <section className="metric-grid">
      <article className="status-card"><span>Provider available</span><strong>{String(health.provider_available)}</strong></article>
      <article className="status-card"><span>Policy loaded</span><strong>{String(health.policy_loaded)}</strong></article>
      <article className="status-card"><span>External MCP enabled</span><strong>{String(health.external_mcp_enabled)}</strong></article>
      {health.policy_error && <article className="status-card"><span>Policy error</span><strong>{health.policy_error}</strong></article>}
    </section>
  )
}
