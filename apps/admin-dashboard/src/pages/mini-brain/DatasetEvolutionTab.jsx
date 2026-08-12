import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const deSubTabs = [
  'Overview', 'Knowledge Evolution', 'Dataset Evolution', 'Simulation', 'Recommendation & Report',
  'RAG Status', 'History', 'Diagnostics',
]

export default function DatasetEvolutionTab({
  deSubTab, setDeSubTab,
  deDiag, deSessionData,
  deSessionsList, deSelectedId, selectDeSession, submitDeCreateSession, deNewSourceId, setDeNewSourceId, deBusy,
  deEventsList,
  runDeKnowledgeEvolution,
  runDeDatasetEvolution,
  runDeSimulation,
  runDeGenerateRecommendation,
  runDeGenerateReport,
  runDeAdminReview,
  submitDeRunRagEvaluation, deRagForm, setDeRagForm, runDeFinalizeRagEvaluation,
  runDeAdminReviewRag,
}) {
  return (
    <>
      <p className="notice">
        MB-11 -- Autonomous Dataset Evolution &amp; Knowledge Factory. Not a Training Engine, a
        Dataset Editor, or a Runtime. It continuously analyzes what MB-05, MB-05.1, MB-08, MB-09,
        and MB-10 have already computed and plans how Brud AI's dataset should evolve --
        recommendation and planning only. It never writes a dataset record, never trains, never
        deploys, and never modifies RAG -- every action requires explicit admin approval.
      </p>

      <div className="dataset-tabs">
        {deSubTabs.map((t) => (
          <Button key={t} className={deSubTab === t ? 'active' : ''} onClick={() => setDeSubTab(t)}>{t}</Button>
        ))}
      </div>

      {deSubTab === 'Overview' && (
        <>
          {deDiag && (
            <div className="notice">
              <p><strong>Dataset writes performed:</strong> {String(deDiag.dataset_writes_performed)} -- Dataset Studio remains the only place a dataset is actually written.</p>
              <p><strong>Training started:</strong> {String(deDiag.training_started)} -- <strong>Models deployed:</strong> {String(deDiag.models_deployed)} -- <strong>RAG modified:</strong> {String(deDiag.rag_modified)}</p>
            </div>
          )}
          {deSessionData && (
            <section className="metric-grid">
              <StatusCard label="Dataset source" value={deSessionData.dataset_source_public_id.slice(0, 12)} tone="neutral" />
              <StatusCard label="Stage" value={deSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={deSessionData.status} tone={deSessionData.status.includes('reject') ? 'waiting' : deSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Evolution cycles</h4>
              <ul className="notice">
                {deSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={deSelectedId === s.public_id ? 'active' : ''} onClick={() => selectDeSession(s.public_id)}>
                      {s.dataset_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!deSessionsList.length && <li>No evolution cycles yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitDeCreateSession}>
                <label>Dataset source public ID<input value={deNewSourceId} onChange={(e) => setDeNewSourceId(e.target.value)} placeholder="source public_id from Dataset Studio" /></label>
                <Button type="submit" disabled={deBusy || !deNewSourceId.trim()}>{deBusy ? 'Working…' : 'Start evolution cycle'}</Button>
              </form>
            </div>
            <div>
              {!deSessionData && <div className="notice">Select or start an evolution cycle to work through its workflow in the other sub-tabs.</div>}
              {deSessionData && (
                <>
                  <h4>Cycle events</h4>
                  <ul className="notice">
                    {deEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!deEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {deSubTab === 'Knowledge Evolution' && (
        <>
          {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
          {deSessionData && (
            <>
              {deSessionData.stage === 'knowledge_evolution' && (
                <div className="notice">
                  <p>Combines the current dataset's real MB-05/MB-05.1 analysis with recent closed MB-08/MB-09/MB-10 evidence into one evolution analysis, dependency graph, coverage classification, and knowledge-relationship report.</p>
                  <Button onClick={runDeKnowledgeEvolution} disabled={deBusy}>Run knowledge evolution analysis</Button>
                </div>
              )}
              {deSessionData.evolution_analysis?.evolution_pressure !== undefined && (
                <>
                  <h4>Evolution analysis</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.evolution_analysis, null, 2)}</pre>
                  <h4>Dependency graph</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.dependency_graph, null, 2)}</pre>
                  <h4>Coverage</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.coverage_report, null, 2)}</pre>
                  <h4>Knowledge relationships</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.relationship_report, null, 2)}</pre>
                </>
              )}
            </>
          )}
        </>
      )}

      {deSubTab === 'Dataset Evolution' && (
        <>
          {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
          {deSessionData && (
            <>
              {deSessionData.stage === 'dataset_evolution' && (
                <div className="notice">
                  <p>Plans expansion action, version projection, knowledge-factory content recommendations, a synthetic-dataset design, and predicted quality evolution. Recommends only -- never performs any of it.</p>
                  <Button onClick={runDeDatasetEvolution} disabled={deBusy}>Plan dataset evolution</Button>
                </div>
              )}
              {deSessionData.expansion_plan?.action && (
                <>
                  <h4>Expansion plan</h4>
                  <p className="notice">Recommended action: <strong>{deSessionData.expansion_plan.action}</strong> -- {deSessionData.expansion_plan.why}</p>
                  <h4>Version plan</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.version_plan, null, 2)}</pre>
                  <h4>Knowledge factory plan</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.knowledge_factory_plan, null, 2)}</pre>
                  <h4>Synthetic dataset plan (design only, never generated)</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.synthetic_dataset_plan, null, 2)}</pre>
                  <h4>Quality evolution prediction</h4>
                  <pre className="notice">{JSON.stringify(deSessionData.quality_evolution, null, 2)}</pre>
                </>
              )}
            </>
          )}
        </>
      )}

      {deSubTab === 'Simulation' && (
        <>
          {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
          {deSessionData && (
            <>
              {deSessionData.stage === 'evolution_simulation' && (
                <div className="notice">
                  <p>Simulation only -- no benchmark runs, no model is evaluated, no RAG query executes.</p>
                  <Button onClick={runDeSimulation} disabled={deBusy}>Run evolution simulation</Button>
                </div>
              )}
              {deSessionData.simulation_report?.expected_improvement !== undefined && (
                <pre className="notice">{JSON.stringify(deSessionData.simulation_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {deSubTab === 'Recommendation & Report' && (
        <>
          {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
          {deSessionData && (
            <>
              {deSessionData.stage === 'recommendation' && !deSessionData.recommendation_report?.recommendation && (
                <div className="notice">
                  <p>One of: Continue Current Dataset / Expand Dataset / Split Dataset / Replace Dataset / Research More / Collect More Data / Wait / Reject -- with WHY, evidence, confidence, and risk.</p>
                  <Button onClick={runDeGenerateRecommendation} disabled={deBusy}>Generate recommendation</Button>
                </div>
              )}
              {deSessionData.recommendation_report?.recommendation && deSessionData.stage === 'recommendation' && !deSessionData.evolution_report?.ready_for_admin_review && (
                <div className="notice">
                  <p>Recommended: <strong>{deSessionData.recommendation_report.recommendation}</strong> (confidence {deSessionData.recommendation_report.confidence}, risk {deSessionData.recommendation_report.risk}) -- {deSessionData.recommendation_report.why}</p>
                  <Button onClick={runDeGenerateReport} disabled={deBusy}>Generate evolution report</Button>
                </div>
              )}
              {deSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Evolution Report ready for review.</p>
                  <pre className="notice">{JSON.stringify(deSessionData.evolution_report, null, 2)}</pre>
                  <Button onClick={() => runDeAdminReview('approve_evolution')} disabled={deBusy}>Approve Evolution</Button>{' '}
                  <Button onClick={() => runDeAdminReview('edit_plan')} disabled={deBusy}>Edit Plan</Button>{' '}
                  <Button onClick={() => runDeAdminReview('research_more')} disabled={deBusy}>Research More</Button>{' '}
                  <Button onClick={() => runDeAdminReview('request_provider_consensus')} disabled={deBusy}>Request Provider Consensus</Button>{' '}
                  <Button onClick={() => runDeAdminReview('expand_dataset')} disabled={deBusy}>Expand Dataset</Button>{' '}
                  <Button onClick={() => runDeAdminReview('split_dataset')} disabled={deBusy}>Split Dataset</Button>{' '}
                  <Button onClick={() => runDeAdminReview('merge_dataset')} disabled={deBusy}>Merge Dataset</Button>{' '}
                  <Button onClick={() => runDeAdminReview('archive_plan')} disabled={deBusy}>Archive Plan</Button>{' '}
                  <Button onClick={() => runDeAdminReview('reject')} disabled={deBusy}>Reject</Button>{' '}
                  <Button onClick={() => runDeAdminReview('send_to_rag')} disabled={deBusy || deSessionData.draft_admin_decision !== 'approve_evolution'}>Send to RAG</Button>
                </div>
              )}
              {deSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Evolution cycle closed with status <strong>{deSessionData.status}</strong>. No automatic action was taken.</p>
                </div>
              )}
            </>
          )}
        </>
      )}

      {deSubTab === 'RAG Status' && (
        <>
          {!deSessionData && <div className="notice">Select an evolution cycle in Overview first.</div>}
          {deSessionData && (
            <>
              <p className="notice">Reuses MB-06/MB-10's exact RAG Sandbox pattern: generation + evaluation + report finalization only. Corpus, index, and retrieval remain admin-driven through RAG Sandbox's own UI.</p>
              {deSessionData.stage === 'rag_evaluation' && (
                <form className="inline-form training-form" onSubmit={submitDeRunRagEvaluation}>
                  <label>RAG Sandbox experiment public ID<input value={deRagForm.rag_sandbox_experiment_public_id} onChange={(e) => setDeRagForm({ ...deRagForm, rag_sandbox_experiment_public_id: e.target.value })} /></label>
                  <label>Retrieval run public ID<input value={deRagForm.retrieval_run_public_id} onChange={(e) => setDeRagForm({ ...deRagForm, retrieval_run_public_id: e.target.value })} /></label>
                  <label>Generation assignment public ID<input value={deRagForm.generation_assignment_public_id} onChange={(e) => setDeRagForm({ ...deRagForm, generation_assignment_public_id: e.target.value })} /></label>
                  <Button type="submit" disabled={deBusy}>Run RAG generation + evaluation</Button>
                  <Button type="button" onClick={runDeFinalizeRagEvaluation} disabled={deBusy}>Finalize report (retry after human review)</Button>
                </form>
              )}
              {deSessionData.rag_report && Object.keys(deSessionData.rag_report).length > 0 && (
                <pre className="notice">{JSON.stringify(deSessionData.rag_report, null, 2)}</pre>
              )}
              {deSessionData.stage === 'awaiting_rag_review' && (
                <div className="notice">
                  <Button onClick={() => runDeAdminReviewRag('approve')} disabled={deBusy}>Approve</Button>{' '}
                  <Button onClick={() => runDeAdminReviewRag('reject')} disabled={deBusy}>Reject</Button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {deSubTab === 'History' && deSessionData && (
        <>
          <h4>Cycle events</h4>
          <ul className="notice">
            {deEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!deEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {deSubTab === 'History' && !deSessionData && (
        <div className="notice">Select an evolution cycle in Overview first.</div>
      )}

      {deSubTab === 'Diagnostics' && (
        <>
          {deDiag && <pre className="notice">{JSON.stringify(deDiag, null, 2)}</pre>}
          {!deDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
