import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const pcSubTabs = [
  'Overview', 'Link Phases', 'RAG Gate', 'Readiness & Timeline', 'Prediction',
  'Recommendation & Report', 'History', 'Diagnostics',
]

export default function PipelineCoordinatorTab({
  pcSubTab, setPcSubTab,
  pcDiag, pcSessionData,
  pcSessionsList, pcSelectedId, selectPcSession, submitPcCreateSession, pcNewTopic, setPcNewTopic, pcBusy,
  submitPcLinkResearch, pcMb09Id, setPcMb09Id,
  submitPcLinkResearchCenter, pcMb10Id, setPcMb10Id,
  runPcRefreshResearchCenter,
  submitPcLinkDatasetEvolution, pcMb11Id, setPcMb11Id,
  submitPcLinkTraining, pcMb06Id, setPcMb06Id,
  runPcRefreshTraining,
  runPcRunRagFirstEnforcement,
  runPcGenerateTrainingReadiness,
  runPcGenerateTimeline,
  runPcPredictImprovement,
  runPcGenerateRecommendation,
  runPcGenerateReport,
  runPcAdminDecide,
  pcEventsList,
}) {
  return (
    <>
      <p className="notice">
        MB-12 -- Autonomous AI Knowledge Pipeline Coordinator. Not a Training Engine, a Dataset
        Writer, or a Runtime. It links together, in order, the real sessions MB-09, MB-10, MB-11,
        and MB-06 already produced for one topic and reports on the result -- orchestration,
        validation, scheduling, and reporting only. It never contacts RAG Sandbox itself; it only
        ever reads a RAG report MB-11 or MB-06 already produced. Every stage transition is
        dependency-checked so a pipeline can never skip a stage.
      </p>

      <div className="dataset-tabs">
        {pcSubTabs.map((t) => (
          <Button key={t} className={pcSubTab === t ? 'active' : ''} onClick={() => setPcSubTab(t)}>{t}</Button>
        ))}
      </div>

      {pcSubTab === 'Overview' && (
        <>
          {pcDiag && (
            <div className="notice">
              <p><strong>Training started:</strong> {String(pcDiag.training_started)} -- <strong>Models deployed:</strong> {String(pcDiag.models_deployed)} -- <strong>RAG Sandbox called directly:</strong> {String(pcDiag.rag_sandbox_called_directly)}</p>
            </div>
          )}
          {pcSessionData && (
            <section className="metric-grid">
              <StatusCard label="Topic" value={pcSessionData.topic} tone="neutral" />
              <StatusCard label="Stage" value={pcSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={pcSessionData.status} tone={pcSessionData.status.includes('reject') ? 'waiting' : pcSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Pipelines</h4>
              <ul className="notice">
                {pcSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={pcSelectedId === s.public_id ? 'active' : ''} onClick={() => selectPcSession(s.public_id)}>
                      {s.topic} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!pcSessionsList.length && <li>No pipelines yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitPcCreateSession}>
                <label>Topic<input value={pcNewTopic} onChange={(e) => setPcNewTopic(e.target.value)} placeholder="matches the topic used in MB-09/MB-10" /></label>
                <Button type="submit" disabled={pcBusy || !pcNewTopic.trim()}>{pcBusy ? 'Working…' : 'Start pipeline'}</Button>
              </form>
            </div>
            <div>
              {!pcSessionData && <div className="notice">Select or start a pipeline to work through it in the other sub-tabs.</div>}
              {pcSessionData && (
                <>
                  <h4>Linked sessions</h4>
                  <ul className="notice">
                    <li>MB-09 (Research): {pcSessionData.mb09_session_public_id || 'not linked'}</li>
                    <li>MB-10 (Provider Consensus / Draft): {pcSessionData.mb10_session_public_id || 'not linked'}</li>
                    <li>MB-11 (Dataset Evolution): {pcSessionData.mb11_session_public_id || 'not linked'}</li>
                    <li>MB-06 (Training): {pcSessionData.mb06_session_public_id || 'not linked'}</li>
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {pcSubTab === 'Link Phases' && (
        <>
          {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
          {pcSessionData && (
            <div className="notice">
              <p>Every link is dependency-checked -- linking out of order is rejected with the exact reason.</p>
              <form className="inline-form training-form" onSubmit={submitPcLinkResearch}>
                <label>MB-09 planning session public ID<input value={pcMb09Id} onChange={(e) => setPcMb09Id(e.target.value)} /></label>
                <Button type="submit" disabled={pcBusy || !pcMb09Id.trim()}>Link Research (MB-09)</Button>
              </form>
              <form className="inline-form training-form" onSubmit={submitPcLinkResearchCenter}>
                <label>MB-10 research session public ID<input value={pcMb10Id} onChange={(e) => setPcMb10Id(e.target.value)} /></label>
                <Button type="submit" disabled={pcBusy || !pcMb10Id.trim()}>Link Provider Consensus / Draft (MB-10)</Button>
              </form>
              <Button onClick={runPcRefreshResearchCenter} disabled={pcBusy}>Refresh MB-10 link (check for draft readiness)</Button>
              <form className="inline-form training-form" onSubmit={submitPcLinkDatasetEvolution}>
                <label>MB-11 evolution session public ID<input value={pcMb11Id} onChange={(e) => setPcMb11Id(e.target.value)} /></label>
                <Button type="submit" disabled={pcBusy || !pcMb11Id.trim()}>Link Dataset Evolution (MB-11)</Button>
              </form>
              <form className="inline-form training-form" onSubmit={submitPcLinkTraining}>
                <label>MB-06 learning session public ID<input value={pcMb06Id} onChange={(e) => setPcMb06Id(e.target.value)} /></label>
                <Button type="submit" disabled={pcBusy || !pcMb06Id.trim()}>Link Training (MB-06)</Button>
              </form>
              <Button onClick={runPcRefreshTraining} disabled={pcBusy}>Refresh MB-06 link (check for training/benchmark/release progress)</Button>
            </div>
          )}
        </>
      )}

      {pcSubTab === 'RAG Gate' && (
        <>
          {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
          {pcSessionData && (
            <>
              <p className="notice">Reads whichever RAG report MB-11 or MB-06 already produced -- verifies citations, evidence, hallucination rate, and admin approval. Never calls RAG Sandbox itself. On failure, the pipeline returns to Dataset Planned.</p>
              <Button onClick={runPcRunRagFirstEnforcement} disabled={pcBusy}>Run RAG First Enforcement</Button>
              {pcSessionData.rag_first_report && Object.keys(pcSessionData.rag_first_report).length > 0 && (
                <pre className="notice">{JSON.stringify(pcSessionData.rag_first_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {pcSubTab === 'Readiness & Timeline' && (
        <>
          {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
          {pcSessionData && (
            <>
              <p className="notice">Unified readiness score combines already-computed signals from MB-05, MB-05.1, MB-06, MB-08, MB-09, MB-10, and MB-11 -- omitting any source not yet linked, never treating it as zero.</p>
              <Button onClick={runPcGenerateTrainingReadiness} disabled={pcBusy}>Generate training readiness report</Button>{' '}
              <Button onClick={runPcGenerateTimeline} disabled={pcBusy}>Generate lifecycle timeline</Button>
              {pcSessionData.training_readiness_report?.unified_readiness_score !== undefined && (
                <pre className="notice">{JSON.stringify(pcSessionData.training_readiness_report, null, 2)}</pre>
              )}
              {pcSessionData.lifecycle_timeline?.timeline && (
                <pre className="notice">{JSON.stringify(pcSessionData.lifecycle_timeline, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {pcSubTab === 'Prediction' && (
        <>
          {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
          {pcSessionData && (
            <>
              <p className="notice">Simulation only -- expected benchmark, reasoning, Tamil quality, English quality, memory, and hallucination-reduction gains, derived from MB-11's own projection and, once linked, MB-06's real benchmark comparison.</p>
              <Button onClick={runPcPredictImprovement} disabled={pcBusy}>Predict improvement</Button>
              {pcSessionData.improvement_prediction?.expected_benchmark_gain !== undefined && (
                <pre className="notice">{JSON.stringify(pcSessionData.improvement_prediction, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {pcSubTab === 'Recommendation & Report' && (
        <>
          {!pcSessionData && <div className="notice">Select a pipeline in Overview first.</div>}
          {pcSessionData && (
            <>
              <div className="notice">
                <Button onClick={runPcGenerateRecommendation} disabled={pcBusy}>Generate recommendation</Button>{' '}
                <Button onClick={runPcGenerateReport} disabled={pcBusy}>Generate master pipeline report</Button>
              </div>
              {pcSessionData.recommendation_report?.action && (
                <p className="notice">Recommended: <strong>{pcSessionData.recommendation_report.action}</strong> (confidence {pcSessionData.recommendation_report.confidence}, risk {pcSessionData.recommendation_report.risk}) -- {pcSessionData.recommendation_report.why}</p>
              )}
              {pcSessionData.master_report?.next_action && (
                <pre className="notice">{JSON.stringify(pcSessionData.master_report, null, 2)}</pre>
              )}
              <div className="notice">
                <p>Admin Decision Center -- always available, no decision executes anything:</p>
                <Button onClick={() => runPcAdminDecide('continue')} disabled={pcBusy}>Continue</Button>{' '}
                <Button onClick={() => runPcAdminDecide('pause')} disabled={pcBusy}>Pause</Button>{' '}
                <Button onClick={() => runPcAdminDecide('research_more')} disabled={pcBusy}>Research More</Button>{' '}
                <Button onClick={() => runPcAdminDecide('request_providers')} disabled={pcBusy}>Request Providers</Button>{' '}
                <Button onClick={() => runPcAdminDecide('improve_dataset')} disabled={pcBusy}>Improve Dataset</Button>{' '}
                <Button onClick={() => runPcAdminDecide('retry_rag')} disabled={pcBusy}>Retry RAG</Button>{' '}
                <Button onClick={() => runPcAdminDecide('approve_training')} disabled={pcBusy}>Approve Training</Button>{' '}
                <Button onClick={() => runPcAdminDecide('reject')} disabled={pcBusy}>Reject</Button>{' '}
                <Button onClick={() => runPcAdminDecide('archive')} disabled={pcBusy}>Archive</Button>
              </div>
            </>
          )}
        </>
      )}

      {pcSubTab === 'History' && pcSessionData && (
        <>
          <h4>Pipeline events</h4>
          <ul className="notice">
            {pcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!pcEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {pcSubTab === 'History' && !pcSessionData && (
        <div className="notice">Select a pipeline in Overview first.</div>
      )}

      {pcSubTab === 'Diagnostics' && (
        <>
          {pcDiag && <pre className="notice">{JSON.stringify(pcDiag, null, 2)}</pre>}
          {!pcDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
