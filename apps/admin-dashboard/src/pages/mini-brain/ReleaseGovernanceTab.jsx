import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const rgSubTabs = [
  'Overview', 'Sources', 'Safety', 'Compliance', 'Benchmarks', 'Risks', 'Rollback', 'Compatibility',
  'Prerequisites', 'Package', 'Report', 'History', 'Diagnostics',
]

export default function ReleaseGovernanceTab({
  rgSubTab, setRgSubTab,
  rgDiag, rgSessionData,
  rgSessionsList, rgSelectedId, selectRgSession, submitRgCreateSession, rgNewTopic, setRgNewTopic, rgBusy,
  rgEventsList,
  submitRgCollectDatasets, rgDatasetSessionIds, setRgDatasetSessionIds,
  submitRgCollectRag, rgRagSessionIds, setRgRagSessionIds,
  submitRgCollectPackage, rgPackageSessionId, setRgPackageSessionId,
  submitRgCollectEvaluation, rgEvaluationSessionId, setRgEvaluationSessionId,
  runRgSafety,
  runRgCompliance,
  runRgBenchmarks,
  runRgBuildRiskRollback,
  runRgBuildPackage, rgArtifactsList,
  runRgGenerateReport,
  runRgAdminReview,
  rgMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-20 -- Release Readiness &amp; Deployment Governance Center. A decision-and-governance
        layer only: it never deploys a model, starts an inference server or public chat, calls a
        runtime-manager start API, calls a Docker/Kubernetes deployment API, uploads weights
        anywhere, exports GGUF, or quantizes. It performs the final governance review of an
        already-certified MB-16 dataset, an already-approved MB-17 RAG session, an
        already-approved MB-18 training package, and an already-approved MB-19 evaluation.
        Approval never implies production safety.
      </p>

      <div className="dataset-tabs">
        {rgSubTabs.map((t) => (
          <Button key={t} className={rgSubTab === t ? 'active' : ''} onClick={() => setRgSubTab(t)}>{t}</Button>
        ))}
      </div>

      {rgSubTab === 'Overview' && (
        <>
          {rgDiag && (
            <div className="notice">
              <p><strong>Model deployed:</strong> {String(rgDiag.model_deployed)} -- <strong>Runtime manager start called:</strong> {String(rgDiag.runtime_manager_start_called)} -- <strong>Production traffic enabled:</strong> {String(rgDiag.production_traffic_enabled)}</p>
              <p><strong>Requires certified sources:</strong> {String(rgDiag.requires_certified_sources)} -- <strong>Automatic approval:</strong> {String(rgDiag.automatic_approval)}</p>
            </div>
          )}
          {rgSessionData && (
            <section className="metric-grid">
              <StatusCard label="Topic" value={rgSessionData.topic.slice(0, 24)} tone="neutral" />
              <StatusCard label="Stage" value={rgSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={rgSessionData.status} tone={rgSessionData.status.includes('reject') ? 'waiting' : rgSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Release governance sessions</h4>
              <ul className="notice">
                {rgSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={rgSelectedId === s.public_id ? 'active' : ''} onClick={() => selectRgSession(s.public_id)}>
                      {s.topic.slice(0, 30)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!rgSessionsList.length && <li>No release governance sessions yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitRgCreateSession}>
                <label>Topic<input value={rgNewTopic} onChange={(e) => setRgNewTopic(e.target.value)} placeholder="Mountain scene release" /></label>
                <Button type="submit" disabled={rgBusy || !rgNewTopic.trim()}>{rgBusy ? 'Working…' : 'Create session'}</Button>
              </form>
            </div>
            <div>
              {!rgSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
              {rgSessionData && (
                <>
                  <h4>Session events</h4>
                  <ul className="notice">
                    {rgEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!rgEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {rgSubTab === 'Sources' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && (
            <>
              {rgSessionData.stage === 'collect_datasets' && (
                <form className="inline-form training-form" onSubmit={submitRgCollectDatasets}>
                  <label>MB-16 certified dataset session public ID(s), comma-separated
                    <input value={rgDatasetSessionIds} onChange={(e) => setRgDatasetSessionIds(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={rgBusy || !rgDatasetSessionIds.trim()}>Collect dataset evidence</Button>
                </form>
              )}
              {rgSessionData.dataset_collection_report?.accepted_count !== undefined && (
                <pre className="notice">{JSON.stringify(rgSessionData.dataset_collection_report, null, 2)}</pre>
              )}

              {rgSessionData.stage === 'collect_rag' && (
                <form className="inline-form training-form" onSubmit={submitRgCollectRag}>
                  <label>MB-17 approved RAG session public ID(s), comma-separated, optional
                    <input value={rgRagSessionIds} onChange={(e) => setRgRagSessionIds(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={rgBusy}>Collect RAG evidence</Button>
                </form>
              )}
              {rgSessionData.rag_collection_report?.accepted_count !== undefined && (
                <pre className="notice">{JSON.stringify(rgSessionData.rag_collection_report, null, 2)}</pre>
              )}

              {rgSessionData.stage === 'collect_training_package' && (
                <form className="inline-form training-form" onSubmit={submitRgCollectPackage}>
                  <label>MB-18 approved training package session public ID
                    <input value={rgPackageSessionId} onChange={(e) => setRgPackageSessionId(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={rgBusy || !rgPackageSessionId.trim()}>Collect training package</Button>
                </form>
              )}
              {rgSessionData.training_package_collection_report?.accepted !== undefined && (
                <pre className="notice">{JSON.stringify(rgSessionData.training_package_collection_report, null, 2)}</pre>
              )}

              {rgSessionData.stage === 'collect_evaluation' && (
                <form className="inline-form training-form" onSubmit={submitRgCollectEvaluation}>
                  <label>MB-19 approved evaluation session public ID
                    <input value={rgEvaluationSessionId} onChange={(e) => setRgEvaluationSessionId(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={rgBusy || !rgEvaluationSessionId.trim()}>Collect evaluation report</Button>
                </form>
              )}
              {rgSessionData.evaluation_collection_report?.accepted !== undefined && (
                <pre className="notice">{JSON.stringify(rgSessionData.evaluation_collection_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {rgSubTab === 'Safety' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && (
            <>
              {rgSessionData.stage === 'run_safety_gates' && (
                <div className="notice">
                  <p>Ten deterministic checks against already-computed MB-17/MB-18/MB-19 signals -- any failed gate affects the final recommendation, never silently overridden.</p>
                  <Button onClick={runRgSafety} disabled={rgBusy}>Run safety gates</Button>
                </div>
              )}
              {rgSessionData.safety_gate_report?.overall_status !== undefined && (
                <>
                  <p><strong>Overall status:</strong> <span className={`pill ${rgSessionData.safety_gate_report.overall_status === 'pass' ? 'good' : 'block'}`}>{rgSessionData.safety_gate_report.overall_status}</span></p>
                  <pre className="notice">{JSON.stringify(rgSessionData.safety_gate_report, null, 2)}</pre>
                </>
              )}
            </>
          )}
        </>
      )}

      {rgSubTab === 'Compliance' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && (
            <>
              {rgSessionData.stage === 'run_compliance_gates' && (
                <div className="notice">
                  <p>A checklist only -- never a legal certification. Items not yet built at this stage (rollback plan, operator instructions, deployment prerequisites) are marked pending, not failing.</p>
                  <Button onClick={runRgCompliance} disabled={rgBusy}>Run compliance gates</Button>
                </div>
              )}
              {rgSessionData.compliance_gate_report?.overall_status !== undefined && (
                <pre className="notice">{JSON.stringify(rgSessionData.compliance_gate_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {rgSubTab === 'Benchmarks' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && (
            <>
              {rgSessionData.stage === 'run_benchmark_gates' && (
                <div className="notice">
                  <p>Consumes MB-19's own already-computed benchmark result rows -- never re-benchmarks anything.</p>
                  <Button onClick={runRgBenchmarks} disabled={rgBusy}>Run benchmark gates</Button>
                </div>
              )}
              {rgSessionData.benchmark_gate_report?.overall_benchmark_status !== undefined && (
                <pre className="notice">{JSON.stringify(rgSessionData.benchmark_gate_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {rgSubTab === 'Risks' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && (
            <>
              {rgSessionData.stage === 'build_risk_rollback' && (
                <div className="notice">
                  <p>One risk entry per failed safety gate, missing compliance item, and failed/marginal benchmark metric -- never a speculative risk.</p>
                  <Button onClick={runRgBuildRiskRollback} disabled={rgBusy}>Build risk register &amp; rollback plan</Button>
                </div>
              )}
              {rgSessionData.risk_rollback_report?.risk_register && (
                <>
                  <h4>Risk register ({rgSessionData.risk_rollback_report.risk_register.entry_count})</h4>
                  <pre className="notice">{JSON.stringify(rgSessionData.risk_rollback_report.risk_register, null, 2)}</pre>
                </>
              )}
            </>
          )}
        </>
      )}

      {rgSubTab === 'Rollback' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && rgSessionData.risk_rollback_report?.rollback_plan && (
            <pre className="notice">{JSON.stringify(rgSessionData.risk_rollback_report.rollback_plan, null, 2)}</pre>
          )}
          {rgSessionData && !rgSessionData.risk_rollback_report?.rollback_plan && (
            <div className="notice">Build the risk register &amp; rollback plan in the Risks tab first.</div>
          )}
        </>
      )}

      {rgSubTab === 'Compatibility' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && rgSessionData.release_manifest?.compatibility_matrix && (
            <pre className="notice">{JSON.stringify(rgSessionData.release_manifest.compatibility_matrix, null, 2)}</pre>
          )}
          {rgSessionData && !rgSessionData.release_manifest?.compatibility_matrix && (
            <div className="notice">Build the release package in the Package tab first.</div>
          )}
        </>
      )}

      {rgSubTab === 'Prerequisites' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && rgSessionData.release_manifest?.deployment_prerequisites && (
            <pre className="notice">{JSON.stringify(rgSessionData.release_manifest.deployment_prerequisites, null, 2)}</pre>
          )}
          {rgSessionData && !rgSessionData.release_manifest?.deployment_prerequisites && (
            <div className="notice">Build the release package in the Package tab first.</div>
          )}
        </>
      )}

      {rgSubTab === 'Package' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && (
            <>
              {rgSessionData.stage === 'build_release_package' && (
                <div className="notice">
                  <p>Writes 12 deterministic JSON governance files to this session's own release directory, with a SHA-256 checksum recorded for every file. No model weights, no deployment.</p>
                  <Button onClick={runRgBuildPackage} disabled={rgBusy}>Build release decision package</Button>
                </div>
              )}
              {rgSessionData.release_manifest?.artifact_count !== undefined && (
                <pre className="notice">{JSON.stringify(rgSessionData.release_manifest, null, 2)}</pre>
              )}
              <h4>Release artifacts ({rgArtifactsList.length})</h4>
              <ul className="notice">
                {rgArtifactsList.map((a) => (
                  <li key={a.public_id}>{a.artifact_name} -- {a.file_size_bytes} bytes -- sha256={a.sha256.slice(0, 16)}…</li>
                ))}
                {!rgArtifactsList.length && <li>No artifacts written yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {rgSubTab === 'Report' && (
        <>
          {!rgSessionData && <div className="notice">Select a session in Overview first.</div>}
          {rgSessionData && (
            <>
              {rgSessionData.stage === 'generate_report' && (
                <div className="notice">
                  <Button onClick={runRgGenerateReport} disabled={rgBusy}>Generate release readiness report</Button>
                </div>
              )}
              {rgSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Release Readiness Report ready for review. No deployment, runtime start, or
                  public traffic was ever performed by this service -- approval does not imply
                  production safety.</p>
                  <p><strong>Recommendation:</strong> <span className={`pill ${rgSessionData.readiness_report.final_recommendation === 'approved_for_release' ? 'good' : rgSessionData.readiness_report.final_recommendation === 'not_approved' ? 'block' : 'neutral'}`}>{rgSessionData.readiness_report.final_recommendation}</span> -- <strong>Score:</strong> {rgSessionData.readiness_report.overall_readiness_score}</p>
                  <pre className="notice">{JSON.stringify(rgSessionData.readiness_report, null, 2)}</pre>

                  <h4>Final decision</h4>
                  <Button onClick={() => runRgAdminReview('approve')} disabled={rgBusy}>Approve</Button>{' '}
                  <Button onClick={() => runRgAdminReview('reject')} disabled={rgBusy}>Reject</Button>{' '}
                  <Button onClick={() => runRgAdminReview('archive')} disabled={rgBusy}>Archive</Button>
                </div>
              )}
              {rgSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Session closed with status <strong>{rgSessionData.status}</strong>. Permanent release memory recorded.</p>
                </div>
              )}

              <h4>Release memory (permanent)</h4>
              <ul className="notice">
                {rgMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- score {m.overall_readiness_score} -- {m.release_decision_status}</li>
                ))}
                {!rgMemoryList.length && <li>No release memory recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {rgSubTab === 'History' && rgSessionData && (
        <>
          <h4>Session events</h4>
          <ul className="notice">
            {rgEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!rgEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {rgSubTab === 'History' && !rgSessionData && (
        <div className="notice">Select a session in Overview first.</div>
      )}

      {rgSubTab === 'Diagnostics' && (
        <>
          {rgDiag && <pre className="notice">{JSON.stringify(rgDiag, null, 2)}</pre>}
          {!rgDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
