import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const ecSubTabs = [
  'Overview', 'Sources', 'Language', 'OCR', 'Grounding', 'Retrieval', 'Multimodal', 'Package',
  'Regression', 'Report', 'Exports', 'History', 'Diagnostics',
]

export default function EvaluationCenterTab({
  ecSubTab, setEcSubTab,
  ecDiag, ecSessionData,
  ecSessionsList, ecSelectedId, selectEcSession, submitEcCreateSession, ecNewTopic, setEcNewTopic, ecBusy,
  ecEventsList,
  submitEcCollectDatasets, ecDatasetSessionIds, setEcDatasetSessionIds,
  submitEcCollectRagSessions, ecRagSessionIds, setEcRagSessionIds,
  submitEcCollectTrainingPackages, ecPackageSessionIds, setEcPackageSessionIds,
  runEcLanguageBenchmarks,
  runEcOcrBenchmarks,
  runEcGroundingRetrievalBenchmarks,
  runEcMultimodalBenchmarks,
  runEcPackageBenchmarks,
  submitEcRegression, ecBaselineSessionId, setEcBaselineSessionId,
  runEcGenerateReport,
  runEcAdminReview,
  ecMemoryList,
  ecExportsList,
}) {
  return (
    <>
      <p className="notice">
        MB-19 -- Evaluation &amp; Benchmark Center. An evaluation-only system: it never trains,
        fine-tunes, exports GGUF, quantizes, deploys, or activates a runtime. It measures the
        quality of already-certified MB-16 datasets, already-approved MB-17 grounded RAG
        sessions, and already-built MB-18 training packages. Evaluation approval never
        guarantees production model quality.
      </p>

      <div className="dataset-tabs">
        {ecSubTabs.map((t) => (
          <Button key={t} className={ecSubTab === t ? 'active' : ''} onClick={() => setEcSubTab(t)}>{t}</Button>
        ))}
      </div>

      {ecSubTab === 'Overview' && (
        <>
          {ecDiag && (
            <div className="notice">
              <p><strong>Training started:</strong> {String(ecDiag.training_started)} -- <strong>Runtime activated:</strong> {String(ecDiag.runtime_activated)} -- <strong>Model inference performed:</strong> {String(ecDiag.model_inference_performed)}</p>
              <p><strong>Requires certified dataset:</strong> {String(ecDiag.requires_certified_dataset)} -- <strong>Automatic approval:</strong> {String(ecDiag.automatic_approval)}</p>
            </div>
          )}
          {ecSessionData && (
            <section className="metric-grid">
              <StatusCard label="Topic" value={ecSessionData.topic.slice(0, 24)} tone="neutral" />
              <StatusCard label="Stage" value={ecSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={ecSessionData.status} tone={ecSessionData.status.includes('reject') ? 'waiting' : ecSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Evaluation sessions</h4>
              <ul className="notice">
                {ecSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={ecSelectedId === s.public_id ? 'active' : ''} onClick={() => selectEcSession(s.public_id)}>
                      {s.topic.slice(0, 30)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!ecSessionsList.length && <li>No evaluation sessions yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitEcCreateSession}>
                <label>Topic<input value={ecNewTopic} onChange={(e) => setEcNewTopic(e.target.value)} placeholder="Mountain scene evaluation" /></label>
                <Button type="submit" disabled={ecBusy || !ecNewTopic.trim()}>{ecBusy ? 'Working…' : 'Create session'}</Button>
              </form>
            </div>
            <div>
              {!ecSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
              {ecSessionData && (
                <>
                  <h4>Session events</h4>
                  <ul className="notice">
                    {ecEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!ecEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {ecSubTab === 'Sources' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'collect_datasets' && (
                <form className="inline-form training-form" onSubmit={submitEcCollectDatasets}>
                  <label>MB-16 certified dataset session public ID(s), comma-separated
                    <input value={ecDatasetSessionIds} onChange={(e) => setEcDatasetSessionIds(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={ecBusy || !ecDatasetSessionIds.trim()}>Collect certified datasets</Button>
                </form>
              )}
              {ecSessionData.dataset_collection_report?.accepted_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.dataset_collection_report, null, 2)}</pre>
              )}

              {ecSessionData.stage === 'collect_rag_sessions' && (
                <form className="inline-form training-form" onSubmit={submitEcCollectRagSessions}>
                  <label>MB-17 approved RAG session public ID(s), comma-separated, optional
                    <input value={ecRagSessionIds} onChange={(e) => setEcRagSessionIds(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={ecBusy}>Collect approved RAG sessions</Button>
                </form>
              )}
              {ecSessionData.rag_collection_report?.accepted_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.rag_collection_report, null, 2)}</pre>
              )}

              {ecSessionData.stage === 'collect_training_packages' && (
                <form className="inline-form training-form" onSubmit={submitEcCollectTrainingPackages}>
                  <label>MB-18 approved training package session public ID(s), comma-separated, optional
                    <input value={ecPackageSessionIds} onChange={(e) => setEcPackageSessionIds(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={ecBusy}>Collect training packages</Button>
                </form>
              )}
              {ecSessionData.package_collection_report?.accepted_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.package_collection_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {ecSubTab === 'Language' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'run_language_benchmarks' && (
                <div className="notice">
                  <Button onClick={runEcLanguageBenchmarks} disabled={ecBusy}>Run language benchmarks</Button>
                </div>
              )}
              {ecSessionData.language_benchmark_report?.records_analyzed !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.language_benchmark_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {ecSubTab === 'OCR' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'run_ocr_benchmarks' && (
                <div className="notice">
                  <p>Reuses MB-14's own OCR cross-validator applied to MB-17's own already-retrieved evidence -- never a new OCR pass.</p>
                  <Button onClick={runEcOcrBenchmarks} disabled={ecBusy}>Run OCR benchmarks</Button>
                </div>
              )}
              {ecSessionData.ocr_benchmark_report?.session_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.ocr_benchmark_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {ecSubTab === 'Grounding' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'run_grounding_retrieval_benchmarks' && (
                <div className="notice">
                  <p>Grounding and retrieval benchmarks run together as one combined stage.</p>
                  <Button onClick={runEcGroundingRetrievalBenchmarks} disabled={ecBusy}>Run grounding &amp; retrieval benchmarks</Button>
                </div>
              )}
              {ecSessionData.grounding_benchmark_report?.session_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.grounding_benchmark_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {ecSubTab === 'Retrieval' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && ecSessionData.retrieval_benchmark_report?.session_count !== undefined && (
            <pre className="notice">{JSON.stringify(ecSessionData.retrieval_benchmark_report, null, 2)}</pre>
          )}
          {ecSessionData && ecSessionData.retrieval_benchmark_report?.session_count === undefined && (
            <div className="notice">Run grounding &amp; retrieval benchmarks in the Grounding tab first.</div>
          )}
        </>
      )}

      {ecSubTab === 'Multimodal' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'run_multimodal_benchmarks' && (
                <div className="notice">
                  <Button onClick={runEcMultimodalBenchmarks} disabled={ecBusy}>Run multimodal coverage benchmarks</Button>
                </div>
              )}
              {ecSessionData.multimodal_benchmark_report?.total_record_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.multimodal_benchmark_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {ecSubTab === 'Package' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'run_package_benchmarks' && (
                <div className="notice">
                  <p>Every checksum and file-existence check reads real files on disk -- this never modifies an MB-18 package.</p>
                  <Button onClick={runEcPackageBenchmarks} disabled={ecBusy}>Run package integrity benchmarks</Button>
                </div>
              )}
              {ecSessionData.package_benchmark_report?.package_count !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.package_benchmark_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {ecSubTab === 'Regression' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'run_regression_comparison' && (
                <form className="inline-form training-form" onSubmit={submitEcRegression}>
                  <label>Baseline evaluation session public ID (optional -- defaults to the most recent approved session)
                    <input value={ecBaselineSessionId} onChange={(e) => setEcBaselineSessionId(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={ecBusy}>Run regression comparison</Button>
                </form>
              )}
              {ecSessionData.regression_report?.has_baseline !== undefined && (
                <pre className="notice">{JSON.stringify(ecSessionData.regression_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {ecSubTab === 'Report' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              {ecSessionData.stage === 'generate_report' && (
                <div className="notice">
                  <Button onClick={runEcGenerateReport} disabled={ecBusy}>Generate evaluation &amp; release readiness report</Button>
                </div>
              )}
              {ecSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Evaluation Report ready for review. No model inference was ever performed by this
                  service -- evaluation approval does not guarantee production model quality.</p>
                  <p><strong>Release readiness:</strong> <span className={`pill ${ecSessionData.release_readiness.status === 'Ready' ? 'good' : ecSessionData.release_readiness.status === 'Blocked' ? 'block' : 'neutral'}`}>{ecSessionData.release_readiness.status}</span></p>
                  <pre className="notice">{JSON.stringify(ecSessionData.evaluation_report, null, 2)}</pre>

                  <h4>Final decision</h4>
                  <Button onClick={() => runEcAdminReview('approve')} disabled={ecBusy}>Approve</Button>{' '}
                  <Button onClick={() => runEcAdminReview('reject')} disabled={ecBusy}>Reject</Button>{' '}
                  <Button onClick={() => runEcAdminReview('archive')} disabled={ecBusy}>Archive</Button>
                </div>
              )}
              {ecSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Session closed with status <strong>{ecSessionData.status}</strong>. Permanent evaluation memory recorded.</p>
                </div>
              )}

              <h4>Evaluation memory (permanent)</h4>
              <ul className="notice">
                {ecMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- score {m.overall_score} -- {m.release_readiness_status}</li>
                ))}
                {!ecMemoryList.length && <li>No evaluation memory recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {ecSubTab === 'Exports' && (
        <>
          {!ecSessionData && <div className="notice">Select a session in Overview first.</div>}
          {ecSessionData && (
            <>
              <h4>Export artifacts ({ecExportsList.length})</h4>
              <ul className="notice">
                {ecExportsList.map((a) => (
                  <li key={a.artifact_name}>{a.artifact_name} -- {a.file_size_bytes} bytes -- sha256={a.sha256.slice(0, 16)}…</li>
                ))}
                {!ecExportsList.length && <li>No export artifacts written yet -- generate the report first.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {ecSubTab === 'History' && ecSessionData && (
        <>
          <h4>Session events</h4>
          <ul className="notice">
            {ecEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!ecEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {ecSubTab === 'History' && !ecSessionData && (
        <div className="notice">Select a session in Overview first.</div>
      )}

      {ecSubTab === 'Diagnostics' && (
        <>
          {ecDiag && <pre className="notice">{JSON.stringify(ecDiag, null, 2)}</pre>}
          {!ecDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
