import { useEffect, useState } from 'react'
import {
  coreModelAssignments,
  coreModelCapabilities,
  coreModelCheckpoints,
  coreModelChecks,
  coreModelConfigs,
  coreModelFamilies,
  coreModelVersion,
  coreModelVersionAction,
  coreModelVersions,
  createCoreModelConfig,
  createCoreModelFamily,
  createCoreModelVersion,
  estimateCoreModelConfig,
  tokenizerVersions,
  validateCoreModelConfig,
  verifyCoreModelCheckpoint,
} from '../services/api.js'

const tabs = ['Overview', 'Families', 'Configurations', 'Versions', 'Architecture Checks', 'Smoke Test', 'Checkpoints', 'Assignments']

// Real state progression this UI can actually reach and display -- taken
// directly from `core_model_versions.lifecycle_status`'s own CHECK
// constraint, never invented. 'active' and 'retired' are deliberately
// excluded from this page's own action buttons (Phase 2.7D safety scope:
// this page stops at "staged" -- activating a version, and the separate
// Public Chat assignment/activation gate, are governed elsewhere and are
// never wired to a button here).
const LIFECYCLE_ORDER = ['draft', 'initialized', 'architecture_verified', 'smoke_tested', 'staging', 'active', 'failed', 'retired']

const defaultFamilyForm = { name: '', display_name: '', description: '' }
const defaultConfigForm = {
  name: '', config_version: 'v1', tokenizer_version_public_id: '', preset: 'micro',
  context_length: '', hidden_size: '', intermediate_size: '', num_hidden_layers: '',
  num_attention_heads: '', num_key_value_heads: '',
}
const defaultVersionForm = { family_public_id: '', config_public_id: '', version: 'v1', initialization_seed: 42 }

function numberOrUndefined(value) {
  if (value === '' || value === null || value === undefined) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

export default function CoreModelPage() {
  const [active, setActive] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: null, data: {} })
  const [tokenizers, setTokenizers] = useState([])
  const [familyForm, setFamilyForm] = useState(defaultFamilyForm)
  const [configForm, setConfigForm] = useState(defaultConfigForm)
  const [versionForm, setVersionForm] = useState(defaultVersionForm)
  const [estimate, setEstimate] = useState(null)
  const [formError, setFormError] = useState({ family: '', config: '', version: '' })
  const [busy, setBusy] = useState('')
  const [selectedVersionId, setSelectedVersionId] = useState(null)
  const [versionDetail, setVersionDetail] = useState(null)
  const [versionDetailError, setVersionDetailError] = useState('')

  async function load() {
    setState((old) => ({ ...old, loading: true, error: null }))
    try {
      const [capabilities, families, configs, versions, assignments, tokenizerList] = await Promise.all([
        coreModelCapabilities(),
        coreModelFamilies(),
        coreModelConfigs(),
        coreModelVersions(),
        coreModelAssignments(),
        tokenizerVersions('?page_size=100'),
      ])
      setState({ loading: false, error: null, data: { capabilities, families, configs, versions, assignments } })
      setTokenizers(tokenizerList.items ?? [])
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  useEffect(() => { load() }, [])

  async function loadVersionDetail(publicId) {
    setSelectedVersionId(publicId)
    setVersionDetailError('')
    try {
      const [version, checks, checkpoints] = await Promise.all([
        coreModelVersion(publicId),
        coreModelChecks(publicId),
        coreModelCheckpoints(publicId),
      ])
      setVersionDetail({ version, checks: checks.items ?? [], checkpoints: checkpoints.items ?? [] })
    } catch (error) {
      setVersionDetailError(error.message)
    }
  }

  async function submitFamily(event) {
    event.preventDefault()
    setFormError((old) => ({ ...old, family: '' }))
    setBusy('family')
    try {
      await createCoreModelFamily(familyForm)
      setFamilyForm(defaultFamilyForm)
      await load()
    } catch (error) {
      setFormError((old) => ({ ...old, family: error.message }))
    } finally {
      setBusy('')
    }
  }

  async function submitEstimate() {
    setFormError((old) => ({ ...old, config: '' }))
    setBusy('estimate')
    try {
      const payload = buildConfigPayload(configForm)
      setEstimate(await estimateCoreModelConfig(payload))
    } catch (error) {
      setEstimate(null)
      setFormError((old) => ({ ...old, config: error.message }))
    } finally {
      setBusy('')
    }
  }

  async function submitConfig(event) {
    event.preventDefault()
    setFormError((old) => ({ ...old, config: '' }))
    setBusy('config')
    try {
      const payload = buildConfigPayload(configForm)
      await createCoreModelConfig(payload)
      setConfigForm(defaultConfigForm)
      setEstimate(null)
      await load()
    } catch (error) {
      setFormError((old) => ({ ...old, config: error.message }))
    } finally {
      setBusy('')
    }
  }

  async function runValidateConfig(publicId) {
    setBusy(`validate-${publicId}`)
    try {
      await validateCoreModelConfig(publicId)
      await load()
    } catch (error) {
      setFormError((old) => ({ ...old, config: error.message }))
    } finally {
      setBusy('')
    }
  }

  async function submitVersion(event) {
    event.preventDefault()
    setFormError((old) => ({ ...old, version: '' }))
    setBusy('version')
    try {
      await createCoreModelVersion({ ...versionForm, initialization_seed: Number(versionForm.initialization_seed) || 42 })
      setVersionForm(defaultVersionForm)
      await load()
    } catch (error) {
      setFormError((old) => ({ ...old, version: error.message }))
    } finally {
      setBusy('')
    }
  }

  async function runVersionAction(publicId, action) {
    setBusy(`${action}-${publicId}`)
    setVersionDetailError('')
    try {
      await coreModelVersionAction(publicId, action)
      await load()
      await loadVersionDetail(publicId)
    } catch (error) {
      setVersionDetailError(error.message)
    } finally {
      setBusy('')
    }
  }

  async function runVerifyCheckpoint(checkpointId) {
    setBusy(`verify-checkpoint-${checkpointId}`)
    try {
      await verifyCoreModelCheckpoint(checkpointId)
      if (selectedVersionId) await loadVersionDetail(selectedVersionId)
    } catch (error) {
      setVersionDetailError(error.message)
    } finally {
      setBusy('')
    }
  }

  if (state.loading) return <section className="panel"><p>Loading Core Model foundation…</p></section>
  if (state.error) return <section className="panel error"><p>{state.error}</p></section>
  const { capabilities, families, configs, versions, assignments } = state.data
  const validatedConfigs = (configs.items ?? []).filter((item) => item.status === 'validated')
  const initialized = versions.items?.filter((item) => ['initialized', 'architecture_verified', 'smoke_tested', 'staging', 'active'].includes(item.lifecycle_status)).length ?? 0

  return (
    <section className="stack">
      <div className="page-title">
        <div>
          <p className="eyebrow">Architecture foundation</p>
          <h1>Core Model</h1>
          <p>CPU-first decoder-only Transformer setup. Random weights are not language-capable. This page operates the real Family → Config → Version lifecycle through its existing backend — it stops at "staged"; activation and Public Chat assignment remain governed elsewhere and are never available from here.</p>
        </div>
        <button onClick={load}>Refresh</button>
      </div>
      <div className="tabs">{tabs.map((tab) => <button key={tab} className={active === tab ? 'active' : ''} onClick={() => setActive(tab)}>{tab}</button>)}</div>

      {active === 'Overview' && <div className="grid cards">
        <Card title="PyTorch" value={capabilities.pytorch_available ? capabilities.pytorch_version : 'Unavailable'} note={`CUDA: ${capabilities.cuda_available ? 'available' : 'not required'}`} />
        <Card title="Families" value={families.total ?? 0} note="Logical model lines" />
        <Card title="Configs" value={configs.total ?? 0} note={`${validatedConfigs.length} validated`} />
        <Card title="Initialized" value={initialized} note="Untrained architecture versions" />
      </div>}

      {active === 'Families' && <>
        <form className="inline-form" onSubmit={submitFamily}>
          <h2>Create family</h2>
          <label>Name<input value={familyForm.name} onChange={(e) => setFamilyForm({ ...familyForm, name: e.target.value })} placeholder="brud-text" required /></label>
          <label>Display name<input value={familyForm.display_name} onChange={(e) => setFamilyForm({ ...familyForm, display_name: e.target.value })} placeholder="Brud Text" required /></label>
          <label>Description<input value={familyForm.description} onChange={(e) => setFamilyForm({ ...familyForm, description: e.target.value })} /></label>
          <button type="submit" disabled={busy === 'family'}>{busy === 'family' ? 'Creating…' : 'Create family'}</button>
        </form>
        {formError.family && <div className="notice error-notice">{formError.family}</div>}
        <List title="Families" items={families.items} fields={['name', 'display_name', 'status']} empty="No core model families yet." />
      </>}

      {active === 'Configurations' && <>
        <form className="inline-form" onSubmit={submitConfig}>
          <h2>Create configuration</h2>
          <label>Name<input value={configForm.name} onChange={(e) => setConfigForm({ ...configForm, name: e.target.value })} placeholder="brud-micro" required /></label>
          <label>Config version<input value={configForm.config_version} onChange={(e) => setConfigForm({ ...configForm, config_version: e.target.value })} required /></label>
          <label>Tokenizer version
            <select value={configForm.tokenizer_version_public_id} onChange={(e) => setConfigForm({ ...configForm, tokenizer_version_public_id: e.target.value })} required>
              <option value="">Select tokenizer</option>
              {tokenizers.map((item) => <option key={item.public_id} value={item.public_id}>{item.version} · {item.lifecycle_status}</option>)}
            </select>
          </label>
          <label>Preset
            <select value={configForm.preset} onChange={(e) => setConfigForm({ ...configForm, preset: e.target.value })}>
              <option value="micro">micro</option>
              <option value="tiny">tiny</option>
            </select>
          </label>
          {['context_length', 'hidden_size', 'intermediate_size', 'num_hidden_layers', 'num_attention_heads', 'num_key_value_heads'].map((key) => (
            <label key={key}>{key.replaceAll('_', ' ')} (optional override)
              <input value={configForm[key]} onChange={(e) => setConfigForm({ ...configForm, [key]: e.target.value })} placeholder="preset default" />
            </label>
          ))}
          <div className="document-actions">
            <button type="button" onClick={submitEstimate} disabled={busy === 'estimate' || !configForm.tokenizer_version_public_id}>{busy === 'estimate' ? 'Estimating…' : 'Estimate parameters'}</button>
            <button type="submit" disabled={busy === 'config' || !configForm.tokenizer_version_public_id}>{busy === 'config' ? 'Creating…' : 'Create config'}</button>
          </div>
        </form>
        {estimate && <div className="notice">Estimated parameters: {estimate.parameter_count_estimate.toLocaleString()} · training memory: {(estimate.memory_estimates.training_adamw / 1e6).toFixed(1)} MB · checksum {estimate.config_checksum_sha256.slice(0, 12)}</div>}
        {formError.config && <div className="notice error-notice">{formError.config}</div>}
        <List
          title="Configurations"
          items={configs.items}
          fields={['name', 'config_version', 'status', 'parameter_count_estimate', 'memory_estimate_bytes']}
          empty="No configurations yet — create one above."
          renderActions={(item) => item.status !== 'validated' && (
            <button onClick={() => runValidateConfig(item.public_id)} disabled={busy === `validate-${item.public_id}`}>
              {busy === `validate-${item.public_id}` ? 'Validating…' : 'Validate'}
            </button>
          )}
        />
      </>}

      {active === 'Versions' && <>
        <form className="inline-form" onSubmit={submitVersion}>
          <h2>Create version</h2>
          <label>Family
            <select value={versionForm.family_public_id} onChange={(e) => setVersionForm({ ...versionForm, family_public_id: e.target.value })} required>
              <option value="">Select family</option>
              {(families.items ?? []).map((item) => <option key={item.public_id} value={item.public_id}>{item.display_name}</option>)}
            </select>
          </label>
          <label>Validated config
            <select value={versionForm.config_public_id} onChange={(e) => setVersionForm({ ...versionForm, config_public_id: e.target.value })} required>
              <option value="">Select validated config</option>
              {validatedConfigs.map((item) => <option key={item.public_id} value={item.public_id}>{item.name} {item.config_version}</option>)}
            </select>
          </label>
          <label>Version<input value={versionForm.version} onChange={(e) => setVersionForm({ ...versionForm, version: e.target.value })} required /></label>
          <label>Initialization seed<input type="number" value={versionForm.initialization_seed} onChange={(e) => setVersionForm({ ...versionForm, initialization_seed: e.target.value })} /></label>
          <button type="submit" disabled={busy === 'version' || validatedConfigs.length === 0}>{busy === 'version' ? 'Creating…' : 'Create version'}</button>
          {validatedConfigs.length === 0 && <p className="empty">No validated configurations yet — validate a configuration first.</p>}
        </form>
        {formError.version && <div className="notice error-notice">{formError.version}</div>}

        <div className="training-grid">
          <section className="data-list">
            <h3>Versions</h3>
            {(versions.items ?? []).length === 0 && <article>No model versions yet.</article>}
            {(versions.items ?? []).map((item) => (
              <button className="training-job-row" key={item.public_id} onClick={() => loadVersionDetail(item.public_id)}>
                <strong>{item.version}</strong>
                <span>{item.lifecycle_status}</span>
                <small>{(item.actual_parameter_count ?? item.estimated_parameter_count)?.toLocaleString()} params</small>
              </button>
            ))}
          </section>
          <section className="training-detail">
            <h3>Version Detail</h3>
            {!selectedVersionId && <p>Select a version to view its lifecycle.</p>}
            {versionDetailError && <div className="notice error-notice">{versionDetailError}</div>}
            {versionDetail && versionDetail.version.public_id === selectedVersionId && <>
              <LifecycleTimeline status={versionDetail.version.lifecycle_status} />
              <div className="import-counts">
                <span>Status {versionDetail.version.lifecycle_status}</span>
                <span>Est. params {versionDetail.version.estimated_parameter_count?.toLocaleString()}</span>
                <span>Actual params {versionDetail.version.actual_parameter_count?.toLocaleString() ?? '—'}</span>
                <span>Weights checksum {versionDetail.version.weights_checksum_sha256?.slice(0, 12) ?? '—'}</span>
              </div>
              <div className="document-actions">
                <button onClick={() => runVersionAction(selectedVersionId, 'initialize')} disabled={busy !== '' || !['draft', 'failed'].includes(versionDetail.version.lifecycle_status)}>
                  {busy === `initialize-${selectedVersionId}` ? 'Initializing…' : 'Initialize'}
                </button>
                <button onClick={() => runVersionAction(selectedVersionId, 'verify-architecture')} disabled={busy !== '' || versionDetail.version.lifecycle_status !== 'initialized'}>
                  {busy === `verify-architecture-${selectedVersionId}` ? 'Verifying…' : 'Verify architecture'}
                </button>
                <button onClick={() => runVersionAction(selectedVersionId, 'smoke-test')} disabled={busy !== '' || versionDetail.version.lifecycle_status !== 'architecture_verified'}>
                  {busy === `smoke-test-${selectedVersionId}` ? 'Running…' : 'Run smoke test'}
                </button>
                <button onClick={() => runVersionAction(selectedVersionId, 'stage')} disabled={busy !== '' || versionDetail.version.lifecycle_status !== 'smoke_tested'}>
                  {busy === `stage-${selectedVersionId}` ? 'Staging…' : 'Stage'}
                </button>
              </div>
              <p className="notice">Activation and Public Chat assignment are not available from this page — they remain governed by release/evaluation and the existing activation gate.</p>

              <h3>Architecture Checks</h3>
              <List items={versionDetail.checks} fields={['check_name', 'status', 'metric_value', 'created_at']} empty="Run architecture verification to populate checks." />

              <h3>Checkpoints</h3>
              <div className="data-list">
                {versionDetail.checkpoints.length === 0 && <article>No checkpoints yet.</article>}
                {versionDetail.checkpoints.map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.checkpoint_type}</strong><small>{item.status} · step {item.step} · {item.file_size_bytes} bytes · {item.checksum_sha256?.slice(0, 12)}</small></div>
                    <button onClick={() => runVerifyCheckpoint(item.public_id)} disabled={busy === `verify-checkpoint-${item.public_id}`}>
                      {busy === `verify-checkpoint-${item.public_id}` ? 'Verifying…' : 'Verify'}
                    </button>
                  </article>
                ))}
              </div>
              <p className="notice">These are the Core Model lifecycle's own internal checkpoints (initialization/smoke-test state, via `CheckpointManager`) — a separate, legitimate mechanism from a real training run's canonical checkpoint (`TrainingCheckpointManager`, used by Mini Brain's Training Engine and by Training page jobs). See the Phase 2.7D report for the full distinction.</p>
            </>}
          </section>
        </div>
      </>}

      {active === 'Architecture Checks' && <section className="panel">
        <h2>Architecture Checks</h2>
        <p>Select a version under the Versions tab to view its checks — this tab mirrors that same data for the currently selected version.</p>
        <List items={versionDetail?.checks} fields={['check_name', 'status', 'metric_value', 'created_at']} empty="No version selected, or no checks yet." />
      </section>}

      {active === 'Smoke Test' && <section className="panel">
        <h2>Smoke Test</h2>
        <p>This verifies trainability only. It does not prove language understanding. Run it from the Versions tab once a version reaches "architecture_verified".</p>
        <List items={versionDetail?.checks?.filter((item) => item.check_name === 'tiny_overfit')} fields={['check_name', 'status', 'metric_value']} empty="No smoke test result yet." />
      </section>}

      {active === 'Checkpoints' && <section className="panel">
        <h2>Checkpoints</h2>
        <p>Select a version under the Versions tab to view and verify its checkpoints.</p>
        <List items={versionDetail?.checkpoints} fields={['checkpoint_type', 'status', 'step', 'file_size_bytes', 'checksum_sha256']} empty="No version selected, or no checkpoints yet." />
      </section>}

      {active === 'Assignments' && <section className="panel">
        <h2>Assignments</h2>
        <p className="notice">Read-only in this phase. These are internal architecture-default pointers (e.g. which version smoke-tests default to) — not Public Chat activation, which is a separate, still fully governed system this page never touches.</p>
        <List title="Assignments" items={assignments.items} fields={['assignment_key', 'enabled', 'updated_at']} empty="No assignments configured." />
      </section>}
    </section>
  )
}

function buildConfigPayload(form) {
  return {
    name: form.name,
    config_version: form.config_version,
    tokenizer_version_public_id: form.tokenizer_version_public_id,
    preset: form.preset,
    context_length: numberOrUndefined(form.context_length),
    hidden_size: numberOrUndefined(form.hidden_size),
    intermediate_size: numberOrUndefined(form.intermediate_size),
    num_hidden_layers: numberOrUndefined(form.num_hidden_layers),
    num_attention_heads: numberOrUndefined(form.num_attention_heads),
    num_key_value_heads: numberOrUndefined(form.num_key_value_heads),
  }
}

function LifecycleTimeline({ status }) {
  const relevant = LIFECYCLE_ORDER.filter((s) => s !== 'failed' && s !== 'retired')
  const currentIndex = relevant.indexOf(status)
  return (
    <div className="lifecycle-timeline">
      {relevant.map((step, index) => (
        <span key={step} className={index <= currentIndex && currentIndex >= 0 ? 'lifecycle-step done' : 'lifecycle-step'}>
          {step.replaceAll('_', ' ')}
        </span>
      ))}
      {(status === 'failed' || status === 'retired') && <span className="lifecycle-step error-notice">{status}</span>}
    </div>
  )
}

function Card({ title, value, note }) {
  return <article className="card"><span>{title}</span><strong>{value}</strong><small>{note}</small></article>
}

function List({ title, items = [], fields, empty, renderActions }) {
  return (
    <section className="panel">
      {title && <h2>{title}</h2>}
      {!items?.length ? <p className="empty">{empty}</p> : <div className="table-wrap"><table><thead><tr>{fields.map((field) => <th key={field}>{field}</th>)}{renderActions && <th>actions</th>}</tr></thead><tbody>{items.map((item) => <tr key={item.public_id ?? item.assignment_key}>{fields.map((field) => <td key={field}>{String(item[field] ?? '—').slice(0, 80)}</td>)}{renderActions && <td>{renderActions(item)}</td>}</tr>)}</tbody></table></div>}
    </section>
  )
}
