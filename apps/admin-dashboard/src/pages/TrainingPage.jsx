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
  pretrainingWorkers,
  generatePretrainingCoverage,
  pretrainingCoverage,
  pretrainingStreams,
  verifyPretrainingStreams,
  staleJobs,
  recoverPretrainingJob,
  jobRecoveries,
  pretrainingSummary,
  assessJobQuality,
  jobQuality,
  jobQualityIssues,
  compareCheckpoints,
  compareJobs,
  retentionPreview,
  retentionApply,
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

function heartbeatAgeSeconds(worker) {
  const last = Date.parse(`${worker.last_heartbeat_at}Z`)
  if (Number.isNaN(last)) return null
  return Math.max(0, Math.round((Date.now() - last) / 1000))
}

function isStaleWorker(worker) {
  const age = heartbeatAgeSeconds(worker)
  return worker.status === 'running' && age !== null && age > 180
}

export default function TrainingPage() {
  const [state, setState] = useState({ loading: true, error: '', capabilities: null, jobs: [], datasets: [], tokenizers: [], models: [] })
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState({ metrics: [], checkpoints: [], events: [] })
  const [form, setForm] = useState({ name: 'Micro bounded pretraining', dataset_version_public_id: '', tokenizer_version_public_id: '', core_model_version_public_id: '', configuration: defaultConfig })
  const [workers, setWorkers] = useState([])
  const [stale, setStale] = useState([])
  const [coverage, setCoverage] = useState({ items: [] })
  const [streams, setStreams] = useState({ items: [] })
  const [streamVerification, setStreamVerification] = useState(null)
  const [recoveries, setRecoveries] = useState({ items: [] })
  const [summary, setSummary] = useState(null)
  const [quality, setQuality] = useState(null)
  const [qualityIssues, setQualityIssues] = useState({ items: [] })
  const [compareLeft, setCompareLeft] = useState('')
  const [compareRight, setCompareRight] = useState('')
  const [comparison, setComparison] = useState(null)
  const [retention, setRetention] = useState(null)
  const [overrideComment, setOverrideComment] = useState('')
  const [panelError, setPanelError] = useState('')
  const selectedJob = useMemo(() => state.jobs.find((job) => job.public_id === selected) || state.jobs[0], [state.jobs, selected])

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [capabilities, jobs, datasets, tokenizers, models, workerList, staleList] = await Promise.all([
        pretrainingCapabilities(),
        pretrainingJobs(),
        datasetVersions('?page_size=100'),
        tokenizerVersions('?page_size=100'),
        coreModelVersions('?page_size=100'),
        pretrainingWorkers(),
        staleJobs(),
      ])
      setState({ loading: false, error: '', capabilities, jobs: jobs.items ?? [], datasets: datasets.items ?? [], tokenizers: tokenizers.items ?? [], models: models.items ?? [] })
      setWorkers(workerList.items ?? [])
      setStale(staleList.items ?? [])
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  async function loadDetail(job) {
    if (!job) return
    setSelected(job.public_id)
    setPanelError('')
    const [metrics, checkpoints, events] = await Promise.all([
      pretrainingMetrics(job.public_id),
      pretrainingCheckpoints(job.public_id),
      pretrainingEvents(job.public_id),
    ])
    setDetail({ metrics: metrics.items ?? [], checkpoints: checkpoints.items ?? [], events: events.items ?? [] })
    const [coverageResult, streamsResult, recoveryResult] = await Promise.all([
      pretrainingCoverage(job.public_id).catch(() => ({ items: [] })),
      pretrainingStreams(job.public_id).catch(() => ({ items: [] })),
      jobRecoveries(job.public_id).catch(() => ({ items: [] })),
    ])
    setCoverage(coverageResult)
    setStreams(streamsResult)
    setRecoveries(recoveryResult)
    setStreamVerification(null)
    setRetention(null)
    setComparison(null)
    setSummary(await pretrainingSummary(job.public_id).catch(() => null))
    setQuality(await jobQuality(job.public_id).catch(() => null))
    setQualityIssues(await jobQualityIssues(job.public_id).catch(() => ({ items: [] })))
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
    try {
      await promotePretrainingCheckpoint(id, overrideComment)
      setPanelError('')
      await loadDetail(selectedJob)
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateCoverage() {
    await generatePretrainingCoverage(selectedJob.public_id)
    setCoverage(await pretrainingCoverage(selectedJob.public_id))
  }

  async function runVerifyStreams() {
    setStreamVerification(await verifyPretrainingStreams(selectedJob.public_id))
  }

  async function runRecover(jobPublicId) {
    await recoverPretrainingJob(jobPublicId)
    await load()
    if (selectedJob) await loadDetail(selectedJob)
  }

  async function runAssessQuality() {
    setQuality(await assessJobQuality(selectedJob.public_id))
    setQualityIssues(await jobQualityIssues(selectedJob.public_id))
  }

  async function runCompareCheckpoints() {
    setComparison(await compareCheckpoints(compareLeft, compareRight))
  }

  async function runCompareJobs() {
    setComparison(await compareJobs(compareLeft, compareRight))
  }

  async function runRetentionPreview() {
    setRetention(await retentionPreview(selectedJob.public_id))
  }

  async function runRetentionApply() {
    const eligible = (retention?.items ?? []).filter((item) => item.classification === 'eligible').map((item) => item.public_id)
    if (eligible.length === 0) return
    const result = await retentionApply(selectedJob.public_id, eligible)
    setRetention(null)
    setPanelError(result.dry_run ? 'Retention applied in dry-run mode (BRUD_PRETRAINING_RETENTION_DRY_RUN=true) — no checkpoints were archived.' : `Archived ${result.applied.length} checkpoint(s).`)
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

      <h3>Worker Status</h3>
      <div className="data-list">
        {workers.length === 0 && <article>No workers have registered yet.</article>}
        {workers.map((worker) => {
          const age = heartbeatAgeSeconds(worker)
          const staleFlag = isStaleWorker(worker)
          return (
            <article key={worker.public_id}>
              <div>
                <strong>{worker.status}</strong>
                <small>worker {worker.public_id.slice(0, 8)} · current job {worker.current_job_public_id ? worker.current_job_public_id.slice(0, 8) : '—'}</small>
              </div>
              <div>
                <span>heartbeat {age === null ? '—' : `${age}s ago`}</span>
                <span>lease gen {worker.lease_generation ?? '—'}</span>
                <span>lease expires {worker.lease_expires_at ?? '—'}</span>
                {staleFlag && <span className="error-notice">stale</span>}
              </div>
            </article>
          )
        })}
      </div>

      <h3>Recovery — Stale Jobs</h3>
      <div className="data-list">
        {stale.length === 0 && <article>No jobs require recovery.</article>}
        {stale.map((job) => (
          <article key={job.public_id}>
            <div><strong>{job.name}</strong><small>{job.public_id.slice(0, 8)} · {job.status}</small></div>
            <button onClick={() => runRecover(job.public_id)}>Recover</button>
          </article>
        ))}
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
          {state.jobs.map((job) => <button className="training-job-row" key={job.public_id} onClick={() => loadDetail(job)}><strong>{job.name}</strong><span>{job.status}</span><small>{job.completed_steps}/{job.total_steps} steps · {job.processed_tokens} tokens · quality {job.quality_readiness_status}</small></button>)}
        </section>
        <section className="training-detail">
          <h3>Job Detail</h3>
          {!selectedJob && <p>No job selected.</p>}
          {panelError && <div className="notice error-notice">{panelError}</div>}
          {selectedJob && <>
            <div className="import-counts"><span>Loss {selectedJob.latest_training_loss ?? '—'}</span><span>Validation {selectedJob.latest_validation_loss ?? '—'}</span><span>LR {selectedJob.learning_rate ?? '—'}</span><span>Progress {Math.round((selectedJob.progress ?? 0) * 100)}%</span></div>
            <div className="document-actions"><button onClick={() => action(selectedJob, 'validate')}>Validate</button><button onClick={() => action(selectedJob, 'queue')}>Queue</button><button onClick={() => action(selectedJob, 'pause')}>Pause</button><button onClick={() => action(selectedJob, 'resume')}>Resume</button><button onClick={() => action(selectedJob, 'cancel')}>Cancel</button></div>

            <h3>Metrics</h3>
            <div className="metric-table">{detail.metrics.map((metric) => <span key={metric.public_id}>step {metric.step}: loss {Number(metric.training_loss).toFixed(4)} · {metric.processed_tokens} tokens</span>)}</div>

            <h3>Checkpoints</h3>
            <div className="data-list">{detail.checkpoints.map((item) => <article key={item.public_id}><div><strong>{item.checkpoint_kind}</strong><small>step {item.step} · {item.combined_checksum_sha256?.slice(0, 12)} · {item.is_best ? 'best' : ''} {item.is_latest ? 'latest' : ''}</small></div><div><button onClick={() => verifyCheckpoint(item.public_id)}>Verify</button><button onClick={() => promoteCheckpoint(item.public_id)}>Promote</button></div></article>)}</div>
            <label>Promotion override comment (required only if quality is "warning")<input value={overrideComment} onChange={(e) => setOverrideComment(e.target.value)} /></label>

            <h3>Dataset Coverage</h3>
            <button onClick={runGenerateCoverage}>Generate coverage</button>
            <div className="data-list">
              {(coverage.items ?? []).map((item) => (
                <article key={item.public_id}>
                  <div><strong>{item.split}</strong><small>{item.stream_checksum_sha256?.slice(0, 12)}</small></div>
                  <div className="metric-table">
                    <span>total {item.total_records}</span><span>encoded {item.encoded_records}</span><span>excluded {item.excluded_records}</span>
                    <span>zero-token {item.zero_token_records}</span><span>oversized {item.oversized_records}</span>
                    <span>total tokens {item.total_tokens}</span><span>usable tokens {item.usable_tokens}</span><span>padding {item.padding_tokens}</span>
                    <span>coverage ratio {(item.coverage_ratio * 100).toFixed(1)}%</span>
                  </div>
                  <div className="metric-table">
                    <span>languages {JSON.stringify(item.language_distribution)}</span>
                    <span>record types {JSON.stringify(item.record_type_distribution)}</span>
                    <span>sources {JSON.stringify(item.source_type_distribution)}</span>
                    <span>exclusion reasons {JSON.stringify(item.exclusion_reasons)}</span>
                  </div>
                </article>
              ))}
            </div>

            <h3>Streams</h3>
            <button onClick={runVerifyStreams}>Verify streams</button>
            {streamVerification && <div className="notice">{streamVerification.verified ? 'All stream checksums verified.' : 'Stream checksum mismatch detected.'}</div>}
            <div className="data-list">{(streams.items ?? []).map((item) => <article key={item.public_id}><div><strong>{item.split}</strong><small>{item.stream_checksum_sha256?.slice(0, 12)}</small></div><small>{item.block_count} blocks · seq {item.sequence_length} · {item.eos_policy} / {item.overlength_policy}</small></article>)}</div>

            <h3>Recovery History</h3>
            <div className="data-list">{(recoveries.items ?? []).map((item) => <article key={item.public_id}><div><strong>{item.recovery_type}</strong><small>{item.status}</small></div><small>step {item.recovered_step ?? '—'} · tokens {item.recovered_tokens ?? '—'}</small></article>)}</div>

            <h3>Run Summary</h3>
            {summary ? (
              <div className="metric-table">
                <span>status {summary.status}</span><span>steps {summary.initial_step}→{summary.final_step}</span>
                <span>loss {summary.initial_training_loss?.toFixed?.(4) ?? '—'}→{summary.final_training_loss?.toFixed?.(4) ?? '—'}</span>
                <span>validation loss {summary.final_validation_loss ?? '—'}</span>
                <span>perplexity {summary.final_perplexity ?? 'unavailable (unsafe or missing loss)'}</span>
                <span>tokens {summary.processed_tokens}</span><span>tokens/sec {summary.average_tokens_per_second?.toFixed?.(1) ?? '—'}</span>
                <span>checkpoints {summary.checkpoint_count}</span><span>pauses {summary.pause_count}</span><span>resumes {summary.resume_count}</span><span>recoveries {summary.recovery_count}</span>
              </div>
            ) : <p>No run summary yet — completes once the job finishes.</p>}

            <h3>Quality</h3>
            <button onClick={runAssessQuality}>Assess quality</button>
            <p className="notice">This score measures training-process integrity. It does not measure Tamil fluency, chatbot quality, or instruction-following ability.</p>
            {quality && <div className="metric-table">
              <span>overall {(quality.overall_score * 100).toFixed(1)}%</span>
              <span>readiness {quality.readiness_status}</span>
              {Object.entries(quality.dimension_scores ?? {}).map(([dimension, score]) => <span key={dimension}>{dimension.replaceAll('_', ' ')} {(score * 100).toFixed(0)}%</span>)}
            </div>}
            <div className="data-list">
              {(qualityIssues.items ?? []).map((issue) => <article key={issue.public_id}><div><strong>{issue.severity}</strong><small>{issue.issue_code}</small></div><small>{issue.message}</small></article>)}
              {(qualityIssues.items ?? []).length === 0 && quality && <article>No quality issues.</article>}
            </div>

            <h3>Checkpoint Retention</h3>
            <div className="document-actions"><button onClick={runRetentionPreview}>Preview retention</button><button onClick={runRetentionApply} disabled={!retention}>Apply to eligible checkpoints</button></div>
            <div className="data-list">{(retention?.items ?? []).map((item) => <article key={item.public_id}><div><strong>{item.classification}</strong><small>{item.public_id.slice(0, 8)}</small></div><small>{item.protection_reason ?? 'no protection — eligible for archival'}</small></article>)}</div>

            <h3>Events</h3>
            <div className="audit-list">{detail.events.slice(-8).map((event) => <article key={`${event.event_type}-${event.created_at}`}><div><span>{event.event_type}</span><small>{event.new_status}</small></div><small>{event.created_at}</small></article>)}</div>
          </>}
        </section>
      </div>

      <h3>Comparisons</h3>
      <div className="inline-form">
        <label>Left public ID<input value={compareLeft} onChange={(e) => setCompareLeft(e.target.value)} /></label>
        <label>Right public ID<input value={compareRight} onChange={(e) => setCompareRight(e.target.value)} /></label>
        <button onClick={runCompareCheckpoints}>Compare checkpoints</button>
        <button onClick={runCompareJobs}>Compare jobs</button>
      </div>
      {comparison && (
        <div className="metric-table">
          <span>compatibility {comparison.compatibility}</span>
          {comparison.compatibility !== 'compatible' && <span>ranking across incompatible items is not shown</span>}
          {comparison.fields && Object.entries(comparison.fields).map(([field, value]) => <span key={field}>{field}: {String(value.left)} vs {String(value.right)}</span>)}
        </div>
      )}
    </section>
  )
}
