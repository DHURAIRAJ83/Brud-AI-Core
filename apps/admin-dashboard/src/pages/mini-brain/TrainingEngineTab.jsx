import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const teSubTabs = [
  'Overview', 'Jobs', 'Authorization', 'Resources', 'Manifest', 'Runtime', 'Metrics', 'Checkpoints',
  'Logs', 'Report', 'Archive', 'History', 'Diagnostics',
]

export default function TrainingEngineTab({
  teSubTab, setTeSubTab,
  teDiag, teJobData,
  runTeValidateRelease, runTeValidatePackage,
  teJobsList, teSelectedId, selectTeJob, submitTeCreateJob,
  teNewTopic, setTeNewTopic, teNewPackageId, setTeNewPackageId, teNewReleaseId, setTeNewReleaseId,
  teNewExecutionMode, setTeNewExecutionMode, teBusy,
  teNewCoreModelVersionId, setTeNewCoreModelVersionId, teCoreModelVersion,
  teNewDatasetVersionId, setTeNewDatasetVersionId, teDatasetReadinessData, teDatasetReadinessContractData,
  teTrainingReadinessData,
  submitTeAuthorize, teAuthorizationReason, setTeAuthorizationReason,
  runTePlanResources,
  runTeBuildManifest,
  runTeReserveRuntime,
  runTeStart,
  runTePause, runTeCancel, runTeResume,
  submitTeStreamMetric, teMetricStep, setTeMetricStep, teMetricEpoch, setTeMetricEpoch, teMetricsList,
  submitTeSaveCheckpoint, teCheckpointStep, setTeCheckpointStep, teCheckpointEpoch, setTeCheckpointEpoch, teCheckpointsList,
  teEventsList,
  runTeFinalize,
  runTeGenerateReport,
  runTeArchive,
  teMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-22 -- Real Training Execution Engine. The first Mini Brain phase allowed to run a
        training workflow -- but only ever behind a fresh, per-job admin authorization token,
        never auto-started, never auto-deployed, never auto-promoted to production. Simulation
        and CPU execution modes never run real weights; GPU mode drives the real trainer against
        a real, admin-identified Core Model Version and requires one (Phase 2.7E) -- select or
        create one on the Core Model page first. An existing checkpoint is never overwritten,
        and training here never releases, activates, or assigns a model to Public Chat.
      </p>

      <div className="dataset-tabs">
        {teSubTabs.map((t) => (
          <Button key={t} className={teSubTab === t ? 'active' : ''} onClick={() => setTeSubTab(t)}>{t}</Button>
        ))}
      </div>

      {teSubTab === 'Overview' && (
        <>
          {teDiag && (
            <div className="notice">
              <p><strong>Simulation mode available:</strong> {String(teDiag.simulation_mode_available)} -- <strong>Real CPU training available:</strong> {String(teDiag.real_cpu_training_available)} -- <strong>Real GPU training available:</strong> {String(teDiag.real_gpu_training_available)}</p>
              <p><strong>Auto-start after package approval:</strong> {String(teDiag.auto_start_after_package_approval)} -- <strong>Checkpoints ever overwritten:</strong> {String(teDiag.existing_checkpoints_ever_overwritten)}</p>
            </div>
          )}
          {teJobData && (
            <section className="metric-grid">
              <StatusCard label="Topic" value={teJobData.topic.slice(0, 24)} tone="neutral" />
              <StatusCard label="Stage" value={teJobData.stage} tone="neutral" />
              <StatusCard label="Status" value={teJobData.status} tone="neutral" />
            </section>
          )}
          {teJobData && teJobData.execution_mode === 'gpu' && (
            <div className="notice">
              <h4>Real Brud AI Text Model identity</h4>
              {!teJobData.core_model_version_public_id && (
                <p>This job has no Core Model Version identity -- real training cannot proceed without one.</p>
              )}
              {teJobData.core_model_version_public_id && !teCoreModelVersion && <Skeleton lines={2} />}
              {teCoreModelVersion && (
                <p>
                  Family <strong>{teCoreModelVersion.family_name}</strong> -- config <strong>{teCoreModelVersion.config_public_id?.slice(0, 8)}</strong> -- version <strong>{teCoreModelVersion.version}</strong> -- lifecycle <strong>{teCoreModelVersion.lifecycle_status}</strong>.
                  {' '}This is the exact Family/Config/Version this training job trains -- see the Core Model page for its full lifecycle, checkpoints, and architecture checks. Training here never releases, activates, or assigns this model to Public Chat -- that remains governed elsewhere.
                </p>
              )}
              <p>
                Dataset: <strong>{teJobData.dataset_version_public_id ? teJobData.dataset_version_public_id.slice(0, 8) : 'none'}</strong>
                {' -- '}Pretraining checkpoint registration: <strong>{teJobData.pretraining_job_public_id ? `job ${teJobData.pretraining_job_public_id.slice(0, 8)} registered` : 'not registered yet'}</strong>.
                {' '}Registration (Phase 2.7F) links a real checkpoint into the existing evaluation/release system -- it never evaluates, releases, or activates a model by itself.
              </p>
              {teDatasetReadinessData && (
                <p>
                  Training readiness (Phase 2.7G, real dataset -&gt; token-block pipeline):{' '}
                  <strong>{teDatasetReadinessData.ready ? 'TRAINING_READY' : 'NOT_READY'}</strong>
                  {!teDatasetReadinessData.ready && <>{' -- '}{teDatasetReadinessData.reason}</>}
                  {teDatasetReadinessData.ready && teDatasetReadinessData.report && (
                    <>
                      {' -- context length '}{teDatasetReadinessData.report.context_length}
                      {', train blocks '}{teDatasetReadinessData.report.train_report?.packed?.block_count}
                      {', validation blocks '}{teDatasetReadinessData.report.validation_report?.packed?.block_count}
                    </>
                  )}
                </p>
              )}
              {teDatasetReadinessContractData && (
                <p>
                  Readiness contract (Phase 2.7H, distinguishes BLOCKED from NOT_READY): {' '}
                  <strong>{teDatasetReadinessContractData.status}</strong>
                  {teDatasetReadinessContractData.status !== 'READY' && teDatasetReadinessContractData.reason && (
                    <>{' -- '}{teDatasetReadinessContractData.reason}</>
                  )}
                  {teDatasetReadinessContractData.status === 'READY' && (
                    <>
                      {' -- '}{teDatasetReadinessContractData.dataset?.record_count}{' dataset records, '}
                      avg tokens/record{' '}
                      {teDatasetReadinessContractData.blocks?.train_token_length_stats?.average_tokens?.toFixed(1)},
                      {' vocabulary utilization '}
                      {(
                        (teDatasetReadinessContractData.quality?.train_vocabulary_coverage?.vocabulary_utilization_ratio || 0) * 100
                      ).toFixed(1)}%,
                      {' pipeline time '}
                      {teDatasetReadinessContractData.resource_estimate?.pipeline_wall_clock_seconds?.toFixed(3)}s
                    </>
                  )}
                </p>
              )}
              {teTrainingReadinessData && (
                <p>
                  Training readiness gate (Phase 2.8A -- qualified to start a controlled training run, not a
                  release or model-quality verdict): {' '}
                  <strong>{teTrainingReadinessData.status}</strong>
                  {teTrainingReadinessData.status !== 'READY' && teTrainingReadinessData.reason && (
                    <>{' -- '}{teTrainingReadinessData.reason}</>
                  )}
                  {teTrainingReadinessData.status === 'READY' && (
                    <>
                      {' -- '}{teTrainingReadinessData.core_model?.context_length}{' context length, '}
                      {teTrainingReadinessData.resource_estimate?.parameter_count?.toLocaleString()}{' parameters, '}
                      envelope {teTrainingReadinessData.resource_estimate?.envelope_classification}
                    </>
                  )}
                </p>
              )}
            </div>
          )}
          {!teJobData && <div className="notice">Select or create a job in the Jobs sub-tab first.</div>}
          {teJobData && (
            <div className="notice">
              <h4>Advance workflow</h4>
              {teJobData.stage === 'validate_release' && <Button onClick={runTeValidateRelease} disabled={teBusy}>Validate release approval</Button>}
              {teJobData.stage === 'validate_package' && <Button onClick={runTeValidatePackage} disabled={teBusy}>Validate training package</Button>}
              {teJobData.stage === 'validate_authorization' && <p>Authorize this job in the Authorization sub-tab.</p>}
              {teJobData.stage === 'plan_resources' && <p>Plan resources in the Resources sub-tab.</p>}
              {teJobData.stage === 'build_manifest' && <p>Build the training manifest in the Manifest sub-tab.</p>}
              {teJobData.stage === 'reserve_runtime' && <p>Reserve the runtime and start training in the Runtime sub-tab.</p>}
              {teJobData.stage === 'start_training' && <p>Start training in the Runtime sub-tab.</p>}
              {teJobData.stage === 'streaming_metrics' && <p>Stream metrics and save checkpoints, then finalize in the Report sub-tab.</p>}
              {teJobData.stage === 'generate_report' && <p>Generate the final report in the Report sub-tab.</p>}
              {teJobData.stage === 'awaiting_archive' && <p>Archive this job in the Archive sub-tab.</p>}
              {teJobData.stage === 'cancelled' && <p>This job was cancelled. Archive it in the Archive sub-tab.</p>}
              {teJobData.stage === 'archived' && <p>This job is archived.</p>}
            </div>
          )}
        </>
      )}

      {teSubTab === 'Jobs' && (
        <div className="training-grid">
          <div>
            <h4>Training jobs</h4>
            <ul className="notice">
              {teJobsList.map((j) => (
                <li key={j.public_id}>
                  <Button className={teSelectedId === j.public_id ? 'active' : ''} onClick={() => selectTeJob(j.public_id)}>
                    {j.topic.slice(0, 26)} -- {j.stage} ({j.status})
                  </Button>
                </li>
              ))}
              {!teJobsList.length && <li>No training jobs yet.</li>}
            </ul>
            <form className="inline-form training-form" onSubmit={submitTeCreateJob}>
              <label>Topic<input value={teNewTopic} onChange={(e) => setTeNewTopic(e.target.value)} placeholder="mountain river fine-tune" /></label>
              <label>MB-18 training package session public ID<input value={teNewPackageId} onChange={(e) => setTeNewPackageId(e.target.value)} /></label>
              <label>MB-20 release governance session public ID<input value={teNewReleaseId} onChange={(e) => setTeNewReleaseId(e.target.value)} /></label>
              <label>Execution mode
                <select value={teNewExecutionMode} onChange={(e) => setTeNewExecutionMode(e.target.value)}>
                  <option value="simulation">simulation</option>
                  <option value="cpu">cpu</option>
                  <option value="gpu">gpu</option>
                </select>
              </label>
              {teNewExecutionMode === 'gpu' && (
                <>
                  <label>Core Model Version public ID (required for real training -- create/verify one on the Core Model page first)
                    <input value={teNewCoreModelVersionId} onChange={(e) => setTeNewCoreModelVersionId(e.target.value)} placeholder="architecture-verified version public id" />
                  </label>
                  <label>Dataset version public ID (required for real training -- must be ready or archived)
                    <input value={teNewDatasetVersionId} onChange={(e) => setTeNewDatasetVersionId(e.target.value)} placeholder="ready dataset version public id" />
                  </label>
                </>
              )}
              <Button type="submit" disabled={teBusy || !teNewTopic.trim() || !teNewPackageId.trim() || !teNewReleaseId.trim() || (teNewExecutionMode === 'gpu' && (!teNewCoreModelVersionId.trim() || !teNewDatasetVersionId.trim()))}>{teBusy ? 'Working…' : 'Create job'}</Button>
            </form>
          </div>
          <div>
            {!teJobData && <div className="notice">Select or create a job to work through it in the other sub-tabs.</div>}
            {teJobData && <pre className="notice">{JSON.stringify(teJobData, null, 2)}</pre>}
          </div>
        </div>
      )}

      {teSubTab === 'Authorization' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (
            <>
              {teJobData.stage === 'validate_authorization' && (
                <form className="inline-form training-form" onSubmit={submitTeAuthorize}>
                  <label>Explicit authorization reason (required before this job may ever start)
                    <input value={teAuthorizationReason} onChange={(e) => setTeAuthorizationReason(e.target.value)} placeholder="approved for CPU-first simulation training run" />
                  </label>
                  <Button type="submit" disabled={teBusy || !teAuthorizationReason.trim()}>Authorize</Button>
                </form>
              )}
              {teJobData.authorization_report?.authorized !== undefined && (
                <pre className="notice">{JSON.stringify(teJobData.authorization_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {teSubTab === 'Resources' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (
            <>
              {teJobData.stage === 'plan_resources' && (
                <div className="notice">
                  <p>Every figure here is heuristic -- never a real hardware benchmark.</p>
                  <Button onClick={runTePlanResources} disabled={teBusy}>Plan resources</Button>
                </div>
              )}
              {teJobData.resource_plan_report?.execution_mode && (
                <pre className="notice">{JSON.stringify(teJobData.resource_plan_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {teSubTab === 'Manifest' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (
            <>
              {teJobData.stage === 'build_manifest' && (
                <div className="notice">
                  <Button onClick={runTeBuildManifest} disabled={teBusy}>Build training manifest</Button>
                </div>
              )}
              {teJobData.training_manifest?.fingerprint && (
                <pre className="notice">{JSON.stringify(teJobData.training_manifest, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {teSubTab === 'Runtime' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (
            <>
              {teJobData.stage === 'reserve_runtime' && (
                <div className="notice">
                  <Button onClick={runTeReserveRuntime} disabled={teBusy}>Reserve runtime</Button>
                </div>
              )}
              {teJobData.runtime_reservation_report?.reserved !== undefined && (
                <pre className="notice">{JSON.stringify(teJobData.runtime_reservation_report, null, 2)}</pre>
              )}
              {teJobData.stage === 'start_training' && (
                <div className="notice">
                  <Button onClick={runTeStart} disabled={teBusy}>Start training</Button>
                </div>
              )}
              {teJobData.status === 'running' && (
                <div className="notice">
                  <Button onClick={runTePause} disabled={teBusy}>Pause</Button>{' '}
                  <Button onClick={runTeCancel} disabled={teBusy}>Cancel</Button>
                </div>
              )}
              {teJobData.status === 'paused' && (
                <div className="notice">
                  <Button onClick={runTeResume} disabled={teBusy}>Resume</Button>{' '}
                  <Button onClick={runTeCancel} disabled={teBusy}>Cancel</Button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {teSubTab === 'Metrics' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (
            <>
              {teJobData.status === 'running' && (
                <form className="inline-form training-form" onSubmit={submitTeStreamMetric}>
                  <label>Step<input type="number" min="0" value={teMetricStep} onChange={(e) => setTeMetricStep(e.target.value)} /></label>
                  <label>Epoch<input type="number" min="0" value={teMetricEpoch} onChange={(e) => setTeMetricEpoch(e.target.value)} /></label>
                  <Button type="submit" disabled={teBusy}>Stream metric</Button>
                </form>
              )}
              <table>
                <thead><tr><th>Step</th><th>Epoch</th><th>Loss</th><th>Learning rate</th><th>Tokens/sec</th></tr></thead>
                <tbody>
                  {teMetricsList.map((m) => (
                    <tr key={m.public_id}><td>{m.step}</td><td>{m.epoch}</td><td>{m.loss}</td><td>{m.learning_rate}</td><td>{m.tokens_per_second}</td></tr>
                  ))}
                  {!teMetricsList.length && <tr><td colSpan="5">No metrics recorded yet.</td></tr>}
                </tbody>
              </table>
            </>
          )}
        </>
      )}

      {teSubTab === 'Checkpoints' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (
            <>
              {(teJobData.status === 'running' || teJobData.status === 'paused') && (
                <form className="inline-form training-form" onSubmit={submitTeSaveCheckpoint}>
                  <label>Step<input type="number" min="0" value={teCheckpointStep} onChange={(e) => setTeCheckpointStep(e.target.value)} /></label>
                  <label>Epoch<input type="number" min="0" value={teCheckpointEpoch} onChange={(e) => setTeCheckpointEpoch(e.target.value)} /></label>
                  <Button type="submit" disabled={teBusy}>Save checkpoint</Button>
                </form>
              )}
              <ul className="notice">
                {teCheckpointsList.map((c) => (
                  <li key={c.public_id}>
                    {c.checkpoint_name} -- sha256 {c.sha256.slice(0, 16)}… -- {c.is_metadata_only ? 'metadata-only' : 'real file'}
                    {' -- registered for release: '}
                    <strong>{c.pretraining_checkpoint_public_id ? 'yes' : 'no'}</strong>
                  </li>
                ))}
                {!teCheckpointsList.length && <li>No checkpoints saved yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {teSubTab === 'Logs' && teJobData && (
        <>
          <h4>Job events</h4>
          <ul className="notice">
            {teEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!teEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {teSubTab === 'Logs' && !teJobData && (
        <div className="notice">Select a job in Jobs first.</div>
      )}

      {teSubTab === 'Report' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (
            <>
              {(teJobData.status === 'running' || teJobData.status === 'paused') && (
                <div className="notice">
                  <p>Only finalize may set this job's status to completed.</p>
                  <Button onClick={runTeFinalize} disabled={teBusy}>Finalize training</Button>
                </div>
              )}
              {teJobData.stage === 'generate_report' && (
                <div className="notice">
                  <Button onClick={runTeGenerateReport} disabled={teBusy}>Generate final report</Button>
                </div>
              )}
              {teJobData.final_report?.disclaimer && (
                <>
                  <p className="notice">{teJobData.final_report.disclaimer}</p>
                  <pre className="notice">{JSON.stringify(teJobData.final_report, null, 2)}</pre>
                </>
              )}
            </>
          )}
        </>
      )}

      {teSubTab === 'Archive' && (
        <>
          {!teJobData && <div className="notice">Select a job in Jobs first.</div>}
          {teJobData && (teJobData.status === 'completed' || teJobData.status === 'cancelled') && (
            <div className="notice">
              <Button onClick={runTeArchive} disabled={teBusy}>Archive job</Button>
            </div>
          )}
          {teJobData && teJobData.status === 'archived' && <div className="notice">Job archived.</div>}
          {teJobData && !['completed', 'cancelled', 'archived'].includes(teJobData.status) && (
            <div className="notice">Archiving requires status completed or cancelled (currently {teJobData.status}).</div>
          )}
        </>
      )}

      {teSubTab === 'History' && (
        <>
          <h4>Training engine memory (permanent)</h4>
          <ul className="notice">
            {teMemoryList.map((m) => (
              <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.final_status} -- final loss {m.final_loss} -- {m.checkpoint_count} checkpoint(s)</li>
            ))}
            {!teMemoryList.length && <li>No training engine memory recorded yet.</li>}
          </ul>
        </>
      )}

      {teSubTab === 'Diagnostics' && (
        <>
          {teDiag && <pre className="notice">{JSON.stringify(teDiag, null, 2)}</pre>}
          {!teDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
