import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

export default function ContinuousLearningTab({
  clDiagnostics,
  clSessions, clSelectedId, selectClSession,
  submitClCreateSession, clCycleWindowDays, setClCycleWindowDays, clBusy,
  clSession,
  runClCollectFeedback,
  runClAnalyzeFailures,
  runClAnalyzeHallucinations,
  runClAnalyzeKnowledgeGaps,
  runClDetectWeakTopics,
  runClAnalyzeDifficulty,
  runClRecommendDatasets,
  runClRecommendTraining,
  runClRankPriorities,
  runClGenerateReport,
  runClAdminReview,
  clEvents,
}) {
  return (
    <>
      <p className="notice">
        MB-08 -- Continuous Learning &amp; Feedback Engine. Advisory only: observes real Public
        Chat routing/feedback evidence and the Knowledge Gap Registry, analyzes weaknesses, and
        prepares a report for admin approval. Never retrains, never edits a dataset, never
        modifies a checkpoint, never activates a model. Approving a report records the admin's
        judgment only -- nothing here automatically starts MB-06 or MB-07; an admin acts on the
        recommendations manually, through those phases' own UIs.
      </p>
      {clDiagnostics && (
        <div className="notice">
          <p><strong>Pipeline stages:</strong> {clDiagnostics.pipeline_stages.join(' -> ')}</p>
          <p><strong>Writes:</strong> {clDiagnostics.writes_scope}</p>
        </div>
      )}

      <div className="training-grid">
        <div>
          <h4>Learning cycles</h4>
          <ul className="notice">
            {clSessions.map((s) => (
              <li key={s.public_id}>
                <Button className={clSelectedId === s.public_id ? 'active' : ''} onClick={() => selectClSession(s.public_id)}>
                  {s.public_id.slice(0, 8)} -- {s.stage} ({s.status})
                </Button>
              </li>
            ))}
            {!clSessions.length && <li>No learning cycles yet.</li>}
          </ul>

          <h4>New learning cycle</h4>
          <form className="inline-form training-form" onSubmit={submitClCreateSession}>
            <label>Cycle window (days, intent only -- see diagnostics)<input type="number" min="1" max="365" value={clCycleWindowDays} onChange={(e) => setClCycleWindowDays(Number(e.target.value))} /></label>
            <Button type="submit" disabled={clBusy}>{clBusy ? 'Working…' : 'Start learning cycle'}</Button>
          </form>
        </div>

        <div>
          {!clSession && <div className="notice">Select or start a learning cycle to see its workflow.</div>}

          {clSession && (
            <>
              <section className="metric-grid">
                <StatusCard label="Stage" value={clSession.stage} tone="neutral" />
                <StatusCard label="Status" value={clSession.status} tone={clSession.status === 'admin_approved' ? 'good' : clSession.status === 'admin_rejected' ? 'waiting' : 'neutral'} />
                <StatusCard label="Overall health" value={clSession.continuous_learning_report?.overall_health ?? 'not yet assessed'} tone={clSession.continuous_learning_report?.overall_health === 'Healthy' ? 'good' : clSession.continuous_learning_report?.overall_health === 'At Risk' ? 'waiting' : 'neutral'} />
                <StatusCard label="Admin decision" value={clSession.admin_decision ?? 'pending'} tone={clSession.admin_decision === 'approve' ? 'good' : 'neutral'} />
              </section>

              {clSession.stage === 'feedback_collection' && (
                <div className="notice">
                  <p>Stage 1: collect real Public Chat routing + feedback evidence (approved logs only -- no raw text is ever read).</p>
                  <Button onClick={runClCollectFeedback} disabled={clBusy}>Collect feedback</Button>
                </div>
              )}
              {clSession.feedback_report?.total_conversations_observed !== undefined && (
                <pre className="notice">{JSON.stringify(clSession.feedback_report, null, 2)}</pre>
              )}

              {clSession.stage === 'failure_analysis' && (
                <div className="notice">
                  <p>Stage 2: classify failures -- no answer, blocked, timeout, low confidence, wrong answer.</p>
                  <Button onClick={runClAnalyzeFailures} disabled={clBusy}>Analyze failures</Button>
                </div>
              )}

              {clSession.stage === 'hallucination_analysis' && (
                <div className="notice">
                  <p>Stage 3: hallucination signal from the routing pipeline's own real evidence_status field.</p>
                  <Button onClick={runClAnalyzeHallucinations} disabled={clBusy}>Analyze hallucinations</Button>
                </div>
              )}

              {clSession.stage === 'knowledge_gap_analysis' && (
                <div className="notice">
                  <p>Stage 4: aggregate the existing Knowledge Gap Registry's own cases -- read-only, never writes back to it.</p>
                  <Button onClick={runClAnalyzeKnowledgeGaps} disabled={clBusy}>Analyze knowledge gaps</Button>
                </div>
              )}

              {clSession.stage === 'weak_topic_detection' && (
                <div className="notice">
                  <p>Stage 5: rank domains by a disclosed weakness index (no true per-domain accuracy % is measurable from real data today).</p>
                  <Button onClick={runClDetectWeakTopics} disabled={clBusy}>Detect weak topics</Button>
                </div>
              )}
              {clSession.weak_topic_report?.topics && (
                <pre className="notice">{JSON.stringify(clSession.weak_topic_report.topics, null, 2)}</pre>
              )}

              {clSession.stage === 'difficulty_analysis' && (
                <div className="notice">
                  <p>Stage 6: Easy/Medium/Hard/Expert/Unknown, reusing MB-05.1's difficulty scoring unchanged.</p>
                  <Button onClick={runClAnalyzeDifficulty} disabled={clBusy}>Analyze difficulty</Button>
                </div>
              )}

              {clSession.stage === 'dataset_recommendation' && (
                <div className="notice">
                  <p>Stage 7: recommend dataset formats per weak domain, each with a WHY.</p>
                  <Button onClick={runClRecommendDatasets} disabled={clBusy}>Recommend datasets</Button>
                </div>
              )}

              {clSession.stage === 'training_recommendation' && (
                <div className="notice">
                  <p>Stage 8: No Training / Fine Tune / Continue Training / Full Retraining, with WHY.</p>
                  <Button onClick={runClRecommendTraining} disabled={clBusy}>Recommend training action</Button>
                </div>
              )}

              {clSession.stage === 'priority_ranking' && !clSession.continuous_learning_report?.overall_health && (
                <div className="notice">
                  <p>Stage 9: rank recommendations using the Knowledge Gap Registry's own real priority scores.</p>
                  <Button onClick={runClRankPriorities} disabled={clBusy}>Rank priorities</Button>
                </div>
              )}
              {clSession.stage === 'priority_ranking' && clSession.priority_report?.training_recommendation && (
                <div className="notice">
                  <p>Stage 10: assemble the final Continuous Learning Report.</p>
                  <Button onClick={runClGenerateReport} disabled={clBusy}>Generate report</Button>
                </div>
              )}

              {clSession.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Admin reviews the full Continuous Learning Report and decides.</p>
                  <pre className="notice">{JSON.stringify(clSession.continuous_learning_report, null, 2)}</pre>
                  <Button onClick={() => runClAdminReview('reject')} disabled={clBusy}>Reject</Button>{' '}
                  <Button onClick={() => runClAdminReview('approve')} disabled={clBusy}>Approve</Button>
                </div>
              )}

              {clSession.stage === 'closed' && (
                <div className="notice">
                  <p>Cycle closed with status <strong>{clSession.status}</strong>. No automatic action was taken.</p>
                </div>
              )}

              <h4>Cycle events</h4>
              <ul className="notice">
                {clEvents.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!clEvents.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  )
}
