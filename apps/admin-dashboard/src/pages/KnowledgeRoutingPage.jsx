import { useEffect, useState } from 'react'
import {
  classifyKnowledgeRoutingRecord, classifyKnowledgeRoutingText, knowledgeRoutingContextTypes,
  knowledgeRoutingDecision, knowledgeRoutingDecisions, knowledgeRoutingMetrics,
  knowledgeRoutingPolicy, knowledgeRoutingReasonCodes,
} from '../services/api.js'

const tabs = ['Overview', 'Try Classifier', 'Structured Record', 'Recent Decisions', 'Reason Codes', 'Policy']

const RECOMMENDATION_ONLY_NOTE = 'Recommendation only -- no route was executed.'

export default function KnowledgeRoutingPage() {
  const [tab, setTab] = useState('Overview')
  const [busy, setBusy] = useState(''), [error, setError] = useState('')

  const [metrics, setMetrics] = useState(null)
  const [policy, setPolicy] = useState(null)
  const [reasonCodes, setReasonCodes] = useState({})
  const [contextTypes, setContextTypes] = useState([])
  const [decisions, setDecisions] = useState([])
  const [routeFilter, setRouteFilter] = useState('')

  useEffect(() => { refreshOverview() }, [])

  async function refreshOverview() {
    try {
      setMetrics(await knowledgeRoutingMetrics())
      setPolicy(await knowledgeRoutingPolicy())
      setContextTypes((await knowledgeRoutingContextTypes()).context_types)
    } catch (reason) { setError(reason.message) }
  }

  async function refreshDecisions(route = routeFilter) {
    try {
      const query = route ? `?execution_route=${route}` : ''
      setDecisions((await knowledgeRoutingDecisions(query)).decisions)
    } catch (reason) { setError(reason.message) }
  }

  async function loadReasonCodes() {
    try { setReasonCodes((await knowledgeRoutingReasonCodes()).reason_codes) } catch (reason) { setError(reason.message) }
  }

  async function action(label, callback) {
    setBusy(label); setError('')
    try { return await callback() } catch (reason) { setError(reason.message); return undefined } finally { setBusy('') }
  }

  return <section className="documents-workspace">
    <header className="section-heading">
      <div>
        <h2>Knowledge Routing</h2>
        <p>Deterministic, CPU-first classification of language, intent, knowledge domain, freshness, evidence requirement, execution-route recommendation, and learning-target recommendation. {RECOMMENDATION_ONLY_NOTE}</p>
      </div>
      <button onClick={refreshOverview}>Refresh</button>
    </header>
    <div className="dataset-tabs">{tabs.map((value) => <button key={value} className={tab === value ? 'active' : ''} onClick={() => { setTab(value); if (value === 'Recent Decisions') refreshDecisions(); if (value === 'Reason Codes') loadReasonCodes() }}>{value}</button>)}</div>
    {error && <div className="form-error" role="alert">{error}</div>}

    {tab === 'Overview' && <OverviewTab metrics={metrics} policy={policy} />}

    {tab === 'Try Classifier' && <TryClassifierTab
      busy={busy} contextTypes={contextTypes}
      classify={(text, contextType) => action('Classify', () => classifyKnowledgeRoutingText({ text, context_type: contextType }))}
    />}

    {tab === 'Structured Record' && <StructuredRecordTab
      busy={busy} contextTypes={contextTypes.filter((c) => c !== 'public_chat_question')}
      classify={(contextType, record) => action('Classify record', () => classifyKnowledgeRoutingRecord({ context_type: contextType, record }))}
    />}

    {tab === 'Recent Decisions' && <RecentDecisionsTab
      decisions={decisions} routeFilter={routeFilter} setRouteFilter={setRouteFilter}
      refresh={refreshDecisions}
      loadOne={(id) => action('Load decision', () => knowledgeRoutingDecision(id))}
    />}

    {tab === 'Reason Codes' && <ReasonCodesTab reasonCodes={reasonCodes} load={loadReasonCodes} />}

    {tab === 'Policy' && <PolicyTab policy={policy} />}
  </section>
}

function OverviewTab({ metrics, policy }) {
  if (!metrics) return <div className="notice">Loading...</div>
  return <>
    <div className="notice">{RECOMMENDATION_ONLY_NOTE}</div>
    <h3>Classification volume</h3>
    <section className="metric-grid">
      <article className="status-card"><span>Total classifications</span><strong>{metrics.total_classifications}</strong></article>
      <article className="status-card"><span>Requires human review</span><strong>{metrics.requires_human_review_count}</strong></article>
      <article className="status-card"><span>Policy version</span><strong>{policy?.policy_version ?? '--'}</strong></article>
      <article className="status-card"><span>Taxonomy version</span><strong>{policy?.taxonomy_version ?? '--'}</strong></article>
    </section>
    <h3>By execution route</h3>
    <section className="metric-grid">
      {Object.entries(metrics.by_execution_route || {}).map(([route, count]) => (
        <article className="status-card" key={route}><span>{route}</span><strong>{count}</strong></article>
      ))}
    </section>
    <h3>By knowledge domain</h3>
    <section className="metric-grid">
      {Object.entries(metrics.by_domain || {}).map(([domain, count]) => (
        <article className="status-card" key={domain}><span>{domain}</span><strong>{count}</strong></article>
      ))}
    </section>
    <h3>By learning target</h3>
    <section className="metric-grid">
      {Object.entries(metrics.by_learning_target || {}).map(([target, count]) => (
        <article className="status-card" key={target}><span>{target}</span><strong>{count}</strong></article>
      ))}
    </section>
  </>
}

function TryClassifierTab({ busy, contextTypes, classify }) {
  const [text, setText] = useState('')
  const [contextType, setContextType] = useState('public_chat_question')
  const [result, setResult] = useState(null)

  return <>
    <h3>Classify free text</h3>
    <p>Nothing here calls the model, RAG, web, tool, or memory -- this only runs the deterministic classification pipeline and shows its recommendation.</p>
    <div className="panel-controls">
      <label>Context type
        <select value={contextType} onChange={(e) => setContextType(e.target.value)}>
          {(contextTypes.length ? contextTypes : ['public_chat_question']).map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
    </div>
    <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a question in Tamil, English, or Tanglish..." />
    <button disabled={Boolean(busy) || !text.trim()} onClick={async () => setResult(await classify(text, contextType))}>Classify</button>
    {result && <ClassificationResultView result={result} />}
  </>
}

function StructuredRecordTab({ busy, contextTypes, classify }) {
  const [contextType, setContextType] = useState(contextTypes[0] || 'rag_record')
  const [fieldsJson, setFieldsJson] = useState('{\n  "title": "",\n  "summary": ""\n}')
  const [result, setResult] = useState(null)
  const [jsonError, setJsonError] = useState('')

  async function submit() {
    setJsonError('')
    let record
    try { record = JSON.parse(fieldsJson) } catch { setJsonError('Record must be valid JSON.'); return }
    setResult(await classify(contextType, record))
  }

  return <>
    <h3>Classify a structured record</h3>
    <p>For RAG records, dataset candidates, training candidates, evaluation prompts, and future knowledge-gap cases -- no knowledge-gap registry exists yet in this phase.</p>
    <div className="panel-controls">
      <label>Context type
        <select value={contextType} onChange={(e) => setContextType(e.target.value)}>
          {contextTypes.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
    </div>
    <textarea rows={6} value={fieldsJson} onChange={(e) => setFieldsJson(e.target.value)} />
    {jsonError && <div className="form-error" role="alert">{jsonError}</div>}
    <button disabled={Boolean(busy)} onClick={submit}>Classify record</button>
    {result && <ClassificationResultView result={result} />}
  </>
}

function ClassificationResultView({ result }) {
  return <div className="history-panel">
    <div className="notice">{RECOMMENDATION_ONLY_NOTE}</div>
    <p>Language: {result.language_category} · Intent: {result.intent} ({result.intent_confidence_band})</p>
    <p>Domain: {result.domain}{result.subdomain ? ` / ${result.subdomain}` : ''} ({result.domain_confidence_band})</p>
    <p>Freshness: {result.freshness} ({result.freshness_confidence_band}) · Ambiguity: {result.ambiguity}</p>
    <p>Safety risk: {result.safety_risk}{result.safety_matched_category ? ` (${result.safety_matched_category})` : ''}</p>
    <p>Evidence requirement: {result.evidence_requirement}</p>
    <p><strong>Execution route recommendation: {result.execution_route}</strong> ({result.execution_route_confidence_band})</p>
    <p><strong>Learning target recommendation: {result.learning_target}</strong> ({result.learning_target_confidence_band})</p>
    {result.tamil_first_policy_violation && <p className="form-error" role="alert">Tamil-first policy violation detected -- please report this.</p>}
    <p>Requires human review: {result.requires_human_review ? 'Yes' : 'No'}</p>
    <h4>Reason codes</h4>
    <ul>{(result.all_reason_codes || []).map((code) => <li key={code}>{code}</li>)}</ul>
    {result.public_id && <p>Decision id: {result.public_id}</p>}
  </div>
}

function RecentDecisionsTab({ decisions, routeFilter, setRouteFilter, refresh, loadOne }) {
  const [detail, setDetail] = useState(null)
  return <>
    <h3>Recent classification decisions</h3>
    <p>No raw question text is stored -- only the SHA-256 input hash and the structured classification outputs.</p>
    <div className="panel-controls">
      <input placeholder="Filter by execution route" value={routeFilter} onChange={(e) => setRouteFilter(e.target.value)} />
      <button type="button" onClick={() => refresh(routeFilter)}>Filter</button>
      <button type="button" onClick={() => refresh('')}>Clear filter</button>
    </div>
    <table>
      <thead><tr><th>Domain</th><th>Route</th><th>Target</th><th>Review</th><th>Created</th><th></th></tr></thead>
      <tbody>
        {decisions.map((d) => (
          <tr key={d.public_id}>
            <td>{d.domain}{d.subdomain ? `/${d.subdomain}` : ''}</td>
            <td>{d.execution_route}</td>
            <td>{d.learning_target}</td>
            <td>{d.requires_human_review ? 'Yes' : 'No'}</td>
            <td>{d.created_at}</td>
            <td><button type="button" onClick={async () => setDetail(await loadOne(d.public_id))}>Details</button></td>
          </tr>
        ))}
      </tbody>
    </table>
    {detail && <div className="history-panel"><pre>{JSON.stringify(detail, null, 2)}</pre></div>}
  </>
}

function ReasonCodesTab({ reasonCodes, load }) {
  const entries = Object.entries(reasonCodes || {})
  return <>
    <h3>Reason-code registry</h3>
    <button type="button" onClick={load}>Load reason codes</button>
    <p>{entries.length} registered reason codes.</p>
    <table>
      <thead><tr><th>Code</th><th>Description</th></tr></thead>
      <tbody>{entries.map(([code, description]) => <tr key={code}><td>{code}</td><td>{description}</td></tr>)}</tbody>
    </table>
  </>
}

function PolicyTab({ policy }) {
  if (!policy) return <div className="notice">Loading...</div>
  return <>
    <h3>Classification policy</h3>
    <p>Versioned, checksummed, schema-validated data file -- keyword lexicons only, no executable content.</p>
    <div className="history-panel">
      <p>Valid: {policy.valid ? 'Yes' : 'No'}</p>
      <p>Policy version: {policy.policy_version}</p>
      <p>Taxonomy version: {policy.taxonomy_version}</p>
      <p>Checksum (SHA-256): {policy.policy_checksum_sha256}</p>
      <p>Domain count: {policy.domain_count} · Intent count: {policy.intent_count}</p>
    </div>
  </>
}
