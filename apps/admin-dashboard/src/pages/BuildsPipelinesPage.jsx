import { useEffect, useState } from 'react'
import {
  cancelGovernedBuild, confirmGovernedBuild, createGovernedBuild, executeGovernedBuild,
  generateGovernedBuildManifest, governedBuild, governedBuildBlockedItems, governedBuildHistory,
  governedBuildItems, governedBuildManifest, governedBuildSummary, governedBuilds,
  governedCommercialPreflight, governedEvaluationHandoff, governedPretrainingHandoff,
  governedPublicExportPreflight, governedRagHandoff, governedSftHandoff,
  governedTokenizerHandoff, lineageForEntity, preflightGovernedBuild, previewGovernedBuild,
  updateGovernedBuildSelection,
} from '../services/api.js'

const tabs = [
  'Overview', 'Create Build', 'Build Preview', 'Blocked Records', 'Dataset Versions',
  'RAG Handoffs', 'Tokenizer & Training', 'Evaluation Builds', 'Manifests', 'Lineage', 'History',
]

const PIPELINE_TARGETS = [
  'dataset_version', 'rag', 'tokenizer', 'pretraining', 'instruction_tuning',
  'evaluation', 'commercial_release', 'public_export',
]

const BUILD_STATUSES = [
  'draft', 'preflight_running', 'preflight_ready', 'blocked', 'approved_to_build',
  'building', 'completed', 'failed', 'cancelled',
]

export default function BuildsPipelinesPage() {
  const [tab, setTab] = useState('Overview')
  const [busy, setBusy] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState('')

  const [summary, setSummary] = useState({})
  const [buildItems, setBuildItems] = useState([]), [statusFilter, setStatusFilter] = useState('')
  const [selectedBuildId, setSelectedBuildId] = useState('')
  const [buildDetail, setBuildDetail] = useState(null)
  const [previewResult, setPreviewResult] = useState(null)
  const [items, setItems] = useState([])
  const [blocked, setBlocked] = useState([])
  const [manifest, setManifest] = useState(null)
  const [history, setHistory] = useState(null)
  const [lineageEntityId, setLineageEntityId] = useState(''), [lineage, setLineage] = useState(null)

  useEffect(() => { refreshSummary(); refreshBuilds() }, [])

  async function refreshSummary() {
    try { setSummary((await governedBuildSummary()).counts_by_status || {}) } catch (reason) { setError(reason.message) }
  }

  async function refreshBuilds(status = statusFilter) {
    try {
      const query = status ? `?status=${status}` : ''
      setBuildItems((await governedBuilds(query)).items)
    } catch (reason) { setError(reason.message) }
  }

  async function openBuild(id) {
    try {
      setSelectedBuildId(id)
      setBuildDetail(await governedBuild(id))
      setPreviewResult(null)
      setItems([])
      setBlocked([])
      setManifest(null)
      setHistory(null)
    } catch (reason) { setError(reason.message) }
  }

  async function action(label, callback, { keepTab } = {}) {
    setBusy(label); setError('')
    try {
      const result = await callback()
      if (selectedBuildId) setBuildDetail(await governedBuild(selectedBuildId))
      await refreshBuilds()
      await refreshSummary()
      setNotice(`${label} completed.`)
      return result
    } catch (reason) { setError(reason.message) } finally { setBusy('') }
    return undefined
  }

  return <section className="documents-workspace">
    <header className="section-heading">
      <div><h2>Builds &amp; Pipelines</h2><p>Governed, target-specific dataset builds and their handoffs into RAG, tokenizer, pretraining, instruction-tuning, and evaluation -- nothing starts automatically.</p></div>
      <button onClick={() => { refreshSummary(); refreshBuilds() }}>Refresh</button>
    </header>
    <div className="dataset-tabs">{tabs.map((value) => <button key={value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>{value}</button>)}</div>
    {notice && <div className="success-note" role="status">{notice}</div>}
    {error && <div className="form-error" role="alert">{error}</div>}

    {tab === 'Overview' && <OverviewTab summary={summary} buildItems={buildItems} openBuild={(id) => { openBuild(id); setTab('Build Preview') }} />}

    {tab === 'Create Build' && <CreateBuildTab
      busy={busy}
      create={(body) => action('Build request created', async () => {
        const created = await createGovernedBuild(body)
        await openBuild(created.public_id)
        setTab('Build Preview')
        return created
      })}
    />}

    {tab === 'Build Preview' && <BuildPreviewTab
      buildItems={buildItems} selectedBuildId={selectedBuildId} buildDetail={buildDetail} busy={busy}
      openBuild={openBuild}
      preview={() => action('Preview computed', async () => setPreviewResult(await previewGovernedBuild(selectedBuildId)))}
      previewResult={previewResult}
      preflight={() => action('Preflight run', () => preflightGovernedBuild(selectedBuildId))}
      confirm={() => action('Build confirmed', () => confirmGovernedBuild(selectedBuildId))}
      execute={() => action('Build executed', () => executeGovernedBuild(selectedBuildId))}
      cancel={() => action('Build cancelled', () => cancelGovernedBuild(selectedBuildId))}
      loadItems={async () => setItems((await governedBuildItems(selectedBuildId)).items)}
      items={items}
      updateSelection={(itemId, included) => action('Selection updated', () => updateGovernedBuildSelection(selectedBuildId, itemId, included))}
    />}

    {tab === 'Blocked Records' && <BlockedRecordsTab
      selectedBuildId={selectedBuildId}
      loadBlocked={async () => setBlocked((await governedBuildBlockedItems(selectedBuildId)).items)}
      blocked={blocked}
    />}

    {tab === 'Dataset Versions' && <TargetHandoffTab
      title="Dataset Version" busy={busy} selectedBuildId={selectedBuildId} buildDetail={buildDetail}
      expectedPipeline="dataset_version"
      action={(label, fn) => action(label, fn)}
    />}

    {tab === 'RAG Handoffs' && <RagHandoffTab
      busy={busy} selectedBuildId={selectedBuildId} buildDetail={buildDetail}
      ingest={(spaceId, title) => action('RAG ingestion', () => governedRagHandoff(selectedBuildId, { knowledge_space_public_id: spaceId, title }))}
    />}

    {tab === 'Tokenizer & Training' && <TrainingHandoffTab
      busy={busy} selectedBuildId={selectedBuildId} buildDetail={buildDetail}
      tokenizerHandoff={() => action('Tokenizer handoff', () => governedTokenizerHandoff(selectedBuildId))}
      pretrainingHandoff={() => action('Pretraining handoff', () => governedPretrainingHandoff(selectedBuildId))}
      sftHandoff={() => action('SFT handoff', () => governedSftHandoff(selectedBuildId))}
    />}

    {tab === 'Evaluation Builds' && <EvaluationHandoffTab
      busy={busy} selectedBuildId={selectedBuildId} buildDetail={buildDetail}
      evaluationHandoff={() => action('Evaluation handoff', () => governedEvaluationHandoff(selectedBuildId))}
      publicExportPreflight={async () => await governedPublicExportPreflight(selectedBuildId)}
      commercialPreflight={async () => await governedCommercialPreflight(selectedBuildId)}
    />}

    {tab === 'Manifests' && <ManifestsTab
      busy={busy} selectedBuildId={selectedBuildId}
      generate={() => action('Manifest generated', async () => setManifest(await generateGovernedBuildManifest(selectedBuildId)))}
      load={async () => setManifest(await governedBuildManifest(selectedBuildId))}
      manifest={manifest}
    />}

    {tab === 'Lineage' && <LineageTab
      lineageEntityId={lineageEntityId} setLineageEntityId={setLineageEntityId}
      trace={async () => setLineage(await lineageForEntity('dataset_record', lineageEntityId))}
      lineage={lineage}
    />}

    {tab === 'History' && <HistoryTab
      selectedBuildId={selectedBuildId}
      load={async () => setHistory(await governedBuildHistory(selectedBuildId))}
      history={history}
    />}
  </section>
}

function OverviewTab({ summary, buildItems, openBuild }) {
  return <>
    <h3>Build requests by status</h3>
    <section className="metric-grid">
      {BUILD_STATUSES.map((status) => <article className="status-card" key={status}><span>{status.replaceAll('_', ' ')}</span><strong>{summary[status] || 0}</strong></article>)}
    </section>
    <h3>Recent build requests</h3>
    <div className="candidate-list">
      {buildItems.slice(0, 10).map((item) => (
        <article key={item.public_id}>
          <header><strong>{item.build_code}</strong><span>{item.target_pipeline} · {item.status}</span></header>
          <button type="button" onClick={() => openBuild(item.public_id)}>Open</button>
        </article>
      ))}
    </div>
  </>
}

function CreateBuildTab({ busy, create }) {
  const [targetPipeline, setTargetPipeline] = useState('dataset_version')
  const [buildLabel, setBuildLabel] = useState('')
  const [datasetName, setDatasetName] = useState(''), [datasetVersion, setDatasetVersion] = useState('v1')
  const [recordTypes, setRecordTypes] = useState(''), [languages, setLanguages] = useState('')
  const [includeIds, setIncludeIds] = useState(''), [excludeIds, setExcludeIds] = useState('')

  function buildConfiguration() {
    const configuration = {}
    if (datasetName.trim()) configuration.dataset_name = datasetName.trim()
    if (datasetVersion.trim()) configuration.dataset_version = datasetVersion.trim()
    if (recordTypes.trim()) configuration.record_types = recordTypes.split(',').map((s) => s.trim()).filter(Boolean)
    if (languages.trim()) configuration.languages = languages.split(',').map((s) => s.trim()).filter(Boolean)
    if (includeIds.trim()) configuration.include_entity_ids = includeIds.split(',').map((s) => s.trim()).filter(Boolean)
    if (excludeIds.trim()) configuration.exclude_entity_ids = excludeIds.split(',').map((s) => s.trim()).filter(Boolean)
    return configuration
  }

  return <>
    <h3>Step 1: choose a target pipeline</h3>
    <select value={targetPipeline} onChange={(e) => setTargetPipeline(e.target.value)}>
      {PIPELINE_TARGETS.map((t) => <option key={t} value={t}>{t}</option>)}
    </select>

    <h3>Step 2: selection filters (optional)</h3>
    <div className="panel-controls">
      <label>Record types (comma-separated)<input value={recordTypes} onChange={(e) => setRecordTypes(e.target.value)} /></label>
      <label>Languages (comma-separated)<input value={languages} onChange={(e) => setLanguages(e.target.value)} /></label>
    </div>
    <div className="panel-controls">
      <label>Include entity IDs (comma-separated)<input value={includeIds} onChange={(e) => setIncludeIds(e.target.value)} /></label>
      <label>Exclude entity IDs (comma-separated)<input value={excludeIds} onChange={(e) => setExcludeIds(e.target.value)} /></label>
    </div>

    <h3>Step 3: configuration</h3>
    <div className="panel-controls">
      <label>Build label<input value={buildLabel} onChange={(e) => setBuildLabel(e.target.value)} /></label>
      <label>Dataset name<input value={datasetName} onChange={(e) => setDatasetName(e.target.value)} /></label>
      <label>Dataset version<input value={datasetVersion} onChange={(e) => setDatasetVersion(e.target.value)} /></label>
    </div>

    <button
      disabled={Boolean(busy)}
      onClick={() => create({ target_pipeline: targetPipeline, build_label: buildLabel, configuration: buildConfiguration() })}
    >Create build request</button>
    <p>After creating, go to the Build Preview tab to run preview/preflight, resolve blockers, and confirm.</p>
  </>
}

function BuildPreviewTab({
  buildItems, selectedBuildId, buildDetail, busy, openBuild, preview, previewResult,
  preflight, confirm, execute, cancel, loadItems, items, updateSelection,
}) {
  return <>
    <h3>Select a build request</h3>
    <select value={selectedBuildId} onChange={(e) => openBuild(e.target.value)}>
      <option value="">Choose a build</option>
      {buildItems.map((b) => <option key={b.public_id} value={b.public_id}>{b.build_code} -- {b.target_pipeline} ({b.status})</option>)}
    </select>
    {!buildDetail ? <div className="notice">Select or create a build request first.</div> : (
      <>
        <h4>{buildDetail.build_code} <span className="review-status-badge">{buildDetail.status}</span></h4>
        <p>Target pipeline: {buildDetail.target_pipeline}</p>

        <div className="review-actions">
          <button disabled={Boolean(busy)} onClick={preview}>Preview (ephemeral)</button>
          <button disabled={Boolean(busy)} onClick={preflight}>Run preflight</button>
          <button disabled={Boolean(busy) || buildDetail.status !== 'preflight_ready'} onClick={confirm}>Confirm</button>
          <button disabled={Boolean(busy) || buildDetail.status !== 'approved_to_build'} onClick={execute}>Execute</button>
          <button disabled={Boolean(busy)} onClick={cancel}>Cancel</button>
        </div>

        {previewResult && (
          <div className="history-panel">
            <h4>Preview</h4>
            <p>Eligible: {previewResult.eligible_records.length} · Blocked: {previewResult.blocked_records.length} · Warning: {previewResult.warning_records.length} · Excluded: {previewResult.excluded_records.length}</p>
            <p>Source summary: {JSON.stringify(previewResult.source_summary)}</p>
            <p>Rights summary: {JSON.stringify(previewResult.rights_summary)}</p>
            <p>Language distribution: {JSON.stringify(previewResult.language_distribution)}</p>
            <p>Record type distribution: {JSON.stringify(previewResult.record_type_distribution)}</p>
          </div>
        )}

        <h4>Selected items</h4>
        <button type="button" onClick={loadItems}>Load items</button>
        <div className="candidate-list">
          {items.map((item) => (
            <article key={item.public_id}>
              <header><strong>{item.entity_public_id}</strong><span>{item.decision}</span></header>
              <p>{item.decision_code}{item.blocking_reasons?.length ? ` -- ${item.blocking_reasons.join(', ')}` : ''}</p>
              <label><input type="checkbox" checked={Boolean(item.included)} disabled={item.decision === 'blocked'} onChange={(e) => updateSelection(item.public_id, e.target.checked)} /> Included</label>
            </article>
          ))}
        </div>
      </>
    )}
  </>
}

function BlockedRecordsTab({ selectedBuildId, loadBlocked, blocked }) {
  if (!selectedBuildId) return <div className="notice">Select a build from the Build Preview tab first.</div>
  return <>
    <h3>Blocked records</h3>
    <button type="button" onClick={loadBlocked}>Load blocked records</button>
    <table>
      <thead><tr><th>Entity</th><th>Source</th><th>Decision code</th><th>Blocking reasons</th></tr></thead>
      <tbody>
        {blocked.map((item) => (
          <tr key={item.public_id}>
            <td>{item.entity_public_id}</td>
            <td>{item.source_public_id || '--'}</td>
            <td>{item.decision_code}</td>
            <td>{(item.blocking_reasons || []).join('; ')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </>
}

function TargetHandoffTab({ selectedBuildId, buildDetail }) {
  if (!selectedBuildId) return <div className="notice">Select a build from the Build Preview tab first.</div>
  return <>
    <h3>Dataset version result</h3>
    <p>Status: {buildDetail?.status}</p>
    {buildDetail?.result_entity_type === 'dataset_version' && <p>Dataset version: {buildDetail.result_entity_public_id}</p>}
    <p>Execute the build from the Build Preview tab to create its dataset version -- this tab only reports the result.</p>
  </>
}

function RagHandoffTab({ busy, selectedBuildId, buildDetail, ingest }) {
  const [spaceId, setSpaceId] = useState(''), [title, setTitle] = useState('')
  if (!selectedBuildId) return <div className="notice">Select a build from the Build Preview tab first.</div>
  if (buildDetail?.target_pipeline !== 'rag') return <div className="notice">This build was not created for the rag pipeline.</div>
  return <>
    <h3>RAG ingestion</h3>
    <p>Requires the build to be completed (a dataset version created) first.</p>
    <div className="panel-controls">
      <label>Knowledge space public id<input value={spaceId} onChange={(e) => setSpaceId(e.target.value)} /></label>
      <label>RAG source title<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
    </div>
    <button disabled={Boolean(busy) || !spaceId.trim() || !title.trim()} onClick={() => ingest(spaceId, title)}>Ingest into RAG</button>
    <p>The resulting RAG source is never activated automatically -- build and activate its index through the existing Knowledge &amp; RAG workflow.</p>
  </>
}

function TrainingHandoffTab({ busy, selectedBuildId, buildDetail, tokenizerHandoff, pretrainingHandoff, sftHandoff }) {
  if (!selectedBuildId) return <div className="notice">Select a build from the Build Preview tab first.</div>
  return <>
    <h3>Tokenizer / pretraining / instruction-tuning handoff</h3>
    <p>Marks a completed, governed dataset version as ready for the matching pipeline -- none of these starts a run automatically.</p>
    <div className="review-actions">
      <button disabled={Boolean(busy) || buildDetail?.target_pipeline !== 'tokenizer'} onClick={tokenizerHandoff}>Tokenizer handoff</button>
      <button disabled={Boolean(busy) || buildDetail?.target_pipeline !== 'pretraining'} onClick={pretrainingHandoff}>Pretraining handoff</button>
      <button disabled={Boolean(busy) || buildDetail?.target_pipeline !== 'instruction_tuning'} onClick={sftHandoff}>SFT handoff</button>
    </div>
  </>
}

function EvaluationHandoffTab({ busy, selectedBuildId, buildDetail, evaluationHandoff, publicExportPreflight, commercialPreflight }) {
  const [result, setResult] = useState(null)
  if (!selectedBuildId) return <div className="notice">Select a build from the Build Preview tab first.</div>
  return <>
    <h3>Evaluation handoff</h3>
    <button disabled={Boolean(busy) || buildDetail?.target_pipeline !== 'evaluation'} onClick={evaluationHandoff}>Evaluation handoff</button>

    <h3>Public export / commercial preflight</h3>
    <div className="panel-controls">
      <button disabled={buildDetail?.target_pipeline !== 'public_export'} type="button" onClick={async () => setResult(await publicExportPreflight())}>Run public-export preflight</button>
      <button disabled={buildDetail?.target_pipeline !== 'commercial_release'} type="button" onClick={async () => setResult(await commercialPreflight())}>Run commercial preflight</button>
    </div>
    {result && (
      <div className="history-panel">
        <p>Allowed: {result.allowed_count} · Blocked: {result.blocked_count}</p>
        <ul>{result.blocked_items.map((item) => <li key={item.entity_public_id}>{item.entity_public_id}: {item.decision_code} {item.expired ? '(expired)' : ''}</li>)}</ul>
      </div>
    )}
  </>
}

function ManifestsTab({ busy, selectedBuildId, generate, load, manifest }) {
  if (!selectedBuildId) return <div className="notice">Select a build from the Build Preview tab first.</div>
  return <>
    <h3>Manifest</h3>
    <div className="panel-controls">
      <button disabled={Boolean(busy)} onClick={generate}>Generate manifest</button>
      <button type="button" onClick={load}>Load manifest</button>
    </div>
    {manifest && (
      <div className="history-panel">
        <h4>Governance extension</h4>
        <p>Record count: {manifest.governance_extension?.record_count}</p>
        <p>Language counts: {JSON.stringify(manifest.governance_extension?.language_counts)}</p>
        <p>Source manifest checksum: {manifest.governance_extension?.source_manifest_checksum}</p>
        <p>Record manifest checksum: {manifest.governance_extension?.record_manifest_checksum}</p>
        <p>Attribution entries: {(manifest.governance_extension?.attribution_entries || []).length}</p>
        <h4>Dataset version manifest</h4>
        <p>{manifest.dataset_version_manifest ? `schema_version ${manifest.dataset_version_manifest.schema_version}` : 'Not available.'}</p>
      </div>
    )}
  </>
}

function LineageTab({ lineageEntityId, setLineageEntityId, trace, lineage }) {
  return <>
    <h3>Source-to-model lineage trace</h3>
    <p>Anchored at a dataset_record -- shows every upstream/downstream edge this system actually recorded; never fabricates a missing link.</p>
    <div className="panel-controls">
      <input placeholder="dataset_record public id" value={lineageEntityId} onChange={(e) => setLineageEntityId(e.target.value)} />
      <button disabled={!lineageEntityId.trim()} type="button" onClick={trace}>Trace</button>
    </div>
    {lineage && (
      <div className="history-panel">
        <p>{lineage.complete ? 'Lineage found.' : 'Lineage incomplete -- no edges recorded for this entity.'}</p>
        <h4>Nodes</h4>
        <ul>{lineage.nodes.map((n) => <li key={`${n.entity_type}-${n.entity_id}`}>{n.entity_type}: {n.entity_id}</li>)}</ul>
        <h4>Edges</h4>
        <ul>{lineage.edges.map((e) => <li key={e.public_id}>{e.upstream_entity_type}:{e.upstream_entity_id} --{e.relationship_type}--&gt; {e.downstream_entity_type}:{e.downstream_entity_id}</li>)}</ul>
      </div>
    )}
  </>
}

function HistoryTab({ selectedBuildId, load, history }) {
  if (!selectedBuildId) return <div className="notice">Select a build from the Build Preview tab first.</div>
  return <>
    <h3>Build request history</h3>
    <button type="button" onClick={load}>Load history</button>
    {history && <ol>{history.items.map((e) => <li key={e.public_id}>{e.event_type} by {e.performed_by_admin_public_id} at {e.created_at}{e.notes ? ` -- ${e.notes}` : ''}</li>)}</ol>}
  </>
}
