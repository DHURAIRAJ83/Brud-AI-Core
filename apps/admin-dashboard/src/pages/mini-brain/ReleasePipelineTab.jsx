import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function ReleasePipelineTab({
  rpDiagnostics,
  rpSessions, rpSelectedId, selectRpSession,
  submitRpCreateSession, rpCreateForm, setRpCreateForm, rpBusy,
  rpSession,
  runRpValidateCheckpoint,
  runRpConvert,
  runRpQuantize,
  runRpVerify,
  runRpPerformance,
  submitRpCreateVersion, rpVersionForm, setRpVersionForm,
  runRpAdminReview,
  submitRpActivate, rpActivateLevel, setRpActivateLevel,
  submitRpEvaluateRollback, rpRollbackEvalForm, setRpRollbackEvalForm, rpRollbackEval,
  submitRpExecuteRollback, rpRollbackExecuteForm, setRpRollbackExecuteForm,
  rpEvents,
}) {
  return (
    <>
      <p className="notice">
        MB-07 -- Release Pipeline &amp; Model Deployment Manager. Starts only after MB-06 has
        produced an approved Release Candidate. Converts an already-promoted checkpoint into a
        production-ready GGUF artifact, then gates every irreversible step (version creation,
        activation) behind an explicit admin decision. Never retrains, never modifies the source
        checkpoint or a dataset, never activates automatically.
      </p>
      {rpDiagnostics && (
        <div className="notice">
          <p><strong>Genuinely supported quantization levels:</strong> {rpDiagnostics.quantization_levels_supported.join(', ')}</p>
          <p>Q2/Q3/Q4_K_M/Q5/Q6 are requested-but-unsupported in this environment -- the installed
          GGUF library has no real encoder for those K-quant formats (dequantize-only).</p>
        </div>
      )}

      <div className="training-grid">
        <div>
          <h4>Sessions</h4>
          <ul className="notice">
            {rpSessions.map((s) => (
              <li key={s.public_id}>
                <Button className={rpSelectedId === s.public_id ? 'active' : ''} onClick={() => selectRpSession(s.public_id)}>
                  {s.public_id.slice(0, 8)} -- {s.stage} ({s.status})
                </Button>
              </li>
            ))}
            {!rpSessions.length && <li>No sessions yet.</li>}
          </ul>

          <h4>New session</h4>
          <form className="inline-form training-form" onSubmit={submitRpCreateSession}>
            <label>Core model version public ID<input value={rpCreateForm.core_model_version_public_id} onChange={(e) => setRpCreateForm({ ...rpCreateForm, core_model_version_public_id: e.target.value })} placeholder="approved release candidate from MB-06" /></label>
            <label>Pretraining checkpoint public ID<input value={rpCreateForm.pretraining_checkpoint_public_id} onChange={(e) => setRpCreateForm({ ...rpCreateForm, pretraining_checkpoint_public_id: e.target.value })} /></label>
            <label>Model release family public ID<input value={rpCreateForm.model_release_family_public_id} onChange={(e) => setRpCreateForm({ ...rpCreateForm, model_release_family_public_id: e.target.value })} placeholder="from Model Release Studio" /></label>
            <label>Target quantizations (comma separated)<input value={rpCreateForm.target_quantizations} onChange={(e) => setRpCreateForm({ ...rpCreateForm, target_quantizations: e.target.value })} /></label>
            <label>Dataset version public ID (optional)<input value={rpCreateForm.dataset_version_public_id} onChange={(e) => setRpCreateForm({ ...rpCreateForm, dataset_version_public_id: e.target.value })} /></label>
            <label>Evaluation run public ID (optional)<input value={rpCreateForm.model_evaluation_run_public_id} onChange={(e) => setRpCreateForm({ ...rpCreateForm, model_evaluation_run_public_id: e.target.value })} /></label>
            <Button type="submit" disabled={rpBusy || !rpCreateForm.core_model_version_public_id}>{rpBusy ? 'Working…' : 'Create session'}</Button>
          </form>
        </div>

        <div>
          {!rpSession && <div className="notice">Select or create a session to see its workflow.</div>}

          {rpSession && (
            <>
              <section className="metric-grid">
                <StatusCard label="Stage" value={rpSession.stage} tone="neutral" />
                <StatusCard label="Status" value={rpSession.status} tone={rpSession.status.includes('failed') || rpSession.status.includes('rejected') ? 'waiting' : rpSession.status === 'activated' ? 'good' : 'neutral'} />
                <StatusCard label="Version" value={rpSession.version_string ?? 'not yet created'} tone="neutral" />
                <StatusCard label="Admin decision" value={rpSession.admin_activation_decision ?? 'pending'} tone={rpSession.admin_activation_decision === 'approve' ? 'good' : 'neutral'} />
              </section>

              {rpSession.stage === 'checkpoint_validation' && (
                <div className="notice">
                  <p>Stage 2: validate the checkpoint (exists, readable, metadata, corruption).</p>
                  <Button onClick={runRpValidateCheckpoint} disabled={rpBusy}>Validate checkpoint</Button>
                  {rpSession.checkpoint_validation_report?.status === 'Invalid' && (
                    <ul>{rpSession.checkpoint_validation_report.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  )}
                </div>
              )}

              {rpSession.stage === 'conversion' && (
                <div className="notice">
                  <p>Stage 3: plan the PyTorch to GGUF tensor mapping. No permute is applied -- Brud's
                  own RoPE convention already matches ggml's native "llama" architecture directly
                  (empirically verified).</p>
                  <Button onClick={runRpConvert} disabled={rpBusy}>Convert model</Button>
                </div>
              )}

              {rpSession.stage === 'quantization' && (
                <div className="notice">
                  <p>Stage 4: write a real GGUF file per requested quantization level.</p>
                  <Button onClick={runRpQuantize} disabled={rpBusy}>Quantize + export</Button>
                </div>
              )}

              {rpSession.quantization_report?.levels && (
                <div className="notice">
                  <h4>Exported levels</h4>
                  <ul>
                    {Object.entries(rpSession.quantization_report.levels).map(([level, entry]) => (
                      <li key={level}>{level}: {entry.exported ? `exported, ${entry.file_size_bytes} bytes` : `not supported -- ${entry.reason}`}</li>
                    ))}
                  </ul>
                </div>
              )}

              {rpSession.stage === 'integrity_validation' && (
                <div className="notice">
                  <p>Stage 5/6: verify GGUF file integrity, then compatibility with MB-04 Runtime
                  (a real load + real generation smoke test, on a throwaway backend instance --
                  never the live Runtime singleton before admin approval).</p>
                  <Button onClick={runRpVerify} disabled={rpBusy}>Verify</Button>
                </div>
              )}

              {rpSession.stage === 'compatibility_validation' && (
                <div className="notice">
                  <p>Stage 6: compatibility check did not complete on the first pass -- retry.</p>
                  <Button onClick={runRpVerify} disabled={rpBusy}>Retry verify</Button>
                </div>
              )}

              {rpSession.stage === 'performance_validation' && (
                <div className="notice">
                  <p>Stage 7: measure real load time, memory, tokens/sec, and latency.</p>
                  <Button onClick={runRpPerformance} disabled={rpBusy}>Measure performance</Button>
                  {rpSession.performance_report?.levels && (
                    <pre className="notice">{JSON.stringify(rpSession.performance_report.levels, null, 2)}</pre>
                  )}
                </div>
              )}

              {rpSession.stage === 'version_registration' && (
                <div className="notice">
                  <p>Stage 8/10: create an immutable version (composes the existing Model Release
                  governance system -- eligibility, model card, manifest, approval, release).
                  Versions are never overwritten.</p>
                  <form className="inline-form training-form" onSubmit={submitRpCreateVersion}>
                    <label>Version (Brud-X.Y)<input value={rpVersionForm.version} onChange={(e) => setRpVersionForm({ ...rpVersionForm, version: e.target.value })} placeholder="Brud-0.1" /></label>
                    <label>Prerelease label (optional)<input value={rpVersionForm.prerelease_label} onChange={(e) => setRpVersionForm({ ...rpVersionForm, prerelease_label: e.target.value })} /></label>
                    <Button type="submit" disabled={rpBusy}>Create release version</Button>
                  </form>
                </div>
              )}

              {rpSession.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Stage 11: admin reviews the full release report and decides.</p>
                  <pre className="notice">{JSON.stringify({
                    ready_for_admin_review: rpSession.release_report?.ready_for_admin_review,
                    blocking_reasons: rpSession.release_report?.blocking_reasons,
                  }, null, 2)}</pre>
                  <Button onClick={() => runRpAdminReview('reject')} disabled={rpBusy}>Reject</Button>{' '}
                  <Button onClick={() => runRpAdminReview('archive')} disabled={rpBusy}>Archive</Button>{' '}
                  <Button onClick={() => runRpAdminReview('approve')} disabled={rpBusy}>Approve</Button>
                </div>
              )}

              {rpSession.stage === 'production_activation' && (
                <div className="notice">
                  <p>Stage 12: activate into MB-04 Runtime. No Public Chat deployment yet -- this
                  only registers and loads the model into the Runtime's own registry.</p>
                  <form className="inline-form training-form" onSubmit={submitRpActivate}>
                    <label>Quantization level to activate
                      <select value={rpActivateLevel} onChange={(e) => setRpActivateLevel(e.target.value)}>
                        <option value="">Select a level</option>
                        {Object.entries(rpSession.quantization_report?.levels ?? {}).filter(([, v]) => v.exported).map(([level]) => (
                          <option key={level} value={level}>{level}</option>
                        ))}
                      </select>
                    </label>
                    <Button type="submit" disabled={rpBusy || !rpActivateLevel}>Activate</Button>
                  </form>
                </div>
              )}

              {rpSession.stage === 'closed' && (
                <div className="notice">
                  <p>Session closed with status <strong>{rpSession.status}</strong>.</p>
                  {rpSession.runtime_model_public_id && (
                    <p>Runtime model: <code>{rpSession.runtime_model_public_id}</code></p>
                  )}
                </div>
              )}

              <h4>Rollback (available any time a version exists)</h4>
              <div className="notice">
                <form className="inline-form training-form" onSubmit={submitRpEvaluateRollback}>
                  <label>Target version to evaluate<input value={rpRollbackEvalForm.target_version} onChange={(e) => setRpRollbackEvalForm({ target_version: e.target.value })} /></label>
                  <Button type="submit" disabled={rpBusy}>Evaluate rollback target</Button>
                </form>
                {rpRollbackEval && (
                  <pre className="notice">{JSON.stringify(rpRollbackEval, null, 2)}</pre>
                )}
                <form className="inline-form training-form" onSubmit={submitRpExecuteRollback}>
                  <label>Target release public ID<input value={rpRollbackExecuteForm.target_release_public_id} onChange={(e) => setRpRollbackExecuteForm({ ...rpRollbackExecuteForm, target_release_public_id: e.target.value })} /></label>
                  <label>Reason<input value={rpRollbackExecuteForm.reason} onChange={(e) => setRpRollbackExecuteForm({ ...rpRollbackExecuteForm, reason: e.target.value })} /></label>
                  <Button type="submit" disabled={rpBusy}>Execute rollback</Button>
                </form>
              </div>

              <h4>Session events</h4>
              <ul className="notice">
                {rpEvents.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!rpEvents.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  )
}
