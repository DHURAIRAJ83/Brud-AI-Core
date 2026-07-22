import { useEffect, useMemo, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  coreModelVersions,
  createPretrainingJob,
  datasetVersions,
  pretrainingCapabilities,
  pretrainingCheckpoints,
  pretrainingEvents,
  pretrainingJobAction,
  pretrainingJobs,
  pretrainingMetrics,
  pretrainingPreflight,
  tokenizerVersions,
  verifyPretrainingCheckpoint,
  promotePretrainingCheckpoint,
} from '../services/api.js'

const defaultConfig = {
  batch_size: 1,
  gradient_accumulation_steps: 2,
  sequence_length: 64,
  total_steps: 20,
  learning_rate: 0.0003,
  checkpoint_interval_steps: 10,
  validation_interval_steps: 10,
  metric_interval_steps: 1,
  scheduler: 'constant',
}

export default function TrainingPage() {
  const [state, setState] = useState({ loading: true, error: '', capabilities: null, jobs: [], datasets: [], tokenizers: [], models: [] })
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState({ metrics: [], checkpoints: [], events: [] })
  const [form, setForm] = useState({ name: 'Micro bounded pretraining', dataset_version_public_id: '', tokenizer_version_public_id: '', core_model_version_public_id: '', configuration: defaultConfig })
  const selectedJob = useMemo(() => state.jobs.find((job) => job.public_id === selected) || state.jobs[0], [state.jobs, selected])

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [capabilities, jobs, datasets, tokenizers, models] = await Promise.all([
        pretrainingCapabilities(),
        pretrainingJobs(),
        datasetVersions('?page_size=100'),
        tokenizerVersions('?page_size=100'),
        coreModelVersions('?page_size=100'),
      ])
      setState({ loading: false, error: '', capabilities, jobs: jobs.items ?? [], datasets: datasets.items ?? [], tokenizers: tokenizers.items ?? [], models: models.items ?? [] })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  async function loadDetail(job) {
    if (!job) return
    setSelected(job.public_id)
    const [metrics, checkpoints, events] = await Promise.all([
      pretrainingMetrics(job.public_id),
      pretrainingCheckpoints(job.public_id),
      pretrainingEvents(job.public_id),
    ])
    setDetail({ metrics: metrics.items ?? [], checkpoints: checkpoints.items ?? [], events: events.items ?? [] })
  }

  useEffect(() => { load() }, [])
  useEffect(() => { if (selectedJob) loadDetail(selectedJob).catch(() => {}) }, [selectedJob?.public_id])

  async function submitJob(event) {
    event.preventDefault()
    const payload = { ...form, job_mode: 'smoke_pretraining' }
    await pretrainingPreflight(payload)
    await createPretrainingJob(payload)
    await load()
  }

  async function action(job, name) {
    await pretrainingJobAction(job.public_id, name)
    await load()
    await loadDetail(job)
  }

  async function verifyCheckpoint(id) {
    await verifyPretrainingCheckpoint(id)
    await loadDetail(selectedJob)
  }

  async function promoteCheckpoint(id) {
    await promotePretrainingCheckpoint(id)
    await loadDetail(selectedJob)
  }

  if (state.loading) return <section className="notice">Loading pretraining status…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Bounded Core Model Pretraining</h2>
          <p>Base pretraining learns token prediction patterns. A short CPU run does not make the model production-ready or conversationally reliable.</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>
      <div className="metric-grid">
        <StatusCard label="Worker mode" value={state.capabilities.worker_mode} tone="good" />
        <StatusCard label="PyTorch" value={state.capabilities.pytorch_version} tone="good" />
        <StatusCard label="NumPy" value={state.capabilities.numpy_version} tone="good" />
      </div>
      <form className="inline-form training-form" onSubmit={submitJob}>
        <h2>Create bounded job</h2>
        <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>Dataset<select value={form.dataset_version_public_id} onChange={(e) => setForm({ ...form, dataset_version_public_id: e.target.value })}><option value="">Select ready dataset</option>{state.datasets.map((item) => <option key={item.public_id} value={item.public_id}>{item.name} {item.version}</option>)}</select></label>
        <label>Tokenizer<select value={form.tokenizer_version_public_id} onChange={(e) => setForm({ ...form, tokenizer_version_public_id: e.target.value })}><option value="">Select tokenizer</option>{state.tokenizers.map((item) => <option key={item.public_id} value={item.public_id}>{item.version} · {item.lifecycle_status}</option>)}</select></label>
        <label>Core model<select value={form.core_model_version_public_id} onChange={(e) => setForm({ ...form, core_model_version_public_id: e.target.value })}><option value="">Select architecture</option>{state.models.map((item) => <option key={item.public_id} value={item.public_id}>{item.version} · {item.lifecycle_status}</option>)}</select></label>
        {['sequence_length', 'total_steps', 'gradient_accumulation_steps', 'learning_rate'].map((key) => (
          <label key={key}>{key.replaceAll('_', ' ')}<input value={form.configuration[key]} onChange={(e) => setForm({ ...form, configuration: { ...form.configuration, [key]: Number(e.target.value) } })} /></label>
        ))}
        <button type="submit">Preflight and create draft</button>
      </form>
      <div className="training-grid">
        <section className="data-list">
          <h3>Pretraining Jobs</h3>
          {state.jobs.length === 0 && <article>No pretraining jobs yet.</article>}
          {state.jobs.map((job) => <button className="training-job-row" key={job.public_id} onClick={() => loadDetail(job)}><strong>{job.name}</strong><span>{job.status}</span><small>{job.completed_steps}/{job.total_steps} steps · {job.processed_tokens} tokens</small></button>)}
        </section>
        <section className="training-detail">
          <h3>Job Detail</h3>
          {!selectedJob && <p>No job selected.</p>}
          {selectedJob && <>
            <div className="import-counts"><span>Loss {selectedJob.latest_training_loss ?? '—'}</span><span>Validation {selectedJob.latest_validation_loss ?? '—'}</span><span>LR {selectedJob.learning_rate ?? '—'}</span><span>Progress {Math.round((selectedJob.progress ?? 0) * 100)}%</span></div>
            <div className="document-actions"><button onClick={() => action(selectedJob, 'validate')}>Validate</button><button onClick={() => action(selectedJob, 'queue')}>Queue</button><button onClick={() => action(selectedJob, 'pause')}>Pause</button><button onClick={() => action(selectedJob, 'resume')}>Resume</button><button onClick={() => action(selectedJob, 'cancel')}>Cancel</button></div>
            <h3>Metrics</h3>
            <div className="metric-table">{detail.metrics.map((metric) => <span key={metric.public_id}>step {metric.step}: loss {Number(metric.training_loss).toFixed(4)} · {metric.processed_tokens} tokens</span>)}</div>
            <h3>Checkpoints</h3>
            <div className="data-list">{detail.checkpoints.map((item) => <article key={item.public_id}><div><strong>{item.checkpoint_kind}</strong><small>step {item.step} · {item.combined_checksum_sha256?.slice(0, 12)}</small></div><div><button onClick={() => verifyCheckpoint(item.public_id)}>Verify</button><button onClick={() => promoteCheckpoint(item.public_id)}>Promote</button></div></article>)}</div>
            <h3>Events</h3>
            <div className="audit-list">{detail.events.slice(-8).map((event) => <article key={`${event.event_type}-${event.created_at}`}><div><span>{event.event_type}</span><small>{event.new_status}</small></div><small>{event.created_at}</small></article>)}</div>
          </>}
        </section>
      </div>
    </section>
  )
}
