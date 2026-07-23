import { useEffect, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  coreModelVersions,
  createInstructionTuningExperiment,
  createInstructionTuningRun,
  createInstructionTuningTemplate,
  datasetVersions,
  diagnosticGenerate,
  evaluateInstructionTuningRun,
  generateInstructionTuningProfile,
  instructionTuningCandidate,
  instructionTuningComparisons,
  instructionTuningExperiment,
  instructionTuningExperiments,
  instructionTuningLanguageMetrics,
  instructionTuningLearningChecks,
  instructionTuningManifest,
  instructionTuningMetrics,
  instructionTuningProfile,
  instructionTuningRuns,
  instructionTuningTemplates,
  patchInstructionTuningExperiment,
  queueInstructionTuningRun,
  selectInstructionTuningCandidate,
  compareInstructionTuningRuns,
  verifyInstructionTuningManifest,
} from '../services/api.js'

const DISCLAIMER = 'Instruction tuning teaches response behavior and formatting. It does not prove factual accuracy, safety, or production chat readiness.'
const DIAGNOSTIC_NOTICE = 'Admin-only bounded diagnostic generation. This is not the public chatbot.'

const TABS = [
  'Overview', 'Dataset Profile', 'Templates', 'Runs', 'Training Metrics',
  'Language Evaluation', 'Diagnostic Lab', 'Leakage Checks', 'Candidate Selection',
  'Reproducibility',
]

const defaultRunConfig = {
  batch_size: 1,
  gradient_accumulation_steps: 1,
  sequence_length: 64,
  total_steps: 100,
  checkpoint_interval_steps: 25,
  validation_interval_steps: 100,
  metric_interval_steps: 5,
  learning_rate: 0.0003,
  scheduler: 'constant',
}

export default function InstructionTuningPage() {
  const [tab, setTab] = useState('Overview')
  const [state, setState] = useState({ loading: true, error: '', experiments: [], datasets: [], models: [] })
  const [selectedId, setSelectedId] = useState(null)
  const [experiment, setExperiment] = useState(null)
  const [profile, setProfile] = useState(null)
  const [templates, setTemplates] = useState({ items: [] })
  const [runs, setRuns] = useState({ items: [] })
  const [selectedRunId, setSelectedRunId] = useState('')
  const [metrics, setMetrics] = useState({ items: [] })
  const [languageMetrics, setLanguageMetrics] = useState({ items: [] })
  const [learningChecks, setLearningChecks] = useState({ items: [] })
  const [candidate, setCandidate] = useState(null)
  const [manifest, setManifest] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)
  const [comparisons, setComparisons] = useState({ items: [] })
  const [compareLeft, setCompareLeft] = useState('')
  const [compareRight, setCompareRight] = useState('')
  const [diagnosticPrompt, setDiagnosticPrompt] = useState('Say hello in Tamil')
  const [diagnosticResult, setDiagnosticResult] = useState(null)
  const [form, setForm] = useState({ name: '', objective: '', base_core_model_version_public_id: '', dataset_version_public_id: '' })
  const [templateForm, setTemplateForm] = useState({ name: 'brud-instruction', version: '1', tokenizer_version_public_id: '' })
  const [runForm, setRunForm] = useState({ run_label: 'Run A', configuration: defaultRunConfig })
  const [panelError, setPanelError] = useState('')

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [experiments, datasets, models] = await Promise.all([
        instructionTuningExperiments(),
        datasetVersions('?page_size=100'),
        coreModelVersions('?page_size=100'),
      ])
      setState({
        loading: false, error: '',
        experiments: experiments.items ?? [], datasets: datasets.items ?? [], models: models.items ?? [],
      })
    } catch (error) {
      setState((old) => ({ ...old, loading: false, error: error.message }))
    }
  }

  async function loadDetail(item) {
    if (!item) return
    setSelectedId(item.public_id)
    setPanelError('')
    setExperiment(await instructionTuningExperiment(item.public_id))
    setProfile(await instructionTuningProfile(item.public_id).catch(() => null))
    setTemplates(await instructionTuningTemplates().catch(() => ({ items: [] })))
    setRuns(await instructionTuningRuns(item.public_id).catch(() => ({ items: [] })))
    setComparisons(await instructionTuningComparisons(item.public_id).catch(() => ({ items: [] })))
    setCandidate(await instructionTuningCandidate(item.public_id).catch(() => null))
    setManifest(null)
    setManifestVerification(null)
    setMetrics({ items: [] })
    setLanguageMetrics({ items: [] })
    setLearningChecks({ items: [] })
    setDiagnosticResult(null)
    setSelectedRunId('')
  }

  useEffect(() => { load() }, [])

  const selectedExperiment = state.experiments.find((item) => item.public_id === selectedId) || state.experiments[0]
  useEffect(() => { if (selectedExperiment) loadDetail(selectedExperiment).catch(() => {}) }, [selectedExperiment?.public_id])

  async function submitExperiment(event) {
    event.preventDefault()
    try {
      await createInstructionTuningExperiment(form)
      setForm({ name: '', objective: '', base_core_model_version_public_id: '', dataset_version_public_id: '' })
      setPanelError('')
      await load()
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateProfile() {
    try {
      setProfile(await generateInstructionTuningProfile(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitTemplate(event) {
    event.preventDefault()
    try {
      const created = await createInstructionTuningTemplate(templateForm)
      setTemplates(await instructionTuningTemplates())
      await patchInstructionTuningExperiment(experiment.public_id, { instruction_template_public_id: created.public_id })
      setExperiment(await instructionTuningExperiment(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitRun(event) {
    event.preventDefault()
    try {
      await createInstructionTuningRun(experiment.public_id, runForm)
      setRuns(await instructionTuningRuns(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function queueRun(runId) {
    try {
      await queueInstructionTuningRun(runId)
      setRuns(await instructionTuningRuns(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function evaluateRun(runId) {
    try {
      await evaluateInstructionTuningRun(runId)
      setSelectedRunId(runId)
      setMetrics(await instructionTuningMetrics(runId))
      setLanguageMetrics(await instructionTuningLanguageMetrics(runId))
      setLearningChecks(await instructionTuningLearningChecks(runId))
      setRuns(await instructionTuningRuns(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function viewRunDetail(runId) {
    setSelectedRunId(runId)
    setMetrics(await instructionTuningMetrics(runId).catch(() => ({ items: [] })))
    setLanguageMetrics(await instructionTuningLanguageMetrics(runId).catch(() => ({ items: [] })))
    setLearningChecks(await instructionTuningLearningChecks(runId).catch(() => ({ items: [] })))
  }

  async function runDiagnostic() {
    try {
      setDiagnosticResult(await diagnosticGenerate(selectedRunId, diagnosticPrompt, 32))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runCompare() {
    try {
      setComparisons({ items: [await compareInstructionTuningRuns(experiment.public_id, compareLeft, compareRight)] })
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runSelectCandidate() {
    try {
      setCandidate(await selectInstructionTuningCandidate(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateManifest() {
    try {
      setManifest(await instructionTuningManifest(experiment.public_id))
      setManifestVerification(null)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runVerifyManifest() {
    setManifestVerification(await verifyInstructionTuningManifest(experiment.public_id))
  }

  if (state.loading) return <section className="notice">Loading instruction-tuning experiments…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Supervised Instruction Tuning</h2>
          <p className="notice">{DISCLAIMER}</p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <nav className="inline-form" aria-label="Instruction tuning sections">
        {TABS.map((name) => (
          <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>
        ))}
      </nav>

      {panelError && <div className="notice error-notice">{panelError}</div>}

      <div className="training-grid">
        <section className="data-list">
          <h3>Experiments</h3>
          {state.experiments.length === 0 && <article>No experiments yet.</article>}
          {state.experiments.map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadDetail(item)}>
              <strong>{item.name}</strong>
              <span>{item.status}</span>
            </button>
          ))}
        </section>

        <section className="training-detail">
          {tab === 'Overview' && (
            <>
              <form className="inline-form training-form" onSubmit={submitExperiment}>
                <h3>Create experiment</h3>
                <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
                <label>Objective<input value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} /></label>
                <label>Base model (staging/active, base_pretrained)
                  <select value={form.base_core_model_version_public_id} onChange={(e) => setForm({ ...form, base_core_model_version_public_id: e.target.value })}>
                    <option value="">Select base-pretrained candidate</option>
                    {state.models.map((item) => <option key={item.public_id} value={item.public_id}>{item.version} · {item.lifecycle_status}</option>)}
                  </select>
                </label>
                <label>Dataset
                  <select value={form.dataset_version_public_id} onChange={(e) => setForm({ ...form, dataset_version_public_id: e.target.value })}>
                    <option value="">Select ready dataset</option>
                    {state.datasets.map((item) => <option key={item.public_id} value={item.public_id}>{item.name} {item.version}</option>)}
                  </select>
                </label>
                <button type="submit">Create experiment</button>
              </form>
              {experiment && (
                <div className="metric-grid">
                  <StatusCard label="Status" value={experiment.status} tone="good" />
                  <StatusCard label="Template assigned" value={experiment.instruction_template_public_id ? 'yes' : 'no'} tone="neutral" />
                  <StatusCard label="Base model" value={experiment.base_core_model_version_public_id?.slice(0, 8)} tone="neutral" />
                </div>
              )}
            </>
          )}

          {tab === 'Dataset Profile' && (
            <>
              <h3>Dataset Profile</h3>
              <button onClick={runGenerateProfile} disabled={!experiment}>Generate profile</button>
              {profile ? (
                <div className="metric-table">
                  <span>total {profile.total_records}</span>
                  <span>eligible {profile.eligible_records}</span>
                  <span>invalid {profile.invalid_records}</span>
                  <span>excluded {profile.excluded_records}</span>
                  <span>train {profile.train_count}</span><span>validation {profile.validation_count}</span><span>test {profile.test_count}</span>
                  <span>sufficiency {profile.data_sufficiency_status}</span>
                  <span>assistant target tokens {profile.maskable_assistant_token_count}</span>
                  <span>languages {JSON.stringify(profile.language_distribution)}</span>
                  <span>input checksum {profile.input_stream_checksum_sha256?.slice(0, 12)}</span>
                  <span>label checksum {profile.label_stream_checksum_sha256?.slice(0, 12)}</span>
                </div>
              ) : <p>No profile generated yet.</p>}
              {profile?.data_sufficiency_status !== 'sufficient' && profile && (
                <div className="notice error-notice">
                  Dataset is below the recommended 1,000-record minimum — this is a limited-scale
                  instruction-tuning experiment, not a representative-scale result.
                </div>
              )}
            </>
          )}

          {tab === 'Templates' && (
            <>
              <h3>Instruction Templates</h3>
              <form className="inline-form" onSubmit={submitTemplate}>
                <label>Name<input value={templateForm.name} onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })} /></label>
                <label>Version<input value={templateForm.version} onChange={(e) => setTemplateForm({ ...templateForm, version: e.target.value })} /></label>
                <label>Tokenizer public ID<input value={templateForm.tokenizer_version_public_id} onChange={(e) => setTemplateForm({ ...templateForm, tokenizer_version_public_id: e.target.value })} /></label>
                <button type="submit" disabled={!experiment}>Create + assign to experiment</button>
              </form>
              <div className="data-list">
                {(templates.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.name} v{item.version}</strong><small>{item.is_valid ? 'valid' : 'invalid'}</small></div>
                    <small>checksum {item.template_checksum_sha256?.slice(0, 12)}</small>
                  </article>
                ))}
              </div>
            </>
          )}

          {tab === 'Runs' && (
            <>
              <form className="inline-form" onSubmit={submitRun}>
                <h3>Create Run</h3>
                <label>Run label<input value={runForm.run_label} onChange={(e) => setRunForm({ ...runForm, run_label: e.target.value })} /></label>
                {['sequence_length', 'total_steps', 'learning_rate'].map((key) => (
                  <label key={key}>{key.replaceAll('_', ' ')}
                    <input value={runForm.configuration[key]} onChange={(e) => setRunForm({ ...runForm, configuration: { ...runForm.configuration, [key]: Number(e.target.value) } })} />
                  </label>
                ))}
                <button type="submit" disabled={!experiment?.instruction_template_public_id}>Create run</button>
              </form>
              <div className="data-list">
                {(runs.items ?? []).length === 0 && <article>No runs yet.</article>}
                {(runs.items ?? []).map((run) => (
                  <article key={run.public_id}>
                    <div><strong>{run.run_label}</strong><small>{run.job_status}</small></div>
                    <small>target tokens {run.assistant_target_tokens} · prompt tokens {run.prompt_tokens} · ignored {run.ignored_tokens}</small>
                    <div className="document-actions">
                      <button onClick={() => queueRun(run.public_id)}>Queue</button>
                      <button onClick={() => evaluateRun(run.public_id)}>Evaluate</button>
                      <button onClick={() => viewRunDetail(run.public_id)}>View</button>
                    </div>
                  </article>
                ))}
              </div>
              <h3>Run Comparison</h3>
              <div className="inline-form">
                <label>Left run<input value={compareLeft} onChange={(e) => setCompareLeft(e.target.value)} /></label>
                <label>Right run<input value={compareRight} onChange={(e) => setCompareRight(e.target.value)} /></label>
                <button onClick={runCompare}>Compare runs</button>
              </div>
              <div className="data-list">
                {(comparisons.items ?? []).map((item, index) => (
                  <article key={item.public_id ?? index}><strong>compatibility {item.compatibility}</strong></article>
                ))}
              </div>
            </>
          )}

          {tab === 'Training Metrics' && (
            <>
              <h3>Training Metrics {selectedRunId && <small>run {selectedRunId.slice(0, 8)}</small>}</h3>
              <p className="notice">
                Base-pretraining loss and instruction-tuning response-only loss are not directly
                comparable — instruction-tuning loss is computed only over assistant-target tokens.
              </p>
              <div className="metric-table">
                {(metrics.items ?? []).map((item) => (
                  <span key={item.public_id}>
                    step {item.step}: loss {item.training_loss?.toFixed?.(4) ?? '—'} · target tokens {item.target_tokens} · ignored {item.ignored_tokens}
                  </span>
                ))}
              </div>
            </>
          )}

          {tab === 'Language Evaluation' && (
            <>
              <h3>Language Evaluation</h3>
              <div className="data-list">
                {(languageMetrics.items ?? []).map((item, index) => (
                  <article key={item.public_id ?? index}>
                    <div><strong>{item.language}</strong></div>
                    <small>{item.metric_name}: {item.metric_value?.toFixed?.(4) ?? item.metric_value}</small>
                  </article>
                ))}
                {(languageMetrics.items ?? []).length === 0 && <article>No language metrics yet — evaluate a run first.</article>}
              </div>
            </>
          )}

          {tab === 'Diagnostic Lab' && (
            <>
              <h3>Diagnostic Lab</h3>
              <p className="notice">{DIAGNOSTIC_NOTICE}</p>
              <div className="inline-form">
                <label>Run public ID<input value={selectedRunId} onChange={(e) => setSelectedRunId(e.target.value)} /></label>
                <label>Prompt<input value={diagnosticPrompt} onChange={(e) => setDiagnosticPrompt(e.target.value)} /></label>
                <button onClick={runDiagnostic} disabled={!selectedRunId}>Generate (bounded, greedy)</button>
              </div>
              {diagnosticResult && (
                <div className="metric-table">
                  <span>output: {diagnosticResult.generated_text}</span>
                  <span>stopped reason: {diagnosticResult.stopped_reason}</span>
                  <span>tokens generated: {diagnosticResult.output_token_count}</span>
                </div>
              )}
            </>
          )}

          {tab === 'Leakage Checks' && (
            <>
              <h3>Leakage, Repetition, Memorization Checks</h3>
              <div className="data-list">
                {(learningChecks.items ?? []).map((item) => (
                  <article key={item.public_id}>
                    <div><strong>{item.check_code.replaceAll('_', ' ')}</strong><small>{item.status}</small></div>
                    <small>{item.message}</small>
                  </article>
                ))}
                {(learningChecks.items ?? []).length === 0 && <article>No learning checks yet — evaluate a run first.</article>}
              </div>
            </>
          )}

          {tab === 'Candidate Selection' && (
            <>
              <h3>Candidate Selection</h3>
              <button onClick={runSelectCandidate} disabled={!experiment}>Select candidate</button>
              {candidate ? (
                <div className="metric-table">
                  <span>status {candidate.status}</span>
                  <span>role leakage result {candidate.role_leakage_result}</span>
                  <span>memorization warnings {candidate.memorization_warning_count}</span>
                  <span>base checkpoint before {candidate.base_checkpoint_checksum_before?.slice(0, 12)}</span>
                  <span>base checkpoint after {candidate.base_checkpoint_checksum_after?.slice(0, 12)}</span>
                </div>
              ) : <p>No candidate selected yet.</p>}
              <p className="notice">
                A selected instruction-tuned candidate is never assigned to the public chatbot. It
                remains evaluation_required and not_public_chat_ready.
              </p>
            </>
          )}

          {tab === 'Reproducibility' && (
            <>
              <h3>Reproducibility Manifest</h3>
              <div className="document-actions">
                <button onClick={runGenerateManifest} disabled={!experiment}>Generate / view manifest</button>
                <button onClick={runVerifyManifest} disabled={!manifest}>Verify checksum</button>
              </div>
              {manifest && (
                <div className="metric-table">
                  <span>checksum {manifest.manifest_checksum_sha256?.slice(0, 16)}</span>
                  <span>base checkpoint checksum {manifest.manifest?.base_checkpoint_checksum_sha256?.slice(0, 12)}</span>
                  <span>runs {manifest.manifest?.run_public_ids?.length ?? 0}</span>
                  {manifest.manifest?.known_limitations?.test_evaluation_notice && (
                    <span className="error-notice">{manifest.manifest.known_limitations.test_evaluation_notice}</span>
                  )}
                </div>
              )}
              {manifestVerification && (
                <div className="notice">{manifestVerification.matches ? 'Checksum verified — manifest matches.' : 'Checksum mismatch detected.'}</div>
              )}
            </>
          )}
        </section>
      </div>
    </section>
  )
}
