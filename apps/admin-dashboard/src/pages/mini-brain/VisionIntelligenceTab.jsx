import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const viSubTabs = [
  'Overview', 'Image Extraction', 'Quality', 'Objects', 'OCR Compare', 'Caption', 'Annotation',
  'Knowledge Graph', 'QA', 'Vision Draft', 'Report', 'History', 'Diagnostics',
]

export default function VisionIntelligenceTab({
  viSubTab, setViSubTab,
  viDiag, viSessionData,
  viSessionsList, viSelectedId, selectViSession, submitViCreateSession, viNewDocumentSourceId, setViNewDocumentSourceId, viNewDatasetSourceId, setViNewDatasetSourceId, viBusy,
  viEventsList,
  runViImageExtraction, viImagesList,
  runViImageQuality,
  runViVisionUnderstanding, viObjectsList,
  viDatasetTextInput, setViDatasetTextInput, runViOcrCrossValidation,
  viAdminCaptionInput, setViAdminCaptionInput, runViCaption,
  runViBoundingBoxPlan,
  submitViAnnotate, viAnnotateAction, setViAnnotateAction, viAnnotateObjectId, setViAnnotateObjectId,
  viAnnotateLabel, setViAnnotateLabel, viAnnotateImageId, setViAnnotateImageId,
  viAnnotateCaption, setViAnnotateCaption,
  viAnnotateBoxX, setViAnnotateBoxX, viAnnotateBoxY, setViAnnotateBoxY, viAnnotateBoxW, setViAnnotateBoxW, viAnnotateBoxH, setViAnnotateBoxH,
  runViFinishAnnotation,
  runViKnowledgeGraph,
  runViQaGeneration,
  runViDatasetDraft,
  runViQualityScore,
  runViGenerateReport,
  runViAdminReview,
}) {
  return (
    <>
      <p className="notice">
        MB-14 -- Vision Intelligence &amp; Image Understanding Center. Not an image generator,
        dataset editor, OCR engine, training engine, or runtime. It extracts and analyzes images
        already inside a document, compares them with OCR/dataset text, and prepares structured
        visual knowledge for admin review. No vision model, object-detection model, or
        captioning model exists anywhere in this codebase (confirmed by audit) -- every
        automated detection is honestly reported as an <code>Unknown Object</code> with
        confidence 0.0 until an admin annotates it. It never edits the original document, never
        writes to Dataset Studio, never starts training, and never deploys.
      </p>

      <div className="dataset-tabs">
        {viSubTabs.map((t) => (
          <Button key={t} className={viSubTab === t ? 'active' : ''} onClick={() => setViSubTab(t)}>{t}</Button>
        ))}
      </div>

      {viSubTab === 'Overview' && (
        <>
          {viDiag && (
            <div className="notice">
              <p><strong>Vision model available:</strong> {String(viDiag.vision_model_available)} -- <strong>Object detection available:</strong> {String(viDiag.object_detection_model_available)} -- <strong>Captioning available:</strong> {String(viDiag.captioning_model_available)}</p>
              <p><strong>Dataset writes performed:</strong> {String(viDiag.dataset_writes_performed)} -- Dataset Studio remains the only place a dataset is actually written.</p>
              <p><strong>Training started:</strong> {String(viDiag.training_started)} -- <strong>Runtime activated:</strong> {String(viDiag.runtime_activated)} -- <strong>RAG modified:</strong> {String(viDiag.rag_modified)} -- <strong>Automatic approval:</strong> {String(viDiag.automatic_approval)}</p>
            </div>
          )}
          {viSessionData && (
            <section className="metric-grid">
              <StatusCard label="Document source" value={viSessionData.document_source_public_id.slice(0, 12)} tone="neutral" />
              <StatusCard label="Stage" value={viSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={viSessionData.status} tone={viSessionData.status.includes('reject') ? 'waiting' : viSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Vision cycles</h4>
              <ul className="notice">
                {viSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={viSelectedId === s.public_id ? 'active' : ''} onClick={() => selectViSession(s.public_id)}>
                      {s.document_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!viSessionsList.length && <li>No vision cycles yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitViCreateSession}>
                <label>Document source public ID<input value={viNewDocumentSourceId} onChange={(e) => setViNewDocumentSourceId(e.target.value)} placeholder="document public_id from Document Workspace" /></label>
                <label>Dataset source public ID (optional)<input value={viNewDatasetSourceId} onChange={(e) => setViNewDatasetSourceId(e.target.value)} placeholder="linked Dataset Studio source, optional" /></label>
                <Button type="submit" disabled={viBusy || !viNewDocumentSourceId.trim()}>{viBusy ? 'Working…' : 'Start vision cycle'}</Button>
              </form>
            </div>
            <div>
              {!viSessionData && <div className="notice">Select or start a vision cycle to work through it in the other sub-tabs.</div>}
              {viSessionData && (
                <>
                  <h4>Cycle events</h4>
                  <ul className="notice">
                    {viEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!viEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {viSubTab === 'Image Extraction' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'image_extraction' && (
                <div className="notice">
                  <p>Extracts every real embedded image from the already-stored PDF via PyMuPDF -- the original document is never modified.</p>
                  <Button onClick={runViImageExtraction} disabled={viBusy}>Run image extraction</Button>
                </div>
              )}
              {viSessionData.image_extraction_report?.total_images !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.image_extraction_report, null, 2)}</pre>
              )}
              {!!viImagesList.length && (
                <>
                  <h4>Extracted images</h4>
                  <ul className="notice">
                    {viImagesList.map((img) => (
                      <li key={img.public_id}>
                        page {img.page_number} #{img.image_index} -- {img.image_format} {img.width_pixels}x{img.height_pixels} -- {img.file_size_bytes} bytes -- {img.checksum_sha256.slice(0, 12)}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'Quality' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'image_quality' && (
                <div className="notice">
                  <p>Real pixel statistics via Pillow: resolution, brightness/contrast (grayscale histogram), a blur proxy (edge-variance), and rotation (real EXIF orientation tag). Crop and noise detection are honestly NOT implemented.</p>
                  <Button onClick={runViImageQuality} disabled={viBusy}>Run image quality analysis</Button>
                </div>
              )}
              {viSessionData.quality_report?.average_quality_score !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.quality_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'Objects' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'vision_understanding' && (
                <div className="notice">
                  <p>No vision model exists anywhere in this codebase -- every extracted image is honestly reported as containing one <code>Unknown Object</code> placeholder with confidence 0.0, pending Stage 7 Admin Annotation. Nothing is ever invented.</p>
                  <Button onClick={runViVisionUnderstanding} disabled={viBusy}>Run vision understanding</Button>
                </div>
              )}
              {viSessionData.vision_understanding_report?.vision_model_available !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.vision_understanding_report, null, 2)}</pre>
              )}
              <h4>Active objects</h4>
              <ul className="notice">
                {viObjectsList.map((o) => (
                  <li key={o.public_id}>
                    {o.label} -- confidence {o.confidence} -- source {o.source} -- {o.public_id.slice(0, 12)}
                    {o.bounding_box && Object.keys(o.bounding_box).length > 0 && ` -- box ${JSON.stringify(o.bounding_box)}`}
                  </li>
                ))}
                {!viObjectsList.length && <li>No objects recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {viSubTab === 'OCR Compare' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'ocr_cross_validation' && (
                <div className="notice">
                  <p>Compares each page's real OCR text (already extracted by Document Workspace) against an optional linked dataset text. No vision model exists to describe image content for a true Image/OCR/Dataset three-way comparison -- this honestly compares only what is real and available. Never auto-corrects.</p>
                  <label>Dataset text to compare against (optional)<textarea rows={3} value={viDatasetTextInput} onChange={(e) => setViDatasetTextInput(e.target.value)} /></label>
                  <Button onClick={runViOcrCrossValidation} disabled={viBusy}>Run OCR cross validation</Button>
                </div>
              )}
              {viSessionData.ocr_cross_validation_report?.pages_compared !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.ocr_cross_validation_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'Caption' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'caption_generation' && (
                <div className="notice">
                  <p>No image-captioning model exists anywhere in this codebase -- a caption is only ever populated from an admin-supplied caption, never generated automatically. Always <code>verified: false</code>.</p>
                  <label>Admin-supplied caption (optional)<textarea rows={2} value={viAdminCaptionInput} onChange={(e) => setViAdminCaptionInput(e.target.value)} /></label>
                  <Button onClick={runViCaption} disabled={viBusy}>Set caption</Button>
                </div>
              )}
              {viSessionData.caption_report?.source && (
                <pre className="notice">{JSON.stringify(viSessionData.caption_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'Annotation' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'bounding_box_planning' && (
                <div className="notice">
                  <p>No object-detection model exists anywhere in this codebase -- no box is ever planned automatically. This only classifies already admin-drawn boxes; nothing is auto-accepted.</p>
                  <Button onClick={runViBoundingBoxPlan} disabled={viBusy}>Run bounding box planning</Button>
                </div>
              )}
              {viSessionData.bounding_box_report?.box_count !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.bounding_box_report, null, 2)}</pre>
              )}
              {viSessionData.stage === 'admin_annotation' && (
                <div className="notice">
                  <p>Admin can rename, delete, add, correct a caption, correct a label, or redraw a box. Everything is recorded as an event, and delete is a soft status flip, never a row delete.</p>
                  <form className="inline-form training-form" onSubmit={submitViAnnotate}>
                    <label>Action
                      <select value={viAnnotateAction} onChange={(e) => setViAnnotateAction(e.target.value)}>
                        <option value="rename">rename</option>
                        <option value="delete">delete</option>
                        <option value="add">add</option>
                        <option value="correct_caption">correct_caption</option>
                        <option value="correct_label">correct_label</option>
                        <option value="redraw_box">redraw_box</option>
                      </select>
                    </label>
                    {viAnnotateAction !== 'add' && (
                      <label>Object
                        <select value={viAnnotateObjectId} onChange={(e) => setViAnnotateObjectId(e.target.value)}>
                          <option value="">select an object…</option>
                          {viObjectsList.map((o) => (
                            <option key={o.public_id} value={o.public_id}>{o.label} -- {o.public_id.slice(0, 12)}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {(viAnnotateAction === 'rename' || viAnnotateAction === 'correct_label' || viAnnotateAction === 'add') && (
                      <label>Label<input value={viAnnotateLabel} onChange={(e) => setViAnnotateLabel(e.target.value)} /></label>
                    )}
                    {viAnnotateAction === 'add' && (
                      <label>Image
                        <select value={viAnnotateImageId} onChange={(e) => setViAnnotateImageId(e.target.value)}>
                          <option value="">select an image…</option>
                          {viImagesList.map((img) => (
                            <option key={img.public_id} value={img.public_id}>page {img.page_number} #{img.image_index} -- {img.public_id.slice(0, 12)}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {viAnnotateAction === 'correct_caption' && (
                      <label>Caption<input value={viAnnotateCaption} onChange={(e) => setViAnnotateCaption(e.target.value)} /></label>
                    )}
                    {(viAnnotateAction === 'redraw_box' || viAnnotateAction === 'add') && (
                      <>
                        <label>Box x (0-1)<input value={viAnnotateBoxX} onChange={(e) => setViAnnotateBoxX(e.target.value)} /></label>
                        <label>Box y (0-1)<input value={viAnnotateBoxY} onChange={(e) => setViAnnotateBoxY(e.target.value)} /></label>
                        <label>Box width (0-1)<input value={viAnnotateBoxW} onChange={(e) => setViAnnotateBoxW(e.target.value)} /></label>
                        <label>Box height (0-1)<input value={viAnnotateBoxH} onChange={(e) => setViAnnotateBoxH(e.target.value)} /></label>
                      </>
                    )}
                    <Button type="submit" disabled={viBusy}>{viBusy ? 'Working…' : 'Apply annotation'}</Button>
                  </form>
                  <Button onClick={runViFinishAnnotation} disabled={viBusy}>Finish annotation stage</Button>
                </div>
              )}
              {viSessionData.annotation_report?.total_annotations !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.annotation_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'Knowledge Graph' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'knowledge_graph' && (
                <div className="notice">
                  <p>Relationships (contains/inside/overlaps/near) are derived purely from real bounding-box geometry -- never a semantic or causal claim about what the objects actually depict.</p>
                  <Button onClick={runViKnowledgeGraph} disabled={viBusy}>Build knowledge graph</Button>
                </div>
              )}
              {viSessionData.knowledge_graph_report?.node_count !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.knowledge_graph_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'QA' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'qa_generation' && (
                <div className="notice">
                  <p>Generates educational questions from admin-verified objects and caption -- always <code>verified: false</code>.</p>
                  <Button onClick={runViQaGeneration} disabled={viBusy}>Generate vision questions</Button>
                </div>
              )}
              {viSessionData.qa_report?.question_count !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.qa_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'Vision Draft' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'vision_dataset_draft' && (
                <div className="notice">
                  <p>Assembles image metadata, OCR, caption, bounding boxes, objects, QA, and the knowledge graph into one draft. Nothing is inserted into Dataset Studio -- always <code>verified: false</code>.</p>
                  <Button onClick={runViDatasetDraft} disabled={viBusy}>Build vision dataset draft</Button>
                </div>
              )}
              {viSessionData.vision_dataset_draft_report?.status && (
                <pre className="notice">{JSON.stringify(viSessionData.vision_dataset_draft_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'Report' && (
        <>
          {!viSessionData && <div className="notice">Select a vision cycle in Overview first.</div>}
          {viSessionData && (
            <>
              {viSessionData.stage === 'vision_quality_score' && (
                <div className="notice">
                  <Button onClick={runViQualityScore} disabled={viBusy}>Compute vision quality score</Button>
                </div>
              )}
              {viSessionData.vision_quality_score_report?.overall_vision_score !== undefined && (
                <pre className="notice">{JSON.stringify(viSessionData.vision_quality_score_report, null, 2)}</pre>
              )}
              {viSessionData.stage === 'vision_report' && (
                <div className="notice">
                  <Button onClick={runViGenerateReport} disabled={viBusy}>Generate vision report</Button>
                </div>
              )}
              {viSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Vision Report ready for review.</p>
                  <pre className="notice">{JSON.stringify(viSessionData.vision_report, null, 2)}</pre>
                  <Button onClick={() => runViAdminReview('approve')} disabled={viBusy}>Approve</Button>{' '}
                  <Button onClick={() => runViAdminReview('reject')} disabled={viBusy}>Reject</Button>{' '}
                  <Button onClick={() => runViAdminReview('request_fix')} disabled={viBusy}>Request Fix</Button>{' '}
                  <Button onClick={() => runViAdminReview('archive')} disabled={viBusy}>Archive</Button>
                </div>
              )}
              {viSessionData.stage === 'certified' && (
                <div className="notice">
                  <p>Vision Certified -- eligible for MB-15 Multimodal Dataset Generator, MB-16 Vision RAG, and MB-17 Multimodal Training Pipeline. This service never submits it to any of them automatically.</p>
                </div>
              )}
              {viSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Vision cycle closed with status <strong>{viSessionData.status}</strong>. No automatic action was taken.</p>
                </div>
              )}
            </>
          )}
        </>
      )}

      {viSubTab === 'History' && viSessionData && (
        <>
          <h4>Cycle events</h4>
          <ul className="notice">
            {viEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!viEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {viSubTab === 'History' && !viSessionData && (
        <div className="notice">Select a vision cycle in Overview first.</div>
      )}

      {viSubTab === 'Diagnostics' && (
        <>
          {viDiag && <pre className="notice">{JSON.stringify(viDiag, null, 2)}</pre>}
          {!viDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
