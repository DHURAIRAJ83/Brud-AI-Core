import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const mdSubTabs = [
  'Overview', 'Sources', 'Images', 'Text', 'Conversation', 'Instructions', 'QA', 'Dataset Draft',
  'Quality', 'Reports', 'History', 'Diagnostics',
]

export default function MultimodalDatasetGeneratorTab({
  mdSubTab, setMdSubTab,
  mdDiag, mdSessionData,
  mdSessionsList, mdSelectedId, selectMdSession, submitMdCreateSession,
  mdNewDocumentId, setMdNewDocumentId, mdNewVisionSessionId, setMdNewVisionSessionId,
  mdNewLanguageSessionId, setMdNewLanguageSessionId, mdNewVisionModelSessionId, setMdNewVisionModelSessionId,
  mdBusy,
  mdEventsList,
  runMdCollectSources,
  runMdMergeMetadata,
  runMdCollectText,
  runMdCollectImages,
  runMdConversationBuilder,
  runMdInstructionBuilder,
  mdRecordsList,
  runMdDatasetDraft,
  submitMdSplit, mdSplitRecordIds, setMdSplitRecordIds,
  submitMdMerge, mdMergeSessionIds, setMdMergeSessionIds,
  mdExportFormat, setMdExportFormat, runMdExportDraft, runMdDeleteDraft, mdExportResult,
  runMdQualityAnalysis,
  runMdDuplicateDetection,
  runMdGenerateReport,
  runMdAdminReview,
  mdMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-16 -- Multimodal Dataset Generator Center. Not an OCR engine, vision model, language
        model, dataset writer, training engine, or runtime. It combines already-computed output from
        MB-13, MB-14, MB-15, Dataset Studio, and Document Workspace -- read through their own public
        methods only -- into one unified draft dataset spanning conversation, instruction, QA,
        caption, vision, grounding, reasoning, and training record flavors. Every record stays
        <code>verified: false</code> and every dataset stays Draft until an admin certifies it. Nothing
        here is ever written into Dataset Studio, Document Workspace, or any prior Mini Brain phase.
      </p>

      <div className="dataset-tabs">
        {mdSubTabs.map((t) => (
          <Button key={t} className={mdSubTab === t ? 'active' : ''} onClick={() => setMdSubTab(t)}>{t}</Button>
        ))}
      </div>

      {mdSubTab === 'Overview' && (
        <>
          {mdDiag && (
            <div className="notice">
              <p><strong>Dataset Studio writes:</strong> {String(mdDiag.dataset_studio_writes_performed)} -- <strong>Document Workspace writes:</strong> {String(mdDiag.document_workspace_writes_performed)}</p>
              <p><strong>Training started:</strong> {String(mdDiag.training_started)} -- <strong>Automatic export:</strong> {String(mdDiag.automatic_export)} -- <strong>Automatic approval:</strong> {String(mdDiag.automatic_approval)}</p>
            </div>
          )}
          {mdSessionData && (
            <section className="metric-grid">
              <StatusCard label="Document" value={mdSessionData.document_source_public_id.slice(0, 12)} tone="neutral" />
              <StatusCard label="Stage" value={mdSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={mdSessionData.status} tone={mdSessionData.status.includes('reject') || mdSessionData.status === 'draft_deleted' ? 'waiting' : mdSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Multimodal dataset cycles</h4>
              <ul className="notice">
                {mdSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={mdSelectedId === s.public_id ? 'active' : ''} onClick={() => selectMdSession(s.public_id)}>
                      {s.document_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!mdSessionsList.length && <li>No multimodal dataset cycles yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitMdCreateSession}>
                <label>Document source public ID<input value={mdNewDocumentId} onChange={(e) => setMdNewDocumentId(e.target.value)} placeholder="document public_id from Document Workspace" /></label>
                <label>MB-14 vision session (optional)<input value={mdNewVisionSessionId} onChange={(e) => setMdNewVisionSessionId(e.target.value)} /></label>
                <label>MB-13 language session (optional)<input value={mdNewLanguageSessionId} onChange={(e) => setMdNewLanguageSessionId(e.target.value)} /></label>
                <label>MB-15 vision model session (optional)<input value={mdNewVisionModelSessionId} onChange={(e) => setMdNewVisionModelSessionId(e.target.value)} /></label>
                <Button type="submit" disabled={mdBusy || !mdNewDocumentId.trim()}>{mdBusy ? 'Working…' : 'Start dataset cycle'}</Button>
              </form>
            </div>
            <div>
              {!mdSessionData && <div className="notice">Select or start a dataset cycle to work through it in the other sub-tabs.</div>}
              {mdSessionData && (
                <>
                  <h4>Cycle events</h4>
                  <ul className="notice">
                    {mdEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!mdEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {mdSubTab === 'Sources' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'collect_sources' && (
                <div className="notice">
                  <Button onClick={runMdCollectSources} disabled={mdBusy}>Collect sources</Button>
                </div>
              )}
              {mdSessionData.source_report?.available_source_count !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.source_report, null, 2)}</pre>
              )}
              {mdSessionData.stage === 'merge_metadata' && (
                <div className="notice">
                  <p>Merges the text section, image section, and a reference (never regenerated) knowledge graph into one unified object.</p>
                  <Button onClick={runMdMergeMetadata} disabled={mdBusy}>Merge metadata</Button>
                </div>
              )}
              {mdSessionData.metadata_report?.is_multimodal !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.metadata_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {mdSubTab === 'Text' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'collect_text' && (
                <div className="notice">
                  <p>Reuses MB-13's own already-computed language/Unicode/OCR/Tanglish reports when a Language Intelligence session is linked; otherwise language-quality fields are honestly unavailable.</p>
                  <Button onClick={runMdCollectText} disabled={mdBusy}>Collect text</Button>
                </div>
              )}
              {mdSessionData.text_section?.ocr_char_count !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.text_section, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {mdSubTab === 'Images' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'collect_images' && (
                <div className="notice">
                  <p>Reuses MB-14's own image metadata/checksum/resolution/boxes/caption/objects/relationships/quality, plus MB-15's own vision-provider predictions and corrections when linked.</p>
                  <Button onClick={runMdCollectImages} disabled={mdBusy}>Collect images</Button>
                </div>
              )}
              {mdSessionData.image_section?.image_count !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.image_section, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {mdSubTab === 'Conversation' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'conversation_builder' && (
                <div className="notice">
                  <p>Builds User/Assistant turns only from real, already-computed data -- MB-14's own QA questions and real OCR text. Always <code>verified: false</code>.</p>
                  <Button onClick={runMdConversationBuilder} disabled={mdBusy}>Build conversations</Button>
                </div>
              )}
              {mdSessionData.conversation_report?.conversation_count !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.conversation_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {mdSubTab === 'Instructions' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'instruction_builder' && (
                <div className="notice">
                  <p>Builds instruction/input/output triples from real transcription, caption, and object-list data. No summarization model exists in this codebase.</p>
                  <Button onClick={runMdInstructionBuilder} disabled={mdBusy}>Build instructions</Button>
                </div>
              )}
              {mdSessionData.instruction_report?.instruction_count !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.instruction_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {mdSubTab === 'QA' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              <p className="notice">QA-flavored records are a filtered view of the dataset draft -- reused from MB-14's own QA generation, never regenerated here.</p>
              <ul className="notice">
                {mdRecordsList.filter((r) => r.record_type === 'qa').map((r) => (
                  <li key={r.public_id}>{r.content.user} -- {r.content.assistant}</li>
                ))}
                {!mdRecordsList.filter((r) => r.record_type === 'qa').length && <li>No QA records yet -- build the dataset draft first.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {mdSubTab === 'Dataset Draft' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'dataset_draft' && (
                <div className="notice">
                  <p>Assembles every record flavor (conversation, instruction, qa, caption, vision, grounding, reasoning, training) from already-built data. Nothing inserted into Dataset Studio.</p>
                  <Button onClick={runMdDatasetDraft} disabled={mdBusy}>Assemble dataset draft</Button>
                </div>
              )}
              {mdSessionData.dataset_draft_report?.record_count !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.dataset_draft_report, null, 2)}</pre>
              )}
              <h4>Records ({mdRecordsList.length})</h4>
              <ul className="notice">
                {mdRecordsList.slice(0, 50).map((r) => (
                  <li key={r.public_id}>
                    <span className="pill neutral">{r.record_type}</span> {r.status !== 'active' && <span className="pill warn">{r.status}</span>} -- {r.public_id.slice(0, 12)}
                  </li>
                ))}
                {!mdRecordsList.length && <li>No records yet.</li>}
              </ul>

              {mdSessionData.stage === 'certified' && (
                <>
                  <h4>Split into a new draft</h4>
                  <form className="inline-form training-form" onSubmit={submitMdSplit}>
                    <label>Record public IDs (comma-separated)<input value={mdSplitRecordIds} onChange={(e) => setMdSplitRecordIds(e.target.value)} /></label>
                    <Button type="submit" disabled={mdBusy}>Split dataset</Button>
                  </form>
                  <h4>Merge with other certified datasets</h4>
                  <form className="inline-form training-form" onSubmit={submitMdMerge}>
                    <label>Session public IDs incl. this one (comma-separated)<input value={mdMergeSessionIds} onChange={(e) => setMdMergeSessionIds(e.target.value)} /></label>
                    <Button type="submit" disabled={mdBusy}>Merge datasets</Button>
                  </form>
                </>
              )}

              <h4>Export / Delete</h4>
              <div className="notice">
                <label>Format
                  <select value={mdExportFormat} onChange={(e) => setMdExportFormat(e.target.value)}>
                    <option value="json">json</option>
                    <option value="jsonl">jsonl</option>
                  </select>
                </label>{' '}
                <Button onClick={runMdExportDraft} disabled={mdBusy}>Export draft</Button>{' '}
                {mdSessionData.stage !== 'certified' && (
                  <Button onClick={runMdDeleteDraft} disabled={mdBusy}>Delete draft</Button>
                )}
                {mdExportResult && (
                  <pre className="notice">{mdExportResult.content}</pre>
                )}
              </div>
            </>
          )}
        </>
      )}

      {mdSubTab === 'Quality' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'quality_analysis' && (
                <div className="notice">
                  <Button onClick={runMdQualityAnalysis} disabled={mdBusy}>Run quality analysis</Button>
                </div>
              )}
              {mdSessionData.quality_report?.overall_dataset_quality !== undefined && (
                <pre className="notice">{JSON.stringify(mdSessionData.quality_report, null, 2)}</pre>
              )}
              {mdSessionData.stage === 'duplicate_detection' && (
                <div className="notice">
                  <p>Reuses the existing ExternalDatasetDuplicateService (Phase 12) -- never a new duplicate-matching implementation.</p>
                  <Button onClick={runMdDuplicateDetection} disabled={mdBusy}>Run duplicate detection</Button>
                </div>
              )}
              {mdSessionData.duplicate_report?.reused_service && (
                <pre className="notice">{JSON.stringify(mdSessionData.duplicate_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {mdSubTab === 'Reports' && (
        <>
          {!mdSessionData && <div className="notice">Select a dataset cycle in Overview first.</div>}
          {mdSessionData && (
            <>
              {mdSessionData.stage === 'report' && (
                <div className="notice">
                  <Button onClick={runMdGenerateReport} disabled={mdBusy}>Generate dataset report</Button>
                </div>
              )}
              {mdSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Dataset Report ready for review.</p>
                  <pre className="notice">{JSON.stringify(mdSessionData.dataset_report, null, 2)}</pre>
                  <Button onClick={() => runMdAdminReview('approve')} disabled={mdBusy}>Approve</Button>{' '}
                  <Button onClick={() => runMdAdminReview('reject')} disabled={mdBusy}>Reject</Button>{' '}
                  <Button onClick={() => runMdAdminReview('request_changes')} disabled={mdBusy}>Request Changes</Button>{' '}
                  <Button onClick={() => runMdAdminReview('archive')} disabled={mdBusy}>Archive</Button>
                </div>
              )}
              {mdSessionData.stage === 'certified' && (
                <div className="notice">
                  <p>Dataset Certified -- eligible for MB-17 Vision RAG, MB-18 Multimodal Training Pipeline, MB-19 Evaluation, and MB-20 Release Pipeline. This service never submits it to any of them automatically, and nothing has been written into Dataset Studio.</p>
                </div>
              )}
              {mdSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Dataset cycle closed with status <strong>{mdSessionData.status}</strong>. No automatic action was taken.</p>
                </div>
              )}

              <h4>Dataset Memory (permanent)</h4>
              <ul className="notice">
                {mdMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- v{m.dataset_version} -- {m.total_records} record(s) -- {m.admin_decision}</li>
                ))}
                {!mdMemoryList.length && <li>No dataset memory recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {mdSubTab === 'History' && mdSessionData && (
        <>
          <h4>Cycle events</h4>
          <ul className="notice">
            {mdEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!mdEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {mdSubTab === 'History' && !mdSessionData && (
        <div className="notice">Select a dataset cycle in Overview first.</div>
      )}

      {mdSubTab === 'Diagnostics' && (
        <>
          {mdDiag && <pre className="notice">{JSON.stringify(mdDiag, null, 2)}</pre>}
          {!mdDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
