import { useEffect, useMemo, useState } from 'react'
import StatusCard from '../components/StatusCard.jsx'
import {
  baseTrainingCandidate,
  baseTrainingComparisons,
  baseTrainingExperiment,
  baseTrainingExperiments,
  baseTrainingLanguageMetrics,
  baseTrainingLearningChecks,
  baseTrainingManifest,
  baseTrainingProfile,
  baseTrainingRuns,
  baseTrainingTokenizerEvaluation,
  compareBaseTrainingRuns,
  coreModelVersions,
  createBaseTrainingExperiment,
  createBaseTrainingRun,
  datasetVersions,
  evaluateBaseTrainingRun,
  evaluateBaseTrainingTokenizer,
  generateBaseTrainingProfile,
  patchBaseTrainingExperiment,
  queueBaseTrainingRun,
  selectBaseTrainingCandidate,
  tokenizerVersions,
  verifyBaseTrainingManifest,
} from '../services/api.js'

const defaultRunConfig = {
  batch_size: 1,
  gradient_accumulation_steps: 2,
  sequence_length: 64,
  total_steps: 200,
  learning_rate: 0.0005,
  checkpoint_interval_steps: 50,
  validation_interval_steps: 50,
  metric_interval_steps: 5,
  scheduler: 'constant',
}

export default function BaseTrainingPage() {
  const [state, setState] = useState({ loading: true, error: '', experiments: [], datasets: [], models: [] })
  const [selectedId, setSelectedId] = useState(null)
  const [experiment, setExperiment] = useState(null)
  const [profile, setProfile] = useState(null)
  const [tokenizerEvaluation, setTokenizerEvaluation] = useState(null)
  const [runs, setRuns] = useState({ items: [] })
  const [selectedRunId, setSelectedRunId] = useState('')
  const [languageMetrics, setLanguageMetrics] = useState({ items: [] })
  const [learningChecks, setLearningChecks] = useState({ items: [] })
  const [comparisons, setComparisons] = useState({ items: [] })
  const [candidate, setCandidate] = useState(null)
  const [manifest, setManifest] = useState(null)
  const [manifestVerification, setManifestVerification] = useState(null)
  const [form, setForm] = useState({ name: '', objective: '', dataset_version_public_id: '' })
  const [runForm, setRunForm] = useState({ run_label: 'Run A', configuration: defaultRunConfig })
  const [compareLeft, setCompareLeft] = useState('')
  const [compareRight, setCompareRight] = useState('')
  const [panelError, setPanelError] = useState('')
  const selectedExperiment = useMemo(
    () => state.experiments.find((item) => item.public_id === selectedId) || state.experiments[0],
    [state.experiments, selectedId],
  )

  async function load() {
    setState((old) => ({ ...old, loading: true, error: '' }))
    try {
      const [experiments, datasets, models] = await Promise.all([
        baseTrainingExperiments(),
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
    setExperiment(await baseTrainingExperiment(item.public_id))
    setProfile(await baseTrainingProfile(item.public_id).catch(() => null))
    setTokenizerEvaluation(await baseTrainingTokenizerEvaluation(item.public_id).catch(() => null))
    setRuns(await baseTrainingRuns(item.public_id).catch(() => ({ items: [] })))
    setComparisons(await baseTrainingComparisons(item.public_id).catch(() => ({ items: [] })))
    setCandidate(await baseTrainingCandidate(item.public_id).catch(() => null))
    setManifest(null)
    setManifestVerification(null)
    setLanguageMetrics({ items: [] })
    setLearningChecks({ items: [] })
    setSelectedRunId('')
  }

  useEffect(() => { load() }, [])
  useEffect(() => { if (selectedExperiment) loadDetail(selectedExperiment).catch(() => {}) }, [selectedExperiment?.public_id])

  async function submitExperiment(event) {
    event.preventDefault()
    await createBaseTrainingExperiment(form)
    setForm({ name: '', objective: '', dataset_version_public_id: '' })
    await load()
  }

  async function assignModel(modelPublicId) {
    await patchBaseTrainingExperiment(experiment.public_id, { core_model_version_public_id: modelPublicId })
    await loadDetail(selectedExperiment)
  }

  async function runGenerateProfile() {
    try {
      setProfile(await generateBaseTrainingProfile(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runEvaluateTokenizer() {
    try {
      setTokenizerEvaluation(await evaluateBaseTrainingTokenizer(experiment.public_id))
      setExperiment(await baseTrainingExperiment(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function submitRun(event) {
    event.preventDefault()
    try {
      await createBaseTrainingRun(experiment.public_id, runForm)
      setRuns(await baseTrainingRuns(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function queueRun(runId) {
    try {
      await queueBaseTrainingRun(runId)
      setRuns(await baseTrainingRuns(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function evaluateRun(runId) {
    try {
      const result = await evaluateBaseTrainingRun(runId)
      setLanguageMetrics({ items: result.language_metrics ?? [] })
      setLearningChecks({ items: result.learning_checks ?? [] })
      setSelectedRunId(runId)
      setRuns(await baseTrainingRuns(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function viewRunMetrics(runId) {
    setSelectedRunId(runId)
    setLanguageMetrics(await baseTrainingLanguageMetrics(runId).catch(() => ({ items: [] })))
    setLearningChecks(await baseTrainingLearningChecks(runId).catch(() => ({ items: [] })))
  }

  async function runCompare() {
    try {
      setComparisons({ items: [await compareBaseTrainingRuns(experiment.public_id, compareLeft, compareRight)] })
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runSelectCandidate() {
    try {
      setCandidate(await selectBaseTrainingCandidate(experiment.public_id))
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runGenerateManifest() {
    try {
      setManifest(await baseTrainingManifest(experiment.public_id))
      setManifestVerification(null)
      setPanelError('')
    } catch (error) {
      setPanelError(error.message)
    }
  }

  async function runVerifyManifest() {
    setManifestVerification(await verifyBaseTrainingManifest(experiment.public_id))
  }

  if (state.loading) return <section className="notice">Loading base training experiments…</section>
  if (state.error) return <section className="notice error-notice">{state.error}</section>

  return (
    <section className="training-workspace">
      <header className="section-heading">
        <div>
          <h2>Representative Base Pretraining and Learning Evaluation</h2>
          <p className="notice">
            A base-pretrained model predicts tokens from learned patterns. It is not yet
            instruction-tuned or chat-ready.
          </p>
        </div>
        <button onClick={load}>Refresh</button>
      </header>

      <form className="inline-form training-form" onSubmit={submitExperiment}>
        <h3>Create experiment</h3>
        <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>Objective<input value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} /></label>
        <label>Dataset
          <select value={form.dataset_version_public_id} onChange={(e) => setForm({ ...form, dataset_version_public_id: e.target.value })}>
            <option value="">Select ready dataset</option>
            {state.datasets.map((item) => <option key={item.public_id} value={item.public_id}>{item.name} {item.version}</option>)}
          </select>
        </label>
        <button type="submit">Create experiment</button>
      </form>

      <div className="training-grid">
        <section className="data-list">
          <h3>Experiments</h3>
          {state.experiments.length === 0 && <article>No experiments yet.</article>}
          {state.experiments.map((item) => (
            <button className="training-job-row" key={item.public_id} onClick={() => loadDetail(item)}>
              <strong>{item.name}</strong>
              <span>{item.status}</span>
              <small>tokenizer: {item.tokenizer_decision}</small>
            </button>
          ))}
        </section>

        <section className="training-detail">
          <h3>Experiment Detail</h3>
          {!experiment && <p>No experiment selected.</p>}
          {panelError && <div className="notice error-notice">{panelError}</div>}
          {experiment && <>
            <div className="metric-grid">
              <StatusCard label="Status" value={experiment.status} tone="good" />
              <StatusCard label="Tokenizer decision" value={experiment.tokenizer_decision} tone="good" />
              <StatusCard label="Core model assigned" value={experiment.core_model_version_public_id ? 'yes' : 'no'} tone="neutral" />
            </div>

            {!experiment.core_model_version_public_id && (
              <label>Assign core model
                <select onChange={(e) => e.target.value && assignModel(e.target.value)} defaultValue="">
                  <option value="">Select architecture</option>
                  {state.models.map((item) => <option key={item.public_id} value={item.public_id}>{item.version} · {item.lifecycle_status}</option>)}
                </select>
              </label>
            )}

            <h3>Dataset Profile</h3>
            <button onClick={runGenerateProfile}>Generate profile</button>
            {profile ? (
              <div className="metric-table">
                <span>total {profile.total_records}</span>
                <span>train {profile.train_count}</span><span>validation {profile.validation_count}</span><span>test {profile.test_count}</span>
                <span>total tokens {profile.total_tokens}</span>
                <span>sufficiency {profile.data_sufficiency_status}</span>
                <span>languages {JSON.stringify(profile.language_distribution)}</span>
                <span>duplicate rate {(profile.duplicate_rate * 100).toFixed(1)}%</span>
                <span>checksum {profile.profile_checksum_sha256?.slice(0, 12)}</span>
              </div>
            ) : <p>No profile generated yet.</p>}
            {profile?.data_sufficiency_status !== 'sufficient' && profile && (
              <div className="notice error-notice">
                Dataset is below the recommended 500-record minimum — this is a limited-scale
                experiment, not a representative-scale result.
              </div>
            )}

            <h3>Tokenizer Suitability</h3>
            <button onClick={runEvaluateTokenizer}>Evaluate tokenizer</button>
            {tokenizerEvaluation ? (
              <div className="metric-table">
                <span>decision {tokenizerEvaluation.tokenizer_decision}</span>
                <span>round trip {(tokenizerEvaluation.evaluation?.metrics?.overall?.round_trip_success_rate * 100 || 0).toFixed(1)}%</span>
                <span>unknown token rate {(tokenizerEvaluation.evaluation?.metrics?.overall?.unknown_token_rate * 100 || 0).toFixed(1)}%</span>
              </div>
            ) : <p>Not evaluated yet.</p>}

            <h3>Create Run</h3>
            <form className="inline-form" onSubmit={submitRun}>
              <label>Run label<input value={runForm.run_label} onChange={(e) => setRunForm({ ...runForm, run_label: e.target.value })} /></label>
              {['sequence_length', 'total_steps', 'learning_rate'].map((key) => (
                <label key={key}>{key.replaceAll('_', ' ')}
                  <input
                    value={runForm.configuration[key]}
                    onChange={(e) => setRunForm({ ...runForm, configuration: { ...runForm.configuration, [key]: Number(e.target.value) } })}
                  />
                </label>
              ))}
              <button type="submit" disabled={experiment.tokenizer_decision === 'blocked_tokenizer_unsuitable'}>Create run</button>
            </form>

            <h3>Runs</h3>
            <div className="data-list">
              {(runs.items ?? []).length === 0 && <article>No runs yet.</article>}
              {(runs.items ?? []).map((run) => (
                <article key={run.public_id}>
                  <div><strong>{run.run_label}</strong><small>{run.job_status}</small></div>
                  <div className="document-actions">
                    <button onClick={() => queueRun(run.public_id)}>Queue</button>
                    <button onClick={() => evaluateRun(run.public_id)}>Evaluate (validation)</button>
                    <button onClick={() => viewRunMetrics(run.public_id)}>View metrics</button>
                  </div>
                </article>
              ))}
            </div>

            <h3>Language Metrics {selectedRunId && <small>run {selectedRunId.slice(0, 8)}</small>}</h3>
            <div className="data-list">
              {(languageMetrics.items ?? []).map((item, index) => (
                <article key={`${item.language}-${item.split}-${index}`}>
                  <div><strong>{item.language}</strong><small>{item.split}</small></div>
                  <small>loss {item.loss?.toFixed?.(4) ?? '—'} · perplexity {item.perplexity?.toFixed?.(2) ?? '—'} · records {item.evaluated_records}</small>
                </article>
              ))}
              {(languageMetrics.items ?? []).length === 0 && <article>No language metrics yet — evaluate a run first.</article>}
            </div>

            <h3>Learning Checks</h3>
            <p className="notice">
              These checks measure evidence of generalization, not proof of language
              understanding. A decreasing training loss alone is optimization, not learning.
            </p>
            <div className="data-list">
              {(learningChecks.items ?? []).map((item) => (
                <article key={item.check_code}>
                  <div><strong>{item.check_code.replaceAll('_', ' ')}</strong><small>{item.status}</small></div>
                  <small>{item.message}</small>
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
                <article key={item.public_id ?? index}>
                  <div><strong>compatibility {item.compatibility}</strong></div>
                </article>
              ))}
            </div>

            <h3>Candidate Selection</h3>
            <button onClick={runSelectCandidate}>Select candidate</button>
            {candidate ? (
              <div className="metric-table">
                <span>status {candidate.status}</span>
                <span>generalization {candidate.generalization_result}</span>
                <span>memorization warnings {candidate.memorization_warning_count}</span>
              </div>
            ) : <p>No candidate selected yet.</p>}
            <p className="notice">
              A selected base candidate is never assigned to the public chatbot. It remains
              not_instruction_tuned and not_chat_ready.
            </p>

            <h3>Reproducibility Manifest</h3>
            <div className="document-actions">
              <button onClick={runGenerateManifest}>Generate / view manifest</button>
              <button onClick={runVerifyManifest} disabled={!manifest}>Verify checksum</button>
            </div>
            {manifest && (
              <div className="metric-table">
                <span>checksum {manifest.manifest_checksum_sha256?.slice(0, 16)}</span>
                <span>dataset checksum {manifest.manifest?.dataset_checksum_sha256?.slice(0, 12)}</span>
                <span>runs {manifest.manifest?.run_public_ids?.length ?? 0}</span>
                {manifest.manifest?.known_limitations?.test_evaluation_notice && (
                  <span className="error-notice">{manifest.manifest.known_limitations.test_evaluation_notice}</span>
                )}
              </div>
            )}
            {manifestVerification && (
              <div className="notice">{manifestVerification.matches ? 'Checksum verified — manifest matches.' : 'Checksum mismatch detected.'}</div>
            )}
          </>}
        </section>
      </div>
    </section>
  )
}
