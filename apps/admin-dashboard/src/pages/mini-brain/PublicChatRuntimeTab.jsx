import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const pcrSubTabs = [
  'Overview', 'Live Sessions', 'Conversations', 'Analytics', 'Feedback Signals', 'Failure Clusters',
  'Improvement Queue', 'Candidate Review', 'Admin Handoffs', 'Exports', 'Runtime Diagnostics',
  'Safety Monitor', 'History',
]

export default function PublicChatRuntimeTab({
  pcrSubTab, setPcrSubTab,
  pcrAnalyticsData, pcrCandidatesList, pcrDiag,
  pcrSessionsList, pcrSelectedSessionId, selectPcrSession, pcrSessionData,
  pcrMessagesList,
  pcrSignalsList,
  pcrClustersList,
  submitPcrGenerateCandidates, pcrMinFrequency, setPcrMinFrequency, pcrBusy,
  pcrSelectedCandidateId, selectPcrCandidate,
  pcrCandidateData, pcrReviewNotes, setPcrReviewNotes, submitPcrReview, pcrCandidateEventsList,
  pcrApprovedCandidatesList,
  runPcrExportAnalytics, runPcrExportCandidates, pcrExportResult,
}) {
  return (
    <>
      <p className="notice">
        MB-23 -- Public Chat Runtime &amp; Self-Improvement Feedback Loop. Every real answer is
        produced by the existing public chat router -- this phase only observes its already-
        computed signals to detect knowledge gaps, cluster repeated failures, and queue advisory
        improvement candidates. No raw message text is ever stored, only content hashes and
        already-sanitized signal text. Every candidate is born pending admin review and can only
        leave that status through an explicit review here -- nothing here starts MB-22 training,
        approves an MB-16/17/18/19/20 record, or dispatches an MB-21 provider.
      </p>

      <div className="dataset-tabs">
        {pcrSubTabs.map((t) => (
          <Button key={t} className={pcrSubTab === t ? 'active' : ''} onClick={() => setPcrSubTab(t)}>{t}</Button>
        ))}
      </div>

      {pcrSubTab === 'Overview' && (
        <>
          {pcrAnalyticsData && (
            <section className="metric-grid">
              <StatusCard label="Total sessions" value={pcrAnalyticsData.total_sessions} tone="neutral" />
              <StatusCard label="Total messages" value={pcrAnalyticsData.total_messages} tone="neutral" />
              <StatusCard label="Pending candidates" value={pcrCandidatesList.length} tone="neutral" />
            </section>
          )}
          {pcrDiag && (
            <div className="notice">
              <p><strong>Candidates require admin review:</strong> {String(pcrDiag.candidates_require_admin_review)} -- <strong>Automatic learning performed:</strong> {String(pcrDiag.automatic_learning_performed)} -- <strong>Automatic training performed:</strong> {String(pcrDiag.automatic_training_performed)}</p>
              <p><strong>Raw message content stored:</strong> {String(pcrDiag.raw_message_content_stored)} -- <strong>Raw personal data stored:</strong> {String(pcrDiag.raw_personal_data_stored)}</p>
            </div>
          )}
        </>
      )}

      {pcrSubTab === 'Live Sessions' && (
        <div className="training-grid">
          <div>
            <h4>Active sessions</h4>
            <ul className="notice">
              {pcrSessionsList.map((s) => (
                <li key={s.public_id}>
                  <Button className={pcrSelectedSessionId === s.public_id ? 'active' : ''} onClick={() => selectPcrSession(s.public_id)}>
                    {s.public_id.slice(0, 8)}… -- {s.language} -- {s.message_count} msg(s) -- {s.unresolved_count} unresolved -- {s.started_at}
                  </Button>
                </li>
              ))}
              {!pcrSessionsList.length && <li>No active sessions.</li>}
            </ul>
          </div>
          <div>
            {!pcrSessionData && <div className="notice">Select a session to inspect it.</div>}
            {pcrSessionData && <pre className="notice">{JSON.stringify(pcrSessionData, null, 2)}</pre>}
          </div>
        </div>
      )}

      {pcrSubTab === 'Conversations' && (
        <>
          {!pcrSessionData && <div className="notice">Select a session in Live Sessions first.</div>}
          {pcrSessionData && (
            <>
              <p className="notice">No raw message text is stored -- only a content hash and derived flags per turn.</p>
              <ul className="notice">
                {pcrMessagesList.map((m) => (
                  <li key={m.public_id}>
                    {m.role} -- hash {m.content_hash.slice(0, 12)}… -- rag={String(m.used_rag)} vision={String(m.used_vision)} tool={String(m.used_tool)} -- route={m.route_used || 'n/a'} -- {m.created_at}
                  </li>
                ))}
                {!pcrMessagesList.length && <li>No messages yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {pcrSubTab === 'Analytics' && (
        <>
          {pcrAnalyticsData && <pre className="notice">{JSON.stringify(pcrAnalyticsData, null, 2)}</pre>}
          {!pcrAnalyticsData && <Skeleton lines={2} />}
        </>
      )}

      {pcrSubTab === 'Feedback Signals' && (
        <>
          {!pcrSessionData && <div className="notice">Select a session in Live Sessions first.</div>}
          {pcrSessionData && (
            <ul className="notice">
              {pcrSignalsList.map((s) => (
                <li key={s.public_id}>{s.signal_type} -- {s.severity} -- "{s.normalized_text.slice(0, 60)}" -- topic: {s.topic_key} -- {s.created_at}</li>
              ))}
              {!pcrSignalsList.length && <li>No feedback signals recorded for this session.</li>}
            </ul>
          )}
        </>
      )}

      {pcrSubTab === 'Failure Clusters' && (
        <ul className="notice">
          {pcrClustersList.map((c) => (
            <li key={c.topic_key}>
              <strong>{c.topic_key}</strong> -- frequency {c.frequency} -- {c.distinct_session_count} session(s) --
              severity {JSON.stringify(c.severity_counts)} -- types {JSON.stringify(c.signal_type_counts)} -- most recent {c.most_recent_at}
            </li>
          ))}
          {!pcrClustersList.length && <li>No repeated failure clusters yet.</li>}
        </ul>
      )}

      {pcrSubTab === 'Improvement Queue' && (
        <>
          <form className="inline-form training-form" onSubmit={submitPcrGenerateCandidates}>
            <label>Minimum cluster frequency
              <input type="number" min="1" value={pcrMinFrequency} onChange={(e) => setPcrMinFrequency(e.target.value)} />
            </label>
            <Button type="submit" disabled={pcrBusy}>{pcrBusy ? 'Working…' : 'Generate candidates from clusters'}</Button>
          </form>
          <ul className="notice">
            {pcrCandidatesList.map((c) => (
              <li key={c.public_id}>
                <Button className={pcrSelectedCandidateId === c.public_id ? 'active' : ''} onClick={() => selectPcrCandidate(c.public_id)}>
                  {c.topic.slice(0, 30)} -- frequency {c.frequency} -- priority {c.priority_score} -- {c.recommended_action} -- {c.status}
                </Button>
              </li>
            ))}
            {!pcrCandidatesList.length && <li>No candidates pending review.</li>}
          </ul>
        </>
      )}

      {pcrSubTab === 'Candidate Review' && (
        <>
          {!pcrCandidateData && <div className="notice">Select a candidate in Improvement Queue first.</div>}
          {pcrCandidateData && (
            <>
              <pre className="notice">{JSON.stringify(pcrCandidateData, null, 2)}</pre>
              {pcrCandidateData.status === 'pending_admin_review' && (
                <div className="notice">
                  <label>Review notes<input value={pcrReviewNotes} onChange={(e) => setPcrReviewNotes(e.target.value)} placeholder="optional notes" /></label>
                  <Button onClick={() => submitPcrReview('approve')} disabled={pcrBusy}>Approve</Button>
                  <Button onClick={() => submitPcrReview('reject')} disabled={pcrBusy}>Reject</Button>
                </div>
              )}
              {pcrCandidateData.status !== 'pending_admin_review' && (
                <div className="notice">This candidate was already reviewed: {pcrCandidateData.status}.</div>
              )}
              <h4>Candidate events</h4>
              <ul className="notice">
                {pcrCandidateEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!pcrCandidateEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {pcrSubTab === 'Admin Handoffs' && (
        <>
          <p className="notice">Advisory only -- approving a candidate here never creates, starts, or approves anything in MB-13/16/18/21/22; an admin must act on it manually through those phases' own workflows.</p>
          <ul className="notice">
            {pcrApprovedCandidatesList.map((c) => (
              <li key={c.public_id}>
                <strong>{c.topic}</strong> -- {c.handoff_report?.recommended_next_phase || 'n/a'}
                <br />{c.handoff_report?.candidate_summary}
                {c.handoff_report?.example_anonymized_questions?.length > 0 && (
                  <ul>
                    {c.handoff_report.example_anonymized_questions.map((q, i) => <li key={i}>{q}</li>)}
                  </ul>
                )}
              </li>
            ))}
            {!pcrApprovedCandidatesList.length && <li>No approved candidates yet.</li>}
          </ul>
        </>
      )}

      {pcrSubTab === 'Exports' && (
        <>
          <div className="notice">
            <Button onClick={runPcrExportAnalytics} disabled={pcrBusy}>Export analytics</Button>
            <Button onClick={runPcrExportCandidates} disabled={pcrBusy}>Export candidates</Button>
          </div>
          {pcrExportResult && <pre className="notice">{JSON.stringify(pcrExportResult, null, 2)}</pre>}
        </>
      )}

      {pcrSubTab === 'Runtime Diagnostics' && (
        <>
          {pcrDiag && <pre className="notice">{JSON.stringify(pcrDiag, null, 2)}</pre>}
          {!pcrDiag && <Skeleton lines={2} />}
        </>
      )}

      {pcrSubTab === 'Safety Monitor' && (
        <>
          {pcrDiag && (
            <ul className="notice">
              <li>MB-22 training started or finalized: {String(pcrDiag.mb22_training_started_or_finalized)}</li>
              <li>MB-16 dataset approvals performed: {String(pcrDiag.mb16_dataset_approvals_performed)}</li>
              <li>MB-17 grounded answer approvals performed: {String(pcrDiag.mb17_grounded_answer_approvals_performed)}</li>
              <li>MB-18 package approvals performed: {String(pcrDiag.mb18_package_approvals_performed)}</li>
              <li>MB-19 evaluation approvals performed: {String(pcrDiag.mb19_evaluation_approvals_performed)}</li>
              <li>MB-20 release approvals performed: {String(pcrDiag.mb20_release_approvals_performed)}</li>
              <li>MB-21 provider dispatch performed: {String(pcrDiag.mb21_provider_dispatch_performed)}</li>
              <li>Models deployed: {String(pcrDiag.models_deployed)}</li>
              <li>Production models changed: {String(pcrDiag.production_models_changed)}</li>
              <li>Shell commands executed: {String(pcrDiag.shell_commands_executed)}</li>
            </ul>
          )}
          <h4>Safety-flagged signals in current session</h4>
          <ul className="notice">
            {pcrSignalsList.filter((s) => s.signal_type === 'safety_flag').map((s) => (
              <li key={s.public_id}>{s.created_at} -- {s.severity} -- {s.normalized_text.slice(0, 60)}</li>
            ))}
            {!pcrSignalsList.some((s) => s.signal_type === 'safety_flag') && <li>No safety-flag signals in the selected session.</li>}
          </ul>
        </>
      )}

      {pcrSubTab === 'History' && (
        <>
          <h4>Recently reviewed candidates</h4>
          <ul className="notice">
            {pcrApprovedCandidatesList.map((c) => (
              <li key={c.public_id}>{c.reviewed_at} -- {c.topic.slice(0, 30)} -- {c.status} -- reviewed by {c.reviewed_by_admin_public_id}</li>
            ))}
            {!pcrApprovedCandidatesList.length && <li>No reviewed candidates yet.</li>}
          </ul>
        </>
      )}
    </>
  )
}
