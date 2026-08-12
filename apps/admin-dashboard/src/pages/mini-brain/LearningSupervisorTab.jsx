import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function LearningSupervisorTab({
  lsSessions, lsSelectedId, selectLsSession,
  submitLsCreateSession, lsCreateForm, setLsCreateForm, lsProfiles, lsBusy,
  lsSession,
  runLsValidateDataset,
  runLsDecideDataset,
  submitLsRagEvaluation, lsRagForm, setLsRagForm, runLsFinalizeRag,
  runLsDecideRag,
  submitLsTrainingRequest, lsTrainingForm, setLsTrainingForm,
  runLsMonitorTraining, lsMonitor, runLsAnalyzeTraining,
  submitLsBenchmark, lsBenchmarkForm, setLsBenchmarkForm,
  submitLsCompareModels, lsCompareForm, setLsCompareForm,
  runLsRecommendations,
  runLsAdminReview,
  submitLsReleaseCandidate, lsReleaseForm, setLsReleaseForm,
  lsEvents,
}) {
  return (
    <>
      <p className="notice">
        MB-06 -- Learning Supervisor. Orchestration only: it never trains a model, never writes a
        dataset/tokenizer/RAG/checkpoint/Runtime row, and never deploys or exports anything. Every
        stage below composes the Training Engine, Model Evaluation, and RAG Sandbox through their
        own existing, unmodified public methods; every irreversible step requires an explicit
        admin decision recorded on the session first.
      </p>

      <div className="training-grid">
        <div>
          <h4>Sessions</h4>
          <ul className="notice">
            {lsSessions.map((s) => (
              <li key={s.public_id}>
                <Button className={lsSelectedId === s.public_id ? 'active' : ''} onClick={() => selectLsSession(s.public_id)}>
                  {s.public_id.slice(0, 8)} -- {s.stage} ({s.status})
                </Button>
              </li>
            ))}
            {!lsSessions.length && <li>No sessions yet.</li>}
          </ul>

          <h4>New session</h4>
          <form className="inline-form training-form" onSubmit={submitLsCreateSession}>
            <label>Dataset source public ID
              <input value={lsCreateForm.dataset_source_public_id} onChange={(e) => setLsCreateForm({ ...lsCreateForm, dataset_source_public_id: e.target.value })} placeholder="source public_id from Dataset Studio" />
            </label>
            <label>Hyperparameter profile
              <select value={lsCreateForm.hyperparameter_profile} onChange={(e) => setLsCreateForm({ ...lsCreateForm, hyperparameter_profile: e.target.value })}>
                {(lsProfiles.length ? lsProfiles : ['default']).map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
            <Button type="submit" disabled={lsBusy || !lsCreateForm.dataset_source_public_id}>{lsBusy ? 'Working…' : 'Create session'}</Button>
          </form>
        </div>

        <div>
          {!lsSession && <div className="notice">Select or create a session to see its workflow.</div>}

          {lsSession && (
            <>
              <section className="metric-grid">
                <StatusCard label="Stage" value={lsSession.stage} tone="neutral" />
                <StatusCard label="Status" value={lsSession.status} tone={lsSession.status.includes('reject') ? 'waiting' : lsSession.status === 'accepted' ? 'good' : 'neutral'} />
                <StatusCard label="Dataset decision" value={lsSession.dataset_decision ?? 'pending'} tone={lsSession.dataset_decision === 'approve' ? 'good' : 'neutral'} />
                <StatusCard label="RAG decision" value={lsSession.rag_decision ?? 'pending'} tone={lsSession.rag_decision === 'approve' ? 'good' : 'neutral'} />
                <StatusCard label="Admin final decision" value={lsSession.admin_final_decision ?? 'pending'} tone={lsSession.admin_final_decision === 'accept' ? 'good' : 'neutral'} />
              </section>

              {lsSession.stage === 'dataset_validation' && (
                <div className="notice">
                  <p>Stage 2/3: run dataset validation (MB-05 + MB-05.1 readiness and advanced analysis).</p>
                  <Button onClick={runLsValidateDataset} disabled={lsBusy}>Validate dataset</Button>
                </div>
              )}

              {lsSession.stage === 'awaiting_dataset_decision' && (
                <div className="notice">
                  <p>Stage 4: admin decision gate on dataset readiness.</p>
                  <pre className="notice">{JSON.stringify(lsSession.dataset_readiness_report?.training_readiness, null, 2)}</pre>
                  <Button onClick={() => runLsDecideDataset('approve')} disabled={lsBusy}>Approve</Button>{' '}
                  <Button onClick={() => runLsDecideDataset('reject')} disabled={lsBusy}>Reject</Button>
                </div>
              )}

              {lsSession.stage === 'rag_evaluation' && (
                <div className="notice">
                  <p>Stage 5: RAG evaluation. Retrieval and corpus/index/query-set setup remain
                  admin-driven through the existing RAG Sandbox admin flow -- this only runs
                  grounded generation, automated evaluation, and report finalization on top of an
                  already-built retrieval run.</p>
                  <form className="inline-form training-form" onSubmit={submitLsRagEvaluation}>
                    <label>RAG Sandbox experiment public ID<input value={lsRagForm.rag_sandbox_experiment_public_id} onChange={(e) => setLsRagForm({ ...lsRagForm, rag_sandbox_experiment_public_id: e.target.value })} /></label>
                    <label>Retrieval run public ID<input value={lsRagForm.retrieval_run_public_id} onChange={(e) => setLsRagForm({ ...lsRagForm, retrieval_run_public_id: e.target.value })} /></label>
                    <label>Generation assignment public ID<input value={lsRagForm.generation_assignment_public_id} onChange={(e) => setLsRagForm({ ...lsRagForm, generation_assignment_public_id: e.target.value })} /></label>
                    <Button type="submit" disabled={lsBusy}>Run generation + evaluation</Button>
                  </form>
                  {lsSession.rag_evaluation_report?.status === 'pending_human_review' && (
                    <>
                      <p>{lsSession.rag_evaluation_report.reason}</p>
                      <Button onClick={runLsFinalizeRag} disabled={lsBusy}>Retry finalize (after human review)</Button>
                    </>
                  )}
                </div>
              )}

              {lsSession.stage === 'awaiting_rag_decision' && (
                <div className="notice">
                  <p>Stage 6: admin decision gate on the RAG evaluation report.</p>
                  <pre className="notice">{JSON.stringify({
                    production_rag_readiness: lsSession.rag_evaluation_report?.production_rag_readiness,
                    blocking_reasons: lsSession.rag_evaluation_report?.blocking_reasons,
                  }, null, 2)}</pre>
                  <Button onClick={() => runLsDecideRag('approve')} disabled={lsBusy}>Approve</Button>{' '}
                  <Button onClick={() => runLsDecideRag('reject')} disabled={lsBusy}>Reject</Button>
                </div>
              )}

              {lsSession.stage === 'training_request' && (
                <div className="notice">
                  <p>Stage 7: build and submit the training request to the existing Training Engine.
                  MB-06 never trains -- only `create_job` is ever called.</p>
                  <form className="inline-form training-form" onSubmit={submitLsTrainingRequest}>
                    <label>Job name<input value={lsTrainingForm.name} onChange={(e) => setLsTrainingForm({ ...lsTrainingForm, name: e.target.value })} /></label>
                    <label>Dataset version public ID<input value={lsTrainingForm.dataset_version_public_id} onChange={(e) => setLsTrainingForm({ ...lsTrainingForm, dataset_version_public_id: e.target.value })} /></label>
                    <label>Tokenizer version public ID<input value={lsTrainingForm.tokenizer_version_public_id} onChange={(e) => setLsTrainingForm({ ...lsTrainingForm, tokenizer_version_public_id: e.target.value })} /></label>
                    <label>Core model version public ID<input value={lsTrainingForm.core_model_version_public_id} onChange={(e) => setLsTrainingForm({ ...lsTrainingForm, core_model_version_public_id: e.target.value })} /></label>
                    <label>Hyperparameter profile override
                      <select value={lsTrainingForm.hyperparameter_profile} onChange={(e) => setLsTrainingForm({ ...lsTrainingForm, hyperparameter_profile: e.target.value })}>
                        <option value="">(use session default: {lsSession.hyperparameter_profile})</option>
                        {lsProfiles.map((p) => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </label>
                    <Button type="submit" disabled={lsBusy}>Submit training request</Button>
                  </form>
                </div>
              )}

              {lsSession.stage === 'training_monitoring' && (
                <div className="notice">
                  <p>Stage 8: read-only training monitoring. No pause/resume/cancel control exists
                  here -- MB-06 never intervenes in a running job.</p>
                  <Button onClick={runLsMonitorTraining} disabled={lsBusy}>Refresh monitor</Button>
                  {lsMonitor && <pre className="notice">{JSON.stringify(lsMonitor.job, null, 2)}</pre>}
                  <p>Once the job reaches a terminal status (completed/failed/paused/cancelled):</p>
                  <Button onClick={runLsAnalyzeTraining} disabled={lsBusy}>Analyze training result</Button>
                </div>
              )}

              {lsSession.stage === 'benchmark_evaluation' && (
                <div className="notice">
                  <p>Stage 10: run the existing benchmark system against the trained candidate.</p>
                  <pre className="notice">{JSON.stringify(lsSession.training_report, null, 2)}</pre>
                  <form className="inline-form training-form" onSubmit={submitLsBenchmark}>
                    <label>Fixture set public ID<input value={lsBenchmarkForm.model_evaluation_fixture_set_public_id} onChange={(e) => setLsBenchmarkForm({ ...lsBenchmarkForm, model_evaluation_fixture_set_public_id: e.target.value })} /></label>
                    <label>Candidate core model version public ID<input value={lsBenchmarkForm.candidate_core_model_version_public_id} onChange={(e) => setLsBenchmarkForm({ ...lsBenchmarkForm, candidate_core_model_version_public_id: e.target.value })} /></label>
                    <Button type="submit" disabled={lsBusy}>Run benchmark</Button>
                  </form>
                </div>
              )}

              {lsSession.stage === 'model_comparison' && (
                <div className="notice">
                  <p>Stage 11: compare the new benchmark run against a previous production run.</p>
                  <form className="inline-form training-form" onSubmit={submitLsCompareModels}>
                    <label>Previous benchmark run public ID<input value={lsCompareForm.previous_benchmark_run_public_id} onChange={(e) => setLsCompareForm({ previous_benchmark_run_public_id: e.target.value })} /></label>
                    <Button type="submit" disabled={lsBusy}>Compare models</Button>
                  </form>
                </div>
              )}

              {lsSession.stage === 'recommendation' && (
                <div className="notice">
                  <p>Stage 12/13: generate deterministic recommendations and assemble the final
                  learning report for admin review.</p>
                  <pre className="notice">{JSON.stringify(lsSession.comparison_report, null, 2)}</pre>
                  <Button onClick={runLsRecommendations} disabled={lsBusy}>Generate recommendations + report</Button>
                </div>
              )}

              {lsSession.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Admin reviews the full learning report and decides.</p>
                  <pre className="notice">{JSON.stringify(lsSession.recommendation_report?.recommendations, null, 2)}</pre>
                  <Button onClick={() => runLsAdminReview('reject')} disabled={lsBusy}>Reject</Button>{' '}
                  <Button onClick={() => runLsAdminReview('retrain')} disabled={lsBusy}>Retrain</Button>{' '}
                  <Button onClick={() => runLsAdminReview('fine_tune')} disabled={lsBusy}>Fine tune</Button>{' '}
                  <Button onClick={() => runLsAdminReview('accept')} disabled={lsBusy}>Accept</Button>
                </div>
              )}

              {lsSession.stage === 'release_candidate' && (
                <div className="notice">
                  <p>Stage 14: create a release candidate core model version. This does NOT deploy
                  and does NOT export GGUF -- it only marks a promoted checkpoint for a future,
                  separate Release Pipeline to continue.</p>
                  <form className="inline-form training-form" onSubmit={submitLsReleaseCandidate}>
                    <label>Checkpoint public ID<input value={lsReleaseForm.checkpoint_public_id} onChange={(e) => setLsReleaseForm({ ...lsReleaseForm, checkpoint_public_id: e.target.value })} /></label>
                    <label>Override comment (if quality warning)<input value={lsReleaseForm.override_comment} onChange={(e) => setLsReleaseForm({ ...lsReleaseForm, override_comment: e.target.value })} /></label>
                    <Button type="submit" disabled={lsBusy}>Create release candidate</Button>
                  </form>
                </div>
              )}

              {lsSession.stage === 'closed' && (
                <div className="notice">
                  <p>Session closed with status <strong>{lsSession.status}</strong>.</p>
                  {lsSession.release_candidate_core_model_version_public_id && (
                    <p>Release candidate: <code>{lsSession.release_candidate_core_model_version_public_id}</code></p>
                  )}
                </div>
              )}

              <h4>Session events</h4>
              <ul className="notice">
                {lsEvents.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!lsEvents.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  )
}
