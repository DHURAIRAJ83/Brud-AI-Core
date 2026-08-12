import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const rcSubTabs = [
  'Overview', 'Provider Registry', 'Research Requests', 'Consensus', 'Evidence', 'Dataset Draft',
  'RAG Status', 'Training Status', 'Reports', 'History', 'Diagnostics',
]

export default function ResearchCenterTab({
  rcSubTab, setRcSubTab,
  rcDiag, rcSessionData,
  rcSessionsList, rcSelectedId, selectRcSession, submitRcCreateSession, rcNewTopic, setRcNewTopic, rcBusy,
  rcEventsList,
  rcProviders, toggleRcProviderStatus, submitRcAddProvider, rcNewProviderForm, setRcNewProviderForm,
  submitRcResearchRequest, rcPlanningCenterId, setRcPlanningCenterId,
  submitRcSelectMode, rcMode, setRcMode, rcProviderKeys, setRcProviderKeys,
  submitRcBuildLocalDraft, rcExistingDatasetId, setRcExistingDatasetId,
  runRcPrepareProviderRequestPackage,
  submitRcIngestProviderResults, rcProviderOutputs, setRcProviderOutputs,
  runRcBuildDatasetDraft,
  runRcAdminReviewDraft,
  submitRcRunRagEvaluation, rcRagForm, setRcRagForm, runRcFinalizeRagEvaluation,
  runRcAdminReviewRag,
  runRcCheckTrainingGate, rcTrainingReportMb06Id, setRcTrainingReportMb06Id, submitRcAnalyzeTrainingReport,
  runRcGenerateReport, rcReport,
  rcMemoryItems, submitRcRecordMemory, rcMemoryNotes, setRcMemoryNotes,
}) {
  return (
    <>
      <p className="notice">
        MB-10 -- AI Research &amp; Knowledge Acquisition Center. Admin-only: prepares research
        requests, compares multiple AI providers (never contacting any of them automatically --
        an admin runs them externally and pastes results back), builds evidence-backed dataset
        drafts, and sends only admin-approved knowledge to the RAG Sandbox and later the Learning
        Supervisor (MB-06). Nothing here starts training, deploys a model, activates a runtime, or
        writes/approves a dataset -- every irreversible step requires an explicit prior admin
        decision recorded on the session.
      </p>

      <div className="dataset-tabs">
        {rcSubTabs.map((t) => (
          <Button key={t} className={rcSubTab === t ? 'active' : ''} onClick={() => setRcSubTab(t)}>{t}</Button>
        ))}
      </div>

      {rcSubTab === 'Overview' && (
        <>
          {rcDiag && (
            <div className="notice">
              <p><strong>External providers called:</strong> {String(rcDiag.external_providers_called)} -- Brud AI has no Claude/OpenAI/Gemini/OpenRouter integration; provider outputs must be collected externally and supplied back.</p>
              <p><strong>RAG first policy:</strong> {rcDiag.rag_first_policy}</p>
            </div>
          )}
          {rcSessionData && (
            <section className="metric-grid">
              <StatusCard label="Topic" value={rcSessionData.topic} tone="neutral" />
              <StatusCard label="Mode" value={rcSessionData.mode ?? 'not selected'} tone="neutral" />
              <StatusCard label="Stage" value={rcSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={rcSessionData.status} tone={rcSessionData.status.includes('reject') ? 'waiting' : rcSessionData.status.startsWith('admin_') || rcSessionData.status === 'training_eligible' ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Research sessions</h4>
              <ul className="notice">
                {rcSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={rcSelectedId === s.public_id ? 'active' : ''} onClick={() => selectRcSession(s.public_id)}>
                      {s.topic} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!rcSessionsList.length && <li>No research sessions yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitRcCreateSession}>
                <label>Topic<input value={rcNewTopic} onChange={(e) => setRcNewTopic(e.target.value)} placeholder="e.g. Photosynthesis" /></label>
                <Button type="submit" disabled={rcBusy || !rcNewTopic.trim()}>{rcBusy ? 'Working…' : 'Start research session'}</Button>
              </form>
            </div>
            <div>
              {!rcSessionData && <div className="notice">Select or start a research session to work through its workflow in the other sub-tabs.</div>}
              {rcSessionData && (
                <>
                  <h4>Session events</h4>
                  <ul className="notice">
                    {rcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!rcEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {rcSubTab === 'Provider Registry' && (
        <>
          <p className="notice">Real, admin-extensible registry -- never a hardcoded provider list. Future providers are added here, not in code.</p>
          <ul className="notice">
            {rcProviders.map((p) => (
              <li key={p.provider_key}>
                <strong>{p.display_name}</strong> ({p.provider_key}) -- {p.status} -- {p.requires_external_call ? 'external call' : 'no external call'} -- {p.description}{' '}
                <Button onClick={() => toggleRcProviderStatus(p.provider_key, p.status)} disabled={rcBusy}>
                  {p.status === 'active' ? 'Deactivate' : 'Activate'}
                </Button>
              </li>
            ))}
            {!rcProviders.length && <li>No providers registered.</li>}
          </ul>
          <form className="inline-form training-form" onSubmit={submitRcAddProvider}>
            <label>Provider key<input value={rcNewProviderForm.provider_key} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, provider_key: e.target.value })} /></label>
            <label>Display name<input value={rcNewProviderForm.display_name} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, display_name: e.target.value })} /></label>
            <label>Description<input value={rcNewProviderForm.description} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, description: e.target.value })} /></label>
            <label>
              <input type="checkbox" checked={rcNewProviderForm.requires_external_call} onChange={(e) => setRcNewProviderForm({ ...rcNewProviderForm, requires_external_call: e.target.checked })} />
              {' '}Requires external call
            </label>
            <Button type="submit" disabled={rcBusy || !rcNewProviderForm.provider_key || !rcNewProviderForm.display_name}>Add provider</Button>
          </form>
        </>
      )}

      {rcSubTab === 'Research Requests' && (
        <>
          {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
          {rcSessionData && (
            <>
              {rcSessionData.stage === 'research_request' && (
                <div className="notice">
                  <p>Builds a set of research questions, folding in evidence from an already-completed MB-09 Planning Center cycle if one is supplied.</p>
                  <form className="inline-form training-form" onSubmit={submitRcResearchRequest}>
                    <label>MB-09 planning session public ID (optional)<input value={rcPlanningCenterId} onChange={(e) => setRcPlanningCenterId(e.target.value)} /></label>
                    <Button type="submit" disabled={rcBusy}>Prepare research request</Button>
                  </form>
                </div>
              )}
              {rcSessionData.stage === 'mode_selection' && (
                <div className="notice">
                  <p>Mode 1 (Local Draft): Mini Brain drafts from its own existing evidence, no provider contacted. Mode 2 (Multi-Provider Consensus): a package is prepared for the admin to run externally.</p>
                  <form className="inline-form training-form" onSubmit={submitRcSelectMode}>
                    <label>Mode
                      <select value={rcMode} onChange={(e) => setRcMode(e.target.value)}>
                        <option value="local_draft">Local Draft</option>
                        <option value="multi_provider">Multi-Provider Consensus</option>
                      </select>
                    </label>
                    {rcMode === 'multi_provider' && (
                      <label>Provider keys (comma separated)<input value={rcProviderKeys} onChange={(e) => setRcProviderKeys(e.target.value)} /></label>
                    )}
                    <Button type="submit" disabled={rcBusy}>Select mode</Button>
                  </form>
                </div>
              )}
              {rcSessionData.research_request?.questions && (
                <pre className="notice">{JSON.stringify(rcSessionData.research_request, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {rcSubTab === 'Consensus' && (
        <>
          {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
          {rcSessionData && (
            <>
              {rcSessionData.stage === 'local_draft' && (
                <div className="notice">
                  <p>Local Draft: uses Mini Brain's own existing evidence -- Knowledge Roadmap, Learning Queue, Dataset Intelligence, Continuous Learning History (read via MB-09, read-only).</p>
                  <form className="inline-form training-form" onSubmit={submitRcBuildLocalDraft}>
                    <label>Existing dataset source public ID (optional)<input value={rcExistingDatasetId} onChange={(e) => setRcExistingDatasetId(e.target.value)} /></label>
                    <Button type="submit" disabled={rcBusy}>Build local draft</Button>
                  </form>
                </div>
              )}
              {rcSessionData.stage === 'provider_request' && (
                <div className="notice">
                  <p>Prepares a Provider Request Package only -- Brud AI never calls a provider automatically. The admin runs these providers externally.</p>
                  <Button onClick={runRcPrepareProviderRequestPackage} disabled={rcBusy}>Prepare provider request package</Button>
                </div>
              )}
              {rcSessionData.provider_request?.status && (
                <pre className="notice">{JSON.stringify(rcSessionData.provider_request, null, 2)}</pre>
              )}
              {rcSessionData.stage === 'provider_consensus' && (
                <div className="notice">
                  <p>Once an admin has run the requested providers externally, paste their outputs here for duplicate/conflict detection and consensus.</p>
                  <form className="inline-form training-form" onSubmit={submitRcIngestProviderResults}>
                    {rcProviderOutputs.map((o, idx) => (
                      <label key={idx}>{o.provider} output
                        <input value={o.output_text} onChange={(e) => {
                          const next = [...rcProviderOutputs]; next[idx] = { ...next[idx], output_text: e.target.value }; setRcProviderOutputs(next)
                        }} />
                      </label>
                    ))}
                    <Button type="submit" disabled={rcBusy}>Ingest provider results</Button>
                  </form>
                </div>
              )}
              {rcSessionData.consensus_report?.verdict && (
                <pre className="notice">{JSON.stringify(rcSessionData.consensus_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {rcSubTab === 'Evidence' && (
        <>
          {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
          {rcSessionData && (
            <>
              <p className="notice">Citation Analyzer and Evidence Validator are rule-based heuristics only (URL/year/attribution markers, absolute-claim and hedging-word counts) -- never a fact-checker, never AI-generated judgment.</p>
              {rcSessionData.evidence_report?.per_provider ? (
                <pre className="notice">{JSON.stringify(rcSessionData.evidence_report, null, 2)}</pre>
              ) : <div className="notice">No evidence signals yet -- only produced for Multi-Provider Consensus mode after ingesting provider results.</div>}
              {rcSessionData.quality_report?.overall_quality !== undefined && (
                <>
                  <h4>Research Quality Score</h4>
                  <pre className="notice">{JSON.stringify(rcSessionData.quality_report, null, 2)}</pre>
                </>
              )}
            </>
          )}
        </>
      )}

      {rcSubTab === 'Dataset Draft' && (
        <>
          {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
          {rcSessionData && (
            <>
              {rcSessionData.stage === 'dataset_draft' && (
                <div className="notice">
                  <p>Assembles the draft only -- <code>verified: false</code>, needs admin review. MB-10 never creates a final dataset; Dataset Studio remains the only place that happens.</p>
                  <Button onClick={runRcBuildDatasetDraft} disabled={rcBusy}>Build dataset draft</Button>
                </div>
              )}
              {rcSessionData.recommendation_report?.recommendation && (
                <p className="notice">Recommended: <strong>{rcSessionData.recommendation_report.recommendation}</strong> -- {rcSessionData.recommendation_report.why}</p>
              )}
              {rcSessionData.dataset_draft?.status && (
                <pre className="notice">{JSON.stringify(rcSessionData.dataset_draft, null, 2)}</pre>
              )}
              {rcSessionData.stage === 'awaiting_draft_review' && (
                <div className="notice">
                  <p>Admin decision (accept, then send-to-RAG, is a two-step confirmation -- RAG FIRST POLICY):</p>
                  <Button onClick={() => runRcAdminReviewDraft('reject')} disabled={rcBusy}>Reject</Button>{' '}
                  <Button onClick={() => runRcAdminReviewDraft('edit')} disabled={rcBusy}>Edit</Button>{' '}
                  <Button onClick={() => runRcAdminReviewDraft('accept_draft')} disabled={rcBusy}>Accept Draft</Button>{' '}
                  <Button onClick={() => runRcAdminReviewDraft('request_more_research')} disabled={rcBusy}>Request More Research</Button>{' '}
                  <Button onClick={() => runRcAdminReviewDraft('request_different_providers')} disabled={rcBusy}>Request Different Providers</Button>{' '}
                  <Button onClick={() => runRcAdminReviewDraft('request_local_draft')} disabled={rcBusy}>Request Local Draft</Button>{' '}
                  <Button onClick={() => runRcAdminReviewDraft('send_to_rag')} disabled={rcBusy || rcSessionData.draft_admin_decision !== 'accept_draft'}>Send to RAG</Button>{' '}
                  <Button onClick={() => runRcAdminReviewDraft('archive')} disabled={rcBusy}>Archive</Button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {rcSubTab === 'RAG Status' && (
        <>
          {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
          {rcSessionData && (
            <>
              <p className="notice">RAG FIRST POLICY: every dataset draft passes through the existing RAG Sandbox (generation + evaluation + report, reusing MB-06's exact pattern) before a training gate can ever open. Corpus, index, and retrieval remain admin-driven through RAG Sandbox's own UI.</p>
              {rcSessionData.stage === 'rag_evaluation' && (
                <form className="inline-form training-form" onSubmit={submitRcRunRagEvaluation}>
                  <label>RAG Sandbox experiment public ID<input value={rcRagForm.rag_sandbox_experiment_public_id} onChange={(e) => setRcRagForm({ ...rcRagForm, rag_sandbox_experiment_public_id: e.target.value })} /></label>
                  <label>Retrieval run public ID<input value={rcRagForm.retrieval_run_public_id} onChange={(e) => setRcRagForm({ ...rcRagForm, retrieval_run_public_id: e.target.value })} /></label>
                  <label>Generation assignment public ID<input value={rcRagForm.generation_assignment_public_id} onChange={(e) => setRcRagForm({ ...rcRagForm, generation_assignment_public_id: e.target.value })} /></label>
                  <Button type="submit" disabled={rcBusy}>Run RAG generation + evaluation</Button>
                  <Button type="button" onClick={runRcFinalizeRagEvaluation} disabled={rcBusy}>Finalize report (retry after human review)</Button>
                </form>
              )}
              {rcSessionData.rag_report && Object.keys(rcSessionData.rag_report).length > 0 && (
                <pre className="notice">{JSON.stringify(rcSessionData.rag_report, null, 2)}</pre>
              )}
              {rcSessionData.stage === 'awaiting_rag_review' && (
                <div className="notice">
                  <Button onClick={() => runRcAdminReviewRag('approve')} disabled={rcBusy}>Approve</Button>{' '}
                  <Button onClick={() => runRcAdminReviewRag('reject')} disabled={rcBusy}>Reject</Button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {rcSubTab === 'Training Status' && (
        <>
          {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
          {rcSessionData && (
            <>
              <p className="notice">Eligibility check only -- never a training trigger. Training Engine only accepts admin-approved + RAG-approved datasets, and only ever starts through MB-06's own UI.</p>
              {rcSessionData.stage === 'training_gate' && (
                <Button onClick={runRcCheckTrainingGate} disabled={rcBusy}>Check training gate</Button>
              )}
              {rcSessionData.training_gate_report && Object.keys(rcSessionData.training_gate_report).length > 0 && (
                <pre className="notice">{JSON.stringify(rcSessionData.training_gate_report, null, 2)}</pre>
              )}
              {rcSessionData.training_gate_report?.eligible && (
                <form className="inline-form training-form" onSubmit={submitRcAnalyzeTrainingReport}>
                  <label>MB-06 Learning Supervisor session public ID (once training has completed there)<input value={rcTrainingReportMb06Id} onChange={(e) => setRcTrainingReportMb06Id(e.target.value)} /></label>
                  <Button type="submit" disabled={rcBusy}>Analyze training report (read-only)</Button>
                </form>
              )}
            </>
          )}
        </>
      )}

      {rcSubTab === 'Reports' && (
        <>
          {!rcSessionData && <div className="notice">Select a research session in Overview first.</div>}
          {rcSessionData && (
            <>
              <p className="notice">Assembled on demand from fields already on the session -- pure merge, nothing recomputed, nothing stored separately.</p>
              <Button onClick={runRcGenerateReport} disabled={rcBusy}>Generate research report</Button>
              {rcReport && <pre className="notice">{JSON.stringify(rcReport, null, 2)}</pre>}
            </>
          )}
        </>
      )}

      {rcSubTab === 'History' && (
        <>
          <h4>Learning Memory (permanent, insert-only)</h4>
          <div className="notice">
            <ul>
              {rcMemoryItems.map((m) => (
                <li key={m.public_id}>{m.created_at} -- session {m.research_session_public_id.slice(0, 8)} -- decision: {m.admin_decision ?? 'n/a'} -- {m.notes}</li>
              ))}
              {!rcMemoryItems.length && <li>No memory entries recorded yet.</li>}
            </ul>
            {rcSessionData && (
              <form className="inline-form training-form" onSubmit={submitRcRecordMemory}>
                <label>Notes<input value={rcMemoryNotes} onChange={(e) => setRcMemoryNotes(e.target.value)} /></label>
                <Button type="submit" disabled={rcBusy}>Record memory snapshot for selected session</Button>
              </form>
            )}
          </div>
          {rcSessionData && (
            <>
              <h4>Selected session events</h4>
              <ul className="notice">
                {rcEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                {!rcEventsList.length && <li>No events yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {rcSubTab === 'Diagnostics' && (
        <>
          {rcDiag && <pre className="notice">{JSON.stringify(rcDiag, null, 2)}</pre>}
          {!rcDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
