import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const liSubTabs = [
  'Overview', 'Language Scan', 'Unicode & Character', 'Spell & Grammar', 'OCR', 'Tanglish',
  'Translation', 'Dataset Draft', 'Quality & Report', 'History', 'Diagnostics',
]

export default function LanguageIntelligenceTab({
  liSubTab, setLiSubTab,
  liDiag, liSessionData,
  liSessionsList, liSelectedId, selectLiSession, submitLiCreateSession, liNewSourceId, setLiNewSourceId, liBusy,
  liEventsList,
  runLiLanguageScan,
  runLiUnicodeValidation,
  runLiSpellAnalysis,
  runLiGrammarAnalysis,
  runLiOcrAnalysis,
  runLiTanglishAnalysis,
  runLiTranslationAnalysis,
  runLiDatasetDraft,
  runLiQualityScore,
  runLiGenerateReport,
  runLiAdminReview,
}) {
  return (
    <>
      <p className="notice">
        MB-13 -- Language Intelligence &amp; Dataset Normalization Center. Not a spell checker,
        OCR engine, translator, dataset generator, or Training Engine. It validates, normalizes,
        scores, and certifies a dataset's language quality before RAG or Training. It never edits
        a dataset record, never starts training, and never deploys -- every action requires
        explicit admin approval, and every check reuses this codebase's own existing Tamil/
        Unicode/Tanglish utilities rather than a second implementation.
      </p>

      <div className="dataset-tabs">
        {liSubTabs.map((t) => (
          <Button key={t} className={liSubTab === t ? 'active' : ''} onClick={() => setLiSubTab(t)}>{t}</Button>
        ))}
      </div>

      {liSubTab === 'Overview' && (
        <>
          {liDiag && (
            <div className="notice">
              <p><strong>Dataset writes performed:</strong> {String(liDiag.dataset_writes_performed)} -- Dataset Studio remains the only place a dataset is actually written.</p>
              <p><strong>Training started:</strong> {String(liDiag.training_started)} -- <strong>RAG called:</strong> {String(liDiag.rag_called)} -- <strong>Automatic approval:</strong> {String(liDiag.automatic_approval)}</p>
            </div>
          )}
          {liSessionData && (
            <section className="metric-grid">
              <StatusCard label="Dataset source" value={liSessionData.dataset_source_public_id.slice(0, 12)} tone="neutral" />
              <StatusCard label="Stage" value={liSessionData.stage} tone="neutral" />
              <StatusCard label="Status" value={liSessionData.status} tone={liSessionData.status.includes('reject') ? 'waiting' : liSessionData.status.startsWith('admin_') ? 'good' : 'neutral'} />
            </section>
          )}
          <div className="training-grid">
            <div>
              <h4>Language cycles</h4>
              <ul className="notice">
                {liSessionsList.map((s) => (
                  <li key={s.public_id}>
                    <Button className={liSelectedId === s.public_id ? 'active' : ''} onClick={() => selectLiSession(s.public_id)}>
                      {s.dataset_source_public_id.slice(0, 10)} -- {s.stage} ({s.status})
                    </Button>
                  </li>
                ))}
                {!liSessionsList.length && <li>No language cycles yet.</li>}
              </ul>
              <form className="inline-form training-form" onSubmit={submitLiCreateSession}>
                <label>Dataset source public ID<input value={liNewSourceId} onChange={(e) => setLiNewSourceId(e.target.value)} placeholder="source public_id from Dataset Studio" /></label>
                <Button type="submit" disabled={liBusy || !liNewSourceId.trim()}>{liBusy ? 'Working…' : 'Start language cycle'}</Button>
              </form>
            </div>
            <div>
              {!liSessionData && <div className="notice">Select or start a language cycle to work through it in the other sub-tabs.</div>}
              {liSessionData && (
                <>
                  <h4>Cycle events</h4>
                  <ul className="notice">
                    {liEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
                    {!liEventsList.length && <li>No events yet.</li>}
                  </ul>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {liSubTab === 'Language Scan' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'language_scan' && (
                <div className="notice">
                  <p>Reuses MB-05's real language distribution (Tamil/English/Tanglish/Mixed) for this dataset.</p>
                  <Button onClick={runLiLanguageScan} disabled={liBusy}>Run language scan</Button>
                </div>
              )}
              {liSessionData.language_scan_report?.dominant_language && (
                <pre className="notice">{JSON.stringify(liSessionData.language_scan_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'Unicode & Character' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'unicode_validation' && (
                <div className="notice">
                  <p>Reuses core_model.corpus.unicode_normalization (replacement/mojibake/combining-mark checks) and the Tamil Fluency Validator's orphan vowel-sign detection.</p>
                  <Button onClick={runLiUnicodeValidation} disabled={liBusy}>Run Unicode &amp; Tamil character validation</Button>
                </div>
              )}
              {liSessionData.unicode_report?.unicode_score !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.unicode_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'Spell & Grammar' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'spell_analysis' && (
                <div className="notice">
                  <p>Matches text against the existing, admin-curated Document Tamil Correction Registry's active rules only -- never a fabricated dictionary.</p>
                  <Button onClick={runLiSpellAnalysis} disabled={liBusy}>Run spell analysis</Button>
                </div>
              )}
              {liSessionData.spell_report?.spell_score !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.spell_report, null, 2)}</pre>
              )}
              {liSessionData.stage === 'grammar_analysis' && (
                <div className="notice">
                  <p>Script-structural heuristics only -- real grammatical analysis (verb agreement, gender, number, case, tense) is honestly NOT implemented; see disclosure in the result.</p>
                  <Button onClick={runLiGrammarAnalysis} disabled={liBusy}>Run grammar &amp; sentence quality analysis</Button>
                </div>
              )}
              {liSessionData.grammar_report?.grammar_confidence !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.grammar_report, null, 2)}</pre>
              )}
              {liSessionData.sentence_quality_report?.naturalness_score !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.sentence_quality_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'OCR' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'ocr_analysis' && (
                <div className="notice">
                  <p>Never edits automatically -- only reports possible OCR mistakes with a confidence band and suggested correction. An admin must apply any accepted correction manually through Dataset Studio.</p>
                  <Button onClick={runLiOcrAnalysis} disabled={liBusy}>Run OCR correction planning</Button>
                </div>
              )}
              {liSessionData.ocr_report?.ocr_score !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.ocr_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'Tanglish' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'tanglish_analysis' && (
                <div className="notice">
                  <p>Tanglish -&gt; Tamil (existing MB-04A dictionary) and Tamil -&gt; Tanglish (existing Phase 10A phonetic transliterator) -- never overwrites the original text.</p>
                  <Button onClick={runLiTanglishAnalysis} disabled={liBusy}>Run Tanglish analysis</Button>
                </div>
              )}
              {liSessionData.tanglish_report?.forward && (
                <pre className="notice">{JSON.stringify(liSessionData.tanglish_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'Translation' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'translation_analysis' && (
                <div className="notice">
                  <p>No Tamil&lt;-&gt;English translation engine exists in this codebase -- this only validates already-claimed pairs (none, for a monolingual dataset), never invents a translation.</p>
                  <Button onClick={runLiTranslationAnalysis} disabled={liBusy}>Run translation analysis</Button>
                </div>
              )}
              {liSessionData.translation_report?.pairs_analyzed !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.translation_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'Dataset Draft' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'dataset_draft_generation' && (
                <div className="notice">
                  <p>For a Tamil-dominant dataset: a real Tanglish draft (deterministic transliteration). No English draft is ever fabricated -- no translation engine exists. Always <code>verified: false</code>.</p>
                  <Button onClick={runLiDatasetDraft} disabled={liBusy}>Generate language dataset draft</Button>
                </div>
              )}
              {liSessionData.dataset_draft_report?.applicable !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.dataset_draft_report, null, 2)}</pre>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'Quality & Report' && (
        <>
          {!liSessionData && <div className="notice">Select a language cycle in Overview first.</div>}
          {liSessionData && (
            <>
              {liSessionData.stage === 'language_quality_score' && (
                <div className="notice">
                  <Button onClick={runLiQualityScore} disabled={liBusy}>Compute language quality score</Button>
                </div>
              )}
              {liSessionData.quality_score_report?.overall_language_quality !== undefined && (
                <pre className="notice">{JSON.stringify(liSessionData.quality_score_report, null, 2)}</pre>
              )}
              {liSessionData.stage === 'language_report' && (
                <div className="notice">
                  <Button onClick={runLiGenerateReport} disabled={liBusy}>Generate language report</Button>
                </div>
              )}
              {liSessionData.stage === 'awaiting_admin_review' && (
                <div className="notice">
                  <p>Language Report ready for review.</p>
                  <pre className="notice">{JSON.stringify(liSessionData.language_report, null, 2)}</pre>
                  <Button onClick={() => runLiAdminReview('approve')} disabled={liBusy}>Approve</Button>{' '}
                  <Button onClick={() => runLiAdminReview('reject')} disabled={liBusy}>Reject</Button>{' '}
                  <Button onClick={() => runLiAdminReview('request_fix')} disabled={liBusy}>Request Fix</Button>{' '}
                  <Button onClick={() => runLiAdminReview('archive')} disabled={liBusy}>Archive</Button>
                </div>
              )}
              {liSessionData.stage === 'certified' && (
                <div className="notice">
                  <p>Language Certified -- eligible for MB-11 Dataset Evolution, RAG Sandbox, and MB-06 Learning Supervisor. This service never submits it to any of them automatically.</p>
                </div>
              )}
              {liSessionData.stage === 'closed' && (
                <div className="notice">
                  <p>Language cycle closed with status <strong>{liSessionData.status}</strong>. No automatic action was taken.</p>
                </div>
              )}
            </>
          )}
        </>
      )}

      {liSubTab === 'History' && liSessionData && (
        <>
          <h4>Cycle events</h4>
          <ul className="notice">
            {liEventsList.map((e) => <li key={e.public_id}>{e.created_at} -- {e.event_type} -- {e.message}</li>)}
            {!liEventsList.length && <li>No events yet.</li>}
          </ul>
        </>
      )}
      {liSubTab === 'History' && !liSessionData && (
        <div className="notice">Select a language cycle in Overview first.</div>
      )}

      {liSubTab === 'Diagnostics' && (
        <>
          {liDiag && <pre className="notice">{JSON.stringify(liDiag, null, 2)}</pre>}
          {!liDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
