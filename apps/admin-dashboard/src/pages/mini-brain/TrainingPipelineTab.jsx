import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const tpSubTabs = [
  'Overview', 'Sources', 'Language', 'Vision', 'Tokenizer', 'Splits', 'Curriculum', 'Hardware',
  'Package', 'Report', 'History', 'Diagnostics',
]

export default function TrainingPipelineTab({
  tpSubTab, setTpSubTab,
  tpDiag, tpSessionData,
  tpSessionsList, tpSelectedId, selectTpSession, submitTpCreateSession, tpNewTopic, setTpNewTopic, tpBusy,
  tpEventsList,
  submitTpCollectDatasets, tpDatasetSessionIds, setTpDatasetSessionIds,
  submitTpCollectRagMemory, tpRagSessionIds, setTpRagSessionIds, tpAvailableRagMemory,
  runTpAnalyzeLanguage,
  runTpAnalyzeVision,
  runTpAnalyzeTokenizer,
  submitTpPlanSplits, tpSplitSeed, setTpSplitSeed,
  runTpPlanCurriculum,
  runTpEstimateHardware,
  runTpBuildPackage, tpPackagesList,
  runTpGenerateReport,
  runTpAdminReview,
  tpMemoryList,
}) {
  return (
    <>
      <p className="notice">
        MB-18 -- Multimodal Training Pipeline Center. A planning, validation, packaging, and
        reporting system only: it never starts a training job, never calls a training or
        quantization API, never creates a GGUF file, and never deploys or activates a runtime.
        It prepares a deterministic, checksummed package of JSON metadata files from
        already-certified MB-16 datasets and already-approved MB-17 grounded RAG memory. Package
        approval never implies model quality.
      </p>

      <div className="dataset-tabs">
        {tpSubTabs.map((t) => (
          <Button key={t} className={tpSubTab === t ? 'active' : ''} onClick={() => setTpSubTab(t)}>{t}</Button>
        ))}
      </div>

      {tpSubTab === 'Overview' && (
        <>
          {tpDiag && (
            <div className="notice">
              <p><strong>Training started:</strong> {String(tpDiag.training_started)} -- <strong>Runtime activated:</strong> {String(tpDiag.runtime_activated)} -- <strong>Model weights produced:</strong> {String(tpDiag.model_weights_produced)}</p>
              <p><strong>Requires certified datasets:</strong> {String(tpDiag.requires_certified_datasets)} -- <strong>Automatic approval:</strong> {String(tpDiag.automatic_approval)}</p>
            </div>
          )}
          {tpSessionData && (
            <section className="metric-grid">
              <StatusCard label="Topic" value={tpSessionData.topic.slice(0, 24)} tone="neutral" />
              <StatusCard label="Stage" value={tpSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={tpSessionData.status} tone={tpSessionData.status.includes('reject') ? 'waiting' : tpSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Training pipeline sessions</h4>
              <ul className="notice">
                {tpSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={tpSelectedId === s.public_id ? 'active' : ''} onClick={() => selectTpSession(s.public_id)}>
                      {s.topic.slice(0, 30)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!tpSessionsList.length && <li>No training pipeline sessions yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitTpCreateSession}>
                <label>Topic<input value={tpNewTopic} onChange={(e) => setTpNewTopic(e.target.value)} placeholder="Mountain scene multimodal package" /></label>
                <Button type="submit" disabled={tpBusy || !tpNewTopic.trim()}>{tpBusy ? 'Working…' : 'Create session'}</Button>
              </form>
            </div>
            <div>
              {!tpSessionData && <div className="notice">Select or start a session to work through it in the other sub-tabs.</div>}
              {tpSessionData && (
                <>
                  <h4>Session events</h4>
                  <ul className="notice">
                    {tpEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!tpEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {tpSubTab === 'Sources' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'collect_datasets' && (
                <form className="inline-form training-form" onSubmit={submitTpCollectDatasets}>
                  <label>MB-16 certified dataset session public ID(s), comma-separated
                    <input value={tpDatasetSessionIds} onChange={(e) => setTpDatasetSessionIds(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={tpBusy || !tpDatasetSessionIds.trim()}>Collect certified datasets</Button>
                </form>
              )}
              {tpSessionData.dataset_collection_report?.ready !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.dataset_collection_report, null, 2)}</pre>
              )}

              {tpSessionData.stage === 'collect_rag_memory' && (
                <form className="inline-form training-form" onSubmit={submitTpCollectRagMemory}>
                  <label>MB-17 approved RAG session public ID(s), comma-separated, optional
                    <input value={tpRagSessionIds} onChange={(e) => setTpRagSessionIds(e.target.value)} />
                  </label>
                  <Button type="submit" disabled={tpBusy}>Collect grounded RAG memory</Button>
                </form>
              )}
              {tpSessionData.rag_memory_collection_report?.accepted_count !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.rag_memory_collection_report, null, 2)}</pre>
              )}

              <h4>Available approved MB-17 RAG memory</h4>
              <ul className="notice">
                {tpAvailableRagMemory.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- "{m.query?.slice(0, 40)}" -- {m.admin_decision} -- confidence {m.confidence}</li>
                ))}
                {!tpAvailableRagMemory.length && <li>No approved RAG memory recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {tpSubTab === 'Language' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'analyze_language' && (
                <div className="notice">
                  <Button onClick={runTpAnalyzeLanguage} disabled={tpBusy}>Analyze language distribution</Button>
                </div>
              )}
              {tpSessionData.language_distribution_report?.session_count !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.language_distribution_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {tpSubTab === 'Vision' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'analyze_vision' && (
                <div className="notice">
                  <p>Aggregates MB-14's own real image metadata and MB-17's own confidence/hallucination fields -- no new detection or retrieval pass.</p>
                  <Button onClick={runTpAnalyzeVision} disabled={tpBusy}>Analyze vision &amp; grounding coverage</Button>
                </div>
              )}
              {tpSessionData.image_statistics_report?.image_count !== undefined && (
                <>
                  <h4>Image statistics</h4>
                  <pre className="notice">{JSON.stringify(tpSessionData.image_statistics_report, null, 2)}</pre>
                </>
              )}
              {tpSessionData.grounding_quality_report?.query_count !== undefined && (
                <>
                  <h4>Grounding quality</h4>
                  <pre className="notice">{JSON.stringify(tpSessionData.grounding_quality_report, null, 2)}</pre>
                </>
              )}
            </>
          )}
        </>
      )}

      {tpSubTab === 'Tokenizer' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'analyze_tokenizer' && (
                <div className="notice">
                  <p>No tokenizer model is loaded -- character-level and Unicode-category analysis only.</p>
                  <Button onClick={runTpAnalyzeTokenizer} disabled={tpBusy}>Analyze tokenizer coverage</Button>
                </div>
              )}
              {tpSessionData.tokenizer_coverage_report?.total_character_count !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.tokenizer_coverage_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {tpSubTab === 'Splits' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'plan_splits' && (
                <form className="inline-form training-form" onSubmit={submitTpPlanSplits}>
                  <label>Seed (optional, deterministic if repeated)<input value={tpSplitSeed} onChange={(e) => setTpSplitSeed(e.target.value)} placeholder="20260101" /></label>
                  <Button type="submit" disabled={tpBusy}>Plan dataset splits</Button>
                </form>
              )}
              {tpSessionData.splits_report?.seed !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.splits_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {tpSubTab === 'Curriculum' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'plan_curriculum' && (
                <div className="notice">
                  <Button onClick={runTpPlanCurriculum} disabled={tpBusy}>Plan curriculum &amp; training recipe</Button>
                </div>
              )}
              {tpSessionData.curriculum_report?.stage_count !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.curriculum_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {tpSubTab === 'Hardware' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'estimate_hardware' && (
                <div className="notice">
                  <p>All estimates are explicitly marked heuristic -- no benchmark is executed.</p>
                  <Button onClick={runTpEstimateHardware} disabled={tpBusy}>Estimate hardware &amp; storage</Button>
                </div>
              )}
              {tpSessionData.hardware_estimate_report?.estimated_token_count !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.hardware_estimate_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {tpSubTab === 'Package' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'build_package' && (
                <div className="notice">
                  <p>Writes deterministic JSON metadata files only -- never model weights -- to this session's own artifact directory, with a SHA-256 checksum recorded for every file.</p>
                  <Button onClick={runTpBuildPackage} disabled={tpBusy}>Build training package</Button>
                </div>
              )}
              {tpSessionData.package_manifest?.artifact_count !== undefined && (
                <pre className="notice">{JSON.stringify(tpSessionData.package_manifest, null, 2)}</pre>
              )}
              <h4>Package artifacts ({tpPackagesList.length})</h4>
              <ul className="notice">
                {tpPackagesList.map((p) => (
                  <li key={p.public_id}>{p.artifact_name} -- {p.file_size_bytes} bytes -- sha256={p.sha256.slice(0, 16)}…</li>
                ))}
                {!tpPackagesList.length && <li>No artifacts written yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {tpSubTab === 'Report' && (
        <>
          {!tpSessionData && <div className="notice">Select a session in Overview first.</div>}
          {tpSessionData && (
            <>
              {tpSessionData.stage === 'generate_report' && (
                <div className="notice">
                  <Button onClick={runTpGenerateReport} disabled={tpBusy}>Generate training readiness report</Button>
                </div>
              )}
              {tpSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Training Readiness Report ready for review. No training has been executed by this
                  service -- package approval does not imply model quality.</p>
                  <pre className="notice">{JSON.stringify(tpSessionData.readiness_report, null, 2)}</pre>

                  <h4>Final decision</h4>
                  <Button onClick={() => runTpAdminReview('approve')} disabled={tpBusy}>Approve</Button>{' '}
                  <Button onClick={() => runTpAdminReview('reject')} disabled={tpBusy}>Reject</Button>{' '}
                  <Button onClick={() => runTpAdminReview('archive')} disabled={tpBusy}>Archive</Button>
                </div>
              )}
              {tpSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Session closed with status <strong>{tpSessionData.status}</strong>. Permanent pipeline memory recorded.</p>
                </div>
              )}

              <h4>Training pipeline memory (permanent)</h4>
              <ul className="notice">
                {tpMemoryList.map((m) => (
                  <li key={m.public_id}>{m.created_at} -- "{m.topic.slice(0, 40)}" -- {m.admin_decision} -- readiness {m.readiness_score}</li>
                ))}
                {!tpMemoryList.length && <li>No pipeline memory recorded yet.</li>}
              </ul>
            </>
          )}
        </>
      )}

      {tpSubTab === 'History' && tpSessionData && (
        <>
          <h4>Session events</h4>
          <ul className="notice">
            {tpEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!tpEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {tpSubTab === 'History' && !tpSessionData && (
        <div className="notice">Select a session in Overview first.</div>
      )}

      {tpSubTab === 'Diagnostics' && (
        <>
          {tpDiag && <pre className="notice">{JSON.stringify(tpDiag, null, 2)}</pre>}
          {!tpDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
