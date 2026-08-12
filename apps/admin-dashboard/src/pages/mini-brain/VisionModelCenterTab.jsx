import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const vmSubTabs = [
  'Overview', 'Providers', 'Detection', 'Caption', 'Scene', 'Relationships', 'Corrections',
  'Learning Memory', 'Reports', 'History', 'Diagnostics',
]
const vmReviewActions = [
  'approve', 'reject', 'rename', 'split', 'merge', 'delete', 'add', 'move_box', 'resize_box', 'rotate_box',
]

export default function VisionModelCenterTab({
  vmSubTab, setVmSubTab,
  vmDiag, vmSessionData,
  vmSessionsList, vmSelectedId, selectVmSession, submitVmCreateSession,
  vmNewVisionSessionId, setVmNewVisionSessionId, vmNewProviderKey, setVmNewProviderKey, vmProvidersList, vmBusy,
  vmEventsList,
  toggleVmProviderStatus,
  runVmImageLoad,
  vmModelPath, setVmModelPath, vmMmprojPath, setVmMmprojPath, runVmProviderSelection,
  runVmObjectDetection, vmPredictionsList,
  submitVmReview, vmReviewAction, setVmReviewAction, vmReviewPredictionId, setVmReviewPredictionId,
  vmReviewLabel, setVmReviewLabel, vmReviewImageId, setVmReviewImageId,
  vmReviewBoxX, setVmReviewBoxX, vmReviewBoxY, setVmReviewBoxY, vmReviewBoxW, setVmReviewBoxW, vmReviewBoxH, setVmReviewBoxH,
  runVmFinishReview,
  runVmSceneDetection,
  runVmCaption,
  runVmRelationshipDetection,
  vmDatasetTextInput, setVmDatasetTextInput, runVmOcrCrossValidation,
  runVmKnowledgeGraph,
  runVmCorrectionMemory, vmCorrectionsList,
  vmLearningMemoryList,
  runVmQualityScore,
  runVmDatasetDraft,
  runVmGenerateReport,
  runVmAdminReview,
}) {
  return (
    <>
      <p className="notice">
        MB-15 -- Vision Model Integration &amp; Human-in-the-Loop Annotation Center. Not another
        Vision Intelligence module -- that is MB-14, whose images and objects this phase only ever
        reads. MB-15 connects a real, pluggable vision inference backend to MB-14's already-extracted
        images and structures whatever it predicts into suggestions. No vision model file exists
        anywhere in this environment, so predictions are honestly empty until an admin configures a
        real model. Everything here requires explicit admin approval -- nothing is accepted
        automatically, and no dataset, document, MB-14 row, training run, runtime, GGUF export, or RAG
        index is ever touched by this service.
      </p>

      <div className="dataset-tabs">
        {vmSubTabs.map((t) => (
          <Button key={t} className={vmSubTab === t ? 'active' : ''} onClick={() => setVmSubTab(t)}>{t}</Button>
        ))}
      </div>

      {vmSubTab === 'Overview' && (
        <>
          {vmDiag && (
            <div className="notice">
              <p><strong>Vision model file present:</strong> {String(vmDiag.vision_model_file_present)} -- <strong>LLaVA GGUF library available:</strong> {String(vmDiag.backend_library_available?.llava_gguf)}</p>
              <p><strong>Dataset writes:</strong> {String(vmDiag.dataset_writes_performed)} -- <strong>MB-14 writes:</strong> {String(vmDiag.mb14_writes_performed)} -- <strong>Training started:</strong> {String(vmDiag.training_started)} -- <strong>Automatic approval:</strong> {String(vmDiag.automatic_approval)}</p>
            </div>
          )}
          {vmSessionData && (
            <section className="metric-grid">
              <StatusCard label="MB-14 session" value={vmSessionData.vision_session_public_id.slice(0, 12)} tone="neutral" />
              <StatusCard label="Provider" value={vmSessionData.provider_key} tone="neutral" />
              <StatusCard label="Stage" value={vmSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={vmSessionData.status} tone={vmSessionData.status.includes('reject') ? 'waiting' : vmSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Vision model cycles</h4>
              <ul className="notice">
                {vmSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={vmSelectedId === s.public_id ? 'active' : ''} onClick={() => selectVmSession(s.public_id)}>
                      {s.provider_key} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!vmSessionsList.length && <li>No vision model cycles yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitVmCreateSession}>
                <label>MB-14 vision session public ID<input value={vmNewVisionSessionId} onChange={(e) => setVmNewVisionSessionId(e.target.value)} placeholder="a certified or in-progress MB-14 session" /></label>
                <label>Provider
                  <select value={vmNewProviderKey} onChange={(e) => setVmNewProviderKey(e.target.value)}>
                    {vmProvidersList.filter((p) => p.status === 'active').map((p) => (
                      <option key={p.provider_key} value={p.provider_key}>{p.display_name}</option>
                    ))}
                  </select>
                </label>
                <Button type="submit" disabled={vmBusy || !vmNewVisionSessionId.trim()}>{vmBusy ? 'Working…' : 'Start vision model cycle'}</Button>
              </form>
            </div>
            <div>
              {!vmSessionData && <div className="notice">Select or start a vision model cycle to work through it in the other sub-tabs.</div>}
              {vmSessionData && (
                <>
                  <h4>Cycle events</h4>
                  <ul className="notice">
                    {vmEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!vmEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {vmSubTab === 'Providers' && (
        <>
          <h4>Provider registry</h4>
          <ul className="notice">
            {vmProvidersList.map((p) => (
              <li key={p.provider_key}>
                <strong>{p.display_name}</strong> ({p.provider_key}, {p.backend_type}/{p.hardware_target}) --{' '}
                <span className={`pill ${p.status === 'active' ? 'good' : 'neutral'}`}>{p.status}</span>{' '}
                <Button onClick={() => toggleVmProviderStatus(p.provider_key, p.status)} disabled={vmBusy}>
                  {p.status === 'active' ? 'Deactivate' : 'Activate'}
                </Button>
                <div>{p.description}</div>
              </li>
            ))}
          </ul>

          {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
          {vmSessionData && (
            <>
              {vmSessionData.stage === 'image_load' && (
                <div className="notice">
                  <p>Reads MB-14's own already-extracted image metadata read-only.</p>
                  <Button onClick={runVmImageLoad} disabled={vmBusy}>Load images from MB-14</Button>
                </div>
              )}
              {vmSessionData.image_load_report?.image_count !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.image_load_report, null, 2)}</pre>
              )}
              {vmSessionData.stage === 'provider_selection' && (
                <div className="notice">
                  <p>No vision model file exists anywhere in this environment by default -- supply real paths only if one has been placed on disk. Otherwise every prediction stage will honestly report the provider unavailable.</p>
                  <label>Model path (optional)<input value={vmModelPath} onChange={(e) => setVmModelPath(e.target.value)} placeholder="/path/to/vision-model.gguf" /></label>
                  <label>CLIP mmproj path (optional, LLaVA only)<input value={vmMmprojPath} onChange={(e) => setVmMmprojPath(e.target.value)} placeholder="/path/to/mmproj.gguf" /></label>
                  <Button onClick={runVmProviderSelection} disabled={vmBusy}>Select provider</Button>
                </div>
              )}
              {vmSessionData.provider_report?.selected !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.provider_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vmSubTab === 'Detection' && (
        <>
          {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
          {vmSessionData && (
            <>
              {vmSessionData.stage === 'object_detection' && (
                <div className="notice">
                  <p>Real bounding boxes are never produced by any provider in this codebase -- no detection-capable model architecture exists for any of them.</p>
                  <Button onClick={runVmObjectDetection} disabled={vmBusy}>Run object detection</Button>
                </div>
              )}
              {vmSessionData.detection_report?.object_count !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.detection_report, null, 2)}</pre>
              )}

              <h4>Predictions</h4>
              <ul className="notice">
                {vmPredictionsList.map((p) => (
                  <li key={p.public_id}>
                    {p.label} -- confidence {p.confidence} -- {p.source} -- <span className="pill neutral">{p.review_status}</span> -- {p.public_id.slice(0, 12)}
                  </li>
                ))}
                {!vmPredictionsList.length && <li>No predictions yet.</li>}
              </ul>

              {vmSessionData.stage === 'admin_review' && (
                <div className="notice">
                  <p>Admin can approve, reject, rename, split, merge, delete, add, move box, resize box, or rotate box. Every correction becomes permanent Vision Correction Memory.</p>
                  <form className="inline-form training-form" onSubmit={submitVmReview}>
                    <label>Action
                      <select value={vmReviewAction} onChange={(e) => setVmReviewAction(e.target.value)}>
                        {vmReviewActions.map((a) => <option key={a} value={a}>{a}</option>)}
                      </select>
                    </label>
                    {vmReviewAction !== 'add' && vmReviewAction !== 'merge' && (
                      <label>Prediction
                        <select value={vmReviewPredictionId} onChange={(e) => setVmReviewPredictionId(e.target.value)}>
                          <option value="">select a prediction…</option>
                          {vmPredictionsList.map((p) => (
                            <option key={p.public_id} value={p.public_id}>{p.label} -- {p.public_id.slice(0, 12)}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {(vmReviewAction === 'rename' || vmReviewAction === 'add') && (
                      <label>Label<input value={vmReviewLabel} onChange={(e) => setVmReviewLabel(e.target.value)} /></label>
                    )}
                    {vmReviewAction === 'add' && (
                      <label>Image public ID<input value={vmReviewImageId} onChange={(e) => setVmReviewImageId(e.target.value)} /></label>
                    )}
                    {['move_box', 'resize_box', 'rotate_box', 'add'].includes(vmReviewAction) && (
                      <>
                        <label>Box x (0-1)<input value={vmReviewBoxX} onChange={(e) => setVmReviewBoxX(e.target.value)} /></label>
                        <label>Box y (0-1)<input value={vmReviewBoxY} onChange={(e) => setVmReviewBoxY(e.target.value)} /></label>
                        <label>Box width (0-1)<input value={vmReviewBoxW} onChange={(e) => setVmReviewBoxW(e.target.value)} /></label>
                        <label>Box height (0-1)<input value={vmReviewBoxH} onChange={(e) => setVmReviewBoxH(e.target.value)} /></label>
                      </>
                    )}
                    <Button type="submit" disabled={vmBusy}>{vmBusy ? 'Working…' : 'Apply review'}</Button>
                  </form>
                  <Button onClick={runVmFinishReview} disabled={vmBusy}>Finish admin review stage</Button>
                </div>
              )}
              {vmSessionData.admin_review_report?.total_predictions !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.admin_review_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vmSubTab === 'Scene' && (
        <>
          {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
          {vmSessionData && (
            <>
              {vmSessionData.stage === 'scene_detection' && (
                <div className="notice">
                  <Button onClick={runVmSceneDetection} disabled={vmBusy}>Run scene detection</Button>
                </div>
              )}
              {vmSessionData.scene_report?.provider_available !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.scene_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vmSubTab === 'Caption' && (
        <>
          {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
          {vmSessionData && (
            <>
              {vmSessionData.stage === 'caption_generation' && (
                <div className="notice">
                  <Button onClick={runVmCaption} disabled={vmBusy}>Run caption generation</Button>
                </div>
              )}
              {vmSessionData.caption_report?.provider_available !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.caption_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vmSubTab === 'Relationships' && (
        <>
          {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
          {vmSessionData && (
            <>
              {vmSessionData.stage === 'relationship_detection' && (
                <div className="notice">
                  <p>Reuses MB-14's own real bounding-box geometry -- zero new relationship logic.</p>
                  <Button onClick={runVmRelationshipDetection} disabled={vmBusy}>Detect relationships (preview)</Button>
                </div>
              )}
              {vmSessionData.relationship_report?.node_count !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.relationship_report, null, 2)}</pre>
              )}
              {vmSessionData.stage === 'ocr_cross_validation' && (
                <div className="notice">
                  <label>Dataset text to compare against (optional)<textarea rows={3} value={vmDatasetTextInput} onChange={(e) => setVmDatasetTextInput(e.target.value)} /></label>
                  <Button onClick={runVmOcrCrossValidation} disabled={vmBusy}>Run OCR/vision/dataset cross validation</Button>
                </div>
              )}
              {vmSessionData.ocr_cross_validation_report?.status && (
                <pre className="notice">{JSON.stringify(vmSessionData.ocr_cross_validation_report, null, 2)}</pre>
              )}
              {vmSessionData.stage === 'knowledge_graph' && (
                <div className="notice">
                  <p>Final knowledge graph, built from admin-approved predictions only.</p>
                  <Button onClick={runVmKnowledgeGraph} disabled={vmBusy}>Build final knowledge graph</Button>
                </div>
              )}
              {vmSessionData.knowledge_graph_report?.node_count !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.knowledge_graph_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {vmSubTab === 'Corrections' && (
        <>
          {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
          {vmSessionData && (
            <>
              {vmSessionData.stage === 'correction_memory' && (
                <div className="notice">
                  <Button onClick={runVmCorrectionMemory} disabled={vmBusy}>Summarize correction memory</Button>
                </div>
              )}
              {vmSessionData.correction_memory_report?.total_corrections !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.correction_memory_report, null, 2)}</pre>
              )}
              <h4>Correction memory (permanent)</h4>
              <ul className="notice">
                {vmCorrectionsList.map((c) => (
                  <li key={c.public_id}>{c.created_at} -- {c.action} -- {c.wrong_label} -&gt; {c.correct_label || '(n/a)'} -- {c.reason}</li>
                ))}
                {!vmCorrectionsList.length && <li>No corrections recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {vmSubTab === 'Learning Memory' && (
        <>
          <p className="notice">Permanent, insert-only rollups -- MB-15 never retrains anything; a future training phase can reuse this history.</p>
          <ul className="notice">
            {vmLearningMemoryList.map((m) => (
              <li key={m.public_id}>
                {m.created_at} -- {m.provider_key} -- {m.total_predictions} prediction(s), {m.corrected_count} corrected, {m.rejected_count} rejected, rate {m.correction_rate}
              </li>
            ))}
            {!vmLearningMemoryList.length && <li>No learning memory recorded yet.</li>}
          </ul>
        </>
      )}

      {vmSubTab === 'Reports' && (
        <>
          {!vmSessionData && <div className="notice">Select a vision model cycle in Overview first.</div>}
          {vmSessionData && (
            <>
              {vmSessionData.stage === 'quality_score' && (
                <div className="notice">
                  <Button onClick={runVmQualityScore} disabled={vmBusy}>Compute AI-only quality score</Button>
                </div>
              )}
              {vmSessionData.quality_report?.overall_vision_model_score !== undefined && (
                <pre className="notice">{JSON.stringify(vmSessionData.quality_report, null, 2)}</pre>
              )}
              {vmSessionData.stage === 'dataset_draft' && (
                <div className="notice">
                  <Button onClick={runVmDatasetDraft} disabled={vmBusy}>Build vision model dataset draft</Button>
                </div>
              )}
              {vmSessionData.dataset_draft_report?.status && (
                <pre className="notice">{JSON.stringify(vmSessionData.dataset_draft_report, null, 2)}</pre>
              )}
              {vmSessionData.stage === 'vision_report' && (
                <div className="notice">
                  <Button onClick={runVmGenerateReport} disabled={vmBusy}>Generate vision model report</Button>
                </div>
              )}
              {vmSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Vision Model Report ready for review.</p>
                  <pre className="notice">{JSON.stringify(vmSessionData.vision_report, null, 2)}</pre>
                  <Button onClick={() => runVmAdminReview('approve')} disabled={vmBusy}>Approve</Button>{' '}
                  <Button onClick={() => runVmAdminReview('reject')} disabled={vmBusy}>Reject</Button>{' '}
                  <Button onClick={() => runVmAdminReview('request_fix')} disabled={vmBusy}>Request Fix</Button>{' '}
                  <Button onClick={() => runVmAdminReview('archive')} disabled={vmBusy}>Archive</Button>
                </div>
              )}
              {vmSessionData.stage === 'certified' && (
                <div className="notice">
                  <p>Vision Model Certified -- eligible for MB-16 Multimodal Dataset Generator, MB-17 Vision RAG, and MB-18 Multimodal Training Pipeline. This service never submits it to any of them automatically.</p>
                </div>
              )}
              {vmSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Vision model cycle closed with status <strong>{vmSessionData.status}</strong>. No automatic action was taken.</p>
                </div>
              )}
            </>
          )}
        </>
      )}

      {vmSubTab === 'History' && vmSessionData && (
        <>
          <h4>Cycle events</h4>
          <ul className="notice">
            {vmEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!vmEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {vmSubTab === 'History' && !vmSessionData && (
        <div className="notice">Select a vision model cycle in Overview first.</div>
      )}

      {vmSubTab === 'Diagnostics' && (
        <>
          {vmDiag && <pre className="notice">{JSON.stringify(vmDiag, null, 2)}</pre>}
          {!vmDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
