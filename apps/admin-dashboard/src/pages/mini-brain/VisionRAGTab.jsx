import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const vrSubTabs = [
  'Overview', 'Query', 'Results', 'Evidence', 'Images', 'OCR', 'Objects', 'Graph', 'Quality',
  'Hallucinations', 'History', 'Reports', 'Diagnostics',
]

export default function VisionRAGTab({
  vrSubTab, setVrSubTab,
  vrDiag, vrSessionData,
  vrSessionsList, vrSelectedId, selectVrSession, submitVrCreateSession,
  vrNewDatasetSessionId, setVrNewDatasetSessionId, vrNewQuery, setVrNewQuery, vrBusy,
  vrEventsList,
  runVrTextRetrieval,
  runVrAnswer,
  runVrEvidenceFusion, vrEvidenceList,
  runVrImageRetrieval,
  runVrOcrRetrieval,
  runVrObjectRetrieval,
  runVrKnowledgeGraphRetrieval,
  runVrQuality,
  runVrHallucinationCheck,
  runVrGenerateReport,
  submitVrCorrect, vrCorrectAction, setVrCorrectAction, vrCorrectAnswer, setVrCorrectAnswer,
  vrCorrectEvidenceId, setVrCorrectEvidenceId, vrCorrectSnippet, setVrCorrectSnippet,
  vrAddEvidenceType, setVrAddEvidenceType,
  runVrAdminReview,
  vrMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-17 -- Vision RAG &amp; Multimodal Retrieval Center. Not an OCR engine, vision model,
        dataset generator, embedding trainer, training engine, runtime, or release pipeline. It
        answers questions using text, OCR, image, object, and knowledge-graph retrieval from an
        already-certified MB-16 dataset -- every answer stays evidence-linked, and if evidence is
        insufficient it says so honestly instead of guessing. It never edits Dataset Studio, Document
        Workspace, or any prior Mini Brain phase, and it runs no vision model inference of its own.
      </p>

      <div className="dataset-tabs">
        {vrSubTabs.map((t) => (
          <Button key={t} className={vrSubTab === t ? 'active' : ''} onClick={() => setVrSubTab(t)}>{t}</Button>
        ))}
      </div>

      {vrSubTab === 'Overview' && (
        <>
          {vrDiag && (
            <div className="notice">
              <p><strong>Requires certified dataset:</strong> {String(vrDiag.requires_certified_dataset)} -- <strong>Vision model inference performed:</strong> {String(vrDiag.vision_model_inference_performed)}</p>
              <p><strong>Dataset Studio writes:</strong> {String(vrDiag.dataset_studio_writes_performed)} -- <strong>Training started:</strong> {String(vrDiag.training_started)} -- <strong>Automatic approval:</strong> {String(vrDiag.automatic_approval)}</p>
            </div>
          )}
          {vrSessionData && (
            <section className="metric-grid">
              <StatusCard label="Query" value={vrSessionData.query.slice(0, 24)} tone="neutral" />
              <StatusCard label="Stage" value={vrSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={vrSessionData.status} tone={vrSessionData.status.includes('reject') || vrSessionData.status.includes('hallucination') ? 'waiting' : vrSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Vision RAG query sessions</h4>
              <ul className="notice">
                {vrSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={vrSelectedId === s.public_id ? 'active' : ''} onClick={() => selectVrSession(s.public_id)}>
                      {s.query.slice(0, 30)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!vrSessionsList.length && <li>No query sessions yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitVrCreateSession}>
                <label>MB-16 certified dataset session public ID<input value={vrNewDatasetSessionId} onChange={(e) => setVrNewDatasetSessionId(e.target.value)} /></label>
                <label>Query<input value={vrNewQuery} onChange={(e) => setVrNewQuery(e.target.value)} placeholder="Where is the river located?" /></label>
                <Button type="submit" disabled={vrBusy || !vrNewDatasetSessionId.trim() || !vrNewQuery.trim()}>{vrBusy ? 'Working…' : 'Ask'}</Button>
              </form>
            </div>
            <div>
              {!vrSessionData && <div className="notice">Select or start a query session to work through it in the other sub-tabs.</div>}
              {vrSessionData && (
                <>
                  <h4>Session events</h4>
                  <ul className="notice">
                    {vrEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!vrEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {vrSubTab === 'Query' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <div className="notice">
              <p><strong>Query:</strong> {vrSessionData.query}</p>
              <p><strong>Detected language:</strong> {vrSessionData.query_language}</p>
              {vrSessionData.stage === 'query_session' && (
                <Button onClick={runVrTextRetrieval} disabled={vrBusy}>Run text retrieval</Button>
              )}
            </div>
          )}
        </>
      )}

      {vrSubTab === 'Results' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'grounded_answer' && (
                <div className="notice">
                  <p>Never generates free text -- the answer is built only from real, already-retrieved evidence snippets with citation markers. If evidence is insufficient, it says so honestly.</p>
                  <Button onClick={runVrAnswer} disabled={vrBusy}>Generate grounded answer</Button>
                </div>
              )}
              {vrSessionData.answer_report?.answer !== undefined && (
                <div className="notice">
                  <p><strong>Answer:</strong> {vrSessionData.answer_report.answer}</p>
                  <p><strong>Confidence:</strong> {vrSessionData.answer_report.confidence} -- <strong>Status:</strong> {vrSessionData.answer_report.status}</p>
                  <pre className="notice">{JSON.stringify(vrSessionData.answer_report, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </>
      )}

      {vrSubTab === 'Evidence' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'evidence_fusion' && (
                <div className="notice">
                  <Button onClick={runVrEvidenceFusion} disabled={vrBusy}>Fuse evidence</Button>
                </div>
              )}
              {vrSessionData.evidence_fusion_report?.evidence_count !== undefined && (
                <pre className="notice">{JSON.stringify(vrSessionData.evidence_fusion_report, null, 2)}</pre>
              )}
              <h4>Evidence ({vrEvidenceList.length})</h4>
              <ul className="notice">
                {vrEvidenceList.map((e) => (
                  <li key={e.public_id}>
                    <span className="pill neutral">{e.evidence_type}</span> {e.used_in_answer && <span className="pill good">cited</span>} score={e.relevance_score} -- {e.content_snippet?.slice(0, 80)}
                  </li>
                ))}
                {!vrEvidenceList.length && <li>No evidence yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {vrSubTab === 'Images' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'image_retrieval' && (
                <div className="notice">
                  <p>No semantic image embedding exists in this codebase -- images are matched by their real, already-computed caption text only.</p>
                  <Button onClick={runVrImageRetrieval} disabled={vrBusy}>Retrieve images</Button>
                </div>
              )}
              {vrSessionData.image_retrieval_report?.image_count !== undefined && (
                <pre className="notice">{JSON.stringify(vrSessionData.image_retrieval_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vrSubTab === 'OCR' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'ocr_retrieval' && (
                <div className="notice">
                  <Button onClick={runVrOcrRetrieval} disabled={vrBusy}>Retrieve OCR text</Button>
                </div>
              )}
              {vrSessionData.ocr_retrieval_report?.ocr_record_count !== undefined && (
                <pre className="notice">{JSON.stringify(vrSessionData.ocr_retrieval_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vrSubTab === 'Objects' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'object_retrieval' && (
                <div className="notice">
                  <p>Reuses MB-15's admin-approved predictions when linked, otherwise MB-14's admin-annotated objects -- never a new detection pass.</p>
                  <Button onClick={runVrObjectRetrieval} disabled={vrBusy}>Retrieve objects</Button>
                </div>
              )}
              {vrSessionData.object_retrieval_report?.object_count !== undefined && (
                <pre className="notice">{JSON.stringify(vrSessionData.object_retrieval_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vrSubTab === 'Graph' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'knowledge_graph_retrieval' && (
                <div className="notice">
                  <p>Never regenerates a graph -- only filters MB-14/MB-15's already-built graph down to query-relevant edges.</p>
                  <Button onClick={runVrKnowledgeGraphRetrieval} disabled={vrBusy}>Retrieve graph edges</Button>
                </div>
              )}
              {vrSessionData.knowledge_graph_retrieval_report?.matched_edge_count !== undefined && (
                <pre className="notice">{JSON.stringify(vrSessionData.knowledge_graph_retrieval_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vrSubTab === 'Quality' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'quality_evaluation' && (
                <div className="notice">
                  <Button onClick={runVrQuality} disabled={vrBusy}>Evaluate RAG quality</Button>
                </div>
              )}
              {vrSessionData.quality_report?.overall_rag_quality !== undefined && (
                <pre className="notice">{JSON.stringify(vrSessionData.quality_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vrSubTab === 'Hallucinations' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'hallucination_check' && (
                <div className="notice">
                  <p>Every claim must trace to a real, cited evidence row -- reuses the production RAG system's own citation-validity and grounding-quality functions.</p>
                  <Button onClick={runVrHallucinationCheck} disabled={vrBusy}>Run hallucination check</Button>
                </div>
              )}
              {vrSessionData.hallucination_report?.hallucination_risk !== undefined && (
                <div className="notice">
                  <p><strong>Hallucination flag:</strong> <span className={`pill ${vrSessionData.hallucination_report.hallucination_flag ? 'block' : 'good'}`}>{String(vrSessionData.hallucination_report.hallucination_flag)}</span></p>
                  <pre className="notice">{JSON.stringify(vrSessionData.hallucination_report, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </>
      )}

      {vrSubTab === 'Reports' && (
        <>
          {!vrSessionData && <div className="notice">Select a query session in Overview first.</div>}
          {vrSessionData && (
            <>
              {vrSessionData.stage === 'report' && (
                <div className="notice">
                  <Button onClick={runVrGenerateReport} disabled={vrBusy}>Generate RAG report</Button>
                </div>
              )}
              {vrSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>RAG Report ready for review.</p>
                  <pre className="notice">{JSON.stringify(vrSessionData.rag_report, null, 2)}</pre>

                  <h4>Correct before deciding (optional, repeatable)</h4>
                  <form className="inline-form training-form" onSubmit={submitVrCorrect}>
                    <label>Action
                      <select value={vrCorrectAction} onChange={(e) => setVrCorrectAction(e.target.value)}>
                        <option value="correct_answer">correct_answer</option>
                        <option value="correct_evidence">correct_evidence</option>
                        <option value="add_evidence">add_evidence</option>
                      </select>
                    </label>
                    {vrCorrectAction === 'correct_answer' && (
                      <label>Corrected answer<input value={vrCorrectAnswer} onChange={(e) => setVrCorrectAnswer(e.target.value)} /></label>
                    )}
                    {vrCorrectAction === 'correct_evidence' && (
                      <>
                        <label>Evidence public ID<input value={vrCorrectEvidenceId} onChange={(e) => setVrCorrectEvidenceId(e.target.value)} /></label>
                        <label>Corrected snippet<input value={vrCorrectSnippet} onChange={(e) => setVrCorrectSnippet(e.target.value)} /></label>
                      </>
                    )}
                    {vrCorrectAction === 'add_evidence' && (
                      <>
                        <label>Evidence type
                          <select value={vrAddEvidenceType} onChange={(e) => setVrAddEvidenceType(e.target.value)}>
                            <option value="text">text</option>
                            <option value="ocr">ocr</option>
                            <option value="image">image</option>
                            <option value="object">object</option>
                            <option value="graph_edge">graph_edge</option>
                          </select>
                        </label>
                        <label>Content snippet<input value={vrCorrectSnippet} onChange={(e) => setVrCorrectSnippet(e.target.value)} /></label>
                      </>
                    )}
                    <Button type="submit" disabled={vrBusy}>Apply correction</Button>
                  </form>

                  <h4>Final decision</h4>
                  <Button onClick={() => runVrAdminReview('approve')} disabled={vrBusy}>Approve</Button>{' '}
                  <Button onClick={() => runVrAdminReview('reject')} disabled={vrBusy}>Reject</Button>{' '}
                  <Button onClick={() => runVrAdminReview('flag_hallucination')} disabled={vrBusy}>Flag Hallucination</Button>{' '}
                  <Button onClick={() => runVrAdminReview('archive')} disabled={vrBusy}>Archive</Button>
                </div>
              )}
              {vrSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Query closed with status <strong>{vrSessionData.status}</strong>. RAG Memory recorded -- eligible for MB-18/19/20 to reuse, never submitted automatically.</p>
                </div>
              )}

              <h4>RAG Memory (permanent)</h4>
              <ul className="notice">
                {vrMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- "{m.query.slice(0, 40)}" -- {m.admin_decision} -- confidence {m.confidence} -- hallucination {String(m.hallucination_flag)}</li>
                ))}
                {!vrMemoryList.length && <li>No RAG memory recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {vrSubTab === 'History' && vrSessionData && (
        <>
          <h4>Session events</h4>
          <ul className="notice">
            {vrEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!vrEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {vrSubTab === 'History' && !vrSessionData && (
        <div className="notice">Select a query session in Overview first.</div>
      )}

      {vrSubTab === 'Diagnostics' && (
        <>
          {vrDiag && <pre className="notice">{JSON.stringify(vrDiag, null, 2)}</pre>}
          {!vrDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
