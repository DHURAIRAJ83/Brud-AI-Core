import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function ContinuousLearningCenterTab({
  clcDiag,
  clcMemoryItems, submitClcRecordMemory, clcMemoryForm, setClcMemoryForm, clcBusy,
  clcSessionsList, clcSelectedId, selectClcSession, submitClcCreateSession,
  clcSessionData,
  runClcEvolveKnowledgeGaps,
  runClcBuildLearningQueue,
  submitClcBuildDraft, clcDraftTopic, setClcDraftTopic,
  submitClcPrepareProviderRequest, clcProviders, setClcProviders,
  submitClcIngestProviderResults, clcProviderOutputs, setClcProviderOutputs,
  submitClcPlanDatasetEvolution, clcExistingDatasetId, setClcExistingDatasetId,
  runClcBuildRoadmap,
  runClcGenerateRecommendation,
  runClcGenerateReport,
  runClcAdminReview,
  clcEventsList,
}) {
  return (
    <>
      <p className="notice">
        MB-09 -- Continuous Learning Center. A planning and recommendation layer only: it is not a
        Training Engine, Dataset Generator, or Model Runtime. It continuously analyzes completed
        MB-08 reports, discovers recurring knowledge gaps, prepares learning plans and draft
        outlines, plans multi-provider consensus requests, and recommends the next learning cycle.
        Nothing here automatically modifies a dataset, calls an external AI provider, triggers RAG,
        starts MB-06, launches MB-07, or trains a model -- every downstream action stays behind
        explicit admin approval.
      </p>
      {clcDiag && (
        <div className="notice">
          <p><strong>External providers called:</strong> {String(clcDiag.external_providers_called)} -- Brud AI has no Claude/OpenAI/Gemini/OpenRouter integration; provider outputs must be collected externally and supplied back.</p>
          <p><strong>Writes:</strong> {clcDiag.writes_scope}</p>
        </div>
      )}

      <h4>Learning Memory (permanent history)</h4>
      <div className="notice">
        <ul>
          {clcMemoryItems.map((m) => (
            <li key={m.public_id}>{m.created_at} -- weak: {m.weak_domains.join(', ') || 'none'} -- training decision: {m.training_decision ?? 'n/a'} -- {m.improvement_notes}</li>
          ))}
          {!clcMemoryItems.length && <li>No memory entries recorded yet.</li>}
        </ul>
        <form className="inline-form training-form" onSubmit={submitClcRecordMemory}>
          <label>MB-08 session public ID<input value={clcMemoryForm.continuous_learning_session_public_id} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, continuous_learning_session_public_id: e.target.value })} /></label>
          <label>Model version public ID (optional)<input value={clcMemoryForm.model_version_public_id} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, model_version_public_id: e.target.value })} /></label>
          <label>Dataset version public ID (optional)<input value={clcMemoryForm.dataset_version_public_id} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, dataset_version_public_id: e.target.value })} /></label>
          <label>Improvement notes<input value={clcMemoryForm.improvement_notes} onChange={(e) => setClcMemoryForm({ ...clcMemoryForm, improvement_notes: e.target.value })} /></label>
          <Button type="submit" disabled={clcBusy || !clcMemoryForm.continuous_learning_session_public_id}>Record memory</Button>
        </form>
      </div>

      <div className="training-grid">
        <div>
          <h4>Planning cycles</h4>
          <ul className="notice">
            {clcSessionsList.map((s) => (
              <li key={s.public_id}>
                <Button className={clcSelectedId === s.public_id ? 'active' : ''} onClick={() => selectClcSession(s.public_id)}>
                  {s.public_id.slice(0, 8)} -- {s.stage} ({s.status})
                </Button>
              </li>
            ))}
            {!clcSessionsList.length && <li>No planning cycles yet.</li>}
          </ul>
          <form className="inline-form training-form" onSubmit={submitClcCreateSession}>
            <Button type="submit" disabled={clcBusy}>{clcBusy ? 'Working…' : 'Start planning cycle'}</Button>
          </form>
        </div>

        <div>
          {!clcSessionData && <div className="notice">Select or start a planning cycle to see its workflow.</div>}

          {clcSessionData && (
            <>
              <section className="metric-grid">
                <StatusCard label="Stage" value={clcSessionData.stage} tone="neutral" />
                <StatusCard label="Status" value={clcSessionData.status} tone={clcSessionData.status.includes('reject') ? 'waiting' : clcSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
                <StatusCard label="Admin decision" value={clcSessionData.admin_decision ?? 'pending'} tone={clcSessionData.admin_decision ? 'good' : 'neutral'} />
              </section>

              {clcSessionData.stage === 'knowledge_gap_evolution' && (
                <div className="notice">
                  <p>Knowledge Gap Evolution: compares recent MB-08 reports for recurring weaknesses.</p>
                  <Button onClick={runClcEvolveKnowledgeGaps} disabled={clcBusy}>Evolve knowledge gaps</Button>
                </div>
              )}
              {clcSessionData.knowledge_gap_evolution_report?.recurring_weak_domains && (
                <pre className="notice">{JSON.stringify(clcSessionData.knowledge_gap_evolution_report.recurring_weak_domains, null, 2)}</pre>
              )}

              {clcSessionData.stage === 'learning_queue' && (
                <div className="notice">
                  <p>Learning Queue: prioritized topics only -- never creates a dataset.</p>
                  <Button onClick={runClcBuildLearningQueue} disabled={clcBusy}>Build learning queue</Button>
                </div>
              )}
              {clcSessionData.learning_queue_report?.queue && (
                <pre className="notice">{JSON.stringify(clcSessionData.learning_queue_report.queue, null, 2)}</pre>
              )}

              {clcSessionData.stage === 'draft_planning' && (
                <div className="notice">
                  <p>Local Draft Planner: structure only -- never invents facts, never claims verification.</p>
                  <form className="inline-form training-form" onSubmit={submitClcBuildDraft}>
                    <label>Topic (optional -- defaults to top queue item)<input value={clcDraftTopic} onChange={(e) => setClcDraftTopic(e.target.value)} /></label>
                    <Button type="submit" disabled={clcBusy}>Build draft outline</Button>
                  </form>
                </div>
              )}
              {clcSessionData.draft_report?.topic && (
                <pre className="notice">{JSON.stringify(clcSessionData.draft_report, null, 2)}</pre>
              )}

              {clcSessionData.stage === 'provider_request' && (
                <div className="notice">
                  <p>Multi-Provider Consensus Planner: prepares a request only -- Brud AI never calls a provider automatically.</p>
                  <form className="inline-form training-form" onSubmit={submitClcPrepareProviderRequest}>
                    <label>Providers (comma separated: claude, openai, gemini, openrouter, local_only)<input value={clcProviders} onChange={(e) => setClcProviders(e.target.value)} /></label>
                    <Button type="submit" disabled={clcBusy}>Prepare provider request</Button>
                  </form>
                </div>
              )}

              {clcSessionData.stage === 'provider_consensus' && (
                <div className="notice">
                  <p>Once an admin has run the requested providers externally, supply their outputs here for comparison, conflict detection, and consensus.</p>
                  <form className="inline-form training-form" onSubmit={submitClcIngestProviderResults}>
                    {clcProviderOutputs.map((o, idx) => (
                      <label key={idx}>{o.provider} output
                        <input value={o.output_text} onChange={(e) => {
                          const next = [...clcProviderOutputs]; next[idx] = { ...next[idx], output_text: e.target.value }; setClcProviderOutputs(next)
                        }} />
                      </label>
                    ))}
                    <Button type="submit" disabled={clcBusy}>Ingest provider results</Button>
                  </form>
                </div>
              )}
              {clcSessionData.provider_consensus_report?.confidence && (
                <pre className="notice">{JSON.stringify(clcSessionData.provider_consensus_report, null, 2)}</pre>
              )}

              {clcSessionData.stage === 'dataset_evolution' && (
                <div className="notice">
                  <p>Dataset Evolution Planner: recommends merge/extend/replace/split/ignore -- never performs the merge.</p>
                  <form className="inline-form training-form" onSubmit={submitClcPlanDatasetEvolution}>
                    <label>Existing dataset source public ID (optional)<input value={clcExistingDatasetId} onChange={(e) => setClcExistingDatasetId(e.target.value)} /></label>
                    <Button type="submit" disabled={clcBusy}>Plan dataset evolution</Button>
                  </form>
                </div>
              )}

              {clcSessionData.stage === 'knowledge_roadmap' && (
                <div className="notice">
                  <p>Knowledge Roadmap: strengths, weaknesses, missing knowledge, future priorities.</p>
                  <Button onClick={runClcBuildRoadmap} disabled={clcBusy}>Build roadmap</Button>
                </div>
              )}

              {clcSessionData.stage === 'recommendation' && !clcSessionData.planning_report?.next_action && (
                <div className="notice">
                  <p>Learning Recommendation Engine: one of No Action / Collect More Data / Local Draft / External Provider Consensus / RAG Evaluation / Training Candidate.</p>
                  <Button onClick={runClcGenerateRecommendation} disabled={clcBusy}>Generate recommendation</Button>
                </div>
              )}
              {clcSessionData.stage === 'recommendation' && clcSessionData.recommendation_report?.action && !clcSessionData.planning_report?.next_action && (
                <div className="notice">
                  <p>Recommended: <strong>{clcSessionData.recommendation_report.action}</strong> -- {clcSessionData.recommendation_report.why}</p>
                  <Button onClick={runClcGenerateReport} disabled={clcBusy}>Generate admin planning report</Button>
                </div>
              )}

              {clcSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Admin Planning Report ready for review.</p>
                  <pre className="notice">{JSON.stringify(clcSessionData.planning_report, null, 2)}</pre>
                  <Button onClick={() => runClcAdminReview('reject')} disabled={clcBusy}>Reject</Button>{' '}
                  <Button onClick={() => runClcAdminReview('edit')} disabled={clcBusy}>Edit</Button>{' '}
                  <Button onClick={() => runClcAdminReview('approve_draft')} disabled={clcBusy}>Approve Draft</Button>{' '}
                  <Button onClick={() => runClcAdminReview('request_provider_consensus')} disabled={clcBusy}>Request Provider Consensus</Button>{' '}
                  <Button onClick={() => runClcAdminReview('send_to_rag')} disabled={clcBusy}>Send to RAG</Button>{' '}
                  <Button onClick={() => runClcAdminReview('archive')} disabled={clcBusy}>Archive</Button>
                </div>
              )}

              {clcSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Planning cycle closed with status <strong>{clcSessionData.status}</strong>. No automatic action was taken.</p>
                </div>
              )}

              <h4>Cycle events</h4>
              <ul className="notice">
                {clcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!clcEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  )
}
