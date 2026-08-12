import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const gaSubTabs = [
  'Overview', 'Authorization', 'Providers', 'Sanitization', 'Public Evaluation', 'Data Acquisition',
  'Provider Responses', 'Agreement', 'Evidence', 'Report', 'History', 'Diagnostics',
]

export default function ExternalAIGatewayTab({
  gaSubTab, setGaSubTab,
  gaDiag, gaSessionData,
  gaSessionsList, gaSelectedId, selectGaSession, submitGaCreateSession,
  gaNewTopic, setGaNewTopic, gaNewPurpose, setGaNewPurpose, gaNewDatasetIds, setGaNewDatasetIds, gaNewRagId, setGaNewRagId,
  gaBusy,
  gaEventsList,
  submitGaAuthorize, gaAuthorizationNote, setGaAuthorizationNote,
  submitGaSelectProviders, gaProviderKeys, setGaProviderKeys,
  runGaDispatch,
  submitGaSanitize, gaAdminStatedNeed, setGaAdminStatedNeed,
  runGaAction, gaSanitize,
  runGaCollect,
  runGaNormalize, gaProviderRunsList,
  runGaAnalyze,
  runGaBuildEvidence,
  runGaGenerateReport,
  runGaAdminReview,
  runGaArchive,
  gaMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-21 -- External AI Evaluation Gateway. External AI providers are used strictly as
        evaluation assistants, never as autonomous decision-makers. This phase never trains a
        model, modifies weights, starts a runtime, deploys, approves a dataset, approves a
        release, or writes into Dataset Studio or Document Workspace. Every provider output
        remains untrusted candidate evidence until a human admin reviews it.
      </p>

      <div className="dataset-tabs">
        {gaSubTabs.map((t) => (
          <Button key={t} className={gaSubTab === t ? 'active' : ''} onClick={() => setGaSubTab(t)}>{t}</Button>
        ))}
      </div>

      {gaSubTab === 'Overview' && (
        <>
          {gaDiag && (
            <div className="notice">
              <p><strong>Model deployed:</strong> {String(gaDiag.model_deployed)} -- <strong>Shell commands executed:</strong> {String(gaDiag.shell_commands_executed)} -- <strong>Provider calls require authorization:</strong> {String(gaDiag.provider_calls_require_authorization)}</p>
              <p><strong>External AI output treated as:</strong> {gaDiag.external_ai_output_treated_as} -- <strong>Automatic approval:</strong> {String(gaDiag.automatic_approval)}</p>
            </div>
          )}
          {gaSessionData && (
            <section className="metric-grid">
              <StatusCard label="Topic" value={gaSessionData.topic.slice(0, 24)} tone="neutral" />
              <StatusCard label="Purpose" value={gaSessionData.purpose} tone="neutral" />
              <StatusCard label="Stage" value={gaSessionData.stage} tone="neutral" />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>External AI gateway sessions</h4>
              <ul className="notice">
                {gaSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={gaSelectedId === s.public_id ? 'active' : ''} onClick={() => selectGaSession(s.public_id)}>
                      {s.topic.slice(0, 26)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!gaSessionsList.length && <li>No external AI gateway sessions yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitGaCreateSession}>
                <label>Topic<input value={gaNewTopic} onChange={(e) => setGaNewTopic(e.target.value)} placeholder="Mountain scene public evaluation" /></label>
                <label>Purpose
                  <select value={gaNewPurpose} onChange={(e) => setGaNewPurpose(e.target.value)}>
                    <option value="public_style_stress_test">public_style_stress_test</option>
                    <option value="data_acquisition_assistance">data_acquisition_assistance</option>
                  </select>
                </label>
                <label>MB-16 dataset session public ID(s), comma-separated, optional<input value={gaNewDatasetIds} onChange={(e) => setGaNewDatasetIds(e.target.value)} /></label>
                <label>MB-17 RAG session public ID, optional<input value={gaNewRagId} onChange={(e) => setGaNewRagId(e.target.value)} /></label>
                <Button type="submit" disabled={gaBusy || !gaNewTopic.trim()}>{gaBusy ? 'Working…' : 'Create session'}</Button>
              </form>
            </div>
            <div>
              {!gaSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
              {gaSessionData && (
                <>
                  <h4>Session events</h4>
                  <ul className="notice">
                    {gaEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!gaEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {gaSubTab === 'Authorization' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && (
            <>
              {gaSessionData.stage === 'validate_authorization' && (
                <form className="inline-form training-form" onSubmit={submitGaAuthorize}>
                  <label>Explicit authorization reason (required before any provider is ever called)
                    <input value={gaAuthorizationNote} onChange={(e) => setGaAuthorizationNote(e.target.value)} placeholder="testing public-style stress evaluation for release readiness" />
                  </label>
                  <Button type="submit" disabled={gaBusy || !gaAuthorizationNote.trim()}>Authorize</Button>
                </form>
              )}
              {gaSessionData.authorization_report?.authorized !== undefined && (
                <pre className="notice">{JSON.stringify(gaSessionData.authorization_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {gaSubTab === 'Providers' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && (
            <>
              {gaSessionData.stage === 'select_providers' && (
                <form className="inline-form training-form" onSubmit={submitGaSelectProviders}>
                  <label>Requested provider key(s), comma-separated<input value={gaProviderKeys} onChange={(e) => setGaProviderKeys(e.target.value)} /></label>
                  <Button type="submit" disabled={gaBusy || !gaProviderKeys.trim()}>Select providers</Button>
                </form>
              )}
              {gaSessionData.provider_selection_report?.selected_count !== undefined && (
                <pre className="notice">{JSON.stringify(gaSessionData.provider_selection_report, null, 2)}</pre>
              )}
              {gaSessionData.stage === 'dispatch_requests' && (
                <div className="notice">
                  <p>Dispatches the sanitized prompt to every selected provider. The full raw prompt is never persisted -- only its SHA-256 hash.</p>
                  <Button onClick={runGaDispatch} disabled={gaBusy}>Dispatch provider requests</Button>
                </div>
              )}
              {gaSessionData.dispatch_report?.dispatched_count !== undefined && (
                <pre className="notice">{JSON.stringify(gaSessionData.dispatch_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {gaSubTab === 'Sanitization' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && (
            <>
              {gaSessionData.stage === 'sanitize_inputs' && gaSessionData.purpose === 'data_acquisition_assistance' && (
                <form className="inline-form training-form" onSubmit={submitGaSanitize}>
                  <label>What data is missing? (admin-stated need)<input value={gaAdminStatedNeed} onChange={(e) => setGaAdminStatedNeed(e.target.value)} /></label>
                  <Button type="submit" disabled={gaBusy || !gaAdminStatedNeed.trim()}>Sanitize &amp; continue</Button>
                </form>
              )}
              {gaSessionData.stage === 'sanitize_inputs' && gaSessionData.purpose === 'public_style_stress_test' && (
                <div className="notice">
                  <p>Builds sanitized context from the session's own topic plus any linked MB-16/MB-17 sessions.</p>
                  <Button onClick={() => runGaAction(() => gaSanitize(gaSelectedId, ''))} disabled={gaBusy}>Sanitize inputs</Button>
                </div>
              )}
              {gaSessionData.sanitization_report?.privacy_audit && (
                <pre className="notice">{JSON.stringify(gaSessionData.sanitization_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {gaSubTab === 'Public Evaluation' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && gaSessionData.purpose !== 'public_style_stress_test' && (
            <div className="notice">This session's purpose is {gaSessionData.purpose}, not public_style_stress_test.</div>
          )}
          {gaSessionData && gaSessionData.purpose === 'public_style_stress_test' && gaSessionData.evidence_bundle?.recommendations && (
            <pre className="notice">{JSON.stringify(gaSessionData.evidence_bundle.recommendations, null, 2)}</pre>
          )}
          {gaSessionData && gaSessionData.purpose === 'public_style_stress_test' && !gaSessionData.evidence_bundle?.recommendations && (
            <div className="notice">Build the evidence bundle in the Evidence tab first.</div>
          )}
        </>
      )}

      {gaSubTab === 'Data Acquisition' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && gaSessionData.purpose !== 'data_acquisition_assistance' && (
            <div className="notice">This session's purpose is {gaSessionData.purpose}, not data_acquisition_assistance.</div>
          )}
          {gaSessionData && gaSessionData.purpose === 'data_acquisition_assistance' && gaSessionData.evidence_bundle?.recommendations && (
            <>
              <p className="notice">Unverified candidate data only -- never inserted into Dataset Studio automatically.</p>
              <pre className="notice">{JSON.stringify(gaSessionData.evidence_bundle.recommendations, null, 2)}</pre>
            </>
          )}
          {gaSessionData && gaSessionData.purpose === 'data_acquisition_assistance' && !gaSessionData.evidence_bundle?.recommendations && (
            <div className="notice">Build the evidence bundle in the Evidence tab first.</div>
          )}
        </>
      )}

      {gaSubTab === 'Provider Responses' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && (
            <>
              {gaSessionData.stage === 'collect_responses' && (
                <div className="notice">
                  <Button onClick={runGaCollect} disabled={gaBusy}>Collect provider responses</Button>
                </div>
              )}
              {gaSessionData.stage === 'normalize_responses' && (
                <div className="notice">
                  <Button onClick={runGaNormalize} disabled={gaBusy}>Normalize responses</Button>
                </div>
              )}
              <h4>Provider runs ({gaProviderRunsList.length})</h4>
              <ul className="notice">
                {gaProviderRunsList.map((r) => (
                  <li key={r.public_id}><span className={`pill ${r.status === 'success' ? 'good' : 'block'}`}>{r.status}</span> {r.provider_key} -- {r.latency_ms}ms{r.error_message ? ` -- ${r.error_message}` : ''}</li>
                ))}
                {!gaProviderRunsList.length && <li>No provider runs yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {gaSubTab === 'Agreement' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && (
            <>
              {gaSessionData.stage === 'analyze_agreement' && (
                <div className="notice">
                  <p>No majority voting here ever produces an automatic truth decision.</p>
                  <Button onClick={runGaAnalyze} disabled={gaBusy}>Analyze agreement &amp; failures</Button>
                </div>
              )}
              {gaSessionData.agreement_report?.agreement && (
                <pre className="notice">{JSON.stringify(gaSessionData.agreement_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {gaSubTab === 'Evidence' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && (
            <>
              {gaSessionData.stage === 'build_evidence' && (
                <div className="notice">
                  <p>Only hashes of raw provider text are included by default.</p>
                  <Button onClick={runGaBuildEvidence} disabled={gaBusy}>Build evidence bundle</Button>
                </div>
              )}
              {gaSessionData.evidence_bundle?.provider_metadata && (
                <pre className="notice">{JSON.stringify(gaSessionData.evidence_bundle, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {gaSubTab === 'Report' && (
        <>
          {!gaSessionData && <div className="notice">Select a session in Overview first.</div>}
          {gaSessionData && (
            <>
              {gaSessionData.stage === 'generate_report' && (
                <div className="notice">
                  <Button onClick={runGaGenerateReport} disabled={gaBusy}>Generate evaluation report</Button>
                </div>
              )}
              {gaSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Every provider output above is unverified candidate evidence. No dataset, release,
                  or training decision is made by this review.</p>
                  <p><strong>Confidence:</strong> <span className="pill neutral">{gaSessionData.gateway_report.confidence_level}</span></p>
                  <pre className="notice">{JSON.stringify(gaSessionData.gateway_report, null, 2)}</pre>

                  <h4>Final decision (marks this evaluation session's own findings only)</h4>
                  <Button onClick={() => runGaAdminReview('accept')} disabled={gaBusy}>Accept</Button>{' '}
                  <Button onClick={() => runGaAdminReview('reject')} disabled={gaBusy}>Reject</Button>{' '}
                  <Button onClick={() => runGaAdminReview('needs_followup')} disabled={gaBusy}>Needs Follow-up</Button>
                </div>
              )}
              {gaSessionData.stage === 'reviewed' && (
                <div className="notice">
                  <p>Reviewed with status <strong>{gaSessionData.status}</strong>.</p>
                  <Button onClick={runGaArchive} disabled={gaBusy}>Archive session</Button>
                </div>
              )}
              {gaSessionData.stage === 'archived' && (
                <div className="notice">Session archived.</div>
              )}

              <h4>External AI memory (permanent)</h4>
              <ul className="notice">
                {gaMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- agreement {m.agreement_score}</li>
                ))}
                {!gaMemoryList.length && <li>No external AI memory recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {gaSubTab === 'History' && gaSessionData && (
        <>
          <h4>Session events</h4>
          <ul className="notice">
            {gaEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!gaEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {gaSubTab === 'History' && !gaSessionData && (
        <div className="notice">Select a session in Overview first.</div>
      )}

      {gaSubTab === 'Diagnostics' && (
        <>
          {gaDiag && <pre className="notice">{JSON.stringify(gaDiag, null, 2)}</pre>}
          {!gaDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
