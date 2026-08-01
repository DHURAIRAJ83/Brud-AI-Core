import { useEffect, useState } from 'react'
import { toolsOverview, toolsRegistry, toolsExecutionEvents, toolsTest } from '../services/api.js'

const tabs = [
  'Overview', 'Registry', 'Calculator', 'Unit Conversion', 'Date Arithmetic',
  'Execution Events', 'Errors', 'Permissions', 'MCP Readiness',
]

export default function DeterministicToolsPage() {
  const [tab, setTab] = useState('Overview')
  const [error, setError] = useState('')
  const [overview, setOverview] = useState(null)
  const [registry, setRegistry] = useState([])
  const [events, setEvents] = useState([])

  useEffect(() => { refreshOverview() }, [])

  async function refreshOverview() {
    try { setOverview(await toolsOverview()) } catch (reason) { setError(reason.message) }
  }

  async function selectTab(value) {
    setTab(value)
    setError('')
    try {
      if (['Registry', 'Calculator', 'Unit Conversion', 'Date Arithmetic', 'Permissions', 'MCP Readiness'].includes(value)) {
        setRegistry((await toolsRegistry()).tools)
      }
      if (value === 'Execution Events' || value === 'Errors') {
        setEvents((await toolsExecutionEvents()).items)
      }
    } catch (reason) { setError(reason.message) }
  }

  return (
    <section className="documents-workspace">
      <header className="section-heading">
        <div>
          <h2>Deterministic Tools</h2>
          <p>
            Phase 20 sandboxed deterministic tool gateway (calculator, unit conversion, date/time
            arithmetic). Tool results are never model-generated -- the structured numeric result
            from these tools is always authoritative.
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
      {tab === 'Registry' && <RegistryTab registry={registry} />}
      {tab === 'Calculator' && <ToolTester registry={registry} toolName="calculator" onError={setError}
        exampleInput={{ expression: '987654 * 12345' }} />}
      {tab === 'Unit Conversion' && <ToolTester registry={registry} toolName="unit_conversion" onError={setError}
        exampleInput={{ value: 5, source_unit: 'km', target_unit: 'm' }} />}
      {tab === 'Date Arithmetic' && <ToolTester registry={registry} toolName="date_time_arithmetic" onError={setError}
        exampleInput={{ operation: 'add_days', date: '2026-08-01', days: 30 }} />}
      {tab === 'Execution Events' && <EventsTab events={events} filterStatus={null} />}
      {tab === 'Errors' && <EventsTab events={events} filterStatus="error" />}
      {tab === 'Permissions' && <PermissionsTab registry={registry} />}
      {tab === 'MCP Readiness' && <McpReadinessTab overview={overview} />}
    </section>
  )
}

function OverviewTab({ overview }) {
  if (!overview) return <div className="notice">Loading...</div>
  return (
    <section className="metric-grid">
      <article className="status-card"><span>Total executions</span><strong>{overview.total_executions}</strong></article>
      <article className="status-card"><span>External MCP enabled</span><strong>{String(overview.external_mcp_enabled)}</strong></article>
      {Object.entries(overview.by_tool || {}).map(([name, n]) => (
        <article className="status-card" key={name}><span>{name}</span><strong>{n}</strong></article>
      ))}
      {Object.entries(overview.by_status || {}).map(([status, n]) => (
        <article className="status-card" key={status}><span>{status}</span><strong>{n}</strong></article>
      ))}
    </section>
  )
}

function RegistryTab({ registry }) {
  return (
    <table>
      <thead><tr><th>Tool</th><th>Version</th><th>Risk</th><th>Source</th><th>Public</th><th>Admin</th></tr></thead>
      <tbody>
        {registry.map((t) => (
          <tr key={t.tool_name}>
            <td>{t.tool_name}</td><td>{t.tool_version}</td><td>{t.risk_level}</td><td>{t.source}</td>
            <td>{String(t.public_enabled)}</td><td>{String(t.admin_enabled)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ToolTester({ toolName, exampleInput, onError }) {
  const [inputJson, setInputJson] = useState(JSON.stringify(exampleInput, null, 2))
  const [result, setResult] = useState(null)
  async function run() {
    try {
      const input_payload = JSON.parse(inputJson)
      setResult(await toolsTest({ tool_name: toolName, input_payload }))
    } catch (reason) { onError(reason.message) }
  }
  return (
    <>
      <p>Admin-only test execution through the exact same registry + validation pipeline a public request uses.</p>
      <textarea rows={4} value={inputJson} onChange={(e) => setInputJson(e.target.value)} />
      <div className="form-row"><button onClick={run}>Run test</button></div>
      {result && <pre className="notice">{JSON.stringify(result, null, 2)}</pre>}
    </>
  )
}

function EventsTab({ events, filterStatus }) {
  const rows = filterStatus ? events.filter((e) => e.status !== 'success') : events
  return (
    <table>
      <thead><tr><th>Tool</th><th>Status</th><th>Result</th><th>Error</th><th>Latency (ms)</th><th>Created</th></tr></thead>
      <tbody>
        {rows.map((e) => (
          <tr key={e.public_id}>
            <td>{e.tool_name}</td><td>{e.status}</td><td>{e.result_summary || '--'}</td>
            <td>{e.error_code || '--'}</td><td>{e.latency_ms}</td><td>{e.created_at}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function PermissionsTab({ registry }) {
  return (
    <>
      <div className="notice">
        Only these three built-in tools may execute for public requests. No file-write, shell,
        browser-automation, email, calendar, payment, or account-management tool exists in this
        registry.
      </div>
      <table>
        <thead><tr><th>Tool</th><th>Permission</th><th>Timeout (s)</th><th>Max input size</th></tr></thead>
        <tbody>
          {registry.map((t) => (
            <tr key={t.tool_name}>
              <td>{t.tool_name}</td><td>{t.permission}</td><td>{t.timeout_seconds}</td><td>{t.maximum_input_size}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

function McpReadinessTab({ overview }) {
  return (
    <section className="metric-grid">
      <article className="status-card">
        <span>External MCP enabled</span>
        <strong>{overview ? String(overview.external_mcp_enabled) : '...'}</strong>
      </article>
      <article className="status-card">
        <span>External MCP tool sources registered</span>
        <strong>0</strong>
      </article>
      <article className="status-card">
        <span>MCP-ready contract</span>
        <strong>defined (built_in_deterministic active; internal_service / external_mcp reserved)</strong>
      </article>
    </section>
  )
}
