import Button from '../../components/Button.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const diSubTabs = ['Overview', 'Quality', 'Language', 'Domain', 'Training', 'RAG', 'SFT', 'Recommendations', 'Reports', 'Diagnostics']
const advancedSubTabs = ['Overview', 'Conflict', 'Bias', 'Coverage', 'Difficulty', 'Curriculum', 'Knowledge Gaps', 'Risk', 'Priority', 'Report', 'Diagnostics']

export default function DatasetIntelligenceTab({
  runDatasetIntelligenceReport, diSourceId, setDiSourceId, diBusy,
  diSubTab, setDiSubTab, diReport, diDiagnostics,
  toggleAdvanced, showAdvanced, advBusy, runAdvancedReport,
  advSubTab, setAdvSubTab, advReport, advDiagnostics,
}) {
  return (
    <>
      <p className="notice">
        MB-05 -- Brud Mini Brain as an Admin Dataset Expert. Analysis only: never modifies, approves,
        deletes, or trains anything. Every check below is deterministic and reuses Dataset Studio's
        own existing, unmodified read APIs and quality/language/duplicate services.
      </p>

      <form className="inline-form training-form" onSubmit={runDatasetIntelligenceReport}>
        <label>Dataset source public ID<input value={diSourceId} onChange={(e) => setDiSourceId(e.target.value)} placeholder="source public_id from Dataset Studio" /></label>
        <Button type="submit" disabled={diBusy || !diSourceId}>{diBusy ? 'Analyzing…' : 'Run full report'}</Button>
      </form>

      <div className="dataset-tabs">
        {diSubTabs.map((value) => (
          <Button key={value} className={diSubTab === value ? 'active' : ''} onClick={() => setDiSubTab(value)}>{value}</Button>
        ))}
      </div>

      {diSubTab === 'Overview' && diReport && (
        <>
          <section className="metric-grid">
            <StatusCard label="Overall status" value={diReport.overall_status} tone={diReport.overall_status === 'Ready' ? 'good' : diReport.overall_status === 'Not Ready' ? 'waiting' : 'neutral'} />
            <StatusCard label="Overall score" value={diReport.scores.overall.score} tone="neutral" />
            <StatusCard label="Records analyzed" value={diReport.records_analyzed} tone="neutral" />
            <StatusCard label="Record type" value={Object.keys(diReport.dataset_summary.by_record_type)[0] ?? '--'} tone="neutral" />
            <StatusCard label="Processing time" value={`${Math.round(diReport.processing_time_ms)} ms`} tone="good" />
          </section>
          <h4>Warnings</h4>
          <div className="notice">
            <ul>{diReport.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
            {!diReport.warnings.length && <p>No warnings.</p>}
          </div>
          <h4>Dataset summary</h4>
          <pre className="notice">{JSON.stringify(diReport.dataset_summary, null, 2)}</pre>
        </>
      )}

      {diSubTab === 'Quality' && diReport && (
        <>
          <section className="metric-grid">
            <StatusCard label="Clean ratio" value={diReport.quality_report.clean_ratio} tone={diReport.quality_report.clean_ratio >= 0.85 ? 'good' : 'waiting'} />
            <StatusCard label="Flagged records" value={diReport.quality_report.flagged_records} tone="neutral" />
            <StatusCard label="Empty content" value={diReport.quality_report.empty_content_records} tone="neutral" />
            <StatusCard label="Broken references" value={diReport.quality_report.broken_reference_records} tone="neutral" />
          </section>
          <h4>Issue counts</h4>
          <pre className="notice">{JSON.stringify(diReport.quality_report.issue_counts, null, 2)}</pre>
          <h4>Duplicates</h4>
          <pre className="notice">{JSON.stringify(diReport.duplicates, null, 2)}</pre>
        </>
      )}

      {diSubTab === 'Language' && diReport && (
        <>
          <section className="metric-grid">
            {Object.entries(diReport.language_report.distribution_percentages).map(([lang, pct]) => (
              <StatusCard key={lang} label={lang} value={`${pct}%`} tone="neutral" />
            ))}
          </section>
          <h4>Token estimation (heuristic, not a real tokenizer)</h4>
          <pre className="notice">{JSON.stringify(diReport.language_report.token_estimation, null, 2)}</pre>
        </>
      )}

      {diSubTab === 'Domain' && diReport && (
        <>
          <section className="metric-grid">
            <StatusCard label="Classified as" value={diReport.domain.category} tone="good" />
          </section>
          <div className="notice"><p>{diReport.domain.reason}</p></div>
          <h4>Topic scores</h4>
          <pre className="notice">{JSON.stringify(diReport.domain.topic_scores, null, 2)}</pre>
        </>
      )}

      {diSubTab === 'Training' && diReport && (
        <>
          <section className="metric-grid">
            <StatusCard label="Status" value={diReport.training_report.status} tone={diReport.training_report.status === 'Ready' ? 'good' : diReport.training_report.status === 'Not Ready' ? 'waiting' : 'neutral'} />
          </section>
          <ul>{diReport.training_report.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </>
      )}

      {diSubTab === 'RAG' && diReport && (
        <>
          <section className="metric-grid">
            <StatusCard label="Status" value={diReport.rag_report.status} tone={diReport.rag_report.status === 'Ready' ? 'good' : diReport.rag_report.status === 'Not Ready' ? 'waiting' : 'neutral'} />
            <StatusCard label="Chunk suitability" value={diReport.rag_report.chunk_suitability_ratio} tone="neutral" />
            <StatusCard label="Citation readiness" value={diReport.rag_report.citation_readiness_ratio} tone="neutral" />
          </section>
          <ul>{diReport.rag_report.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="notice">{diReport.rag_report.missing_titles}</p>
        </>
      )}

      {diSubTab === 'SFT' && diReport && (
        <>
          <section className="metric-grid">
            <StatusCard label="Status" value={diReport.sft_report.status} tone={diReport.sft_report.status === 'Ready' ? 'good' : diReport.sft_report.status === 'Not Ready' ? 'waiting' : 'neutral'} />
            <StatusCard label="Instruction quality" value={diReport.sft_report.instruction_quality_ratio} tone="neutral" />
            <StatusCard label="Answer completeness" value={diReport.sft_report.answer_completeness_ratio} tone="neutral" />
          </section>
          <ul>{diReport.sft_report.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </>
      )}

      {diSubTab === 'Recommendations' && diReport && (
        <div className="data-list">
          {diReport.recommendations.map((rec, i) => (
            <article key={i}>
              <strong>[{rec.priority}] {rec.category}</strong> — {rec.recommendation}
              <div><small>Why: {rec.reason}</small></div>
            </article>
          ))}
          {!diReport.recommendations.length && <div className="notice">No recommendations -- dataset looks clean.</div>}
        </div>
      )}

      {diSubTab === 'Reports' && diReport && (
        <>
          <h4>Every score (formula, calculation, reason)</h4>
          <pre className="notice">{JSON.stringify(diReport.scores, null, 2)}</pre>
        </>
      )}

      {diSubTab === 'Diagnostics' && diDiagnostics && (
        <section className="metric-grid">
          <StatusCard label="AI model used" value={String(diDiagnostics.ai_model_used)} tone={diDiagnostics.ai_model_used ? 'waiting' : 'good'} />
          <StatusCard label="Writes performed" value={diDiagnostics.writes_performed} tone="good" />
          <StatusCard label="Max records/analysis" value={diDiagnostics.max_records_per_analysis} tone="neutral" />
          <StatusCard label="Pipeline stages" value={diDiagnostics.pipeline_stages.length} tone="neutral" />
        </section>
      )}

      {!diReport && diSubTab !== 'Diagnostics' && (
        <div className="notice">Enter a dataset source public ID above and run a report to see results here.</div>
      )}

      <hr />
      <h3>Advanced Dataset Intelligence <small>(MB-05.1)</small></h3>
      <p className="notice">
        MB-05.1 -- conflicts, bias, coverage, difficulty, curriculum sequencing, knowledge gaps, and
        PII/secret risk. Read-only, deterministic, reuses MB-05's own outputs above without changing
        it. Uses the same source ID entered above.
      </p>
      <div className="form-row">
        <Button onClick={toggleAdvanced}>{showAdvanced ? 'Hide advanced section' : 'Show advanced section'}</Button>
      </div>

      {showAdvanced && (
        <>
          <form className="inline-form training-form" onSubmit={runAdvancedReport}>
            <Button type="submit" disabled={advBusy || !diSourceId}>{advBusy ? 'Analyzing…' : 'Run advanced report'}</Button>
          </form>

          <div className="dataset-tabs">
            {advancedSubTabs.map((value) => (
              <Button key={value} className={advSubTab === value ? 'active' : ''} onClick={() => setAdvSubTab(value)}>{value}</Button>
            ))}
          </div>

          {advSubTab === 'Overview' && advReport && (
            <section className="metric-grid">
              <StatusCard label="Overall score" value={advReport.scores.overall.score} tone="neutral" />
              <StatusCard label="Conflicts" value={advReport.conflicts.conflict_count} tone={advReport.conflicts.conflict_count ? 'waiting' : 'good'} />
              <StatusCard label="Risk items" value={advReport.risk.risk_item_count} tone={advReport.risk.risk_item_count ? 'waiting' : 'good'} />
              <StatusCard label="Records analyzed" value={advReport.records_analyzed} tone="neutral" />
              <StatusCard label="Processing time" value={`${Math.round(advReport.processing_time_ms)} ms`} tone="good" />
            </section>
          )}

          {advSubTab === 'Conflict' && advReport && (
            <div className="data-list">
              {advReport.conflicts.conflict_groups.map((group, i) => (
                <article key={i}>
                  <strong>{group.question_preview}</strong>
                  <div><small>Answers: {group.distinct_answers.join(' | ')}</small></div>
                </article>
              ))}
              {!advReport.conflicts.conflict_groups.length && <div className="notice">No conflicts found.</div>}
            </div>
          )}

          {advSubTab === 'Bias' && advReport && (
            <pre className="notice">{JSON.stringify(advReport.bias, null, 2)}</pre>
          )}

          {advSubTab === 'Coverage' && advReport && (
            <pre className="notice">{JSON.stringify(advReport.coverage, null, 2)}</pre>
          )}

          {advSubTab === 'Difficulty' && advReport && (
            <section className="metric-grid">
              {Object.entries(advReport.difficulty.distribution).map(([level, count]) => (
                <StatusCard key={level} label={level} value={count} tone="neutral" />
              ))}
            </section>
          )}

          {advSubTab === 'Curriculum' && advReport && (
            <div className="data-list">
              {advReport.curriculum.topics.map((t, i) => (
                <article key={i}>
                  <strong>{t.domain} / {t.subtopic}</strong> — {t.verdict}
                  <div><small>{t.reason}</small></div>
                </article>
              ))}
            </div>
          )}

          {advSubTab === 'Knowledge Gaps' && advReport && (
            <div className="data-list">
              {advReport.knowledge_gaps.missing_topics.map((g, i) => (
                <article key={i}><strong>{g.topic}</strong><div><small>{g.reason}</small></div></article>
              ))}
            </div>
          )}

          {advSubTab === 'Risk' && advReport && (
            <>
              <section className="metric-grid">
                <StatusCard label="Risk score" value={advReport.risk.risk_score} tone={advReport.risk.risk_score ? 'waiting' : 'good'} />
              </section>
              <pre className="notice">{JSON.stringify(advReport.risk.category_counts, null, 2)}</pre>
            </>
          )}

          {advSubTab === 'Priority' && advReport && (
            <div className="data-list">
              {advReport.priorities.map((p, i) => (
                <article key={i}>
                  <strong>[{p.priority}] {p.issue}</strong>
                  <div><small>Why: {p.why} — Impact: {p.impact}</small></div>
                </article>
              ))}
            </div>
          )}

          {advSubTab === 'Report' && advReport && (
            <pre className="notice">{JSON.stringify(advReport.scores, null, 2)}</pre>
          )}

          {advSubTab === 'Diagnostics' && advDiagnostics && (
            <section className="metric-grid">
              <StatusCard label="AI model used" value={String(advDiagnostics.ai_model_used)} tone={advDiagnostics.ai_model_used ? 'waiting' : 'good'} />
              <StatusCard label="Writes performed" value={advDiagnostics.writes_performed} tone="good" />
              <StatusCard label="Pipeline stages" value={advDiagnostics.pipeline_stages.length} tone="neutral" />
            </section>
          )}

          {!advReport && advSubTab !== 'Diagnostics' && (
            <div className="notice">Run the advanced report above to see results here.</div>
          )}
        </>
      )}
    </>
  )
}
